"""Human silhouettes for the Shadow Theatre engine — anatomy from signed distance fields, motion from biomechanics (planted feet, IK).

Everything is code (no footage, no AI):
  * BODY: every muscle mass is a smooth primitive (ellipse / tapered capsule) and the masses are merged with a smooth
    minimum, so the shoulder flows into the arm, the buttock into the thigh, the calf bulges behind the shin. The edge is
    computed per pixel at full resolution (anti-aliased by the distance itself), then softened by ~1 px only, so lips,
    fingers and knees survive instead of being halved and blurred like the engine's own masks.
  * WALK: the stance foot is planted on the ground and the leg is solved with two-bone IK from the body's real speed, so
    it cannot slide; the knee flexes on loading, the heel rolls off over the ball of the foot, the swing foot follows a
    minimum-jerk path with toe clearance, the pelvis rises and falls twice per stride because the legs are rigid
    levers, the arms counter-swing with the elbow lagging, the head stays level.
  * IDLE: breathing in the ribcage, a slow weight shift between the legs, small head drift — nobody stands still.

Pose angles keep the engine convention (0 = limb down, +90 = forward, 180 = up; arms relative to the torso, legs
absolute; elbow/knee bends added to the parent). Extra keys the walk adds: pitch_a/pitch_b (foot roll, deg, + heel up),
breath (-1..1). Units of length are the body height h. The engine files are untouched: register(E) swaps functions in."""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

T = [0.0]

LEN = {
    "plain": {"torso": 0.314, "neck": 0.036, "head": 0.130, "upper_arm": 0.186, "forearm": 0.154, "hand": 0.100,
              "thigh": 0.245, "shin": 0.238, "ankle": 0.040, "foot": 0.150, "heel": 0.034},
    "dress": {"torso": 0.306, "neck": 0.038, "head": 0.132, "upper_arm": 0.178, "forearm": 0.148, "hand": 0.092,
              "thigh": 0.250, "shin": 0.240, "ankle": 0.036, "foot": 0.130, "heel": 0.026},
}
# profile head, facing +x, y up, units of head height, origin at the skull centre (brow, nose, lips, chin, jaw, skull)
HEAD = {
    "plain": [(0.02, 0.52), (0.2, 0.47), (0.33, 0.36), (0.39, 0.22), (0.415, 0.12), (0.43, 0.07), (0.405, 0.035), (0.445, -0.035),
              (0.505, -0.11), (0.495, -0.14), (0.43, -0.158), (0.445, -0.2), (0.432, -0.232), (0.418, -0.25), (0.437, -0.282),
              (0.427, -0.312), (0.397, -0.332), (0.415, -0.372), (0.405, -0.425), (0.345, -0.475), (0.22, -0.495), (0.1, -0.47),
              (-0.05, -0.4), (-0.22, -0.36), (-0.36, -0.24), (-0.45, -0.06), (-0.46, 0.12), (-0.4, 0.3), (-0.26, 0.44), (-0.12, 0.51)],
    "dress": [(0.02, 0.52), (0.2, 0.47), (0.33, 0.36), (0.385, 0.22), (0.405, 0.12), (0.415, 0.075), (0.395, 0.04), (0.428, -0.03),
              (0.472, -0.1), (0.465, -0.125), (0.41, -0.145), (0.43, -0.185), (0.425, -0.215), (0.405, -0.238), (0.43, -0.265),
              (0.42, -0.3), (0.39, -0.318), (0.392, -0.36), (0.37, -0.41), (0.31, -0.455), (0.2, -0.47), (0.09, -0.445),
              (-0.05, -0.38), (-0.22, -0.34), (-0.36, -0.22), (-0.45, -0.05), (-0.46, 0.12), (-0.4, 0.3), (-0.26, 0.44), (-0.12, 0.51)],
}

# ------------------------------------------------------------------ small vector helpers


def set_time(t):
    T[0] = float(t)


def _dir(deg, f):
    r = math.radians(deg)
    return f * math.sin(r), math.cos(r)


def _add(p, d, k):
    return p[0] + d[0] * k, p[1] + d[1] * k


def _smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def catmull(pts, n=6, closed=True):
    """Catmull-Rom spline through the points: polygons drawn from it have no corners."""
    P = list(pts)
    m = len(P)
    if m < 3:
        return P
    out = []
    for i in range(m if closed else m - 1):
        if closed:
            p0, p1, p2, p3 = P[(i - 1) % m], P[i], P[(i + 1) % m], P[(i + 2) % m]
        else:
            p0 = P[i - 1] if i > 0 else P[i]
            p1, p2 = P[i], P[i + 1]
            p3 = P[i + 2] if i + 2 < m else P[i + 1]
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[c]) + (-p0[c] + p2[c]) * t + (2 * p0[c] - 5 * p1[c] + 4 * p2[c] - p3[c]) * t2 +
                                   (-p0[c] + 3 * p1[c] - 3 * p2[c] + p3[c]) * t3) for c in (0, 1)))
    if not closed:
        out.append(P[-1])
    return out


# ------------------------------------------------------------------ skeleton (same joint names the scene builder uses)


