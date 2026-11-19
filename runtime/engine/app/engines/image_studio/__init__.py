"""Image studio (استوديو الصور): Arabic titles that shape right, cinematic 9:16 reframe, grades, 4x upscale, cutout, covers, review sheets.

Every function writes one file and returns a measured dict (path, size, mean luma...) so the caller can prove the result.
Arabic text: Pillow with libraqm when present (true shaping + RTL), else arabic_reshaper + python-bidi.
"""
import json, os, shutil, subprocess, tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps, features

HERE = Path(__file__).resolve().parent
ENGINES = HERE.parent
FONT_DIRS = [ENGINES / "cinema" / "assets" / "fonts", ENGINES / "web_film" / "assets" / "fonts",
             ENGINES / "talking_head" / "data" / "fonts"]
FONTS = {  # short name -> file (all OFL, shipped with the skill)
    "cairo": "Cairo-900.ttf", "cairo-bold": "Cairo-700.ttf", "cairo-regular": "Cairo-400.ttf",
    "amiri": "Amiri-Bold.ttf", "ruqaa": "ArefRuqaa-Bold.ttf", "messiri": "ElMessiri-700.ttf",
    "kufi": "ReemKufi-700.ttf", "tajawal": "Tajawal-Black.ttf", "serif": "InstrumentSerif-Italic.ttf",
    "anton": "Anton-Regular.ttf",
}
GRADES = json.loads((HERE / "data" / "grades.json").read_text(encoding="utf-8"))
RAQM = features.check("raqm")
UPSCAYL_MODELS = ["ultrasharp-4x", "high-fidelity-4x", "remacri-4x", "ultramix-balanced-4x", "digital-art-4x", "upscayl-lite-4x"]


# ---------- helpers ----------
def font_path(name: str) -> str:
    if name and Path(name).exists():
        return str(name)
    fn = FONTS.get((name or "cairo").lower(), name)
    for d in FONT_DIRS:
        if (d / fn).exists():
            return str(d / fn)
    raise FileNotFoundError(f"font {name!r} not found; choose from {', '.join(FONTS)} or pass a .ttf path")


def is_rtl(text: str) -> bool:
    return any("\u0590" <= ch <= "\u08ff" or "\ufb50" <= ch <= "\ufeff" for ch in text)


def _shape(text: str):
    """Return (string_to_draw, draw_kwargs) so Arabic joins and runs right-to-left."""
    if not is_rtl(text):
        return text, {}
    if RAQM:
        return text, {"direction": "rtl", "language": "ar", "features": ["liga", "calt"]}
    import arabic_reshaper
    from bidi.algorithm import get_display
    return get_display(arabic_reshaper.reshape(text)), {}


def _size(s) -> tuple:
    if isinstance(s, (tuple, list)):
        return int(s[0]), int(s[1])
    w, h = str(s).lower().split("x")
    return int(w), int(h)


def _open(path) -> Image.Image:
    im = Image.open(path)
    im = ImageOps.exif_transpose(im)
    return im.convert("RGBA") if im.mode in ("RGBA", "LA", "P") else im.convert("RGB")


def _save(im: Image.Image, out) -> dict:
    out = Path(out); out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix.lower() in (".jpg", ".jpeg"):
        im.convert("RGB").save(out, quality=95, subsampling=0, optimize=True)
    elif out.suffix.lower() == ".webp":
        im.save(out, quality=95, method=6)
    else:
        im.save(out, optimize=True)
    return measure(out)


def measure(path) -> dict:
    """Size, mode, mean luma and alpha coverage of an image file (evidence for the report)."""
    im = Image.open(path)
    rgb = np.asarray(im.convert("RGB"), dtype=np.float32)
    luma = float((rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)).mean())
    r = {"path": str(path), "width": im.width, "height": im.height, "mode": im.mode,
         "bytes": Path(path).stat().st_size, "mean_luma": round(luma, 2)}
    if im.mode == "RGBA":
        r["alpha_coverage"] = round(float((np.asarray(im)[..., 3] > 127).mean()), 4)
    return r


