"""Rod puppets for the Shadow Theatre engine: people as professional shadow puppets that still read as real people.

A real shadow show has four things the plain figures lacked; this module adds them when a spec says "puppetry": true
(or an actor carries "puppet": {...}):

1. Optics. The lamp hangs `dist` m behind the cloth. A puppet held `gap` m off the cloth throws a shadow L/(L-gap)
   times larger, pushed away from the lamp, and its edge blurs by size*gap/(L-gap) (size = the flame's width).
   Pressed to the cloth it is crisp; drawn back it grows and softens. (`draw-math puppet-shadow` gives the same.)
2. Rods. A main rod between the shoulder blades and a hand rod in the near palm run down to the puppeteer below the
   stage. Their shadows widen and soften towards the bottom, because that end is further from the cloth.
3. A puppeteer's hand. The body hangs from the main rod, so it leans into every start and stop and settles in a
   damped sway; the rod hand arrives with a small overshoot; the free arm swings like a pendulum; the head follows
   through. It is all integrated once per actor at 240 Hz, so a frame stays a pure function of t.
4. An oil lamp: warm light that breathes, a hot spot that wanders a little, and the weave of the cloth.

The anatomy and the walk (planted feet, IK) come from human_figure.py, so the puppets move and look like people.

Spec:  "puppetry": true, "screen_m": 1.8 (the lit cloth's height in metres),
       "lamp": {"x": 0.5, "y": 0.42, "dist": 2.4, "size": 0.05, "kind": "oil", "flicker": 0.035}
Actor: "gap" (metres off the cloth; may be keyed like x), "rods": ["back", "hand_a"],
       "puppet": {"sway": 1.0, "follow": 1.0}, "cycles": [{"from": 0, ...walk...}, {"from": 4.6, ...stepto...}]
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import human_figure as HF

DT = 1.0 / 240.0
# (frequency Hz, damping ratio) of each secondary motion
SPRINGS = {"sway": (1.1, 0.32), "hand": (2.4, 0.62), "pend": (1.25, 0.2), "head": (1.8, 0.45), "rodhand": (0.9, 0.7)}
SWAY_DEG = 55.0      # body lean (deg) per screen-height/s² of the rod's forward acceleration (puppeteers exaggerate)
PEND_DEG = 90.0      # free-arm swing (deg) per screen-height/s²
ROD_M = 0.006        # rod thickness, metres
ROD_REACH = 0.32     # the puppeteer's hand is this much further from the cloth than the puppet
ROD_SLANT = {"back": -0.10, "hand_a": 0.05, "hand_b": 0.03}   # bottom end, in screen heights, ahead (+) or behind (-)
OIL_TINT = np.array((1.0, 0.9, 0.74), np.float32)

_E = None
_prev_render = None


# ------------------------------------------------------------------ optics
def optics(dist, gap, size):
    """Magnification and penumbra width (metres) of a puppet `gap` m off the cloth, lamp `dist` m behind, flame `size` m."""
    gap = min(max(0.0, gap), 0.9 * dist)
    return dist / (dist - gap), size * gap / (dist - gap)


def lamp_at(self, t):
    L = self.spec.get("lamp", {}) or {}
    kind = L.get("kind", "oil")
    fl = float(L.get("flicker", 0.035 if kind == "oil" else 0.0))
    s = float(self.seed)
    n = 0.55 * math.sin(2 * math.pi * 1.7 * t + s) + 0.3 * math.sin(2 * math.pi * 3.9 * t + 1.3 * s) + 0.15 * math.sin(2 * math.pi * 7.3 * t + 2.1 * s)
    return {"x": float(L.get("x", 0.5)), "y": float(L.get("y", 0.45)), "dist": float(L.get("dist", 2.4)), "size": float(L.get("size", 0.05)),
            "kind": kind, "level": 1.0 + fl * n, "jx": 0.004 * n * (fl > 0), "jy": 0.003 * math.sin(2 * math.pi * 0.9 * t + s) * (fl > 0)}


def _hotspot(self, lam):
    cx, cy = lam["x"] + lam["jx"], lam["y"] + 0.06 + lam["jy"]
    r2 = ((self._u - cx) / 0.75) ** 2 + ((self._v - cy) / 0.75) ** 2
    if lam["kind"] == "oil":
        return np.clip(1.12 - 0.55 * r2, 0.35, 1.12)[..., None]
    return np.clip(1.08 - 0.42 * r2, 0.45, 1.1)[..., None]


def _weave(self):
    w = getattr(self, "_pup_weave", None)
    if w is None:
        yy, xx = np.mgrid[0:self.H, 0:self.W].astype(np.float32)
        rng = np.random.default_rng(self.seed + 11)
        w = 1.0 + 0.016 * np.sin(2 * np.pi * xx / 3.4) * np.sin(2 * np.pi * yy / 3.4) + rng.normal(0, 0.008, (self.H, self.W)).astype(np.float32)
        w = w[..., None].astype(np.float32)
        self._pup_weave = w
    return w


# ------------------------------------------------------------------ the puppeteer's hand (secondary motion)
def _spring(target, f, z, y0=None):
    """y'' + 2zw y' + w² y = w² x, semi-implicit Euler at DT, starting at rest."""
    w = 2 * math.pi * f
    y = float(target[0]) if y0 is None else y0
    v = 0.0
    out = np.empty(len(target), np.float64)
    for i, x in enumerate(target):
        v += (w * w * (x - y) - 2 * z * w * v) * DT
        y += v * DT
        out[i] = y
    return out


