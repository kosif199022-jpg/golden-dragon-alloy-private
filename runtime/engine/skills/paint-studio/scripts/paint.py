#!/usr/bin/env python
"""paint-studio: a scriptable paint engine with the same feature set as Windows 11 Paint.

Everything is plain Pillow/NumPy/OpenCV code written for this skill (no Microsoft code or assets).

Commands
  new      OUT --size 1152x648 [--bg white|transparent|#RRGGBB]
  info     IN
  draw     IN OUT (--ops ops.json | --op '{"op":...}' ...)   IN/OUT may be images or .dpaint projects
  export   IN.dpaint OUT.png|jpg|webp|...                    flatten a layered project
  preview  IN OUT [--zoom 2] [--grid 32] [--rulers] [--box x0,y0,x1,y1]
  pick     IN X Y                                             color picker (prints hex)
  ops                                                         list every op and its parameters
  gui      [IN]                                               open in the real Paint app
  print    IN                                                 send to default printer (ask user first)
  wallpaper IN [--style fill|fit|center|tile|stretch|span]    set desktop wallpaper (ask user first)
"""
import argparse, io, json, math, os, random, subprocess, sys, zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:
    pass

SS = 4  # supersampling for anti-aliased masks

# ───────────────────────────── colors ─────────────────────────────
PALETTE = {  # Paint-like default palette names
    "black": "#000000", "gray": "#7f7f7f", "dark_red": "#880015", "red": "#ed1c24", "orange": "#ff7f27",
    "yellow": "#fff200", "green": "#22b14c", "turquoise": "#00a2e8", "indigo": "#3f48cc", "purple": "#a349a4",
    "white": "#ffffff", "light_gray": "#c3c3c3", "brown": "#b97a57", "rose": "#ffaec9", "gold": "#ffc90e",
    "light_yellow": "#efe4b0", "lime": "#b5e61d", "light_turquoise": "#99d9ea", "blue_gray": "#7092be",
    "lavender": "#c8bfe7", "blue": "#0050ef", "pink": "#ff4fa0", "transparent": "#00000000",
}


def color(c, default=(0, 0, 0, 255)):
    if c is None:
        return default
    if isinstance(c, (list, tuple)):
        c = tuple(int(v) for v in c)
        return c if len(c) == 4 else c + (255,)
    c = PALETTE.get(str(c).lower(), str(c))
    if c.startswith("#"):
        h = c[1:]
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        v = tuple(int(h[i:i + 2], 16) for i in range(0, len(h), 2))
        return v if len(v) == 4 else v + (255,)
    from PIL import ImageColor
    return ImageColor.getcolor(c, "RGBA")


def hexc(rgba):
    return "#%02x%02x%02x" % rgba[:3] + ("" if len(rgba) < 4 or rgba[3] == 255 else "%02x" % rgba[3])


# ───────────────────────────── documents & layers ─────────────────────────────
class Doc:
    """A layered document. Plain images load as one layer; .dpaint projects keep every layer."""

    def __init__(self, w, h, bg="white"):
        self.w, self.h = w, h
        self.background = color(bg) if bg not in (None, "transparent") else (255, 255, 255, 255)
        self.bg_visible = bg not in (None, "transparent")
        self.layers = []  # dicts: name, image(RGBA), visible, opacity, blend
        self.current = 0
        self.dpi = (96, 96)

    # layers
    def add_layer(self, name=None, image=None, index=None):
        img = image if image is not None else Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        lay = {"name": name or f"Layer {len(self.layers) + 1}", "image": img.convert("RGBA"),
               "visible": True, "opacity": 1.0, "blend": "normal"}
        index = len(self.layers) if index is None else index
        self.layers.insert(index, lay)
        self.current = index
        return lay

    @property
    def layer(self):
        return self.layers[self.current]

    @property
    def img(self):
        return self.layer["image"]

    @img.setter
    def img(self, v):
        self.layer["image"] = v.convert("RGBA")

    def flatten(self, with_bg=True):
        base = Image.new("RGBA", (self.w, self.h), self.background if (with_bg and self.bg_visible) else (0, 0, 0, 0))
        for lay in self.layers:
            if not lay["visible"]:
                continue
            im = lay["image"]
            if lay["opacity"] < 1:
                a = im.getchannel("A").point(lambda v: int(v * lay["opacity"]))
                im = im.copy(); im.putalpha(a)
            base = blend(base, im, lay.get("blend", "normal"))
        return base

    def resize_all(self, fn):
        for lay in self.layers:
            lay["image"] = fn(lay["image"])
        self.w, self.h = self.layers[0]["image"].size

    # io
    @classmethod
    def load(cls, path):
        path = Path(path)
        if path.suffix.lower() == ".dpaint":
            with zipfile.ZipFile(path) as z:
                meta = json.loads(z.read("project.json"))
                d = cls(meta["width"], meta["height"])
                d.background = tuple(meta["background"]["color"])
                d.bg_visible = meta["background"]["visible"]
                for i, lm in enumerate(meta["layers"]):
                    im = Image.open(io.BytesIO(z.read(f"layers/{i:03d}.png"))).convert("RGBA")
                    lay = d.add_layer(lm["name"], im)
                    lay.update(visible=lm["visible"], opacity=lm.get("opacity", 1.0), blend=lm.get("blend", "normal"))
                d.current = meta.get("current", len(d.layers) - 1)
                d.dpi = tuple(meta.get("dpi", (96, 96)))
            return d
        im = Image.open(path)
        im.load()
        dpi = im.info.get("dpi", (96, 96))
        im = ImageOps.exif_transpose(im).convert("RGBA")
        has_alpha = im.getchannel("A").getextrema()[0] < 255
        d = cls(im.width, im.height, "transparent" if has_alpha else "white")
        d.add_layer("Background image", im)
        d.dpi = tuple(int(v) for v in dpi)
        return d

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() == ".dpaint":
            meta = {"format": "paint-studio/1", "width": self.w, "height": self.h, "current": self.current,
                    "dpi": list(self.dpi),
                    "background": {"color": list(self.background), "visible": self.bg_visible},
                    "layers": [{k: v for k, v in l.items() if k != "image"} for l in self.layers]}
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr("project.json", json.dumps(meta, indent=1))
                for i, l in enumerate(self.layers):
                    b = io.BytesIO(); l["image"].save(b, "PNG"); z.writestr(f"layers/{i:03d}.png", b.getvalue())
                b = io.BytesIO(); self.flatten().save(b, "PNG"); z.writestr("preview.png", b.getvalue())
            return path
        save_image(self.flatten(), path, dpi=self.dpi)
        return path


