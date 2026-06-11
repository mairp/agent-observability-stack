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
      "captureContent": { "enabled": false }   // never export prompt/response bodies
    }
  }
  ```
- **`diagnostics-prometheus`** — serves `GET /api/diagnostics/prometheus` (gateway-auth). Because the
  gateway is firewalled to the LAN, a host-side script (`exporters/openclaw_textfile.sh`) scrapes it
  over **loopback** with the gateway token and republishes it through the node_exporter textfile
  collector. It also emits `openclaw_diagnostics_up` as a liveness signal.

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
