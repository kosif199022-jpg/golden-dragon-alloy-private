# -*- coding: utf-8 -*-
"""chroma-motion: image -> color system + motion language + brand identity kit.

Usage:
  python -X utf8 chroma_identity.py IMAGE --name "اسم البراند" [--tagline "..."]
         [--out DIR] [--subject auto|on|off] [--motif auto|wing|wave|bloom|orbit|pulse]
         [--k 10] [--video 16:9|9:16|1:1|none] [--seconds 8] [--fps 30]

Outputs in DIR: palette.json, tokens.css, tokens.json (design tokens), palette.gpl,
palette.ase, brand_board.png, swatches.png, identity.html (live motion page),
motion.mp4 (identity reveal), report.md.
"""
import argparse, json, math, os, struct, subprocess, sys, colorsys, shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "..", "assets", "fonts")
CAIRO = os.path.join(FONTS, "Cairo.ttf")
AMIRI = os.path.join(FONTS, "Amiri-Bold.ttf")

# ---------------------------------------------------------------- color math (OKLab)
def srgb_to_lin(c):
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)

def lin_to_srgb(c):
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * np.power(np.clip(c, 0, None), 1 / 2.4) - 0.055)

def rgb_to_oklab(rgb):  # rgb 0..1, shape (...,3)
    l = srgb_to_lin(rgb)
    M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                   [0.2119034982, 0.6806995451, 0.1073969566],
                   [0.0883024619, 0.2817188376, 0.6299787005]])
    lms = np.cbrt(l @ M1.T)
    M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                   [1.9779984951, -2.4285922050, 0.4505937099],
                   [0.0259040371, 0.7827717662, -0.8086757660]])
    return lms @ M2.T

def oklab_to_rgb(lab):
    lab = np.asarray(lab, dtype=np.float64)
    M2i = np.array([[1.0, 0.3963377774, 0.2158037573],
                    [1.0, -0.1055613458, -0.0638541728],
                    [1.0, -0.0894841775, -1.2914855480]])
    lms = (lab @ M2i.T) ** 3
    M1i = np.array([[4.0767416621, -3.3077115913, 0.2309699292],
                    [-1.2684380046, 2.6097574011, -0.3413193965],
                    [-0.0041960863, -0.7034186147, 1.7076147010]])
    return lin_to_srgb(lms @ M1i.T)

def lab_to_lch(lab):
    L, a, b = lab
    return L, math.hypot(a, b), (math.degrees(math.atan2(b, a)) + 360) % 360

def lch_to_lab(L, C, H):
    return np.array([L, C * math.cos(math.radians(H)), C * math.sin(math.radians(H))])

def in_gamut(rgb, eps=1e-4):
    return bool(np.all(rgb >= -eps) and np.all(rgb <= 1 + eps))

def lch_to_rgb_clamped(L, C, H):
    """Reduce chroma until the color fits sRGB (keeps hue and lightness)."""
    lo, hi = 0.0, C
    rgb = oklab_to_rgb(lch_to_lab(L, C, H))
    if in_gamut(rgb):
        return np.clip(rgb, 0, 1)
    for _ in range(24):
        mid = (lo + hi) / 2
        if in_gamut(oklab_to_rgb(lch_to_lab(L, mid, H))):
            lo = mid
        else:
            hi = mid
    return np.clip(oklab_to_rgb(lch_to_lab(L, lo, H)), 0, 1)

def to_hex(rgb):
    r, g, b = [int(round(float(np.clip(x, 0, 1)) * 255)) for x in rgb]
    return "#%02X%02X%02X" % (r, g, b)

def hex_to_rgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)])

def rel_lum(rgb):
    l = srgb_to_lin(rgb)
    return float(0.2126 * l[0] + 0.7152 * l[1] + 0.0722 * l[2])

def contrast(a, b):
    la, lb = rel_lum(a), rel_lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)

def hue_dist(h1, h2):
    d = abs(h1 - h2) % 360
    return min(d, 360 - d)

HUE_NAMES = [(20, "أحمر قرمزي", "Crimson"), (45, "برتقالي", "Orange"), (70, "عنبري", "Amber"),
             (100, "ذهبي زيتوني", "Olive Gold"), (140, "أخضر", "Green"), (175, "زمردي", "Emerald"),
             (205, "فيروزي", "Teal"), (240, "أزرق سماوي", "Azure"), (275, "أزرق ملكي", "Royal Blue"),
             (310, "بنفسجي", "Violet"), (345, "ماجنتا", "Magenta"), (360, "أحمر قرمزي", "Crimson")]

def color_name(L, C, H):
    if C < 0.035:
        if L > 0.9: return ("أبيض عاجي", "Ivory")
        if L < 0.25: return ("أسود فحمي", "Charcoal")
        return ("رمادي حجري", "Stone Gray")
    for lim, ar, en in HUE_NAMES:
        if H < lim:
            base_ar, base_en = ar, en
            break
    if L < 0.4: return (base_ar + " غامق", "Deep " + base_en)
    if L > 0.85: return (base_ar + " فاتح", "Pale " + base_en)
    if C < 0.08: return (base_ar + " مطفي", "Muted " + base_en)
    return (base_ar, base_en)

# ---------------------------------------------------------------- analysis
def load_image(path, max_side=1600):
    im = Image.open(path)
    im = im.convert("RGBA") if im.mode in ("RGBA", "LA", "P") else im.convert("RGB")
    if max(im.size) > max_side:
        s = max_side / max(im.size)
        im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    return im

def subject_mask(im, mode):
    """Return float mask 0..1 (1 = subject). Uses existing alpha, else rembg."""
    if im.mode == "RGBA":
        a = np.asarray(im.split()[-1], dtype=np.float32) / 255
        if a.min() < 0.9:
            return a, "alpha"
    if mode == "off":
        return None, "off"
    try:
        from rembg import remove, new_session
        sess = new_session("isnet-general-use")
        cut = remove(im.convert("RGB"), session=sess)
        a = np.asarray(cut.split()[-1], dtype=np.float32) / 255
        cover = float((a > 0.5).mean())
        if mode == "auto" and not (0.03 < cover < 0.92):
            return None, "rembg-rejected(cover=%.2f)" % cover
        return a, "rembg(cover=%.2f)" % cover
    except Exception as e:  # rembg missing / model missing
        return None, "rembg-failed:%s" % type(e).__name__