def _smooth(a, n=9):
    k = np.ones(n) / n
    return np.convolve(np.pad(a, (n // 2, n // 2), mode="edge"), k, mode="valid")


def _dynamics(self, scene, actor):
    cache = self.__dict__.setdefault("_pup_dyn", {})
    key = (id(scene), id(actor))
    if key in cache:
        return cache[key]
    E = _E
    dur = float(scene["end"] - scene["start"])
    n = int(dur / DT) + 2
    ts = np.arange(n) * DT
    xs = np.empty(n)
    F = {f: np.empty(n) for f in ("arm_a", "elbow_a", "arm_b", "head", "torso")}
    for i, t in enumerate(ts):
        k = E.sample_keys(actor.get("keys", [{"t": 0}]), t)
        xs[i] = float(k.get("x", 0.5))
        p = E.mix_pose(k.get("_pose_mix", (actor.get("pose"), actor.get("pose"), 0)))
        for f in F:
            F[f][i] = float(p.get(f, 0.0))
    facing = int(actor.get("facing", 1))
    v = np.gradient(xs, DT) * self.sw / self.sh                 # screen heights per second
    a = _smooth(np.gradient(_smooth(v), DT)) * facing           # the rod's forward acceleration
    pp = actor.get("puppet") if isinstance(actor.get("puppet"), dict) else {}
    sway, fol = float(pp.get("sway", 1.0)), float(pp.get("follow", 1.0))
    d = {"tilt": _spring(np.clip(a * SWAY_DEG * sway, -10, 10), *SPRINGS["sway"], y0=0.0),
         "pend": _spring(np.clip(-a * PEND_DEG * sway, -14, 14), *SPRINGS["pend"], y0=0.0),
         "xr": _spring(xs, *SPRINGS["rodhand"])}
    for f, spr in (("arm_a", "hand"), ("elbow_a", "hand"), ("head", "head")):
        d["d_" + f] = (_spring(F[f], *SPRINGS[spr]) - F[f]) * fol
    d["n"] = n
    cache[key] = d
    return d


# ------------------------------------------------------------------ drawing
def _blur(cov, sigma):
    if sigma < 0.3:
        return cov, 0
    pad = int(math.ceil(3 * sigma))
    img = Image.fromarray((np.pad(cov, pad) * 255 + 0.5).astype(np.uint8)).filter(ImageFilter.GaussianBlur(sigma))
    return np.asarray(img, np.float32) / 255.0, pad


def _rod_layer(segs, n=8):
    """segs: [(top, bottom, w_top, w_bottom, s_top, s_bottom)] in px. Tapered lines whose blur grows along them."""
    xs = [p[0] for s in segs for p in (s[0], s[1])]
    ys = [p[1] for s in segs for p in (s[0], s[1])]
    m = max(max(s[3] for s in segs), 1) + 3 * max(max(s[5] for s in segs), 1) + 2
    x0, y0, x1, y1 = int(min(xs) - m), int(min(ys) - m), int(max(xs) + m), int(max(ys) + m)
    out = np.zeros((y1 - y0, x1 - x0), np.float32)
    for top, bot, w0, w1, s0, s1 in segs:
        for k in range(n):
            u0, u1, um = k / n, (k + 1) / n, (k + 0.5) / n
            p = (top[0] + (bot[0] - top[0]) * u0 - x0, top[1] + (bot[1] - top[1]) * u0 - y0)
            q = (top[0] + (bot[0] - top[0]) * u1 - x0, top[1] + (bot[1] - top[1]) * u1 - y0)
            wd, sg = w0 + (w1 - w0) * um, s0 + (s1 - s0) * um
            # each piece overlaps its neighbours (no notches where the blur steps up)
            L = math.hypot(q[0] - p[0], q[1] - p[1]) or 1.0
            ex, ey = (q[0] - p[0]) / L * (0.8 * wd + sg), (q[1] - p[1]) / L * (0.8 * wd + sg)
            p, q = (p[0] - ex * (k > 0), p[1] - ey * (k > 0)), (q[0] + ex * (k < n - 1), q[1] + ey * (k < n - 1))
            pad = int(3 * sg + wd + 2)
            bx0, by0 = int(min(p[0], q[0]) - pad), int(min(p[1], q[1]) - pad)
            bx1, by1 = int(max(p[0], q[0]) + pad), int(max(p[1], q[1]) + pad)
            bx0, by0, bx1, by1 = max(0, bx0), max(0, by0), min(out.shape[1], bx1), min(out.shape[0], by1)
            if bx1 <= bx0 or by1 <= by0:
                continue
            img = Image.new("L", (bx1 - bx0, by1 - by0), 0)
            ImageDraw.Draw(img).line([(p[0] - bx0, p[1] - by0), (q[0] - bx0, q[1] - by0)], fill=255, width=max(1, int(round(wd))))
            if sg >= 0.3:
                img = img.filter(ImageFilter.GaussianBlur(sg))
            sl = out[by0:by1, bx0:bx1]
            np.maximum(sl, np.asarray(img, np.float32) / 255.0, out=sl)
    return out, x0, y0


def _paste_max(full, cov, x0, y0):
    H, W = full.shape
    h, w = cov.shape
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
    if xb > xa and yb > ya:
        sl = full[ya:yb, xa:xb]
        np.maximum(sl, cov[ya - y0:yb - y0, xa - x0:xb - x0], out=sl)


def _keyed(E, keys, t, field, default):
    """A numeric field the engine's sampler does not animate (gap), with the same per-key easing."""
    pts = [k for k in keys if field in k]
    if not pts:
        return default
    if t <= pts[0]["t"]:
        return float(pts[0][field])
    if t >= pts[-1]["t"]:
        return float(pts[-1][field])
    for a, b in zip(pts, pts[1:]):
        if a["t"] <= t <= b["t"]:
            u = E.EASES.get(b.get("ease", "inout"), E.EASES["inout"])((t - a["t"]) / max(1e-6, b["t"] - a["t"]))
            return float(a[field]) + (float(b[field]) - float(a[field])) * u
    return float(pts[-1][field])


def _active_cycle(actor, tl):
    cyc = actor.get("cycles")
    if not cyc:
        return actor.get("cycle")
    cur = cyc[0]
    for c in cyc:
        if tl >= float(c.get("from", 0)):
            cur = c
    return cur


def puppet_layers(self, scene, actor, tl, lam):
    """The actor's shadow and its rods: [(coverage, x0, y0), ...] at full resolution."""
    E = _E
    k = E.sample_keys(actor.get("keys", [{"t": 0}]), tl)
    op = float(k.get("opacity", 1.0))
    if op <= 0.003:
        return []
    puppet = bool(self.spec.get("puppetry") or actor.get("puppet"))
    gap = _keyed(E, actor.get("gap_keys") or actor.get("keys", []), tl, "gap", float(actor.get("gap", 0.02 if puppet else 0.0)))
    M, pen_m = optics(lam["dist"], gap, lam["size"])
    ppm = self.sh / float(self.spec.get("screen_m", 1.8))       # pixels per metre on the cloth
    x, y = float(k.get("x", 0.5)), float(k.get("y", 0.93))
    px, py = self.to_px(lam["x"] + (x - lam["x"]) * M, lam["y"] + (y - lam["y"]) * M, work=False)
    h = float(k.get("height", actor.get("height", 0.42))) * self.sh * float(k.get("scale", 1.0)) * M
    costume = actor.get("costume", "plain")
    facing = int(k.get("facing", actor.get("facing", 1)))
    grounded = actor.get("grounded", True)
    pose = dict(HF.gait(E.mix_pose(k.get("_pose_mix", (actor.get("pose"), actor.get("pose"), 0))), _active_cycle(actor, tl), tl,
                        E._engine_apply_cycle, costume))
    rods = list(actor.get("rods", ["back", "hand_a"] if puppet else []))
    D = None
    if puppet:
        D = _dynamics(self, scene, actor)
        i = min(D["n"] - 1, max(0, int(round(tl / DT))))
        pose["torso"] = pose.get("torso", 0.0) + D["tilt"][i]
        pose["head"] = pose.get("head", 0.0) + D["d_head"][i] - 0.5 * D["tilt"][i]
        pose["arm_a"] = pose.get("arm_a", 0.0) + D["d_arm_a"][i]
        pose["elbow_a"] = pose.get("elbow_a", 0.0) + D["d_elbow_a"][i]
        if "hand_b" not in rods:
            pose["arm_b"] = pose.get("arm_b", 0.0) + D["pend"][i]
    cov, x0, y0 = HF.figure_mask(px, py, pose, costume, h, facing, grounded, bounds=(0, 0, self.W, self.H))
    out = []
    base = float(self.spec.get("human_penumbra", 0.9))
    sig = math.hypot(base, 0.31 * pen_m * ppm)                  # 10-90 % of a linear penumbra ≈ 2.56 sigma of a Gaussian
    if cov is not None:
        cov, pad = _blur(cov, sig)
        out.append((cov * op, x0 - pad, y0 - pad))
    if rods and D is not None:
        j, Lb = HF.body_skeleton(pose, costume, h, facing)
        oy = py - HF.ground_low(pose, j, Lb, h) if grounded else py
        P = {kk: (px + v[0], oy + v[1]) for kk, v in j.items() if not kk.startswith("_")}
        M2, pen2 = optics(lam["dist"], gap + ROD_REACH, lam["size"])
        xr = D["xr"][min(D["n"] - 1, max(0, int(round(tl / DT))))]
        bx_screen = lam["x"] + (xr - lam["x"]) * M2
        segs = []
        for name in rods:
            if name == "back":
                nb, hp = P["neck_base"], P["hip"]
                top = (nb[0] + (hp[0] - nb[0]) * 0.2 - facing * 0.035 * h, nb[1] + (hp[1] - nb[1]) * 0.2)
            elif name.startswith("hand_"):
                s = name[-1]
                wr, el = P["wr_" + s], P["el_" + s]
                dx, dy = wr[0] - el[0], wr[1] - el[1]
                ln = math.hypot(dx, dy) or 1.0
                top = (wr[0] + dx / ln * 0.035 * h, wr[1] + dy / ln * 0.035 * h)
            else:
                continue
            bx, _ = self.to_px(bx_screen, 1.0, work=False)
            bot = (bx + facing * ROD_SLANT.get(name, 0.0) * self.sh + (top[0] - px), self.sy1 + 0.04 * self.H)
            segs.append((top, bot, ROD_M * ppm * M, ROD_M * 1.3 * ppm * M2, math.hypot(base, 0.31 * pen_m * ppm),
                         math.hypot(base, 0.31 * pen2 * ppm)))
        if segs:
            rc, rx0, ry0 = _rod_layer(segs)
            out.append((rc * op * float(actor.get("rod_opacity", 0.92)), rx0, ry0))
    return out


def render(self, t):
    if not self.spec.get("puppetry") and not any(isinstance(a, dict) and a.get("puppet") for s in self.spec.get("scenes", [])
                                                 for a in s.get("actors", [])):
        return _prev_render(self, t)
    E = _E
    HF.set_time(t)
    scene = self.scene_at(t)
    tl = t - scene["start"]
    lam = lamp_at(self, t)
    bd = self.backdrop(scene, tl)
    shadow = np.zeros((self.hh, self.hw), np.float32)
    full = np.zeros((self.H, self.W), np.float32)
    for actor in scene.get("actors", []):
        if actor.get("type", "human") == "human":
            for cov, x0, y0 in puppet_layers(self, scene, actor, tl, lam):
                _paste_max(full, cov, x0, y0)
        else:
            m, op, _ = self.actor_layer(actor, tl)
            if m is not None:
                np.maximum(shadow, m * op, out=shadow)
    sh = np.maximum(E._resize(shadow, (self.W, self.H)), full)[..., None]
    light = _hotspot(self, lam) * lam["level"] * _weave(self)
    if lam["kind"] == "oil":
        light = light * OIL_TINT
    lit = bd * light * (1 - sh * (1 - self.leak))
    lmask = self._screen * self.light_level(scene, t)
    iris = self.iris_mask(scene, tl)
    if iris is not None:
        lmask = lmask * iris
    cloth = self._screen * np.array((0.035, 0.03, 0.04), np.float32)
    out = lit * lmask + cloth * (1 - lmask) + self._stage * (1 - self._screen)
    rng = np.random.default_rng(int(t * self.fps) + self.seed)
    grain = rng.normal(0, float(self.spec.get("grain", 0.006)), (self.hh, self.hw)).astype(np.float32)
    grain = np.repeat(np.repeat(grain, 2, 0), 2, 1)[: self.H, : self.W, None]
    return E.Frame((np.clip(out + grain, 0, 1) * 255 + 0.5).astype(np.uint8))


def register(E):
    """Install the human anatomy and the puppet renderer into the engine (idempotent)."""
    global _E, _prev_render
    HF.register(E)
    _E = E
    E.BACKDROPS.setdefault("oil-lamp", {"stops": [[0, [214, 158, 96]], [0.5, [248, 206, 142]], [1, [196, 134, 76]]], "clouds": 0.03})
    R = E.ShadowRenderer
    if getattr(R, "_puppet_patched", False):
        return
    _prev_render = R.render
    R.render = render
    R._puppet_patched = True
