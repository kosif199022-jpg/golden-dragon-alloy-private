"""Helpers of power_programs/atlas_build.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from pathlib import Path
import json
import math
import numpy as np
import os
import re
import subprocess


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


def _lum(hexc):
    h = hexc.lstrip("#")
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(a, b):
    la, lb = sorted([_lum(a), _lum(b)], reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _git(cwd, *args):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}
    return subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=True).stdout.strip()


def _histogram_quantile(q, buckets):
    """Prometheus histogram_quantile: buckets = [(le, cumulative_count)] sorted, last le = inf."""
    total = buckets[-1][1]
    rank = q * total
    prev_le, prev_c = 0.0, 0.0
    for le, c in buckets:
        if c >= rank:
            if le == math.inf:
                return prev_le
            return prev_le + (le - prev_le) * (rank - prev_c) / (c - prev_c)
        prev_le, prev_c = le, c
    return prev_le


def _a11y_scan(html):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for el in soup.find_all(attrs={"role": "button"}):
        if el.name != "button":
            out.append(("native-first", el.get("id")))
    for el in soup.find_all(["button", "a"]) + soup.find_all(attrs={"role": True}):
        name = el.get("aria-label") or el.get_text(strip=True)
        if not name:
            out.append(("accessible-name", el.get("id")))
    for el in soup.find_all(style=True):
        m = re.search(r"width:\s*(\d+)px.*height:\s*(\d+)px", el["style"])
        if m and (int(m[1]) < 24 or int(m[2]) < 24):
            out.append(("2.5.8-target-size", el.get("id")))
    for el in soup.find_all("img"):
        if el.get("alt") is None:
            out.append(("1.1.1-alt", el.get("id")))
    for el in soup.find_all("input"):
        if el.get("type") != "hidden" and not (el.get("aria-label") or (el.get("id") and soup.find("label", attrs={"for": el["id"]}))):
            out.append(("label", el.get("id")))
    return sorted(set(out), key=str)


def _oklch(hexc):
    rgb = [int(hexc[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    l_ = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m_ = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s_ = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = [math.copysign(abs(v) ** (1 / 3), v) for v in (l_, m_, s_)]
    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    A = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    B = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return L, math.hypot(A, B), math.degrees(math.atan2(B, A)) % 360


def _resolve_tokens(tokens):
    flat = {}

    def walk(node, path):
        if "$value" in node:
            flat[".".join(path)] = node
            return
        for k, v in node.items():
            if not k.startswith("$"):
                walk(v, path + [k])

    walk(tokens, [])

    def val(name, stack=()):
        if name in stack:
            raise ValueError("circular: " + " -> ".join(stack + (name,)))
        v = flat[name]["$value"]
        m = re.fullmatch(r"\{([\w.]+)\}", str(v))
        return val(m[1], stack + (name,)) if m else v

    return flat, val


def _lab(img):
    rgb = img.astype(float) / 255
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = lin @ M.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def _diff(actual, desired, de_tol=3.0, region=0.005, mask=None):
    de = np.linalg.norm(_lab(actual) - _lab(desired), axis=-1)
    bad = de > de_tol
    if mask is not None:
        bad &= ~mask
    frac = bad.mean()
    return {"pass": bool(frac <= region), "bad_fraction": float(frac), "max_dE": float(de[~mask].max() if mask is not None else de.max())}


def _elements_diff(actual_boxes, desired_boxes, px_tol=2):
    out = []
    for k, (x, y, w, h) in desired_boxes.items():
        ax, ay, aw, ah = actual_boxes[k]
        if max(abs(ax - x), abs(ay - y), abs(aw - w), abs(ah - h)) > px_tol:
            out.append({"element": k, "kind": "position", "delta": [ax - x, ay - y]})
    return out
