"""Helpers of runners/fam_pixel_retro_stylized.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from PIL import Image
from PIL import ImageFont
from pathlib import Path
from .core import check
import json
import numpy as np
import subprocess


def _rng(seed=7):
    return np.random.default_rng(seed)


def _save(path, a):
    a = np.clip(np.asarray(a, dtype=float), 0, 255).round().astype(np.uint8)
    Image.fromarray(a).save(path)
    return Path(path)


def _load(path):
    return np.asarray(Image.open(path).convert("RGB")).astype(float)


def _hex(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=float)


def _luma(a):
    return a[..., 0] * .2126 + a[..., 1] * .7152 + a[..., 2] * .0722


def _colours(a):
    return {tuple(int(v) for v in c) for c in np.asarray(a).reshape(-1, np.asarray(a).shape[-1])}


def _blur(a, s):
    from scipy.ndimage import gaussian_filter
    sig = (s, s) + ((0,) if np.asarray(a).ndim == 3 else ())
    return gaussian_filter(np.asarray(a, dtype=float), sig)


def _video(path, frames, fps=30, lossless=True):
    frames = [np.clip(np.round(f), 0, 255).astype(np.uint8) for f in frames]
    h, w = frames[0].shape[:2]
    codec = ["-c:v", "libx264rgb", "-qp", "0", "-pix_fmt", "rgb24"] if lossless else \
        ["-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p"]
    p = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                        "-s", "%dx%d" % (w, h), "-r", str(fps), "-i", "-", *codec, str(path)],
                       input=b"".join(f.tobytes() for f in frames), capture_output=True, timeout=60)
    if p.returncode:
        raise RuntimeError(p.stderr.decode()[-300:])
    return Path(path)


def _shift_x(a, b, maxs=12):
    """Integer horizontal shift s that best maps a onto b (b[x] ~ a[x - s])."""
    best, bs = None, 0
    for s in range(-maxs, maxs + 1):
        e = np.mean((np.roll(a, s, axis=1) - b) ** 2)
        if best is None or e < best:
            best, bs = e, s
    return bs


def _font(size=10):
    return ImageFont.load_default(size=size)


def _prompt_lock(wd, name, block, scenes, forbidden):
    prompts = ["%s\n\nSTYLE LOCK:\n%s" % (s, block) for s in scenes]
    out = wd / ("%s_prompts.json" % name)
    out.write_text(json.dumps({"style_block": block, "prompts": prompts}, ensure_ascii=False, indent=1), "utf-8")
    back = json.loads(out.read_text("utf-8"))["prompts"]
    import hashlib
    hashes = {hashlib.sha256(p.split("STYLE LOCK:\n", 1)[1].encode()).hexdigest() if "STYLE LOCK:\n" in p else None
              for p in back}
    raw_has = sum(block in s for s in scenes)
    bad = [w for w in forbidden if any(w.lower() in p.lower() for p in back)]
    return [check("every prompt carries the style block verbatim", all(block in p for p in back), len(back), len(scenes)),
            check("one identical style block hash across prompts", len(hashes) == 1 and None not in hashes, len(hashes), 1),
            check("forbidden words absent", not bad, bad, []),
            check("negative control: raw scene prompts lack the block", raw_has == 0, raw_has, 0)], [out]


B4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], dtype=float)


def _bayer_quant(v, n):
    """v in 0..1 -> palette index with a 4x4 Bayer threshold offset."""
    h, w = v.shape
    th = np.tile(B4, (h // 4 + 1, w // 4 + 1))[:h, :w] / 16.0 + 1 / 32.0
    return np.clip(np.floor(v * (n - 1) + th), 0, n - 1).astype(int)


SPRITE = ["......oooo......", ".....ohhhho.....", "....ohbbbbho....", "....obbbbbbo....",
          "....obsbbsbo....", "....obbbbbbo....", ".....obbbbo.....", "....oobbbboo....",
          "...ohbbbbbbbbo..", "...obbbbbbbbbo..", "...obbobbobbbo..", "....obbbbbbo....",
          "....obbbbbbo....", "....obb..bbo....", "....oo....oo....", "................"]


def _pose(pose):
    rows = [list(r) for r in SPRITE]
    if pose % 2:   # walking pose: swap leg columns, generator keeps every other pixel on-model
        rows[13] = list("....obbo.bbo....")
        rows[14] = list("....oo...ooo....")
    return ["".join(r) for r in rows]


def _corner_tile(tl, tr, bl, br, cols, n=8):
    corners = np.array([[0, 0], [0, n], [n, 0], [n, n]], dtype=float)
    vals = [tl, tr, bl, br]
    t = np.zeros((n, n, 3))
    for y in range(n):
        for x in range(n):
            d = np.hypot(corners[:, 0] - (y + .5), corners[:, 1] - (x + .5))
            t[y, x] = cols[vals[int(np.argmin(d))]]
    return t


def _srgb_to_lab(rgb):
    c = rgb / 255
    c = np.where(c > .04045, ((c + .055) / 1.055) ** 2.4, c / 12.92)
    m = np.array([[.4124, .3576, .1805], [.2126, .7152, .0722], [.0193, .1192, .9505]])
    xyz = c @ m.T / np.array([.95047, 1, 1.08883])
    f = np.where(xyz > .008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


RAMP = " .:-=+*#%@"


def _ascii(lum, cols):
    H, W = lum.shape
    cw = W // cols
    rows = H // (cw * 9 // 8) if False else H // cw * 1
    ch = cw
    grid = lum[:(H // ch) * ch, :cols * cw].reshape(H // ch, ch, cols, cw).mean(axis=(1, 3))
    idx = np.clip(np.floor(grid / 256 * len(RAMP)), 0, len(RAMP) - 1).astype(int)
    return grid, idx, ["".join(RAMP[i] for i in r) for r in idx]


DITHER = Path("/opt/node22/lib/node_modules/hyperframes/dist/skills/media-use/scripts/dither.mjs")


def _rel_lum(h):
    c = _hex(h) / 255
    c = np.where(c <= .03928, c / 12.92, ((c + .055) / 1.055) ** 2.4)
    return float(c @ np.array([.2126, .7152, .0722]))


def _contrast(a, b):
    la, lb = sorted([_rel_lum(a), _rel_lum(b)], reverse=True)
    return (la + .05) / (lb + .05)
