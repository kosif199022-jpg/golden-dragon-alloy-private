"""Code brush: renders pressure strokes to an RGBA PNG with numpy (host Python, not Krita).

Why it exists: Krita's own brush engine (Node.paintLine/paintPath) needs a GUI view and
crashes inside kritarunner, so hand-drawn looking strokes are stamped here and handed to
Krita as a normal paint layer (still editable/paintable in Krita afterwards).

Stroke spec (all coordinates in canvas pixels):
  {"points": [[x, y], [x, y, pressure], ...],   # pressure 0..1, default 1
   "tip": "ink|pencil|soft|chalk|marker|round",  # default ink
   "size": 12, "color": "#1b1b1b", "opacity": 1.0,
   "smooth": true,          # Catmull-Rom through the points
   "closed": false,
   "taper": [0.15, 0.25],   # fraction of length that thins at start / end
   "spacing": 0.08,         # stamp spacing as a fraction of size
   "jitter": 0.0,           # random position wobble in px
   "seed": 1}
Shorthand generators: {"circle": [cx, cy, r]}, {"line": [x1, y1, x2, y2]},
{"arc": [cx, cy, r, deg_from, deg_to]} replace "points".
"""
from __future__ import annotations

import math
import numpy as np

TIPS = {
    #          hardness grain  flow  min_size  pressure->opacity
    "ink":    (0.92,    0.00,  1.00, 0.08,     0.0),
    "round":  (0.98,    0.00,  1.00, 1.00,     0.0),
    "pencil": (0.80,    0.55,  0.75, 0.35,     0.7),
    "soft":   (0.05,    0.00,  0.18, 0.60,     0.6),
    "chalk":  (0.55,    0.80,  0.85, 0.50,     0.4),
    "marker": (0.85,    0.08,  0.55, 0.85,     0.2),
}


