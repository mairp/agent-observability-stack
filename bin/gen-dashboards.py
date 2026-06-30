#!/usr/bin/env python3
"""Generate Grafana dashboard JSON into grafana/dashboards/.
Keeps panels consistent; re-run after editing. Output is committed as static JSON."""
import json, os, itertools

OUT = os.path.join(os.path.dirname(__file__), "..", "grafana", "dashboards")
PROM = {"type": "prometheus", "uid": "prometheus"}
TEMPO = {"type": "tempo", "uid": "tempo"}
LOKI = {"type": "loki", "uid": "loki"}
_id = itertools.count(1)


def ts(title, exprs, unit="short", w=12, h=8, x=0, y=0, legend="{{instance}}", stack=False):
    return {
        "id": next(_id), "type": "timeseries", "title": title,
        "datasource": PROM, "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "fieldConfig": {"defaults": {"unit": unit, "custom": {
            "drawStyle": "line", "fillOpacity": 18 if not stack else 40,
            "stacking": {"mode": "normal" if stack else "none"}}}, "overrides": []},
        "options": {"legend": {"displayMode": "table", "placement": "bottom", "calcs": ["lastNotNull", "max"]},
                    "tooltip": {"mode": "multi"}},
        "targets": [{"refId": chr(65 + i), "datasource": PROM, "expr": e[0],
                     "legendFormat": e[1] if len(e) > 1 else legend} for i, e in enumerate(exprs)],
    }


def stat(title, expr, unit="short", w=6, h=4, x=0, y=0, legend="", thresholds=None, color="thresholds"):
    return {
        "id": next(_id), "type": "stat", "title": title, "datasource": PROM,
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "fieldConfig": {"defaults": {"unit": unit, "color": {"mode": color},
            "thresholds": {"mode": "absolute", "steps": thresholds or [{"color": "green", "value": None}]}}, "overrides": []},
        "options": {"colorMode": "value", "graphMode": "area", "reduceOptions": {"calcs": ["lastNotNull"]}},
        "targets": [{"refId": "A", "datasource": PROM, "expr": expr, "legendFormat": legend}],
    }


def table(title, expr, w=12, h=8, x=0, y=0):
    return {
        "id": next(_id), "type": "table", "title": title, "datasource": PROM,
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "targets": [{"refId": "A", "datasource": PROM, "expr": expr, "format": "table", "instant": True}],
        "fieldConfig": {"defaults": {}, "overrides": []},
    }


def traces(title, w=24, h=10, x=0, y=0):
    return {
        "id": next(_id), "type": "table", "title": title, "datasource": TEMPO,
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "targets": [{"refId": "A", "datasource": TEMPO, "queryType": "traceql",
                     "query": '{}', "limit": 20, "tableType": "traces"}],
    }


def logs(title, expr, w=24, h=10, x=0, y=0):
    return {
        "id": next(_id), "type": "logs", "title": title, "datasource": LOKI,
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "options": {"showTime": True, "wrapLogMessage": True, "dedupStrategy": "none",
                    "sortOrder": "Descending", "enableLogDetails": True},
        "targets": [{"refId": "A", "datasource": LOKI, "expr": expr, "queryType": "range"}],
    }


def lts(title, exprs, unit="short", w=12, h=8, x=0, y=0, stack=False):
    """Timeseries from Loki LogQL metric queries."""
    return {
        "id": next(_id), "type": "timeseries", "title": title, "datasource": LOKI,
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "fieldConfig": {"defaults": {"unit": unit, "custom": {
            "drawStyle": "line", "fillOpacity": 18 if not stack else 40,
            "stacking": {"mode": "normal" if stack else "none"}}}, "overrides": []},
        "options": {"legend": {"displayMode": "table", "placement": "bottom", "calcs": ["lastNotNull", "max"]},
                    "tooltip": {"mode": "multi"}},
        "targets": [{"refId": chr(65 + i), "datasource": LOKI, "expr": e[0],
                     "legendFormat": e[1] if len(e) > 1 else "{{agent_type}}", "queryType": "range"}
                    for i, e in enumerate(exprs)],
    }


