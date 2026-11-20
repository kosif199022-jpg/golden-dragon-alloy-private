"""Fonts, in-world text and burned-in captions. Latin uses Poppins ExtraBold; Arabic (and any right-to-left text)
is shaped with HarfBuzz + bidi through skia's paragraph layout in Lalezar, so letters join and read right to left.
"""
import functools
import math
import os
import re

import skia

from .paint import C, fill, stroke, argb, INK, HERE

FONT_PATH = os.path.join(HERE, 'fonts', 'Poppins-ExtraBold.ttf')
AR_FONT_PATH = os.environ.get('MAVEN_TOON_AR_FONT') or os.path.join(HERE, 'fonts', 'Lalezar-Regular.ttf')
AR_SCALE = 1.14          # Lalezar sits a little smaller than Poppins at the same size

_RTL = re.compile('[֐-ࣿיִ-﷿ﹰ-ﻼ]')


def is_rtl(s):
    return bool(_RTL.search(s or ''))


@functools.lru_cache(maxsize=4)
def typeface(path=FONT_PATH):
    return skia.Typeface.MakeFromFile(path)


@functools.lru_cache(maxsize=256)
def font(size):
    f = skia.Font(typeface(), size)
    f.setEdging(skia.Font.Edging.kAntiAlias)
    f.setSubpixel(True)
    return f


# ----------------------------------------------------------------------------- shaped (Arabic) text
@functools.lru_cache(maxsize=2)
def _collection(path):
    tf = typeface(path)
    prov = skia.textlayout_TypefaceFontProvider()
    prov.registerTypeface(tf)
    fc = skia.textlayout_FontCollection()
    fc.setDefaultFontManager(prov)
    return fc, tf.getFamilyName()


def _unicodes():
    try:
        return skia.Unicodes.ICU.Make()
    except Exception:                                         # pragma: no cover - older skia builds
        return None


def shaped(s, size, paint, path=None, width=100000.0):
    """A laid-out skia Paragraph for s (single line unless it is wider than width)."""
    fc, fam = _collection(path or AR_FONT_PATH)
    ps = skia.textlayout_ParagraphStyle()
    ps.setTextAlign(skia.textlayout_TextAlign.kLeft)
    ts = skia.textlayout_TextStyle()
    ts.setFontFamilies([fam])
    ts.setFontSize(size)
    ts.setForegroundPaint(paint)
    u = _unicodes()
    b = skia.textlayout_ParagraphBuilder.make(ps, fc, u) if u is not None else skia.textlayout_ParagraphBuilder.make(ps, fc)
    b.pushStyle(ts)
    if is_rtl(s):                                             # right-to-left marks so end punctuation (، ؟ !) and
        s = '‏' + s + '‏'                          # numbers sit on the reading side, not the left-to-right one
    b.addText(s)
    p = b.Build()
    p.layout(width)
    return p


@functools.lru_cache(maxsize=1024)
def _shaped_width(s, size):
    return shaped(s, size, fill('#ffffff')).MaxIntrinsicWidth


def text_width(s, size):
    if is_rtl(s):
        return _shaped_width(s, size * AR_SCALE)
    return font(size).measureText(s)


def _draw_shaped(cv, s, x_left, baseline, size, paint):
    p = shaped(s, size, paint)
    p.paint(cv, x_left, baseline - p.AlphabeticBaseline)


def draw_text(cv, s, cx, baseline, size, col='#ffffff', outline=None, ow=0.0, align='center', skew=0.0):
    w = text_width(s, size)
    x = cx - w / 2 if align == 'center' else (cx - w if align == 'right' else cx)
    if is_rtl(s):
        sz = size * AR_SCALE
        if outline:
            _draw_shaped(cv, s, x, baseline, sz, stroke(outline, ow))
        _draw_shaped(cv, s, x, baseline, sz, fill(col))
        return w
    f = font(size)
    blob = skia.TextBlob.MakeFromString(s, f)
    if outline:
        cv.drawTextBlob(blob, x, baseline, stroke(outline, ow))
    cv.drawTextBlob(blob, x, baseline, fill(col))
    return w


# ----------------------------------------------------------------------------- captions
CAP_SIZE = 84            # ~7.8% of 1080 width
CAP_Y = 0.70             # centre of the caption block, fraction of height
CAP_MAX_W = 900          # inside the Shorts safe zone (90 px side margins)


def caption_lines(words, size=CAP_SIZE):
    """1-2 words -> max 2 lines that fit the safe width (Arabic keeps reading order: first word on top)."""
    txt = ' '.join(words)
    if text_width(txt, size) <= CAP_MAX_W or len(words) == 1:
        return [txt]
    return [words[0], ' '.join(words[1:])]


def draw_caption(cv, words, age, W=1080, H=1920, size=CAP_SIZE):
    """age = seconds since the chunk's onset (drives the quick pop-in)."""
    if not words:
        return
    # pop: 0.86 -> 1.06 -> 1.0 over ~0.12 s
    k = min(1.0, age / 0.12)
    sc = 0.86 + 0.2 * math.sin(k * math.pi * 0.5) if k < 1 else 1.0
    if 0.6 < k < 1.0:
        sc = 1.06 - (k - 0.6) / 0.4 * 0.06
    alpha = min(1.0, age / 0.05 + 0.3)
    lines = caption_lines(words, size)
    lh = size * (1.25 if is_rtl(' '.join(words)) else 1.08)
    cy = H * CAP_Y - (len(lines) - 1) * lh / 2
    cv.save()
    cv.translate(W / 2, H * CAP_Y)
    cv.scale(sc, sc)
    cv.translate(-W / 2, -H * CAP_Y)
    for i, ln in enumerate(lines):
        base = cy + i * lh + size * 0.36
        sh = skia.Paint(AntiAlias=True)
        sh.setColor4f(C((0x1b, 0x12, 0x20), 0.55 * alpha))
        sh.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 7))
        if is_rtl(ln):
            sz = size * AR_SCALE
            w = text_width(ln, size)
            x = W / 2 - w / 2
            base += size * 0.08                               # Lalezar's letters sit higher on the baseline
            _draw_shaped(cv, ln, x + 3, base + 6, sz, sh)
            _draw_shaped(cv, ln, x, base, sz, stroke((0x1b, 0x12, 0x20), 10.0, alpha))
            _draw_shaped(cv, ln, x, base, sz, fill('#ffffff', alpha))
            continue
        f = font(size)
        w = f.measureText(ln)
        blob = skia.TextBlob.MakeFromString(ln, f)
        x = W / 2 - w / 2
        cv.drawTextBlob(blob, x + 3, base + 6, sh)
        cv.drawTextBlob(blob, x, base, stroke((0x1b, 0x12, 0x20), 8.5, alpha))
        cv.drawTextBlob(blob, x, base, fill('#ffffff', alpha))
    cv.restore()
