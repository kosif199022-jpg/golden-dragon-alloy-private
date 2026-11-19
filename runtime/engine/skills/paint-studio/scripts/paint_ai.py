#!/usr/bin/env python
"""paint-studio AI: local, free equivalents of Paint's Copilot features (SD-Turbo on CPU, no cloud, no credits).

Run with the toon venv (it has diffusers):  %USERPROFILE%\\dragon-models\\toon\\venv\\Scripts\\python.exe paint_ai.py ...

  create     OUT --prompt "..." [--style STYLE] [--size 512x512] [--n 1] [--seed 7]        (Image Creator)
  cocreator  SKETCH OUT --prompt "..." [--creativity 0.5] [--style STYLE]                   (Cocreator: sketch -> art)
  reimagine  IN OUT [--prompt "..."] [--strength 0.5] [--style STYLE]                        (Reimagine)
  fill       IN OUT --prompt "..." (--box x0,y0,x1,y1 | --mask mask.png) [--strength 0.9]   (Generative fill)
  erase      IN OUT (--box ... | --mask ...)                                                 (Generative erase, AI refine)
  sticker    OUT --prompt "..." [--style cartoon] [--n 1]                                    (Stickers, transparent PNG)
  coloring   OUT --prompt "..."                                                              (Coloring book page)
  styles                                                                                    list style presets
SD-Turbo is ~512 px native; bigger outputs are generated at 512-768 then upscaled with Lanczos
(use `paint.py draw ... --op '{"op":"upscale"}'` for real 4x detail).
"""
import argparse, os, subprocess, sys, time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

MODEL = Path(os.environ.get("PAINT_SD_MODEL", Path.home() / "dragon-models" / "toon" / "sd-turbo"))
HERE = Path(__file__).resolve().parent
SYS_PY = os.environ.get("PAINT_SYS_PY", "python")

STYLES = {
    "none": "",
    "photo": "photorealistic photo, natural light, sharp focus, high detail",
    "digital_art": "digital art, vibrant colors, detailed illustration, artstation",
    "watercolor": "watercolor painting, soft washes, paper texture, delicate brush strokes",
    "oil": "oil painting on canvas, thick impasto brush strokes, rich colors",
    "ink_sketch": "black ink sketch, pen drawing, cross hatching, white paper",
    "charcoal": "charcoal drawing, smudged shading, textured paper, monochrome",
    "anime": "anime illustration, cel shading, clean line art, vivid colors",
    "pixel_art": "pixel art, 16-bit retro game sprite, crisp pixels, limited palette",
    "3d": "3d render, pixar style, soft lighting, smooth shapes, cute",
    "cartoon": "flat cartoon illustration, bold outlines, simple shapes, bright colors",
    "fantasy": "fantasy concept art, epic lighting, highly detailed, magical atmosphere",
}
NEG = "blurry, low quality, deformed, watermark, text, signature, jpeg artifacts"
_PIPES = {}


def _torch():
    import torch
    torch.set_num_threads(max(1, (os.cpu_count() or 4) - 1))
    return torch


def pipe(kind):
    if kind in _PIPES:
        return _PIPES[kind]
    torch = _torch()
    from diffusers import AutoPipelineForText2Image, AutoPipelineForImage2Image, AutoPipelineForInpainting
    if not (MODEL / "model_index.json").exists():
        raise SystemExit(f"SD-Turbo model not found at {MODEL}")
    cls = {"t2i": AutoPipelineForText2Image, "i2i": AutoPipelineForImage2Image, "inpaint": AutoPipelineForInpainting}[kind]
    base = next(iter(_PIPES.values()), None)
    t = time.time()
    dtype = torch.float32 if os.environ.get("PAINT_SD_FP32") else torch.bfloat16
    p = cls.from_pipe(base) if base is not None else cls.from_pretrained(str(MODEL), variant="fp16", torch_dtype=dtype)
    p.set_progress_bar_config(disable=True)
    print(f"  model ready ({kind}) in {time.time() - t:.1f}s", flush=True)
    _PIPES[kind] = p
    return p


