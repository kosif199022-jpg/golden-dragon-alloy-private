"""Helpers of power_programs/atlas_media.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

import math
import numpy as np


def spring_step(zeta, omega, dt=1 / 1000, t_end=1.5):
    x, v, xs = 0.0, 0.0, []
    for _ in range(int(t_end / dt)):
        a = omega * omega * (1 - x) - 2 * zeta * omega * v
        v += a * dt
        x += v * dt
        xs.append(x)
    return np.array(xs)


def srgb_to_lin(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def goertzel(x, f, sr):
    k = 2 * math.cos(2 * math.pi * f / sr)
    s1 = s2 = 0.0
    for v in x:
        s1, s2 = v + k * s1 - s2, s1
    return s1 * s1 + s2 * s2 - k * s1 * s2
