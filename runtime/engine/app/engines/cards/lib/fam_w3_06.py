"""Helpers of runners/fam_w3_06.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from pathlib import Path
from .core import fx
import json
import math
import re
import shutil
import subprocess


def _np():
    import numpy as np
    return np


def tw(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def wj(path, obj):
    return tw(path, json.dumps(obj, ensure_ascii=False, indent=1))


def save_png(arr, path):
    from PIL import Image
    Image.fromarray(_np().clip(arr, 0, 255).round().astype("uint8")).save(path)
    return Path(path)


def load_png(path):
    from PIL import Image
    return _np().asarray(Image.open(path).convert("RGB")).astype(float)


def write_video(path, frames, fps=30, lossless=True, audio=None):
    np = _np()
    frames = list(frames)
    h, w = frames[0].shape[:2]
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", "%dx%d" % (w, h), "-r", str(fps), "-i", "-"]
    if audio:
        cmd += ["-i", str(audio), *fx.fit_audio(len(frames) / fps), "-c:a", "aac", "-b:a", "128k", "-frames:v", str(len(frames))]
    cmd += (["-c:v", "libx264rgb", "-qp", "0", "-preset", "ultrafast"] if lossless else
            ["-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p"]) + [str(path)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    for f in frames:
        p.stdin.write(np.clip(f, 0, 255).round().astype("uint8").tobytes())
    p.stdin.close()
    if p.wait():
        raise RuntimeError("ffmpeg encode failed: %s" % p.stderr.read().decode(errors="replace")[-300:])
    return Path(path)


def read_video(path, size=None):
    np = _np()
    st = [s for s in fx.probe(path)["streams"] if s.get("codec_type") == "video"][0]
    w, h = (int(st["width"]), int(st["height"])) if size is None else size
    vf = [] if size is None else ["-vf", "scale=%d:%d" % size]
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), *vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, timeout=120, stdin=subprocess.DEVNULL).stdout
    return np.frombuffer(out, dtype=np.uint8).reshape(-1, h, w, 3).astype(float)


def contact_sheet(imgs, cols, path, pad=4, bg=24):
    np = _np()
    h, w = imgs[0].shape[:2]
    rows = int(math.ceil(len(imgs) / float(cols)))
    sheet = np.full((rows * (h + pad) + pad, cols * (w + pad) + pad, 3), float(bg))
    for i, im in enumerate(imgs):
        r, c = divmod(i, cols)
        sheet[pad + r * (h + pad): pad + r * (h + pad) + h, pad + c * (w + pad): pad + c * (w + pad) + w] = im
    return save_png(sheet, path)


def lum_rel(rgb):
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in [v / 255.0 for v in rgb]]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b):
    la, lb = sorted([lum_rel(a), lum_rel(b)], reverse=True)
    return (la + 0.05) / (lb + 0.05)


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def phash(img, size=32, keep=8):
    """Perceptual hash: DCT of the 32x32 grey image, top-left 8x8 above the median."""
    np = _np()
    from PIL import Image
    from scipy.fft import dctn
    g = np.asarray(Image.fromarray(np.clip(img, 0, 255).astype("uint8")).convert("L").resize((size, size), Image.BILINEAR), float)
    d = dctn(g, norm="ortho")[:keep, :keep].flatten()
    return d[1:] > np.median(d[1:])


def hamming(a, b):
    return int((a != b).sum())


def red_x(img):
    np = _np()
    m = (img[..., 0] > 200) & (img[..., 1] < 100) & (img[..., 2] < 100)
    xs = np.nonzero(m)[1]
    return float(xs.min()) if len(xs) else -1.0


def texture(seed, h, w, block=8, lo=40, hi=220):
    np = _np()
    r = np.random.default_rng(seed)
    base = r.uniform(lo, hi, (h // block + 1, w // block + 1, 3))
    return np.kron(base, np.ones((block, block, 1)))[:h, :w]


def moving_shot(seed, n, h, w, step=2):
    np = _np()
    big = texture(seed, h, w * 3)
    return [np.roll(big, -step * i, axis=1)[:, :w].copy() for i in range(n)]


def tone_wav(path, seconds, freq=440.0, amp=0.25, rate=48000, beeps=None):
    """A tone (or silence with short beeps at the given times) as 16-bit WAV."""
    np = _np()
    t = np.arange(int(seconds * rate)) / rate
    if beeps is None:
        y = amp * np.sin(2 * np.pi * freq * t)
    else:
        y = np.zeros_like(t)
        for b in beeps:
            m = (t >= b) & (t < b + 0.05)
            y[m] = amp * np.sin(2 * np.pi * freq * t[m])
    return fx.write_wav(path, y, rate)


def energy(frames):
    np = _np()
    return np.abs(np.diff(frames, axis=0)).mean(axis=(1, 2, 3))


def lapvar(img):
    np = _np()
    g = img.mean(axis=2) if img.ndim == 3 else img
    lap = g[1:-1, 1:-1] * 4 - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:]
    return float(lap.var())


def _walker(frame, n, swing=28.0, bob=4.0, H=120, W=100):
    """Stick figure: legs swing +-swing deg, hips lowest at contact (max spread), highest at passing."""
    from PIL import Image, ImageDraw
    ph = 2 * math.pi * frame / n
    a = math.radians(swing) * math.cos(ph)
    hip_y = 70 - bob * (1 - abs(math.cos(ph))) if swing else 70.0
    im = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(im)
    hx = W // 2
    d.ellipse([hx - 7, hip_y - 52, hx + 7, hip_y - 38], fill=255)
    d.line([hx, hip_y - 38, hx, hip_y], fill=255, width=4)
    L = 40
    for s in (1, -1):
        d.line([hx, hip_y, hx + s * L * math.sin(a), hip_y + L * math.cos(a)], fill=255, width=4)
    return _np().asarray(im, float)


def _beat_film(path, dead=(3, 5), seconds=8, W=160, H=90, fps=30, seed=21):
    np = _np()
    shot = moving_shot(seed, seconds * fps, H, W, 2)
    fr = []
    for i in range(seconds * fps):
        s = i // fps
        fr.append(shot[dead[0] * fps] if dead and dead[0] <= s < dead[1] else shot[i])
    return write_video(path, fr, fps)


def copy_tree(src, dst, ignore=("__pycache__", "node_modules", ".git", "out", "renders")):
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*ignore))
    return Path(dst)


def mutate(path, old, new):
    t = Path(path).read_text(encoding="utf-8")
    if old not in t:
        raise RuntimeError("mutation anchor not found in %s" % path)
    Path(path).write_text(t.replace(old, new, 1), encoding="utf-8")


def _overlap_score(task, option):
    tw_ = set(re.findall(r"\w+", task.lower()))
    ow = set(re.findall(r"\w+", option.lower()))
    return len(tw_ & ow) / float(len(ow) or 1)


def _rig(frames=48, phase=0.0, rigid=False, rubber=False, slide=False):
    """Planar character rig by forward kinematics (pelvis, knee, foot per leg) -> joints (F, 5, 2). The root advances
    so the stance foot (the lower one) stays planted; `slide` adds a drift that drags the planted foot."""
    np = _np()
    out, root_x, prev = [], 0.0, None
    for f in range(frames):
        ph = 2 * math.pi * f / frames + phase
        rel = []
        for side in (0, math.pi):
            a = 0.4 * math.sin(ph + side) if not rigid else 0.0
            thigh = 0.5 * (1 + (0.25 * math.sin(ph * 2) if rubber else 0))
            knee = thigh * np.array([math.sin(a), -math.cos(a)])
            foot = knee + 0.5 * np.array([math.sin(a * 0.5), -math.cos(a * 0.5)])
            foot = foot + np.array([0.0, 0.1 * max(0.0, math.cos(ph + side))]) if not rigid else foot   # swing foot lifts
            rel.append((knee, foot))
        y0, y1 = rel[0][1][1], rel[1][1][1]
        stance = 0 if y0 < y1 - 1e-12 else 1 if y1 < y0 - 1e-12 else (prev[0] if prev else 0)
        if prev is not None and prev[0] == stance:
            root_x -= rel[stance][1][0] - prev[1]
        if slide:
            root_x += 0.02
        prev = (stance, rel[stance][1][0])
        pelvis = np.array([root_x, 1.0])
        js = [pelvis] + [pelvis + v for kn, ft in rel for v in (kn, ft)]
        if rigid:
            rot = 0.3 * math.sin(ph)
            R = np.array([[math.cos(rot), -math.sin(rot)], [math.sin(rot), math.cos(rot)]])
            js = [pelvis + R @ (jj - pelvis) for jj in js]
        out.append(js)
    return np.array(out)
