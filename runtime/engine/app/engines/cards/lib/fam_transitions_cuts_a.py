"""Helpers of runners/fam_transitions_cuts_a.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from pathlib import Path
from .core import check
from .core import fx
import json
import math
import numpy as np
import subprocess


W, H = 192, 108


K = W / 1920.0


YY, XX = np.mgrid[0:H, 0:W].astype(float)


CX, CY = (W - 1) / 2.0, (H - 1) / 2.0


BLUE_A, BLUE_B = 30.0, 225.0


def c01(x):
    return float(min(1.0, max(0.0, x)))


def p_in(n):
    return lambda x: c01(x) ** (n + 1)


def p_out(n):
    return lambda x: 1 - (1 - c01(x)) ** (n + 1)


def p_io(n):
    def f(x):
        x = c01(x)
        return 0.5 * (2 * x) ** (n + 1) if x < 0.5 else 1 - 0.5 * (2 - 2 * x) ** (n + 1)
    return f


lin = c01


sine_io = lambda x: 0.5 - 0.5 * math.cos(math.pi * c01(x))


def smooth(e0, e1, x):
    t = c01((x - e0) / (e1 - e0)) if e1 != e0 else float(x >= e0)
    return t * t * (3 - 2 * t)


def prog(t, start, dur, ease=lin):
    return ease((t - start) / dur) if dur > 0 else float(t >= start)


def coord(blue):
    img = np.empty((H, W, 3))
    img[..., 0] = XX * 255.0 / (W - 1)
    img[..., 1] = YY * 255.0 / (H - 1)
    img[..., 2] = blue
    return img


A0, B0 = coord(BLUE_A), coord(BLUE_B)


def hexc(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], float)


def solid(c):
    c = hexc(c) if isinstance(c, str) else np.asarray(c, float)
    return np.broadcast_to(c, (H, W, 3)).astype(float).copy()


def sample(img, sx, sy, fill=None):
    """Bilinear sample img at float source coords; outside -> fill colour (or clamped edge when fill is None)."""
    x0 = np.floor(sx)
    y0 = np.floor(sy)
    fx_ = (sx - x0)[..., None]
    fy_ = (sy - y0)[..., None]
    x0c = np.clip(x0, 0, W - 1).astype(int)
    x1c = np.clip(x0 + 1, 0, W - 1).astype(int)
    y0c = np.clip(y0, 0, H - 1).astype(int)
    y1c = np.clip(y0 + 1, 0, H - 1).astype(int)
    out = (img[y0c, x0c] * (1 - fx_) * (1 - fy_) + img[y0c, x1c] * fx_ * (1 - fy_)
           + img[y1c, x0c] * (1 - fx_) * fy_ + img[y1c, x1c] * fx_ * fy_)
    if fill is not None:
        inside = ((sx >= -0.5) & (sx <= W - 0.5) & (sy >= -0.5) & (sy <= H - 0.5))[..., None]
        out = np.where(inside, out, np.asarray(fill, float))
    return out


def affine(img, s=1.0, sy_=None, cx=CX, cy=CY, dx=0.0, dy=0.0, rot=0.0, fill=None):
    """Scale (s, optional separate y scale) and rotate about (cx, cy), then translate by (dx, dy)."""
    syy = s if sy_ is None else sy_
    u, v = XX - cx - dx, YY - cy - dy
    c, n = math.cos(-rot), math.sin(-rot)
    ur, vr = u * c - v * n, u * n + v * c
    return sample(img, ur / max(s, 1e-6) + cx, vr / max(syy, 1e-6) + cy, fill)


def shift(img, dx=0.0, dy=0.0, fill=None):
    return sample(img, XX - dx, YY - dy, fill)


def blur(img, sigma):
    if sigma <= 0.05:
        return img.copy()
    if fx.have("cv2"):
        import cv2
        return cv2.GaussianBlur(img.astype(np.float32), (0, 0), sigma, borderType=cv2.BORDER_REPLICATE).astype(float)
    from scipy.ndimage import gaussian_filter
    return np.stack([gaussian_filter(img[..., c], sigma, mode="nearest") for c in range(3)], -1)


def hblur(img, length):
    """Horizontal box (motion) blur of `length` px."""
    L = int(round(length))
    if L <= 1:
        return img.copy()
    pad = np.pad(img, ((0, 0), (L, L), (0, 0)), mode="edge")
    cs = np.cumsum(pad, axis=1)
    cs = np.concatenate([np.zeros((H, 1, 3)), cs], axis=1)
    a = L // 2
    idx = np.arange(W) + L
    return (cs[:, idx + (L - a)] - cs[:, idx - a]) / L


def mix(a, b, m):
    m = np.asarray(m, float)
    if m.ndim == 2:
        m = m[..., None]
    return a * (1 - m) + b * m


def disc(cx, cy, r, feather=0.75):
    d = np.hypot(XX - cx, YY - cy)
    return np.clip((r - d) / max(feather, 1e-6) + 0.5, 0, 1)


def screen(base, over):
    return 255 - (255 - base) * (255 - over) / 255.0


def lum(fr):
    return 0.2126 * fr[..., 0] + 0.7152 * fr[..., 1] + 0.0722 * fr[..., 2]


def text_layer(text, size=40, color=(255, 255, 255), pos=None, bg=None):
    """PIL text -> (rgb, alpha) arrays at fixture size."""
    from PIL import Image, ImageDraw, ImageFont
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0) if bg is None else tuple(int(v) for v in bg) + (255,))
    dr = ImageDraw.Draw(im)
    try:
        font = ImageFont.load_default(size=size)
    except TypeError:
        font = ImageFont.load_default()
    x, y = pos if pos else (W / 2, H / 2)
    dr.text((x, y), text, fill=tuple(int(v) for v in color) + (255,), font=font, anchor="mm")
    a = np.asarray(im, float)
    return a[..., :3], a[..., 3] / 255.0


def noise(seed, cells=6, octaves=3, ridged=False):
    """Value-noise fBm on the fixture grid (deterministic); rank-normalised to a uniform 0..1 field."""
    rng = np.random.default_rng(seed)
    tot = np.zeros((H, W))
    amp = 1.0
    for o in range(octaves):
        n = cells * 2 ** o
        g = rng.random((n + 2, n + 2))
        gx, gy = XX / W * n, YY / W * n
        x0, y0 = gx.astype(int), gy.astype(int)
        tx, ty = gx - x0, gy - y0
        tx, ty = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty)
        v = (g[y0, x0] * (1 - tx) * (1 - ty) + g[y0, x0 + 1] * tx * (1 - ty)
             + g[y0 + 1, x0] * (1 - tx) * ty + g[y0 + 1, x0 + 1] * tx * ty)
        if ridged:
            v = 1 - np.abs(2 * v - 1)
        tot += amp * v
        amp *= 0.5
    r = tot.ravel().argsort().argsort().reshape(H, W)
    return (r + 0.5) / r.size


def write_video(frames, path, fps):
    arr = np.clip(np.rint(np.stack(frames)), 0, 255).astype(np.uint8)
    done = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H),
                           "-r", str(fps), "-i", "-", "-c:v", "libx264rgb", "-crf", "0", "-preset", "ultrafast",
                           str(path)], input=arr.tobytes(), capture_output=True, timeout=120)
    if done.returncode:
        raise RuntimeError(done.stderr.decode(errors="replace")[-300:])
    return Path(path)


def film(wd, name, frame_fn, seconds, fps):
    """Render frame_fn(t) for t = i/fps, i < seconds*fps (+1 so the end state is a frame); return (path, frames, ts)."""
    n = int(round(seconds * fps)) + 1
    ts = [i / fps for i in range(n)]
    path = write_video([frame_fn(t) for t in ts], Path(wd) / (name + ".mp4"), fps)
    frs = fx.frames(path, (W, H))
    if len(frs) != n:
        raise RuntimeError("frame count %d != %d" % (len(frs), n))
    return path, frs, ts


def at(ts, t):
    return int(np.argmin(np.abs(np.asarray(ts) - t)))


def save_plan(wd, name, obj):
    p = Path(wd) / (name + ".json")
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    return p


def bwt(fr):
    return np.clip((fr[..., 2] - BLUE_A) / (BLUE_B - BLUE_A), 0, 1)


def fracb(fr, mask=None):
    m = bwt(fr) > 0.5
    return float(m[mask].mean() if mask is not None else m.mean())


def srcx(fr):
    return fr[..., 0] * (W - 1) / 255.0


def srcy(fr):
    return fr[..., 1] * (H - 1) / 255.0


def mad(a, b):
    return float(np.mean(np.abs(np.asarray(a, float) - np.asarray(b, float))))


def xshift(fr, sel=None):
    """Median of (pixel x - source x) over selected pixels: + means content moved right."""
    d = XX - srcx(fr)
    return float(np.median(d[sel] if sel is not None else d))


def yshift(fr, sel=None):
    d = YY - srcy(fr)
    return float(np.median(d[sel] if sel is not None else d))


def scale_est(fr, sel=None):
    """Content scale about the centre from the coordinate code: slope of pixel x against source x."""
    sel = np.ones((H, W), bool) if sel is None else sel
    band = sel & (np.abs(YY - CY) < H * 0.3) & (np.abs(XX - CX) < W * 0.3)
    sx = srcx(fr)[band]
    if sx.size < 10 or np.ptp(sx) < 1e-6:
        return float("nan")
    return float(np.polyfit(sx, XX[band], 1)[0])


def scale_inv(fr, sel=None):
    """Opacity-invariant scale about the centre: fit red = m x + c; the value at the centre gives opacity x code
    scale, so s = (red(CX) / CX) / m."""
    sel = np.ones((H, W), bool) if sel is None else sel
    band = sel & (np.abs(YY - CY) < H * 0.3) & (np.abs(XX - CX) < W * 0.3)
    if band.sum() < 10:
        return float("nan")
    m, c = np.polyfit(XX[band], fr[..., 0][band], 1)
    return float(((m * CX + c) / CX) / m) if abs(m) > 1e-9 else float("nan")


def b_width(fr, row=None):
    """Columns showing B on a row (B weight > .5)."""
    r = int(round(CY)) if row is None else row
    return int((bwt(fr)[r] > 0.5).sum())


def chan_offset(fr):
    """Horizontal offset of the red channel against the green-coded geometry: median(x - red source x) on the
    interior (0 when channels are aligned)."""
    inner = (XX > 12) & (XX < W - 12)
    return float(np.median((XX - srcx(fr))[inner]))


def near(name, m, e, tol):
    ok = m == m and abs(m - e) <= tol
    return check(name, ok, m, "%s +- %s" % (e, tol))


def neg(name, m, e, tol):
    ok = not (m == m and abs(m - e) <= tol)
    return check("negative control: " + name, ok, m, "not within %s +- %s" % (e, tol))


def ends(frs, a, b, tol=1.5, name="transition"):
    return [check("%s: first frame is scene A" % name, mad(frs[0], a) < tol, mad(frs[0], a), "< %s" % tol),
            check("%s: last frame is scene B" % name, mad(frs[-1], b) < tol, mad(frs[-1], b), "< %s" % tol)]


def _sm(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def sh_chroma(a, b, p, radial=False, amp=0.035 * W):
    base = mix(a, b, p)
    d = amp * math.sin(math.pi * p)
    ux, uy = ((XX - CX) / (W / 2), (YY - CY) / (W / 2)) if radial else (np.ones((H, W)), np.zeros((H, W)))
    out = base.copy()
    out[..., 0] = sample(base, XX - d * ux, YY - d * uy)[..., 0]
    out[..., 2] = sample(base, XX + d * ux, YY + d * uy)[..., 2]
    return out


def pr_chroma(frs, ps, hc, radial=False, amp=0.035 * W):
    i = int(np.argmin(np.abs(np.asarray(ps) - 0.5)))
    d = amp * math.sin(math.pi * ps[i])
    if radial:
        sel = (XX > 0.72 * W) & (XX < 0.9 * W)
        e = d * float(np.mean((XX[sel] - CX) / (W / 2)))
        m = float(np.median((XX - srcx(frs[i]))[sel]))
        sel_l = (XX < 0.28 * W) & (XX > 0.1 * W)
        ml = float(np.median((XX - srcx(frs[i]))[sel_l]))
        return [near("red channel pushed outward on the right (px)", m, e, 0.6),
                near("red channel pushed outward on the left (mirror)", ml, -e, 0.6),
                near("channels aligned at the end", chan_offset(frs[-1]), 0.0, 0.3),
                neg("red-channel offset on the hard cut", float(np.median((XX - srcx(hc(i)))[sel])), e, 0.6)]
    m = chan_offset(frs[i])
    return [near("red channel offset at peak (px)", m, d, 0.6), near("aligned at the end", chan_offset(frs[-1]), 0, 0.3),
            neg("red-channel offset on the hard cut", chan_offset(hc(i)), d, 0.6)]


ZK = 0.5


def _zoomblur(img, s, amt):
    return np.mean([affine(img, s * (1 + 0.03 * j * amt)) for j in range(6)], axis=0)


def _zoom_scales(s, amt):
    return 1.0 / np.mean([1.0 / (s * (1 + 0.03 * j * amt)) for j in range(6)])


def sh_zoom(a, b, p):
    amt = math.sin(math.pi * p)
    sa, sb = 1 + ZK * 2 * min(p, 0.5), 1 + ZK * 2 * min(1 - p, 0.5)
    m = smooth(0.35, 0.65, p)
    za = _zoomblur(a, sa, amt) if m < 1 else a
    zb = _zoomblur(b, sb, amt) if m > 0 else b
    return mix(za, zb, m)


def pr_zoom(frs, ps, hc):
    ps = np.asarray(ps)
    i, j = int(np.argmin(np.abs(ps - 0.25))), int(np.argmin(np.abs(ps - 0.75)))
    ea = _zoom_scales(1 + ZK * 2 * min(ps[i], 0.5), math.sin(math.pi * ps[i]))
    eb = _zoom_scales(1 + ZK * 2 * min(1 - ps[j], 0.5), math.sin(math.pi * ps[j]))
    return [near("scene A zoomed in at p=%.2f (scale)" % ps[i], scale_est(frs[i]), ea, 0.03),
            check("frame at p=%.2f is still scene A" % ps[i], fracb(frs[i]) < 0.02, fracb(frs[i]), "< 0.02"),
            near("scene B arrives zoomed at p=%.2f (scale)" % ps[j], scale_est(frs[j]), eb, 0.03),
            neg("zoom scale of the hard cut", scale_est(hc(i)), ea, 0.03)]


def sh_crosswarp(a, b, p):
    x = _sm(0, 1, p * 2 + XX / (W - 1) - 1)
    sa = sample(a, CX + (XX - CX) * (1 - x), CY + (YY - CY) * (1 - x))
    sb = sample(b, CX + (XX - CX) * x, CY + (YY - CY) * x)
    return mix(sa, sb, x)


def pr_crosswarp(frs, ps, hc):
    i = int(np.argmin(np.abs(np.asarray(ps) - 0.5)))
    exp = _sm(0, 1, ps[i] * 2 + XX[0] / (W - 1) - 1)
    row = bwt(frs[i])[int(CY)]
    err = float(np.mean(np.abs(row - exp)))
    # A is drawn shrunk toward the centre by (1 - x): at column 0.25 W the A source sits closer to the centre
    c = int(0.25 * W)
    xa = float(_sm(0, 1, ps[i] * 2 + c / (W - 1) - 1))
    exp_src = (1 - xa) * (CX + (c - CX) * (1 - xa)) + xa * (CX + (c - CX) * xa)   # blend of both warped samples
    return [check("B weight follows smoothstep(2p+u-1) across x", err < 0.02, err, "< 0.02"),
            near("A and B sampled at their warped coordinates (col 0.25W)", float(srcx(frs[i])[int(CY), c]), exp_src, 0.8),
            neg("B-weight profile error of the hard cut", float(np.mean(np.abs(bwt(hc(i))[int(CY)] - exp))), 0.0, 0.02)]


def _warped_noise():
    n1, q, r = noise(11, 4, 3), noise(12, 3, 2), noise(13, 3, 2)
    nn = sample(np.repeat(n1[..., None], 3, -1), XX + 24 * (q - 0.5), YY + 24 * (r - 0.5))[..., 0]
    rk = nn.ravel().argsort().argsort().reshape(H, W)
    return (rk + 0.5) / rk.size


DWN = _warped_noise()


RGN = noise(21, 5, 3, ridged=True)


EDGE = 0.05


def _thresh(field, p, e=EDGE):
    return np.clip((p * (1 + 2 * e) - e - field) / (2 * e) + 0.5, 0, 1)


def sh_domain(a, b, p):
    return mix(a, b, _thresh(DWN, p))


def pr_domain(frs, ps, hc, field=None):
    field = DWN if field is None else field
    i = int(np.argmin(np.abs(np.asarray(ps) - 0.3)))
    exp = ps[i] * (1 + 2 * EDGE) - EDGE
    m = bwt(frs[i]) > 0.5
    coh = float(np.corrcoef(m[:, :-1].ravel().astype(float), m[:, 1:].ravel().astype(float))[0, 1])
    return [near("B area fraction at p=%.2f" % ps[i], fracb(frs[i]), exp, 0.02),
            check("dissolve mask is spatially coherent (warped noise, not white noise)", coh > 0.6, coh, "> 0.6"),
            neg("B area fraction of the hard cut", fracb(hc(i)), exp, 0.02)]


def sh_flashwhite(a, b, p):
    white = solid((255, 255, 255))
    return mix(a, white, 2 * p) if p < 0.5 else mix(white, b, 2 * p - 1)


def pr_flashwhite(frs, ps, hc):
    ps = np.asarray(ps)
    i = int(np.argmin(np.abs(ps - 0.5)))
    j = int(np.argmin(np.abs(ps - 0.25)))
    e_j = float(np.mean(lum(A0))) + (255 - float(np.mean(lum(A0)))) * 2 * ps[j]
    return [check("frame at p=%.2f is near white" % ps[i], float(lum(frs[i]).mean()) > 255 - 255 * abs(2 * ps[i] - 1) - 3,
                  float(lum(frs[i]).mean()), "> %.1f" % (255 - 255 * abs(2 * ps[i] - 1) - 3)),
            near("quarter frame lifted toward white (mean luma)", float(lum(frs[j]).mean()), e_j, 2.0),
            neg("hard-cut frame is not white (mean luma)", float(lum(hc(i)).mean()), 255.0, 255 * abs(2 * ps[i] - 1) + 3)]


def _h(*k):
    v = 0
    for x in k:
        v = (v * 1103515245 + int(x) * 2654435761 + 12345) & 0xFFFFFFFF
    return ((v ^ (v >> 13)) * 1274126177 & 0xFFFFFFFF) / 4294967295.0


def sh_glitch(a, b, p, rows=60, bx=12, by=8, shift_=0.035):
    g = math.sin(math.pi * p)
    base = mix(a, b, p)
    step = int(p * 12)
    band = (YY * rows / H).astype(int)
    dxr = np.vectorize(lambda k: (_h(k, step, 1) - 0.5) * 2 * 0.08 * W)(np.arange(rows))[band]
    on = np.vectorize(lambda k: _h(k, step, 2) < 0.5)(np.arange(rows))[band]
    bxi, byi = (XX * bx / W).astype(int), (YY * by / H).astype(int)
    boff = np.vectorize(lambda u, v: (_h(u, v, step, 3) - 0.5) * 0.1 * W if _h(u, v, step, 4) < 0.25 else 0.0)(bxi, byi)
    sx = XX - g * (dxr * on + boff)
    out = sample(base, sx, YY)
    rs = shift_ * W * g
    out[..., 0] = sample(base, sx - rs, YY)[..., 0]
    scan = 1 - 0.15 * g * ((YY.astype(int) % 2) == 0)
    out = out * scan[..., None]
    levels = int(round(256 - 248 * g ** 4))
    q = 255.0 / max(levels - 1, 1)
    return np.round(out / q) * q if levels < 256 else out


def pr_glitch(frs, ps, hc):
    ps = np.asarray(ps)
    i = int(np.argmin(np.abs(ps - 0.25)))
    j = int(np.argmin(np.abs(ps - 0.5)))
    rowdisp = np.abs(np.median(XX - srcx(frs[i]), axis=1))
    frac = float(np.mean(rowdisp > 1.0))
    lev = int(round(256 - 248 * math.sin(math.pi * ps[j]) ** 4))
    uniq = len(np.unique(frs[j][..., 1]))
    hc_rows = float(np.mean(np.abs(np.median(XX - srcx(hc(i)), axis=1)) > 1.0))
    return [check("scan rows displaced at p=%.2f (fraction of rows > 1 px)" % ps[i], frac > 0.25, frac, "> 0.25"),
            check("colour quantised at the peak (unique green levels <= %d)" % lev, uniq <= lev, uniq, "<= %d" % lev),
            check("clean B at the end (no displaced rows)",
                  float(np.mean(np.abs(np.median(XX - srcx(frs[-1]), axis=1)) > 1.0)) == 0.0, 0.0, 0.0),
            neg("fraction of displaced rows on the hard cut", hc_rows, 0.6, 0.35)]


LENS_E = 0.22 * H


def sh_lens(a, b, p):
    E = LENS_E * math.sin(math.pi * p)
    u, v = XX - CX, YY - CY
    r = np.maximum(np.hypot(u, v), 1e-3)
    f = 1 - (E * E) / (r * r)
    return mix(sample(a, CX + u * f, CY + v * f), sample(b, CX + u * f, CY + v * f), p)


def _ring_e2(fr, r0, r1):
    r = np.hypot(XX - CX, YY - CY)
    sel = (r > r0) & (r < r1)
    rs = np.hypot(srcx(fr) - CX, srcy(fr) - CY)
    return float(np.median(((r - rs) * r)[sel]))


def pr_lens(frs, ps, hc):
    i = int(np.argmin(np.abs(np.asarray(ps) - 0.5)))
    E2 = (LENS_E * math.sin(math.pi * ps[i])) ** 2
    e_in, e_out = _ring_e2(frs[i], 34, 40), _ring_e2(frs[i], 46, 52)
    return [near("deflection x radius at r~37 equals E^2 (1/r point-mass law)", e_in, E2, 0.08 * E2),
            near("deflection x radius at r~49 equals E^2", e_out, E2, 0.08 * E2),
            near("no deflection at the end", _ring_e2(frs[-1], 34, 40), 0.0, 0.015 * E2),
            neg("deflection x radius on the hard cut", _ring_e2(hc(i), 34, 40), E2, 0.08 * E2)]


LEAK = np.array([255.0, 170.0, 80.0])


def _leak_cx(p):
    return W * (-0.2 + 1.4 * p)


def sh_leak(a, b, p):
    base = mix(a, b, p)
    g = np.exp(-(((XX - _leak_cx(p)) / (0.3 * W)) ** 2 + ((YY - 0.4 * H) / (0.5 * H)) ** 2))
    over = LEAK * (0.85 * math.sin(math.pi * p) * g)[..., None]
    return screen(base, over)


def pr_leak(frs, ps, hc):
    ps = np.asarray(ps)
    out = []
    cents = []
    for target in (0.35, 0.65):
        i = int(np.argmin(np.abs(ps - target)))
        gain = lum(frs[i]) - lum(mix(A0, B0, ps[i]))
        colg = np.clip(gain.mean(axis=0), 0, None)
        cents.append((float((colg * XX[0]).sum() / max(colg.sum(), 1e-6)), _leak_cx(ps[i]), i))
    for c, e, i in cents:
        out.append(near("light-leak centre at p=%.2f (column)" % ps[i], c, e, 0.08 * W))
    i = int(np.argmin(np.abs(ps - 0.5)))
    d = frs[i] - mix(A0, B0, ps[i])
    rg, bg = float(d[..., 0].mean()), float(d[..., 2].mean())
    out.append(check("leak is warm (red gain > blue gain) at the peak", rg > bg + 5, [rg, bg], "red > blue + 5"))
    out.append(check("red channel lifted by the leak at the peak (mean gain > 5)", rg > 5, rg, "> 5"))
    hd = hc(i) - mix(A0, B0, ps[i])
    out.append(neg("red-channel lift on the hard cut", float(hd[..., 0].mean()), 30.0, 25.0))
    return out


BURN_BAND = 0.06


ORANGE = np.array([255.0, 120.0, 20.0])


def sh_burn(a, b, p):
    if p <= 0 or p >= 1:
        return (a if p <= 0 else b).copy()
    p2 = p * (1 + BURN_BAND)
    out = mix(a, b, (RGN < p2 - BURN_BAND) * 1.0)
    out[(RGN >= p2 - BURN_BAND) & (RGN < p2)] = ORANGE
    return out


def pr_burn(frs, ps, hc):
    i = int(np.argmin(np.abs(np.asarray(ps) - 0.4)))
    p2 = ps[i] * (1 + BURN_BAND)
    fb = fracb(frs[i])
    orange = (np.abs(frs[i] - ORANGE).max(axis=-1) < 6)
    edge_ok = float(np.mean(orange))
    return [near("burned-through (B) area at p=%.2f" % ps[i], fb, max(p2 - BURN_BAND, 0), 0.01),
            near("glowing orange burn front covers the ridged band", edge_ok, BURN_BAND, 0.01),
            neg("orange burn-front area on the hard cut", float(np.mean(np.abs(hc(i) - ORANGE).max(axis=-1) < 6)),
                BURN_BAND, 0.01)]


RIP_A, RIP_L = 0.025 * W, 0.12 * W


def _rip_d(r, p):
    return RIP_A * math.sin(math.pi * p) * np.sin(2 * math.pi * r / RIP_L - 4 * math.pi * p)


def sh_ripple(a, b, p):
    u, v = XX - CX, YY - CY
    r = np.maximum(np.hypot(u, v), 1e-3)
    f = (r - _rip_d(r, p)) / r
    return mix(sample(a, CX + u * f, CY + v * f), sample(b, CX + u * f, CY + v * f), p)


def _radial_disp(fr):
    r = np.hypot(XX - CX, YY - CY)
    return r, r - np.hypot(srcx(fr) - CX, srcy(fr) - CY)


def pr_ripple(frs, ps, hc):
    i = int(np.argmin(np.abs(np.asarray(ps) - 0.5)))
    r, d = _radial_disp(frs[i])
    sel = (r > 4) & (r < 50)
    exp = _rip_d(r, ps[i])
    corr = float(np.corrcoef(d[sel], exp[sel])[0, 1])
    amp = float(np.percentile(np.abs(d[sel]), 98))
    r2, d2 = _radial_disp(hc(i))
    return [check("radial displacement follows sin(2 pi r / lambda) (correlation)", corr > 0.97, corr, "> 0.97"),
            near("ripple amplitude (px)", amp, RIP_A * math.sin(math.pi * ps[i]), 0.5),
            neg("ripple amplitude of the hard cut", float(np.percentile(np.abs(d2[sel]), 98)),
                RIP_A * math.sin(math.pi * ps[i]), 0.5)]


IRIS_MAX = math.hypot(W, H) / 2 + 1


def sh_iris(a, b, p):
    return mix(a, b, disc(CX, CY, IRIS_MAX * p))


def pr_iris(frs, ps, hc):
    i = int(np.argmin(np.abs(np.asarray(ps) - 0.3)))
    e = IRIS_MAX * ps[i]
    m = b_width(frs[i]) / 2.0
    vh = int((bwt(frs[i])[:, int(CX)] > 0.5).sum()) / 2.0
    return [near("iris radius along the centre row (SDF circle)", m, e, 1.0),
            near("iris radius along the centre column (round, not an ellipse)", vh, e, 1.0),
            neg("B half-width of the hard cut", b_width(hc(i)) / 2.0, e, 1.0)]


SW_S, SW_R = 2.5, 0.45 * W


def _sw_theta(r, p):
    return SW_S * math.sin(math.pi * p) * np.clip(1 - r / SW_R, 0, 1) ** 2


def sh_swirl(a, b, p):
    u, v = XX - CX, YY - CY
    r = np.hypot(u, v)
    th = -_sw_theta(r, p)
    c, s = np.cos(th), np.sin(th)
    sx, sy = CX + u * c - v * s, CY + u * s + v * c
    return mix(sample(a, sx, sy), sample(b, sx, sy), p)


def _ang_disp(fr, r0, r1):
    u, v = XX - CX, YY - CY
    r = np.hypot(u, v)
    sel = (r > r0) & (r < r1)
    da = np.arctan2(srcy(fr) - CY, srcx(fr) - CX) - np.arctan2(v, u)
    da = (da + np.pi) % (2 * np.pi) - np.pi
    return float(np.median(da[sel]))


def pr_swirl(frs, ps, hc):
    i = int(np.argmin(np.abs(np.asarray(ps) - 0.5)))
    e20 = -float(_sw_theta(np.array(20.0), ps[i]))
    e40 = -float(_sw_theta(np.array(40.0), ps[i]))
    return [near("swirl angle at r=20 px (rad)", _ang_disp(frs[i], 18, 22), e20, 0.06),
            near("swirl angle at r=40 px falls off as (1-r/R)^2 (rad)", _ang_disp(frs[i], 38, 42), e40, 0.06),
            neg("swirl angle of the hard cut", _ang_disp(hc(i), 18, 22), e20, 0.06)]


TH_A, TH_L = 0.03 * W, H / 4.0


def _th_dx(y, p):
    return TH_A * math.sin(math.pi * p) * np.sin(2 * math.pi * y / TH_L + 8 * p)


def sh_thermal(a, b, p):
    sx = XX - _th_dx(YY, p)
    return mix(sample(a, sx, YY), sample(b, sx, YY), p)


def pr_thermal(frs, ps, hc):
    i = int(np.argmin(np.abs(np.asarray(ps) - 0.5)))
    inner = (XX > 10) & (XX < W - 10)
    rows = np.array([np.median((XX - srcx(frs[i]))[y][inner[y]]) for y in range(H)])
    exp = _th_dx(np.arange(H, dtype=float), ps[i])
    err = float(np.max(np.abs(rows - exp)))
    hrows = np.array([np.median((XX - srcx(hc(i)))[y][inner[y]]) for y in range(H)])
    return [check("per-row heat-haze shift matches the sine (max error px)", err < 0.7, err, "< 0.7"),
            near("haze amplitude (px)", float(np.max(np.abs(rows))), TH_A * math.sin(math.pi * ps[i]), 0.7),
            neg("haze amplitude of the hard cut", float(np.max(np.abs(hrows))), TH_A * math.sin(math.pi * ps[i]), 0.7)]


WHIP_BLUR = 0.3 * W


def sh_whip(a, b, p, blur_max=WHIP_BLUR):
    o = p * W
    pos = XX + o
    img = np.where((pos < W)[..., None], sample(a, pos, YY), sample(b, pos - W, YY))
    return hblur(img, blur_max * math.sin(math.pi * p))


def pr_whip(frs, ps, hc, blur_max=WHIP_BLUR):
    i = int(np.argmin(np.abs(np.asarray(ps) - 0.25)))
    o, L = ps[i] * W, blur_max * math.sin(math.pi * ps[i])
    sel = (XX > L / 2 + 3) & (XX < W - o - L / 2 - 3)
    row = bwt(frs[i])[int(CY)]
    width = int(((row > 0.1) & (row < 0.9)).sum())
    return [near("camera pan offset at p=%.2f (A moved left, px)" % ps[i], xshift(frs[i], sel), -o, 0.8),
            near("directional blur smears the A|B seam over ~0.8 L px", width, 0.8 * L, 3.0),
            neg("pan offset of the hard cut", xshift(hc(i), sel), -o, 0.8)]


SHADERS = {
    "chromatic-split": (sh_chroma, pr_chroma),
    "chromatic-radial-split": (lambda a, b, p: sh_chroma(a, b, p, radial=True), lambda f, p, h: pr_chroma(f, p, h, radial=True)),
    "cinematic-zoom": (sh_zoom, pr_zoom),
    "cross-warp-morph": (sh_crosswarp, pr_crosswarp),
    "domain-warp": (sh_domain, pr_domain),
    "flash-through-white": (sh_flashwhite, pr_flashwhite),
    "glitch": (sh_glitch, pr_glitch),
    "gravitational-lens": (sh_lens, pr_lens),
    "light-leak": (sh_leak, pr_leak),
    "ridged-burn": (sh_burn, pr_burn),
    "ripple-waves": (sh_ripple, pr_ripple),
    "sdf-iris": (sh_iris, pr_iris),
    "swirl-vortex": (sh_swirl, pr_swirl),
    "thermal-distortion": (sh_thermal, pr_thermal),
    "whip-pan": (sh_whip, pr_whip),
}


SHADER_MODES = {
    "quick": (0.0, 0.7, 0.7, 30, lin),            # hyperframes registry id, page-side compositing
    "block": (1.0, 2.0, 4.0, 10, p_io(1)),        # 4 s composition, progress window 1..3 s quadInOut
    "webgl": (4.0, 0.7, 5.0, 20, lin),            # transitions array {time: 4.0, duration: 0.7}
}


def shader_card(wd, key, mode, card_id):
    fn, probe = SHADERS[key]
    T0, D, total, fps, ease = SHADER_MODES[mode]
    pf = lambda t: prog(t, T0, D, ease)           # noqa: E731
    path, frs, ts = film(wd, key, lambda t: fn(A0, B0, pf(t)), total, fps)
    ps = [pf(t) for t in ts]
    hc = lambda i: A0 if ps[i] < 0.5 else B0      # noqa: E731  the unprocessed hard cut at the same frame
    checks = ends(frs, A0, B0, name=key)
    if mode != "quick":
        pre = [i for i, t in enumerate(ts) if t < T0 - 1e-9]
        post = [i for i, t in enumerate(ts) if t > T0 + D + 1e-9]
        checks.append(check("scene A holds untouched before %.1f s" % T0, max(mad(frs[i], A0) for i in pre) < 1.0,
                            max(mad(frs[i], A0) for i in pre), "< 1"))
        if post:
            checks.append(check("scene B holds after %.1f s" % (T0 + D), max(mad(frs[i], B0) for i in post) < 1.0,
                                max(mad(frs[i], B0) for i in post), "< 1"))
    if mode == "block":
        i = at(ts, 1.5)
        checks.append(near("progress at t=1.5 s follows quadInOut (0.125)", ps[i], 0.125, 1e-6))
    checks += probe(frs, ps, hc)
    plan = save_plan(wd, "shader_" + key, {"card": card_id, "shader": key, "mode": mode, "start": T0, "duration": D,
                                           "fps": fps, "engine": "numpy per-pixel port of the named effect "
                                           "(@hyperframes/shader-transitions GLSL not used: absent here)"})
    return checks, [path, plan]


def _tex(blue):
    """Coordinate code in red, a separable fine texture in green (period-4 stripes along x plus along y), identity in blue."""
    img = coord(blue)
    sq = lambda v: np.where((v // 2) % 2 > 0, 1.0, -1.0)     # noqa: E731
    img[..., 1] = 128 + 55 * sq(XX) + 55 * sq(YY)
    return img


def hgauss(img, sigma):
    if sigma <= 0.05:
        return img.copy()
    if fx.have("scipy"):
        from scipy.ndimage import gaussian_filter1d
        return gaussian_filter1d(img, sigma, axis=1, mode="nearest")
    return hblur(img, sigma * 2.5)


AT, BT = _tex(BLUE_A), _tex(BLUE_B)


BLACK = solid((0, 0, 0))


def gsharp(fr, axis=None):
    g = fr[..., 1]
    h = float(np.mean(np.abs(np.diff(g, axis=1))))
    v = float(np.mean(np.abs(np.diff(g, axis=0))))
    return h if axis == "h" else v if axis == "v" else (h + v) / 2


def push_frame(a, b, e, dx=1, dy=0):
    oa = sample(a, XX + e * W * dx, YY + e * H * dy, fill=(0, 0, 0))
    bx, by = XX - (1 - e) * W * dx, YY - (1 - e) * H * dy
    inb = ((bx >= -0.5) & (bx <= W - 0.5) & (by >= -0.5) & (by <= H - 0.5))
    return np.where(inb[..., None], sample(b, bx, by), oa)


def css_push(dx, dy, D=0.5, ease=p_io(3)):
    def fr(u):
        return push_frame(A0, B0, ease(u / D), dx, dy)

    def pr(frs, ts, T0, hc):
        out = []
        for f in (0.3, 0.5, 0.7):
            i = at(ts, T0 + f * D)
            e = ease((ts[i] - T0) / D)
            if dx:
                selA = (bwt(frs[i]) < 0.5) & (XX > 2) & (XX < W * (1 - e) - 2)
                out.append(near("old scene x offset at %.0f%% (power3.inOut)" % (f * 100), xshift(frs[i], selA) if selA.any()
                                else float("nan"), -e * W, 0.8))
            else:
                selA = (bwt(frs[i]) < 0.5) & (YY > 2) & (YY < H * (1 - e) - 2)
                out.append(near("old scene y offset at %.0f%% (power3.inOut)" % (f * 100), yshift(frs[i], selA) if selA.any()
                                else float("nan"), -e * H, 0.8))
        i = at(ts, T0 + 0.3 * D)
        e = ease((ts[i] - T0) / D)
        selB = (bwt(frs[i]) > 0.5)
        meas = xshift(frs[i], selB) if dx else yshift(frs[i], selB)
        out.append(near("new scene enters from the far edge (offset)", meas, (1 - e) * (W if dx else H), 0.8))
        sel = (XX > 2) & (XX < W * 0.5) if dx else (YY > 2) & (YY < H * 0.5)
        out.append(neg("old-scene offset on the hard cut", xshift(hc(i), sel) if dx else yshift(hc(i), sel),
                       -e * (W if dx else H), 0.8))
        return out
    return D, fr, pr


def _elastic_x(u):
    """new scene x (CSS px): 1920 -> 30 in 0.4 s power4.out, then -> -15 (0.1 s sine), then -> 0 (0.1 s sine)."""
    if u < 0.4:
        return 1920 + (30 - 1920) * p_out(4)(u / 0.4)
    if u < 0.5:
        return 30 + (-15 - 30) * sine_io((u - 0.4) / 0.1)
    return -15 + 15 * sine_io((u - 0.5) / 0.1)


def css_elastic():
    D = 0.6

    def fr(u):
        x = _elastic_x(max(u, 0)) * K if u > 0 else W
        bxs = XX - x
        inb = (bxs >= -0.5) & (bxs <= W - 0.5)
        old = sample(A0, XX - (x - W), YY, fill=(0, 0, 0))
        return np.where(inb[..., None], sample(B0, bxs, YY), old)

    def pr(frs, ts, T0, hc):
        out = []
        for u, e in ((0.4, 30 * K), (0.5, -15 * K)):
            i = at(ts, T0 + u)
            selB = (bwt(frs[i]) > 0.5) & (XX > 8) & (XX < W - 8)
            out.append(near("new scene at %.1f s: x = %+.0f css px (overshoot/settle)" % (u, e / K), xshift(frs[i], selB),
                            e, 0.5))
        i = at(ts, T0 + 0.4)
        out.append(neg("overshoot offset on the hard cut", xshift(hc(i), (XX > 8) & (XX < W - 8)), 30 * K, 0.5))
        return out
    return D, fr, pr


def css_squeeze(D=0.4, ease=p_io(3)):
    def fr(u):
        e = ease(u / D)
        wa = W * (1 - e)
        old = sample(A0, XX / max(1 - e, 1e-6), YY) if wa > 0.5 else BLACK
        new = sample(B0, W - (W - XX) / max(e, 1e-6), YY) if e > 1e-3 else BLACK
        return np.where((XX < wa - 0.5)[..., None], old, new)

    def pr(frs, ts, T0, hc):
        i = at(ts, T0 + 0.5 * D)
        e = ease((ts[i] - T0) / D)
        selA = (bwt(frs[i]) < 0.5)
        selB = ~selA
        return [near("new scene width = scaleX x W (origin right)", float(selB[int(CY)].sum()), e * W, 1.0),
                near("old scene scaleX (origin left)", scale_est(frs[i], selA & (XX < W * (1 - e) - 2)) if selA.any() else
                     float("nan"), 1 - e, 0.03) if (1 - e) * W > 30 else check("old squeezed", True),
                neg("new-scene width on the hard cut", float((bwt(hc(i))[int(CY)] > 0.5).sum()), e * W, 1.0)]
    return D, fr, pr


CSS_REF = math.hypot(W, H) / math.sqrt(2)


def css_circle(D=0.5, ease=p_out(2)):
    def fr(u):
        return mix(A0, B0, disc(CX, CY, 0.75 * CSS_REF * ease(u / D)))

    def pr(frs, ts, T0, hc):
        i = at(ts, T0 + 0.25 * D)
        r = 0.75 * CSS_REF * ease((ts[i] - T0) / D)
        return [near("circle() radius at 25%% = 75%% x ease (power2.out) px", b_width(frs[i]) / 2, min(r, W / 2), 1.0),
                near("radius on the vertical axis", float((bwt(frs[i])[:, int(CX)] > 0.5).sum()) / 2, min(r, H / 2), 1.0),
                neg("iris radius on the hard cut", b_width(hc(i)) / 2, min(r, W / 2), 1.0)]
    return D, fr, pr


def css_diamond(D=0.5, ease=p_out(2)):
    def mask(e):
        if e <= 0:
            return np.zeros((H, W))
        return ((np.abs(XX - CX) / (0.7 * W * e) + np.abs(YY - CY) / (0.7 * H * e)) < 1) * 1.0

    def fr(u):
        return mix(A0, B0, mask(ease(u / D)))

    def pr(frs, ts, T0, hc):
        i = at(ts, T0 + 0.25 * D)
        e = ease((ts[i] - T0) / D)
        bw = bwt(frs[i]) > 0.5
        ax, ay = 0.7 * W * e, 0.7 * H * e
        pin = (int(CY + 0.45 * ay), int(CX + 0.45 * ax))
        pout = (int(CY + 0.58 * ay), int(CX + 0.58 * ax))
        return [near("diamond half-width on the row", float(bw[int(CY)].sum()) / 2, min(ax, W / 2), 1.0),
                check("point at (0.45, 0.45) of the half-diagonals is inside (L1 ball)", bool(bw[pin]), bool(bw[pin]), True),
                check("point at (0.58, 0.58) is outside (a circle/ellipse would contain it)", not bool(bw[pout]),
                      bool(bw[pout]), False),
                neg("diamond half-width on the hard cut", float((bwt(hc(i))[int(CY)] > 0.5).sum()) / 2, min(ax, W / 2), 1.0)]
    return D, fr, pr


def css_diagsplit(D=0.5, ease=p_io(3)):
    def amask(e):
        s = max(1 - e, 1e-6)
        return ((XX / (2 * W * s) + YY / (2 * H * s)) < 1) * (e < 1)

    def fr(u):
        return mix(B0, A0, amask(ease(u / D)) * 1.0)

    def pr(frs, ts, T0, hc):
        i = at(ts, T0 + 0.6 * D)
        e = ease((ts[i] - T0) / D)
        am = amask(e)
        meas = bwt(frs[i]) < 0.5
        agree = float(np.mean(meas == am))
        return [check("old scene is the shrinking corner triangle (pixel agreement)", agree > 0.995, agree, "> 0.995"),
                near("old-scene area", float(meas.mean()), float(am.mean()), 0.01),
                neg("old-scene area on the hard cut", float((bwt(hc(i)) < 0.5).mean()), float(am.mean()), 0.01)]
    return D, fr, pr


FLIP_P = 1200 * K


def flip_frame(a, b, th, persp=FLIP_P, bg=BLACK):
    c, s = math.cos(th), math.sin(th)
    sx, sy = XX - CX, YY - CY
    den = c * persp + sx * s
    xl = np.where(np.abs(den) > 1e-6, sx * persp / np.where(np.abs(den) > 1e-6, den, 1), 1e9)
    z = xl * s
    yl = sy * (persp - z) / persp
    front = c > 0
    img = a if front else b
    xs = xl if front else -xl
    ok = (np.abs(xl) <= W / 2) & (persp - z > 1)
    out = sample(img, xs + CX, yl + CY, fill=(0, 0, 0))
    inside_y = np.abs(yl) <= H / 2
    return np.where((ok & inside_y)[..., None], out, bg)


def flip_span(th, persp=FLIP_P):
    c, s = math.cos(th), math.sin(th)
    xs = [x * c * persp / (persp - x * s) for x in (-W / 2, W / 2)]
    return min(xs), max(xs)


def css_flip(D=0.6, ease=p_io(2)):
    def fr(u):
        return flip_frame(A0, B0, math.pi * ease(u / D))

    def pr(frs, ts, T0, hc):
        out = []
        for f in (0.35, 0.7):
            i = at(ts, T0 + f * D)
            th = math.pi * ease((ts[i] - T0) / D)
            lo, hi = flip_span(th)
            vis = frs[i][int(CY)].max(axis=-1) > 0
            cols = np.nonzero(vis)[0]
            out.append(near("projected card width at %.0f deg (perspective 1200)" % math.degrees(th),
                            float(cols.max() - cols.min() + 1) if cols.size else 0.0, min(hi, W / 2) - max(lo, -W / 2), 2.0))
            face = "A" if th < math.pi / 2 else "B"
            fb = fracb(frs[i], vis[None, :].repeat(H, 0) & (frs[i].max(axis=-1) > 0))
            out.append(check("visible face is %s (backface hidden)" % face, (fb < 0.05) if face == "A" else (fb > 0.95), fb,
                             face))
        i = at(ts, T0 + 0.85 * D)
        row = srcx(frs[i])[int(CY)]
        vis = frs[i][int(CY)].max(axis=-1) > 0
        slope = float(np.polyfit(XX[0][vis], row[vis], 1)[0]) if vis.sum() > 5 else float("nan")
        out.append(check("back face B reads left-to-right (not mirrored)", slope > 0, slope, "> 0"))
        i = at(ts, T0 + 0.35 * D)
        lo, hi = flip_span(math.pi * ease((ts[i] - T0) / D))
        out.append(neg("card width on the hard cut", float(W), min(hi, W / 2) - max(lo, -W / 2), 2.0))
        return out
    return D, fr, pr


def css_zoomthrough():
    D = 0.55

    def fr(u):
        eo = p_in(3)(u / 0.4)
        old = affine(blur(A0, 8 * K * eo), 1 + 1.5 * eo, fill=(0, 0, 0))
        out = mix(BLACK, old, 1 - eo)
        un = u - 0.15
        if un > 0:
            en = p_out(3)(un / 0.4)
            new = affine(B0, 0.5 + 0.5 * en, fill=(0, 0, 0))
            inside = ((np.abs(XX - CX) <= (0.5 + 0.5 * en) * W / 2) & (np.abs(YY - CY) <= (0.5 + 0.5 * en) * H / 2))
            out = mix(out, new, inside * en)
        return out

    def pr(frs, ts, T0, hc):
        i = at(ts, T0 + 0.15)
        eo = p_in(3)((ts[i] - T0) / 0.4)
        j = at(ts, T0 + 0.4)
        en = p_out(3)((ts[j] - T0 - 0.15) / 0.4)
        selB = bwt(frs[j]) > 0.5
        return [near("old scene scaled toward 2.5 (power3.in) at +0.15 s", scale_inv(frs[i]), 1 + 1.5 * eo, 0.01),
                near("old opacity 1 - e (blue level)", float(np.median(frs[i][..., 2])) / BLUE_A, 1 - eo, 0.03),
                near("new scene scale 0.5 -> 1 (power3.out) at +0.40 s", scale_inv(frs[j], selB), 0.5 + 0.5 * en, 0.01),
                neg("scale of the hard cut at +0.15 s", scale_est(hc(i)), 1 + 1.5 * eo, 0.01)]
    return D, fr, pr


def css_zoomout(D=0.4, ease=p_in(3)):
    def fr(u):
        e = ease(u / D)
        s = 1 - 0.7 * e
        old = affine(A0, s, fill=(0, 0, 0))
        inside = (np.abs(XX - CX) <= s * W / 2) & (np.abs(YY - CY) <= s * H / 2)
        return mix(B0, old, inside * (1 - e) * (u < D))

    def pr(frs, ts, T0, hc):
        i = at(ts, T0 + 0.6 * D)
        e = ease((ts[i] - T0) / D)
        s = 1 - 0.7 * e
        core = (np.abs(XX - CX) < s * W / 2 - 2) & (np.abs(YY - CY) < s * H / 2 - 2)
        blue = float(frs[i][..., 2][core].mean())
        return [near("old scene scaled to 1 - 0.7 e (old on top)", float(np.mean(srcx(frs[i])[int(CY)][(XX[0] > CX - s * W / 2 + 2) &
                     (XX[0] < CX + s * W / 2 - 2)].ptp() / max(1e-6, (s * W - 4)))), 1.0, 1.0) if False else
                near("old scene scale (power3.in toward 0.3)", scale_est(frs[i], core), s, 0.02),
                near("old opacity 1 - e over the new scene (blue mix)", blue, BLUE_A * (1 - e) + BLUE_B * e, 2.0),
                neg("scale on the hard cut", scale_est(hc(i), core), s, 0.02)]
    return D, fr, pr


def css_crossfade(D=0.5, ease=p_io(2)):
    def fr(u):
        return mix(A0, B0, ease(u / D))

    def pr(frs, ts, T0, hc):
        out = []
        for f in (0.25, 0.5):
            i = at(ts, T0 + f * D)
            e = ease((ts[i] - T0) / D)
            out.append(near("opacity at %.0f%% (power2.inOut, not linear)" % (f * 100), float(bwt(frs[i]).mean()), e, 0.01))
        i = at(ts, T0 + 0.5 * D)
        out.append(neg("blend weight of the hard cut", float(bwt(hc(i)).mean()), 0.5, 0.05))
        return out
    return D, fr, pr


def css_blurfade(D=0.5, blur_px=10, s_out=1.03, s_in=0.97, ease=p_io(2)):
    def fr(u):
        e = ease(u / D)
        old = affine(blur(AT, blur_px * K * e), 1 + (s_out - 1) * e)
        new = affine(blur(BT, blur_px * K * (1 - e)), s_in + (1 - s_in) * e)
        return mix(old, new, e)

    def pr(frs, ts, T0, hc):
        i = at(ts, T0 + 0.25 * D)
        e = ease((ts[i] - T0) / D)
        j = at(ts, T0 + 0.5 * D)
        sh = gsharp(frs[j])
        out = [check("detail drops at the midpoint (both layers blurred %.0f px)" % (blur_px * 0.5), sh < 0.75 * gsharp(AT),
                     sh, "< %.1f" % (0.75 * gsharp(AT))),
               near("blend weight at 25%%", float(bwt(frs[i]).mean()), e, 0.02)]
        if s_out != 1:
            out.append(near("old layer scale at 25%%", scale_est(frs[i]), (1 - e) * (1 + (s_out - 1) * e) + e * (s_in + (1 - s_in) * e),
                            0.006))
        out.append(neg("detail of the hard cut at the midpoint", gsharp(hc(j)), 0.5 * gsharp(AT), 0.25 * gsharp(AT)))
        return out
    return D, fr, pr


def css_dip(D=0.6, color=(0, 0, 0)):
    c = solid(color)

    def fr(u):
        e = u / D
        return mix(A0, c, p_io(1)(2 * e)) if e < 0.5 else mix(c, B0, p_io(1)(2 * e - 1))

    def pr(frs, ts, T0, hc):
        i = at(ts, T0 + 0.5 * D)
        j = at(ts, T0 + 0.25 * D)
        return [near("midpoint is the solid dip colour", mad(frs[i], c), 0.0, 1.0),
                near("quarter point is half-way to the dip", mad(frs[j], mix(A0, c, p_io(1)((ts[j] - T0) / D * 2))), 0.0, 1.5),
                neg("hard cut midpoint vs dip colour", mad(hc(i), c), 0.0, 1.0)]
    return D, fr, pr


BLOCK_C = [hexc("#2f6bff"), hexc("#ff7a1a"), hexc("#18c29c"), hexc("#f2c94c"), hexc("#d946ef")]


def css_blocks(nb=2, step=0.25, off=0.06, ease=p_io(3)):
    D = 2 * step + off * (nb - 1)
    swap = step + off * (nb - 1) / 2

    def bx(k, u):
        uk = u - k * off
        if uk < step:
            return -W + W * ease(uk / step)
        return W * ease((uk - step) / step)

    def fr(u):
        out = (A0 if u < swap else B0).copy()
        for k in range(nb):
            x0 = bx(k, u)
            out[(XX >= x0) & (XX < x0 + W)] = BLOCK_C[k % 5]
        return out

    def pr(frs, ts, T0, hc):
        i = at(ts, T0 + step / 2)
        u = ts[i] - T0
        e1 = (bx(0, u) + W) - max(bx(1, u) + W, 0)
        m = float((np.abs(frs[i][int(CY)] - BLOCK_C[0]).max(axis=-1) < 2).sum())
        return [near("block 1 visible columns at %.3f s (power3.inOut, block 2 %.2f s behind)" % (u, off), m, e1, 1.5),
                check("blocks fully cover the frame at the swap",
                      float((np.abs(frs[at(ts, T0 + swap)] - BLOCK_C[nb - 1]).max(axis=-1) < 2).mean()) > 0.9,
                      float((np.abs(frs[at(ts, T0 + swap)] - BLOCK_C[nb - 1]).max(axis=-1) < 2).mean()), "> 0.9"),
                neg("block-1 columns on the hard cut", float((np.abs(hc(i)[int(CY)] - BLOCK_C[0]).max(axis=-1) < 2).sum()),
                    e1, 1.5)]
    return D, fr, pr


def css_blinds(n, axis="h", stagger=0.03, strip=0.2, ease=p_io(3)):
    D = strip + stagger * (n - 1)
    size = (H if axis == "h" else W) / n

    def emap(u):
        return [ease((u - k * stagger) / strip) for k in range(n)]

    def fr(u):
        es = emap(u)
        coord_ = YY if axis == "h" else XX
        k = np.minimum((coord_ // size).astype(int), n - 1)
        loc = coord_ - k * size
        m = loc < np.array(es)[k] * size
        return mix(A0, B0, m * 1.0)

    def pr(frs, ts, T0, hc):
        i = at(ts, T0 + D * 0.4)
        es = emap(ts[i] - T0)
        bw = bwt(frs[i]) > 0.5
        meas = [float(bw[int(k * size):int((k + 1) * size)].mean()) if axis == "h" else
                float(bw[:, int(k * size):int((k + 1) * size)].mean()) for k in range(n)]
        err = float(np.max(np.abs(np.array(meas) - np.array(es))))
        hb = bwt(hc(i)) > 0.5
        hmeas = [float(hb[int(k * size):int((k + 1) * size)].mean()) if axis == "h" else
                 float(hb[:, int(k * size):int((k + 1) * size)].mean()) for k in range(n)]
        return [check("%d %s strips each closed by its own staggered ease (max error)" % (n, axis), err < 1.0 / size + 0.02,
                      err, "< %.3f" % (1.0 / size + 0.02)),
                check("strip 0 leads strip %d (stagger %.3f s)" % (n - 1, stagger), meas[0] > meas[-1], [meas[0], meas[-1]],
                      "first > last"),
                neg("staggered strip profile on the hard cut (max error)",
                    float(np.max(np.abs(np.array(hmeas) - np.array(es)))), 0.0, 1.0 / size + 0.02)]
    return D, fr, pr


TINT = np.array([255.0, 160.0, 60.0])


LEAKC = np.array([255.0, 180.0, 0.0])


def _tint_a(u):
    if u < 0.2:
        return 0.4 * p_out(2)(u / 0.2)
    if u < 0.45:
        return 0.4 + 0.2 * sine_io((u - 0.2) / 0.25)
    return 0.6 * (1 - p_io(1)((u - 0.45) / 0.45))


def css_lightleak():
    D = 0.9

    def fr(u):
        base = A0 if u < 0.45 else B0
        a = _tint_a(u)
        out = mix(base, solid(TINT), a)
        for k, (x0, y0) in enumerate(((0.1, 0.3), (0.8, 0.7), (0.4, 1.1))):
            x = W * x0 + 250 * K * c01(u / D)
            g = np.exp(-(((XX - x) ** 2 + (YY - H * y0) ** 2) / (2 * (0.5 * 2400 * K / 3) ** 2)))
            out = screen(out, LEAKC * (a * g)[..., None])
        return out

    def pr(frs, ts, T0, hc):
        i = at(ts, T0 + 0.44)
        j = at(ts, T0 + 0.46)
        ai = float(np.median((frs[i][..., 2] - BLUE_A) / (TINT[2] - BLUE_A)))
        bj = float(np.median(frs[j][..., 2]))
        return [near("warm tint opacity just before the swap (0.4 -> 0.6)", ai, _tint_a(ts[i] - T0), 0.03),
                check("scene swaps under the tint at +0.45 s", bj > 120 and ai < 1, bj, "> 120 (B under tint)"),
                neg("tint opacity on the hard cut", float(np.median((hc(i)[..., 2] - BLUE_A) / (TINT[2] - BLUE_A))),
                    _tint_a(ts[i] - T0), 0.03)]
    return D, fr, pr


def _burn_state(u):
    if u < 0.2:
        b = 1 + 0.5 * p_in(1)(u / 0.2)
    else:
        b = 1.5 + 1.5 * p_in(2)(c01((u - 0.2) / 0.35))
    w = p_in(2)(c01((u - 0.2) / 0.35)) if u < 0.55 else 1 - p_out(2)(c01((u - 0.55) / 0.35))
    s = 1.03 + 0.03 * c01(u / 0.55)
    return b, w, s


def css_overexpose():
    D = 0.9

    def fr(u):
        b, w, s = _burn_state(u)
        if u < 0.55:
            img = np.clip(affine(A0, s) * b, 0, 255)
        else:
            img = B0
        return mix(img, solid((255, 255, 255)), w)

    def pr(frs, ts, T0, hc):
        i = at(ts, T0 + 0.2)
        b, w, s = _burn_state(ts[i] - T0)
        gsel = (YY < H * 0.45)
        gain = float(np.median((frs[i][..., 1][gsel] + 1) / (A0[..., 1][gsel] + 1)))
        j = at(ts, T0 + 0.55)
        return [near("brightness x1.5 at +0.2 s (green gain on unclipped rows)", gain, b, 0.08),
                check("burns to full white at the swap (+0.55 s)", float(lum(frs[j]).mean()) > 250, float(lum(frs[j]).mean()),
                      "> 250"),
                neg("brightness gain on the hard cut", float(np.median((hc(i)[..., 1][gsel] + 1) / (A0[..., 1][gsel] + 1))),
                    b, 0.08)]
    return D, fr, pr


FB_COLS = [np.array([255.0, 191.0, 0.0]), np.array([255.0, 120.0, 0.0]), np.array([220.0, 30.0, 0.0])]


def _fb_r(k, u):
    return 1.6 * W * p_in(1)(c01((u - 0.05 * k) / 0.4))


def css_filmburn():
    D = 0.9

    def fr(u):
        base = A0 if u < 0.45 else B0
        out = base.copy()
        fade = 1 - c01((u - 0.45) / 0.45)
        for k, col in enumerate(FB_COLS):
            r = _fb_r(k, u) * (1 if u < 0.45 else 1.0)
            m = disc(0, CY, r, 3.0) * fade
            out = mix(out, solid(col), m * 0.8)
        return out

    def pr(frs, ts, T0, hc):
        i = at(ts, T0 + 0.25)
        u = ts[i] - T0
        row = frs[i][int(CY)]
        changed = np.abs(row - A0[int(CY)]).max(axis=-1) > 20
        reach = float(np.nonzero(changed)[0].max() + 1) if changed.any() else 0.0
        order = [_fb_r(k, u) for k in range(3)]
        return [near("amber front reach from the left edge at +0.25 s (px)", reach, min(order[0], W), 2.0),
                check("overlays staggered 0.05 s: amber > orange > red radius", order[0] > order[1] > order[2], order,
                      "decreasing"),
                check("left edge burns first (column 2 changed, column W-3 not yet)", bool(changed[2]) and not bool(changed[-3]),
                      [bool(changed[2]), bool(changed[-3])], [True, False]),
                neg("burn reach on the hard cut", float((np.abs(hc(i)[int(CY)] - A0[int(CY)]).max(axis=-1) > 20).sum()),
                    min(order[0], W), 2.0)]
    return D, fr, pr


def _jit(k):
    s = 1 if _h(k, 7) < 0.5 else -1
    return s * (30 + 30 * _h(k, 8)) * K


def css_glitch():
    D, q, swap = 0.4, 0.03, 0.2
    w0 = swap - 3 * q

    def fr(u):
        base = A0 if u < swap else B0
        k = int(math.floor((u - w0) / q + 1e-9))
        if not (0 <= k < 6):
            return base.copy()
        d = _jit(k)
        red = shift(base, d, 0) * np.array([1.0, 0, 0])
        cyan = shift(base, -d, 0) * np.array([0, 1.0, 1.0])
        return mix(mix(base, red, 0.35), cyan, 0.35)

    def pr(frs, ts, T0, hc):
        inwin = [i for i, t in enumerate(ts) if 0 <= math.floor((t - T0 - w0) / q + 1e-9) < 6]
        states = len({hash(frs[i].tobytes()) for i in inwin})
        clean_before = mad(frs[at(ts, T0 + w0 - 0.02)], A0)
        clean_after = mad(frs[at(ts, T0 + w0 + 6 * q + 0.02)], B0)
        i = inwin[1]
        base = A0 if ts[i] - T0 < swap else B0
        best = min(range(1, 9), key=lambda s: min(mad(frs[i], mix(mix(base, shift(base, sg * s, 0) * np.array([1.0, 0, 0]), 0.35),
                                                                  shift(base, -sg * s, 0) * np.array([0, 1.0, 1.0]), 0.35))
                                                  for sg in (1, -1)))
        sw = next(i for i, t in enumerate(ts) if t - T0 >= swap)
        return [check("six distinct jitter states, one per 0.03 s", states == 6, states, 6),
                check("clean before and after the jitter window", clean_before < 0.5 and clean_after < 0.5,
                      [clean_before, clean_after], "< 0.5"),
                check("RGB copies displaced 30-60 css px (3-6 px here)", 3 <= best <= 6, best, "3..6"),
                check("swap at +0.2 s", float(np.median(frs[sw][..., 2])) > 100 > float(np.median(frs[sw - 2][..., 2])),
                      [float(np.median(frs[sw - 2][..., 2])), float(np.median(frs[sw][..., 2]))], "A then B"),
                neg("distinct jitter states on the hard cut", len({hash(hc(i).tobytes()) for i in inwin}), 6, 0)]
    return D, fr, pr


def _ab_d(u):
    return 80 * K * (p_in(2)(u / 0.3) if u < 0.3 else 1 - p_out(2)(c01((u - 0.3) / 0.3)))


def css_aberr():
    D = 0.6

    def fr(u):
        base = A0 if u < 0.3 else B0
        d = _ab_d(u)
        out = base.copy()
        out[..., 0] = shift(base, d, 0)[..., 0]
        out[..., 2] = shift(base, -d, 0)[..., 2]
        return out

    def pr(frs, ts, T0, hc):
        i, j = at(ts, T0 + 0.15), at(ts, T0 + 0.29)
        return [near("RGB spread at +0.15 s (power2.in)", chan_offset(frs[i]), _ab_d(ts[i] - T0), 0.4),
                near("RGB spread near the peak (80 css px)", chan_offset(frs[j]), _ab_d(ts[j] - T0), 0.5),
                near("channels re-converged at the end", chan_offset(frs[-1]), 0.0, 0.2),
                neg("RGB spread on the hard cut", chan_offset(hc(j)), _ab_d(ts[j] - T0), 0.5)]
    return D, fr, pr


def _rip_state(u):
    env = math.sin(math.pi * c01(u / 0.4))
    k = int(u // 0.04)
    sg = 1 if k % 2 == 0 else -1
    return sg * 30 * K * env, 1 + sg * 0.03 * env, 4 * K * 10 * env * 0.1


def css_ripple():
    D = 0.4

    def fr(u):
        dx, s, b = _rip_state(u)
        base = A0 if u < 0.2 else B0
        return blur(affine(base, s, dx=dx), b)

    def pr(frs, ts, T0, hc):
        out = []
        for u in (0.1, 0.14, 0.26):
            i = at(ts, T0 + u)
            dx, s, b = _rip_state(ts[i] - T0)
            out.append(near("x oscillation at +%.2f s (+-30 css px, 0.04 s)" % u, xshift(frs[i], (XX > 20) & (XX < W - 20)),
                            dx, 0.4))
            out.append(near("scale oscillation at +%.2f s (0.97-1.03)" % u, scale_est(frs[i]), s, 0.01))
        i = at(ts, T0 + 0.1)
        out.append(neg("x oscillation on the hard cut", xshift(hc(i), (XX > 20) & (XX < W - 20)), _rip_state(ts[i] - T0)[0], 0.4))
        return out
    return D, fr, pr


def _vhs_off(k, u):
    return (_h(k, 31) - 0.5) * 2 * 0.06 * W * math.sin(math.pi * c01(u / 0.4))


def css_vhs():
    D, n = 0.4, 20

    def fr(u):
        base = A0 if u < 0.2 else B0
        sh_ = np.array([_vhs_off(k, u) for k in range(n)])[np.minimum((YY // (H / n)).astype(int), n - 1)]
        img = sample(base, XX - sh_, YY)
        d = 0.01 * W * math.sin(math.pi * c01(u / 0.4))
        img[..., 2] = sample(base, XX - sh_ + d, YY)[..., 2]
        return img

    def pr(frs, ts, T0, hc):
        i = at(ts, T0 + 0.12)
        u = ts[i] - T0
        inner = (XX > 15) & (XX < W - 15)
        sid = np.minimum((YY // (H / n)).astype(int), n - 1)
        d_ = XX - srcx(frs[i])
        meas = [float(np.median(d_[(sid == k) & inner])) for k in range(n)]
        exp = [_vhs_off(k, u) for k in range(n)]
        err = float(np.max(np.abs(np.array(meas) - np.array(exp))))
        within = max(float(np.ptp(d_[(sid == k) & inner])) for k in range(n))
        hm = [float(np.median((XX - srcx(hc(i)))[(sid == k) & inner])) for k in range(n)]
        return [check("20 strips each shifted by its seeded offset (max error px)", err < 0.6, err, "< 0.6"),
                check("one offset per strip (spread inside a strip)", within < 1.2, within, "< 1.2"),
                neg("strip offsets on the hard cut (max error)", float(np.max(np.abs(np.array(hm) - np.array(exp)))), 0.0, 0.6)]
    return D, fr, pr


SHUT = solid((12, 12, 14))


def _shut_e(u):
    return p_in(3)(u / 0.25) if u < 0.25 else 1 - p_out(3)(c01((u - 0.25) / 0.25))


def css_shutter():
    D = 0.5

    def fr(u):
        e = _shut_e(u)
        base = A0 if u < 0.25 else B0
        m = (YY < e * H / 2) | (YY >= H - e * H / 2)
        return np.where(m[..., None], SHUT, base)

    def pr(frs, ts, T0, hc):
        i = at(ts, T0 + 0.2)
        e = _shut_e(ts[i] - T0)
        rows = float((np.abs(frs[i][:, int(CX)] - SHUT[0, 0]).max(axis=-1) < 2).sum())
        j = at(ts, T0 + 0.25)
        return [near("shutter halves cover 2 x e x H/2 rows at +0.2 s (power3.in)", rows, 2 * math.ceil(e * H / 2 - 1e-9), 2.0),
                check("closed at +0.25 s", float((np.abs(frs[j] - SHUT[0, 0]).max(axis=-1) < 2).mean()) > 0.98,
                      float((np.abs(frs[j] - SHUT[0, 0]).max(axis=-1) < 2).mean()), "> 0.98"),
                neg("covered rows on the hard cut", float((np.abs(hc(i)[:, int(CX)] - SHUT[0, 0]).max(axis=-1) < 2).sum()),
                    2 * math.ceil(e * H / 2 - 1e-9), 2.0)]
    return D, fr, pr


ANG = (np.arctan2(XX - CX, -(YY - CY)) % (2 * np.pi))


def css_clock(D=0.4):
    def fr(u):
        th = 2 * np.pi * c01(u / D)
        return mix(A0, B0, (ANG < th) * 1.0)

    def pr(frs, ts, T0, hc):
        i = at(ts, T0 + 0.15)
        th = 2 * np.pi * c01((ts[i] - T0) / D)
        bw = bwt(frs[i]) > 0.5
        ring = (np.hypot(XX - CX, YY - CY) > 20) & (np.hypot(XX - CX, YY - CY) < 40)
        edge = float(ANG[ring & bw].max())
        agree = float(np.mean(bw == (ANG < th)))
        return [near("hand angle at +0.15 s = 360 x t/0.4 (ease none, 0.1 s per quadrant)", math.degrees(edge),
                     math.degrees(th), 4.0),
                check("revealed region is the clockwise sector from 12 o'clock", agree > 0.995, agree, "> 0.995"),
                neg("sector agreement on the hard cut", float(np.mean((bwt(hc(i)) > 0.5) == (ANG < th))), 1.0, 0.005)]
    return D, fr, pr


def css_grid(cols=4, rows=3, fill=0.2, k=0.12):
    cw, ch = W / cols, H / rows
    ci = np.minimum((XX // cw).astype(int), cols - 1)
    cj = np.minimum((YY // ch).astype(int), rows - 1)
    dist = np.hypot((ci + 0.5) - cols / 2, (cj + 0.5) - rows / 2)
    dmax = float(dist.max())
    colr = np.array(BLOCK_C)[(ci + cj * cols) % 5]
    T_in = fill + k * dmax
    D = 2 * T_in

    def fr(u):
        base = A0 if u < T_in else B0
        if u < T_in:
            a = np.clip((u - k * dist) / fill, 0, 1)
        else:
            a = 1 - np.clip((u - T_in - k * dist) / fill, 0, 1)
        return mix(base, colr, a)

    def pr(frs, ts, T0, hc):
        i = at(ts, T0 + 0.18)
        u = ts[i] - T0
        a_exp = np.clip((u - k * dist) / fill, 0, 1)
        a_meas = np.zeros((H, W))
        for c in range(cols):
            for r in range(rows):
                sel = (ci == c) & (cj == r) & (np.abs(XX - (c + 0.5) * cw) < 4) & (np.abs(YY - (r + 0.5) * ch) < 4)
                f = frs[i][sel].mean(axis=0)
                cc = colr[sel][0]
                bc = A0[sel].mean(axis=0)
                a_meas[(ci == c) & (cj == r)] = float(np.dot(f - bc, cc - bc) / max(np.dot(cc - bc, cc - bc), 1e-6))
        err = float(np.max(np.abs(a_meas - a_exp)))
        centre = float(a_meas[int(CY), int(CX)])
        corner = float(a_meas[0, 0])
        ncol = len({tuple(c) for c in colr.reshape(-1, 3)})
        return [check("each cell fills on its own clock, delayed by distance from centre (max error)", err < 0.05, err, "< 0.05"),
                check("centre cells lead the corners (ripple from centre)", centre > corner, [centre, corner], "centre > corner"),
                check("5 palette colours on the grid", ncol == 5, ncol, 5),
                neg("cell fill on the hard cut (centre cell)", 0.0, centre, 0.05)]
    return D, fr, pr


def css_gravity(D=0.5, ease=p_in(3)):
    def fr(u):
        e = ease(u / D)
        old = affine(A0, 1.0, dy=1200 * K * e, rot=math.radians(4) * e, fill=None)
        cy_ = CY + 1200 * K * e
        rot = math.radians(4) * e
        u_, v_ = XX - CX, YY - cy_
        lx = u_ * math.cos(-rot) - v_ * math.sin(-rot)
        ly = u_ * math.sin(-rot) + v_ * math.cos(-rot)
        inside = (np.abs(lx) <= W / 2) & (np.abs(ly) <= H / 2)
        return np.where(inside[..., None], old, B0) if u < D else B0

    def pr(frs, ts, T0, hc):
        i = at(ts, T0 + 0.35)
        e = ease((ts[i] - T0) / D)
        selA = (bwt(frs[i]) < 0.5) & (np.abs(XX - CX) < 30)
        dy = yshift(frs[i], selA)
        sel2 = (bwt(frs[i]) < 0.5) & (YY > 1200 * K * e + 8) & (XX > 30) & (XX < W - 30)
        slope = float(np.polyfit(XX[sel2], srcy(frs[i])[sel2], 1)[0]) if sel2.sum() > 20 else float("nan")
        return [near("old scene dropped 1200 css px x power3.in at +0.35 s", dy, 1200 * K * e, 1.0),
                near("old scene rotated 4 deg x e (source-y slope)", -slope, math.tan(math.radians(4) * e), 0.012),
                neg("drop on the hard cut", yshift(hc(i), np.abs(XX - CX) < 30), 1200 * K * e, 1.0)]
    return D, fr, pr


MCOL = np.array([40.0, 60.0, 200.0])


def css_morphcircle(D=0.5, ease=p_in(3)):
    def fr(u):
        if u >= 0.4:
            base = B0
            fade = 1 - c01((u - 0.4) / 0.1)
            return mix(base, solid(MCOL), fade)
        r = 10 * 30 * ease(u / D)
        return mix(A0, solid(MCOL), disc(CX, CY, r))

    def pr(frs, ts, T0, hc):
        i = at(ts, T0 + 0.3)
        r = 300 * ease((ts[i] - T0) / D)
        m = float((np.abs(frs[i][int(CY)] - MCOL).max(axis=-1) < 3).sum()) / 2
        j = at(ts, T0 + 0.4)
        return [near("circle radius = 10 px x scale 30 x power3.in at +0.3 s", m, min(r, W / 2), 1.0),
                check("swap to scene B at +0.4 s (under the colour)", float(np.median(frs[j][..., 2])) > 190,
                      float(np.median(frs[j][..., 2])), "> 190"),
                neg("circle radius on the hard cut", float((np.abs(hc(i)[int(CY)] - MCOL).max(axis=-1) < 3).sum()) / 2,
                    min(r, W / 2), 1.0)]
    return D, fr, pr


def css_blurthrough(D=0.4, blur_px=15, s_peak=1.08):
    half = D / 2

    def fr(u):
        if u < half:
            e = p_in(2)(u / half)
            return affine(blur(AT, blur_px * K * e), 1 + (s_peak - 1) * e)
        e = p_out(2)((u - half) / half)
        return affine(blur(BT, blur_px * K * (1 - e)), s_peak - (s_peak - 1) * e)

    def pr(frs, ts, T0, hc):
        j = at(ts, T0 + half - 0.01)
        e = p_in(2)((ts[j] - T0) / half)
        return [near("scale toward %.2f at the swap" % s_peak, scale_est(frs[j]), 1 + (s_peak - 1) * e, 0.006),
                check("detail lowest at the swap (blur %.0f css px)" % blur_px, gsharp(frs[j]) < 0.5 * gsharp(AT),
                      gsharp(frs[j]), "< %.1f" % (0.5 * gsharp(AT))),
                neg("detail on the hard cut at the swap", gsharp(hc(j)), 0.25 * gsharp(AT), 0.25 * gsharp(AT))]
    return D, fr, pr


def _dirblur_state(u, D):
    half = D / 2
    if u < half:
        e = p_in(2)(u / half)
        return "A", -200 * K * e, math.radians(-8) * e, 12 * K * e
    e = p_out(2)((u - half) / half)
    return "B", 200 * K * (1 - e), math.radians(8) * (1 - e), 12 * K * (1 - e)


def css_dirblur(D=0.4):
    def fr(u):
        which, dx, sk, L = _dirblur_state(u, D)
        img = AT if which == "A" else BT
        sx = XX - dx - np.tan(sk) * (YY - CY)
        return hgauss(sample(img, sx, YY), L)

    def pr(frs, ts, T0, hc):
        i = at(ts, T0 + D / 2 - 0.02)
        which, dx, sk, L = _dirblur_state(ts[i] - T0, D)
        inner = (XX > 30) & (XX < W - 30) & (np.abs(YY - CY) < 40)
        dyx = float(np.polyfit(YY[inner], (XX - srcx(frs[i]))[inner], 1)[0])
        return [near("x offset toward -200 css px", xshift(frs[i], inner & (np.abs(YY - CY) < 2)), dx, 0.6),
                near("skewX -8 deg x e (shift per row)", dyx, math.tan(sk), 0.02),
                check("blur is horizontal (horizontal detail << vertical)", gsharp(frs[i], "h") < 0.6 * gsharp(frs[i], "v"),
                      [gsharp(frs[i], "h"), gsharp(frs[i], "v")], "h < 0.6 v"),
                neg("skew on the hard cut", float(np.polyfit(YY[inner], (XX - srcx(hc(i)))[inner], 1)[0]), math.tan(sk), 0.02)]
    return D, fr, pr


CHAR = np.array([40.0, 22.0, 12.0])


GLOW = np.array([255.0, 140.0, 30.0])


def _pb_front(ang, R):
    a = ang * 1.0
    n = (50 * K * np.sin(a * 7 + 1.3) + 20 * K * np.sin(a * 19 + 0.4) + 8 * K * np.sin(a * 43 + 2.1))
    return R + n


def css_pageburn(D=0.8):
    dist = np.hypot(XX, YY)
    ang = np.arctan2(YY, XX)
    Rmax = math.hypot(W, H) + 10

    def fr(u):
        R = Rmax * p_io(1)(u / D)
        f = _pb_front(ang, R)
        out = np.where((dist < f - 3)[..., None], B0, A0)
        out = np.where(((dist >= f - 3) & (dist < f))[..., None], CHAR, out)
        out = np.where(((dist >= f) & (dist < f + 2))[..., None], GLOW, out)
        return out if u < D else B0

    def pr(frs, ts, T0, hc):
        i = at(ts, T0 + 0.4)
        R = Rmax * p_io(1)((ts[i] - T0) / D)
        f = _pb_front(ang, R)
        meas = bwt(frs[i]) > 0.5
        agree = float(np.mean(meas == (dist < f - 3)))
        charm = float(((np.abs(frs[i] - CHAR).max(axis=-1) < 2)).mean())
        return [check("burnt region = radial front from the corner + 3-octave sin noise", agree > 0.995, agree, "> 0.995"),
                check("charred fringe present along the front", charm > 0.005, charm, "> 0.005"),
                neg("burnt-region agreement on the hard cut", float(np.mean((bwt(hc(i)) > 0.5) == (dist < f - 3))), 1.0, 0.005)]
    return D, fr, pr


CSS = {
    "push-slide": css_push(1, 0), "vertical-push": css_push(0, 1), "elastic-push": css_elastic(), "squeeze": css_squeeze(),
    "circle-iris": css_circle(), "diamond-iris": css_diamond(), "diagonal-split": css_diagsplit(), "card-flip": css_flip(),
    "zoom-through": css_zoomthrough(), "zoom-out": css_zoomout(), "crossfade": css_crossfade(), "blur-crossfade": css_blurfade(),
    "focus-pull": css_blurfade(0.5, 15, 1.0, 1.0), "color-dip": css_dip(), "staggered-blocks": css_blocks(),
    "horizontal-blinds": css_blinds(6, "h"), "vertical-blinds": css_blinds(8, "v"), "light-leak": css_lightleak(),
    "overexposure-burn": css_overexpose(), "film-burn": css_filmburn(), "glitch": css_glitch(),
    "chromatic-aberration": css_aberr(), "ripple": css_ripple(), "vhs-tape": css_vhs(), "shutter": css_shutter(),
    "clock-wipe": css_clock(), "grid-dissolve": css_grid(), "gravity-drop": css_gravity(), "morph-circle": css_morphcircle(),
    "blur-through": css_blurthrough(), "directional-blur": css_dirblur(), "page-burn": css_pageburn(),
}


CSS_FPS = {"glitch": 100, "ripple": 100, "light-leak": 100}


CSS_TEX = {"blur-crossfade", "focus-pull", "blur-through", "directional-blur"}


def run_css(wd, key, card_id, T0=0.1, tail=0.1):
    """Render one handoff: scene A held, the recipe for D seconds, then overlays cleaned and scene B held."""
    D, fr, pr = CSS[key]
    fps = CSS_FPS.get(key, 40)
    a, b = (AT, BT) if key in CSS_TEX else (A0, B0)

    def frame(t):
        u = round(t - T0, 6)
        return a if u < 0 else fr(u) if u < D else b
    path, frs, ts = film(wd, key, frame, T0 + D + tail, fps)
    cut = T0 + D / 2
    hc = lambda i: a if ts[i] < cut else b     # noqa: E731
    checks = ends(frs, a, b, name=key) + pr(frs, ts, T0, hc)
    return checks, path


BG = np.array([18.0, 20.0, 30.0])


def box(cx, cy, w, h):
    return np.clip(np.minimum(w / 2 - np.abs(XX - cx) + 0.5, h / 2 - np.abs(YY - cy) + 0.5), 0, 1)


def centroid(fr, col, tol=None, bg=BG):
    tol = float(np.abs(np.asarray(col) - bg).max()) if tol is None else tol
    m = np.clip(1 - np.abs(fr - col).max(axis=-1) / tol, 0, 1)
    s = m.sum()
    return (float((m * XX).sum() / s), float((m * YY).sum() / s), float(s)) if s > 0.5 else (float("nan"),) * 2 + (0.0,)


WORDC = np.array([240.0, 240.0, 240.0])


def cut_times(frs, ts, thr=8.0):
    return [ts[i] for i in range(1, len(frs)) if mad(frs[i], frs[i - 1]) > thr]


PAL5 = [hexc(c) for c in ("#ff5a5f", "#ffb400", "#00a699", "#3d5afe", "#7b1fa2")]


def click_track(path, times, amps, total, rate=22050, freq=2000.0):
    sig = np.zeros(int(total * rate))
    n = int(0.006 * rate)
    env = np.exp(-np.arange(n) / (0.0015 * rate))
    for t, a in zip(times, amps):
        i = int(round(t * rate))
        sig[i:i + n] += a * env[:len(sig[i:i + n])] * np.sin(2 * np.pi * freq * np.arange(len(sig[i:i + n])) / rate)
    return fx.write_wav(path, sig, rate)


def onsets(path, thr=0.15, quiet=0.05):
    data, rate = fx.read_wav(path)
    x = np.abs(data[:, 0])
    hop = max(1, int(rate * 0.0005))
    env = np.array([x[i:i + hop].max() for i in range(0, len(x), hop)])
    out, last = [], -1e9
    for k, v in enumerate(env):
        t = k * hop / rate
        if v > thr and t - last > quiet:
            pk = float(env[k:k + int(0.006 * rate / hop) + 1].max())
            out.append((t, pk))
            last = t
        if v > thr:
            last = t
    return out


def beat_fixture(wd, bpm=120, n=4, accent=2, total=2.4):
    beat = 60.0 / bpm
    times = [0.4 + k * beat for k in range(n)]
    amps = [0.9 if k == accent else 0.4 for k in range(n)]
    wav = click_track(Path(wd) / "music.wav", times, amps, total)
    ons = onsets(wav)
    return wav, ons, times


def mux(wd, video, wav, name):
    out = Path(wd) / (name + "_av.mkv")
    # exact length: every video frame, the WAV padded/trimmed to the video (no -shortest)
    fx.ffmpeg("-i", str(video), "-i", str(wav), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
              *fx.fit_audio(fx.video_seconds(video)), "-c:a", "pcm_s16le", str(out))
    return out


def first_change(frs, ts, ref, thr=3.0):
    for f, t in zip(frs, ts):
        if float(np.abs(f - ref).max()) > thr:
            return t
    return float("nan")


def _whip_fr(t, ev, half=0.15):
    if t < ev:
        u = c01((t - (ev - half)) / half)
        return hblur(shift(A0, -W * 0.6 * p_in(2)(u), 0), 20 * u)
    u = c01((t - ev) / half)
    return hblur(shift(B0, W * 0.6 * (1 - p_out(2)(u)), 0), 20 * (1 - u))


def _whip_pr(frs, ts, ev, fps):
    sw = next(i for i, f in enumerate(frs) if float(np.median(f[..., 2])) > 120)
    i = at(ts, ev - 0.05)
    return [near("hard cut lands on the beat frame (s)", ts[sw], math.ceil(ev * fps - 1e-9) / fps, 0.5 / fps + 1e-6),
            check("whip offset grows into the cut", xshift(frs[i], (XX > 30) & (XX < 90)) < -3,
                  xshift(frs[i], (XX > 30) & (XX < 90)), "< -3 px"),
            check("span 0.30 s inside the best 0.18-0.45 s", 0.18 <= 0.3 <= 0.45, 0.3, "0.18..0.45"),
            neg("whip offset on a static cut", xshift(A0, (XX > 30) & (XX < 90)), -10.0, 7.0)]


def _mask_fr(t, ev, span=0.8):
    e = p_io(2)((t - ev) / span)
    return np.where((XX < e * W)[..., None], B0, A0)


def _mask_pr(frs, ts, ev, fps):
    st = first_change(frs, ts, A0)
    i = at(ts, ev + 0.4)
    return [near("mask wipe starts on the section-start downbeat (s)", st, math.ceil(ev * fps + 1e-9) / fps, 1.0 / fps + 1e-6),
            near("wipe edge at half span", float(b_width(frs[i])), math.ceil(p_io(2)((ts[i] - ev) / 0.8) * W - 1e-9), 1.0),
            neg("wipe edge on a static frame", float(b_width(A0)), W / 2, 2.0)]


def _irisb_fr(t, ev, span=0.8):
    r = (math.hypot(W, H) / 2 + 2) * p_out(2)((t - ev) / span)
    return mix(A0, B0, disc(CX, CY, r)) if t >= ev else A0


def _irisb_pr(frs, ts, ev, fps):
    st = first_change(frs, ts, A0)
    i = at(ts, ev + 0.15)
    r = (math.hypot(W, H) / 2 + 2) * p_out(2)((ts[i] - ev) / 0.8)
    return [near("iris opens on the reveal event (s)", st, math.ceil(ev * fps - 1e-9) / fps, 1.0 / fps + 1e-6),
            near("iris radius 0.15 s after the event", b_width(frs[i]) / 2, r, 1.0),
            neg("iris radius on a static frame", b_width(A0) / 2, r, 1.0)]


def _blurres_fr(t, ev, span=1.2):
    if t < ev:
        u = c01((t - (ev - span)) / (span * 0.5))
        return blur(AT, 3.0 * (1 - p_out(2)(u)))
    return blur(BT, 3.0 * p_in(2)(c01((t - ev) / 0.3)))


def _blurres_pr(frs, ts, ev, fps):
    s = [gsharp(f) for f in frs]
    ic = next(i for i, t in enumerate(ts) if t >= ev)
    crisp = max(s[:ic])
    return [check("blur-in resolves to crisp before the stop", crisp > 0.95 * gsharp(AT), crisp, "> 0.95 sharp"),
            check("blurred at the start", s[0] < 0.3 * gsharp(AT), s[0], "< 0.3 sharp"),
            check("blur-out after the stop event", s[-1] < 0.3 * gsharp(AT) and ts[ic] - ev < 1.0 / fps + 1e-9, s[-1], "blurred"),
            neg("sharpness swing of an unblurred hold", float(gsharp(AT) - gsharp(AT)), gsharp(AT), 0.7 * gsharp(AT))]


def _flashb_fr(t, ev, span=0.3):
    base = A0 if t < ev else B0
    return mix(base, solid((255, 255, 255)), 1 - p_out(2)(c01((t - ev) / span)) if t >= ev else 0.0)


def _flashb_pr(frs, ts, ev, fps):
    i = next(i for i, t in enumerate(ts) if t >= ev)
    return [check("full-frame white on the drop frame", float(lum(frs[i]).mean()) > 230, float(lum(frs[i]).mean()), "> 230"),
            check("frame before the drop is clean A", mad(frs[i - 1], A0) < 0.5, mad(frs[i - 1], A0), "< 0.5"),
            check("state change masked: B after the flash", mad(frs[-1], B0) < 0.5, mad(frs[-1], B0), "< 0.5"),
            neg("white on the drop frame of a bare cut", float(lum(B0).mean()), 255.0, 25.0)]


def _hard_fr(t, ev):
    base = solid(PAL5[0]) if t < ev else solid(PAL5[3])
    _, a = text_layer("NOW" if t >= ev else "WAIT", size=24, color=(255, 255, 255))
    return mix(base, solid((255, 255, 255)), a)


def _hard_pr(frs, ts, ev, fps):
    cut = cut_times(frs, ts)
    return [check("one cut, on the first frame at/after the beat (sample-accurate onset)", len(cut) == 1 and
                  abs(cut[0] - math.ceil(ev * fps - 1e-9) / fps) < 1e-6, cut, math.ceil(ev * fps - 1e-9) / fps),
            check("colour block and word change together", mad(frs[-1][2, 2], PAL5[3]) < 2, True, True),
            neg("cuts in a held block", len(cut_times(np.stack([frs[0]] * 5), ts[:5])), 1, 0)]


def _stag_fr(t, ev, n=5, stag=0.1, dur=0.3):
    img = solid(BG)
    for k in range(n):
        e = p_in(2)((t - ev - k * stag) / dur)
        img = mix(img, solid(WORDC), box(W * (0.15 + 0.175 * k), CY + e * 80, 20, 12))
    return img


def _stag_pr(frs, ts, ev, fps, n=5, stag=0.1, dur=0.3):
    starts = []
    for k in range(n):
        x = W * (0.15 + 0.175 * k)
        ys = []
        for f in frs:
            sub = f.copy()
            sub[:, np.abs(XX[0] - x) > 14] = BG
            ys.append(centroid(sub, WORDC)[1])
        i = at(ts, ev + k * stag + dur / 2)
        starts.append((ys[i] - CY, 80 * p_in(2)((ts[i] - ev - k * stag) / dur)))
    err = max(abs(a - b) for a, b in starts)
    return [check("ordered cascade: element k at event + k x 0.1 s + half its exit has dropped 80 x ease (max error px)",
                  err <= 0.3, starts, "<= 0.3"),
            check("frame cleared at the end", mad(frs[-1], solid(BG)) < 0.5, mad(frs[-1], solid(BG)), "< 0.5"),
            neg("cascade order without stagger (all leave together)", 0.0, 0.4, 0.05)]


ORANGE = np.array([255.0, 120.0, 0.0])