def body_skeleton(pose, costume, h, facing):
    c = costume if costume in LEN else "plain"
    L = {k: v * h for k, v in LEN[c].items()}
    f = facing
    tor = math.radians(pose["torso"])
    up = (f * math.sin(tor), -math.cos(tor))
    fwd = (f * math.cos(tor), math.sin(tor))
    hip = (0.0, 0.0)
    base = _add(hip, up, L["torso"])
    hr = math.radians(pose["torso"] + pose["head"] * 0.6)
    nr = math.radians(pose["torso"] + pose["head"] * 0.25)  # the neck takes part of the head tilt
    nu = (f * math.sin(nr), -math.cos(nr))
    hu = (f * math.sin(hr), -math.cos(hr))
    ntop = _add(base, nu, L["neck"])
    head = _add(ntop, hu, L["head"] * 0.5)
    hfw = (f * math.cos(hr), math.sin(hr))
    nose = (head[0] + hfw[0] * 0.5 * L["head"] - hu[0] * 0.11 * L["head"], head[1] + hfw[1] * 0.5 * L["head"] - hu[1] * 0.11 * L["head"])
    j = {"nose": nose, "hip": hip, "chest": _add(_add(hip, up, L["torso"] * 0.74), fwd, 0.055 * h), "neck": _add(base, nu, L["neck"] * 0.5),
         "neck_base": base, "head": head, "_up": up, "_fwd": fwd, "_hu": hu, "_hr": hr, "_nu": nu}
    sh = _add(_add(hip, up, L["torso"] * 0.9), fwd, -0.004 * h)
    for s in ("a", "b"):
        a1 = pose["arm_" + s] + pose["torso"]
        el = _add(sh, _dir(a1, f), L["upper_arm"])
        wr = _add(el, _dir(a1 + pose["elbow_" + s], f), L["forearm"])
        j["sh_" + s], j["el_" + s], j["wr_" + s] = sh, el, wr
        j["_fa_" + s] = a1 + pose["elbow_" + s]
        l1 = pose["leg_" + s]
        kn = _add(hip, _dir(l1, f), L["thigh"])
        an = _add(kn, _dir(l1 + pose["knee_" + s], f), L["shin"])
        j["kn_" + s], j["ft_" + s] = kn, an
        j["_sa_" + s] = l1 + pose["knee_" + s]
    return j, L


def foot_pitch(pose):
    """Foot roll (deg, + = heel up about the ball, - = toe up about the heel). The walk sets it; static poses derive it."""
    out = {}
    for s in ("a", "b"):
        if "pitch_" + s in pose:
            out[s] = float(pose["pitch_" + s])
        else:
            out[s] = max(0.0, min(35.0, -(pose["leg_" + s] + pose["knee_" + s]) * 0.9 - 4))
    return out


def shoe_poly(an, h, L, f, pitch, costume):
    """Shoe outline from the ankle. Heel up rotates about the ball; toe up rotates about the heel."""
    toe = L["foot"] - L["heel"]
    hh = L["ankle"]
    if costume == "dress":   # a low pump: the ankle and the top of the foot show
        pts = [(-L["heel"] * 0.7, -0.15), (-L["heel"] * 0.98, 0.45), (-L["heel"] * 0.85, 1.0), (toe * 0.62, 1.0), (toe * 0.95, 0.94), (toe, 0.8),
               (toe * 0.82, 0.6), (toe * 0.45, 0.36), (toe * 0.12, 0.08), (0.008 * h, -0.2)]
    else:
        pts = [(-L["heel"] * 0.75, -0.25), (-L["heel"] * 1.05, 0.38), (-L["heel"] * 0.95, 1.0), (toe * 0.78, 1.0), (toe * 1.0, 0.9), (toe * 1.04, 0.66),
               (toe * 0.86, 0.44), (toe * 0.52, 0.24), (toe * 0.2, 0.02), (0.012 * h, -0.3)]
    # the foot is hinged at the ankle: + pitch = heel up (x' = x cos - y sin, y' = x sin + y cos). Heel up, the shoe
    # bends at the ball like a real forefoot: everything ahead of the ball stays level on the ground.
    r = math.radians(pitch)
    ca, sa = math.cos(r), math.sin(r)
    bd = toe * 0.65
    bx, by = bd * ca - hh * sa, bd * sa + hh * ca            # the ball after the roll
    out = []
    for x, y in pts:
        yy = y * hh
        rx, ry = x * ca - yy * sa, x * sa + yy * ca
        if pitch > 0 and x > bd:
            w = min(1.0, (x - bd) / (0.12 * toe))                # blend over a short crease, then fully level
            fx, fy = bx + (x - bd), by + (yy - hh)
            rx, ry = rx + (fx - rx) * w, ry + (fy - ry) * w
        out.append((an[0] + f * rx, an[1] + ry))
    return catmull(out, 3)


def foot_contact(p, bd, hl, ah):
    """Where the ankle must sit so the contact point stays planted while the foot rolls (rigid foot, hinge at the ankle).
    Returns (forward shift of the ankle vs. the flat foot, ankle height above the ground). Heel up rolls over the ball
    (bd ahead of the ankle), toe up rocks on the heel (hl behind)."""
    r = math.radians(p)
    if p >= 0:
        return bd * (1 - math.cos(r)) + ah * math.sin(r), bd * math.sin(r) + ah * math.cos(r)
    return -hl * (1 - math.cos(r)) + ah * math.sin(r), -hl * math.sin(r) + ah * math.cos(r)


def ground_low(pose, j, L, h):
    """Lowest contact below the hip: the true lowest point of either shoe (or a knee / the seat when kneeling, sitting)."""
    p = foot_pitch(pose)
    lows = []
    for s in ("a", "b"):
        lows.append(max(y for _, y in shoe_poly(j["ft_" + s], h, L, 1, p[s], "plain")))
    return max(lows + [j["kn_a"][1] + 0.03 * h, j["kn_b"][1] + 0.03 * h, j["hip"][1] + 0.07 * h])


# ------------------------------------------------------------------ signed distance fields (numpy, pixel units)


def sd_ucap(X, Y, A, B, ra, rb):
    """Tapered capsule from A (radius ra) to B (radius rb) — Inigo Quilez's uneven capsule in an arbitrary direction."""
    dx, dy = B[0] - A[0], B[1] - A[1]
    Ln = math.hypot(dx, dy)
    if Ln < 1e-6:
        return np.hypot(X - A[0], Y - A[1]) - max(ra, rb)
    ux, uy = dx / Ln, dy / Ln
    px, py = X - A[0], Y - A[1]
    qy = px * ux + py * uy
    qx = np.abs(-px * uy + py * ux)
    b = (ra - rb) / Ln
    a = math.sqrt(max(0.0, 1 - b * b))
    k = qx * (-b) + qy * a
    d1 = np.hypot(qx, qy) - ra
    d2 = np.hypot(qx, qy - Ln) - rb
    d3 = qx * a + qy * b - ra
    return np.where(k < 0, d1, np.where(k > a * Ln, d2, d3))


