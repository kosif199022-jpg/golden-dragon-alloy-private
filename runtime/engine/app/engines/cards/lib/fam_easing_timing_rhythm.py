"""Helpers of runners/fam_easing_timing_rhythm.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from pathlib import Path
from .core import fx
import html
import json
import math
import shutil
import subprocess


def _node_mod(name):
    for base in [Path(shutil.which("node") or "/usr/bin/node").resolve().parent.parent / "lib/node_modules",
                 Path("/opt/node22/lib/node_modules"), Path("/usr/lib/node_modules"), Path("/usr/local/lib/node_modules")]:
        if (base / name).exists():
            return base / name
    return Path("/opt/node22/lib/node_modules") / name


GSAP = _node_mod("gsap")


def chrome_bin():
    for c in ["google-chrome", "chromium", "chromium-browser"]:
        if shutil.which(c):
            return shutil.which(c)
    for p in sorted(Path("/opt/pw-browsers").glob("chromium-*/chrome-linux64/chrome")):
        return str(p)
    return None


def chrome(wd, name, body_html, flags=()):
    """Load a page in headless Chrome; the page's script stores JSON in <body data-r>; return it."""
    page = Path(wd) / (name + ".html")
    page.write_text(body_html, encoding="utf-8")
    done = subprocess.run([chrome_bin(), "--headless=new", "--no-sandbox", "--disable-gpu", "--allow-file-access-from-files",
                           "--virtual-time-budget=4000", *flags, "--dump-dom", page.as_uri()], capture_output=True, text=True,
                          timeout=40, stdin=subprocess.DEVNULL)
    import re
    m = re.search(r'data-r="([^"]*)"', done.stdout)
    if not m:
        raise RuntimeError("page produced no result: " + done.stderr[-300:])
    return json.loads(html.unescape(m.group(1)))


def jw(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return Path(path)


def bez(x1, y1, x2, y2):
    """Independent CSS cubic-bezier solver (bisection on x), used to cross-check other implementations."""
    def cx(t):
        return 3 * x1 * t * (1 - t) ** 2 + 3 * x2 * t * t * (1 - t) + t ** 3

    def cy(t):
        return 3 * y1 * t * (1 - t) ** 2 + 3 * y2 * t * t * (1 - t) + t ** 3

    def f(x):
        if x <= 0:
            return 0.0
        if x >= 1:
            return 1.0
        lo, hi = 0.0, 1.0
        for _ in range(60):
            mid = (lo + hi) / 2
            if cx(mid) < x:
                lo = mid
            else:
                hi = mid
        return cy((lo + hi) / 2)
    return f


def write_mp4(path, frames, fps=30):
    import numpy as np
    arr = [np.asarray(f, dtype=np.uint8) for f in frames]
    h, w = arr[0].shape[:2]
    p = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                        "-s", "%dx%d" % (w, h), "-r", str(fps), "-i", "-", "-c:v", "libx264", "-crf", "12",
                        "-pix_fmt", "yuv420p", str(path)], input=b"".join(a.tobytes() for a in arr),
                       capture_output=True, timeout=60)
    if p.returncode:
        raise RuntimeError(p.stderr.decode(errors="replace")[-300:])
    return Path(path)


def read_mp4(path, w, h):
    return fx.frames(path, size=(w, h))


def curves_png(path, curves, size=(320, 240)):
    from PIL import Image, ImageDraw
    w, h = size
    im = Image.new("RGB", size, (16, 18, 24))
    d = ImageDraw.Draw(im)
    vals = [v for c in curves.values() for v in c]
    lo, hi = min(0.0, min(vals)), max(1.0, max(vals))
    cols = [(231, 182, 90), (91, 209, 165), (120, 160, 255), (255, 107, 107), (200, 200, 200), (190, 120, 255)]
    for k, (_, c) in enumerate(curves.items()):
        n = len(c) - 1
        pts = [(10 + (w - 20) * i / n, h - 10 - (h - 20) * (v - lo) / (hi - lo)) for i, v in enumerate(c)]
        d.line(pts, fill=cols[k % len(cols)], width=2)
    im.save(path)
    return Path(path)


def canvas(w, h, bg=(10, 12, 18)):
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (w, h), bg)
    return im, ImageDraw.Draw(im)


def blob_x(frame, thr=128, ch=None):
    """Bounding box and centroid of bright pixels in a frame (H, W, 3) array."""
    import numpy as np
    a = frame if ch is None else frame[..., ch:ch + 1]
    m = a.max(axis=2) > thr
    if not m.any():
        return None
    ys, xs = np.nonzero(m)
    return {"x0": int(xs.min()), "x1": int(xs.max()), "y0": int(ys.min()), "y1": int(ys.max()),
            "cx": float(xs.mean()), "cy": float(ys.mean()), "n": int(m.sum())}


