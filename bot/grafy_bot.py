#!/usr/bin/env python3
"""Grafy — a slash-command Telegram bot for the observability stack.

Commands (only honored from allowlisted chat ids):
  /graph <dashboard> [range]   rendered dashboard PNG + key values
  /values <dashboard> [range]  key values only (no image)
  /alerts                      currently firing alerts
  /list                        available dashboards
  /help                        usage

Env: TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_CHATS (comma sep), GRAFANA_URL, GRAFANA_USER,
GRAFANA_PASSWORD, PROM_URL, RENDER_WIDTH, RENDER_HEIGHT.
"""
import os, re, time, traceback
import requests

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ALLOWED = {c.strip() for c in os.environ.get("TELEGRAM_ALLOWED_CHATS", "").split(",") if c.strip()}
GRAFANA = os.environ.get("GRAFANA_URL", "http://grafana:3000").rstrip("/")
GUSER = os.environ.get("GRAFANA_USER", "admin")
GPASS = os.environ.get("GRAFANA_PASSWORD", "admin")
PROM = os.environ.get("PROM_URL", "http://prometheus:9090").rstrip("/")
RW = int(os.environ.get("RENDER_WIDTH", "1600"))
RH = int(os.environ.get("RENDER_HEIGHT", "1300"))
API = f"https://api.telegram.org/bot{TOKEN}"

# dashboard aliases -> (uid, slug, title)
DASH = {
    "host": ("host", "host", "Host / System"),
    "system": ("host", "host", "Host / System"),
    "proxmox": ("host", "host", "Host / System"),
    "accelerators": ("accelerators", "accelerators", "Accelerators (iGPU+NPU)"),
    "acc": ("accelerators", "accelerators", "Accelerators (iGPU+NPU)"),
    "gpu": ("accelerators", "accelerators", "Accelerators (iGPU+NPU)"),
    "npu": ("accelerators", "accelerators", "Accelerators (iGPU+NPU)"),
    "network": ("network", "network", "Network & Connectivity"),
    "net": ("network", "network", "Network & Connectivity"),
    "containers": ("containers", "containers", "Containers"),
    "docker": ("containers", "containers", "Containers"),
    "agents": ("agents", "agents", "OpenClaw Agents"),
    "agent": ("agents", "agents", "OpenClaw Agents"),
    "openclaw": ("agents", "agents", "OpenClaw Agents"),
    "claude-code": ("claude-code", "claude-code", "Claude Code"),
    "claude": ("claude-code", "claude-code", "Claude Code"),
    "cc": ("claude-code", "claude-code", "Claude Code"),
    "llm-cost": ("llm-cost", "llm-cost", "LLM Cost & Consumption"),
    "cost": ("llm-cost", "llm-cost", "LLM Cost & Consumption"),
    "llm": ("llm-cost", "llm-cost", "LLM Cost & Consumption"),
    "spend": ("llm-cost", "llm-cost", "LLM Cost & Consumption"),
    "rag": ("rag", "rag", "RAG / Memory"),
    "memory": ("rag", "rag", "RAG / Memory"),
    "qmd": ("rag", "rag", "RAG / Memory"),
}

# per-uid value summaries: (label, promql, formatter)
def pct(v): return f"{float(v):.1f}%"
def num(v): return f"{float(v):.0f}"
def num1(v): return f"{float(v):.1f}"
def usd(v): return f"${float(v):.4f}"
def sec(v): return f"{float(v):.1f}s"
def ms(v): return f"{float(v)*1000:.0f} ms"
def mhz(v): return f"{float(v):.0f} MHz"
def watt(v): return f"{float(v):.1f} W"
def days(v): return f"{float(v):.2f} d"
def gb(v): return f"{float(v)/1e9:.2f} GB"
def mb(v): return f"{float(v)/1e6:.0f} MB"

