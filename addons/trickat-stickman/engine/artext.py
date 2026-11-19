"""Arabic-aware text layout for the engine.

Every on-screen string goes through layout(): it splits the text into Arabic (RTL) and Latin/number (LTR)
runs, shapes each run with HarfBuzz using the right font (Arabic font for Arabic, the original hand-lettered
Latin font for English words and numbers), orders the runs right-to-left when the line is Arabic, and returns a
ready-to-draw skia.TextBlob plus its advance width. Results are cached, so per-frame drawing stays cheap.
"""
import os, re
from functools import lru_cache
import skia
import uharfbuzz as hb

AR_LETTER = re.compile(r"[؀-ٟٮ-ۓە-ۯۺ-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]")
# tokens: Arabic word | Latin word / number (keeps 3.5, $26.49, 100%, 2/3 together) | spaces | anything else
TOKEN = re.compile(r"[؀-ٟٮ-ۓە-ۯۺ-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿ً-ٰٟـ]+"
                   r"|[A-Za-z0-9٠-٩۰-۹$€£%#+][A-Za-z0-9٠-٩۰-۹$€£%#+.,:/'\-]*(?<![.,:'\-])"
                   r"|\s+|.", re.S)


def is_rtl(s): return bool(AR_LETTER.search(s or ""))


class Face:
    """A font role (hand / body / marker): an Arabic typeface + a Latin typeface, with size trims."""

    def __init__(self, ar_path, lat_path, ar_scale=1.0, ar_dy=0.0):
        self.ar = self._load(ar_path); self.lat = self._load(lat_path); self.ar_scale = ar_scale; self.ar_dy = ar_dy
        self.name = os.path.basename(ar_path)

    @staticmethod
    def _load(path):
        if not os.path.exists(path): raise SystemExit(f"font missing: {path}")
        data = open(path, "rb").read(); face = hb.Face(hb.Blob(data)); font = hb.Font(face)
        tf = skia.Typeface.MakeFromFile(path)
        if tf is None: raise SystemExit(f"font unreadable: {path}")
        return dict(hb=font, upem=face.upem, tf=tf)

    def __repr__(self): return f"Face({self.name})"


def _shape(f, text, rtl):
    buf = hb.Buffer(); buf.add_str(text); buf.guess_segment_properties()
    buf.direction = "rtl" if rtl else "ltr"
    hb.shape(f["hb"], buf, {"kern": True, "liga": True})
    return buf.glyph_infos, buf.glyph_positions


def _classify(tok):
    if AR_LETTER.search(tok): return "R"
    if re.match(r"[A-Za-z0-9٠-٩۰-۹$€£%#+]", tok): return "L"
    return "N"


@lru_cache(maxsize=8192)
def layout(text, face, size):
    """-> (blob or None, width). Blob origin: x=0 at the left edge, y=0 on the baseline."""
    text = str(text)
    if not text.strip(): return None, 0.0
    rtl_par = is_rtl(text)
    toks = TOKEN.findall(text)
    cls = [_classify(t) for t in toks]
    if not rtl_par: cls = ["L"] * len(toks)
    else:  # neutrals take the direction of their strong neighbours, else the paragraph's (RTL)
        for i, c in enumerate(cls):
            if c != "N": continue
            prev = next((cls[j] for j in range(i - 1, -1, -1) if cls[j] != "N"), None)
            nxt = next((cls[j] for j in range(i + 1, len(cls)) if cls[j] != "N"), None)
            cls[i] = "L" if prev == "L" and nxt == "L" else "R"
    runs = []
    for t, c in zip(toks, cls):
        if runs and runs[-1][1] == c: runs[-1][0] += t
        else: runs.append([t, c])
    if rtl_par:
        runs = runs[::-1]
        if runs: runs[0][0] = runs[0][0].rstrip() if runs[0][1] == "R" else runs[0][0]
    pieces = []; x = 0.0
    for t, c in runs:
        rtl = c == "R"
        order = (face.ar, face.lat) if rtl else (face.lat, face.ar)
        for f in order:
            infos, poss = _shape(f, t, rtl)
            if all(i.codepoint != 0 for i in infos) or f is order[-1]: break
        is_ar = f is face.ar
        sz = size * (face.ar_scale if is_ar else 1.0); k = sz / f["upem"]; dy = face.ar_dy * size if is_ar else 0.0
        gl, pts = [], []
        for i, p in zip(infos, poss):
            gl.append(i.codepoint); pts.append(skia.Point(x + p.x_offset * k, dy - p.y_offset * k)); x += p.x_advance * k
        if gl: pieces.append((skia.Font(f["tf"], sz), gl, pts))
    if not pieces: return None, 0.0
    b = skia.TextBlobBuilder()
    for fnt, gl, pts in pieces:
        fnt.setSubpixel(True); fnt.setEdging(skia.Font.Edging.kAntiAlias); b.allocRunPos(fnt, gl, pts)
    return b.make(), x


def width(text, face, size): return layout(text, face, round(size, 2))[1]


def draw(c, text, x, y, face, size, paint):
    """Draw with the left edge at x and the baseline at y."""
    blob, _ = layout(text, face, round(size, 2))
    if blob is not None: c.drawTextBlob(blob, x, y, paint)
