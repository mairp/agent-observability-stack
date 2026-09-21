<!-- pi-ralph-loop: hand-authored 2026-07-12 — roadmap 8.1 dashboard+grafy slice. Task dir = repo root so deliverables are under it and required_outputs need no '..'. -->
---
commands:
  - name: baseline-unchanged
    run: 'set -euo pipefail; cd ~/agent-observability-stack; test "$(sha256sum grafana/dashboards/ai-agents/claude-code.json | cut -d" " -f1)" = "87c99a33ff70be1084bb6cdb33ba04fdcbb10b13f18127a929da3598e279eec6" && echo "claude-code.json UNCHANGED (baseline ok)"'
    timeout: 30
    acceptance: true
  - name: dashboard-json-parses
    run: 'set -euo pipefail; cd ~/agent-observability-stack; python3 -c "import json; d=json.load(open(\"grafana/dashboards/ai-agents/agents-composite.json\")); assert d.get(\"uid\")==\"agents-composite\"; print(\"composite json parses, uid ok\")"'
    timeout: 30
    acceptance: true
  - name: validate-dashboard
    run: 'set -euo pipefail; cd ~/agent-observability-stack; python3 tools/validate_composite_dashboard.py grafana/dashboards/ai-agents/agents-composite.json && echo VALIDATOR_OK'
    timeout: 60
    acceptance: true
  - name: grafy-pytest
    run: 'set -euo pipefail; cd ~/agent-observability-stack; python3 -m venv bot/.venv-test >/dev/null 2>&1 || true; . bot/.venv-test/bin/activate; pip -q install pytest requests >/dev/null 2>&1; python -m pytest bot/test_grafy_bot.py -q 2>&1 | tail -30'
    timeout: 240
    acceptance: true
max_iterations: 24
inter_iteration_delay: 0
timeout: 900
completion_promise: DONE
completion_gate: required
required_outputs:
  - grafana/dashboards/ai-agents/agents-composite.json
  - tools/validate_composite_dashboard.py
  - bot/test_grafy_bot.py
  - RALPH-8.1-NOTES.md
stop_on_error: false
guardrails:
  block_commands:
    - 'git\s+push'
    - 'git\s+commit'
    - 'rm\s+-rf'
    - 'docker\b'
  protected_files:
    - 'policy:secret-bearing-paths'
    - '*claude-code.json'
    - '.env*'
---

# Task: composite Grafana dashboard + grafy Telegram delivery (roadmap 8.1, section B/C)

**Your shell cwd is your home directory `~` (NOT the repo).** ALL files you create/edit live in the repo
`~/agent-observability-stack/` — always use ABSOLUTE paths (e.g.
`~/agent-observability-stack/grafana/dashboards/ai-agents/agents-composite.json`,
`~/agent-observability-stack/tools/…`, `~/agent-observability-stack/bot/…`). A
repo-relative path like `grafana/…` will wrongly resolve under `~` and the acceptance gate
will not see your work. Read
`~/roadmap/8.1_grafana-composite-claude-pi-roadmap.md` — Deliverables 2, 6, 7 and Success
criteria B(7,8), C(9,10).

The pi telemetry EXTENSION is a SEPARATE task (`~/.pi/agent/extensions/otel-telemetry/`) — do NOT
touch it here. All work is in THIS repo. Note: this repo root has a 6 MB `media/` file, so ralph's
progress snapshot may truncate — ignore the "no durable progress" heuristic here; the **acceptance
commands below are the real gate**, not the file-change heuristic.

## Fresh evidence each iteration

```text
baseline (claude-code.json must stay byte-identical):
{{ commands.baseline-unchanged }}

composite dashboard parses + uid:
{{ commands.dashboard-json-parses }}

offline validator:
{{ commands.validate-dashboard }}

grafy unit tests (hermetic, upstream mocked):
{{ commands.grafy-pytest }}
```

## Build (offline / loop-drivable — the acceptance gate)

