"""Helpers of runners/fam_w3_10.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from pathlib import Path
import html as _html
from .core import fx
import json
import math
import os
import re
import subprocess
import unicodedata


FONTS = Path(__import__("os").environ.get("KOSIF_FONTS") or Path.home() / "kosif-tool" / ".claude" / "skills" / "kosif-superpowers" / "proofs" / "_shared" / "fonts")  # read-only asset in the old repo


CAIRO = FONTS / "Cairo[slnt,wght].ttf"


AMIRI = FONTS / "Amiri-Regular.ttf"


AMIRI_B = FONTS / "Amiri-Bold.ttf"


TAJAWAL = FONTS / "Tajawal-Bold.ttf"


POPPINS = FONTS / "Poppins-Bold.ttf"


AR_RE = re.compile("[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")


def np_():
    import numpy as np
    return np


def font(path=CAIRO, size=48, wght=None, basic=False):
    from PIL import ImageFont
    eng = ImageFont.Layout.BASIC if basic else ImageFont.Layout.RAQM
    f = ImageFont.truetype(str(path), int(round(size)), layout_engine=eng)
    if wght is not None:
        axes = f.get_variation_axes()
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


def arr(im):
    np = np_()
    return np.asarray(im.convert("RGB"), dtype=float)


def lum(a):
    return a[..., :3].mean(axis=-1)


def bbox(m):
    np = np_()
    ys, xs = np.nonzero(m)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def comps(m):
    from scipy import ndimage
    return int(ndimage.label(m)[1])


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


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


def shaped_mask(text, f, fill=255):
    """Binary ink mask of a raqm-shaped string."""
    t, _ = tile(text, f, fill=(255, 255, 255, 255))
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


CAIRO800 = FONTS / "cairo-arabic-800-normal.woff2"


CAIRO600 = FONTS / "cairo-arabic-600-normal.woff2"


REEM = FONTS / "ReemKufi[wght].ttf"


AREF_B = FONTS / "ArefRuqaa-Bold.ttf"


POPPINS_R = FONTS / "Poppins-Regular.ttf"


MONO = Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")


INTER = Path("/usr/share/fonts/opentype/inter/Inter-Regular.otf")


FMB = Path("/home/claude/fastify-motion-bro")


def chrome_dump(wd, name, html_text, size=(400, 300), budget=1500):
    """Run a page offline in the headless shell and return the JSON its script wrote into <pre id=OUT>."""
    exe = chrome_bin()
    if not exe:
        raise RuntimeError("no headless chrome shell found")
    src = Path(wd) / (name + ".html")
    src.write_text(html_text, encoding="utf-8")
    cmd = [exe, "--no-sandbox", "--disable-gpu", "--hide-scrollbars", "--allow-file-access-from-files",
           "--host-resolver-rules=MAP * ~NOTFOUND", "--user-data-dir=%s" % (Path(wd) / ("chrome-" + name)),
           "--window-size=%d,%d" % size, "--virtual-time-budget=%d" % budget, "--dump-dom", src.as_uri()]
    done = subprocess.run(cmd, capture_output=True, text=True, timeout=40, stdin=subprocess.DEVNULL)
    m = re.search(r'<pre id="OUT">(.*?)</pre>', done.stdout, re.S)
    if not m or not m.group(1).strip():
        raise RuntimeError("page wrote no #OUT: " + done.stderr[-300:])
    out = json.loads(_html.unescape(m.group(1)))
    if isinstance(out, dict) and out.get("__error"):
        raise RuntimeError("page error: " + out["__error"])
    return src, out


def hpage(body, js, css="", W=400, H=300):
    faces = ("@font-face{font-family:'CairoT';src:url('%s') format('woff2');font-weight:800}"
             "@font-face{font-family:'CairoT';src:url('%s') format('woff2');font-weight:600}") % (
        CAIRO800.as_uri(), CAIRO600.as_uri())
    return ("<!doctype html><html><head><meta charset=utf-8><style>%shtml,body{margin:0;background:#fff;"
            "width:%dpx;height:%dpx;overflow:hidden}%s</style></head><body>%s<pre id=\"OUT\"></pre><script>"
            "function OUT(v){document.getElementById('OUT').textContent=JSON.stringify(v)}"
            "(async()=>{try{%s}catch(e){OUT({__error:String(e)})}})();</script></body></html>") % (faces, W, H, css, body, js)


def bez(x1, y1, x2, y2):
    def bx(t, a, b):
        return 3 * a * t * (1 - t) ** 2 + 3 * b * t * t * (1 - t) + t ** 3

    def f(p):
        p = clamp(p)
        if p <= 0 or p >= 1:
            return p
        lo, hi = 0.0, 1.0
        for _ in range(40):
            mid = (lo + hi) / 2
            if bx(mid, x1, x2) < p:
                lo = mid
            else:
                hi = mid
        return bx((lo + hi) / 2, y1, y2)
    return f


def in_out_cubic(p):
    p = clamp(p)
    return 4 * p ** 3 if p < .5 else 1 - (-2 * p + 2) ** 3 / 2


def in_back(p, s=1.70158):
    p = clamp(p)
    return (s + 1) * p ** 3 - s * p ** 2


def prog(t, a, b):
    return clamp((t - a) / (b - a)) if b > a else float(t >= a)


def spring_curve(k, c, m=1.0, T=3.0, dt=1 / 2400.0):
    """Damped spring from 0 to 1 (semi-implicit Euler); returns f(t)."""
    n = int(T / dt) + 2
    xs = [0.0] * n
    x, v = 0.0, 0.0
    for i in range(1, n):
        a = (-k * (x - 1.0) - c * v) / m
        v += a * dt
        x += v * dt
        xs[i] = x
    return lambda t: 0.0 if t <= 0 else (xs[min(n - 1, int(t / dt))] if t < T else 1.0)


def mono(size):
    from PIL import ImageFont
    return ImageFont.truetype(str(MONO), int(size))


def draw_digits(c, text, x, y, size, fill=(255, 255, 255)):
    from PIL import ImageDraw
    ImageDraw.Draw(c).text((x, y), text, font=mono(size), fill=fill)


def read_digits(fr, x, y, n, size, alphabet="0123456789", thr=100, search=0):
    """Decode a mono number drawn by draw_digits at (x, y): nearest template per cell (blank -> ' ').
    search=k also tries origins x-k..x and keeps the decode with the smallest total mismatch."""
    from PIL import Image, ImageDraw
    np = np_()
    f = mono(size)
    adv = f.getlength("0")
    hgt = int(size * 1.25)
    cw = int(round(adv))
    temps = {}
    for ch in alphabet:
        im = Image.new("L", (cw, hgt), 0)
        ImageDraw.Draw(im).text((0, 0), ch, font=f, fill=255)
        temps[ch] = np.asarray(im, dtype=float) > thr
    g = lum(fr) > thr
    best_txt, best_cost = None, None
    for dx in range(-search, 1):
        out, cost = "", 0.0
        for k in range(n):
            x0 = int(round(x + dx + k * adv))
            cell = np.zeros((hgt, cw), bool)
            part = g[int(y):int(y) + hgt, max(0, x0):max(0, x0) + cw]
            cell[:part.shape[0], :part.shape[1]] = part
            if cell.sum() < 3:
                out += " "
                continue
            costs = {ch: float((temps[ch] ^ cell).sum()) for ch in temps}
            ch = min(costs, key=costs.get)
            out += ch
            cost += costs[ch]
        if best_cost is None or cost < best_cost:
            best_txt, best_cost = out, cost
    return best_txt


def resample(pts, step=1.0):
    np = np_()
    p = np.asarray(pts, dtype=float)
    seg = np.hypot(*np.diff(p, axis=0).T)
    cum = np.concatenate([[0], np.cumsum(seg)])
    L = cum[-1]
    s = np.arange(0, L + 1e-9, step)
    if s[-1] < L:
        s = np.append(s, L)
    return np.stack([np.interp(s, cum, p[:, 0]), np.interp(s, cum, p[:, 1])], axis=1), L


def prefix(pts, frac):
    """Polyline prefix holding `frac` of the arc length (the dashoffset draw-on of pathLength=1)."""
    np = np_()
    p = np.asarray(pts, dtype=float)
    seg = np.hypot(*np.diff(p, axis=0).T)
    cum = np.concatenate([[0], np.cumsum(seg)])
    L = cum[-1] * clamp(frac)
    if L <= 0:
        return p[:1]
    k = int(np.searchsorted(cum, L))
    k = max(1, min(k, len(p) - 1))
    u = (L - cum[k - 1]) / max(1e-9, seg[k - 1])
    tip = p[k - 1] + (p[k] - p[k - 1]) * u
    return np.vstack([p[:k], tip[None]])


def point_at(pts, frac):
    return prefix(pts, frac)[-1]


def plen(pts):
    np = np_()
    p = np.asarray(pts, dtype=float)
    return float(np.hypot(*np.diff(p, axis=0).T).sum()) if len(p) > 1 else 0.0


def poly(im, pts, width, fill, cap=True):
    from PIL import ImageDraw
    d = ImageDraw.Draw(im)
    q = [tuple(map(float, x)) for x in pts]
    if len(q) >= 2:
        d.line(q, fill=fill, width=int(round(width)), joint="curve")
    if cap and q:
        r = width / 2.0
        for x, y in (q[0], q[-1]):
            d.ellipse((x - r, y - r, x + r, y + r), fill=fill)


def rgbim(size, bg):
    from PIL import Image
    return Image.new("RGB", size, tuple(bg))


def film(wd, name, draw, dur, size=(320, 180), fps=30):
    """draw(t) -> PIL RGB frame; encoded losslessly (libx264rgb qp 0) and decoded back exactly."""
    np = np_()
    W, H = size
    n = int(round(dur * fps))
    path = Path(wd) / name
    p = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", "%dx%d" % (W, H), "-r", str(fps), "-i", "-", "-c:v", "libx264rgb", "-qp", "0",
                          "-preset", "ultrafast", str(path)], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    for i in range(n):
        p.stdin.write(draw(i / fps).convert("RGB").tobytes())
    p.stdin.close()
    err = p.stderr.read()
    if p.wait():
        raise RuntimeError("encode failed: %s" % err[-300:])
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, timeout=120, stdin=subprocess.DEVNULL).stdout
    return path, np.frombuffer(out, dtype=np.uint8).reshape(-1, H, W, 3).astype(float)


def sharp(a):
    """Variance of the Laplacian of the luminance (focus measure)."""
    from scipy import ndimage
    return float(ndimage.laplace(lum(a)).var())


def node_eval(js, timeout=20):
    done = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    if done.returncode:
        raise RuntimeError("node failed: " + done.stderr[-300:])
    return json.loads(done.stdout)


def strip_marks(s):
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn")


def angle_grid(h, w, cx, cy):
    """Per-pixel radius and clockwise angle from 12 o'clock, in degrees 0..360."""
    np = np_()
    ys, xs = np.mgrid[0:h, 0:w]
    dx, dy = xs + 0.5 - cx, ys + 0.5 - cy
    return np.hypot(dx, dy), (np.degrees(np.arctan2(dx, -dy)) + 360.0) % 360.0


