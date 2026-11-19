"""Helpers of runners/fam_typography_latin.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from pathlib import Path
from .core import fx
import json
import math
import os
import re
import subprocess


FONTS = Path(__import__("os").environ.get("KOSIF_FONTS") or Path.home() / "kosif-tool" / ".claude" / "skills" / "kosif-superpowers" / "proofs" / "_shared" / "fonts")  # read-only asset in the old repo


CAIRO = FONTS / "Cairo[slnt,wght].ttf"


POPPINS = FONTS / "Poppins-Bold.ttf"


K = 0.5


INTERD = Path("/usr/share/fonts/opentype/inter")


LIB = Path("/usr/share/fonts/truetype/liberation")


DJV = Path("/usr/share/fonts/truetype/dejavu")


def pick(*cands):
    for c in cands:
        if Path(c).exists():
            return Path(c)
    raise FileNotFoundError(cands[0])


INTER = pick(INTERD / "Inter-Regular.otf", FONTS / "Poppins-Regular.ttf")


INTER_B = pick(INTERD / "Inter-Bold.otf", POPPINS)


INTER_K = pick(INTERD / "Inter-Black.otf", POPPINS)


INTER_L = pick(INTERD / "Inter-Light.otf", FONTS / "Poppins-Regular.ttf")


SERIF = pick(LIB / "LiberationSerif-Regular.ttf", DJV / "DejaVuSerif.ttf")


SERIF_I = pick(LIB / "LiberationSerif-Italic.ttf", LIB / "LiberationSerif-Regular.ttf")


SERIF_B = pick(LIB / "LiberationSerif-Bold.ttf", DJV / "DejaVuSerif-Bold.ttf")


MONO = pick(DJV / "DejaVuSansMono.ttf", LIB / "LiberationMono-Regular.ttf")


MONO_B = pick(DJV / "DejaVuSansMono-Bold.ttf", MONO)


AR_RE = re.compile("[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")


def np_():
    import numpy as np
    return np


def font(path=CAIRO, size=48, wght=None, basic=False):
    from PIL import ImageFont
    eng = ImageFont.Layout.BASIC if basic else ImageFont.Layout.RAQM
    f = ImageFont.truetype(str(path), int(round(size)), layout_engine=eng)
    if wght is not None:
        try:
            axes = f.get_variation_axes()
        except OSError:
            return f
        vals = []
        for a in axes:
            nm = a["name"].decode() if isinstance(a["name"], bytes) else str(a["name"])
            vals.append(max(a["minimum"], min(a["maximum"], wght)) if nm.lower().startswith("weight") else a["default"])
        f.set_variation_by_axes(vals)
    return f


def _dir(text):
    return "rtl" if AR_RE.search(text) else "ltr"


def _kw(f, text, direction=None, features=None):
    from PIL import ImageFont
    if f.layout_engine == ImageFont.Layout.BASIC:
        return {}
    kw = {"direction": direction or _dir(text)}
    if features is not None:
        kw["features"] = features
    if kw["direction"] == "rtl":
        kw["language"] = "ar"
    return kw


def tlen(text, f, direction=None, features=None):
    return f.getlength(text, **_kw(f, text, direction, features))


def tile(text, f, fill=(255, 255, 255, 255), direction=None, features=None, stroke=0, stroke_fill=None, pad=None):
    """Text rendered on a transparent RGBA tile with padding; returns (tile, (ox, oy)) where o is the text origin."""
    from PIL import Image, ImageDraw
    kw = _kw(f, text, direction, features)
    d0 = ImageDraw.Draw(Image.new("L", (1, 1)))
    bb = d0.textbbox((0, 0), text, font=f, stroke_width=stroke, **kw)
    pad = int(f.size * 0.35) if pad is None else pad
    w, h = bb[2] - bb[0] + 2 * pad, bb[3] - bb[1] + 2 * pad
    im = Image.new("RGBA", (max(1, w), max(1, h)), tuple(fill[:3]) + (0,))  # premultiplied-safe for blur
    o = (pad - bb[0], pad - bb[1])
    ImageDraw.Draw(im).text(o, text, font=f, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill, **kw)
    return im, o


def place(canvas, t, cx, cy, scale=1.0, alpha=1.0, blur=0.0, rot=0.0, clip=None, sx=None, sy=None):
    """Composite tile t centred at (cx, cy) with transform/opacity/blur; clip=(x0,y0,x1,y1) masks to a box."""
    from PIL import Image, ImageFilter
    if alpha <= 0.002:
        return
    sx = scale if sx is None else sx
    sy = scale if sy is None else sy
    im = t
    if abs(sx - 1) > 1e-4 or abs(sy - 1) > 1e-4:
        im = im.resize((max(1, int(round(im.width * sx))), max(1, int(round(im.height * sy)))), Image.BICUBIC)
    if abs(rot) > 1e-3:
        im = im.rotate(rot, resample=Image.BICUBIC, expand=True)
    if blur > 0.05:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    if alpha < 0.999:
        a = im.getchannel("A").point(lambda v: int(v * alpha))
        im = im.copy()
        im.putalpha(a)
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    layer.paste(im, (int(round(cx - im.width / 2)), int(round(cy - im.height / 2))))
    if clip is not None:
        m = Image.new("L", canvas.size, 0)
        x0, y0, x1, y1 = [int(round(v)) for v in clip]
        m.paste(255, (x0, y0, x1, y1))
        a = Image.composite(layer.getchannel("A"), Image.new("L", canvas.size, 0), m)
        layer.putalpha(a)
    canvas.alpha_composite(layer)


def blank(size, bg=(0, 0, 0)):
    from PIL import Image
    return Image.new("RGBA", size, tuple(bg) + (255,))


def encode(path, frames, size, fps=30):
    """Pipe RGBA/RGB PIL frames into an H.264 file."""
    w, h = size
    p = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", "%dx%d" % (w, h), "-r", str(fps), "-i", "-", "-c:v", "libx264", "-crf", "10",
                          "-preset", "ultrafast", "-pix_fmt", "yuv444p", str(path)], stdin=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    for fr in frames:
        p.stdin.write(fr.convert("RGB").tobytes())
    p.stdin.close()
    err = p.stderr.read()
    if p.wait():
        raise RuntimeError("encode failed: %s" % err[-300:])
    return Path(path)


def video(wd, name, draw, dur, size=(270, 480), fps=30, bg=(0, 0, 0)):
    """Render draw(t, canvas) for every frame, encode, decode back and return (path, frames as float arrays)."""
    n = int(round(dur * fps))

    def gen():
        for i in range(n):
            c = blank(size, bg)
            draw(i / fps, c)
            yield c
    p = encode(Path(wd) / name, gen(), size, fps)
    return p, fx.frames(p, size)


def arr(im):
    np = np_()
    return np.asarray(im.convert("RGB"), dtype=float)


def lum(a):
    return a[..., :3].mean(axis=-1)


def mask_of(a, thr=110):
    return lum(a) > thr


def bbox(m):
    np = np_()
    ys, xs = np.nonzero(m)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def centroid(m):
    np = np_()
    ys, xs = np.nonzero(m)
    if len(xs) == 0:
        return None
    return float(xs.mean()), float(ys.mean())


def wcentroid(a):
    np = np_()
    g = lum(a)
    tot = g.sum()
    if tot <= 0:
        return None
    ys, xs = np.mgrid[0:g.shape[0], 0:g.shape[1]]
    return float((xs * g).sum() / tot), float((ys * g).sum() / tot)


def comps(m):
    from scipy import ndimage
    return int(ndimage.label(m)[1])


def colour_mask(a, rgb, tol=40):
    np = np_()
    return np.abs(a[..., :3] - np.array(rgb, dtype=float)).max(axis=-1) < tol


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def frame_at(frames, t, fps=30):
    return frames[min(len(frames) - 1, max(0, int(round(t * fps))))]


def clamp(v, a=0.0, b=1.0):
    return max(a, min(b, v))


def expo_out(p):
    p = clamp(p)
    return 1.0 if p >= 1 else 1 - 2 ** (-10 * p)


def pow_out(p, k):
    return 1 - (1 - clamp(p)) ** k


def back_out(p, s=1.70158):
    p = clamp(p) - 1
    return 1 + (s + 1) * p ** 3 + s * p ** 2


def cubic_out(p):
    return pow_out(p, 3)


def shaped_mask(text, f, fill=255):
    """Binary ink mask of a raqm-shaped string."""
    t, _ = tile(text, f, fill=(255, 255, 255, 255))
    return np_().asarray(t.getchannel("A")) > 128


def basic_mask(text, path, size):
    """Same string with the BASIC layout (no shaping, no bidi): isolated forms in logical order = the raw input."""
    t, _ = tile(text, font(path, size, basic=True))
    return np_().asarray(t.getchannel("A")) > 128


def save_png(im, path):
    im.convert("RGB").save(path)
    return Path(path)


def write_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return Path(path)


def chrome_bin():
    import glob
    for pat in ("/opt/pw-browsers/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell",
                os.path.expanduser("~/.cache/hyperframes/chrome/chrome-headless-shell/*/*/chrome-headless-shell")):
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    return None


def chrome_shot(wd, html_text, name, w, h, budget=None):
    """Render HTML in headless Chrome (headless shell, private profile in wd) to a PNG (fonts via file://)."""
    src = Path(wd) / (name + ".html")
    src.write_text(html_text, encoding="utf-8")
    out = Path(wd) / (name + ".png")
    exe = chrome_bin()
    if not exe:
        raise RuntimeError("no headless chrome shell found")
    cmd = [exe, "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
           "--user-data-dir=%s" % (Path(wd) / ("chrome-" + name)), "--force-device-scale-factor=1",
           "--window-size=%d,%d" % (w, h), "--screenshot=%s" % out]
    if budget:
        cmd.append("--virtual-time-budget=%d" % budget)
    cmd.append(src.as_uri())
    subprocess.run(cmd, capture_output=True, timeout=40, stdin=subprocess.DEVNULL)
    if not out.exists():
        raise RuntimeError("chrome produced no screenshot")
    return src, out


def iou(a, b):
    np = np_()
    h, w = min(a.shape[0], b.shape[0]), min(a.shape[1], b.shape[1])
    a, b = a[:h, :w], b[:h, :w]
    u = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / u) if u else 0.0