def cluster(lab, w, k):
    from sklearn.cluster import KMeans
    k = min(k, max(2, len(lab) // 50))
    km = KMeans(n_clusters=k, n_init=4, random_state=7).fit(lab, sample_weight=w)
    cents, weights = [], []
    for i in range(k):
        m = km.labels_ == i
        if not m.any():
            continue
        ww = w[m]
        cents.append((lab[m] * ww[:, None]).sum(0) / ww.sum())
        weights.append(ww.sum())
    cents, weights = np.array(cents), np.array(weights)
    # merge perceptually-close clusters (deltaE_ok < 0.045)
    merged = True
    while merged and len(cents) > 1:
        merged = False
        D = np.linalg.norm(cents[:, None] - cents[None], axis=-1) + np.eye(len(cents)) * 9
        i, j = np.unravel_index(D.argmin(), D.shape)
        if D[i, j] < 0.045:
            tw = weights[i] + weights[j]
            cents[i] = (cents[i] * weights[i] + cents[j] * weights[j]) / tw
            weights[i] = tw
            cents = np.delete(cents, j, 0); weights = np.delete(weights, j)
            merged = True
    order = np.argsort(-weights)
    return cents[order], weights[order] / weights.sum()

def extract(im, mask, k):
    rgb = np.asarray(im.convert("RGB"), dtype=np.float64) / 255
    h, w = rgb.shape[:2]
    s = 220 / max(h, w)
    small = np.asarray(im.convert("RGB").resize((max(1, int(w * s)), max(1, int(h * s))), Image.BOX), dtype=np.float64) / 255
    sh, sw = small.shape[:2]
    lab = rgb_to_oklab(small.reshape(-1, 3))
    chroma = np.hypot(lab[:, 1], lab[:, 2])
    yy, xx = np.mgrid[0:sh, 0:sw]
    center = np.exp(-(((xx / sw - 0.5) ** 2) + ((yy / sh - 0.5) ** 2)) / 0.18).reshape(-1)
    if mask is not None:
        m = np.asarray(Image.fromarray((mask * 255).astype(np.uint8)).resize((sw, sh), Image.BILINEAR), dtype=np.float64).reshape(-1) / 255
    else:
        m = None
    # salience weight: chroma + centre; subject pixels dominate when mask exists
    sal = 0.35 + np.clip(chroma / 0.15, 0, 1.2) + 0.5 * center
    if m is not None:
        w_subj = sal * (0.01 + m)
        w_bg = (1 - m) + 1e-3
    else:
        w_subj = sal
        w_bg = None
    cents, wts = cluster(lab, w_subj, k)
    # vivid representative per cluster: mean of its top-25% chroma pixels (k-means
    # averages wash out iridescent/pure colours like a kingfisher wing)
    near = np.argmin(np.linalg.norm(lab[:, None] - cents[None], axis=-1), axis=1)
    vivid = cents.copy()
    for i in range(len(cents)):
        sel = (near == i) & (w_subj > np.percentile(w_subj, 20))
        if sel.sum() >= 8:
            ci = chroma[sel]
            top = sel.copy(); top[sel] = ci >= np.percentile(ci, 75)
            vivid[i] = lab[top].mean(0)
    cents = np.stack([cents, vivid], 1)  # (n, 2, 3): [mean, vivid]
    bg = None
    if w_bg is not None and w_bg.sum() > 5:
        bg = cluster(lab, w_bg, 4)
    # raw area share (unweighted) for reporting
    return cents, wts, bg, lab, chroma

def _lab(x):
    return np.array([x["L"], x["C"] * math.cos(math.radians(x["H"])), x["C"] * math.sin(math.radians(x["H"]))])

def dE(x, y):
    return float(np.linalg.norm(_lab(x) - _lab(y)))

def assign_roles(cents, wts, bg, img_c95=0.1):
    items = []
    for cv, w in zip(cents, wts):
        c, v = cv
        L, C, H = lab_to_lch(c)
        vL, vC, vH = lab_to_lch(v)
        items.append(dict(lab=c, L=L, C=C, H=H, w=float(w), vivid=dict(L=vL, C=vC, H=vH)))
    roles = {}
    # ---- monochrome photo: stay honest, build a tonal (gray) system, no invented hues
    if img_c95 < 0.025:
        def gray(L, w=0.0, syn=False):
            return dict(L=L, C=0.0, H=0.0, w=w, synthetic=syn, lab=lch_to_lab(L, 0, 0))
        byL = sorted(items, key=lambda x: x["L"])
        pick = lambda t: min(byL, key=lambda x: abs(x["L"] - t))
        roles["primary"] = gray(float(np.clip(pick(0.42)["L"], 0.32, 0.55)), pick(0.42)["w"])
        roles["secondary"] = gray(float(np.clip(pick(0.68)["L"], 0.6, 0.8)), pick(0.68)["w"])
        roles["accent"] = gray(float(np.clip(byL[-1]["L"], 0.82, 0.9)), byL[-1]["w"])
        gL = float(np.clip(items[0]["L"], 0.3, 0.9))
        if min(abs(gL - roles[r]["L"]) for r in ("primary", "secondary", "accent")) < 0.08:
            gL = 0.9 if roles["accent"]["L"] < 0.84 else 0.88 if abs(roles["accent"]["L"] - 0.88) > 0.05 else 0.25
        roles["ground"] = gray(gL, items[0]["w"])
        roles["ink"] = gray(min(0.17, byL[0]["L"]), byL[0]["w"])
        roles["paper"] = gray(0.975, 0, True)
        roles["_mode"] = "monochrome"
    else:
        chrom = [x for x in items if x["C"] >= 0.045 and 0.22 < x["L"] < 0.93]
        # ground first (environment colour) so brand roles can avoid duplicating it
        if bg is not None:
            g = lab_to_lch(bg[0][0]); ground = dict(L=g[0], C=g[1], H=g[2], w=float(bg[1][0]))
        else:
            ground = None
        if chrom:
            prim = max(chrom, key=lambda x: x["w"] * (0.5 + min(x["C"], 0.25) / 0.12))
        else:
            d = items[0]
            prim = dict(L=0.55, C=max(0.03, d["C"]), H=d["H"], w=d["w"], synthetic=True)
        rest = [x for x in chrom if x is not prim and dE(x, prim) > 0.08]
        acc = max(rest, key=lambda x: (x["vivid"]["C"] ** 1.2) * (0.25 + hue_dist(x["H"], prim["H"]) / 180) * (0.3 + x["w"] ** 0.5)) if rest else None
        if acc is not None:  # accent = vivid version of its cluster (pure wing/petal colour)
            vv = acc["vivid"]
            acc = dict(acc, L=float(np.clip(vv["L"], 0.45, 0.8)), C=vv["C"], H=vv["H"], src=acc)
        if acc is None or hue_dist(acc["H"], prim["H"]) < 25:
            H2 = (prim["H"] + 180) % 360
            C2 = float(np.clip(img_c95 * 1.2, 0.05, 0.12))  # no louder than the photo itself
            acc = dict(L=0.66, C=C2, H=H2, w=0, synthetic=True)
        acc_src = acc.get("src")
        rest2 = [x for x in rest if x is not acc_src and dE(x, acc) > 0.07 and dE(x, prim) > 0.08
                 and (ground is None or dE(x, ground) > 0.06)]
        sec = max(rest2, key=lambda x: x["w"] * (0.4 + hue_dist(x["H"], prim["H"]) / 90)) if rest2 else None
        if sec is None:
            # tonal secondary: same hue family, clearly lighter or darker than primary
            L3 = prim["L"] - 0.22 if prim["L"] > 0.55 else prim["L"] + 0.2
            sec = dict(L=L3, C=prim["C"] * 0.75, H=(prim["H"] + 12) % 360, w=0, synthetic=True)
        if ground is None or dE(ground, prim) < 0.06 or dE(ground, sec) < 0.05:
            cand = [x for x in items if dE(x, prim) > 0.08 and dE(x, sec) > 0.06]
            if cand:
                g = max(cand, key=lambda x: x["w"] * (1 - min(x["C"], 0.2) * 3))
                ground = dict(L=g["L"], C=min(g["C"], 0.08), H=g["H"], w=g["w"])
            else:
                ground = dict(L=0.9, C=prim["C"] * 0.25, H=prim["H"], w=0, synthetic=True)
        roles.update(primary=prim, accent=acc, secondary=sec, ground=ground)
        darks = [x for x in items if x["L"] < 0.32]
        ink = min(darks, key=lambda x: x["L"]) if darks else None
        if ink is None or ink["L"] > 0.24:
            ink = dict(L=0.19, C=0.025, H=prim["H"], w=0, synthetic=True)
        lights = [x for x in items if x["L"] > 0.9 and x["C"] < 0.05]
        paper = max(lights, key=lambda x: x["L"]) if lights else dict(L=0.975, C=0.01, H=prim["H"], w=0, synthetic=True)
        roles["ink"] = dict(ink, C=min(ink["C"], 0.035))
        roles["paper"] = dict(paper, C=min(paper["C"], 0.015), L=max(paper["L"], 0.965))
        roles["_mode"] = "color"
    mode = roles.pop("_mode")
    for r, v in roles.items():
        rgb = lch_to_rgb_clamped(v["L"], v["C"], v["H"])
        v["hex"] = to_hex(rgb)
        v["ar"], v["en"] = color_name(v["L"], v["C"], v["H"])
    roles_mode[0] = mode
    return roles, items

roles_mode = ["color"]

def text_color(roles, bg_role="paper", fg_role="primary", min_ratio=4.5):
    """Brand colour for text on bg; darken/lighten along the hue until it reads."""
    fg, bg = roles[fg_role], roles[bg_role]
    bgc = hex_to_rgb(bg["hex"])
    if contrast(hex_to_rgb(fg["hex"]), bgc) >= min_ratio:
        return fg["hex"]
    dark_bg = rel_lum(bgc) < 0.3
    for L in np.arange(fg["L"], 0.98 if dark_bg else 0.1, 0.02 if dark_bg else -0.02):
        h = to_hex(lch_to_rgb_clamped(float(L), fg["C"], fg["H"]))
        if contrast(hex_to_rgb(h), bgc) >= min_ratio:
            return h
    return roles["ink"]["hex"]

def fit_font(d, s, path, size, max_w, weight=None, min_size=18):
    while size > min_size:
        f = font(path, size, weight)
        rtl = any("؀" <= ch <= "ۿ" for ch in s)
        kw = dict(direction="rtl", language="ar") if rtl else {}
        try: w = d.textlength(s, font=f, **kw)
        except Exception: w = d.textlength(s, font=f)
        if w <= max_w: return f
        size = int(size * 0.94)
    return font(path, min_size, weight)

TONE_STEPS = [(50, 0.975), (100, 0.94), (200, 0.88), (300, 0.80), (400, 0.71),
              (500, 0.62), (600, 0.53), (700, 0.44), (800, 0.35), (900, 0.26), (950, 0.19)]

def tonal_scale(v):
    out = {}
    for step, L in TONE_STEPS:
        # chroma fades at extremes so tints/shades stay clean
        cf = 1 - (abs(L - 0.6) / 0.45) ** 2 * 0.75
        out[step] = to_hex(lch_to_rgb_clamped(L, v["C"] * max(cf, 0.12), v["H"]))
    return out

def mood(roles, items, chroma_px, lab_px):
    p = roles["primary"]
    warm = sum(x["w"] for x in items if x["C"] > 0.04 and (x["H"] < 110 or x["H"] > 330))
    cool = sum(x["w"] for x in items if x["C"] > 0.04 and 150 < x["H"] < 300)
    sat = float(np.percentile(chroma_px, 75))
    Ls = lab_px[:, 0]
    tonal = float(np.percentile(Ls, 95) - np.percentile(Ls, 5))
    hues = [x["H"] for x in items if x["C"] > 0.05]
    spread = max((hue_dist(a, b) for a in hues for b in hues), default=0)
    words = []
    words += ["دافي", "قريب"] if warm > cool * 1.3 else (["هادي", "واثق"] if cool > warm * 1.3 else ["متوازن"])
    words += ["حيوي", "جريء"] if sat > 0.12 else (["ناعم", "راقي"] if sat < 0.06 else ["طبيعي"])
    words += ["درامي"] if tonal > 0.6 else (["هوائي", "خفيف"] if tonal < 0.35 else [])
    words += ["متكامل الأضداد"] if spread > 140 else (["متناغم"] if spread < 60 else [])
    scheme = ("Complementary" if spread > 150 else "Split / Triadic" if spread > 100 else
              "Analogous" if spread > 30 else "Monochrome")
    return dict(words=words, warm=round(warm, 3), cool=round(cool, 3), saturation=round(sat, 3),
                tonal_range=round(tonal, 3), hue_spread=round(spread, 1), scheme=scheme)

# ---------------------------------------------------------------- motion signature
MOTIFS = {
    "wing":  dict(ar="جناح: رفرفة وانسياب", ease="cubic-bezier(0.22, 1.2, 0.36, 1)", desc="دخول بقوس وارتداد خفيف زي فرد الجناح، وبعده طفو هادي"),
    "wave":  dict(ar="موجة: تموّج متصل", ease="cubic-bezier(0.45, 0.05, 0.25, 1)", desc="عناصر بتدخل متتابعة على منحنى جيبي"),
    "bloom": dict(ar="تفتّح: من المركز للخارج", ease="cubic-bezier(0.16, 1, 0.3, 1)", desc="كبر من المركز مع تباطؤ طويل في الآخر"),
    "orbit": dict(ar="مدار: دوران وتمركز", ease="cubic-bezier(0.65, 0, 0.35, 1)", desc="حركة دائرية متزنة ودقيقة"),
    "pulse": dict(ar="نبض: إيقاع حاد", ease="cubic-bezier(0.7, 0, 0.2, 1)", desc="قطعات سريعة بإيقاع ثابت"),
}

def motion_signature(im, mask, motif):
    import cv2
    g = np.asarray(im.convert("L").resize((512, int(512 * im.height / im.width))), dtype=np.uint8)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3); gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.hypot(gx, gy)
    energy = float(np.clip(mag.mean() / 40.0, 0, 1))
    # dominant edge orientation (structure tensor) -> direction of travel for sweeps
    jxx, jyy, jxy = (gx * gx).sum(), (gy * gy).sum(), (gx * gy).sum()
    theta = 0.5 * math.degrees(math.atan2(2 * jxy, jxx - jyy))  # gradient direction
    flow = (theta + 90) % 180  # edges run perpendicular to gradient
    coherence = float(math.sqrt((jxx - jyy) ** 2 + 4 * jxy ** 2) / (jxx + jyy + 1e-6))
    # organic vs geometric: share of edge pixels that lie on long straight lines
    edges = cv2.Canny(g, 60, 160)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 60, minLineLength=40, maxLineGap=4)
    line_px = 0.0
    if lines is not None and len(lines):
        L4 = np.asarray(lines, dtype=np.float64).reshape(-1, 4)
        line_px = float(np.hypot(L4[:, 2] - L4[:, 0], L4[:, 3] - L4[:, 1]).sum())
    geometric = float(np.clip(line_px / (edges.astype(bool).sum() + 1) * 1.5, 0, 1))
    # subject silhouette: elongation + pointiness (beak, wing tips) -> overshoot amount
    elong, spiky = 1.0, 0.0
    if mask is not None:
        m = (cv2.resize(mask, (g.shape[1], g.shape[0])) > 0.5).astype(np.uint8)
        cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        if cnts:
            c = max(cnts, key=cv2.contourArea)
            if len(c) >= 5:
                (_, _), (MA, ma), ang = cv2.fitEllipse(c)
                elong = max(MA, ma) / max(1, min(MA, ma))
            hull = cv2.convexHull(c)
            spiky = float(np.clip(1 - cv2.contourArea(c) / max(1, cv2.contourArea(hull)), 0, 1))
    if motif == "auto":
        if mask is not None and spiky > 0.12 and geometric < 0.5:
            motif = "wing"
        elif geometric > 0.55:
            motif = "orbit" if energy < 0.5 else "pulse"
        elif coherence > 0.35:
            motif = "wave"
        else:
            motif = "bloom"
    base = int(round(720 - 380 * energy))  # calm image -> slower, busy -> snappier
    overshoot = round(float(np.clip(0.15 + spiky * 1.6 - geometric * 0.3, 0, 0.6)), 3)
    stagger = int(round(base * (0.10 + 0.08 * coherence)))
    info = dict(MOTIFS[motif])
    return dict(motif=motif, motif_ar=info["ar"], motif_desc=info["desc"], easing=info["ease"],
                ease_out="cubic-bezier(0.16, 1, 0.3, 1)", ease_in_out="cubic-bezier(0.65, 0, 0.35, 1)",
                dur_fast=int(base * 0.45), dur_base=base, dur_slow=int(base * 1.8), stagger=stagger,
                overshoot=overshoot, direction_deg=round(flow, 1), energy=round(energy, 3),
                coherence=round(coherence, 3), geometric=round(geometric, 3),
                elongation=round(elong, 2), spikiness=round(spiky, 3))