def sd_ell(X, Y, C, ax_dir, ra, rb):
    """Ellipse centred at C, semi-axis ra along unit ax_dir and rb across (a good distance near the edge)."""
    ux, uy = ax_dir
    px, py = X - C[0], Y - C[1]
    u = px * ux + py * uy
    v = -px * uy + py * ux
    return (np.hypot(u / ra, v / rb) - 1.0) * min(ra, rb)


def smin(a, b, k):
    if k <= 0:
        return np.minimum(a, b)
    hh = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1 - hh) + a * hh - k * hh * (1 - hh)


# per-costume anatomy (units of h). torso masses: (name, u along hip->neck, offset forward, half-length, half-depth)
TORSO_MASS = {
    "plain": [("pelvis", 0.07, -0.006, 0.075, 0.062), ("buttock", 0.035, -0.022, 0.05, 0.048), ("abdomen", 0.37, 0.004, 0.1, 0.055),
              ("lumbar", 0.45, -0.008, 0.08, 0.05), ("ribcage", 0.72, 0.004, 0.13, 0.066), ("pec", 0.79, 0.04, 0.03, 0.036),
              ("scapula", 0.8, -0.022, 0.085, 0.05)],
    "dress": [("pelvis", 0.07, -0.008, 0.08, 0.066), ("buttock", 0.02, -0.05, 0.062, 0.06), ("abdomen", 0.4, 0.002, 0.09, 0.045),
              ("lumbar", 0.46, -0.004, 0.07, 0.043), ("ribcage", 0.72, 0.0, 0.12, 0.054), ("bust", 0.68, 0.036, 0.046, 0.04),
              ("scapula", 0.8, -0.018, 0.07, 0.043)],
}
LIMBS = {   # (r at start, r at end) in h; bulges: (u along, forward offset, half-len, half-width)
    "plain": {"thigh": (0.072, 0.046, [(0.42, 0.012, 0.11, 0.054)]), "shin": (0.044, 0.036, [(0.3, -0.004, 0.09, 0.045)]),
              "upper_arm": (0.041, 0.031, [(0.12, 0.0, 0.07, 0.047), (0.5, 0.008, 0.07, 0.039)]),
              "forearm": (0.032, 0.021, [(0.25, 0.002, 0.07, 0.035)]), "neck": (0.037, 0.032)},
    "dress": {"thigh": (0.07, 0.042, [(0.42, 0.008, 0.1, 0.05)]), "shin": (0.032, 0.017, [(0.3, -0.014, 0.085, 0.033)]),
              "upper_arm": (0.032, 0.024, [(0.12, 0.0, 0.06, 0.037)]), "forearm": (0.025, 0.016, [(0.25, 0.0, 0.065, 0.027)]),
              "neck": (0.028, 0.025)},
}


class Canvas:
    """A full-resolution coverage buffer over the figure's bounding box: SDF masses + supersampled polygons."""

    def __init__(self, x0, y0, x1, y1, ss=3):
        self.x0, self.y0 = int(math.floor(x0)), int(math.floor(y0))
        self.w, self.h = max(1, int(math.ceil(x1)) - self.x0), max(1, int(math.ceil(y1)) - self.y0)
        ys, xs = np.mgrid[0:self.h, 0:self.w].astype(np.float32)
        self.X, self.Y = xs + self.x0 + 0.5, ys + self.y0 + 0.5
        self.d = np.full((self.h, self.w), 1e6, np.float32)
        self.ss = ss
        self.poly_img = Image.new("L", (self.w * ss, self.h * ss), 0)
        self.pd = ImageDraw.Draw(self.poly_img)

    def add(self, sd, k):
        self.d = smin(self.d, sd.astype(np.float32), k)

    def poly(self, pts):
        s = self.ss
        self.pd.polygon([((x - self.x0) * s, (y - self.y0) * s) for x, y in pts], fill=255)

    def line(self, pts, width):
        s = self.ss
        self.pd.line([((x - self.x0) * s, (y - self.y0) * s) for x, y in pts], fill=255, width=max(1, int(round(width * s))))

    def coverage(self):
        cov = np.clip(0.5 - self.d, 0.0, 1.0)
        pc = np.asarray(self.poly_img.resize((self.w, self.h), Image.BOX), np.float32) / 255.0
        return np.maximum(cov, pc)


# ------------------------------------------------------------------ the figure