def save_image(im, path, dpi=(96, 96)):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ext = path.suffix.lower()
    no_alpha = ext in (".jpg", ".jpeg", ".jpe", ".jfif", ".bmp", ".dib")
    if no_alpha:
        bg = Image.new("RGB", im.size, "white"); bg.paste(im, mask=im.getchannel("A")); im = bg
    kw = {"dpi": dpi}
    if ext in (".jpg", ".jpeg", ".jpe", ".jfif"):
        kw.update(quality=95, subsampling=0)
    elif ext == ".webp":
        kw.update(quality=95, method=6)
    elif ext == ".avif":
        kw.update(quality=90)
    elif ext == ".ico":
        kw = {"sizes": [(s, s) for s in (16, 24, 32, 48, 64, 128, 256) if s <= max(im.size)]}
    elif ext == ".gif":
        kw = {}
    im.save(path, **kw)


def blend(base, top, mode="normal"):
    if mode == "normal":
        return Image.alpha_composite(base, top)
    b = np.asarray(base, dtype=np.float32) / 255
    t = np.asarray(top, dtype=np.float32) / 255
    bc, ba, tc, ta = b[..., :3], b[..., 3:4], t[..., :3], t[..., 3:4]
    if mode == "multiply":
        mix = bc * tc
    elif mode == "screen":
        mix = 1 - (1 - bc) * (1 - tc)
    elif mode == "overlay":
        mix = np.where(bc < .5, 2 * bc * tc, 1 - 2 * (1 - bc) * (1 - tc))
    elif mode == "darken":
        mix = np.minimum(bc, tc)
    elif mode == "lighten":
        mix = np.maximum(bc, tc)
    else:
        raise ValueError(f"unknown blend mode {mode}")
    mix = (1 - ba) * tc + ba * mix          # where the base is empty, the top keeps its own colour
    oa = ta + ba * (1 - ta)
    out = np.empty_like(b)
    out[..., :3] = (bc * ba * (1 - ta) + mix * ta) / np.maximum(oa, 1e-6)
    out[..., 3:4] = oa
    return Image.fromarray((np.clip(out, 0, 1) * 255 + .5).astype(np.uint8), "RGBA")


# ───────────────────────────── geometry helpers ─────────────────────────────
def resample(points, step):
    pts = [tuple(map(float, p)) for p in points]
    if len(pts) == 1:
        return pts
    out = [pts[0]]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        d = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(d / max(step, .5)))
        out += [(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n) for i in range(1, n + 1)]
    return out


def bezier(p0, p3, c1=None, c2=None, n=200):
    c1 = c1 or [(p0[0] + p3[0]) / 2, (p0[1] + p3[1]) / 2]
    c2 = c2 or c1
    pts = []
    for i in range(n + 1):
        t = i / n
        x = (1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * c1[0] + 3 * (1 - t) * t ** 2 * c2[0] + t ** 3 * p3[0]
        y = (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * c1[1] + 3 * (1 - t) * t ** 2 * c2[1] + t ** 3 * p3[1]
        pts.append((x, y))
    return pts


def ss_mask(size, painter):
    """Draw onto a supersampled L mask then downscale for anti-aliasing."""
    w, h = size
    m = Image.new("L", (w * SS, h * SS), 0)
    painter(ImageDraw.Draw(m), SS)
    return m.resize((w, h), Image.LANCZOS)


def composite_color(img, mask, rgba, opacity=1.0, mode="normal"):
    layer = Image.new("RGBA", img.size, rgba[:3] + (0,))
    a = np.asarray(mask, dtype=np.float32) * (rgba[3] / 255) * opacity
    layer.putalpha(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)))
    return blend(img, layer, mode)


def noise(size, scale=1.0, seed=0):
    rng = np.random.default_rng(seed)
    w, h = size
    sw, sh = max(1, int(w / scale)), max(1, int(h / scale))
    n = rng.random((sh, sw)).astype(np.float32)
    return np.asarray(Image.fromarray((n * 255).astype(np.uint8)).resize((w, h), Image.BILINEAR), np.float32) / 255


# ───────────────────────────── brushes ─────────────────────────────
BRUSHES = ["pencil", "brush", "calligraphy_brush", "calligraphy_pen", "airbrush", "oil", "crayon",
           "marker", "natural_pencil", "watercolor", "eraser"]


def stroke_mask(size, points, brush, width, seed=0):
    w, h = size
    pts = [tuple(p) for p in points]
    if brush == "pencil":  # hard 1-px-style aliased line
        m = Image.new("L", size, 0)
        d = ImageDraw.Draw(m)
        if len(pts) == 1:
            d.point(pts[0], 255)
        d.line(pts, fill=255, width=max(1, int(width)), joint="curve")
        return np.asarray(m, np.float32) / 255

    def round_line(d, s, wd=width, pp=pts):
        sp = [(x * s, y * s) for x, y in pp]
        r = wd * s / 2
        if len(sp) > 1:
            d.line(sp, fill=255, width=max(1, int(wd * s)), joint="curve")
        for x, y in (sp[0], sp[-1]) if len(sp) > 1 else sp:
            d.ellipse([x - r, y - r, x + r, y + r], fill=255)

    if brush in ("brush", "marker", "crayon", "watercolor", "oil", "eraser", "natural_pencil"):
        wd = width if brush != "natural_pencil" else max(1, width * .6)
        if brush == "marker":  # chisel tip: squared ends
            m = ss_mask(size, lambda d, s: d.line([(x * s, y * s) for x, y in pts], fill=255,
                                                   width=int(wd * s), joint="curve"))
        else:
            m = ss_mask(size, lambda d, s: round_line(d, s, wd))
        m = np.asarray(m, np.float32) / 255
        if brush == "crayon":
            g = noise(size, 1.0, seed)
            m = m * (g > 0.42) * (0.7 + 0.3 * noise(size, 3, seed + 1))
        elif brush == "natural_pencil":
            g = noise(size, 1.0, seed)
            m = m * (0.35 + 0.65 * (g > 0.3)) * 0.85
        elif brush == "watercolor":
            blur = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(
                ImageFilter.GaussianBlur(max(1, width / 5))), np.float32) / 255
            edge = np.clip(m - np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(
                ImageFilter.GaussianBlur(max(1, width / 3))), np.float32) / 255, 0, 1)
            paper = noise(size, 2.5, seed)
            m = np.clip(blur * (0.38 + 0.18 * paper) + edge * 0.9, 0, 1)
        elif brush == "oil":
            # bristle streaks across the stroke direction
            streak = np.zeros((h, w), np.float32)
            dense = resample(pts, 1)
            rng = random.Random(seed)
            if len(dense) > 1:
                bristles = [(rng.uniform(-.5, .5), rng.uniform(.55, 1.0)) for _ in range(max(6, int(width)))]
                img = Image.new("L", (w * 2, h * 2), 0)
                dr = ImageDraw.Draw(img)
                for off, val in bristles:
                    path = []
                    for i in range(len(dense)):
                        x0, y0 = dense[max(0, i - 1)]; x1, y1 = dense[min(len(dense) - 1, i + 1)]
                        dx, dy = x1 - x0, y1 - y0; L = math.hypot(dx, dy) or 1
                        nx, ny = -dy / L, dx / L
                        x, y = dense[i]
                        path.append(((x + nx * off * width) * 2, (y + ny * off * width) * 2))
                    dr.line(path, fill=int(255 * val), width=max(1, int(width / 6 * 2)))
                streak = np.asarray(img.resize((w, h), Image.LANCZOS), np.float32) / 255
            m = np.clip(m * (0.55 + 0.45 * streak / max(streak.max(), 1e-3)), 0, 1)
        return m

    if brush in ("calligraphy_brush", "calligraphy_pen"):
        ang = math.radians(45)
        nib_w = width if brush == "calligraphy_brush" else width * 1.1
        nib_h = width * (0.30 if brush == "calligraphy_brush" else 0.08)
        dense = resample(pts, max(.5, nib_h / 2))

        def paint(d, s):
            ca, sa = math.cos(ang), math.sin(ang)
            for x, y in dense:
                corners = []
                for px, py in ((-nib_w / 2, -nib_h / 2), (nib_w / 2, -nib_h / 2), (nib_w / 2, nib_h / 2), (-nib_w / 2, nib_h / 2)):
                    corners.append(((x + px * ca - py * sa) * s, (y + px * sa + py * ca) * s))
                d.polygon(corners, fill=255)
        m = np.asarray(ss_mask(size, paint), np.float32) / 255
        if brush == "calligraphy_brush":
            m = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(.6)), np.float32) / 255
        return m

    if brush == "airbrush":
        rng = np.random.default_rng(seed)
        m = np.zeros((h, w), np.float32)
        dense = resample(pts, max(1, width / 6))
        r = width / 2
        for x, y in dense:
            n = int(max(8, width * 1.5))
            ang = rng.uniform(0, 2 * math.pi, n); rad = r * np.sqrt(rng.uniform(0, 1, n))
            xs = np.clip((x + rad * np.cos(ang)).astype(int), 0, w - 1)
            ys = np.clip((y + rad * np.sin(ang)).astype(int), 0, h - 1)
            m[ys, xs] = 1
        return m
    raise ValueError(f"unknown brush {brush}; choose from {BRUSHES}")


