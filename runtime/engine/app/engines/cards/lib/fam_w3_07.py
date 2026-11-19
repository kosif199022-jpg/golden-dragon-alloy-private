"""Helpers of runners/fam_w3_07.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from pathlib import Path
from .core import fx
import json
import math
import numpy as np
import shutil
import subprocess


FONTS = Path(__import__("os").environ.get("KOSIF_FONTS") or Path.home() / "kosif-tool" / ".claude" / "skills" / "kosif-superpowers" / "proofs" / "_shared" / "fonts")  # read-only asset in the old repo


AMIRI_B = FONTS / "Amiri-Bold.ttf"


POPPINS = FONTS / "Poppins-Bold.ttf"


def R(seed):
    return np.random.default_rng(seed)


def canvas(W, H, bg=(0, 0, 0)):
    a = np.zeros((H, W, 3))
    a[:] = bg
    return a


def save(path, a):
    Image.fromarray(np.clip(np.round(np.asarray(a, dtype=float)), 0, 255).astype(np.uint8)).save(path)
    return Path(path)


def load(path):
    return np.asarray(Image.open(path).convert("RGB")).astype(float)


def video(path, frames, fps=30):
    frames = [np.clip(np.round(f), 0, 255).astype(np.uint8) for f in frames]
    h, w = frames[0].shape[:2]
    p = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                        "-s", "%dx%d" % (w, h), "-r", str(fps), "-i", "-", "-c:v", "libx264rgb", "-qp", "0",
                        "-pix_fmt", "rgb24", str(path)], input=b"".join(f.tobytes() for f in frames),
                       capture_output=True, timeout=60)
    if p.returncode:
        raise RuntimeError(p.stderr.decode()[-300:])
    return Path(path)


def vread(path, W, H):
    return fx.frames(path, size=(W, H))


def disc(a, x, y, r, col, mode="max", alpha=1.0):
    H, W = a.shape[:2]
    x0, x1 = max(0, int(x - r - 2)), min(W, int(x + r + 3))
    y0, y1 = max(0, int(y - r - 2)), min(H, int(y + r + 3))
    if x0 >= x1 or y0 >= y1:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1]
    m = (np.hypot(yy + .5 - y, xx + .5 - x) <= r)[..., None]
    win = a[y0:y1, x0:x1]
    c = np.asarray(col, dtype=float)
    if mode == "add":
        win += m * c * alpha
    elif mode == "over":
        win[...] = win * (1 - m * alpha) + m * c * alpha
    else:
        win[...] = np.where(m, np.maximum(win, c * alpha), win)


def draw_layer(W, H, fn, mode="RGB"):
    im = Image.new(mode, (W, H), 0)
    fn(ImageDraw.Draw(im))
    a = np.asarray(im).astype(float)
    return a if a.ndim == 3 else a


def poly_mask(W, H, pts):
    im = Image.new("L", (W, H), 0)
    ImageDraw.Draw(im).polygon([tuple(map(float, p)) for p in pts], fill=255)
    return np.asarray(im) > 127


def centroid(mask):
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return None
    return float(xs.mean()), float(ys.mean())


def label(mask, eight=False):
    from scipy.ndimage import label as _l
    lab, n = _l(mask, structure=np.ones((3, 3)) if eight else None)
    return lab, n


def iou(a, b):
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else 0.0


def jw(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return Path(path)


def hexc(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=float)


def out_expo(t):
    t = np.clip(t, 0, 1)
    return np.where(t >= 1, 1.0, 1 - 2.0 ** (-10 * t))


def in_out_cubic(t):
    t = np.clip(t, 0, 1)
    return np.where(t < .5, 4 * t ** 3, 1 - (-2 * t + 2) ** 3 / 2)


def out_cubic(t):
    t = np.clip(t, 0, 1)
    return 1 - (1 - t) ** 3


def in_cubic(t):
    t = np.clip(t, 0, 1)
    return t ** 3


def out_back(t, s=1.70158):
    t = np.clip(t, 0, 1)
    return 1 + (s + 1) * (t - 1) ** 3 + s * (t - 1) ** 2


def out_bounce(t):
    t = np.clip(np.asarray(t, dtype=float), 0, 1)
    n, d = 7.5625, 2.75
    return np.where(t < 1 / d, n * t * t, np.where(t < 2 / d, n * (t - 1.5 / d) ** 2 + .75,
                    np.where(t < 2.5 / d, n * (t - 2.25 / d) ** 2 + .9375, n * (t - 2.625 / d) ** 2 + .984375)))


def out_elastic(t):
    t = np.clip(np.asarray(t, dtype=float), 0, 1)
    c = 2 * math.pi / 3
    return np.where(t <= 0, 0.0, np.where(t >= 1, 1.0, 2.0 ** (-10 * t) * np.sin((t * 10 - .75) * c) + 1))


def spring(t, k, d, m=1.0):
    """Unit-step response of m x'' + d x' + k x = k (0 -> 1), closed form."""
    t = np.maximum(np.asarray(t, dtype=float), 0)
    w0 = math.sqrt(k / m)
    z = d / (2 * math.sqrt(k * m))
    if z < 1:
        wd = w0 * math.sqrt(1 - z * z)
        return 1 - np.exp(-z * w0 * t) * (np.cos(wd * t) + z * w0 / wd * np.sin(wd * t))
    return 1 - np.exp(-w0 * t) * (1 + w0 * t)


