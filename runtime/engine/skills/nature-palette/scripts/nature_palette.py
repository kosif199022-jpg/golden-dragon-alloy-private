#!/usr/bin/env python3
"""nature_palette.py — استخراج باليتة ألوان من صور الطيور والحيوانات والأشياء.

Commands:
  extract IMG [IMG...]   palette card (PNG) + palette.json + palette.css + swatches.txt
  reel IMG               animated 9:16 mp4: the eyedropper visits each color, swatches pop in
  learn VIDEO            contact sheet of a reference reel, to study a creator's method
Needs: python3, numpy, Pillow (with raqm for Arabic). ffmpeg only for `reel` and `learn`.
"""
import argparse, json, math, os, shutil, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FONT = os.path.join(ROOT, "assets", "Cairo.ttf")
NAMES = os.path.join(ROOT, "data", "color_names.json")

# ---------------------------------------------------------------- color math
_M = np.array([[0.4124564, 0.3575761, 0.1804375],
               [0.2126729, 0.7151522, 0.0721750],
               [0.0193339, 0.1191920, 0.9503041]])
_WP = np.array([0.95047, 1.0, 1.08883])


def rgb2lab(rgb):
    c = np.asarray(rgb, dtype=np.float64) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    xyz = (c @ _M.T) / _WP
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    L = 116 * f[..., 1] - 16
    a = 500 * (f[..., 0] - f[..., 1])
    b = 200 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], -1)


def chroma_hue(lab):
    C = np.hypot(lab[..., 1], lab[..., 2])
    H = (np.degrees(np.arctan2(lab[..., 2], lab[..., 1])) + 360) % 360
    return C, H


def hexof(rgb):
    return "#%02X%02X%02X" % tuple(int(round(v)) for v in rgb)


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def lum(rgb):
    c = np.asarray(rgb, float) / 255
    c = np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a, b):
    la, lb = sorted([lum(a), lum(b)], reverse=True)
    return (la + 0.05) / (lb + 0.05)


_names = None


def name_of(rgb):
    global _names
    if _names is None:
        rows = json.load(open(NAMES, encoding="utf-8"))
        _names = (rows, rgb2lab(np.array([hex2rgb(r[0]) for r in rows])))
    rows, labs = _names
    d = np.linalg.norm(labs - rgb2lab(np.array(rgb, float)), axis=1)
    r = rows[int(d.argmin())]
    return r[1], r[2]


# ---------------------------------------------------------------- k-means
def kmeans(X, k, w=None, iters=25, seed=0):
    rng = np.random.default_rng(seed)
    n = len(X)
    k = min(k, n)
    w = np.ones(n) if w is None else w
    cent = [X[rng.choice(n, p=w / w.sum())]]
    for _ in range(1, k):  # k-means++
        d = np.min(((X[:, None] - np.array(cent)[None]) ** 2).sum(-1), 1) * w
        if d.sum() == 0:
            break
        cent.append(X[rng.choice(n, p=d / d.sum())])
    C = np.array(cent)
    for _ in range(iters):
        lab = np.argmin(((X[:, None] - C[None]) ** 2).sum(-1), 1)
        newC = np.array([np.average(X[lab == j], 0, w[lab == j]) if (lab == j).any() else C[j]
                         for j in range(len(C))])
        if np.allclose(newC, C, atol=0.05):
            break
        C = newC
    lab = np.argmin(((X[:, None] - C[None]) ** 2).sum(-1), 1)
    return C, lab


# ---------------------------------------------------------------- subject mask
def _box(a, r):
    if r < 1:
        return a
    k = 2 * r + 1
    p = np.pad(a, r, mode="edge").cumsum(0).cumsum(1)
    p = np.pad(p, ((1, 0), (1, 0)))
    return (p[k:, k:] - p[:-k, k:] - p[k:, :-k] + p[:-k, :-k]) / (k * k)


def _otsu(v):
    hist, edges = np.histogram(v, 64)
    p = hist / hist.sum()
    best, t = -1, edges[32]
    for i in range(1, 64):
        w0, w1 = p[:i].sum(), p[i:].sum()
        if w0 == 0 or w1 == 0:
            continue
        m0 = (p[:i] * edges[:i]).sum() / w0
        m1 = (p[i:] * edges[i:64]).sum() / w1
        s = w0 * w1 * (m0 - m1) ** 2
        if s > best:
            best, t = s, edges[i]
    return t


