# Open Questions — 8.1 Composite Dashboard

## P0 (blocking) — none remain

| # | Question | Status |
|---|----------|--------|
| 1 | Does the composite dashboard JSON parse and have correct uid? | ✅ Resolved — validator confirms |
| 2 | Does every panel expr reference service_name? | ✅ Resolved — validator confirms |
| 3 | Does grafy bot support composite aliases + Loki queries? | ✅ Resolved — 11/11 tests pass |
| 4 | Are existing dashboard rows intact after grafy changes? | ✅ Resolved — tests verify host + claude-code |
| 5 | Is claude-code.json byte-identical? | ✅ Resolved — sha256 unchanged |

## P1 (non-blocking, follow-ups)

| # | Question | Notes |
|---|----------|-------|
| 1 | Grafana provisions agents-composite automatically | Dashboard file is in the provisioned dir (`grafana/dashboards/ai-agents/`); the `ai-agents` provider should auto-discover it. Needs live Grafana verification. |
| 2 | Grafy image rebuild succeeds | Requires `docker compose build grafy-bot` — out of loop scope. |
| 3 | Telegram `/values agents-composite` returns both agents | Requires Loki with pi data — out of loop scope. |
| 4 | pi telemetry extension (separate task) | `~/.pi/agent/extensions/otel-telemetry/` — NOT in this repo. |

## No remaining P0/P1 blockers

All deliverables are complete and verified. The remaining items require running infrastructure (Grafana, Loki, Telegram) which is out of loop scope per the task spec.