def lstat(title, expr, unit="short", w=6, h=4, x=0, y=0, thresholds=None):
    """Stat from a Loki LogQL instant query (persistent totals over the dashboard range)."""
    return {
        "id": next(_id), "type": "stat", "title": title, "datasource": LOKI,
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "fieldConfig": {"defaults": {"unit": unit, "color": {"mode": "thresholds"},
            "thresholds": {"mode": "absolute", "steps": thresholds or [{"color": "green", "value": None}]}}, "overrides": []},
        "options": {"colorMode": "value", "graphMode": "area", "reduceOptions": {"calcs": ["lastNotNull"]}},
        "targets": [{"refId": "A", "datasource": LOKI, "expr": expr, "queryType": "instant"}],
    }


def lbar(title, expr, unit="short", w=12, h=8, x=0, y=0):
    """Bar gauge from a Loki LogQL instant query (e.g. totals by agent_type over the range)."""
    return {
        "id": next(_id), "type": "bargauge", "title": title, "datasource": LOKI,
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "fieldConfig": {"defaults": {"unit": unit, "color": {"mode": "palette-classic"}}, "overrides": []},
        "options": {"displayMode": "gradient", "orientation": "horizontal", "reduceOptions": {"calcs": ["lastNotNull"]}},
        "targets": [{"refId": "A", "datasource": LOKI, "expr": expr, "queryType": "instant", "legendFormat": "{{agent_type}}"}],
    }


def barg(title, exprs, unit="bytes", w=12, h=8, x=0, y=0):
    """Stacked bar gauge for a breakdown (e.g. memory by consumer)."""
    return {
        "id": next(_id), "type": "bargauge", "title": title, "datasource": PROM,
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "fieldConfig": {"defaults": {"unit": unit, "color": {"mode": "palette-classic"}}, "overrides": []},
        "options": {"displayMode": "gradient", "orientation": "horizontal", "reduceOptions": {"calcs": ["lastNotNull"]}},
        "targets": [{"refId": chr(65 + i), "datasource": PROM, "expr": e[0], "legendFormat": e[1], "instant": True}
                    for i, e in enumerate(exprs)],
    }


def var_query(name, query, ds=PROM):
    return {"name": name, "type": "query", "datasource": ds, "query": query,
            "includeAll": True, "multi": True, "refresh": 2, "current": {"text": "All", "value": "$__all"}}


def dashboard(title, uid, panels, tags, refresh="30s", templating=None):
    if templating is None:
        templating = [var_query("model", "label_values(litellm_spend_metric_total, model)")]
    return {"uid": uid, "title": title, "tags": tags, "schemaVersion": 39, "version": 1,
            "editable": True, "refresh": refresh, "time": {"from": "now-6h", "to": "now"},
            "timezone": "browser", "panels": panels, "templating": {"list": templating}}


def write(d, folder="."):
    dest = os.path.join(OUT, folder)
    os.makedirs(dest, exist_ok=True)
    p = os.path.join(dest, d["uid"] + ".json")
    json.dump(d, open(p, "w"), indent=2)
    print("wrote", os.path.relpath(p))