SUMMARY = {
    "host": [
        ("CPU busy", '100-(avg(rate(node_cpu_seconds_total{mode="idle"}[5m]))*100)', pct),
        ("Mem used", '(1-node_memory_MemAvailable_bytes/node_memory_MemTotal_bytes)*100', pct),
        ("Load 1m", 'node_load1', num1),
        ("Disk max", 'max((1-node_filesystem_avail_bytes{fstype!~"tmpfs|overlay"}/node_filesystem_size_bytes{fstype!~"tmpfs|overlay"})*100)', pct),
        ("Uptime", '(node_time_seconds-node_boot_time_seconds)/86400', days),
        ("VMs/CTs up", 'sum(pve_up{id=~"qemu/.*|lxc/.*"})', num),
    ],
    "accelerators": [
        ("NPU busy", 'clamp_max(rate(intel_npu_busy_time_us[5m])/1e6*100,100)', pct),
        ("NPU freq", 'intel_npu_frequency_mhz{type="current"}', mhz),
        ("NPU mem", 'intel_npu_memory_bytes', mb),
        ("iGPU busy", 'max(intel_gpu_engine_busy_ratio)*100', pct),
        ("iGPU power", 'intel_gpu_power_watts{domain="Package"}', watt),
    ],
    "network": [
        ("Targets up", 'sum(probe_success)', num),
        ("Targets down", 'sum(probe_success==0) or vector(0)', num),
        ("Internet RTT", 'probe_duration_seconds{instance="1.1.1.1"}', ms),
        ("Site latency", 'probe_duration_seconds{instance=~"https://.*"}', ms),
    ],
    "agents": [
        ("Spend 24h", 'sum(increase(litellm_spend_metric_total[24h]))', usd),
        ("Tokens 24h", 'sum(increase(litellm_total_tokens_metric_total[24h]))', num),
        ("Calls 1h", 'sum(increase(openclaw_model_call_total[1h]))', num),
        ("p95 latency", 'histogram_quantile(0.95,sum by(le)(rate(openclaw_model_call_duration_seconds_bucket[10m])))', sec),
        ("Cache hit", 'sum(rate(litellm_input_cached_tokens_metric_total[30m]))/clamp_min(sum(rate(litellm_input_tokens_metric_total[30m])),1)*100', pct),
        ("Agents", 'openclaw_agents_total', num),
    ],
    "claude-code": [
        ("CC tokens 24h", 'sum(increase(claude_code_token_usage_tokens_total[24h]))', num),
        ("CC cost 24h", 'sum(increase(claude_code_cost_usage_USD_total[24h]))', usd),
        ("Sessions 24h", 'sum(increase(claude_code_session_count_total[24h]))', num),
        ("Models", 'count(count by(model)(claude_code_token_usage_tokens_total))', num),
        ("Cache hit", 'sum(rate(claude_code_token_usage_tokens_total{type="cacheRead"}[30m]))/clamp_min(sum(rate(claude_code_token_usage_tokens_total{type=~"input|cacheRead|cacheCreation"}[30m])),1)*100', pct),
    ],
    "llm-cost": [
        ("Total spend 24h", '(sum(increase(claude_code_cost_usage_USD_total[24h])) or vector(0))+(sum(increase(litellm_spend_metric_total[24h])) or vector(0))', usd),
        ("Claude Code 24h", 'sum(increase(claude_code_cost_usage_USD_total[24h])) or vector(0)', usd),
        ("OpenClaw 24h", 'sum(increase(litellm_spend_metric_total[24h])) or vector(0)', usd),
        ("CC tokens 24h", 'sum(increase(claude_code_token_usage_tokens_total[24h]))', num),
        ("OC tokens 24h", 'sum(increase(litellm_total_tokens_metric_total[24h]))', num),
    ],
    "rag": [
        ("RAG docs", 'sum(qmd_documents_total)', num),
        ("RAG vectors", 'sum(qmd_vectors_total)', num),
        ("Indexes", 'count(qmd_documents_total)', num),
    ],
    "containers": [
        ("Containers", 'count(container_last_seen{name!=""})', num),
        ("Total mem", 'sum(container_memory_working_set_bytes{name!=""})', gb),
        ("Total CPU/s", 'sum(rate(container_cpu_usage_seconds_total{name!=""}[5m]))', num1),
    ],
}


def promq(expr):
    try:
        r = requests.get(f"{PROM}/api/v1/query", params={"query": expr}, timeout=10)
        res = r.json()["data"]["result"]
        return res[0]["value"][1] if res else None
    except Exception:
        return None


def values_text(uid):
    rows = SUMMARY.get(uid, [])
    out = []
    for label, expr, fmt in rows:
        v = promq(expr)
        out.append(f"  {label:<13} {fmt(v) if v is not None else 'n/a'}")
    return "\n".join(out)


def render_png(uid, slug, rng):
    url = f"{GRAFANA}/render/d/{uid}/{slug}"
    params = {"kiosk": "", "width": RW, "height": RH, "from": f"now-{rng}", "to": "now",
              "theme": "dark", "tz": "Asia/Dubai"}
    r = requests.get(url, params=params, auth=(GUSER, GPASS), timeout=60)
    if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
        return r.content
    return None


_ALLOWED_TAGS = ("b", "i", "code", "pre", "u", "s")


