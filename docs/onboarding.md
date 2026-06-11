# Dynamic onboarding

The fleet grows. The stack is built so new **agents**, **containers**, and **accelerators** appear
with **zero config edits** — convention over per-target configuration.

## Automatic by construction
- **Agents** — diagnostics plugins are gateway-scoped, so a new agent's traces flow immediately. The
  onboarding script also publishes `openclaw_agent_info{agent,model,...}`, so new agents show up in
  the inventory panel and `label_values()` dropdowns automatically.
- **Containers** — `docker_sd_configs` + cAdvisor discover any new container; add the label
  `prometheus.scrape=true` (and `prometheus.port`) to have its `/metrics` scraped too.
- **Accelerators** — the iGPU/NPU collectors locate the device dynamically via sysfs/`intel_gpu_top`,
  so a newly added/enabled accelerator is picked up on the next tick.

## The onboarding layers (both run)
1. **Deterministic core** — `onboard/observability-onboard.sh`, run by `observability-onboard.timer`
   every 5 minutes. It publishes the agent inventory metric, diffs against `onboard/registry.json`,
   logs anything **NEW**, optionally drops a Grafana annotation, and hot-reloads Prometheus. Idempotent,
   no LLM in the hot path.
2. **`observ` cron-agent** *(optional, OpenClaw)* — a channel-less agent that runs
   `onboard/observ-digest.sh` (the single allowlisted entrypoint: runs onboarding, then reads live
   Prometheus data) on a daily cron and produces a short health digest. Add it with `openclaw agents
   add observ` + an exec allowlist for the digest script + a cron job. See the workspace skill in
   `examples/observ-skill.md`.

## Alert rules stay agent-agnostic
Rules use label matchers (e.g. `by (model)`, `{outcome!="completed"}`) and LiteLLM spend, so they
cover current and future agents/models without enumeration. Budgets are by model + a global cap.