def crop_ink(m):
    b = bbox(m)
    return m[b[1]:b[3], b[0]:b[2]] if b else m


def word_row(words, f, W, cy, gap=None, rtl=True, fills=None):
    """Lay whole words on one centred line, first word on the right for RTL. Returns list of dicts."""
    gap = f.size * 0.32 if gap is None else gap
    tiles = []
    for i, w in enumerate(words):
        fill = fills[i] if fills else (255, 255, 255, 255)
        t, _ = tile(w, f, fill=fill)
        tiles.append((w, t, tlen(w, f)))
    total = sum(x[2] for x in tiles) + gap * (len(tiles) - 1)
    out = []
    x = (W + total) / 2 if rtl else (W - total) / 2
    for w, t, ln in tiles:
        cx = x - ln / 2 if rtl else x + ln / 2
        out.append({"word": w, "tile": t, "cx": cx, "cy": cy, "len": ln,
                    "box": (cx - ln / 2 - 2, cy - t.height / 2, cx + ln / 2 + 2, cy + t.height / 2)})
        x = x - ln - gap if rtl else x + ln + gap
    return out


def crop(fr, box):
    x0, y0, x1, y1 = [int(round(v)) for v in box]
    return fr[max(0, y0):max(0, y1), max(0, x0):max(0, x1)]