1. **`grafana/dashboards/ai-agents/agents-composite.json`** — NEW composite dashboard.
   `uid:"agents-composite"`, title `"Agents — Claude Code vs pi"`, tags `["ai","composite"]`.
   Templating `$service` = Loki `label_values(service_name)`, `multi:true`, `includeAll:true`,
   default `All`. **Reuse `grafana/dashboards/ai-agents/claude-code.json` panel JSON as the
   template** (read it), but every panel is broken down `by (service_name)` and the logs panel
   matches `{service_name=~"$service"}`. Panels: Cost(range), Output tokens, Cache-read tokens,
   Requests (stat rows per service); time-series Cost/Tokens/Requests/latency-p95
   `by (service_name, model)`; one Loki logs panel. **Every** `target.expr` must reference
   `service_name`; **NO** panel may hard-code `service_name="claude-code"`.

2. **`tools/validate_composite_dashboard.py`** — NEW offline validator (create `tools/`). `argv[1]`
   = dashboard path. Exit 0 iff: JSON parses; `uid`==`agents-composite`; `$service` templating
   present; every `target.expr` references `service_name`; no expr contains literal
   `service_name="claude-code"`. Non-zero + clear message otherwise. Pure stdlib, no network.

3. **`bot/grafy_bot.py`** (landmarks: `DASH`~L30, `SUMMARY`~L84, `promq()`~L146) — do NOT break
   existing PromQL rows:
   - `DASH` aliases `composite`/`agents-composite`/`both`/`claude-vs-pi` →
     `("agents-composite","agents-composite","Agents — Claude Code vs pi")`.
   - `lokiq(expr)` helper mirroring `promq()`, hitting `LOKI/loki/api/v1/query`;
     `LOKI = os.environ.get("LOKI_URL","http://loki:3100").rstrip("/")`.
   - per-service `SUMMARY["agents-composite"]` with Loki metric-queries (LogQL
     `sum by (service_name)(sum_over_time(... | event_name="api_request" | unwrap output_tokens [24h]))`
     + cost/requests). Generalize the SUMMARY tuple to carry source
     (`(label,expr,fmt,"loki"|"prom")`) OR add `SUMMARY_LOKI`; `values_text` switches on source.
   - Add `LOKI_URL: "http://loki:3100"` to the `grafy-bot` service env in `docker-compose.yml`
     only.

4. **`bot/test_grafy_bot.py`** — NEW pytest (hermetic; monkeypatch/fake `requests`, NO real
   network): `lokiq()` parses a mocked Loki scalar; composite SUMMARY routes to Loki + renders
   BOTH `claude-code` and `pi`; an existing prom-sourced dashboard's rows still render. Assert no
   real socket opened.

5. **`RALPH-8.1-NOTES.md`** (repo root) — the grafy image REBUILD step (baked image
   `agent-obs/grafy-bot:local`: `docker compose build grafy-bot && docker compose up -d grafy-bot`,
   not just restart) + the LIVE checks below (human-run, out of loop scope).

6. **`OPEN_QUESTIONS.md`** (repo root) — blockers as P0/P1; none may remain to finish.

## Out of scope — document in NOTES, DO NOT attempt (need running infra + Telegram + rebuild)

criterion 7 (Grafana provisions `agents-composite`; `/api/dashboards/uid/agents-composite`→200;
panels non-empty for both services); criterion 9 (grafy `/graph`+`/values` from Telegram after
rebuild); criterion 5/6 live Loki drive.

## Hard constraints

- **`claude-code.json` byte-identical** (guarded + hash-checked). Never edit it.
- No `git commit`/`git push` (human commits, signed `-s`, `oec.valle.art@gmail.com`). No `docker`.
- Do NOT touch pi config / `models.json` / the otel-telemetry extension.

Emit `<promise>DONE</promise>` ONLY when: baseline-unchanged ok; composite JSON parses w/ correct
uid; `validate_composite_dashboard.py` exits 0; grafy pytest green (existing rows intact + loki
path covered); NOTES + OPEN_QUESTIONS complete; and the completion audit maps every gate to real
evidence.

Iteration {{ ralph.iteration }} of {{ ralph.max_iterations }}.