def spring_num(t, k, d, m=1.0, dt=1 / 600):
    """Independent semi-implicit Euler integration of the same spring, to cross-check the closed form."""
    x, v, out, tt = 0.0, 0.0, [], 0.0
    ts = sorted(np.atleast_1d(t))
    i = 0
    while i < len(ts):
        if tt >= ts[i] - 1e-12:
            out.append(x)
            i += 1
            continue
        v += (k * (1 - x) - d * v) / m * dt
        x += v * dt
        tt += dt
    return np.array(out)


def font(path, size):
    return ImageFont.truetype(str(path), size)


def text_mask(W, H, text, size, path=AMIRI_B, rtl=False, xy=None):
    im = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(im)
    f = font(path, size)
    kw = {"direction": "rtl", "language": "ar"} if rtl else {}
    bb = d.textbbox((0, 0), text, font=f, **kw)
    if xy is None:
        xy = ((W - (bb[2] - bb[0])) / 2 - bb[0], (H - (bb[3] - bb[1])) / 2 - bb[1])
    d.text(xy, text, fill=255, font=f, **kw)
    return np.asarray(im).astype(float)


def chrome_bin():
    for c in ["chromium", "google-chrome", "chromium-browser"]:
        if shutil.which(c):
            return shutil.which(c)
    for p in sorted(Path("/opt/pw-browsers").glob("chromium-*/chrome-linux*/chrome")):
        return str(p)
    raise RuntimeError("no chromium found")


def track(frames, ch=0, thr=60, others=(1, 2), othr=40):
    out = []
    for f in frames:
        m = (f[..., ch] > thr) & np.all([f[..., o] < othr for o in others], axis=0)
        out.append(centroid(m))
    return out


def bbox(mask):
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def resample_closed(pts, n):
    """Resample a closed polyline to n points equally spaced by arc length."""
    p = np.asarray(pts, dtype=float)
    q = np.vstack([p, p[:1]])
    seg = np.hypot(*np.diff(q, axis=0).T)
    s = np.concatenate([[0], np.cumsum(seg)])
    u = np.linspace(0, s[-1], n, endpoint=False)
    x = np.interp(u, s, q[:, 0])
    y = np.interp(u, s, q[:, 1])
    return np.stack([x, y], 1)


def signed_area(p):
    p = np.asarray(p)
    x, y = p[:, 0], p[:, 1]
    return .5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


def poly_regular(n, r, cx=0.0, cy=0.0, rot=-math.pi / 2):
    a = rot + 2 * math.pi * np.arange(n) / n
    return np.stack([cx + r * np.cos(a), cy + r * np.sin(a)], 1)


def star_poly(n, r1, r2, cx=0.0, cy=0.0, rot=-math.pi / 2):
    a = rot + math.pi * np.arange(2 * n) / n
    rr = np.where(np.arange(2 * n) % 2 == 0, r1, r2)
    return np.stack([cx + rr * np.cos(a), cy + rr * np.sin(a)], 1)


