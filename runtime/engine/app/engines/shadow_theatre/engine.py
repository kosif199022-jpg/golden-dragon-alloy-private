"""Shadow-theatre renderer: projected backdrop, articulated body silhouettes, props, depth, iris and spotlight.

Pure numpy + Pillow. Every frame is a function of time drawn from a scene spec (JSON), so any frame renders alone
(stills) and the film is deterministic. Poses, costumes and backdrops live in data/library.json.

Units: x = fraction of the screen width, y = fraction of the screen height (y=1 is the bottom edge); figure height and
prop scale are fractions of the screen height. Angles are degrees.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

LIB = json.loads((Path(__file__).resolve().parent / "data" / "library.json").read_text(encoding="utf-8"))
POSES: dict[str, dict] = LIB["poses"]
COSTUMES: dict[str, dict] = LIB["costumes"]
BACKDROPS: dict[str, dict] = LIB["backdrops"]
JOINTS = ("torso", "head", "arm_a", "elbow_a", "arm_b", "elbow_b", "leg_a", "knee_a", "leg_b", "knee_b")

# --------------------------------------------------------------------------- easing and keyframes

EASES = {
    "linear": lambda u: u,
    "in": lambda u: u * u * u,
    "out": lambda u: 1 - (1 - u) ** 3,
    "inout": lambda u: 4 * u * u * u if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2,
    "smooth": lambda u: u * u * (3 - 2 * u),
    "hold": lambda u: 0.0,
}
ANIM_FIELDS = ("x", "y", "scale", "depth", "rot", "opacity", "height")


def _lerp(a, b, u):
    return a + (b - a) * u


def sample_keys(keys: list[dict], t: float) -> dict:
    """Numeric fields and named poses interpolated between keyframes (keys sorted by t; the ease of a key shapes the
    segment arriving at it). Outside the keys the first/last key holds."""
    if not keys:
        return {}
    if t <= keys[0]["t"] or t >= keys[-1]["t"]:
        k = dict(keys[0] if t <= keys[0]["t"] else keys[-1])
        k["_pose_mix"] = (k.get("pose"), k.get("pose"), 0.0)
        return k
    for a, b in zip(keys, keys[1:]):
        if a["t"] <= t <= b["t"]:
            u = EASES.get(b.get("ease", "inout"), EASES["inout"])((t - a["t"]) / max(1e-6, b["t"] - a["t"]))
            out = {f: _lerp(a.get(f, b.get(f)), b.get(f, a.get(f)), u) for f in ANIM_FIELDS if f in a or f in b}
            out.update({f: a[f] for f in ("facing", "shape", "costume") if f in a})
            out["_pose_mix"] = (a.get("pose"), b.get("pose", a.get("pose")), u)
            return out
    return dict(keys[-1])


# --------------------------------------------------------------------------- body model
# Limb directions: 0 = straight down, +90 = forward (+x when facing right), 180 = up. Arms are relative to the torso,
# legs absolute; elbow/knee are bends added to the parent.


def resolve_pose(name_or_dict) -> dict:
    if isinstance(name_or_dict, dict):
        base = dict(POSES["stand"])
        if "base" in name_or_dict:
            base.update(POSES[name_or_dict["base"]])
        base.update({k: v for k, v in name_or_dict.items() if k in JOINTS})
        return base
    if name_or_dict is None:
        return dict(POSES["stand"])
    if name_or_dict not in POSES:
        raise KeyError(f"unknown pose {name_or_dict!r}; known: {', '.join(sorted(POSES))}")
    return dict(POSES[name_or_dict])


def mix_pose(mix) -> dict:
    a, b, u = mix
    pa, pb = resolve_pose(a), resolve_pose(b)
    return {j: _lerp(pa[j], pb[j], u) for j in JOINTS}


def apply_cycle(pose: dict, cycle: dict | None, t: float) -> dict:
    """Procedural motion on top of the keyed pose: walk, sway, wave, breathe, flutter."""
    if not cycle:
        return pose
    p = dict(pose)
    kind, period = cycle.get("type", "walk"), max(0.05, float(cycle.get("period", 1.0)))
    amp = float(cycle.get("amp", 1.0))
    ph = 2 * math.pi * (t / period + float(cycle.get("phase", 0.0)))
    s = math.sin(ph)
    if kind == "walk":
        p["leg_a"] += 26 * amp * s
        p["leg_b"] -= 26 * amp * s
        p["knee_a"] += -32 * amp * max(0.0, -s)
        p["knee_b"] += -32 * amp * max(0.0, s)
        p["arm_a"] -= 20 * amp * s
        p["arm_b"] += 20 * amp * s
    elif kind == "sway":
        p["torso"] += 7 * amp * s
        p["arm_a"] += 12 * amp * s
        p["arm_b"] += 12 * amp * s
    elif kind == "wave":
        p["elbow_a"] += 28 * amp * s
        p["arm_a"] += 8 * amp * math.sin(ph * 0.5)
    elif kind == "breathe":
        p["torso"] += 2.5 * amp * s
        p["head"] += 3 * amp * s
    elif kind == "flutter":  # fronds in wind
        p["elbow_a"] += 14 * amp * s
        p["elbow_b"] += 14 * amp * math.sin(ph + 1.3)
        p["torso"] += 3 * amp * math.sin(ph + 0.6)
    return p


def _dir(deg: float, facing: int) -> tuple[float, float]:
    r = math.radians(deg)
    return facing * math.sin(r), math.cos(r)


def _add(p, d, k):
    return p[0] + d[0] * k, p[1] + d[1] * k


def body_skeleton(pose: dict, costume: str, h_px: float, facing: int):
    """Forward kinematics with the hip at (0,0). Returns joints and limb lengths in pixels."""
    L = {k: v * h_px for k, v in COSTUMES.get(costume, COSTUMES["plain"]).items()}
    tor = math.radians(pose["torso"])
    up = (facing * math.sin(tor), -math.cos(tor))
    hip = (0.0, 0.0)
    chest = _add(hip, up, L["torso"])
    hr = math.radians(pose["torso"] + pose["head"] * 0.6)
    hu = (facing * math.sin(hr), -math.cos(hr))
    neck = _add(chest, hu, L["head"] * 0.55)
    j = {"hip": hip, "chest": chest, "neck": neck, "head": _add(neck, hu, L["head"] * 1.05)}
    for side in ("a", "b"):
        a1 = pose["arm_" + side] + pose["torso"]
        sh = _add(chest, up, -L["torso"] * 0.06)
        el = _add(sh, _dir(a1, facing), L["upper_arm"])
        j["sh_" + side], j["el_" + side] = sh, el
        j["wr_" + side] = _add(el, _dir(a1 + pose["elbow_" + side], facing), L["forearm"])
        l1 = pose["leg_" + side]
        kn = _add(hip, _dir(l1, facing), L["thigh"])
        j["kn_" + side], j["ft_" + side] = kn, _add(kn, _dir(l1 + pose["knee_" + side], facing), L["shin"])
    return j, L


def _capsule(draw: ImageDraw.ImageDraw, p, q, w, fill=255):
    draw.line([p, q], fill=fill, width=max(1, int(round(w))))
    r = w / 2
    for c in (p, q):
        draw.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=fill)


def _disc(draw, x, y, rx, ry=None):
    ry = rx if ry is None else ry
    draw.ellipse([x - rx, y - ry, x + rx, y + ry], fill=255)


def draw_body(draw, ox, oy, pose, costume, h_px, facing, grounded):
    j, L = body_skeleton(pose, costume, h_px, facing)
    if grounded:  # the lowest point (foot or knee) stands on the ground line oy
        low = max(j["ft_a"][1], j["ft_b"][1], j["kn_a"][1], j["kn_b"][1], j["hip"][1] + L["w_hip"] * 0.5)
        oy = oy - low - L["w_limb"] * 0.4
    P = {k: (ox + v[0], oy + v[1]) for k, v in j.items()}
    wl = L["w_limb"]
    for s in ("a", "b"):  # legs and feet
        _capsule(draw, P["hip"], P["kn_" + s], wl * 1.25)
        _capsule(draw, P["kn_" + s], P["ft_" + s], wl * 0.95)
        fx, fy = P["ft_" + s]
        draw.polygon([(fx - wl * 0.45, fy - wl * 0.4), (fx + facing * wl * 1.5, fy + wl * 0.05), (fx - wl * 0.45, fy + wl * 0.3)], fill=255)
    (hx, hy), (cx, cy) = P["hip"], P["chest"]  # torso quad
    n = math.hypot(cx - hx, cy - hy) or 1
    nx, ny = -(cy - hy) / n, (cx - hx) / n
    wc, wh = L["w_chest"] / 2, L["w_hip"] / 2
    draw.polygon([(hx + nx * wh, hy + ny * wh), (cx + nx * wc, cy + ny * wc), (cx - nx * wc, cy - ny * wc), (hx - nx * wh, hy - ny * wh)], fill=255)
    _capsule(draw, P["chest"], P["neck"], wl * 0.9)
    _disc(draw, cx, cy, wc * 1.05)
    _disc(draw, hx, hy, wh * 1.1)
    r = L["head"]  # head (slightly egg-shaped) + hair bun
    gx, gy = P["head"]
    _disc(draw, gx, gy, r * 0.86, r)
    if costume in ("dress", "child"):
        bx = gx - facing * r * 0.95
        draw.ellipse([bx - r * 0.42, gy - r * 0.2, bx + r * 0.42, gy + r * 0.62], fill=255)
    if costume == "elder":  # walking stick in the front hand
        wx, wy = P["wr_a"]
        draw.line([(wx, wy), (wx + facing * r * 0.6, oy + 0.0)], fill=255, width=max(1, int(wl * 0.45)))
    if costume in ("dress", "child"):  # skirt
        hem = h_px * (0.36 if costume == "dress" else 0.25)
        ml = math.radians((pose["leg_a"] + pose["leg_b"]) * 0.5)
        hx2, hy2 = hx + facing * math.sin(ml) * hem, hy + math.cos(ml) * hem
        ww = h_px * (0.13 if costume == "dress" else 0.11)
        draw.polygon([(hx - wh * 1.2, hy - h_px * 0.05), (hx + wh * 1.2, hy - h_px * 0.05), (hx2 + ww, hy2), (hx2 - ww, hy2)], fill=255)
    for s in ("a", "b"):  # arms last: they cross the torso
        _capsule(draw, P["sh_" + s], P["el_" + s], wl * 1.0)
        _capsule(draw, P["el_" + s], P["wr_" + s], wl * 0.8)
        _disc(draw, *P["wr_" + s], wl * 0.45)


# --------------------------------------------------------------------------- outlines and props


def shape_points(shape: str, n: int = 160) -> list[tuple[float, float]]:
    """Unit outlines centred on (0,0), radius ~0.5, for props and iris masks."""
    if shape == "circle":
        return [(0.5 * math.cos(a), 0.5 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, n, endpoint=False)]
    if shape == "heart":
        pts = []
        for a in np.linspace(0, 2 * math.pi, n, endpoint=False):
            x = 16 * math.sin(a) ** 3
            y = 13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a)
            pts.append((x / 34, -y / 34 - 0.03))
        return pts
    if shape == "star":
        return [((0.5 if i % 2 == 0 else 0.21) * math.cos(-math.pi / 2 + i * math.pi / 5),
                 (0.5 if i % 2 == 0 else 0.21) * math.sin(-math.pi / 2 + i * math.pi / 5)) for i in range(10)]
    if shape == "arch":  # pointed arch / mihrab window
        pts = [(-0.3, 0.5), (-0.3, -0.05)]
        pts += [(0.3 + 0.6 * math.cos(a), -0.05 + 0.45 * math.sin(a)) for a in np.linspace(math.pi, math.pi * 4 / 3, 24)]
        pts += [(-0.3 + 0.6 * math.cos(a), -0.05 + 0.45 * math.sin(a)) for a in np.linspace(math.pi * 5 / 3, math.pi * 2, 24)]
        return pts + [(0.3, -0.05), (0.3, 0.5)]
    raise KeyError(f"unknown outline {shape!r}")


@dataclass
class _Prop:
    """Drawing context of one prop: anchor (cx, cy), size s in pixels, rotation, time and params."""
    img: Image.Image
    d: ImageDraw.ImageDraw
    cx: float
    cy: float
    s: float
    rot: float
    t: float
    params: dict

    def T(self, x, y, rot=None):
        r = math.radians(self.rot if rot is None else rot)
        cr, sr = math.cos(r), math.sin(r)
        return self.cx + (x * cr - y * sr) * self.s, self.cy + (x * sr + y * cr) * self.s

    def poly(self, pts, fill=255, rot=None):
        self.d.polygon([tuple(map(float, self.T(x, y, rot))) for x, y in pts], fill=fill)


def _outline(p: _Prop, shape):
    p.poly(shape_points("circle" if shape == "sun" else shape))


def _crescent(p: _Prop):
    p.poly(shape_points("circle"))
    p.poly([(x * 0.92 + 0.2, y * 0.92 - 0.1) for x, y in shape_points("circle")], fill=0)


def _bird(p: _Prop):
    wy = -0.35 * math.sin(2 * math.pi * p.t * p.params.get("flap", 2.2))
    p.poly([(-0.5, wy), (-0.25, -0.05 + wy * 0.3), (-0.05, 0.02), (0, -0.04), (0.05, 0.02), (0.25, -0.05 + wy * 0.3),
            (0.5, wy), (0.28, 0.05 + wy * 0.25), (0.06, 0.1), (0, 0.13), (-0.06, 0.1), (-0.28, 0.05 + wy * 0.25)])


def _palm(p: _Prop):  # anchor = base of the trunk, s = total height
    period = p.params.get("period", 3.0)
    sway = math.sin(2 * math.pi * p.t / period) * 0.03
    trunk = [(0.12 * math.sin(u * 1.6) + sway * u * u, -u, 0.035 * (1 - u) + 0.018) for u in (i / 20 for i in range(21))]
    p.poly([(x - w, y) for x, y, w in trunk] + [(x + w, y) for x, y, w in reversed(trunk)])
    top = trunk[-1]
    for k, ang in enumerate((-160, -125, -95, -60, -25, 10, 150, 35)):
        a = math.radians(ang + 8 * math.sin(2 * math.pi * p.t / period + k))
        ln = 0.42 if abs(ang) < 140 else 0.3
        frond = [(top[0] + math.cos(a) * ln * u, top[1] + math.sin(a) * ln * u + 0.28 * u * u,
                  0.045 * math.sin(math.pi * min(0.999, u + 0.05))) for u in (i / 12 for i in range(13))]
        p.poly([(x, y - w) for x, y, w in frond] + [(x, y + w) for x, y, w in reversed(frond)])
    for k in range(3):  # dates
        bx, by = top[0] - 0.03 + 0.03 * k, top[1] + 0.05
        (x0, y0), (x1, y1) = p.T(bx - 0.022, by - 0.022), p.T(bx + 0.022, by + 0.022)
        p.d.ellipse([min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)], fill=255)


def _skyline(p: _Prop):  # domes and minarets, anchor = bottom centre, s = height
    p.poly([(-1.1, 0), (-1.1, -0.18), (1.1, -0.18), (1.1, 0)])
    for dx, r in ((0.0, 0.32), (-0.55, 0.16), (0.55, 0.16)):
        dome = [(dx + r * math.cos(a), -0.18 - 0.05 - r * 1.05 * math.sin(a)) for a in np.linspace(0, math.pi, 40)]
        p.poly([(dx + r, -0.17)] + dome + [(dx - r, -0.17)])
        p.poly([(dx - 0.012, -0.22 - r * 1.05), (dx, -0.33 - r * 1.05), (dx + 0.012, -0.22 - r * 1.05)])
    for mx in (-0.92, 0.92):
        p.poly([(mx - 0.045, -0.18), (mx - 0.035, -0.85), (mx + 0.035, -0.85), (mx + 0.045, -0.18)])
        p.poly([(mx - 0.07, -0.62), (mx + 0.07, -0.62), (mx + 0.07, -0.66), (mx - 0.07, -0.66)])
        p.poly([(mx - 0.035, -0.85), (mx, -1.0), (mx + 0.035, -0.85)])
    for wx in (-0.3, -0.1, 0.1, 0.3):  # punched arched windows let the light through
        p.poly([(x * 0.11 + wx, y * 0.2 - 0.1) for x, y in shape_points("arch")], fill=0)


def _band(p: _Prop, n, top, bottom):
    """A full-width ground band: polyline y(u) for u in 0..1 closed down to `bottom`."""
    w = p.img.size[0]
    pts = [(0, bottom)] + [(i / n * w, top(i / n)) for i in range(n + 1)] + [(w, bottom)]
    p.d.polygon([(float(x), float(y)) for x, y in pts], fill=255)


def _dunes(p: _Prop):  # s = band height, cx ignored
    ph = p.t * p.params.get("drift", 0.0)
    _band(p, 100, lambda u: p.cy - p.s * (0.55 + 0.25 * math.sin(u * 7.0 + 1.3 + ph) + 0.2 * math.sin(u * 15.0 + ph * 1.7)), p.cy)


def _waves(p: _Prop):
    ph = 2 * math.pi * p.t / p.params.get("period", 2.4)
    _band(p, 160, lambda u: p.cy - p.s * (0.5 + 0.28 * math.sin(u * 18 - ph) + 0.18 * math.sin(u * 41 + ph * 1.4)), p.cy + p.s)


def _lantern(p: _Prop):  # Ramadan fanous; anchor = hanging ring, s = height; it swings on its ring
    rot = p.rot + math.sin(2 * math.pi * p.t / p.params.get("period", 2.8)) * 6
    if p.params.get("chain", 0):
        p.d.line([p.T(0, -p.params["chain"], rot), p.T(0, 0, rot)], fill=255, width=max(1, int(p.s * 0.015)))
    p.poly([(0.06 * math.cos(a), 0.05 + 0.05 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 24)], rot=rot)
    p.poly([(0.03 * math.cos(a), 0.05 + 0.025 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 16)], fill=0, rot=rot)
    p.poly([(-0.08, 0.1), (0.08, 0.1), (0.2, 0.24), (0.2, 0.56), (0.28, 0.62), (0.13, 0.82), (0.0, 0.9),
            (-0.13, 0.82), (-0.28, 0.62), (-0.2, 0.56), (-0.2, 0.24)], rot=rot)
    for wx in (-0.1, 0.1):  # cut-out windows
        p.poly([(x * 0.13 + wx, y * 0.3 + 0.42) for x, y in shape_points("arch")], fill=0, rot=rot)
    p.poly([(x * 0.08, y * 0.08 + 0.72) for x, y in shape_points("star")], fill=0, rot=rot)


def _foliage(p: _Prop):  # a leafy branch held by a performer; anchor = centre, s = diameter
    rng = np.random.default_rng(int(p.params.get("seed", 3)))
    for i in range(int(p.params.get("leaves", 60))):
        a, r = rng.random() * 2 * math.pi, 0.42 * math.sqrt(rng.random())
        lx, ly = r * math.cos(a), r * math.sin(a) * 0.7
        lx += 0.015 * math.sin(2 * math.pi * p.t / p.params.get("period", 2.0) + i)
        la = rng.random() * math.pi
        ln, lw = 0.09 + 0.05 * rng.random(), 0.04
        leaf = []
        for k in range(16):
            u = 2 * math.pi * k / 16
            ex, ey = ln * math.cos(u), lw * math.sin(u)
            leaf.append((lx + ex * math.cos(la) - ey * math.sin(la), ly + ex * math.sin(la) + ey * math.cos(la)))
        p.poly(leaf)
    for k in range(4):  # twigs to the hand
        a = math.radians(60 + 20 * k)
        _capsule(p.d, p.T(0, 0.35), p.T(0.25 * math.cos(a + math.pi), -0.25 * math.sin(a)), p.s * 0.018)


def _hand(p: _Prop):  # a big hand entering from an edge; anchor = wrist, s = length, rot 0 = fingers up
    p.poly([(-0.17, 0.1), (0.17, 0.1), (0.2, -0.35), (-0.2, -0.35)])
    for fx, ln, ang in ((-0.15, 0.42, -10), (-0.05, 0.55, -3), (0.05, 0.58, 2), (0.15, 0.48, 9)):
        a = math.radians(ang)
        _capsule(p.d, p.T(fx, -0.3), p.T(fx + math.sin(a) * ln, -0.3 - math.cos(a) * ln), p.s * 0.085)
    _capsule(p.d, p.T(0.18, -0.05), p.T(0.42, -0.32), p.s * 0.09)


PROPS = {**{k: (lambda p, k=k: _outline(p, k)) for k in ("circle", "heart", "star", "arch", "sun")},
         "crescent": _crescent, "bird": _bird, "palm": _palm, "skyline": _skyline, "dunes": _dunes, "waves": _waves,
         "lantern": _lantern, "foliage": _foliage, "hand": _hand}


def draw_prop(img: Image.Image, shape: str, cx: float, cy: float, s: float, rot: float, t: float, params: dict):
    """s = prop size in pixels; (cx, cy) = anchor (centre, or base centre for grounded things)."""
    if shape not in PROPS:
        raise KeyError(f"unknown prop shape {shape!r}")
    PROPS[shape](_Prop(img, ImageDraw.Draw(img), cx, cy, s, rot, t, params))


# --------------------------------------------------------------------------- backdrops


def _gradient(h, w, stops):
    ys = np.linspace(0, 1, h, dtype=np.float32)
    out = np.zeros((h, 3), np.float32)
    pos = [s[0] for s in stops]
    for ch in range(3):
        out[:, ch] = np.interp(ys, pos, [s[1][ch] for s in stops])
    return np.repeat(out[:, None, :] / 255.0, w, axis=1)


def _noise(h, w, seed, octaves=4):
    rng = np.random.default_rng(seed)
    acc = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        g = (rng.random((max(2, h // (64 >> o)), max(2, w // (64 >> o)))) * 255).astype(np.uint8)
        acc += np.asarray(Image.fromarray(g).resize((w, h), Image.BICUBIC), np.float32) / 255.0 * amp
        tot += amp
        amp *= 0.5
    acc /= tot
    return (acc - acc.mean()) / (acc.std() + 1e-6)


def _resize(arr01, size, resample=Image.BILINEAR):
    """float 0..1 mask -> 8-bit image resized -> float 0..1 (the quantisation is part of the look)."""
    return np.asarray(Image.fromarray((arr01 * 255).astype(np.uint8)).resize(size, resample), np.float32) / 255.0


# --------------------------------------------------------------------------- renderer


@dataclass
class Frame:
    rgb: np.ndarray  # HxWx3 uint8


class ShadowRenderer:
    def __init__(self, spec: dict):
        self.spec = spec
        self.W, self.H = int(spec.get("width", 1080)), int(spec.get("height", 1920))
        self.fps = float(spec.get("fps", 30))
        self.seed = int(spec.get("seed", 7))
        sc = spec.get("screen", {})
        m = float(sc.get("margin", 0.045))
        mx = int(self.W * m)
        self.sx0, self.sy0 = mx, int(self.H * float(sc.get("top", m * 1.6)))
        self.sx1, self.sy1 = self.W - mx, self.H - int(self.H * float(sc.get("bottom", m * 1.6)))
        self.sw, self.sh = self.sx1 - self.sx0, self.sy1 - self.sy0
        self.hw, self.hh = self.W // 2, self.H // 2  # work resolution for masks
        self.leak = float(spec.get("shadow_leak", 0.05))
        self.blur_base = float(spec.get("penumbra", 1.2))
        self._screen = self._screen_mask(float(sc.get("radius", 0.07)))
        self._bd_cache: dict = {}
        self._stage = np.array(spec.get("stage_color", (5, 5, 14)), np.float32) / 255.0
        yy, xx = np.mgrid[0:self.H, 0:self.W].astype(np.float32)
        self._u, self._v = (xx - self.sx0) / self.sw, (yy - self.sy0) / self.sh
        r2 = ((self._u - 0.5) / 0.75) ** 2 + ((self._v - 0.48) / 0.75) ** 2
        self._hotspot = np.clip(1.08 - 0.42 * r2, 0.45, 1.1)[..., None]  # the lamp's hot centre
        cl = _noise(max(8, self.H // 3), max(8, self.W // 10), self.seed)  # wide, flat cloud banks
        self._clouds = _resize((cl * 0.18 + 0.5).clip(0, 1), (self.W, self.H), Image.BICUBIC)

    def _screen_mask(self, radius):
        img = Image.new("L", (self.W, self.H), 0)
        r = int(min(self.sw, self.sh) * radius)
        ImageDraw.Draw(img).rounded_rectangle([self.sx0, self.sy0, self.sx1, self.sy1], radius=r, fill=255)
        img = img.filter(ImageFilter.GaussianBlur(max(2, self.W // 220)))
        return (np.asarray(img, np.float32) / 255.0)[..., None]

    def to_px(self, x, y, work=True):
        k = 0.5 if work else 1.0
        return (self.sx0 + x * self.sw) * k, (self.sy0 + y * self.sh) * k

    def backdrop(self, scene: dict, t_local: float) -> np.ndarray:
        name = scene.get("backdrop", "night-blue")
        preset = dict(BACKDROPS[name]) if isinstance(name, str) else dict(name)
        key = name if isinstance(name, str) else id(scene)
        if key not in self._bd_cache:
            base = np.zeros((self.H, self.W, 3), np.float32)
            base[self.sy0:self.sy1, self.sx0:self.sx1] = _gradient(self.sh, self.sw, preset["stops"])
            self._bd_cache[key] = base
        img = self._bd_cache[key].copy()
        spot = scene.get("spot", preset.get("spot"))
        if spot:
            r = spot["r"]
            if "r_keys" in spot:
                r = sample_keys(spot["r_keys"], t_local).get("scale", r)
            col = np.array(spot.get("color", (236, 238, 255)), np.float32) / 255.0
            dist = np.sqrt(((self._u - spot["x"]) * self.sw / self.sh) ** 2 + (self._v - spot["y"]) ** 2)
            pool = np.clip(1 - (dist / max(1e-3, r)) ** 2, 0, 1) ** 1.3
            img = img * (1 - pool[..., None]) + col * pool[..., None]
        amt = float(scene.get("clouds", preset.get("clouds", 0.1)))
        if amt:
            drift = int(t_local * float(scene.get("cloud_speed", 14))) % self._clouds.shape[1]
            img = img * (1 + (np.roll(self._clouds, -drift, axis=1)[..., None] - 0.5) * 2 * amt * 2.2)
        return img

    def actor_layer(self, actor: dict, t_local: float):
        """One silhouette mask at work resolution, its opacity and depth (closer to the lamp = bigger and softer)."""
        k = sample_keys(actor.get("keys", [{"t": 0}]), t_local)
        if k.get("opacity", 1.0) <= 0.003:
            return None, 0.0, 0.0
        depth = float(k.get("depth", actor.get("depth", 0.0)))
        grow = 1.0 + 2.2 * depth
        img = Image.new("L", (self.W, self.H), 0)  # drawn at full res, then halved (antialias)
        x, y = float(k.get("x", 0.5)), float(k.get("y", 0.93))
        lx = float(self.spec.get("lamp", {}).get("x", 0.5))
        if depth:  # the shadow spreads away from the lamp axis sideways and grows up from the floor line
            x = lx + (x - lx) * grow
        px, py = self.to_px(x, y, work=False)
        if actor.get("type", "human") == "human":
            h = float(k.get("height", actor.get("height", 0.42))) * self.sh * grow * float(k.get("scale", 1.0))
            pose = apply_cycle(mix_pose(k.get("_pose_mix", (actor.get("pose"), actor.get("pose"), 0))), actor.get("cycle"), t_local)
            draw_body(ImageDraw.Draw(img), px, py, pose, actor.get("costume", "plain"), h,
                      int(k.get("facing", actor.get("facing", 1))), actor.get("grounded", True))
        else:
            s = float(k.get("scale", actor.get("scale", 0.2))) * self.sh * grow
            draw_prop(img, actor["shape"], px, py, s, float(k.get("rot", 0)), t_local, actor.get("params", {}))
        img = img.resize((self.hw, self.hh), Image.BILINEAR)
        blur = self.blur_base + depth * float(self.spec.get("depth_blur", 12)) + float(actor.get("blur", 0))
        if blur > 0.3:
            img = img.filter(ImageFilter.GaussianBlur(blur))
        return np.asarray(img, np.float32) / 255.0, float(k.get("opacity", 1.0)), depth

    def iris_mask(self, scene: dict, t_local: float):
        iris = scene.get("iris")
        if not iris:
            return None
        sc = float(sample_keys(iris["keys"], t_local).get("scale", 3.0))
        if sc >= 2.9:  # fully open
            return None
        img = Image.new("L", (self.hw, self.hh), 0)
        cx, cy = self.to_px(float(iris.get("x", 0.5)), float(iris.get("y", 0.5)))
        s = sc * self.sh * 0.5
        if s > 0.5:
            ImageDraw.Draw(img).polygon([(cx + px * s, cy + py * s) for px, py in shape_points(iris.get("shape", "circle"))], fill=255)
        img = img.filter(ImageFilter.GaussianBlur(float(iris.get("soft", 2.5))))
        return np.asarray(img.resize((self.W, self.H), Image.BILINEAR), np.float32)[..., None] / 255.0

    def scene_at(self, t: float):
        return next((s for s in self.spec["scenes"] if s["start"] <= t < s["end"]), self.spec["scenes"][-1])

    def light_level(self, scene: dict, t: float) -> float:
        fi, fo = float(scene.get("fade_in", 0.5)), float(scene.get("fade_out", 0.5))
        a = 1.0
        if fi > 0:
            a = min(a, (t - scene["start"]) / fi)
        if fo > 0:
            a = min(a, (scene["end"] - t) / fo)
        return float(EASES["smooth"](min(1.0, max(0.0, a))))

    def render(self, t: float) -> Frame:
        scene = self.scene_at(t)
        tl = t - scene["start"]
        bd = self.backdrop(scene, tl)
        shadow = np.zeros((self.hh, self.hw), np.float32)
        for actor in scene.get("actors", []):
            m, op, _ = self.actor_layer(actor, tl)
            if m is not None:
                np.maximum(shadow, m * op, out=shadow)
        sh = _resize(shadow, (self.W, self.H))[..., None]
        lit = bd * self._hotspot * (1 - sh * (1 - self.leak))
        lmask = self._screen * self.light_level(scene, t)
        iris = self.iris_mask(scene, tl)
        if iris is not None:
            lmask = lmask * iris
        # the unlit screen is a faint cloth tone, not pure black, like the real screen between cues
        cloth = self._screen * np.array((0.035, 0.035, 0.07), np.float32)
        out = lit * lmask + cloth * (1 - lmask) + self._stage * (1 - self._screen)
        rng = np.random.default_rng(int(t * self.fps) + self.seed)
        grain = rng.normal(0, float(self.spec.get("grain", 0.006)), (self.hh, self.hw)).astype(np.float32)
        grain = np.repeat(np.repeat(grain, 2, 0), 2, 1)[: self.H, : self.W, None]
        return Frame((np.clip(out + grain, 0, 1) * 255 + 0.5).astype(np.uint8))
