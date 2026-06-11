# Dashboards

Provisioned as code from `bin/gen-dashboards.py` into two Grafana folders.

## Infrastructure
| Dashboard | Highlights |
|-----------|-----------|
| **Host / System** | CPU by mode, memory, load, disk, network by device, temps; a **memory breakdown** (system RAM %, **iGPU/NPU mem % of RAM**, "where's my RAM" bar); and **Top processes by memory & CPU** (which program is the hog — chromium/node/litellm/claude…), via process-exporter. |
| **Accelerators (iGPU + NPU)** | Intel Arc engine busy %, freq, power; NPU busy/freq/mem; **iGPU/NPU memory** (shared system RAM) + accel mem % of RAM. |
| **Network & Connectivity** | blackbox ICMP/HTTP probe up + latency, HTTP status. |
| **Containers** | per-container CPU/mem/net (cAdvisor). |

## AI & Agents
| Dashboard | Highlights |
|-----------|-----------|
| **Claude Code** | cost & tokens **by model**, tokens **by type** (input/output/**cacheRead/cacheCreation**), cache-read by model, request count & **p95 latency** per model, **subagents** (runs/tokens **by agent type** — Explore/Plan/…, and by model), and a **Loki logs panel** of per-request events. All totals are persistent — driven from Loki `api_request` events, not the ephemeral OTLP metrics. |
| **LLM Cost & Consumption** | unified spend/tokens across **Claude Code + OpenClaw/LiteLLM**, by model/provider, cache savings, 24h totals. |
| **OpenClaw Agents** | model-call latency p50/p95, call outcomes/errors by category, run-duration, queue depth, LiteLLM cost/tokens/cache, **agent inventory**, Tempo **traces**. |
| **RAG / Memory (QMD)** | docs/vectors/size per index, index freshness. |

## Metric sources (where each number comes from)
- **Claude Code**: per-request `api_request` **events** in **Loki** (`{service_name="claude-code"}`) —
  fields `cost_usd`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_creation_tokens`,
  `model`, `duration_ms`; subagents from `subagent_completed` (`agent_type`, `model`, `total_tokens`).
  The dashboards sum these with LogQL `sum_over_time(... | unwrap <field> [$__range])`. The OTLP
  `claude_code_*` **metrics** are *not* used — they expire ~5 min after a session and short sessions
  exit before the 10s metric flush; the log events are exported immediately and persist (7-day retention).
- **OpenClaw/LiteLLM**: `openclaw_model_*` (latency/outcomes), `litellm_*` (tokens/spend/cache), by `model`.
- **Accelerators**: `intel_gpu_*` / `intel_npu_*` from the host textfile collectors; iGPU memory is summed
  per-client `resident` from `intel_gpu_top` (shared system RAM).
- **Memory breakdown**: `node_memory_*` + `intel_gpu_memory_bytes` + `intel_npu_memory_bytes`.
- **Top processes** (`namedprocess_namegroup_*` from **process-exporter**): per-program RSS + CPU,
  grouped by command name (`{{.Comm}}` — chromium tabs summed, etc.). `topk()` for the leaderboard.

Edit a dashboard in Grafana, or change `bin/gen-dashboards.py` and re-run it (helpers: `ts`, `stat`,
`table`, `barg`, `logs`, `traces`). Output JSON is committed under `grafana/dashboards/{infrastructure,ai-agents}/`.

> Claude Code telemetry must be enabled in the **shell environment** (`CLAUDE_CODE_ENABLE_TELEMETRY=1`
> + `OTEL_*` exports in `~/.bashrc`) — the `~/.claude/settings.json` `env` block is **not** applied to
> the telemetry exporter. Restart your Claude Code session after adding it. Panels then populate from
> Loki as you use Claude Code; multiple models / subagents appear as you use them. See the README.
