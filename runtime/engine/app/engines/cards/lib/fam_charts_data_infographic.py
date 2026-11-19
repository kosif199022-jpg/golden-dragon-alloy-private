"""Helpers of runners/fam_charts_data_infographic.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from pathlib import Path
from .core import fx
import json
import math
import subprocess


def _np():
    import numpy as np
    return np


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def canvas(w, h, bg="#ffffff"):
    np = _np()
    a = np.zeros((h, w, 3), dtype=float)
    a[:, :] = rgb(bg) if isinstance(bg, str) else bg
    return a


def save_png(arr, path):
    from PIL import Image
    Image.fromarray(_np().clip(arr, 0, 255).round().astype("uint8")).save(path)
    return Path(path)


def load_png(path):
    from PIL import Image
    return _np().asarray(Image.open(path).convert("RGB")).astype(float)


def write_video(path, frames, fps=30):
    """Encode numpy frames losslessly (libx264rgb qp 0) so pixel measurements read back exactly."""
    np = _np()
    frames = list(frames)
    h, w = frames[0].shape[:2]
    p = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", "%dx%d" % (w, h), "-r", str(fps), "-i", "-", "-c:v", "libx264rgb", "-qp", "0",
                          "-preset", "ultrafast", str(path)], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    for f in frames:
        p.stdin.write(np.clip(f, 0, 255).round().astype("uint8").tobytes())
    p.stdin.close()
    if p.wait():
        raise RuntimeError("ffmpeg encode failed: %s" % p.stderr.read().decode(errors="replace")[-300:])
    return Path(path)


def read_video(path):
    np = _np()
    pr = fx.probe(path)
    st = [s for s in pr["streams"] if s.get("codec_type") == "video"][0]
    w, h = int(st["width"]), int(st["height"])
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, timeout=120, stdin=subprocess.DEVNULL).stdout
    return np.frombuffer(out, dtype=np.uint8).reshape(-1, h, w, 3).astype(float)


def pil_mask(w, h, fn):
    from PIL import Image, ImageDraw
    im = Image.new("L", (w, h), 0)
    fn(ImageDraw.Draw(im))
    return _np().asarray(im) > 127


def paint(arr, mask, color, alpha=1.0):
    c = _np().array(rgb(color) if isinstance(color, str) else color, dtype=float)
    arr[mask] = arr[mask] * (1 - alpha) + c * alpha
    return arr


def rect(arr, x0, y0, x1, y1, color, alpha=1.0):
    h, w = arr.shape[:2]
    x0, x1 = max(0, int(round(x0))), min(w, int(round(x1)))
    y0, y1 = max(0, int(round(y0))), min(h, int(round(y1)))
    if x1 > x0 and y1 > y0:
        c = _np().array(rgb(color) if isinstance(color, str) else color, dtype=float)
        arr[y0:y1, x0:x1] = arr[y0:y1, x0:x1] * (1 - alpha) + c * alpha
    return arr


def near(arr, color, tol=12.0):
    np = _np()
    c = np.array(rgb(color) if isinstance(color, str) else color, dtype=float)
    return np.abs(arr - c).max(axis=-1) <= tol


def angle_grid(h, w, cx, cy):
    """Per-pixel radius and clockwise angle from 12 o'clock, in degrees 0..360."""
    np = _np()
    ys, xs = np.mgrid[0:h, 0:w]
    dx, dy = xs + 0.5 - cx, ys + 0.5 - cy
    r = np.hypot(dx, dy)
    ang = (np.degrees(np.arctan2(dx, -dy)) + 360.0) % 360.0
    return r, ang


def ring_mask(h, w, cx, cy, r0, r1, a0=0.0, a1=360.0):
    r, ang = angle_grid(h, w, cx, cy)
    m = (r >= r0) & (r < r1)
    if a1 - a0 < 360:
        a0m, a1m = a0 % 360, a1 % 360
        if a1 - a0 <= 0:
            return m & False
        m &= ((ang >= a0m) & (ang < a1m)) if a0m <= a1m else ((ang >= a0m) | (ang < a1m))
    return m


def arc_fraction(arr, cx, cy, r0, r1, color, tol=12.0):
    """Measured share of the annulus painted in colour (0..1)."""
    h, w = arr.shape[:2]
    ann = ring_mask(h, w, cx, cy, r0 + 1, r1 - 1)
    return float((near(arr, color, tol) & ann).sum()) / float(ann.sum())