def prompt_of(text, style):
    s = STYLES.get(style or "none", style or "")
    return f"{text}, {s}" if s else text


def fit8(w, h, side):
    sc = side / max(w, h)
    return max(64, int(w * sc) // 8 * 8), max(64, int(h * sc) // 8 * 8)


def gen(seed):
    torch = _torch()
    return torch.Generator("cpu").manual_seed(int(seed))


def save(im, out, i=0, n=1):
    out = Path(out)
    if n > 1:
        out = out.with_name(f"{out.stem}_{i + 1}{out.suffix}")
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)
    print(out, f"{im.width}x{im.height}")
    return out


def cmd_create(a, extra=""):
    w, h = map(int, a.size.lower().split("x"))
    gw, gh = fit8(w, h, min(768, max(w, h)))
    outs = []
    for i in range(a.n):
        t = time.time()
        im = pipe("t2i")(prompt=prompt_of(a.prompt, a.style) + extra, num_inference_steps=a.steps, guidance_scale=0.0,
                         width=gw, height=gh, generator=gen(a.seed + i)).images[0]
        if (gw, gh) != (w, h):
            im = im.resize((w, h), Image.LANCZOS)
        outs.append(save(im, a.out, i, a.n)); print(f"  {time.time() - t:.1f}s")
    return outs


def i2i(src, prompt, strength, steps, seed, side=640):
    w, h = src.size
    gw, gh = fit8(w, h, side)
    steps = max(steps, int(np.ceil(1 / max(strength, 0.05))))  # SD-Turbo needs steps*strength >= 1
    im = pipe("i2i")(prompt=prompt, image=src.convert("RGB").resize((gw, gh), Image.LANCZOS), strength=strength,
                     num_inference_steps=steps, guidance_scale=0.0, generator=gen(seed)).images[0]
    return im.resize((w, h), Image.LANCZOS)


def cmd_cocreator(a):
    src = Image.open(a.src).convert("RGBA")
    flat = Image.new("RGB", src.size, "white"); flat.paste(src, mask=src.getchannel("A"))
    strength = 0.35 + 0.55 * max(0.0, min(1.0, a.creativity))
    save(i2i(flat, prompt_of(a.prompt, a.style), strength, a.steps, a.seed), a.out)


def cmd_reimagine(a):
    src = Image.open(a.src).convert("RGB")
    p = prompt_of(a.prompt or "same scene, beautiful, highly detailed", a.style)
    for i in range(a.n):
        save(i2i(src, p, a.strength, a.steps, a.seed + i), a.out, i, a.n)


def load_mask(a, size):
    if a.mask:
        return Image.open(a.mask).convert("L").resize(size)
    x0, y0, x1, y1 = map(int, a.box.split(","))
    m = Image.new("L", size, 0); ImageDraw.Draw(m).rectangle([x0, y0, x1, y1], fill=255); return m


def inpaint(src, mask, prompt, strength, steps, seed):
    w, h = src.size
    # work on a padded crop around the mask so small edits keep full detail
    bb = mask.point(lambda v: 255 if v > 20 else 0).getbbox()
    if not bb:
        return src
    pad = max(32, int(0.35 * max(bb[2] - bb[0], bb[3] - bb[1])))
    cx0, cy0, cx1, cy1 = max(0, bb[0] - pad), max(0, bb[1] - pad), min(w, bb[2] + pad), min(h, bb[3] + pad)
    crop, mcrop = src.crop((cx0, cy0, cx1, cy1)).convert("RGB"), mask.crop((cx0, cy0, cx1, cy1))
    gw, gh = fit8(crop.width, crop.height, 512)
    steps = max(steps, int(np.ceil(1 / max(strength, 0.05))))
    out = pipe("inpaint")(prompt=prompt, image=crop.resize((gw, gh), Image.LANCZOS), mask_image=mcrop.resize((gw, gh)),
                          strength=strength, num_inference_steps=steps, guidance_scale=0.0, generator=gen(seed),
                          width=gw, height=gh).images[0].resize(crop.size, Image.LANCZOS)
    soft = mcrop.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(4))
    res = src.convert("RGBA").copy()
    res.paste(Image.composite(out.convert("RGBA"), crop.convert("RGBA"), soft), (cx0, cy0))
    return res


