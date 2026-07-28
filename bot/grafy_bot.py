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
# Browser-reachable Grafana base (for clickable links in messages); internal render URL is not.
GRAFANA_PUBLIC = os.environ.get("GRAFANA_PUBLIC_URL", "").rstrip("/")
LOKI = os.environ.get("LOKI_URL", "http://loki:3100").rstrip("/")
RW = int(os.environ.get("RENDER_WIDTH", "1600"))
RH = int(os.environ.get("RENDER_HEIGHT", "1300"))
API = f"https://api.telegram.org/bot{TOKEN}"

# dashboard aliases -> (uid, slug, title)
DASH = {
    "host": ("host", "host", "Host / System"),
    "system": ("host", "host", "Host / System"),
    "hypervisor": ("host", "host", "Host / System"),
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
    "vectors": ("qmd-vector-space", "qmd-vector-space", "QMD Vector Space"),
    "vector": ("qmd-vector-space", "qmd-vector-space", "QMD Vector Space"),
    "vector-space": ("qmd-vector-space", "qmd-vector-space", "QMD Vector Space"),
    "vectorspace": ("qmd-vector-space", "qmd-vector-space", "QMD Vector Space"),
    "space": ("qmd-vector-space", "qmd-vector-space", "QMD Vector Space"),
    "embeddings": ("qmd-vector-space", "qmd-vector-space", "QMD Vector Space"),
    "pca": ("qmd-vector-space", "qmd-vector-space", "QMD Vector Space"),
    # Composite: Claude Code vs pi
    "composite": ("agents-composite", "agents-composite", "Agents — Claude Code vs pi"),
    "agents-composite": ("agents-composite", "agents-composite", "Agents — Claude Code vs pi"),
    "both": ("agents-composite", "agents-composite", "Agents — Claude Code vs pi"),
    "claude-vs-pi": ("agents-composite", "agents-composite", "Agents — Claude Code vs pi"),
    # Ralph autonomous loops (Loki-backed)
    "ralph": ("ralph-loops", "ralph-loops", "Ralph Loops (Claude Code)"),
    "ralph-loops": ("ralph-loops", "ralph-loops", "Ralph Loops (Claude Code)"),
    "loops": ("ralph-loops", "ralph-loops", "Ralph Loops (Claude Code)"),
    "loop": ("ralph-loops", "ralph-loops", "Ralph Loops (Claude Code)"),
    # Local inference (llama.cpp on the RTX 3090)
    "inference": ("inference-llama", "inference-llama", "LLM Inference — llama.cpp + MTP (RTX 3090)"),
    "llama": ("inference-llama", "inference-llama", "LLM Inference — llama.cpp + MTP (RTX 3090)"),
    "mtp": ("inference-llama", "inference-llama", "LLM Inference — llama.cpp + MTP (RTX 3090)"),
    # Agent mix — frontier fading (12.1)
    "agent-mix": ("agent-mix", "agent-mix", "Agent Mix — Frontier Fading (12.1)"),
    "mix": ("agent-mix", "agent-mix", "Agent Mix — Frontier Fading (12.1)"),
    "frontier-fading": ("agent-mix", "agent-mix", "Agent Mix — Frontier Fading (12.1)"),
}