def box_ink(fr, box, thr=110):
    return float((lum(crop(fr, box)) > thr).sum())


def ink_box_abs(r):
    """Absolute ink box of a word placed by word_row (tile is centred on cx, cy)."""
    a = np_().asarray(r["tile"].getchannel("A")) > 128
    b = bbox(a)
    x0 = r["cx"] - r["tile"].width / 2
    y0 = r["cy"] - r["tile"].height / 2
    return (x0 + b[0], y0 + b[1], x0 + b[2], y0 + b[3])


def grow(b, dx, dy):
    return (b[0] - dx, b[1] - dy, b[2] + dx, b[3] + dy)


def kinetic(wd, name, words, f, state, dur, size=(270, 480), cy=None, fills=None, slot_pad=None, fps=30, extra=None):
    """Whole-word kinetic type: state(i, t) -> dict(dx, dy, alpha, blur, scale, rot, clip) or None (hidden)."""
    W, H = size
    row = word_row(words, f, W, H / 2 if cy is None else cy, fills=fills)
    sp = f.size * 0.3 if slot_pad is None else slot_pad
    for r in row:
        r["ink"] = ink_box_abs(r)
        r["slot"] = grow(r["ink"], 3, sp)

    def draw(t, c):
        if extra:
            extra(t, c, row)
        for i, r in enumerate(row):
            s = state(i, t)
            if s is None:
                continue
            place(c, r["tile"], r["cx"] + s.get("dx", 0), r["cy"] + s.get("dy", 0), scale=s.get("scale", 1),
                  alpha=s.get("alpha", 1), blur=s.get("blur", 0), rot=s.get("rot", 0),
                  clip=r["slot"] if s.get("clip") else None)
    p, frames = video(wd, name, draw, dur, size, fps)
    return p, frames, row


def outside_ink(fr, boxes, thr=110):
    np = np_()
    m = lum(fr) > thr
    keep = np.zeros_like(m)
    for b in boxes:
        x0, y0, x1, y1 = [int(round(v)) for v in b]
        keep[max(0, y0):y1, max(0, x0):x1] = True
    return int((m & ~keep).sum())


def lumsum(fr, box):
    x0, y0, x1, y1 = [int(round(v)) for v in box]
    return float(lum(fr[max(0, y0):y1, max(0, x0):x1]).sum())


def first_time(series, frac, fps=30):
    top = max(series) or 1
    for i, v in enumerate(series):
        if v >= frac * top:
            return i / fps
    return None


