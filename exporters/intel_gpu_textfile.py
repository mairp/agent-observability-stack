#!/usr/bin/env python3
"""Intel iGPU (i915/xe) -> Prometheus textfile collector.
Samples `intel_gpu_top -J` briefly, parses the last full sample, writes a .prom file.
Requires intel-gpu-tools. Safe no-op if the binary or device is absent."""
import json, os, re, shutil, subprocess, sys, tempfile

OUT = os.path.join(os.environ.get("TEXTFILE_DIR", "/var/lib/node_exporter/textfile_collector"), "intel_gpu.prom")


def sample():
    if not shutil.which("intel_gpu_top"):
        return None
    try:
        # ~2 samples at 700ms; first is a startup artifact, use the last full one.
        p = subprocess.run(["timeout", "2", "intel_gpu_top", "-J", "-s", "700"],
                           capture_output=True, text=True)
    except Exception:
        return None
    raw = p.stdout.strip()
    if not raw:
        return None
    # intel_gpu_top emits `[ {..}, {..}, ` (often unterminated). Normalize to a JSON array.
    raw = raw.lstrip("[").rstrip().rstrip(",")
    objs = re.split(r"\}\s*,\s*\{", raw)
    if not objs:
        return None
    last = objs[-1]
    if not last.startswith("{"):
        last = "{" + last
    if not last.endswith("}"):
        last = last + "}"
    try:
        return json.loads(last)
    except Exception:
        # fall back to the first complete object
        try:
            first = objs[0]
            if not first.endswith("}"):
                first += "}"
            return json.loads(first)
        except Exception:
            return None


def esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def main():
    d = sample()
    lines = ["# HELP intel_gpu_present Whether intel_gpu_top produced a sample.",
             "# TYPE intel_gpu_present gauge"]
    if not d:
        lines.append("intel_gpu_present 0")
    else:
        lines.append("intel_gpu_present 1")
        freq = d.get("frequency", {})
        lines += ["# TYPE intel_gpu_frequency_mhz gauge",
                  f'intel_gpu_frequency_mhz{{type="requested"}} {freq.get("requested",0)}',
                  f'intel_gpu_frequency_mhz{{type="actual"}} {freq.get("actual",0)}']
        pw = d.get("power", {})
        lines.append("# TYPE intel_gpu_power_watts gauge")
        for dom in ("GPU", "Package"):
            if dom in pw:
                lines.append(f'intel_gpu_power_watts{{domain="{dom}"}} {pw[dom]}')
        if "rc6" in d:
            lines += ["# TYPE intel_gpu_rc6_ratio gauge",
                      f'intel_gpu_rc6_ratio {float(d["rc6"].get("value",0))/100.0}']
        lines.append("# TYPE intel_gpu_engine_busy_ratio gauge")
        for name, e in (d.get("engines", {}) or {}).items():
            lines.append(f'intel_gpu_engine_busy_ratio{{engine="{esc(name)}"}} {float(e.get("busy",0))/100.0}')
        # iGPU memory: integrated GPU uses shared system RAM; sum per-client resident/total.
        clients = d.get("clients", {}) or {}
        def _sum(field):
            t = 0
            for c in clients.values():
                v = ((c.get("memory") or {}).get("system") or {}).get(field)
                try: t += int(v)
                except (TypeError, ValueError): pass
            return t
        lines += ["# HELP intel_gpu_memory_bytes iGPU system memory in use (shared RAM).",
                  "# TYPE intel_gpu_memory_bytes gauge",
                  f'intel_gpu_memory_bytes{{type="resident"}} {_sum("resident")}',
                  f'intel_gpu_memory_bytes{{type="total"}} {_sum("total")}',
                  "# HELP intel_gpu_clients Number of active iGPU clients.",
                  "# TYPE intel_gpu_clients gauge",
                  f'intel_gpu_clients {len(clients)}']
    tmp = tempfile.NamedTemporaryFile("w", delete=False, dir=os.path.dirname(OUT))
    tmp.write("\n".join(lines) + "\n")
    tmp.close()
    os.replace(tmp.name, OUT)
    os.chmod(OUT, 0o644)


if __name__ == "__main__":
    main()
