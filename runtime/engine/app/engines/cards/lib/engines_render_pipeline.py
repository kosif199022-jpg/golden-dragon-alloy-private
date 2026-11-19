"""Helpers of power_programs/engines_render_pipeline.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from PIL import Image
from PIL import ImageDraw
from pathlib import Path
import hashlib
import json
import math
import numpy as np
import re
import wave


def write_png(path, arr):
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).save(path)


def write_wav(path, samples, sr=16000, channels=1):
    s = np.asarray(samples, dtype=np.float64)
    if channels == 2 and s.ndim == 1:
        s = np.stack([s, s], 1)
    pcm = (np.clip(s, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())


def tone(freq, sec, sr=16000, amp=0.5):
    t = np.arange(int(sec * sr)) / sr
    return amp * np.sin(2 * np.pi * freq * t)


def amp_at(x, freq, sr):
    """Amplitude of a sinusoid at freq in signal x (single-bin DFT)."""
    n = len(x)
    t = np.arange(n) / sr
    return 2 * abs(np.dot(x, np.exp(-2j * np.pi * freq * t))) / n


def save_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def mulberry32(seed):
    """Exact port of the JS mulberry32 (constant 0x6D2B79F5), 32-bit integer maths."""
    state = [seed & 0xFFFFFFFF]

    def imul(a, b):
        return (a * b) & 0xFFFFFFFF

    def nxt():
        state[0] = (state[0] + 0x6D2B79F5) & 0xFFFFFFFF
        a = state[0]
        t = imul(a ^ (a >> 15), 1 | a)
        t = ((t + imul(t ^ (t >> 7), 61 | t)) & 0xFFFFFFFF) ^ t
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296
    return nxt


def hash2(i, j):
    """Stateless integer hash of a cell -> [0,1) (mulberry32 seeded with a mixed key)."""
    return mulberry32((i * 374761393 + j * 668265263) & 0xFFFFFFFF)()


def parse_html(text):
    from bs4 import BeautifulSoup
    return BeautifulSoup(text, "html.parser")


def _raises(fn, exc):
    try:
        fn()
    except exc:
        return True
    return False


def clamp01(x):
    return max(0.0, min(1.0, x))


def composition_errors(html, required=("data-composition-id", "data-width", "data-height", "data-duration", "data-fps"),
                       fps_allowed=None, root_selector=None):
    """Validate a seekable HTML composition: a root carrying the data-* attrs, a paused timeline
    registered literally on window.__timelines[<id>], and a MOTION.shim(<id>, seconds) call that
    matches data-duration. Returns a list of problems (empty = valid)."""
    soup = parse_html(html)
    root = soup.select_one(root_selector) if root_selector else soup.find(attrs={"data-composition-id": True})
    if root is None:
        return ["no root with data-composition-id"]
    errs = [f"root missing {a}" for a in required if not root.has_attr(a)]
    if errs:
        return errs
    for a in ("data-width", "data-height", "data-duration", "data-fps"):
        if root.has_attr(a):
            try:
                if float(root[a]) <= 0:
                    errs.append(f"{a} not positive")
            except ValueError:
                errs.append(f"{a} not numeric")
    if fps_allowed and root.has_attr("data-fps") and int(float(root["data-fps"])) not in fps_allowed:
        errs.append(f"data-fps {root['data-fps']} not in {sorted(fps_allowed)}")
    cid = root["data-composition-id"]
    script = "\n".join(s.get_text() for s in soup.find_all("script"))
    if not re.search(r"window\.__timelines\[\s*['\"]%s['\"]\s*\]\s*=" % re.escape(cid), script):
        errs.append("timeline not registered literally on window.__timelines")
    if "paused" not in script or not re.search(r"paused\s*:\s*true", script):
        errs.append("timeline not paused")
    m = re.search(r"MOTION\.shim\(\s*['\"]%s['\"]\s*,\s*([\d.]+)\s*\)" % re.escape(cid), script)
    if "MOTION.shim" in script or "data-fps" in required:
        if not m:
            errs.append("MOTION.shim(root, seconds) missing")
        elif root.has_attr("data-duration") and abs(float(m.group(1)) - float(root["data-duration"])) > 1e-9:
            errs.append("shim seconds differ from data-duration")
    return errs


def composition_page(cid="root", w=1920, h=1080, dur=8, fps=30, shim=True, extra_body="", attrs=None):
    a = {"data-composition-id": cid, "data-width": w, "data-height": h, "data-duration": dur, "data-fps": fps}
    if attrs is not None:
        a = attrs
    at = " ".join(f'{k}="{v}"' for k, v in a.items())
    sh_line = f"MOTION.shim('{cid}', {dur});" if shim else ""
    return (f"<!doctype html><html><body><div id=\"{cid}\" {at}>{extra_body}</div>"
            f"<script>const tl = gsap.timeline({{paused: true}});\n"
            f"tl.to('#{cid} .t', {{opacity: 1, duration: 1}}, 0.2);\n"
            f"window.__timelines = window.__timelines || {{}};\nwindow.__timelines['{cid}'] = tl;\n{sh_line}</script>"
            f"</body></html>")


BANNED_JS = {
    "Math.random": r"Math\.random\s*\(",
    "Date.now": r"Date\.now\s*\(",
    "performance.now": r"performance\.now\s*\(",
    "requestAnimationFrame": r"requestAnimationFrame\s*\(",
    "setTimeout": r"setTimeout\s*\(",
    "setInterval": r"setInterval\s*\(",
    "fetch": r"\bfetch\s*\(",
}


def lint_js(src, banned):
    """Return the banned names that occur in JS source (comments stripped)."""
    code = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    code = re.sub(r"//[^\n]*", "", code)
    return sorted(name for name in banned if re.search(BANNED_JS.get(name, re.escape(name)), code))


def post_stack(img, bloom=.22, radius=.6, threshold=.9, clamp=48.0, vignette=.42, ca=1.2, grain=.16, seed=1):
    """NaN guard -> clamp -> bloom (threshold, gaussian radius) -> CA -> vignette -> grain."""
    from scipy.ndimage import gaussian_filter
    x = np.nan_to_num(np.asarray(img, np.float64), nan=0.0, posinf=clamp, neginf=0.0)
    x = np.minimum(x, clamp)
    bright = np.maximum(x - threshold, 0)
    sig = radius * min(x.shape[:2]) / 16
    x = x + bloom * np.stack([gaussian_filter(bright[..., c], sig) for c in range(3)], -1)
    s = int(round(ca))
    if s:
        x[..., 0] = np.roll(x[..., 0], s, axis=1)
        x[..., 2] = np.roll(x[..., 2], -s, axis=1)
    h, w = x.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    r2 = (((xx - (w - 1) / 2) / ((w - 1) / 2)) ** 2 + ((yy - (h - 1) / 2) / ((h - 1) / 2)) ** 2) / 2
    x = x * (1 - vignette * r2)[..., None]
    if grain:
        rng = np.random.default_rng(seed)
        x = x + (rng.random((h, w, 1)) - 0.5) * grain
    return x


def shard_plan(frames, n):
    base, extra = divmod(frames, n)
    shards, i0 = [], 0
    for k in range(n):
        i1 = i0 + base + (1 if k < extra else 0)
        shards.append({"i0": i0, "i1": i1})
        i0 = i1
    return {"frames": frames, "shards": shards}


def pick_video_codec(w, h, fps, supported):
    ll = "2A" if (w * h > 1280 * 720 or fps > 30) else "1F"
    chain = [f"avc1.6400{ll}", f"avc1.4D40{ll}", f"avc1.42E0{ll}", "avc1.42E01F"]
    for c in chain:
        if c in supported:  # isConfigSupported({codec:c, bitrate:8e6})
            return c, chain
    return None, chain


def ss_mask(polys, w, h, ss=3, holes=()):
    big = Image.new("L", (w * ss, h * ss), 0)
    d = ImageDraw.Draw(big)
    for p in polys:
        d.polygon([(x * ss, y * ss) for x, y in p], fill=255)
    for p in holes:
        d.polygon([(x * ss, y * ss) for x, y in p], fill=0)
    return np.asarray(big.reduce(ss)).astype(int)


NAMED = {"black": (0, 0, 0), "white": (255, 255, 255), "red": (255, 0, 0), "lime": (0, 255, 0), "blue": (0, 0, 255),
         "rebeccapurple": (102, 51, 153), "orange": (255, 165, 0), "gold": (255, 215, 0), "teal": (0, 128, 128),
         "navy": (0, 0, 128), "gray": (128, 128, 128), "silver": (192, 192, 192), "crimson": (220, 20, 60)}


def svg_length(v, ref=100.0):
    v = v.strip()
    m = re.fullmatch(r"(-?[\d.]+)(px|%|em|rem|pt)?", v)
    num, unit = float(m.group(1)), m.group(2) or "px"
    return {"px": num, "%": num * ref / 100, "em": num * 16, "rem": num * 16, "pt": num * 1.333}[unit]


def svg_color(v, current=(0, 0, 0)):
    v = v.strip().lower()
    if v == "currentcolor":
        return current + (1.0,)
    if v in NAMED:
        return NAMED[v] + (1.0,)
    if v.startswith("#"):
        hx = v[1:]
        if len(hx) == 3:
            hx = "".join(c * 2 for c in hx)
        return tuple(int(hx[i:i + 2], 16) for i in (0, 2, 4)) + (1.0,)
    m = re.fullmatch(r"(rgba?|hsla?)\(([^)]*)\)", v)
    parts = [p.strip() for p in m.group(2).split(",")]
    a = float(parts[3]) if len(parts) > 3 else 1.0
    if m.group(1).startswith("rgb"):
        return tuple(int(round(float(p[:-1]) * 2.55)) if p.endswith("%") else int(float(p)) for p in parts[:3]) + (a,)
    import colorsys
    hh, ss, ll = float(parts[0]) / 360, float(parts[1].rstrip("%")) / 100, float(parts[2].rstrip("%")) / 100
    r, g, b = colorsys.hls_to_rgb(hh, ll, ss)
    return (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)), a)


def svg_transform(s):
    M = np.eye(3)
    for name, args in re.findall(r"(\w+)\(([^)]*)\)", s):
        a = [float(x) for x in re.split(r"[ ,]+", args.strip())]
        if name == "translate":
            T = np.array([[1, 0, a[0]], [0, 1, a[1] if len(a) > 1 else 0], [0, 0, 1]])
        elif name == "scale":
            T = np.diag([a[0], a[1] if len(a) > 1 else a[0], 1])
        elif name == "rotate":
            c, s_ = math.cos(math.radians(a[0])), math.sin(math.radians(a[0]))
            T = np.array([[c, -s_, 0], [s_, c, 0], [0, 0, 1]])
        elif name == "skewX":
            T = np.array([[1, math.tan(math.radians(a[0])), 0], [0, 1, 0], [0, 0, 1]])
        elif name == "skewY":
            T = np.array([[1, 0, 0], [math.tan(math.radians(a[0])), 1, 0], [0, 0, 1]])
        else:
            T = np.array([[a[0], a[2], a[4]], [a[1], a[3], a[5]], [0, 0, 1]])
        M = M @ T
    return M


SKIP_TAGS = {"filter", "mask", "clipPath", "pattern", "image"}


def load_svg(text, max_steps=160):
    root = ET.fromstring(text)
    steps = []
    title = None

    def tag(e):
        return e.tag.split("}")[-1]

    def walk(e, M):
        nonlocal title
        t = tag(e)
        if t == "title":
            title = e.text
        if t in SKIP_TAGS or t == "defs":
            return
        M2 = M @ svg_transform(e.get("transform", "")) if e.get("transform") else M
        if t in {"rect", "circle", "ellipse", "line", "polyline", "polygon", "path", "text"}:
            steps.append({"tag": t, "fill": e.get("fill"), "matrix": M2.round(6).tolist()})
        for c in e:
            if len(steps) < max_steps:
                walk(c, M2)
    walk(root, np.eye(3))
    return title, steps[:max_steps]


def gradient_chain(grads, gid, limit=8):
    seen, cur = [], gid
    while cur and len(seen) < limit:
        if cur in seen:
            break
        seen.append(cur)
        cur = grads.get(cur)
    return seen


def subframe_render(pos_fn, w, h, n, fps, k, shutter, stack="average"):
    """Render n frames of a 1-px dot moving by pos_fn(t); accumulate k sub-frames over shutter*frame."""
    out = []
    for i in range(n):
        acc = np.zeros((h, w))
        for j in range(k):
            t = (i + (shutter * (j + 0.5) / k if k > 1 else 0)) / fps
            img = np.zeros((h, w))
            x = int(round(pos_fn(t)))
            if 0 <= x < w:
                img[:, x] = 1.0
            acc = np.maximum(acc, img) if stack == "lighten" else acc + img / k
        out.append(acc)
    return out


def storyboard_errors(sb):
    p = []
    for k in ["version", "brief", "duration_seconds", "aspect", "fps", "scenes"]:
        if k not in sb:
            p.append(f"missing {k}")
    if p:
        return p
    if sb["fps"] != 30:
        p.append("fps must be 30")
    prev = 0
    for i, s in enumerate(sb["scenes"]):
        if s.get("id") != f"scene-{i + 1:02d}":
            p.append(f"id {s.get('id')}")
        for k in ["start", "end"]:
            if round(s[k], 3) != s[k]:
                p.append(f"{s['id']} {k} beyond ms precision")
        if s["start"] != prev or s["end"] <= s["start"]:
            p.append(f"{s['id']} timing")
        prev = s["end"]
        for k in ["title", "text", "visual", "motion", "sfx"]:
            if k not in s:
                p.append(f"{s['id']} missing {k}")
    if abs(prev - sb["duration_seconds"]) > 1e-9:
        p.append("scenes do not end at duration")
    return p


def value_noise(t, seed=0, rate=8.0):
    x = t * rate
    i = math.floor(x)
    f = x - i
    a, b = hash2(i, seed), hash2(i + 1, seed)
    u = f * f * (3 - 2 * f)
    return (a + (b - a) * u) * 2 - 1


def sampled(fn, t0, t1, fps=60):
    n = round((t1 - t0) * fps)
    return [{"duration": 1 / fps, "ease": "none", **fn(t0 + (i + 1) / fps)} for i in range(n)]


def play_keyframes(start, kfs, t, key):
    """GSAP-style keyframe playback (ease none): linear between successive keyframe values."""
    prev, acc = start, 0.0
    for k in kfs:
        if t <= acc + k["duration"] + 1e-12:
            u = (t - acc) / k["duration"]
            return prev + (k[key] - prev) * u
        prev, acc = k[key], acc + k["duration"]
    return prev


def mulberry32_np(seed, n):
    """Second, independent implementation with numpy uint32 arithmetic (the '3D kit' copy)."""
    a = np.uint32(seed)
    out = []
    with np.errstate(over="ignore"):
        for _ in range(n):
            a = np.uint32(a + np.uint32(0x6D2B79F5))
            t = np.uint32((a ^ (a >> np.uint32(15))) * (np.uint32(1) | a))
            t = np.uint32((t + np.uint32((t ^ (t >> np.uint32(7))) * (np.uint32(61) | t))) ^ t)
            out.append(float(np.uint32(t ^ (t >> np.uint32(14)))) / 4294967296)
    return out


def aces(x, exposure=0.6):
    x = np.asarray(x, np.float64) * exposure
    return np.clip((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0, 1)


def pbr_neutral(c):
    c = np.array(c, np.float64)
    start, desat = 0.8 - 0.04, 0.15
    x = c.min()
    off = x - 6.25 * x * x if x < 0.08 else 0.04
    c = c - off
    peak = c.max()
    if peak < start:
        return c
    d = 1 - start
    new = 1 - d * d / (peak + d - start)
    c = c * new / peak
    g = 1 - 1 / (desat * (peak - new) + 1)
    return c * (1 - g) + new * g


def spring(t, k, d, m=1.0):
    w0 = math.sqrt(k / m)
    z = d / (2 * math.sqrt(k * m))
    if z < 1:
        wd = w0 * math.sqrt(1 - z * z)
        return 1 - math.exp(-z * w0 * t) * (math.cos(wd * t) + z * w0 / wd * math.sin(wd * t))
    if z == 1:
        return 1 - math.exp(-w0 * t) * (1 + w0 * t)
    r1, r2 = -w0 * (z - math.sqrt(z * z - 1)), -w0 * (z + math.sqrt(z * z - 1))
    c2 = r1 / (r1 - r2)
    c1 = 1 - c2
    return 1 - (c1 * math.exp(r1 * t) + c2 * math.exp(r2 * t))


def spring_ode(t_end, k, d, dt=1e-4):
    x, v = 0.0, 0.0
    for _ in range(int(t_end / dt)):
        a = -k * (x - 1) - d * v
        v += a * dt
        x += v * dt
    return x


def project_kind(html):
    if re.search(r"three-kit|window\.K3", html):
        kind = "3d"
    elif re.search(r"window\.seek\s*=", html):
        kind = "canvas"
    elif "manifest-player" in html:
        kind = "manifest"
    else:
        kind = "2d"
    w = re.search(r'data-width="(\d+)"', html)
    h = re.search(r'data-height="(\d+)"', html)
    d = re.search(r'data-duration="([\d.]+)"', html)
    return {"kind": kind, "size": (int(w.group(1)), int(h.group(1))) if w and h else None, "duration": float(d.group(1)) if d else None}


def render_contract_errors(html):
    soup = parse_html(html)
    p = []
    body = soup.body
    for a in ["data-composition-id", "data-width", "data-height", "data-duration", "data-fps"]:
        if body is None or not body.has_attr(a):
            p.append(f"body missing {a}")
    js = "\n".join(s.get_text() for s in soup.find_all("script"))
    for need, rx in [("window.render", r"window\.render\s*="), ("window.__duration", r"window\.__duration\s*="), ("window.__ready", r"window\.__ready\s*=\s*true")]:
        if not re.search(rx, js):
            p.append(f"missing {need}")
    if "capture" not in js:
        p.append("no ?capture mode")
    m = re.search(r"window\.render\s*=\s*function\s*\(\s*t\s*\)\s*\{(.*?)\n\};", js, re.S)
    if m and lint_js(m.group(1), ["requestAnimationFrame", "Date.now", "Math.random"]):
        p.append("render(t) not pure")
    return p


def fingerprint(project, params):
    h = hashlib.sha1()
    for p in sorted(project.rglob("*")):
        if not p.is_file() or p.name.endswith(".kosif.json") or p.suffix == ".mp4":
            continue
        rel = str(p.relative_to(project))
        if p.suffix in {".html", ".js", ".css", ".json", ".svg", ".txt"}:
            h.update(rel.encode() + p.read_bytes())
        else:
            st = p.stat()
            h.update(f"{rel}:{st.st_size}:{st.st_mtime_ns}".encode())
    keys = ["engine", "fps", "size", "scale", "blur", "shutter", "stack", "capture", "preset", "crf", "quality"]
    h.update(json.dumps({**{k: params.get(k) for k in keys}, "v": 4}, sort_keys=True).encode())
    return h.hexdigest()


def cached_render(project, film, params, force=False):
    fp = fingerprint(project, params)
    stamp = Path(str(film) + ".kosif.json")
    if not force and film.exists() and stamp.exists() and json.loads(stamp.read_text())["fingerprint"] == fp:
        return "cached"
    film.write_bytes(b"film" + fp.encode())
    save_json(stamp, {"fingerprint": fp, "params": params})
    return "rendered"


def hf_errors(html, fps_allowed=(24, 30, 60), sizes=((1920, 1080), (1080, 1920))):
    p = composition_errors(html, required=("data-composition-id", "data-width", "data-height", "data-duration"), fps_allowed=fps_allowed)
    soup = parse_html(html)
    root = soup.find(attrs={"data-composition-id": True})
    if root is not None and root.has_attr("data-width") and (int(root["data-width"]), int(root["data-height"])) not in sizes:
        p.append("size")
    for c in soup.find_all(class_="clip"):
        for a in ["id", "data-start", "data-duration", "data-track-index"]:
            if not c.has_attr(a):
                p.append(f"clip missing {a}")
    js = "\n".join(s.get_text() for s in soup.find_all("script"))
    if re.search(r"(setTimeout|then|addEventListener)\s*\([^;]*__timelines", js, re.S):
        p.append("timeline registered asynchronously")
    return [e for e in p if e != "MOTION.shim(root, seconds) missing"]


def subcomp_errors(host, subs):
    p = []
    soup = parse_html(host)
    for h in soup.find_all(attrs={"data-composition-src": True}):
        for a in ["data-composition-id", "data-start", "data-duration", "data-track-index"]:
            if not h.has_attr(a):
                p.append(f"host missing {a}")
        sub = subs.get(h["data-composition-src"])
        if sub is None:
            p.append("missing sub file")
        elif not parse_html(sub).find("template"):
            p.append("sub not wrapped in <template>")
    for v in soup.find_all("video"):
        if not (v.has_attr("muted") and v.has_attr("playsinline")):
            p.append("video must be muted playsinline")
    if soup.find_all("video") and not soup.find_all("audio"):
        p.append("no separate <audio> element")
    js = "\n".join(s.get_text() for s in soup.find_all("script"))
    if re.search(r"\.(to|from|fromTo)\(\s*['\"]video", js):
        p.append("animate a wrapper, not the <video>")
    return p


def cubic_bezier(x1, y1, x2, y2):
    def bx(s):
        return 3 * (1 - s) ** 2 * s * x1 + 3 * (1 - s) * s * s * x2 + s ** 3

    def by(s):
        return 3 * (1 - s) ** 2 * s * y1 + 3 * (1 - s) * s * s * y2 + s ** 3

    def f(x):
        lo, hi = 0.0, 1.0
        for _ in range(60):
            mid = (lo + hi) / 2
            if bx(mid) < x:
                lo = mid
            else:
                hi = mid
        return by((lo + hi) / 2)
    return f, bx, by


def interpolate(frame, inp, out, easing=None, clamp=True):
    if clamp:
        frame = min(max(frame, inp[0]), inp[-1])
    for k in range(len(inp) - 1):
        if frame <= inp[k + 1] or k == len(inp) - 2:
            p = (frame - inp[k]) / (inp[k + 1] - inp[k])
            e = easing[k] if isinstance(easing, list) else easing
            p = e(p) if e else p
            return out[k] + (out[k + 1] - out[k]) * p


def back_out(p, c=1.6):
    q = p - 1
    return q * q * ((c + 1) * q + c) + 1


def comfy_errors(g):
    errs = []
    for nid, node in g.items():
        if not isinstance(nid, str) or "class_type" not in node or "inputs" not in node:
            errs.append(f"{nid}: shape")
            continue
        for k, v in node["inputs"].items():
            if isinstance(v, list):
                if len(v) != 2 or str(v[0]) not in g or not isinstance(v[1], int):
                    errs.append(f"{nid}.{k}: bad link {v}")
    return errs


def guess_role(name):
    n = name.lower()
    ext = n.rsplit(".", 1)[-1]
    kind = {"mp4": "video", "mov": "video", "webm": "video", "mp3": "audio", "wav": "audio", "m4a": "audio", "png": "image", "jpg": "image",
            "jpeg": "image", "webp": "image", "pdf": "pdf", "txt": "text", "md": "text", "docx": "text", "srt": "captions", "vtt": "captions",
            "ttf": "font", "otf": "font", "woff2": "font", "zip": "zip", "json": "json"}.get(ext, "link")
    rules = {"video": [("ref", "ref"), ("مرجع", "ref"), ("bg", "bg")], "audio": [("voice", "voice"), ("تعليق", "voice"), ("music", "music"), ("أغنية", "music"), ("sfx", "sfx")],
             "image": [("logo", "logo"), ("شعار", "logo"), ("bg", "bg")], "pdf": [("brand", "brand")], "text": [("script", "script"), ("brand", "brand")]}
    default = {"video": "main", "audio": "music", "image": "clip", "pdf": "doc", "text": "doc", "link": "ref"}
    for key, role in rules.get(kind, []):
        if key in n:
            return kind, role
    return kind, default.get(kind, kind)


def blocked_host(host):
    import ipaddress
    h = host.strip("[]").lower()
    if h in {"localhost"} or h.endswith((".local", ".internal", ".localhost")):
        return True
    try:
        ip = ipaddress.ip_address(h)
    except ValueError:
        return bool(re.fullmatch(r"[\d.]+|0x[0-9a-f]+", h))
    if ip.version == 6:
        return True
    nets = ["10.0.0.0/8", "192.168.0.0/16", "172.16.0.0/12", "169.254.0.0/16", "100.64.0.0/10", "127.0.0.0/8", "0.0.0.0/8"]
    return any(ip in ipaddress.ip_network(n) for n in nets) or True


def clip_errors(html):
    soup = parse_html(html)
    p = []
    for e in soup.find_all(attrs={"data-start": True}):
        if e.has_attr("data-composition-id"):
            continue
        if "clip" not in (e.get("class") or []):
            p.append(f"#{e.get('id')} timed but not class=clip")
    return p


def lint_composition(src):
    codes = []
    if lint_js(src, ["Math.random", "Date.now", "performance.now"]):
        codes.append("non_deterministic_code")
    if lint_js(src, ["requestAnimationFrame"]):
        codes.append("requestanimationframe_in_composition")
    if re.search(r"gsap\.timeline\(\s*\)", src) or re.search(r"paused\s*:\s*false", src):
        codes.append("timeline_not_paused")
    return codes


def auto_workers_studio(frames, cores, software_gl=True, env=None):
    if env and env.get("KOSIF_WORKERS"):
        return int(env["KOSIF_WORKERS"])
    n = max(1, min(6, frames // 20))
    if software_gl:
        n = min(n, max(1, cores // 2))
    return n


def determinism_report(html):
    js = "\n".join(s.get_text() for s in parse_html(html).find_all("script"))
    srcs = [t.get("src") or t.get("href") or "" for t in parse_html(html).find_all(["script", "link", "img", "video", "audio"])]
    return {"seeded_rng": bool(re.search(r"\brng\(\s*\d+\s*\)", js)),
            "no_random_or_clock": not lint_js(js, ["Math.random", "Date.now"]),
            "fonts_ready_gate": "__kosifReady" in js,
            "no_network": not any(re.match(r"https?://", s) for s in srcs) and "fetch(" not in js}


def seekability_lint(src):
    p = []
    for name in ["setTimeout", "Math.random", "fetch"]:
        if lint_js(src, [name]):
            p.append(name)
    if re.search(r"requestAnimationFrame\([^)]*\)", src) and re.search(r"\b\w+\s*(\+=|-=|\+\+)", src):
        p.append("requestAnimationFrame state")
    if re.search(r"getBoundingClientRect\(\)[^;]*;\s*[^;]*tl\.(to|from|fromTo)", src) or re.search(r"tl\.(to|from|fromTo)\([^)]*getBoundingClientRect", src):
        p.append("getBoundingClientRect at tween creation")
    return p


def lottie_errors(doc, raw_bytes):
    p = []
    if doc.get("fr") not in (30, 60):
        p.append("fr must be 30 or 60")
    if len(raw_bytes) >= 100 * 1024:
        p.append("UI file >= 100 KB")
    for L in doc.get("layers", []):
        if L.get("ty") == 2:
            p.append(f"{L.get('nm')}: raster image layer")
        if L.get("ef"):
            p.append(f"{L.get('nm')}: layer effects")
        if L.get("bm", 0):
            p.append(f"{L.get('nm')}: blending mode")
        if L.get("ddd", 0):
            p.append(f"{L.get('nm')}: 3D layer")
        if '"x":' in json.dumps(L.get("ks", {})):
            p.append(f"{L.get('nm')}: expression")
    names = {m.get("cm") for m in doc.get("markers", [])}
    if not {"intro", "loop", "outro"} <= names:
        p.append("markers intro/loop/outro missing")
    return p
