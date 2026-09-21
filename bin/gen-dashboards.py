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


def text(title, content, w=24, h=3, x=0, y=0):
    return {
        "id": next(_id), "type": "text", "title": title,
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "options": {"mode": "markdown", "content": content},
    }


def table(title, expr, w=12, h=8, x=0, y=0):
    return {
        "id": next(_id), "type": "table", "title": title, "datasource": PROM,
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "targets": [{"refId": "A", "datasource": PROM, "expr": expr, "format": "table", "instant": True}],
        "fieldConfig": {"defaults": {}, "overrides": []},
    }


def tql(title, query, w=24, h=10, x=0, y=0, table_type="traces", limit=30):
    """Tempo TraceQL search rendered as a table (tableType: traces | spans)."""
    return {
        "id": next(_id), "type": "table", "title": title, "datasource": TEMPO,
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "targets": [{"refId": "A", "datasource": TEMPO, "queryType": "traceql",
                     "query": query, "limit": limit, "spss": 50, "tableType": table_type}],
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


def lbar(title, expr, unit="short", w=12, h=8, x=0, y=0, legend="{{agent_type}}"):
    """Bar gauge from a Loki LogQL instant query (e.g. totals by agent_type over the range)."""
    return {
        "id": next(_id), "type": "bargauge", "title": title, "datasource": LOKI,
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "fieldConfig": {"defaults": {"unit": unit, "color": {"mode": "palette-classic"}}, "overrides": []},
        "options": {"displayMode": "gradient", "orientation": "horizontal", "reduceOptions": {"calcs": ["lastNotNull"]}},
        "targets": [{"refId": "A", "datasource": LOKI, "expr": expr, "queryType": "instant", "legendFormat": legend}],
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
        templating = [var_query("model", "label_values(litellm_model_info, model)")]
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
    stat("Targets down", 'sum(probe_success==0) or vector(0)', "short", 6, 4, 6, 0,
         thresholds=[{"color": "green", "value": None}, {"color": "red", "value": 1}]),
    stat("Internet RTT (1.1.1.1)", 'probe_duration_seconds{instance="1.1.1.1"}', "s", 6, 4, 12, 0),
    stat("cws VM RTT (192.0.2.10)", 'probe_duration_seconds{instance="192.0.2.10"}', "s", 6, 4, 18, 0),
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

# ---------------- LLM Inference (RTX 3090 via llama-swap) ----------------
# The always-on `llama-arc` container was replaced by on-demand `llama-swap` (2026-07-01 migration).
# llama-swap's /metrics exposes only llamaswap_* SYSTEM + GPU gauges (util/power/temp/VRAM/fan) — NOT
# the old per-token llamacpp:* decode/prefill/MTP series. Those live on the upstream llama-server
# behind /upstream/<model> and scraping them would trigger a model load every interval and defeat the
# idle TTL, so they are intentionally out of scope here. Models load on demand and unload after 900s
# idle, so utilization/power/VRAM read near-zero when nothing is loaded — expected, not an outage.
_id = itertools.count(1)
NOTE = (
    "RTX 3090 GPU + system telemetry from **llama-swap** (`llamaswap_*` on `llama-swap:8080/metrics`), "
    "which replaced the always-on `llama-arc` container on 2026-07-01. Models load **on demand** and "
    "unload after 900s idle, so utilization/power/VRAM read near-zero when nothing is loaded — that is "
    "expected, not an outage. Per-token decode/prefill/MTP-acceptance metrics (the old `llamacpp:*` "
    "series) are **not collected**: they live only on the upstream llama-server behind `/upstream/<model>`, "
    "and scraping that path would trigger a model load every interval and defeat the idle TTL."
)
inf = [
    text("About this dashboard", NOTE, 24, 3, 0, 0),
    stat("GPU utilization", 'llamaswap_gpu_util_percent', "percent", 6, 4, 0, 3,
         thresholds=[{"color": "blue", "value": None}, {"color": "green", "value": 5}, {"color": "orange", "value": 90}]),
    stat("Power draw", 'llamaswap_gpu_power_draw_watts', "watt", 6, 4, 6, 3,
         thresholds=[{"color": "blue", "value": None}, {"color": "green", "value": 60}, {"color": "orange", "value": 380}]),
    stat("GPU temperature", 'llamaswap_gpu_temperature_celsius', "celsius", 6, 4, 12, 3,
         thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 75}, {"color": "red", "value": 84}]),
    stat("VRAM used", 'llamaswap_gpu_memory_used_bytes', "bytes", 6, 4, 18, 3,
         thresholds=[{"color": "blue", "value": None}, {"color": "green", "value": 1000000000}, {"color": "orange", "value": 23000000000}]),
    ts("GPU utilization (%)", [('llamaswap_gpu_util_percent', "compute"), ('llamaswap_gpu_memory_util_percent', "memory bandwidth")], "percent", 12, 8, 0, 7),
    ts("Power draw (W)", [('llamaswap_gpu_power_draw_watts', "power draw")], "watt", 12, 8, 12, 7),
    ts("Temperature (°C) — core / VRAM", [('llamaswap_gpu_temperature_celsius', "core"), ('llamaswap_gpu_vram_temperature_celsius', "vram (0 if unsupported)")], "celsius", 12, 8, 0, 15),
    ts("Fan speed (%)", [('llamaswap_gpu_fan_speed_percent', "fan")], "percent", 12, 8, 12, 15),
    ts("GPU VRAM: used / total (3090)", [('nvidia_gpu_memory_used_bytes', "used (node collector)"), ('nvidia_gpu_memory_total_bytes', "total")], "bytes", 12, 8, 0, 23),
    ts("Host load average", [('llamaswap_load_average', "load avg")], "short", 12, 8, 12, 23),
]
write(dashboard("LLM Inference — llama.cpp + MTP (RTX 3090)", "inference-llama", inf, ["ai", "inference", "llama.cpp", "llama-swap", "gpu"], templating=[]), "ai-agents")

