"""Helpers of runners/fam_camera_composition_layout_b.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from pathlib import Path
from .core import check
from .core import fx
import json
import math
import subprocess


MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"


SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


SANS_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


COL = {"red": (255, 0, 0), "blue": (0, 0, 255), "green": (0, 255, 0), "yellow": (255, 255, 0),
       "magenta": (255, 0, 255), "cyan": (0, 255, 255)}


def np():
    import numpy
    return numpy


def ease_io_cubic(p):
    p = min(1.0, max(0.0, p))
    return 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2


def ease_in_cubic(p):
    p = min(1.0, max(0.0, p))
    return p ** 3


def ease_out_expo(p):
    p = min(1.0, max(0.0, p))
    return 1.0 if p >= 1 else 1 - 2 ** (-10 * p)


def ease_io_sine(p):
    p = min(1.0, max(0.0, p))
    return -(math.cos(math.pi * p) - 1) / 2


def smoothstep(p):
    p = min(1.0, max(0.0, p))
    return p * p * (3 - 2 * p)


def power2_out(p):
    p = min(1.0, max(0.0, p))
    return 1 - (1 - p) ** 2


def bezier(x1, y1, x2, y2):
    def calc(t, a, b):
        return ((1 - 3 * b + 3 * a) * t + (3 * b - 6 * a)) * t * t + 3 * a * t

    def f(x):
        if x <= 0:
            return 0.0
        if x >= 1:
            return 1.0
        lo, hi = 0.0, 1.0
        for _ in range(40):
            mid = (lo + hi) / 2
            if calc(mid, x1, x2) < x:
                lo = mid
            else:
                hi = mid
        return calc((lo + hi) / 2, y1, y2)
    return f


def write_video(path, frames, fps=30):
    """frames: list of HxWx3 uint8 arrays → H.264 mp4 (crf 10)."""
    N = np()
    frames = [N.asarray(f, dtype=N.uint8) for f in frames]
    H, W = frames[0].shape[:2]
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H),
                          "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "8",
                          "-pix_fmt", "yuv444p", str(path)], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    for f in frames:
        p.stdin.write(f.tobytes())
    p.stdin.close()
    err = p.stderr.read()
    if p.wait():
        raise RuntimeError("ffmpeg encode failed: %s" % err[-300:])
    return Path(path)


def read_video(path):
    """Decoded frames as uint8 (N, H, W, 3) at the native size (numeric work converts to int16/float itself)."""
    N = np()
    pr = fx.probe(path)
    v = [s for s in pr["streams"] if s["codec_type"] == "video"][0]
    w, h = int(v["width"]), int(v["height"])
    done = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                          capture_output=True, timeout=120, stdin=subprocess.DEVNULL)
    if done.returncode:
        raise RuntimeError(done.stderr.decode(errors="replace")[-300:])
    return N.frombuffer(done.stdout, dtype=N.uint8).reshape(-1, h, w, 3)


def save_png(path, arr):
    from PIL import Image
    Image.fromarray(np().asarray(arr, dtype=np().uint8)).save(path)
    return Path(path)


def load_png(path):
    from PIL import Image
    return np().asarray(Image.open(path).convert("RGB")).astype(float)


def mask_of(frame, color, tol=60):
    N = np()
    c = N.array(COL.get(color, color), dtype=N.int16)
    return N.abs(frame.astype(N.int16) - c).max(axis=2) < tol


def centroid(frame, color, tol=60, min_px=3):
    N = np()
    m = mask_of(frame, color, tol)
    if m.sum() < min_px:
        return None
    ys, xs = N.nonzero(m)
    return (float(xs.mean()), float(ys.mean()))


def area(frame, color, tol=60):
    return int(mask_of(frame, color, tol).sum())


def bbox(frame, color, tol=60):
    N = np()
    m = mask_of(frame, color, tol)
    if m.sum() < 2:
        return None
    ys, xs = N.nonzero(m)
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)


def track(frames, color, tol=60):
    return [centroid(f, color, tol) for f in frames]


def ink(frame, box, bg, thr=30):
    """Fraction of pixels in box (x0,y0,x1,y1) that differ from bg by more than thr."""
    N = np()
    x0, y0, x1, y1 = [int(round(v)) for v in box]
    reg = frame[y0:y1, x0:x1]
    if reg.size == 0:
        return 0.0
    return float((N.abs(reg - N.array(bg, float)).max(axis=2) > thr).mean())


def peak(frame, box):
    x0, y0, x1, y1 = [int(round(v)) for v in box]
    return float(frame[y0:y1, x0:x1].max())


def sharpness(gray):
    N = np()
    g = N.asarray(gray, float)
    if g.ndim == 3:
        g = g.mean(axis=2)
    lap = g[1:-1, 1:-1] * 4 - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:]
    return float(lap.var())


def max_err(meas, exp):
    worst = 0.0
    for m, e in zip(meas, exp):
        if isinstance(e, str):
            continue
        if m is None or e is None:
            if (m is None) != (e is None):
                return 1e9
            continue
        worst = max(worst, math.hypot(m[0] - e[0], m[1] - e[1]))
    return worst


def r2_linear(xs, ys):
    N = np()
    xs, ys = N.asarray(xs, float), N.asarray(ys, float)
    A = N.vstack([xs, N.ones_like(xs)]).T
    coef, *_ = N.linalg.lstsq(A, ys, rcond=None)
    pred = A @ coef
    ss = ((ys - ys.mean()) ** 2).sum()
    return 1 - ((ys - pred) ** 2).sum() / ss if ss > 0 else 0.0


def world(Wc, Hc, markers, bg=(40, 44, 52), grid=40, seed=1):
    """A world canvas with a faint grid and coloured disc markers {name: (color, x, y, r)}."""
    N = np()
    img = N.zeros((Hc, Wc, 3), N.uint8)
    img[:] = bg
    img[::grid, :] = (70, 74, 82)
    img[:, ::grid] = (70, 74, 82)
    yy, xx = N.mgrid[0:Hc, 0:Wc]
    for _, (color, x, y, r) in markers.items():
        img[(xx - x) ** 2 + (yy - y) ** 2 <= r * r] = COL.get(color, color)
    return img


def mat_stage(x=0.0, y=0.0, s=1.0, rot=0.0, origin=(0.0, 0.0)):
    """CSS-like stage transform: screen = origin + R*s*(p - origin) + (x, y)."""
    N = np()
    a = math.radians(rot)
    R = N.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]]) * s
    o = N.array(origin, float)
    t = o - R @ o + N.array([x, y], float)
    return N.hstack([R, t[:, None]])


def mat_cam(cx, cy, s, W, H, rot=0.0):
    """Camera looking at world point (cx, cy) with zoom s and roll rot: that point lands on the screen centre."""
    N = np()
    a = math.radians(rot)
    R = N.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]]) * s
    t = N.array([W / 2, H / 2]) - R @ N.array([cx, cy], float)
    return N.hstack([R, t[:, None]])


def apply_mat(M, p):
    return (float(M[0, 0] * p[0] + M[0, 1] * p[1] + M[0, 2]), float(M[1, 0] * p[0] + M[1, 1] * p[1] + M[1, 2]))


_GRIDS = {}


def warp(img, M, W, H, fill=(0, 0, 0)):
    """Render img through the 2x3 affine M (world → screen) by inverse nearest sampling."""
    N = np()
    A = N.vstack([M, [0, 0, 1]])
    Ai = N.linalg.inv(A)
    if (H, W) not in _GRIDS:
        _GRIDS[(H, W)] = N.mgrid[0:H, 0:W].astype(float)
    yy, xx = _GRIDS[(H, W)]
    sx = Ai[0, 0] * xx + Ai[0, 1] * yy + Ai[0, 2]
    sy = Ai[1, 0] * xx + Ai[1, 1] * yy + Ai[1, 2]
    xi, yi = N.round(sx).astype(int), N.round(sy).astype(int)
    ok = (xi >= 0) & (yi >= 0) & (xi < img.shape[1]) & (yi < img.shape[0])
    out = N.zeros((H, W, 3), N.uint8)
    out[:] = fill
    out[ok] = img[yi[ok], xi[ok]]
    return out


def cam_run(wd, name, wimg, mats, W, H, fps, markers, tol=2.5, input_mats=None, neg_k=3.0, frames=None):
    """Render the camera move and a static input clip; track every marker in both decoded videos.

    Returns (checks, outputs, data) where data has measured tracks, expected tracks and per-frame scale."""
    N = np()
    rendered = frames if frames is not None else [warp(wimg, M, W, H) for M in mats]
    out = write_video(wd / ("%s.mp4" % name), rendered, fps)
    imats = input_mats if input_mats is not None else [mats[0]] * len(mats)
    cache = {}
    for M in imats:
        k = M.tobytes()
        if k not in cache:
            cache[k] = warp(wimg, M, W, H)
    inp = write_video(wd / ("%s_input.mp4" % name), [cache[M.tobytes()] for M in imats], fps)
    fo, fi = read_video(out), read_video(inp)
    data = {"meas": {}, "exp": {}, "inp": {}}
    for k, (color, x, y, r) in markers.items():
        exp = []
        for M in mats:
            q = apply_mat(M, (x, y))
            rs = r * math.sqrt(abs(M[0, 0] * M[1, 1] - M[0, 1] * M[1, 0])) + 2
            inside = rs <= q[0] < W - rs and rs <= q[1] < H - rs
            outside = q[0] < -rs or q[1] < -rs or q[0] > W + rs or q[1] > H + rs
            exp.append(q if inside else (None if outside else "skip"))
        data["exp"][k] = exp
        data["meas"][k] = track(fo, color)
        data["inp"][k] = track(fi, color)
    err = max(max_err(data["meas"][k], data["exp"][k]) for k in markers)
    nerr = max(max_err(data["inp"][k], data["exp"][k]) for k in markers)
    checks = [check("%s: decoded markers follow the planned camera (max px error)" % name, err <= tol, err, "<= %s" % tol),
              check("negative control: static input does not follow the camera curve", nerr > neg_k * tol, nerr,
                    "> %s" % (neg_k * tol))]
    data["frames"] = fo
    data["input_frames"] = fi
    return checks, [out], data


def pair_scale(data, a, b, d0, which="meas"):
    """Per-frame scale measured from the distance between two tracked markers (d0 = world distance)."""
    res = []
    for p, q in zip(data[which][a], data[which][b]):
        res.append(None if p is None or q is None else math.hypot(p[0] - q[0], p[1] - q[1]) / d0)
    return res


def pair_angle(data, a, b, which="meas"):
    res = []
    for p, q in zip(data[which][a], data[which][b]):
        res.append(None if p is None or q is None else math.degrees(math.atan2(q[1] - p[1], q[0] - p[0])))
    return res


_FONTS = {}


def font(path, size):
    from PIL import ImageFont
    key = (path, size)
    if key not in _FONTS:
        try:
            _FONTS[key] = ImageFont.truetype(path, size)
        except OSError:
            _FONTS[key] = ImageFont.load_default()
    return _FONTS[key]


def canvas(W, H, bg):
    from PIL import Image
    return Image.new("RGB", (W, H), tuple(bg))


def blend(fg, bg, a):
    return tuple(int(round(bg[i] * (1 - a) + fg[i] * a)) for i in range(3))


def text_match(frame, xy, s, fnt, fg, bg, anchor="la", wrong=None):
    """Mean abs difference between the frame region and a clean rendering of string s (lower = match).

    Returns (err_for_s, err_for_wrong) so a check can assert the right label beats a wrong one."""
    from PIL import Image, ImageDraw
    N = np()
    H, W = frame.shape[:2]

    def err(txt):
        im = Image.new("RGB", (W, H), tuple(bg))
        d = ImageDraw.Draw(im)
        d.text(xy, txt, font=fnt, fill=tuple(fg), anchor=anchor)
        box = d.textbbox(xy, s, font=fnt, anchor=anchor)
        x0, y0, x1, y1 = max(0, box[0] - 1), max(0, box[1] - 1), min(W, box[2] + 1), min(H, box[3] + 1)
        ref = N.asarray(im).astype(float)[y0:y1, x0:x1]
        return float(N.abs(frame[y0:y1, x0:x1] - ref).mean())
    return err(s), (err(wrong) if wrong is not None else None)


def tc(t, fps=30):
    """mm:ss:ff timecode."""
    f = int(round(t * fps))
    return "%02d:%02d:%02d" % (f // (fps * 60), (f // fps) % 60, f % fps)


def tc_cs(t):
    cs = int(round(t * 100))
    return "%02d:%02d.%02d" % (cs // 6000, (cs // 100) % 60, cs % 100)


def write_json(wd, name, obj):
    p = wd / name
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    return p


def _near(a, b, tol):
    return a is not None and b is not None and abs(a - b) <= tol


def _pt_near(p, q, tol):
    return p is not None and q is not None and math.hypot(p[0] - q[0], p[1] - q[1]) <= tol


def _segments(flags):
    segs, start = [], None
    for i, f in enumerate(flags + [False]):
        if f and start is None:
            start = i
        if not f and start is not None:
            segs.append((start, i - 1))
            start = None
    return segs


def _push_world(W, H, d=None):
    d = d or W * 0.42
    return {"red": ("red", W / 2 - d, H / 2, 9), "blue": ("blue", W / 2 + d, H / 2, 9)}, 2 * d


def _push_card(wd, name, W, H, fps, scale_fn, n, tol=2.0, neg_k=2.5, d=None):
    mk, d0 = _push_world(W, H, d)
    wimg = world(W, H, mk)
    sc = [scale_fn(f / fps) for f in range(n)]
    mats = [mat_stage(0, 0, s, 0, (W / 2, H / 2)) for s in sc]
    checks, outs, d = cam_run(wd, name, wimg, mats, W, H, fps, mk, tol=tol, neg_k=neg_k)
    return checks, outs, d, pair_scale(d, "red", "blue", d0), pair_scale(d, "red", "blue", d0, "inp"), sc


def _offset_card(wd, name, W, H, fps, offs, scales=None, tol=1.6, neg_k=1.5):
    """Render per-frame stage offsets (and optional scales) and return tracked marker offsets from rest."""
    mk = {"red": ("red", W * 0.3, H * 0.5, 8), "blue": ("blue", W * 0.7, H * 0.5, 8)}
    wimg = world(W, H, mk)
    scales = scales or [1.0] * len(offs)
    mats = [mat_stage(o[0], o[1], s, 0, (W / 2, H / 2)) for o, s in zip(offs, scales)]
    checks, outs, d = cam_run(wd, name, wimg, mats, W, H, fps, mk, tol=tol, input_mats=[mat_stage()] * len(mats), neg_k=neg_k)
    mid = [((a[0] + b[0]) / 2 - W / 2, (a[1] + b[1]) / 2 - H / 2) if a and b else None for a, b in zip(d["meas"]["red"], d["meas"]["blue"])]
    return checks, outs, d, mid


def _vnoise(seed, x):
    i = math.floor(x)
    f = x - i
    h = lambda k: (math.sin((k + seed * 31.7) * 127.1) * 43758.5453) % 1.0 * 2 - 1
    u = f * f * (3 - 2 * f)
    return h(i) * (1 - u) + h(i + 1) * u


def _catmull(pts, n=200):
    out = []
    P = [pts[0]] + pts + [pts[-1]]
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(n):
            t = k / n
            out.append(tuple(0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t * t +
                                    (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t ** 3) for j in range(2)))
    out.append(pts[-1])
    return out


def _rgb(c):
    if isinstance(c, str):
        c = c.lstrip("#")
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    return tuple(c)


def draw_text(draw, xy, s, fnt, fill, anchor="la", tracking=0.0):
    """Text with optional letter-spacing (em). Returns the bbox."""
    if not tracking:
        draw.text(xy, s, font=fnt, fill=fill, anchor=anchor)
        return draw.textbbox(xy, s, font=fnt, anchor=anchor)
    size = fnt.size
    widths = [draw.textlength(ch, font=fnt) for ch in s]
    total = sum(widths) + tracking * size * (len(s) - 1)
    x, y = xy
    if anchor[0] == "r":
        x -= total
    elif anchor[0] == "m":
        x -= total / 2
    a2 = "l" + anchor[1]
    x0 = x
    for ch, w in zip(s, widths):
        draw.text((x, y), ch, font=fnt, fill=fill, anchor=a2)
        x += w + tracking * size
    b = draw.textbbox((x0, y), s, font=fnt, anchor=a2)
    return (b[0], b[1], int(math.ceil(x0 + total)), b[3])


def _label_xy(el, W, H):
    at = el["at"]
    ins = el.get("inset", 0.03)
    ix, iy = W * ins, H * ins
    if isinstance(at, tuple):
        return at[:2], at[2] if len(at) > 2 else "la"
    return {"tl": ((ix, iy), "lt"), "tr": ((W - ix, iy), "rt"), "bl": ((ix, H - iy), "lb"), "br": ((W - ix, H - iy), "rb"),
            "tc": ((W / 2, iy), "mt"), "bc": ((W / 2, H - iy), "mb")}[at]


def _label_text(el, i, t):
    s = el["text"](i, t) if callable(el["text"]) else el["text"]
    return s.upper() if el.get("upper") else s


def hud_draw(img, elems, i, t):
    from PIL import ImageDraw
    W, H = img.size
    over = img.copy()
    d = ImageDraw.Draw(over)
    bg = img.getpixel((W // 2, H // 2))
    boxes = []
    for el in elems:
        typ, col = el["type"], _rgb(el.get("color", (255, 255, 255)))
        a = el.get("alpha", 1.0)
        c = blend(col, el.get("bg", bg), a)
        if typ == "brackets":
            ins, L, w = el.get("inset", 0.03), el.get("len", 0.04), el.get("w", 2)
            ix, iy, l = W * ins, H * ins, W * L
            for sx, sy in ((0, 0), (1, 0), (0, 1), (1, 1)):
                x = ix if sx == 0 else W - ix
                y = iy if sy == 0 else H - iy
                dx = l if sx == 0 else -l
                dy = l if sy == 0 else -l
                d.line([(x, y), (x + dx, y)], fill=c, width=w)
                d.line([(x, y), (x, y + dy)], fill=c, width=w)
        elif typ == "label":
            xy, anc = _label_xy(el, W, H)
            draw_text(d, xy, _label_text(el, i, t), font(el.get("font", MONO), el.get("size", 12)), c, anc, el.get("tracking", 0))
        elif typ == "bar":
            x0, y0, x1, y1 = el["box"]
            fr = max(0.0, min(1.0, el["frac"](t)))
            segs, gap = el.get("segments", 1), el.get("gap", 3)
            if el.get("track"):
                d.rectangle([x0, y0, x1, y1], fill=blend(_rgb(el["track"]), bg, el.get("track_alpha", 1.0)))
            sw = (x1 - x0 - gap * (segs - 1)) / segs
            for k in range(segs):
                sx0 = x0 + k * (sw + gap)
                fill_to = min(sx0 + sw, x0 + fr * (x1 - x0))
                if segs > 1:
                    fill_to = sx0 + sw if fr * segs >= k + 1 else (sx0 + sw * (fr * segs - k) if fr * segs > k else sx0)
                if fill_to > sx0 + 0.5:
                    d.rectangle([sx0, y0, fill_to - 1, y1], fill=c)
        elif typ == "ticks":
            x0, y0, x1, y1 = el["box"]
            for k in range(el["count"] + 1):
                x = x0 + (x1 - x0) * k / el["count"]
                d.line([(x, y0 - 4 if (el.get("major") and k % el["major"] == 0) else y0), (x, y1)], fill=c, width=1)
        elif typ == "playhead":
            x0, y0, x1, y1 = el["box"]
            x = x0 + (x1 - x0) * max(0.0, min(1.0, el["frac"](t)))
            d.rectangle([x - 1, y0, x + 1, y1], fill=c)
        elif typ == "dots":
            act = el["active"](t)
            for k, (x, y) in enumerate(el["centers"]):
                r = el.get("r", 4)
                if k <= act if el.get("cumulative") else k == act:
                    d.ellipse([x - r, y - r, x + r, y + r], fill=c)
                else:
                    d.ellipse([x - r, y - r, x + r, y + r], outline=blend(col, bg, a * 0.6), width=1)
        elif typ == "custom":
            el["draw"](d, over, i, t)
    return over


def _bracket_boxes(W, H, ins=0.03, L=0.04):
    ix, iy, l = W * ins, H * ins, W * L
    return [(ix - 3, iy - 3, ix + l, iy + l), (W - ix - l, iy - 3, W - ix + 3, iy + l),
            (ix - 3, H - iy - l, ix + l, H - iy + 3), (W - ix - l, H - iy - l, W - ix + 3, H - iy + 3)]


def hud_card(wd, name, elems, W=960, H=540, fps=10, seconds=3.0, bg=(18, 18, 20), base=None, samples=None):
    """Render the HUD over a background clip, decode it and check every element off the pixels."""
    from PIL import Image, ImageDraw
    N = np()
    n = int(seconds * fps)
    bgs = []
    frames = []
    for i in range(n):
        t = i / fps
        b = base(i, t) if base else Image.new("RGB", (W, H), bg)
        bgs.append(N.asarray(b))
        frames.append(N.asarray(hud_draw(b, elems, i, t)))
    out = write_video(wd / ("%s.mp4" % name), frames, fps)
    inp = write_video(wd / ("%s_input.mp4" % name), bgs, fps)
    fo, fi = read_video(out).astype(float), read_video(inp).astype(float)
    samples = samples or sorted({0, n // 2, n - 1})
    checks = []
    neg_boxes = []
    for el in elems:
        typ = el["type"]
        col = _rgb(el.get("color", (255, 255, 255)))
        a = el.get("alpha", 1.0)
        if typ == "brackets":
            bxs = _bracket_boxes(W, H, el.get("inset", 0.03), el.get("len", 0.04))
            got = [ink(fo[0], b, fi[0][int(b[1]) + 1, int(b[0]) + 1], 12) for b in bxs]
            checks.append(check("%s: crop brackets in all four corners" % name, min(got) > 0.03, min(got), "> 0.03"))
            neg_boxes += bxs
        elif typ == "label":
            xy, anc = _label_xy(el, W, H)
            fnt = font(el.get("font", MONO), el.get("size", 12))
            for k in samples:
                t = k / fps
                s = _label_text(el, k, t)
                others = [_label_text(el, j, j / fps) for j in range(n)]
                wrong = next((o for o in others if o != s), None) or ("X" * len(s))
                bgc = tuple(int(v) for v in bgs[k][int(min(H - 1, max(0, xy[1]))), int(min(W - 1, max(0, xy[0])))])
                c = blend(col, bgc, a)

                rest = hud_draw(Image.fromarray(bgs[k].copy()), [e for e in elems if e is not el], k, t)

                def err(txt):
                    im = rest.copy()
                    dd = ImageDraw.Draw(im)
                    box = draw_text(dd, xy, txt, fnt, c, anc, el.get("tracking", 0))
                    ref = N.asarray(im).astype(float)
                    bb = draw_text(ImageDraw.Draw(Image.new("RGB", (W, H))), xy, s, fnt, c, anc, el.get("tracking", 0))
                    x0, y0, x1, y1 = int(max(0, bb[0] - 1)), int(max(0, bb[1] - 1)), int(min(W, bb[2] + 1)), int(min(H, bb[3] + 1))
                    return float(N.abs(fo[k][y0:y1, x0:x1] - ref[y0:y1, x0:x1]).mean()), (x0, y0, x1, y1)
                e_ok, bx = err(s)
                e_bad, _ = err(wrong)
                checks.append(check("%s: label %r reads %r at t=%.2fs" % (name, el.get("id", el["at"]), s, t), e_ok < 0.6 * e_bad and e_ok < 6,
                                    [round(e_ok, 2), round(e_bad, 2)], "right text matches, other text does not"))
                neg_boxes.append(bx)
            if a < 1.0:
                pk = peak(fo[samples[0]], bx)
                exp_pk = max(blend(col, tuple(int(v) for v in bgs[samples[0]][int(bx[1]), int(bx[0])]), a))
                checks.append(check("%s: label %r opacity %.0f%%" % (name, el.get("id", el["at"]), a * 100), abs(pk - exp_pk) <= 14, pk, exp_pk))
        elif typ == "bar":
            x0, y0, x1, y1 = el["box"]
            yc = int((y0 + y1) / 2)
            c = N.array(blend(col, bg if not base else tuple(int(v) for v in bgs[0][yc, x0]), a), float)
            for k in samples:
                row = fo[k][yc, int(x0):int(x1) + 1]
                on = N.abs(row - c).max(axis=1) < 30
                fr = float(on.sum()) / (x1 - x0 + 1)
                segs_ = el.get("segments", 1)
                exp_f = el["frac"](k / fps)
                if segs_ > 1:
                    gapfrac = el.get("gap", 3) * (segs_ - 1) / (x1 - x0)
                    exp_f = min(1.0, exp_f) * (1 - gapfrac)
                checks.append(check("%s: bar %r fill at t=%.2fs" % (name, el.get("id", "bar"), k / fps), abs(fr - exp_f) < 0.03, fr, exp_f))
            if el.get("segments", 1) > 1:
                row = fo[-1][yc, int(x0):int(x1) + 1] if el["frac"]((n - 1) / fps) >= 0.999 else None
                if row is not None:
                    on = list(N.abs(row - c).max(axis=1) < 30)
                    runs = sum(1 for j in range(len(on)) if on[j] and (j == 0 or not on[j - 1]))
                    checks.append(check("%s: %d segments" % (name, el["segments"]), runs == el["segments"], runs, el["segments"]))
            neg_boxes.append((x0, y0, x1, y1))
        elif typ == "playhead":
            x0, y0, x1, y1 = el["box"]
            for k in samples:
                yc = int(y0) + 1
                row = N.abs(fo[k][yc, :] - N.array(blend(col, bg, a), float)).max(axis=1) < 30
                xs = N.nonzero(row[int(x0) - 2:int(x1) + 3])[0]
                xm = float(xs.mean()) + int(x0) - 2 if len(xs) else -1
                exp_x = x0 + (x1 - x0) * el["frac"](k / fps)
                checks.append(check("%s: playhead at t=%.2fs" % (name, k / fps), abs(xm - exp_x) <= 1.5, xm, exp_x))
        elif typ == "ticks":
            x0, y0, x1, y1 = el["box"]
            row = N.abs(fo[0][int(y1) - 1, :] - fi[0][int(y1) - 1, :]).max(axis=1) > 25
            seg = row[int(x0) - 1:int(x1) + 2]
            runs = sum(1 for j in range(len(seg)) if seg[j] and (j == 0 or not seg[j - 1]))
            checks.append(check("%s: %d ticks" % (name, el["count"] + 1), runs == el["count"] + 1, runs, el["count"] + 1))
            neg_boxes.append((x0, y0, x1, y1))
        elif typ == "dots":
            for k in samples:
                act = el["active"](k / fps)
                cc = N.array(blend(col, bg, a), float)
                filled = [float(N.abs(fo[k][int(y) - 1:int(y) + 2, int(x) - 1:int(x) + 2] - cc).max()) < 40 for x, y in el["centers"]]
                exp_ = [(j <= act) if el.get("cumulative") else (j == act) for j in range(len(el["centers"]))]
                checks.append(check("%s: active dot(s) at t=%.2fs" % (name, k / fps), filled == exp_, filled, exp_))
        elif typ == "custom" and el.get("check"):
            checks += el["check"](fo, fi, fps)
    if neg_boxes:
        neg = max(ink(fi[k], b, fi[k][min(H - 1, int(b[1]) + 1), min(W - 1, int(b[0]) + 1)], 12) for b in neg_boxes for k in samples)
        checks.append(check("negative control: the input frames carry none of the HUD", neg < 0.01, neg, "< 0.01"))
    return checks, [out]


def _chapters(names, seconds):
    def at(t):
        k = min(len(names) - 1, int(t / seconds * len(names)))
        return k
    return at


def _hud_simple(wd, name, ins_tl, ins_tr, ins_bl, ins_br, extra=(), S=3.0, size=12, alpha=1.0, color="#f0eee6", brackets=True, W=960, H=540, fps=10, samples=None):
    els = [{"type": "brackets", "color": color, "alpha": alpha}] if brackets else []
    for at, txt in (("tl", ins_tl), ("tr", ins_tr), ("bl", ins_bl), ("br", ins_br)):
        if txt is not None:
            els.append({"type": "label", "id": at, "at": at, "inset": 0.05, "text": txt, "size": size, "alpha": alpha, "color": color})
    els += list(extra)
    return hud_card(wd, name, els, W, H, fps, S, samples=samples or [0, int(S * fps / 2), int(S * fps) - 1])


def _footage_world(W, H):
    mk = {"red": ("red", W * 0.3, H * 0.5, 7), "blue": ("blue", W * 0.7, H * 0.5, 7)}
    img = world(W, H, mk, bg=(90, 96, 104))
    return img, mk


def _black_frac(f, thr=8):
    N = np()
    return float((f.max(axis=2) < thr).mean())


_MOVES = {  # name: (z0, z1, x0, x1, y0, y1, r0, r1, ease)
    "push_in": (1.0, 1.15, 0, 0, 0, 0, 0, 0, ease_io_sine), "pull_out": (1.2, 1.0, 0, 0, 0, 0, 0, 0, ease_io_sine),
    "slow_zoom": (1.0, 1.06, 0, 0, 0, 0, 0, 0, lambda p: p), "punch_in": (1.0, 1.18, 0, 0, 0, 0, 0, 0, lambda p: 1 - (1 - min(1, p / 0.16)) ** 3),
    "whip_pan": (1.12, 1.12, 1, -1, 0, 0, 0, 0, lambda p: ease_out_expo(p)), "pan": (1.15, 1.15, 0.8, -0.8, 0, 0, 0, 0, ease_io_sine),
    "tilt": (1.15, 1.15, 0, 0, 0.8, -0.8, 0, 0, ease_io_sine), "truck": (1.2, 1.2, -0.9, 0.9, 0, 0, 0, 0, lambda p: p),
    "dolly_zoom": (1.0, 1.3, 0, 0, 0, 0, 0, 0, lambda p: p * p), "orbit": (1.12, 1.18, 0.5, -0.5, 0, 0, -3, 3, ease_io_sine),
    "crane_up": (1.2, 1.05, 0, 0, 0.7, -0.6, 0, 0, ease_io_cubic)}


def _move_mat(m, p, W, H):
    z0, z1, x0, x1, y0, y1, r0, r1, ez = m
    e = ez(p)
    z = z0 + (z1 - z0) * e
    room_x, room_y = (z - 1) * W / 2, (z - 1) * H / 2
    return mat_stage((x0 + (x1 - x0) * e) * room_x, (y0 + (y1 - y0) * e) * room_y, z, r0 + (r1 - r0) * e, (W / 2, H / 2)), z, e


def _plan_moves(mood, cuts, peaks, D):
    """CAM.plan rules: first push_in (photo: ken_burns) + punch 0.55; last pull_out; music/hype punch every 2nd cut;
    cinematic rack_focus on 35 % of long shots; loud peaks → punch_in (<=1 per 4 s, >=2.5 s apart, not within 0.35 s of a cut);
    never the same move twice in a row."""
    shots = [(cuts[i], cuts[i + 1] if i + 1 < len(cuts) else D) for i in range(len(cuts))]
    long_pool = {"talk": ["push_in", "slow_zoom", "drift"], "music": ["pan", "push_in", "truck"], "hype": ["whip_pan", "push_in", "truck"],
                 "cinematic": ["slow_zoom", "pan", "crane_up"], "photo": ["ken_burns", "pan", "tilt"], "screen": ["push_in", "pan", "locked_off"]}[mood]
    short_pool = ["punch_in", "push_in", "locked_off"]
    moves, accents = [], []
    longs = 0
    for i, (a, b) in enumerate(shots):
        pool = long_pool if b - a > 1.6 else short_pool
        if i == 0:
            mv = "ken_burns" if mood == "photo" else "push_in"
            accents.append({"at": a, "kind": "punch", "amount": 0.55})
        elif i == len(shots) - 1:
            mv = "pull_out"
        else:
            if mood == "cinematic" and b - a > 1.6:
                longs += 1
                mv = "rack_focus" if (longs * 0.35) % 1 < 0.35 else pool[i % len(pool)]
            else:
                mv = pool[i % len(pool)]
        if moves and mv == moves[-1]:
            mv = next(p for p in pool + short_pool + ["drift"] if p != moves[-1])
        moves.append(mv)
        if mood in ("music", "hype") and i % 2 == 1:
            accents.append({"at": a, "kind": "punch"})
    last = -99
    for p in peaks:
        if p - last >= 2.5 and min(abs(p - c) for c in cuts) > 0.35 and sum(1 for x in accents if x["kind"] == "punch_in" and abs(x["at"] - p) < 4) == 0:
            accents.append({"at": p, "kind": "punch_in"})
            last = p
    return [{"shot": i, "start": a, "end": b, "move": m} for i, ((a, b), m) in enumerate(zip(shots, moves))], accents


def _fit_box(iw, ih, W, H, mode):
    s = max(W / iw, H / ih) if mode == "cover" else min(W / iw, H / ih)
    w, h = iw * s, ih * s
    return s, ((W - w) / 2, (H - h) / 2, w, h)


def _persp_project(pts, rx, ry, rz, s, D=1500.0):
    """Rotate 3D points (x,y,z) by rx, ry, rz degrees, scale s, perspective with eye distance D; returns 2D."""
    out = []
    ax, ay, az = (math.radians(v) for v in (rx, ry, rz))
    for x, y, z in pts:
        y, z = y * math.cos(ax) - z * math.sin(ax), y * math.sin(ax) + z * math.cos(ax)
        x, z = x * math.cos(ay) + z * math.sin(ay), -x * math.sin(ay) + z * math.cos(ay)
        x, y = x * math.cos(az) - y * math.sin(az), x * math.sin(az) + y * math.cos(az)
        k = D / (D - z)
        out.append((x * s * k, y * s * k))
    return out


_PAL = [(255, 0, 0), (0, 0, 255), (0, 200, 0), (255, 200, 0), (255, 0, 255), (0, 220, 220), (255, 120, 0), (120, 0, 255), (0, 120, 60), (200, 200, 200)]


def layout_render(wd, name, W, H, items, bg=(24, 24, 28), radius=None, extra=None):
    """items: [(key, (x0, y0, x1, y1))] drawn in unique colours; returns (png, measured {key: bbox})."""
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(im)
    cmap = {}
    for i, (key, box) in enumerate(items):
        c = _PAL[i % len(_PAL)]
        cmap[key] = c
        x0, y0, x1, y1 = [int(round(v)) for v in box]
        if radius and key in radius:
            d.rounded_rectangle([x0, y0, x1 - 1, y1 - 1], radius=radius[key], fill=c)
        else:
            d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=c)
    if extra:
        extra(d, im)
    p = wd / ("%s.png" % name)
    im.save(p)
    A = np().asarray(im)
    return p, {k: bbox(A, c, 12) for k, c in cmap.items()}, A


def _card_shadow(im, box, radius, offset, blur, alpha):
    from PIL import Image, ImageDraw, ImageFilter
    sh = Image.new("L", im.size, 0)
    x0, y0, x1, y1 = box
    ImageDraw.Draw(sh).rounded_rectangle([x0, y0 + offset, x1, y1 + offset], radius=radius, fill=int(255 * alpha))
    sh = sh.filter(ImageFilter.GaussianBlur(blur / 2))
    return Image.composite(Image.new("RGB", im.size, (0, 0, 0)), im, sh)


def _tile_wall(W, H, angle, speed, t, cols=7, rows=6, tw=60, th=40, gap=12, radius=8, x_off=0, colfn=None):
    """A rotated wall of rounded tiles translated diagonally by speed*t (wraps), as a PIL RGBA layer."""
    from PIL import Image, ImageDraw
    big = Image.new("RGBA", (W * 2, H * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    pitch_x, pitch_y = tw + gap, th + gap
    sh = (speed * t) % pitch_y
    for r in range(-2, rows * 3):
        for c in range(-2, cols * 3):
            x = c * pitch_x + x_off
            y = r * pitch_y - sh
            col = colfn(r, c) if colfn else (200, 200, 210, 255)
            d.rounded_rectangle([x, y, x + tw, y + th], radius=radius, fill=col)
    return big.rotate(angle, center=(W, H), resample=Image.NEAREST).crop((W // 2, H // 2, W // 2 + W, H // 2 + H))


def _subject_png(wd, name, cx, cy, W=900, H=600, r=40, extra=None, bg=(128, 128, 128)):
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(im)
    if extra:
        extra(d)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(250, 250, 250))
    p = wd / ("%s.png" % name)
    im.save(p)
    return p


def kelvin_rgb(K):
    """Tanner Helland's blackbody approximation (1000-40000 K)."""
    t = K / 100.0
    r = 255 if t <= 66 else 329.698727446 * ((t - 60) ** -0.1332047592)
    g = 99.4708025861 * math.log(t) - 161.1195681661 if t <= 66 else 288.1221695283 * ((t - 60) ** -0.0755148492)
    b = 255 if t >= 66 else (0 if t <= 19 else 138.5177312231 * math.log(t - 10) - 305.0447927307)
    return tuple(max(0, min(255, int(round(v)))) for v in (r, g, b))


