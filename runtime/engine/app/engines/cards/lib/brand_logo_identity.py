"""Helpers of power_programs/brand_logo_identity.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFilter
from PIL import ImageFont
from pathlib import Path
import colorsys
import json
import math
import numpy as np
import re


FONT_DIRS = ["/usr/share/fonts/truetype/noto", "/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/truetype/liberation"]


LATIN = ["NotoSans-Bold.ttf", "NotoSans-Regular.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans.ttf", "LiberationSans-Bold.ttf"]


ARABIC = ["NotoSansArabic-Bold.ttf", "NotoSansArabic-Regular.ttf", "NotoNaskhArabic-Regular.ttf", "DejaVuSans.ttf"]


def font_path(names) -> str:
    for d in FONT_DIRS:
        for n in names:
            p = Path(d) / n
            if p.is_file():
                return str(p)
    raise FileNotFoundError("no usable font")


def font(size: int, arabic=False):
    return ImageFont.truetype(font_path(ARABIC if arabic else LATIN), size)


def save(work: Path, name: str, data) -> Path:
    p = work / name
    if isinstance(data, Image.Image):
        data.save(p)
    elif isinstance(data, (dict, list)):
        p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        p.write_text(str(data), encoding="utf-8")
    return p


def hex2rgb(h: str):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb2hex(c) -> str:
    return "#" + "".join(f"{int(round(v)):02x}" for v in c[:3])


def _lin(c):
    c = c / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def contrast(a: str, b: str) -> float:
    la, lb = (0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(bb) for r, g, bb in (hex2rgb(a), hex2rgb(b)))
    hi, lo = max(la, lb), min(la, lb)
    return round((hi + 0.05) / (lo + 0.05), 2)


def cubic_bezier(x1, y1, x2, y2):
    def bx(t): return 3 * (1 - t) ** 2 * t * x1 + 3 * (1 - t) * t ** 2 * x2 + t ** 3
    def by(t): return 3 * (1 - t) ** 2 * t * y1 + 3 * (1 - t) * t ** 2 * y2 + t ** 3

    def f(x):
        lo, hi = 0.0, 1.0
        for _ in range(60):
            mid = (lo + hi) / 2
            if bx(mid) < x:
                lo = mid
            else:
                hi = mid
        return by((lo + hi) / 2)
    return f


def expo_out(p): return 1.0 if p >= 1 else 1 - 2 ** (-10 * p)


def in_out_cubic(p): return 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2


def out_quad(p): return 1 - (1 - p) ** 2


def clamp01(p): return max(0.0, min(1.0, p))


def spring_curve(stiffness, damping, mass=1.0, frames=120, fps=30, sub=40):
    """Integrate x'' = (-k(x-1) - c x') / m from x=0, v=0 (Remotion-style spring to 1); one value per frame."""
    x, v, out = 0.0, 0.0, []
    dt = 1 / fps / sub
    for _ in range(frames):
        out.append(x)
        for _ in range(sub):
            a = (-stiffness * (x - 1) - damping * v) / mass
            v += a * dt
            x += v * dt
    return np.array(out)


def analytic_overshoot(stiffness, damping, mass=1.0):
    z = damping / (2 * math.sqrt(stiffness * mass))
    return math.exp(-z * math.pi / math.sqrt(1 - z * z)) if z < 1 else 0.0


def srgb_to_oklch(h: str):
    r, g, b = (_lin(c) for c in hex2rgb(h))
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = (np.cbrt(v) for v in (l, m, s))
    L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
    A = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    B = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    return round(float(L), 4), round(float(math.hypot(A, B)), 4), round(math.degrees(math.atan2(B, A)) % 360, 2)


def oklch_to_hex(L, C, H):
    a, b = C * math.cos(math.radians(H)), C * math.sin(math.radians(H))
    l_ = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    rgb = (4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
           -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
           -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_)
    out = []
    for c in rgb:
        c = max(0.0, min(1.0, c))
        c = 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
        out.append(round(c * 255))
    return rgb2hex(out)


def ink_bbox(img: Image.Image, thr=40):
    a = np.asarray(img.convert("L"))
    ys, xs = np.nonzero(a > thr)
    if not len(xs):
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


ARABIC_RE = re.compile(r"[؀-ۿﭐ-﷿ﹰ-﻿]")


def tracking_lint(elements: list) -> list:
    """Flag letter-spacing (tracking) on any element whose text is Arabic."""
    return [e["text"] for e in elements if ARABIC_RE.search(e["text"]) and abs(e.get("letter_spacing", 0)) > 1e-9]


OPERATORS = {"monogram + meaning", "product action", "metaphor fusion", "negative space", "construction geometry"}


def mark_type(name: str, new_product=False, recognition_budget=False) -> str:
    letters = re.sub(r"[^A-Za-z]", "", name)
    if len(name.split()) >= 3 or len(letters) > 12:
        return "lettermark"
    if len(letters) <= 6 and re.search(r"[aeiou]", letters.lower()) and not new_product:
        return "wordmark"
    if recognition_budget:
        return "pictorial"
    return "combination"


def validate_brief(b: dict) -> list:
    errs = [f"missing {k}" for k in ("brand", "one_thing", "for", "surface", "personality", "must", "must_not", "colours") if not b.get(k)]
    if b.get("personality") and not 3 <= len(b["personality"]) <= 5:
        errs.append(f"{len(b['personality'])} adjectives")
    ops = b.get("operators", [])
    if not 1 <= len(ops) <= 2 or not set(ops) <= OPERATORS:
        errs.append(f"operators {ops}")
    return errs


def mono_svg_ok(svg: str) -> bool:
    return not re.search(r"<(linear|radial)Gradient|url\(#", svg)


FONT_MAP = {"technical": ("Space Grotesk", "IBM Plex Sans Arabic"), "warm": ("Nunito Sans", "Tajawal"),
            "authority": ("IBM Plex Sans", "Readex Pro")}


ADJ_CLASS = {"precise": "technical", "engineered": "technical", "modern": "technical", "friendly": "warm",
             "cosy": "warm", "human": "warm", "trusted": "authority", "official": "authority", "serious": "authority"}


def identity_from_interview(answers: dict) -> dict:
    if len(answers) > 4:
        raise ValueError("more than 4 questions")
    votes = {}
    for a in answers["adjectives"]:
        c = ADJ_CLASS.get(a)
        if c:
            votes[c] = votes.get(c, 0) + 1
    cls = max(sorted(votes), key=lambda k: votes[k])
    latin, arabic = FONT_MAP[cls]
    radius = 4 if answers["shape"] == "sharp" else 16
    dark = bool(re.search(r"night|cinema|dark|evening|ليل", answers["watched"]))
    presets = answers.get("presets", [])[:3]
    return {"class": cls, "latin": latin, "arabic": arabic, "radius": radius, "mode": "dark" if dark else "light",
            "presets_shown": presets}


def render_from_tokens(tok: dict, size=(64, 36)) -> Image.Image:
    im = Image.new("RGB", size, hex2rgb(tok["bg"]))
    d = ImageDraw.Draw(im)
    d.rectangle([4, 4, 30, 31], fill=hex2rgb(tok["surface"]))
    d.rectangle([36, 4, 59, 14], fill=hex2rgb(tok["accent"]))
    d.rectangle([36, 20, 59, 31], fill=hex2rgb(tok["text"]))
    return im


def drift(tok: dict, im: Image.Image, tol=3) -> dict:
    probes = {"bg": (1, 1), "surface": (10, 10), "accent": (40, 8), "text": (40, 25)}
    out = {}
    for role, xy in probes.items():
        got = im.getpixel(xy)
        diff = max(abs(a - b) for a, b in zip(got, hex2rgb(tok[role])))
        if diff > tol:
            out[role] = {"want": tok[role], "got": rgb2hex(got)}
    return out


def resolve_tokens(tree: dict) -> dict:
    flat = {}

    def walk(node, path):
        if isinstance(node, dict) and "$value" in node:
            flat[".".join(path)] = node
        elif isinstance(node, dict):
            for k, v in node.items():
                if not k.startswith("$"):
                    walk(v, path + [k])
    walk(tree, [])

    def val(key, seen=()):
        if key in seen:
            raise ValueError(f"circular alias {key}")
        v = flat[key]["$value"]
        m = re.fullmatch(r"{([^}]+)}", str(v))
        return val(m.group(1), seen + (key,)) if m else v
    return {k: val(k) for k in flat}


def theme_maps(prim: dict, semantic: dict) -> dict:
    out = {}
    for brand, modes in semantic.items():
        for mode, roles in modes.items():
            tree = {"prim": prim, "sem": {r: {"$value": v, "$type": "color"} for r, v in roles.items()}}
            res = resolve_tokens(tree)
            out[f"{brand}.{mode}"] = {k.split(".", 1)[1]: v for k, v in res.items() if k.startswith("sem.")}
    return out


def resolve_design_file(files: set) -> str | None:
    for name in ("frame.md", "design.md", "DESIGN.md"):
        if name in files:
            return name
    return None


def px_to_cqw(px: float, width=1920) -> float:
    return round(px / width * 100, 3)


BOOK_PARTS = ["cover", "story", "logo", "colour", "type", "imagery", "motion", "voice", "applications", "contacts"]


def build_brand_book(tokens: dict, voice: list) -> str:
    if not 3 <= len(voice) <= 5:
        raise ValueError("voice needs 3-5 attributes")
    rows = []
    names = list(tokens)
    for n in names:
        L, C, H = srgb_to_oklch(tokens[n])
        rgb = hex2rgb(tokens[n])
        rows.append(f'<tr data-token="{n}"><td>{tokens[n]}</td><td>rgb({rgb[0]} {rgb[1]} {rgb[2]})</td>'
                    f"<td>oklch({L} {C} {H})</td></tr>")
    pairs = [f'<li data-pair="{a}/{b}">{contrast(tokens[a], tokens[b])}</li>' for a in names for b in names if a < b]
    secs = "".join(f'<section id="{p}"></section>' for p in BOOK_PARTS)
    return (f"<html><body>{secs}<table>{''.join(rows)}</table><ul>{''.join(pairs)}</ul>"
            f"<ol id='voice'>{''.join(f'<li>{v}</li>' for v in voice)}</ol></body></html>")


def make_font(path: Path, family: str, licence: str, url: str):
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder([".notdef", "A"])
    fb.setupCharacterMap({65: "A"})
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0)); pen.lineTo((500, 700)); pen.lineTo((1000, 0)); pen.closePath()
    g = pen.glyph()
    fb.setupGlyf({".notdef": TTGlyphPen(None).glyph(), "A": g})
    fb.setupHorizontalMetrics({".notdef": (500, 0), "A": (1000, 0)})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": family, "styleName": "Regular", "licenseDescription": licence, "licenseInfoURL": url})
    fb.setupOS2()
    fb.setupPost()
    fb.save(str(path))


