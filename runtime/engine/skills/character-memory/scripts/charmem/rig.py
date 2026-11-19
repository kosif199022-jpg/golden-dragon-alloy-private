"""A 2D front-view biped: bones, forward kinematics and flat cartoon drawing primitives.

Image coordinates: x right, y down. A limb angle is measured from straight down: d(a) = (sin a, cos a), so 0 points
down, +90 points to image-right, 180 points up. Bone names follow rigging practice: .R is the character's right
(image left when it faces us), .L its left. Joints sit at the pivots of rotation.
The same primitives draw the reference character (from its design) and the remembered character (from memory).
"""
from __future__ import annotations

import math

import numpy as np

BONES = [  # name, parent joint, child joint
    ("spine", "pelvis", "neck"), ("head", "neck", "head"),
    ("upper_arm.R", "shoulder.R", "elbow.R"), ("forearm.R", "elbow.R", "wrist.R"),
    ("upper_arm.L", "shoulder.L", "elbow.L"), ("forearm.L", "elbow.L", "wrist.L"),
    ("thigh.R", "hip.R", "knee.R"), ("shin.R", "knee.R", "ankle.R"),
    ("thigh.L", "hip.L", "knee.L"), ("shin.L", "knee.L", "ankle.L"),
]
JOINTS = ["pelvis", "neck", "head", "shoulder.R", "elbow.R", "wrist.R", "hand.R", "shoulder.L", "elbow.L", "wrist.L", "hand.L",
          "hip.R", "knee.R", "ankle.R", "foot.R", "hip.L", "knee.L", "ankle.L", "foot.L"]
POSE_KEYS = ["px", "py", "spine", "head_tilt", "ua.R", "fa.R", "ua.L", "fa.L", "th.R", "sh.R", "th.L", "sh.L"]


def d(a):
    r = math.radians(a)
    return math.sin(r), math.cos(r)


def add(p, v, k=1.0):
    return (p[0] + v[0] * k, p[1] + v[1] * k)


def fk(pose, B):
    """Joint positions (px) from a pose and bone lengths B (px). Spine/head tilt are degrees from vertical (+ leans to
    image-right); limb angles are absolute (from straight down); forearm/shin are relative bends added to the parent."""
    J = {}
    P = (pose["px"], pose["py"])
    J["pelvis"] = P
    sp = pose.get("spine", 0.0)
    up = (math.sin(math.radians(sp)), -math.cos(math.radians(sp)))
    side = (math.cos(math.radians(sp)), math.sin(math.radians(sp)))        # image-right across the body
    J["neck"] = add(P, up, B["spine"])
    ht = sp + pose.get("head_tilt", 0.0)
    hup = (math.sin(math.radians(ht)), -math.cos(math.radians(ht)))
    J["head"] = add(J["neck"], hup, B["head"])
    sh_y = B["spine"] * 0.86
    for s, sgn in (("R", -1), ("L", 1)):
        J["shoulder." + s] = add(add(P, up, sh_y), side, sgn * B["shoulder_w"] / 2)
        ua = pose["ua." + s]
        J["elbow." + s] = add(J["shoulder." + s], d(ua), B["upper_arm"])
        J["wrist." + s] = add(J["elbow." + s], d(ua + pose["fa." + s]), B["forearm"])
        J["hand." + s] = add(J["wrist." + s], d(ua + pose["fa." + s]), B["hand"])
        J["hip." + s] = add(P, side, sgn * B["hip_w"] / 2)
        th = pose["th." + s]
        J["knee." + s] = add(J["hip." + s], d(th), B["thigh"])
        J["ankle." + s] = add(J["knee." + s], d(th + pose["sh." + s]), B["shin"])
        J["foot." + s] = add(J["ankle." + s], (sgn * 0.18 * B["foot"], 0.35 * B["foot"]), 1.0)
    J["_up"], J["_side"], J["_hup"] = up, side, hup
    return J


