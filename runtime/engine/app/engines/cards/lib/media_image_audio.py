"""Helpers of power_programs/media_image_audio.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from .photo_video_footage import ffstderr
import json
import math
import numpy as np


def deskew_angle(gray):
    import cv2
    g = cv2.medianBlur(gray, 3)
    _, b = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    b = cv2.morphologyEx(b, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    b = cv2.dilate(b, np.ones((5, 60), np.uint8))
    cs, _ = cv2.findContours(b, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    angs = []
    for c in cs:
        if cv2.contourArea(c) <= 5000:
            continue
        (cx, cy), (w, h), a = cv2.minAreaRect(c)
        if w < h:
            a -= 90
        angs.append(a)
    return float(np.median(angs)), len(angs)


def ssim(a, b):
    import cv2
    a, b = a.astype(np.float64), b.astype(np.float64)
    C1, C2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    vals = []
    for ch in range(3):
        x, y = a[..., ch], b[..., ch]
        mx, my = cv2.GaussianBlur(x, (11, 11), 1.5), cv2.GaussianBlur(y, (11, 11), 1.5)
        sx = cv2.GaussianBlur(x * x, (11, 11), 1.5) - mx * mx
        sy = cv2.GaussianBlur(y * y, (11, 11), 1.5) - my * my
        sxy = cv2.GaussianBlur(x * y, (11, 11), 1.5) - mx * my
        vals.append((((2 * mx * my + C1) * (2 * sxy + C2)) / ((mx * mx + my * my + C1) * (sx + sy + C2))).mean())
    return float(np.mean(vals))


def yin(x, sr, fmin=100, fmax=1000, frame=2048, hop=512, thresh=0.1):
    tmin, tmax = int(sr / fmax), int(sr / fmin)
    f0 = []
    for s in range(0, len(x) - frame - tmax, hop):
        w = x[s:s + frame + tmax]
        d = np.array([np.sum((w[:frame] - w[t:t + frame]) ** 2) for t in range(tmax + 1)])
        cmnd = np.ones_like(d)
        cmnd[1:] = d[1:] * np.arange(1, tmax + 1) / np.maximum(np.cumsum(d[1:]), 1e-12)
        cand = np.nonzero(cmnd[tmin:] < thresh)[0]
        t = (cand[0] + tmin) if len(cand) else int(np.argmin(cmnd[tmin:]) + tmin)
        while t + 1 <= tmax and cmnd[t + 1] < cmnd[t]:
            t += 1
        if 1 <= t < tmax:  # parabolic interpolation
            a, b, c = cmnd[t - 1], cmnd[t], cmnd[t + 1]
            t = t + 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) else t
        f0.append(sr / t)
    return np.array(f0)


def onsets(x, sr, hop=128):
    env = np.array([np.sqrt((x[i:i + hop] ** 2).mean()) for i in range(0, len(x) - hop, hop)])
    flux = np.maximum(np.diff(env, prepend=env[0]), 0)
    thr = 0.3 * flux.max()
    on, last = [], -1e9
    for i in range(1, len(flux) - 1):
        if flux[i] > thr and flux[i] >= flux[i - 1] and flux[i] > flux[i + 1] and i - last > 0.1 * sr / hop:
            on.append(i * hop / sr)
            last = i
    return np.array(on)


def k_weight_lufs(x, sr):
    """ITU-R BS.1770-4 integrated loudness (mono), gated."""
    from scipy.signal import lfilter
    f0, G, Q = 1681.974450955533, 3.999843853973347, 0.7071752369554196
    K = math.tan(math.pi * f0 / sr)
    Vh = 10 ** (G / 20)
    Vb = Vh ** 0.4996667741545416
    a0 = 1 + K / Q + K * K
    b1 = [(Vh + Vb * K / Q + K * K) / a0, 2 * (K * K - Vh) / a0, (Vh - Vb * K / Q + K * K) / a0]
    a1 = [1, 2 * (K * K - 1) / a0, (1 - K / Q + K * K) / a0]
    f0, Q = 38.13547087602444, 0.5003270373238773
    K = math.tan(math.pi * f0 / sr)
    a2 = [1, 2 * (K * K - 1) / (1 + K / Q + K * K), (1 - K / Q + K * K) / (1 + K / Q + K * K)]
    b2 = [1, -2, 1]
    y = lfilter(b2, a2, lfilter(b1, a1, x))
    blk, step = int(0.4 * sr), int(0.1 * sr)
    z = np.array([np.mean(y[i:i + blk] ** 2) for i in range(0, len(y) - blk + 1, step)])
    l = -0.691 + 10 * np.log10(z + 1e-20)
    z1 = z[l > -70]
    rel = -0.691 + 10 * np.log10(z1.mean()) - 10
    z2 = z1[(-0.691 + 10 * np.log10(z1 + 1e-20)) > rel]
    return float(-0.691 + 10 * np.log10(z2.mean()))


def ebur128_I(path):
    err = ffstderr("-nostats", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-")
    return float([l for l in err.splitlines() if l.strip().startswith("I:")][-1].split()[1])


def loudnorm_two_pass(src, dst, I=-14, TP=-1.0, LRA=11, lra_rule=True):
    err = ffstderr("-nostats", "-i", src, "-af", f"loudnorm=I={I}:TP={TP}:LRA={LRA}:print_format=json", "-f", "null", "-")
    m = json.loads(err[err.rindex("{"):err.rindex("}") + 1])
    lra = max(LRA, float(m["input_lra"]) + 1) if lra_rule else LRA
    af = (f"loudnorm=I={I}:TP={TP}:LRA={lra}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:"
          "linear=true:print_format=json")
    err2 = ffstderr("-nostats", "-i", src, "-af", af, "-ar", "48000", dst)
    return m, json.loads(err2[err2.rindex("{"):err2.rindex("}") + 1])
