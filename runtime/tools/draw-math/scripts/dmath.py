#!/usr/bin/env python3
"""dmath.py - draw-math: geometry, measurement and proportion calculator for drawing
and animating people and scenes (shadow puppets, 3D silhouette films, 2D figures).

Standard library only. Units are meters and degrees unless a subcommand says otherwise.
Every subcommand prints a short human answer; add --json for machine-readable output.
Points are comma lists: 2D "x,y" or 3D "x,y,z" (negative values like -1,2,0 are fine).

    python -I -X utf8 dmath.py <subcommand> --help

Subcommands: body, dist, angle, midpoint, lerp, ik2, cam, cam-size, frame-fit,
             angular, sun-shadow, puppet-shadow, gait, ease, arc, bezier
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys

VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Anthropometry table
# Source: Drillis, R. & Contini, R. (1966). Body Segment Parameters. Report 1166-03,
# Office of Vocational Rehabilitation, Dept. of Health, Education and Welfare;
# New York University School of Engineering and Science.
# As tabulated in: D. A. Winter, "Biomechanics and Motor Control of Human Movement",
# Fig. 4.1 ("segment lengths expressed as a fraction of body height H").
#
# status  "fig"     value printed in Winter Fig. 4.1 (and quoted in the task brief)
#         "fig?"    APPROXIMATE: recalled from the same figure; the number is
#                   self-consistent with the others but the label/value was not
#                   re-checked against the book here
#         "derived" difference of two figure values (inherits their error)
# kind    "height"  landmark height above the floor, standing upright, arms hanging
#         "length"  segment length (joint centre to joint centre / landmark to landmark)
#         "width"   breadth across the body
# Every value is a population average: real people differ by several percent.
# Known inconsistency: shoulder 0.818 - elbow 0.630 = 0.188, but upper arm is 0.186.
# ---------------------------------------------------------------------------
DRILLIS_CONTINI = (
    # key             label                                     xH     kind      status
    ("eye",           "eye height",                             0.936, "height", "fig"),
    ("chin",          "chin height",                            0.870, "height", "fig"),
    ("shoulder",      "shoulder (acromion) height",             0.818, "height", "fig"),
    ("chest",         "chest (nipple line) height",             0.720, "height", "fig?"),
    ("elbow",         "elbow height",                           0.630, "height", "fig?"),
    ("hip",           "hip (greater trochanter) height",        0.530, "height", "fig"),
    ("wrist",         "wrist height",                           0.485, "height", "fig?"),
    ("fingertip",     "fingertip height",                       0.377, "height", "fig?"),
    ("knee",          "knee height",                            0.285, "height", "fig"),
    ("ankle",         "ankle height",                           0.039, "height", "fig"),
    ("head_neck",     "head + neck (vertex to shoulder line)",  0.182, "length", "fig"),
    ("head",          "head (vertex to chin)",                  0.130, "length", "derived"),
    ("neck",          "neck (chin to shoulder line)",           0.052, "length", "derived"),
    ("trunk",         "trunk (shoulder line to hip)",           0.288, "length", "derived"),
    ("upper_arm",     "upper arm",                              0.186, "length", "fig"),
    ("forearm",       "forearm",                                0.146, "length", "fig"),
    ("hand",          "hand",                                   0.108, "length", "fig"),
    ("thigh",         "thigh (femur)",                          0.245, "length", "fig"),
    ("shank",         "shank (lower leg)",                      0.246, "length", "fig"),
    ("foot_length",   "foot length",                            0.152, "length", "fig"),
    ("foot_height",   "foot height (floor to ankle)",           0.039, "length", "fig"),
    ("shoulder_width", "shoulder width",                        0.259, "width",  "fig"),
    ("hip_width",     "hip width",                              0.191, "width",  "fig"),
    ("foot_width",    "foot width",                             0.055, "width",  "fig?"),
)
DC_SOURCE = ("Drillis & Contini (1966), Body Segment Parameters, Rep. 1166-03 (NYU); "
             "as tabulated in D. A. Winter, Biomechanics and Motor Control of Human Movement, Fig. 4.1")

# Artist canons (head = vertex to chin). Real adults ~7.5 heads; idealised/heroic 8 heads
# (e.g. A. Loomis, Figure Drawing for All It's Worth, 1943). D&C head 0.130H = 7.69 heads.
CANON_REAL = 7.5
CANON_HEROIC = 8.0

# Gait: step length ~0.413 x stature. RULE OF THUMB (pedometer calibration guides; the
# common version is 0.413 women / 0.415 men). Not a peer-reviewed regression; we use
# 0.413 for both because we cannot name a better source with confidence.
GAIT_STEP_FRACTION = {"m": 0.413, "f": 0.413}
COMFORT_SPEED = 1.3          # m/s, typical comfortable adult walking speed
CADENCE_TYPICAL = (100, 120)  # steps/min, typical adult free walking

THREE_NEAR, THREE_FAR = 0.1, 2000.0  # three.js PerspectiveCamera defaults


# ---------------------------------------------------------------------------
# Small vector helpers (tuples of floats, 2D or 3D)
# ---------------------------------------------------------------------------
def _dims(*pts):
    d = {len(p) for p in pts}
    if len(d) != 1:
        raise ValueError("all points must have the same dimension (all 2D or all 3D)")
    return d.pop()


def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _unit(a):
    n = math.hypot(*a)
    if n == 0:
        raise ValueError("zero-length vector")
    return tuple(x / n for x in a)


def _pad3(a):
    return tuple(a) + (0.0,) * (3 - len(a))


def _wrap_deg(a):
    """Wrap degrees to (-180, 180]."""
    a = (a + 180.0) % 360.0 - 180.0
    return 180.0 if a == -180.0 else a


# ---------------------------------------------------------------------------
# Core functions (pure; tests call these directly). All return dicts.
# ---------------------------------------------------------------------------
def body(height, sex="m", px_per_m=None, canon=CANON_REAL):
    """Segment lengths/heights from stature H using the Drillis & Contini fractions."""
    if height <= 0:
        raise ValueError("height must be > 0 (meters)")
    if sex not in ("m", "f"):
        raise ValueError("sex must be m or f")
    if canon <= 0:
        raise ValueError("canon (heads per body) must be > 0")
    if px_per_m is not None and px_per_m <= 0:
        raise ValueError("--px-per-m must be > 0")
    head_unit = height / canon
    rows, by_key = [], {}
    for key, label, frac, kind, status in DRILLIS_CONTINI:
        m = frac * height
        row = {"key": key, "label": label, "fraction": frac, "kind": kind, "status": status,
               "m": m, "heads": m / head_unit}
        if px_per_m:
            row["px"] = m * px_per_m
        rows.append(row)
        by_key[key] = m
    notes = ["Fractions are one population average (not split by sex in Winter's figure); "
             "--sex does not change them.",
             "status fig? = recalled from the figure, approximate; derived = difference of two heights.",
             "Upper arm 0.186H vs shoulder-elbow 0.818-0.630 = 0.188H: the figure is not perfectly consistent."]
    if sex == "f":
        notes.append("For women, shoulders are usually relatively narrower and hips relatively wider "
                     "than these averages; adjust widths by eye.")
    return {"H": height, "sex": sex, "canon_heads": canon, "head_unit_m": head_unit,
            "canons": {"real_7.5_heads_m": height / CANON_REAL,
                       "heroic_8_heads_m": height / CANON_HEROIC,
                       "drillis_contini_head_m": 0.130 * height,
                       "drillis_contini_heads_per_body": 1 / 0.130},
            "px_per_m": px_per_m, "rows": rows, "m": by_key, "source": DC_SOURCE, "notes": notes}


def dist(p, q):
    _dims(p, q)
    d = _sub(q, p)
    return {"p": tuple(p), "q": tuple(q), "delta": d, "distance": math.hypot(*d)}


def angle(a, b, c):
    """Angle ABC at vertex B in degrees (0..180); 2D also gives the signed CCW angle BA->BC."""
    dim = _dims(a, b, c)
    u, v = _sub(a, b), _sub(c, b)
    if math.hypot(*u) == 0 or math.hypot(*v) == 0:
        raise ValueError("A and C must both differ from B")
    u3, v3 = _pad3(u), _pad3(v)
    cr = _cross(u3, v3)
    dt = _dot(u3, v3)
    out = {"a": tuple(a), "b": tuple(b), "c": tuple(c),
           "angle_deg": math.degrees(math.atan2(math.hypot(*cr), dt))}
    if dim == 2:
        out["signed_deg"] = math.degrees(math.atan2(cr[2], dt))
    return out


def midpoint(p, q):
    _dims(p, q)
    return {"p": tuple(p), "q": tuple(q), "midpoint": tuple((x + y) / 2 for x, y in zip(p, q))}


def lerp(p, q, t):
    _dims(p, q)
    return {"p": tuple(p), "q": tuple(q), "t": t,
            "point": tuple(x * (1 - t) + y * t for x, y in zip(p, q))}


def fk2(l1, l2, th1, th2, root=(0.0, 0.0)):
    """Planar two-bone forward kinematics. Angles in radians, measured from the
    down-vector (0,-1), counter-clockwise positive. th2 is the middle-joint flexion
    relative to bone 1. Returns (middle_joint, end)."""
    mx = root[0] + l1 * math.sin(th1)
    my = root[1] - l1 * math.cos(th1)
    a = th1 + th2
    return (mx, my), (mx + l2 * math.sin(a), my - l2 * math.cos(a))


def ik2(l1, l2, x, y, bend=1, root=(0.0, 0.0)):
    """Planar two-bone IK (hip-knee-ankle, shoulder-elbow-wrist). Target (x,y) in the
    same frame as root, Y up. bend=+1 flexes the middle joint CCW, -1 CW."""
    if l1 <= 0 or l2 <= 0:
        raise ValueError("bone lengths must be > 0")
    if bend not in (1, -1):
        raise ValueError("bend must be +1 or -1")
    tx, ty = x - root[0], y - root[1]
    d = math.hypot(tx, ty)
    rmax, rmin = l1 + l2, abs(l1 - l2)
    eps = 1e-12 * rmax
    phi = math.atan2(tx, -ty) if d > 0 else 0.0  # target direction, from down, CCW
    if d > rmax + eps:
        reachable, why = False, "too far: arm fully straightened toward the target"
        th1, th2 = phi, 0.0
    elif d < rmin - eps:
        reachable, why = False, "too close: chain fully folded toward the target"
        th2 = bend * math.pi
        th1 = phi if l1 >= l2 else phi + math.pi
    else:
        reachable, why = True, "reachable"
        c2 = max(-1.0, min(1.0, (d * d - l1 * l1 - l2 * l2) / (2 * l1 * l2)))
        th2 = bend * math.acos(c2)
        th1 = phi - math.atan2(l2 * math.sin(th2), l1 + l2 * math.cos(th2))
    mid, end = fk2(l1, l2, th1, th2, root)
    fk_err = math.hypot(end[0] - x, end[1] - y)
    root_deg, mid_deg = _wrap_deg(math.degrees(th1)), math.degrees(th2)
    return {"L1": l1, "L2": l2, "root": tuple(root), "target": (x, y), "bend": bend,
            "distance": d, "reach_max": rmax, "reach_min": rmin, "reachable": reachable,
            "status": why, "reach_margin": rmax - d, "inner_margin": d - rmin,
            "root_deg": root_deg, "mid_deg": mid_deg,
            "bone2_deg": _wrap_deg(root_deg + mid_deg), "interior_mid_deg": 180.0 - abs(mid_deg),
            "mid_joint": mid, "end": end, "clamped_end": None if reachable else end,
            "fk_error": fk_err, "fk_ok": (fk_err < 1e-9) if reachable else None,
            "convention": "angles from straight down (0,-1), CCW positive (toward +X); "
                          "mid_deg = flexion of bone 2 relative to bone 1 (0 = straight)"}


def parse_res(text):
    m = re.fullmatch(r"\s*(\d+)\s*[xX*,:]\s*(\d+)\s*", str(text))
    if not m or int(m.group(1)) <= 0 or int(m.group(2)) <= 0:
        raise ValueError(f"bad resolution {text!r}: use WxH like 1080x1920")
    return int(m.group(1)), int(m.group(2))


def fov_pair(vfov, w, h):
    """Vertical FOV (three.js PerspectiveCamera.fov) -> (vfov, hfov) in degrees."""
    if not 0 < vfov < 180:
        raise ValueError("fov must be between 0 and 180 degrees (vertical, like three.js)")
    t = math.tan(math.radians(vfov) / 2)
    return vfov, math.degrees(2 * math.atan(t * w / h))


def _look_at(pos, target, up=(0.0, 1.0, 0.0)):
    """Camera basis like three.js Matrix4.lookAt; camera looks down its -z axis."""
    z = _sub(pos, target)
    if math.hypot(*z) == 0:
        raise ValueError("camera pos and target are the same point")
    z = _unit(z)
    x = _cross(up, z)
    nudged = False
    if _dot(x, x) < 1e-24:  # looking straight up/down: nudge z as three.js does
        z = (z[0] + 1e-4, z[1], z[2]) if abs(up[2]) == 1 else (z[0], z[1], z[2] + 1e-4)
        z = _unit(z)
        x = _cross(up, z)
        nudged = True
    x = _unit(x)
    return x, _cross(z, x), z, nudged


def cam_project(fov, res, pos, target, points, near=THREE_NEAR, far=THREE_FAR):
    """Project 3D points with a three.js-style pinhole camera. Pixels: origin top-left."""
    w, h = parse_res(res) if isinstance(res, str) else res
    _dims(pos, target, *points) if points else _dims(pos, target)
    if len(pos) != 3:
        raise ValueError("cam needs 3D points x,y,z")
    vfov, hfov = fov_pair(fov, w, h)
    t = math.tan(math.radians(vfov) / 2)
    aspect = w / h
    bx, by, bz, nudged = _look_at(pos, target)
    out = []
    for p in points:
        v = _sub(p, pos)
        xc, yc, depth = _dot(v, bx), _dot(v, by), -_dot(v, bz)
        rec = {"point": tuple(p), "depth": depth, "distance": math.hypot(*v)}
        if depth <= 0:
            rec.update(px=None, py=None, ndc=None, in_frame=False, note="behind the camera")
        else:
            nx, ny = xc / (depth * t * aspect), yc / (depth * t)
            px, py = (nx + 1) / 2 * w, (1 - ny) / 2 * h
            inside_xy = 0 <= px <= w and 0 <= py <= h
            inside = inside_xy and near <= depth <= far
            note = ("in frame" if inside else "nearer than the near plane" if depth < near
                    else "beyond the far plane" if depth > far else "outside the frame")
            rec.update(px=px, py=py, ndc=(nx, ny), in_frame=inside, note=note)
        out.append(rec)
    return {"fov_v_deg": vfov, "fov_h_deg": hfov, "res": (w, h), "aspect": aspect,
            "pos": tuple(pos), "target": tuple(target), "near": near, "far": far,
            "focal_px": h / (2 * t), "up_nudged": nudged, "points": out}


def cam_size(fov, res, dist_, size):
    """On-screen height of an object of height `size` whose plane is `dist_` in front of the camera."""
    w, h = parse_res(res) if isinstance(res, str) else res
    if dist_ <= 0 or size <= 0:
        raise ValueError("dist and size must be > 0")
    vfov, hfov = fov_pair(fov, w, h)
    vis_h = 2 * dist_ * math.tan(math.radians(vfov) / 2)
    return {"fov_v_deg": vfov, "fov_h_deg": hfov, "res": (w, h), "dist": dist_, "size": size,
            "px_height": size / vis_h * h, "frame_fraction": size / vis_h,
            "visible_height": vis_h, "visible_width": vis_h * w / h,
            "focal_px": h / (2 * math.tan(math.radians(vfov) / 2))}


def frame_fit(fov, res, height, fill=0.8, width=None):
    """Camera distance so an object of `height` fills `fill` of the frame height
    (and, if `width` is given, also fits `fill` of the frame width)."""
    w, h = parse_res(res) if isinstance(res, str) else res
    if height <= 0 or fill <= 0 or (width is not None and width <= 0):
        raise ValueError("height, fill and width must be > 0")
    vfov, hfov = fov_pair(fov, w, h)
    tv = math.tan(math.radians(vfov) / 2)
    d_h = height / (2 * fill * tv)
    d, limit = d_h, "height"
    d_w = None
    if width is not None:
        d_w = width / (2 * fill * tv * w / h)
        if d_w > d_h:
            d, limit = d_w, "width"
    cs = cam_size(vfov, (w, h), d, height)
    return {"fov_v_deg": vfov, "fov_h_deg": hfov, "res": (w, h), "height": height, "width": width,
            "fill": fill, "distance": d, "distance_for_height": d_h, "distance_for_width": d_w,
            "limited_by": limit, "px_height": cs["px_height"],
            "visible_height": cs["visible_height"], "visible_width": cs["visible_width"],
            "level_camera": {"pos": (0.0, height / 2, d), "target": (0.0, height / 2, 0.0)}}


def angular_size(size, dist_):
    if size <= 0 or dist_ <= 0:
        raise ValueError("size and dist must be > 0")
    rad = 2 * math.atan(size / (2 * dist_))
    return {"size": size, "dist": dist_, "deg": math.degrees(rad), "arcmin": math.degrees(rad) * 60,
            "rad": rad, "small_angle_deg": math.degrees(size / dist_)}


def angular_solve(deg, size=None, dist_=None):
    """Inverse: given the angle and one of size/dist, return the other."""
    if not 0 < deg < 180:
        raise ValueError("deg must be between 0 and 180")
    if (size is None) == (dist_ is None):
        raise ValueError("give exactly one of --size or --dist with --deg")
    half = math.tan(math.radians(deg) / 2)
    if dist_ is not None:
        if dist_ <= 0:
            raise ValueError("dist must be > 0")
        size = 2 * dist_ * half
    else:
        if size <= 0:
            raise ValueError("size must be > 0")
        dist_ = size / (2 * half)
    return {"deg": deg, "size": size, "dist": dist_}


def sun_shadow(height, elev, az=None):
    """Shadow of a vertical pole of `height` on flat ground. az: compass degrees
    (0 = north, 90 = east) of the sun; the shadow points the opposite way."""
    if height <= 0:
        raise ValueError("height must be > 0")
    if elev <= 0:
        raise ValueError("sun elevation must be > 0 deg: at or below the horizon there is no finite shadow")
    if elev > 90:
        raise ValueError("sun elevation must be <= 90 deg")
    e = math.radians(elev)
    length = 0.0 if elev == 90 else height / math.tan(e)
    out = {"height": height, "elev_deg": elev, "az_deg": az, "length": length,
           "ratio": length / height, "shadow_az_deg": None, "dir_en": None, "tip_en": None,
           "sun_dir_enu": None}
    if az is not None:
        saz = (az + 180.0) % 360.0
        de, dn = math.sin(math.radians(saz)), math.cos(math.radians(saz))
        a = math.radians(az)
        out.update(shadow_az_deg=saz, dir_en=(de, dn), tip_en=(length * de, length * dn),
                   sun_dir_enu=(math.cos(e) * math.sin(a), math.cos(e) * math.cos(a), math.sin(e)))
    return out


PUPPET_RULE = ("Moving the puppet away from the screen (toward the lamp) makes its shadow "
               "bigger (M = L/(L-d)) and blurrier (penumbra = w*d/(L-d)); pressed to the screen "
               "it is true size and sharp.")


def puppet_shadow(light_dist, puppet_dist, size, light_size=0.0, want=None):
    """Shadow-theatre optics: lamp L from the screen, puppet d from the screen (0 <= d < L)."""
    L, d, s, w = light_dist, puppet_dist, size, light_size
    if L <= 0 or s <= 0:
        raise ValueError("light-dist and size must be > 0")
    if not 0 <= d < L:
        raise ValueError("puppet-dist must satisfy 0 <= d < light-dist (puppet between lamp and screen)")
    if w < 0:
        raise ValueError("light-size must be >= 0")
    mag = L / (L - d)
    shadow = s * mag
    pen = w * d / (L - d)
    out = {"light_dist": L, "puppet_dist": d, "size": s, "light_size": w,
           "magnification": mag, "shadow_size": shadow, "penumbra": pen,
           "outer_size": shadow + pen, "umbra_size": max(0.0, shadow - pen),
           "rule": PUPPET_RULE, "want": want, "puppet_dist_for_want": None}
    if want is not None:
        if want < s:
            raise ValueError("--want must be >= size: a point lamp never shrinks the shadow below the puppet")
        out["puppet_dist_for_want"] = L * (1 - s / want)
    return out


def gait(height, speed=None, sex="m", fps=None):
    if height <= 0:
        raise ValueError("height must be > 0")
    if sex not in GAIT_STEP_FRACTION:
        raise ValueError("sex must be m or f")
    v = COMFORT_SPEED if speed is None else speed
    if v <= 0:
        raise ValueError("speed must be > 0")
    if fps is not None and fps <= 0:
        raise ValueError("fps must be > 0")
    k = GAIT_STEP_FRACTION[sex]
    step = k * height
    cadence = v * 60 / step
    step_t = step / v
    out = {"height": height, "sex": sex, "speed": v, "speed_assumed": speed is None,
           "step_fraction": k, "step_length": step, "stride_length": 2 * step,
           "cadence_spm": cadence, "step_period_s": step_t, "stride_period_s": 2 * step_t,
           "typical_cadence_spm": CADENCE_TYPICAL,
           "cadence_typical": CADENCE_TYPICAL[0] <= cadence <= CADENCE_TYPICAL[1],
           "fps": fps, "frames_per_step": None, "frames_per_stride": None,
           "approximation": "step ~0.413 x height is a rule of thumb (pedometer calibration guides); "
                            "real step length grows with speed, so cadence here is approximate",
           "phases": "normal walking: stance ~60% / swing ~40% of the stride, double support ~10% twice"}
    if fps:
        out["frames_per_step"] = fps * step_t
        out["frames_per_stride"] = 2 * fps * step_t
    return out


EASES = {
    "linear": lambda t: t,
    "in": lambda t: t ** 3,                                   # cubic ease-in
    "out": lambda t: 1 - (1 - t) ** 3,                        # cubic ease-out
    "inout": lambda t: 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2,  # cubic in-out
    "smoothstep": lambda t: t * t * (3 - 2 * t),              # 3t^2 - 2t^3
    "minjerk": lambda t: t ** 3 * (10 - 15 * t + 6 * t * t),  # 10t^3 - 15t^4 + 6t^5
}


def ease_value(curve, t):
    if curve not in EASES:
        raise ValueError(f"curve must be one of {', '.join(EASES)}")
    return EASES[curve](t)


def ease(dur, fps, a, b, curve="inout"):
    if curve not in EASES:
        raise ValueError(f"curve must be one of {', '.join(EASES)}")
    if dur <= 0 or fps <= 0:
        raise ValueError("dur and fps must be > 0")
    exact = dur * fps
    n = int(round(exact))
    if n < 1:
        raise ValueError("dur*fps must be at least 1 frame")
    frames, prev = [], None
    for i in range(n + 1):
        t = i / n
        s = EASES[curve](t)
        val = a * (1 - s) + b * s
        frames.append({"frame": i, "time": i * dur / n, "t": t, "s": s, "value": val,
                       "delta": None if prev is None else val - prev})
        prev = val
    deltas = [f["delta"] for f in frames[1:]]
    big = max(range(len(deltas)), key=lambda k: abs(deltas[k]))
    return {"curve": curve, "dur": dur, "fps": fps, "from": a, "to": b, "frames_count": n,
            "rounded": abs(exact - n) > 1e-9, "frames": frames,
            "max_delta": deltas[big], "max_delta_frame": big + 1}


def arc(radius, deg):
    if radius <= 0:
        raise ValueError("radius must be > 0")
    if not 0 < deg <= 360:
        raise ValueError("deg must be in (0, 360]")
    th = math.radians(deg)
    return {"radius": radius, "deg": deg, "arc_length": radius * th,
            "chord": 2 * radius * math.sin(th / 2), "sagitta": radius * (1 - math.cos(th / 2))}


def bezier_point(p0, p1, p2, p3, t):
    mt = 1 - t
    a, b, c, d = mt ** 3, 3 * mt * mt * t, 3 * mt * t * t, t ** 3
    return tuple(a * w + b * x + c * y + d * z for w, x, y, z in zip(p0, p1, p2, p3))


def _poly_len(p0, p1, p2, p3, n):
    total, prev = 0.0, p0
    for i in range(1, n + 1):
        cur = bezier_point(p0, p1, p2, p3, i / n)
        total += math.hypot(*_sub(cur, prev))
        prev = cur
    return total


def bezier(p0, p1, p2, p3, n=1000, at=0.5):
    _dims(p0, p1, p2, p3)
    if n < 2:
        raise ValueError("n must be >= 2")
    length = _poly_len(p0, p1, p2, p3, n)
    coarse = _poly_len(p0, p1, p2, p3, n // 2)
    return {"p": (tuple(p0), tuple(p1), tuple(p2), tuple(p3)), "n": n, "length": length,
            "error_estimate": abs(length - coarse) / 3,
            "chord": math.hypot(*_sub(p3, p0)),
            "control_polygon": sum(math.hypot(*_sub(b, a)) for a, b in ((p0, p1), (p1, p2), (p2, p3))),
            "at": at, "point_at": bezier_point(p0, p1, p2, p3, at),
            "point_at_half": bezier_point(p0, p1, p2, p3, 0.5)}


# ---------------------------------------------------------------------------
# Formatting helpers for the human output (ASCII only, safe on any console)
# ---------------------------------------------------------------------------
def _g(x, nd=6):
    if x is None:
        return "-"
    if abs(x) < 1e-12:
        x = 0.0
    return f"{x:.{nd}g}"


def _pt(p, nd=6):
    return "(" + ", ".join(_g(v, nd) for v in p) + ")"


# ---------------------------------------------------------------------------
# CLI handlers: each returns (json_dict, text)
# ---------------------------------------------------------------------------
def cmd_body(a):
    r = body(a.H, a.sex, a.px_per_m, a.canon)
    if a.only:
        keys = [k.strip() for k in a.only.split(",") if k.strip()]
        bad = [k for k in keys if k not in r["m"]]
        if bad:
            raise ValueError(f"unknown key(s) {', '.join(bad)}; valid: {', '.join(r['m'])}")
        r["rows"] = [row for row in r["rows"] if row["key"] in keys]
        r["m"] = {k: r["m"][k] for k in r["m"] if k in keys}
    H = r["H"]
    c = r["canons"]
    lines = [f"Body for H = {H:.3f} m (sex {r['sex']}): Drillis & Contini 1966 fractions, Winter Fig. 4.1",
             f"head unit = H/{a.canon:g} = {r['head_unit_m']:.4f} m | real 7.5 heads = {c['real_7.5_heads_m']:.4f} m"
             f" | heroic 8 heads = {c['heroic_8_heads_m']:.4f} m | D&C head 0.130H = "
             f"{c['drillis_contini_head_m']:.4f} m (= 7.69 heads)"]
    head = f"  {'':40s}{'xH':>7s}{'m':>9s}"
    if a.px_per_m:
        head += f"{'px':>9s}"
    if a.heads:
        head += f"{'heads':>8s}"
    titles = {"height": "HEIGHTS above floor", "length": "LENGTHS", "width": "WIDTHS"}
    mark = {"fig": " ", "fig?": "*", "derived": "d"}
    for kind in ("height", "length", "width"):
        if not any(row["kind"] == kind for row in r["rows"]):
            continue
        lines.append(titles[kind] + head[len(titles[kind]):])
        for row in r["rows"]:
            if row["kind"] != kind:
                continue
            s = f"  {mark[row['status']]} {row['label']:38s}{row['fraction']:7.3f}{row['m']:9.4f}"
            if a.px_per_m:
                s += f"{row['px']:9.1f}"
            if a.heads:
                s += f"{row['heads']:8.2f}"
            lines.append(s)
    lines.append("* recalled from the figure, approximate   d derived (difference of two heights)")
    lines.append("Population averages: real people vary by several %. --sex does not change the fractions.")
    if r["sex"] == "f":
        lines.append(r["notes"][-1])
    return r, "\n".join(lines)


def cmd_dist(a):
    r = dist(a.P, a.Q)
    return r, f"distance = {_g(r['distance'])} m   delta = {_pt(r['delta'])}"


def cmd_angle(a):
    r = angle(a.A, a.B, a.C)
    s = f"angle ABC at B = {_g(r['angle_deg'])} deg"
    if "signed_deg" in r:
        s += f"   (2D signed BA->BC, CCW positive: {_g(r['signed_deg'])} deg)"
    return r, s


def cmd_midpoint(a):
    r = midpoint(a.P, a.Q)
    return r, f"midpoint = {_pt(r['midpoint'])}"


def cmd_lerp(a):
    r = lerp(a.P, a.Q, a.t)
    return r, f"lerp(t={_g(a.t)}) = {_pt(r['point'])}"


def cmd_ik2(a):
    r = ik2(a.L1, a.L2, a.X, a.Y, a.bend, a.root)
    if r["reachable"]:
        verdict = f"REACHABLE, margin {_g(r['reach_margin'])} to full extension"
    elif r["reach_margin"] < 0:
        verdict = f"UNREACHABLE, {_g(-r['reach_margin'])} too far [{r['status']}]"
    else:
        verdict = f"UNREACHABLE, {_g(-r['inner_margin'])} too close [{r['status']}]"
    lines = [f"2-bone IK  L1={_g(r['L1'])} L2={_g(r['L2'])}  root={_pt(r['root'])}  "
             f"target=({_g(a.X)}, {_g(a.Y)})  bend={r['bend']:+d}",
             f"distance {_g(r['distance'])} (reach {_g(r['reach_min'])}..{_g(r['reach_max'])}) -> {verdict}",
             f"root angle   = {r['root_deg']:.4f} deg from straight down (CCW +, toward +X)",
             f"middle joint = {r['mid_deg']:.4f} deg flexion (0 = straight; interior angle "
             f"{r['interior_mid_deg']:.4f} deg); bone 2 at {r['bone2_deg']:.4f} deg from down",
             f"middle joint at {_pt(r['mid_joint'])}; end at {_pt(r['end'])}"]
    if r["reachable"]:
        lines.append(f"FK check: |FK - target| = {r['fk_error']:.1e}  {'OK' if r['fk_ok'] else 'FAIL'}")
    else:
        lines.append(f"clamped end point = {_pt(r['clamped_end'])} (gap {_g(r['fk_error'])})")
    return r, "\n".join(lines)


def cmd_cam(a):
    pts = a.point or [a.target]
    r = cam_project(a.fov, a.res, a.pos, a.target, pts, a.near, a.far)
    w, h = r["res"]
    lines = [f"camera fov {_g(r['fov_v_deg'])} deg vertical / {r['fov_h_deg']:.4f} deg horizontal, "
             f"{w}x{h} (aspect {r['aspect']:.4f}), focal {r['focal_px']:.2f} px",
             f"pos {_pt(r['pos'])} -> target {_pt(r['target'])}; pixels origin top-left"
             + ("; up nudged (looking straight up/down)" if r["up_nudged"] else "")]
    for p in r["points"]:
        if p["px"] is None:
            lines.append(f"  {_pt(p['point'])}: depth {p['depth']:.4f} m  {p['note'].upper()}")
        else:
            lines.append(f"  {_pt(p['point'])}: px ({p['px']:.2f}, {p['py']:.2f})  depth {p['depth']:.4f} m  "
                         f"{'IN' if p['in_frame'] else 'OUT'} ({p['note']})")
    return r, "\n".join(lines)


def cmd_cam_size(a):
    r = cam_size(a.fov, a.res, a.dist, a.size)
    w, h = r["res"]
    return r, (f"{_g(a.size)} m at {_g(a.dist)} m -> {r['px_height']:.1f} px tall "
               f"({r['frame_fraction'] * 100:.1f}% of {h} px)\n"
               f"fov {_g(r['fov_v_deg'])} deg vertical / {r['fov_h_deg']:.4f} deg horizontal at {w}x{h}; "
               f"visible area at that depth {r['visible_width']:.3f} x {r['visible_height']:.3f} m")


def cmd_frame_fit(a):
    r = frame_fit(a.fov, a.res, a.height, a.fill, a.width)
    w, h = r["res"]
    lc = r["level_camera"]
    return r, (f"distance = {r['distance']:.4f} m so {_g(a.height)} m fills {a.fill * 100:g}% of the frame "
               f"height ({r['px_height']:.1f} of {h} px); limited by {r['limited_by']}\n"
               f"fov {_g(r['fov_v_deg'])} deg vertical / {r['fov_h_deg']:.4f} deg horizontal at {w}x{h}; "
               f"visible {r['visible_width']:.3f} x {r['visible_height']:.3f} m\n"
               f"level camera for an object standing on y=0: --pos 0,{lc['pos'][1]:.4g},{lc['pos'][2]:.4g} "
               f"--target 0,{lc['target'][1]:.4g},0")


def cmd_angular(a):
    if a.deg is None:
        if a.size is None or a.dist is None:
            raise ValueError("give --size and --dist, or --deg with one of them")
        r = angular_size(a.size, a.dist)
        r["mode"] = "angle"
        return r, (f"{_g(a.size)} at {_g(a.dist)} subtends {r['deg']:.4f} deg "
                   f"({r['arcmin']:.2f} arcmin; small-angle approx {r['small_angle_deg']:.4f} deg)")
    r = angular_solve(a.deg, a.size, a.dist)
    if a.dist is not None:
        r["mode"] = "size"
        return r, f"{_g(a.deg)} deg at distance {_g(a.dist)} spans size {_g(r['size'])}"
    r["mode"] = "dist"
    return r, f"size {_g(a.size)} subtends {_g(a.deg)} deg at distance {_g(r['dist'])}"


def cmd_sun_shadow(a):
    r = sun_shadow(a.height, a.elev, a.az)
    s = f"shadow length = {r['length']:.4f} m ({r['ratio']:.4f} x height) at sun elevation {_g(a.elev)} deg"
    if a.az is None:
        s += "\ndirection: opposite the sun's azimuth (give --az for a bearing)"
    else:
        s += (f"\nshadow points to azimuth {r['shadow_az_deg']:.2f} deg (compass, 0=N, 90=E); "
              f"unit (E,N) = {_pt(r['dir_en'], 4)}, tip at (E,N) = {_pt(r['tip_en'], 5)}"
              f"\nsun direction (E,N,Up) = {_pt(r['sun_dir_enu'], 5)}  [three.js: x=E, y=Up, z=-N]")
    return r, s


def cmd_puppet_shadow(a):
    r = puppet_shadow(a.light_dist, a.puppet_dist, a.size, a.light_size, a.want)
    s = (f"magnification = {r['magnification']:.4f}  shadow size = {r['shadow_size']:.4f} m"
         f"  penumbra (blur) = {r['penumbra']:.4f} m per edge")
    if a.light_size:
        s += f"\nfull extent {r['outer_size']:.4f} m, dark core (umbra) {r['umbra_size']:.4f} m"
    if a.want is not None:
        s += f"\nfor a {_g(a.want)} m shadow put the puppet {r['puppet_dist_for_want']:.4f} m from the screen"
    return r, s + "\n" + PUPPET_RULE


def cmd_gait(a):
    r = gait(a.height, a.speed, a.sex, a.fps)
    s = (f"step {r['step_length']:.3f} m, stride {r['stride_length']:.3f} m (0.413 x H, rule of thumb)\n"
         f"at {_g(r['speed'])} m/s{' (assumed comfortable speed)' if r['speed_assumed'] else ''}: "
         f"cadence {r['cadence_spm']:.1f} steps/min, step {r['step_period_s']:.3f} s, "
         f"stride (gait cycle) {r['stride_period_s']:.3f} s")
    if a.fps:
        s += f"\nat {_g(a.fps)} fps: {r['frames_per_step']:.2f} frames/step, {r['frames_per_stride']:.2f} frames/stride"
    s += (f"\ntypical adult cadence 100-120 steps/min"
          f"{'' if r['cadence_typical'] else ' (this result is outside it)'}; approximations only")
    return r, s


def cmd_ease(a):
    r = ease(a.dur, a.fps, a.a, a.b, a.curve)
    lines = [f"ease {r['curve']}  {_g(a.a)} -> {_g(a.b)}  over {_g(a.dur)} s at {_g(a.fps)} fps = "
             f"{r['frames_count']} frames ({r['frames_count'] + 1} keys incl. frame 0)"
             + ("  [dur*fps rounded]" if r["rounded"] else ""),
             f"{'frame':>5s} {'time':>7s} {'s':>7s} {'value':>11s} {'delta':>10s}"]
    for f in r["frames"]:
        lines.append(f"{f['frame']:5d} {f['time']:7.3f} {f['s']:7.4f} {f['value']:11.5f} "
                     f"{'' if f['delta'] is None else format(f['delta'], '10.5f')}".rstrip())
    lines.append(f"largest step {r['max_delta']:.5f} into frame {r['max_delta_frame']} "
                 "(spacing chart: small steps = slow, big = fast)")
    return r, "\n".join(lines)


def cmd_arc(a):
    r = arc(a.radius, a.deg)
    return r, (f"arc length = {r['arc_length']:.6g}   chord = {r['chord']:.6g}   "
               f"sagitta (arc height) = {r['sagitta']:.6g}")


def cmd_bezier(a):
    r = bezier(a.P0, a.P1, a.P2, a.P3, a.n, a.at)
    s = (f"length = {r['length']:.6f} (n={r['n']} samples, est. error {r['error_estimate']:.1e}); "
         f"chord {r['chord']:.6g}, control polygon {r['control_polygon']:.6g}\n"
         f"point at t=0.5 = {_pt(r['point_at_half'])}")
    if a.at != 0.5:
        s += f"\npoint at t={_g(a.at)} = {_pt(r['point_at'])}"
    return r, s


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
class _Parser(argparse.ArgumentParser):
    """ArgumentParser that reads '-1,2,0' (negative coordinate list) as a value, not an option."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._negative_number_matcher = re.compile(r"^-\.?\d")


