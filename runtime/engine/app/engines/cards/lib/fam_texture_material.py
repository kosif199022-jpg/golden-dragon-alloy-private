"""Helpers of runners/fam_texture_material.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from PIL import Image
from pathlib import Path
from .core import check
import hashlib
import json
import math
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


def _blur(a, s):
    from scipy.ndimage import gaussian_filter
    a = np.asarray(a, dtype=float)
    if np.ndim(s) == 0:
        s = (s, s)
    return gaussian_filter(a, tuple(s) + ((0,) if a.ndim == 3 else ()))


def _hf(a):
    a = np.asarray(a, dtype=float)
    return float(np.abs(a - _blur(a, 2)).mean())


def _video(path, frames, fps=30):
    frames = [np.clip(np.round(f), 0, 255).astype(np.uint8) for f in frames]
    h, w = frames[0].shape[:2]
    p = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                        "-s", "%dx%d" % (w, h), "-r", str(fps), "-i", "-", "-c:v", "libx264rgb", "-qp", "0",
                        "-pix_fmt", "rgb24", str(path)],
                       input=b"".join(f.tobytes() for f in frames), capture_output=True, timeout=60)
    if p.returncode:
        raise RuntimeError(p.stderr.decode()[-300:])
    return Path(path)


def _smoothstep(e0, e1, x):
    t = np.clip((np.asarray(x, dtype=float) - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def _value_noise(shape, cell, seed, octaves=1, stretch=(1, 1)):
    H, W = shape
    out, amp, tot = np.zeros(shape), 1.0, 0.0
    for o in range(octaves):
        cy, cx = max(1, cell * stretch[1] / 2 ** o), max(1, cell * stretch[0] / 2 ** o)
        g = np.random.default_rng(seed + o).random((int(H / cy) + 3, int(W / cx) + 3))
        y, x = np.mgrid[:H, :W]
        y, x = y / cy, x / cx
        y0, x0 = np.floor(y).astype(int), np.floor(x).astype(int)
        fy, fx_ = _smoothstep(0, 1, y - y0), _smoothstep(0, 1, x - x0)
        v = (g[y0, x0] * (1 - fx_) + g[y0, x0 + 1] * fx_) * (1 - fy) + (g[y0 + 1, x0] * (1 - fx_) + g[y0 + 1, x0 + 1] * fx_) * fy
        out += amp * v
        tot += amp
        amp *= .5
    return out / tot


def _corr_len(a, axis):
    a = a - a.mean()
    for lag in range(1, a.shape[axis] // 2):
        c = (a * np.roll(a, lag, axis=axis)).mean() / (a * a).mean()
        if c < .5:
            return lag
    return a.shape[axis] // 2


def _spectral_slope(img, f_lo, f_hi):
    a = img - img.mean()
    P = np.abs(np.fft.fftshift(np.fft.fft2(a))) ** 2
    H, W = a.shape
    fy = np.fft.fftshift(np.fft.fftfreq(H))[:, None]
    fx_ = np.fft.fftshift(np.fft.fftfreq(W))[None]
    f = np.hypot(fy, fx_)
    bins = np.geomspace(f_lo, f_hi, 12)
    xs, ys = [], []
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (f >= lo) & (f < hi)
        if m.any():
            xs.append(math.log((lo * hi) ** .5))
            ys.append(math.log(P[m].mean() + 1e-12))
    return float(np.polyfit(xs, ys, 1)[0])


def _prompt_lock(wd, name, block, scenes, forbidden):
    prompts = ["%s\n\nSTYLE LOCK:\n%s" % (s, block) for s in scenes]
    out = wd / ("%s_prompts.json" % name)
    out.write_text(json.dumps({"style_block": block, "prompts": prompts}, ensure_ascii=False, indent=1), "utf-8")
    back = json.loads(out.read_text("utf-8"))["prompts"]
    hashes = {hashlib.sha256(p.split("STYLE LOCK:\n", 1)[1].encode()).hexdigest() if "STYLE LOCK:\n" in p else None
              for p in back}
    raw_has = sum(block in s for s in scenes)
    bad = [w for w in forbidden if any(w.lower() in p.lower() for p in back)]
    return [check("every prompt carries the style block verbatim", all(block in p for p in back), len(back), len(scenes)),
            check("one identical style block hash across prompts", len(hashes) == 1 and None not in hashes, len(hashes), 1),
            check("forbidden words absent", not bad, bad, []),
            check("negative control: raw scene prompts lack the block", raw_has == 0, raw_has, 0)], [out]


def _sphere(n=128):
    yy, xx = (np.mgrid[:n, :n] + .5) / n * 2 - 1
    yy = -yy
    r2 = xx * xx + yy * yy
    inside = r2 < 1
    z = np.sqrt(np.clip(1 - r2, 0, 1))
    N = np.stack([xx, yy, z], -1)
    return N, inside


def _norm(v):
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def _ggx(N, V, L, base, metal, rough, light=3.0):
    """Cook-Torrance GGX / Smith-Schlick / Fresnel-Schlick, as in three.js MeshStandardMaterial."""
    H = _norm(V + L)
    nl = np.clip((N * L).sum(-1), 0, 1)
    nv = np.clip((N * V).sum(-1), 1e-4, 1)
    nh = np.clip((N * H).sum(-1), 0, 1)
    vh = np.clip((V * H).sum(-1), 0, 1)
    a = max(rough, .02) ** 2
    D = a * a / (math.pi * (nh * nh * (a * a - 1) + 1) ** 2)
    k = a / 2
    G = (nl / (nl * (1 - k) + k)) * (nv / (nv * (1 - k) + k))
    F0 = .04 * (1 - metal) + base * metal
    F = F0 + (1 - F0) * ((1 - vh) ** 5)[..., None]
    spec = (D * G / (4 * nl * nv + 1e-4))[..., None] * F
    diff = base * (1 - metal) / math.pi * (1 - F)
    return (diff + spec) * (nl * light)[..., None], spec * (nl * light)[..., None]


def _to8(lin):
    return np.clip(lin, 0, 1) ** (1 / 2.2) * 255


def _glsl_rand(u, v):
    x = np.sin(u * 12.9898 + v * 78.233) * 43758.5453
    return x - np.floor(x)


def _panel_fixture(H=200, W=320, seed=41):
    rng = _rng(seed)
    yy, xx = np.mgrid[:H, :W]
    bg = np.stack([40 + 30 * np.sin(xx / 7.0), 30 + 25 * np.cos(yy / 5.0), 60 + 30 * np.sin((xx + yy) / 9.0)], -1)
    bg += rng.normal(0, 8, bg.shape)
    return np.clip(bg, 0, 255)


def _css_saturate(s):
    return np.array([[.213 + .787 * s, .715 - .715 * s, .072 - .072 * s],
                     [.213 - .213 * s, .715 + .285 * s, .072 - .072 * s],
                     [.213 - .213 * s, .715 - .715 * s, .072 + .928 * s]])


def _perlin(x, y, perm, grads):
    xi, yi = np.floor(x).astype(int), np.floor(y).astype(int)
    xf, yf = x - xi, y - yi

    def g(ix, iy, dx, dy):
        h = perm[(perm[ix & 255] + iy) & 255]
        gv = grads[h % 8]
        return gv[..., 0] * dx + gv[..., 1] * dy
    u, v = xf ** 3 * (xf * (xf * 6 - 15) + 10), yf ** 3 * (yf * (yf * 6 - 15) + 10)
    n00, n10 = g(xi, yi, xf, yf), g(xi + 1, yi, xf - 1, yf)
    n01, n11 = g(xi, yi + 1, xf, yf - 1), g(xi + 1, yi + 1, xf - 1, yf - 1)
    return (n00 * (1 - u) + n10 * u) * (1 - v) + (n01 * (1 - u) + n11 * u) * v