def _split_words(text):
    return [w for w in text.split(" ") if w]


def _kashida(word, n=2):
    """Insert n tatweels after the first letter that joins to the next one (both dual/joining letters)."""
    non_left = set("اأإآدذرزوؤءة")
    for i in range(len(word) - 1):
        a, b = word[i], word[i + 1]
        if a not in non_left and unicodedata.category(a) == "Lo" and unicodedata.category(b) == "Lo":
            return word[:i + 1] + "ـ" * n + word[i + 1:]
    return word


def _persp(src, dst):
    np = np_()
    A, B = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); B.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); B.append(v)
    return list(np.linalg.solve(np.array(A, float), np.array(B, float)))


def _xheight_ar(f):
    return float(crop_ink(shaped_mask("ـسـ", f)).shape[0])


def _xheight_lat(f):
    return float(crop_ink(shaped_mask("x", f)).shape[0])


VIDEO_SCALE = {"caption": (56, 72), "title": (96, 180), "label": (32, 1e9)}


def type_scale(role, script, base=None):
    lo, hi = VIDEO_SCALE[role]
    b = base if base is not None else {"caption": 58, "title": 120, "label": 32}[role]
    return round(b * (1.12 if script == "ar" else 1.0), 1)


def meaning_units(words, maxw=5):
    n = len(words)
    k = math.ceil(n / maxw)
    base, extra = divmod(n, k)
    out, i = [], 0
    for j in range(k):
        m = base + (1 if j < extra else 0)
        out.append(words[i:i + m])
        i += m
    return out


