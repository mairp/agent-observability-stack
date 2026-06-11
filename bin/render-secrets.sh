#!/usr/bin/env bash
# Render secret files + templated configs from .env. Outputs are git-ignored.
# Idempotent; run before `docker compose up`.
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] || { echo "ERROR: .env missing (copy .env.example)"; exit 1; }
set -a; . ./.env; set +a

mkdir -p secrets
umask 077

# Prometheus -> OpenClaw bearer token
printf '%s' "${OPENCLAW_SCRAPE_TOKEN:-}" > secrets/openclaw_token

# Prometheus -> LiteLLM /metrics bearer (master key)
printf '%s' "${LITELLM_MASTER_KEY:-}" > secrets/litellm_token

# Alertmanager -> Telegram bot token (file) + rendered config (chat_id inline)
printf '%s' "${TELEGRAM_BOT_TOKEN:-}" > secrets/telegram_token
# chat_id must be a non-zero integer. Until the real ID is set, render a valid no-op receiver
# so Alertmanager runs; once a real chat_id is present, render the Telegram receiver.
# Treat non-numeric AND any numeric-zero (0, 000, 000000000...) as "unset".
CHAT_ID="${TELEGRAM_CHAT_ID:-0}"
if ! printf '%s' "$CHAT_ID" | grep -qE '^-?[0-9]+$' || [ "$CHAT_ID" -eq 0 ] 2>/dev/null; then
  CHAT_ID=0
fi
if [ "$CHAT_ID" = "0" ]; then
  printf 'route:\n  receiver: "null"\nreceivers:\n  - name: "null"\n' > alertmanager/alertmanager.yml
  echo "  (TELEGRAM_CHAT_ID not set — rendered no-op receiver; set it and re-run to enable Telegram)"
else
  sed "s|\${TELEGRAM_CHAT_ID}|${CHAT_ID}|g" \
      alertmanager/alertmanager.tmpl.yml > alertmanager/alertmanager.yml
fi

chmod 600 secrets/* 2>/dev/null || true
echo "Rendered: secrets/openclaw_token, secrets/telegram_token, alertmanager/alertmanager.yml"
