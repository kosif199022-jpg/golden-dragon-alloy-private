"""Helpers of runners/fam_hand_drawn_draw_on.py used by data cards, copied verbatim (the extractor binds a card to them only when
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


def svg_paths(d, arc_step=6.0, n=16):
    """Pure-Python SVG path sampler (M/L/H/V/C/S/Q/T/A/Z, curves sampled, closed paths return to start)."""
    import re
    toks = re.findall(r"[MLHVCSQTAZmlhvcsqtaz]|-?(?:\d+\.?\d*|\.\d+)(?:e-?\d+)?", d)
    paths, cur, start, pos = [], [], (0.0, 0.0), (0.0, 0.0)
    i, cmd, prev_c, prev_q = 0, None, None, None

    def num():
        nonlocal i
        v = float(toks[i])
        i += 1
        return v
    while i < len(toks):
        if re.match(r"[A-Za-z]", toks[i]):
            cmd = toks[i]
            i += 1
        rel = cmd.islower()
        C = cmd.upper()
        ox, oy = pos if rel else (0.0, 0.0)
        if C == "Z":
            cur.append(start)
            paths.append(cur)
            cur, pos = [], start
            prev_c = prev_q = None
            continue
        if C == "M":
            if cur:
                paths.append(cur)
            pos = (ox + num(), oy + num())
            start, cur = pos, [pos]
            cmd = "l" if rel else "L"
            continue
        if C in "LHV":
            if C == "L":
                pos = (ox + num(), oy + num())
            elif C == "H":
                pos = ((pos[0] if rel else 0) + num(), pos[1])
            else:
                pos = (pos[0], (pos[1] if rel else 0) + num())
            cur.append(pos)
            prev_c = prev_q = None
        elif C in "CS":
            if C == "C":
                c1 = (ox + num(), oy + num())
            else:
                c1 = (2 * pos[0] - prev_c[0], 2 * pos[1] - prev_c[1]) if prev_c else pos
            c2 = (ox + num(), oy + num())
            p1 = (ox + num(), oy + num())
            p0 = pos
            for k in range(1, n + 1):
                t = k / n
                cur.append(tuple((1 - t) ** 3 * a + 3 * (1 - t) ** 2 * t * b + 3 * (1 - t) * t * t * c + t ** 3 * e for a, b, c, e in zip(p0, c1, c2, p1)))
            pos, prev_c, prev_q = p1, c2, None
        elif C in "QT":
            if C == "Q":
                q = (ox + num(), oy + num())
            else:
                q = (2 * pos[0] - prev_q[0], 2 * pos[1] - prev_q[1]) if prev_q else pos
            p1 = (ox + num(), oy + num())
            p0 = pos
            for k in range(1, n + 1):
                t = k / n
                cur.append(tuple((1 - t) ** 2 * a + 2 * (1 - t) * t * b + t * t * c for a, b, c in zip(p0, q, p1)))
            pos, prev_q, prev_c = p1, q, None
        elif C == "A":
            rx, ry, phi, fa, fs = abs(num()), abs(num()), math.radians(num()), int(num()), int(num())
            p1 = (ox + num(), oy + num())
            x1, y1 = pos
            x2, y2 = p1
            cp, sp = math.cos(phi), math.sin(phi)
            dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
            x1p, y1p = cp * dx + sp * dy, -sp * dx + cp * dy
            lam = x1p ** 2 / rx ** 2 + y1p ** 2 / ry ** 2
            if lam > 1:
                rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
            num_ = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
            co = math.sqrt(max(0, num_) / (rx * rx * y1p * y1p + ry * ry * x1p * x1p)) * (-1 if fa == fs else 1)
            cxp, cyp = co * rx * y1p / ry, -co * ry * x1p / rx
            cx, cy = cp * cxp - sp * cyp + (x1 + x2) / 2, sp * cxp + cp * cyp + (y1 + y2) / 2
            ang = lambda ux, uy, vx, vy: math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
            t1 = ang(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
            dt = ang((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
            if not fs and dt > 0:
                dt -= 2 * math.pi
            elif fs and dt < 0:
                dt += 2 * math.pi
            m = max(12, int(math.ceil(abs(math.degrees(dt)) / arc_step)))
            for k in range(1, m + 1):
                a = t1 + dt * k / m
                cur.append((cx + rx * math.cos(a) * cp - ry * math.sin(a) * sp, cy + rx * math.cos(a) * sp + ry * math.sin(a) * cp))
            cur[-1] = p1
            pos, prev_c, prev_q = p1, None, None
    if cur:
        paths.append(cur)
    return paths


def fit_tf(paths, box, margin=0.08):
    xs = [x for p in paths for x, _ in p]
    ys = [y for p in paths for _, y in p]
    bw, bh = box
    s = min(bw * (1 - 2 * margin) / (max(xs) - min(xs) or 1), bh * (1 - 2 * margin) / (max(ys) - min(ys) or 1))
    ox = (bw - s * (max(xs) - min(xs))) / 2 - s * min(xs)
    oy = (bh - s * (max(ys) - min(ys))) / 2 - s * min(ys)
    return lambda p: (p[0] * s + ox, p[1] * s + oy)


def plen(pts):
    return sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def resample(pts, n):
    """n+1 points evenly spaced by arc length."""
    cum = [0.0]
    for i in range(len(pts) - 1):
        cum.append(cum[-1] + math.dist(pts[i], pts[i + 1]))
    L, out, j = cum[-1], [], 0
    for k in range(n + 1):
        s = L * k / n
        while j < len(pts) - 2 and cum[j + 1] < s:
            j += 1
        seg = cum[j + 1] - cum[j] or 1
        u = (s - cum[j]) / seg
        out.append((pts[j][0] + (pts[j + 1][0] - pts[j][0]) * u, pts[j][1] + (pts[j + 1][1] - pts[j][1]) * u))
    return out


def partial(pts, frac, n=400):
    rs = resample(pts, n)
    k = max(0, min(n, int(round(frac * n))))
    return rs[: k + 1] if k else []


def dash_runs(pts, dash, gap, offset, n=1000):
    """Visible pieces of a pathLength=1 dash pattern (SVG semantics: dashoffset shifts the pattern start)."""
    rs = resample(pts, n)
    per = dash + gap
    vis = [((k / n + offset) % per) < dash for k in range(n + 1)]
    runs, cur = [], []
    for p, v in zip(rs, vis):
        if v:
            cur.append(p)
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    return runs, vis


def sample_colours(img, pts):
    import numpy as np
    a = np.asarray(img)
    H, W = a.shape[:2]
    return [tuple(int(v) for v in a[min(H - 1, max(0, int(round(y)))), min(W - 1, max(0, int(round(x))))][:3]) for x, y in pts]


def rough_line(p0, p1, roughness, bowing, rng, passes=2):
    """Rough.js-style sketch line: two passes, endpoint jitter and a bowed midpoint, both scaled by roughness."""
    L = math.dist(p0, p1)
    out = []
    off = min(L * 0.1, 2.0) * roughness
    nx, ny = (-(p1[1] - p0[1]) / (L or 1), (p1[0] - p0[0]) / (L or 1))
    for _ in range(passes):
        j = lambda: rng.uniform(-off, off) if roughness else 0.0
        bow = bowing * roughness * L * 0.01 * rng.uniform(-1, 1) if roughness else 0.0
        a = (p0[0] + j(), p0[1] + j())
        b = (p1[0] + j(), p1[1] + j())
        m = ((a[0] + b[0]) / 2 + nx * bow * 4 + j(), (a[1] + b[1]) / 2 + ny * bow * 4 + j())
        out.append([((1 - t) ** 2 * a[0] + 2 * (1 - t) * t * m[0] + t * t * b[0], (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * m[1] + t * t * b[1])
                    for t in [i / 16 for i in range(17)]])
    return out


def hachure(poly, angle_deg, gap):
    """Parallel fill lines at angle_deg, gap px apart, clipped to the polygon (shapely)."""
    from shapely.geometry import LineString, Polygon
    P = Polygon(poly)
    cx, cy = P.centroid.x, P.centroid.y
    R = max(math.dist((cx, cy), p) for p in poly) + 2
    a = math.radians(angle_deg)
    d, nrm = (math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))
    lines = []
    k = -R
    while k <= R:
        o = (cx + nrm[0] * k, cy + nrm[1] * k)
        seg = LineString([(o[0] - d[0] * R, o[1] - d[1] * R), (o[0] + d[0] * R, o[1] + d[1] * R)]).intersection(P)
        for g in getattr(seg, "geoms", [seg]):
            if not g.is_empty and g.length > 0.5:
                lines.append(list(g.coords))
        k += gap
    return lines


def rough_rect(x, y, w, h, roughness=1.0, bowing=1.0, fill_style="hachure", gap=6, angle=-41, seed=1):
    import numpy as np
    rng = np.random.default_rng(seed)
    c = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    strokes = [s for i in range(4) for s in rough_line(c[i], c[(i + 1) % 4], roughness, bowing, rng)]
    fills = []
    if fill_style in ("hachure", "cross-hatch"):
        fills = hachure(c, angle, gap)
        if fill_style == "cross-hatch":
            fills += hachure(c, angle + 90, gap)
    return strokes, fills


def draw_lines(d, lines, col, width, frac=1.0):
    total = sum(plen(l) for l in lines) or 1
    budget = total * frac
    for l in lines:
        L = plen(l)
        if budget <= 0:
            break
        seg = l if budget >= L else partial(l, budget / L)
        if len(seg) > 1:
            d.line(seg, fill=col, width=max(1, int(round(width))), joint="curve")
        budget -= L


def hexrgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def smoothstep(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def catmull_like(pts, n=12):
    out = []
    P = [pts[0]] + pts + [pts[-1]]
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(n):
            t = k / n
            out.append(tuple(0.5 * ((2 * b) + (-a + c) * t + (2 * a - 5 * b + 4 * c - e) * t * t + (-a + 3 * b - 3 * c + e) * t ** 3)
                             for a, b, c, e in zip(p0, p1, p2, p3)))
    out.append(pts[-1])
    return out


def interpolate_clamp(f, f0, f1):
    return max(0.0, min(1.0, (f - f0) / (f1 - f0)))


def annotation_lines(kind, box, rng):
    x0, y0, x1, y1 = box
    cx, cy, w, h = (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0
    if kind == "underline":
        return rough_line((x0, y1 + 4), (x1, y1 + 4), 1.0, 1.0, rng)
    if kind == "strike":
        return rough_line((x0, cy), (x1, cy), 1.0, 1.0, rng)
    if kind == "crossed-off":
        return rough_line((x0, y0), (x1, y1), 1.0, 1.0, rng) + rough_line((x0, y1), (x1, y0), 1.0, 1.0, rng)
    if kind == "box":
        c = [(x0 - 4, y0 - 4), (x1 + 4, y0 - 4), (x1 + 4, y1 + 4), (x0 - 4, y1 + 4)]
        return [s for i in range(4) for s in rough_line(c[i], c[(i + 1) % 4], 1.0, 1.0, rng)]
    if kind == "bracket":
        return rough_line((x1 + 6, y0), (x1 + 12, y0), 1, 1, rng) + rough_line((x1 + 12, y0), (x1 + 12, y1), 1, 1, rng) + rough_line((x1 + 12, y1), (x1 + 6, y1), 1, 1, rng)
    if kind == "circle":
        j = [rng.uniform(-0.04, 0.04) for _ in range(9)]
        pts = [(cx + (w / 2 + 10) * (1 + j[k % 9]) * math.cos(2 * math.pi * k / 48 * 1.08), cy + (h / 2 + 8) * (1 + j[k % 9]) * math.sin(2 * math.pi * k / 48 * 1.08)) for k in range(49)]
        return [pts]
    if kind == "highlight":
        return [[(x0, cy + rng.uniform(-1, 1)), (x1, cy + rng.uniform(-1, 1))]]
    raise ValueError(kind)


def palette_count(a, bg, tol=24, min_share=0.002):
    import numpy as np
    px = a.reshape(-1, 3).astype(int)
    px = px[np.abs(px - np.array(bg)).sum(1) > tol]
    if not len(px):
        return 0
    q = (px // 32) * 32
    vals, cnt = np.unique(q, axis=0, return_counts=True)
    return int((cnt > min_share * a.shape[0] * a.shape[1]).sum())


def onset_times(samples, rate, thr=0.2, gap=0.15):
    import numpy as np
    env = np.abs(np.asarray(samples, dtype=float))
    hop = int(rate * 0.005)
    e = np.array([env[i:i + hop].max() for i in range(0, len(env) - hop, hop)])
    out, last = [], -1.0
    for i in range(1, len(e)):
        t = i * hop / rate
        if e[i] > thr and e[i - 1] <= thr and t - last > gap:
            out.append(t)
            last = t
    return out


def read_nib(a):
    import numpy as np
    m = (a[:, :, 0] > 180) & (a[:, :, 1] < 80)
    return float(np.nonzero(m)[1].mean())
