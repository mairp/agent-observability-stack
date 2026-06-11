#!/usr/bin/env python3
"""Record Grafana dashboard walkthroughs via an existing Chromium DevTools endpoint, encode mp4+gif.
Opens a NEW isolated tab (does not touch other tabs), kiosk-views each dashboard, auto-scrolls,
captures a screencast, and writes media/<clip>.mp4 + media/<clip>.gif.

Usage: record-dashboards.py <clip> <uid[:secs]> [uid[:secs] ...]
Env: CDP_URL (default http://127.0.0.1:18800), GRAFANA (default http://127.0.0.1:3000), FPS (8)
"""
import asyncio, base64, json, os, shutil, subprocess, sys, urllib.request
import websockets

CDP = os.environ.get("CDP_URL", "http://127.0.0.1:18800")
GRAFANA = os.environ.get("GRAFANA", "http://127.0.0.1:3000")
FPS = int(os.environ.get("FPS", "8"))
W, H = 1600, 900
OUTDIR = os.path.join(os.path.dirname(__file__), "..", "media")


def http_json(path):
    return json.load(urllib.request.urlopen(CDP + path))


class CDP_:
    def __init__(self, ws): self.ws = ws; self._id = 0; self.frames = []; self.session = None

    async def call(self, method, params=None, session=None, collect=False, timeout=30):
        """Send a command and return its result, queueing/acking any screencast frames seen meanwhile."""
        self._id += 1; mid = self._id
        msg = {"id": mid, "method": method, "params": params or {}}
        if session: msg["sessionId"] = session
        await self.ws.send(json.dumps(msg))
        while True:
            raw = await asyncio.wait_for(self.ws.recv(), timeout)
            m = json.loads(raw)
            if m.get("method") == "Page.screencastFrame":
                p = m["params"]
                if collect: self.frames.append(base64.b64decode(p["data"]))
                await self.ws.send(json.dumps({"id": -1, "method": "Page.screencastFrameAck",
                                               "params": {"sessionId": p["sessionId"]}, "sessionId": self.session}))
            elif m.get("id") == mid:
                if "error" in m: raise RuntimeError(f"{method}: {m['error']}")
                return m.get("result", {})

    async def drain(self, seconds):
        """Receive for N seconds, collecting + acking screencast frames."""
        end = asyncio.get_event_loop().time() + seconds
        while asyncio.get_event_loop().time() < end:
            try: raw = await asyncio.wait_for(self.ws.recv(), max(0.1, end - asyncio.get_event_loop().time()))
            except asyncio.TimeoutError: break
            m = json.loads(raw)
            if m.get("method") == "Page.screencastFrame":
                p = m["params"]; self.frames.append(base64.b64decode(p["data"]))
                await self.ws.send(json.dumps({"id": -1, "method": "Page.screencastFrameAck",
                                               "params": {"sessionId": p["sessionId"]}, "sessionId": self.session}))


async def record(clip, specs):
    os.makedirs(OUTDIR, exist_ok=True)
    fd = os.path.join(OUTDIR, "frames"); shutil.rmtree(fd, ignore_errors=True); os.makedirs(fd)
    wsurl = http_json("/json/version")["webSocketDebuggerUrl"]
    async with websockets.connect(wsurl, max_size=None) as ws:
        c = CDP_(ws)
        t = await c.call("Target.createTarget", {"url": "about:blank"})
        target = t["targetId"]
        a = await c.call("Target.attachToTarget", {"targetId": target, "flatten": True})
        c.session = a["sessionId"]
        await c.call("Page.enable", session=c.session)
        await c.call("Runtime.enable", session=c.session)
        await c.call("Emulation.setDeviceMetricsOverride",
                     {"width": W, "height": H, "deviceScaleFactor": 1, "mobile": False}, session=c.session)
        STEP = 0.25  # seconds between screenshots -> smooth fixed-cadence capture
        for spec in specs:
            uid, _, secs = spec.partition(":"); secs = int(secs or 7)
            url = f"{GRAFANA}/d/{uid}/{uid}?kiosk&refresh=5s&from=now-3h&to=now"
            await c.call("Page.navigate", {"url": url}, session=c.session)
            await asyncio.sleep(4.0)  # render
            n = int(secs / STEP)
            for i in range(n):
                frac = i / max(1, n - 1)
                await c.call("Runtime.evaluate",
                             {"expression": f"window.scrollTo(0,(document.body.scrollHeight-{H})*{frac:.3f});"},
                             session=c.session)
                shot = await c.call("Page.captureScreenshot", {"format": "jpeg", "quality": 78}, session=c.session)
                c.frames.append(base64.b64decode(shot["data"]))
                await asyncio.sleep(STEP)
        await c.call("Target.closeTarget", {"targetId": target})
        frames = c.frames
    if not frames:
        print("ERROR: no frames captured"); return 1
    for i, fr in enumerate(frames):
        open(os.path.join(fd, f"f{i:05d}.jpg"), "wb").write(fr)
    print(f"  captured {len(frames)} frames")
    mp4 = os.path.join(OUTDIR, f"{clip}.mp4"); gif = os.path.join(OUTDIR, f"{clip}.gif")
    subprocess.run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", f"{fd}/f%05d.jpg",
                    "-vf", "scale=1280:-2:flags=lanczos,format=yuv420p", "-movflags", "+faststart", mp4],
                   check=True, capture_output=True)
    pal = os.path.join(fd, "pal.png")
    subprocess.run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", f"{fd}/f%05d.jpg",
                    "-vf", "fps=5,scale=960:-1:flags=lanczos,palettegen", pal], check=True, capture_output=True)
    subprocess.run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", f"{fd}/f%05d.jpg", "-i", pal,
                    "-lavfi", "fps=5,scale=960:-1:flags=lanczos[x];[x][1:v]paletteuse", gif],
                   check=True, capture_output=True)
    shutil.rmtree(fd, ignore_errors=True)
    for f in (mp4, gif): print(f"  wrote {os.path.relpath(f)} ({os.path.getsize(f)//1024} KB)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 3: print(__doc__); sys.exit(2)
    sys.exit(asyncio.run(record(sys.argv[1], sys.argv[2:])))