def chamfer(a_pts, b_pts):
    from scipy.spatial import cKDTree
    d1, _ = cKDTree(b_pts).query(a_pts)
    d2, _ = cKDTree(a_pts).query(b_pts)
    return float((d1.mean() + d2.mean()) / 2)


def mask_pts(mask):
    ys, xs = np.nonzero(mask)
    return np.stack([xs, ys], 1).astype(float)


def _curl_vel(p, t):
    """Velocity of the analytic stream function psi = sum a_i sin(k_i . p - w_i t + ph_i): v = (dpsi/dy, -dpsi/dx)."""
    ks = np.array([[.0061, .0023], [-.0031, .0057], [.0044, -.0049], [.0097, .0012], [-.0072, -.0036],
                   [.0025, .0089], [-.0014, -.0066]])
    a = np.array([58, 44, 36, 28, 24, 20, 16.0]) * 60
    ph = np.arange(7) * 1.3
    w = np.array([.21, .17, .26, .31, .14, .22, .19])
    arg = p @ ks.T - w * t + ph
    c = np.cos(arg) * a
    vx = (c * ks[:, 1]).sum(-1)
    vy = -(c * ks[:, 0]).sum(-1) - 18.0
    return np.stack([vx, vy], -1)


def lint_particles(spec):
    issues = []
    if spec.get("role") not in ("entity", "sample", "direction", "focus", "quantity->structure", "energy", "flow",
                                "dissolution"):
        issues.append("particles carry no meaning (decorative)")
    if not spec.get("unit"):
        issues.append("unit not stated on screen or in VO")
    if spec.get("count", 0) > spec.get("cap", 600):
        issues.append("count over cap")
    if spec.get("draw_all_edges"):
        issues.append("draws every edge instead of sampling")
    if not spec.get("ends_static"):
        issues.append("does not end on a static frame")
    if spec.get("subject") == "aggregated human harm":
        issues.append("particles avoided for aggregated or uncertain human harm")
    return issues


def _burst_state(t, n=160, seed=20261015, cx=160, cy=90):
    rng = R(seed)
    ang = rng.uniform(0, 2 * math.pi, n)
    sp = rng.uniform(400, 1300, n) * .12          # px travel scaled to a 320x180 frame
    size = rng.uniform(4, 14, n) * .3
    life_len = rng.uniform(.7, 1.0, n)
    teal = rng.random(n) < .7
    life = np.clip(t / life_len, 0, 1)
    d = out_expo(life) * sp
    x = cx + np.cos(ang) * d
    y = cy + np.sin(ang) * d + life * 120 * .12
    alpha = 1 - in_out_cubic(life)
    r = size * (1 - .6 * life)
    return x, y, r, alpha, teal, sp, ang, life


def _confetti(t, n=70, seed=8):
    rng = R(seed)
    x0 = rng.uniform(60, 260, n)
    vx = rng.uniform(-60, 60, n)
    vy = rng.uniform(-520, -380, n)
    ph = rng.uniform(0, 2 * math.pi, n)
    spin = rng.uniform(-4, 4, n)
    g = 750.0
    x = x0 + vx * t + np.sin(3 * t + ph) * 20
    y = 200 + vy * t + .5 * g * t * t
    sy = np.cos(8 * t + ph)
    return x, y, sy, spin * t, ph, g


def _sparkle(size):
    yy, xx = np.mgrid[-size:size + 1, -size:size + 1].astype(float)
    return np.clip(1 - (np.minimum(np.abs(xx), np.abs(yy)) * 2.5 + np.hypot(xx, yy) * .35) / size, 0, 1)


def chrome_shot(wd, name, body, size=(1920, 1080), budget=4000):
    page = Path(wd) / (name + ".html")
    page.write_text(body, encoding="utf-8")
    png = Path(wd) / (name + ".png")
    subprocess.run([chrome_bin(), "--headless=new", "--no-sandbox", "--disable-gpu", "--allow-file-access-from-files",
                    "--hide-scrollbars", "--window-size=%d,%d" % size, "--virtual-time-budget=%d" % budget,
                    "--screenshot=%s" % png, page.as_uri()], capture_output=True, timeout=60, stdin=subprocess.DEVNULL)
    if not png.exists() or png.stat().st_size == 0:
        raise RuntimeError("no screenshot")
    return png