# ---------------- Host / System ----------------
_id = itertools.count(1)
host = [
    stat("CPU busy", '100-(avg(rate(node_cpu_seconds_total{mode="idle"}[5m]))*100)', "percent", 6, 4, 0, 0,
         thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 75}, {"color": "red", "value": 90}]),
    stat("Mem used", '(1-node_memory_MemAvailable_bytes/node_memory_MemTotal_bytes)*100', "percent", 6, 4, 6, 0,
         thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 80}, {"color": "red", "value": 90}]),
    stat("Uptime", 'node_time_seconds-node_boot_time_seconds', "s", 6, 4, 12, 0),
    stat("Running VMs/CTs", 'sum(pve_up{id=~"qemu/.*|lxc/.*"})', "short", 6, 4, 18, 0),
    ts("CPU by mode", [('sum by (mode)(rate(node_cpu_seconds_total{mode!="idle"}[5m]))', "{{mode}}")], "short", 12, 8, 0, 4, stack=True),
    ts("Memory", [('node_memory_MemTotal_bytes', "total"), ('node_memory_MemTotal_bytes-node_memory_MemAvailable_bytes', "used")], "bytes", 12, 8, 12, 4),
    ts("Load average", [('node_load1', "1m"), ('node_load5', "5m"), ('node_load15', "15m")], "short", 12, 8, 0, 12),
    ts("Disk usage %", [('(1-node_filesystem_avail_bytes{fstype!~"tmpfs|overlay"}/node_filesystem_size_bytes{fstype!~"tmpfs|overlay"})*100', "{{mountpoint}}")], "percent", 12, 8, 12, 12),
    ts("Network throughput (rx)", [('rate(node_network_receive_bytes_total{device!~"lo|veth.*|docker.*|br-.*"}[5m])*8', "{{device}}")], "bps", 12, 8, 0, 20),
    ts("Network throughput (tx)", [('rate(node_network_transmit_bytes_total{device!~"lo|veth.*|docker.*|br-.*"}[5m])*8', "{{device}}")], "bps", 12, 8, 12, 20),
    ts("CPU temperature", [('node_hwmon_temp_celsius', "{{chip}} {{sensor}}")], "celsius", 24, 8, 0, 28),
    # ----- Memory breakdown: system RAM and how much is iGPU / NPU (they share system RAM) -----
    stat("Mem used %", '(1-node_memory_MemAvailable_bytes/node_memory_MemTotal_bytes)*100', "percent", 6, 4, 0, 36,
         thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 80}, {"color": "red", "value": 90}]),
    stat("iGPU mem % of RAM", 'intel_gpu_memory_bytes{type="resident"}/ignoring(type) node_memory_MemTotal_bytes*100', "percent", 6, 4, 6, 36),
    stat("NPU mem % of RAM", 'intel_npu_memory_bytes/node_memory_MemTotal_bytes*100', "percent", 6, 4, 12, 36),
    stat("Mem available", 'node_memory_MemAvailable_bytes', "bytes", 6, 4, 18, 36),
    barg("Where's my RAM (bytes)", [
        ('scalar(node_memory_MemTotal_bytes-node_memory_MemAvailable_bytes)-scalar(intel_gpu_memory_bytes{type="resident"} or vector(0))-scalar(intel_npu_memory_bytes or vector(0))', "processes (CPU)"),
        ('scalar(intel_gpu_memory_bytes{type="resident"} or vector(0))', "iGPU"),
        ('scalar(intel_npu_memory_bytes or vector(0))', "NPU"),
        ('scalar(node_memory_MemAvailable_bytes)', "free"),
    ], "bytes", 12, 8, 0, 40),
    ts("Memory: used vs iGPU vs NPU", [
        ('node_memory_MemTotal_bytes-node_memory_MemAvailable_bytes', "used (total)"),
        ('intel_gpu_memory_bytes{type="resident"}', "iGPU"),
        ('intel_npu_memory_bytes', "NPU"),
    ], "bytes", 12, 8, 12, 40),
    # ----- Top processes (who is consuming memory / CPU) — process-exporter -----
    ts("Top processes by memory (RSS)", [('topk(10, sum by (groupname)(namedprocess_namegroup_memory_bytes{memtype="resident"}))', "{{groupname}}")], "bytes", 12, 9, 0, 48, stack=True),
    ts("Top processes by CPU (cores)", [('topk(10, sum by (groupname)(rate(namedprocess_namegroup_cpu_seconds_total[5m])))', "{{groupname}}")], "short", 12, 9, 12, 48, stack=True),
    table("Top memory consumers (process)", 'topk(15, sum by (groupname)(namedprocess_namegroup_memory_bytes{memtype="resident"}))', 12, 9, 0, 57),
    table("Top CPU consumers (process)", 'topk(15, sum by (groupname)(rate(namedprocess_namegroup_cpu_seconds_total[5m])))', 12, 9, 12, 57),
]
write(dashboard("Host / System", "host", host, ["infra", "host"]), "infrastructure")