def _word_frame(word, f, W=360, H=160, bg=(0, 0, 0)):
    t, _ = tile(word, f)
    return t


def _alpha_np(t):
    return np_().asarray(t.getchannel("A"), dtype=float) / 255.0


def quart_out(p):
    return pow_out(p, 4)


def graphemes_n(s):
    import regex
    return len([g for g in regex.findall(r"\X", s) if not g.isspace()])


def display_time(text):
    return min(6.0, max(0.15 * graphemes_n(text), 2.0))


def _ass(path, W, H, styles, events):
    head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: %d\nPlayResY: %d\nWrapStyle: 0\n\n[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
            "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
            "MarginR, MarginV, Encoding\n") % (W, H)
    st = "".join("Style: %s,Cairo,%g,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,%d,%g,%g,2,%d,%d,%d,1\n"
                 % (n, fs, bs, ol, sh, ml, ml, mv) for n, fs, bs, ol, sh, ml, mv in styles)
    ev = "\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n" + "".join(
        "Dialogue: 0,0:00:00.00,0:00:05.00,%s,,0,0,0,,%s\n" % (s, "‏" + t + "‏") for s, t in events)
    Path(path).write_text(head + st + ev, encoding="utf-8")
    return Path(path)


def _libass_frame(wd, name, W, H, styles, events, bg="0x808080"):
    a = _ass(Path(wd) / (name + ".ass"), W, H, styles, events)
    out = Path(wd) / (name + ".png")
    fx.ffmpeg("-f", "lavfi", "-i", "color=c=%s:s=%dx%d:d=1" % (bg, W, H), "-vf",
              "subtitles=%s:fontsdir=%s" % (a, FONTS), "-frames:v", "1", str(out))
    from PIL import Image
    return out, np_().asarray(Image.open(out).convert("RGB"), dtype=float)