def figure_mask(ox, oy, pose, costume, h, facing, grounded=True, bounds=None):
    """Coverage (0..1, float32) of one figure and its top-left corner, at full resolution."""
    c = costume if costume in LEN else "plain"
    f = facing
    j, L = body_skeleton(pose, c, h, f)
    t = T[0]
    pitch = foot_pitch(pose)
    if grounded:
        oy = oy - ground_low(pose, j, L, h)
    P = {k: (ox + v[0], oy + v[1]) for k, v in j.items() if not k.startswith("_")}
    up, fwd, hu, hr, nu = j["_up"], j["_fwd"], j["_hu"], j["_hr"], j["_nu"]
    xs = [p[0] for p in P.values()]
    ys = [p[1] for p in P.values()]
    m = 0.2 * h
    x0, x1, y0, y1 = min(xs) - m, max(xs) + m, min(ys) - 0.16 * h, max(ys) + 0.1 * h
    if bounds:
        x0, y0, x1, y1 = max(x0, bounds[0]), max(y0, bounds[1]), min(x1, bounds[2]), min(y1, bounds[3])
        if x1 <= x0 or y1 <= y0:
            return None, 0, 0
    cv = Canvas(x0, y0, x1, y1)
    X, Y = cv.X, cv.Y
    k_body = 0.022 * h
    breath = float(pose.get("breath", 0.0))
    H0, B0 = P["hip"], P["neck_base"]

    def tpt(u, a):
        return (H0[0] + (B0[0] - H0[0]) * u + fwd[0] * a * h, H0[1] + (B0[1] - H0[1]) * u + fwd[1] * a * h)

    # torso masses (the S-curve of the back and the chest come from where the masses sit)
    tor = None
    for name, u, a, ln, dp in TORSO_MASS[c]:
        if name in ("ribcage", "pec", "bust"):
            dp = dp * (1 + 0.03 * breath) if name == "ribcage" else dp
            a = a + 0.002 * breath
        sd = sd_ell(X, Y, tpt(u, a), up, ln * h, dp * h)
        tor = sd if tor is None else smin(tor, sd, k_body)
    cv.add(tor, k_body)
    # shoulder girdle and trapezius into the neck
    shp = P["sh_a"]
    nb_back = _add(B0, fwd, -0.018 * h)
    cv.add(sd_ucap(X, Y, _add(nb_back, nu, L["neck"] * 0.55), _add(shp, up, 0.012 * h), 0.022 * h, 0.034 * h if c == "plain" else 0.028 * h), 0.03 * h)
    nr0, nr1 = LIMBS[c]["neck"]
    neck_top = _add(P["head"], hu, -0.28 * L["head"])
    neck_top = _add(neck_top, (f * math.cos(hr), math.sin(hr)), -0.04 * L["head"])
    cv.add(sd_ucap(X, Y, _add(B0, fwd, -0.004 * h), neck_top, nr0 * h, nr1 * h), 0.016 * h)

    # legs, far first (one silhouette)
    LM = LIMBS[c]
    for s in ("b", "a"):
        hipj = _add(P["hip"], fwd, 0.006 * h)
        for bone, A, B in (("thigh", hipj, P["kn_" + s]), ("shin", P["kn_" + s], P["ft_" + s])):
            r0, r1, bul = LM[bone]
            cv.add(sd_ucap(X, Y, A, B, r0 * h, r1 * h), 0.02 * h)
            dx, dy = B[0] - A[0], B[1] - A[1]
            ln = math.hypot(dx, dy) or 1
            ax = (dx / ln, dy / ln)
            nf = (f * ax[1], -f * ax[0])  # toward the facing side for a limb pointing down
            for u, off, hl, hw in bul:
                C = (A[0] + dx * u + nf[0] * off * h, A[1] + dy * u + nf[1] * off * h)
                cv.add(sd_ell(X, Y, C, ax, hl * h, hw * h), 0.02 * h)
        cv.poly(shoe_poly(P["ft_" + s], h, L, f, pitch[s], c))
    # the ankle into the shoe
    for s in ("a", "b"):
        cv.add(sd_ucap(X, Y, P["ft_" + s], _add(P["ft_" + s], (0, 1), L["ankle"] * 0.6), LM["shin"][1] * h, LM["shin"][1] * h * 1.05), 0.01 * h)

    # dress: an A-line skirt from the waist; the hem follows the legs and the wind, with folds
    if c == "dress":
        _dress(cv, P, j, L, h, f, fwd, up, pose, t)

    # head (profile) and hair
    Hh = L["head"]
    C = P["head"]
    hfw = (f * math.cos(hr), math.sin(hr))

    def head_pt(x, y):
        return C[0] + hfw[0] * x * Hh + hu[0] * y * Hh, C[1] + hfw[1] * x * Hh + hu[1] * y * Hh

    cv.poly(catmull([head_pt(x, y) for x, y in HEAD[c]], 4))
    _hair(cv, c, head_pt, P, j, L, h, f, fwd, t, Hh)

    # arms last, with hands
    for s in ("b", "a"):
        for bone, A, B in (("upper_arm", P["sh_" + s], P["el_" + s]), ("forearm", P["el_" + s], P["wr_" + s])):
            r0, r1, bul = LM[bone]
            cv.add(sd_ucap(X, Y, A, B, r0 * h, r1 * h), 0.018 * h)
            dx, dy = B[0] - A[0], B[1] - A[1]
            ln = math.hypot(dx, dy) or 1
            ax = (dx / ln, dy / ln)
            nf = (f * ax[1], -f * ax[0])
            for u, off, hl, hw in bul:
                Cc = (A[0] + dx * u + nf[0] * off * h, A[1] + dy * u + nf[1] * off * h)
                cv.add(sd_ell(X, Y, Cc, ax, hl * h, hw * h), 0.018 * h)
        _hand(cv, P["wr_" + s], j["_fa_" + s], L["hand"], LM["forearm"][1] * h, f, float(pose.get("curl_" + s, 9.0)))
    return cv.coverage(), cv.x0, cv.y0


def _hand(cv, W, fa_deg, ln, rw, f, curl):
    """Palm, a finger block that curls in two joints toward the palm side, and a thumb."""
    X, Y = cv.X, cv.Y
    d0 = _dir(fa_deg + 6, f)
    knuckle = _add(W, d0, ln * 0.46)
    cv.add(sd_ucap(X, Y, W, knuckle, rw * 1.02, rw * 0.98), rw * 0.5)
    a1 = fa_deg + 6 + curl
    mid = _add(knuckle, _dir(a1, f), ln * 0.3)
    a2 = a1 + curl * 0.8
    tip = _add(mid, _dir(a2, f), ln * 0.24)
    cv.add(sd_ucap(X, Y, knuckle, mid, rw * 0.86, rw * 0.72), rw * 0.4)
    cv.add(sd_ucap(X, Y, mid, tip, rw * 0.7, rw * 0.5), rw * 0.3)
    nf = (f * d0[1], -f * d0[0])
    tb = _add(_add(W, d0, ln * 0.14), nf, rw * 0.45)
    tt = _add(tb, _dir(fa_deg + 6 + 14 + curl * 0.5, f), ln * 0.33)
    cv.add(sd_ucap(X, Y, tb, tt, rw * 0.58, rw * 0.4), rw * 0.45)