def _largest_components(m, keep_frac=0.15):
    h, w = m.shape
    lab = np.zeros((h, w), np.int32)
    sizes = []
    cur = 0
    for y0, x0 in zip(*np.nonzero(m)):
        if lab[y0, x0]:
            continue
        cur += 1
        stack = [(y0, x0)]
        lab[y0, x0] = cur
        n = 0
        while stack:
            y, x = stack.pop()
            n += 1
            for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= yy < h and 0 <= xx < w and m[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = cur
                    stack.append((yy, xx))
        sizes.append(n)
    if not sizes:
        return m
    big = max(sizes)
    keep = [i + 1 for i, s in enumerate(sizes) if s >= big * keep_frac]
    return np.isin(lab, keep)


def center_mask(h, w):
    yy, xx = np.mgrid[0:h, 0:w]
    return ((xx - w / 2) / (w * 0.36)) ** 2 + ((yy - h / 2) / (h * 0.40)) ** 2 <= 1


def auto_mask(img):
    """Subject = differs from the border colors AND/OR is sharper than the bokeh, near the center."""
    small = img.copy()
    small.thumbnail((240, 240))
    a = np.asarray(small.convert("RGB"), float)
    h, w = a.shape[:2]
    lab = rgb2lab(a)
    bw = max(2, int(min(h, w) * 0.06))
    border = np.concatenate([lab[:bw].reshape(-1, 3), lab[-bw:].reshape(-1, 3),
                             lab[:, :bw].reshape(-1, 3), lab[:, -bw:].reshape(-1, 3)])
    bc, _ = kmeans(border, 5, iters=12)
    dist = np.min(np.linalg.norm(lab[:, :, None] - bc[None, None], axis=-1), -1)
    L = lab[..., 0]
    gy, gx = np.gradient(L)
    sharp = _box(np.hypot(gx, gy), 3)
    nz = lambda v: (v - np.percentile(v, 2)) / (np.percentile(v, 98) - np.percentile(v, 2) + 1e-6)
    yy, xx = np.mgrid[0:h, 0:w]
    prior = np.exp(-(((xx - w / 2) / (w * 0.55)) ** 2 + ((yy - h / 2) / (h * 0.55)) ** 2))
    score = (0.65 * np.clip(nz(dist), 0, 1) + 0.35 * np.clip(nz(sharp), 0, 1)) * (0.55 + 0.45 * prior)
    score = _box(score, 2)
    m = score > _otsu(score.ravel())
    m = _box(m.astype(float), 2) > 0.5
    m = _largest_components(m)
    frac = m.mean()
    how = "auto"
    if frac < 0.04 or frac > 0.88:
        m, how = center_mask(h, w), "center (auto mask unsure)"
    return Image.fromarray((m * 255).astype(np.uint8)).resize(img.size, Image.BILINEAR), how, bc


def get_mask(img, mode):
    if mode == "full":
        return Image.new("L", img.size, 255), "full", None
    if mode == "center":
        h, w = img.size[1], img.size[0]
        return Image.fromarray((center_mask(h, w) * 255).astype(np.uint8)), "center", None
    if mode and os.path.isfile(mode):  # cut-out PNG (alpha) or b/w mask
        m = Image.open(mode)
        m = m.getchannel("A") if m.mode in ("RGBA", "LA") else m.convert("L")
        return m.resize(img.size), "file", None
    return auto_mask(img)


# ---------------------------------------------------------------- palette
ROLE_AR = {"dominant": "السائد", "secondary": "الثانوي", "accent": "لون التمييز",
           "shadow": "الظل", "highlight": "الإضاءة", "support": "مساعد", "environment": "البيئة"}


def extract(img, k=6, mask_mode="auto", with_env=True, crop=None):
    img = ImageOps.exif_transpose(img).convert("RGB")
    if crop:  # x0,y0,x1,y1 as fractions: zoom on the subject before anything else
        x0, y0, x1, y1 = [float(v) for v in crop.split(",")]
        W0, H0 = img.size
        img = img.crop((int(x0 * W0), int(y0 * H0), int(x1 * W0), int(y1 * H0)))
    work = img.copy()
    work.thumbnail((420, 420))
    mask, how, bg_centers = get_mask(work, mask_mode)
    A = np.asarray(work, float)
    M = np.asarray(mask, float) / 255 > 0.5
    px = A[M]
    if len(px) < 200:
        px, M, how = A.reshape(-1, 3), np.ones(A.shape[:2], bool), "full (mask too small)"
    rng = np.random.default_rng(1)
    if len(px) > 30000:
        px = px[rng.choice(len(px), 30000, replace=False)]
    lab = rgb2lab(px)
    C0, H0 = chroma_hue(lab)
    # vivid pixels count a bit more: a designer's eye goes to color, not to mud
    wts = 1 + np.clip(C0 / 60, 0, 1)
    cents, lbl = kmeans(lab, 16, wts)
    clusters = []
    for j in range(len(cents)):
        sel = lbl == j
        if sel.sum() < 10:
            continue
        cl, cp = lab[sel], px[sel]
        c, _ = chroma_hue(cl)
        # "true color": the purer half of the cluster, not the muddy mean
        pure = c >= np.percentile(c, 50)
        rep = np.median(cp[pure], 0)
        clusters.append({"rgb": rep, "lab": rgb2lab(rep), "w": sel.mean()})
    # merge near-identical
    clusters.sort(key=lambda c: -c["w"])
    merged = []
    for c in clusters:
        for m in merged:
            if np.linalg.norm(m["lab"] - c["lab"]) < 9:
                m["w"] += c["w"]
                break
        else:
            merged.append(dict(c))
    for c in merged:
        c["C"], c["H"] = [float(v) for v in chroma_hue(c["lab"])]
        c["L"] = float(c["lab"][0])

    # 1) greedy pick: area x vividness x distance from what we already have
    #    (a painter keeps the small vivid patches: the macaw's blue, the kingfisher's orange)
    chosen = []

    def min_de(c):
        return min([np.linalg.norm(c["lab"] - o["lab"]) for o in chosen] or [99])

    def score(c):
        vivid = 1 + 1.6 * min(c["C"] / 50, 1.5)
        sep = min(min_de(c) / 32, 1.0) ** 2
        return (c["w"] ** 0.45) * vivid * sep

    pool = [c for c in merged if c["w"] >= 0.012]  # ignore specks (a tail-light, a plate)
    chosen.append(max(pool, key=lambda c: c["w"]))
    pool = [c for c in pool if c is not chosen[0]]
    while pool and len(chosen) < k:
        c = max(pool, key=score)
        if min_de(c) < 14:
            break
        chosen.append(c)
        pool = [p for p in pool if p is not c]
    # 2) roles, decided after the pick
    for c in chosen:
        c["role"] = "support"
    dom = max(chosen, key=lambda c: c["w"])
    dom["role"] = "dominant"
    rest = [c for c in chosen if c is not dom]

    def hue_gap(c):
        g = abs(c["H"] - dom["H"]) % 360
        return min(g, 360 - g) / 180

    acc = [c for c in rest if c["C"] > 22 and c["w"] < 0.35]
    if acc:
        max(acc, key=lambda c: c["C"] * (c["w"] ** 0.3) * ((0.6 + hue_gap(c)) if dom["C"] > 12 else 1))["role"] = "accent"
    free = lambda: [c for c in rest if c["role"] == "support"]
    darks = [c for c in free() if c["L"] < 32]
    if darks:
        min(darks, key=lambda c: c["L"])["role"] = "shadow"
    lights = [c for c in free() if c["L"] > 72 and c["C"] < 35]
    if lights:
        max(lights, key=lambda c: c["L"])["role"] = "highlight"
    if free():
        max(free(), key=lambda c: c["w"])["role"] = "secondary"
    order = {"dominant": 0, "secondary": 1, "accent": 2, "support": 3, "highlight": 4, "shadow": 5}
    chosen.sort(key=lambda c: (order[c["role"]], -c["w"]))

    env = None
    if with_env and bg_centers is not None and how.startswith("auto"):
        Bpx = A[~M]
        if len(Bpx) > 200:
            bl = rgb2lab(Bpx[rng.choice(len(Bpx), min(len(Bpx), 15000), replace=False)])
            bc, bll = kmeans(bl, 3, iters=12)
            j = np.bincount(bll).argmax()
            # back to rgb via nearest real pixel
            Bs = Bpx[rng.choice(len(Bpx), min(len(Bpx), 4000), replace=False)]
            idx = np.argmin(np.linalg.norm(rgb2lab(Bs) - bc[j], axis=1))
            env = {"rgb": Bs[idx], "lab": rgb2lab(Bs[idx]), "w": float((bll == j).mean()), "role": "environment"}

    # where on the photo each color lives (for the eyedropper markers)
    LabImg = rgb2lab(A)
    for c in chosen + ([env] if env else []):
        d = np.linalg.norm(LabImg - c["lab"], axis=-1)
        hit = (d < 10) & (M if c["role"] != "environment" else ~M)
        if hit.sum() < 3:
            hit = d < np.percentile(d, 1)
        dens = _box(hit.astype(float), 4) * hit
        y, x = np.unravel_index(int(dens.argmax()), dens.shape)
        c["xy"] = (x / A.shape[1], y / A.shape[0])

    total = sum(c["w"] for c in chosen) or 1
    out = []
    for c in chosen:
        ar, en = name_of(c["rgb"])
        out.append({"hex": hexof(c["rgb"]), "rgb": [int(round(v)) for v in c["rgb"]],
                    "role": c["role"], "role_ar": ROLE_AR[c["role"]], "share": round(c["w"] / total, 3),
                    "name_ar": ar, "name_en": en, "L": round(float(c["lab"][0]), 1),
                    "chroma": round(float(chroma_hue(c["lab"])[0]), 1),
                    "hue": round(float(chroma_hue(c["lab"])[1]), 1), "xy": [round(v, 4) for v in c["xy"]]})
    if env:
        ar, en = name_of(env["rgb"])
        env_out = {"hex": hexof(env["rgb"]), "rgb": [int(v) for v in env["rgb"]], "role": "environment",
                   "role_ar": ROLE_AR["environment"], "name_ar": ar, "name_en": en,
                   "xy": [round(v, 4) for v in env["xy"]]}
    else:
        env_out = None
    ys, xs = np.nonzero(M)
    center = [round(float(xs.mean() / A.shape[1]), 3), round(float(ys.mean() / A.shape[0]), 3)] if len(xs) else [0.5, 0.5]
    return {"palette": out, "environment": env_out, "mask": how, "center": center,
            "harmony": harmony(out), "rule_60_30_10": rule603010(out)}, img, mask


def harmony(pal):
    chrom = [p for p in pal if p["chroma"] > 15]
    if len(chrom) < 2:
        return {"type": "monochrome", "ar": "أحادي (درجات لون واحد ومحايدات)"}
    hs = [p["hue"] for p in chrom]
    gaps = []
    for i in range(len(hs)):
        for j in range(i + 1, len(hs)):
            g = abs(hs[i] - hs[j]) % 360
            gaps.append(min(g, 360 - g))
    mx = max(gaps)
    if mx < 50:
        return {"type": "analogous", "ar": "متجاور (ألوان جيران على العجلة)", "max_hue_gap": round(mx)}
    if mx >= 150:
        has_mid = any(60 < g < 150 for g in gaps)
        if has_mid and len(chrom) >= 3:
            return {"type": "split-complementary", "ar": "متكامل منقسم", "max_hue_gap": round(mx)}
        return {"type": "complementary", "ar": "متكامل (ألوان متقابلة)", "max_hue_gap": round(mx)}
    if 100 <= mx < 150 and len(chrom) >= 3:
        return {"type": "triadic", "ar": "ثلاثي", "max_hue_gap": round(mx)}
    return {"type": "related", "ar": "متقارب مع لون مختلف", "max_hue_gap": round(mx)}


def rule603010(pal):
    by = {p["role"]: p for p in pal}
    d = by.get("dominant")
    s = by.get("secondary") or by.get("shadow") or by.get("highlight")
    a = by.get("accent")
    return {"60": d and d["hex"], "30": s and s["hex"], "10": a and a["hex"]}


# ---------------------------------------------------------------- rendering
def font(sz):
    try:
        f = ImageFont.truetype(FONT, sz, layout_engine=ImageFont.Layout.RAQM)
        try:
            f.set_variation_by_name("Bold" if sz >= 40 else "SemiBold")
        except Exception:
            pass
        return f
    except Exception:
        for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"]:
            if os.path.exists(p):
                return ImageFont.truetype(p, sz)
        return ImageFont.load_default()


def text_c(d, xy, s, f, fill, anchor="mm"):
    d.text(xy, s, font=f, fill=fill, anchor=anchor, direction="rtl" if any("\u0600" <= ch <= "\u06ff" for ch in s) else None)


def rounded(img, r):
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, img.size[0] - 1, img.size[1] - 1], r, fill=255)
    return m


