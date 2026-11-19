"""Original synth score for a shadow film: a slow pad per chapter plus a low swell and a bell on each cue. No samples."""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

from .engine import LIB

NOTE = {"C": -9, "C#": -8, "Db": -8, "D": -7, "D#": -6, "Eb": -6, "E": -5, "F": -4, "F#": -3, "Gb": -3,
        "G": -2, "G#": -1, "Ab": -1, "A": 0, "A#": 1, "Bb": 1, "B": 2}


def hz(name: str) -> float:
    pitch, octv = name[:-1], int(name[-1])
    return 440.0 * 2 ** ((NOTE[pitch] + 12 * (octv - 4)) / 12)


def synth_score(spec: dict, path, sr: int = 48000) -> Path:
    dur = float(spec["duration"])
    n = int(dur * sr)
    t = np.arange(n) / sr
    L, R = np.zeros(n, np.float32), np.zeros(n, np.float32)
    chords = LIB["default_chords"]
    for i, s in enumerate(spec["scenes"]):  # pad: the chapter's chord, faded in and out, slow tremolo
        chord = s.get("chord") or chords[i % len(chords)]
        a, b = int(s["start"] * sr), min(n, int((s["end"] + 0.8) * sr))
        tt = t[a:b] - s["start"]
        env = np.minimum(1, tt / 1.4) * np.clip((s["end"] + 0.8 - s["start"] - tt) / 1.6, 0, 1)
        trem = 0.85 + 0.15 * np.sin(2 * np.pi * 0.23 * tt + i)
        for j, nm in enumerate(chord):
            f = hz(nm)
            v = (np.sin(2 * np.pi * f * tt) + 0.35 * np.sin(2 * np.pi * 2 * f * tt + 0.3) + 0.12 * np.sin(2 * np.pi * 3 * f * tt)) * 0.06
            L[a:b] += (v * env * trem * (1.0 if j % 2 else 0.8)).astype(np.float32)
            R[a:b] += (np.sin(2 * np.pi * f * 1.003 * tt + 0.5) * 0.06 * env * trem * (0.8 if j % 2 else 1.0)).astype(np.float32)
    for c in [s["start"] for s in spec["scenes"]] + [float(x) for x in spec.get("cues", [])]:  # swell + bell per cue
        a = int(c * sr)
        m = min(n - a, int(3.0 * sr))
        if m <= 0:
            continue
        tt = t[:m]
        boom = np.sin(2 * np.pi * (48 + 20 * np.exp(-tt * 6)) * tt) * np.exp(-tt * 2.2) * 0.35
        bell = sum(np.sin(2 * np.pi * 1046.5 * k * tt) * np.exp(-tt * (2.5 + k)) / (k * 6) for k in (1, 2.76, 5.4))
        L[a:a + m] += (boom + bell * 0.8).astype(np.float32)
        R[a:a + m] += (boom + bell).astype(np.float32)
    for d, g in ((0.113, 0.32), (0.229, 0.22), (0.347, 0.15), (0.61, 0.08)):  # small room
        k = int(d * sr)
        L[k:] += R[:-k] * g
        R[k:] += L[:-k] * g
    fade = np.clip((dur - t) / 1.5, 0, 1)
    L, R = L * fade, R * fade
    peak = max(1e-6, float(np.abs(np.concatenate([L, R])).max()))
    st = (np.stack([L, R], 1) / peak * 0.7 * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(st.tobytes())
    return Path(path)
