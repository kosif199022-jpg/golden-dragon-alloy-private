"""Helpers of power_programs/camera_composition_layout__bd.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

import math


def need_zoom(roll_deg: float, w: int, h: int) -> float:
    """Exact minimum zoom so a w x h frame rotated by roll still covers the w x h canvas."""
    r = math.radians(abs(roll_deg))
    c, s = math.cos(r), math.sin(r)
    return max((w * c + h * s) / w, (w * s + h * c) / h)


def card_rule(roll_deg: float, w: int, h: int, z: float = 1.0) -> float:
    """The card's shipped approximation: need = |cos r| + q*|sin r|*0.56, q = long/short side."""
    r = math.radians(roll_deg)
    q = max(w, h) / min(w, h)
    return max(z, abs(math.cos(r)) + q * abs(math.sin(r)) * 0.56)


def covered(roll_deg, w, h, z, n=64):
    """Rotate canvas corners into source space and check they stay inside the zoomed source."""
    r = math.radians(roll_deg)
    for cx, cy in [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]:
        x = (cx * math.cos(r) + cy * math.sin(r)) / z
        y = (-cx * math.sin(r) + cy * math.cos(r)) / z
        if abs(x) > w / 2 + 1e-9 or abs(y) > h / 2 + 1e-9:
            return False
    return True