def ink_box_abs(r):
    """Absolute ink box of a word placed by word_row (tile is centred on cx, cy)."""
    a = np_().asarray(r["tile"].getchannel("A")) > 128
    b = bbox(a)
    x0 = r["cx"] - r["tile"].width / 2
    y0 = r["cy"] - r["tile"].height / 2
    return (x0 + b[0], y0 + b[1], x0 + b[2], y0 + b[3])


def grow(b, dx, dy):
    return (b[0] - dx, b[1] - dy, b[2] + dx, b[3] + dy)


def kinetic(wd, name, words, f, state, dur, size=(270, 480), cy=None, fills=None, slot_pad=None, fps=30, extra=None):
    """Whole-word kinetic type: state(i, t) -> dict(dx, dy, alpha, blur, scale, rot, clip) or None (hidden)."""
    W, H = size
    row = word_row(words, f, W, H / 2 if cy is None else cy, fills=fills)
    sp = f.size * 0.3 if slot_pad is None else slot_pad
    for r in row:
        r["ink"] = ink_box_abs(r)
        r["slot"] = grow(r["ink"], 3, sp)

    def draw(t, c):
        if extra:
            extra(t, c, row)
        for i, r in enumerate(row):
            s = state(i, t)
            if s is None:
                continue
            place(c, r["tile"], r["cx"] + s.get("dx", 0), r["cy"] + s.get("dy", 0), scale=s.get("scale", 1),
                  alpha=s.get("alpha", 1), blur=s.get("blur", 0), rot=s.get("rot", 0),
                  clip=r["slot"] if s.get("clip") else None)
    p, frames = video(wd, name, draw, dur, size, fps)
    return p, frames, row


def outside_ink(fr, boxes, thr=110):
    np = np_()
    m = lum(fr) > thr
    keep = np.zeros_like(m)
    for b in boxes:
        x0, y0, x1, y1 = [int(round(v)) for v in b]
        keep[max(0, y0):y1, max(0, x0):x1] = True
    return int((m & ~keep).sum())


def lumsum(fr, box):
    x0, y0, x1, y1 = [int(round(v)) for v in box]
    return float(lum(fr[max(0, y0):y1, max(0, x0):x1]).sum())


def first_time(series, frac, fps=30):
    top = max(series) or 1
    for i, v in enumerate(series):
        if v >= frac * top:
            return i / fps
    return None


def wrap_words(words, f, maxw, gap=None):
    lines, cur = [], []
    for w in words:
        test = " ".join(cur + [w])
        if cur and tlen(test, f) > maxw:
            lines.append(" ".join(cur))
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(" ".join(cur))
    return lines


def persp_coeffs(src, dst):
    """PIL PERSPECTIVE coefficients mapping output points dst -> input points src."""
    np = np_()
    A, B = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        B += [u, v]
    return np.linalg.solve(np.array(A, float), np.array(B, float)).tolist()


def turn_in(canvas, t_img, cx, by, theta_deg, z0, dy=0.0, persp=900.0, blur=0.0):
    """Place a tile rotated about its bottom edge by rotationX theta with z offset under CSS-style perspective."""
    from PIL import Image, ImageFilter
    w, h = t_img.size
    th = math.radians(theta_deg)

    def proj(x, y):
        yy, z = y * math.cos(th), z0 + y * math.sin(th)
        s = persp / (persp - z)
        return (cx + x * s, by + dy - yy * s)
    dst = [proj(-w / 2, h), proj(w / 2, h), proj(w / 2, 0), proj(-w / 2, 0)]
    src = [(0, 0), (w, 0), (w, h), (0, h)]
    im = t_img.filter(ImageFilter.GaussianBlur(blur)) if blur > 0.05 else t_img
    warped = im.transform(canvas.size, Image.PERSPECTIVE, persp_coeffs(src, dst), Image.BICUBIC)
    canvas.alpha_composite(warped)
    ys = [p[1] for p in dst]
    return max(ys) - min(ys)


def pca_angle(m):
    np = np_()
    ys, xs = np.nonzero(m)
    xs = xs - xs.mean()
    ys = ys - ys.mean()
    cov = np.cov(np.vstack([xs, ys]))
    w, v = np.linalg.eigh(cov)
    vx, vy = v[:, np.argmax(w)]
    a = math.degrees(math.atan2(-vy, vx))
    return (a + 90) % 180 - 90