EASE = {
    "linear": lambda t: t,
    "power2.inOut": lambda t: 2 * t * t if t < .5 else 1 - (-2 * t + 2) ** 2 / 2,
    "power2.out": lambda t: 1 - (1 - t) ** 2,
    "power2.in": lambda t: t * t,
    "power3.out": lambda t: 1 - (1 - t) ** 3,
    "easeOutCubic": lambda t: 1 - (1 - t) ** 3,
    "easeInOutCubic": lambda t: 4 * t ** 3 if t < .5 else 1 - (-2 * t + 2) ** 3 / 2,
    "easeOutExpo": lambda t: 1.0 if t >= 1 else 1 - 2 ** (-10 * t),
    "easeInExpo": lambda t: 0.0 if t <= 0 else 2 ** (10 * t - 10),
    "easeInOutSine": lambda t: -(math.cos(math.pi * t) - 1) / 2,
    "easeOut": lambda t: 1 - (1 - t) ** 2,
    "easeInOut": lambda t: -(math.cos(math.pi * t) - 1) / 2,
    "back.out": lambda t: 1 + 2.70158 * (t - 1) ** 3 + 1.70158 * (t - 1) ** 2,
}


def ease(name, t):
    return EASE[name](min(1.0, max(0.0, t)))


def prog(t, start, dur):
    return min(1.0, max(0.0, (t - start) / dur)) if dur > 0 else float(t >= start)


_DIG = {"0": "abcdef", "1": "bc", "2": "abdeg", "3": "abcdg", "4": "bcfg", "5": "acdfg", "6": "acdefg", "7": "abc",
        "8": "abcdefg", "9": "abcdfg", "-": "g", "+": "gv", " ": ""}


_INV = {frozenset(v): k for k, v in _DIG.items()}


