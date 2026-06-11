#!/usr/bin/env bash
# Live smoke test — requires the stack to be up (`make up`). Asserts the pipelines actually work.
set -uo pipefail
cd "$(dirname "$0")/.."
PROM="${PROM_URL:-http://127.0.0.1:9090}"
GRAF="${GRAFANA_URL:-http://127.0.0.1:3000}"
TEMPO="${TEMPO_URL:-http://127.0.0.1:3200}"
fail=0
ok(){ printf '  \033[32mPASS\033[0m %s\n' "$1"; }
no(){ printf '  \033[31mFAIL\033[0m %s\n' "$1"; fail=1; }

q(){ curl -s "$PROM/api/v1/query" --data-urlencode "query=$1" \
     | python3 -c 'import sys,json;r=json.load(sys.stdin)["data"]["result"];print(r[0]["value"][1] if r else "")' 2>/dev/null; }
present(){ [ -n "$(q "$1")" ] && ok "$2" || no "$2 (metric absent: $1)"; }

echo "== Prometheus targets healthy =="
down=$(curl -s "$PROM/api/v1/targets?state=any" \
  | python3 -c 'import sys,json;d=json.load(sys.stdin)["data"]["activeTargets"];print(",".join(sorted(set(t["labels"]["job"] for t in d if t["health"]!="up"))))' 2>/dev/null)
[ -z "$down" ] && ok "all targets up" || no "targets down: $down"

echo "== infra metrics present =="
present 'node_uname_info' 'node-exporter'
present 'container_last_seen' 'cadvisor'
present 'probe_success' 'blackbox'
present 'intel_npu_present' 'NPU textfile'
present 'intel_gpu_present' 'iGPU textfile'
present 'intel_gpu_memory_bytes' 'iGPU memory'
present 'namedprocess_namegroup_memory_bytes' 'per-process memory (process-exporter)'

echo "== agent telemetry present =="
present 'openclaw_diagnostics_up' 'openclaw diagnostics'
present 'openclaw_agents_total' 'agent inventory (onboarding)'
present 'litellm_spend_metric_total' 'litellm spend'
present 'qmd_documents_total' 'RAG / QMD index stats'
# Claude Code consumption lives in Loki (per-request `api_request` events persist; the OTLP metrics
# are ephemeral and short sessions exit before the flush — see docs/claude-code.md). Assert the
# persistent log source, not the metric. Don't fail if no session has run since telemetry was enabled.
LOKI="${LOKI_URL:-http://127.0.0.1:3100}"
ccq=$(curl -s "$LOKI/loki/api/v1/query" \
  --data-urlencode 'query=sum(count_over_time({service_name="claude-code"} | event_name=`api_request` [24h]))' \
  | python3 -c 'import sys,json;r=json.load(sys.stdin)["data"]["result"];print(r[0]["value"][1] if r else "")' 2>/dev/null)
[ -n "$ccq" ] && ok "Claude Code telemetry (Loki api_request events, 24h)" \
  || echo "  INFO No Claude Code api_request events in last 24h (start a session; needs telemetry env in the shell)"

echo "== Grafana datasources healthy =="
GPW="$(grep -E '^GRAFANA_ADMIN_PASSWORD=' .env 2>/dev/null | cut -d= -f2-)"
code=$(curl -s -o /dev/null -w '%{http_code}' -u "admin:${GPW}" "$GRAF/api/datasources/uid/prometheus/health")
[ "$code" = "200" ] && ok "grafana prometheus datasource" || no "grafana datasource ($code)"
cnt=$(curl -s -u "admin:${GPW}" "$GRAF/api/search?type=dash-db" | python3 -c 'import sys,json;print(len(json.load(sys.stdin)))' 2>/dev/null)
[ "${cnt:-0}" -ge 8 ] && ok "dashboards provisioned ($cnt)" || no "dashboards provisioned ($cnt)"

echo "== Loki (logs backend) =="
lr=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:3100/ready")
[ "$lr" = "200" ] && ok "loki ready" || no "loki ready ($lr)"
labels=$(curl -s "http://127.0.0.1:3100/loki/api/v1/labels" | python3 -c 'import sys,json;print(",".join(json.load(sys.stdin).get("data") or []))' 2>/dev/null)
echo "$labels" | grep -q service_name && ok "loki ingesting logs (service_name)" \
  || echo "  INFO loki has no logs yet (start a Claude Code session with telemetry)"

echo "== Tempo trace ingest (synthetic span) =="
TRACE_ID="$(python3 -c 'import os;print(os.urandom(16).hex())')"
SPAN_ID="$(python3 -c 'import os;print(os.urandom(8).hex())')"
NOW_NS="$(python3 -c 'import time;print(int(time.time()*1e9))')"
curl -s -o /dev/null -X POST "http://127.0.0.1:4318/v1/traces" -H 'Content-Type: application/json' -d "{
  \"resourceSpans\":[{\"resource\":{\"attributes\":[{\"key\":\"service.name\",\"value\":{\"stringValue\":\"smoke-test\"}}]},
  \"scopeSpans\":[{\"spans\":[{\"traceId\":\"$TRACE_ID\",\"spanId\":\"$SPAN_ID\",\"name\":\"smoke-span\",
  \"kind\":1,\"startTimeUnixNano\":\"$NOW_NS\",\"endTimeUnixNano\":\"$NOW_NS\"}]}]}]}"
sleep 6
found=$(curl -s "$TEMPO/api/traces/$TRACE_ID" | python3 -c 'import sys,json
try: d=json.load(sys.stdin); print("yes" if d.get("batches") or d.get("trace") else "no")
except: print("no")' 2>/dev/null)
[ "$found" = "yes" ] && ok "tempo ingested synthetic trace" || no "tempo did not return the synthetic trace"

echo "== Grafy bot + image renderer =="
GPW2="$(grep -E '^GRAFANA_ADMIN_PASSWORD=' .env 2>/dev/null | cut -d= -f2-)"
rcode=$(curl -s -o /tmp/_render.png -w '%{http_code}' -u "admin:${GPW2}" \
  "$GRAF/render/d/host/host?kiosk&width=600&height=400&from=now-1h&to=now")
if [ "$rcode" = "200" ] && file /tmp/_render.png 2>/dev/null | grep -q 'PNG image'; then ok "image renderer (real PNG)"; else no "image renderer ($rcode)"; fi
rm -f /tmp/_render.png
if docker compose ps grafy-bot --format '{{.State}}' 2>/dev/null | grep -q running; then ok "grafy-bot running"; else echo "  INFO grafy-bot not running (needs TELEGRAM_* in .env)"; fi

echo
[ "$fail" = 0 ] && { echo "SMOKE TEST PASSED"; exit 0; } || { echo "SMOKE TEST FAILED"; exit 1; }