def licence_gate(path: Path) -> dict:
    from fontTools.ttLib import TTFont
    name = TTFont(str(path))["name"]
    lic = (name.getDebugName(13) or "") + " " + (name.getDebugName(14) or "")
    ok = bool(re.search(r"SIL Open Font License|OFL|scripts\.sil\.org/OFL|openfontlicense", lic, re.I))
    return {"family": name.getDebugName(1), "licence": lic.strip(), "ofl": ok}


def to_hex(s: str):
    s = s.strip().lower()
    m = re.fullmatch(r"#([0-9a-f]{3}|[0-9a-f]{6})", s)
    if m:
        h = m.group(1)
        return "#" + ("".join(c * 2 for c in h) if len(h) == 3 else h)
    m = re.fullmatch(r"rgba?\(\s*(\d+)[ ,]+(\d+)[ ,]+(\d+)\s*(?:[/,]\s*[\d.]+%?)?\s*\)", s)
    if m:
        return rgb2hex([min(255, int(v)) for v in m.groups()])
    m = re.fullmatch(r"hsla?\(\s*([\d.]+)[ ,]+([\d.]+)%[ ,]+([\d.]+)%\s*(?:[/,]\s*[\d.]+%?)?\s*\)", s)
    if m:
        h, sat, l = float(m.group(1)) / 360, float(m.group(2)) / 100, float(m.group(3)) / 100
        return rgb2hex([v * 255 for v in colorsys.hls_to_rgb(h, l, sat)])
    m = re.fullmatch(r"oklch\(\s*([\d.]+)(%?)\s+([\d.]+)\s+([\d.]+)\s*\)", s)
    if m:
        L = float(m.group(1)) / (100 if m.group(2) else 1)
        return oklch_to_hex(L, float(m.group(3)), float(m.group(4)))
    return None