def _segs(H):
    W = int(round(H * 0.55))
    T = max(2, int(round(H * 0.13)))
    m = H // 2
    lo, hi = m - T // 2, m + (T + 1) // 2
    return W, T, {"a": (T, 0, W - T, T), "b": (W - T, T, W, lo), "c": (W - T, hi, W, H - T), "d": (T, H - T, W - T, H),
                  "e": (0, hi, T, H - T), "f": (0, T, T, lo), "g": (T, lo, W - T, hi),
                  "v": (W // 2 - T // 2, H // 4, W // 2 - T // 2 + T, H - H // 4)}


def seg_layout(pattern, H, x, y):
    W, T, _ = _segs(H)
    gap = max(2, T)
    cells, cx = [], x
    for ch in pattern:
        if ch in ",.":
            cells.append((ch, cx, y))
            cx += T + gap
        else:
            cells.append(("d", cx, y))
            cx += W + gap
    return cells, cx - gap - x


def seg_width(pattern, H):
    return seg_layout(pattern, H, 0, 0)[1]


def draw_seg(arr, text, pattern, H, x, y, color, alpha=1.0):
    if len(text) != len(pattern):
        raise ValueError("text %r does not fit pattern %r" % (text, pattern))
    W, T, S = _segs(H)
    cells, _ = seg_layout(pattern, H, x, y)
    for (kind, cx, cy), ch in zip(cells, text):
        if kind == "d":
            for s in _DIG[ch]:
                x0, y0, x1, y1 = S[s]
                rect(arr, cx + x0, cy + y0, cx + x1, cy + y1, color, alpha)
        elif ch in ",.":
            rect(arr, cx, cy + H - T, cx + T, cy + H, color, alpha)
    return arr


def read_seg(arr, pattern, H, x, y, bg, thr=None, fg=None):
    """Decode the glyphs at a known layout by sampling each segment centre (on = far from background;
    with bg=None, on = within thr of the foreground colour, for text over footage)."""
    np = _np()
    W, T, S = _segs(H)
    cells, _ = seg_layout(pattern, H, x, y)
    fgc = None if fg is None else np.array(rgb(fg) if isinstance(fg, str) else fg, dtype=float)
    bgc = None if bg is None else np.array(rgb(bg) if isinstance(bg, str) else bg, dtype=float)
    if thr is None:
        thr = 0.5 * float(np.abs(fgc - bgc).max()) if bgc is not None else 40.0
    hh, ww = arr.shape[:2]

    def on(px, py):
        px, py = int(px), int(py)
        if not (0 <= px < ww and 0 <= py < hh):
            return False
        if bgc is None:
            return float(np.abs(arr[py, px] - fgc).max()) <= thr
        return float(np.abs(arr[py, px] - bgc).max()) > thr
    out = ""
    for kind, cx, cy in cells:
        if kind == "d":
            lit = set()
            for s, (x0, y0, x1, y1) in S.items():
                px, py = cx + (x0 + x1) / 2.0, cy + (y0 + y1) / 2.0
                if s == "v":
                    py = cy + H * 0.33
                if on(px, py):
                    lit.add(s)
            out += _INV.get(frozenset(lit), "?")
        else:
            out += kind if on(cx + T / 2.0, cy + H - T / 2.0) else " "
    return out


def _nz(v):
    return -1e9 if v is None else v


def seg_value(s):
    t = s.replace(",", "").replace(" ", "")
    if not t or "?" in t:
        return None
    try:
        return float(t)
    except ValueError:
        return None


def fmt_int(v, pattern, sep=False):
    s = format(int(round(v)), ",d") if sep else str(int(round(v)))
    return s.rjust(len(pattern))


def nice_num(x):
    """Smallest nice step >= x from {1, 2, 2.5, 5, 10} x 10^n."""
    if x <= 0:
        return 1.0
    e = math.floor(math.log10(x))
    f = x / 10 ** e
    return next(s for s in (1, 2, 2.5, 5, 10) if f <= s + 1e-9) * 10 ** e


def nice_ticks(vmax, n=4):
    step = nice_num(vmax / n)
    top = math.ceil(vmax / step - 1e-9) * step
    k = int(round(top / step))
    return [round(i * step, 10) for i in range(k + 1)], step


def is_nice(v):
    if v == 0:
        return True
    e = math.floor(math.log10(abs(v)))
    f = round(abs(v) / 10 ** e, 6)
    return f in (1.0, 2.0, 2.5, 5.0, 10.0)


def wjson(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return Path(path)


def col_runs(mask_1d):
    """Lengths of consecutive True runs in a 1-D boolean array, with their starts."""
    runs, start = [], None
    for i, v in enumerate(list(mask_1d) + [False]):
        if v and start is None:
            start = i
        elif not v and start is not None:
            runs.append((start, i - start))
            start = None
    return runs


def clusters(idx, gap=1):
    """Group sorted integer positions into clusters; returns their centres."""
    idx = sorted(int(i) for i in idx)
    out, cur = [], []
    for i in idx:
        if cur and i - cur[-1] > gap:
            out.append(sum(cur) / len(cur))
            cur = []
        cur.append(i)
    if cur:
        out.append(sum(cur) / len(cur))
    return out


def srgb_to_lab(c):
    def lin(u):
        u /= 255.0
        return u / 12.92 if u <= 0.04045 else ((u + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(float(v)) for v in c)
    X = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    Y = (0.2126 * r + 0.7152 * g + 0.0722 * b)
    Z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116
    return 116 * f(Y) - 16, 500 * (f(X) - f(Y)), 200 * (f(Y) - f(Z))


def de2000(c1, c2):
    L1, a1, b1 = srgb_to_lab(c1)
    L2, a2, b2 = srgb_to_lab(c2)
    C1, C2 = math.hypot(a1, b1), math.hypot(a2, b2)
    Cb = (C1 + C2) / 2
    G = 0.5 * (1 - math.sqrt(Cb ** 7 / (Cb ** 7 + 25 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360
    h2p = math.degrees(math.atan2(b2, a2p)) % 360
    dLp, dCp = L2 - L1, C2p - C1p
    dh = h2p - h1p
    if C1p * C2p == 0:
        dh = 0
    elif dh > 180:
        dh -= 360
    elif dh < -180:
        dh += 360
    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dh / 2))
    Lbp, Cbp = (L1 + L2) / 2, (C1p + C2p) / 2
    if C1p * C2p == 0:
        hbp = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hbp = (h1p + h2p) / 2
    else:
        hbp = (h1p + h2p + 360) / 2 if h1p + h2p < 360 else (h1p + h2p - 360) / 2
    T = (1 - 0.17 * math.cos(math.radians(hbp - 30)) + 0.24 * math.cos(math.radians(2 * hbp))
         + 0.32 * math.cos(math.radians(3 * hbp + 6)) - 0.20 * math.cos(math.radians(4 * hbp - 63)))
    dth = 30 * math.exp(-((hbp - 275) / 25) ** 2)
    Rc = 2 * math.sqrt(Cbp ** 7 / (Cbp ** 7 + 25 ** 7))
    Sl = 1 + 0.015 * (Lbp - 50) ** 2 / math.sqrt(20 + (Lbp - 50) ** 2)
    Sc, Sh = 1 + 0.045 * Cbp, 1 + 0.015 * Cbp * T
    Rt = -math.sin(math.radians(2 * dth)) * Rc
    return math.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh))


_CVD = {"protan": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)),
        "deutan": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881)),
        "tritan": ((1.255528, -0.076749, -0.178779), (-0.078411, 0.930809, 0.147602), (0.004733, 0.691367, 0.303900))}


