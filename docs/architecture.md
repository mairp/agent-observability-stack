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
- **LiteLLM** `/metrics/` — tokens, spend, cache, latency by model (bearer-auth scrape).
- **OpenClaw diagnostics** — a host-side script scrapes the gateway's `/api/diagnostics/prometheus`
  over **loopback** and republishes it via the textfile collector (avoids exposing the gateway port to
  containers). See [agents.md](agents.md).
- **docker_sd_configs** — any container labeled `prometheus.scrape=true` is auto-discovered.
- *(optional)* a **virtualization-host exporter** via a private compose overlay.

## Agent / AI telemetry (OTLP push) — traces, metrics, logs
The OTel Collector receives OTLP and fans out to three backends:
- **Traces → Tempo** — from the OpenClaw `diagnostics-otel` plugin (per-run spans).
- **Metrics → Prometheus** — collector-exported; plus **Claude Code** native OTel metrics
  (`claude_code_*`, by model / type / `query_source`).
- **Logs → Loki** — **Claude Code per-request events** (`claude_code.api_request`: model, tokens, tool
  calls). This pipeline was added so those events aren't dropped; queryable as `{service_name="claude-code"}`.

Content capture (prompt/response bodies) is **disabled**; the collector additionally scrubs any
`gen_ai.*` message attributes on traces **and** logs defensively (metadata/counts only).

## Grafana
Provisioned datasources (**Prometheus + Tempo + Loki**) and dashboards (as code in
`grafana/dashboards/{infrastructure,ai-agents}/`, built by `bin/gen-dashboards.py`), grouped into
**Infrastructure** and **AI & Agents** folders. Exemplars link latency panels to traces. See
[dashboards.md](dashboards.md).

## Why textfile collectors for accelerators + OpenClaw?
- Intel NPU has no Prometheus exporter; its sysfs counters are trivially scraped by a tiny script.
- `intel_gpu_top` needs host privileges; running it on the host (not a privileged container) is safer.
- The OpenClaw gateway is firewalled to the LAN; scraping it over loopback avoids opening the port to
  the Docker bridge. All three publish through node_exporter's textfile directory.