def _project(P, rot_y, W, H, f=2.6, dist=3.2):
    c, s = math.cos(rot_y), math.sin(rot_y)
    x = P[:, 0] * c + P[:, 2] * s
    z = -P[:, 0] * s + P[:, 2] * c
    y = P[:, 1]
    k = f / (dist - z)
    return W / 2 + x * k * H / 2.4, H / 2 - y * k * H / 2.4, z


def _sort_tp(P, bands=24):
    """Order points by (theta band, phi); bands are equal-count quantiles so two sets pair band to band."""
    th = np.arctan2(P[:, 1], np.hypot(P[:, 0], P[:, 2]))
    ph = np.arctan2(P[:, 2], P[:, 0])
    band = np.argsort(np.argsort(th)) * bands // len(P)
    return np.lexsort((ph, band))


def perlin2(x, y, seed=0):
    rng = R(seed)
    p = rng.permutation(256)
    p = np.concatenate([p, p])
    xi, yi = np.floor(x).astype(int) & 255, np.floor(y).astype(int) & 255
    xf, yf = x - np.floor(x), y - np.floor(y)
    fade = lambda t: t * t * t * (t * (t * 6 - 15) + 10)
    u, v = fade(xf), fade(yf)
    ang = rng.uniform(0, 2 * math.pi, 256)
    gx, gy = np.cos(ang), np.sin(ang)

    def gd(h, dx, dy):
        h = h & 255
        return gx[h] * dx + gy[h] * dy
    aa, ab = p[p[xi] + yi], p[p[xi] + yi + 1]
    ba, bb = p[p[xi + 1] + yi], p[p[xi + 1] + yi + 1]
    x1 = gd(aa, xf, yf) + u * (gd(ba, xf - 1, yf) - gd(aa, xf, yf))
    x2 = gd(ab, xf, yf - 1) + u * (gd(bb, xf - 1, yf - 1) - gd(ab, xf, yf - 1))
    return x1 + v * (x2 - x1)


def fbm2(x, y, oct=5, seed=0):
    a, w, s = 0.0, 1.0, 0.0
    for i in range(oct):
        a = a + w * perlin2(x, y, seed + i)
        s += w
        x, y, w = x * 2, y * 2, w * .5
    return a / s


def _streak_angle(img, thr=40):
    """Median orientation (deg from vertical) of the bright streak components in an image."""
    lab, n = label(img.max(-1) > thr, eight=True)
    out = []
    for k in range(1, n + 1):
        ys, xs = np.nonzero(lab == k)
        if len(xs) < 6:
            continue
        w_, v_ = np.linalg.eigh(np.cov(np.stack([xs, ys])))
        ax = v_[:, 1]
        out.append(math.degrees(math.atan2(abs(ax[0]), abs(ax[1]))) * (1 if ax[0] * ax[1] >= 0 else -1))
    return float(np.median(out)) if out else 0.0, len(out)


def fib_sphere(N):
    i = np.arange(N)
    y = 1 - 2 * (i + .5) / N
    r = np.sqrt(1 - y * y)
    th = 2.39996 * i
    return np.stack([r * np.cos(th), y, r * np.sin(th)], 1)


def css_bezier(x1, y1, x2, y2):
    def f(x):
        x = np.atleast_1d(np.asarray(x, dtype=float))
        lo, hi = np.zeros_like(x), np.ones_like(x)
        for _ in range(50):
            mid = (lo + hi) / 2
            cx = 3 * x1 * mid * (1 - mid) ** 2 + 3 * x2 * mid * mid * (1 - mid) + mid ** 3
            lo, hi = np.where(cx < x, mid, lo), np.where(cx < x, hi, mid)
        t = (lo + hi) / 2
        y = 3 * y1 * t * (1 - t) ** 2 + 3 * y2 * t * t * (1 - t) + t ** 3
        return y if y.size > 1 else y.reshape(())
    return f


def align_start(p):
    """Rotate a closed point list so it starts at the topmost vertex (smallest y)."""
    return np.roll(p, -int(np.argmin(p[:, 1] + 1e-6 * p[:, 0])), 0)


