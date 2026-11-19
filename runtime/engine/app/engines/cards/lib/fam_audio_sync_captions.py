"""Helpers of runners/fam_audio_sync_captions.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from pathlib import Path
from .core import fx
import json
import math
import numpy as np
import subprocess


SR = 48000


def tt(secs, sr=SR):
    return np.arange(int(round(secs * sr))) / sr


def save(wd, name, x, sr=SR):
    p = Path(wd) / name
    fx.write_wav(p, np.clip(np.asarray(x, float), -1, 1), sr)
    return p


def load_any(p, sr=SR):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.float32).astype(float), sr


def dbfs(x):
    return 20 * math.log10(math.sqrt(float(np.mean(np.square(x)))) + 1e-12)


def speechlike(secs, spans, f0=170.0, amp=0.3, sr=SR, seed=4):
    """Voiced spans of a harmonic buzz with a syllable-rate (5 Hz) envelope; digital silence elsewhere."""
    t = tt(secs, sr)
    x = sum(np.sin(2 * np.pi * f0 * k * t) / k for k in range(1, 8))
    syl = 0.6 + 0.4 * np.sin(2 * np.pi * 5 * t) ** 2
    gate = np.zeros_like(t)
    for a, b in spans:
        gate[(t >= a) & (t < b)] = 1
    ramp = int(0.01 * sr)
    gate = np.convolve(gate, np.ones(ramp) / ramp, mode="same")
    return amp * x / np.abs(x).max() * syl * gate


def jdump(p, obj):
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return Path(p)
