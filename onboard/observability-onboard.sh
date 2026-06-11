#!/usr/bin/env bash
# Auto-onboard new OpenClaw agents, models, and accelerators into observability.
#
# What it does (idempotent, deterministic — safe to run on a timer):
#   1. Publishes an `openclaw_agent_info{agent,model,...}` gauge per agent into the node_exporter
#      textfile collector, so new agents appear in Prometheus/Grafana with ZERO config edits.
#   2. Discovers models (from LiteLLM) and accelerators (NPU/iGPU presence) currently seen.
#   3. Diffs against onboard/registry.json; logs anything NEW and (optionally) drops a Grafana
#      annotation so the dashboards mark when an agent/model/device first appeared.
#   4. Hot-reloads Prometheus if rule files changed.
#
# The companion OpenClaw `observ` cron-agent calls this and narrates the diff. The heavy lifting is
# here (no LLM in the hot path); the agent only adds judgment/summary.
set -uo pipefail
HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
TEXTFILE_DIR="${TEXTFILE_DIR:-/var/lib/node_exporter/textfile_collector}"
REGISTRY="$HERE/registry.json"
PROM_URL="${PROM_URL:-http://127.0.0.1:9090}"
GRAFANA_URL="${GRAFANA_URL:-http://127.0.0.1:3000}"
log(){ printf '[onboard] %s\n' "$*"; }

# ---- 1. agent inventory -> textfile metric -----------------------------------------------------
agents_json="$(openclaw agents list --json 2>/dev/null || echo '[]')"
tmp="$(mktemp)"
python3 - "$agents_json" > "$tmp" <<'PY'
import sys, json
try: agents = json.loads(sys.argv[1]) or []
except Exception: agents = []
print("# HELP openclaw_agent_info OpenClaw agent inventory (value always 1).")
print("# TYPE openclaw_agent_info gauge")
def esc(s): return str(s or "").replace("\\","\\\\").replace('"','\\"')
for a in agents:
    labels = ",".join(f'{k}="{esc(a.get(v))}"' for k,v in
                      [("agent","id"),("identity","identityName"),("model","model"),("default","isDefault")])
    print(f"openclaw_agent_info{{{labels}}} 1")
print("# HELP openclaw_agents_total Number of configured OpenClaw agents.")
print("# TYPE openclaw_agents_total gauge")
print(f"openclaw_agents_total {len(agents)}")
PY
mv "$tmp" "$TEXTFILE_DIR/openclaw_agents.prom"; chmod 644 "$TEXTFILE_DIR/openclaw_agents.prom"

# ---- 2. discover current models + accelerators -------------------------------------------------
q(){ curl -s "$PROM_URL/api/v1/query" --data-urlencode "query=$1" \
       | python3 -c 'import sys,json;[print(s["metric"].get(sys.argv[1],"")) for s in json.load(sys.stdin)["data"]["result"]]' "$2" 2>/dev/null; }
models="$(q 'group by (model)(litellm_spend_metric_total)' model | sort -u | grep -v '^$' || true)"
accel="$( { [ "$(q 'intel_npu_present==1' __name__)" ] && echo npu; [ "$(q 'intel_gpu_present==1' __name__)" ] && echo igpu; } )"
agent_ids="$(printf '%s' "$agents_json" | python3 -c 'import sys,json;print(" ".join(a.get("id","") for a in (json.load(sys.stdin) or [])))' 2>/dev/null)"

# ---- 3. diff against registry ------------------------------------------------------------------
prev_agents=""; prev_models=""; prev_accel=""
if [ -f "$REGISTRY" ]; then
  prev_agents="$(python3 -c 'import json;print(" ".join(json.load(open("'"$REGISTRY"'")).get("agents",[])))' 2>/dev/null)"
  prev_models="$(python3 -c 'import json;print(" ".join(json.load(open("'"$REGISTRY"'")).get("models",[])))' 2>/dev/null)"
  prev_accel="$(python3 -c 'import json;print(" ".join(json.load(open("'"$REGISTRY"'")).get("accel",[])))' 2>/dev/null)"
fi
new_items=""
for a in $agent_ids; do case " $prev_agents " in *" $a "*) ;; *) new_items="$new_items agent:$a";; esac; done
for m in $models;    do case " $prev_models " in *" $m "*) ;; *) new_items="$new_items model:$m";; esac; done
for x in $accel;     do case " $prev_accel " in *" $x "*) ;; *) new_items="$new_items accel:$x";; esac; done

# annotate Grafana for each newly-seen item (best-effort; needs admin creds in env)
if [ -n "${new_items# }" ] && [ -n "${GRAFANA_ADMIN_PASSWORD:-}" ]; then
  for item in $new_items; do
    curl -s -u "${GRAFANA_ADMIN_USER:-admin}:${GRAFANA_ADMIN_PASSWORD}" \
      -H 'Content-Type: application/json' \
      -d "{\"tags\":[\"onboarding\"],\"text\":\"Observability onboarded: ${item}\"}" \
      "$GRAFANA_URL/api/annotations" >/dev/null 2>&1 || true
  done
fi
[ -n "${new_items# }" ] && log "NEW:${new_items}" || log "no new agents/models/accelerators"

# ---- 4. persist registry -----------------------------------------------------------------------
python3 - "$REGISTRY" "$agent_ids" "$models" "$accel" <<'PY'
import sys, json
reg, agents, models, accel = sys.argv[1], sys.argv[2].split(), sys.argv[3].split(), sys.argv[4].split()
json.dump({"agents":agents,"models":models,"accel":accel}, open(reg,"w"), indent=1)
PY

# ---- 5. reload Prometheus (rules are agent-agnostic; reload is cheap + idempotent) --------------
curl -s -o /dev/null -X POST "$PROM_URL/-/reload" || true
log "done: ${agent_ids:-none} | models: $(echo $models|tr '\n' ' ') | accel: ${accel:-none}"
