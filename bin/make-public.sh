#!/usr/bin/env bash
# Build a sanitized, generic, virtualization host-free copy of the stack for public release.
#   bin/make-public.sh [dest]   (default: /tmp/agent-observability-stack)
# Keeps the live deployment intact; produces a clean tree + runs the public secret scan.
set -euo pipefail
SRC="$(cd "$(dirname "$0")/.." && pwd)"
DST="${1:-/tmp/agent-observability-stack}"

rm -rf "$DST"; mkdir -p "$DST"
# Copy tracked-worthy content; exclude secrets, data, private overlay, generated state, vcs.
tar -C "$SRC" \
  --exclude='.git' --exclude='.env' --exclude='secrets' --exclude='data' \
  --exclude='docker-compose.override.yml' --exclude='onboard/registry.json' \
  --exclude='alertmanager/alertmanager.yml' --exclude='media/frames' \
  --exclude='*.lock' --exclude='prometheus/secrets/*' --exclude='*.bak*' \
  -cf - . | tar -C "$DST" -xf -

# Drop the virtualization host/virtualization-host scrape job from the public prometheus.yml.
python3 - "$DST/prometheus/prometheus.yml" <<'PY'
import re, sys
p = sys.argv[1]; s = open(p).read()
s = re.sub(r"\n  # --- virtualization-host exporter.*?replacement: pve-exporter:9221\n",
           "\n", s, flags=re.S)
open(p, "w").write(s)
PY

# Genericize host-specifics across text files (configs, scripts, docs, dashboards, Makefile).
mapfile -t FILES < <(grep -rIl . "$DST" --include='*.yml' --include='*.yaml' --include='*.sh' \
  --include='*.py' --include='*.md' --include='*.json' --include='*.service' --include='*.timer' \
  --include='*.tmpl.yml' --include='Makefile' 2>/dev/null)
for f in "${FILES[@]}"; do
  sed -i -E \
    -e 's#10\.254\.252\.[0-9]+#192.0.2.10#g' \
    -e 's#10\.254\.252\.0/24#192.0.2.0/24#g' \
    -e 's#10\.10\.10\.1#192.0.2.20#g; s#10\.20\.20\.1#192.0.2.21#g' \
    -e 's#10\.10\.10\.0/24#192.0.2.0/24#g; s#10\.20\.20\.0/24#198.51.100.0/24#g' \
    -e 's#https://host\.ai#https://example.com#g; s#host\.ai#example.com#g' \
    -e 's#\bmairp\b#host#g' \
    -e 's#/opt/observability#/opt/observability#g' \
    -e 's#/root/\.openclaw#${HOME}/.openclaw#g' \
    -e 's#/root/\.claude#${HOME}/.claude#g' \
    -e 's#(Host / )virtualization host#\1System#g; s#virtualization-host#virtualization-host#g; s#a virtualization host#a virtualization host#g; s#\bProxmox\b#virtualization host#g' \
    "$f"
done

# Drop the virtualization host-specific pve smoke assertion from the public copy.
sed -i "/pve_up/d; /pve-exporter/d" "$DST/tests/smoke.sh" 2>/dev/null || true

# Public .gitignore should also ignore the private overlay + rendered secrets.
cat > "$DST/.gitignore" <<'EOF'
.env
secrets/
*.secret
docker-compose.override.yml
data/
*/data/
onboard/registry.json
alertmanager/alertmanager.yml
media/frames/
*.bak*
EOF

# LICENSE (MIT)
cat > "$DST/LICENSE" <<'EOF'
MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED. IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
OTHER LIABILITY ARISING FROM THE USE OF THE SOFTWARE.
EOF

echo "Sanitized tree at: $DST"
echo "== running public secret scan =="
"$SRC/bin/secret-scan.sh" --public "$DST"