def radius_kind(px: float) -> str:
    return "pill" if px >= 9999 else "round" if px >= 12 else "soft" if px >= 4 else "sharp"


def shot_offsets(page_h: int, view_h=1080, overlap=0.3) -> list:
    step = int(view_h * (1 - overlap))
    offs = list(range(0, max(1, page_h - view_h) + 1, step))
    if offs[-1] + view_h < page_h:
        offs.append(page_h - view_h)
    return offs


def trace_layers(img: Image.Image, up=8, simplify=0.85, max_colours=16, merge_dist=30):
    import cv2
    big = img.resize((img.width * up, img.height * up), Image.BICUBIC)
    q = big.quantize(colors=max_colours, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    qa = np.asarray(q)
    qpal = np.array(q.getpalette()[:3 * max_colours], float).reshape(-1, 3)
    counts = np.bincount(qa.ravel(), minlength=len(qpal)).astype(float)
    # merge palette entries closer than merge_dist (heaviest absorbs), keep clusters with >= 3% of pixels (anti-alias fringes fall below)
    order = np.argsort(-counts)
    kept = []
    for i in order:
        if counts[i] == 0:
            continue
        near = [k for k in kept if np.linalg.norm(qpal[k[0]] - qpal[i]) < merge_dist]
        if near:
            near[0][1] += counts[i]
        else:
            kept.append([i, counts[i]])
    kept = [k for k, n in kept if n >= 0.03 * qa.size]
    pal_k = qpal[kept]
    rgb = np.asarray(big.convert("RGB")).astype(float)
    a = np.argmin(((rgb[:, :, None, :] - pal_k[None, None]) ** 2).sum(-1), axis=2)
    pal = pal_k.round().astype(int).ravel().tolist()
    bg = np.bincount(np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])).argmax()
    layers = []
    for idx in np.unique(a):
        if idx == bg:
            continue
        mask = (a == idx).astype(np.uint8) * 255
        area = int(mask.sum() // 255)
        if area < up * up * 4:
            continue
        cs, hier = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
        polys = []
        for i, c in enumerate(cs):
            ap = cv2.approxPolyDP(c, simplify * up, True)
            polys.append({"hole": bool(hier[0][i][3] >= 0), "pts": (ap[:, 0, :] / up).round(2).tolist()})
        ys, xs = np.nonzero(mask)
        layers.append({"color": rgb2hex(pal[idx * 3: idx * 3 + 3]), "area": area / up / up,
                       "centre": [round(xs.mean() / up, 1), round(ys.mean() / up, 1)], "polys": polys})
    layers.sort(key=lambda l: -l["area"])
    return layers


def app_icon(size: int, mark_scale=1.4) -> Image.Image:
    yy, xx = np.mgrid[0:size, 0:size] / size
    r = np.hypot(xx - 0.28, yy - 0.18) / 1.05
    stops = [(0, hex2rgb("#3a2f27")), (0.5, hex2rgb("#1d1814")), (1, hex2rgb("#110e0b"))]
    img = np.zeros((size, size, 3))
    for ch in range(3):
        img[..., ch] = np.interp(np.clip(r, 0, 1), [s for s, _ in stops], [c[ch] for _, c in stops])
    im = Image.fromarray(img.astype(np.uint8))
    d = ImageDraw.Draw(im)
    half = size * 0.2 * mark_scale / 1.4
    c = size / 2
    d.polygon([(c, c - half), (c + half, c), (c, c + half), (c - half, c)], fill=(232, 189, 118))
    return im


def sprite(names) -> str:
    syms = "".join(f'<symbol id="i-{n}" viewBox="0 0 24 24"><path d="M4 12h16" fill="none" stroke="currentColor" stroke-width="1.8"/></symbol>' for n in names)
    uses = "".join(f'<svg class="i"><use href="#i-{n}"/></svg>' for n in names)
    return f'<svg style="display:none">{syms}</svg>{uses}'


SQC_HEX = [(150, 16), (183, 35), (183, 73), (150, 92), (117, 73), (117, 35)]


def sqc_svg() -> str:
    pts = " ".join(f"{x},{y}" for x, y in SQC_HEX)
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 110">'
            '<defs><linearGradient id="ledger"><stop offset="0" stop-color="#f6c39b"/><stop offset=".5" stop-color="#f2732d"/>'
            '<stop offset="1" stop-color="#a53e07"/></linearGradient></defs>'
            '<path id="S" d="M80 30c-20-10-50 0-40 20s40 10 30 30-30 15-40 5" fill="none" stroke="url(#ledger)" stroke-width="19"/>'
            f'<polygon id="Q" points="{pts}" fill="none" stroke="url(#ledger)" stroke-width="19"/>'
            '<path id="facets" d="M150 16V54M183 73L150 54M117 73L150 54" stroke="#fff" stroke-width="5" opacity=".55"/>'
            '<path id="tick" d="M164 80 l13 13 28-33" fill="none" stroke="#a53e07" stroke-width="17"/>'
            '<rect id="diamond" x="250" y="49" width="12" height="12" transform="rotate(45 256 55)"/></svg>')


