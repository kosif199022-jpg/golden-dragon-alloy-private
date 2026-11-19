"""Helpers of power_programs/photo_video_footage.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from pathlib import Path
import colorsys
import json
import numpy as np
import subprocess
import wave
from .core import fx


FF = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]


def ff(*args, inp: bytes | None = None) -> subprocess.CompletedProcess:
    r = subprocess.run(FF + [str(a) for a in args], input=inp, capture_output=True, timeout=60)
    if r.returncode:
        raise RuntimeError(r.stderr.decode()[-600:])
    return r


def ffstderr(*args) -> str:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-y"] + [str(a) for a in args],
                       capture_output=True, timeout=60)
    return r.stderr.decode(errors="replace")


def probe(path, *entries) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams",
                        "-show_format", str(path)], capture_output=True, timeout=30)
    return json.loads(r.stdout or b"{}")


def vstream(path) -> dict:
    return next(s for s in probe(path)["streams"] if s["codec_type"] == "video")


def astreams(path) -> list:
    return [s for s in probe(path).get("streams", []) if s["codec_type"] == "audio"]


def duration(path) -> float:
    return float(probe(path)["format"]["duration"])


def write_video(path, frames, fps=30, codec="ffv1", extra=(), audio: Path | None = None):
    frames = np.asarray(frames, dtype=np.uint8)
    n, h, w, _ = frames.shape
    args = ["-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-"]
    if audio:
        args += ["-i", str(audio), *fx.fit_audio(n / fps), "-c:a", "aac", "-frames:v", str(n)]
    if codec == "ffv1":
        args += ["-c:v", "ffv1", "-pix_fmt", "bgr0"]
    else:
        args += ["-c:v", codec, "-pix_fmt", "yuv420p", "-preset", "ultrafast", "-crf", "1"]
    ff(*args, *extra, path, inp=frames.tobytes())
    return Path(path)


def read_video(path, size=None) -> np.ndarray:
    st = vstream(path)
    w, h = (size or (int(st["width"]), int(st["height"])))
    vf = ["-vf", f"scale={w}:{h}"] if size else []
    r = subprocess.run(FF + ["-i", str(path), *vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                       capture_output=True, timeout=60)
    a = np.frombuffer(r.stdout, np.uint8)
    return a.reshape(-1, h, w, 3)


def write_wav(path, x, sr=16000, ch=1):
    x = np.clip(np.asarray(x, dtype=np.float64), -1, 1)
    pcm = (x * 32767).astype("<i2")
    with wave.open(str(path), "wb") as wv:
        wv.setnchannels(ch)
        wv.setsampwidth(2)
        wv.setframerate(sr)
        wv.writeframes(pcm.tobytes())
    return Path(path)


def read_wav(path):
    with wave.open(str(path)) as wv:
        sr, ch, n = wv.getframerate(), wv.getnchannels(), wv.getnframes()
        x = np.frombuffer(wv.readframes(n), "<i2").astype(np.float64) / 32767
    return (x.reshape(-1, ch).mean(1) if ch > 1 else x), sr


def decode_audio(path, sr=16000):
    r = subprocess.run(FF + ["-i", str(path), "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
                       capture_output=True, timeout=60)
    return np.frombuffer(r.stdout, "<i2").astype(np.float64) / 32767


def tone(sec, f=440, sr=16000, amp=0.5):
    t = np.arange(int(sec * sr)) / sr
    return amp * np.sin(2 * np.pi * f * t)


def dom_freq(x, sr):
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    return np.fft.rfftfreq(len(x), 1 / sr)[int(np.argmax(spec))]


def solid(n, h, w, rgb):
    return np.tile(np.array(rgb, np.uint8), (n, h, w, 1))


def jwrite(work, name, obj):
    p = Path(work) / name
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return p


def luma(img):
    img = np.asarray(img, np.float64)
    return 0.2126 * img[..., 0] + 0.7152 * img[..., 1] + 0.0722 * img[..., 2]


def rel_lum(rgb):
    c = np.asarray(rgb, np.float64) / 255
    c = np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * c[..., 0] + 0.7152 * c[..., 1] + 0.0722 * c[..., 2]


def contrast(a, b):
    la, lb = sorted([float(rel_lum(a)), float(rel_lum(b))], reverse=True)
    return (la + 0.05) / (lb + 0.05)


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def near(a, b, tol):
    return abs(a - b) <= tol


def chk(name, ok, obs):
    return (name, bool(ok), str(obs))


def frame_index_frames(n, h=36, w=64):
    """Frame i encodes its index: R = (i % 16) * 16, G = (i // 16) * 16."""
    f = np.zeros((n, h, w, 3), np.uint8)
    for i in range(n):
        f[i, ..., 0] = (i % 16) * 16 + 8
        f[i, ..., 1] = (i // 16) * 12 + 8
    return f


def decode_index(frame):
    r, g = frame[..., 0].mean(), frame[..., 1].mean()
    return int(round((g - 8) / 12)) * 16 + int(round((r - 8) / 16))


def detect_cuts(frames, fps, threshold=10.0, min_len=0.5):
    """Mean abs diff in 0-100 scale; cut where > threshold and >= min_len after last cut."""
    f = frames.astype(np.float64)
    d = np.abs(np.diff(f, axis=0)).mean(axis=(1, 2, 3)) / 255 * 100
    cuts, last = [], 0.0
    for i, v in enumerate(d, start=1):
        t = i / fps
        if v > threshold and t - last >= min_len:
            cuts.append(round(t, 3))
            last = t
    return cuts, d


def motion_energy(frames, src_fps, fps=6):
    step = max(1, round(src_fps / fps))
    s = frames[::step].astype(np.float64).mean(-1)
    return np.abs(np.diff(s, axis=0)).mean(axis=(1, 2)), step


def exposure(img):
    y = luma(img)
    p = np.percentile(y, [1, 50, 99])
    clipped = float((y >= 250).mean() * 100)
    crushed = float((y <= 5).mean() * 100)
    mean = float(y.mean())
    if mean > 185 or clipped > 5:
        v = "over"
    elif mean < 60 or crushed > 15:
        v = "under"
    else:
        v = "ok"
    advice = []
    if clipped > 2:
        advice.append("خفّض التعريض: الإضاءات محترقة")
    if crushed > 10:
        advice.append("ارفع الظلال: الأسود مسحوق")
    if p[2] - p[0] < 120:
        advice.append("زد التباين: المدى ضيق")
    return {"verdict": v, "mean": round(mean, 1), "clipped": round(clipped, 2), "crushed": round(crushed, 2),
            "range": round(float(p[2] - p[0]), 1), "advice": advice}


def classify_boundaries(frames, fps):
    """cut = one big jump; dissolve = run of frames that are blends of the neighbours; fadeblack = luma hits 0."""
    f = frames.astype(np.float64)
    y = f.mean(axis=(1, 2, 3))
    d = np.abs(np.diff(f, axis=0)).mean(axis=(1, 2, 3))
    out, i = [], 0
    n = len(d)
    while i < n:
        if d[i] < 1.0:
            i += 1
            continue
        j = i
        while j + 1 < n and d[j + 1] >= 1.0:
            j += 1
        span = j - i + 1
        seg_y = y[i:j + 2]
        if seg_y.min() < 3 and (span > 1):
            kind = "fadeblack"
        elif span == 1:
            kind = "cut"
        else:
            kind = "dissolve"
        out.append({"kind": kind, "start": round((i + 1) / fps, 3), "frames": span})
        i = j + 1
    return out


def ramp_duration(ramp, src_len):
    """Programme time to consume src_len seconds with piecewise-linear speed [[t, speed]...] (t in source s)."""
    ts = np.linspace(0, src_len, 20001)
    sp = np.interp(ts, [r[0] for r in ramp], [r[1] for r in ramp])
    return float(np.trapezoid(1 / sp, ts))


def atempo_chain(f):
    parts = []
    while f < 0.5:
        parts.append(0.5)
        f /= 0.5
    while f > 2.0:
        parts.append(2.0)
        f /= 2.0
    parts.append(round(f, 6))
    return ",".join(f"atempo={p:g}" for p in parts)


def trim_counts(work):
    fr = frame_index_frames(300)
    src = work / "src.mp4"
    ff("-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "64x36", "-r", "30", "-i", "-", "-c:v", "libx264",
       "-preset", "ultrafast", "-g", "60", "-keyint_min", "60", "-sc_threshold", "0", "-crf", "5",
       "-pix_fmt", "yuv420p", src, inp=fr.tobytes())
    return src


def nframes(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                        "stream=nb_read_frames", "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return int(r.stdout.strip() or 0)


def shaky(n=40):
    rng = np.random.default_rng(7)
    base = np.kron(rng.integers(0, 255, (180 // 8, 320 // 8, 1)), np.ones((8, 8, 3))).astype(np.uint8)
    return np.stack([np.roll(np.roll(base, rng.integers(-3, 4), 0), rng.integers(-4, 5), 1) for _ in range(n)])


def global_shifts(frames):
    import cv2
    ref = luma(frames[0]).astype(np.float32)
    return np.array([cv2.phaseCorrelate(ref, luma(f).astype(np.float32))[0] for f in frames])


def recolor(img, src_hex, dst_hex, tolerance=40, keep_shading=True):
    hsv = np.array([[colorsys.rgb_to_hsv(*(p / 255)) for p in row] for row in img])
    sh, ss, sv = colorsys.rgb_to_hsv(*(np.array(hexrgb(src_hex)) / 255))
    dh, ds, dv = colorsys.rgb_to_hsv(*(np.array(hexrgb(dst_hex)) / 255))
    dhue = np.minimum(np.abs(hsv[..., 0] - sh), 1 - np.abs(hsv[..., 0] - sh)) * 360
    mask = (dhue <= tolerance) & (hsv[..., 1] > 0.25)
    out = hsv.copy()
    out[..., 0] = np.where(mask, dh, hsv[..., 0])
    if keep_shading:
        out[..., 1] = np.where(mask, np.clip(hsv[..., 1] * ds / max(ss, 1e-6), 0, 1), hsv[..., 1])
        out[..., 2] = np.where(mask, np.clip(hsv[..., 2] * dv / max(sv, 1e-6), 0, 1), hsv[..., 2])
    rgb = np.array([[colorsys.hsv_to_rgb(*p) for p in row] for row in out]) * 255
    return rgb.round().astype(np.uint8), mask


def spring(stiff, damp, t_end=1.5, dt=1 / 1000):
    x, v, xs = 0.0, 0.0, []
    for _ in range(int(t_end / dt)):
        a = stiff * (1 - x) - damp * v
        v += a * dt
        x += v * dt
        xs.append(x)
    return np.array(xs)


def back_out(p, s=1.6):
    p -= 1
    return 1 + (s + 1) * p ** 3 + s * p ** 2


def click_track(bpm, sec, sr=16000):
    x = np.zeros(int(sec * sr))
    step = 60 / bpm
    for k in range(int(sec / step) + 1):
        i = int(k * step * sr)
        n = min(160, len(x) - i)
        if n > 0:
            x[i:i + n] += np.sin(2 * np.pi * 1000 * np.arange(n) / sr) * np.exp(-np.arange(n) / 40)
    return x


def detect_beats(x, sr):
    hop = 160
    env = np.array([np.sqrt((x[i:i + hop] ** 2).mean()) for i in range(0, len(x) - hop, hop)])
    on = np.maximum(np.diff(env, prepend=0.0), 0)
    peaks = [i for i in range(1, len(on) - 1) if on[i] > 0.3 * on.max() and on[i] >= on[i - 1] and on[i] > on[i + 1]]
    times = np.array(peaks) * hop / sr
    bpm = 60 / np.median(np.diff(times))
    return times, bpm


def guided(I, p, r, eps):
    import cv2
    box = lambda x: cv2.boxFilter(x, -1, (2 * r + 1, 2 * r + 1))
    mI, mp = box(I), box(p)
    a = (box(I * p) - mI * mp) / (box(I * I) - mI * mI + eps)
    b = mp - a * mI
    return box(a) * I + box(b)