def prep_morph(a, b, n=96):
    """Morph law: resample both to n points, same winding (reverse if signed areas differ), aligned start."""
    A, B = resample_closed(a, n), resample_closed(b, n)
    if np.sign(signed_area(A)) != np.sign(signed_area(B)):
        B = B[::-1]
    return align_start(A), align_start(B)


def morph_frames(A, B, ts, dur, ease, W, H, col=(255, 255, 255), extra=None):
    out = []
    for t in ts:
        e = float(ease(np.clip(t / dur, 0, 1)))
        P = A + (B - A) * e
        a = canvas(W, H)
        a[poly_mask(W, H, P)] = col
        if extra:
            extra(a, t, e)
        out.append(a)
    return out


def self_intersections(P):
    n = len(P)
    cnt = 0
    for i in range(n):
        p1, p2 = P[i], P[(i + 1) % n]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            q1, q2 = P[j], P[(j + 1) % n]
            d = lambda a, b, c: (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            if d(p1, p2, q1) * d(p1, p2, q2) < 0 and d(q1, q2, p1) * d(q1, q2, p2) < 0:
                cnt += 1
    return cnt


def superellipse(n, R, cx, cy, k=180):
    th = np.linspace(0, 2 * math.pi, k, endpoint=False)
    c, s = np.cos(th), np.sin(th)
    return np.stack([cx + np.sign(c) * np.abs(c) ** (2 / n) * R, cy + np.sign(s) * np.abs(s) ** (2 / n) * R], 1)


def polar_shape(a, b, k, p, cx, cy, n=240):
    th = np.linspace(0, 2 * math.pi, n, endpoint=False)
    r = a + b * np.abs(np.cos(k * th / 2)) ** p
    return np.stack([cx + r * np.cos(th), cy + r * np.sin(th)], 1), r


def goo(alpha, sd=10.0):
    """feGaussianBlur(stdDeviation) then feColorMatrix alpha row (0 0 0 18 -7), on alpha in 0..1."""
    from scipy.ndimage import gaussian_filter
    return np.clip(18 * gaussian_filter(alpha, sd) - 7, 0, 1)


def checkmark(cx, cy, s, n=60):
    P = np.array([[cx - s, cy], [cx - s * .3, cy + s * .7], [cx + s, cy - s * .8]])
    seg = np.hypot(*np.diff(P, axis=0).T)
    u = np.linspace(0, seg.sum(), n)
    cum = np.concatenate([[0], np.cumsum(seg)])
    return np.stack([np.interp(u, cum, P[:, 0]), np.interp(u, cum, P[:, 1])], 1)


def ring_gap_angle(img, cx, cy, r, thr=100):
    """Circular-mean angle (rad, y down) of the unlit samples on a ring of radius r."""
    th = np.linspace(0, 2 * math.pi, 720, endpoint=False)
    on = np.array([img[int(round(cy + r * math.sin(a))), int(round(cx + r * math.cos(a)))].max() > thr for a in th])
    off = ~on
    if not off.any() or off.all():
        return None
    return float(np.angle(np.exp(1j * th[off]).mean()) % (2 * math.pi))


def lint_style(spec):
    issues = []
    if len(set(spec["primitives"])) > 3:
        issues.append("more than three primitives")
    if len(set(spec["colours"])) > 2:
        issues.append("more than two colours + background")
    if any(r not in (0, 8, 24, 50) for r in spec["radii"]):
        issues.append("radius off the 0/8/24/50% scale")
    if any(s not in (2, 4, 8) for s in spec["strokes"]):
        issues.append("stroke off the 2/4/8 scale")
    if spec["negative_space"] < .3:
        issues.append("negative space under 30%")
    return issues


def nested_radius(outer, gap):
    inner = outer - gap
    return inner if gap < 32 and inner > 2 else outer


def overshoots(y, target, tol):
    """Number of local extrema beyond the target by more than tol (an overshoot or a rebound)."""
    d = np.asarray(y) - target
    ext = [i for i in range(1, len(d) - 1) if (d[i] > d[i - 1] and d[i] >= d[i + 1]) or (d[i] < d[i - 1] and d[i] <= d[i + 1])]
    return sum(1 for i in ext if abs(d[i]) > tol and i > 2)