# ---------------------------------------------------------------- exports
def write_gpl(path, name, sw):
    with open(path, "w", encoding="utf-8") as f:
        f.write("GIMP Palette\nName: %s\nColumns: 6\n#\n" % name)
        for label, hx in sw:
            r, g, b = [int(hx[i:i + 2], 16) for i in (1, 3, 5)]
            f.write("%3d %3d %3d\t%s\n" % (r, g, b, label))

def write_ase(path, sw):
    blocks = b""
    for label, hx in sw:
        nm = (label + "\0").encode("utf-16-be")
        r, g, b = hex_to_rgb(hx)
        body = struct.pack(">H", len(nm) // 2) + nm + b"RGB " + struct.pack(">fffH", r, g, b, 2)
        blocks += struct.pack(">HI", 1, len(body)) + body
    with open(path, "wb") as f:
        f.write(b"ASEF" + struct.pack(">HHI", 1, 0, len(sw)) + blocks)

def write_css(path, roles, scales, mo):
    L = [":root {"]
    for r in ("primary", "secondary", "accent", "ground", "ink", "paper"):
        L.append("  --c-%s: %s;" % (r, roles[r]["hex"]))
    for r, sc in scales.items():
        for step, hx in sc.items():
            L.append("  --%s-%d: %s;" % (r, step, hx))
    L += ["  --ease-signature: %s;" % mo["easing"], "  --ease-out: %s;" % mo["ease_out"],
          "  --ease-in-out: %s;" % mo["ease_in_out"], "  --dur-fast: %dms;" % mo["dur_fast"],
          "  --dur-base: %dms;" % mo["dur_base"], "  --dur-slow: %dms;" % mo["dur_slow"],
          "  --stagger: %dms;" % mo["stagger"], "  --flow-angle: %sdeg;" % mo["direction_deg"], "}"]
    open(path, "w", encoding="utf-8").write("\n".join(L) + "\n")

# ---------------------------------------------------------------- drawing helpers
def font(path, size, weight=None):
    f = ImageFont.truetype(path, size)
    if weight:
        try: f.set_variation_by_name(weight)
        except Exception: pass
    return f

def text(d, xy, s, f, fill, anchor="la", rtl=None):
    if rtl is None:
        rtl = any("؀" <= ch <= "ۿ" for ch in s)
    kw = dict(direction="rtl", language="ar") if rtl else {}
    try:
        d.text(xy, s, font=f, fill=fill, anchor=anchor, **kw)
    except Exception:
        d.text(xy, s, font=f, fill=fill, anchor=anchor)

def readable_on(hx):
    rgb = hex_to_rgb(hx)
    return "#FFFFFF" if contrast(rgb, np.ones(3)) >= contrast(rgb, np.zeros(3)) else "#111111"

def cover(im, W, H):
    s = max(W / im.width, H / im.height)
    r = im.convert("RGB").resize((int(im.width * s + 1), int(im.height * s + 1)), Image.LANCZOS)
    x, y = (r.width - W) // 2, (r.height - H) // 2
    return r.crop((x, y, x + W, y + H))

def monogram(name, roles, size, progress=1.0, mo=None):
    """Brand mark: wing-arc emblem built from the palette + first letter."""
    S = size * 2
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    p, s, a = roles["primary"]["hex"], roles["secondary"]["hex"], roles["accent"]["hex"]
    cx = cy = S / 2
    R = S * 0.46
    t = progress
    d.ellipse([cx - R * t, cy - R * t, cx + R * t, cy + R * t], fill=p)
    # emblem in the upper half (letter sits below); shape follows the motion motif
    motif = (mo or {}).get("motif", "wing")
    tilt = float(np.clip(((mo or {}).get("direction_deg", 90) - 90) * 0.25, -18, 18))
    cols = (s, a, roles["paper"]["hex"])
    lw = max(4, int(S * 0.045))
    for i, col in enumerate(cols):
        k = max(0.0, min(1.0, t * 1.6 - i * 0.25))
        if k <= 0.01: continue
        if motif == "wave":
            y0 = cy - R * (0.55 - i * 0.17); amp = R * 0.08
            xs = np.linspace(cx - R * 0.62, cx - R * 0.62 + R * 1.24 * k, 40)
            d.line([(x, y0 + amp * math.sin((x - cx) / R * 7 + i)) for x in xs], fill=col, width=lw, joint="curve")
        elif motif == "bloom":
            n = 5; rr = R * (0.2 - i * 0.04) * k
            for j in range(n):
                ang = math.radians(200 + j * 35 + i * 8)
                px, py = cx + math.cos(ang) * R * (0.52 - i * 0.14), cy * 0.98 + math.sin(ang) * R * (0.52 - i * 0.14)
                d.ellipse([px - rr, py - rr, px + rr, py + rr], fill=col)
        elif motif == "orbit":
            rr = R * (0.62 - i * 0.16)
            d.arc([cx - rr, cy - rr * 0.9 - R * 0.05, cx + rr, cy + rr * 0.9 - R * 0.05], 180 + tilt, 180 + tilt + 180 * k, fill=col, width=lw)
            ang = math.radians(180 + tilt + 180 * k)
            dot = lw * 1.1
            px, py = cx + math.cos(ang) * rr, cy - R * 0.05 + math.sin(ang) * rr * 0.9
            d.ellipse([px - dot, py - dot, px + dot, py + dot], fill=col)
        elif motif == "pulse":
            bw = R * 0.16
            for j in range(3):
                hgt = R * (0.25 + 0.3 * ((j + i) % 3) / 2) * k
                x0 = cx - R * 0.45 + (i * 3 + j) * R * 0.11
                d.rounded_rectangle([x0, cy - hgt, x0 + bw * 0.5, cy], int(bw * 0.2), fill=col)
        else:  # wing: feather arcs over the top
            rr = R * (0.78 - i * 0.17)
            span = 170 * k
            mid = 270 + tilt
            d.arc([cx - rr, cy - rr + R * 0.12, cx + rr, cy + rr + R * 0.12], mid - span / 2, mid + span / 2, fill=col, width=lw)
    letter = name.strip()[0] if name.strip() else "•"
    if t > 0.55:
        f = font(CAIRO, int(S * 0.24), "Black")
        alpha = int(255 * min(1, (t - 0.55) / 0.45))
        tmp = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        text(ImageDraw.Draw(tmp), (cx, cy * 1.42), letter, f, readable_on(p), anchor="mm")
        tmp.putalpha(Image.fromarray((np.asarray(tmp.split()[-1]) * (alpha / 255)).astype(np.uint8)))
        img = Image.alpha_composite(img, tmp)
    return img.resize((size, size), Image.LANCZOS)

# ---------------------------------------------------------------- brand board
ROLE_AR = dict(primary="الأساسي", secondary="الثانوي", accent="لون الإبراز", ground="الأرضية", ink="الحبر", paper="الورق")
ROLE_SHARE = dict(primary="60%", secondary="25%", accent="10%", ground="—", ink="نصوص", paper="خلفية")

def brand_board(path, im, name, tagline, roles, scales, mo, md):
    W, H = 2400, 1500
    paper, ink = roles["paper"]["hex"], roles["ink"]["hex"]
    B = Image.new("RGB", (W, H), paper)
    d = ImageDraw.Draw(B)
    # source photo
    ph = cover(im, 760, 760)
    B.paste(ph, (W - 80 - 760, 80))
    # header (RTL on right side, beside the photo)
    xR = W - 80 - 760 - 60
    maxw = xR - (80 + 300 + 40)
    tcol = text_color(roles, "paper", "primary", 4.5)
    fN = fit_font(d, name, CAIRO, 120, maxw, "Black")
    bb = d.textbbox((xR, 90), name, font=fN, anchor="ra", direction="rtl", language="ar")
    y = bb[3] + 22
    if tagline:
        fT = fit_font(d, tagline, CAIRO, 46, maxw, "Medium")
        text(d, (xR, y), tagline, fT, tcol, anchor="ra")
        y = d.textbbox((xR, y), tagline, font=fT, anchor="ra", direction="rtl", language="ar")[3] + 18
    text(d, (xR, min(max(y, 300), 378)), " · ".join(md["words"]), fit_font(d, " · ".join(md["words"]), CAIRO, 34, maxw), ink, anchor="ra")
    text(d, (xR, 90), name, fN, ink, anchor="ra")
    mg = monogram(name, roles, 300, 1.0, mo)
    B.paste(mg, (80, 80), mg)
    # role swatches (big)
    order = ["primary", "secondary", "accent", "ground", "ink", "paper"]
    sx, sy, sw_, sh_ = 80, 440, 205, 380
    xx = xR
    for r in order:
        v = roles[r]
        x0 = xx - sw_
        d.rounded_rectangle([x0, sy, xx, sy + sh_], 22, fill=v["hex"], outline=ink if r == "paper" else None, width=2)
        fg = readable_on(v["hex"])
        text(d, (xx - 18, sy + 22), ROLE_AR[r], font(CAIRO, 34, "Bold"), fg, anchor="ra")
        nm = v["ar"]; fs = 24
        while fs > 14 and d.textlength(nm, font=font(CAIRO, fs), direction="rtl", language="ar") > sw_ - 30: fs -= 1
        text(d, (xx - 18, sy + 70), nm, font(CAIRO, fs, "Regular"), fg, anchor="ra")
        text(d, (x0 + 18, sy + sh_ - 88), v["hex"], font(CAIRO, 30, "Bold"), fg, rtl=False)
        text(d, (x0 + 18, sy + sh_ - 48), ROLE_SHARE[r], font(CAIRO, 22, "Regular"), fg, anchor="la")
        xx = x0 - 18
    # tonal scales
    ty = 880
    for r in ("primary", "secondary", "accent"):
        steps = list(scales[r].items())
        cw = (W - 160) / len(steps)
        for i, (st, hx) in enumerate(steps):
            x0 = 80 + i * cw
            d.rectangle([x0, ty, x0 + cw, ty + 92], fill=hx)
            text(d, (x0 + 10, ty + 8), str(st), font(CAIRO, 20, "Bold"), readable_on(hx), rtl=False)
            text(d, (x0 + 10, ty + 62), hx, font(CAIRO, 18, "Regular"), readable_on(hx), rtl=False)
        ty += 104
    # bottom: typography + UI sample + motion card
    by = 1210
    text(d, (W - 80, by), "أبجد هوز — Aa 123", font(CAIRO, 64, "Bold"), ink, anchor="ra")
    text(d, (W - 80, by + 95), "Cairo للعناوين والواجهات · Amiri للاقتباسات والفخامة", font(CAIRO, 28, "Regular"), ink, anchor="ra")
    text(d, (W - 80, by + 145), "قول اللي يشبهك.", font(AMIRI, 52), tcol, anchor="ra")
    # buttons
    bx = 80
    p_hex, a_hex = roles["primary"]["hex"], roles["accent"]["hex"]
    for lbl, bgc in (("ابدأ الآن", p_hex), ("اكتشف", a_hex)):
        d.rounded_rectangle([bx, by, bx + 260, by + 84], 42, fill=bgc)
        text(d, (bx + 130, by + 40), lbl, font(CAIRO, 34, "Bold"), readable_on(bgc), anchor="mm")
        bx += 290
    d.rounded_rectangle([bx, by, bx + 260, by + 84], 42, outline=ink, width=3)
    text(d, (bx + 130, by + 40), "المزيد", font(CAIRO, 34, "Bold"), ink, anchor="mm")
    # motion card
    my = by + 120
    text(d, (80, my), "الحركة: %s" % mo["motif_ar"], font(CAIRO, 32, "Bold"), ink, anchor="la")
    text(d, (80, my + 50), "%s  ·  %dms  ·  stagger %dms  ·  flow %s deg" % (mo["easing"], mo["dur_base"], mo["stagger"], mo["direction_deg"]),
         font(CAIRO, 22, "Regular"), ink, rtl=False)
    # easing curve plot
    cx0, cy0, cwid = 1000, by + 175, 170
    pts = [(cx0 + t * cwid, cy0 - bezier_y(mo["easing"], t) * 150) for t in np.linspace(0, 1, 60)]
    d.line([(cx0, cy0), (cx0 + cwid, cy0)], fill=ink, width=1)
    d.line(pts, fill=a_hex, width=5)
    B.save(path, quality=95)

def parse_bezier(s):
    nums = [float(x) for x in s[s.index("(") + 1:s.index(")")].split(",")]
    return nums

def bezier_y(spec, t):
    x1, y1, x2, y2 = parse_bezier(spec) if isinstance(spec, str) else spec
    # solve x(u)=t by bisection
    lo, hi = 0.0, 1.0
    for _ in range(30):
        u = (lo + hi) / 2
        x = 3 * (1 - u) ** 2 * u * x1 + 3 * (1 - u) * u ** 2 * x2 + u ** 3
        if x < t: lo = u
        else: hi = u
    u = (lo + hi) / 2
    return 3 * (1 - u) ** 2 * u * y1 + 3 * (1 - u) * u ** 2 * y2 + u ** 3

def swatch_strip(path, roles):
    order = ["primary", "secondary", "accent", "ground", "ink", "paper"]
    W, H = 1800, 360
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    w = W / len(order)
    for i, r in enumerate(order):
        hx = roles[r]["hex"]
        x0 = W - (i + 1) * w
        d.rectangle([x0, 0, x0 + w, H], fill=hx)
        text(d, (x0 + w / 2, H / 2 - 30), ROLE_AR[r], font(CAIRO, 40, "Bold"), readable_on(hx), anchor="mm")
        text(d, (x0 + w / 2, H / 2 + 34), hx, font(CAIRO, 32, "Regular"), readable_on(hx), anchor="mm", rtl=False)
    im.save(path)

# ---------------------------------------------------------------- motion video
def ease(mo, t, kind="sig"):
    t = float(np.clip(t, 0, 1))
    spec = mo["easing"] if kind == "sig" else mo["ease_out"] if kind == "out" else mo["ease_in_out"]
    return bezier_y(spec, t)

def render_video(path, im, name, tagline, roles, mo, aspect="16:9", seconds=8.0, fps=30):
    W, H = {"16:9": (1920, 1080), "9:16": (1080, 1920), "1:1": (1080, 1080)}[aspect]
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return "ffmpeg missing"
    photo = cover(im, W, H)
    paper = roles["paper"]["hex"]; ink = roles["ink"]["hex"]
    cols = [roles[r]["hex"] for r in ("primary", "secondary", "accent", "ground", "ink")]
    N = int(seconds * fps)
    ang = math.radians(mo["direction_deg"])
    proc = subprocess.Popen([ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", "%dx%d" % (W, H), "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "slow",
                             "-crf", "17", "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709",
                             "-color_trc", "bt709", "-movflags", "+faststart", path], stdin=subprocess.PIPE)
    big = min(W, H)
    f_hex = font(CAIRO, int(big * 0.028), "Bold")
    f_role = font(CAIRO, int(big * 0.03), "Bold")
    stg = mo["stagger"] / 1000
    T1, T2, T3 = seconds * 0.22, seconds * 0.55, seconds * 0.85
    vertical = H >= W  # square uses the stacked (centred) layout too
    _d = ImageDraw.Draw(Image.new("L", (8, 8)))
    f_name = fit_font(_d, name, CAIRO, int(big * 0.12), W * (0.86 if vertical else 0.5), "Black")
    f_tag = fit_font(_d, tagline or "-", CAIRO, int(big * 0.04), W * (0.86 if vertical else 0.5), "Medium")
    tcol = text_color(roles, "paper", "primary", 4.5)
    def masked(fr, xy, s_, f_, color, anchor, alpha):
        m = Image.new("L", (W, H), 0)
        text(ImageDraw.Draw(m), xy, s_, f_, 255, anchor=anchor)
        if alpha < 1: m = m.point(lambda v: int(v * alpha))
        fr.paste(color, (0, 0), m)
    for fi in range(N):
        t = fi / fps
        fr = Image.new("RGB", (W, H), paper)
        d = ImageDraw.Draw(fr)
        if t < T1 + 0.6:
            # scene 1: photo slowly pushes in, then palette bands wipe across along image flow
            z = 1 + 0.06 * ease(mo, t / (T1 + 0.6), "io")
            pw, ph = int(W * z), int(H * z)
            p2 = photo.resize((pw, ph), Image.BILINEAR).crop(((pw - W) // 2, (ph - H) // 2, (pw - W) // 2 + W, (ph - H) // 2 + H))
            fr.paste(p2)
            n = len(cols)
            for i, c in enumerate(cols):
                k = ease(mo, (t - T1 * 0.45 - i * stg) / (mo["dur_base"] / 1000 * 1.4), "sig")
                if k <= 0: continue
                if vertical:
                    bh = H / n; y0 = i * bh
                    d.rectangle([0, y0, W * k, y0 + bh + 1], fill=c)
                else:
                    bw = W / n; x0 = W - (i + 1) * bw
                    d.rectangle([x0, H - H * k - math.sin(ang) * 0, x0 + bw + 1, H], fill=c)
        elif t < T2:
            # scene 2: bands settle into labelled swatches (cards) with signature easing
            n = len(cols)
            roles_order = ("primary", "secondary", "accent", "ground", "ink")
            for i, r in enumerate(roles_order):
                k = ease(mo, (t - T1 - 0.6 - i * stg) / (mo["dur_base"] / 1000 * 1.3), "sig")
                hx = roles[r]["hex"]
                if vertical:
                    bh = H / n; full = [0, i * bh, W, (i + 1) * bh + 1]
                    tgt = [W * 0.1, H * 0.12 + i * H * 0.15, W * 0.9, H * 0.12 + i * H * 0.15 + H * 0.12]
                else:
                    bw = W / n; full = [W - (i + 1) * bw, 0, W - i * bw + 1, H]
                    cw = W * 0.15; gap = W * 0.025; tot = n * cw + (n - 1) * gap; xs = W - (W - tot) / 2 - (i + 1) * cw - i * gap
                    tgt = [xs, H * 0.24, xs + cw, H * 0.76]
                box = [full[j] + (tgt[j] - full[j]) * k for j in range(4)]
                rad = int(28 * min(1, max(0, k)))
                d.rounded_rectangle(box, rad, fill=hx)
                if k > 0.7:
                    fg = readable_on(hx)
                    cxm = (box[0] + box[2]) / 2
                    text(d, (cxm, box[1] + (box[3] - box[1]) * 0.18), ROLE_AR[r], f_role, fg, anchor="mm")
                    text(d, (cxm, box[3] - (box[3] - box[1]) * 0.12), hx, f_hex, fg, anchor="mm", rtl=False)
        else:
            # scene 3: mark draws on (arcs = feathers), name rises, tagline follows; end card holds
            fr.paste(Image.new("RGB", (W, H), paper))
            k = ease(mo, (t - T2) / (mo["dur_slow"] / 1000 * 1.2), "sig")
            ms = int(big * (0.5 if H > W * 1.2 else 0.36))
            mg = monogram(name, roles, ms, max(0.001, min(1, k)), mo)
            if vertical:
                block = ms + big * 0.42 + (big * 0.08 if H > W * 1.2 else 0)
                mx, my = (W - ms) // 2, int((H - block) / 2)
                nx, ny = W / 2, my + ms + big * (0.25 if H > W * 1.2 else 0.17)
            else:
                mx, my = int(W * 0.62), (H - ms) // 2
                nx, ny = W * 0.56, H / 2 - big * 0.05
            fr.paste(mg, (mx, my), mg)
            kn = ease(mo, (t - T2 - 0.35) / (mo["dur_base"] / 1000 * 1.4), "out")
            if kn > 0:
                al = min(1, kn * 1.3)
                off = (1 - kn) * big * 0.08
                masked(fr, (nx, ny + off), name, f_name, ink, "ms" if vertical else "rs", al)
                kt = ease(mo, (t - T2 - 0.35 - 3 * stg) / (mo["dur_base"] / 1000 * 1.4), "out")
                if tagline and kt > 0:
                    masked(fr, (nx, ny + big * 0.09 + (1 - kt) * big * 0.05), tagline, f_tag, tcol,
                           "ma" if vertical else "ra", min(1, kt * 1.3))
                ku = ease(mo, (t - T2 - 0.6) / (mo["dur_base"] / 1000), "io")
                if ku > 0:
                    lw = big * 0.28 * ku
                    y = ny + big * 0.2
                    dd = ImageDraw.Draw(fr)
                    if vertical: dd.rectangle([nx - lw / 2, y, nx + lw / 2, y + 8], fill=roles["accent"]["hex"])
                    else: dd.rectangle([nx - lw, y, nx, y + 8], fill=roles["accent"]["hex"])
            # thin palette bar on the end card
            if t > T3 - 0.4:
                kb = ease(mo, (t - T3 + 0.4) / 0.6, "out")
                bw = W / len(cols)
                for i, c in enumerate(cols):
                    d2 = ImageDraw.Draw(fr)
                    d2.rectangle([W - (i + 1) * bw, H - 22 * kb, W - i * bw + 1, H], fill=c)
        proc.stdin.write(fr.tobytes())
    proc.stdin.close()
    proc.wait()
    return "ok" if proc.returncode == 0 else "ffmpeg error %s" % proc.returncode

# ---------------------------------------------------------------- html
def write_html(path, name, tagline, roles, scales, mo, md, img_rel):
    css = open(os.path.join(os.path.dirname(path), "tokens.css"), encoding="utf-8").read()
    cards = "".join(
        '<div class="sw" style="--i:%d;background:%s;color:%s"><b>%s</b><span>%s</span><code>%s</code></div>'
        % (i, roles[r]["hex"], readable_on(roles[r]["hex"]), ROLE_AR[r], roles[r]["ar"], roles[r]["hex"])
        for i, r in enumerate(("primary", "secondary", "accent", "ground", "ink", "paper")))
    tones = "".join('<div class="row">' + "".join('<i style="background:%s" title="%s %s"></i>' % (hx, r, st) for st, hx in scales[r].items()) + "</div>"
                    for r in ("primary", "secondary", "accent"))
    p, s, a, ink, paper = (roles[r]["hex"] for r in ("primary", "secondary", "accent", "ink", "paper"))
    html = f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{name} — هوية</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;700;900&family=Amiri:wght@700&display=swap" rel="stylesheet">
<style>{css}
*{{box-sizing:border-box;margin:0}} body{{font-family:Cairo,system-ui,sans-serif;background:var(--c-paper);color:var(--c-ink);overflow-x:hidden}}
.hero{{min-height:100vh;display:grid;grid-template-columns:1.1fr .9fr;align-items:center;gap:4vw;padding:6vw}}
.hero img{{width:100%;aspect-ratio:1;object-fit:cover;border-radius:28px;animation:rise var(--dur-slow) var(--ease-out) both}}
h1{{font-size:clamp(48px,8vw,128px);font-weight:900;line-height:1;animation:rise var(--dur-slow) var(--ease-signature) both .2s}}
.tag{{font-size:clamp(20px,2.4vw,34px);color:{text_color(roles)};margin-top:.6em;animation:rise var(--dur-slow) var(--ease-signature) both calc(.2s + var(--stagger)*2)}}
.mark{{width:160px;height:160px;margin-bottom:28px}}
.mark circle{{transform-origin:50% 50%;animation:pop var(--dur-slow) var(--ease-signature) both}}
.mark path{{stroke-dasharray:300;stroke-dashoffset:300;animation:draw var(--dur-slow) var(--ease-out) forwards}}
.mark path:nth-of-type(2){{animation-delay:calc(var(--stagger)*1)}} .mark path:nth-of-type(3){{animation-delay:calc(var(--stagger)*2)}}
.btns{{display:flex;gap:14px;margin-top:36px;animation:rise var(--dur-slow) var(--ease-signature) both calc(.2s + var(--stagger)*4)}}
.btn{{border:0;border-radius:999px;padding:16px 34px;font:700 20px Cairo;cursor:pointer;transition:transform var(--dur-fast) var(--ease-signature),box-shadow var(--dur-fast) var(--ease-out)}}
.btn:hover{{transform:translateY(-4px) scale(1.04);box-shadow:0 14px 30px -12px var(--c-primary)}}
.b1{{background:var(--c-primary);color:{readable_on(p)}}} .b2{{background:var(--c-accent);color:{readable_on(a)}}}
section{{padding:6vw}} h2{{font-size:40px;margin-bottom:24px}}
.sws{{display:grid;grid-template-columns:repeat(6,1fr);gap:14px}}
.sw{{border-radius:22px;padding:20px;min-height:260px;display:flex;flex-direction:column;gap:6px;opacity:0;transform:translateY(40px) rotate(calc(var(--flow-angle) / 30));
     transition:transform var(--dur-slow) var(--ease-signature),opacity var(--dur-base) var(--ease-out);transition-delay:calc(var(--i)*var(--stagger))}}
.sw.in{{opacity:1;transform:none}} .sw b{{font-size:24px}} .sw code{{margin-top:auto;font-size:18px;direction:ltr;text-align:left}}
.sw:hover{{transform:translateY(-8px) scale(1.03)}}
.row{{display:flex;height:64px;margin-bottom:8px;border-radius:14px;overflow:hidden}} .row i{{flex:1}}
.motion{{display:grid;grid-template-columns:1fr 1fr;gap:28px;align-items:center}}
.track{{height:90px;border-radius:18px;background:color-mix(in oklab,var(--c-ground) 25%,var(--c-paper));position:relative;overflow:hidden}}
.dot{{position:absolute;top:21px;right:20px;width:48px;height:48px;border-radius:50%;background:var(--c-accent);animation:fly calc(var(--dur-slow)*1.6) var(--ease-signature) infinite alternate}}
@keyframes fly{{to{{right:calc(100% - 68px)}}}}
@keyframes rise{{from{{opacity:0;transform:translateY(60px)}}}} @keyframes pop{{from{{transform:scale(0)}}}} @keyframes draw{{to{{stroke-dashoffset:0}}}}
.facts{{font-size:18px;line-height:2}} code{{font-family:ui-monospace,Consolas,monospace;direction:ltr;unicode-bidi:isolate}}
.sw:last-child{{border:2px solid var(--c-ink)}}
@media (max-width:900px){{.hero,.motion{{grid-template-columns:1fr}} .sws{{grid-template-columns:repeat(2,1fr)}}}}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important;transition:none!important}} .sw{{opacity:1;transform:none}}}}
</style></head><body>
<div class="hero"><div>
<svg class="mark" viewBox="0 0 100 100"><circle cx="50" cy="50" r="46" fill="{p}"/>
<path d="M18 62 Q50 8 82 62" fill="none" stroke="{s}" stroke-width="5" stroke-linecap="round"/>
<path d="M28 66 Q50 26 72 66" fill="none" stroke="{a}" stroke-width="5" stroke-linecap="round"/>
<path d="M38 70 Q50 44 62 70" fill="none" stroke="{paper}" stroke-width="5" stroke-linecap="round"/></svg>
<h1>{name}</h1><p class="tag">{tagline}</p>
<div class="btns"><button class="btn b1">ابدأ الآن</button><button class="btn b2">اكتشف</button></div></div>
<img src="{img_rel}" alt="مصدر الألوان"></div>
<section><h2>الألوان بالأدوار</h2><div class="sws">{cards}</div></section>
<section><h2>درجات الألوان</h2>{tones}</section>
<section class="motion"><div><h2>لغة الحركة: {mo['motif_ar']}</h2>
<p class="facts">{mo['motif_desc']}<br>منحنى التوقيع: <code>{mo['easing']}</code><br>
المدد: <code>{mo['dur_fast']} / {mo['dur_base']} / {mo['dur_slow']}ms</code> · التتابع: <code>{mo['stagger']}ms</code><br>
اتجاه الانسياب من الصورة: <code>{mo['direction_deg']}°</code> · الطاقة: <code>{mo['energy']}</code><br>
المزاج: {' · '.join(md['words'])} — نظام: {md['scheme']}</p></div>
<div class="track"><div class="dot"></div></div></section>
<script>const io=new IntersectionObserver(es=>es.forEach(e=>e.isIntersecting&&e.target.classList.add('in')),{{threshold:.2}});document.querySelectorAll('.sw').forEach(x=>io.observe(x));</script>
</body></html>"""
    open(path, "w", encoding="utf-8").write(html)

# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--name", default="هوية")
    ap.add_argument("--tagline", default="")
    ap.add_argument("--out", default=None)
    ap.add_argument("--subject", default="auto", choices=["auto", "on", "off"])
    ap.add_argument("--motif", default="auto", choices=["auto"] + list(MOTIFS))
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--video", default="16:9", choices=["16:9", "9:16", "1:1", "none"])
    ap.add_argument("--seconds", type=float, default=8.0)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--set", action="append", default=[], help="override a role: primary=#1E6FA8")
    a = ap.parse_args()
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.image)), "identity_" + os.path.splitext(os.path.basename(a.image))[0])
    os.makedirs(out, exist_ok=True)

    im = load_image(a.image)
    mask, mask_info = subject_mask(im, a.subject)
    if mask is not None:
        Image.fromarray((mask * 255).astype(np.uint8)).save(os.path.join(out, "subject_mask.png"))
    cents, wts, bg, lab_px, chroma_px = extract(im, mask, a.k)
    roles, items = assign_roles(cents, wts, bg, float(np.percentile(chroma_px, 95)))
    for ov in a.set:  # manual override, e.g. --set accent=#FF7A1A
        r, hx = ov.split("=")
        L, C, H = lab_to_lch(rgb_to_oklab(hex_to_rgb(hx)))
        roles[r].update(L=L, C=C, H=H, hex=hx.upper(), synthetic=False, override=True)
        roles[r]["ar"], roles[r]["en"] = color_name(L, C, H)
    scales = {r: tonal_scale(roles[r]) for r in ("primary", "secondary", "accent", "ground")}
    md = mood(roles, items, chroma_px, lab_px)
    mo = motion_signature(im, mask, a.motif)

    # contrast matrix (WCAG 2.x)
    pairs = []
    for fg in ("ink", "paper", "primary", "accent"):
        for bgr in ("paper", "ink", "primary", "secondary", "accent", "ground"):
            if fg == bgr: continue
            c = contrast(hex_to_rgb(roles[fg]["hex"]), hex_to_rgb(roles[bgr]["hex"]))
            pairs.append(dict(fg=fg, bg=bgr, ratio=round(c, 2), AA_text=c >= 4.5, AA_large=c >= 3))

    sw = [(ROLE_AR[r] + " " + roles[r]["hex"], roles[r]["hex"]) for r in ROLE_AR]
    for r, sc in scales.items():
        sw += [("%s-%d" % (r, st), hx) for st, hx in sc.items()]
    write_gpl(os.path.join(out, "palette.gpl"), a.name, sw)
    write_ase(os.path.join(out, "palette.ase"), sw)
    write_css(os.path.join(out, "tokens.css"), roles, scales, mo)
    clean = {r: {k: (round(float(v), 4) if isinstance(v, (float, np.floating)) else v) for k, v in d.items() if k not in ("lab", "src", "vivid")} for r, d in roles.items()}
    raw = []
    for x in items:
        hx = to_hex(np.clip(oklab_to_rgb(x["lab"]), 0, 1))
        raw.append(dict(hex=hx, share=round(x["w"], 4), L=round(x["L"], 3), C=round(x["C"], 3), H=round(x["H"], 1)))
    data = dict(name=a.name, tagline=a.tagline, source=os.path.abspath(a.image), subject=mask_info,
                roles=clean, scales={r: {str(k): v for k, v in sc.items()} for r, sc in scales.items()},
                extracted=raw, mood=md, motion=mo, contrast=pairs)
    json.dump(data, open(os.path.join(out, "palette.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    tokens = {"color": {r: {"$value": roles[r]["hex"], "$type": "color"} for r in roles},
              "duration": {k: {"$value": "%dms" % mo[k], "$type": "duration"} for k in ("dur_fast", "dur_base", "dur_slow", "stagger")},
              "cubicBezier": {k: {"$value": parse_bezier(mo[k]), "$type": "cubicBezier"} for k in ("easing", "ease_out", "ease_in_out")}}
    json.dump(tokens, open(os.path.join(out, "tokens.json"), "w", encoding="utf-8"), indent=2)

    # copy source next to html
    src_copy = os.path.join(out, "source" + os.path.splitext(a.image)[1].lower())
    im.convert("RGB").save(os.path.splitext(src_copy)[0] + ".jpg", quality=92)
    brand_board(os.path.join(out, "brand_board.png"), im, a.name, a.tagline, roles, scales, mo, md)
    swatch_strip(os.path.join(out, "swatches.png"), roles)
    write_html(os.path.join(out, "identity.html"), a.name, a.tagline, roles, scales, mo, md, "source.jpg")
    vid = "skipped"
    if a.video != "none":
        vid = render_video(os.path.join(out, "motion.mp4"), im, a.name, a.tagline, roles, mo, a.video, a.seconds, a.fps)

    rep = ["# هوية: %s" % a.name, "", "المصدر: `%s` · فصل الموضوع: %s" % (a.image, mask_info), "",
           "| الدور | اللون | الاسم | مُستخرج؟ |", "|---|---|---|---|"]
    for r in ROLE_AR:
        rep.append("| %s | `%s` | %s / %s | %s |" % (ROLE_AR[r], roles[r]["hex"], roles[r]["ar"], roles[r]["en"],
                                                 "مُولَّد" if roles[r].get("synthetic") else ("يدوي" if roles[r].get("override") else "من الصورة")))
    rep += ["", "**المزاج:** %s — نظام الألوان: %s" % (" · ".join(md["words"]), md["scheme"]), "",
            "**الحركة:** %s — `%s` — %d/%d/%dms، تتابع %dms، اتجاه %s°" % (mo["motif_ar"], mo["easing"], mo["dur_fast"], mo["dur_base"], mo["dur_slow"], mo["stagger"], mo["direction_deg"]),
            "", "**تباين نجح AA للنص العادي (4.5+):** " + ", ".join("%s/%s %.1f" % (p["fg"], p["bg"], p["ratio"]) for p in pairs if p["AA_text"]),
            "", "الفيديو: %s" % vid]
    open(os.path.join(out, "report.md"), "w", encoding="utf-8").write("\n".join(rep) + "\n")
    print(json.dumps(dict(out=out, subject=mask_info, mode=roles_mode[0], roles={r: roles[r]["hex"] + (" (synthetic)" if roles[r].get("synthetic") else "") for r in roles},
                          motif=mo["motif"], easing=mo["easing"], dur=mo["dur_base"], video=vid), ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