def do_stroke(doc, o):
    brush = o.get("brush", o["op"])
    width = float(o.get("size", 3 if brush == "pencil" else 10))
    pts = o["points"]
    if o.get("smooth") and len(pts) > 2:
        pts = chaikin(pts, int(o["smooth"]))
    m = stroke_mask((doc.w, doc.h), pts, brush, width, seed=int(o.get("seed", len(pts))))
    if brush == "eraser":
        im = doc.img
        a = np.asarray(im.getchannel("A"), np.float32) * (1 - m)
        if doc.current == 0 and doc.bg_visible and o.get("to", "transparent") == "background":
            doc.img = composite_color(im, Image.fromarray((m * 255).astype(np.uint8)), doc.background); return
        im = im.copy(); im.putalpha(Image.fromarray(a.astype(np.uint8))); doc.img = im; return
    rgba = color(o.get("color", "black"))
    op_default = {"marker": .65, "watercolor": 1.0, "natural_pencil": .9}.get(brush, 1.0)
    mode = o.get("blend", "multiply" if brush == "marker" else "normal")
    doc.img = composite_color(doc.img, Image.fromarray((np.clip(m, 0, 1) * 255).astype(np.uint8)), rgba,
                              float(o.get("opacity", op_default)), mode)


def chaikin(pts, it=2):
    pts = [tuple(p) for p in pts]
    for _ in range(it):
        new = [pts[0]]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            new += [(.75 * x0 + .25 * x1, .75 * y0 + .25 * y1), (.25 * x0 + .75 * x1, .25 * y0 + .75 * y1)]
        new.append(pts[-1]); pts = new
    return pts


# ───────────────────────────── shapes ─────────────────────────────
SHAPES = ["line", "curve", "ellipse", "rectangle", "rounded_rectangle", "polygon", "triangle", "right_triangle",
          "diamond", "pentagon", "hexagon", "arrow_right", "arrow_left", "arrow_up", "arrow_down",
          "star4", "star5", "star6", "callout_rect", "callout_oval", "callout_cloud", "heart", "lightning"]


def regular(n, rot=-90):
    return [(.5 + .5 * math.cos(math.radians(rot + i * 360 / n)), .5 + .5 * math.sin(math.radians(rot + i * 360 / n))) for i in range(n)]


def star(n, inner=.42):
    pts = []
    for i in range(n * 2):
        r = .5 if i % 2 == 0 else .5 * inner
        a = math.radians(-90 + i * 180 / n)
        pts.append((.5 + r * math.cos(a), .5 + r * math.sin(a)))
    return pts


def ellipse_pts(cx=.5, cy=.5, rx=.5, ry=.5, n=180, a0=0, a1=360):
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def rounded_rect_pts(w, h, r):
    r = min(r, .5 * min(w, h)) / max(w, h, 1e-6)
    rx, ry = r * max(w, h) / w, r * max(w, h) / h
    pts = []
    for cx, cy, a0 in ((1 - rx, ry, -90), (1 - rx, 1 - ry, 0), (rx, 1 - ry, 90), (rx, ry, 180)):
        pts += ellipse_pts(cx, cy, rx, ry, 16, a0, a0 + 90)
    return pts


