"""Helpers of runners/fam_particles_fluids_physics.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from PIL import Image
from pathlib import Path
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


def _blur(a, s):
    from scipy.ndimage import gaussian_filter
    a = np.asarray(a, dtype=float)
    return gaussian_filter(a, (s, s) + ((0,) if a.ndim == 3 else ()))


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


def _disc(img, x, y, r, col, mode="max", alpha=1.0):
    H, W = img.shape[:2]
    x0, x1 = max(0, int(x - r - 2)), min(W, int(x + r + 3))
    y0, y1 = max(0, int(y - r - 2)), min(H, int(y + r + 3))
    if x0 >= x1 or y0 >= y1:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1]
    m = (np.hypot(yy - y, xx - x) <= r)[..., None]
    win = img[y0:y1, x0:x1]
    c = np.asarray(col, dtype=float) * alpha
    if mode == "add":
        win += m * c
    elif mode == "over":
        win[...] = win * (1 - m * alpha) + m * np.asarray(col, dtype=float) * alpha
    else:
        win[...] = np.where(m, np.maximum(win, c), win)


def _centroid(mask):
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return None
    return float(xs.mean()), float(ys.mean())


def _track(frames, ch=0, thr=40, others=(1, 2)):
    """Centroid of pixels lit in channel ch only (the tracked particle is drawn pure in that channel)."""
    out = []
    for f in frames:
        m = (f[..., ch] > thr) & np.all([f[..., o] < 20 for o in others], axis=0)
        out.append(_centroid(m))
    return out


def _quad_fit(t, y):
    c = np.polyfit(t, y, 2)
    res = float(np.abs(np.polyval(c, t) - y).max())
    return 2 * c[0], c[1], res


def _smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def _value_noise(shape, cell, seed, octaves=1):
    H, W = shape
    out, amp, tot = np.zeros(shape), 1.0, 0.0
    for o in range(octaves):
        c = max(1, cell / 2 ** o)
        gh, gw = int(H / c) + 3, int(W / c) + 3
        g = np.random.default_rng(seed + o).random((gh, gw))
        y, x = np.mgrid[:H, :W] / c
        y0, x0 = np.floor(y).astype(int), np.floor(x).astype(int)
        fy, fx_ = _smoothstep(0, 1, y - y0), _smoothstep(0, 1, x - x0)
        v = (g[y0, x0] * (1 - fx_) + g[y0, x0 + 1] * fx_) * (1 - fy) + (g[y0 + 1, x0] * (1 - fx_) + g[y0 + 1, x0 + 1] * fx_) * fy
        out += amp * v
        tot += amp
        amp *= .5
    return out / tot


RAMP7 = [(0, "#000010"), (.12, "#2a0a6b"), (.30, "#7b1fa2"), (.45, "#d81b60"), (.60, "#ff6d00"), (.78, "#ffd600"),
         (1.0, "#ffffff")]


def _ramp(v):
    xs = [p for p, _ in RAMP7]
    cs = np.array([_hex(c) for _, c in RAMP7])
    return np.stack([np.interp(v, xs, cs[:, k]) for k in range(3)], -1)


def _basma_rnd(i):
    v = math.sin(127.1 * i + 311.7) * 43758.5453
    return v - math.floor(v)