def k_favicon() -> Image.Image:
    im = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, 31, 31], radius=8, fill=hex2rgb("#2F1B68"))
    d.line([(10, 7), (10, 25)], fill="white", width=3)
    d.line([(10, 17), (20, 7)], fill="white", width=3)
    d.line([(12, 15), (21, 25)], fill="white", width=3)
    d.ellipse([22, 22, 28, 28], fill=hex2rgb("#2EA6A6"))
    return im


LUXE = cubic_bezier(.16, 1, .3, 1)


GLIDE = cubic_bezier(.65, 0, .35, 1)


SETTLE = cubic_bezier(.22, 1.2, .36, 1)


GOLD = ["#4a3110", "#8a6424", "#c9a24a", "#e8cf8a", "#fff4d6", "#c9a24a", "#4a3110"]


STOPS = [0, 16, 40, 56, 68, 86, 100]


def metal_gradient(h=101, w=4) -> Image.Image:
    col = np.zeros((h, 3))
    for ch in range(3):
        col[:, ch] = np.interp(np.linspace(0, 100, h), STOPS, [hex2rgb(c)[ch] for c in GOLD])
    return Image.fromarray(np.repeat(col[:, None, :], w, axis=1).round().astype(np.uint8))


def tagline_times(words, start=7.0, every=0.17):
    return [round(start + i * every, 2) for i in range(len(words))]


