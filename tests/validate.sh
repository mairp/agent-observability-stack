#!/usr/bin/env bash
# Static validation — no running stack required. Used by CI and `make test`.
set -uo pipefail
cd "$(dirname "$0")/.."
fail=0
ok(){ printf '  \033[32mPASS\033[0m %s\n' "$1"; }
no(){ printf '  \033[31mFAIL\033[0m %s\n' "$1"; fail=1; }

echo "== docker compose config =="
docker compose -f docker-compose.yml config -q && ok "base compose parses" || no "base compose"

echo "== prometheus config + rules =="
# promtool checks that credentials_file + file_sd paths exist, so mount the config dir at the real
# path and provide (dummy if needed) secret token files.
SECDIR="$(mktemp -d)"; : > "$SECDIR/openclaw_token"; : > "$SECDIR/litellm_token"
docker run --rm --entrypoint promtool -u 0:0 \
  -v "$PWD/prometheus":/etc/prometheus -v "$SECDIR":/etc/prometheus/secrets \
  prom/prometheus:v2.54.1 check config /etc/prometheus/prometheus.yml >/dev/null 2>&1 \
  && ok "prometheus.yml" || no "prometheus.yml"
rm -rf "$SECDIR"
docker run --rm --entrypoint promtool -v "$PWD/prometheus":/p prom/prometheus:v2.54.1 \
  check rules /p/rules/alerts.yml /p/rules/agent-budgets.yml >/dev/null 2>&1 && ok "alert rules" || no "alert rules"
if [ -f prometheus/ruletests/alerts_test.yml ]; then
  docker run --rm --entrypoint promtool -v "$PWD/prometheus":/p prom/prometheus:v2.54.1 \
    test rules /p/ruletests/alerts_test.yml >/dev/null 2>&1 && ok "rule unit tests" || no "rule unit tests"
fi

echo "== alertmanager config =="
if [ -f alertmanager/alertmanager.yml ]; then
  # Mount at the real paths so bot_token_file (/etc/alertmanager/secrets/telegram_token) resolves.
  ASEC="$(mktemp -d)"; : > "$ASEC/telegram_token"
  docker run --rm --entrypoint amtool -u 0:0 \
    -v "$PWD/alertmanager":/etc/alertmanager -v "$ASEC":/etc/alertmanager/secrets \
    prom/alertmanager:v0.27.0 check-config /etc/alertmanager/alertmanager.yml >/dev/null 2>&1 \
    && ok "alertmanager.yml" || no "alertmanager.yml"
  rm -rf "$ASEC"
else
  echo "  (alertmanager.yml not rendered; run bin/render-secrets.sh)"
fi

echo "== otel-collector config =="
docker run --rm -v "$PWD/otel-collector":/c otel/opentelemetry-collector-contrib:0.109.0 \
  validate --config=/c/config.yaml >/dev/null 2>&1 && ok "otel config" || no "otel config"

echo "== dashboards are valid JSON =="
while IFS= read -r f; do
  python3 -c "import json,sys;json.load(open('$f'))" >/dev/null 2>&1 && ok "$(basename "$(dirname "$f")")/$(basename "$f")" || no "$f"
done < <(find grafana/dashboards -name '*.json')

echo "== shell scripts (shellcheck) =="
if command -v shellcheck >/dev/null; then
  shellcheck -S error exporters/*.sh onboard/*.sh bin/*.sh >/dev/null 2>&1 && ok "shellcheck" || no "shellcheck"
else
  echo "  (shellcheck not installed; skipped)"
fi

echo
[ "$fail" = 0 ] && { echo "ALL STATIC CHECKS PASSED"; exit 0; } || { echo "STATIC CHECKS FAILED"; exit 1; }
