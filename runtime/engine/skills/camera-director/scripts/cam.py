#!/usr/bin/env python3
"""camera-director / cam.py — one camera spec -> every backend.

Write the camera move ONCE as JSON (a named move or raw keyframes); this tool
samples it per frame with real easing + seeded handheld noise, checks it like a
camera operator would, draws a storyboard before any render, renders 2D moves
over stills/footage with sub-pixel warps + true shutter-angle motion blur, and
exports the identical path to Blender (bpy), three.js and HTML/GSAP.

Commands
  moves                              list the move vocabulary (2D + 3D) with defaults
  sample SPEC [--out track.json]     bake per-frame track
  check  SPEC [--json]               operator checks (coverage, softness, speed, judder, ease, 180/30 rules)
  board  SPEC --out board.png        storyboard: path + start/mid/end frames on the source (2D) / top view (3D)
  render SPEC --out OUT.mp4          2D render (image or video source), motion blur, AAC audio passthrough
  blender SPEC --out cam_anim.py     bpy script that keys camera (loc/rot/lens/focus) per frame
  three  SPEC --out track.js         three.js / HTML track (+ runtime helpers)
  analyze VIDEO [--json]             measure the camera motion in any video (pan/tilt/zoom/roll/shake)
  verify SPEC OUT.mp4                render-vs-spec: analyze the output and compare with intended move
  doctor                             check dependencies (read-only)

All coordinates: 2D -> cx, cy in [0..1] of the SOURCE, zoom >= 1 (1 = cover-fit), rot in degrees.
                 3D -> Blender convention, Z up, metres; lens in mm on a 36 mm sensor.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys

VERSION = "1.0.0"


# --------------------------------------------------------------------------- unicode-safe IO (OpenCV on Windows cannot open non-ASCII paths)
def imread_u(path, flags=None):
    import cv2, numpy as np
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR if flags is None else flags) if data.size else None


def imwrite_u(path, img):
    import cv2
    ok, buf = cv2.imencode(os.path.splitext(path)[1] or ".png", img)
    if not ok: raise SystemExit("encode failed " + path)
    buf.tofile(path)


_TMP_COPIES = {}
def vcap(path):
    """cv2.VideoCapture that survives Arabic/Unicode paths (falls back to an ASCII temp hard-link/copy)."""
    import cv2, tempfile
    cap = cv2.VideoCapture(path)
    if cap.isOpened():
        return cap
    if path not in _TMP_COPIES:
        import atexit
        d = tempfile.mkdtemp(prefix="camdir_")
        dst = os.path.join(d, "src" + os.path.splitext(path)[1])
        shutil.copy2(path, dst)            # copy (not link): also hydrates OneDrive cloud-only files
        _TMP_COPIES[path] = dst
        atexit.register(shutil.rmtree, d, True)
    cap = cv2.VideoCapture(_TMP_COPIES[path])
    if not cap.isOpened():
        raise SystemExit(f"cannot open video {path}")
    return cap

# --------------------------------------------------------------------------- easing
def _bez(x1, y1, x2, y2):
    """CSS cubic-bezier(x1,y1,x2,y2) -> f(t)."""
    def bx(s): return 3 * x1 * s * (1 - s) ** 2 + 3 * x2 * s * s * (1 - s) + s ** 3
    def by(s): return 3 * y1 * s * (1 - s) ** 2 + 3 * y2 * s * s * (1 - s) + s ** 3
    def f(t):
        if t <= 0: return 0.0
        if t >= 1: return 1.0
        lo, hi = 0.0, 1.0
        for _ in range(40):
            mid = (lo + hi) / 2
            if bx(mid) < t: lo = mid
            else: hi = mid
        return by((lo + hi) / 2)
    return f


EASES = {
    "linear": lambda t: t,
    "inSine": lambda t: 1 - math.cos(t * math.pi / 2),
    "outSine": lambda t: math.sin(t * math.pi / 2),
    "inOutSine": lambda t: -(math.cos(math.pi * t) - 1) / 2,
    "inCubic": lambda t: t ** 3,
    "outCubic": lambda t: 1 - (1 - t) ** 3,
    "inOutCubic": lambda t: 4 * t ** 3 if t < .5 else 1 - (-2 * t + 2) ** 3 / 2,
    "inOutQuart": lambda t: 8 * t ** 4 if t < .5 else 1 - (-2 * t + 2) ** 4 / 2,
    "inOutQuint": lambda t: 16 * t ** 5 if t < .5 else 1 - (-2 * t + 2) ** 5 / 2,
    "outQuart": lambda t: 1 - (1 - t) ** 4,
    "outExpo": lambda t: 1.0 if t >= 1 else 1 - 2 ** (-10 * t),
    "inExpo": lambda t: 0.0 if t <= 0 else 2 ** (10 * t - 10),
    "inOutExpo": lambda t: 0.0 if t <= 0 else 1.0 if t >= 1 else (2 ** (20 * t - 10) / 2 if t < .5 else (2 - 2 ** (-20 * t + 10)) / 2),
    "smoothstep": lambda t: t * t * (3 - 2 * t),
    # "film" curves: long, gentle acceleration like a dolly grip / fluid head
    "dolly": _bez(0.45, 0.0, 0.25, 1.0),
    "operator": _bez(0.33, 0.0, 0.2, 1.0),
    "settle": _bez(0.16, 1.0, 0.3, 1.0),      # fast start, long settle (crash zoom landing)
}
ZERO_START = {"inSine", "inOutSine", "inCubic", "inOutCubic", "inOutQuart", "inOutQuint", "inExpo",
              "inOutExpo", "smoothstep", "dolly", "operator"}
ZERO_END = {"outSine", "inOutSine", "outCubic", "inOutCubic", "inOutQuart", "inOutQuint", "outQuart",
            "outExpo", "inOutExpo", "smoothstep", "dolly", "operator", "settle"}


def ease_fn(e):
    if isinstance(e, list) and len(e) == 4:
        return _bez(*e)
    if e not in EASES:
        raise SystemExit(f"unknown ease '{e}'. choose: {', '.join(EASES)} or [x1,y1,x2,y2]")
    return EASES[e]

# --------------------------------------------------------------------------- noise (handheld)
def _hash(i, seed):
    x = (i * 374761393 + seed * 668265263) & 0xFFFFFFFF
    x = (x ^ (x >> 13)) * 1274126177 & 0xFFFFFFFF
    return ((x ^ (x >> 16)) & 0xFFFF) / 32767.5 - 1.0


def vnoise(x, seed):
    """Smooth 1D value noise in [-1,1] (quintic fade, continuous velocity)."""
    i = math.floor(x)
    f = x - i
    u = f * f * f * (f * (f * 6 - 15) + 10)
    return _hash(i, seed) * (1 - u) + _hash(i + 1, seed) * u


def fbm(x, seed, octaves=2):
    s, a, n = 0.0, 1.0, 0.0
    for o in range(octaves):
        s += a * vnoise(x * (2 ** o), seed + 97 * o)
        n += a
        a *= 0.5
    return s / n


# amp_* in degrees (rotation) and in fraction of the visible frame (2D position) / metres (3D)
SHAKE_PRESETS = {
    "none":      dict(rot=0.0,  pos=0.0,    freq=0.0),
    "breath":    dict(rot=0.10, pos=0.0015, freq=0.25),  # locked-off tripod that is "alive"
    "float":     dict(rot=0.25, pos=0.003,  freq=0.35),  # gimbal / steadicam drift
    "handheld":  dict(rot=0.55, pos=0.006,  freq=0.9),   # documentary shoulder rig
    "nervous":   dict(rot=1.1,  pos=0.012,  freq=1.8),   # tension, found-footage
    "run":       dict(rot=2.0,  pos=0.025,  freq=2.6),   # running operator
    "impact":    dict(rot=3.0,  pos=0.035,  freq=11.0, decay=0.45),  # hit / explosion, trauma decays
}


def shake_margin(sh, w, h):
    """extra zoom so handheld offsets/roll never expose the frame edge."""
    if not sh: return 1.0
    if isinstance(sh, str): sh = {"preset": sh}
    b = dict(SHAKE_PRESETS.get(sh.get("preset", "handheld"), SHAKE_PRESETS["handheld"])); b.update({k: v for k, v in sh.items() if k != "preset"})
    k = float(b.get("amount", 1.0)) ** 2
    r = math.radians(b["rot"] * k)
    rot_cov = math.cos(r) + math.sin(r) * max(w / h, h / w)
    return (1 + 2.2 * b["pos"] * k) * rot_cov


def shake_at(t, sh, seed, dur):
    """returns (dx, dy, droll, dpitch, dyaw) using Eiserloh trauma^2 scaling."""
    if not sh:
        return (0, 0, 0, 0, 0)
    if isinstance(sh, str):
        sh = {"preset": sh}
    base = dict(SHAKE_PRESETS.get(sh.get("preset", "handheld"), SHAKE_PRESETS["handheld"]))
    base.update({k: v for k, v in sh.items() if k != "preset"})
    if base["freq"] <= 0:
        return (0, 0, 0, 0, 0)
    trauma = float(base.get("amount", 1.0))
    if "decay" in base:                       # impact: trauma falls linearly from t0
        t0 = float(base.get("at", 0.0))
        if t < t0:
            trauma = 0.0
        else:
            trauma *= max(0.0, 1 - (t - t0) / max(1e-6, base["decay"]))
    k = trauma * trauma                        # trauma^2 feels right (Eiserloh, GDC 2016)
    x = t * base["freq"]
    return (base["pos"] * k * fbm(x, seed + 1), base["pos"] * k * fbm(x, seed + 2),
            base["rot"] * k * fbm(x, seed + 3), base["rot"] * k * fbm(x, seed + 4),
            base["rot"] * k * fbm(x, seed + 5))

# --------------------------------------------------------------------------- move vocabulary
MOVES2D = {
    "static":      ("Locked-off frame. Authority, observation, lets action play.", "hold"),
    "push_in":     ("Slow push toward the subject: rising importance, intimacy, realisation.", "inOutSine 4-8 s, zoom +12..25%"),
    "pull_out":    ("Pull back: isolation, reveal context, ending.", "inOutSine 4-8 s"),
    "ken_burns":   ("Gentle zoom+drift on a still toward a point of interest.", "linear/inOutSine 5-8 s, zoom 1.05->1.2"),
    "pan_left":    ("Horizontal pan (subject/content slides right). Follow or reveal across.", "operator 3-7 s"),
    "pan_right":   ("Horizontal pan (content slides left).", "operator 3-7 s"),
    "tilt_up":     ("Tilt up: scale, aspiration, reveal height.", "operator 3-6 s"),
    "tilt_down":   ("Tilt down: descend, discover, weight.", "operator 3-6 s"),
    "reveal":      ("Start tight on a detail, pull out to the whole.", "dolly 4-7 s"),
    "punch_in":    ("Hard cut-like fast zoom on a beat (emphasis).", "outExpo 0.15-0.3 s, +20..40%"),
    "crash_zoom":  ("Violent zoom into the subject (comedy, shock).", "outExpo 0.3-0.6 s, zoom x1.8-2.5"),
    "whip_pan":    ("Very fast pan with motion blur; use as a transition.", "inOutExpo 0.25-0.45 s"),
    "dutch_roll":  ("Roll the horizon: unease, dream, imbalance.", "inOutSine 2-5 s, 5-15 deg"),
    "drift":       ("Slow lateral float: dreamy B-roll, keeps stills alive.", "linear 5-10 s"),
    "handheld":    ("Static framing + operator noise (shake preset).", "any"),
    "keys":        ("Raw keyframes [{t,cx,cy,zoom,rot,ease}].", "any"),
}
MOVES3D = {
    "static":     ("Locked camera at pos looking at target.", ""),
    "dolly_in":   ("Physically move toward the target (perspective changes, unlike zoom).", "dolly 3-8 s"),
    "dolly_out":  ("Move away from the target.", "dolly 3-8 s"),
    "truck":      ("Lateral slide, camera keeps its heading (parallax reveals depth).", "operator 3-8 s"),
    "pedestal":   ("Vertical rise/fall, heading kept.", "operator 3-6 s"),
    "crane_up":   ("Rise while keeping the subject framed (tilts down): grandeur, ending.", "dolly 4-8 s"),
    "orbit":      ("Arc around the target (arc deg). Product hero, character reveal.", "inOutSine 4-10 s, 20-90 deg"),
    "dolly_zoom": ("Vertigo: move while counter-zooming so subject size holds; background warps.", "inOutSine 2-5 s"),
    "flythrough": ("Catmull-Rom path through points, looks ahead along the path (or at target).", "inOutSine"),
    "rack_focus": ("Static camera, focus pulls from target to focus_to point.", "inOutSine 1-2.5 s"),
    "keys":       ("Raw keyframes [{t,pos,target,lens,roll,ease}].", "any"),
}

# --------------------------------------------------------------------------- spec -> keys (2D)
def _lerp(a, b, u): return a + (b - a) * u


def build_keys_2d(spec):
    mv = spec.get("move", "keys")
    d = float(spec.get("dur", 5.0))
    sx, sy = spec.get("subject", [0.5, 0.5])
    s = float(spec.get("strength", 1.0))
    ease = spec.get("ease")
    z0 = float(spec.get("zoom", 1.0))
    if mv == "keys":
        return spec["keys"]
    if mv in ("static", "handheld"):
        z = max(z0, 1.06 if spec.get("shake") else z0)
        return [dict(t=0, cx=sx if z > 1 else .5, cy=sy if z > 1 else .5, zoom=z), dict(t=d, cx=sx if z > 1 else .5, cy=sy if z > 1 else .5, zoom=z)]
    if mv == "push_in":
        return [dict(t=0, cx=.5, cy=.5, zoom=z0), dict(t=d, cx=_lerp(.5, sx, .8), cy=_lerp(.5, sy, .8), zoom=z0 * (1 + .18 * s), ease=ease or "inOutSine")]
    if mv == "pull_out":
        return [dict(t=0, cx=_lerp(.5, sx, .8), cy=_lerp(.5, sy, .8), zoom=z0 * (1 + .18 * s)), dict(t=d, cx=.5, cy=.5, zoom=z0, ease=ease or "inOutSine")]
    if mv == "ken_burns":
        za, zb = 1.05 * z0, z0 * (1.05 + .15 * s)
        return [dict(t=0, cx=_lerp(.5, sx, .3), cy=_lerp(.5, sy, .3), zoom=za), dict(t=d, cx=sx, cy=sy, zoom=zb, ease=ease or "inOutSine")]
    if mv == "reveal":
        return [dict(t=0, cx=sx, cy=sy, zoom=z0 * (1 + .9 * s)), dict(t=d, cx=.5, cy=.5, zoom=z0, ease=ease or "dolly")]
    if mv in ("pan_left", "pan_right", "tilt_up", "tilt_down", "drift"):
        z = max(z0, 1.25 if mv != "drift" else 1.12)
        span = (1 - 1 / z) * .5 * .92 * min(1.0, s)     # how far the window can travel from centre
        a, b = (.5 + span, .5 - span)
        if mv == "pan_left":   return [dict(t=0, cx=a, cy=sy if z > 1 else .5, zoom=z), dict(t=d, cx=b, cy=sy, zoom=z, ease=ease or "operator")]
        if mv == "pan_right":  return [dict(t=0, cx=b, cy=sy, zoom=z), dict(t=d, cx=a, cy=sy, zoom=z, ease=ease or "operator")]
        if mv == "tilt_up":    return [dict(t=0, cx=sx, cy=a, zoom=z), dict(t=d, cx=sx, cy=b, zoom=z, ease=ease or "operator")]
        if mv == "tilt_down":  return [dict(t=0, cx=sx, cy=b, zoom=z), dict(t=d, cx=sx, cy=a, zoom=z, ease=ease or "operator")]
        return [dict(t=0, cx=.5 - span * .5, cy=sy, zoom=z), dict(t=d, cx=.5 + span * .5, cy=sy, zoom=z, ease=ease or "linear")]
    if mv in ("punch_in", "crash_zoom"):
        hit = float(spec.get("at", 0.0))
        dz = (.3 if mv == "punch_in" else 1.2) * s
        ln = float(spec.get("move_dur", .22 if mv == "punch_in" else .45))
        k = [dict(t=0, cx=.5, cy=.5, zoom=z0)]
        if hit > 0: k.append(dict(t=hit, cx=.5, cy=.5, zoom=z0))
        k.append(dict(t=hit + ln, cx=sx, cy=sy, zoom=z0 * (1 + dz), ease=ease or "outExpo"))
        if hit + ln < d: k.append(dict(t=d, cx=sx, cy=sy, zoom=z0 * (1 + dz)))
        return k
    if mv == "whip_pan":
        z = max(z0, 1.6)
        span = (1 - 1 / z) * .5 * .95
        sgn = -1 if spec.get("dir", "right") == "left" else 1
        return [dict(t=0, cx=.5 - sgn * span, cy=.5, zoom=z), dict(t=d, cx=.5 + sgn * span, cy=.5, zoom=z, ease=ease or "inOutExpo")]
    if mv == "dutch_roll":
        ang = float(spec.get("angle", 8.0)) * s
        w, h = spec.get("size", [1920, 1080])
        r = math.radians(abs(ang))
        zc = z0 * (math.cos(r) + math.sin(r) * max(w / h, h / w)) * 1.01   # zoom that keeps the rolled frame filled
        return [dict(t=0, cx=sx, cy=sy, zoom=z0, rot=0), dict(t=d, cx=sx, cy=sy, zoom=zc, rot=ang, ease=ease or "inOutSine")]
    raise SystemExit(f"unknown 2D move '{mv}'. see: cam.py moves")


def _interp_keys(keys, t, fields):
    keys = sorted(keys, key=lambda k: k["t"])
    if t <= keys[0]["t"]:
        return {f: keys[0].get(f, DEF2D.get(f, 0)) for f in fields}
    for a, b in zip(keys, keys[1:]):
        if t <= b["t"]:
            u = (t - a["t"]) / max(1e-9, b["t"] - a["t"])
            u = ease_fn(b.get("ease", "inOutSine"))(u)
            out = {}
            for f in fields:
                va, vb = a.get(f, DEF2D.get(f, 0)), b.get(f, DEF2D.get(f, 0))
                if isinstance(va, list):
                    out[f] = [x + (y - x) * u for x, y in zip(va, vb)]
                elif f == "zoom":     # zoom interpolates in log space -> perceptually constant speed
                    out[f] = math.exp(math.log(va) + (math.log(vb) - math.log(va)) * u)
                else:
                    out[f] = va + (vb - va) * u
            return out
    return {f: keys[-1].get(f, DEF2D.get(f, 0)) for f in fields}


DEF2D = dict(cx=.5, cy=.5, zoom=1.0, rot=0.0)

# --------------------------------------------------------------------------- geometry 2D
def src_size(spec):
    if "src_size" in spec:
        return tuple(spec["src_size"])
    src = spec.get("source")
    if not src:
        return tuple(spec.get("size", [1920, 1080]))
    import cv2
    if os.path.splitext(src)[1].lower() in (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"):
        cap = vcap(src)
        w, h = int(cap.get(3)), int(cap.get(4))
        cap.release()
        if w and h:
            return (w, h)
    im = imread_u(src, cv2.IMREAD_UNCHANGED)
    if im is None:
        raise SystemExit(f"cannot read source {src}")
    return (im.shape[1], im.shape[0])


def half_extent(W, H, w, h, zoom, rot):
    s0 = max(w / W, h / H)
    r = math.radians(rot)
    c, s = abs(math.cos(r)), abs(math.sin(r))
    sc = s0 * zoom
    return ((c * w / 2 + s * h / 2) / sc, (s * w / 2 + c * h / 2) / sc, s0)


def sample_2d(spec):
    fps = float(spec.get("fps", 30))
    d = float(spec.get("dur", 5.0))
    w, h = spec.get("size", [1920, 1080])
    W, H = src_size(spec)
    keys = build_keys_2d(spec)
    d = max(d, max(k["t"] for k in keys))
    n = int(round(d * fps))
    seed = int(spec.get("seed", 7))
    safe = spec.get("safe", True)
    out, fixed, zfixed = [], 0, 0
    margin = shake_margin(spec.get("shake"), w, h)
    for i in range(n):
        t = i / fps
        v = _interp_keys(keys, t, ["cx", "cy", "zoom", "rot"])
        dx, dy, dr, _, _ = shake_at(t, spec.get("shake"), seed, d)
        z, rot = v["zoom"] * margin, v["rot"] + dr
        ex, ey, s0 = half_extent(W, H, w, h, z, rot)
        cx = v["cx"] * W + dx * (w / (s0 * z))
        cy = v["cy"] * H + dy * (h / (s0 * z))
        corrected = False
        if safe:
            need = max(2 * ex / W, 2 * ey / H)        # >1 means window bigger than source -> zoom up
            if need > 1.0001:
                z *= need
                ex, ey, s0 = half_extent(W, H, w, h, z, rot)
                corrected = True
                zfixed += 1
            ncx = min(max(cx, ex), W - ex)
            ncy = min(max(cy, ey), H - ey)
            if abs(ncx - cx) > 0.01 * 2 * ex or abs(ncy - cy) > 0.01 * 2 * ey:
                corrected = True
            cx, cy = ncx, ncy
        fixed += corrected
        out.append(dict(f=i, t=round(t, 5), cx=cx / W, cy=cy / H, zoom=z, rot=rot))
    return dict(mode="2d", fps=fps, size=[w, h], src_size=[W, H], frames=out, safe_fixed=fixed, zoom_forced=zfixed,
                move=spec.get("move", "keys"))

# --------------------------------------------------------------------------- 3D
def _v(a): return [float(x) for x in a]
def _sub(a, b): return [x - y for x, y in zip(a, b)]
def _add(a, b): return [x + y for x, y in zip(a, b)]
def _mul(a, k): return [x * k for x in a]
def _len(a): return math.sqrt(sum(x * x for x in a))
def _norm(a):
    l = _len(a) or 1.0
    return [x / l for x in a]
def _cross(a, b): return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _catmull(ps, u):
    """centripetal-ish uniform Catmull-Rom through points, u in [0,1]."""
    n = len(ps) - 1
    x = min(max(u, 0), 1) * n
    i = min(int(x), n - 1)
    t = x - i
    p0, p1, p2, p3 = ps[max(i - 1, 0)], ps[i], ps[i + 1], ps[min(i + 2, n)]
    return [0.5 * ((2 * b) + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t * t + (-a + 3 * b - 3 * c + d) * t ** 3)
            for a, b, c, d in zip(p0, p1, p2, p3)]


def build_keys_3d(spec):
    mv = spec.get("move", "keys")
    d = float(spec.get("dur", 5.0))
    T = _v(spec.get("target", [0, 0, 1]))
    P = _v(spec.get("pos", [0, -6, 1.6]))
    lens = float(spec.get("lens", 50))
    s = float(spec.get("strength", 1.0))
    ease = spec.get("ease")
    if mv == "keys":
        return spec["keys"]
    fwd = _norm(_sub(T, P))
    right = _norm(_cross(fwd, [0, 0, 1]))
    dist = _len(_sub(T, P))
    if mv in ("static", "rack_focus"):
        k0 = dict(t=0, pos=P, target=T, lens=lens, focus=dist)
        k1 = dict(t=d, pos=P, target=T, lens=lens, focus=dist, ease=ease or "inOutSine")
        if mv == "rack_focus":
            ft = _v(spec.get("focus_to", T))
            k1["focus"] = _len(_sub(ft, P))
            k0["focus"] = float(spec.get("focus_from", dist))
        return [k0, k1]
    if mv in ("dolly_in", "dolly_out"):
        amt = float(spec.get("distance", dist * .35 * s))
        Q = _add(P, _mul(fwd, amt))
        a, b = (P, Q) if mv == "dolly_in" else (Q, P)
        return [dict(t=0, pos=a, target=T, lens=lens), dict(t=d, pos=b, target=T, lens=lens, ease=ease or "dolly")]
    if mv == "truck":
        amt = float(spec.get("distance", dist * .4 * s)) * (-1 if spec.get("dir") == "left" else 1)
        off = _mul(right, amt)
        return [dict(t=0, pos=P, target=T, lens=lens), dict(t=d, pos=_add(P, off), target=_add(T, off), lens=lens, ease=ease or "operator")]
    if mv == "pedestal":
        amt = float(spec.get("distance", dist * .25 * s)) * (-1 if spec.get("dir") == "down" else 1)
        off = [0, 0, amt]
        return [dict(t=0, pos=P, target=T, lens=lens), dict(t=d, pos=_add(P, off), target=_add(T, off), lens=lens, ease=ease or "operator")]
    if mv == "crane_up":
        amt = float(spec.get("distance", dist * .6 * s))
        back = _mul(fwd, -dist * .15 * s)
        return [dict(t=0, pos=P, target=T, lens=lens), dict(t=d, pos=_add(_add(P, back), [0, 0, amt]), target=T, lens=lens, ease=ease or "dolly")]
    if mv == "orbit":
        arc = float(spec.get("arc", 45.0)) * (-1 if spec.get("dir") == "left" else 1)
        rel = _sub(P, T)
        r = math.hypot(rel[0], rel[1])
        a0 = math.atan2(rel[1], rel[0])
        steps = max(2, int(abs(arc) / 5) + 1)
        e = ease or "inOutSine"
        # keys carry angle so interpolation stays on the circle
        return [dict(t=0, angle=a0, radius=r, z=P[2], target=T, lens=lens),
                dict(t=d, angle=a0 + math.radians(arc), radius=r * float(spec.get("radius_end", 1.0)), z=P[2] + float(spec.get("rise", 0.0)), target=T, lens=lens, ease=e)]
    if mv == "dolly_zoom":
        k = float(spec.get("ratio", 2.0)) * s        # end distance = dist * ratio  (ratio>1: pull back + zoom in)
        d1 = dist * k
        Q = _sub(T, _mul(fwd, d1))
        return [dict(t=0, pos=P, target=T, lens=lens, dz=dist), dict(t=d, pos=Q, target=T, lens=lens * d1 / dist, dz=d1, ease=ease or "inOutSine")]
    if mv == "flythrough":
        return [dict(t=0, path=spec["path"], target=spec.get("target"), lens=lens), dict(t=d, lens=float(spec.get("lens_end", lens)), ease=ease or "inOutSine")]
    raise SystemExit(f"unknown 3D move '{mv}'. see: cam.py moves")


def sample_3d(spec):
    fps = float(spec.get("fps", 30))
    d = float(spec.get("dur", 5.0))
    keys = build_keys_3d(spec)
    mv = spec.get("move", "keys")
    seed = int(spec.get("seed", 7))
    n = int(round(d * fps))
    out = []
    for i in range(n):
        t = i / fps
        if mv == "orbit":
            k0, k1 = keys
            u = ease_fn(k1["ease"])(min(1, t / d))
            ang = _lerp(k0["angle"], k1["angle"], u)
            r = _lerp(k0["radius"], k1["radius"], u)
            z = _lerp(k0["z"], k1["z"], u)
            T = k0["target"]
            pos, tgt, lens = [T[0] + r * math.cos(ang), T[1] + r * math.sin(ang), z], T, k0["lens"]
            focus = _len(_sub(tgt, pos))
        elif mv == "flythrough":
            k0, k1 = keys
            u = ease_fn(k1["ease"])(min(1, t / d))
            ps = [_v(p) for p in k0["path"]]
            pos = _catmull(ps, u)
            tgt = _v(k0["target"]) if k0.get("target") else _catmull(ps, min(1, u + float(spec.get("lookahead", .08))))
            if _len(_sub(tgt, pos)) < 1e-4:
                tgt = _add(pos, _sub(ps[-1], ps[-2]))
            lens = _lerp(k0["lens"], k1["lens"], u)
            focus = _len(_sub(tgt, pos))
        elif mv == "dolly_zoom":
            k0, k1 = keys
            u = ease_fn(k1["ease"])(min(1, t / d))
            dz = _lerp(k0["dz"], k1["dz"], u)
            fwd = _norm(_sub(k0["target"], k0["pos"]))
            pos = _sub(k0["target"], _mul(fwd, dz))
            tgt = k0["target"]
            lens = k0["lens"] * dz / k0["dz"]          # exact: subject size ∝ lens / distance
            focus = dz
        else:
            v = _interp_keys(keys, t, ["pos", "target", "lens"] + (["focus"] if "focus" in keys[0] else []))
            pos, tgt, lens = v["pos"], v["target"], v["lens"]
            focus = v.get("focus", _len(_sub(tgt, pos)))
        _, _, droll, dp, dy = shake_at(t, spec.get("shake"), seed, d)
        out.append(dict(f=i, t=round(t, 5), pos=[round(x, 5) for x in pos], target=[round(x, 5) for x in tgt],
                        lens=round(lens, 4), roll=round(float(spec.get("roll", 0)) + droll, 4),
                        pitch_n=round(dp, 4), yaw_n=round(dy, 4), focus=round(focus, 4)))
    return dict(mode="3d", fps=fps, size=spec.get("size", [1920, 1080]), frames=out, move=mv,
                fstop=spec.get("fstop"), shutter=spec.get("shutter", 180))


def sample(spec):
    return sample_3d(spec) if spec.get("mode") == "3d" else sample_2d(spec)

# --------------------------------------------------------------------------- checks
def _issue(level, code, msg): return dict(level=level, code=code, msg=msg)


def check(spec, tr=None):
    tr = tr or sample(spec)
    iss = []
    fr = tr["frames"]
    fps = tr["fps"]
    d = len(fr) / fps
    mv = spec.get("move", "keys")
    fast = mv in ("whip_pan", "crash_zoom", "punch_in")
    if fps not in (23.976, 24, 25, 29.97, 30, 48, 50, 59.94, 60):
        iss.append(_issue("warn", "fps", f"unusual fps {fps}"))
    if not fast and d < 1.5 and mv not in ("static", "handheld"):
        iss.append(_issue("warn", "too_short", f"{mv} over {d:.2f}s: a motivated move needs >= ~1.5-2 s to read"))
    if mv in ("push_in", "pull_out", "ken_burns", "drift") and d > 12:
        iss.append(_issue("info", "long", f"{d:.1f}s single move; most moves resolve in 3-8 s"))
    if tr["mode"] == "2d":
        w, h = tr["size"]
        W, H = tr["src_size"]
        if tr.get("zoom_forced"):
            iss.append(_issue("warn", "coverage_zoom", f"{tr['zoom_forced']} frames: window was bigger than the source, zoom forced up (rotation/shake/aspect). raise zoom yourself"))
        elif tr.get("safe_fixed"):
            iss.append(_issue("info", "edge_clamp", f"{tr['safe_fixed']} frames: subject sits near the source edge, centre clamped >1% so the frame stays filled"))
        zmax = max(f["zoom"] for f in fr)
        s0 = max(w / W, h / H)
        upscale = s0 * zmax
        if upscale > 1.5:
            iss.append(_issue("fail", "soft", f"peak magnification {upscale:.2f}x source pixels -> visibly soft. use a bigger source or less zoom (<=1.25x ok)"))
        elif upscale > 1.15:
            iss.append(_issue("warn", "soft", f"peak magnification {upscale:.2f}x source pixels (slight softening)"))
        # screen speed in output-widths per second (content motion)
        sp, zr, rr = [], [], []
        for a, b in zip(fr, fr[1:]):
            vis_w = W / (s0 * a["zoom"])
            dxp = (b["cx"] - a["cx"]) * W / vis_w * w    # output px of content travel
            dyp = (b["cy"] - a["cy"]) * H / vis_w * w
            sp.append(math.hypot(dxp, dyp))
            zr.append(abs(math.log(b["zoom"] / a["zoom"])) * fps)
            rr.append(abs(b["rot"] - a["rot"]) * fps)
        if sp:
            peak = max(sp)
            secs_to_cross = (w / (peak * fps)) if peak > 0 else 1e9
            # RED pan-speed guidance: at 24 fps no faster than one frame width per ~7 s (scales with fps)
            red_limit = 7.0 * 24.0 / fps
            if not fast and peak > 0 and secs_to_cross < red_limit:
                lvl = "warn" if not spec.get("motion_blur", True) else "info"
                iss.append(_issue(lvl, "judder", f"content crosses the frame in {secs_to_cross:.1f}s (RED guide: >= {red_limit:.1f}s at {fps:g}fps). "
                                  + ("no motion blur -> strobing" if lvl == "warn" else "shutter blur on; OK if the move tracks a subject")))
            if not fast and secs_to_cross < 2.0:
                iss.append(_issue("warn", "fast_pan", f"peak pan crosses frame width in {secs_to_cross:.2f}s ({peak:.1f}px/frame): reads as a whip, not a pan. slow it or call it whip_pan"))
            tr["stats"] = dict(peak_px_per_frame=round(peak, 2), cross_frame_s=round(secs_to_cross, 2),
                               peak_zoom_rate_pct_s=round(max(zr) * 100, 1), peak_roll_deg_s=round(max(rr), 2),
                               peak_magnification=round(upscale, 3))
            if not fast and max(zr) > 0.12:
                iss.append(_issue("warn", "zoom_rate", f"zoom rate peaks at {max(zr)*100:.0f}%/s; calm push-ins live at 2-6%/s"))
            # ease: velocity at ends
            if not fast and len(sp) > 4 and mv not in ("drift", "static", "handheld", "keys"):
                v_end = sp[-1] + zr[-1] * w / fps * 0.5
                v_mid = max(sp[len(sp) // 2], 1e-9) + zr[len(zr) // 2] * w / fps * 0.5
                if v_end > 0.35 * v_mid and not spec.get("cut_on_motion"):
                    iss.append(_issue("info", "ease_end", "move still travelling on the last frame; fine only if you cut on motion (set cut_on_motion:true)"))
    else:
        lens = [f["lens"] for f in fr]
        if min(lens) < 12 or max(lens) > 300:
            iss.append(_issue("warn", "lens", f"lens range {min(lens):.0f}-{max(lens):.0f}mm is extreme"))
        sp = [_len(_sub(b["pos"], a["pos"])) * fps for a, b in zip(fr, fr[1:])]
        ang = []
        for a, b in zip(fr, fr[1:]):
            da = _norm(_sub(a["target"], a["pos"])); db = _norm(_sub(b["target"], b["pos"]))
            ang.append(math.degrees(math.acos(max(-1, min(1, sum(x * y for x, y in zip(da, db)))))) * fps)
        if ang:
            hfov = 2 * math.degrees(math.atan(18 / min(lens)))
            cross = hfov / max(ang) if max(ang) > 0 else 1e9
            tr["stats"] = dict(peak_speed_m_s=round(max(sp), 3), peak_turn_deg_s=round(max(ang), 2),
                               hfov_deg=round(hfov, 1), frame_cross_s=round(cross, 2))
            if not fast and cross < 2.0:
                iss.append(_issue("warn", "fast_turn", f"camera turns one frame width in {cross:.2f}s: will judder at 24/30fps without motion blur"))
        if spec.get("fstop") and spec["fstop"] < 1.4:
            iss.append(_issue("info", "dof", "f/<1.4: razor focus, make sure focus tracks the subject"))
    return iss


def check_sequence(seq):
    """shot-to-shot film grammar: 180 line, 30-degree rule, motion continuity."""
    iss = []
    shots = seq["shots"]
    line = seq.get("axis")          # [[x,y],[x,y]] the line of action (3D top view)
    prev = None
    for i, sh in enumerate(shots):
        if sh.get("mode") == "3d" and line:
            (ax, ay), (bx, by) = line
            px, py = sh["pos"][0], sh["pos"][1]
            side = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
            sh["_side"] = 1 if side > 0 else -1
            if prev is not None and prev.get("_side") and sh["_side"] != prev["_side"] and not sh.get("cross_line_ok"):
                iss.append(_issue("fail", "180_rule", f"shot {i}: camera jumped across the line of action (screen direction flips). add a neutral shot or cross_line_ok:true"))
        if prev is not None and sh.get("mode") == "3d" and prev.get("mode") == "3d" and sh.get("target") == prev.get("target"):
            da = _norm(_sub(prev["target"], prev["pos"])); db = _norm(_sub(sh["target"], sh["pos"]))
            angd = math.degrees(math.acos(max(-1, min(1, sum(x * y for x, y in zip(da, db))))))
            lr = max(sh.get("lens", 50), prev.get("lens", 50)) / min(sh.get("lens", 50), prev.get("lens", 50))
            if angd < 30 and lr < 1.5:
                iss.append(_issue("warn", "30_rule", f"shot {i}: only {angd:.0f} deg and x{lr:.2f} lens from previous shot on same subject -> jump cut. change angle >=30 deg or size (lens x1.5+)"))
        if prev is not None:
            a, b = prev.get("move", "static"), sh.get("move", "static")
            if a in ("pan_left", "truck") and b in ("pan_right",) or a == "pan_right" and b == "pan_left":
                iss.append(_issue("warn", "vector", f"shot {i}: pan direction reverses across the cut ({a} -> {b}); motion should carry through the cut"))
            if a == "push_in" and b == "pull_out" and not sh.get("intent_reset"):
                iss.append(_issue("info", "vector", f"shot {i}: push -> pull across a cut reads as a recoil; intended?"))
        for x in check(sh):
            x["msg"] = f"shot {i}: " + x["msg"]
            iss.append(x)
        prev = sh
    return iss

# --------------------------------------------------------------------------- 2D renderer
def _affine(W, H, w, h, f):
    s0 = max(w / W, h / H)
    sc = s0 * f["zoom"]
    r = math.radians(f["rot"])
    c, s = math.cos(r) * sc, math.sin(r) * sc
    cx, cy = f["cx"] * W, f["cy"] * H
    # out = R*sc*(src - C) + (w/2,h/2)
    import numpy as np
    return np.array([[c, -s, w / 2 - (c * cx - s * cy)], [s, c, h / 2 - (s * cx + c * cy)]], dtype=np.float64)


def _is_video(p): return os.path.splitext(p)[1].lower() in (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v")


def _has_audio(p):
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", p],
                           capture_output=True, text=True)
        return bool(r.stdout.strip())
    except Exception:
        return False


def render_2d(spec, out, crf=16, preview=False):
    import cv2
    import numpy as np
    tr = sample_2d(spec)
    w, h = tr["size"]
    W, H = tr["src_size"]
    fps = tr["fps"]
    src = spec["source"]
    vid = _is_video(src)
    shutter = float(spec.get("shutter", 180)) if spec.get("motion_blur", True) else 0.0
    if preview:
        w, h = w // 2 // 2 * 2, h // 2 // 2 * 2
        tr["size"] = [w, h]
    if vid:
        cap = vcap(src)
        sfps = cap.get(cv2.CAP_PROP_FPS) or fps
        cache = {}
        def frame_at(t):
            idx = int(round(t * sfps))
            if idx in cache: return cache[idx]
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, im = cap.read()
            if not ok:
                im = cache.get(max(cache)) if cache else None
            cache.clear(); cache[idx] = im
            return im
    else:
        still = imread_u(src)
        def frame_at(t): return still
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-"]
    audio = vid and _has_audio(src) and spec.get("audio", True)
    if audio:
        cmd += ["-i", src, "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "256k", "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", "medium" if preview else "slow", "-crf", str(crf), "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    fr = tr["frames"]
    # pre-shrink oversized sources so peak magnification ~1 (same pixels, far less work)
    zmax = max(f["zoom"] for f in fr)
    pre = min(1.0, max(w / W, h / H) * zmax * 1.05)
    if pre < 0.95:
        _raw = frame_at
        Wp, Hp = int(round(W * pre)), int(round(H * pre))
        def frame_at(t, _raw=_raw):
            im0 = _raw(t)
            return None if im0 is None else cv2.resize(im0, (Wp, Hp), interpolation=cv2.INTER_AREA)
        W, H = Wp, Hp
    interp = cv2.INTER_LANCZOS4 if not preview else cv2.INTER_LINEAR
    blurred = 0
    for i, f in enumerate(fr):
        im = frame_at(f["t"])
        g = fr[min(i + 1, len(fr) - 1)]
        # how many px does a corner travel this frame? -> sub-samples for shutter blur
        A0, A1 = _affine(W, H, w, h, f), _affine(W, H, w, h, g)
        inv = cv2.invertAffineTransform(A0)
        oc = np.array([[0, 0, 1], [w, 0, 1], [0, h, 1], [w, h, 1], [w / 2, h / 2, 1]], float).T
        srcpts = np.vstack([inv @ oc, np.ones((1, 5))])
        travel = float(np.max(np.linalg.norm(A1 @ srcpts - oc[:2], axis=0)))
        nsub = 1
        if shutter > 0 and travel * shutter / 360 > 1.5:
            nsub = int(min(24, math.ceil(travel * shutter / 360 / 1.5)))
        if nsub == 1:
            o = cv2.warpAffine(im, A0, (w, h), flags=interp, borderMode=cv2.BORDER_REFLECT101)
        else:
            blurred += 1
            acc = np.zeros((h, w, 3), np.float32)
            for k in range(nsub):
                u = (k / nsub) * shutter / 360 - shutter / 720       # centred shutter
                ff = {key: f[key] + (g[key] - f[key]) * u for key in ("cx", "cy", "zoom", "rot")}
                acc += cv2.warpAffine(im, _affine(W, H, w, h, ff), (w, h), flags=cv2.INTER_CUBIC if not preview else interp, borderMode=cv2.BORDER_REFLECT101).astype(np.float32)
            o = np.clip(acc / nsub + 0.5, 0, 255).astype(np.uint8)
        p.stdin.write(o.tobytes())
    p.stdin.close()
    rc = p.wait()
    if rc:
        raise SystemExit(f"ffmpeg failed rc={rc}")
    return dict(out=out, frames=len(fr), fps=fps, size=[w, h], motion_blur_frames=blurred, audio=bool(audio))

# --------------------------------------------------------------------------- storyboard
def board(spec, out):
    import cv2
    import numpy as np
    tr = sample(spec)
    fr = tr["frames"]
    if tr["mode"] == "2d":
        W, H = tr["src_size"]
        w, h = tr["size"]
        if spec.get("source") and not _is_video(spec["source"]):
            base = imread_u(spec["source"])
        elif spec.get("source"):
            cap = vcap(spec["source"]); ok, base = cap.read(); cap.release()
        else:
            base = np.full((H, W, 3), 60, np.uint8)
        k = 1400 / max(W, H)
        img = cv2.resize(base, (int(W * k), int(H * k)), interpolation=cv2.INTER_AREA)
        img = (img * 0.55).astype(np.uint8)
        cols = [(80, 220, 80), (0, 200, 255), (60, 60, 255)]
        picks = [0, len(fr) // 2, len(fr) - 1]
        pts = [(int(f["cx"] * W * k), int(f["cy"] * H * k)) for f in fr]
        for a, b in zip(pts, pts[1:]):
            cv2.line(img, a, b, (255, 255, 255), 2, cv2.LINE_AA)
        for c, j in zip(cols, picks):
            f = fr[j]
            ex, ey, s0 = half_extent(W, H, w, h, f["zoom"], 0)
            hw, hh = w / 2 / (s0 * f["zoom"]), h / 2 / (s0 * f["zoom"])
            r = math.radians(f["rot"])
            box = []
            for sx, sy in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)):
                x = f["cx"] * W + sx * math.cos(r) - sy * math.sin(r)
                y = f["cy"] * H + sx * math.sin(r) + sy * math.cos(r)
                box.append((int(x * k), int(y * k)))
            cv2.polylines(img, [np.array(box, np.int32)], True, c, 3, cv2.LINE_AA)
            row = picks.index(j)
            cv2.putText(img, f"{['START','MID','END'][row]} t={f['t']:.2f}s z={f['zoom']:.2f}", (12, 34 + 34 * row),
                        cv2.FONT_HERSHEY_SIMPLEX, .8, c, 2, cv2.LINE_AA)
        # rendered thumbnails strip
        thumbs = []
        for j in picks:
            f = fr[j]
            th = cv2.warpAffine(base, _affine(W, H, w, h, f), (w, h), flags=cv2.INTER_AREA, borderMode=cv2.BORDER_REFLECT101)
            tk = 300 / max(w, h)
            thumbs.append(cv2.resize(th, (int(w * tk), int(h * tk)), interpolation=cv2.INTER_AREA))
        th_h = max(t.shape[0] for t in thumbs)
        strip = np.full((th_h + 20, img.shape[1], 3), 20, np.uint8)
        x = 10
        for c, t in zip(cols, thumbs):
            if x + t.shape[1] > strip.shape[1]: break
            strip[10:10 + t.shape[0], x:x + t.shape[1]] = t
            cv2.rectangle(strip, (x, 10), (x + t.shape[1], 10 + t.shape[0]), c, 2)
            x += t.shape[1] + 14
        img = np.vstack([img, strip])
    else:
        S = 900
        img = np.full((S, S, 3), 24, np.uint8)
        xs = [p for f in fr for p in (f["pos"][0], f["target"][0])]
        ys = [p for f in fr for p in (f["pos"][1], f["target"][1])]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        span = max(max(xs) - min(xs), max(ys) - min(ys), 1.0) * 1.3
        def P(x, y): return (int(S / 2 + (x - cx) / span * S), int(S / 2 - (y - cy) / span * S))
        for i in range(0, 11):
            g = int(i * S / 10); cv2.line(img, (g, 0), (g, S), (40, 40, 40), 1); cv2.line(img, (0, g), (S, g), (40, 40, 40), 1)
        for a, b in zip(fr, fr[1:]):
            cv2.line(img, P(*a["pos"][:2]), P(*b["pos"][:2]), (255, 255, 255), 2, cv2.LINE_AA)
        for j, c in zip([0, len(fr) // 2, len(fr) - 1], [(80, 220, 80), (0, 200, 255), (60, 60, 255)]):
            f = fr[j]
            p0 = P(*f["pos"][:2]); t0 = P(*f["target"][:2])
            hf = math.atan(18 / f["lens"])
            dx, dy = t0[0] - p0[0], t0[1] - p0[1]
            base_a = math.atan2(dy, dx)
            L = 140
            for sgn in (-1, 1):
                q = (int(p0[0] + L * math.cos(base_a + sgn * hf)), int(p0[1] + L * math.sin(base_a + sgn * hf)))
                cv2.line(img, p0, q, c, 2, cv2.LINE_AA)
            cv2.circle(img, p0, 7, c, -1)
            cv2.putText(img, f"t={f['t']:.1f}s {f['lens']:.0f}mm z={f['pos'][2]:.1f}m", (p0[0] + 10, p0[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, .6, c, 2, cv2.LINE_AA)
        cv2.drawMarker(img, P(*fr[0]["target"][:2]), (255, 120, 255), cv2.MARKER_CROSS, 22, 3)
        cv2.putText(img, f"TOP VIEW  {tr['move']}  {len(fr)/tr['fps']:.1f}s", (16, 32), cv2.FONT_HERSHEY_SIMPLEX, .9, (230, 230, 230), 2, cv2.LINE_AA)
    imwrite_u(out, img)
    return out

# --------------------------------------------------------------------------- exporters
BLENDER_TMPL = r'''# generated by camera-director cam.py {ver} — run inside Blender:  blender -b scene.blend -P {name}
import bpy, json, math
from mathutils import Vector, Euler, Quaternion
TRACK = json.loads(r"""{track}""")
scn = bpy.context.scene
cam = scn.camera
if cam is None or "{cam}" != "":
    cam = bpy.data.objects.get("{cam}") if "{cam}" else None
    if cam is None:
        cd = bpy.data.cameras.new("CAM-director")
        cam = bpy.data.objects.new("CAM-director", cd)
        scn.collection.objects.link(cam)
    scn.camera = cam
for c in list(cam.constraints):           # baked keys own the camera
    cam.constraints.remove(c)
cd = cam.data
cd.sensor_fit = 'AUTO'; cd.sensor_width = 36.0
fstop = TRACK.get("fstop")
cd.dof.use_dof = bool(fstop)
if fstop: cd.dof.aperture_fstop = float(fstop)
scn.render.fps = int(round(TRACK["fps"]))
scn.render.resolution_x, scn.render.resolution_y = TRACK["size"]
scn.frame_start = 1; scn.frame_end = len(TRACK["frames"])
shutter = float(TRACK.get("shutter") or 0)
scn.render.use_motion_blur = shutter > 0
if shutter > 0: scn.render.motion_blur_shutter = shutter / 360.0
cam.rotation_mode = 'QUATERNION'
cam.animation_data_clear(); cd.animation_data_clear()
for fr in TRACK["frames"]:
    f = fr["f"] + 1
    pos, tgt = Vector(fr["pos"]), Vector(fr["target"])
    q = (tgt - pos).to_track_quat('-Z', 'Y')
    noise = Euler((math.radians(fr["pitch_n"]), math.radians(fr["yaw_n"]), math.radians(fr["roll"])), 'XYZ').to_quaternion()
    cam.location = pos
    cam.rotation_quaternion = q @ noise
    cd.lens = fr["lens"]
    cd.dof.focus_distance = fr["focus"]
    cam.keyframe_insert("location", frame=f); cam.keyframe_insert("rotation_quaternion", frame=f)
    cd.keyframe_insert("lens", frame=f); cd.dof.keyframe_insert("focus_distance", frame=f)
for ad in (cam.animation_data, cd.animation_data):
    if ad and ad.action:
        try:
            for fc in ad.action.fcurves:
                for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
        except AttributeError:   # Blender 5 layered actions
            for layer in ad.action.layers:
                for strip in layer.strips:
                    for cb in strip.channelbags:
                        for fc in cb.fcurves:
                            for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
print("camera-director: keyed", len(TRACK["frames"]), "frames on", cam.name)
# operator check: is the target hidden behind geometry (pillar, wall) on any frame?
dg = bpy.context.evaluated_depsgraph_get()
hidden = []
for fr in TRACK["frames"]:
    pos, tgt = Vector(fr["pos"]), Vector(fr["target"])
    d = (tgt - pos).length
    hit, loc, nor, idx, obj, mat = scn.ray_cast(dg, pos, (tgt - pos).normalized(), distance=d)
    if hit and (loc - pos).length < d * 0.6:
        hidden.append((fr["f"] + 1, obj.name if obj else "?"))
if hidden:
    print("camera-director: OCCLUDED", len(hidden), "frames, e.g.", hidden[:6], "-> move the path, raise the camera, or hide those objects for the camera")
else:
    print("camera-director: occlusion check OK (target visible every frame)")
'''

THREE_RUNTIME = r'''// generated by camera-director cam.py {ver}
// 3D: applyCam3(camera, frameIndex)  — three.js PerspectiveCamera (Y-up); converts from Blender Z-up.
// 2D: applyCam2(el, frameIndex)       — any DOM element sized to the SOURCE (src_size px), inside a stage of size[] px with overflow:hidden.
export const TRACK = {track};
export function frameAt(t) {{ return TRACK.frames[Math.max(0, Math.min(TRACK.frames.length - 1, Math.round(t * TRACK.fps)))]; }}
export function applyCam3(camera, i) {{
  const f = TRACK.frames[i], p = f.pos, g = f.target;
  camera.filmGauge = 36; camera.setFocalLength(f.lens);           // matches Blender sensor_fit AUTO on 36 mm
  camera.position.set(p[0], p[2], -p[1]);
  camera.up.set(0, 1, 0);
  camera.lookAt(g[0], g[2], -g[1]);
  camera.rotateX(f.pitch_n * Math.PI / 180); camera.rotateY(f.yaw_n * Math.PI / 180); camera.rotateZ(f.roll * Math.PI / 180);
  camera.updateProjectionMatrix();
}}
export function applyCam2(el, i) {{
  const f = TRACK.frames[i], [W, H] = TRACK.src_size, [w, h] = TRACK.size;
  const s = Math.max(w / W, h / H) * f.zoom;
  el.style.transformOrigin = "0 0";
  el.style.transform = `translate(${{w / 2}}px, ${{h / 2}}px) rotate(${{f.rot}}deg) scale(${{s}}) translate(${{-f.cx * W}}px, ${{-f.cy * H}}px)`;
}}
// GSAP / HyperFrames: drive with a proxy so the timeline stays seekable
// const o = {{ f: 0 }}; tl.to(o, {{ f: TRACK.frames.length - 1, duration: TRACK.frames.length / TRACK.fps, ease: "none", onUpdate: () => applyCam2(stage, Math.round(o.f)) }}, 0);
'''


def export_blender(spec, out, cam_name=""):
    tr = sample(spec)
    if tr["mode"] != "3d":
        raise SystemExit("blender export needs mode:3d")
    js = json.dumps(dict(fps=tr["fps"], size=tr["size"], fstop=tr.get("fstop"), shutter=tr.get("shutter"), frames=tr["frames"]))
    open(out, "w", encoding="utf-8").write(BLENDER_TMPL.format(ver=VERSION, name=os.path.basename(out), track=js, cam=cam_name))
    return out


def export_three(spec, out):
    tr = sample(spec)
    tr.pop("stats", None)
    open(out, "w", encoding="utf-8").write(THREE_RUNTIME.format(ver=VERSION, track=json.dumps(tr)))
    return out

# --------------------------------------------------------------------------- analyze any video
def analyze(path, max_w=480, step=1):
    import cv2
    import numpy as np
    cap = vcap(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    ok, prev = cap.read()
    if not ok:
        raise SystemExit("cannot read video")
    k = max_w / prev.shape[1]
    small = lambda im: cv2.cvtColor(cv2.resize(im, None, fx=k, fy=k, interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    pg = small(prev)
    Wn = pg.shape[1]
    rows = []
    i = 0
    while True:
        ok, im = cap.read()
        if not ok: break
        i += 1
        if i % step: continue
        g = small(im)
        pts = cv2.goodFeaturesToTrack(pg, 400, 0.01, 8)
        dx = dy = 0.0; sc = 1.0; ang = 0.0; good = 0
        if pts is not None and len(pts) >= 8:
            nxt, st, _ = cv2.calcOpticalFlowPyrLK(pg, g, pts, None, winSize=(21, 21), maxLevel=3)
            a, b = pts[st == 1], nxt[st == 1]
            good = len(a)
            if good >= 8:
                M, inl = cv2.estimateAffinePartial2D(a, b, method=cv2.RANSAC, ransacReprojThreshold=2.0)
                if M is not None:
                    sc = math.hypot(M[0, 0], M[1, 0]); ang = math.degrees(math.atan2(M[1, 0], M[0, 0]))
                    # translation of the frame centre
                    cxy = np.array([g.shape[1] / 2, g.shape[0] / 2])
                    moved = M[:, :2] @ cxy + M[:, 2]
                    dx, dy = (moved - cxy) / Wn             # in frame-widths
        rows.append(dict(t=round(i / fps, 3), dx=dx, dy=dy, scale=sc, rot=ang, feats=good))
        pg = g
    cap.release()
    if not rows:
        raise SystemExit("video too short")
    n = len(rows)
    dur = n / fps * step
    cum_dx = sum(r["dx"] for r in rows); cum_dy = sum(r["dy"] for r in rows)
    cum_z = math.exp(sum(math.log(max(1e-6, r["scale"])) for r in rows))
    cum_r = sum(r["rot"] for r in rows)
    # shake = RMS wobble of the accumulated camera path around a local cubic fit (1 s window).
    # eased dolly/pan curves are locally ~cubic -> ~0; handheld noise is not. units: % frame width.
    win = max(7, int(fps * 1.0 / step)) | 1
    hw_ = win // 2
    def resid(key):
        acc = np.cumsum([r[key] for r in rows])
        if n < win + 2: return 0.0
        tt = np.arange(-hw_, hw_ + 1, dtype=float)
        e = []
        for j in range(hw_, n - hw_):
            seg = acc[j - hw_:j + hw_ + 1]
            c = np.polyfit(tt, seg, 3)
            e.append(seg[hw_] - np.polyval(c, 0.0))
        return float(np.sqrt(np.mean(np.square(e))))
    shake = math.hypot(resid("dx"), resid("dy")) * 100
    labels = []
    # camera moves opposite to content: content dx<0 -> camera pans right
    if abs(cum_dx) > 0.08: labels.append("pan_right" if cum_dx < 0 else "pan_left")
    if abs(cum_dy) > 0.08: labels.append("tilt_down" if cum_dy < 0 else "tilt_up")
    if cum_z > 1.04: labels.append("push_in/zoom_in")
    if cum_z < 0.96: labels.append("pull_out/zoom_out")
    if abs(cum_r) > 2: labels.append("roll")
    peak = max(math.hypot(r["dx"], r["dy"]) for r in rows) * fps
    # steadiness (CameraBench levels). calibrated 2026-11-16 on renders with known shake:
    # smooth eased moves have shake/peak <= 0.52, handheld presets >= 0.93
    ratio = shake / max(peak, 1e-6)
    if shake < 0.005 or ratio < 0.7: steadiness = "no-shake"
    elif shake < 0.03: steadiness = "minimal"
    elif shake < 0.2: steadiness = "unsteady"
    else: steadiness = "very-unsteady"
    if steadiness != "no-shake": labels.append(f"handheld({steadiness})")
    if not labels: labels.append("static")
    # cut detector: frames where tracking collapses
    cuts = [r["t"] for r in rows if r["feats"] < 8]
    return dict(file=path, fps=fps, dur_s=round(dur, 2), moves=labels,
                content_travel_frame_widths=dict(x=round(cum_dx, 3), y=round(cum_dy, 3)),
                zoom_total=round(cum_z, 3), roll_total_deg=round(cum_r, 2), shake_index=round(shake, 3), steadiness=steadiness,
                peak_speed_frame_widths_s=round(peak, 3), tracking_lost_at=cuts[:20], per_frame=rows)


def verify(spec, video):
    tr = sample(spec)
    a = analyze(video)
    res = []
    fr = tr["frames"]
    if tr["mode"] == "2d":
        z_exp = fr[-1]["zoom"] / fr[0]["zoom"]
        res.append(("zoom", round(z_exp, 3), a["zoom_total"], abs(math.log(a["zoom_total"] / z_exp)) < 0.04))
        W, H = tr["src_size"]; w, h = tr["size"]
        s0 = max(w / W, h / H)
        # expected content travel in frame widths (approx, mid zoom)
        zm = fr[len(fr) // 2]["zoom"]
        ex = -(fr[-1]["cx"] - fr[0]["cx"]) * W * s0 * zm / w
        ey = -(fr[-1]["cy"] - fr[0]["cy"]) * H * s0 * zm / w
        res.append(("travel_x", round(ex, 3), a["content_travel_frame_widths"]["x"], abs(ex - a["content_travel_frame_widths"]["x"]) < max(0.05, abs(ex) * 0.25)))
        res.append(("travel_y", round(ey, 3), a["content_travel_frame_widths"]["y"], abs(ey - a["content_travel_frame_widths"]["y"]) < max(0.05, abs(ey) * 0.25)))
    exp_frames = len(fr)
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                            "stream=nb_read_frames,width,height", "-of", "json", video], capture_output=True, text=True)
        st = json.loads(r.stdout)["streams"][0]
        res.append(("frames", exp_frames, int(st["nb_read_frames"]), int(st["nb_read_frames"]) == exp_frames))
        res.append(("size", tr["size"], [st["width"], st["height"]], [st["width"], st["height"]] == list(tr["size"])))
    except Exception as e:
        res.append(("ffprobe", "ok", str(e), False))
    return dict(checks=[dict(name=n, expected=e, measured=m, ok=o) for n, e, m, o in res], analysis={k: v for k, v in a.items() if k != "per_frame"})

# --------------------------------------------------------------------------- doctor
def doctor():
    rows = []
    for mod in ("numpy", "cv2"):
        try:
            m = __import__(mod); rows.append((mod, True, getattr(m, "__version__", "?")))
        except Exception as e:
            rows.append((mod, False, str(e)))
    for exe in ("ffmpeg", "ffprobe", "blender"):
        p = shutil.which(exe)
        rows.append((exe, bool(p), p or "not on PATH" + (" (optional: only for 3D renders)" if exe == "blender" else "")))
    ok = all(r[1] for r in rows if r[0] != "blender")
    for n, o, v in rows:
        print(f"{'OK ' if o else 'MISSING'} {n:8s} {v}")
    print("doctor:", "ready" if ok else "missing required tools")
    return 0 if ok else 1

# --------------------------------------------------------------------------- CLI
def _load(p):
    with open(p, encoding="utf-8-sig") as fh:
        s = json.load(fh)
    base = os.path.dirname(os.path.abspath(p))
    def fix(x):
        if isinstance(x, dict) and x.get("source") and not os.path.isabs(x["source"]):
            x["source"] = os.path.join(base, x["source"])
    fix(s)
    for sh in s.get("shots", []): fix(sh)
    return s


def _print_issues(iss):
    if not iss:
        print("PASS  no issues"); return 0
    icon = dict(fail="FAIL", warn="WARN", info="INFO")
    for x in iss:
        print(f"{icon[x['level']]:4s}  [{x['code']}] {x['msg']}")
    return 1 if any(x["level"] == "fail" for x in iss) else 0


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("moves")
    sub.add_parser("doctor")
    for c in ("sample", "check", "board", "render", "blender", "three", "verify"):
        sp = sub.add_parser(c)
        sp.add_argument("spec")
        if c == "verify": sp.add_argument("video")
        sp.add_argument("--out")
        sp.add_argument("--json", action="store_true")
        if c == "render":
            sp.add_argument("--crf", type=int, default=16)
            sp.add_argument("--preview", action="store_true", help="half-res fast preview")
            sp.add_argument("--force", action="store_true", help="render even if check FAILs")
        if c == "blender":
            sp.add_argument("--camera", default="", help="existing camera object name to drive")
    sa = sub.add_parser("analyze"); sa.add_argument("video"); sa.add_argument("--json", action="store_true"); sa.add_argument("--out")
    a = ap.parse_args(argv)

    if a.cmd == "moves":
        print("2D (stills / footage / HTML stage)  — spec: {move, dur, subject:[x,y], strength, zoom, ease, shake}")
        for k, (d, e) in MOVES2D.items(): print(f"  {k:12s} {d}  [{e}]")
        print("\n3D (Blender / three.js)  — spec: {mode:'3d', move, dur, pos, target, lens, fstop, ease, shake, ...}")
        for k, (d, e) in MOVES3D.items(): print(f"  {k:12s} {d}  [{e}]")
        print("\nshake presets:", ", ".join(f"{k}(rot {v['rot']}deg, {v['freq']}Hz)" for k, v in SHAKE_PRESETS.items()))
        print("eases:", ", ".join(EASES), "or [x1,y1,x2,y2]")
        return 0
    if a.cmd == "doctor":
        return doctor()
    if a.cmd == "analyze":
        r = analyze(a.video)
        if a.out: json.dump(r, open(a.out, "w", encoding="utf-8"), indent=1)
        r.pop("per_frame")
        print(json.dumps(r, ensure_ascii=False, indent=1)); return 0
    spec = _load(a.spec)
    if a.cmd == "check":
        iss = check_sequence(spec) if "shots" in spec else check(spec)
        if a.json:
            print(json.dumps(iss, ensure_ascii=False, indent=1)); return 0
        if "shots" not in spec:
            tr = sample(spec); check(spec, tr)
            if tr.get("stats"): print("stats:", json.dumps(tr["stats"]))
        return _print_issues(iss)
    if a.cmd == "sample":
        tr = sample(spec)
        out = a.out or "track.json"
        json.dump(tr, open(out, "w", encoding="utf-8"), indent=0)
        print(f"wrote {out}  frames={len(tr['frames'])}"); return 0
    if a.cmd == "board":
        print("wrote", board(spec, a.out or "board.png")); return 0
    if a.cmd == "render":
        if spec.get("mode") == "3d":
            raise SystemExit("3D specs render in Blender: cam.py blender SPEC --out cam.py, then blender -b scene.blend -P cam.py -a")
        iss = check(spec)
        rc = _print_issues(iss)
        if rc and not a.force:
            raise SystemExit("check FAILED - fix the spec or pass --force")
        r = render_2d(spec, a.out or "camera.mp4", crf=a.crf, preview=a.preview)
        print(json.dumps(r)); return 0
    if a.cmd == "blender":
        print("wrote", export_blender(spec, a.out or "cam_anim.py", a.camera)); return 0
    if a.cmd == "three":
        print("wrote", export_three(spec, a.out or "track.js")); return 0
    if a.cmd == "verify":
        r = verify(spec, a.video)
        for c in r["checks"]:
            print(f"{'OK  ' if c['ok'] else 'FAIL'} {c['name']:9s} expected={c['expected']} measured={c['measured']}")
        print("analysis:", json.dumps(r["analysis"]["moves"]))
        return 0 if all(c["ok"] for c in r["checks"]) else 1


if __name__ == "__main__":
    sys.exit(main())