def lower_third(c, at, t, title, sub, accent="#E7B65A", size=44, inset=72, bottom=160, k=K, side=None, detect=True):
    from PIL import ImageDraw
    W, H = c.size
    rtl = (side == "right") if side else (detect and bool(AR_RE.search(title)))
    acc = hexrgb(accent)
    ft, fs = font(CAIRO, int(size * k), 700), font(CAIRO, int(size * 0.55 * k), 600)
    y = H - bottom * k
    if t >= at:
        w = 120 * k * cubic_out((t - at) / 0.4)
        x = W - inset * k if rtl else inset * k
        ImageDraw.Draw(c).rectangle([x - w if rtl else x, y - 2 * k * 2, x if rtl else x + w, y], fill=acc)
    for txt, ff, dt, fill, dy in ((title, ft, 0.12, (255, 255, 255, 255), -size * k * 1.0), (sub, fs, 0.24, (255, 255, 255, 191), size * k * 0.7)):
        if t >= at + dt:
            e = cubic_out((t - at - dt) / 0.5)
            tl, _ = tile(txt, ff, fill=fill)
            half = tl.width / 2 - ff.size * 0.35
            cx = (W - inset * k - half) if rtl else (inset * k + half)
            place(c, tl, cx, y + dy + 16 * k * (1 - e), alpha=e)


def bezier(x1, y1, x2, y2):
    """CSS cubic-bezier(x1, y1, x2, y2) as an easing function of progress."""
    def f(p):
        p = clamp(p)
        lo, hi = 0.0, 1.0
        for _ in range(40):
            m = (lo + hi) / 2
            x = 3 * (1 - m) ** 2 * m * x1 + 3 * (1 - m) * m * m * x2 + m ** 3
            lo, hi = (m, hi) if x < p else (lo, m)
        m = (lo + hi) / 2
        return 3 * (1 - m) ** 2 * m * y1 + 3 * (1 - m) * m * m * y2 + m ** 3
    return f


E_OUT = bezier(.16, 1, .3, 1)


E_IN = bezier(.7, 0, .84, 0)


def tracked(text, f, spacing=0.0, fill=(255, 255, 255, 255), pad=None):
    """Text with CSS letter-spacing (px) added after every character, kerning kept via cumulative advances."""
    from PIL import Image, ImageDraw
    pad = int(f.size * 0.35) if pad is None else pad
    w = tlen(text, f, "ltr") + spacing * max(0, len(text) - 1)
    asc, desc = f.getmetrics()
    im = Image.new("RGBA", (int(w + 2 * pad), int(asc + desc + 2 * pad)), tuple(fill[:3]) + (0,))
    d = ImageDraw.Draw(im)
    for i, ch in enumerate(text):
        x = pad + tlen(text[:i], f, "ltr") + spacing * i if i else pad
        d.text((x, pad), ch, font=f, fill=fill, direction="ltr")
    return im


def ink_w(im):
    b = bbox(np_().asarray(im.getchannel("A")) > 128)
    return b[2] - b[0]


def contrast(c1, c2):
    def L(c):
        v = []
        for x in c:
            x = x / 255
            v.append(x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4)
        return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]
    a, b = sorted([L(c1), L(c2)], reverse=True)
    return (a + 0.05) / (b + 0.05)


def cap_h(f, ch="H"):
    m = shaped_mask(ch, f)
    b = bbox(m)
    return b[3] - b[1]


VIDEO_MIN = {1920: {"headline": 60, "body": 20, "label": 16}, 1080: {"headline": 84, "support": 44}}


def lint_sizes(spec):
    W = spec["width"]
    issues = []
    for role, px in spec["sizes"].items():
        mn = VIDEO_MIN.get(W, {}).get(role)
        if mn and px < mn:
            issues.append("%s %dpx < %dpx" % (role, px, mn))
    if spec.get("feed") and spec["sizes"].get("tertiary", 99) < 24:
        issues.append("tertiary < 24px")
    if spec.get("safe", (80, 100)) < (80, 100):
        issues.append("safe area")
    if contrast(spec["fg"], spec["bg"]) < 7:
        issues.append("contrast")
    return issues


def fit_font_size(text, path, max_width, base=78, minimum=42, step=2):
    s = base
    while s > minimum and tlen(text, font(path, s), "ltr") > max_width:
        s -= step
    return s, tlen(text, font(path, s), "ltr") <= max_width


def text_rung(s, role):
    words = len(s.split())
    if re.search(r"\d", s) and len(s) > 6:
        return 3 if role == "data" else 2
    if role == "label":
        return 1 if words <= 4 and len(s) <= 25 else 2
    if role == "title":
        return 1 if words <= 8 and len(s) <= 25 else 2
    return 2 if len(s) <= 120 else 3


def latin_row(words, f, W, cy, gap=None, fills=None):
    return word_row(words, f, W, cy, gap=gap, rtl=False, fills=fills)


def _static(tiles, xs, W, H, y=None):
    c = blank((W, H))
    for tl, x in zip(tiles, xs):
        place(c, tl, x, H / 2 if y is None else y)
    return c


