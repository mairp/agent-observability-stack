# agent-observability-stack

A self-hostable observability stack for **LLM agents + a Linux host (Intel iGPU/NPU + NVIDIA GPU aware)**,
built as a single LAN-accessible pane of glass. Two pipelines, one Grafana:

- **Infra metrics (pull):** CPU, RAM, disk, network + latency, containers, and **accelerator** telemetry —
  **Intel iGPU/NPU** and **NVIDIA GPU** (`nvidia-smi`: util, VRAM incl. per-process, temp, power, clocks) →
  Prometheus.
- **Agent telemetry (push):** [OpenClaw](https://openclaw.ai) diagnostics → OTLP → OpenTelemetry
  Collector → **Grafana Tempo** (traces) + Prometheus (metrics); LLM **tokens, cost, latency, cache**
  from a [LiteLLM](https://litellm.ai) proxy; and **local llama.cpp inference** (`/metrics`: decode/prefill
  tok/s, queue depth, and an **MTP speculative-decoding** acceptance signal).

New agents, containers, and accelerators **onboard themselves** — no per-target config edits.

## Demo

Full walkthrough (~72s) — the dashboards end to end: infra (host, accelerators, containers), the
agents pipeline (cost, tokens, latency, call outcomes, traces, live agent inventory), the **Claude Code
& RAG** dashboard, and the **QMD Vector Space** (RAG memory corpus + benchmark queries projected to
2D/3D).

https://github.com/user-attachments/assets/ef08dcad-d20c-43eb-aa14-42b8cd2c014c

## Architecture

```
INFRA METRICS (pull)                       AGENT / AI TELEMETRY (push)
 node_exporter ────┐                        OpenClaw gateway          Claude Code (OTel)
 cadvisor         ─┤                          ├─ diag-prometheus ─(loopback textfile)─┐   │
 blackbox         ─┤                          │                                       │   │ OTLP
 intel igpu/npu   ─┼─► Prometheus ◄───────────┤                                       │   ▼
 nvidia gpu       ─┤        ▲                  └─ diag-otel ──OTLP─┐                   └► OTel Collector
 llama.cpp /metrics┤        │                                     ▼                        │
 litellm /metrics ─┘        │                               OTel Collector ──traces──► Tempo
                            │                                    │  │  └────logs──────► Loki
                            └───────────────(metrics)────────────┘  │                     │
                         Grafana ◄────────── Prometheus + Tempo + Loki datasources ◄───────┘
                      (LAN :3000)   folders: Infrastructure · AI & Agents
                            ▲
        grafy-bot (Telegram /graph) · grafana-image-renderer (PNG) · Alertmanager → Telegram

 accelerators: host textfile collectors (nvidia-smi / intel_gpu_top / intel_vpu sysfs) → node_exporter
 inference:    llama.cpp server-cuda (RTX 3090, MTP speculative decoding) → llama-arc:8080/metrics
```

## Quickstart

```bash
cp .env.example .env          # fill in Grafana password, OpenClaw scrape token, Telegram bot, etc.
make up                       # render secrets + docker compose up -d
# host-side accelerator + diagnostics collectors (systemd):
sudo cp systemd/*.service systemd/*.timer /etc/systemd/system/
sudo systemctl enable --now accel-textfile.timer observability-onboard.timer
```

Open Grafana at `http://<HOST_LAN_IP>:3000`. Dashboards are provisioned into two folders:
**Infrastructure** (host, accelerators incl. NVIDIA GPU, network, containers) and **AI & Agents**
(Claude Code, LLM Cost & Consumption, OpenClaw Agents, **LLM Inference — llama.cpp + MTP**, RAG).

| Service                  | Port | Purpose                                        |
|--------------------------|------|------------------------------------------------|
| Grafana                  | 3000 | dashboards (LAN)                               |
| Prometheus               | 9090 | metrics TSDB                                    |
| Tempo                    | 3200 | trace store                                    |
| Loki                     | 3100 | logs/events store (Claude Code per-request events) |
| OTel Collector           | 4317/4318 | OTLP ingest — traces→Tempo, metrics→Prom, logs→Loki |
| Alertmanager             | 9093 | alert routing → Telegram                       |
| grafana-image-renderer   | 8081 | server-side PNG rendering (for the bot)         |
| grafy-bot                | —    | Telegram `/graph` bot (image + values)          |

## Claude Code metrics

[Claude Code](https://claude.com/claude-code) ships native **OpenTelemetry**. Enable it in your
**shell environment** — add this to `~/.bashrc` (or `~/.zshrc`) and **restart the session**:

```bash
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_METRICS_EXPORTER=otlp
export OTEL_LOGS_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
export OTEL_METRIC_EXPORT_INTERVAL=10000
export OTEL_LOGS_EXPORT_INTERVAL=5000
export OTEL_RESOURCE_ATTRIBUTES=service.name=claude-code
```

> **Gotcha:** putting these in `~/.claude/settings.json`'s `env` block does **not** work — that block
> isn't applied to Claude Code's telemetry exporter, so metrics stay at 0. It must be in the shell env.

The **Claude Code** dashboard then breaks consumption out **by model** (Opus/Sonnet/Haiku), **by token
type** (input / output / cacheRead / cacheCreation), and **by named subagent** (Explore/Plan/… from
`subagent_completed` events), plus cost, cache-read per model, request count and **p95 latency**. It is
built on the per-request **`api_request` events in Loki** (`{service_name="claude-code"}`) rather than
the OTLP counters — the events persist (the counters are ephemeral and short sessions exit before the
metric flush). Prompt/response content is exported too when the `OTEL_LOG_*` content flags are set
(see [Phoenix](#phoenix): content capture is on for this stack).
See [docs/agents.md](docs/agents.md) and [docs/dashboards.md](docs/dashboards.md).

## What you get

- **Host & virtualization-host dashboards** (node_exporter), **Intel Arc iGPU** (busy %, freq, power),
  **Intel NPU** (busy, freq, memory) and **NVIDIA GPU** (utilization, VRAM used/free/total incl.
  **per-process VRAM**, temperature, power vs limit, SM/mem clocks) panels, network reachability +
  latency (blackbox), per-container resources (cAdvisor).
- **LLM Inference (llama.cpp)**: decode & prefill throughput (tok/s) vs a no-speculation baseline line,
  request queue depth, token volume, and an **MTP speculative-decoding** signal —
  `tokens_predicted_total / n_decode_total` (≈ tokens accepted per decode; 1.0 = no speculation). Pairs
  the inference server's `llamacpp:*` metrics with the GPU's VRAM/util on one dashboard.
- **Agents**: per-model call latency (p50/p95), call volume & outcomes (OpenClaw), tokens + spend +
  prompt-cache hit ratio (LiteLLM), and **per-run traces** in Tempo. A live **agent inventory** table
  updates as agents are added.
- **Claude Code (by model + subagent)**: persistent consumption from per-request **Loki events** —
  cost & tokens **per model** (Opus/Sonnet/Haiku), tokens by type (input / output / cache-read /
  cache-creation), cache-read per model, request count & **p95 latency**, and **named subagents**
  (runs/tokens by `agent_type` — Explore/Plan/… — and by model), with a drill-down logs panel.
- **LLM Cost & Consumption**: unified spend/tokens across Claude Code + OpenClaw/LiteLLM, by model/provider.
- **Memory breakdown**: system RAM %, and how much is the **iGPU** / **NPU** (they share system RAM) —
  a "where's my RAM" view in bytes and % of total.
- **RAG**: QMD index health (docs, vectors, freshness) per index.
- **Logs (Loki)**: the OTel Collector's logs pipeline ships Claude Code events to Loki; queryable in
  Grafana. Dashboards are grouped into **Infrastructure** and **AI & Agents** folders.
- **Alerting**: label-matched rules (host pressure, target-down, NPU saturation, **NVIDIA GPU VRAM >95%
  / over-temp / saturation**, **inference server down / decode-throughput collapse**, model latency,
  daily spend budget) → Alertmanager → Telegram.
- **Telegram bot (Grafy)**: text `/graph <dashboard> [range]` to get a rendered dashboard **image +
  key values** on your phone, plus `/values`, `/alerts`, `/list` — chat-locked to you. See
  [docs/telegram-bot.md](docs/telegram-bot.md).
- **Self-onboarding**: a systemd timer + an optional OpenClaw `observ` cron-agent keep everything in
  sync as the fleet grows.

## Phoenix

[Arize Phoenix](https://github.com/Arize-ai/phoenix) (self-hosted, open source) is a **second trace
backend** for LLM work: every trace that reaches the collector is also sent to Phoenix, which renders
prompts, completions and tool I/O better than a generic trace view. This is an **additive fan-out**.
Tempo, Loki, Prometheus, ClickHouse and every Grafana dashboard work as before, and producers keep
sending only to the collector (host `:4317` gRPC / `:4318` HTTP).

| | |
|---|---|
| UI | `http://<host>:5606/` (LAN, `0.0.0.0`). **No login.** |
| Port | host `5606` -> container `6006`, declared once as `phoenix_ui` in the fleet port registry (`ports.yaml`), set here as `PHOENIX_UI_PORT` in `.env`. Only the UI is published; Phoenix's OTLP ports stay on the `obs` network. |
| Image | `arizephoenix/phoenix:20.16.0` (pinned) |
| Storage | dedicated `phoenix-postgres` (`postgres:16-alpine`, volume `phoenix_pg_data`, no host port). Credentials in `secrets/phoenix_pg.env`, generated once by `bin/render-secrets.sh` and never committed. Phoenix owns its schema (migrations run at start). |
| Retention | `PHOENIX_DEFAULT_RETENTION_POLICY_DAYS=30`: the default project policy deletes traces older than 30 days (Tempo keeps 7). Change it per project in the UI (Settings -> Data retention). |
| Projects | one per `service.name`. The collector copies `service.name` into `openinference.project.name` (only when the producer did not set it), in the Phoenix pipeline only. |
| Hardening | the built-in agent assistant's server-side bash, web access and GitHub tools are disabled (`PHOENIX_AGENTS_DISABLE_*`), because the UI is unauthenticated. Phoenix telemetry is off. |

**Fan-out.** `otel-collector/config.yaml` has a second traces pipeline, `traces/phoenix`, on the same
`otlp` receiver, which exports to `otlphttp/phoenix` (`http://phoenix:6006/v1/traces`, gzip). It uses
OTLP/HTTP rather than Phoenix's gRPC `:4317` because Phoenix's gRPC server has a fixed 4 MiB receive
limit, while its HTTP endpoint has no body limit. The exporter has its own `sending_queue` (5000
batches) and retries for 15 minutes, so a Phoenix outage buffers in the collector and never slows
Tempo or ClickHouse. When Phoenix comes back the queue drains without a collector restart.

**Content capture is ON (2026-09-25).** The collector's former `attributes/scrub` processor is
removed, so `gen_ai.prompt` / `gen_ai.completion` / message attributes reach **Tempo, Loki and
Phoenix** unchanged. Size limits were raised so large content survives:

| Component | Setting | Value |
|---|---|---|
| Collector OTLP receiver | gRPC `max_recv_msg_size_mib` / HTTP `max_request_body_size` | 64 MiB / 64 MiB |
| Collector batch | `send_batch_size` / `send_batch_max_size` | 256 / 512 spans |
| Tempo 2.6 | `max_bytes_per_trace` (overrides) / OTLP gRPC receive / internal gRPC | 50 MiB / 64 MiB / 64 MiB. Tempo 2.6 does not truncate individual attributes. |
| Loki 3.1 | `max_structured_metadata_size` / `max_line_size` (truncate) / gRPC | 1 MB / 1 MB / 32 MiB |
| Phoenix | OTLP/HTTP body | no limit (gRPC 4 MiB is not used) |

ClickHouse `workflow_otel.spans_v1` is still **metadata only by design**: its materialized view
projects allowlisted columns and drops content attributes.

> **Warning:** with the scrub removed and Phoenix open on the LAN without auth, **anyone on the LAN
> can read every captured prompt and completion**, including anything sensitive pasted into an
> agent. This was the owner's explicit choice.

**Rollback.**
1. `otel-collector/config.yaml`: remove the `traces/phoenix` pipeline (and optionally the
   `otlphttp/phoenix` exporter and `resource/phoenix_project` processor). Restore
   `attributes/scrub` (it deleted `gen_ai.prompt`, `gen_ai.completion`, `gen_ai.request.messages`
   and `gen_ai.response.messages`) and add it back to the `traces` and `logs` processors, before
   `batch`. Then `docker compose restart otel-collector` (restart, not recreate).
2. `docker compose stop phoenix phoenix-postgres && docker compose rm -f phoenix phoenix-postgres`,
   then remove both services from `docker-compose.yml`. `docker volume rm observability_phoenix_pg_data`
   discards the stored traces.
3. Producer switches: remove the `OTEL_LOG_*` content flags (Claude Code) and set OpenClaw
   `diagnostics.otel.captureContent.*` back to `false`.

## Docs

- [Architecture](docs/architecture.md) · [Dashboards](docs/dashboards.md) · [Agents](docs/agents.md) · [Onboarding](docs/onboarding.md)
- [Hardware (iGPU/NPU/NVIDIA GPU + inference metrics)](docs/hardware.md) · [Telegram bot](docs/telegram-bot.md) · [Alerting](docs/alerting.md) · [Security](docs/security.md)

## Tests

```bash
make validate   # static: compose, promtool (+ rule unit tests), amtool, otel, dashboards, shellcheck
make smoke      # live: targets up, metrics present, datasources healthy, Tempo trace ingest
make scan       # secret + host-leak scan
```

CI runs `validate` + a secret scan on every PR (`.github/workflows/ci.yml`).

## License

Apache-2.0 — see [LICENSE](LICENSE).
