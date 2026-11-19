"""Helpers of runners/fam_color_palette_grading.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from .core import fx
import json
import math
import numpy as np
import re
import subprocess


def hx(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def tohex(c):
    return "#%02x%02x%02x" % tuple(int(round(max(0, min(255, float(v))))) for v in c[:3])


def save(a, p):
    Image.fromarray(np.clip(np.rint(np.asarray(a, dtype=float)), 0, 255).astype(np.uint8)).save(str(p))
    return p


def load(p):
    return np.asarray(Image.open(str(p)).convert("RGB")).astype(float)


def ffimg(src, vf, dst, *extra_inputs):
    args = ["-i", str(src)]
    for e in extra_inputs:
        args += ["-i", str(e)]
    if extra_inputs:
        args += ["-filter_complex", vf]
    else:
        args += ["-vf", vf + ",format=rgb24"]
    fx.ffmpeg(*args, "-frames:v", "1", "-pix_fmt", "rgb24", str(dst))
    return load(dst)


def write_video(path, frames, fps=30, codec="libx264", crf="17", extra=()):
    frames = [np.clip(np.rint(f), 0, 255).astype(np.uint8) for f in frames]
    h, w = frames[0].shape[:2]
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", "%dx%d" % (w, h), "-r", str(fps), "-i", "-"]
    if codec == "ffv1":
        cmd += ["-c:v", "ffv1", "-pix_fmt", "bgr0"]
    else:
        cmd += ["-c:v", codec, "-crf", crf, "-pix_fmt", "yuv420p", *extra]
    cmd.append(str(path))
    done = subprocess.run(cmd, input=b"".join(f.tobytes() for f in frames), capture_output=True, timeout=60)
    if done.returncode:
        raise RuntimeError(done.stderr.decode(errors="replace")[-300:])
    return path


def lin(c):
    c = np.asarray(c, dtype=float) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def unlin(v):
    v = np.clip(np.asarray(v, dtype=float), 0, 1)
    return 255.0 * np.where(v <= 0.0031308, v * 12.92, 1.055 * v ** (1 / 2.4) - 0.055)


def rel_lum(c):
    l = lin(c)
    return float(0.2126 * l[..., 0] + 0.7152 * l[..., 1] + 0.0722 * l[..., 2]) if np.ndim(l) == 1 else \
        0.2126 * l[..., 0] + 0.7152 * l[..., 1] + 0.0722 * l[..., 2]


def contrast(a, b):
    la, lb = rel_lum(hx(a) if isinstance(a, str) else a), rel_lum(hx(b) if isinstance(b, str) else b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def luma(a):
    a = np.asarray(a, dtype=float)
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


def rgb2hsv(a):
    a = np.asarray(a, dtype=float) / 255.0
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx, mn = a.max(-1), a.min(-1)
    d = mx - mn
    h = np.zeros_like(mx)
    m = d > 1e-9
    rm = m & (mx == r)
    gm = m & (mx == g) & ~rm
    bm = m & ~rm & ~gm
    h[rm] = ((g - b)[rm] / d[rm]) % 6
    h[gm] = (b - r)[gm] / d[gm] + 2
    h[bm] = (r - g)[bm] / d[bm] + 4
    s = np.where(mx > 1e-9, d / np.maximum(mx, 1e-9), 0)
    return np.stack([h * 60.0, s, mx], -1)


def hsv2rgb(hsv):
    h, s, v = hsv[..., 0] % 360 / 60.0, hsv[..., 1], hsv[..., 2]
    i = np.floor(h).astype(int) % 6
    f = h - np.floor(h)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    r = np.choose(i, [v, q, p, p, t, v])
    g = np.choose(i, [t, v, v, q, p, p])
    b = np.choose(i, [p, p, t, v, v, q])
    return np.stack([r, g, b], -1) * 255.0


def hue_of(c):
    return float(rgb2hsv(np.array(c, dtype=float))[0])


def hue_dist(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


def hsl2hex(h, s, l):
    import colorsys
    r, g, b = colorsys.hls_to_rgb((h % 360) / 360.0, l, s)
    return tohex((r * 255, g * 255, b * 255))


def hex2hsl(hexc):
    import colorsys
    r, g, b = [v / 255.0 for v in hx(hexc)]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return h * 360, s, l


def lab(a):
    l = lin(a)
    m = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = l @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    L = 116 * f[..., 1] - 16
    A = 500 * (f[..., 0] - f[..., 1])
    B = 200 * (f[..., 1] - f[..., 2])
    return np.stack([L, A, B], -1)


def blur(a, sigma):
    from scipy.ndimage import gaussian_filter
    a = np.asarray(a, dtype=float)
    if a.ndim == 3:
        return np.stack([gaussian_filter(a[..., c], sigma) for c in range(a.shape[2])], -1)
    return gaussian_filter(a, sigma)


def psnr(a, b):
    mse = float(np.mean((np.asarray(a, float) - np.asarray(b, float)) ** 2))
    return 99.0 if mse == 0 else 10 * math.log10(255.0 ** 2 / mse)


def ramp(w=256, h=32):
    x = np.linspace(0, 255, w)
    return np.repeat(np.repeat(x[None, :, None], h, 0), 3, 2)


def testsrc_png(path, size="320x180"):
    fx.ffmpeg("-f", "lavfi", "-i", "testsrc2=s=%s:r=1:d=1" % size, "-frames:v", "1", "-pix_fmt", "rgb24", str(path))
    return load(path)


def chart(colors, cell=24):
    a = np.zeros((cell, cell * len(colors), 3))
    for i, c in enumerate(colors):
        a[:, i * cell:(i + 1) * cell] = hx(c) if isinstance(c, str) else c
    return a


def patch(a, i, cell=24, m=4):
    return a[m:cell - m, i * cell + m:(i + 1) * cell - m].reshape(-1, 3).mean(0)


def font(size=24, bold=True):
    for p in (["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"] if bold else []) + \
             ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/freefont/FreeSans.ttf"]:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def jdump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=lambda o: float(o)), encoding="utf-8")
    return path


def smoothstep(e0, e1, x):
    t = np.clip((np.asarray(x, float) - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def css_filter(a, ops):
    v = np.asarray(a, float) / 255.0
    for name, amt in ops:
        if name in ("grayscale", "sepia", "saturate", "hue-rotate"):
            if name == "grayscale":
                k = 1 - amt
                m = [[0.2126 + 0.7874 * k, 0.7152 - 0.7152 * k, 0.0722 - 0.0722 * k],
                     [0.2126 - 0.2126 * k, 0.7152 + 0.2848 * k, 0.0722 - 0.0722 * k],
                     [0.2126 - 0.2126 * k, 0.7152 - 0.7152 * k, 0.0722 + 0.9278 * k]]
            elif name == "sepia":
                k = 1 - amt
                m = [[0.393 + 0.607 * k, 0.769 - 0.769 * k, 0.189 - 0.189 * k],
                     [0.349 - 0.349 * k, 0.686 + 0.314 * k, 0.168 - 0.168 * k],
                     [0.272 - 0.272 * k, 0.534 - 0.534 * k, 0.131 + 0.869 * k]]
            elif name == "saturate":
                s = amt
                m = [[0.213 + 0.787 * s, 0.715 - 0.715 * s, 0.072 - 0.072 * s],
                     [0.213 - 0.213 * s, 0.715 + 0.285 * s, 0.072 - 0.072 * s],
                     [0.213 - 0.213 * s, 0.715 - 0.715 * s, 0.072 + 0.928 * s]]
            else:
                c, s = math.cos(math.radians(amt)), math.sin(math.radians(amt))
                m = [[0.213 + c * 0.787 - s * 0.213, 0.715 - c * 0.715 - s * 0.715, 0.072 - c * 0.072 + s * 0.928],
                     [0.213 - c * 0.213 + s * 0.143, 0.715 + c * 0.285 + s * 0.140, 0.072 - c * 0.072 - s * 0.283],
                     [0.213 - c * 0.213 - s * 0.787, 0.715 - c * 0.715 + s * 0.715, 0.072 + c * 0.928 + s * 0.072]]
            v = v @ np.array(m).T
        elif name == "contrast":
            v = v * amt + (0.5 - 0.5 * amt)
        elif name == "brightness":
            v = v * amt
        v = np.clip(v, 0, 1)
    return v * 255.0


def chroma_spread(a):
    a = np.asarray(a, float)
    return a.max(-1) - a.min(-1)


def hald_to_cube(hald_png, cube_path, n=33, level=8):
    from scipy.ndimage import map_coordinates
    h = load(hald_png).reshape(-1, 3) / 255.0
    s = level * level
    lut = h.reshape(s, s, s, 3)  # [b][g][r]
    g = np.linspace(0, s - 1, n)
    bb, gg, rr = np.meshgrid(g, g, g, indexing="ij")
    coords = np.stack([bb.ravel(), gg.ravel(), rr.ravel()])
    vals = np.stack([map_coordinates(lut[..., c], coords, order=1) for c in range(3)], -1)
    lines = ["TITLE \"baked\"", "LUT_3D_SIZE %d" % n] + ["%.6f %.6f %.6f" % tuple(v) for v in vals]
    cube_path.write_text("\n".join(lines) + "\n")
    return cube_path


def write_cube(path, fn, n=33):
    g = np.linspace(0, 1, n)
    bb, gg, rr = np.meshgrid(g, g, g, indexing="ij")
    rgb = np.stack([rr.ravel(), gg.ravel(), bb.ravel()], -1)
    out = np.clip(fn(rgb), 0, 1)
    path.write_text("LUT_3D_SIZE %d\n" % n + "\n".join("%.6f %.6f %.6f" % tuple(v) for v in out) + "\n")
    return path


def basma_chain(look):
    k = []
    c, s, b = look.get("contrast", 1), look.get("saturation", 1), look.get("brightness", 1)
    k.append("eq=contrast=%g:saturation=%g:brightness=%g" % (c, s, (b - 1) * 0.5))
    tone = look.get("tone")
    if tone == "teal_orange":
        k.append("colorbalance=rs=-0.08:bs=0.10:rh=0.08:bh=-0.06")
    elif tone == "bw":
        k.append("hue=s=0")
    elif tone in ("warm", "cool"):
        sgn = 1 if tone == "warm" else -1
        kk = look.get("k", .2)
        k.append("colorbalance=rm=%g:bm=%g" % (sgn * .6 * kk, -sgn * .6 * kk))
    if look.get("vignette", 0) > 0.3:
        k.append("vignette=PI/5")
    if look.get("grain", 0) > 0:
        k.append("noise=alls=%d:allf=t" % round(6 + 40 * look["grain"]))
    if look.get("letterbox"):
        k.append("drawbox=x=0:y=0:w=iw:h=ih*0.105:color=black:t=fill,"
                 "drawbox=x=0:y=ih-ih*0.105:w=iw:h=ih:color=black:t=fill")
    return ",".join(k)


MOODS = {"night": ("#0B0F1E", "#221C3B", "#ECBD51", "#F9E094", "blue_hour"),
         "dawn": ("#12142B", "#994329", "#FAA442", "#FFDDA3", "golden_hour"),
         "gold": ("#110D09", "#372715", "#EEAD2B", "#FBD774", "golden_hour"),
         "sea": ("#07131D", "#16444B", "#3CDDD2", "#ACF6F6", "teal_orange"),
         "ink": ("#0A0A0A", "#1C1C1C", "#B2B2B2", "#EBEBEB", "vintage_film")}


def mood_frame(mood, hue_shift, bright, w=160, h=90):
    top, bot, glow, mote, _ = MOODS[mood]
    y = np.linspace(0, 1, h)[:, None, None]
    f = np.array(hx(top)) * (1 - y) + np.array(hx(bot)) * y
    f = np.repeat(f, w, 1)
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.hypot(xx - w / 2, yy - h / 2)
    f = np.where((d < 14)[..., None], np.array(hx(glow), float), f)
    f[5:7, 20:22] = hx(mote)
    hsv = rgb2hsv(f)
    hsv[..., 0] += hue_shift
    return np.clip(hsv2rgb(hsv) * bright, 0, 255)


GRADE_PRESETS = {"neutral": {}, "warm-daylight": {"exposure": .06, "contrast": .07, "temperature": .18, "saturation": .08},
                 "food-pop": {"contrast": .1, "temperature": .14, "saturation": .18},
                 "muted-editorial": {"saturation": -.12, "vignette": .1}, "mono-clean": {"saturation": -1},
                 "deep-contrast": {"contrast": .2}}


def apply_grade(img, grade):
    adj = dict(GRADE_PRESETS.get(grade.get("preset", "neutral"), {}))
    adj.update(grade.get("adjust", {}))
    k = float(np.clip(grade.get("intensity", 1.0), 0, 1))
    clampd = {key: float(np.clip(v, -2, 2) if key == "exposure" else np.clip(v, -1, 1)) for key, v in adj.items()}
    l = lin(img) * 2.0 ** (k * clampd.get("exposure", 0))
    t = k * clampd.get("temperature", 0)
    l = l * np.array([1 + .5 * t, 1.0, 1 - .5 * t])
    v = unlin(l) / 255.0
    c = 1 + k * clampd.get("contrast", 0)
    v = (v - .5) * c + .5
    y = (0.2126 * v[..., 0] + 0.7152 * v[..., 1] + 0.0722 * v[..., 2])[..., None]
    v = y + (v - y) * (1 + k * clampd.get("saturation", 0))
    vig = k * (grade.get("details", {}).get("vignette", 0) + clampd.get("vignette", 0))
    if vig:
        h, w = v.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w]
        d = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2)) / math.sqrt(2)
        v = v * (1 - vig * smoothstep(.4, 1.0, d))[..., None]
    return np.clip(v, 0, 1) * 255.0, clampd


LANES = [("correction", ["too dark", "flat", "too warm", "too cold", "washed", "dark", "مظلم", "باهت"]),
         ("treatment", ["premium", "cinematic", "luxury", "فخم", "سينمائي"]),
         ("shader", ["retro", "vhs", "print", "ascii", "glitch", "camcorder", "8mm", "قديم"]),
         ("privacy", ["blur face", "privacy", "hide", "pixelate", "إخفاء", "طمس"])]


def feedback_lane(text):
    t = text.lower()
    for lane, words in LANES:
        if any(w in t for w in words):
            return lane
    return "framing"


def look_fn(name):
    def f(rgb):
        y = (0.2126 * rgb[:, 0] + 0.7152 * rgb[:, 1] + 0.0722 * rgb[:, 2])[:, None]
        if name == "teal-orange-blockbuster":
            k, c = .85, .18
            o = (rgb - .5) * (1 + c) + .5
            o = o + (1 - y) * np.array([-.04, .05, .09]) + y * np.array([.1, .04, -.03])
        elif name == "bleach-bypass":
            k = .8
            o = (rgb - .5) * 1.55 + .5
            yy = (0.2126 * o[:, 0] + 0.7152 * o[:, 1] + 0.0722 * o[:, 2])[:, None]
            o = yy + (o - yy) * (1 - .72)
        else:  # film-fade
            k = .75
            o = .35 * .5 + rgb * (1 - .35 * .5)
            o = (o - .5) * (1 - .28) + .5
            o = o * np.array([1 + .16 * .25, 1, 1 - .16 * .25])
        return rgb + k * (np.clip(o, 0, 1) - rgb)
    return f


def is_log(stream, profile=None):
    if profile:
        return "log" in profile.lower()
    trc = (stream.get("color_transfer") or "").lower()
    if "log" in trc:
        return True
    return False


def neutral_wb(img, bias=0.0, iters=3):
    hsv = rgb2hsv(img)
    mx = img.max(-1) / 255.0
    m = (mx > .25) & (mx < .85) & (hsv[..., 1] <= .2)
    if m.mean() < .005:
        return img, None
    r, g, b = (img[..., c][m].mean() for c in range(3))
    sr, sb = g / r, g / b                                 # hold G, move R/B
    out = img.copy()
    for _ in range(iters):                                # secant on the R-B target (bias)
        out = np.clip(img * np.array([sr, 1, sb]), 0, 255)
        err = (out[..., 0][m].mean() - out[..., 2][m].mean()) - bias
        if abs(err) < .5:
            break
        sr -= err / (2 * g)
        sb += err / (2 * g)
    sr, sb = float(np.clip(sr, .8, 1.2)), float(np.clip(sb, .8, 1.2))
    return np.clip(img * np.array([sr, 1, sb]), 0, 255), (sr, sb)


def pivot_contrast(y10, c, pivot):
    return (y10 / 1023.0 - pivot) * c * 1023.0 + pivot * 1023.0


SAT_BANDS = {"morning": (50, 110), "day": (60, 120), "afternoon": (60, 130), "evening": (45, 100), "night": (30, 80)}


def sat_floor(img, period):
    spread10 = float(chroma_spread(img).mean()) * 4
    lo, _ = SAT_BANDS[period]
    s = 1.0 if spread10 >= lo else min(1.25, lo / max(spread10, 1e-6))
    y = luma(img)[..., None]
    yn = y / 255.0
    w = np.ones_like(yn)
    w = np.where(yn < .15, .6 + .4 * yn / .15, w)
    w = np.where(yn > .85, .6 + .4 * (1 - yn) / .15, w)
    k = 1 + (s - 1) * w
    return np.clip(y + (img - y) * k, 0, 255), s


def ire_stats(img):
    y = (0.2126 * img[..., 0] + 0.7152 * img[..., 1] + 0.0722 * img[..., 2]) / 255.0 * 100
    return [float(np.percentile(y, p)) for p in (10, 50, 95)], float(np.mean(y > 99) * 100)


def median_cut(px, k):
    boxes = [px]
    while len(boxes) < k:
        scores = [float(np.ptp(b, 0).max()) * len(b) if len(b) > 1 else 0.0 for b in boxes]
        if max(scores) <= 0:
            break
        i = int(np.argmax(scores))
        b = boxes.pop(i)
        ch = int(np.argmax(np.ptp(b, 0)))
        b = b[np.argsort(b[:, ch], kind="stable")]
        vals = b[:, ch]
        m = np.median(vals)
        cut = int(np.searchsorted(vals, m, side="right"))
        if cut <= 0 or cut >= len(b):
            cut = int(np.searchsorted(vals, m, side="left"))
        if cut <= 0 or cut >= len(b):
            boxes.append(b)
            break
        boxes += [b[:cut], b[cut:]]
    return [(b.mean(0), len(b) / len(px)) for b in boxes]


def mccamy(rgb_mean):
    l = lin(rgb_mean)
    m = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    X, Y, Z = m @ l
    x, y = X / (X + Y + Z), Y / (X + Y + Z)
    n = (x - 0.3320) / (0.1858 - y)
    return 449 * n ** 3 + 3525 * n ** 2 + 6823.3 * n + 5520.33


def analyze_colour(img):
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    rb = float(r.mean() - b.mean())
    rg, yb = r - g, .5 * (r + g) - b
    colourful = float(math.hypot(rg.std(), yb.std()) + .3 * math.hypot(rg.mean(), yb.mean()))
    thumb = np.asarray(Image.fromarray(img.astype(np.uint8)).resize((256, 256), Image.NEAREST)).reshape(-1, 3).astype(float)
    pal = sorted(median_cut(thumb, 6), key=lambda t: -t[1])
    return {"cct": float(mccamy(img.reshape(-1, 3).mean(0))), "cast": "warm" if rb > 12 else "cool" if rb < -12 else "neutral",
            "colourfulness": colourful, "palette": [(tohex(c), round(s, 4)) for c, s in pal]}


GELS = [("Full CTB", -159), ("1/2 CTB", -68), ("1/4 CTB", -30), ("1/8 CTB", -12), ("1/8 CTO", 20), ("1/4 CTO", 42),
        ("1/2 CTO", 81), ("Full CTO", 159)]


def mired(from_k, to_k):
    s = 1e6 / to_k - 1e6 / from_k
    gel = min(GELS, key=lambda g: abs(g[1] - s))[0]
    return round(s, 1), gel, "cooler (blue)" if s < 0 else "warmer (orange)"


def stats(img):
    return img.reshape(-1, 3).mean(0), img.reshape(-1, 3).std(0)


def colour_transfer(img, look, strength=.7):
    mu, sd = stats(img)
    g = np.clip(1 + strength * (look[1] / np.maximum(sd, 1e-6) - 1), .6, 1.6)
    o = np.clip(strength * (look[0] - g * mu) + (1 - strength) * (1 - g) * mu, -120, 120)
    return np.clip(img * g + o, 0, 255), g, o


def measure_fix(img):
    y = luma(img)
    p02, p50, p98 = (float(np.percentile(y, q)) for q in (2, 50, 98))
    rng_ = p98 - p02
    c = float(np.clip(200 / rng_, .9, 1.3)) if rng_ < 200 else 1.0
    b = float(np.clip(118 / max(p50, 1), .85, 1.3)) if not (112 <= p50 <= 150) else 1.0
    hsv = rgb2hsv(img)
    s = float(hsv[..., 1].mean())
    sat = float(np.clip(.24 / s, 1, 1.25)) if .05 < s < .18 else 1.0
    m = (hsv[..., 1] < .22) & (y > 50) & (y < 215)
    gains = np.ones(3)
    if m.mean() >= .06:
        mean = img[m].mean(0)
        gains = np.clip(mean.mean() / mean, .82, 1.18)
    out = img * gains
    out = css_filter(out, [("brightness", b), ("contrast", c), ("saturate", sat)])
    return out, {"contrast": c, "brightness": b, "saturation": sat, "gains": gains.tolist(), "p50": p50, "range": rng_}


def look_dna(img):
    hsv = rgb2hsv(img)
    s = float(hsv[..., 1].mean())
    y = luma(img)
    warmth = float((img[..., 0].mean() - img[..., 2].mean()) / 255)
    blue_sh = float((img[..., 2] - img[..., 0])[y < 85].mean()) if (y < 85).any() else 0
    red_hi = float((img[..., 0] - img[..., 2])[y > 150].mean()) if (y > 150).any() else 0
    if s < .07:
        return "bw"
    if blue_sh > 6 and red_hi > 10:
        return "teal_orange"
    if warmth > .1:
        return "golden" if s > .3 else "warm"
    if warmth < -.05:
        return "blue_hour" if y.mean() < 90 else "cool"
    return "clean" if float(y.std() / 255) > .26 and s > .32 else "neutral"


COLOUR_WORDS = {"red": "#d62828", "أحمر": "#d62828", "الأحمر": "#d62828", "blue": "#2f6fd6", "أزرق": "#2f6fd6",
                "الأزرق": "#2f6fd6", "gold": "#c9a227", "ذهبي": "#c9a227", "cyan": "#19c3d9", "سماوي": "#19c3d9",
                "green": "#2a9d4b", "أخضر": "#2a9d4b"}


def parse_colour_request(text):
    words = re.findall(r"[\w؀-ۿ]+", text.lower())
    found = [COLOUR_WORDS[w] for w in words if w in COLOUR_WORDS]
    return (found[0], found[1]) if len(found) >= 2 else None


def recolor(img, src_hex, dst_hex, tolerance=40):
    s, d = np.array(hx(src_hex), float), np.array(hx(dst_hex), float)
    hs, hd = rgb2hsv(s), rgb2hsv(d)
    hsv = rgb2hsv(img)
    v = np.maximum(img.max(-1, keepdims=True), 1)
    norm = img * (s.max() / v)                       # compare at the source brightness, so shading stays in the mask
    m = np.linalg.norm(norm - s, axis=-1) < tolerance
    out = hsv.copy()
    out[..., 0] = np.where(m, hd[0], hsv[..., 0])
    out[..., 1] = np.where(m, np.clip(hsv[..., 1] * hd[1] / max(hs[1], 1e-6), 0, 1), hsv[..., 1])
    out[..., 2] = np.where(m, np.clip(hsv[..., 2] * hd[2] / max(hs[2], 1e-6), 0, 1), hsv[..., 2])
    return hsv2rgb(out), m


def logo_palette(img, max_colors=16, min_share=.001):
    px = img.reshape(-1, 3)
    q = (px // 8).astype(int)
    keys, inv, counts = np.unique(q[:, 0] * 1024 + q[:, 1] * 32 + q[:, 2], return_inverse=True, return_counts=True)
    order = np.argsort(-counts)
    cands = []
    for k in order:
        if counts[k] / len(px) < min_share:
            break
        c = px[inv == k].mean(0)
        if all(np.linalg.norm(c - p) >= 30 for p in cands):
            cands.append(c)
        if len(cands) >= max_colors:
            break
    pal = []
    for c in cands:
        near = px[np.linalg.norm(px - c, axis=1) < 22]
        pal.append((near.mean(0), len(near) / len(px)))
    # drop antialias blends: a candidate that is a two-colour mixture t in .08..92 of stronger ones within 18
    keep = []
    for i, (c, s) in enumerate(pal):
        blend = False
        for j, (a, sa) in enumerate(pal):
            for k, (b, sb) in enumerate(pal):
                if len({i, j, k}) < 3 or sa < s or sb < s:
                    continue
                d = b - a
                t = float(np.dot(c - a, d) / max(np.dot(d, d), 1e-9))
                if .08 <= t <= .92 and np.linalg.norm(a + t * d - c) < 18:
                    blend = True
        if not blend:
            keep.append((c, s))
    return keep


def walk_until(hexc, bg, ratio, direction):
    h, s, l = hex2hsl(hexc)
    grounds = bg if isinstance(bg, (list, tuple)) else [bg]
    for _ in range(200):
        c = hsl2hex(h, s, l)
        if all(contrast(c, g) >= ratio for g in grounds):
            return c
        l = min(1, max(0, l + direction * .005))
    return hsl2hex(h, s, l)


def design_tokens(brand, name="k"):
    h, s, _ = hex2hsl(brand)
    light = {"bg": "#faf9f7", "surface": "#ffffff", "ink": hsl2hex(h, .35, .1)}
    dark = {"bg": hsl2hex(h, .2, .07), "surface": hsl2hex(h, .18, .11), "ink": hsl2hex(h, .2, .93)}
    light["brand"] = walk_until(brand, [light["bg"], light["surface"]], 4.6, -1)
    dark["brand"] = walk_until(brand, [dark["bg"], dark["surface"]], 4.6, +1)
    light["ui"] = walk_until(brand, light["bg"], 3.0, -1)
    dark["ui"] = walk_until(brand, dark["bg"], 3.0, +1)
    for st, hue in (("ok", 140), ("warn", 35), ("bad", 4), ("info", 200)):
        light[st] = walk_until(hsl2hex(hue, .65, .45), [light["bg"], light["surface"]], 4.6, -1)
        dark[st] = walk_until(hsl2hex(hue, .65, .55), [dark["bg"], dark["surface"]], 4.6, +1)
    pairs = []
    for theme, t in (("light", light), ("dark", dark)):
        for k in ("ink", "brand", "ok", "warn", "bad", "info"):
            for g in ("bg", "surface"):
                pairs.append((theme, k, g, 4.6, round(contrast(t[k], t[g]), 2)))
        pairs.append((theme, "ui", "bg", 3.0, round(contrast(t["ui"], t["bg"]), 2)))
    space = [4, 8, 12, 16, 24, 32, 48, 64]
    type_scale = [round(16 * 1.25 ** i, 2) for i in range(-1, 5)]
    var = lambda t: "".join("  --%s-%s: %s;\n" % (name, k, v) for k, v in t.items())
    css = (":root {\n%s  --t-fast: 120ms; --t: 180ms; --ease: cubic-bezier(.2,.8,.2,1);\n}\n" % var(light) +
           "@media (prefers-color-scheme: dark) {\n :root:not([data-theme=light]) {\n%s }\n}\n" % var(dark) +
           "[data-theme=dark] {\n%s}\n" % var(dark) +
           "@media (prefers-reduced-motion: reduce) {\n :root { --t-fast: 0ms; --t: 0ms; }\n}\n")
    return {"light": light, "dark": dark, "contrast": pairs, "space": space, "type": type_scale, "css": css}


def render_identity(t, w=240, h=135, accent="saffron"):
    im = Image.new("RGB", (w, h), t["bg"])
    d = ImageDraw.Draw(im)
    d.rectangle((16, 16, w - 16, h - 16), fill=t.get("surface", t["bg"]))
    d.rectangle((28, 30, 150, 44), fill=t["ink"])
    d.rectangle((28, 56, 90, 62), fill=t.get(accent, t.get("brand")))
    return np.asarray(im).astype(float)


BRAND_HEX = {"#0b1030": "#1d1814", "#19c3d9": "#f2732d", "#f4f6fb": "#fbf8f3"}


BRAND_RGBA = {(35, 64, 196): (217, 83, 14)}


def brand_css(css):
    css = re.sub(r"(?i)(\bcolor\s*:\s*)#2340c4", r"\1#a53e07", css)
    css = re.sub(r"(?i)(\bbackground(?:-color)?\s*:\s*)#2340c4", r"\1#1d1814", css)
    css = re.sub(r"(?i)#2340c4", "#d9530e", css)
    css = re.sub(r"(?i)#([0-9a-f]{6})(?=[0-9a-f]{2}\b|\b)", lambda m: BRAND_HEX.get("#" + m.group(1).lower(), m.group(0)), css)
    css = re.sub(r"rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,", lambda m: "rgba(%d,%d,%d," %
                 BRAND_RGBA.get(tuple(int(x) for x in m.groups()), tuple(int(x) for x in m.groups())), css)
    return css


def recolor_ice(img):
    hsv = rgb2hsv(img)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    w = smoothstep(18, 30, h) * (1 - smoothstep(62, 74, h)) * smoothstep(.08, .22, s)
    target = 190 + (h - 45) * .35
    h2 = h + w * (target - h)
    blue = (h >= 196) & (h <= 248)
    h2 = np.where(blue, h + .5 * (228 - h), h2)
    out = np.stack([h2, s * (1 - .1 * w), v * (1 - .06 * w)], -1)
    return hsv2rgb(out)


def resolve_cascade(layers):
    final = {}
    for _, vars_ in layers:
        final.update(vars_)
    return final


R_KEYS = ("background", "accent", "font", "finish", "overlay", "animation", "transition")


def theme_r(spec):
    missing = [k for k in R_KEYS if not spec.get(k)]
    if missing:
        raise ValueError("missing: %s" % ",".join(missing))
    for k in ("background", "accent"):
        if not re.match(r"^#[0-9a-f]{6}$", spec[k]):
            raise ValueError("bad hex for %s" % k)
    return dict({"small": "#333333", "end_card": "fade to black"}, **spec)


def style_lock(theme):
    bg, hero, small = theme
    return "STYLE LOCK: background %s, hero colour %s, small text %s; same font, finish and transition in every clip." % \
        (bg, hero, small)


def editorial_frame(p, accent_share=.2, w=200, h=120):
    im = Image.new("RGB", (w, h), p["bg"])
    d = ImageDraw.Draw(im)
    for x in range(0, w, 20):
        d.line((x, 0, x, h), fill=p["grid"])
    d.rectangle((10, 10, 90, 60), fill=p["shape"])
    d.rectangle((10, 70, 120, 78), fill=p["text"])
    d.line((10, 90, 190, 90), fill=p["line"], width=2)
    aw = int(round(accent_share * w * h / 50))
    d.rectangle((w - 10 - aw, 100 - 50, w - 10, 99), fill=p["accent"])
    return np.asarray(im).astype(float)


def pick_row(row):
    bg, fg = max(((a, b) for a in row for b in row if a != b and rel_lum(hx(a)) >= rel_lum(hx(b)) or
                  (a != b and rel_lum(hx(a)) < .05)), key=lambda p: contrast(*p))
    accent = max((c for c in row if c not in (bg, fg)), key=lambda c: float(rgb2hsv(np.array(hx(c), float))[1]))
    return {"bg": bg, "fg": fg, "accent": accent}


def derive(primary):
    h, s, l = hex2hsl(primary)
    return {"primary": primary, "light": hsl2hex(h, s, min(1, l + .15)), "dark": hsl2hex(h, s, max(0, l - .08)),
            "glow": "rgba(%d,%d,%d,.12)" % hx(primary)}


DEUTAN = np.array([[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]])


def simulate_deutan(hexc):
    return unlin(np.clip(DEUTAN @ lin(hx(hexc)), 0, 1))


def min_de(cols, sim=True):
    labs = [lab(simulate_deutan(c) if sim else np.array(hx(c), float)) for c in cols]
    return min(float(np.linalg.norm(labs[i] - labs[j])) for i in range(len(cols)) for j in range(i + 1, len(cols)))


def ramp_map(v, stops, cols, smooth=True, cap=None):
    v = np.asarray(v, float)
    if cap is not None:
        v = np.minimum(v, cap)
    c = np.array([hx(x) for x in cols], float)
    out = np.zeros(v.shape + (3,))
    out[...] = c[0]
    for i in range(len(stops) - 1):
        t = np.clip((v - stops[i]) / (stops[i + 1] - stops[i]), 0, 1)
        if smooth:
            t = t * t * (3 - 2 * t)
        m = (v >= stops[i])
        out = np.where(m[..., None], c[i] * (1 - t[..., None]) + c[i + 1] * t[..., None], out)
    return out


MAGMA = [(0, (0, 0, 4)), (.2, (40, 11, 84)), (.4, (120, 28, 109)), (.6, (192, 58, 118)), (.75, (236, 105, 89)),
         (.88, (251, 165, 74)), (1, (252, 253, 191))]


def magma(v):
    s = [p for p, _ in MAGMA]
    return ramp_map(v, s, [tohex(c) for _, c in MAGMA], smooth=False)


def alpine(height, slope):
    if height < -5:
        return "#2f4a3a"
    if height < 5:
        return "#b9a77a"
    if height >= 520:
        return "#f4f7fb"
    if 120 <= height <= 420 and slope >= .28:
        return "#5d5a58" if slope < .6 else "#7a6f66"
    return "#4e6e34" if height <= 25 else "#6b8a3c"


SCHEMES = {"complementary": (0, 180), "analogous": (-30, 0, 30), "triadic": (0, 120, 240), "split": (0, 150, 210),
           "tetradic": (0, 60, 180, 240)}


def harmony(scheme, base, sat=.6, light=.5):
    hues = [(base + o) % 360 for o in SCHEMES[scheme]]
    return hues, ["hsl(%d %d%% %d%%)" % (h, sat * 100, light * 100) for h in hues]


def oklch(hexc):
    l = lin(hx(hexc))
    m1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566],
                   [0.0883024619, 0.2817188376, 0.6299787005]])
    m2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099],
                   [0.0259040371, 0.7827717662, -0.8086757660]])
    L, a, b = m2 @ np.cbrt(m1 @ l)
    return float(L), float(math.hypot(a, b)), float(math.degrees(math.atan2(b, a)) % 360)


def detect_harmony(hexes, tol=15):
    hues = sorted(oklch(h)[2] for h in hexes if oklch(h)[1] >= .04)
    if not hues:
        return "neutral"
    if max(hue_dist(a, b) for a in hues for b in hues) <= tol:
        return "mono"
    for name in ("complementary", "triadic", "split", "tetradic", "analogous"):
        offs = SCHEMES[name]
        for base in hues:
            want = [(base + o) % 360 for o in offs]
            if len(hues) == len(want) and all(min(hue_dist(w, h) for h in hues) <= tol for w in want):
                return name
    return "free"


def flatten(fg, bg, alpha):
    return tuple(np.array(fg, float) * alpha + np.array(bg, float) * (1 - alpha))


def neutral_ramp(brand_hue, sat=.08, n=9):
    return [hsl2hex(brand_hue, sat, l) for l in np.linspace(.06, .96, n)]


def style_lock_intake(hexes, mood):
    if not 4 <= len(hexes) <= 6:
        raise ValueError("need 4-6 named hex")
    bg = max(hexes, key=lambda kv: rel_lum(hx(kv[1])))
    if bg[0] != "bg":
        raise ValueError("bg must be the lightest")
    if sum(1 for k, _ in hexes if k == "accent") != 1:
        raise ValueError("exactly one accent")
    return "STYLE LOCK: palette %s; soft window light; 35 mm lens; low-contrast grade; fine grain; 1970s; mood: %s." % (
        ", ".join("%s %s" % kv for kv in hexes), ", ".join(mood))


def tm_aces(x, exposure=1.0):
    x = np.asarray(x, float) * exposure / .6
    a_in = np.array([[0.59719, 0.35458, 0.04823], [0.07600, 0.90834, 0.01566], [0.02840, 0.13383, 0.83777]])
    a_out = np.array([[1.60475, -0.53108, -0.07367], [-0.10208, 1.10813, -0.00605], [-0.00327, -0.07276, 1.07602]])
    v = x @ a_in.T
    v = (v * (v + 0.0245786) - 0.000090537) / (v * (0.983729 * v + 0.4329510) + 0.238081)
    return np.clip(v @ a_out.T, 0, 1)


def tm_neutral(c, exposure=1.0):
    c = np.asarray(c, float) * exposure
    start, desat = .8 - .04, .15
    x = c.min(-1, keepdims=True)
    off = np.where(x < .08, x - 6.25 * x * x, .04)
    c = c - off
    peak = c.max(-1, keepdims=True)
    d = 1 - start
    newp = 1 - d * d / (peak + d - start)
    scaled = c * np.where(peak > 0, newp / np.maximum(peak, 1e-9), 1)
    g = 1 - 1 / (desat * (peak - newp) + 1)
    comp = scaled * (1 - g) + newp * g
    return np.clip(np.where(peak < start, c, comp), 0, 1)


def tm_agx(c, exposure=1.0):
    c = np.asarray(c, float) * exposure
    m = np.array([[0.842479062253094, 0.0784335999999992, 0.0792237451477643],
                  [0.0423282422610123, 0.878468636469772, 0.0791661274605434],
                  [0.0423756549057051, 0.0784336, 0.879142973793104]])
    inv = np.array([[1.19687900512017, -0.0980208811401368, -0.0990297440797205],
                    [-0.0528968517574562, 1.15190312990417, -0.0989611768448433],
                    [-0.0529716355144438, -0.0980434501171241, 1.15107367264116]])
    lo, hi = -12.47393, 4.026069
    v = c @ m.T
    v = np.clip(np.log2(np.maximum(v, 1e-10)), lo, hi)
    v = (v - lo) / (hi - lo)
    x2 = v * v
    x4 = x2 * x2
    v = 15.5 * x4 * x2 - 40.14 * x4 * v + 31.96 * x4 - 6.868 * x2 * v + .4298 * x2 + .1191 * v - .00232
    v = v @ inv.T
    return np.clip(np.maximum(v, 0) ** 2.2, 0, 1)


def pick_tone(kind):
    return {"product": "neutral", "neon": "agx", "fire": "agx", "lamp": "agx"}.get(kind, "aces")


def look_pass(img, gamut=None, night=0.0, split=0.0, warm="#ffc98a", cool="#5a7fb8"):
    v = np.asarray(img, float) / 255.0
    if gamut:
        c, wdt, st = gamut
        hsv = rgb2hsv(v * 255)
        dist = np.vectorize(lambda h: hue_dist(h, c))(hsv[..., 0])
        out_w = smoothstep(wdt / 2, wdt / 2 + 25, dist)
        y = (0.2126 * v[..., 0] + 0.7152 * v[..., 1] + 0.0722 * v[..., 2])[..., None]
        v = v + (y - v) * (out_w * st)[..., None]
    if night:
        rod = (v @ np.array([.05, .55, .40]))[..., None]
        y = (0.2126 * v[..., 0] + 0.7152 * v[..., 1] + 0.0722 * v[..., 2])[..., None]
        w = (1 - smoothstep(.02, .35, y)) * night
        v = v * (1 - w) + rod * np.array([.72, .86, 1.12]) * .75 * w
    if split:
        y = (0.2126 * v[..., 0] + 0.7152 * v[..., 1] + 0.0722 * v[..., 2])[..., None]
        t = smoothstep(.1, .7, y)
        tint = (np.array(hx(cool)) * (1 - t) + np.array(hx(warm)) * t) / 255.0
        v = v * (1 - .35 * split) + v * tint / np.maximum(tint.mean(-1, keepdims=True), 1e-6) * .35 * split
    return np.clip(v, 0, 1) * 255


def fog_exp2(col, fog, d, density, scatter):
    f = 1 - np.exp(-(density * np.array(scatter) * d) ** 2)
    return np.array(col, float) * (1 - f) + np.array(fog, float) * f


def shader_finish(img, warm=.5, lift=.02, vig=.42, ca=1.2, grain=.028, seed=0):
    v = np.asarray(img, float) / 255.0
    h, w = v.shape[:2]
    y = (0.2126 * v[..., 0] + 0.7152 * v[..., 1] + 0.0722 * v[..., 2])[..., None]
    tone = np.array([.92, .98, 1.08]) * (1 - y) + np.array([1.08, 1.0, .92]) * y
    v = v * tone
    v = v * (1 - warm + warm * np.array([1.05, .98, .9]))
    v = lift + v * (1 - lift)
    yy, xx = np.mgrid[0:h, 0:w]
    dx, dy = (xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2)
    r = np.hypot(dx, dy) / math.sqrt(2)
    off = ca * w / 1920.0 * r
    from scipy.ndimage import map_coordinates
    rr = map_coordinates(v[..., 0], [yy - dy * off, xx - dx * off], order=1, mode="nearest")
    bb = map_coordinates(v[..., 2], [yy + dy * off, xx + dx * off], order=1, mode="nearest")
    v = np.stack([rr, v[..., 1], bb], -1)
    v = v * (1 - vig * smoothstep(.35, .95, r))[..., None]
    rng = np.random.default_rng(seed)
    v = v + (rng.random((h, w, 1)) - .5) * grain
    return np.clip(v, 0, 1) * 255


def kelvin_rgb(k):
    t = k / 100.0
    r = 255 if t <= 66 else 329.698727446 * (t - 60) ** -0.1332047592
    g = 99.4708025861 * math.log(t) - 161.1195681661 if t <= 66 else 288.1221695283 * (t - 60) ** -0.0755148492
    b = 255 if t >= 66 else (0 if t <= 19 else 138.5177312231 * math.log(t - 10) - 305.0447927307)
    return tuple(int(round(min(255, max(0, v)))) for v in (r, g, b))


LIGHT_SOURCES = {"sodium": "#ffa040", "mercury": "#bff0dc", "moon": tohex(kelvin_rgb(4100)), "flame": tohex(kelvin_rgb(1900))}


def filmic(x, exposure=1.0, contrast_=1.0, saturation=1.0, lift=0.0):
    v = np.asarray(x, float) * exposure
    v = v * (2.51 * v + .03) / (v * (2.43 * v + .59) + .14)
    v = (v - .5) * contrast_ + .5
    y = (0.2126 * v[..., 0] + 0.7152 * v[..., 1] + 0.0722 * v[..., 2])[..., None] if v.ndim and v.shape[-1] == 3 else v
    v = y + (v - y) * saturation
    return np.clip(lift + v * (1 - lift), 0, 1)


def painter_grade(img, shadows, highlights, amount, contrast_=1.0):
    v = np.asarray(img, float) / 255.0
    y = (0.2126 * v[..., 0] + 0.7152 * v[..., 1] + 0.0722 * v[..., 2])[..., None]
    tint = np.array(hx(shadows)) / 255.0 * (1 - y) + np.array(hx(highlights)) / 255.0 * y
    v = v * (1 - amount) + tint * amount
    return np.clip((v - .5) * contrast_ + .5, 0, 1) * 255


def grain(img, amount, seed):
    rng = np.random.default_rng(seed)
    return np.clip(img + (rng.random(img.shape[:2] + (1,)) - .5) * 255 * amount * 2, 0, 255)


def rolloff(x, k=0.82):
    y = np.array(x, dtype=float, copy=True)
    m = x > k
    if k < 1:
        y[m] = k + (1 - k) * np.tanh((x[m] - k) / (1 - k))
    return (np.clip(y, 0, 1) * 255 + 0.5).astype(np.uint8)


def painter_vignette(img, strength=.5):
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.hypot(xx - w / 2, yy - h / 2) / math.hypot(w / 2, h / 2)
    return img * (1 - strength * smoothstep(.35, 1.0, d))[..., None]


def hx8(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)), (int(h[6:8], 16) / 255.0 if len(h) == 8 else 1.0)


def paint_gradient(t, stops):
    t = np.clip(t, 0, 1)
    cols = np.array([hx8(c)[0] for _, c in stops], float)
    alph = np.array([hx8(c)[1] for _, c in stops], float)
    pos = np.array([p for p, _ in stops])
    rgb = np.stack([np.interp(t, pos, cols[:, i]) for i in range(3)], -1)
    return rgb, np.interp(t, pos, alph)


def blend(base, col, a, mode):
    b, c = base / 255.0, col / 255.0
    if mode == "add":
        o = b + c * a[..., None]
    elif mode == "screen":
        o = b + c * a[..., None] * (1 - np.minimum(b, 1))
    elif mode == "multiply":
        o = b * (1 - a[..., None]) + b * c * a[..., None]
    else:
        o = b * (1 - a[..., None]) + c * a[..., None]
    return o * 255


def smooth_ease(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


def lerp_ops(a, b, k):
    return [(n, va + (vb - va) * k) for (n, va), (_, vb) in zip(a, b)]


def equal_lum_hues(hues, sat=.7, target=.3):
    out = []
    for h in hues:
        lo, hi = 0.0, 1.0
        for _ in range(40):
            m = (lo + hi) / 2
            lo, hi = (m, hi) if rel_lum(hx(hsl2hex(h, sat, m))) < target else (lo, m)
        out.append(hsl2hex(h, sat, (lo + hi) / 2))
    return out


def overshoot(t, s=1.70158):
    t = np.clip(t, 0, 1) - 1
    return t * t * ((s + 1) * t + s) + 1


def blob_frame(t, w=160, h=90, period=10.0):
    img = np.zeros((h, w, 3)) + hx("#0c0b18")
    yy, xx = np.mgrid[0:h, 0:w]
    blobs = [("#7a3fd0", .3, .8, .7, 0), ("#ff7a3d", .7, .85, .6, 1.7), ("#3a7bd0", .5, .3, .55, 3.1)]
    for col, cx, cy, size, ph in blobs:
        x = cx * w + 12 * math.sin(2 * math.pi * t / period + ph)
        y = cy * h + 6 * math.cos(2 * math.pi * t / period + ph)
        r = size * w / 2
        a = np.clip(1 - np.hypot(xx - x, yy - y) / r, 0, 1) ** 2 * .7
        img = img * (1 - a[..., None]) + np.array(hx(col)) * a[..., None]
    img = blur(img, 6)
    dots = (xx % 24 == 0) & (yy % 24 == 0)
    img[dots] = img[dots] * .92 + 255 * .08
    return img


def zone_stats(img, edges=(0, 15, 35, 55, 75, 100)):
    L = lab(img)
    C = np.hypot(L[..., 1], L[..., 2])
    out = []
    for a, b in zip(edges[:-1], edges[1:]):
        m = (L[..., 0] >= a) & (L[..., 0] < b)
        if m.sum():
            c = C[m]
            med = float(np.median(c))
            out.append((a, b, med, float(np.median(np.abs(c - med))), int(m.sum())))
        else:
            out.append((a, b, None, None, 0))
    return out, float(L[..., 0].std()), float(np.mean(L[..., 0] < 10))