def hexagon(cx, cy, r):
    return [(cx + r * math.cos(math.radians(90 + 60 * i)), cy + r * math.sin(math.radians(90 + 60 * i))) for i in range(7)]


def partial_path(pts, frac):
    seg = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    want, out = sum(seg) * frac, [pts[0]]
    for i, s in enumerate(seg):
        if want <= 0:
            break
        t = min(1.0, want / s)
        a, b = pts[i], pts[i + 1]
        out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
        want -= s
    return out


def draw_on_frame(t, draw=1.25, fill_at=1.5, fill_dur=0.4, size=120):
    im = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(im)
    pts = hexagon(60, 60, 40)
    f = clamp01((t - fill_at) / fill_dur)
    if f > 0:
        d.polygon(pts[:-1], fill=int(round(255 * f)))
    p = clamp01(t / draw)
    if p > 0:
        d.line(partial_path(pts, p), fill=255, width=3)
    return im


def resample(pts, n):
    seg = np.array([math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)])
    cum = np.concatenate([[0], np.cumsum(seg)])
    out = []
    for s in np.linspace(0, cum[-1], n, endpoint=False):
        i = min(int(np.searchsorted(cum, s, side="right") - 1), len(seg) - 1)
        t = (s - cum[i]) / seg[i]
        out.append((pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t))
    return np.array(out)


def mg022_phase(t):
    return "prep" if t < 0.6 else "assemble" if t < 1.8 else "hold" if t <= 3.0 else "end"


def morph(a, b, p):
    return a + (b - a) * p


def unfold_frame(t, rtl=True, w=200, h=40, shift=0.4, mask=0.55):
    """Mark slides (shift), then the word reveals from the mark side through a mask with easeOutExpo."""
    im = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(im)
    s = expo_out(clamp01(t / shift))
    mark_x = (w - 30) / 2 + s * ((w - 30) / 2 if rtl else -(w - 30) / 2)
    d.rectangle([mark_x, 5, mark_x + 30, 35], fill=128)
    p = expo_out(clamp01((t - shift) / mask))
    word_l, word_r = 10, w - 40
    revealed = (word_r - word_l) * p
    if revealed > 0:
        if rtl:
            d.rectangle([word_r - revealed, 15, word_r, 25], fill=255)
        else:
            d.rectangle([word_l, 15, word_l + revealed, 25], fill=255)
    return im


def tracked_width(text, size, em_spacing, fnt=None):
    fnt = fnt or font(size)
    adv = [fnt.getlength(c) for c in text]
    return sum(adv) + em_spacing * size * (len(text) - 1)


