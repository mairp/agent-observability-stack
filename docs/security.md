# Security & exposure

## Secrets
All secrets live in `.env` (chmod 600) and `secrets/` — both git-ignored. Config files reference
`${VARS}`; `bin/render-secrets.sh` materializes:
- `secrets/openclaw_token`, `secrets/litellm_token` (Prometheus bearer scrapes)
- `secrets/telegram_token` (Alertmanager `bot_token_file`)
- `alertmanager/alertmanager.yml` (rendered, git-ignored)

`bin/secret-scan.sh` (and CI) fail the build on any token/key/private-key leak; `--public` mode also
fails on host-specific strings (LAN IPs, hostnames, absolute host paths).

## No content capture
`diagnostics.otel.captureContent` is **disabled**, so prompt/response bodies never leave the host. The
OTel Collector additionally **scrubs** `gen_ai.*` message attributes as defense-in-depth.

## LAN exposure
Grafana (3000), Prometheus (9090), Alertmanager (9093), Tempo (3200) publish on the host so you can
reach them from a laptop/phone on the LAN. Grafana has anonymous **Viewer** + an admin login for edits.

Hardening (recommended on shared networks): scope the published ports to your LAN subnet with a host
firewall (nftables/ufw), and/or put Grafana behind a reverse proxy with auth/TLS. The OpenClaw gateway
itself stays firewalled to the LAN; its diagnostics are scraped over loopback, so no extra port is
opened for observability.

## Least privilege
- A dedicated read-only token scrapes the OpenClaw gateway diagnostics.
- The virtualization-host exporter (if used) uses a read-only API token (audit role).
- The `observ` agent has **no channel binding** and an exec allowlist limited to one digest script.
