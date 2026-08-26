# RALPH 8.1 Notes — Composite Dashboard + Grafy Loki Value Path

## What was built in this repo (`~/agent-observability-stack`)

### 1. Composite dashboard — `grafana/dashboards/ai-agents/agents-composite.json`
- `uid: "agents-composite"`, title `"Agents — Claude Code vs pi"`, tags `["ai","composite"]`
- **$service template variable**: Loki `label_values(service_name)`, multi:true, includeAll:true, default All
- **15 panels** mirroring claude-code.json structure but every `target.expr` uses `service_name=~"$service"` and `sum by (service_name, ...)` grouping
- Panels: Cost, Output tokens, Cache-read tokens, Requests (stat rows); Cost by model, Tokens by type, Output tokens by model, Requests by model, Cache-read by model, Latency p95, Subagent runs/tokens/activity (timeseries + bargauge); Loki logs panel `{service_name=~"$service"}`
- **No panel hard-codes `service_name="claude-code"`** — all use `$service` template variable
- Also includes the existing `model` Prometheus template variable from claude-code.json

### 2. Offline validator — `tools/validate_composite_dashboard.py`
- Pure stdlib, no network
- Checks: JSON parses, uid=="agents-composite", $service templating present (Loki, multi, includeAll), every target.expr references service_name, no expr contains literal `service_name="claude-code"`
- Exit 0 on pass, exit 1 + clear message on failure

### 3. Grafy bot modifications — `bot/grafy_bot.py`
- **DASH aliases added**: `composite`, `agents-composite`, `both`, `claude-vs-pi` → `("agents-composite","agents-composite","Agents — Claude Code vs pi")`
- **`lokiq()` helper** (~line 150): mirrors `promq()`, hits `LOKI/loki/api/v1/query`, returns scalar or None
- **`LOKI_URL` env** added: `os.environ.get("LOKI_URL","http://loki:3100").rstrip("/")`
- **SUMMARY["agents-composite"]**: 4 Loki metric-queries (cost, tokens, cache-read, requests) with `service_name=~"$service"` LogQL
- **Generalized SUMMARY tuple**: now `(label, expr, fmt, "loki"|"prom")` — `values_text()` switches on source field
- **Existing prom-sourced rows unchanged**: host, accelerators, network, agents, claude-code, llm-cost, rag, qmd-vector-space, containers all still use `"prom"` source

### 4. Docker compose — `docker-compose.yml`
- Added `LOKI_URL: "http://loki:3100"` to `grafy-bot` service env block

### 5. Hermetic pytest suite — `bot/test_grafy_bot.py`
- 11 tests, all passing
- `lokiq()` parses mocked Loki scalar ✓
- `lokiq()` handles empty results and connection errors ✓
- Composite SUMMARY routes to Loki and renders values ✓
- Existing prom-sourced dashboards (host, claude-code) still render ✓
- No real socket opened (all HTTP via FakeSession) ✓
- DASH aliases include all 4 composite aliases ✓
- Existing dashboard aliases (host, claude-code, agents, llm-cost) untouched ✓

## Grafy Image Rebuild Step (human-run, out of loop)

After these code changes, the grafy-bot container needs a **full image rebuild** (not just restart):

```bash
cd ~/agent-observability-stack
docker compose build grafy-bot
docker compose up -d grafy-bot
```

This is because grafy-bot runs from a **baked image** `agent-obs/grafy-bot:local`. A `docker compose restart` will NOT pick up new code. The rebuild compiles the Dockerfile context (which copies `bot/` into the image) and recreates the container.

## Live Checks (human-run, out of loop scope)

After the rebuild, from an allowlisted Telegram chat:

1. `/list` — should include "agents-composite"
2. `/graph agents-composite 24h` — returns PNG showing both agents
3. `/values agents-composite 24h` — returns text rows with both claude-code and pi values from Loki

## Out of scope (documented, not attempted)

- **Criterion 7**: Grafana provisions `agents-composite` via `/api/dashboards/uid/agents-composite`→200. Requires running Grafana with the dashboard file mounted.
- **Criterion 9**: Telegram `/graph`+`/values` live from grafy after rebuild. Requires running Telegram bot + Loki.
- **Criterion 5/6**: Live Loki drive — pi telemetry extension + real data. This is the **separate pi telemetry extension task** (`~/.pi/agent/extensions/otel-telemetry/`).
- **Criterion 1-4**: pi telemetry extension tests (vitest, ≥95% coverage). Separate task.
- **Step 0**: pi virtual key swap. Separate task.

## Baseline integrity

- `claude-code.json` byte-identical: `sha256: 87c99a33ff70be1084bb6cdb33ba04fdcbb10b13f18127a929da3598e279eec6` ✓
- No changes to pi config, `models.json`, or otel-telemetry extension ✓