def _dress(cv, P, j, L, h, f, fwd, up, pose, t):
    H0, B0 = P["hip"], P["neck_base"]
    wind = 0.6 + 0.4 * math.sin(t * 1.3) + 0.15 * math.sin(t * 3.7)
    wu = 0.4
    waist = (H0[0] + (B0[0] - H0[0]) * wu, H0[1] + (B0[1] - H0[1]) * wu)
    waist_f = _add(waist, fwd, 0.046 * h)
    waist_b = _add(waist, fwd, -0.044 * h)
    ground = max(P["ft_a"][1], P["ft_b"][1]) + L["ankle"]
    hem_y = ground - 0.2 * h
    # how far forward/back the legs reach at hem height: the skirt is pushed by the knee in front
    xs = []
    for s in ("a", "b"):
        for k in range(21):
            u = k / 20
            A, Bn = (P["hip"], P["kn_" + s]) if u <= 0.5 else (P["kn_" + s], P["ft_" + s])
            uu = u * 2 if u <= 0.5 else (u - 0.5) * 2
            q = (A[0] + (Bn[0] - A[0]) * uu, A[1] + (Bn[1] - A[1]) * uu)
            if q[1] <= hem_y + 0.03 * h:
                xs.append(q[0] * f)
    xs = xs or [H0[0] * f]
    front = max(xs) * f + f * 0.078 * h
    back = min(xs) * f - f * 0.1 * h
    push = -0.045 * h * wind
    hem = []
    n = 14
    for i in range(n + 1):
        u = i / n
        x = back + (front - back) * u + push * (0.35 + 0.3 * math.sin(t * 2.1 + u * 4)) * (1 - 0.6 * (1 - u))
        fold = 0.011 * h * math.sin(t * 2.9 + u * 11) + 0.006 * h * math.sin(t * 4.3 + u * 23)
        y = hem_y + fold + 0.012 * h * (1 - abs(2 * u - 1))
        hem.append((x, y))
    hip_b = _add(_add(H0, fwd, -0.098 * h), (push * 0.15 / h, 0), h)
    seat = (H0[0] - fwd[0] * 0.104 * h + push * 0.3, H0[1] + 0.075 * h)
    hip_f = _add(H0, fwd, 0.064 * h)
    # hem runs back -> front for either facing (back/front already carry the facing); a calf point rounds the back
    calf_b = (seat[0] * 0.55 + hem[0][0] * 0.45 - f * 0.012 * h, seat[1] * 0.4 + hem[0][1] * 0.6)
    pts = [waist_b, hip_b, seat, calf_b] + hem + [hip_f, waist_f]
    cv.poly(catmull(pts, 4))


def _hair(cv, c, head_pt, P, j, L, h, f, fwd, t, Hh):
    wind = 0.6 + 0.4 * math.sin(t * 1.3) + 0.15 * math.sin(t * 3.7)
    if c == "plain":
        cap = []
        for i in range(31):
            a = math.radians(64 + 156 * i / 30)
            taper = _smooth((i - 22) / 8)             # the last stretch thins into the nape instead of ending in a lip
            r = 0.565 - 0.09 * taper + 0.004 * math.sin(i * 2.7) + 0.003 * math.sin(i * 5.3 + 1)
            cap.append((r * math.cos(a) * 0.93, r * math.sin(a) + 0.03))
        cap += [(-0.3, -0.3), (-0.22, -0.22), (-0.1, 0.0), (0.1, 0.3), (0.26, 0.43)]
        cv.poly(catmull([head_pt(x, y) for x, y in cap], 3))
        # a short sideburn in front of the ear
        cv.poly([head_pt(0.02, 0.06), head_pt(0.07, -0.02), head_pt(0.05, -0.14), head_pt(-0.02, -0.1)])
        return
    # long hair: crown, a fall down the back that sways with the wind and the body, flyaway strands at the edge
    cap = []
    for i in range(31):
        a = math.radians(55 + 180 * i / 30)
        r = 0.6 + 0.004 * math.sin(i * 1.3)
        cap.append((r * math.cos(a) * 0.95, r * math.sin(a) + 0.04))
    cv.poly(catmull([head_pt(x, y) for x, y in cap] + [head_pt(-0.42, -0.44), head_pt(-0.24, -0.3), head_pt(0.0, 0.12), head_pt(0.3, 0.4)], 3))
    H0, B0 = P["hip"], P["neck_base"]
    outer, inner = [head_pt(-0.6, 0.06)], [head_pt(-0.32, -0.5)]
    for i in range(1, 15):
        s = i / 14
        u = 1.0 - 0.5 * s
        pb = (H0[0] + (B0[0] - H0[0]) * u, H0[1] + (B0[1] - H0[1]) * u)
        back = _add(pb, fwd, -0.05 * h)
        sway = -Hh * (0.2 * wind * s ** 1.5 + 0.045 * math.sin(t * 2.0 + s * 4.0) * s)
        thick = Hh * (0.3 * (1 - s) + 0.07)
        inner.append((back[0] + sway * 0.4, back[1]))
        outer.append((back[0] - fwd[0] * thick + sway, back[1] - fwd[1] * thick + 0.02 * Hh * math.sin(math.pi * s)))
    tips = []
    for k in range(7):
        u = k / 6
        a, b = outer[-1], inner[-1]
        tips.append((a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u + (0.1 * Hh if k % 2 else -0.01 * Hh)))
    cv.poly(catmull(outer, 3, closed=False) + tips + catmull(inner[::-1], 3, closed=False))
    nape = _add(B0, fwd, -0.03 * h)
    cv.poly([head_pt(-0.58, 0.02), head_pt(-0.44, -0.4), nape, inner[2], outer[2], outer[1]])
    for k in range(0):  # flyaway strands read as spikes at this size: off
        s0 = 0.08 + 0.16 * k
        base = outer[min(len(outer) - 1, int(s0 * 14))]
        ln2 = Hh * (0.16 + 0.05 * (k % 2))
        ang = 0.6 * math.sin(t * 2.6 + k * 1.7)
        tip = (base[0] - ln2 * (0.6 + 0.3 * wind), base[1] + ln2 * (0.35 + 0.25 * ang))
        midp = ((base[0] + tip[0]) / 2 - 0.05 * Hh, (base[1] + tip[1]) / 2 + 0.03 * Hh)
        cv.line(catmull([base, midp, tip], 4, closed=False), max(1.0, h * 0.0018))


# ------------------------------------------------------------------ motion