def hex_rgb(c):
    c = c.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return np.array([int(c[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float32) / 255.0


def _catmull(pts, closed, per_seg=12):
    p = np.asarray(pts, dtype=np.float64)
    if len(p) < 3:
        return p
    if closed:
        p = np.vstack([p[-1:], p, p[:2]])
    else:
        p = np.vstack([p[:1], p, p[-1:]])
    out = []
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        for t in np.linspace(0, 1, per_seg, endpoint=False):
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(p[-2])
    return np.array(out)


def _expand(stroke):
    if "circle" in stroke:
        cx, cy, r = stroke["circle"]
        a = np.linspace(0, 2 * math.pi, 64, endpoint=False)
        stroke.setdefault("closed", True)
        return [[cx + r * math.cos(t), cy + r * math.sin(t)] for t in a]
    if "arc" in stroke:
        cx, cy, r, d0, d1 = stroke["arc"]
        a = np.radians(np.linspace(d0, d1, max(8, int(abs(d1 - d0) / 4))))
        return [[cx + r * math.cos(t), cy + r * math.sin(t)] for t in a]
    if "line" in stroke:
        x1, y1, x2, y2 = stroke["line"]
        return [[x1, y1], [x2, y2]]
    return stroke["points"]


def _resample(pts, step):
    """Even stamps along the polyline; carries pressure (3rd column)."""
    seg = np.diff(pts[:, :2], axis=0)
    seglen = np.hypot(seg[:, 0], seg[:, 1])
    cum = np.concatenate([[0], np.cumsum(seglen)])
    total = cum[-1]
    if total < 1e-6:
        return pts[:1], 0.0
    s = np.arange(0, total + 1e-9, max(step, 0.35))
    xs = np.interp(s, cum, pts[:, 0])
    ys = np.interp(s, cum, pts[:, 1])
    ps = np.interp(s, cum, pts[:, 2])
    return np.stack([xs, ys, ps, s / total], axis=1), total


def _grain(h, w, seed):
    """Paper tooth: blurred value noise, fixed per layer so strokes share the same paper."""
    rng = np.random.default_rng(seed)
    g = rng.random((h // 2 + 2, w // 2 + 2)).astype(np.float32)
    g = np.repeat(np.repeat(g, 2, 0), 2, 1)[:h, :w]
    g = (g + np.roll(g, 1, 0) + np.roll(g, 1, 1) + np.roll(g, -1, 0)) / 4
    return np.clip((g - g.min()) / (np.ptp(g) + 1e-6), 0, 1)


def render_strokes(width, height, strokes, seed=7):
    """Returns float32 RGBA (straight alpha) array of shape (H, W, 4)."""
    canvas = np.zeros((height, width, 4), dtype=np.float32)
    grain = _grain(height, width, seed)
    yy_cache = {}
    for si, st in enumerate(strokes):
        st = dict(st)
        tip = st.get("tip", "ink")
        hard, grain_amt, flow, min_size, p2o = TIPS.get(tip, TIPS["ink"])
        size = float(st.get("size", 10))
        color = hex_rgb(st.get("color", "#1b1b1b"))
        opacity = float(st.get("opacity", 1.0))
        raw = [list(p) + [1.0] * (3 - len(p)) if len(p) < 3 else list(p)[:3] for p in _expand(st)]
        pts = np.array(raw, dtype=np.float64)
        if st.get("smooth", True) and len(pts) >= 3:
            xy = _catmull(pts[:, :2], st.get("closed", False))
            pr = np.interp(np.linspace(0, 1, len(xy)), np.linspace(0, 1, len(pts)), pts[:, 2])
            pts = np.column_stack([xy, pr])
        elif st.get("closed"):
            pts = np.vstack([pts, pts[:1]])
        stamps, total = _resample(pts, size * float(st.get("spacing", 0.08)))
        t0, t1 = st.get("taper", [0.12, 0.22] if tip in ("ink", "pencil") else [0, 0])
        rng = np.random.default_rng(int(st.get("seed", si + 1)))
        jit = float(st.get("jitter", 0.0))

        mask = np.zeros((height, width), dtype=np.float32)
        for x, y, p, u in stamps:
            taper = 1.0
            if t0 > 0 and u < t0:
                s_ = u / t0
                taper = s_ * s_ * (3 - 2 * s_)  # smoothstep: no visible shoulder
            if t1 > 0 and u > 1 - t1:
                s_ = (1 - u) / t1
                taper = min(taper, s_ * s_ * (3 - 2 * s_))
            pr = p * taper
            r = 0.5 * size * (min_size + (1 - min_size) * pr)
            if r < 0.3:
                continue
            if jit:
                x += rng.normal(0, jit)
                y += rng.normal(0, jit)
            x0, x1 = int(max(0, math.floor(x - r - 1))), int(min(width, math.ceil(x + r + 2)))
            y0, y1 = int(max(0, math.floor(y - r - 1))), int(min(height, math.ceil(y + r + 2)))
            if x0 >= x1 or y0 >= y1:
                continue
            ys, xs = np.mgrid[y0:y1, x0:x1].astype(np.float32)
            d = np.hypot(xs - x, ys - y) / r
            if hard >= 0.5:  # anti-aliased hard edge with a soft shoulder
                edge = max(1.0 / r, (1 - hard) * 0.9)
                a = np.clip((1 - d) / edge, 0, 1)
            else:  # gaussian airbrush
                a = np.exp(-(d ** 2) * 3.0) * (d < 1.2)
            a *= flow * (1 - p2o + p2o * pr)
            sub = mask[y0:y1, x0:x1]
            if tip in ("soft", "marker"):  # build-up
                np.copyto(sub, sub + a * (1 - sub))
            else:  # one coat per stroke, overlaps don't darken
                np.maximum(sub, a, out=sub)
        if grain_amt:
            g = grain
            if tip == "pencil":
                g = np.clip((grain - 0.25) * 2.2, 0, 1)
            mask *= (1 - grain_amt) + grain_amt * g
        a = np.clip(mask * opacity, 0, 1)[..., None]
        # straight-alpha source-over
        out_a = a + canvas[..., 3:4] * (1 - a)
        safe = np.where(out_a > 1e-6, out_a, 1)
        canvas[..., :3] = (color * a + canvas[..., :3] * canvas[..., 3:4] * (1 - a)) / safe
        canvas[..., 3:4] = out_a
    return canvas


def save_png(rgba, path):
    from PIL import Image
    arr = (np.clip(rgba, 0, 1) * 255 + 0.5).astype(np.uint8)
    Image.fromarray(arr, "RGBA").save(path, optimize=False, compress_level=4)
    return path


if __name__ == "__main__":  # quick self-test
    import sys
    s = [{"line": [40, 60, 560, 80], "tip": t, "size": 24, "color": "#202a44"} for t in TIPS]
    for i, st in enumerate(s):
        st["line"] = [40, 50 + i * 55, 560, 70 + i * 55]
    img = render_strokes(600, 400, s)
    save_png(img, sys.argv[1] if len(sys.argv) > 1 else "brush_test.png")
    print("ok")
