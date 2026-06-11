#!/usr/bin/env bash
# Single entrypoint for the observ cron-agent: run onboarding, then print a digest from live
# Prometheus data. One allowlisted command => no per-call approvals, no web_fetch (uses curl here).
set -uo pipefail
export LC_ALL=C
HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
PROM="${PROM_URL:-http://127.0.0.1:9090}"
r2(){ python3 -c "import sys;v=sys.argv[1]
try:print(f'{float(v):.4f}')
except:print(v)" "$1"; }
r0(){ python3 -c "import sys;v=sys.argv[1]
try:print(f'{float(v):.0f}')
except:print(v)" "$1"; }

onboard_out="$("$HERE/observability-onboard.sh" 2>&1 | grep -E '\[onboard\]' || true)"

pq(){ curl -s "$PROM/api/v1/query" --data-urlencode "query=$1" \
      | python3 -c 'import sys,json
r=json.load(sys.stdin)["data"]["result"]
print(r[0]["value"][1] if r else "n/a")' 2>/dev/null; }

agents="$(pq 'openclaw_agents_total')"
spend="$(pq 'sum(increase(litellm_spend_metric_total[24h]))')"
tokens="$(pq 'sum(increase(litellm_total_tokens_metric_total[24h]))')"
npu="$(pq 'intel_npu_present')"; igpu="$(pq 'intel_gpu_present')"
cpu="$(pq '100-(avg(rate(node_cpu_seconds_total{mode=\"idle\"}[5m]))*100)')"
firing="$(curl -s "$PROM/api/v1/query" --data-urlencode 'query=ALERTS{alertstate="firing"}' \
          | python3 -c 'import sys,json;r=json.load(sys.stdin)["data"]["result"];print(", ".join(sorted(set(s["metric"].get("alertname","?") for s in r))) or "all clear")' 2>/dev/null)"

echo "=== OBSERVABILITY DIGEST ==="
[ -n "$onboard_out" ] && echo "$onboard_out"
echo "Agents onboarded : ${agents}"
echo "Spend (24h)      : \$$(r2 "${spend:-0}")"
echo "Tokens (24h)     : $(r0 "${tokens:-0}")"
echo "CPU busy         : $(r0 "${cpu:-0}")%"
echo "Accelerators     : NPU=$([ "$npu" = 1 ] && echo present || echo n/a)  iGPU=$([ "$igpu" = 1 ] && echo present || echo n/a)"
echo "Firing alerts    : ${firing}"
