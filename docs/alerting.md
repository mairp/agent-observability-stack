# Alerting

Prometheus evaluates the rules in `prometheus/rules/`; Alertmanager routes them to **Telegram**.

## Rule catalog (`prometheus/rules/alerts.yml`, `agent-budgets.yml`)
| Group        | Alert | Fires when |
|--------------|-------|------------|
| host         | HostHighCPU / HostHighMemory / HostDiskAlmostFull / HostHighTemp | sustained pressure |
| accelerators | NPUSaturated / NvidiaGPUSaturated | NPU or NVIDIA GPU busy >95% for 10m |
| accelerators | NvidiaVRAMHigh / NvidiaGPUHot | NVIDIA VRAM >95% (OOM risk) / >85°C |
| network      | ProbeTargetDown / ProbeHighLatency | blackbox down / >2s |
| containers   | ContainerRestartLoop | repeated restarts |
| agents       | OpenClawGatewayDown / ModelCallLatencyP95High / ModelCallErrorSpike / LiteLLMProxyDown | telemetry/SLO |
| inference    | LlamaArcDown / LlamaDecodeCollapse | llama.cpp /metrics down / decode <20 tok/s while generating |
| agent-budgets| DailySpendBudgetExceeded / ModelDailySpendBudgetExceeded | LiteLLM 24h spend over budget |

Rules are **label-matched** (by `model`, `instance`, …), so they cover new agents/models automatically.
Unit tests live in `prometheus/ruletests/alerts_test.yml` (`promtool test rules`).

## Telegram delivery
1. Create a bot with **@BotFather**, copy the token.
2. Send the bot any message, then read your chat id:
   `curl -s "https://api.telegram.org/bot<token>/getUpdates"` → `result[].message.chat.id`.
3. Put both in `.env`:
   ```
   TELEGRAM_BOT_TOKEN=...
   TELEGRAM_CHAT_ID=...
   ```
4. `make render` regenerates `alertmanager/alertmanager.yml` from the template (token via
   `bot_token_file`, chat id inline). Until a chat id is set, a valid **no-op receiver** is rendered so
   Alertmanager still runs.

Test it: `amtool alert add --alertmanager.url=http://localhost:9093 alertname=Test severity=warning`.
