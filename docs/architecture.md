# Architecture

Two independent pipelines feed one Grafana.

## Infra metrics (Prometheus pull)
Prometheus scrapes:
- **node_exporter** (host CPU/RAM/disk/net/hwmon) — runs with host network + PID, and reads a
  **textfile collector** directory where host-side scripts drop extra metrics.
- **cAdvisor** — per-container CPU/RAM/net for every Docker stack on the box.
- **blackbox_exporter** — ICMP + HTTP probes for connectivity & latency (targets are data in
  `prometheus/targets/*.yml`, discovered via `file_sd`).
- **Intel iGPU/NPU** — `exporters/intel_gpu_textfile.py` (wraps `intel_gpu_top -J`) and
  `exporters/intel_npu_textfile.sh` (reads `intel_vpu` sysfs) write `.prom` files into the textfile dir.
- **NVIDIA GPU** — `exporters/nvidia_gpu_textfile.sh` (wraps `nvidia-smi`) writes `nvidia_gpu_*`
  (util, VRAM used/free/total incl. **per-process**, temp, power/limit, SM/mem clocks) into the textfile
  dir. All three accelerator collectors are chained by `exporters/accel_collect.sh` (one `accel-textfile.timer`).
- **LiteLLM** `/metrics/` — tokens, spend, cache, latency by model (bearer-auth scrape).
- **llama-swap** (`llama-swap:8080/metrics`, job `llama-swap`) — the on-demand model loader on the RTX 3090
  (replaced the always-on `llama-arc` container, 2026-07-01). Exposes `llamaswap_*` system + GPU gauges
  (util/power/temp/VRAM/fan). Scraped directly over the shared `litellm_default` docker network (no auth,
  internal only). Per-token `llamacpp:*` metrics are **not** scraped — they live on the upstream
  llama-server behind `/upstream/<model>` and scraping them would trigger a model load and fight the idle TTL.
- **OpenClaw diagnostics** — a host-side script scrapes the gateway's `/api/diagnostics/prometheus`
  over **loopback** and republishes it via the textfile collector (avoids exposing the gateway port to
  containers). See [agents.md](agents.md).
- **docker_sd_configs** — any container labeled `prometheus.scrape=true` is auto-discovered.
- *(optional)* a **virtualization-host exporter** via a private compose overlay.

## Agent / AI telemetry (OTLP push) — traces, metrics, logs
The OTel Collector receives OTLP and fans out to these backends (plus ClickHouse for governed-fleet
span analytics, and **Arize Phoenix** as a second trace backend; see the README "Phoenix" section):
- **Traces → Tempo** — from the OpenClaw `diagnostics-otel` plugin (per-run spans).
- **Metrics → Prometheus** — collector-exported; plus **Claude Code** native OTel metrics
  (`claude_code_*`, by model / type / `query_source`).
- **Logs → Loki** — **Claude Code per-request events** (`claude_code.api_request`: model, tokens, tool
  calls). This pipeline was added so those events aren't dropped; queryable as `{service_name="claude-code"}`.

Content capture (prompt/response bodies) is **enabled** (2026-09-25, owner decision). The former
collector scrub of `gen_ai.*` message attributes was removed, so content reaches Tempo, Loki and Phoenix.

## Grafana
Provisioned datasources (**Prometheus + Tempo + Loki**) and dashboards (as code in
`grafana/dashboards/{infrastructure,ai-agents}/`, built by `bin/gen-dashboards.py`), grouped into
**Infrastructure** and **AI & Agents** folders. Exemplars link latency panels to traces. See
[dashboards.md](dashboards.md).

## Why textfile collectors for accelerators + OpenClaw?
- Intel NPU has no Prometheus exporter; its sysfs counters are trivially scraped by a tiny script.
- `intel_gpu_top` / `nvidia-smi` need host access; running them on the host (not a privileged container)
  is safer and avoids giving a container GPU access just to read counters.
- The OpenClaw gateway is firewalled to the LAN; scraping it over loopback avoids opening the port to
  the Docker bridge. All publish through node_exporter's textfile directory.

> **Firewall note:** node_exporter runs `network_mode: host`, so the dockerised Prometheus scrapes it via
> `host.docker.internal:9100`. With a default-DROP host `INPUT` policy this must be allowed
> (`iptables -A INPUT -s 172.16.0.0/12 -p tcp --dport 9100 -j ACCEPT`) or the **whole `node` job is down**
> (all host + accelerator metrics missing). See [hardware.md](hardware.md).