# ---------------- Ralph Loops (autonomous Claude Code loops) ----------------
# Telemetry from utilities/ralph_loop.sh --stream-json (utilities/ralph_loki_ship.py).
# Loki stream labels (low-cardinality): job="ralph", task, backend, event, model.
# Per-request numbers (cost_usd, *_tokens, duration_ms, num_turns, is_error) live in the
# log line as logfmt -> queries do `| logfmt | unwrap <field>`. Events: run_start,
# iter_start, api_request (one per model turn), tool_use (one per tool call), gate,
# run_stop, run_end. All totals are over the dashboard range ($__range) = true history.
_id = itertools.count(1)
REQ  = '{job="ralph", event="api_request", task=~"$task"}'
TOOL = '{job="ralph", event="tool_use", task=~"$task"}'
ITER = '{job="ralph", event="iter_start", task=~"$task"}'
RUN  = '{job="ralph", event="run_start", task=~"$task"}'
GATE = '{job="ralph", event="gate", task=~"$task"}'
RNOTE = (
    "Autonomous Claude Code **Ralph loops** (`utilities/ralph_loop.sh --stream-json`). Each "
    "iteration is a fresh headless `claude` run; this dashboard tracks cost, tokens, tool "
    "use, iteration duration and gate outcomes per run. Use the **task** variable to focus "
    "one loop. Data is the persistent Loki event stream (`job=\"ralph\"`) over the time range."
)
ralph = [
    text("About this dashboard", RNOTE, 24, 3, 0, 0),
    lstat("Runs", f'sum(count_over_time({RUN} [$__range]))', "short", 4, 4, 0, 3),
    lstat("Iterations", f'sum(count_over_time({ITER} [$__range]))', "short", 4, 4, 4, 3),
    lstat("Cost (range)", f'sum(sum_over_time({REQ} | logfmt | unwrap cost_usd [$__range]))', "currencyUSD", 4, 4, 8, 3),
    lstat("Output tokens", f'sum(sum_over_time({REQ} | logfmt | unwrap output_tokens [$__range]))', "short", 4, 4, 12, 3),
    lstat("Tool calls", f'sum(count_over_time({TOOL} [$__range]))', "short", 4, 4, 16, 3),
    lstat("Errored requests", f'sum(count_over_time({REQ} | logfmt | is_error="true" [$__range]))', "short", 4, 4, 20, 3,
          thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 1}, {"color": "red", "value": 5}]),
    # ----- cost / tokens over time -----
    lts("Cost by model", [(f'sum by (model)(sum_over_time({REQ} | logfmt | unwrap cost_usd [$__interval]))', "{{model}}")], "currencyUSD", 12, 8, 0, 7, stack=True),
    lts("Tokens by type", [
        (f'sum(sum_over_time({REQ} | logfmt | unwrap input_tokens [$__interval]))', "input"),
        (f'sum(sum_over_time({REQ} | logfmt | unwrap output_tokens [$__interval]))', "output"),
        (f'sum(sum_over_time({REQ} | logfmt | unwrap cache_read_tokens [$__interval]))', "cacheRead"),
        (f'sum(sum_over_time({REQ} | logfmt | unwrap cache_creation_tokens [$__interval]))', "cacheCreation")], "short", 12, 8, 12, 7, stack=True),
    # ----- iteration cost/latency + throughput -----
    lts("Iteration duration (p95 / p50)", [
        (f'quantile_over_time(0.95, {REQ} | logfmt | unwrap duration_ms [$__interval])', "p95"),
        (f'quantile_over_time(0.50, {REQ} | logfmt | unwrap duration_ms [$__interval])', "p50")], "ms", 12, 8, 0, 15),
    lts("Requests & tool calls (rate)", [
        (f'sum by (model)(count_over_time({REQ} [$__interval]))', "req {{model}}"),
        (f'sum(count_over_time({TOOL} [$__interval]))', "tool calls")], "short", 12, 8, 12, 15, stack=True),
    # ----- breakdowns -----
    lbar("Tool calls by tool (range)", f'sum by (tool)(count_over_time({TOOL} | logfmt [$__range]))', "short", 8, 8, 0, 23, legend="{{tool}}"),
    lbar("Cost by task (range)", f'sum by (task)(sum_over_time({REQ} | logfmt | unwrap cost_usd [$__range]))', "currencyUSD", 8, 8, 8, 23, legend="{{task}}"),
    lbar("Gate outcomes (range)", f'sum by (result)(count_over_time({GATE} | logfmt [$__range]))', "short", 8, 8, 16, 23, legend="{{result}}"),
    # ----- raw event stream -----
    logs("Recent Ralph events (run/iter/api_request/tool_use/gate/run_end)", '{job="ralph", task=~"$task"}', 24, 11, 0, 31),
]
write(dashboard("Ralph Loops (Claude Code)", "ralph-loops", ralph, ["ai", "claude-code", "ralph"],
                templating=[var_query("task", 'label_values({job="ralph"}, task)', ds=LOKI)]), "ai-agents")