# ---------------- Accelerators (iGPU + NPU) ----------------
_id = itertools.count(1)
acc = [
    stat("NPU busy", 'clamp_max(rate(intel_npu_busy_time_us[5m])/1e6*100,100)', "percent", 6, 4, 0, 0,
         thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 70}, {"color": "red", "value": 95}]),
    stat("NPU freq", 'intel_npu_frequency_mhz{type="current"}', "rotmhz", 6, 4, 6, 0),
    stat("NPU mem", 'intel_npu_memory_bytes', "bytes", 6, 4, 12, 0),
    stat("iGPU busy (max engine)", 'max(intel_gpu_engine_busy_ratio)*100', "percent", 6, 4, 18, 0,
         thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 70}, {"color": "red", "value": 95}]),
    ts("NPU utilization", [('clamp_max(rate(intel_npu_busy_time_us[5m])/1e6*100,100)', "busy %")], "percent", 12, 8, 0, 4),
    ts("NPU frequency", [('intel_npu_frequency_mhz{type="current"}', "current"), ('intel_npu_frequency_mhz{type="max"}', "max")], "rotmhz", 12, 8, 12, 4),
    ts("iGPU engine busy %", [('intel_gpu_engine_busy_ratio*100', "{{engine}}")], "percent", 12, 8, 0, 12),
    ts("iGPU frequency", [('intel_gpu_frequency_mhz', "{{type}}")], "rotmhz", 6, 8, 12, 12),
    ts("iGPU power", [('intel_gpu_power_watts', "{{domain}}")], "watt", 6, 8, 18, 12),
    # ----- Accelerator memory (shared system RAM) -----
    stat("iGPU mem (resident)", 'intel_gpu_memory_bytes{type="resident"}', "bytes", 6, 4, 0, 20),
    stat("iGPU clients", 'intel_gpu_clients', "short", 6, 4, 6, 20),
    stat("NPU mem", 'intel_npu_memory_bytes', "bytes", 6, 4, 12, 20),
    stat("Accel mem % of RAM", '(scalar(intel_gpu_memory_bytes{type="resident"} or vector(0))+scalar(intel_npu_memory_bytes or vector(0)))/scalar(node_memory_MemTotal_bytes)*100', "percent", 6, 4, 18, 20),
    ts("iGPU memory (resident vs total)", [('intel_gpu_memory_bytes{type="resident"}', "resident"), ('intel_gpu_memory_bytes{type="total"}', "total")], "bytes", 12, 8, 0, 24),
    ts("NPU memory", [('intel_npu_memory_bytes', "npu mem")], "bytes", 12, 8, 12, 24),
    # ----- NVIDIA dGPU (nvidia-smi textfile collector) — the CUDA inference card -----
    stat("NVIDIA GPU util", 'nvidia_gpu_utilization_ratio*100', "percent", 6, 4, 0, 32,
         thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 70}, {"color": "red", "value": 95}]),
    stat("NVIDIA VRAM used %", 'nvidia_gpu_memory_used_bytes/nvidia_gpu_memory_total_bytes*100', "percent", 6, 4, 6, 32,
         thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 85}, {"color": "red", "value": 95}]),
    stat("NVIDIA temp", 'nvidia_gpu_temperature_celsius', "celsius", 6, 4, 12, 32,
         thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 75}, {"color": "red", "value": 85}]),
    stat("NVIDIA power", 'nvidia_gpu_power_watts', "watt", 6, 4, 18, 32,
         thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 300}, {"color": "red", "value": 400}]),
    ts("NVIDIA GPU utilization %", [('nvidia_gpu_utilization_ratio*100', "{{name}}")], "percent", 12, 8, 0, 36),
    ts("NVIDIA VRAM (used / free / total)", [('nvidia_gpu_memory_used_bytes', "used"),
        ('nvidia_gpu_memory_free_bytes', "free"), ('nvidia_gpu_memory_total_bytes', "total")], "bytes", 12, 8, 12, 36),
    ts("NVIDIA per-process VRAM", [('nvidia_gpu_process_memory_bytes', "{{process}} (pid {{pid}})")], "bytes", 12, 8, 0, 44),
    ts("NVIDIA power: draw vs limit", [('nvidia_gpu_power_watts', "draw"),
        ('nvidia_gpu_power_limit_watts', "limit")], "watt", 6, 8, 12, 44),
    ts("NVIDIA clocks (SM / mem)", [('nvidia_gpu_clock_sm_mhz', "SM"),
        ('nvidia_gpu_clock_mem_mhz', "mem")], "rotmhz", 6, 8, 18, 44),
]
write(dashboard("Accelerators (NVIDIA + iGPU + NPU)", "accelerators", acc, ["infra", "gpu", "npu", "nvidia"]), "infrastructure")

