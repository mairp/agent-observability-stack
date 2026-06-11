#!/usr/bin/env bash
# Secret + host-leak scanner. Run before publishing.
#   bin/secret-scan.sh [dir]            -> fail on hard secrets (tokens/keys/private keys)
#   bin/secret-scan.sh --public [dir]   -> also fail on host-specific leaks (IPs, hostnames, virtualization host)
# Uses gitleaks if available; always runs the built-in pattern checks too.
set -uo pipefail
PUBLIC=0
[ "${1:-}" = "--public" ] && { PUBLIC=1; shift; }
DIR="${1:-.}"
cd "$DIR"

# Never scan secrets/data/vcs internals, or the scanners themselves (they contain the patterns).
EXCLUDES=(--exclude-dir=.git --exclude-dir=secrets --exclude-dir=data
          --exclude-dir=node_modules --exclude=.env --exclude='*.prom' --exclude-dir=media
          --exclude=secret-scan.sh --exclude=make-public.sh)

hits=0
scan(){ # <label> <regex>
  local out; out="$(grep -RnE "${EXCLUDES[@]}" "$2" . 2>/dev/null)"
  if [ -n "$out" ]; then echo "  [LEAK] $1:"; echo "$out" | sed 's/^/      /' | head -8; hits=1; fi
}

echo "== hard secrets =="
scan "Telegram bot token"   '[0-9]{8,10}:[A-Za-z0-9_-]{35}'
scan "LiteLLM/OpenAI key"   'sk-[A-Za-z0-9]{20,}'
scan "Private key block"    '-----BEGIN (RSA |EC |OPENSSH |)PRIVATE KEY-----'
scan "PVE token UUID"       'PVE_TOKEN_SECRET=[0-9a-f]{8}-[0-9a-f]{4}'
scan "Generic bearer hex"   'OPENCLAW_SCRAPE_TOKEN=[0-9a-f]{32,}'

if [ "$PUBLIC" = 1 ]; then
  echo "== host-specific leaks (public mode) =="
  scan "RFC1918 LAN IPs"    '10\.(254\.252|10\.10|20\.20)\.[0-9]+'
  scan "Hostname host"     '\bmairp\b'
  scan "virtualization host references" '(?i)proxmox|prometheus-pve-exporter|\bpve\b'
  scan "Absolute /root path" '/root/'
fi

if command -v gitleaks >/dev/null 2>&1; then
  echo "== gitleaks =="
  gitleaks detect --no-banner --redact -s . 2>&1 | tail -5 || hits=1
fi

echo
[ "$hits" = 0 ] && { echo "CLEAN — no secrets/leaks found"; exit 0; } || { echo "FAILED — review leaks above"; exit 1; }
