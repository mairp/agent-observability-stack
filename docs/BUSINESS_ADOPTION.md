# Business adoption: Agent Tokenomics and Fleet Observability

Date: 2026-09-06
Audience: executive review. Baselines are to be measured at the adopting site; figures below come from a single-host lab deployment unless stated otherwise.

## Use case

Agent Tokenomics and Fleet Observability

Tokenomics here means the economics of every token an agent consumes: what each task costs, which model and hosting choice produced that cost, how much of it prompt caching saved, and whether the outcome was worth it. It is the unit economics of running AI agents, measured continuously rather than estimated once a quarter.

An organisation adopting coding and operations agents (Claude Code, OpenClaw agents, autonomous "Ralph" task loops, locally hosted models) quickly ends up with many agents spending money, calling models and touching systems, with nobody able to answer three basic questions at once: what did the agents cost today, are they healthy, and what did each one actually do. Today those answers are assembled by hand from provider invoices, log files and individual engineers' recollection, usually after the bill or the incident has already arrived.

This composite use case puts every agent, every model call and the hardware underneath them on one pane of glass, with tokenomics as the organising lens. It combines four capabilities that are normally bought or built separately:

1. Tokenomics. Tokens, spend, cache hit ratio, latency and cost per completed task, broken down per model, per provider, per agent and per named subagent, with daily budget alerts. This is the layer that turns agent usage into a managed cost line with a known return.
2. Agent reliability and audit. Call volume, error rate, p95 latency, per-run traces and per-request event logs, so a failed or runaway run can be reconstructed after the fact.
3. Autonomous run supervision. Long-running agent loops report iteration count, acceptance-test outcome and cost per iteration, so an unattended job can be stopped on budget or on repeated failure rather than discovered in the morning.
4. Capacity for self-hosted inference, the supply side of tokenomics. GPU utilisation, VRAM, temperature, decode throughput and speculative-decoding acceptance for local models, alongside host CPU, memory, disk and container health, so the decision to run a workload locally or through a paid provider is made on measured numbers.

Agents, containers and accelerators onboard themselves as they appear; no per-agent configuration is edited. Alerts and rendered dashboard images are delivered to the operator's phone through a chat bot. Prompt and response content is never captured; only counts, timings and metadata leave the agent.

## Impact

- Tokenomics becomes a live number: spend per agent, per model and per task is visible while it is happening, instead of on the monthly invoice, and is capped by budget alerts.
- Runaway or looping agent runs are caught in minutes by latency, error and cost signals rather than by an engineer noticing hours later.
- Every model call is attributable to an agent, a session and a subagent, so incident review and audit questions are answered from records rather than reconstruction.
- Local GPU inference is right-sized on evidence: idle accelerators are powered down and saturated ones are identified before they throttle or run out of memory.
- Engineering time spent building one-off cost spreadsheets and log greps is removed; new agents inherit dashboards and alerts automatically.
- Adopting further agents becomes a governed decision, because each one arrives with its own tokenomics line and health signal from day one.
- Model and hosting choices are made on unit economics: the cheapest model that completes the task, and local inference where it beats the provider's price, are chosen from measured cost per outcome rather than instinct.

## Feasibility

Proven end to end on a single Linux host in a lab: two ingest pipelines (pull for infrastructure, push over OpenTelemetry for agents) feed one Grafana with provisioned dashboards, a Prometheus rule set with unit tests, Alertmanager routing to Telegram, and a bot that renders dashboards to images. Static validation, live smoke tests and a secret-leak scan run in continuous integration.

The stack is entirely self-hosted on open-source components (Prometheus, Grafana, Tempo, Loki, OpenTelemetry Collector, ClickHouse) and runs under Docker Compose, so there is no per-seat licence and no telemetry sent to a third party. Adoption requires: agents that emit OpenTelemetry or expose a metrics endpoint (Claude Code does natively; LiteLLM and llama.cpp expose metrics; other agents need a small exporter), one host or virtual machine to run the stack, and a chat channel for alert delivery. Secrets are held in environment files and read-only scrape tokens; the stack itself has no write access to any agent or model provider.

Known limits: the current build is single-host and LAN-exposed with anonymous viewer access, so a multi-team deployment needs a reverse proxy with single sign-on and per-team folders. Cost figures depend on the model price table being kept current. Agents that do not emit telemetry are invisible until an exporter is written for them.

## Success metrics

Baselines are recorded in month one from provider invoices, existing logs and a short engineer time survey. Targets are reviewed monthly at sponsor level.

### Tokenomics

- Cost per completed task, per model and per workload: baseline in month one → target reduction of 30%+ by month six through model and hosting choices.
- Share of model spend attributable to a named agent, session and subagent: partial and manual today → target 100%.
- Time from a cost overrun starting to an operator being notified: monthly invoice today → target under 15 minutes, automatic.
- Prompt-cache hit ratio per model: baseline in month one → target 60%+ on repeat-context workloads, tracked monthly.
- Share of eligible workload served by local inference where it beats the provider's price: 0% today → target agreed per workload, decided on measured cost per outcome.
- Reported spend reconciled against the provider invoice: not done today → within 5% every month, difference tracked as its own metric.

### Agent reliability and audit

- Time to reconstruct what an agent run did after an incident: hours of log reading today (to measure) → target under 10 minutes from the trace and event record.
- Model call error rate and p95 latency per agent: baseline in month one → alert thresholds agreed per agent, no unexplained regression month on month.
- Time from a runaway or looping run starting to detection: hours today (to measure) → target under 15 minutes, automatic.

### Autonomous run supervision

