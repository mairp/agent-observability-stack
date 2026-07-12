#!/usr/bin/env bash
# llama-swap loaded-model gauge for the node-exporter textfile collector.
# Polls GET /running (cheap, does NOT trigger a model load) + /v1/models (config
# list, also load-free) and emits llamaswap_model_loaded{model} 1|0 for every
# configured model, so PromQL swap math is robust:
#   loads over time: sum(clamp_min(delta(llamaswap_model_loaded[10m]), 0))
# Same pattern as nvidia_gpu_textfile.sh (atomic mktemp+mv). jq is NOT on this
# host — python3 does the JSON.
set -uo pipefail
export LC_ALL=C
OUT="${TEXTFILE_DIR:-/var/lib/node_exporter/textfile_collector}/llamaswap.prom"
tmp="$(mktemp)"
{
  echo '# HELP llamaswap_api_up llama-swap /running endpoint reachable.'
  echo '# TYPE llamaswap_api_up gauge'
  running="$(curl -fsS -m 2 http://127.0.0.1:8081/running 2>/dev/null)"
  models="$(curl -fsS -m 2 http://127.0.0.1:8081/v1/models 2>/dev/null)"
  if [ -n "$running" ]; then
    echo 'llamaswap_api_up 1'
    echo '# HELP llamaswap_model_loaded 1 if the model is resident in llama-swap (0 = configured but not loaded).'
    echo '# TYPE llamaswap_model_loaded gauge'
    printf '%s\n%s\n' "$running" "$models" | python3 -c '
import sys, json
run = json.loads(sys.stdin.readline() or "{}")
try:
    cfg = json.loads(sys.stdin.readline() or "{}")
except Exception:
    cfg = {}
loaded = {m.get("model") for m in run.get("running") or []}
names = {m.get("id") for m in cfg.get("data") or []} | loaded
for n in sorted(x for x in names if x):
    print(f"llamaswap_model_loaded{{model=\"{n}\"}} {1 if n in loaded else 0}")'
  else
    echo 'llamaswap_api_up 0'
  fi
} > "$tmp" && mv "$tmp" "$OUT" && chmod 644 "$OUT"