# ---------------- Network ----------------
_id = itertools.count(1)
net = [
    stat("Targets up", 'sum(probe_success)', "short", 6, 4, 0, 0),
    stat("Targets down", 'sum(probe_success==0)', "short", 6, 4, 6, 0,
         thresholds=[{"color": "green", "value": None}, {"color": "red", "value": 1}]),
    stat("Internet RTT (1.1.1.1)", 'probe_duration_seconds{instance="1.1.1.1"}', "s", 6, 4, 12, 0),
    stat("example.com latency", 'probe_duration_seconds{instance="https://example.com"}', "s", 6, 4, 18, 0),
    ts("Probe latency", [('probe_duration_seconds', "{{instance}}")], "s", 24, 9, 0, 4),
    table("Probe status", 'probe_success', 12, 8, 0, 13),
    ts("HTTP status code", [('probe_http_status_code', "{{instance}}")], "short", 12, 8, 12, 13),
]
write(dashboard("Network & Connectivity", "network", net, ["infra", "network"]), "infrastructure")

# ---------------- Agents (cost / latency / traces) ----------------
# OpenClaw model metrics: call counts + latency (by model/outcome). Tokens + cost: LiteLLM (by model).
# Per-agent drill-down: Tempo traces (service openclaw-gateway). No `agent` label on metrics in 2026.6.5.
_id = itertools.count(1)
ag = [
    stat("Spend (24h)", 'sum(increase(litellm_spend_metric_total[24h]))', "currencyUSD", 6, 4, 0, 0),
    stat("Tokens (24h)", 'sum(increase(litellm_total_tokens_metric_total[24h]))', "short", 6, 4, 6, 0),
    stat("Model calls (1h)", 'sum(increase(openclaw_model_call_total[1h]))', "short", 6, 4, 12, 0),
    stat("Errors (1h)", 'sum(increase(openclaw_model_call_total{outcome!="completed"}[1h])) or vector(0)', "short", 6, 4, 18, 0,
         thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 1}, {"color": "red", "value": 5}]),
    ts("Cost by model (1h rate)", [('sum by (model)(rate(litellm_spend_metric_total{model=~"$model"}[1h]))*3600', "{{model}} $/h")], "currencyUSD", 12, 8, 0, 4, stack=True),
    ts("Tokens by type", [('sum(rate(litellm_input_tokens_metric_total{model=~"$model"}[5m]))', "input"),
                          ('sum(rate(litellm_output_tokens_metric_total{model=~"$model"}[5m]))', "output"),
                          ('sum(rate(litellm_cached_tokens_metric_total[5m]))', "cached"),
                          ('sum(rate(litellm_output_reasoning_tokens_metric_total[5m]))', "reasoning")], "short", 12, 8, 12, 4),
    ts("Model-call p95 / p50 latency", [('histogram_quantile(0.95, sum by (le,model)(rate(openclaw_model_call_duration_seconds_bucket[5m])))', "p95 {{model}}"),
                                        ('histogram_quantile(0.50, sum by (le,model)(rate(openclaw_model_call_duration_seconds_bucket[5m])))', "p50 {{model}}")], "s", 12, 8, 0, 12),
    ts("Call outcomes", [('sum by (outcome)(rate(openclaw_model_call_total[5m]))', "{{outcome}}")], "short", 6, 8, 12, 12, stack=True),
    ts("Prompt cache hit ratio (cached input tokens)", [('sum(rate(litellm_input_cached_tokens_metric_total[30m]))/clamp_min(sum(rate(litellm_input_tokens_metric_total[30m])),1)', "cache hit ratio")], "percentunit", 6, 8, 18, 12),
    # ----- enriched from the broader openclaw_* family -----
    ts("Run duration p95 / p50", [('histogram_quantile(0.95, sum by (le)(rate(openclaw_run_duration_seconds_bucket[10m])))', "p95"),
                                   ('histogram_quantile(0.50, sum by (le)(rate(openclaw_run_duration_seconds_bucket[10m])))', "p50")], "s", 8, 7, 0, 20),
    ts("Model-call errors by category", [('sum by (error_category)(rate(openclaw_model_call_total{error_category!="none"}[10m]))', "{{error_category}}")], "short", 8, 7, 8, 20),
    ts("Queue depth / lane size", [('openclaw_session_queue_depth', "session q"), ('sum(openclaw_queue_lane_size)', "lane size")], "short", 8, 7, 16, 20),
    table("Agent inventory (auto-onboarded)", 'openclaw_agent_info', 24, 6, 0, 27),
    traces("Recent agent traces (Tempo — click to drill into a run)", 24, 10, 0, 33),
]
write(dashboard("OpenClaw Agents — Cost, Latency & Traces", "agents", ag, ["agents", "llm"]), "ai-agents")

