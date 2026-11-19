"""Helpers of runners/fam_light_glow_bloom.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFilter
from PIL import ImageFont
import json
import math
import numpy as np
import subprocess


def hx(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def hxf(h):
    return np.array(hx(h), float) / 255.0


def tohex(c):
    return "#%02x%02x%02x" % tuple(int(round(max(0, min(255, float(v))))) for v in c[:3])


def to8(a):
    return np.clip(np.rint(np.asarray(a, float) * 255), 0, 255).astype(np.uint8)


def save(a, p):
    """save a float 0..1 canvas"""
    Image.fromarray(to8(a)).save(str(p))
    return p


def load(p):
    return np.asarray(Image.open(str(p)).convert("RGB")).astype(float) / 255.0


def write_video(path, frames, fps=30, crf="17"):
    frames = [to8(f) for f in frames]
    h, w = frames[0].shape[:2]
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", "%dx%d" % (w, h), "-r", str(fps), "-i", "-", "-c:v", "libx264", "-crf", crf, "-pix_fmt", "yuv420p",
           str(path)]
    done = subprocess.run(cmd, input=b"".join(f.tobytes() for f in frames), capture_output=True, timeout=60)
    if done.returncode:
        raise RuntimeError(done.stderr.decode(errors="replace")[-300:])
    return path


def luma(a):
    a = np.asarray(a, float)
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


def hue(c):
    r, g, b = [float(x) for x in c[:3]]
    mx, mn = max(r, g, b), min(r, g, b)
    d = mx - mn
    if d < 1e-9:
        return 0.0
    if mx == r:
        h = ((g - b) / d) % 6
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    return h * 60


def blur(a, sigma):
    from scipy.ndimage import gaussian_filter
    a = np.asarray(a, float)
    if sigma <= 0:
        return a
    if a.ndim == 3:
        return np.stack([gaussian_filter(a[..., c], sigma) for c in range(a.shape[2])], -1)
    return gaussian_filter(a, sigma)


def smoothstep(e0, e1, x):
    t = np.clip((np.asarray(x, float) - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def jdump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=lambda o: float(o)), encoding="utf-8")
    return path


def canvas(h, w, col="#000000"):
    return np.zeros((h, w, 3)) + hxf(col)


def m_ellipse(h, w, cx, cy, rx, ry=None, ss=4):
    ry = rx if ry is None else ry
    im = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(im).ellipse(((cx - rx) * ss, (cy - ry) * ss, (cx + rx) * ss, (cy + ry) * ss), fill=255)
    return np.asarray(im.resize((w, h), Image.BOX)).astype(float) / 255.0


def m_line(h, w, pts, width, ss=4):
    im = Image.new("L", (w * ss, h * ss), 0)
    d = ImageDraw.Draw(im)
    p = [(x * ss, y * ss) for x, y in pts]
    d.line(p, fill=255, width=max(1, int(round(width * ss))), joint="curve")
    r = width * ss / 2
    for x, y in (p[0], p[-1]):
        d.ellipse((x - r, y - r, x + r, y + r), fill=255)
    return np.asarray(im.resize((w, h), Image.BOX)).astype(float) / 255.0


def m_text(h, w, text, size, xy, ss=2):
    f = font(size * ss)
    im = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(im).text((xy[0] * ss, xy[1] * ss), text, font=f, fill=255)
    return np.asarray(im.resize((w, h), Image.BOX)).astype(float) / 255.0


def font(size=24):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def fill(cv, mask, col, alpha=1.0, blur_r=0.0, mode="normal"):
    m = blur(mask, blur_r / 2.0) if blur_r else mask
    a = (m * alpha)[..., None]
    c = hxf(col) if isinstance(col, str) else np.asarray(col, float)
    if mode == "add":
        return cv + c * a
    if mode == "screen":
        return cv + c * a * (1 - np.minimum(cv, 1))
    if mode == "multiply":
        return cv * (1 - a) + cv * c * a
    return cv * (1 - a) + c * a


def glow(cv, mask, col, radius, alpha):
    return fill(cv, mask, col, alpha, blur_r=radius, mode="add")


def dist_map(h, w, cx, cy):
    yy, xx = np.mgrid[0:h, 0:w]
    return np.hypot(xx - cx, yy - cy)


def rolloff(x, k=.82):
    y = np.array(x, float, copy=True)
    m = y > k
    y[m] = k + (1 - k) * np.tanh((y[m] - k) / (1 - k))
    return np.clip(y, 0, 1)


def sphere(h, w, cx, cy, r):
    yy, xx = np.mgrid[0:h, 0:w]
    nx, ny = (xx - cx) / r, -(yy - cy) / r
    d2 = nx ** 2 + ny ** 2
    m = d2 < 1
    nz = np.sqrt(np.clip(1 - d2, 0, 1))
    return np.stack([nx, ny, nz], -1) * m[..., None], m


def norm(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def kelvin(k):
    t = k / 100.0
    r = 255 if t <= 66 else 329.698727446 * (t - 60) ** -0.1332047592
    g = 99.4708025861 * math.log(t) - 161.1195681661 if t <= 66 else 288.1221695283 * (t - 60) ** -0.0755148492
    b = 255 if t >= 66 else (0 if t <= 19 else 138.5177312231 * math.log(t - 10) - 305.0447927307)
    return tuple(int(round(min(255, max(0, v)))) for v in (r, g, b))


def fbm(h, w, seed, octaves=5, base=4):
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w))
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        n = base * 2 ** o
        g = rng.random((n + 1, n + 1))
        img = np.asarray(Image.fromarray((g * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)).astype(float) / 255
        out += amp * img
        tot += amp
        amp *= .5
    return out / tot


def perlin1d(x, seed):
    rng = np.random.default_rng(seed)
    grads = rng.uniform(-1, 1, 4096)
    x = np.asarray(x, float)
    i0 = np.floor(x).astype(int)
    f = x - i0
    g0, g1 = grads[i0 % 4096], grads[(i0 + 1) % 4096]
    u = f * f * f * (f * (f * 6 - 15) + 10)
    return (g0 * f * (1 - u) + g1 * (f - 1) * u) * 2


def polyline_len(pts):
    return [0.0] + list(np.cumsum([math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts[:-1], pts[1:])]))


def sub_path(pts, l0, l1):
    cum = polyline_len(pts)
    out = []
    for s in np.linspace(l0, l1, 40):
        i = max(0, min(len(pts) - 2, int(np.searchsorted(cum, s) - 1)))
        t = (s - cum[i]) / max(cum[i + 1] - cum[i], 1e-9)
        out.append((pts[i][0] + t * (pts[i + 1][0] - pts[i][0]), pts[i][1] + t * (pts[i + 1][1] - pts[i][1])))
    return out


def rrect_ring(h, w, cx, cy, half_w, half_h, thick, ss=2):
    im = Image.new("L", (w * ss, h * ss), 0)
    d = ImageDraw.Draw(im)
    box = ((cx - half_w) * ss, (cy - half_h) * ss, (cx + half_w) * ss, (cy + half_h) * ss)
    d.rounded_rectangle(box, radius=max(1, int(min(half_w, half_h) * .3 * ss)), outline=255, width=max(1, int(thick * ss)))
    return np.asarray(im.resize((w, h), Image.BOX)).astype(float) / 255


def bolt_path(seed):
    rng = np.random.default_rng(seed)
    x, y, pts = 150.0, 0.0, [(150.0, 0.0)]
    while y < 430:
        x += rng.uniform(-30, 18)
        y += rng.uniform(18, 34)
        pts.append((x, y))
    return pts


def flash(t):
    return max(0, 1 - abs(t - 10.6) / .09) + .55 * max(0, 1 - abs(t - 10.82) / .07)


def radial_wash(h, w, cx, cy, rx, ry, col, a):
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.hypot((xx - cx) / rx, (yy - cy) / ry)
    return np.clip(1 - d, 0, 1)[..., None] * hxf(col) * a, np.clip(1 - d, 0, 1) * a


def wander(t, w, h):
    return w / 2 + math.sin(.32 * t) * .13 * w, .48 * h + math.cos(.38 * t) * .08 * h


def aurora_frame(t, period=8.0, w=160, h=90, accent="#2ee6a0"):
    cv = canvas(h, w, "#06050a")
    yy, xx = np.mgrid[0:h, 0:w]
    for k, (cx, cy, s) in enumerate(((.25, .75, .5), (.55, .8, .45), (.8, .7, .4))):
        ph = 2 * math.pi * (t / period + k / 3)
        x, y = cx * w + 15 * math.sin(ph), cy * h + 5 * math.cos(ph)
        a = np.clip(1 - np.hypot(xx - x, yy - y) / (s * w / 2), 0, 1) ** 2 * .6
        cv = cv * (1 - a[..., None]) + hxf(accent) * a[..., None]
    v = 1 - .15 * smoothstep(.5, 1.0, np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2)) / math.sqrt(2))
    return blur(cv, 4) * v[..., None]


BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0


def threshold_bloom(img, thr, strength, radius_px, tint=(1, 1, 1)):
    hi = np.maximum(img - thr, 0)
    return img + (blur(hi, radius_px) * strength + blur(hi, 3 * radius_px) * strength * .5) * np.array(tint)


def radial_rays(img, cx, cy, samples=64, decay=.972, stride=.55, thr=.7, gain=.55, sky=None):
    h, w = img.shape[:2]
    src = np.where((luma(img) > thr)[..., None], img, 0)
    if sky is not None:
        src = src * sky[..., None]
    from scipy.ndimage import map_coordinates
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    acc = np.zeros_like(img)
    wgt = 1.0
    for k in range(samples):
        f = 1 - stride * k / samples
        sy, sx = cy + (yy - cy) * f, cx + (xx - cx) * f
        for c in range(3):
            acc[..., c] += map_coordinates(src[..., c], [sy, sx], order=1, mode="constant") * wgt
        wgt *= decay
    return acc / samples * gain * 4


def make_post(hdr, sun=None, bloom=.22, threshold=.9, radius=.6, vignette=.42, ca=1.2, grain=.16, clamp=48.0, seed=0):
    img = np.nan_to_num(hdr, nan=0.0, posinf=clamp, neginf=0.0)
    img = np.clip(img, 0, clamp)                                      # NaN / firefly guard
    h, w = img.shape[:2]
    img = threshold_bloom(img, threshold, bloom * 4, radius * 10)
    if sun is not None:
        img = img + radial_rays(img, sun[0], sun[1], thr=threshold)
    y = luma(np.clip(img, 0, 1))[..., None]
    img = img * (np.array([.92, .98, 1.08]) * (1 - y) + np.array([1.08, 1.0, .92]) * y)
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2)) / math.sqrt(2)
    img = img * (1 - vignette * smoothstep(.35, .95, r))[..., None]
    rng = np.random.default_rng(seed)
    img = img + (rng.random((h, w, 1)) - .5) * grain * .1
    return rolloff(img)


def exposure_curve(t, dur, e):
    return e * smoothstep(0, .35, t) * (1 - .1 * smoothstep(dur - .6, dur, t))


def chroma_ab(img, ca, width_ref=1920):
    from scipy.ndimage import map_coordinates
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    u, v = xx / w - .5, yy / h - .5
    r = np.hypot(u, v)
    off = (ca / width_ref) * r * 4
    out = img.copy()
    out[..., 0] = map_coordinates(img[..., 0], [(v * (1 - off) + .5) * h, (u * (1 - off) + .5) * w], order=1, mode="nearest")
    out[..., 2] = map_coordinates(img[..., 2], [(v * (1 + off) + .5) * h, (u * (1 + off) + .5) * w], order=1, mode="nearest")
    return out


def vfx_chain(src, t, nodes):
    img = src.copy()
    h, w = img.shape[:2]
    from scipy.ndimage import map_coordinates
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    for n in nodes:
        if n["type"] == "wave-warp":
            dx = n.get("amp", 3) * np.sin(2 * math.pi * (yy / n.get("wavelength", 20) + t))
            img = np.stack([map_coordinates(img[..., c], [yy, xx + dx], order=1, mode="nearest") for c in range(3)], -1)
        elif n["type"] == "displacement-map":
            rng = np.random.default_rng(n.get("seed", 1))
            dmap = blur(rng.random((h, w)), 3) - .5
            img = np.stack([map_coordinates(img[..., c], [yy + dmap * 8, xx], order=1, mode="nearest") for c in range(3)], -1)
        elif n["type"] == "pixelate":
            s = n.get("size", 8)
            img = np.kron(img[::s, ::s], np.ones((s, s, 1)))[:h, :w]
        elif n["type"] == "bloom":
            img = threshold_bloom(img, .7, .8, 3)
    return np.clip(img, 0, 1)


def shimmer_frames(text, rtl, n=24, w=300, h=80):
    mask = m_text(h, w, text, 48, (10, 10))
    frames, peaks = [], []
    for i in range(n):
        p = i / (n - 1)
        pos = (0 + p) if rtl else (1 - p)               # background-position 100% -> 0% (LTR), 0% -> 100% for RTL
        X = np.linspace(0, 1, w)
        gx = (X + 2 * pos) / 3                           # 300% wide background: offset = (W - 3W) * pos
        band = np.interp(gx, [0, .40, .47, .50, .53, .60, 1], [0, 0, .6, 1, .6, 0, 0])
        col = hxf("#e9e1cf")[None] * (1 - band[:, None]) + hxf("#ffffff")[None] * band[:, None]
        f = canvas(h, w, "#101010") * (1 - mask[..., None]) + col[None] * mask[..., None]
        frames.append(f)
        peaks.append(int(np.argmax(band)) if band.max() > .5 else None)
    return frames, peaks, mask


def star_path(cx, cy, r, rot):
    pts = []
    for k in range(8):
        rr = r if k % 2 == 0 else r * .25
        a = rot + k * math.pi / 4
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return pts


def sparkle_schedule(seed, dur=3.0, life=.6, rate=13.0):
    rng = np.random.default_rng(seed)
    t, out = 0.0, []
    while t < dur:
        out.append((t, float(rng.uniform(10, 290)), float(rng.uniform(10, 70))))
        t += 1 / rate
    return out


def angular_period(field, cx, cy, r0, r1, a0=-180, a1=180):
    h, w = field.shape
    yy, xx = np.mgrid[0:h, 0:w]
    rr = np.hypot(xx - cx, yy - cy)
    ang = np.degrees(np.arctan2(yy - cy, xx - cx))
    band = (rr > r0) & (rr < r1) & (ang > a0) & (ang < a1)
    bins = np.linspace(a0, a1, 721)
    idx = np.digitize(ang[band], bins)
    vals = field[band]
    prof = np.array([vals[idx == k].mean() if np.any(idx == k) else np.nan for k in range(1, len(bins))])
    prof = np.nan_to_num(prof - np.nanmean(prof), nan=0.0)
    spec = np.abs(np.fft.rfft(prof))
    if spec[1:].max() < 1e-9:
        return None, prof
    k = int(np.argmax(spec[1:])) + 1
    return (a1 - a0) / k, prof


FLARE50 = [("soft", 420, 0.0, "#ffe2b0"), ("ring", 90, .35, "#ffd0a0"), ("soft", 60, .55, "#aad4ff"), ("ring", 140, .75, "#ffc8a0"),
           ("soft", 40, .95, "#ffffff")]


def lens_flare(h, w, sun, occluded=False, scale=.15):
    cv = np.zeros((h, w, 3))
    centres = []
    if occluded:
        return cv, centres
    cx, cy = w / 2, h / 2
    for kind, size, dist, col in FLARE50:
        px = sun[0] + (cx - sun[0]) * 2 * dist
        py = sun[1] + (cy - sun[1]) * 2 * dist
        r = size * scale / 2
        d = dist_map(h, w, px, py) / r
        prof = np.clip(1 - d, 0, 1) ** 2 if kind == "soft" else np.exp(-((d - .85) / .08) ** 2)
        cv = cv + prof[..., None] * hxf(col) * .6
        centres.append((px, py))
    return cv, centres


def painter_flare(h, w, c, col, size, streak, strength, ghosts=3):
    cv = np.zeros((h, w, 3))
    cv = glow(cv, m_ellipse(h, w, c[0], c[1], size * .25), col, size * .4, strength)
    st = fill(np.zeros((h, w, 3)), m_ellipse(h, w, c[0], c[1], streak / 2, .09 * size / 2), col, strength, blur_r=3, mode="add")
    cv = cv + st
    cv = fill(cv, m_ellipse(h, w, c[0], c[1], .55 * streak / 2, .04 * size / 2), "#ffffff", strength, blur_r=1.5, mode="add")
    cx, cy = w / 2, h / 2
    gpos = []
    for k in range(ghosts):
        t = 1 + .55 * k
        gx, gy = cx - (c[0] - cx) * t * .5 * (k + 1) / ghosts, cy - (c[1] - cy) * t * .5 * (k + 1) / ghosts
        cv = fill(cv, m_ellipse(h, w, gx, gy, size * .1 * (1 + .3 * k)), col, .12, blur_r=2, mode="add")
        gpos.append((gx, gy))
    return cv, gpos, st


def flash_curve(t, at, peak=.85, attack=.06, decay=.35, again=True):
    def one(tt, pk):
        if tt < 0:
            return 0.0
        if tt < attack:
            return pk * tt / attack
        u = min(1, (tt - attack) / decay)
        return pk * (1 - u) ** 4                    # power4.out decay
    v = one(t - at, peak)
    if again:
        v = max(v, one(t - at - .16, peak * .5))
    return v


def schedule_flashes(times, max_per_s=3):
    out = []
    for t in sorted(times):
        if sum(1 for o in out if t - 1 < o <= t) < max_per_s:
            out.append(t)
    return out


def corona(r, bass):
    return np.exp(-np.maximum(0, r - .074) * (46 - 12 * bass)) * (.55 + 1.1 * bass)


def softness_deg(size, dist):
    return math.degrees(2 * math.atan(size / (2 * dist)))


def light_dir(az, el):
    a, e = math.radians(az), math.radians(el)
    return norm([math.sin(a) * math.cos(e), math.sin(e), math.cos(a) * math.cos(e)])


SETUPS59 = {"rembrandt": (45, 4, 5600, "classic drama"), "loop": (30, 3, 5600, "natural portrait"), "split": (90, 8, 5600, "conflict"),
            "high_key": (30, 1.5, 5600, "clean, commercial"), "candle": (60, 6, 1900, "intimacy"), "window": (90, 3, 6000, "documentary")}


def lightplan(name):
    ang, ratio, k, mood = SETUPS59[name]
    fill_stops = math.log2(ratio - 1) if ratio > 1 else 0
    clock = (6 + round(ang / 30)) % 12 or 12
    grid = [[" "] * 13 for _ in range(7)]
    grid[6][6] = "C"
    grid[3][6] = "S"
    a = math.radians(180 - ang)
    grid[3 - round(3 * math.cos(a))][6 + round(6 * math.sin(a))] = "K"
    lines = ["## MOOD", "%s: %s" % (name, mood), "## TOP VIEW", "\n".join("".join(r) for r in grid),
             "## LIGHTS", "| role | fixture | power | angle | gel |", "| key | softbox | 0 st | %d deg (%d o'clock) | %d K |" % (ang, clock, k),
             "| fill | bounce | -%.2f st | camera side | %d K |" % (fill_stops, k),
             "## RATIOS & EXPOSURE", "ratio %g:1 -> fill %.2f stops under key" % (ratio, fill_stops),
             "## CAMERA", "ISO 400, 1/50 s, f/2.8, WB %d K" % k, "## BUDGET VERSION", "window + lamp + foam board + phone light",
             "## COMMON MISTAKES", "mixed colour temperatures; fill too strong", "## PROMPT",
             "%s lighting, key %d degrees, %g:1 ratio, %d K" % (name, ang, ratio, k)]
    return "\n".join(lines), fill_stops, clock


def light_calc(op):
    k = op["op"]
    if k == "ratio":
        r = 2 ** op["key_stops_over_fill"] + 1
        mood = "flat" if r <= 2.5 else "natural" if r <= 4.5 else "dramatic" if r <= 9 else "noir"
        return {"ratio": r, "mood": mood}
    if k == "fill_stops":
        return {"stops": math.log2(op["ratio"] - 1)}
    if k == "softness":
        d = softness_deg(op["size_m"], op["dist_m"])
        return {"deg": round(d, 1), "label": "very soft" if d > 45 else "soft" if d > 20 else "medium" if d > 8 else "hard"}
    if k == "falloff":
        return {"stops": 2 * math.log2(op["d2"] / op["d1"])}
    if k == "ev":
        return {"ev": round(math.log2(op["f"] ** 2 / op["t"]) - math.log2(op["iso"] / 100), 2)}
    if k == "shutter":
        return {"t": op["angle"] / 360 / op["fps"]}
    if k == "gn":
        return {"f": op["gn"] * math.sqrt(op["iso"] / 100) / op["dist"]}
    if k == "mired":
        s = 1e6 / op["to_k"] - 1e6 / op["from_k"]
        gels = [("Full CTB", -159), ("1/2 CTB", -68), ("1/4 CTB", -30), ("1/8 CTB", -12), ("1/8 CTO", 20), ("1/4 CTO", 42),
                ("1/2 CTO", 81), ("Full CTO", 159)]
        return {"mired": round(s, 1), "gel": min(gels, key=lambda g: abs(g[1] - s))[0]}
    raise ValueError(k)


def rim(mask, toward, width, soft=.6):
    from scipy.ndimage import shift as nd_shift
    d = norm(list(toward) + [0])[:2]
    shifted = nd_shift(mask, (-d[1] * width, -d[0] * width), order=1, mode="constant")   # copy shifted away from the light
    return blur(np.clip(mask - shifted, 0, 1), soft)


def shade(mask, centre, r, light, lit, dark, core=.35):
    h, w = mask.shape
    lx, ly = norm([light[0] - centre[0], light[1] - centre[1], 0])[:2]
    hx_, hy = centre[0] + r * core * lx, centre[1] + r * core * ly
    t = np.clip(dist_map(h, w, hx_, hy) / (r * (1 + core)), 0, 1)[..., None]
    col = hxf(lit) * (1 - t) + hxf(dark) * t
    return col * mask[..., None], (hx_, hy)


def crystal(n, V, L, depth, iceA, iceB, skyA, skyB, rim_c, fog):
    ice = iceA * (1 - (n[..., 1:2] * .5 + .5)) + iceB * (n[..., 1:2] * .5 + .5)
    R = 2 * np.sum(n * V, -1, keepdims=True) * n - V
    sk = skyA + (skyB - skyA) * smoothstep(-.6, .9, R[..., 1:2])
    ndl = np.clip(np.sum(n * L, -1, keepdims=True), 0, None)
    fres = (1 - np.clip(np.sum(n * V, -1, keepdims=True), 0, None)) ** 2.6
    H = (L + V) / np.linalg.norm(L + V)
    spec = np.clip(np.sum(n * H, -1, keepdims=True), 0, None) ** 64
    c = ice * (.35 + .65 * ndl) + sk * .35 + rim_c * fres * .9 + spec * .8
    f = smoothstep(6, 24, depth)[..., None]
    return c * (1 - f) + fog * f, fres, spec


def refract(I, N, eta):
    cosi = -np.sum(N * I, -1, keepdims=True)
    k = 1 - eta ** 2 * (1 - cosi ** 2)
    return eta * I + (eta * cosi - np.sqrt(np.clip(k, 0, None))) * N


def read_light(img):
    y = luma(img) * 255
    h, w = y.shape
    halves = {"left": y[:, :w // 2].mean(), "right": y[:, w // 2:].mean(), "top": y[:h // 2].mean(), "bottom": y[h // 2:].mean()}
    lr = halves["left"] - halves["right"]
    if abs(lr) < 8:
        return {"side": "even", "stops": 0.0, "ratio": "1:1"}
    lit, shade_ = max(halves["left"], halves["right"]), min(halves["left"], halves["right"])
    stops = math.log2(lit / shade_)
    return {"side": "left" if lr > 0 else "right", "stops": round(stops, 2), "ratio": "%g:1" % round(2 ** stops, 2)}


def sky_dome(h, w, sun_el, sun_az, top, horizon, size=1.0):
    yy, xx = np.mgrid[0:h, 0:w]
    az = (xx / w - .5) * 2 * math.pi
    el = (1 - yy / h) * math.pi / 2
    d = np.stack([np.cos(el) * np.sin(az), np.sin(el), np.cos(el) * np.cos(az)], -1)
    s_dir = norm([math.cos(math.radians(sun_el)) * math.sin(math.radians(sun_az)),
                                                                        math.sin(math.radians(sun_el)),
                                                                        math.cos(math.radians(sun_el)) * math.cos(math.radians(sun_az))])
    t = smoothstep(0, 1, el / (math.pi / 2))[..., None]
    col = hxf(horizon) * (1 - t) + hxf(top) * t
    s = np.clip(d @ s_dir, 0, 1)
    sun = s ** (1800 / size) * 30 + s ** 40 * .8 + s ** 6 * .25
    return col + sun[..., None] * hxf("#ffd29a"), s_dir


def point_size(a_size, z):
    return float(np.clip(a_size * 1100 / -z, 1.5, 90))


def lantern_flicker(t):
    return .9 + .07 * perlin1d(7 * t + 1.3, 11) + .04 * perlin1d(19 * t + 4.1, 12)


HEAT83 = ([0, .12, .30, .45, .60, .78, 1.0], ["#04040c", "#2b0a5a", "#1f9e4a", "#f2d930", "#f28a1a", "#e0301e", "#ffffff"])


def heat_map(v, cap=.75):
    stops, cols = HEAT83
    v = np.minimum(np.asarray(v, float), cap)
    c = np.array([hxf(x) for x in cols])
    out = np.zeros(v.shape + (3,)) + c[0]
    for i in range(len(stops) - 1):
        t = smoothstep(stops[i], stops[i + 1], v)
        out = np.where((v >= stops[i])[..., None], c[i] * (1 - t[..., None]) + c[i + 1] * t[..., None], out)
    return out


def p01_frame(t, w=480, h=854):
    n = 321
    pts = [(40 + i * (w - 80) / (n - 1), h / 2 + 95 * math.exp(-i / 600) * math.sin(3 * math.pi * i / (n - 1))) for i in range(n)]
    k = max(2, int(n * min(1, t / 2.6)))
    part = pts[:k]
    base = Image.new("RGB", (w, h), (8, 11, 23))
    d = ImageDraw.Draw(base)
    for y in range(0, h, 48):
        d.line((0, y, w, y), fill=(14, 18, 34))
    halo = Image.new("RGB", (w, h), (0, 0, 0))
    ImageDraw.Draw(halo).line(part, fill=(0, 150, 195), width=17, joint="curve")
    halo = halo.filter(ImageFilter.GaussianBlur(21))
    img = Image.blend(base, halo, 0.44)
    d = ImageDraw.Draw(img)
    d.line(part, fill=(31, 200, 245), width=6, joint="curve")
    d.line(part, fill=(204, 254, 255), width=2, joint="curve")
    x, y = part[-1]
    d.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(255, 255, 255))
    return img, part


def tinted_bloom(img, light_col, thr=.8, strength=1.2, tint=.6):
    hi = np.maximum(img - thr, 0)
    b = blur(hi, 6) * strength
    core = b * (1 - tint) + luma(b)[..., None] * hxf(light_col) * tint / max(float(luma(hxf(light_col))), 1e-6)
    return img + core


def flash_plan(requests, fps=30):
    big, out = [], []
    for t, kind, frames in sorted(requests):
        if sum(1 for o in out if t - 1 < o[0] <= t) >= 3:
            continue
        if kind == "big" and any(t - 1 < b <= t for b in big):
            continue
        if kind == "white":
            frames = min(frames, 2)
        if kind == "big":
            big.append(t)
        out.append((t, kind, frames))
    return out