def simulate_cvd(c, kind):
    def lin(u):
        u /= 255.0
        return u / 12.92 if u <= 0.04045 else ((u + 0.055) / 1.055) ** 2.4

    def enc(u):
        u = min(1.0, max(0.0, u))
        return 255 * (12.92 * u if u <= 0.0031308 else 1.055 * u ** (1 / 2.4) - 0.055)
    L = [lin(float(v)) for v in c]
    M = _CVD[kind]
    return tuple(enc(sum(M[i][j] * L[j] for j in range(3))) for i in range(3))


def rel_lum(c):
    def lin(u):
        u /= 255.0
        return u / 12.92 if u <= 0.03928 else ((u + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(float(v)) for v in (rgb(c) if isinstance(c, str) else c))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(c1, c2):
    a, b = sorted((rel_lum(c1), rel_lum(c2)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def bar_heights(arr, base_y, xs, bg, thr=40.0):
    """Measure the painted height (px above base_y) in each column x of xs."""
    np = _np()
    bgc = np.array(rgb(bg), dtype=float)
    out = []
    for x in xs:
        col = np.abs(arr[:base_y, int(x)] - bgc).max(axis=-1) > thr
        run = 0
        for y in range(base_y - 1, -1, -1):
            if col[y]:
                run += 1
            else:
                break
        out.append(run)
    return out


def bar_lengths_h(arr, x0, ys, bg, thr=40.0):
    """Horizontal bars: painted run length to the right of x0 on each row y."""
    np = _np()
    bgc = np.array(rgb(bg), dtype=float)
    out = []
    for y in ys:
        row = np.abs(arr[int(y), x0:] - bgc).max(axis=-1) > thr
        run = 0
        for v in row:
            if v:
                run += 1
            else:
                break
        out.append(run)
    return out


def max_ratio_err(measured, values):
    """Largest relative error between measured px and the values scaled by the largest one."""
    k = max(measured) / float(max(values))
    return max(abs(m - v * k) / max(1.0, v * k) for m, v in zip(measured, values))


def line_mask(h, w, pts, width=2):
    return pil_mask(w, h, lambda d: d.line([tuple(map(float, p)) for p in pts], fill=255, width=width, joint="curve"))


def _infer_relationship(ds):
    if "edges" in ds:
        return "flow"
    if "goal" in ds:
        return "target"
    if "pairs" in ds:
        return "correlation"
    if "sample" in ds:
        return "distribution"
    if "periods" in ds and len(ds["periods"]) == 2:
        return "change_two_periods"
    if "stack_over_time" in ds:
        return "composition_time"
    if "parts" in ds and abs(sum(ds["parts"].values()) - ds.get("total", -1)) <= 0.01 * ds.get("total", 1):
        return "part_to_whole"
    if "time" in ds:
        return "trend"
    if "categories" in ds:
        return "ranking" if ds.get("question") == "rank" else "comparison"
    return "unknown"


def _pick_chart(ds, video=True):
    rel = _infer_relationship(ds)
    if rel == "trend":
        return "area" if ds.get("cumulative") else "line"
    if rel == "comparison":
        return "hbar" if len(ds["categories"]) > 7 else "vbar"
    if rel == "part_to_whole":
        return "pie" if len(ds["parts"]) <= (5 if video else 6) else "stacked_bar"
    return {"ranking": "sorted_hbar", "change_two_periods": "slope", "composition_time": "stacked_area",
            "distribution": "histogram", "correlation": "scatter", "flow": "sankey", "target": "bullet"}.get(rel, "table")


_BLACKLIST_RULES = [
    ("3d", lambda s: s.get("3d"), "no decorative 3D"),
    ("pie_slices", lambda s: s["type"] in ("pie", "donut") and s.get("slices", 0) > (3 if s.get("medium") == "video" else 5),
     "pie/donut beyond 3 (video) / 5 slices -> bars"),
    ("animated_pie", lambda s: s["type"] in ("pie", "donut") and s.get("animated"), "no animated pie"),
    ("dual_axis", lambda s: s.get("dual_axis") and not s.get("both_labelled"), "dual axis must be labelled; prefer panels"),
    ("stack_segments", lambda s: s["type"] == "stacked_bar" and s.get("segments", 0) > 4, "many-segment stacks -> small multiples"),
    ("dashboard", lambda s: s["type"] == "dashboard" and s.get("panels", 0) >= 6, "no 6-panel web dashboards"),
    ("baseline", lambda s: s["type"] == "bar" and s.get("baseline", 0) != 0, "bars start at 0"),
]


def ink_bbox(arr, bg, thr=40.0, region=None):
    np = _np()
    x0, y0, x1, y1 = region or (0, 0, arr.shape[1], arr.shape[0])
    sub = arr[y0:y1, x0:x1]
    m = np.abs(sub - np.array(rgb(bg) if isinstance(bg, str) else bg, dtype=float)).max(axis=-1) > thr
    if not m.any():
        return None
    ys, xs = np.nonzero(m)
    return (x0 + int(xs.min()), y0 + int(ys.min()), x0 + int(xs.max()) + 1, y0 + int(ys.max()) + 1)


def sharpness(arr, region):
    """Largest luminance step between neighbouring pixels in a region (blur lowers it)."""
    np = _np()
    x0, y0, x1, y1 = region
    g = arr[y0:y1, x0:x1].mean(axis=-1)
    return float(max(np.abs(np.diff(g, axis=0)).max(), np.abs(np.diff(g, axis=1)).max()))


def vsharp(arr, region):
    np = _np()
    x0, y0, x1, y1 = region
    return float(np.abs(np.diff(arr[y0:y1, x0:x1].mean(axis=-1), axis=0)).max())


def gold_halo(f):
    """Pixels tinted gold (R > G > B, warm) that are not the white glyph itself."""
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    return int(((r > b + 25) & (g > b + 10) & (r > 50) & ~((r > 235) & (g > 235) & (b > 235))).sum())


def blur(arr, radius):
    from PIL import Image, ImageFilter
    if radius <= 0:
        return arr
    im = Image.fromarray(_np().clip(arr, 0, 255).round().astype("uint8"))
    return _np().asarray(im.filter(ImageFilter.GaussianBlur(radius))).astype(float)


def vblur(arr, k):
    """Vertical box blur of k px (motion blur along a rolling digit strip)."""
    np = _np()
    k = int(k)
    if k <= 1:
        return arr
    pad = np.concatenate([np.repeat(arr[:1], k, 0), arr, np.repeat(arr[-1:], k, 0)], 0)
    c = np.cumsum(pad, axis=0)
    out = (c[k:] - c[:-k]) / k
    off = (out.shape[0] - arr.shape[0]) // 2
    return out[off:off + arr.shape[0]]


def scaled_layer(layer, s, cx, cy, out_shape, bg):
    """Scale a layer (numpy RGB over bg) by s about (cx, cy) into a canvas of out_shape."""
    from PIL import Image
    np = _np()
    h, w = layer.shape[:2]
    nw, nh = max(1, int(round(w * s))), max(1, int(round(h * s)))
    im = Image.fromarray(np.clip(layer, 0, 255).round().astype("uint8")).resize((nw, nh), Image.BILINEAR)
    a = canvas(out_shape[1], out_shape[0], bg)
    x, y = int(round(cx - nw / 2)), int(round(cy - nh / 2))
    sub = np.asarray(im).astype(float)
    ys0, xs0 = max(0, -y), max(0, -x)
    ys1, xs1 = min(nh, out_shape[0] - y), min(nw, out_shape[1] - x)
    a[y + ys0:y + ys1, x + xs0:x + xs1] = sub[ys0:ys1, xs0:xs1]
    return a


def lerp_c(c0, c1, t):
    a, b = (rgb(c0) if isinstance(c0, str) else c0), (rgb(c1) if isinstance(c1, str) else c1)
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def gradient_fill(mask, box, stops, angle_deg):
    """CSS linear-gradient(angle, stops...) over box, painted where mask is set; returns the colour field."""
    np = _np()
    x0, y0, x1, y1 = box
    h, w = mask.shape
    ys, xs = np.mgrid[0:h, 0:w]
    a = math.radians(angle_deg)
    dx, dy = math.sin(a), -math.cos(a)
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    L = abs((x1 - x0) * dx) + abs((y1 - y0) * dy)
    t = np.clip(((xs + 0.5 - cx) * dx + (ys + 0.5 - cy) * dy) / L + 0.5, 0, 1)
    pos = [p for p, _ in stops]
    cols = [np.array(rgb(c), float) for _, c in stops]
    out = np.zeros((h, w, 3))
    for ch in range(3):
        out[..., ch] = np.interp(t, pos, [c[ch] for c in cols])
    return out


def _sk_bars(labels, series, line=None, stacked=False, height=260, width=720):
    """SKCharts.bars in Python: grouped/stacked columns + optional line on one axis, nice ticks, 4 gridlines,
    padding l46 r8 t12 b30, rounded data-end corner r = min(4, w/2, h), empty state when all zero."""
    L, R, T, B = 46, 8, 12, 30
    iw, ih = width - L - R, height - T - B
    base = T + ih
    sums = [sum(s["values"][i] for s in series) for i in range(len(labels))] if stacked else \
        [max(s["values"][i] for s in series) for i in range(len(labels))]
    vmax = max(sums + (line["values"] if line else []))
    head = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d">' % (width, height, width, height)
    if vmax <= 0:
        return head + '<text class="empty" x="%d" y="%d" text-anchor="middle">لا توجد بيانات</text></svg>' % (width // 2, height // 2), None
    ticks, step = nice_ticks(vmax, 4)
    top = ticks[-1]
    y = lambda v: base - v / top * ih
    parts, geo = [], {"top": top, "ticks": ticks, "bars": [], "line": [], "base": base, "ih": ih}
    for tv in ticks[1:]:
        parts.append('<line class="grid" x1="%d" x2="%d" y1="%.2f" y2="%.2f"/>' % (L, L + iw, y(tv), y(tv)))
        parts.append('<text class="tick" x="%d" y="%.2f">%g</text>' % (L - 6, y(tv), tv))
    band = iw / float(len(labels))
    gw = band * 0.7
    for i, _ in enumerate(labels):
        acc = 0.0
        for j, s in enumerate(series):
            v = s["values"][i]
            if stacked:
                w, x = gw, L + i * band + (band - gw) / 2
                y0, y1 = y(acc + v), y(acc)
                acc += v
                end = j == len(series) - 1
            else:
                w = gw / len(series)
                x = L + i * band + (band - gw) / 2 + j * w
                y0, y1 = y(v), base
                end = True
            h = y1 - y0
            r = min(4.0, w / 2, h) if end else 0.0
            d = "M%.2f %.2f V%.2f Q%.2f %.2f %.2f %.2f H%.2f Q%.2f %.2f %.2f %.2f V%.2f Z" % (
                x, y1, y0 + r, x, y0, x + r, y0, x + w - r, x + w, y0, x + w, y0 + r, y1)
            parts.append('<path class="bar" fill="%s" data-v="%g" data-r="%.3f" d="%s"/>' % (s["color"], v, r, d))
            geo["bars"].append({"x": x, "w": w, "y0": y0, "y1": y1, "v": v, "r": r, "color": s["color"], "i": i})
    if line:
        pts = [(L + (i + 0.5) * band, y(v)) for i, v in enumerate(line["values"])]
        parts.append('<polyline class="line" fill="none" stroke="%s" stroke-width="2" points="%s"/>' % (
            line["color"], " ".join("%.2f,%.2f" % p for p in pts)))
        geo["line"] = pts
    return head + "".join(parts) + "</svg>", geo


def wilson(k, n, z=1.96):
    p = k / float(n)
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return c - h, c + h


def dist_to_polyline(p, pts):
    best = 1e9
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        u = 0 if L2 == 0 else max(0, min(1, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
        best = min(best, math.hypot(p[0] - ax - u * dx, p[1] - ay - u * dy))
    return best


def point_at(pts, frac):
    segs = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])]
    s = frac * sum(segs)
    for (a, b), L in zip(zip(pts, pts[1:]), segs):
        if s <= L or L == 0:
            u = s / L if L else 0
            return a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u
        s -= L
    return pts[-1]


def centroid(mask):
    np = _np()
    ys, xs = np.nonzero(mask)
    return (xs.mean() + 0.5, ys.mean() + 0.5) if len(xs) else None


def _sk_line(labels, series, area=False, endLabels=True, width=720, height=240):
    L, T, B = 46, 12, 30
    R = 70 if (endLabels and len(series) <= 4) else 8
    iw, ih = width - L - R, height - T - B
    step = int(math.ceil(len(labels) / float(max(3, iw // 56))))
    top = nice_ticks(max(max(s["values"]) for s in series), 4)[0][-1]
    X = lambda i: L + i * iw / float(len(labels) - 1)
    Y = lambda v: T + ih - v / top * ih
    out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" data-pr="%d" data-step="%d">' % (width, height, R, step)]
    for i in range(0, len(labels), step):
        out.append('<text class="xl" x="%.2f" y="%d">%s</text>' % (X(i), height - 8, labels[i]))
    for s in series:
        pts = " ".join("%.2f,%.2f" % (X(i), Y(v)) for i, v in enumerate(s["values"]))
        if area:
            out.append('<path class="area" fill="%s" fill-opacity="0.1" d="M%.2f %.2f L%s L%.2f %.2f Z"/>' % (
                s["color"], X(0), T + ih, pts.replace(" ", " L"), X(len(labels) - 1), T + ih))
        out.append('<polyline class="ln" fill="none" stroke="%s" stroke-width="2" points="%s"/>' % (s["color"], pts))
        j = len(s["values"]) - 1
        out.append('<circle class="pt" r="4" cx="%.2f" cy="%.2f" fill="%s"/>' % (X(j), Y(s["values"][j]), s["color"]))
        if endLabels and len(series) <= 4:
            out.append('<text class="end" x="%.2f" y="%.2f">%s</text>' % (X(j) + 8, Y(s["values"][j]), s["name"]))
    out.append("</svg>")
    return "".join(out), {"X": X, "Y": Y, "step": step, "R": R, "iw": iw}


def point_at_x(pts, x):
    for a, b in zip(pts, pts[1:]):
        if a[0] <= x <= b[0]:
            u = (x - a[0]) / (b[0] - a[0]) if b[0] != a[0] else 0
            return (x, a[1] + (b[1] - a[1]) * u)
    return pts[-1]


def angular_runs(mask, ang):
    """Clusters of lit 1-degree bins around the circle (wrap-aware)."""
    np = _np()
    hist = np.bincount(ang[mask].astype(int) % 360, minlength=360) > 0
    runs = col_runs(hist)
    if len(runs) > 1 and hist[0] and hist[359]:
        s0, n0 = runs[0]
        s1, n1 = runs[-1]
        runs = [(s1, n0 + n1)] + runs[1:-1]
    return runs


def _largest_remainder(weights, total):
    exact = [w * total / float(sum(weights)) for w in weights]
    fl = [int(math.floor(e)) for e in exact]
    for i in sorted(range(len(weights)), key=lambda i: -(exact[i] - fl[i]))[:total - sum(fl)]:
        fl[i] += 1
    return fl


PAL8_LIGHT = "#2a78d6 #eb6834 #1baf7a #eda100 #e87ba4 #008300 #4a3aa7 #e34948".split()


PAL8_DARK = "#3987e5 #d95926 #199e70 #c98500 #d55181 #008300 #9085e9 #e66767".split()


def spring(t, zeta=0.6, w=12.0):
    if t <= 0:
        return 0.0
    wd_ = w * math.sqrt(1 - zeta * zeta)
    return 1 - math.exp(-zeta * w * t) * (math.cos(wd_ * t) + zeta * w / wd_ * math.sin(wd_ * t))


def _steps_layout(n):
    if n <= 4:
        return "grid"
    if n <= 6:
        return "vertical"
    if n <= 9:
        return "vertical-phases"
    return "compact"