MOVES = {"slide_bottom": {"y": 150, "ease": "power4.out", "dur": 0.6}, "slide_top": {"y": -150, "ease": "power4.out", "dur": 0.6},
         "slide_left": {"x": -200, "ease": "power4.out", "dur": 0.6}, "slide_right": {"x": 200, "ease": "power4.out", "dur": 0.6},
         "scale_grow": {"scale": 0.0, "ease": "power2.out", "dur": 0.6}, "scale_punch": {"scale": 0.6, "ease": "back.out(2.2)", "dur": 0.5},
         "fade_in": {"alpha": 0.0, "ease": "linear", "dur": 0.4}, "fade_blur": {"blur": 14, "alpha": 0.0, "ease": "power2.out", "dur": 0.5},
         "bounce_in": {"y": -120, "ease": "bounce.out", "dur": 0.8}, "slam": {"y": -300, "ease": "power4.out", "dur": 0.35}}


def ease_by(name):
    if name == "linear":
        return clamp
    if name.startswith("power"):
        k = int(name[5]) + 1
        return lambda p: pow_out(p, k)
    if name.startswith("back.out"):
        s = float(re.search(r"\(([\d.]+)\)", name).group(1)) if "(" in name else 1.70158
        return lambda p: back_out(p, s)
    if name == "bounce.out":
        def b(p):
            p = clamp(p)
            n, d = 7.5625, 2.75
            if p < 1 / d:
                return n * p * p
            if p < 2 / d:
                p -= 1.5 / d
                return n * p * p + .75
            if p < 2.5 / d:
                p -= 2.25 / d
                return n * p * p + .9375
            p -= 2.625 / d
            return n * p * p + .984375
        return b
    raise KeyError(name)


def move_state(name, p):
    m = MOVES[name]
    e = ease_by(m["ease"])(p)
    st = {"dx": m.get("x", 0) * (1 - e), "dy": m.get("y", 0) * (1 - e), "alpha": 1.0, "blur": m.get("blur", 0) * (1 - e), "scale": 1.0}
    if "scale" in m:
        st["scale"] = m["scale"] + (1 - m["scale"]) * e
    if "alpha" in m:
        st["alpha"] = e
    return st


def scramble_at(text, p, steps=40, seed=3):
    import hashlib
    lock = int(min(len(text), p * len(text) * 1.15))
    step = int(p * steps)
    out = []
    for i, ch in enumerate(text):
        if i < lock or ch == " ":
            out.append(ch)
        else:
            pool = "023456789" if ch.isdigit() else "ABCDEFGHJKLMNPQRSTUVWXYZ"
            h = int(hashlib.md5(("%d:%d:%d" % (seed, i, step)).encode()).hexdigest(), 16)
            out.append(pool[h % len(pool)])
    return "".join(out)


def _land(frames, i, target, f, cw, H=80):
    from PIL import ImageDraw
    x = 10 + i * cw
    ref = blank((cw, H))
    d = ImageDraw.Draw(ref)
    d.rectangle([1, 15, cw - 2, H - 15], fill=(28, 28, 32))
    d.line([1, H / 2, cw - 2, H / 2], fill=(0, 0, 0))
    d.text((cw / 2, H / 2), target[i], font=f, fill="white", anchor="mm")
    rm = mask_of(arr(ref), 150)
    for k, fr in enumerate(frames):
        if iou(mask_of(fr[:, x:x + cw], 150), rm) > 0.95:
            return k / 30
    return None


def fmt_counter(v, sep=",", prefix="", suffix="", decimals=0):
    s = ("{:,.%df}" % decimals).format(v)
    return prefix + s.replace(",", sep) + suffix


def beats_for(tokens, length):
    if len(tokens) > 30:
        raise ValueError("more than 30 words in one clip")
    n = min(5, max(3, math.ceil(len(tokens) / 6)))
    per = math.ceil(len(tokens) / n)
    beats = []
    for j in range(n):
        ws = tokens[j * per:(j + 1) * per]
        if not ws:
            continue
        hi = next((i for i, w in enumerate(ws) if 3 <= len(re.sub(r"\W", "", w)) <= 10), 0)
        beats.append({"lead": ws[:hi], "hero": ws[hi], "tail": ws[hi + 1:], "t0": j * length / n, "t1": (j + 1) * length / n})
    return beats


def hblur(im, px):
    """Directional (horizontal) motion blur of an RGBA tile by averaging shifted copies."""
    from PIL import Image
    np = np_()
    if px < 1:
        return im
    a = np.asarray(im, float)
    n = int(px)
    pad = np.pad(a, ((0, 0), (n, n), (0, 0)))
    acc = sum(pad[:, i:i + a.shape[1] + 2 * n - 2 * n] for i in range(2 * n + 1)) / (2 * n + 1)
    return Image.fromarray(np.clip(acc, 0, 255).astype("uint8"), "RGBA")