def ik2(ax, ay, Tl, Sl):
    """Two-bone leg IK, hip at the origin, target (ax forward, ay down). Returns (leg, knee) in engine degrees."""
    d = math.hypot(ax, ay)
    d = min(max(d, abs(Tl - Sl) + 1e-6), (Tl + Sl) * 0.9995)
    th = math.degrees(math.atan2(ax, ay))
    cosA = (Tl * Tl + d * d - Sl * Sl) / (2 * Tl * d)
    al = math.degrees(math.acos(max(-1.0, min(1.0, cosA))))
    leg = th + al
    kx, ky = Tl * math.sin(math.radians(leg)), Tl * math.cos(math.radians(leg))
    shin = math.degrees(math.atan2(ax - kx, ay - ky))
    return leg, shin - leg


def minjerk(u):
    u = min(1.0, max(0.0, u))
    return u * u * u * (10 - 15 * u + 6 * u * u)


def walk_pose(base, cycle, t, costume="plain"):
    """A real walk solved per frame. cycle: period (s), speed_h (body heights per second), phase."""
    c = costume if costume in LEN else "plain"
    Ln = LEN[c]
    Tl, Sl, ah = Ln["thigh"], Ln["shin"], Ln["ankle"]
    bd = (Ln["foot"] - Ln["heel"]) * 0.65   # ankle-to-ball distance (the roll-off pivot)
    P = max(0.4, float(cycle.get("period", 1.4)))
    v = float(cycle.get("speed_h", 0.35))
    st = 0.62
    travel = v * st * P
    step = v * P / 2                 # heel strike to the other foot's heel strike
    x_hs = step / 2                  # at heel strike the hip sits midway between the two feet
    x_to = x_hs - travel
    ph = t / P + float(cycle.get("phase", 0.0))
    phis = {"a": ph % 1.0, "b": (ph + 0.5) % 1.0}

    def stance_pitch(phi):
        if phi < 0.08:
            return -11.0 * (1 - phi / 0.08)
        if phi < 0.36:
            return 0.0
        return 30.0 * ((phi - 0.36) / (st - 0.36)) ** 1.7

    def knee_flex(phi):  # support knee flexion (deg): loading response, then nearly straight
        return 4.0 + 13.0 * math.exp(-((phi - 0.13) / 0.075) ** 2)

    hl = Ln["heel"] * 0.9                    # ankle-to-heel-contact distance (the heel-strike rocker)
    lift_max = 0.066 * min(1.0, max(0.45, step / 0.30))   # a slow, short step clears the ground by less (no marching)

    def swing_p(u):
        return 30.0 * (1 - u) ** 2 - 11.0 * _smooth((u - 0.6) / 0.4)   # ends on the stance's -11° heel strike

    def swing_lift(u):
        return lift_max * math.sin(math.pi * min(1.0, u ** 0.8)) ** 1.3

    def swing_x(u):
        return x_to + (x_hs - x_to) * minjerk(min(1.0, u * 1.05)) ** 1.15

    def smin_(a, b, k=0.008):
        hh = max(k - abs(a - b), 0.0) / k
        return min(a, b) - hh * hh * k * 0.25

    # hip above the ground: every foot on the ground (or about to touch it) must be reachable, so the smooth minimum of
    # what each foot allows; a foot in the air allows more, by less than its lift, reaching 0 (zero slope) at contact.
    # One supporting leg alone made the hip jump ~1.3 % of the height at every heel strike.
    G = 1e9
    for s_ in ("a", "b"):
        phi_ = phis[s_]
        if phi_ < st:
            dx_, hg_ = foot_contact(stance_pitch(phi_), bd, hl, ah)
            ax_ = x_hs - v * phi_ * P + dx_
            kf = math.radians(knee_flex(phi_))
            dl2 = Tl * Tl + Sl * Sl + 2 * Tl * Sl * math.cos(kf)
            G = smin_(G, math.sqrt(max(1e-6, dl2 - ax_ * ax_)) + hg_)
        else:
            u_ = (phi_ - st) / (1 - st)
            dx_, hg_ = foot_contact(swing_p(u_), bd, hl, ah)
            ax_ = swing_x(u_) + dx_
            allow = min(swing_lift(u_), 0.05 * (1 - u_) ** 2)
            G = smin_(G, math.sqrt(max(1e-6, (Tl + Sl) ** 2 * 0.998 - ax_ * ax_)) + hg_ + allow)
    out = dict(base)
    for s in ("a", "b"):
        phi = phis[s]
        if phi < st:
            p = stance_pitch(phi)
            dx, hg = foot_contact(p, bd, hl, ah)
            ax, ay = x_hs - v * phi * P + dx, G - hg
            if phi > 0.3 and math.hypot(ax, ay) > (Tl + Sl) * 0.999:   # trailing leg can't reach: roll further onto the ball
                for extra in range(1, 40):
                    dx, hg = foot_contact(p + extra, bd, hl, ah)
                    ax, ay = x_hs - v * phi * P + dx, G - hg
                    if math.hypot(ax, ay) <= (Tl + Sl) * 0.999:
                        p = p + extra
                        break
        else:
            u = (phi - st) / (1 - st)
            p = swing_p(u)
            dx, hg = foot_contact(p, bd, hl, ah)     # continuous with toe-off (u=0) and heel strike (u=1)
            ax = swing_x(u) + dx
            ay = G - hg - swing_lift(u)
        leg, knee = ik2(ax, ay, Tl, Sl)
        out["leg_" + s] = leg
        out["knee_" + s] = knee
        out["pitch_" + s] = p
    # arms counter-swing (opposite the same-side leg), elbow flexes more on the forward swing and lags
    mean_leg = (out["leg_a"] + out["leg_b"]) / 2
    for s in ("a", "b"):
        sw = -0.62 * (out["leg_" + s] - mean_leg)
        lag = -0.62 * (ik_leg_at(phis[s] - 0.06, x_hs, x_to, v, P, st, G, Tl, Sl, ah, bd) - mean_leg)
        out["arm_" + s] = base.get("arm_" + s, 0) * 0.3 + 0.5 * sw + 0.5 * lag + 3.0
        fwdness = max(0.0, out["arm_" + s]) / 15.0
        out["elbow_" + s] = 7.0 + 11.0 * fwdness + 2.0 * math.sin(2 * math.pi * (phis[s] + 0.2))
        out["curl_" + s] = 7.0 + 4.0 * fwdness
    out["torso"] = base.get("torso", 0) + 2.5 + 0.7 * math.cos(4 * math.pi * ph)
    out["head"] = base.get("head", 0) - 0.6 * math.cos(4 * math.pi * ph)
    return out