- Unattended agent runs stopped automatically on budget or repeated failure: 0% today → target 100% of runs launched through the supervised loop.
- Spend on runs that end without a passing acceptance test: current (to measure) → target reduction of 50%+.

### Inference capacity and platform

- Local GPU utilisation during working hours: current (to measure) → target inside an agreed band, with idle time powered down.
- GPU out-of-memory and thermal-throttle incidents: current (to measure) → zero unalerted, with VRAM and temperature warnings raised before the limit.
- Time for a new agent, container or accelerator to appear on the dashboards: manual configuration today → target under 5 minutes, no config edits.
- Engineer hours per month spent on cost reporting and log forensics for agents: current (to measure) → target reduction of 80%+.
- Approved agents with no telemetry signal: unknown today → zero older than one week, each one alerted.

## Data needs

- OpenTelemetry metrics, logs and traces from each agent, with agent, session and subagent identity attached; content capture disabled.
- Metrics from the model gateway (tokens, cost, cache, latency per model and per caller) and from any local inference server.
- Host and accelerator metrics from the machines running the agents and the models: CPU, memory, disk, network, container state, GPU utilisation, VRAM and temperature.
- A current model price table, owned by one person, to convert tokens into money.
- Historical provider invoices and any existing incident notes, to set the spend and forensics baselines above.
- A chat channel and identity for alert delivery, and single sign-on if more than one team will view the dashboards.

## Risks and mitigation

- Alert fatigue makes the signal ignored. Rules are label-matched and unit-tested, budgets are set per model from the measured baseline before go-live, and each alert names the agent and the action expected.
- Cost figures drift from the invoice. The price table has a named owner, and reported spend is reconciled against the provider invoice monthly for the first quarter, with the difference tracked as a metric.
- Sensitive content leaks through telemetry. Content capture is disabled at the source, the collector strips message attributes as a second layer, and a secret and host-leak scan runs on every change.
- Dashboards expose operational detail on a shared network. The lab default is LAN-only; production deployment places Grafana behind a reverse proxy with single sign-on and restricts published ports with a host firewall before any wider audience is given access.
- Agents that emit no telemetry give a false sense of complete coverage. The live agent inventory is compared against the list of approved agents weekly, and an agent with no signal for a defined period raises an alert rather than silently disappearing.
- The observability host itself becomes a single point of failure. Loss of the stack never affects the agents, only visibility; the stack is rebuilt from the repository in minutes, and retention targets are agreed so that a rebuild loses no more than the accepted window of history.
- Operators over-trust an automatic stop and skip review. A stopped run is reported with its reason and the last acceptance-test output, and remains a human decision to resume or abandon.

## Adoption & change management plan

Phase 1, measure and prepare (weeks 1 to 4). Record the current baselines: model spend from the last three provider invoices, the share of that spend attributable to a named agent, time to detect the last runaway run, engineer hours spent on cost reporting and log forensics, and GPU utilisation during working hours. Agree the model price table and name its owner. List the agents in scope for the pilot and confirm which already emit telemetry and which need an exporter. Name an executive sponsor, a platform owner from the team running the agents, a cost owner from finance or engineering management, and a security reviewer.

Phase 2, observe only (weeks 5 to 8). Deploy the stack on one host behind the LAN or a reverse proxy with single sign-on, with content capture disabled and the secret scan in the pipeline. Connect the pilot agents, the model gateway and the accelerators. Dashboards and the chat bot are live, but budget alerts are routed to the platform owner only and no run is stopped automatically. Reconcile reported spend against the provider invoice at month end and tune the price table until the difference is under 5%. Tune alert thresholds against the observed baseline so that the first alerts the wider team sees are ones worth acting on.

Phase 3, supervised pilot (weeks 9 to 16). Route budget, latency and error alerts to the team channel. Enable automatic stop on budget and repeated failure for unattended runs launched through the supervised loop, with the platform owner reviewing every stop for the first two weeks and then sampling. Publish the first monthly tokenomics report: cost per completed task by model and workload, cache hit ratio, and the local versus provider split. Track the success metrics weekly against the baselines. Exit criteria: spend reconciles to invoice within 5%, every pilot agent is attributable, no runaway run went undetected for more than 15 minutes, and no incident is attributed to the stack itself.

Phase 4, expand (from month 5). Onboard further teams, agents and hosts one at a time, each with its own observe-only period. Add per-team Grafana folders and budgets. Make the monthly tokenomics report the standard input for model and hosting decisions, and review the metrics monthly at sponsor level. Power-down of idle accelerators and any further automatic action is enabled per host once the team is confident in the reports.

People and roles. Engineers running agents gain a cost line and health signal for their own work and are expected to read them; nobody's job is removed. The cost owner uses the tokenomics report instead of assembling spreadsheets. The platform owner maintains the stack, the price table and the alert rules. The security reviewer signs off on exposure and confirms content capture stays disabled. These are role changes, not headcount changes, and should be stated as such early.

Training and communication. A one-hour session for engineers on the dashboards, what a budget or runaway alert means and how to respond. A short guide on enabling telemetry for a new agent, with the shell environment gotcha spelled out. A monthly tokenomics note to stakeholders reporting spend, cost per task, the top movers and any stopped run.

Governance. Every alert, stopped run and price-table change is recorded with who acted and why. Enabling automatic stops on a new class of run, powering down accelerators automatically, or exposing dashboards beyond the LAN requires sign-off from the platform owner and the security reviewer. Budget changes require the cost owner. A documented stop procedure removes the stack or any single automatic action without affecting the agents themselves, since the stack has no write access to them.
