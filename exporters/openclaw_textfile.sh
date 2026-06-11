#!/usr/bin/env bash
# Scrape the OpenClaw diagnostics-prometheus endpoint over LOOPBACK (allowed by the gateway
# firewall) and publish it into the node_exporter textfile collector. This avoids opening the
# gateway port to the Docker bridge. Emits openclaw_diagnostics_up{} as a freshness signal.
set -uo pipefail

OUT="${TEXTFILE_DIR:-/var/lib/node_exporter/textfile_collector}/openclaw.prom"
CFG="${OPENCLAW_CONFIG:-${HOME}/.openclaw/openclaw.json}"
PORT="$(python3 -c "import json;print(json.load(open('$CFG'))['gateway'].get('port',18789))" 2>/dev/null || echo 18789)"
TOKEN="$(python3 -c "import json;print(json.load(open('$CFG'))['gateway']['auth']['token'])" 2>/dev/null || echo '')"

tmp="$(mktemp)"
body="$(mktemp)"
code="$(curl -sk -m 8 -o "$body" -w '%{http_code}' \
        -H "Authorization: Bearer ${TOKEN}" \
        "https://127.0.0.1:${PORT}/api/diagnostics/prometheus" 2>/dev/null || echo 000)"

{
  echo "# HELP openclaw_diagnostics_up Whether the OpenClaw diagnostics endpoint was scraped OK (1) or not (0)."
  echo "# TYPE openclaw_diagnostics_up gauge"
  if [ "$code" = "200" ] && [ -s "$body" ]; then
    echo "openclaw_diagnostics_up 1"
    # Pass through the gateway's metrics verbatim (already valid Prometheus text).
    grep -E '^(openclaw_|# (HELP|TYPE) openclaw_)' "$body"
  else
    echo "openclaw_diagnostics_up 0"
  fi
} > "$tmp"
mv "$tmp" "$OUT"
chmod 644 "$OUT"
rm -f "$body"