def unit_shape(kind, bw, bh, o):
    if kind == "rectangle": return [(0, 0), (1, 0), (1, 1), (0, 1)]
    if kind == "rounded_rectangle": return rounded_rect_pts(bw, bh, o.get("radius", min(bw, bh) * .18))
    if kind == "ellipse": return ellipse_pts()[:-1]
    if kind == "triangle": return [(.5, 0), (1, 1), (0, 1)]
    if kind == "right_triangle": return [(0, 0), (1, 1), (0, 1)]
    if kind == "diamond": return [(.5, 0), (1, .5), (.5, 1), (0, .5)]
    if kind == "pentagon": return regular(5)
    if kind == "hexagon": return regular(6, 0)
    if kind == "star4": return star(4, .4)
    if kind == "star5": return star(5, .4)
    if kind == "star6": return star(6, .55)
    if kind.startswith("arrow"):
        p = [(0, .3), (.6, .3), (.6, 0), (1, .5), (.6, 1), (.6, .7), (0, .7)]
        tr = {"arrow_right": lambda x, y: (x, y), "arrow_left": lambda x, y: (1 - x, y),
              "arrow_down": lambda x, y: (y, x), "arrow_up": lambda x, y: (y, 1 - x)}[kind]
        return [tr(x, y) for x, y in p]
    if kind == "heart":
        pts = []
        for i in range(200):
            t = 2 * math.pi * i / 200
            x = 16 * math.sin(t) ** 3
            y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
            pts.append((.5 + x / 34, .45 - y / 32))
        return pts
    if kind == "lightning":
        return [(.38, 0), (.62, 0), (.5, .36), (.74, .36), (.3, 1), (.42, .56), (.2, .56)]
    if kind == "callout_rect":
        return [(0, 0), (1, 0), (1, .75), (.45, .75), (.2, 1), (.25, .75), (0, .75)]
    if kind == "callout_oval":
        e = ellipse_pts(.5, .38, .5, .38, 120, 110, 110 + 330)
        return e + [(.22, 1)]
    if kind == "callout_cloud":
        pts = []
        bumps = [(.25, .22, .2), (.5, .14, .22), (.75, .22, .2), (.85, .45, .16), (.7, .62, .18),
                 (.45, .66, .18), (.2, .6, .17), (.12, .4, .15)]
        poly = []
        for cx, cy, r in bumps:
            poly.append((cx, cy, r))
        for i, (cx, cy, r) in enumerate(poly):
            a_c = math.degrees(math.atan2(cy - .42, cx - .5))
            pts += ellipse_pts(cx, cy, r, r * .9, 20, a_c - 80, a_c + 80)
        return pts  # tail drawn as separate bubbles
    raise ValueError(f"unknown shape {kind}; choose from {SHAPES}")


def do_shape(doc, o):
    kind = o.get("shape", o["op"])
    outline = o.get("outline", "black")
    fill = o.get("fill")
    sw = float(o.get("size", 3))
    style = o.get("outline_style", "solid")  # solid | crayon | marker | oil | natural_pencil | watercolor
    if kind in ("line", "curve"):
        if kind == "line":
            pts = [tuple(o["start"]), tuple(o["end"])]
        else:
            pts = bezier(o["start"], o["end"], o.get("control1"), o.get("control2"))
        brush = "brush" if style == "solid" else style
        do_stroke(doc, {"op": "stroke", "brush": brush, "points": pts, "size": sw,
                        "color": outline, "opacity": o.get("opacity", 1.0)})
        if o.get("arrow_head"):
            (x0, y0), (x1, y1) = pts[-2], pts[-1]
            a = math.atan2(y1 - y0, x1 - x0); L = sw * 4
            head = [(x1, y1), (x1 - L * math.cos(a - .45), y1 - L * math.sin(a - .45)),
                    (x1 - L * math.cos(a + .45), y1 - L * math.sin(a + .45))]
            m = ss_mask((doc.w, doc.h), lambda d, s: d.polygon([(x * s, y * s) for x, y in head], fill=255))
            doc.img = composite_color(doc.img, m, color(outline))
        return
    if kind == "polygon":
        pts = [tuple(map(float, p)) for p in o["points"]]
    else:
        x0, y0, x1, y1 = map(float, o["box"])
        bw, bh = x1 - x0, y1 - y0
        pts = [(x0 + u * bw, y0 + v * bh) for u, v in unit_shape(kind, bw, bh, o)]
    rot = float(o.get("rotate", 0))
    if rot:
        cx = sum(p[0] for p in pts) / len(pts); cy = sum(p[1] for p in pts) / len(pts)
        ca, sa = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        pts = [(cx + (x - cx) * ca - (y - cy) * sa, cy + (x - cx) * sa + (y - cy) * ca) for x, y in pts]
    opacity = float(o.get("opacity", 1.0))
    if fill and fill != "none":
        m = ss_mask((doc.w, doc.h), lambda d, s: d.polygon([(x * s, y * s) for x, y in pts], fill=255))
        doc.img = composite_color(doc.img, m, color(fill), opacity)
    if kind == "callout_cloud":  # little tail bubbles
        x0, y0, x1, y1 = map(float, o["box"]); bw, bh = x1 - x0, y1 - y0
        for (u, v, r) in ((.25, .82, .06), (.15, .93, .035)):
            cx, cy = x0 + u * bw, y0 + v * bh; rr = r * min(bw, bh)
            do_shape(doc, {"op": "ellipse", "box": [cx - rr, cy - rr, cx + rr, cy + rr], "fill": fill,
                           "outline": outline, "size": sw, "outline_style": style})
    if outline and outline != "none":
        closed = pts + [pts[0], pts[1]]
        if style == "solid":
            m = ss_mask((doc.w, doc.h), lambda d, s: d.line([(x * s, y * s) for x, y in closed], fill=255,
                                                             width=max(1, int(sw * s)), joint="curve"))
            doc.img = composite_color(doc.img, m, color(outline), opacity)
        else:
            do_stroke(doc, {"op": "stroke", "brush": style, "points": closed, "size": sw, "color": outline,
                            "opacity": opacity})


