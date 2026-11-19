"""Helpers of runners/fam_typography_arabic.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from pathlib import Path
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


K = 0.5


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


def acf_pitch(m, lo, hi):
    """Dominant row period of an ink mask (autocorrelation of the row profile)."""
    np = np_()
    p = m.sum(axis=1).astype(float)
    p = p - p.mean()
    best, lag = -1e18, 0
    for L in range(int(lo), int(hi) + 1):
        v = float((p[:-L] * p[L:]).sum())
        if v > best:
            best, lag = v, L
    return lag


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


AR_LETTERS = "؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿"


AR_RUN = re.compile("[%s«](?:[%s‌‍ «»]*[%s»])?" % (AR_LETTERS, AR_LETTERS, AR_LETTERS))


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


def split_arabic(text, max_chars=18):
    lines, cur = [], ""
    for w in text.split():
        if cur and len(cur) + 1 + len(w) > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines[:4]


def graphemes(s):
    out = []
    for ch in s:
        if out and unicodedata.category(ch) in ("Mn", "Me"):
            out[-1] += ch
        else:
            out.append(ch)
    return out


def parse_script(text):
    lines = []
    for raw in text.splitlines():
        raw = re.sub(r"\[[^\]]*\]", "", raw).replace("...", "").replace("…", "").strip()
        if not raw:
            continue
        toks, seen = [], False
        for w in raw.split():
            em = w.startswith("*") and w.endswith("*") and len(w) > 2
            toks.append({"w": w.strip("*"), "em": bool(em and not seen)})
            seen = seen or em
        lines.append(toks)
    return lines


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


def line_meta(s):
    return {"question": "؟" in s or "?" in s, "quote": "«" in s}


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


AR_DIGITS = "٠١٢٣٤٥٦٧٨٩"


def to_ar_digits(s):
    return "".join(AR_DIGITS[int(c)] if c.isdigit() and c in "0123456789" else c for c in str(s))


def balance_lines(words, f, n):
    """text-wrap: balance — the split into n lines with the smallest widest line."""
    import itertools
    best = None
    for cuts in itertools.combinations(range(1, len(words)), n - 1):
        parts = [" ".join(words[a:b]) for a, b in zip((0,) + cuts, cuts + (len(words),))]
        wmax = max(tlen(x, f) for x in parts)
        if best is None or wmax < best[0]:
            best = (wmax, parts)
    return best[1]


PARTICLES = {"في", "من", "على", "إلى", "الى", "عن", "و", "ثم", "أن", "ان", "لا", "ما", "يا", "بل", "قد", "لم", "لن", "إن", "كل"}


OPENERS = {"اللهم", "يا", "إلا", "الا", "اجعل", "اغفر", "ارحم", "اهدنا", "ارزقنا"}


def segment_dp(words, max_words=7, lo=1.1, hi=3.6):
    """DP over cut points: break bonus (pause, punctuation, openers, و/ف clauses) minus penalties; line 1.1–3.6 s, ≤7 words."""
    n = len(words)

    def bonus(j):                                         # cut after word j-1 (between j-1 and j)
        if j >= n:
            return 0.0
        a, b = words[j - 1], words[j]
        gap = max(0.0, b["s"] - a["e"])
        v = 8 * min(gap, 1) + (1.0 if re.search(r"[،,.!؟?]$", a["w"]) else 0)
        bw = b["w"].strip("،,.")
        v += 0.8 if bw in OPENERS else 0
        v += 0.6 if bw.startswith("و") and len(bw) > 2 else 0
        v += 0.5 if bw.startswith("ف") and len(bw) > 3 else 0
        if a["w"].strip("،,.") in PARTICLES:
            v -= 0.7
        if a["w"].isdigit() and b["w"].isdigit():
            v -= 0.8
        if bw == "يا" and j >= 2 and words[j - 2]["w"] == "يا":
            v -= 1.0
        return v
    best = [(-1e9, None)] * (n + 1)
    best[0] = (0.0, None)
    for j in range(1, n + 1):
        for i in range(max(0, j - max_words), j):
            dur = words[j - 1]["e"] - words[i]["s"]
            pen = 2.0 * (max(0, lo - dur) + max(0, dur - hi))
            sc = best[i][0] + bonus(j) - pen - 0.3
            if sc > best[j][0]:
                best[j] = (sc, i)
    cuts, j = [], n
    while j > 0:
        i = best[j][1]
        cuts.append((i, j))
        j = i
    return [words[i:j] for i, j in reversed(cuts)]


def timed(text, pauses=None, wps=2.2, start=0.5):
    pauses = pauses or {}
    out, t = [], start
    for k, w in enumerate(text.split()):
        d = 0.25 + 0.04 * len(w)
        out.append({"w": w, "s": round(t, 3), "e": round(t + d, 3)})
        t += d + 0.08 + pauses.get(k, 0)
    return out


STOP = {"ده", "دي", "كده", "بس", "يعني", "اوي", "أوي", "في", "من", "على", "إلى", "عن", "هذا", "هذه", "التي", "الذي", "ثم", "و", "يا",
        "هو", "هي", "انا", "أنا", "احنا", "إحنا", "مش", "كان", "كانت", "لما", "علشان", "عشان", "قوي", "جدا", "اللي", "إن", "أن"}


UNITS = {"جنيه", "ريال", "دولار", "كيلو", "متر", "سنة", "سنين", "مرة", "ساعة", "%", "٪"}


def pick_keywords(lines, rms, spacing=1.2):
    """stress = 0.65·z(log rms) + 0.35·z(length); + 0.9·(i+1)/n end focus; +0.5 recurring 2–3x; unit after number −3; fillers never."""
    import statistics
    flat = [w for l in lines for w in l]
    lr = [math.log(max(1e-6, rms[id(w)])) for w in flat]
    ln = [len(w["w"]) for w in flat]
    z = lambda v, xs: (v - statistics.mean(xs)) / (statistics.pstdev(xs) or 1)
    counts = {}
    for w in flat:
        counts[w["w"]] = counts.get(w["w"], 0) + 1
    picked, used, last_t = [], set(), -1e9
    k = 0
    for l in lines:
        best, bw = -1e9, None
        for i, w in enumerate(l):
            idx = flat.index(w)
            if w["w"] in STOP or w["w"] in used:
                continue
            sc = 0.65 * z(lr[idx], lr) + 0.35 * z(ln[idx], ln) + 0.9 * (i + 1) / len(l)
            sc += 0.5 if 2 <= counts[w["w"]] <= 3 else 0
            if i > 0 and (l[i - 1]["w"].isdigit() or re.fullmatch("[٠-٩]+", l[i - 1]["w"])) and w["w"] in UNITS:
                sc -= 3
            if sc > best:
                best, bw = sc, w
        if bw is not None and bw["s"] - last_t >= spacing:
            picked.append(bw["w"])
            used.add(bw["w"])
            last_t = bw["s"]
        else:
            picked.append(None)
    return picked


def ar_norm(t):
    t = unicodedata.normalize("NFKC", t)
    t = re.sub("[ً-ٰٟـ]", "", t)
    t = re.sub("[أإآٱ]", "ا", t).replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
    t = t.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789"))
    t = re.sub(r"[^\w\s]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def align_text(lyrics, asr):
    import difflib
    a = [ar_norm(w) for w in lyrics]
    b = [ar_norm(w["w"]) for w in asr]
    out = [None] * len(lyrics)
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            out[blk.a + k] = (asr[blk.b + k]["s"], asr[blk.b + k]["e"])
    for i in range(len(out)):                                   # fuzzy pass for near misses
        if out[i] is None:
            best = max(range(len(b)), key=lambda j: difflib.SequenceMatcher(a=a[i], b=b[j]).ratio())
            if difflib.SequenceMatcher(a=a[i], b=b[best]).ratio() >= 0.6:
                out[i] = (asr[best]["s"], asr[best]["e"])
    return out


def tone_words(path, words, rate=16000):
    np = np_()
    n = int((words[-1]["e"] + 0.5) * rate)
    s = np.zeros(n)
    for k, w in enumerate(words):
        a, b = int(w["s"] * rate), int(w["e"] * rate)
        tt = np.arange(b - a) / rate
        s[a:b] = w.get("amp", 0.4) * np.sin(2 * math.pi * (180 + 20 * (k % 5)) * tt) * np.hanning(b - a)
    fx.write_wav(path, s, rate)
    return path


def mk_latin(s):
    return s.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫٬", "01234567890123456789.,"))


def line_meta_full(s):
    t = mk_latin(s)
    m = re.search(r"(\d+(?:[.,]\d+)*)\s*(%|٪|ألف|مليون|مليار|k|M)?", t)
    return {"num": float(m.group(1).replace(",", "")) if m else None, "unit": (m.group(2) if m else None),
            "question": "؟" in s or "?" in s, "quote": "«" in s}


def ar_plural(n):
    m = n % 100
    return "zero" if n == 0 else "one" if n == 1 else "two" if n == 2 else "few" if 3 <= m <= 10 else "many" if 11 <= m <= 99 else "other"


def edits_phrase(n):
    d = to_ar_digits(n)
    return {"zero": "لا تعديلات", "one": "تعديل واحد بانتظار الإرسال", "two": "تعديلان بانتظار الإرسال",
            "few": "%s تعديلات بانتظار الإرسال" % d, "many": "%s تعديلاً بانتظار الإرسال" % d, "other": "%s تعديل بانتظار الإرسال" % d}[ar_plural(n)]


def merc(lng, lat, z):
    s = 256 * 2 ** z
    x = (lng + 180) / 360 * s
    la = math.radians(lat)
    y = (1 - math.log(math.tan(la) + 1 / math.cos(la)) / math.pi) / 2 * s
    return x, y


def unmojibake(s):
    best = s
    if len(AR_RE.findall(s)) >= 2:
        return s
    for enc, dec in (("latin-1", "utf-8"), ("cp1252", "utf-8"), ("latin-1", "cp1256")):
        try:
            g = s.encode(enc).decode(dec)
        except (UnicodeError, LookupError):
            continue
        if len(re.findall("[؀-ۿ]", g)) >= 2:
            return g
    return best


def safe_name(s):
    return re.sub(r"[^\w\-. ()؀-ۿ]", "", s).strip()


AR_HUE = [(15, "أحمر"), (45, "برتقالي"), (62, "أصفر"), (165, "أخضر"), (260, "أزرق"), (300, "بنفسجي"), (340, "وردي"), (360, "أحمر")]


def name_ar(rgb):
    import colorsys
    h, s, v = colorsys.rgb_to_hsv(*[c / 255 for c in rgb])
    if s < 0.14 or v < 0.12:
        return "أسود" if v < 0.12 else "أبيض" if v > 0.88 else ("رمادي غامق" if v < 0.45 else "رمادي")
    deg = h * 360
    base = next(n for lim, n in AR_HUE if deg < lim)
    if base in ("برتقالي", "أصفر") and s < 0.35 and v > 0.8:
        return "كريمي"
    if base == "أصفر" and v < 0.6:
        return "زيتوني"
    return base + (" داكن" if v < 0.45 else "")


def paint_text(img, s, x, y, size, colour, anchor="ms", bold=False, alpha=1.0, ss=2):
    """Painter-scene text op: supersampled, shaped, solid or (first-stop) gradient colour, anchors ms/mm/ls/rs."""
    from PIL import Image, ImageDraw
    W, H = img.size
    big = Image.new("RGBA", (W * ss, H * ss), (0, 0, 0, 0))
    f = font(CAIRO, size * ss, 760 if bold else 400)
    ImageDraw.Draw(big).text((x * ss, y * ss), s, font=f, fill=tuple(colour) + (int(255 * alpha),), anchor=anchor,
                             direction=_dir(s), language="ar" if _dir(s) == "rtl" else None)
    img.alpha_composite(big.resize((W, H), Image.LANCZOS))


def svg_import(svg, img):
    import xml.etree.ElementTree as ET
    ns = {"s": "http://www.w3.org/2000/svg"}
    root = ET.fromstring(svg)
    grads = {g.get("id"): g.find("s:stop", ns).get("stop-color") for g in root.iter("{http://www.w3.org/2000/svg}linearGradient")}
    amap = {"start": "ls", "middle": "ms", "end": "rs"}
    done = []
    for t in root.iter("{http://www.w3.org/2000/svg}text"):
        fill = t.get("fill", "#ffffff")
        m = re.match(r"url\(#(.+)\)", fill)
        col = hexrgb(grads[m.group(1)] if m else fill)
        txt = "".join(t.itertext()).strip()
        bold = int(t.get("font-weight", "400")) >= 600
        anchor = amap.get(t.get("text-anchor", "start"), "ls")
        if _dir(txt) == "rtl" and t.get("text-anchor", "start") == "start":
            anchor = "rs"
        paint_text(img, txt, float(t.get("x")), float(t.get("y")), int(float(t.get("font-size"))), col, anchor, bold)
        done.append({"text": txt, "colour": col, "anchor": anchor, "bold": bold})
    return done


ORN = "✦★☾❖✿"


def decorate_bio(s):
    out = []
    for w in s.split():
        if len(w) > 2:
            w = w[:-1] + "ــ" + w[-1]
        out.append(w)
    return "✦ " + " ".join(out) + " ✦"


def motion_lint(s):
    issues = []
    if "ـ" in s:
        issues.append("tatweel")
    if any(ch in ORN or unicodedata.category(ch) == "So" for ch in s):
        issues.append("ornament")
    return issues