# ---------------- Claude Code (by model + agent/subagent) ----------------
# claude_code.* OTel metrics -> Prometheus. token_usage labels: model, type
# (input/output/cacheRead/cacheCreation), query_source (main/subagent), session_id.
# Detailed per-request EVENTS -> Loki (logs panel below). Metrics are session-driven.
_id = itertools.count(1)
# Claude Code's OTLP *metrics* are unreliable for real usage: short sessions exit before the 10s
# metric flush, and the counters are ephemeral (they vanish ~5min after a session ends). The per-request
# `api_request` LOG events are exported immediately and PERSIST in Loki — so the consumption panels are
# driven from Loki. Fields on api_request: cost_usd, input_tokens, output_tokens, cache_read_tokens,
# cache_creation_tokens, model, duration_ms. Subagents come from subagent_completed (agent_type, model,
# total_tokens). All totals below are over the dashboard time range ($__range) — true persistent history.
CC = '{service_name="claude-code"} | event_name=`api_request`'
cc = [
    lstat("Cost (range)", f'sum(sum_over_time({CC} | unwrap cost_usd [$__range]))', "currencyUSD", 6, 4, 0, 0),
    lstat("Output tokens", f'sum(sum_over_time({CC} | unwrap output_tokens [$__range]))', "short", 6, 4, 6, 0),
    lstat("Cache-read tokens", f'sum(sum_over_time({CC} | unwrap cache_read_tokens [$__range]))', "short", 6, 4, 12, 0),
    lstat("Requests", f'sum(count_over_time({CC} [$__range]))', "short", 6, 4, 18, 0),
    lts("Cost by MODEL", [(f'sum by (model)(sum_over_time({CC} | unwrap cost_usd [$__interval]))', "{{model}}")], "currencyUSD", 12, 8, 0, 4, stack=True),
    lts("Tokens by TYPE (in / out / cacheRead / cacheCreation)", [
        (f'sum(sum_over_time({CC} | unwrap input_tokens [$__interval]))', "input"),
        (f'sum(sum_over_time({CC} | unwrap output_tokens [$__interval]))', "output"),
        (f'sum(sum_over_time({CC} | unwrap cache_read_tokens [$__interval]))', "cacheRead"),
        (f'sum(sum_over_time({CC} | unwrap cache_creation_tokens [$__interval]))', "cacheCreation")], "short", 12, 8, 12, 4, stack=True),
    lts("Output tokens by MODEL", [(f'sum by (model)(sum_over_time({CC} | unwrap output_tokens [$__interval]))', "{{model}}")], "short", 12, 8, 0, 12, stack=True),
    lts("Requests by MODEL", [(f'sum by (model)(count_over_time({CC} [$__interval]))', "{{model}}")], "short", 12, 8, 12, 12, stack=True),
    lbar("Cache-read tokens by MODEL (range)", f'sum by (model)(sum_over_time({CC} | unwrap cache_read_tokens [$__range]))', "short", 12, 8, 0, 20),
    lts("Request latency p95 (by model)", [(f'quantile_over_time(0.95, {CC} | unwrap duration_ms [$__interval]) by (model)', "{{model}}")], "ms", 12, 8, 12, 20),
    # ----- Named subagents (from Loki subagent_completed events: agent_type, model, total_tokens) -----
    lbar("Subagent runs by type", 'sum by (agent_type) (count_over_time({service_name="claude-code"} | event_name=`subagent_completed` [$__range]))', "short", 12, 8, 0, 28),
    lbar("Subagent tokens by type", 'sum by (agent_type) (sum_over_time({service_name="claude-code"} | event_name=`subagent_completed` | unwrap total_tokens [$__range]))', "short", 12, 8, 12, 28),
    lts("Subagent tokens over time (by type)", [('sum by (agent_type) (sum_over_time({service_name="claude-code"} | event_name=`subagent_completed` | unwrap total_tokens [$__interval]))', "{{agent_type}}")], "short", 12, 8, 0, 36, stack=True),
    lts("Subagent activity (by model)", [('sum by (model) (count_over_time({service_name="claude-code"} | event_name=`subagent_completed` [$__interval]))', "{{model}}")], "short", 12, 8, 12, 36, stack=True),
    logs("Recent Claude Code events (Loki — request/tool/subagent: model, tokens, agent_type)", '{service_name="claude-code"}', 24, 11, 0, 44),
]
write(dashboard("Claude Code", "claude-code", cc, ["ai", "claude-code"]), "ai-agents")