def click_track(path, bpm=120, beats=8, rate=22050, start=0.25):
    np = np_()
    n = int((start + beats * 60 / bpm + 0.5) * rate)
    s = np.zeros(n)
    times = [start + i * 60 / bpm for i in range(beats)]
    for k, t in enumerate(times):
        a = int(t * rate)
        L = int(0.03 * rate)
        amp = 0.9 if k % 4 == 0 else 0.4
        s[a:a + L] += amp * np.sin(2 * math.pi * 1000 * np.arange(L) / rate) * np.exp(-np.arange(L) / (0.006 * rate))
    fx.write_wav(path, s, rate)
    return times


def onsets(path, thr=0.25):
    np = np_()
    data, rate = fx.read_wav(path)
    x = np.abs(data[:, 0])
    hop = int(rate * 0.005)
    env = np.array([x[i:i + hop].max() for i in range(0, len(x), hop)])
    out, last = [], -1
    for i, v in enumerate(env):
        if v > thr * env.max() and (last < 0 or i - last > 20):
            out.append((i * hop / rate, float(v)))
            last = i
    return out


def ease_bounce(p):
    p = clamp(p)
    n, d = 7.5625, 2.75
    if p < 1 / d:
        return n * p * p
    if p < 2 / d:
        p -= 1.5 / d
        return n * p * p + .75
    if p < 2.5 / d:
        p -= 2.25 / d
        return n * p * p + .9375
    p -= 2.625 / d
    return n * p * p + .984375


def physics_world(bodies, floor, obstacles, steps, dt, g=1800.0, rest=0.35, jitter=None):
    """Axis-aligned rigid boxes under gravity, fixed timestep, resolved against the floor, static obstacles and each other."""
    import random
    rnd = random.Random(jitter) if jitter is not None else None
    st = [dict(b) for b in bodies]
    hist = []
    for k in range(steps):
        h = dt * (1 + (rnd.uniform(-0.4, 0.4) if rnd else 0))
        for b in st:
            b["vy"] += g * h
            b["y"] += b["vy"] * h
            if b["y"] + b["h"] > floor:
                b["y"] = floor - b["h"]
                b["vy"] = -b["vy"] * rest if abs(b["vy"]) > 60 else 0.0
            for ob in obstacles:
                if b["x"] < ob[2] and b["x"] + b["w"] > ob[0] and b["y"] + b["h"] > ob[1] and b["y"] < ob[1] + 10:
                    b["y"] = ob[1] - b["h"]
                    b["vy"] = -b["vy"] * rest if abs(b["vy"]) > 60 else 0.0
        for _ in range(3):
            for i, a in enumerate(st):
                for b in st[:i]:
                    if a["x"] < b["x"] + b["w"] and a["x"] + a["w"] > b["x"] and a["y"] < b["y"] + b["h"] and a["y"] + a["h"] > b["y"]:
                        top, low = (a, b) if a["y"] < b["y"] else (b, a)
                        top["y"] = low["y"] - top["h"]
                        top["vy"] = min(top["vy"], low["vy"])
        hist.append([(b["x"], b["y"]) for b in st])
    return hist


_RING_CACHE = {}


def ring_scene(t, W, H, rings, words, speed, zoom):
    from PIL import Image
    c = blank((W, H), hexrgb("#0d0e12"))
    pal = [hexrgb(x) for x in ("#ff5020", "#2f55ff", "#ffc81e")]
    for i, r0 in enumerate(rings):
        r = r0 * zoom(t)
        ang = speed * t * (1 if i % 2 == 0 else -1)
        f = font(INTER_K, int(10 + 3 * i))
        txt = (words[i % len(words)] + " • ")
        n = max(4, int(2 * math.pi * r / (tlen(txt, f, "ltr") + 1)))
        for j in range(n * len(txt)):
            ch = txt[j % len(txt)]
            if ch == " ":
                continue
            th = math.radians(ang) + 2 * math.pi * j / (n * len(txt))
            key = (ch, i, int(round(-math.degrees(th) - 90)) % 360)
            im = _RING_CACHE.get(key)
            if im is None:
                tl, _ = tile(ch, f, fill=pal[i % 3] + (255,))
                im = _RING_CACHE[key] = tl.rotate(key[2], resample=Image.BICUBIC, expand=True)
            x_, y_ = int(round(W / 2 + r * math.cos(th) - im.width / 2)), int(round(H / 2 + r * math.sin(th) - im.height / 2))
            if -im.width < x_ < W and -im.height < y_ < H:
                xa, ya = max(0, x_), max(0, y_)
                part = im.crop((xa - x_, ya - y_, min(im.width, W - x_), min(im.height, H - y_)))
                c.alpha_composite(part, (xa, ya))
    return c


