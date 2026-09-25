# Agent observability

## What's wired
The OpenClaw gateway runs two official diagnostics plugins:

- **`diagnostics-otel`** — pushes **traces** over OTLP/HTTP to the collector. Enabled via the top-level
  `diagnostics` block in `openclaw.json`:
  ```jsonc
  "diagnostics": {
    "enabled": true,
    "otel": {
      "enabled": true,
      "endpoint": "http://127.0.0.1:4318",
      "protocol": "http/protobuf",
      "serviceName": "openclaw-gateway",
      "traces": true,
      "metrics": false,                 // metrics come via the loopback scrape (below)
      "captureContent": {               // export prompt/response bodies (on since 2026-09-25)
        "enabled": true,
        "inputMessages": true,
        "outputMessages": true,
        "toolInputs": true,
        "toolOutputs": true,
        "systemPrompt": true,
        "toolDefinitions": true
      }
    }
  }
  ```
  With content on, `openclaw.model.call` spans carry `gen_ai.input.messages`, `gen_ai.output.messages`,
  `gen_ai.system_instructions`, `gen_ai.tool.definitions` and `openclaw.content.*` (each value capped
  at 128 KiB and passed through the gateway's secret redaction). They land in Tempo and Phoenix, which
  is open on the LAN without auth (see the README "Phoenix" section). To turn it off, set
  `"captureContent": { "enabled": false }`. The gateway restarts itself on any `diagnostics.*` change.
- **`diagnostics-prometheus`** — serves `GET /api/diagnostics/prometheus` (gateway-auth). Because the
  gateway is firewalled to the LAN, a host-side script (`exporters/openclaw_textfile.sh`) scrapes it
  over **loopback** with the gateway token and republishes it through the node_exporter textfile
  collector. It also emits `openclaw_diagnostics_up` as a liveness signal.
  It runs every 15 s from `systemd/openclaw-textfile.{service,timer}`:
  ```bash
  sudo cp systemd/openclaw-textfile.{service,timer} /etc/systemd/system/   # adjust ExecStart path
  sudo systemctl enable --now openclaw-textfile.timer
  ```
  Watch `time() - node_textfile_mtime_seconds{file=~".*openclaw.prom"}`: if nothing runs the
  script, the file goes stale but still says `openclaw_diagnostics_up 1`.

> **Trust gate:** both diagnostics plugins get the gateway's internal diagnostics events only
> when they are **bundled** or an **official npm install with an install record**. A copy placed by
> hand in `~/.openclaw/extensions/` loads but logs `internal diagnostics capability unavailable`
> and exports nothing (no traces, empty `/api/diagnostics/prometheus`). Install them with the
> gateway's own CLI (it picks the newest version compatible with the runtime), then restart:
> `openclaw plugins install @openclaw/diagnostics-otel --force` (same for `diagnostics-prometheus`).

## Metric sources (by intent)
| Want                         | Metric / source |
|------------------------------|-----------------|
| Model call latency p50/p95   | `openclaw_model_call_duration_seconds_bucket` (by `model`) |
| Call volume & outcomes       | `openclaw_model_call_total{outcome,error_category,model}` |
| Tokens (in/out/cached/reason)| `litellm_*_tokens_metric_total` (by `model`) |
| Spend / cost                 | `litellm_spend_metric_total` (by `model`) |
| Prompt cache hit ratio       | `litellm_input_cached_tokens_metric_total / litellm_input_tokens_metric_total` |
| Per-agent / per-run drill-in | **Tempo traces** (service `openclaw-gateway`) |
| Agent inventory              | `openclaw_agent_info`, `openclaw_agents_total` (from onboarding) |

> Note: in this OpenClaw release, model metrics are labeled by `model`/`provider`/`outcome`, **not**
> by agent. Per-agent attribution is via **traces**; cost/token aggregates are by model (all agents
> route through one LiteLLM key). The agent **inventory** metric gives at-a-glance per-agent presence.

## LiteLLM
Enable Prometheus in `config.yaml`:
```yaml
litellm_settings:
  callbacks: ["prometheus"]
```
`/metrics/` is bearer-auth guarded; Prometheus scrapes it with the master key
(`secrets/litellm_token`, rendered from `.env`).

## Claude Code (separate from OpenClaw)
Claude Code emits its **own** OTel telemetry. **Enable it in the shell env** — put
`CLAUDE_CODE_ENABLE_TELEMETRY=1` plus the `OTEL_*` exports (endpoint `http://localhost:4318`,
`http/protobuf`, `service.name=claude-code`) in **`~/.bashrc`**, then restart the session. The
`~/.claude/settings.json` `env` block is **not** honored by the telemetry exporter — this is the #1
"metrics show 0" gotcha. See the README for the exact block.

The **Claude Code** dashboard is built on the per-request **`api_request` events in Loki**
(`{service_name="claude-code"}`: `cost_usd`, `*_tokens`, `model`, `duration_ms`) and the
**`subagent_completed` events** (`agent_type`, `model`, `total_tokens`) — so it breaks consumption down
by model, by token type, and by **named subagent** (Explore/Plan/…), with persistent history. The OTLP
`claude_code_*` metrics are intentionally **not** used: they're ephemeral (expire ~5 min after a session)
and short sessions exit before the 10s metric flush, whereas the log events export immediately and persist.
The **LLM Cost & Consumption** dashboard sums Claude Code (Loki) + OpenClaw/LiteLLM (metrics) spend.
See [dashboards.md](dashboards.md).