# ---------------- SpecStride runs & traces ----------------
# Spans come from specstride's lib/ralph_otel_spans.py (OTLP -> collector -> Tempo),
# resource service.name="specstride": one trace per run, nested
# run > phase > attempt > iter > tool, plus verification / critic scopes. Scope spans
# land when the scope CLOSES; tool/agent point spans land live (per iteration flush)
# and show "root span not yet received" until their run finishes. The OTLP log copy
# (Loki service_name="ralph") carries trace_id/span_id structured metadata, so every
# log line links to its span (Loki derived field) and every span to its logs.
_id = itertools.count(1)
SS = '{service_name="ralph", task=~"$task"}'
SSR = 'resource.service.name="specstride" && resource.task=~"$task"'
SNOTE = (
    "**SpecStride** runs as traces: one trace per run (`run > phase > attempt > iter > tool`, "
    "plus `verification` and `critic` scopes). Scope spans appear when the scope **closes**; "
    "tool calls appear live, so an in-flight run shows *root span not yet received* until it "
    "ends. Click a trace ID to open the waterfall; each span links to its log lines in Loki."
)
spec = [
    text("About this dashboard", SNOTE, 24, 3, 0, 0),
    lstat("Runs started", f'sum(count_over_time({SS} | event="run_start" [$__range]))', "short", 4, 4, 0, 3),
    lstat("Phases approved", f'sum(count_over_time({SS} | event="verdict" | result="APPROVED" [$__range]))', "short", 4, 4, 4, 3),
    lstat("Rejections", f'sum(count_over_time({SS} | event="reject" [$__range]))', "short", 4, 4, 8, 3,
          thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 1}, {"color": "red", "value": 3}]),
    lstat("Iterations", f'sum(count_over_time({SS} | event="iter_start" [$__range]))', "short", 4, 4, 12, 3),
    lstat("Tool calls", f'sum(count_over_time({SS} | event=~"agent_tool|tool_use" [$__range]))', "short", 4, 4, 16, 3),
    stat("Agent cost (range)", 'sum(increase(ralph_cost_usd_total[$__range]))', "currencyUSD", 4, 4, 20, 3),
    tql("Runs (traces) — click a trace ID for the waterfall", "{" + SSR + "}", 24, 10, 0, 7),
    tql("Phases, attempts, verification & critic gates",
        "{" + SSR + ' && span.specstride.scope=~"phase|attempt|verification|critic"}', 24, 10, 0, 17, table_type="spans", limit=50),
    tql("Failed / rejected spans", "{" + SSR + " && status=error}", 12, 9, 0, 27, table_type="spans", limit=50),
    lts("Tool calls by tool", [(f'sum by (tool)(count_over_time({SS} | event=~"agent_tool|tool_use" [$__interval]))', "{{tool}}")],
        "short", 12, 9, 12, 27, stack=True),
    logs("SpecStride events (click trace_id in log details to open the span)",
         SS + ' | event!="telemetry_delivery"', 24, 11, 0, 36),
]
write(dashboard("SpecStride Runs & Traces", "specstride-traces", spec, ["ai", "specstride", "traces", "ralph"], refresh="30s",
                templating=[dict(var_query("task", 'label_values({service_name="ralph"}, task)', ds=LOKI), allValue=".*")]), "ai-agents")