SB_NAMES = ["افتتاحية", "الفكرة", "التوضيح", "التحول", "النتيجة", "الخاتمة"]


SB_VIS = ["kinetic-typography", "dynamic-infographic", "hand-drawn-shapes"]


def make_storyboard(d):
    beats = 3 if d <= 12 else 5 if d <= 35 else min(12, math.ceil(d / 6))
    mids = SB_NAMES[1:-1]
    out = []
    for i in range(beats):
        name = SB_NAMES[0] if i == 0 else SB_NAMES[-1] if i == beats - 1 else mids[(i - 1) % len(mids)]
        start = round(d * i / beats, 3)
        end = d if i == beats - 1 else round(d * (i + 1) / beats, 3)
        out.append({"name": name, "start": start, "end": end, "visual": SB_VIS[i % 3], "fps": 30})
    return out


def speed_timings(lines, wps=2.2, gap=0.8, lead=0.5, tail=1.0):
    t, rows = lead, []
    for line in lines:
        ws = line.split()
        durs = [(1 / wps) * min(1.6, max(0.6, len(w) / 5)) for w in ws]
        line_d = max(sum(durs), 0.3 * len(ws) + 0.6)
        scale = line_d / sum(durs)
        words, s = [], t
        for w, d in zip(ws, durs):
            d *= scale
            words.append({"w": w, "start": round(s, 4), "end": round(s + 0.92 * d, 4), "slot": d})
            s += d
        rows.append({"line": line, "start": t, "end": s, "words": words})
        t = s + gap
    return rows, rows[-1]["end"] + tail


def fit_film(lines, film):
    lo, hi = 1.2, 2.2
    rows, total = speed_timings(lines, wps=hi)
    if total >= film:
        return rows, total, hi, 0.8
    for _ in range(50):
        mid = (lo + hi) / 2
        if speed_timings(lines, wps=mid)[1] < film:
            hi = mid
        else:
            lo = mid
    wps = (lo + hi) / 2
    rows, total = speed_timings(lines, wps=wps)
    if total < film - 1e-3:  # pace floor reached: open the gaps (<= 2.2 s)
        wps = 1.2
        glo, ghi = 0.8, 2.2
        for _ in range(50):
            g = (glo + ghi) / 2
            if speed_timings(lines, wps=wps, gap=g)[1] < film:
                glo = g
            else:
                ghi = g
        rows, total = speed_timings(lines, wps=wps, gap=(glo + ghi) / 2)
        return rows, total, wps, (glo + ghi) / 2
    return rows, total, wps, 0.8


def back_out(s):
    return lambda p: 1 - (1 - p) ** 2 * ((s + 1) * (1 - p) - s)


def power_out(n):
    return lambda p: 1 - (1 - p) ** (n + 1)


def power_in(n):
    return lambda p: p ** (n + 1)


def max_err(samples, fn):
    n = len(samples) - 1
    return max(abs(v - fn(i / n)) for i, v in enumerate(samples))


def parse_tx(m):
    """translateX from a computed CSS transform string."""
    if not m or m == "none":
        return 0.0
    v = [float(x) for x in m[m.index("(") + 1:-1].split(",")]
    return v[4] if len(v) == 6 else v[12]


def ode_step_response(m, c, k, T, dt=1e-4):
    """RK4 integration of m x'' + c x' + k (x - 1) = 0 from rest at 0."""
    x, v, out = 0.0, 0.0, [0.0]
    f = lambda x, v: (v, (-c * v - k * (x - 1)) / m)
    for _ in range(int(round(T / dt))):
        k1 = f(x, v)
        k2 = f(x + dt / 2 * k1[0], v + dt / 2 * k1[1])
        k3 = f(x + dt / 2 * k2[0], v + dt / 2 * k2[1])
        k4 = f(x + dt * k3[0], v + dt * k3[1])
        x += dt / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0])
        v += dt / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1])
        out.append(x)
    return out


def spring_fz(t, t0, f, z):
    x = t - t0
    if x <= 0:
        return 0.0
    w = 2 * math.pi * f
    wd = w * math.sqrt(1 - z * z)
    return 1 - math.exp(-z * w * x) * (math.cos(wd * x) + z * w / wd * math.sin(wd * x))