def cmask(a, col, tol=24):
    np = np_()
    return np.abs(a[..., :3] - np.array(hexrgb(col) if isinstance(col, str) else col, dtype=float)).max(-1) <= tol


def vbar_heights(a, xs, col, w=6, tol=24):
    """Measured height (px) of a vertical bar of colour col at each x centre."""
    np = np_()
    out = []
    for x in xs:
        m = cmask(a[:, int(x) - w // 2:int(x) + w // 2 + 1], col, tol).any(1)
        out.append(int(m.sum()))
    return out


def pil(size, bg):
    return rgbim(size, hexrgb(bg) if isinstance(bg, str) else bg)


def drect(im, box, col):
    from PIL import ImageDraw
    x0, y0, x1, y1 = box
    if x1 - x0 >= 0.5 and y1 - y0 >= 0.5:
        ImageDraw.Draw(im).rectangle((round(x0), round(y0), round(x1) - 1, round(y1) - 1),
                                     fill=hexrgb(col) if isinstance(col, str) else col)


def dtext(im, xy, s, f, col, anchor="la", **kw):
    from PIL import ImageDraw
    ImageDraw.Draw(im).text(xy, s, font=f, fill=hexrgb(col) if isinstance(col, str) else col, anchor=anchor, **kw)


def pie_plan(vals, labels):
    order = sorted(range(len(vals)), key=lambda i: -vals[i])
    tot = float(sum(vals))
    pct = [vals[i] / tot * 100 for i in order]
    if max(pct) - min(pct) <= 5:
        return {"type": "stacked-bar", "slices": [(labels[i], vals[i]) for i in order]}
    keep = order[:5]
    other = sum(vals[i] for i in order[5:])
    sl = [(labels[i], vals[i]) for i in keep] + ([("أخرى", other)] if other else [])
    return {"type": "pie", "slices": sl}


PAL6 = ["#2563eb", "#f59e0b", "#10b981", "#ef4444", "#a855f7", "#64748b"]


def draw_pie(im, cx, cy, r, slices, sweep=360.0, cols=PAL6):
    from PIL import ImageDraw
    d = ImageDraw.Draw(im)
    tot = float(sum(v for _, v in slices))
    a = 0.0
    for k, (_, v) in enumerate(slices):
        size = v / tot * 360.0
        vis = clamp(sweep - a, 0, size)
        if vis > 0:
            d.pieslice((cx - r, cy - r, cx + r, cy + r), -90 + a, -90 + a + vis, fill=hexrgb(cols[k % len(cols)]))
        a += size


def slice_extent(a, cx, cy, r, col):
    np = np_()
    rr, ang = angle_grid(a.shape[0], a.shape[1], cx, cy)
    m = cmask(a, col, 10) & (rr < r - 2) & (rr > r * 0.3)
    if not m.any():
        return 0.0, None
    ring = (rr < r - 2) & (rr > r * 0.3)
    hist = np.zeros(360)
    for d in range(360):
        sel = ring & (ang >= d) & (ang < d + 1)
        hist[d] = (m & sel).sum() / max(1, sel.sum())
    deg = np.nonzero(hist > 0.5)[0]
    return float((hist > 0.5).sum()), int(deg.min())


def activity_style(act):
    import colorsys
    w = 2 + 4 * clamp(act)
    sat = 0.4 + 0.6 * clamp(act)
    r, g, b = colorsys.hsv_to_rgb(0.58, sat, 0.95)
    return w, (int(r * 255), int(g * 255), int(b * 255))


def out_quint(p):
    return pow_out(p, 5)


def mulberry32(seed):
    a = seed & 0xFFFFFFFF

    def r():
        nonlocal a
        a = (a + 0x6D2B79F5) & 0xFFFFFFFF
        t = a
        t = ((t ^ (t >> 15)) * (t | 1)) & 0xFFFFFFFF
        t ^= (t + (((t ^ (t >> 7)) * (t | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0
    return r


def compact(v, ar=False):
    a = abs(v)
    for lim, en, arw in ((1e9, "B", "مليار"), (1e6, "M", "مليون"), (1e3, "K", "ألف")):
        if a >= lim:
            x = "%.1f" % (v / lim)
            return (x + " " + arw) if ar else (x + en)
    return "{:,}".format(int(v))


def haversine(a, b, R=6371.0088):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def line_series_px(vals, W, H, pad=30):
    n = len(vals)
    lo, hi = min(vals), max(vals)
    return [(pad + (W - 2 * pad) * i / (n - 1), H - pad - (H - 2 * pad) * (v - lo) / (hi - lo)) for i, v in enumerate(vals)]


def resample_n(pts, n):
    np = np_()
    p = np.asarray(pts, float)
    seg = np.hypot(*np.diff(p, axis=0).T)
    cum = np.concatenate([[0], np.cumsum(seg)])
    s = np.linspace(0, cum[-1], n)
    return np.stack([np.interp(s, cum, p[:, 0]), np.interp(s, cum, p[:, 1])], 1)


def star_poly(cx, cy, R, r=None):
    r = R * 0.45 if r is None else r
    return [(cx + (R if k % 2 == 0 else r) * math.cos(-math.pi / 2 + k * math.pi / 5),
             cy + (R if k % 2 == 0 else r) * math.sin(-math.pi / 2 + k * math.pi / 5)) for k in range(10)]


def drawn_frac(mask, dense, r=1):
    """Share of path samples whose pixel (±r) is inked: the drawn fraction of a stroke along its own path."""
    np = np_()
    H, W = mask.shape
    hit = 0
    for x, y in dense:
        xi, yi = int(round(x)), int(round(y))
        if mask[max(0, yi - r):yi + r + 1, max(0, xi - r):xi + r + 1].any():
            hit += 1
    return hit / float(len(dense))


def zigzag(x0, y0, w, h, n=4):
    return [(x0 + w * i / n, y0 + (h if i % 2 else 0)) for i in range(n + 1)]


def jitter_ellipse(cx, cy, rx, ry, seed, overlap=0.15, n=140, amp=3.0):
    rnd = mulberry32(seed)
    ph = [rnd() * 2 * math.pi for _ in range(3)]
    pts = []
    for i in range(n + 1):
        a = -math.pi / 2 + 2 * math.pi * (1 + overlap) * i / n
        k = 1 + amp / max(rx, ry) * sum(math.sin((j + 2) * a + ph[j]) / (j + 1) for j in range(3)) + 0.14 * i / n
        pts.append((cx + rx * k * math.cos(a), cy + ry * k * math.sin(a)))
    return pts


def rough_rrect(x0, y0, x1, y1, r, seed, amp=1.5):
    rnd = mulberry32(seed)
    pts = []
    corners = [(x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)]
    for cx, cy, a0 in corners:
        for k in range(12):
            a = math.radians(a0 + 90 * k / 11)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    pts.append(pts[0])
    dense, _ = resample(pts, 4.0)
    return [(x + (rnd() - 0.5) * 2 * amp, y + (rnd() - 0.5) * 2 * amp) for x, y in dense] + [(pts[0][0] + 6, pts[0][1])]


def wobble_line(x0, y0, x1, y1, seed, amp=1.5, n=40):
    """Seeded vertex noise (fixed per stroke) smoothed by Catmull-Rom."""
    np = np_()
    rnd = mulberry32(seed)
    base = [(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n) for i in range(n + 1)]
    nx, ny = -(y1 - y0), (x1 - x0)
    l = math.hypot(nx, ny)
    nx, ny = nx / l, ny / l
    off = [(rnd() - 0.5) * 2 * amp for _ in base]
    off[0] = off[-1] = 0
    P = [(x + nx * o, y + ny * o) for (x, y), o in zip(base, off)]
    out = []
    for i in range(len(P) - 1):
        p0, p1, p2, p3 = P[max(0, i - 1)], P[i], P[i + 1], P[min(len(P) - 1, i + 2)]
        for u in np.linspace(0, 1, 8, endpoint=False):
            u2, u3 = u * u, u * u * u
            out.append(tuple(0.5 * ((2 * p1[k]) + (-p0[k] + p2[k]) * u + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * u2 +
                                    (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * u3) for k in range(2)))
    out.append(P[-1])
    return out


def var_width_stroke(im, pts, w0, var, seed, colr):
    from PIL import ImageDraw
    rnd = mulberry32(seed + 7)
    d = ImageDraw.Draw(im)
    ws = []
    for i in range(len(pts) - 1):
        w = w0 * (1 + (rnd() - 0.5) * 2 * var)
        ws.append(w)
        d.line([pts[i], pts[i + 1]], fill=colr, width=max(1, int(round(w))))
    return ws


def pf_outline(pts, size, thinning, pressure):
    """perfect-freehand style: radius = size * (0.5 - thinning * (0.5 - pressure)), left/right offsets -> polygon."""
    np = np_()
    P = np.asarray(pts, float)
    out_l, out_r = [], []
    for i in range(len(P)):
        a, b = P[max(0, i - 1)], P[min(len(P) - 1, i + 1)]
        t = b - a
        n = np.array([-t[1], t[0]]) / (np.hypot(*t) + 1e-9)
        r = size * (0.5 - thinning * (0.5 - pressure[i]))
        out_l.append(tuple(P[i] + n * r)); out_r.append(tuple(P[i] - n * r))
    return out_l + out_r[::-1]


def smooth_step(e0, e1, x):
    t = clamp((x - e0) / (e1 - e0))
    return t * t * (3 - 2 * t)


def fmb_cli(wd, *args, env=None):
    e = dict(os.environ)
    e["TMPDIR"] = str(wd)
    done = subprocess.run(["node", str(FMB / "scripts/profiles-cli.mjs"), *args], cwd=str(wd), capture_output=True, text=True,
                          timeout=30, stdin=subprocess.DEVNULL, env=e)
    return done.returncode, done.stdout + done.stderr


def brand_plate(W=1600, H=900, ground="#0B1F3A", metal="#C9A227"):
    """Deterministic stand-in for a generated still: metal sphere + faceted crystal on a flat brand ground,
    warm rim light, object on the right third."""
    np = np_()
    from PIL import Image, ImageDraw, ImageFilter
    im = Image.new("RGB", (W, H), hexrgb(ground))
    d = ImageDraw.Draw(im)
    cx, cy, r = int(W * 0.72), int(H * 0.52), int(H * 0.22)
    for k in range(r, 0, -2):
        f = k / r
        c = tuple(int(v * (0.55 + 0.45 * (1 - f))) for v in hexrgb(metal))
        d.ellipse((cx - k, cy - k, cx + k, cy + k), fill=c)
    d.polygon([(cx - r, cy + r), (cx - r // 2, cy + r // 3), (cx, cy + r + 20)], fill=(210, 230, 245))
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    ImageDraw.Draw(glow).ellipse((cx - r - 6, cy - r - 6, cx + r + 6, cy + r + 6), outline=(255, 190, 120), width=8)
    return Image.fromarray(np.clip(np.asarray(im, float) + np.asarray(glow.filter(ImageFilter.GaussianBlur(6)), float) * 0.8, 0, 255).astype("uint8"))


def tone_track(path, secs=10.0, rate=44100):
    np = np_()
    t = np.arange(int(secs * rate)) / rate
    f = 220 * (1 + (np.floor(t) % 5) / 4.0)
    s = 0.4 * np.sin(2 * np.pi * np.cumsum(f) / rate)
    return fx.write_wav(path, np.stack([s, s * 0.8], 1), rate)


BPM_BY_INDUSTRY = {"crypto": 100, "finance": 92, "creative": 115, "saas": 108}


def bgm_bpm(industry, cascade=False, demo=False):
    return BPM_BY_INDUSTRY[industry] + (10 if cascade else 0) - (8 if demo else 0)


def bgm_backend(reply):
    return "local-composer" if "limit: 0" in reply else "lyria"


def x01_plan(shots_s, rate=12, reserve=0.30, batch=12):
    bad = [s for s in shots_s if not (4 <= s <= 30)]
    credits = sum(shots_s) * rate
    return {"invalid": bad, "credits": credits, "with_reserve": math.ceil(credits * (1 + reserve)),
            "batches": math.ceil(len(shots_s) / batch)}