def tracking_frame(t, text="KOSIF", size=132, dur=0.8):
    p = expo_out(clamp01(t / dur))
    sp = 0.22 + (-0.03 - 0.22) * p
    fnt = font(size)
    w = int(tracked_width(text, size, 0.22, fnt) + 40)
    im = Image.new("L", (w, size + 40), 0)
    d = ImageDraw.Draw(im)
    x = 20
    for c in text:
        d.text((x, 20), c, font=fnt, fill=int(255 * (0.4 + 0.6 * p)))
        x += fnt.getlength(c) + sp * size
    return im, sp


def burst_frame(t, n=40, dur=0.4, size=200):
    im = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(im)
    p = clamp01(t / dur)
    a = int(255 * (1 - p))
    c = size / 2
    for i in range(n):
        ang = 2 * math.pi * i / n
        r0, r1 = 20 + 60 * p, 40 + 60 * p
        d.line([(c + r0 * math.cos(ang), c + r0 * math.sin(ang)), (c + r1 * math.cos(ang), c + r1 * math.sin(ang))], fill=a, width=2)
    return im


def count_rays(im, r, thr=20):
    a = np.asarray(im)
    c = a.shape[0] / 2
    samples = [a[int(round(c + r * math.sin(th))), int(round(c + r * math.cos(th)))] > thr for th in np.linspace(0, 2 * math.pi, 3600, endpoint=False)]
    s = np.array(samples, dtype=int)
    return int(np.sum(np.diff(np.concatenate([s, s[:1]])) == 1))


def orbit_positions(n, r, cx=0, cy=0, phase=0.0):
    return [(cx + r * math.cos(phase + 2 * math.pi * i / n), cy + r * math.sin(phase + 2 * math.pi * i / n)) for i in range(n)]


def reel_position(t, stop_t, target, spin_speed=20.0, settle=0.35, overshoot=0.6):
    """Symbol index position of one reel: spins, then eases out onto target with a tiny back overshoot."""
    if t < stop_t - settle:
        return t * spin_speed
    p = clamp01((t - (stop_t - settle)) / settle)
    start = (stop_t - settle) * spin_speed
    end = target + math.ceil((start - target) / 10 + 1) * 10
    s = overshoot
    e = 1 + (s + 1) * (p - 1) ** 3 + s * (p - 1) ** 2   # back.out(s)
    return start + (end - start) * e


def progress(frame, start, dur, ease=in_out_cubic):
    return ease(clamp01((frame - start) / dur))


def end_card(t, W=270, H=480, stagger=0.15, fade_up=0.3, hold=4.0, fade_out=0.55):
    """Quarter-scale 1080x1920 end card: icon 100 / name 60 / tagline 30 px (x0.25), one URL pill."""
    k = 0.25
    im = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(im)
    out = clamp01((t - (3 * stagger + fade_up + hold)) / fade_out)
    items = [("icon", 100), ("name", 60), ("tag", 30), ("pill", 50)]
    y = 140
    for i, (_, size) in enumerate(items):
        p = clamp01((t - i * stagger) / fade_up)
        a = int(255 * p * (1 - out))
        hpx = size * k
        wpx = hpx if i == 0 else 160
        d.rectangle([W / 2 - wpx / 2, y + 12 * (1 - p), W / 2 + wpx / 2 - 1, y + 12 * (1 - p) + hpx - 1], fill=a)
        y += hpx + 20
    return im


def ripple_radius(t, dur=0.4, rmax=60):
    return rmax * out_quad(clamp01(t / dur))


def cta_scale(t, click=0.55, press=0.12, pulses=(1.2, 1.8)):
    s = 0.96 if click <= t < click + press else 1.0
    for pt in pulses:
        if pt <= t < pt + 0.4:
            s *= 1 + 0.06 * math.sin(math.pi * (t - pt) / 0.4)
    return s


def x_height_px(size):
    fnt = font(size)
    b = fnt.getbbox("x", anchor="ls")
    return -b[1]


def dot_scale(t, dur=0.22):
    p = clamp01(t / dur)
    return 1.2 * (p / 0.6) if p < 0.6 else 1.2 - 0.2 * (p - 0.6) / 0.4


def _raqm():
    from PIL import features
    return features.check("raqm")