def _cont_clip(wd, s):
    N = np()
    W, H = s.get("W", 160), s.get("H", 90)
    k = N.array(kelvin_rgb(s["kelvin"]), float)
    ramp = N.linspace(1.0, 0.45, W) if s["key"] == "left" else N.linspace(0.45, 1.0, W)
    base = (ramp[None, :, None] * k[None, None, :] * 0.8).repeat(H, 0)
    fr = []
    for i in range(10):
        f = base.copy()
        x = int(20 + i * (W - 40) / 9) if s["dir"] == "LR" else int(W - 20 - i * (W - 40) / 9)
        f[H // 2 - 6:H // 2 + 6, x - 6:x + 6] = (0, 255, 0)
        fr.append(f.astype(N.uint8))
    return write_video(wd / ("%s.mp4" % s["id"]), fr, s.get("fps", 10))


def continuity_check(wd, shots):
    """Measure each clip (fps, aspect, colour temperature, key side, screen direction) and compare metadata."""
    N = np()
    meas = []
    for s in shots:
        p = _cont_clip(wd, s)
        st = fx.probe(p)["streams"][0]
        num, den = st["r_frame_rate"].split("/")
        F = read_video(p)
        g = F[0].astype(float)
        bgm = ~((g[..., 1] > 200) & (g[..., 0] < 80))
        rb = float(g[..., 0][bgm].mean() / max(1.0, g[..., 2][bgm].mean()))
        W = g.shape[1]
        side = "left" if g[:, : W // 4].mean() > g[:, -W // 4:].mean() else "right"
        xs = [c[0] for c in track(F, "green") if c]
        meas.append({"fps": float(num) / float(den), "aspect": round(st["width"] / st["height"], 3), "rb": rb, "key": side,
                     "dir": "LR" if xs[-1] > xs[0] else "RL", "path": str(p)})
    flags = set()
    ref, mref = shots[0], meas[0]
    damaged = False
    for i, (s, m) in enumerate(zip(shots, meas)):
        if s["lock"] != ref["lock"]:
            flags.add(("lock text", i))
        if abs(m["rb"] / mref["rb"] - 1) > 0.15 or m["key"] != mref["key"]:
            flags.add(("light", i))
        if damaged and not s["damage"]:
            flags.add(("wardrobe damage", i))
        damaged = damaged or s["damage"]
        if s["tod"] != ref["tod"]:
            flags.add(("time of day", i))
        if s["hand"] != ref["hand"]:
            flags.add(("prop hand", i))
        if m["dir"] != mref["dir"] and not s.get("neutral"):
            flags.add(("screen direction", i))
        if m["fps"] != mref["fps"] or m["aspect"] != mref["aspect"]:
            flags.add(("aspect/fps", i))
    return flags, meas


_HEAD, _FACE_N, _HEAD_R = (0.0, 1.25, 0.65), (0.0, -0.2, -1.0), 0.1


_MON = {"z": -0.3, "x": (-0.3, 0.3), "y": (0.85, 1.25)}


def _cam_basis(pos, pitch_deg, yaw_deg):
    N = np()
    p, y = math.radians(pitch_deg), math.radians(yaw_deg)
    fwd = N.array([math.sin(y) * math.cos(p), math.sin(p), -math.cos(y) * math.cos(p)])
    up0 = N.array([0, 0, -1.0]) if abs(fwd[1]) > 0.99 else N.array([0, 1.0, 0])
    right = N.cross(fwd, up0); right /= N.linalg.norm(right)
    up = N.cross(right, fwd)
    return N.asarray(pos, float), fwd, right, up


def _in_view(cam, pt, vfov, aspect=16 / 9):
    N = np()
    pos, fwd, right, up = cam
    v = N.asarray(pt, float) - pos
    z = v @ fwd
    if z <= 0.05:
        return False, None
    tv = math.tan(math.radians(vfov) / 2)
    x, y = (v @ right) / (z * tv * aspect), (v @ up) / (z * tv)
    return abs(x) <= 1 and abs(y) <= 1, (float(x), float(y))


def _face_visible(cam, vfov, head=_HEAD, normal=_FACE_N):
    N = np()
    n = N.asarray(normal, float); n /= N.linalg.norm(n)
    face_pt = N.asarray(head) + n * _HEAD_R
    inside, _ = _in_view(cam, face_pt, vfov)
    return bool(inside and (cam[0] - face_pt) @ n > 0)


def _reflection_risk(cam, vfov, screen_on):
    """Mirror the face across the dark monitor plane; risky if the mirrored face is in view, seen through the
    monitor rectangle, facing the camera, and not blocked by the head itself."""
    N = np()
    if screen_on:
        return False
    zc = _MON["z"]
    n = N.asarray(_FACE_N, float); n /= N.linalg.norm(n)
    face = N.asarray(_HEAD) + n * _HEAD_R
    mf = face.copy(); mf[2] = 2 * zc - mf[2]
    mn = n.copy(); mn[2] = -mn[2]
    inside, _ = _in_view(cam, mf, vfov)
    pos = cam[0]
    t = (zc - pos[2]) / (mf[2] - pos[2])
    hit = pos + t * (mf - pos)
    on_mon = _MON["x"][0] <= hit[0] <= _MON["x"][1] and _MON["y"][0] <= hit[1] <= _MON["y"][1] and 0 < t < 1
    d = mf - pos; d /= N.linalg.norm(d)
    w = N.asarray(_HEAD) - pos
    blocked = N.linalg.norm(w - (w @ d) * d) < _HEAD_R and 0 < w @ d < N.linalg.norm(mf - pos)
    return bool(inside and on_mon and (pos - mf) @ mn > 0 and not blocked)


_SETUPS = {   # name: (position, pitch, yaw, vfov, story role)
    "overhead": ((0.0, 0.75 + 0.7, 0.05), -90, 0, 50, "process: the work on the desk"),
    "over_shoulder": ((0.25, 1.1 + 0.1, 0.65 + 1.0), -15, 0, 40, "context: what the creator sees"),
    "front_below_chest": ((0.0, 1.0, 0.65 - 1.0), -15, 180, 40, "presence: hands and posture"),
    "object_space": ((0.4, 0.8, 0.3), 0, 0, 40, "detail: the product alone"),
    "side_hands": ((1.0, 0.75 + 0.2, 0.15), -10, -90, 30, "craft: the hands at work"),
}


def _hue_clusters(png, min_frac=0.0001):
    from PIL import Image
    N = np()
    hsv = N.asarray(Image.open(png).convert("RGB").convert("HSV")).astype(int)
    sat = (hsv[..., 1] > 120) & (hsv[..., 2] > 80)
    if not sat.any():
        return 0
    hist = N.bincount((hsv[..., 0][sat] * 12) // 256, minlength=12) / sat.size
    on = hist > min_frac
    # merge circular neighbours into clusters
    return int(sum(1 for i in range(12) if on[i] and not on[i - 1])) or int(on.any())


def _caption_safe_layout(W, H):
    portrait = H > W
    cut = 0.83 * H
    hero_cy = 0.28 * H if portrait else 0.42 * H
    hero_h = (0.22 if portrait else 0.30) * H
    items = [("hero", W * 0.1, hero_cy - hero_h / 2, W * 0.9, hero_cy + hero_h / 2)]
    y = hero_cy + hero_h / 2 + 0.03 * H
    for k in range(3):
        h = 0.06 * H
        if y + h > cut:
            break
        items.append(("line%d" % k, W * 0.1, y, W * 0.8, y + h))
        y += h + 0.02 * H
    return items


def _fit_text(text, box_w, box_h, base, floor, path=SANS):
    """Largest font size <= base whose greedy word wrap fits the box; never below the floor (None if it cannot fit)."""
    from PIL import Image, ImageDraw
    d = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    for s in range(base, floor - 1, -1):
        f = font(path, s)
        lines, cur = [], ""
        for w in text.split():
            t = (cur + " " + w).strip()
            if d.textlength(t, font=f) <= box_w:
                cur = t
            else:
                lines.append(cur); cur = w
        lines.append(cur)
        if max(d.textlength(l, font=f) for l in lines) <= box_w and len(lines) * s * 1.2 <= box_h:
            return s, lines
    return None, None


def _components(mask, dilate=6):
    from scipy import ndimage
    lab, n = ndimage.label(ndimage.binary_dilation(mask, iterations=dilate))
    return lab, n


def _story_frame(wd, name, texts, surface=(300, 160, 660, 330), W=960, H=540, caption=None):
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (W, H), (40, 46, 56))
    d = ImageDraw.Draw(im)
    d.rectangle(surface, fill=(150, 120, 90))                         # a real surface: a sign board in the scene
    for (x, y, s, t) in texts:
        d.text((x, y), t, font=font(SANS_B, s), fill=(255, 255, 255))
    if caption:
        d.text((W // 2, H - 40), caption, font=font(SANS, 22), fill=(255, 255, 0), anchor="mm")
    p = wd / ("%s.png" % name)
    im.save(p)
    return p


def _copy_layers(png, surface, H=540):
    N = np()
    A = load_png(png).astype(int)
    m = (A.min(axis=2) > 235)
    m[int(H * 0.85):] = False                                          # captions (yellow, bottom band) are excluded
    lab, n = _components(m)
    on_surface = []
    for k in range(1, n + 1):
        ys, xs = N.nonzero((lab == k) & m)
        on_surface.append(bool(xs.min() >= surface[0] and xs.max() <= surface[2] and ys.min() >= surface[1] and ys.max() <= surface[3]))
    return n, on_surface


def _bars(wd, name, colours, W=640, H=360):
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (W, H), (245, 245, 242))
    d = ImageDraw.Draw(im)
    hs = [120, 200, 160, 260, 180, 140]
    for i, (h, c) in enumerate(zip(hs, colours)):
        x = 60 + i * 90
        d.rectangle([x, H - 40 - h, x + 60, H - 40], fill=c)
    p = wd / ("%s.png" % name)
    im.save(p)
    return p


def _seg_clip(wd, name, segs, W, H, fps=10, marker=True):
    """segs: [(n_frames, rgb)]: solid shots with a moving white marker; a cut is a colour change."""
    N = np()
    fr = []
    for n, c in segs:
        for i in range(n):
            f = N.zeros((H, W, 3), N.uint8) + N.array(c, N.uint8)
            if marker:
                x = int(4 + (i * 3) % max(1, W - 12))
                f[H // 2 - 3:H // 2 + 3, x:x + 6] = 255
            fr.append(f)
    return write_video(wd / ("%s.mp4" % name), fr, fps)


def _cell_cuts(F, box, thr=40):
    x0, y0, x1, y1 = box
    m = F[:, y0 + 4:y1 - 4, x0 + 4:x1 - 4].astype(int).mean(axis=(1, 2))
    d = np().abs(np().diff(m, axis=0)).max(axis=1)
    return [i + 1 for i in range(len(d)) if d[i] > thr], m