# Dashboards whose full render is unusable headless (e.g. a WebGL scatter3d panel that the
# image-renderer's Chromium can't draw). Render a single SVG panel solo instead, and append a
# note. uid -> (panel_id, note). The note points at the interactive view for the dropped panel.
SOLO = {
    "qmd-vector-space": (1, "🌀 3D view is interactive (WebGL) — open the dashboard in Grafana and drag to rotate."),
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

# per-uid value summaries: (label, expr, fmt, "loki"|"prom")
# source field tells values_text which query helper to use
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
    "qmd-vector-space": [
        ("Docs", 'sum(qmd_documents_total)', num),
        ("Vectors", 'sum(qmd_vectors_total)', num),
        ("Collections", 'count(qmd_documents_total)', num),
    ],
    "containers": [
        ("Containers", 'count(container_last_seen{name!=""})', num, "prom"),
        ("Total mem", 'sum(container_memory_working_set_bytes{name!=""})', gb, "prom"),
        ("Total CPU/s", 'sum(rate(container_cpu_usage_seconds_total{name!=""}[5m]))', num1, "prom"),
    ],
    "agents-composite": [
        ("CC cost 24h", '{service_name=~"$service"} | event_name=`api_request` | unwrap cost_usd', usd, "loki"),
        ("CC tokens 24h", '{service_name=~"$service"} | event_name=`api_request` | unwrap output_tokens', num, "loki"),
        ("CC cache-read", '{service_name=~"$service"} | event_name=`api_request` | unwrap cache_read_tokens', num, "loki"),
        ("CC requests", '{service_name=~"$service"} | event_name=`api_request`', num, "loki"),
    ],
    "ralph-loops": [
        ("Runs 24h", 'sum(count_over_time({job="ralph", event="run_start"} [24h]))', num, "loki"),
        ("Iterations 24h", 'sum(count_over_time({job="ralph", event="iter_start"} [24h]))', num, "loki"),
        ("Cost 24h", 'sum(sum_over_time({job="ralph", event="api_request"} | logfmt | unwrap cost_usd [24h]))', usd, "loki"),
        ("Out tokens 24h", 'sum(sum_over_time({job="ralph", event="api_request"} | logfmt | unwrap output_tokens [24h]))', num, "loki"),
        ("Tool calls 24h", 'sum(count_over_time({job="ralph", event="tool_use"} [24h]))', num, "loki"),
        ("Errors 24h", 'sum(count_over_time({job="ralph", event="api_request"} | logfmt | is_error="true" [24h]))', num, "loki"),
    ],
}


# ---------------------------------------------------------------------------
# Dynamic dashboard discovery — so any NEW dashboard created in Grafana is
# retrievable without editing the curated DASH map above. Grafana's search API
# is the source of truth; results are cached briefly and folded into resolve().
# ---------------------------------------------------------------------------
DISCOVERY_TTL = int(os.environ.get("DISCOVERY_TTL", "120"))  # seconds
_disco = {"at": 0.0, "by_uid": {}, "by_key": {}}  # uid->(uid,slug,title); alias->uid


def _slug_from_url(url, uid):
    """Grafana search returns url like '/d/<uid>/<slug>'. Pull the slug (fallback uid)."""
    try:
        tail = url.split(f"/d/{uid}/", 1)[1]
        return tail.split("/", 1)[0].split("?", 1)[0] or uid
    except Exception:
        return uid


def grafana_search():
    """Return [(uid, slug, title)] for every dashboard Grafana knows about, or [] on error."""
    try:
        r = requests.get(f"{GRAFANA}/api/search", params={"type": "dash-db", "limit": 500},
                         auth=(GUSER, GPASS), timeout=10)
        if r.status_code != 200:
            return []
        out = []
        for d in r.json():
            uid = d.get("uid")
            title = d.get("title")
            if not uid or not title:
                continue
            out.append((uid, _slug_from_url(d.get("url", ""), uid), title))
        return out
    except Exception:
        return []


def _title_keys(title):
    """Derive lowercase lookup aliases from a dashboard title (whole + significant words)."""
    t = title.lower()
    keys = {t, re.sub(r"[^a-z0-9]+", "-", t).strip("-")}
    for w in re.split(r"[^a-z0-9]+", t):
        if len(w) >= 3 and w not in ("the", "and", "for", "vs"):
            keys.add(w)
    return {k for k in keys if k}


def discover(force=False):
    """Refresh the discovery cache if stale. Returns {uid: (uid, slug, title)}."""
    now = time.time()
    if not force and _disco["by_uid"] and (now - _disco["at"]) < DISCOVERY_TTL:
        return _disco["by_uid"]
    found = grafana_search()
    if not found and _disco["by_uid"]:
        return _disco["by_uid"]  # keep the last good snapshot on a transient failure
    by_uid, by_key = {}, {}
    for uid, slug, title in found:
        by_uid[uid] = (uid, slug, title)
        for k in _title_keys(title) | {uid}:
            by_key.setdefault(k, uid)  # curated DASH still wins in resolve(); first title wins here
    _disco.update(at=now, by_uid=by_uid, by_key=by_key)
    return by_uid