def point(text):
    """argparse type: '1,2' or '1,2,3' -> tuple of floats."""
    parts = str(text).replace(chr(0x2212), "-").replace(";", ",").split(",")  # accept U+2212 minus
    try:
        vals = tuple(float(p) for p in parts)
    except ValueError:
        raise argparse.ArgumentTypeError(f"bad point {text!r}: use x,y or x,y,z (e.g. 0,1.5,-2)")
    if len(vals) not in (2, 3) or not all(math.isfinite(v) for v in vals):
        raise argparse.ArgumentTypeError(f"bad point {text!r}: need 2 or 3 finite numbers")
    return vals


def point3(text):
    p = point(text)
    if len(p) != 3:
        raise argparse.ArgumentTypeError(f"{text!r}: need x,y,z")
    return p


def point2(text):
    p = point(text)
    if len(p) != 2:
        raise argparse.ArgumentTypeError(f"{text!r}: need x,y")
    return p


def res_type(text):
    try:
        return parse_res(text)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e))


def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="print machine-readable JSON")
    p = _Parser(prog="dmath.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=f"draw-math {VERSION}")
    sub = p.add_subparsers(dest="cmd", required=True, metavar="<subcommand>")
    RF = argparse.RawDescriptionHelpFormatter

    def add(name, short, desc, func):
        sp = sub.add_parser(name, parents=[common], help=short, description=desc, formatter_class=RF)
        sp.set_defaults(func=func)
        return sp

    def cam_common(sp):
        sp.add_argument("--fov", type=float, default=50.0,
                        help="VERTICAL field of view in degrees, like three.js (default 50)")
        sp.add_argument("--res", type=res_type, default=(1080, 1920),
                        help="frame size WxH in pixels (default 1080x1920, 9:16)")

    s = add("body", "human segment lengths from stature",
            "Segment lengths, landmark heights and widths from stature H (meters), using the\n"
            "Drillis & Contini (1966) fractions of H as tabulated in Winter, Fig. 4.1.\n"
            "Head unit = H/canon (canon 7.5 = real adult, 8 = heroic).\n"
            "example: dmath.py body 1.78 --px-per-m 400 --heads", cmd_body)
    s.add_argument("H", type=float, help="stature in meters")
    s.add_argument("--sex", choices=["m", "f"], default="m", help="label only; fractions are unisex")
    s.add_argument("--px-per-m", type=float, help="also print pixels at this scale")
    s.add_argument("--heads", action="store_true", help="also print values in head units")
    s.add_argument("--canon", type=float, default=CANON_REAL,
                   help="heads per body for head units (7.5 real, 8 heroic; default 7.5)")
    s.add_argument("--only", metavar="KEYS",
                   help="comma list of rows to print: " + ",".join(row[0] for row in DRILLIS_CONTINI))

    s = add("dist", "distance between two points", "Euclidean distance |Q-P| (2D or 3D).\n"
            "example: dmath.py dist 0,0,0 3,4,0", cmd_dist)
    s.add_argument("P", type=point)
    s.add_argument("Q", type=point)

    s = add("angle", "angle ABC at B", "Angle at B between BA and BC in degrees (2D or 3D).\n"
            "2D also prints the signed counter-clockwise angle from BA to BC.\n"
            "example: dmath.py angle 1,0 0,0 0,1", cmd_angle)
    for n in ("A", "B", "C"):
        s.add_argument(n, type=point)

    s = add("midpoint", "midpoint of two points", "(P+Q)/2.\nexample: dmath.py midpoint 0,0 2,4", cmd_midpoint)
    s.add_argument("P", type=point)
    s.add_argument("Q", type=point)

    s = add("lerp", "linear interpolation P->Q", "P + t(Q-P); t may be <0 or >1 (extrapolation).\n"
            "example: dmath.py lerp 0,0 10,0 0.25", cmd_lerp)
    s.add_argument("P", type=point)
    s.add_argument("Q", type=point)
    s.add_argument("t", type=float)

    s = add("ik2", "planar two-bone IK (leg/arm)",
            "Planar two-bone IK. Root at --root (default 0,0), Y up. Angles from straight down,\n"
            "counter-clockwise positive (toward +X). mid = flexion of bone 2 vs bone 1.\n"
            "Character facing +X: knee -> --bend -1, elbow -> --bend +1.\n"
            "Unreachable targets give the clamped end point. FK of the result is checked.\n"
            "example: dmath.py ik2 0.436 0.438 0.25 -0.80 --bend -1", cmd_ik2)
    s.add_argument("L1", type=float, help="first bone (thigh / upper arm)")
    s.add_argument("L2", type=float, help="second bone (shank / forearm)")
    s.add_argument("X", type=float, help="target x")
    s.add_argument("Y", type=float, help="target y (Y up; below the root is negative)")
    s.add_argument("--bend", type=int, choices=[1, -1], default=1, help="+1 CCW or -1 CW middle-joint flexion")
    s.add_argument("--root", type=point2, default=(0.0, 0.0), help="root joint position x,y (default 0,0)")

    s = add("cam", "project 3D points with a three.js-style camera",
            "Pinhole camera like three.js PerspectiveCamera + lookAt (up = +Y).\n"
            "Pixels have origin top-left. depth = distance along the view axis.\n"
            "With no --point the target itself is projected (always the frame centre).\n"
            "example: dmath.py cam --fov 40 --res 1080x1920 --pos 0,1.0,6 --target 0,0.9,0 "
            "--point 0,1.78,0 --point 0,0,0", cmd_cam)
    cam_common(s)
    s.add_argument("--pos", type=point3, required=True, help="camera position x,y,z")
    s.add_argument("--target", type=point3, required=True, help="look-at point x,y,z")
    s.add_argument("--point", type=point3, action="append", help="point to project (repeatable)")
    s.add_argument("--near", type=float, default=THREE_NEAR, help="near plane (default 0.1)")
    s.add_argument("--far", type=float, default=THREE_FAR, help="far plane (default 2000)")

    s = add("cam-size", "on-screen pixel height of an object",
            "px = S * res_h / (2 D tan(vfov/2)). D = depth along the view axis (exact for an\n"
            "object facing the camera, anywhere in the frame).\n"
            "example: dmath.py cam-size --fov 50 --res 1080x1920 --dist 4 --size 1.78", cmd_cam_size)
    cam_common(s)
    s.add_argument("--dist", type=float, required=True, help="object depth D in meters")
    s.add_argument("--size", type=float, required=True, help="object height S in meters")

    s = add("frame-fit", "camera distance so an object fills the frame",
            "D = S / (2 fill tan(vfov/2)); with --width also checks the (narrower, for 9:16)\n"
            "horizontal FOV and takes the larger distance.\n"
            "example: dmath.py frame-fit --fov 50 --res 1080x1920 --height 1.78 --fill 0.8", cmd_frame_fit)
    cam_common(s)
    s.add_argument("--height", type=float, required=True, help="object height S in meters")
    s.add_argument("--fill", type=float, default=0.8, help="fraction of the frame height (default 0.8)")
    s.add_argument("--width", type=float, help="object width, to also fit horizontally")

    s = add("angular", "angular size (and inverse)",
            "theta = 2 atan(S / 2D). Inverse: --deg with --dist gives size, --deg with --size gives distance.\n"
            "example: dmath.py angular --size 1.3927e9 --dist 1.496e11   (the sun, ~0.533 deg)", cmd_angular)
    s.add_argument("--size", type=float)
    s.add_argument("--dist", type=float)
    s.add_argument("--deg", type=float, help="angular size in degrees (inverse mode)")

    s = add("sun-shadow", "shadow length and direction from sun elevation",
            "length = h / tan(elev); direction = sun azimuth + 180 (compass degrees, 0=N, 90=E).\n"
            "Refuses elev <= 0 (no finite shadow).\n"
            "example: dmath.py sun-shadow --height 1.75 --elev 30 --az 135", cmd_sun_shadow)
    s.add_argument("--height", type=float, required=True, help="height of the vertical object (m)")
    s.add_argument("--elev", type=float, required=True, help="sun elevation above horizon (deg)")
    s.add_argument("--az", type=float, help="sun azimuth, compass degrees (0=N, 90=E)")

    s = add("puppet-shadow", "shadow-theatre size and blur",
            "Lamp L from the screen, puppet d from the screen (0 <= d < L).\n"
            "magnification M = L/(L-d); shadow = s*M; penumbra = w*d/(L-d) for a lamp of width w.\n"
            + PUPPET_RULE + "\n"
            "example: dmath.py puppet-shadow --light-dist 3 --puppet-dist 1 --size 0.4 --light-size 0.05",
            cmd_puppet_shadow)
    s.add_argument("--light-dist", type=float, required=True, help="lamp to screen distance L (m)")
    s.add_argument("--puppet-dist", type=float, required=True, help="puppet to screen distance d (m)")
    s.add_argument("--size", type=float, required=True, help="puppet size s (m)")
    s.add_argument("--light-size", type=float, default=0.0, help="lamp width w (m); 0 = point light")
    s.add_argument("--want", type=float, help="desired shadow size: prints where to put the puppet")

    s = add("gait", "walking step, stride, cadence (approximate)",
            "step ~0.413 x H (rule of thumb), stride = 2 steps, cadence = v*60/step steps/min.\n"
            "Default speed 1.3 m/s (comfortable adult walk). Typical cadence 100-120 steps/min.\n"
            "example: dmath.py gait --height 1.75 --fps 24", cmd_gait)
    s.add_argument("--height", type=float, required=True, help="stature (m)")
    s.add_argument("--speed", type=float, help="walking speed m/s (default 1.3)")
    s.add_argument("--sex", choices=["m", "f"], default="m")
    s.add_argument("--fps", type=float, help="also give frames per step/stride")

    s = add("ease", "per-frame eased values (spacing chart)",
            "Values for frames 0..N (N = round(dur*fps)). Curves: linear, in (t^3), out, inout\n"
            "(cubic), smoothstep (3t^2-2t^3), minjerk (10t^3-15t^4+6t^5, Flash & Hogan 1985).\n"
            "example: dmath.py ease --dur 0.5 --fps 24 --from 0 --to 90 --curve minjerk", cmd_ease)
    s.add_argument("--dur", type=float, required=True, help="duration in seconds")
    s.add_argument("--fps", type=float, required=True, help="frames per second")
    s.add_argument("--from", dest="a", type=float, required=True, help="start value")
    s.add_argument("--to", dest="b", type=float, required=True, help="end value")
    s.add_argument("--curve", choices=list(EASES), default="inout")

    s = add("arc", "circular arc length and chord",
            "arc = r*theta, chord = 2r sin(theta/2), sagitta = r(1-cos(theta/2)).\n"
            "example: dmath.py arc --radius 0.7 --deg 60", cmd_arc)
    s.add_argument("--radius", type=float, required=True)
    s.add_argument("--deg", type=float, required=True, help="arc angle in degrees (0, 360]")

    s = add("bezier", "cubic Bezier length and midpoint",
            "Cubic Bezier length by polyline sampling (n segments) plus the point at t=0.5.\n"
            "example: dmath.py bezier 0,0 1,2 3,2 4,0", cmd_bezier)
    for n in ("P0", "P1", "P2", "P3"):
        s.add_argument(n, type=point)
    s.add_argument("--n", type=int, default=1000, help="sample segments (default 1000)")
    s.add_argument("--at", type=float, default=0.5, help="also give the point at this t")
    return p


def _clean(o):
    """Make results JSON-safe (tuples -> lists, -0.0 -> 0.0)."""
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, float) and o == 0:
        return 0.0
    return o


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        data, text = args.func(args)
    except ValueError as e:
        if args.json:
            print(json.dumps({"ok": False, "cmd": args.cmd, "error": str(e)}))
        else:
            print(f"error: {e}", file=sys.stderr)
        return 2
    if args.json:
        out = {"ok": True, "cmd": args.cmd, "units": "meters, degrees"}
        out.update(_clean(data))
        print(json.dumps(out, indent=2, allow_nan=False))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