THEMES = {"light": {"bg": (244, 241, 234), "ink": (28, 28, 28), "sub": (110, 104, 96)},
          "dark": {"bg": (18, 18, 20), "ink": (240, 238, 232), "sub": (150, 146, 140)}}


def draw_marker(d, x, y, rgb, n, f, r=26, ring=(255, 255, 255)):
    d.ellipse([x - r - 5, y - r - 5, x + r + 5, y + r + 5], fill=(0, 0, 0, 90))
    d.ellipse([x - r - 3, y - r - 3, x + r + 3, y + r + 3], fill=ring)
    d.ellipse([x - r, y - r, x + r, y + r], fill=tuple(rgb))
    ink = (0, 0, 0) if lum(rgb) > 0.45 else (255, 255, 255)
    text_c(d, (x, y), str(n), f, ink)


def layout(fmt):
    return {"card": (1080, 1350), "story": (1080, 1920), "square": (1080, 1080)}[fmt]


def compose(res, img, fmt="card", theme="light", title=None, show_n=None, pop=1.0, picker=None):
    """Draw the card. show_n / pop / picker are used by the reel animation."""
    W, H = layout(fmt)
    T = THEMES[theme]
    pal = res["palette"]
    n_all = len(pal)
    show_n = n_all if show_n is None else show_n
    canvas = Image.new("RGB", (W, H), T["bg"])
    d = ImageDraw.Draw(canvas, "RGBA")
    pad = 60
    top = 150 if title else 60
    sw_h = {"card": 360, "story": 520, "square": 300}[fmt]
    ph_box = (W - 2 * pad, H - top - sw_h - 90)
    ph = img.copy()
    # crop the photo around the subject, and keep the marker coords consistent with that crop
    sx, sy = img.size
    scale = max(ph_box[0] / sx, ph_box[1] / sy)
    cx, cy = res.get("center", [0.5, 0.5])
    offx = min(max(cx * sx * scale - ph_box[0] / 2, 0), sx * scale - ph_box[0])
    offy = min(max(cy * sy * scale - ph_box[1] / 2, 0), sy * scale - ph_box[1])
    ph = ph.resize((max(1, round(sx * scale)), max(1, round(sy * scale))), Image.LANCZOS)
    ph = ph.crop((int(offx), int(offy), int(offx) + ph_box[0], int(offy) + ph_box[1]))
    canvas.paste(ph, (pad, top), rounded(ph, 28))
    if title:
        text_c(d, (W // 2, 85), title, font(56), T["ink"])

    def to_xy(xy):
        return (pad + xy[0] * sx * scale - offx, top + xy[1] * sy * scale - offy)

    fm = font(26)
    for i, p in enumerate(pal[:show_n]):
        x, y = to_xy(p["xy"])
        x = min(max(x, pad + 36), W - pad - 36)
        y = min(max(y, top + 36), top + ph_box[1] - 36)
        r = 26 * (pop if i == show_n - 1 else 1)
        if r > 2:
            draw_marker(d, x, y, p["rgb"], i + 1, fm, r=r)
    if picker is not None:  # the moving eyedropper ring
        x, y = to_xy(picker)
        d.ellipse([x - 46, y - 46, x + 46, y + 46], outline=(255, 255, 255), width=6)
        d.line([x - 60, y, x - 50, y], fill=(255, 255, 255), width=4)
        d.line([x + 50, y, x + 60, y], fill=(255, 255, 255), width=4)
        d.line([x, y - 60, x, y - 50], fill=(255, 255, 255), width=4)
        d.line([x, y + 50, x, y + 60], fill=(255, 255, 255), width=4)

    # swatches (right-to-left, number 1 on the right for Arabic readers)
    y0 = top + ph_box[1] + 40
    gap = 18
    sw_w = (W - 2 * pad - gap * (n_all - 1)) / n_all
    fh, fn, fr = font(30 if n_all <= 6 else 24), font(26 if n_all <= 6 else 21), font(21)
    bar_h = sw_h - 130
    for i, p in enumerate(pal[:show_n]):
        x1 = W - pad - (i + 1) * sw_w - i * gap
        x2 = x1 + sw_w
        grow = pop if i == show_n - 1 else 1
        bh = bar_h * grow
        d.rounded_rectangle([x1, y0 + bar_h - bh, x2, y0 + bar_h], 22, fill=tuple(p["rgb"]))
        ink = (0, 0, 0, 200) if lum(p["rgb"]) > 0.45 else (255, 255, 255, 220)
        if grow > 0.6:
            text_c(d, ((x1 + x2) / 2, y0 + 34), str(i + 1), fr, ink)
            text_c(d, ((x1 + x2) / 2, y0 + bar_h - 34), (f'{int(round(p["share"] * 100))}%' if p["share"] >= 0.01 else "<1%"), fr, ink)
            text_c(d, ((x1 + x2) / 2, y0 + bar_h + 32), p["hex"], fh, T["ink"])
            text_c(d, ((x1 + x2) / 2, y0 + bar_h + 72), p["name_ar"], fn, T["ink"])
            text_c(d, ((x1 + x2) / 2, y0 + bar_h + 106), p["role_ar"], fr, T["sub"])
    if show_n == n_all:
        hm = res["harmony"]["ar"]
        r = res["rule_60_30_10"]
        parts = [f"التناغم: {hm}"]
        text_c(d, (W // 2, H - 38), "  ·  ".join(parts), font(24), T["sub"])
    return canvas


# ---------------------------------------------------------------- commands
def write_outputs(res, img, out, stem, fmt, theme, title):
    os.makedirs(out, exist_ok=True)
    card = compose(res, img, fmt, theme, title)
    pc = os.path.join(out, f"{stem}_palette_{fmt}.png")
    card.save(pc, optimize=True)
    json.dump(res, open(os.path.join(out, f"{stem}_palette.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    css = [":root {"] + [f'  --{p["role"]}-{i + 1}: {p["hex"]}; /* {p["name_en"]} · {p["name_ar"]} · {int(p["share"] * 100)}% */'
                         for i, p in enumerate(res["palette"])]
    if res["environment"]:
        css.append(f'  --environment: {res["environment"]["hex"]};')
    css.append("}")
    open(os.path.join(out, f"{stem}_palette.css"), "w", encoding="utf-8").write("\n".join(css) + "\n")
    strip = Image.new("RGB", (120 * len(res["palette"]), 120))
    for i, p in enumerate(res["palette"]):
        ImageDraw.Draw(strip).rectangle([i * 120, 0, i * 120 + 119, 119], fill=tuple(p["rgb"]))
    strip.save(os.path.join(out, f"{stem}_strip.png"))
    return pc


def cmd_extract(a):
    for path in a.images:
        img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
        res, img, mask = extract(img, a.k, a.mask, crop=a.crop)
        stem = os.path.splitext(os.path.basename(path))[0]
        pc = write_outputs(res, img, a.out, stem, a.format, a.theme, a.title)
        if a.debug_mask:
            mask.resize(img.size).save(os.path.join(a.out, f"{stem}_mask.png"))
        print(json.dumps({"image": path, "card": pc, "mask": res["mask"], "harmony": res["harmony"]["type"],
                          "palette": [f'{p["hex"]} {p["role"]} {p["name_en"]} {int(p["share"] * 100)}%' for p in res["palette"]],
                          "environment": res["environment"] and res["environment"]["hex"]}, ensure_ascii=False))


def ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def back(t):
    t = max(0.0, min(1.0, t))
    c = 1.70158
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2


def cmd_reel(a):
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found")
    img = ImageOps.exif_transpose(Image.open(a.image)).convert("RGB")
    res, img, _ = extract(img, a.k, a.mask, crop=a.crop)
    os.makedirs(a.out, exist_ok=True)
    stem = os.path.splitext(os.path.basename(a.image))[0]
    write_outputs(res, img, a.out, stem, "story", a.theme, a.title)
    pal = res["palette"]
    fps, W, H = 30, 1080, 1920
    intro, per, hold = 1.0, a.per, 2.5
    total = intro + per * len(pal) + hold
    mp4 = os.path.join(a.out, f"{stem}_palette_reel.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                           "-crf", "18", "-movflags", "+faststart", mp4], stdin=subprocess.PIPE)
    start = (0.5, 0.5)
    for fi in range(int(total * fps)):
        t = fi / fps
        if t < intro:
            fr = compose(res, img, "story", a.theme, a.title, show_n=0, picker=None)
            k = ease(t / intro)
            fr = Image.blend(Image.new("RGB", fr.size, THEMES[a.theme]["bg"]), fr, k)
        elif t < intro + per * len(pal):
            i = int((t - intro) // per)
            lt = (t - intro - i * per) / per
            prev = start if i == 0 else pal[i - 1]["xy"]
            cur = pal[i]["xy"]
            m = ease(lt / 0.45)
            pick = (prev[0] + (cur[0] - prev[0]) * m, prev[1] + (cur[1] - prev[1]) * m)
            pop = back((lt - 0.45) / 0.35) if lt > 0.45 else 0.0
            fr = compose(res, img, "story", a.theme, a.title, show_n=i + (1 if lt > 0.45 else 0),
                         pop=pop if lt > 0.45 else 1.0, picker=pick if lt < 0.85 else None)
        else:
            fr = compose(res, img, "story", a.theme, a.title)
        ff.stdin.write(fr.tobytes())
    ff.stdin.close()
    ff.wait()
    print(json.dumps({"reel": mp4, "seconds": round(total, 1), "colors": len(pal)}, ensure_ascii=False))


def cmd_learn(a):
    """Contact sheet of a reference reel: one frame every `--every` seconds, numbered with time."""
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found")
    os.makedirs(a.out, exist_ok=True)
    tmp = os.path.join(a.out, "_frames")
    os.makedirs(tmp, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", a.video, "-vf", f"fps=1/{a.every},scale=270:-2",
                    os.path.join(tmp, "f%04d.jpg")], check=True)
    files = sorted(os.listdir(tmp))
    if not files:
        sys.exit("no frames")
    th = [Image.open(os.path.join(tmp, f)) for f in files]
    cols = 6
    tw, thh = th[0].size
    rows = math.ceil(len(th) / cols)
    sheet = Image.new("RGB", (cols * tw, rows * (thh + 30)), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    for i, im in enumerate(th):
        x, y = (i % cols) * tw, (i // cols) * (thh + 30)
        sheet.paste(im, (x, y + 30))
        d.text((x + 8, y + 4), f"{i * a.every:.1f}s", fill=(255, 255, 255), font=font(18))
    stem = os.path.splitext(os.path.basename(a.video))[0]
    p = os.path.join(a.out, f"{stem}_contact.jpg")
    sheet.save(p, quality=88)
    shutil.rmtree(tmp)
    print(json.dumps({"contact_sheet": p, "frames": len(th), "every_s": a.every}))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    e = sp.add_parser("extract")
    e.add_argument("images", nargs="+")
    r = sp.add_parser("reel")
    r.add_argument("image")
    r.add_argument("--per", type=float, default=1.1, help="seconds per color")
    for p in (e, r):
        p.add_argument("--k", type=int, default=6, help="number of colors (4-8)")
        p.add_argument("--mask", default="auto", help="auto | full | center | path to cut-out PNG")
        p.add_argument("--out", default="palette_out")
        p.add_argument("--theme", default="light", choices=["light", "dark"])
        p.add_argument("--title", default=None)
        p.add_argument("--crop", default=None, help="x0,y0,x1,y1 fractions, e.g. 0.2,0.1,0.8,0.9")
    e.add_argument("--format", default="card", choices=["card", "story", "square"])
    e.add_argument("--debug-mask", action="store_true")
    l = sp.add_parser("learn")
    l.add_argument("video")
    l.add_argument("--every", type=float, default=0.5)
    l.add_argument("--out", default="learn_out")
    a = ap.parse_args()
    {"extract": cmd_extract, "reel": cmd_reel, "learn": cmd_learn}[a.cmd](a)


if __name__ == "__main__":
    main()