def spring_ease(response, damping_fraction, eps=0.001, steps=4800):
    if damping_fraction < 0.55:
        raise ValueError("dampingFraction < 0.55 is forbidden")
    w0, z = 2 * math.pi / response, damping_fraction

    def x(t):
        if z >= 1:
            return 1 - math.exp(-w0 * t) * (1 + w0 * t)
        wd = w0 * math.sqrt(1 - z * z)
        return 1 - math.exp(-z * w0 * t) * (math.cos(wd * t) + z * w0 / wd * math.sin(wd * t))
    horizon = 12 * response
    dur = horizon
    for i in range(steps, -1, -1):
        t = horizon * i / steps
        if abs(x(t) - 1) > eps:
            dur = horizon * (i + 1) / steps
            break
    end = x(dur)
    return dur, (lambda p: x(p * dur) / end), x


def lint_13(tl, W=1920, bpm=120):
    issues = []
    for el in tl["elements"]:
        for (t0, x0), (t1, x1) in zip(el["keys"], el["keys"][1:]):
            if abs(x1 - x0) > W / 3:
                issues.append(("travel", el["id"], t0))
    n = len(tl["elements"])
    for k in range(0, int(tl["dur"] * 10)):
        t = k / 10 + 0.05
        moving = sum(1 for el in tl["elements"] if el["keys"][0][0] <= t < el["keys"][-1][0])
        if moving > n / 3:
            issues.append(("crowd", moving, t))
            break
    ev = sorted(tl["events"]) + [tl["dur"]]
    for a, b in zip([0] + ev, ev):
        if b - a > 4:
            issues.append(("gap", a, b))
    for a, b in tl["holds"]:
        if b - a > 1.5 * 60 / bpm:
            issues.append(("hold", a, b))
    return issues