def sanitize_html(text):
    """Escape stray < > & (so Telegram HTML never fails) while keeping <b>/<i>/<code> tags. Idempotent."""
    text = re.sub(r"&(?!(?:amp|lt|gt|quot|#\d+|#x[0-9a-fA-F]+);)", "&amp;", text)
    text = text.replace("<", "&lt;").replace(">", "&gt;")
    for t in _ALLOWED_TAGS:
        text = text.replace(f"&lt;{t}&gt;", f"<{t}>").replace(f"&lt;/{t}&gt;", f"</{t}>")
    return text


def tg(method, **kw):
    try:
        files = kw.pop("files", None)
        return requests.post(f"{API}/{method}", data=kw, files=files, timeout=30).json()
    except Exception:
        traceback.print_exc()
        return {}


def send(chat, text):
    tg("sendMessage", chat_id=chat, text=sanitize_html(text), parse_mode="HTML")


def send_photo(chat, png, caption):
    # parse_mode is REQUIRED here or the caption shows literal <b> tags
    tg("sendPhoto", chat_id=chat, caption=sanitize_html(caption), parse_mode="HTML",
       files={"photo": ("graph.png", png, "image/png")})


HELP = (
    "<b>Grafy</b> — observability bot\n\n"
    "/graph &lt;dashboard&gt; [range] — image + values\n"
    "/values &lt;dashboard&gt; [range] — values only\n"
    "/alerts — firing alerts\n"
    "/list — dashboards\n\n"
    "dashboards: host, accelerators, network, containers, agents, claude-code, llm-cost, rag\n"
    "range: 1h (default 3h), 6h, 24h, 7d\n"
    "e.g. <code>/graph agents 24h</code>"
)


def resolve(name):
    return DASH.get((name or "").lower().lstrip("#"))


def handle(chat, text):
    parts = text.strip().split()
    cmd = parts[0].lower().split("@")[0]
    args = parts[1:]
    if cmd in ("/start", "/help"):
        send(chat, HELP)
    elif cmd == "/list":
        names = sorted({v[0] for v in DASH.values()})
        send(chat, "Dashboards:\n" + "\n".join(f"  • {n}" for n in names))
    elif cmd == "/alerts":
        res = []
        try:
            r = requests.get(f"{PROM}/api/v1/query", params={"query": 'ALERTS{alertstate="firing"}'}, timeout=10)
            for s in r.json()["data"]["result"]:
                m = s["metric"]
                res.append(f"🔴 <b>{m.get('alertname','?')}</b>" +
                           (f" · {m.get('instance')}" if m.get('instance') else "") +
                           (f" · {m.get('severity')}" if m.get('severity') else ""))
        except Exception:
            send(chat, "⚠️ couldn't query alerts"); return
        send(chat, ("Firing alerts:\n" + "\n".join(res)) if res else "✅ All clear — no firing alerts.")
    elif cmd in ("/graph", "/values"):
        if not args:
            send(chat, "Usage: <code>/graph host</code> (see /list)"); return
        d = resolve(args[0])
        if not d:
            send(chat, f"Unknown dashboard '{args[0]}'. Try /list."); return
        uid, slug, title = d
        rng = args[1] if len(args) > 1 else "3h"
        vals = values_text(uid)
        caption = f"<b>{title}</b> · last {rng}\n{vals}"
        if cmd == "/values":
            send(chat, caption); return
        send(chat, f"🖼 rendering <b>{title}</b>…")
        png = render_png(uid, slug, rng)
        if png:
            send_photo(chat, png, caption[:1024])
        else:
            send(chat, "⚠️ render failed; here are the values:\n" + caption)
    else:
        send(chat, "Unknown command. /help")


def main():
    print(f"grafy-bot up; allowed chats: {ALLOWED or '(none!)'}", flush=True)
    offset = None
    # drain old updates so we don't replay stale commands on restart
    try:
        r = requests.get(f"{API}/getUpdates", params={"timeout": 0, "offset": -1}, timeout=15).json()
        if r.get("result"):
            offset = r["result"][-1]["update_id"] + 1
    except Exception:
        pass
    while True:
        try:
            r = requests.get(f"{API}/getUpdates", params={"timeout": 50, "offset": offset}, timeout=60).json()
            for upd in r.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message") or upd.get("edited_message")
                if not msg:
                    continue
                chat = str(msg.get("chat", {}).get("id"))
                text = msg.get("text", "")
                if ALLOWED and chat not in ALLOWED:
                    continue  # silently ignore non-allowlisted chats
                if text.startswith("/"):
                    try:
                        handle(chat, text)
                    except Exception:
                        traceback.print_exc()
                        send(chat, "⚠️ error handling that command")
        except requests.exceptions.ReadTimeout:
            continue
        except Exception:
            traceback.print_exc()
            time.sleep(3)


if __name__ == "__main__":
    main()
