"""Helpers of runners/fam_w3_13.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from pathlib import Path
import site as _site
from .core import fx
import json
import math
import os
import re
import subprocess
import zipfile


FREESERIF = Path("/usr/share/fonts/truetype/freefont/FreeSerif.ttf")


DEJAVU = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")


DEJAVU_B = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")


MONO = Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")


def _np():
    import numpy as np
    return np


def write_json(wd, name, obj):
    p = Path(wd) / name
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    return p


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def hexc(c):
    return "#%02x%02x%02x" % tuple(int(round(max(0, min(255, v)))) for v in c[:3])


def rel_lum(c):
    def ch(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(v) for v in (rgb(c) if isinstance(c, str) else c))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((rel_lum(a), rel_lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def save_png(arr, path):
    from PIL import Image
    Image.fromarray(_np().clip(arr, 0, 255).round().astype("uint8")).save(path)
    return Path(path)


def load_png(path, mode="RGB"):
    from PIL import Image
    return _np().asarray(Image.open(path).convert(mode)).astype(float)


def write_video(path, frames, fps=30):
    """Encode numpy frames losslessly (libx264rgb qp 0) so pixel measurements read back exactly."""
    np = _np()
    frames = list(frames)
    h, w = frames[0].shape[:2]
    p = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", "%dx%d" % (w, h), "-r", str(fps), "-i", "-", "-c:v", "libx264rgb", "-qp", "0",
                          "-preset", "ultrafast", str(path)], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    for f in frames:
        p.stdin.write(np.clip(f, 0, 255).round().astype("uint8").tobytes())
    p.stdin.close()
    if p.wait():
        raise RuntimeError("ffmpeg encode failed: %s" % p.stderr.read().decode(errors="replace")[-300:])
    return Path(path)


def read_video(path):
    np = _np()
    st = [s for s in fx.probe(path)["streams"] if s.get("codec_type") == "video"][0]
    w, h = int(st["width"]), int(st["height"])
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, timeout=120, stdin=subprocess.DEVNULL).stdout
    return np.frombuffer(out, dtype=np.uint8).reshape(-1, h, w, 3).astype(float)


def font(path=DEJAVU, size=24):
    from PIL import ImageFont
    return ImageFont.truetype(str(path), size, layout_engine=ImageFont.Layout.RAQM)


def _figma_file():
    """A fixture shaped like GET /v1/files/:key (document tree + styles map)."""
    def frame(i, name, color, x, spacing):
        return {"id": "1:%d" % i, "name": name, "type": "FRAME", "absoluteBoundingBox": {"x": x, "y": 0, "width": 360, "height": 640},
                "layoutMode": "VERTICAL", "itemSpacing": spacing, "paddingLeft": 24, "paddingTop": 32,
                "fills": [{"type": "SOLID", "color": color}], "styles": {"fill": "S:bg%d" % i},
                "children": [{"id": "1:%d0" % i, "name": "Title", "type": "TEXT", "characters": "Hello",
                              "style": {"fontFamily": "Cairo", "fontSize": 32, "fontWeight": 800, "lineHeightPx": 40},
                              "styles": {"text": "S:h1"}, "fills": [{"type": "SOLID", "color": {"r": 1, "g": 1, "b": 1, "a": 1}}]}]}
    return {"name": "KOSIF UI", "version": "42",
            "document": {"id": "0:0", "type": "DOCUMENT", "children": [
                {"id": "0:1", "name": "Mobile", "type": "CANVAS", "children": [
                    frame(1, "Home", {"r": 0.043, "g": 0.063, "b": 0.125, "a": 1}, 0, 16),
                    frame(2, "Offer", {"r": 0.906, "g": 0.714, "b": 0.353, "a": 1}, 400, 24)]},
                {"id": "0:2", "name": "Icons", "type": "CANVAS", "children": [
                    {"id": "2:%d" % i, "name": "icon-%02d" % i, "type": "COMPONENT", "absoluteBoundingBox": {"x": i * 30, "y": 0, "width": 24, "height": 24}}
                    for i in range(23)]}]},
            "styles": {"S:bg1": {"name": "color/bg", "styleType": "FILL"}, "S:bg2": {"name": "color/accent", "styleType": "FILL"},
                       "S:h1": {"name": "type/h1", "styleType": "TEXT"}}}


def parse_figma_url(url):
    m = re.match(r"https://(?:www\.)?figma\.com/(?:file|design|proto)/([A-Za-z0-9]+)/[^?]*(?:\?(.*))?$", url)
    if not m:
        raise ValueError("not a figma url")
    q = dict(kv.split("=", 1) for kv in (m.group(2) or "").split("&") if "=" in kv)
    node = q.get("node-id")
    return m.group(1), (node.replace("-", ":") if node else None)


def render_ar_lines(path, lines, size=56, fnt=FREESERIF, width=1100):
    from PIL import Image, ImageDraw
    f = font(fnt, size)
    im = Image.new("L", (width, 40 + int(size * 1.8) * len(lines)), 255)
    d = ImageDraw.Draw(im)
    for i, ln in enumerate(lines):
        d.text((width - 30, 20 + i * int(size * 1.8)), ln, font=f, fill=0, direction="rtl", language="ar", anchor="ra")
    im.save(path)
    return Path(path)


_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def tesseract(img, lang="ara", psm=6):
    env = dict(os.environ, OMP_THREAD_LIMIT="1")
    done = subprocess.run(["tesseract", str(img), "-", "-l", lang, "--psm", str(psm)], capture_output=True, text=True,
                          timeout=30, env=env, stdin=subprocess.DEVNULL)
    if done.returncode:
        raise RuntimeError("tesseract failed: " + done.stderr[-300:])
    return done.stdout


_BW_PAIRS = [("ء", "'"), ("آ", "|"), ("أ", ">"), ("ؤ", "&"), ("إ", "<"), ("ئ", "}"), ("ا", "A"), ("ب", "b"), ("ة", "p"),
             ("ت", "t"), ("ث", "v"), ("ج", "j"), ("ح", "H"), ("خ", "x"), ("د", "d"), ("ذ", "*"), ("ر", "r"), ("ز", "z"),
             ("س", "s"), ("ش", "$"), ("ص", "S"), ("ض", "D"), ("ط", "T"), ("ظ", "Z"), ("ع", "E"), ("غ", "g"), ("ـ", "_"),
             ("ف", "f"), ("ق", "q"), ("ك", "k"), ("ل", "l"), ("م", "m"), ("ن", "n"), ("ه", "h"), ("و", "w"), ("ى", "Y"),
             ("ي", "y"), ("\u064b", "F"), ("\u064c", "N"), ("\u064d", "K"), ("\u064e", "a"), ("\u064f", "u"), ("\u0650", "i"),
             ("\u0651", "~"), ("\u0652", "o"), ("\u0670", "`"), ("\u0671", "{")]


_BW = dict(_BW_PAIRS)


_BW_INV = {v: k for k, v in _BW.items()}


def ar2bw(s):
    return "".join(_BW.get(c, c) for c in s)


def bw2ar(s):
    return "".join(_BW_INV.get(c, c) for c in s)


def _sat(r, g, b):
    mx, mn = max(r, g, b) / 255.0, min(r, g, b) / 255.0
    return 0.0 if mx == 0 else (mx - mn) / mx


def colors_from_image(path):
    """Port of the studio's BRAND.colorsFromImage: 64x64 sample, alpha<128 skipped, near-black / near-white-grey
    skipped, 4096 buckets weighted 1+2*saturation, distinct colours by L1 > 90, accent fallback = primary +45% white."""
    from PIL import Image
    im = Image.open(path).convert("RGBA").resize((64, 64), Image.BILINEAR)
    h, dark, light = {}, 0, 0
    for r, g, b, a in im.getdata():
        if a < 128:
            continue
        l, s = 0.299 * r + 0.587 * g + 0.114 * b, _sat(r, g, b)
        if l < 40:
            dark += 1
            continue
        if l > 228 and s < 0.12:
            light += 1
            continue
        k = (r >> 4) << 8 | (g >> 4) << 4 | (b >> 4)
        e = h.setdefault(k, [0.0, 0, 0, 0, 0])
        e[0] += 1 + s * 2
        e[1] += r
        e[2] += g
        e[3] += b
        e[4] += 1
    buckets = sorted(([e[0], e[1] / e[4], e[2] / e[4], e[3] / e[4]] for e in h.values()), key=lambda x: -x[0])
    out = []
    for bk in buckets:
        if all(abs(o[1] - bk[1]) + abs(o[2] - bk[2]) + abs(o[3] - bk[3]) > 90 for o in out):
            out.append(bk)
        if len(out) >= 4:
            break
    if not out:
        return {"primary": "#2a2a2e", "accent": "#ffd23f", "text": "#ffffff", "bg": "#0d0d10"} if dark > light else None
    P = out[0][1:]
    A = out[1][1:] if len(out) > 1 else [v + (255 - v) * 0.45 for v in P]
    return {"primary": hexc(P), "accent": hexc(A), "text": "#ffffff",
            "bg": "#0d0d10" if dark > light * 1.5 else hexc([v * 0.15 for v in P])}


_KNOWN_FONTS = ["Cairo", "Tajawal", "Almarai", "IBM Plex Sans Arabic", "Readex Pro", "Inter", "Roboto", "Montserrat"]


def brand_from_text(txt):
    hexes = list(dict.fromkeys(m.lower() for m in re.findall(r"#[0-9a-fA-F]{6}\b", txt)))

    def named(words):
        m = re.search(r"(?:%s)[^#\n]{0,40}(#[0-9a-fA-F]{6})" % words, txt, re.I)
        return m.group(1).lower() if m else None
    pal = {"primary": named("primary|أساسي|رئيسي|main") or (hexes[0] if hexes else None),
           "accent": named("accent|secondary|ثانوي|إبراز|ابراز|highlight") or (hexes[1] if len(hexes) > 1 else None),
           "bg": named("background|bg|خلفية|dark"), "text": named("text|نص|foreground")}
    return pal, [f for f in _KNOWN_FONTS if re.search(r"\b%s\b" % re.escape(f), txt, re.I)]


def font_weight(name):
    n = name.lower()
    if re.search(r"variable|vf", n):
        return "100 900"
    for pat, w in (("black|heavy", "900"), ("extrabold", "800"), ("semibold|demibold", "600"), ("bold", "700"), ("medium", "500"), ("light|thin", "300")):
        if re.search(pat, n):
            return w
    return "400"


def import_brand(zpath):
    files = {}
    with zipfile.ZipFile(zpath) as z:
        for n in z.namelist():
            if n.endswith("/") or "__MACOSX" in n or "/." in n:
                continue
            files[n.split("/")[-1]] = z.read(n)
    imgs = [n for n in files if re.search(r"\.(png|jpe?g|svg|webp|gif)$", n, re.I)]
    logo = next((n for n in imgs if re.search(r"logo|لوجو|شعار|mark|icon|brand", n, re.I)), None) or next((n for n in imgs if n.endswith(".svg")), None) \
        or (imgs[0] if len(imgs) == 1 else None)
    fonts = {n: font_weight(n) for n in files if re.search(r"\.(ttf|otf|woff2?)$", n, re.I)}
    pal, named_fonts = {}, []
    for n, data in files.items():
        if re.search(r"\.(json|css|txt|md)$", n, re.I):
            p, f = brand_from_text(data.decode("utf-8", "replace"))
            pal.update({k: v for k, v in p.items() if v})
            named_fonts += f
    return files, logo, fonts, pal, named_fonts


def _grey_png(wd):
    from PIL import Image
    Image.new("RGBA", (64, 64), (240, 240, 240, 255)).save(wd / "grey.png")
    return wd / "grey.png"


def srgb_to_oklab(c):
    def lin(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(v) for v in c)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = (math.copysign(abs(x) ** (1 / 3), x) for x in (l, m, s))
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def oklch_to_srgb(L, C, H):
    a, b = C * math.cos(math.radians(H)), C * math.sin(math.radians(H))
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    r = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    bb = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s

    def enc(v):
        v = max(0.0, min(1.0, v))
        return 255 * (12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055)
    return tuple(int(round(enc(v))) for v in (r, g, bb))


def oklch(c):
    L, a, b = srgb_to_oklab(c)
    return L, math.hypot(a, b), (math.degrees(math.atan2(b, a)) + 360) % 360


def uniformity(Ls):
    d = [abs(Ls[i + 1] - Ls[i]) for i in range(len(Ls) - 1)]
    return 1 - (max(d) - min(d)) / (sum(d) / len(d))


def pick_ink(ground, inks=("#ffffff", "#0b0b10")):
    return max(inks, key=lambda i: contrast(i, ground))


def hsl_hex(h, s, l):
    import colorsys
    r, g, b = colorsys.hls_to_rgb((h % 360) / 360.0, l, s)
    return hexc((r * 255, g * 255, b * 255))


def truss_solve(nodes, members, supports, loads):
    """3D direct stiffness: nodes {id: (x,y,z)}, members [(a, b, A, E)], supports {id: (fx,fy,fz) fixed flags},
    loads {id: (Fx,Fy,Fz)} -> member axial forces (N, + tension)."""
    np = _np()
    ids = list(nodes)
    ix = {n: i for i, n in enumerate(ids)}
    K = np.zeros((3 * len(ids), 3 * len(ids)))
    geo = []
    for a, b, A, E in members:
        pa, pb = np.array(nodes[a], float), np.array(nodes[b], float)
        L = np.linalg.norm(pb - pa)
        c = (pb - pa) / L
        k = E * A / L * np.outer(c, c)
        ia, ib = 3 * ix[a], 3 * ix[b]
        for (r, s, sg) in ((ia, ia, 1), (ib, ib, 1), (ia, ib, -1), (ib, ia, -1)):
            K[r:r + 3, s:s + 3] += sg * k
        geo.append((ia, ib, c, L, E, A))
    F = np.zeros(3 * len(ids))
    for n, f in loads.items():
        F[3 * ix[n]:3 * ix[n] + 3] = f
    fixed = [3 * ix[n] + d for n, fl in supports.items() for d in range(3) if fl[d]]
    free = [i for i in range(3 * len(ids)) if i not in fixed]
    U = np.zeros(3 * len(ids))
    U[free] = np.linalg.solve(K[np.ix_(free, free)], F[free])
    return [E * A / L * float(np.dot(c, U[ib:ib + 3] - U[ia:ia + 3])) for ia, ib, c, L, E, A in geo]


def util_colour(u):
    stops = [(0, (0.35, 1, 0.72)), (0.5, (0.75, 1, 0.45)), (0.8, (1, 0.86, 0.35)), (1, (1, 0.36, 0.28))]
    u = max(0.0, min(1.0, u))
    for (u0, c0), (u1, c1) in zip(stops, stops[1:]):
        if u <= u1:
            k = (u - u0) / (u1 - u0)
            return tuple(a + (b - a) * k for a, b in zip(c0, c1))
    return stops[-1][1]


_CANVAS = {"reels": ("9:16", 1080, 1920), "tiktok": ("9:16", 1080, 1920), "shorts": ("9:16", 1080, 1920), "snapchat": ("9:16", 1080, 1920),
           "whatsapp-status": ("9:16", 1080, 1920), "youtube": ("16:9", 1920, 1080), "site": ("16:9", 1920, 1080), "desktop": ("16:9", 1920, 1080),
           "feed-reach": ("4:5", 1080, 1350), "square-feed": ("1:1", 1080, 1080), "link-preview": ("1.91:1", 1200, 630), "pinterest": ("2:3", 1000, 1500),
           "cinema": ("2.39:1", 2048, 858)}


def derive_canvas(where):
    if where not in _CANVAS:
        return None
    ar, w, h = _CANVAS[where]
    return {"plays_on": where, "aspect": ar, "width": w, "height": h, "why": "derived from where it plays (%s), not from 'which size?'" % where}


def width_for(height, ratio):
    a, b = (float(x) for x in ratio.split(":"))
    return int(round(height * a / b))


def round_to(v, m):
    return int(math.floor(v / m + 0.5)) * m


def frames_8k1(seconds, fps):
    return int(round((seconds * fps - 1) / 8)) * 8 + 1


_SAFE = {"top": 250, "bottom": 320, "right": 120, "left": 60}


def safe_zone(w=1080, h=1920, m=_SAFE):
    return (m["left"], m["top"], w - m["right"], h - m["bottom"])


def inside(box, zone):
    return box[0] >= zone[0] and box[1] >= zone[1] and box[2] <= zone[2] and box[3] <= zone[3]


def cap_height(img_gray, thr=128):
    np = _np()
    rows = np.where((img_gray < thr).any(axis=1))[0]
    return int(rows.max() - rows.min() + 1) if len(rows) else 0


def cloudinary_to_ffmpeg(spec, src_h):
    """Cloudinary-style URL transformations (so_/eo_/du_ trim, ac_none, c_limit,h_, fps_) -> local ffmpeg arguments."""
    pre, vf, args = [], [], []
    p = {}
    for comp in spec.split("/"):
        for kv in comp.split(","):
            if "_" in kv:
                k, v = kv.split("_", 1)
                p[k] = v
            else:
                p[kv] = True
    if "so" in p:
        pre += ["-ss", p["so"]]
    if "eo" in p:
        args += ["-t", str(float(p["eo"]) - float(p.get("so", 0)))]
    elif "du" in p:
        args += ["-t", p["du"]]
    if p.get("ac") == "none":
        args += ["-an"]
    if p.get("c") == "limit" and "h" in p and int(p["h"]) < src_h:
        vf.append("scale=-2:%s" % p["h"])
    if "fps" in p:
        vf.append("fps=%s" % p["fps"])
    if vf:
        args += ["-vf", ",".join(vf)]
    return pre, args


_GATE_RULES = [("BLOCK", r"\bpassword|كلمة السر|credit card|card number|\bcvv\b|payment|pay now|ادفع"),
               ("HANDOFF", r"captcha|verification code|\botp\b|رمز التحقق|2fa"),
               ("CONFIRM", r"\bsend\b|\bpost\b|publish|delete|remove|install|submit|ارسل|انشر|احذف")]


_GATE_EXIT = {"RUN": 0, "CONFIRM": 1, "BLOCK": 3, "HANDOFF": 4}


def action_gate(goal, steps, approved=(), allowed_domains=()):
    rows = []
    for i, s in enumerate(steps):
        verdict = "RUN"
        dom = re.search(r"https?://([^/\s]+)", s)
        if dom and allowed_domains and dom.group(1) not in allowed_domains:
            verdict = "BLOCK"
        else:
            for v, pat in _GATE_RULES:
                if re.search(pat, s, re.I):
                    verdict = v
                    break
            if verdict == "CONFIRM" and i in approved:
                verdict = "RUN"
        rows.append({"step": s, "verdict": verdict})
    worst = max((r["verdict"] for r in rows), key=lambda v: [0, 1, 4, 3].index(_GATE_EXIT[v]))
    return {"goal": goal, "steps": rows, "verdict": worst, "exit": _GATE_EXIT[worst]}


_USERBASE = _site.getuserbase()


def _sbx_env(wd, **extra):
    """Environment that keeps every engine's home, cache, config and temp files inside the work folder."""
    wd = Path(wd)
    home = wd / "_home"
    for d in ("", ".cache", ".config", ".local/share", ".state", "tmp"):
        (home / d).mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("ANTHROPIC", "OPENAI", "GRAPHIFY_"))}
    env.update(HOME=str(home), XDG_CACHE_HOME=str(home / ".cache"), XDG_CONFIG_HOME=str(home / ".config"),
               XDG_DATA_HOME=str(home / ".local/share"), XDG_STATE_HOME=str(home / ".state"), TMPDIR=str(home / "tmp"),
               MPLCONFIGDIR=str(home / ".config/mpl"), PYTHONUSERBASE=_USERBASE, PYTHONDONTWRITEBYTECODE="1",
               NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost")
    env.update({k: str(v) for k, v in extra.items()})
    return env


def _manim(wd, script, scenes, res=(192, 108), fps=10, extra_env=None):
    """Render scenes of a Manim script at a tiny -ql resolution; media, Tex cache and temp stay in the work folder."""
    wd = Path(wd)
    (wd / "scene.py").write_text(script, encoding="utf-8")
    env = _sbx_env(wd, **(extra_env or {}))
    done = subprocess.run(["manim", "render", "-ql", "-r", "%d,%d" % res, "--fps", str(fps), "--media_dir", str(wd / "media"),
                           "--disable_caching", "--progress_bar", "none", "-v", "WARNING", "scene.py", *scenes],
                          capture_output=True, text=True, timeout=60, cwd=str(wd), env=env, stdin=subprocess.DEVNULL)
    if done.returncode:
        raise RuntimeError("manim failed: " + (done.stderr or done.stdout)[-500:])
    folder = wd / "media/videos/scene" / ("%dp%d" % (res[1], fps))
    return {s: folder / ("%s.mp4" % s) for s in scenes}


def _hue_mask(frame, rgb_target, tol=60):
    np = _np()
    return (np.abs(frame - np.array(rgb_target, float)).sum(axis=2) < tol)


def _dominant(frame):
    """Pixel counts per hue window (saturation > .45, value > .25): red, yellow, green. Hue survives the anti-aliasing of
    thin strokes on black, where absolute RGB thresholds do not."""
    np = _np()
    from PIL import Image
    hsv = np.asarray(Image.fromarray(np.clip(frame, 0, 255).astype("uint8")).convert("HSV")).astype(float)
    h, sat, val = hsv[..., 0] * 360 / 255, hsv[..., 1] / 255, hsv[..., 2] / 255
    ok = (sat > 0.45) & (val > 0.25)
    return {"red": int((ok & ((h < 15) | (h > 345))).sum()), "yellow": int((ok & (h >= 30) & (h <= 70)).sum()),
            "green": int((ok & (h >= 80) & (h <= 160)).sum())}