# ------------------------------------------------------------------ shapes as polygons (so SVG and raster agree)
def capsule(p, q, r1, r2=None, n=14):
    r2 = r1 if r2 is None else r2
    dx, dy = q[0] - p[0], q[1] - p[1]
    a = math.atan2(dy, dx)
    pts = []
    for k in range(n + 1):
        t = a + math.pi / 2 + math.pi * k / n
        pts.append((q[0] + r2 * math.cos(t - math.pi), q[1] + r2 * math.sin(t - math.pi)))
    for k in range(n + 1):
        t = a - math.pi / 2 + math.pi * k / n
        pts.append((p[0] + r1 * math.cos(t + math.pi), p[1] + r1 * math.sin(t + math.pi)))
    return pts


def ellipse(c, rx, ry, rot=0.0, n=48):
    cr, sr = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    out = []
    for k in range(n):
        t = 2 * math.pi * k / n
        x, y = rx * math.cos(t), ry * math.sin(t)
        out.append((c[0] + x * cr - y * sr, c[1] + x * sr + y * cr))
    return out


def local(poly, origin, axis_up, scale=1.0):
    """Polygon given in a part frame (x across, y down, units of `scale`) into the image, with the part's up axis."""
    ux, uy = axis_up                       # up direction in the image
    sx, sy = -uy, ux                       # across (image-right when up points up)
    return [(origin[0] + (x * sx - y * ux) * scale, origin[1] + (x * sy - y * uy) * scale) for x, y in poly]


def rounded_box(w, h, r, n=6):
    """Rounded rectangle centred at 0, in local units."""
    pts = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for k in range(n + 1):
            t = math.radians(a0 + 90 * k / n)
            pts.append((cx + r * math.cos(t), cy + r * math.sin(t)))
    return pts


def mouth_shape(w, open_, curve, n=24):
    """A mouth in face units centred at 0: a closed curve (lens) when open, else None (drawn as a stroke)."""
    top, bot = [], []
    for k in range(n + 1):
        u = -1 + 2 * k / n
        x = u * w / 2
        bend = curve * (1 - u * u)
        top.append((x, -bend * 0.4 + open_ * 0.15 * (1 - u * u)))
        bot.append((x, bend + open_ * (1 - u * u)))
    return top + bot[::-1]


def mouth_stroke(w, curve, n=16):
    return [(-w / 2 + w * k / n, curve * (1 - (-1 + 2 * k / n) ** 2)) for k in range(n + 1)]


def arc(w, h, n=14):
    """Closed-eye arc (h > 0 bends down like a smile ‿, h < 0 bends up like ^)."""
    return [(-w / 2 + w * k / n, h * (1 - (-1 + 2 * k / n) ** 2)) for k in range(n + 1)]


def draw_poly(dr, pts, fill, outline=None, width=0, s=1.0):
    P = [(x * s, y * s) for x, y in pts]
    if outline and width:
        dr.polygon(P, fill=outline)
        dr.line(P + [P[0]], fill=outline, width=max(1, int(round(width * s))), joint="curve")
        for x, y in P[:: max(1, len(P) // 24)]:
            r = width * s / 2
            dr.ellipse([x - r, y - r, x + r, y + r], fill=outline)
    if fill:
        dr.polygon(P, fill=fill)


def draw_stroke(dr, pts, color, width, s=1.0):
    P = [(x * s, y * s) for x, y in pts]
    dr.line(P, fill=color, width=max(1, int(round(width * s))), joint="curve")
    r = width * s / 2
    for x, y in (P[0], P[-1]):
        dr.ellipse([x - r, y - r, x + r, y + r], fill=color)


def grow(poly, k):
    """Offset a roughly convex polygon outwards by k (for the outline pass)."""
    c = np.mean(np.asarray(poly), axis=0)
    out = []
    for x, y in poly:
        v = np.array([x, y]) - c
        n = np.linalg.norm(v) or 1.0
        out.append(tuple(np.array([x, y]) + v / n * k))
    return out