# ---------------- LLM Cost & Consumption (unified Claude Code + LiteLLM/OpenClaw) ----------------
_id = itertools.count(1)
# Two cost sources: Claude Code (persistent Loki api_request events) + OpenClaw/LiteLLM (persistent
# litellm_* Prometheus metrics — these run continuously so the counters don't go stale like Claude's do).
CCC = '{service_name="claude-code"} | event_name=`api_request`'
cost = [
    lstat("Claude Code spend (range)", f'sum(sum_over_time({CCC} | unwrap cost_usd [$__range]))', "currencyUSD", 8, 4, 0, 0),
    lstat("Claude Code requests", f'sum(count_over_time({CCC} [$__range]))', "short", 8, 4, 8, 0),
    stat("OpenClaw/LiteLLM spend (24h)", 'sum(increase(litellm_spend_metric_total[24h])) or vector(0)', "currencyUSD", 8, 4, 16, 0),
    lts("Claude Code spend by model", [(f'sum by (model)(sum_over_time({CCC} | unwrap cost_usd [$__interval]))', "{{model}}")], "currencyUSD", 12, 8, 0, 4, stack=True),
    ts("OpenClaw/LiteLLM spend by model (1h rate)", [('sum by (model)(rate(litellm_spend_metric_total[1h]))*3600', "{{model}} $/h")], "currencyUSD", 12, 8, 12, 4, stack=True),
    lts("Claude Code tokens by type", [
        (f'sum(sum_over_time({CCC} | unwrap input_tokens [$__interval]))', "input"),
        (f'sum(sum_over_time({CCC} | unwrap output_tokens [$__interval]))', "output"),
        (f'sum(sum_over_time({CCC} | unwrap cache_read_tokens [$__interval]))', "cacheRead")], "short", 12, 8, 0, 12, stack=True),
    ts("OpenClaw/LiteLLM tokens/s", [('sum(rate(litellm_total_tokens_metric_total[5m]))', "total tok/s"),
                                     ('sum(rate(litellm_input_cached_tokens_metric_total[10m]))', "cached read")], "short", 12, 8, 12, 12, stack=True),
    lbar("Claude Code cache-read tokens by model (range)", f'sum by (model)(sum_over_time({CCC} | unwrap cache_read_tokens [$__range]))', "short", 12, 8, 0, 20),
    table("OpenClaw/LiteLLM spend by model (24h)", 'sum by (model)(increase(litellm_spend_metric_total[24h]))', 12, 8, 12, 20),
]
write(dashboard("LLM Cost & Consumption", "llm-cost", cost, ["ai", "cost"]), "ai-agents")

# ---------------- RAG / Memory (QMD) ----------------
_id = itertools.count(1)
rag = [
    stat("RAG docs (all indexes)", 'sum(qmd_documents_total)', "short", 8, 4, 0, 0),
    stat("RAG vectors (all)", 'sum(qmd_vectors_total)', "short", 8, 4, 8, 0),
    stat("Indexes", 'count(qmd_documents_total)', "short", 8, 4, 16, 0),
    ts("Docs per index", [('qmd_documents_total', "{{index}}")], "short", 12, 8, 0, 4),
    ts("Vectors per index", [('qmd_vectors_total', "{{index}}")], "short", 12, 8, 12, 4),
    table("RAG indexes — docs / vectors / size", 'qmd_documents_total or qmd_vectors_total or qmd_index_size_bytes', 12, 8, 0, 12),
    ts("Index freshness (age)", [('qmd_index_age_seconds', "{{index}}")], "s", 12, 8, 12, 12),
]
write(dashboard("RAG / Memory (QMD)", "rag", rag, ["ai", "rag"]), "ai-agents")