def smooth(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def voice_of(line):
    s = line.strip()
    if s.startswith(">") or s.startswith("$") or re.search(r"\b\d+%|\[.*\]", s):
        return "system"
    if s.startswith("(") and s.endswith(")"):
        return "aside"
    if s.endswith("!") or s.split()[0].lower() in ("stop", "go", "build", "ship", "make", "start", "run"):
        return "command"
    return "narration"


def assign_voices(lines, max_voices=4):
    used = []
    out = []
    for l in lines:
        v = voice_of(l)
        if v not in used:
            if len(used) >= max_voices:
                raise ValueError("more than %d voices" % max_voices)
            used.append(v)
        out.append(v)
    return out


TONES = {"hype": {"font": INTER_K, "enter": "pop", "dur": 0.15, "size": (72, 96)},
         "corporate": {"font": INTER_B, "enter": "slide", "dur": 0.3, "size": (56, 72)},
         "tutorial": {"font": MONO, "enter": "type", "dur": 0.45, "size": (48, 64)},
         "storytelling": {"font": SERIF, "enter": "fade", "dur": 0.8, "size": (48, 60)}}


EMO = {"amazing", "love", "never", "finally", "insane", "free"}


CTA = {"join", "buy", "subscribe", "follow", "download", "try"}


def emphasis(words, brands=()):
    out = []
    for w in words:
        c = w.strip(".,!?—").strip()
        if not c:
            continue
        if c in brands or re.search(r"\d", c) or (c.isupper() and len(c) > 1) or c.lower() in EMO or c.lower() in CTA:
            out.append(c)
    return out


def chrome_dom(wd, html_text, name, budget=3000):
    src = Path(wd) / (name + ".html")
    src.write_text(html_text, encoding="utf-8")
    exe = chrome_bin()
    if not exe:
        raise RuntimeError("no headless chrome shell found")
    r = subprocess.run([exe, "--no-sandbox", "--disable-gpu", "--user-data-dir=%s" % (Path(wd) / ("chrome-" + name)),
                        "--virtual-time-budget=%d" % budget, "--dump-dom", src.as_uri()], capture_output=True, timeout=40,
                       stdin=subprocess.DEVNULL, text=True)
    return src, r.stdout


EQ_TERMS = [("E", "t"), ("=", "op"), ("m", "t"), ("c²", "t"), ("+", "op"), ("p", "t"), ("c", "t")]


def eq_svg(t, stagger=0.1, hold=0.3):
    x, parts, k = 30, [], 0
    for s, kind in EQ_TERMS:
        if kind == "op":
            op = 1.0
        else:
            op = clamp((t - hold - stagger * k) / 0.2)
            k += 1
        parts.append('<tspan x="%d" opacity="%.3f">%s</tspan>' % (x, op, s))
        x += 46 if len(s) == 1 else 62
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="420" height="120"><rect width="420" height="120" fill="#000"/>'
            '<text y="78" font-family="Liberation Serif" font-size="56" fill="#fff">%s</text></svg>' % "".join(parts))


def enter_state(style, p):
    """Opacity, blur px, dy px, scale, wipe fraction, chars fraction, outline-only for an enter style at progress p in [0,1]."""
    e = cubic_out(p)
    s = {"op": 1.0, "blur": 0.0, "dy": 0.0, "scale": 1.0, "wipe": 1.0, "chars": 1.0, "outline": False}
    if p >= 1:
        return s
    if style == "soft":
        s["op"] = e
    elif style == "blur":
        s["op"], s["blur"] = e, 8 * (1 - e)
    elif style == "rise":
        s["op"], s["dy"] = e, 20 * (1 - e)
    elif style == "cut":
        s["op"] = 1.0 if p > 0 else 0.0
    elif style == "type":
        s["chars"] = p
    elif style == "wipe":
        s["wipe"] = e
    elif style == "slam":
        s["scale"] = 1 + 1.5 * (1 - e)
    elif style == "pop":
        s["scale"] = max(0.01, back_out(p, 1.7))
    elif style == "blurpop":
        s["scale"], s["blur"] = max(0.01, back_out(p, 1.7)), 6 * (1 - e)
    elif style == "draw":
        s["outline"] = p < 0.6
    elif style == "flicker":
        s["op"] = 1.0 if int(p * 10) % 2 else 0.15
    return s


def parse_accent(line):
    out = []
    for i, part in enumerate(re.split(r"\*([^*]+)\*", line)):
        if part:
            out.append((part, i % 2 == 1))
    return out


def css_tokens(css):
    return {k: v.strip().strip('"') for k, v in re.findall(r"--([\w-]+)\s*:\s*([^;]+);", css)}