def cmd_fill(a):
    src = Image.open(a.src).convert("RGBA")
    m = load_mask(a, src.size)
    save(inpaint(src, m, prompt_of(a.prompt, a.style), a.strength, a.steps, a.seed), a.out)


def cmd_erase(a):
    import cv2
    src = Image.open(a.src).convert("RGBA")
    m = load_mask(a, src.size)
    mk = cv2.dilate((np.asarray(m) > 20).astype(np.uint8) * 255, np.ones((9, 9), np.uint8))
    rgb = cv2.inpaint(np.asarray(src.convert("RGB"))[:, :, ::-1].copy(), mk, 9, cv2.INPAINT_TELEA)[:, :, ::-1]
    base = Image.fromarray(np.ascontiguousarray(rgb)).convert("RGBA")
    # light AI pass over the patched area so texture matches the surroundings
    res = inpaint(base, Image.fromarray(mk), "seamless natural background, matching surroundings, empty", 0.55, a.steps, a.seed)
    save(res, a.out)


def cmd_sticker(a):
    a.size = "512x512"
    outs = cmd_create(a, extra=", sticker, centered single subject, isolated on plain white background, die-cut")
    paint = str(HERE / "paint.py")
    for o in outs:
        subprocess.run([SYS_PY, paint, "draw", str(o), str(o.with_suffix(".png")), "--op", '{"op":"remove_background"}',
                        "--op", '{"op":"sticker_outline","width":10}', "--op", '{"op":"trim","padding":4}'], check=True)


def cmd_coloring(a):
    a.style = "none"; a.size = getattr(a, "size", "768x768")
    outs = cmd_create(a, extra=", black and white coloring book page, thick clean outlines, line art, no shading, white background")
    paint = str(HERE / "paint.py")
    for o in outs:
        subprocess.run([SYS_PY, paint, "draw", str(o), str(o), "--op", '{"op":"coloring_book","block":15,"c":9}'], check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, prompt_required=True):
        p.add_argument("--prompt", required=prompt_required, default=None)
        p.add_argument("--style", default="none")
        p.add_argument("--seed", type=int, default=7)
        p.add_argument("--steps", type=int, default=2)
        p.add_argument("--n", type=int, default=1)
    p = sub.add_parser("create"); p.add_argument("out"); common(p); p.add_argument("--size", default="512x512")
    p = sub.add_parser("cocreator"); p.add_argument("src"); p.add_argument("out"); common(p); p.add_argument("--creativity", type=float, default=0.5)
    p = sub.add_parser("reimagine"); p.add_argument("src"); p.add_argument("out"); common(p, False); p.add_argument("--strength", type=float, default=0.5)
    p = sub.add_parser("fill"); p.add_argument("src"); p.add_argument("out"); common(p); p.add_argument("--box"); p.add_argument("--mask"); p.add_argument("--strength", type=float, default=0.95)
    p = sub.add_parser("erase"); p.add_argument("src"); p.add_argument("out"); common(p, False); p.add_argument("--box"); p.add_argument("--mask")
    p = sub.add_parser("sticker"); p.add_argument("out"); common(p)
    p = sub.add_parser("coloring"); p.add_argument("out"); common(p); p.add_argument("--size", default="768x768")
    sub.add_parser("styles")
    a = ap.parse_args()
    if a.cmd == "styles":
        for k, v in STYLES.items(): print(f"{k:12s} {v}")
        return
    if a.cmd in ("fill", "erase") and not (a.box or a.mask):
        raise SystemExit("give --box x0,y0,x1,y1 or --mask mask.png")
    {"create": cmd_create, "cocreator": cmd_cocreator, "reimagine": cmd_reimagine, "fill": cmd_fill,
     "erase": cmd_erase, "sticker": cmd_sticker, "coloring": cmd_coloring}[a.cmd](a)


if __name__ == "__main__":
    main()