# ---------- text ----------
def text_layer(size, text, font="cairo", px=None, color="#FFFFFF", stroke=0, stroke_color="#000000",
               shadow=True, align="center", pos="center", margin=0.08, max_width=0.86, line_gap=0.18, glow=None):
    """A transparent RGBA layer with a (multi-line) title. Font size auto-fits max_width when px is None.
    pos: center | top | bottom | lower-third | (x, y) in 0..1."""
    W, H = _size(size)
    lines = [l for l in str(text).split("\n")]
    fp = font_path(font)
    px = px or int(H * 0.075)
    while True:  # auto-fit the widest line
        f = ImageFont.truetype(fp, px)
        dims = []
        for l in lines:
            s, kw = _shape(l)
            b = f.getbbox(s, stroke_width=stroke, **kw)
            dims.append((s, kw, b))
        widest = max(b[2] - b[0] for _, _, b in dims)
        if widest <= W * max_width or px <= 12:
            break
        px = int(px * 0.94)
    asc, desc = f.getmetrics()
    lh = int((asc + desc) * (1 + line_gap))
    block_h = lh * len(lines) - int((asc + desc) * line_gap)
    if isinstance(pos, (tuple, list)):
        cx, cy = pos[0] * W, pos[1] * H
    else:
        cx = W / 2
        cy = {"center": H / 2, "top": H * margin + block_h / 2, "bottom": H * (1 - margin) - block_h / 2,
              "lower-third": H * 0.72}.get(pos, H / 2)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    y = cy - block_h / 2
    placed = []
    for s, kw, b in dims:
        tw = b[2] - b[0]
        x = {"center": cx - tw / 2, "right": W * (1 - margin) - tw, "left": W * margin}.get(align, cx - tw / 2) - b[0]
        placed.append((x, y, s, kw)); y += lh

    def draw_all(target, fill, sw=0, sc=None, dx=0, dy=0):
        d = ImageDraw.Draw(target)
        for x, yy, s, kw in placed:
            d.text((x + dx, yy + dy), s, font=f, fill=fill, stroke_width=sw, stroke_fill=sc, **kw)

    if glow:
        g = Image.new("RGBA", (W, H), (0, 0, 0, 0)); draw_all(g, glow, stroke + max(2, px // 18), glow)
        layer = Image.alpha_composite(layer, g.filter(ImageFilter.GaussianBlur(px / 5)))
    if shadow:
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); draw_all(sh, (0, 0, 0, 170), stroke, (0, 0, 0, 170), px // 22, px // 16)
        layer = Image.alpha_composite(layer, sh.filter(ImageFilter.GaussianBlur(max(2, px // 14))))
    top = Image.new("RGBA", (W, H), (0, 0, 0, 0)); draw_all(top, color, stroke, stroke_color)
    layer = Image.alpha_composite(layer, top)
    return layer, {"font": Path(fp).name, "px": px, "lines": len(lines), "rtl": is_rtl(str(text)), "shaper": "raqm" if RAQM else "reshaper"}


def title(out, text, src=None, size="1080x1920", bg="#0B0B0F", **kw):
    """Title on an image (src) or on a solid/gradient background. Returns measured dict + text info."""
    if src:
        base = _open(src).convert("RGBA"); size = base.size
    else:
        W, H = _size(size)
        base = _gradient((W, H), bg) if isinstance(bg, (list, tuple)) else Image.new("RGBA", (W, H), bg)
    layer, info = text_layer(base.size, text, **kw)
    r = _save(Image.alpha_composite(base, layer), out); r["text"] = info
    return r


def _gradient(size, colors):
    W, H = size
    a = np.array(ImageColor_rgb(colors[0]), np.float32); b = np.array(ImageColor_rgb(colors[-1]), np.float32)
    t = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    arr = (a * (1 - t) + b * t).repeat(W, axis=1)
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGB").convert("RGBA")


def ImageColor_rgb(c):
    from PIL import ImageColor
    return ImageColor.getrgb(c)[:3]


# ---------- reframe / grade / finish ----------
def reframe(src, out, size="1080x1920", mode="blur", focus=(0.5, 0.5), blur=48, dim=0.55):
    """Fit any image to a target frame. mode: blur (sharp image over its own blurred, dimmed copy — the cinematic fill),
    cover (crop around focus), contain (letterbox on black)."""
    W, H = _size(size)
    im = _open(src).convert("RGB")
    if mode == "cover":
        return _save(ImageOps.fit(im, (W, H), Image.LANCZOS, centering=focus), out)
    canvas = Image.new("RGB", (W, H), "black")
    if mode == "blur":
        bgim = ImageOps.fit(im, (W, H), Image.LANCZOS, centering=focus).filter(ImageFilter.GaussianBlur(blur))
        canvas = Image.blend(bgim, Image.new("RGB", (W, H), "black"), 1 - dim)
    fg = ImageOps.contain(im, (W, H), Image.LANCZOS)
    canvas.paste(fg, ((W - fg.width) // 2, (H - fg.height) // 2))
    return _save(canvas, out)


def grade(src, out, look="teal_orange", strength=1.0, vignette=None, grain=None):
    """Apply a named look from data/grades.json (lift/gamma/gain per channel, saturation, contrast) plus vignette/grain."""
    if look not in GRADES:
        raise KeyError(f"unknown look {look!r}; choose from {', '.join(k for k in GRADES if not k.startswith('_'))}")
    g = GRADES[look]
    im = _open(src)
    alpha = im.getchannel("A") if im.mode == "RGBA" else None
    x = np.asarray(im.convert("RGB"), np.float32) / 255.0
    y = x.copy()
    lift, gamma, gain = (np.array(g.get(k, d), np.float32) for k, d in (("lift", [0, 0, 0]), ("gamma", [1, 1, 1]), ("gain", [1, 1, 1])))
    y = np.clip(y * gain + lift * (1 - y), 0, 1) ** (1 / gamma)
    c = g.get("contrast", 1.0)
    y = np.clip((y - 0.5) * c + 0.5, 0, 1)
    lum = (y @ np.array([0.2126, 0.7152, 0.0722], np.float32))[..., None]
    y = np.clip(lum + (y - lum) * g.get("saturation", 1.0), 0, 1)
    y = x + (y - x) * float(strength)
    vig = g.get("vignette", 0) if vignette is None else vignette
    if vig:
        H, W = y.shape[:2]
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        d = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) / np.sqrt(2)
        y = y * (1 - vig * np.clip(d, 0, 1) ** 2)[..., None]
    gr = g.get("grain", 0) if grain is None else grain
    if gr:
        y = y + np.random.default_rng(7).normal(0, gr, y.shape[:2])[..., None].astype(np.float32)
    res = Image.fromarray((np.clip(y, 0, 1) * 255 + 0.5).astype(np.uint8), "RGB")
    if alpha is not None:
        res.putalpha(alpha)
    r = _save(res, out); r["look"] = look
    return r


def cover(src, out, text, sub=None, size="1080x1920", look="teal_orange", font="cairo", sub_font="tajawal",
          color="#FFFFFF", accent="#F5C04A", pos="lower-third"):
    """Reel / YouTube cover: reframe (blur fill) -> grade -> bottom darkening -> Arabic title (+ subtitle line)."""
    with tempfile.TemporaryDirectory() as td:
        a = Path(td) / "a.png"; b = Path(td) / "b.png"
        reframe(src, a, size, mode="cover" if _ratio_close(src, size) else "blur")
        grade(a, b, look)
        base = Image.open(b).convert("RGBA")
    W, H = base.size
    ramp = np.clip((np.linspace(0, 1, H) - 0.45) / 0.55, 0, 1) ** 1.6 * 200
    shade = Image.fromarray(np.repeat(ramp[:, None], W, axis=1).astype(np.uint8), "L")
    base = Image.alpha_composite(base, Image.merge("RGBA", (*[Image.new("L", (W, H), 0)] * 3, shade)))
    t_layer, info = text_layer((W, H), text, font=font, color=color, pos=pos, px=int(H * 0.085))
    base = Image.alpha_composite(base, t_layer)
    if sub:
        s_layer, _ = text_layer((W, H), sub, font=sub_font, color=accent, pos=(0.5, 0.72 + 0.1 if pos == "lower-third" else 0.88),
                                px=int(H * 0.034), shadow=True)
        base = Image.alpha_composite(base, s_layer)
    r = _save(base, out); r["text"] = info
    return r


def _ratio_close(src, size, tol=0.06):
    W, H = _size(size)
    with Image.open(src) as im:
        return abs(im.width / im.height - W / H) / (W / H) < tol


# ---------- AI helpers (local programs, free) ----------
def upscayl_bin():
    p = shutil.which("upscayl-bin")
    if not p:
        for c in (Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Upscayl" / "resources" / "bin" / "upscayl-bin.exe",
                  Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Upscayl" / "resources" / "bin" / "upscayl-bin.exe"):
            if c.exists():
                p = str(c); break
    return p


def upscale(src, out, scale=4, model="ultrasharp-4x"):
    """AI upscale with Upscayl (Real-ESRGAN, Vulkan, works without NVIDIA). Falls back to Lanczos + unsharp if absent."""
    exe = upscayl_bin()
    out = Path(out); out.parent.mkdir(parents=True, exist_ok=True)
    if exe:
        models = Path(exe).parent.parent / "models"
        cmd = [exe, "-i", str(src), "-o", str(out), "-s", str(scale), "-m", str(models), "-n", model, "-f", out.suffix.lstrip(".").lower() or "png"]
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if p.returncode == 0 and out.exists():
            r = measure(out); r["method"] = f"upscayl:{model}"; return r
    im = _open(src)
    big = im.resize((im.width * scale, im.height * scale), Image.LANCZOS).filter(ImageFilter.UnsharpMask(2, 80, 2))
    r = _save(big, out); r["method"] = "lanczos+unsharp (upscayl not found)"
    return r


def cutout(src, out, model="isnet-general-use"):
    """Remove the background with rembg -> RGBA PNG (first run downloads the free model once)."""
    from rembg import new_session, remove
    res = remove(_open(src), session=new_session(model), post_process_mask=True)
    r = _save(res, Path(out).with_suffix(".png")); r["model"] = model
    return r


# ---------- review ----------
def sheet(video, out, n=12, cols=4, width=360, label=True):
    """Contact sheet of n evenly spaced frames (with timestamps) so a cut can be judged by eye in one image."""
    from engines.media import exe, probe
    dur = float(probe(video)["format"]["duration"])
    times = [dur * (i + 0.5) / n for i in range(n)]
    tiles = []
    with tempfile.TemporaryDirectory() as td:
        for i, t in enumerate(times):
            fp = Path(td) / f"{i:03d}.png"
            subprocess.run([exe("ffmpeg"), "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                            "-vf", f"scale={width}:-2", str(fp)], check=True)
            im = Image.open(fp).convert("RGB")
            if label:
                d = ImageDraw.Draw(im)
                f = ImageFont.truetype(font_path("cairo-bold"), max(14, width // 14))
                stamp = f"{int(t // 60):02d}:{t % 60:05.2f}"
                d.text((10, 6), stamp, font=f, fill="white", stroke_width=3, stroke_fill="black")
            tiles.append(im)
    tw, th = tiles[0].size; rows = (len(tiles) + cols - 1) // cols; gap = 6
    canvas = Image.new("RGB", (cols * tw + (cols + 1) * gap, rows * th + (rows + 1) * gap), (12, 12, 14))
    for i, im in enumerate(tiles):
        canvas.paste(im, (gap + (i % cols) * (tw + gap), gap + (i // cols) * (th + gap)))
    r = _save(canvas, out); r["frames"] = [round(t, 3) for t in times]
    return r


def looks():
    return {k: v.get("ar", "") for k, v in GRADES.items() if not k.startswith("_")}
