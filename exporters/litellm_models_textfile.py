#!/usr/bin/env python3
"""Export the live LiteLLM model inventory to the node_exporter textfile collector.

Queries the LiteLLM proxy's /v1/models (loopback — the proxy is bound to
127.0.0.1:4000) and writes litellm_model_info{model="..."} 1 lines so the
Grafana "Models — LiteLLM Inventory" dashboard always reflects the current
model_list, including models added later (e.g. GLM). Replaces the previous
static, hand-maintained litellm_models.prom that went stale.

Env: LITELLM_MASTER_KEY (or LITELLM_MASTER_KEY_FILE), LITELLM_URL,
TEXTFILE_DIR. Writes atomically; exits 0 even on failure (writes up=0) so a
timer-driven run never spam-fails.
"""
import json
import os
import sys
import tempfile
import urllib.request

OUT_DIR = os.environ.get("TEXTFILE_DIR", "/var/lib/node_exporter/textfile_collector")
OUT = os.path.join(OUT_DIR, "litellm_models.prom")
BASE = os.environ.get("LITELLM_URL", "http://127.0.0.1:4000").rstrip("/")

key = os.environ.get("LITELLM_MASTER_KEY", "")
if not key and os.environ.get("LITELLM_MASTER_KEY_FILE"):
    with open(os.environ["LITELLM_MASTER_KEY_FILE"]) as fh:
        key = fh.read().strip()

models = []
err = ""
try:
    req = urllib.request.Request(
        f"{BASE}/v1/models", headers={"Authorization": f"Bearer {key}"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        models = sorted(m["id"] for m in json.load(resp)["data"])
except Exception as exc:  # noqa: BLE001
    err = str(exc)

fd, tmp = tempfile.mkstemp(dir=OUT_DIR, prefix=".litellm_models.")
with os.fdopen(fd, "w") as fh:
    fh.write("# HELP litellm_model_info Models currently configured in the LiteLLM proxy.\n")
    fh.write("# TYPE litellm_model_info gauge\n")
    fh.write(f"litellm_models_scrape_up {0 if err else 1}\n")
    for m in models:
        safe = m.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "")
        fh.write(f'litellm_model_info{{model="{safe}"}} 1\n')
os.chmod(tmp, 0o644)
os.replace(tmp, OUT)

if err:
    print(f"litellm_models_textfile: scrape failed: {err}", file=sys.stderr)
    sys.exit(1)
print(f"litellm_models_textfile: wrote {len(models)} models")
