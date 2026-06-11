# Telegram bot (Grafy) + alerts

A single Telegram bot serves two roles, both locked to your chat id(s):
- **Alertmanager → Telegram** delivery of fired alerts.
- **`grafy-bot`** — an interactive slash-command bot that returns dashboard images + values.

Both use the same bot token; Alertmanager only *sends*, `grafy-bot` *polls* — no conflict.

## Setup
1. Create a bot with **@BotFather**, copy the token. Message it once, then read your chat id from
   `https://api.telegram.org/bot<token>/getUpdates` (`result[].message.chat.id`).
2. Put both in `.env`:
   ```
   TELEGRAM_BOT_TOKEN=...
   TELEGRAM_CHAT_ID=...        # also the grafy-bot allowlist (comma-separate for multiple)
   ```
3. `make render && docker compose up -d` — renders the Alertmanager Telegram receiver and starts
   `grafy-bot` + `grafana-image-renderer`.

## Commands
| Command | Result |
|---------|--------|
| `/graph <dashboard> [range]` | rendered dashboard PNG **+ key values** |
| `/values <dashboard> [range]` | key values only |
| `/alerts` | currently firing alerts |
| `/list` · `/help` | dashboards / usage |

Dashboards: `host`, `accelerators`, `network`, `containers`, `agents`, `claude-code`, `llm-cost`, `rag`.
Range: `1h`/`6h`/`24h`/`7d` (default `3h`). Example: `/graph agents 24h`.

## How it works
- `grafy-bot` (`bot/grafy_bot.py`) long-polls `getUpdates`, ignores any chat not in
  `TELEGRAM_ALLOWED_CHATS`, renders via Grafana's `/render/d/<uid>` (served by the
  **grafana-image-renderer** sidecar, admin-auth), and pulls the per-dashboard summary values from
  Prometheus. Replies via `sendPhoto` + `sendMessage`.
- Per-dashboard value queries live in `SUMMARY` in `bot/grafy_bot.py` — extend there to add metrics.
- Security: token + chat id come from env only; the bot never answers non-allowlisted chats.
