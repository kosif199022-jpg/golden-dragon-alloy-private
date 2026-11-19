"""Helpers of runners/fam_w3_11.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from pathlib import Path
from .core import fx
import json
import math
import re
import subprocess


FONTS = Path(__import__("os").environ.get("KOSIF_FONTS") or Path.home() / "kosif-tool" / ".claude" / "skills" / "kosif-superpowers" / "proofs" / "_shared" / "fonts")  # read-only asset in the old repo


def _np():
    import numpy as np
    return np


def jw(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return Path(path)


def tw(path, text):
    Path(path).write_text(text, encoding="utf-8")
    return Path(path)


def font(name="Poppins-Bold.ttf", size=40):
    from PIL import ImageFont
    return ImageFont.truetype(str(FONTS / name), size)


def save_png(arr, path):
    from PIL import Image
    Image.fromarray(_np().clip(arr, 0, 255).round().astype("uint8")).save(path)
    return Path(path)


def load_rgb(path):
    from PIL import Image
    return _np().asarray(Image.open(path).convert("RGB")).astype(float)


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


def duration(path):
    return float(fx.probe(path)["format"]["duration"])


def ink_bbox(arr, bg=(255, 255, 255), tol=40):
    """Bounding box (x0, y0, x1, y1) of pixels that differ from the background, or None."""
    np = _np()
    a = np.asarray(arr, dtype=float)
    if a.ndim == 2:
        m = np.abs(a - (bg if np.isscalar(bg) else bg[0])) > tol
    else:
        m = np.abs(a - np.array(bg, dtype=float)).max(axis=-1) > tol
    ys, xs = np.nonzero(m)
    if not len(xs):
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def color_mask(arr, rgb, tol=30):
    np = _np()
    return np.abs(np.asarray(arr, dtype=float) - np.array(rgb, dtype=float)).max(axis=-1) <= tol


def centroid(mask):
    np = _np()
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return None
    return float(xs.mean()), float(ys.mean())


def bezier(x1, y1, x2, y2):
    """CSS cubic-bezier(x1, y1, x2, y2) as a function of progress 0..1 (Newton + bisection)."""
    def bx(t):
        return 3 * (1 - t) ** 2 * t * x1 + 3 * (1 - t) * t ** 2 * x2 + t ** 3

    def by(t):
        return 3 * (1 - t) ** 2 * t * y1 + 3 * (1 - t) * t ** 2 * y2 + t ** 3

    def f(x):
        x = min(1.0, max(0.0, x))
        lo, hi = 0.0, 1.0
        for _ in range(60):
            mid = (lo + hi) / 2
            if bx(mid) < x:
                lo = mid
            else:
                hi = mid
        return by((lo + hi) / 2)
    return f


def ease_in_out_cubic(p):
    p = min(1.0, max(0.0, p))
    return 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2


def ease_out_cubic(p):
    p = min(1.0, max(0.0, p))
    return 1 - (1 - p) ** 3


def ease_in_cubic(p):
    p = min(1.0, max(0.0, p))
    return p ** 3


def ease_out_quart(p):
    p = min(1.0, max(0.0, p))
    return 1 - (1 - p) ** 4


def sine_in_out(p):
    p = min(1.0, max(0.0, p))
    return -(math.cos(math.pi * p) - 1) / 2


def interp(t, ts, vs, ease=None):
    """Remotion-style interpolate(frame, [t0..tn], [v0..vn], {easing, clamp})."""
    if t <= ts[0]:
        return vs[0]
    if t >= ts[-1]:
        return vs[-1]
    for i in range(len(ts) - 1):
        if ts[i] <= t <= ts[i + 1]:
            p = (t - ts[i]) / float(ts[i + 1] - ts[i])
            return vs[i] + (vs[i + 1] - vs[i]) * (ease(p) if ease else p)
    return vs[-1]


def texture(w, h, seed=7):
    """Deterministic textured plate (blurred noise + grid) that image registration can lock onto."""
    np = _np()
    import cv2
    rng = np.random.default_rng(seed)
    a = rng.random((h, w)).astype("float32")
    a = cv2.GaussianBlur(a, (0, 0), 3)
    a = (a - a.min()) / (a.max() - a.min()) * 200 + 20
    a[::40, :] = 250
    a[:, ::40] = 250
    return np.dstack([a, a * 0.8 + 30, 255 - a]).clip(0, 255)


def warp(img, s=1.0, tx=0.0, ty=0.0, rot=0.0, out=None):
    """One camera transform (scale about the centre, rotate in degrees, translate in px) as one affine matrix."""
    import cv2
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), -rot, s)
    M[0, 2] += tx
    M[1, 2] += ty
    ow, oh = out or (w, h)
    return cv2.warpAffine(img.astype("float32"), M, (ow, oh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)


MARKS = [((255, 0, 0), 0.3, 0.3), ((0, 255, 0), 0.7, 0.3), ((0, 0, 255), 0.7, 0.7), ((255, 255, 0), 0.3, 0.68)]


def fid_plate(w, h, seed=7):
    """Grey textured plate with four coloured fiducial dots, so a camera transform can be measured exactly."""
    np = _np()
    t = texture(w, h, seed).mean(axis=-1, keepdims=True) * 0.5 + 60
    a = np.repeat(t, 3, axis=-1)
    yy, xx = np.mgrid[0:h, 0:w]
    r = max(3, w // 48)
    for col, fx_, fy_ in MARKS:
        a[(xx - fx_ * w) ** 2 + (yy - fy_ * h) ** 2 <= r * r] = col
    return a


def marks(img, tol=70):
    np = _np()
    pts = []
    a = np.asarray(img, float)
    ys, xs = np.mgrid[0:a.shape[0], 0:a.shape[1]]
    for col, _, _ in MARKS:
        d = np.abs(a - np.array(col, float)).max(axis=-1)
        wgt = np.clip(1 - d / 90.0, 0, 1)
        if wgt.sum() < 3:
            return None
        pts.append(((xs * wgt).sum() / wgt.sum(), (ys * wgt).sum() / wgt.sum()))
    return np.array(pts)


def est(ref, img):
    """Measure the camera transform (scale, tx, ty, rot deg) mapping ref onto img from the fiducial dots (Umeyama)."""
    np = _np()
    P, Q = marks(ref), marks(img)
    if P is None or Q is None:
        raise RuntimeError("fiducials not visible")
    mp, mq = P.mean(0), Q.mean(0)
    X, Y = P - mp, Q - mq
    U, S, Vt = np.linalg.svd(Y.T @ X / len(P))
    D = np.diag([1, np.sign(np.linalg.det(U @ Vt))])
    R = U @ D @ Vt
    sc = float(np.trace(np.diag(S) @ D) / (X ** 2).sum(axis=1).mean())
    t = mq - sc * R @ mp
    h, w = ref.shape[:2]
    c = np.array([w / 2.0, h / 2.0])
    tc = sc * R @ c + t - c
    return sc, float(tc[0]), float(tc[1]), float(math.degrees(math.atan2(R[1, 0], R[0, 0])))


def index_clip(wd, name, n, fps=30, w=160, h=90):
    """A clip whose frame i is painted with gray level 4*(i % 60) plus a binary code of i in 8 blocks."""
    np = _np()
    frames = []
    for i in range(n):
        f = np.full((h, w, 3), 0.0)
        f[:h // 2] = (i * 4) % 240
        for b in range(8):
            f[h // 2:, b * (w // 8):(b + 1) * (w // 8)] = 255.0 if (i >> b) & 1 else 0.0
        frames.append(f)
    return write_video(Path(wd) / name, frames, fps)


def frame_index(f):
    h, w = f.shape[:2]
    bits = [f[3 * h // 4, b * (w // 8) + w // 16].mean() > 127 for b in range(8)]
    return sum(1 << b for b, on in enumerate(bits) if on)


def _ebur(p):
    e = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(p), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, timeout=60).stderr
    i = float(re.findall(r"I:\s+(-?[0-9.]+) LUFS", e)[-1])
    tp = re.findall(r"Peak:\s+(-?[0-9.]+) dBFS", e)
    return i, float(tp[-1]) if tp else None


def beat_bpm(x, sr, hop=256, gap=0.2):
    np = _np()
    n = len(x) // hop
    e = np.array([np.sum(x[i * hop:(i + 1) * hop] ** 2) for i in range(n)])
    flux = np.maximum(0, np.diff(e, prepend=e[0]))
    thr = flux.mean() + 2 * flux.std()
    peaks, last = [], -1e9
    for i in range(1, n - 1):
        if flux[i] > thr and flux[i] >= flux[i - 1] and flux[i] >= flux[i + 1] and (i - last) * hop / sr >= gap:
            peaks.append(i * hop / sr)
            last = i
    if len(peaks) < 3:
        return None, peaks
    return 60.0 / float(np.median(np.diff(peaks))), peaks


def band_rms(x, sr, f0, t0, t1):
    np = _np()
    seg = x[int(t0 * sr):int(t1 * sr)]
    t = np.arange(len(seg)) / sr
    c = np.mean(seg * np.cos(2 * np.pi * f0 * t)) * 2
    s = np.mean(seg * np.sin(2 * np.pi * f0 * t)) * 2
    return math.hypot(c, s)


def _render_moves(plate, moves):
    return [warp(plate, *m) for m in moves]


def _layer(w, h, col, x0, y0, x1, y1):
    np = _np()
    a = np.zeros((h, w, 4))
    a[y0:y1, x0:x1, :3] = col
    a[y0:y1, x0:x1, 3] = 1
    return a


def _comp(layers, offsets, w, h, bg=(10, 10, 10)):
    np = _np()
    out = np.zeros((h, w, 3))
    out[:] = bg
    for L, dx in zip(layers, offsets):
        sh = np.roll(L, int(round(dx)), axis=1)
        a = sh[..., 3:4]
        out = out * (1 - a) + sh[..., :3] * a
    return out


def _clamp_path(prop, fps, max_push, max_pan, max_rot):
    """Enforce camera limits on a proposed per-frame path; low-pass to remove shake."""
    np = _np()
    s = np.array([p[0] for p in prop])
    x = np.array([p[1] for p in prop])
    r = np.array([p[3] for p in prop])
    k = 15
    sm = lambda a: np.convolve(np.pad(a, (k // 2, k // 2), mode="edge"), np.ones(k) / k, mode="valid")  # noqa: E731
    s, x, r = sm(s), sm(x), sm(r)
    s = np.clip(s, 1.0, 1.0 + max_push)
    r = np.clip(r, -max_rot, max_rot)
    out_x = [x[0]]
    for v in x[1:]:
        step = max(-max_pan / fps, min(max_pan / fps, v - out_x[-1]))
        out_x.append(out_x[-1] + step)
    return [(float(a), float(b), 0.0, float(c)) for a, b, c in zip(s, out_x, r)]


def _path_stats(meas, fps):
    np = _np()
    s = np.array([m[0] for m in meas])
    x = np.array([m[1] for m in meas])
    r = np.array([m[3] for m in meas])
    acc = np.diff(x, 2)
    return {"push": float(s.max() - 1), "pan_px_s": float(np.abs(np.diff(x)).max() * fps), "rot": float(np.abs(r).max()),
            "shake": float(np.abs(acc).max())}


def _device_rect(aspect, W):
    """Device frame size for the canvas aspect: 9:16 -> 62 % height, 16:9 -> 80 % height on the right third line, 1:1 -> 70 %."""
    H = int(round(W / aspect))
    share = {"9:16": 0.62, "16:9": 0.80, "1:1": 0.70}
    key = "9:16" if aspect < 0.8 else ("16:9" if aspect > 1.2 else "1:1")
    dh = share[key] * H
    dw = dh * 9 / 19.5
    cx = W * 2 / 3 if key == "16:9" else W / 2
    return key, W, H, (cx - dw / 2, H / 2 - dh / 2, cx + dw / 2, H / 2 + dh / 2)


def _face_img(W, H, cx, cy, r):
    np = _np()
    yy, xx = np.mgrid[0:H, 0:W]
    a = np.full((H, W, 3), 200.0)
    a[(xx - cx) ** 2 + ((yy - cy) / 1.25) ** 2 < r * r] = (225, 180, 150)
    for ex in (cx - r * 0.38, cx + r * 0.38):
        a[(xx - ex) ** 2 + (yy - (cy - r * 0.2)) ** 2 < (r * 0.1) ** 2] = (20, 20, 20)
    return a


def _skill_dirs():
    roots = [Path("/mnt/skills/public"), Path.home() / ".claude/skills"]
    out = []
    for r in roots:
        if r.is_dir():
            out += [p.parent for p in r.rglob("SKILL.md")]
    return out


def _pick_skill(request, skills):
    words = set(re.findall(r"[a-z]+", request.lower()))
    best, score = None, 0
    for d in skills:
        head = (d / "SKILL.md").read_text(encoding="utf-8", errors="replace")[:1500].lower()
        m = re.search(r"^description:(.*)$", head, re.M)
        desc = (m.group(1) if m else head)
        s = sum(desc.count(w) for w in words if len(w) > 3)
        if d.name in words:
            s += 10
        if s > score:
            best, score = d, s
    return best, score


def canvas_img(W, H, bg=(255, 255, 255)):
    from PIL import Image
    return Image.new("RGB", (W, H), bg)


def arr(im):
    return _np().asarray(im).astype(float)


def mask_bbox(a, rgb, tol=40):
    np = _np()
    m = color_mask(a, rgb, tol)
    ys, xs = np.nonzero(m)
    if not len(xs):
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


NUM_WORDS = {"two times": "2x", "three times": "3x", "ten times": "10x"}


STOP = set("a an the and or but our your it is are be to of for in on at with than that this every one old new nothing extra "
           "today its".split())


def fit_copy(narration, aspect="9:16"):
    """TYPE-02: one idea per screen; a hero stat plus a few content words; lines 14-22 chars at phrase boundaries."""
    text = narration.lower()
    for k, v in NUM_WORDS.items():
        text = text.replace(k, v)
    phrases = [p.strip() for p in re.split(r",| and ", text) if p.strip()]
    cap = 7 if aspect == "9:16" else 12
    hero_phrase = next((p for p in phrases if re.search(r"\d+x|\$\d|\d+%", p)), phrases[0])
    words = [w for w in re.findall(r"[\w$%]+", hero_phrase) if w not in STOP]
    stat = next(w for w in words if re.match(r"\d+x|\$\d|\d+%", w))
    i = words.index(stat)
    core = words[max(0, i - 1):i + 2]  # verb + stat + adjective: "renders 2x faster"
    lines = [" ".join(core).capitalize()]
    rest = [w for w in re.findall(r"[\w$%]+", phrases[-1]) if w not in STOP][:3]
    if rest and len(" ".join(rest)) >= 10:
        lines.append(" ".join(rest).capitalize())
    lines = [l for l in lines if 14 <= len(l) <= 22] or lines[:1]  # portrait line length 14-22 characters
    words_out = sum(len(l.split()) for l in lines)
    while words_out > min(cap, 6):
        lines.pop()
        words_out = sum(len(l.split()) for l in lines)
    return lines, stat


def hold_after_landing(line):
    return 0.3 + 0.06 * len(line)


def card_seconds(n_words):
    return max(0.5, 0.4 * n_words)


def draw_tracked(d, xy, text, f, spacing, fill):
    """Draw text with extra letter-spacing (px), glyph by glyph using real advances."""
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=f, fill=fill)
        x += f.getlength(ch) + spacing
    return x


def _digit_templates(f, h):
    np = _np()
    from PIL import ImageDraw
    T = {}
    for dgt in "0123456789":
        im = canvas_img(40, h, (0, 0, 0))
        ImageDraw.Draw(im).text((20, h / 2), dgt, font=f, fill=(255, 255, 255), anchor="mm")
        T[dgt] = arr(im).mean(axis=-1)
    return T


def _digit_tape(f, ch):
    """The 0-9 column as one tall strip (0..9 then 0), drawn exactly like the animation."""
    from PIL import ImageDraw
    im = canvas_img(40, ch * 11, (0, 0, 0))
    d = ImageDraw.Draw(im)
    for k in range(11):
        d.text((20, ch / 2 + k * ch), str(k % 10), font=f, fill=(255, 255, 255), anchor="mm")
    return arr(im).mean(axis=-1).astype("float32")


def _tape_offset(cell, tape, ch):
    """Where on the 0-9 tape a column window sits, in rows (0..10), by template matching."""
    import cv2
    r = cv2.matchTemplate(tape, cell.mean(axis=-1).astype("float32"), cv2.TM_SQDIFF)
    y = int(r[:, 0].argmin())
    return (y / ch) % 10


def _read_digit(cell, T):
    np = _np()
    g = cell.mean(axis=-1)
    return min(T, key=lambda k: float(np.abs(T[k] - g).mean()))


def spring(t, v0=2.8, k=180.0, c=12.0):
    """Damped spring displacement (m = 1) starting at 0 with velocity v0: stiffness k, damping c."""
    w0 = math.sqrt(k)
    z = c / (2 * w0)
    wd_ = w0 * math.sqrt(1 - z * z)
    return v0 / wd_ * math.exp(-z * w0 * t) * math.sin(wd_ * t)