def ik_leg_at(phi, x_hs, x_to, v, P, st, G, Tl, Sl, ah, bd):
    """Thigh angle the leg had a moment ago (for the arm's follow-through)."""
    phi %= 1.0
    if phi < st:
        ax = x_hs - v * phi * P
        ay = G - ah
    else:
        u = (phi - st) / (1 - st)
        ax = x_to + (x_hs - x_to) * minjerk(u)
        ay = G - ah - 0.06 * math.sin(math.pi * u)
    return ik2(ax, ay, Tl, Sl)[0]


def leg_fk(leg, knee, Tl, Sl):
    """Ankle relative to the hip (x forward, y down), body-height units."""
    kx, ky = Tl * math.sin(math.radians(leg)), Tl * math.cos(math.radians(leg))
    return kx + Sl * math.sin(math.radians(leg + knee)), ky + Sl * math.cos(math.radians(leg + knee))


def feet_of(pose, costume="plain"):
    """Forward offset of each ankle from the hip in a pose (for planning steps between two keyed stances)."""
    Ln = LEN[costume if costume in LEN else "plain"]
    return {s: leg_fk(pose["leg_" + s], pose["knee_" + s], Ln["thigh"], Ln["shin"])[0] for s in ("a", "b")}


def idle(pose, t, costume="plain", amp=1.0):
    """Nobody stands still: breath in the ribcage, the weight drifting from leg to leg, a drifting head, soft elbows.
    The weight shift moves the PELVIS (a little forward/back and down); both feet stay planted and the knees follow
    by IK — the feet cannot creep the way they do when a knee angle is simply wobbled."""
    seed = 1.3 if costume == "dress" else 0.2
    Ln = LEN[costume if costume in LEN else "plain"]
    Tl, Sl = Ln["thigh"], Ln["shin"]
    p = dict(pose)
    br = math.sin(2 * math.pi * t / 3.6 + seed)
    p["breath"] = br * amp
    p["torso"] = p.get("torso", 0) + 0.5 * br * amp
    p["head"] = p.get("head", 0) + (0.8 * math.sin(2 * math.pi * t / 4.7 + seed * 2) + 0.4 * math.sin(2 * math.pi * t / 2.3 + seed)) * amp
    wgt = math.sin(2 * math.pi * t / 6.5 + seed * 3)            # -1 back leg .. +1 front leg
    dx = 0.006 * wgt * amp                                      # the pelvis drifts over the loaded foot
    dz = (0.004 + 0.002 * abs(wgt)) * amp                       # and settles a little into the knees
    for s in ("a", "b"):
        ax, ay = leg_fk(p["leg_" + s], p["knee_" + s], Tl, Sl)
        p["leg_" + s], p["knee_" + s] = ik2(ax - dx, ay - dz, Tl, Sl)
    for s in ("a", "b"):
        p["arm_" + s] = p.get("arm_" + s, 0) + 0.8 * math.sin(2 * math.pi * t / 5.1 + seed + (0 if s == "a" else 1.7)) * amp
        e = p.get("elbow_" + s, 0)
        if -15 < e < 6:          # a living elbow is never locked straight
            p["elbow_" + s] = 6.0
    return p


def _ease_inout(u):
    return 4 * u * u * u if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2


def stepto_pose(base, cycle, t, costume="plain"):
    """«Step, close»: how a standing person moves a short way. The body travels D body-heights (+ = forward) over
    [t0, t1] on the same ease as the scene keys. Each foot goes from where it stood in the start pose (feet0) to where
    it stands in the end pose (D + feet1): the lead foot first while the other stays planted, then the other. Legs by IK
    from the body's actual position, so neither foot slides. Arms stay as keyed."""
    c = costume if costume in LEN else "plain"
    Ln = LEN[c]
    Tl, Sl, ah = Ln["thigh"], Ln["shin"], Ln["ankle"]
    t0, t1 = float(cycle["t0"]), float(cycle["t1"])
    D = float(cycle.get("D", 0.0))
    f0 = cycle.get("feet0") or {"a": 0.0, "b": 0.0}
    f1 = cycle.get("feet1") or {"a": 0.0, "b": 0.0}
    u = min(1.0, max(0.0, (t - t0) / max(1e-6, t1 - t0)))
    ez = cycle.get("ease", "inout")
    prog = {"inout": _ease_inout, "smooth": lambda x: x * x * (3 - 2 * x), "out": lambda x: 1 - (1 - x) ** 3}.get(ez, lambda x: x)(u)
    hipx = D * prog
    lead = cycle.get("lead", "a")
    trail = "b" if lead == "a" else "a"
    start = {s: f0[s] for s in ("a", "b")}
    end = {s: D + f1[s] for s in ("a", "b")}
    if u < 0.5:
        k = minjerk(u * 2)
        foot = {lead: start[lead] + (end[lead] - start[lead]) * k, trail: start[trail]}
        mv = abs(end[lead] - start[lead])
        lift = {lead: min(0.032, 0.22 * mv + 0.006) * math.sin(math.pi * u * 2) * (mv > 0.004), trail: 0.0}
    else:
        k = minjerk((u - 0.5) * 2)
        foot = {lead: end[lead], trail: start[trail] + (end[trail] - start[trail]) * k}
        mv = abs(end[trail] - start[trail])
        lift = {lead: 0.0, trail: min(0.032, 0.22 * mv + 0.006) * math.sin(math.pi * (u - 0.5) * 2) * (mv > 0.004)}
    reach = (Tl + Sl) * 0.996
    far = max(abs(foot[s] - hipx) for s in ("a", "b"))
    G = math.sqrt(max(1e-6, reach * reach - far * far)) + ah - 0.012 * math.sin(math.pi * u) * min(1.0, abs(D) * 6 + 0.2)
    out = idle(base, t, c)
    w = _smooth(u / 0.1) * _smooth((1 - u) / 0.1)     # knees settle into the keyed stance at both ends
    for s in ("a", "b"):
        leg, knee = ik2(foot[s] - hipx, G - ah - lift[s], Tl, Sl)
        swing = lift[s] > 1e-4
        ph = u * 2 if s == lead else (u - 0.5) * 2
        pitch = (10.0 * math.sin(math.pi * ph) if swing else 0.0) * (1 if D >= 0 else -0.5)
        out["leg_" + s] = out["leg_" + s] * (1 - w) + leg * w
        out["knee_" + s] = out["knee_" + s] * (1 - w) + knee * w
        out["pitch_" + s] = pitch * w
    return out


