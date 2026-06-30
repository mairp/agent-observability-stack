#!/usr/bin/env bash
# One-shot recovery: rebuild .env from the running pve-exporter container's baked-in
# environment + LITELLM_MASTER_KEY from /root/litellm/.env. Never prints secret values.
set -euo pipefail
cd "$(dirname "$0")/.."

CTR=observability-pve-exporter-1
OUT=.env
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

# Snapshot the container env once (KEY=VALUE per line).
docker inspect "$CTR" --format '{{range .Config.Env}}{{println .}}{{end}}' > "$TMP"

# Keys we recover from the container (canonical .env.example set, minus LITELLM_MASTER_KEY).
KEYS=(GRAFANA_ADMIN_USER GRAFANA_ADMIN_PASSWORD OPENCLAW_GATEWAY_HOST OPENCLAW_GATEWAY_PORT \
      OPENCLAW_SCRAPE_TOKEN TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID PVE_TOKEN_ID PVE_TOKEN_SECRET \
      PVE_HOST PVE_VERIFY_SSL PROM_RETENTION)

umask 077
{
  echo "# Regenerated $(cat /proc/sys/kernel/random/uuid) — recovered after reboot wipe"
  for k in "${KEYS[@]}"; do
    line="$(grep -m1 "^${k}=" "$TMP" || true)"
    # If the key was absent from the container, emit an empty assignment.
    [ -n "$line" ] || line="${k}="
    printf '%s\n' "$line"
  done
  # LITELLM_MASTER_KEY comes from the LiteLLM stack's own .env.
  grep -m1 '^LITELLM_MASTER_KEY=' /root/litellm/.env || echo 'LITELLM_MASTER_KEY='
} > "$OUT"
chmod 600 "$OUT"

# Report key names + whether each is non-empty (NEVER the values).
echo "Wrote $OUT with:"
while IFS= read -r l; do
  case "$l" in \#*|'') continue;; esac
  k="${l%%=*}"; v="${l#*=}"
  if [ -n "$v" ]; then echo "  $k = [set]"; else echo "  $k = [EMPTY]"; fi
done < "$OUT"
