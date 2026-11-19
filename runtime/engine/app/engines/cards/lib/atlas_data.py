"""Helpers of power_programs/atlas_data.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from pathlib import Path
import json
import math
from scipy import stats


def _w(work: Path, name: str, obj) -> Path:
    p = work / name
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(obj, (bytes, bytearray)):
        p.write_bytes(obj)
    elif isinstance(obj, str):
        p.write_text(obj, encoding="utf-8")
    else:
        p.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return p


def _c(name, cond, obs):
    return (name, bool(cond), str(obs))


def _iban_ok(iban):
    s = iban.replace(" ", "").upper()
    s = s[4:] + s[:4]
    return int("".join(str(int(ch, 36)) for ch in s)) % 97 == 1


def _n_two_prop(p1, mde, alpha=0.05, power=0.8):
    p2 = p1 + mde
    pbar = (p1 + p2) / 2
    za, zb = stats.norm.ppf(1 - alpha / 2), stats.norm.ppf(power)
    return math.ceil((za * math.sqrt(2 * pbar * (1 - pbar)) + zb * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2 / mde ** 2)


def _holm(p, alpha=0.05):
    order = sorted(range(len(p)), key=lambda i: p[i])
    rej = [False] * len(p)
    for k, i in enumerate(order):
        if p[i] <= alpha / (len(p) - k):
            rej[i] = True
        else:
            break
    return rej


def _bh(p, q=0.05):
    m = len(p)
    order = sorted(range(m), key=lambda i: p[i])
    kmax = max([k + 1 for k, i in enumerate(order) if p[i] <= (k + 1) / m * q] or [0])
    return [order.index(i) < kmax for i in range(m)]


def _ses(y, a):
    f = [y[0]]
    for v in y[:-1]:
        f.append(a * v + (1 - a) * f[-1])
    return f


def _holt(y, a, b, h):
    lvl, tr = y[0], y[1] - y[0]
    for v in y[1:]:
        nl = a * v + (1 - a) * (lvl + tr)
        tr = b * (nl - lvl) + (1 - b) * tr
        lvl = nl
    return [lvl + (i + 1) * tr for i in range(h)]


def _wilson(x, n, z=1.96):
    p = x / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h
