"""Helpers of runners/fam_w3_12.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from PIL import Image
from pathlib import Path
import json
import math
import numpy as np
import re
import subprocess


def jw(path, obj):
    path = Path(path)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=lambda o: float(o) if hasattr(o, "__float__") else str(o)),
                    encoding="utf-8")
    return path


def to8(a):
    return np.clip(np.rint(np.asarray(a, float) * 255), 0, 255).astype(np.uint8)


def save(a, p):
    Image.fromarray(to8(a)).save(str(p))
    return Path(p)


def luma(a):
    a = np.asarray(a, float)
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


def gblur(a, s):
    from scipy.ndimage import gaussian_filter
    a = np.asarray(a, float)
    if a.ndim == 3:
        return np.stack([gaussian_filter(a[..., c], s) for c in range(a.shape[2])], -1)
    return gaussian_filter(a, s)


def write_video(path, frames, fps=30, crf="17", extra=()):
    frames = [to8(f) for f in frames]
    h, w = frames[0].shape[:2]
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (w, h),
           "-r", str(fps), "-i", "-", "-c:v", "libx264", "-crf", crf, "-pix_fmt", "yuv420p", *extra, str(path)]
    done = subprocess.run(cmd, input=b"".join(f.tobytes() for f in frames), capture_output=True, timeout=60)
    if done.returncode:
        raise RuntimeError(done.stderr.decode(errors="replace")[-300:])
    return Path(path)


def png_arr(path):
    return np.asarray(Image.open(str(path)).convert("RGB")).astype(float)


def _bezier(p0, p1, p2, p3, n=2000):
    t = np.linspace(0, 1, n)[:, None]
    pts = (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3
    seg = np.hypot(*np.diff(pts, axis=0).T)
    s = np.concatenate([[0], np.cumsum(seg)])
    return pts, s


def lens_pass(img, k=0.04, ca=1.5, bloom=0.35, thr=0.72, vig=0.35, grain=0.02, seed=1):
    """The owner lens.py method in numpy: barrel bulge k, radial chromatic aberration ca px at the corner, bloom from
    highlights above thr at three radii (h * .006 / .02 / .06, weights .7 / 1 / .45, screen blend, auto-off on bright frames),
    vignette, grain."""
    from scipy.ndimage import map_coordinates
    H, W = img.shape[:2]
    yy, xx = np.mgrid[:H, :W].astype(float)
    cx, cy = (W - 1) / 2, (H - 1) / 2
    R = math.hypot(cx, cy)
    nx, ny = (xx - cx) / R, (yy - cy) / R
    r2 = nx * nx + ny * ny
    out = np.zeros_like(img)
    for c, sh in ((0, ca), (1, 0.0), (2, -ca)):
        scale = (1 + sh / R * 1.0)          # channel scale: red pushed out by ca px at the corner, blue pulled in
        sx = cx + (xx - cx) / (1 + k * r2) / scale
        sy = cy + (yy - cy) / (1 + k * r2) / scale
        out[..., c] = map_coordinates(img[..., c], [sy, sx], order=1, mode="nearest")
    L = luma(out)
    if bloom > 0 and L.mean() < 0.6:
        hi = np.clip(out - thr, 0, None) / (1 - thr)
        b = sum(w * gblur(hi, max(0.5, H * f)) for w, f in ((0.7, 0.006), (1.0, 0.02), (0.45, 0.06))) * bloom
        out = 1 - (1 - out) * (1 - np.clip(b, 0, 1))
    v = 1 - vig * np.clip(r2, 0, 1)
    out = out * v[..., None]
    if grain > 0:
        out = out + np.random.default_rng(seed).normal(0, grain, out.shape[:2])[..., None]
    return np.clip(out, 0, 1)


def _haversine(a, b):
    R = 6371.0088
    la1, lo1, la2, lo2 = map(math.radians, (a[1], a[0], b[1], b[0]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def _bearing(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[1], a[0], b[1], b[0]))
    y = math.sin(lo2 - lo1) * math.cos(la2)
    x = math.cos(la1) * math.sin(la2) - math.sin(la1) * math.cos(la2) * math.cos(lo2 - lo1)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def resolve_service(service, tools, env):
    """name exactly what is needed when no tool covers a service; never echo a secret, never ask for it in chat"""
    s = service.lower()
    t = [x for x in tools if s in x.lower()]
    if t:
        return {"status": "tool", "use": t[0]}
    keyname = re.sub(r"[^A-Z0-9]", "_", service.upper()) + "_API_KEY"
    if env.get(keyname):
        return {"status": "key-present", "env": keyname, "note": "a key is set; call the service with it from code"}
    return {"status": "missing", "connector": "claude.ai Settings -> Connectors -> connect %s" % service,
            "secret": "or add %s as an environment secret (read_documentation environment.secrets)" % keyname,
            "never": "do not paste the key into the chat"}


ELEVEN_MODELS = {"eleven_flash_v2_5": {"ttfb_ms": 75, "credit_per_char": 0.5, "expr": 1}, "eleven_turbo_v2_5": {"ttfb_ms": 150, "credit_per_char": 0.5, "expr": 2},
                 "eleven_multilingual_v2": {"ttfb_ms": 300, "credit_per_char": 1.0, "expr": 3}, "eleven_v3": {"ttfb_ms": 500, "credit_per_char": 1.0, "expr": 4, "arabic": True}}


def pick_eleven(use, chars, budget_ms=None):
    if use == "realtime":
        m = min((k for k in ELEVEN_MODELS if budget_ms is None or ELEVEN_MODELS[k]["ttfb_ms"] <= budget_ms), key=lambda k: ELEVEN_MODELS[k]["ttfb_ms"])
    elif use == "narration":
        m = "eleven_multilingual_v2"
    else:                                        # maximum expression (70+ languages incl. Arabic)
        m = max(ELEVEN_MODELS, key=lambda k: ELEVEN_MODELS[k]["expr"])
    return {"model": m, "credits": chars * ELEVEN_MODELS[m]["credit_per_char"], "ttfb_ms": ELEVEN_MODELS[m]["ttfb_ms"]}


def split_script(text, limit=5000):
    sents = re.findall(r"[^.!?؟。]+[.!?؟。]?\s*", text)
    chunks, cur = [], ""
    for s in sents:
        if len(cur) + len(s) > limit and cur:
            chunks.append(cur.strip())
            cur = ""
        cur += s
    if cur.strip():
        chunks.append(cur.strip())
    return [{"text": c, "previous_text": chunks[i - 1][-300:] if i else None, "next_text": chunks[i + 1][:300] if i + 1 < len(chunks) else None}
            for i, c in enumerate(chunks)]


TTS_ORDER = [("heygen-starfish", "HEYGEN_API_KEY", True), ("elevenlabs", "ELEVENLABS_API_KEY", False), ("kokoro-82m", None, False)]


def validate_speed(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not (0.5 <= float(v) <= 2.0):
        raise ValueError("speed must be a positive number in 0.5..2.0, got %r" % (v,))
    return float(v)


def pick_tts(env, local_models):
    for name, key, ts in TTS_ORDER:
        if (key and env.get(key)) or (key is None and name in local_models):
            return {"provider": name, "word_timestamps": ts, "needs_transcription": not ts}
    return {"provider": None, "reason": "no provider: set HEYGEN_API_KEY or ELEVENLABS_API_KEY, or install a local model"}
