# Local-model savings — how the RTX 3090 section of *LLM Cost & Consumption* is built

Research date: 2026-09-11 (three Opus 5 research agents: data-path audit, market shadow prices, on-prem energy cost).

## Why the local models were "missing"

The open-weight models served by llama-swap on the RTX 3090 (`qwen3.8-27b-q5`, `nemotron-lightning-30b`,
`muse-glimmer-30b`, retired `qwen3-coder-30b-a3b` / `qwen3.6-27b` / `qwen3.8-27b-q4`, plus `antares`, `qwen2.5-vl`)
do cross the LiteLLM proxy and carry full token/request counters, but LiteLLM prices them at **$0**. Every spend
panel therefore drops them (flat-zero series are not drawn). Three further reasons compounded it:

1. **No local traffic crossed LiteLLM for 12+ days** (last increase 2026-08-30 for q5, 08-21 for muse/nemotron) while
   the GPU was still resident ~16 % of the week with 129 load/unload cycles on q5. Callers (bebop / pi / OpenClaw) were
   hitting llama-swap `:8081` directly. That traffic was invisible to both meters.
2. The `$model` variable was sourced from the live inventory (`litellm_model_info`), so retired aliases with 30d of
   history could not be selected. It now comes from `label_values(litellm_total_tokens_metric_total, model)`.
3. The proxy tokens/s panel had no `by (model)`, folding local tokens into one line.

Ralph loops, bebop and OpenClaw emit no `api_request` events, so they never appear on the Loki (agent) meter.

## What changed

- **`exporters/llamaswap_textfile.sh`** now reads `llamacpp:*` counters from the loaded llama-server via
  `/upstream/<model>/metrics`, **only for models `/running` reports as `ready`** (load-free; on an unloaded model that
  path would trigger a load). New series: `llamaswap_upstream_prompt_tokens_total`,
  `llamaswap_upstream_tokens_predicted_total`, `..._prompt_seconds_total`, `..._tokens_predicted_seconds_total`,
  `llamaswap_upstream_requests_processing`, all `{model}`. Counters reset on each (re)load; `increase()`/`rate()`
  absorb that. This is the only meter that sees direct callers. Runs every 15 s via `accel-textfile.timer`.
- **Dashboard variables**: `local_models` (regex over the LiteLLM `model` label), `ref_in` / `ref_cached` / `ref_out`
  ($ per MTok, presets below), `kwh_price` (your tariff).
- **New section** with avoided cost on both meters, electricity, net saving, local share, failures → gpt-5 fallback,
  energy, residency, $/h by model, llama-server tok/s vs watts, per-model table. Default range moved to 7d.

No shadow price was put into LiteLLM's `input_cost_per_token`: it would write into `litellm_spend_metric_total`,
the Postgres spend ledger and key/team budgets, mixing real and hypothetical dollars with no label to separate them.

## Reference prices (USD per 1M tokens)

**Ceiling (default): gpt-5** at 1.25 in / 0.125 cached / 10.00 out. `litellm/config.yaml` wires `fallbacks` and
`context_window_fallbacks` from every local route to gpt-5, so each successful local token is literally a gpt-5 token
not bought.

**Floor: median of live open-weight hosts** for the same weights (OpenRouter endpoints, 2026-09-11):

| alias | weights | hosts (in / out) | reference |
|---|---|---|---|
| qwen3.8-27b-q5 / -q4 | Qwen3.8-27B | Darkbloom 0.15/2.00, Reka 0.214/2.55, Parasail 0.24/2.20, Chutes 0.32/2.50, CoreWeave 0.40/3.00, Novita 0.42/3.00, Alibaba 0.425/2.55 | 0.31 / 2.65 |
| muse-glimmer-30b | Meta Muse Glimmer 30B | DeepInfra 0.30/1.20, Phala 0.30/1.10, Fireworks 0.35/1.50, Together 0.35/1.50 | 0.33 / 1.35 |
| nemotron-lightning-30b | Nemotron 3.5 Lightning 30B-A3B | DeepInfra 0.08/0.20, CoreWeave 0.10/0.25 | 0.09 / 0.225 |
| qwen3-coder-30b-a3b | Qwen3-Coder-30B-A3B | Novita 0.07/0.27, SiliconFlow 0.07/0.28, Bedrock 0.15/0.60, Alibaba 0.292/1.462 | 0.11 / 0.44 |
| qwen3.6-27b | Qwen3.6-27B | Chutes 0.30/2.00, SiliconFlow 0.30/3.20, DeepInfra 0.32/3.20, Alibaba 0.45/2.70 | 0.32 / 2.95 |
| antares | Granite-4.0-1B (no host; priced off Granite 4.0 Micro 3B, a ceiling) | Cloudflare 0.017/0.112 | 0.02 / 0.11 |
| qwen2.5-vl | Qwen2.5-VL-7B (delisted; priced off Qwen3-VL-8B) | Alibaba 0.117/0.455, Parasail 0.25/0.75 | 0.18 / 0.60 |

Sources: https://openrouter.ai/qwen/qwen3.8-27b, https://openrouter.ai/meta/muse-glimmer-30b,
https://openrouter.ai/nvidia/nemotron-3.5-lightning, https://openrouter.ai/qwen/qwen3-coder-30b-a3b-instruct,
https://openrouter.ai/qwen/qwen3.6-27b, https://developers.openai.com/api/docs/pricing.

Quantisation is deliberately not discounted: a q4 token and a bf16 token both displace one cloud token.

## 30-day picture (2026-08-12 → 2026-09-11, proxy meter)

| | value |
|---|---|
| local requests / tokens | 4,996 / 91.2 M (89.2 M input of which 74.7 M cache hits, 1.94 M output) |
| local share of proxy traffic | 7.4 % of requests, 2.3 % of tokens |
| avoided cost @ gpt-5 basis | $46.87 |
| avoided cost @ open-weight median (no cache discount) | ~$15 |
| GPU energy / cost @ $0.25/kWh | 53.0 kWh / $13.26 (39.8 kWh with a model loaded, 13.2 kWh idle at ~35 W) |
| net saving @ gpt-5 basis, $0.25/kWh | $33.61 |
| deployment failures on the llama-swap route | 1,809 (q5 1,368, q4 441) — ~91 % of q5/q4 requests, each retried on gpt-5 |
| hours model-loaded / residency | 142 h / 20 % |
| on-prem energy cost per 1M output tokens | $5.13 marginal, $6.83 fully loaded (@ $0.25/kWh) |
| amortisation (assumed $950 card + enclosure over 36 months) | $26.39/month, ~$13.60 per 1M output tokens at current volume |

Caveats: `llamaswap_gpu_power_draw_watts` is board power only (add ~15–25 % for enclosure PSU and host). The 30d
window includes the Aug 30 – Sep 2 benchmark campaign (5.7–7.8 kWh/day). The llama-server meter starts 2026-09-11,
so the "all callers" avoided-cost stat is near zero until it accumulates history.

## What would move the number

- **Fix the q5/q4 failure rate.** 1,809 failed local calls became gpt-5 spend. That is the single largest lever.
- **Route direct callers through LiteLLM** (or keep the new llama-server meter as the authoritative local count).
- **Cut idle burn**: 13 kWh/30d at ~35 W with nothing loaded (persistence mode keeps the floor at 35 W, not ~10 W).