# ---------------- LLM Inference (llama.cpp + MTP speculative decoding) ----------------
# llama.cpp server-cuda (RTX 3090) runs with --metrics → llamacpp:* (job "llama-arc"). The MTP
# speculative-decoding signal = tokens_predicted_total / n_decode_total (≈ tokens accepted per decode;
# 1.0 = no speculation, >1 = drafts accepted). No llamacpp:kv_cache_* in this build. BASELINE = the
# measured no-MTP decode tok/s (reference line so the speedup is visible on the throughput panel).
_id = itertools.count(1)
BASELINE = "41"
DECODE = 'rate(llamacpp:tokens_predicted_total[1m])/clamp_min(rate(llamacpp:tokens_predicted_seconds_total[1m]),0.001)'
PREFILL = 'rate(llamacpp:prompt_tokens_total[1m])/clamp_min(rate(llamacpp:prompt_seconds_total[1m]),0.001)'
ACCEPT = 'rate(llamacpp:tokens_predicted_total[5m])/clamp_min(rate(llamacpp:n_decode_total[5m]),0.001)'
inf = [
    stat("Decode tok/s (live)", 'llamacpp:predicted_tokens_seconds', "short", 6, 4, 0, 0,
         thresholds=[{"color": "red", "value": None}, {"color": "orange", "value": 40}, {"color": "green", "value": 50}]),
    stat("Prefill tok/s (live)", 'llamacpp:prompt_tokens_seconds', "short", 6, 4, 6, 0),
    stat("MTP tokens/decode", 'llamacpp:tokens_predicted_total/clamp_min(llamacpp:n_decode_total,1)', "short", 6, 4, 12, 0,
         thresholds=[{"color": "red", "value": None}, {"color": "orange", "value": 1.2}, {"color": "green", "value": 1.6}]),
    stat("Requests processing", 'llamacpp:requests_processing', "short", 6, 4, 18, 0),
    ts("Decode throughput (tok/s) vs no-MTP baseline", [(DECODE, "decode tok/s"), (BASELINE, "baseline (no-MTP)")], "short", 12, 8, 0, 4),
    ts("Prefill throughput (tok/s)", [(PREFILL, "prefill tok/s")], "short", 12, 8, 12, 4),
    ts("MTP effectiveness — tokens accepted per decode (1.0 = no speculation)", [(ACCEPT, "tokens/decode"), ("1", "no-spec floor")], "short", 12, 8, 0, 12),
    ts("Requests: processing / deferred", [('llamacpp:requests_processing', "processing"), ('llamacpp:requests_deferred', "deferred")], "short", 12, 8, 12, 12),
    ts("Token volume (rate)", [('rate(llamacpp:tokens_predicted_total[5m])', "generated tok/s"), ('rate(llamacpp:prompt_tokens_total[5m])', "prompt tok/s")], "short", 12, 8, 0, 20),
    ts("GPU VRAM: used / free (3090)", [('nvidia_gpu_memory_used_bytes', "used"), ('nvidia_gpu_memory_free_bytes', "free")], "bytes", 12, 8, 12, 20),
]
write(dashboard("LLM Inference — llama.cpp + MTP (RTX 3090)", "inference-llama", inf, ["ai", "inference", "llama.cpp", "mtp"], templating=[]), "ai-agents")

# ---------------- Containers ----------------
_id = itertools.count(1)
cn = [
    ts("Container CPU", [('sum by (name)(rate(container_cpu_usage_seconds_total{name!=""}[5m]))', "{{name}}")], "short", 12, 9, 0, 0, stack=True),
    ts("Container memory", [('sum by (name)(container_memory_working_set_bytes{name!=""})', "{{name}}")], "bytes", 12, 9, 12, 0),
    ts("Container net rx", [('sum by (name)(rate(container_network_receive_bytes_total{name!=""}[5m]))', "{{name}}")], "Bps", 12, 9, 0, 9),
    ts("Container net tx", [('sum by (name)(rate(container_network_transmit_bytes_total{name!=""}[5m]))', "{{name}}")], "Bps", 12, 9, 12, 9),
]
write(dashboard("Containers", "containers", cn, ["infra", "containers"]), "infrastructure")
print("done")