def typed(text, t, ms=40):
    return text[:int(t * 1000 // ms)]


def cursor_on(t, blink=0.5):
    return int(t // blink) % 2 == 0


def db_fade(n, sr, db_end=-60.0):
    db = np.linspace(0, db_end, n)
    return 10 ** (db / 20)


def reveal_units(text, t, arabic, char_ms=40, word_ms=120):
    if arabic:
        words = text.split()
        return " ".join(words[:int(t * 1000 // word_ms)])
    return text[:int(t * 1000 // char_ms)]


def pendulum(t, theta0=0.5, period=0.6, settle=1.5):
    lam = math.log(50) / settle
    return theta0 * math.exp(-lam * t) * math.cos(2 * math.pi * t / period)


def fit_block(anim: float, slot: float) -> dict:
    if slot < anim:
        raise ValueError("slot shorter than the animation; never time-compress")
    return {"anim": anim, "hold": round(slot - anim, 3), "speed": 1.0}


def testimonial_ok(t: dict) -> bool:
    return bool(t.get("quote") and t.get("source") and t.get("permission") is True)


def marquee(t, row, speed=20):
    return (speed if row % 2 == 0 else -speed) * t


def edge_alpha(x, w, fade=0.1):
    return clamp01(min(x, w - x) / (fade * w))


def chrome_frame(t, centre_val, W=480, H=270, inset=0.04):
    im = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(im)
    x0, y0 = W * inset, H * inset
    d.rectangle([x0, y0, x0 + 40, y0 + 6], fill=200)
    if t >= 0.4:
        d.rectangle([W - x0 - 40, H - y0 - 6, W - x0 - 1, H - y0 - 1], fill=220)
    d.rectangle([W / 2 - 60, H / 2 - 30, W / 2 + 60, H / 2 + 30], fill=centre_val)
    return im


def word_windows(n, at, dur=0.6, stagger=0.06):
    return [(round(at + i * stagger, 3), round(at + i * stagger + dur, 3)) for i in range(n)]


def flood_frame(t, W=96, H=54, start=3.0, dur=1.0, colour=(201, 162, 74)):
    im = Image.new("RGB", (W, H), (10, 10, 12))
    r = math.hypot(W, H) / 2 * in_out_cubic(clamp01((t - start) / dur)) + (1 if t >= start + dur else 0)
    ImageDraw.Draw(im).ellipse([W / 2 - r, H / 2 - r, W / 2 + r, H / 2 + r], fill=colour)
    return im


def bar_progress(t, D=5.0, last=2.0):
    return clamp01((t - (D - last)) / last)


def grid_cells(W, H):
    ar = W / H
    if ar < 1:  # 9:16 stacked
        return [(0, i * H // 4, W, H // 4) for i in range(4)]
    return [(x * W // 2, y * H // 2, W // 2, H // 2) for y in range(2) for x in range(2)]


def clip_frames(seed, n=30, blank_first=False):
    rng = np.random.default_rng(seed)
    fr = [rng.integers(40, 220, (9, 16), dtype=np.uint8) for _ in range(n)]
    if blank_first:
        fr[0] = np.zeros((9, 16), np.uint8)
    return fr


def blank_ends(frames, thr=2.0):
    return [i for i in (0, len(frames) - 1) if frames[i].mean() < thr]


def mark_svg(params: tuple) -> str:
    sides, rot, ring, dots, stroke, fill, inset, gap = params
    pts = " ".join(f"{50 + 40 * math.cos(math.radians(rot * 15 + 360 * i / (sides + 3))):.2f},"
                   f"{50 + 40 * math.sin(math.radians(rot * 15 + 360 * i / (sides + 3))):.2f}" for i in range(sides + 3))
    rings = "".join(f'<circle cx="50" cy="50" r="{10 + 5 * k + gap}" fill="none" stroke="#000" stroke-width="{1 + stroke}"/>' for k in range(ring))
    ds = "".join(f'<circle cx="{50 + (20 + inset * 3) * math.cos(2 * math.pi * k / 6):.2f}" cy="{50 + (20 + inset * 3) * math.sin(2 * math.pi * k / 6):.2f}" r="2"/>' for k in range(dots))
    return f'<svg viewBox="0 0 100 100"><polygon points="{pts}" fill="#{fill * 40:02x}{fill * 40:02x}{fill * 40:02x}"/>{rings}{ds}</svg>'


def brutal_card(W=80, H=60):
    im = Image.new("RGB", (W + 10, H + 10), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.rectangle([6, 6, W + 5, H + 5], fill=hex2rgb("#111111"))
    d.rectangle([0, 0, W - 1, H - 1], fill=(0, 0, 0))
    d.rectangle([3, 3, W - 4, H - 4], fill=hex2rgb("#f47fe0"))
    return im


def star(n=24, r0=40, r1=34, rot=0.0):
    return [((r0 if i % 2 == 0 else r1) * math.cos(math.radians(rot) + math.pi * i / n) + 50,
             (r0 if i % 2 == 0 else r1) * math.sin(math.radians(rot) + math.pi * i / n) + 50) for i in range(2 * n)]


def glow(W=200, H=100, blur_css=30, alpha=0.5):
    base = Image.new("L", (W, H), 0)
    ImageDraw.Draw(base).rectangle([80, 40, 120, 60], fill=255)
    g = base.filter(ImageFilter.GaussianBlur(blur_css / 2))
    g = Image.fromarray((np.asarray(g) * alpha).astype(np.uint8))
    return Image.fromarray(np.maximum(np.asarray(g), np.asarray(base)))


def colour_units(text):
    """Per-letter colour for Latin, per-word for Arabic."""
    return text.split() if ARABIC_RE.search(text) else list(text.replace(" ", ""))


def poster(W=360, H=640):
    im = Image.new("RGB", (W, H), hex2rgb("#2a1010"))
    d = ImageDraw.Draw(im)
    d.rectangle([0, H - 90, W, H - 40], fill=hex2rgb("#c91a1f"))
    d.ellipse([W - 110, 20, W - 20, 110], fill=hex2rgb("#a8c13a"))
    d.ellipse([W - 100, 30, W - 30, 100], fill=hex2rgb("#ffffff"))
    d.ellipse([W - 90, 40, W - 40, 90], fill=hex2rgb("#e3161d"))
    mask = Image.new("L", (W, 140), 0)
    md = ImageDraw.Draw(mask)
    kw = {"direction": "rtl"} if _raqm() else {}
    md.text((W - 20, 70), "خروف كامل", font=font(72, arabic=True), fill=255, anchor="rm", **kw)
    grad = np.linspace(np.array(hex2rgb("#f6e3b6")), np.array(hex2rgb("#c49c5c")), 140)
    gimg = Image.fromarray(np.repeat(grad[:, None, :], W, axis=1).round().astype(np.uint8))
    im.paste(gimg, (0, 140), mask)
    return im, mask


def title_card(t, W=192, H=108):
    yy, xx = np.mgrid[0:H, 0:W].astype(float)
    bg = np.array(hex2rgb("#11171b"), float)
    acc = np.array(hex2rgb("#d9530e"), float)
    d = np.hypot(xx - 0.28 * W, yy - 0.25 * H) / (0.8 * W)
    gl = np.clip(1 - d, 0, 1)[..., None] * 0.6
    img = bg * (1 - gl) + acc * gl
    unit = W / 12
    img[:, (np.arange(W) % round(unit)) == 0] += 6
    ang = 0.1 * t
    for k in range(3):
        a = ang + k * 2.1
        cx, cy = W / 2 + 0.2 * W * math.cos(a), H / 2 + 0.2 * H * math.sin(a)
        m = np.abs(np.hypot((xx - cx) / 30, (yy - cy) / 12) - 1) < 0.04
        img[m] = acc
    return np.clip(img, 0, 255).astype(np.uint8)


def stamp_scale(t, dur=0.15):
    return 1.2 - 0.2 * out_quad(clamp01(t / dur))


def multiply(base, top):
    return tuple(round(b * c / 255) for b, c in zip(base, top))


def fog_mask(t, W=64, H=36, seed=7, start=1.0, end=3.0):
    """Turbulence-style value noise thresholded by progress: revealed where noise < p."""
    rng = np.random.default_rng(seed)
    coarse = rng.random((5, 9))
    noise = np.asarray(Image.fromarray((coarse * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)) / 255
    noise = (noise - noise.min()) / (noise.max() - noise.min())
    p = clamp01((t - start) / (end - start))
    return (noise < p) if p < 1 else np.ones_like(noise, bool)


def negative_space(W=60, H=60):
    bg = Image.new("L", (W, H), 30)
    shape = Image.new("L", (W, H), 0)
    ImageDraw.Draw(shape).rectangle([5, 5, 54, 54], fill=255)
    hole = Image.new("L", (W, H), 0)
    ImageDraw.Draw(hole).ellipse([20, 20, 39, 39], fill=255)
    m = np.asarray(shape) & ~np.asarray(hole)
    out = np.where(m > 0, 230, np.asarray(bg))
    return out.astype(np.uint8)