# ───────────────────────────── fill, text, selection, image ops ─────────────────────────────
def do_fill(doc, o):
    im = doc.flatten() if o.get("sample", "layer") == "all" else doc.img
    x, y = int(o["x"]), int(o["y"])
    tol = float(o.get("tolerance", 32))
    arr = np.asarray(im, np.int16)
    seed = arr[y, x]
    diff = np.abs(arr - seed).max(axis=2) <= tol
    import cv2
    lab = cv2.connectedComponents(diff.astype(np.uint8), connectivity=4)[1]
    region = (lab == lab[y, x]) & diff
    # grow by 1px to hide anti-aliased seams (like Paint does)
    region = cv2.dilate(region.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0 if o.get("grow", True) else region
    m = Image.fromarray((region * 255).astype(np.uint8))
    doc.img = composite_color(doc.img, m, color(o.get("color", "black")), float(o.get("opacity", 1.0)))


FONT_CACHE = {}


def find_font(family="Arial", bold=False, italic=False):
    key = (family.lower(), bold, italic)
    if key in FONT_CACHE:
        return FONT_CACHE[key]
    if os.path.isfile(family):
        FONT_CACHE[key] = family; return family
    want = family.lower()
    style = ("bold italic" if bold and italic else "bold" if bold else "italic" if italic else "")
    cands = []
    try:
        import winreg
        for root, sub in ((winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"),
                          (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts")):
            try:
                k = winreg.OpenKey(root, sub)
            except OSError:
                continue
            i = 0
            while True:
                try:
                    name, file, _ = winreg.EnumValue(k, i); i += 1
                except OSError:
                    break
                n = name.lower().replace("(truetype)", "").replace("(opentype)", "").strip()
                if n.startswith(want):
                    p = file if os.path.isabs(file) else os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", file)
                    rest = n[len(want):].strip()
                    cands.append((rest, p))
    except ImportError:
        pass
    pick = None
    for rest, p in cands:
        if rest == style:
            pick = p; break
    if not pick:
        for rest, p in cands:
            if (("bold" in rest) == bold) and (("italic" in rest) == italic):
                pick = p; break
    if not pick and cands:
        pick = cands[0][1]
    FONT_CACHE[key] = pick or "arial.ttf"
    return FONT_CACHE[key]


def do_text(doc, o):
    font_path = find_font(o.get("font", "Arial"), o.get("bold", False), o.get("italic", False))
    size = int(o.get("size", 32))
    font = ImageFont.truetype(font_path, size)
    text = str(o["text"])
    x, y = float(o["x"]), float(o["y"])
    max_w = o.get("width")
    rtl = any("\u0590" <= ch <= "\u08ff" for ch in text)
    if max_w:  # word wrap
        lines, cur = [], ""
        for para in text.split("\n"):
            cur = ""
            for wd in para.split(" "):
                t = (cur + " " + wd).strip()
                if font.getlength(t) <= float(max_w) or not cur:
                    cur = t
                else:
                    lines.append(cur); cur = wd
            lines.append(cur)
        text = "\n".join(lines)
    align = o.get("align", "right" if rtl else "left")
    layer = Image.new("RGBA", (doc.w, doc.h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    kw = {"font": font, "align": align, "spacing": int(size * float(o.get("line_spacing", .25)))}
    if rtl:
        kw.update(direction="rtl", language=o.get("language", "ar"))
    anchor_x = x
    if max_w and align == "right":
        anchor_x = x + float(max_w); kw["anchor"] = "ra"
    elif max_w and align == "center":
        anchor_x = x + float(max_w) / 2; kw["anchor"] = "ma"
    bbox = d.multiline_textbbox((anchor_x, y), text, **kw)
    if o.get("background") and o["background"] != "none":
        pad = int(o.get("padding", size * .2))
        d.rectangle([bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad], fill=color(o["background"]))
    if o.get("stroke"):
        kw.update(stroke_width=int(o.get("stroke_width", max(1, size // 15))), stroke_fill=color(o["stroke"]))
    d.multiline_text((anchor_x, y), text, fill=color(o.get("color", "black")), **kw)
    lw = max(1, size // 14)
    if o.get("underline") or o.get("strikethrough"):
        # per-line decoration
        line_h = size + kw["spacing"]
        for i, line in enumerate(text.split("\n")):
            lb = d.textbbox((anchor_x, y + i * line_h), line, **{k: v for k, v in kw.items() if k in ("font", "direction", "language", "anchor")})
            if o.get("underline"):
                yy = y + i * line_h + size * 1.05
                d.line([(lb[0], yy), (lb[2], yy)], fill=color(o.get("color", "black")), width=lw)
            if o.get("strikethrough"):
                yy = (lb[1] + lb[3]) / 2
                d.line([(lb[0], yy), (lb[2], yy)], fill=color(o.get("color", "black")), width=lw)
    doc.img = blend(doc.img, layer)


def region_mask(doc, o):
    """Selection mask from box / polygon (free-form) / subject (AI object select). Supports invert."""
    w, h = doc.w, doc.h
    if "polygon" in o:
        m = ss_mask((w, h), lambda d, s: d.polygon([(x * s, y * s) for x, y in o["polygon"]], fill=255))
    elif o.get("subject"):
        m = subject_mask(doc.flatten(), o.get("box"))
    elif "box" in o:
        x0, y0, x1, y1 = map(int, o["box"])
        m = Image.new("L", (w, h), 0); ImageDraw.Draw(m).rectangle([x0, y0, x1 - 1, y1 - 1], fill=255)
    else:
        m = Image.new("L", (w, h), 255)
    if o.get("invert"):
        m = ImageOps.invert(m)
    if o.get("mask"):  # external mask image (white = selected)
        m = Image.open(o["mask"]).convert("L").resize((w, h))
    return m


_REMBG = {}


def _find_rembg_model(model):
    """Use a model already on disk; never block on a surprise download if another model is present."""
    homes = [os.environ.get("U2NET_HOME"), str(Path.home() / ".u2net"), str(Path.home() / ".rembg" / "models" / "u2net")]
    homes = [h for h in homes if h]
    for name in [model, "isnet-general-use", "u2net", "silueta"]:
        for h in homes:
            f = Path(h) / f"{name}.onnx"
            if f.exists() and not Path(str(f) + ".aria2").exists() and f.stat().st_size > 1_000_000:
                return name, h
    return model, homes[1]


def rembg_session(model="isnet-general-use"):
    from rembg import new_session
    model, home = _find_rembg_model(model)
    os.environ["U2NET_HOME"] = home
    if model not in _REMBG:
        _REMBG[model] = new_session(model)
    return _REMBG[model]


def subject_mask(im, box=None):
    from rembg import remove
    w, h = im.size
    if box:
        x0, y0, x1, y1 = map(int, box)
        crop = im.crop((x0, y0, x1, y1)).convert("RGB")
        mm = remove(crop, session=rembg_session(), only_mask=True)
        m = Image.new("L", (w, h), 0); m.paste(mm, (x0, y0)); return m
    return remove(im.convert("RGB"), session=rembg_session(), only_mask=True)


def bbox_of(mask):
    return mask.point(lambda v: 255 if v > 8 else 0).getbbox() or (0, 0, mask.width, mask.height)


def do_select_op(doc, o):
    op = o["op"]
    m = region_mask(doc, o)
    if op == "crop":
        bb = bbox_of(m)
        def f(im):
            c = im.crop(bb)
            if "polygon" in o or o.get("subject") or o.get("invert"):
                a = ImageChops.multiply(c.getchannel("A"), m.crop(bb)); c.putalpha(a)
            return c
        doc.resize_all(f)
        return
    if op == "delete":  # clears to transparent (or to background colour on the bottom layer)
        im = doc.img.copy()
        a = ImageChops.subtract(im.getchannel("A"), m)
        im.putalpha(a); doc.img = im
        if o.get("to") == "background":
            doc.img = composite_color(doc.img, m, doc.background)
        return
    if op in ("move", "copy"):
        im = doc.img
        piece = im.copy(); piece.putalpha(ImageChops.multiply(im.getchannel("A"), m))
        bb = bbox_of(m); piece = piece.crop(bb)
        if "scale" in o:
            s = float(o["scale"]); piece = piece.resize((max(1, int(piece.width * s)), max(1, int(piece.height * s))), Image.LANCZOS)
        if o.get("rotate"):
            piece = piece.rotate(-float(o["rotate"]), expand=True, resample=Image.BICUBIC)
        if o.get("flip") == "h": piece = ImageOps.mirror(piece)
        if o.get("flip") == "v": piece = ImageOps.flip(piece)
        if op == "move":
            base = im.copy(); base.putalpha(ImageChops.subtract(im.getchannel("A"), m))
            if o.get("fill_hole") == "background":
                base = composite_color(base, m, doc.background)
        else:
            base = im
        tx, ty = map(int, o.get("to", bb[:2]))
        layer = Image.new("RGBA", base.size, (0, 0, 0, 0)); layer.paste(piece, (tx, ty))
        doc.img = blend(base, layer)
        return
    if op == "invert_colors":
        im = doc.img
        inv = ImageOps.invert(im.convert("RGB")).convert("RGBA"); inv.putalpha(im.getchannel("A"))
        doc.img = Image.composite(inv, im, m)
        return
    raise ValueError(op)


def do_image_op(doc, o):
    op = o["op"]
    if op == "resize":
        if "percent" in o:
            pw = ph = float(o["percent"]) / 100
            if "percent_h" in o: ph = float(o["percent_h"]) / 100
            nw, nh = int(doc.w * pw), int(doc.h * ph)
        else:
            nw, nh = o.get("width"), o.get("height")
            if o.get("keep_aspect", True):
                if nw and not nh: nh = round(doc.h * nw / doc.w)
                if nh and not nw: nw = round(doc.w * nh / doc.h)
            nw, nh = int(nw or doc.w), int(nh or doc.h)
        doc.resize_all(lambda im: im.resize((nw, nh), Image.LANCZOS))
    elif op == "skew":
        hx = math.tan(math.radians(float(o.get("horizontal", 0))))
        vy = math.tan(math.radians(float(o.get("vertical", 0))))
        w, h = doc.w, doc.h
        nw, nh = int(w + abs(hx) * h), int(h + abs(vy) * w)
        ox = -hx * h if hx < 0 else 0; oy = -vy * w if vy < 0 else 0
        # forward: X = x + hx*y + ox ; Y = y + vy*x + oy  -> inverse matrix
        det = 1 - hx * vy
        a, b = 1 / det, -hx / det; d, e = -vy / det, 1 / det
        c = -(a * ox + b * oy); f = -(d * ox + e * oy)
        doc.resize_all(lambda im: im.transform((nw, nh), Image.AFFINE, (a, b, c, d, e, f), Image.BICUBIC))
    elif op == "rotate":
        deg = float(o.get("degrees", 90))
        if deg % 90 == 0:
            t = {90: Image.ROTATE_270, 180: Image.ROTATE_180, 270: Image.ROTATE_90, -90: Image.ROTATE_90}[int(deg) % 360 if deg > 0 else int(deg)]
            doc.resize_all(lambda im: im.transpose(t))
        else:
            doc.resize_all(lambda im: im.rotate(-deg, expand=o.get("expand", True), resample=Image.BICUBIC))
    elif op == "flip":
        t = Image.FLIP_LEFT_RIGHT if o.get("direction", "horizontal")[0] == "h" else Image.FLIP_TOP_BOTTOM
        doc.resize_all(lambda im: im.transpose(t))
    elif op == "canvas_size":
        nw, nh = int(o["width"]), int(o["height"])
        ax, ay = {"tl": (0, 0), "center": (.5, .5), "c": (.5, .5)}.get(o.get("anchor", "tl"), (0, 0))
        dx, dy = int((nw - doc.w) * ax), int((nh - doc.h) * ay)
        def f(im):
            n = Image.new("RGBA", (nw, nh), (0, 0, 0, 0)); n.paste(im, (dx, dy)); return n
        doc.resize_all(f)
    elif op == "trim":  # crop the canvas to the visible content (+padding)
        bb = doc.flatten(with_bg=False).getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
        if bb:
            p = int(o.get("padding", 0))
            bb = (max(0, bb[0] - p), max(0, bb[1] - p), min(doc.w, bb[2] + p), min(doc.h, bb[3] + p))
            doc.resize_all(lambda im: im.crop(bb))
    elif op == "paste_image":
        src = Image.open(o["path"]); src = ImageOps.exif_transpose(src).convert("RGBA")
        if "width" in o or "height" in o:
            w = o.get("width") or round(src.width * o["height"] / src.height)
            h = o.get("height") or round(src.height * w / src.width)
            src = src.resize((int(w), int(h)), Image.LANCZOS)
        if o.get("rotate"):
            src = src.rotate(-float(o["rotate"]), expand=True, resample=Image.BICUBIC)
        if o.get("opacity", 1) < 1:
            src.putalpha(src.getchannel("A").point(lambda v: int(v * o["opacity"])))
        layer = Image.new("RGBA", (doc.w, doc.h), (0, 0, 0, 0))
        layer.paste(src, (int(o.get("x", 0)), int(o.get("y", 0))), src)
        doc.img = blend(doc.img, layer, o.get("blend", "normal"))
    else:
        raise ValueError(op)


def do_ai_local(doc, o):
    op = o["op"]
    if op == "remove_background":
        from rembg import remove
        im = doc.img
        out = remove(im.convert("RGB"), session=rembg_session(o.get("model", "isnet-general-use")),
                     alpha_matting=o.get("matting", False))
        out.putalpha(ImageChops.multiply(out.getchannel("A"), im.getchannel("A")))
        doc.img = out; doc.bg_visible = False if doc.current == 0 else doc.bg_visible
    elif op == "blur_background":
        im = doc.flatten()
        m = subject_mask(im)
        blurred = im.filter(ImageFilter.GaussianBlur(float(o.get("radius", 12))))
        m = m.filter(ImageFilter.GaussianBlur(1.5))
        doc.img = Image.composite(im, blurred, m)
    elif op == "magic_erase":  # remove an object and rebuild what was behind it
        import cv2
        im = doc.img
        m = region_mask(doc, o)
        if o.get("subject_in_box") and "box" in o:
            m = subject_mask(doc.flatten(), o["box"])
        mk = (np.asarray(m) > 20).astype(np.uint8) * 255
        mk = cv2.dilate(mk, np.ones((int(o.get("grow", 7)),) * 2, np.uint8))
        rgb = cv2.cvtColor(np.asarray(im.convert("RGB")), cv2.COLOR_RGB2BGR)
        out = cv2.inpaint(rgb, mk, float(o.get("radius", 9)), cv2.INPAINT_TELEA)
        res = Image.fromarray(cv2.cvtColor(out, cv2.COLOR_BGR2RGB)).convert("RGBA")
        a = im.getchannel("A"); a = Image.composite(Image.new("L", a.size, 255), a, Image.fromarray(mk)); res.putalpha(a)
        doc.img = res
    elif op == "coloring_book":  # turn a photo/drawing into clean line art
        import cv2
        g = cv2.cvtColor(np.asarray(doc.flatten().convert("RGB")), cv2.COLOR_RGB2GRAY)
        g = cv2.bilateralFilter(g, 9, 60, 60)
        e = cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, int(o.get("block", 11)) | 1,
                                  int(o.get("c", 7)))
        e = cv2.medianBlur(e, 3)
        if o.get("thickness", 1) > 1:
            e = cv2.erode(e, np.ones((int(o["thickness"]),) * 2, np.uint8))
        doc.layers = []; doc.add_layer("Coloring page", Image.fromarray(e).convert("RGBA")); doc.bg_visible = True
    elif op == "sticker_outline":  # white die-cut border around transparent artwork
        im = doc.img
        a = im.getchannel("A").point(lambda v: 255 if v > 30 else 0)
        r = int(o.get("width", 10))
        border = a.filter(ImageFilter.MaxFilter(r * 2 + 1)).filter(ImageFilter.GaussianBlur(1))
        base = Image.new("RGBA", im.size, color(o.get("color", "white"))[:3] + (0,)); base.putalpha(border)
        doc.img = Image.alpha_composite(base, im)
    elif op == "upscale":
        import tempfile, shutil
        exe = shutil.which("upscayl-bin")
        if not exe: raise RuntimeError("upscayl-bin not on PATH")
        with tempfile.TemporaryDirectory() as t:
            src, dst = os.path.join(t, "in.png"), os.path.join(t, "out.png")
            doc.flatten().save(src)
            cmd = [exe, "-i", src, "-o", dst, "-s", str(o.get("scale", 4))]
            if o.get("model"): cmd += ["-n", o["model"]]
            subprocess.run(cmd, check=True, capture_output=True)
            up = Image.open(dst).convert("RGBA")
        doc.layers = []; doc.w, doc.h = up.size; doc.add_layer("Upscaled", up)
    else:
        raise ValueError(op)


def do_layer_op(doc, o):
    op = o["op"]
    if op == "layer_add":
        img = None
        if o.get("from"):
            src = Image.open(o["from"]).convert("RGBA")
            img = Image.new("RGBA", (doc.w, doc.h), (0, 0, 0, 0)); img.paste(src, (int(o.get("x", 0)), int(o.get("y", 0))), src)
        doc.add_layer(o.get("name"), img, index=doc.current + 1 if doc.layers else 0)
    elif op == "layer_select":
        doc.current = int(o["index"]) if "index" in o else [l["name"] for l in doc.layers].index(o["name"])
    elif op == "layer_duplicate":
        l = doc.layer; doc.add_layer(l["name"] + " copy", l["image"].copy(), doc.current + 1)
    elif op == "layer_delete":
        doc.layers.pop(doc.current); doc.current = max(0, doc.current - 1)
        if not doc.layers: doc.add_layer()
    elif op in ("layer_hide", "layer_show"):
        doc.layer["visible"] = op == "layer_show"
    elif op == "layer_move":
        l = doc.layers.pop(doc.current)
        to = {"up": doc.current + 1, "down": doc.current - 1, "top": len(doc.layers), "bottom": 0}.get(o.get("to"), o.get("to"))
        to = max(0, min(len(doc.layers), int(to))); doc.layers.insert(to, l); doc.current = to
    elif op == "layer_merge_down":
        if doc.current == 0: return
        top, bot = doc.layers[doc.current], doc.layers[doc.current - 1]
        im = top["image"]
        if top["opacity"] < 1:
            im = im.copy(); im.putalpha(im.getchannel("A").point(lambda v: int(v * top["opacity"])))
        bot["image"] = blend(bot["image"], im, top.get("blend", "normal"))
        doc.layers.pop(doc.current); doc.current -= 1
    elif op == "layer_props":
        for k in ("name", "opacity", "blend", "visible"):
            if k in o: doc.layer[k] = o[k]
    elif op == "flatten":
        im = doc.flatten(with_bg=False); doc.layers = []; doc.add_layer("Flattened", im)
    elif op == "background":
        if "color" in o: doc.background = color(o["color"])
        if "visible" in o: doc.bg_visible = bool(o["visible"])
    else:
        raise ValueError(op)


OPS = {}
for b in BRUSHES + ["stroke"]: OPS[b] = do_stroke
for s in SHAPES: OPS[s] = do_shape
OPS["shape"] = do_shape
OPS["fill"] = do_fill
OPS["text"] = do_text
for k in ("crop", "delete", "move", "copy", "invert_colors"): OPS[k] = do_select_op
for k in ("resize", "skew", "rotate", "flip", "canvas_size", "paste_image", "trim"): OPS[k] = do_image_op
for k in ("remove_background", "blur_background", "magic_erase", "coloring_book", "sticker_outline", "upscale"): OPS[k] = do_ai_local
for k in ("layer_add", "layer_select", "layer_duplicate", "layer_delete", "layer_hide", "layer_show", "layer_move",
          "layer_merge_down", "layer_props", "flatten", "background"): OPS[k] = do_layer_op

OPS_HELP = """
DRAWING  (points=[[x,y],...], color, size, opacity, smooth=0..3, blend=normal|multiply|screen|overlay|darken|lighten)
  pencil brush calligraphy_brush calligraphy_pen airbrush oil crayon marker natural_pencil watercolor
  eraser  {points,size,to:transparent|background}
LINES    line {start,end,size,outline(color),outline_style,arrow_head}
         curve {start,end,control1,control2,size,outline,outline_style}
SHAPES   {box:[x0,y0,x1,y1] | points (polygon), outline:color|none, fill:color|none, size,
          outline_style: solid|crayon|marker|oil|natural_pencil|watercolor, rotate, opacity, radius}
  ellipse rectangle rounded_rectangle polygon triangle right_triangle diamond pentagon hexagon
  arrow_right arrow_left arrow_up arrow_down star4 star5 star6 callout_rect callout_oval callout_cloud heart lightning
FILL     fill {x,y,color,tolerance=32,sample:layer|all}
TEXT     text {x,y,text,font,size,color,bold,italic,underline,strikethrough,background,width(wrap),align,
               stroke,stroke_width}  (Arabic/RTL shaped automatically)
SELECT   any of: box | polygon (free-form) | subject:true (AI object select, optional box) | mask:file, invert:true
  crop delete{to:background} move{to:[x,y],scale,rotate,flip,fill_hole} copy{to} invert_colors
IMAGE    resize{percent|width/height,keep_aspect}  skew{horizontal,vertical deg}  rotate{degrees,expand}
         flip{direction:horizontal|vertical}  canvas_size{width,height,anchor:tl|center}
         paste_image{path,x,y,width,height,rotate,opacity,blend}  trim{padding}
AI/LOCAL remove_background{model,matting}  blur_background{radius}  magic_erase{box|polygon|mask, subject_in_box}
         coloring_book{block,c,thickness}  sticker_outline{width,color}  upscale{scale:2|3|4,model}
LAYERS   layer_add{name,from,x,y} layer_select{index|name} layer_duplicate layer_delete layer_hide layer_show
         layer_move{to:up|down|top|bottom|index} layer_merge_down layer_props{name,opacity,blend,visible}
         flatten background{color,visible}
"""


def run_ops(doc, ops):
    for i, o in enumerate(ops):
        name = o.get("op")
        if name not in OPS:
            raise SystemExit(f"op #{i}: unknown op '{name}'. Run: paint.py ops")
        if "layer" in o and name not in ("layer_select",):
            do_layer_op(doc, {"op": "layer_select", **({"index": o["layer"]} if isinstance(o["layer"], int) else {"name": o["layer"]})})
        OPS[name](doc, o)
    return doc


# ───────────────────────────── preview / view tools ─────────────────────────────
def preview(src, out, zoom=1.0, grid=0, rulers=False, box=None):
    doc = Doc.load(src)
    im = doc.flatten()
    if doc.bg_visible is False or im.getchannel("A").getextrema()[0] < 255:  # checkerboard for transparency
        cb = Image.new("RGBA", im.size, "white"); d = ImageDraw.Draw(cb); s = 8
        for y in range(0, im.height, s):
            for x in range((y // s % 2) * s, im.width, s * 2):
                d.rectangle([x, y, x + s - 1, y + s - 1], fill=(204, 204, 204, 255))
        im = Image.alpha_composite(cb, im)
    if box:
        im = im.crop(tuple(int(v) for v in box))
    if zoom != 1:
        im = im.resize((max(1, int(im.width * zoom)), max(1, int(im.height * zoom))), Image.NEAREST if zoom > 1 else Image.LANCZOS)
    if grid:
        d = ImageDraw.Draw(im); g = grid * zoom
        for x in np.arange(0, im.width, g): d.line([(x, 0), (x, im.height)], fill=(0, 0, 0, 60))
        for y in np.arange(0, im.height, g): d.line([(0, y), (im.width, y)], fill=(0, 0, 0, 60))
    if rulers:
        R = 24
        canvas = Image.new("RGBA", (im.width + R, im.height + R), (240, 240, 240, 255)); canvas.paste(im, (R, R))
        d = ImageDraw.Draw(canvas); f = ImageFont.truetype(find_font("Segoe UI"), 10)
        step = 100 if zoom < 2 else 50
        ox = box[0] if box else 0; oy = box[1] if box else 0
        for v in range(0, int(im.width / zoom) + 1, 10):
            x = R + v * zoom; L = 10 if v % step == 0 else 5 if v % 50 == 0 else 3
            d.line([(x, R - L), (x, R)], fill="black")
            if v % step == 0: d.text((x + 2, 2), str(v + ox), fill="black", font=f)
        for v in range(0, int(im.height / zoom) + 1, 10):
            y = R + v * zoom; L = 10 if v % step == 0 else 5 if v % 50 == 0 else 3
            d.line([(R - L, y), (R, y)], fill="black")
            if v % step == 0: d.text((2, y + 2), str(v + oy), fill="black", font=f)
        im = canvas
    save_image(im, out)


def set_wallpaper(path, style="fill"):
    import ctypes, winreg
    path = str(Path(path).resolve())
    vals = {"fill": ("10", "0"), "fit": ("6", "0"), "stretch": ("2", "0"), "tile": ("0", "1"), "center": ("0", "0"), "span": ("22", "0")}[style]
    k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop", 0, winreg.KEY_SET_VALUE)
    winreg.SetValueEx(k, "WallpaperStyle", 0, winreg.REG_SZ, vals[0]); winreg.SetValueEx(k, "TileWallpaper", 0, winreg.REG_SZ, vals[1])
    ctypes.windll.user32.SystemParametersInfoW(20, 0, path, 3)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("new"); p.add_argument("out"); p.add_argument("--size", default="1152x648"); p.add_argument("--bg", default="white")
    p = sub.add_parser("info"); p.add_argument("src")
    p = sub.add_parser("draw"); p.add_argument("src"); p.add_argument("out"); p.add_argument("--ops"); p.add_argument("--op", action="append", default=[])
    p = sub.add_parser("export"); p.add_argument("src"); p.add_argument("out")
    p = sub.add_parser("preview"); p.add_argument("src"); p.add_argument("out"); p.add_argument("--zoom", type=float, default=1)
    p.add_argument("--grid", type=int, default=0); p.add_argument("--rulers", action="store_true"); p.add_argument("--box")
    p = sub.add_parser("pick"); p.add_argument("src"); p.add_argument("x", type=int); p.add_argument("y", type=int)
    sub.add_parser("ops")
    p = sub.add_parser("gui"); p.add_argument("src", nargs="?")
    p = sub.add_parser("print"); p.add_argument("src")
    p = sub.add_parser("wallpaper"); p.add_argument("src"); p.add_argument("--style", default="fill")
    a = ap.parse_args(argv)

    if a.cmd == "new":
        w, h = map(int, a.size.lower().split("x"))
        d = Doc(w, h, a.bg); d.add_layer("Layer 1")
        print(d.save(a.out))
    elif a.cmd == "info":
        d = Doc.load(a.src)
        print(json.dumps({"width": d.w, "height": d.h, "dpi": d.dpi, "background": hexc(d.background),
                          "background_visible": d.bg_visible, "current_layer": d.current,
                          "layers": [{"index": i, "name": l["name"], "visible": l["visible"], "opacity": l["opacity"],
                                      "blend": l["blend"], "content_bbox": l["image"].getbbox()} for i, l in enumerate(d.layers)]},
                         ensure_ascii=False, indent=1))
    elif a.cmd == "draw":
        ops = []
        if a.ops:
            data = json.loads(Path(a.ops).read_text(encoding="utf-8"))
            ops += data["ops"] if isinstance(data, dict) else data
        ops += [json.loads(s) for s in a.op]
        d = Doc.load(a.src) if Path(a.src).exists() else None
        if d is None: raise SystemExit(f"missing input {a.src} (create one with: paint.py new)")
        run_ops(d, ops)
        print(d.save(a.out), f"{d.w}x{d.h}", f"{len(ops)} ops")
    elif a.cmd == "export":
        d = Doc.load(a.src); save_image(d.flatten(), a.out, d.dpi); print(a.out)
    elif a.cmd == "preview":
        preview(a.src, a.out, a.zoom, a.grid, a.rulers, [int(v) for v in a.box.split(",")] if a.box else None); print(a.out)
    elif a.cmd == "pick":
        d = Doc.load(a.src); px = d.flatten().getpixel((a.x, a.y)); print(hexc(px), px)
    elif a.cmd == "ops":
        print(OPS_HELP)
    elif a.cmd == "gui":
        subprocess.Popen(["mspaint"] + ([str(Path(a.src).resolve())] if a.src else []), shell=True)
    elif a.cmd == "print":
        os.startfile(str(Path(a.src).resolve()), "print")
    elif a.cmd == "wallpaper":
        set_wallpaper(a.src, a.style); print("wallpaper set")


if __name__ == "__main__":
    main()