def promq(expr):
    try:
        r = requests.get(f"{PROM}/api/v1/query", params={"query": expr}, timeout=10)
        res = r.json()["data"]["result"]
        return res[0]["value"][1] if res else None
    except Exception:
        return None


def lokiq(expr):
    """Query Loki via /loki/api/v1/query. Returns the scalar result string or None."""
    try:
        r = requests.get(f"{LOKI}/loki/api/v1/query", params={"query": expr}, timeout=10)
        res = r.json()["data"]["result"]
        if res:
            # Loki returns {metric:{}, value:[ts, scalar]}
            return res[0]["value"][1]
        return None
    except Exception:
        return None


def values_text(uid):
    rows = SUMMARY.get(uid, [])
    out = []
    for row in rows:
        label, expr, fmt = row[0], row[1], row[2]
        source = row[3] if len(row) > 3 else "prom"
        if source == "loki":
            v = lokiq(expr)
        else:
            v = promq(expr)
        out.append(f"  {label:<13} {fmt(v) if v is not None else 'n/a'}")
    return "\n".join(out)


def render_png(uid, slug, rng, panel_id=None):
    params = {"width": RW, "height": RH, "from": f"now-{rng}", "to": "now",
              "theme": "dark", "tz": "Asia/Dubai"}
    if panel_id is not None:
        # single-panel render: d-solo + panelId, narrower aspect for one chart
        url = f"{GRAFANA}/render/d-solo/{uid}/{slug}"
        params.update({"panelId": panel_id, "width": 1100, "height": 850})
    else:
        url = f"{GRAFANA}/render/d/{uid}/{slug}"
        params["kiosk"] = ""
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
    "dashboards: host, accelerators, network, containers, agents, claude-code, llm-cost, rag, vectors, ralph, inference\n"
    "any dashboard in Grafana works too — use its uid (see /list)\n"
    "range: 1h (default 3h), 6h, 24h, 7d\n"
    "e.g. <code>/graph ralph 24h</code>"
)


def resolve(name):
    """Resolve a user token to (uid, slug, title).

    Curated DASH aliases win (hand-tuned titles/summaries); anything else falls back
    to live Grafana discovery so newly-created dashboards resolve with no code change.
    """
    key = (name or "").lower().lstrip("#")
    if key in DASH:
        return DASH[key]
    by_uid = discover()
    if key in by_uid:                      # exact uid match
        return by_uid[key]
    uid = _disco["by_key"].get(key)        # title / word alias match
    if uid and uid in by_uid:
        return by_uid[uid]
    return None


def handle(chat, text):
    parts = text.strip().split()
    cmd = parts[0].lower().split("@")[0]
    args = parts[1:]
    if cmd in ("/start", "/help"):
        send(chat, HELP)
    elif cmd == "/list":
        curated = {v[0]: v[2] for v in DASH.values()}   # uid -> title
        live = discover()                                 # uid -> (uid, slug, title)
        merged = {uid: curated.get(uid, live[uid][2]) for uid in set(curated) | set(live)}
        for uid, title in curated.items():
            merged.setdefault(uid, title)
        lines = [f"  • {uid}" + (f" — {merged[uid]}" if merged.get(uid) else "")
                 for uid in sorted(merged)]
        note = "" if live else "\n(live discovery unavailable — showing curated set)"
        send(chat, "Dashboards:\n" + "\n".join(lines) + note)
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
        solo = SOLO.get(uid)  # (panel_id, note) for dashboards we render one panel of
        if solo:
            note = solo[1]
            if GRAFANA_PUBLIC:
                note += f"\n{GRAFANA_PUBLIC}/d/{uid}/{slug}"
            caption += f"\n\n{note}"
        if cmd == "/values":
            send(chat, caption); return
        send(chat, f"🖼 rendering <b>{title}</b>…")
        png = render_png(uid, slug, rng, panel_id=solo[0] if solo else None)
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
