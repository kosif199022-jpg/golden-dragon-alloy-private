"""Helpers of runners/fam_shapes_morph_geometry.py used by data cards, copied verbatim (the extractor binds a card to them only when
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
    m = re.search(r"^\s*<template>\s*$(.*)</template>", src, re.S | re.M) or re.search(r"<template>(.*)</template>", src, re.S)
    body = m.group(1) if m else src
    inner = re.sub(r'<script src="[^"]*gsap[^"]*"></script>', "", body)
    shutil.copy(GSAP / "dist/gsap.min.js", Path(wd) / "gsap.min.js")
    page = """<!doctype html><html><head><meta charset=utf-8><script src="gsap.min.js"></script></head>
<body style="margin:0"><div id="host" style="position:relative;width:%dpx;height:%dpx"></div><template id="tpl">%s</template><script>
window.__hyperframes={getVariables:()=>(%s)};
const host=document.getElementById('host'); const frag=document.getElementById('tpl').content.cloneNode(true);
const scripts=[...frag.querySelectorAll('script')]; scripts.forEach(s=>s.remove()); host.appendChild(frag);
for(const s of scripts){const n=document.createElement('script'); n.textContent=s.textContent; document.body.appendChild(n);}
</script><script>(function(){const tl=(window.__timelines||{})[%s], G=(e,p)=>+gsap.getProperty(e,p), $=(s)=>host.querySelector(s), $$=(s)=>[...host.querySelectorAll(s)];
%s
})();</script></body></html>""" % (size[0], size[1], inner, json.dumps(variables), json.dumps(name), probe_js)
    return chrome(wd, "mount_" + name, page), comp


def area(pts):
    return 0.5 * abs(sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts))))


def power_inout2(p):
    return (2 * p) ** 3 / 2 if p < 0.5 else 1 - (2 * (1 - p)) ** 3 / 2


def vnoise3(p, seed=7):
    """Smooth 3-D value noise (quintic-faded trilinear lattice), deterministic, in -1..1."""
    import numpy as np
    p = np.asarray(p, dtype=float)
    i = np.floor(p).astype(np.int64)
    f = p - i
    u = f * f * f * (f * (f * 6 - 15) + 10)

    def h(ix, iy, iz):
        n = (ix * 374761393 + iy * 668265263 + iz * 2147483647 + seed * 144665) & 0xFFFFFFFF
        n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
        return ((n ^ (n >> 16)) & 0xFFFF) / 32767.5 - 1.0
    out = 0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (u[..., 0] if dx else 1 - u[..., 0]) * (u[..., 1] if dy else 1 - u[..., 1]) * (u[..., 2] if dz else 1 - u[..., 2])
                out = out + w * h(i[..., 0] + dx, i[..., 1] + dy, i[..., 2] + dz)
    return out


def sphere_mesh(nu=48, nv=24):
    import numpy as np
    th = np.linspace(0, 2 * np.pi, nu, endpoint=False)
    ph = np.linspace(0.05, np.pi - 0.05, nv)
    T, P = np.meshgrid(th, ph)
    return np.stack([np.sin(P) * np.cos(T), np.cos(P), np.sin(P) * np.sin(T)], axis=-1).reshape(-1, 3)


def sd_circle(x, y, cx, cy, r):
    import numpy as np
    return np.hypot(x - cx, y - cy) - r


def sd_box(x, y, cx, cy, hx, hy):
    import numpy as np
    qx, qy = np.abs(x - cx) - hx, np.abs(y - cy) - hy
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0)


def smin(a, b, k):
    import numpy as np
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)


def catmull(points, n=10, closed=False):
    P = list(points)
    if closed:
        P = [P[-1]] + P + [P[0], P[1]]
    else:
        P = [P[0]] + P + [P[-1]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2 +
                                    (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in range(2)))
    out.append(tuple(P[-2]))
    return out


def arc_table(samples):
    acc = [0.0]
    for a, b in zip(samples, samples[1:]):
        acc.append(acc[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    return acc


def at_distance(samples, acc, s):
    import bisect
    i = min(len(acc) - 2, max(0, bisect.bisect_right(acc, s) - 1))
    u = (s - acc[i]) / (acc[i + 1] - acc[i]) if acc[i + 1] > acc[i] else 0
    a, b = samples[i], samples[i + 1]
    return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)


def circle_pts(cx, cy, r, n=96, rev=False):
    pts = [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]
    return pts[::-1] if rev else pts


def bridge(outer, inner):
    """One polygon: outer ring, a zero-width bridge to the inner ring (reversed) and back, so even-odd fill cancels the bridge."""
    return outer + [outer[0]] + inner + [inner[0], outer[0]]


def tube_mask(spine, radii, W, H, discs=True, n=8):
    import numpy as np
    from PIL import Image, ImageDraw
    im = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(im)
    nrm = []
    for i in range(len(spine)):  # one normal per spine point (central difference), shared by both neighbouring quads
        (xa, ya), (xb, yb) = spine[max(0, i - 1)], spine[min(len(spine) - 1, i + 1)]
        L = math.hypot(xb - xa, yb - ya) or 1
        nrm.append((-(yb - ya) / L, (xb - xa) / L))
    for i in range(len(spine) - 1):
        (x0, y0), (x1, y1) = spine[i], spine[i + 1]
        (n0x, n0y), (n1x, n1y) = nrm[i], nrm[i + 1]
        r0, r1 = radii[i], radii[i + 1]
        d.polygon([(x0 + n0x * r0, y0 + n0y * r0), (x1 + n1x * r1, y1 + n1y * r1), (x1 - n1x * r1, y1 - n1y * r1), (x0 - n0x * r0, y0 - n0y * r0)], fill=255)
    if discs:
        for i in list(range(0, len(spine), max(1, n // 2))) + [len(spine) - 1]:
            r = radii[i]
            if r > 0.6:
                x, y = spine[i]
                d.ellipse([x - r, y - r, x + r, y + r], fill=255)
    return np.asarray(im) > 127


def ridge(seed, base, amp, rough=0.55, rounds=7, width=1.0, peaks=()):
    import numpy as np
    rng = np.random.default_rng(seed)
    ys = [base, base]
    offsets = []
    a = amp
    for _ in range(rounds):
        new, offs = [ys[0]], []
        for y0, y1 in zip(ys, ys[1:]):
            o = a * (rng.random() * 2 - 1)
            new += [(y0 + y1) / 2 + o, y1]
            offs.append(o)
        ys = new
        offsets.append(offs)
        a *= rough
    xs = [width * i / (len(ys) - 1) for i in range(len(ys))]
    ys = [y + sum(h * math.exp(-((x - px) / pw) ** 2) for px, h, pw in peaks) for x, y in zip(xs, ys)]
    return xs, ys, offsets


def quad_curve(p0, c, p1, n=40):
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * c[0] + t * t * p1[0], (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * c[1] + t * t * p1[1])
            for t in [k / n for k in range(n + 1)]]


def square_pts(cx, cy, half, rot):
    return [(cx + half * math.sqrt(2) * math.cos(rot + math.pi / 4 + k * math.pi / 2), cy + half * math.sqrt(2) * math.sin(rot + math.pi / 4 + k * math.pi / 2)) for k in range(4)]


def star8(cx, cy, R, r, rot=0.0):
    return [(cx + (R if k % 2 == 0 else r) * math.cos(rot - math.pi / 2 + k * math.pi / 8), cy + (R if k % 2 == 0 else r) * math.sin(rot - math.pi / 2 + k * math.pi / 8)) for k in range(16)]


def draw_partial(d, pts, frac, col, width, closed=True):
    P = pts + [pts[0]] if closed else pts
    segs = list(zip(P, P[1:]))
    L = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in segs)
    left = L * frac
    for a, b in segs:
        s = math.hypot(b[0] - a[0], b[1] - a[1])
        if left <= 0:
            break
        u = min(1, left / s)
        d.line([a, (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)], fill=col, width=width)
        left -= s


def mulberry32(seed):
    a = seed & 0xFFFFFFFF

    def r():
        nonlocal a
        a = (a + 0x6D2B79F5) & 0xFFFFFFFF
        t = a
        t = ((t ^ (t >> 15)) * (t | 1)) & 0xFFFFFFFF
        t ^= (t + (((t ^ (t >> 7)) * (t | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296
    return r


def power_out_c(p):
    return 1 - (1 - p) ** 3


def _fill_poly(pts, W, H, ss=1):
    import numpy as np
    from PIL import Image, ImageDraw
    im = Image.new("L", (W, H), 0)
    ImageDraw.Draw(im).polygon([(float(x), float(y)) for x, y in pts], fill=255)
    return np.asarray(im, dtype=float)


def _crossings(a, b):
    def inter(p1, p2, p3, p4):
        d = lambda a, b, c: (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        return (d(p1, p2, p3) * d(p1, p2, p4) < 0) and (d(p3, p4, p1) * d(p3, p4, p2) < 0)
    n = len(a)
    return int(sum(bool(inter(a[i], b[i], a[j], b[j])) for i in range(n) for j in range(i + 1, n)))


def _poly_pts(s):
    return [tuple(map(float, q.split(","))) for q in s.split()]


def metaball_field(W, H, centres, r):
    import numpy as np
    y, x = np.mgrid[0:H, 0:W].astype(float)
    f = np.zeros((H, W))
    for cx, cy in centres:
        f += r * r / ((x - cx) ** 2 + (y - cy) ** 2 + 1e-6)
    return f