def fix_13(tl, W=1920, bpm=120):
    out = json.loads(json.dumps(tl))
    for el in out["elements"]:
        keys = [el["keys"][0]]
        for (t0, x0), (t1, x1) in zip(el["keys"], el["keys"][1:]):
            n = math.ceil(abs(x1 - x0) / (W / 3))
            for j in range(1, n + 1):
                keys.append([t0 + (t1 - t0) * j / n, x0 + (x1 - x0) * j / n])
        el["keys"] = keys
    per = max(1, len(out["elements"]) // 3)
    for i, el in enumerate(out["elements"]):
        span = el["keys"][-1][0] - el["keys"][0][0]
        start = (i // per) * (span + 0.1)
        base = el["keys"][0][0]
        el["keys"] = [[start + (t - base), x] for t, x in el["keys"]]
    out["dur"] = max(out["dur"], max(el["keys"][-1][0] for el in out["elements"]))
    ev = sorted(out["events"])
    filled, prev = [], 0
    for e in ev + [out["dur"]]:
        while e - prev > 4:
            prev += 3
            filled.append(prev)
        if e < out["dur"]:
            filled.append(e)
        prev = e
    out["events"] = sorted(filled)
    out["holds"] = [[a, min(b, a + 1.5 * 60 / bpm)] for a, b in out["holds"]]
    return out


def ease_out_cubic(p):
    return 1 - (1 - p) ** 3


UI_LADDER = {"micro": (80, 120), "button": (120, 180), "icon": (150, 250), "card": (200, 350), "modal": (300, 400),
             "page": (400, 600), "dramatic": (600, 1200)}


def ui_duration(element, video=False):
    lo, hi = UI_LADDER[element]
    enter = hi if video else (lo + hi) / 2
    return {"enter": enter, "exit": 0.75 * enter, "exit_ease": "power2.in", "enter_ease": "power2.out"}


def word_layer(text="WOW", size=(200, 100)):
    from PIL import Image, ImageDraw, ImageFont
    im = Image.new("L", size, 0)
    d = ImageDraw.Draw(im)
    try:
        font = ImageFont.load_default(size=48)
    except TypeError:
        font = ImageFont.load_default()
    d.text((size[0] / 2, size[1] / 2), text, fill=255, font=font, anchor="mm")
    return im


def sharpness(a):
    import numpy as np
    a = np.asarray(a, dtype=float)
    if a.ndim == 3:
        a = a.mean(axis=2)
    return float(np.abs(np.diff(a, axis=1)).mean() + np.abs(np.diff(a, axis=0)).mean())


def edge_ramp(row, thr_lo=0.1, thr_hi=0.9):
    """Width in px of the leading-edge ramp of a 1-D brightness profile."""
    import numpy as np
    row = np.asarray(row, dtype=float)
    m = row.max()
    if m <= 0:
        return 0
    n = row / m
    lo = int(np.argmax(n > thr_lo))
    hi = int(np.argmax(n > thr_hi))
    return hi - lo


def cut_film(path, shots, fps=10, size=(32, 18), first_change=None):
    """Render a film of flat-colour shots (one colour per shot); optional element popping in at a frame."""
    import numpy as np
    w, h = size
    frames, palette = [], [(200, 40, 40), (40, 160, 60), (40, 70, 200), (220, 200, 40), (160, 40, 200), (40, 200, 200)]
    for i, dur in enumerate(shots):
        n = int(round(dur * fps))
        for k in range(n):
            a = np.zeros((h, w, 3), dtype=np.uint8)
            a[:] = palette[i % len(palette)]
            if first_change is not None and i == 0 and k >= first_change:
                a[h // 3:2 * h // 3, w // 3:w // 2] = 255
            frames.append(a)
    return write_mp4(path, frames, fps)


def detect_cuts(path, size=(32, 18), thr=40):
    import numpy as np
    fr = read_mp4(path, *size)
    d = [float(np.abs(fr[i + 1] - fr[i]).mean()) for i in range(len(fr) - 1)]
    return [i + 1 for i, v in enumerate(d) if v > thr], len(fr), d


def cut_list(mode, every=2.0, dur=10.0, beats=None, voiced=None, shots=None):
    if mode == "interval":
        return [round(every * k, 6) for k in range(1, int(dur / every + 1e-9)) if every * k < dur]
    if mode == "beat":
        gap, out = max(0.45, 0.8 * every), []
        for b in beats:
            if not out or b - out[-1] >= gap - 1e-9:
                out.append(b)
        return out
    if mode == "speech":
        gap, out, prev_end = max(0.8, every / 2), [], -1e9
        for s, e in voiced:
            if s - prev_end >= 0.3 and (not out or s - out[-1] >= gap):
                out.append(s)
            prev_end = e
        return out
    if mode == "shots":
        return list(shots)
    raise ValueError(mode)


def snap_time(t, targets, px_per_s, w=7):
    best = min(targets, key=lambda x: abs(x - t))
    return best if abs(best - t) * px_per_s <= w else t


def ramp_map(keys):
    """Exact output time for input time s under piecewise-linear speed keys [[s, v], ...] (integral of ds / v)."""
    def T(s):
        acc = 0.0
        for (s0, v0), (s1, v1) in zip(keys, keys[1:]):
            if s <= s0:
                break
            e = min(s, s1)
            b = (v1 - v0) / (s1 - s0)
            v_e = v0 + b * (e - s0)
            acc += (e - s0) / v0 if abs(b) < 1e-12 else math.log(v_e / v0) / b
        return acc
    return T


def ramp_expr(keys):
    """ffmpeg setpts expression in seconds of input time T (log integral, nested if)."""
    T = ramp_map(keys)
    expr = None
    for (s0, v0), (s1, v1) in reversed(list(zip(keys, keys[1:]))):
        b = (v1 - v0) / (s1 - s0)
        seg = "(%.9f+log((%.9f+%.9f*(T-%.9f))/%.9f)/%.9f)" % (T(s0), v0, b, s0, v0, b) if abs(b) > 1e-12 else \
            "(%.9f+(T-%.9f)/%.9f)" % (T(s0), s0, v0)
        expr = seg if expr is None else "if(lt(T,%.9f),%s,%s)" % (s1, seg, expr)
    return expr


def lint_motion_css(rules):
    bad = []
    for sel, decl in rules.items():
        t = decl.get("transition", "")
        if " all" in " " + t or t.startswith("all"):
            bad.append((sel, "transition-all"))
        props = [p.strip().split()[0] for p in t.split(",") if p.strip()]
        if any(p not in ("transform", "opacity", "all") for p in props):
            bad.append((sel, "non-compositor property"))
        if decl.get("money") and decl.get("count-up"):
            bad.append((sel, "money value animates"))
    return bad


def fix_motion_css(rules):
    out = {}
    for sel, decl in rules.items():
        d = dict(decl)
        if "transition" in d:
            dur = [w for w in d["transition"].split() if w.endswith("ms")][:1] or ["200ms"]
            d["transition"] = "transform %s ease-out, opacity %s ease-out" % (dur[0], dur[0])
        if d.get("money"):
            d.pop("count-up", None)
        out[sel] = d
    return out


def ae_to_css(out_influence, in_influence, out_speed=0.0, in_speed=0.0):
    """After Effects keyframe influence (%) with zero speed -> CSS cubic-bezier."""
    return (round(out_influence / 100, 3), out_speed, round(1 - in_influence / 100, 3), 1 - in_speed)


def srgb_to_oklab(c):
    def lin(u):
        u /= 255
        return u / 12.92 if u <= 0.04045 else ((u + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(x) for x in c)
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s, 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


X07 = {"entrance": (0.45, 0.7), "scale_from_min": 0.9, "travel_max": 70, "overshoot_max": 0.04, "stagger": (0.05, 0.08),
       "read_min": 0.8, "appear_min": 0.2, "type_cps_max": 60}


def lint_x07(items):
    bad = []
    for it in items:
        if it["kind"] == "entrance":
            if not X07["entrance"][0] <= it["dur"] <= X07["entrance"][1]:
                bad.append((it["id"], "dur"))
            if it["scale_from"] < X07["scale_from_min"]:
                bad.append((it["id"], "scale"))
            if it["travel"] > X07["travel_max"]:
                bad.append((it["id"], "travel"))
            if it.get("ease") == "back.out(1.7)":
                bad.append((it["id"], "overshoot"))
        if it["kind"] == "read" and it["dur"] < X07["read_min"]:
            bad.append((it["id"], "read"))
        if it["kind"] == "stagger" and not X07["stagger"][0] <= it["each"] <= X07["stagger"][1]:
            bad.append((it["id"], "stagger"))
        if it["kind"] == "type" and it["cps"] > X07["type_cps_max"]:
            bad.append((it["id"], "type"))
    return bad


def fix_x07(items):
    out = []
    for it in items:
        it = dict(it)
        if it["kind"] == "entrance":
            it["dur"] = min(max(it["dur"], 0.45), 0.7)
            it["scale_from"] = max(it["scale_from"], 0.9)
            it["travel"] = min(it["travel"], 70)
            it["ease"] = "cubic-bezier(.16,1,.3,1)"
        if it["kind"] == "read":
            it["dur"] = max(it["dur"], 0.8)
        if it["kind"] == "stagger":
            it["each"] = min(max(it["each"], 0.05), 0.08)
        if it["kind"] == "type":
            it["cps"] = min(it["cps"], 60)
        out.append(it)
    return out


def read_time(words, k=1.0):
    return max(1.0, 0.35 * words + 0.5) * k


def stills(frames, fps, thr=0.5):
    import numpy as np
    runs, start = [], 0
    for i in range(1, len(frames) + 1):
        if i == len(frames) or float(np.abs(frames[i] - frames[i - 1]).mean()) > thr:
            runs.append((start / fps, i / fps))
            start = i
    return runs


def hf_component(wd, name, variables, probe_js, size=(960, 540)):
    """`npx hyperframes add <name>` into wd, mount the component's <template> in a host page with GSAP and
    window.__hyperframes.getVariables, then run probe_js in headless Chrome (G(el, prop) = gsap.getProperty)."""
    import re
    proj = Path(wd) / "hf"
    proj.mkdir(exist_ok=True)
    subprocess.run(["npx", "--no-install", "hyperframes", "add", name], cwd=proj, capture_output=True, text=True, timeout=90,
                       stdin=subprocess.DEVNULL, check=True)
    comp = proj / ("compositions/components/%s.html" % name)
    src = comp.read_text(encoding="utf-8")
    m = re.search(r"<template>(.*)</template>", src, re.S)
    inner = re.sub(r'<script src="[^"]*gsap[^"]*"></script>', "", m.group(1))
    shutil.copy(GSAP / "dist/gsap.min.js", Path(wd) / "gsap.min.js")
    page = """<!doctype html><html><head><meta charset=utf-8><script src="gsap.min.js"></script></head>
<body style="margin:0"><div id="host" style="position:relative;width:%dpx;height:%dpx"></div><template id="tpl">%s</template><script>
window.__hyperframes={getVariables:()=>(%s)};
const host=document.getElementById('host'); const frag=document.getElementById('tpl').content.cloneNode(true);
const scripts=[...frag.querySelectorAll('script')]; scripts.forEach(s=>s.remove()); host.appendChild(frag);
for(const s of scripts){const n=document.createElement('script'); n.textContent=s.textContent; document.body.appendChild(n);}
</script><script>(function(){const tl=window.__timelines[%s], G=(e,p)=>+gsap.getProperty(e,p), $=(s)=>host.querySelector(s), $$=(s)=>[...host.querySelectorAll(s)];
%s
})();</script></body></html>""" % (size[0], size[1], inner, json.dumps(variables), json.dumps(name), probe_js)
    return chrome(wd, "mount_" + name, page), comp