def gait(pose, cycle, t, fallback, costume="plain"):
    kind = (cycle or {}).get("type")
    if kind == "stepto":
        if t < float(cycle["t0"]) or t > float(cycle["t1"]):
            return idle(pose, t, costume)
        return stepto_pose(pose, cycle, t, costume)
    if kind == "walk":
        t0, t1 = float(cycle.get("t0", -1e9)), float(cycle.get("t1", 1e9))
        if t < t0 or t > t1:
            return idle(pose, t, costume)
        wpose = walk_pose(pose, cycle, t, costume)
        bl = float(cycle.get("blend", 0.0))
        if bl <= 0:
            return wpose
        w = _smooth((t - t0) / bl) * _smooth((t1 - t) / bl)
        rest = idle(pose, t, costume)
        out = dict(rest)
        for k, val in wpose.items():
            if isinstance(val, (int, float)) and isinstance(rest.get(k, 0), (int, float)):
                out[k] = rest.get(k, 0) * (1 - w) + val * w
        return out
    if kind == "breathe" or not cycle:
        return idle(pose, t, costume, float((cycle or {}).get("amp", 1.0)))
    return fallback(pose, cycle, t)


# ------------------------------------------------------------------ engine hook-up


def draw_body(draw, ox, oy, pose, costume, h, facing, grounded):
    """Engine signature: paints the figure into the engine's mask image (used by stills/other paths)."""
    cov, x0, y0 = figure_mask(ox, oy, pose, costume, h, facing, grounded)
    if cov is None:
        return
    img = draw._image
    tile = Image.fromarray((cov * 255 + 0.5).astype(np.uint8))
    region = img.crop((x0, y0, x0 + tile.width, y0 + tile.height))
    from PIL import ImageChops
    img.paste(ImageChops.lighter(region, tile), (x0, y0))


def register(E):
    E.body_skeleton = body_skeleton
    E.draw_body = draw_body
    if not hasattr(E, "_engine_apply_cycle"):
        E._engine_apply_cycle = E.apply_cycle
    if getattr(E.ShadowRenderer, "_human_patched", False):
        return
    R = E.ShadowRenderer

    def human_layer(self, actor, tl):
        k = E.sample_keys(actor.get("keys", [{"t": 0}]), tl)
        op = float(k.get("opacity", 1.0))
        if op <= 0.003:
            return None
        x, y = float(k.get("x", 0.5)), float(k.get("y", 0.93))
        px, py = self.to_px(x, y, work=False)
        h = float(k.get("height", actor.get("height", 0.42))) * self.sh * float(k.get("scale", 1.0))
        costume = actor.get("costume", "plain")
        pose = gait(E.mix_pose(k.get("_pose_mix", (actor.get("pose"), actor.get("pose"), 0))), actor.get("cycle"), tl,
                    E._engine_apply_cycle, costume)
        cov, x0, y0 = figure_mask(px, py, pose, costume, h, int(k.get("facing", actor.get("facing", 1))), actor.get("grounded", True),
                                  bounds=(0, 0, self.W, self.H))
        if cov is None:
            return None
        pen = float(self.spec.get("human_penumbra", 0.9))
        if pen > 0.05:
            cov = np.asarray(Image.fromarray((cov * 255 + 0.5).astype(np.uint8)).filter(ImageFilter.GaussianBlur(pen)), np.float32) / 255.0
        return cov * op, x0, y0

    def render(self, t):
        set_time(t)
        scene = self.scene_at(t)
        tl = t - scene["start"]
        bd = self.backdrop(scene, tl)
        shadow = np.zeros((self.hh, self.hw), np.float32)
        full = np.zeros((self.H, self.W), np.float32)
        for actor in scene.get("actors", []):
            if actor.get("type", "human") == "human":
                r = human_layer(self, actor, tl)
                if r is not None:
                    cov, x0, y0 = r
                    hh_, ww_ = cov.shape
                    sl = full[y0:y0 + hh_, x0:x0 + ww_]
                    np.maximum(sl, cov[: sl.shape[0], : sl.shape[1]], out=sl)
            else:
                m, op, _ = self.actor_layer(actor, tl)
                if m is not None:
                    np.maximum(shadow, m * op, out=shadow)
        sh = np.maximum(E._resize(shadow, (self.W, self.H)), full)[..., None]
        lit = bd * self._hotspot * (1 - sh * (1 - self.leak))
        lmask = self._screen * self.light_level(scene, t)
        iris = self.iris_mask(scene, tl)
        if iris is not None:
            lmask = lmask * iris
        cloth = self._screen * np.array((0.035, 0.035, 0.07), np.float32)
        out = lit * lmask + cloth * (1 - lmask) + self._stage * (1 - self._screen)
        rng = np.random.default_rng(int(t * self.fps) + self.seed)
        grain = rng.normal(0, float(self.spec.get("grain", 0.006)), (self.hh, self.hw)).astype(np.float32)
        grain = np.repeat(np.repeat(grain, 2, 0), 2, 1)[: self.H, : self.W, None]
        return E.Frame((np.clip(out + grain, 0, 1) * 255 + 0.5).astype(np.uint8))

    R.render = render
    R._human_patched = True
    # scene builders call E.apply_cycle without the costume: walk and idle need it only for leg lengths (close enough)
    E.apply_cycle = lambda pose, cycle, t: gait(pose, cycle, t, E._engine_apply_cycle)