# ---------------- Agent Mix (12.1 frontier-fading tree) ----------------
# The fading dashboard. ONE event stream (job="agentops", from agent-pack `agentops emit`) feeds
# every panel here; the SAME events also drive the kanban board (two sinks, one stream — they can
# never disagree). Loki stream labels (low-cardinality): job="agentops", event, task. Everything
# else is logfmt in the line: model, agent, verdict, rung, attempts, tokens_in, tokens_out,
# wall_ms, dial_state, degraded, reason, contract_id, card, adhoc, task_class.
#   Events: dispatch (task handed to a leaf), verdict (pass|fail|escalated), escalation (kicked up
#   the ladder), adhoc (bebop ask — a question, no card). LOCAL model = qwen* ; FRONTIER = the rest
#   (claude-*, gpt-*). GPU-degraded-by-reason is the ONE Prometheus panel: metric
#   agentops_gpu_degraded{reason=...} from the S3/H1 watchdog — reason="cpu-fallback" (H1) shows as
#   its own series so a silent CPU-fallback is visually distinct from a device-health degrade (S3).
_id = itertools.count(1)
AOVERD = '{job="agentops", event="verdict", task=~"$task"}'
AODISP = '{job="agentops", event="dispatch", task=~"$task"}'
AOESC  = '{job="agentops", event="escalation", task=~"$task"}'
LOCAL_RE = 'qwen.*'                       # local worker; everything else is frontier
MNOTE = (
    "**Frontier-fading agent tree (12.1).** opus plans/verifies, the local qwen worker executes, and "
    "trust is earned per task-class. Every panel is the persistent Loki event stream "
    "(`job=\"agentops\"`, one event per dispatch/verdict/escalation) over the dashboard range — the "
    "**same** events that drive the kanban board. **Local** = `qwen*`; **Frontier** = `claude-*` / "
    "`gpt-*`. The goal of fading is the two numbers up top moving in opposite directions: local task "
    "share **up**, frontier tokens (cost proxy) **down**, without local-first pass-rate dropping below "
    "the promotion bar (0.85). GPU-degraded is split **by reason** so a silent CPU-fallback (H1, "
    "`reason=cpu-fallback`) reads distinctly from a device-health degrade (S3)."
)
mix = [
    text("About this dashboard", MNOTE, 24, 4, 0, 0),
    # ----- headline stats over the range -----
    lstat("Tasks completed", f'sum(count_over_time({AOVERD} [$__range]))', "short", 6, 4, 0, 4),
    lstat("Local task share",
          f'sum(count_over_time({AOVERD} | logfmt | model=~`{LOCAL_RE}` [$__range])) '
          f'/ sum(count_over_time({AOVERD} | logfmt [$__range]))',
          "percentunit", 6, 4, 6, 4,
          thresholds=[{"color": "red", "value": None}, {"color": "orange", "value": 0.5}, {"color": "green", "value": 0.8}]),
    lstat("Escalation rate",
          f'sum(count_over_time({AOESC} [$__range])) '
          f'/ sum(count_over_time({AODISP} [$__range]))',
          "percentunit", 6, 4, 12, 4,
          thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 0.2}, {"color": "red", "value": 0.4}]),
    stat("GPU degraded now", 'max(agentops_gpu_degraded) or vector(0)', "short", 6, 4, 18, 4,
         thresholds=[{"color": "green", "value": None}, {"color": "red", "value": 1}]),
    # ----- frontier share: tokens + task counts, local vs frontier -----
    lts("Tokens: local vs frontier (cost proxy)", [
        (f'sum(sum_over_time({AOVERD} | logfmt | model=~`{LOCAL_RE}` | unwrap tokens_out [$__interval]))', "local (qwen)"),
        (f'sum(sum_over_time({AOVERD} | logfmt | model!~`{LOCAL_RE}` | unwrap tokens_out [$__interval]))', "frontier (claude/gpt)")],
        "short", 12, 8, 0, 8, stack=True),
    lts("Task mix: local vs frontier (count)", [
        (f'sum(count_over_time({AOVERD} | logfmt | model=~`{LOCAL_RE}` [$__interval]))', "local (qwen)"),
        (f'sum(count_over_time({AOVERD} | logfmt | model!~`{LOCAL_RE}` [$__interval]))', "frontier (claude/gpt)")],
        "short", 12, 8, 12, 8, stack=True),
    # ----- the fading metrics, BY task-class -----
    lbar("Local-first pass rate by class (promote ≥ 0.85)",
         f'sum by (task)(count_over_time({AOVERD} | logfmt | model=~`{LOCAL_RE}` | verdict=`pass` | attempts=`1` [$__range])) '
         f'/ sum by (task)(count_over_time({AOVERD} | logfmt | model=~`{LOCAL_RE}` [$__range]))',
         "percentunit", 12, 8, 0, 16, legend="{{task}}"),
    lbar("Escalation rate by class",
         f'sum by (task)(count_over_time({AOESC} [$__range])) '
         f'/ sum by (task)(count_over_time({AODISP} [$__range]))',
         "percentunit", 12, 8, 12, 16, legend="{{task}}"),
    # ----- dial position + cost proxy breakdown -----
    lbar("Tasks by dial position (fading state)",
         f'sum by (dial_state)(count_over_time({AOVERD} | logfmt [$__range]))',
         "short", 12, 8, 0, 24, legend="{{dial_state}}"),
    lbar("Frontier tokens by model (range) — cost proxy",
         f'sum by (model)(sum_over_time({AOVERD} | logfmt | model!~`{LOCAL_RE}` | unwrap tokens_out [$__range]))',
         "short", 12, 8, 12, 24, legend="{{model}}"),
    # ----- GPU degraded windows, SPLIT BY reason (H1: cpu-fallback distinct from S3 device-health) -----
    ts("GPU degraded windows (by reason) — cpu-fallback = H1, others = S3 device-health",
       [('agentops_gpu_degraded', "{{reason}}")], "short", 24, 7, 0, 32),
    # ----- raw event stream -----
    logs("Recent agent-pack events (dispatch / verdict / escalation / adhoc)",
         '{job="agentops", task=~"$task"}', 24, 11, 0, 39),
]
write(dashboard("Agent Mix — Frontier Fading (12.1)", "agent-mix", mix, ["ai", "agents", "12.1", "fading"],
                templating=[var_query("task", 'label_values({job="agentops"}, task)', ds=LOKI)]), "ai-agents")

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
