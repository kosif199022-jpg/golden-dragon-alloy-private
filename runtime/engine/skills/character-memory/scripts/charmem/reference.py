"""Tamtam («تمتم»): an original cartoon kid drawn from code, and an 8 s reference performance with varied motions and
expressions. It exists to test the rotoscope honestly: because we drew it, every joint, expression and hidden part is
known per frame (ground truth, written to gt.json for the tests only; the analyzer never reads it).

Performance (anticipation before, settle after every big move):
  0-1 s idle + blink · 1-2.65 wave (left arm) + smile · 2.7-3.5 surprise (crouch, pop, arms flare) ·
  3.5-5.4 walk across · 5.4-6.4 laugh, hands on the belly (glove over shirt) · 6.45-7.45 confused, right hand scratches
  BEHIND the head (the hand disappears: occlusion) · 7.45-8 back to rest + blink.
"""
from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from . import rig

W, H, FPS, DUR = 1080, 1920, 30, 8.0
GROUND = 1540
HU = 270.0                                     # head height, px: every size below is in these units
DESIGN = {
    "name": "Tamtam (تمتم)", "view": "front",
    "palette": {"outline": "#1E1A2B", "skin": "#F2B48A", "cap": "#F28C28", "shirt": "#2F80D1", "sleeve": "#2E9E6B",
                "glove": "#FFD84D", "shorts": "#7A4FB0", "shoe": "#D63A3A", "eye": "#FFFFFF", "mouth": "#8E2433"},
    "bones_hu": {"spine": 0.95, "head": 0.48, "shoulder_w": 0.62, "hip_w": 0.40, "upper_arm": 0.42, "forearm": 0.40, "hand": 0.10,
                 "thigh": 0.46, "shin": 0.44, "foot": 0.32},
    "radii_hu": {"arm": 0.10, "leg0": 0.12, "leg1": 0.10, "glove": 0.15, "shoe_rx": 0.20, "shoe_ry": 0.11, "outline": 0.022},
    "background": {"top": "#FFF4E2", "bottom": "#FBE3C0", "floor": "#E8C796"},
}
EXPR = {  # face units of head height
    "neutral": {"eye": 1.0, "eye_mode": "open", "brow": (0.0, 0.0), "mouth": (0.26, 0.0, 0.02, 0.0)},
    "smile": {"eye": 1.0, "eye_mode": "open", "brow": (0.01, 0.01), "mouth": (0.32, 0.0, 0.07, 0.0)},
    "surprise": {"eye": 1.18, "eye_mode": "open", "brow": (0.06, 0.06), "mouth": (0.13, 0.14, 0.0, 0.0)},
    "laugh": {"eye": 1.0, "eye_mode": "happy", "brow": (0.03, 0.03), "mouth": (0.38, 0.17, 0.06, 0.0)},
    "confused": {"eye": 1.0, "eye_mode": "open", "brow": (0.07, -0.01), "mouth": (0.20, 0.0, -0.03, 0.06)},
    "blink": {"eye": 1.0, "eye_mode": "closed", "brow": (0.0, 0.0), "mouth": (0.26, 0.0, 0.02, 0.0)},
}


def hexc(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def ss(a, b, t):
    u = min(1.0, max(0.0, (t - a) / (b - a)))
    return u * u * (3 - 2 * u)


def bones_px(design=DESIGN, hu=HU):
    return {k: v * hu for k, v in design["bones_hu"].items()}


REST = {"px": 400.0, "py": GROUND - 1.122 * HU, "spine": 0.0, "head_tilt": 0.0, "ua.R": -12.0, "fa.R": 4.0, "ua.L": 12.0, "fa.L": -4.0,
        "th.R": -4.0, "sh.R": 0.0, "th.L": 4.0, "sh.L": 0.0}


def blend(p, q, k):
    return {key: p[key] + (q[key] - p[key]) * k for key in p}


def pose_at(t):
    """The keyed performance: pose, expression name(s) with weight, and the right arm's layer (behind the head?)."""
    p = dict(REST)
    p["py"] += 2.0 * math.sin(2 * math.pi * t / 2.4)                     # breathing
    # wave with the left arm: dip, raise, wave the forearm, lower with a small settle
    k_up = ss(1.15, 1.45, t) * (1 - ss(2.35, 2.65, t))
    p["ua.L"] += -8 * (ss(1.0, 1.12, t) - ss(1.12, 1.2, t)) + (150 - 12) * k_up
    wv = math.sin(2 * math.pi * 2.2 * (t - 1.45)) * ss(1.4, 1.55, t) * (1 - ss(2.25, 2.4, t))
    p["fa.L"] += (-16 + 32 * wv) * k_up
    # surprise: crouch, pop, arms flare, settle
    p["py"] += 22 * (ss(2.7, 2.82, t) - ss(2.82, 2.95, t)) - 18 * (ss(2.85, 3.0, t) - ss(3.05, 3.5, t))
    fl = ss(2.82, 2.98, t) * (1 - ss(3.1, 3.5, t))
    p["ua.R"] -= 43 * fl
    p["ua.L"] += 43 * fl
    p["fa.R"] -= 16 * fl
    p["fa.L"] += 16 * fl
    # walk across: x eases in and out, legs march (front view), arms swing against the legs, body bobs
    kx = ss(3.5, 5.4, t)
    p["px"] += 280 * kx
    if 3.5 < t < 5.4:
        e = ss(3.5, 3.7, t) * (1 - ss(5.2, 5.4, t))
        ph = (t - 3.5) / 0.76
        for s, off, sgn in (("R", 0.0, -1), ("L", 0.5, 1)):
            lift = max(0.0, math.sin(2 * math.pi * (ph + off))) * e
            p["th." + s] += sgn * 14 * lift
            p["sh." + s] -= sgn * 30 * lift
            p["ua." + s] += sgn * 7 * math.sin(2 * math.pi * (ph + off + 0.5)) * e
        p["py"] -= 7 * abs(math.sin(2 * math.pi * ph)) * e
        p["spine"] += 3 * math.sin(2 * math.pi * ph) * e
    # laugh: hands on the belly, head bobs and tilts
    kl = ss(5.4, 5.6, t) * (1 - ss(6.2, 6.4, t))
    p["ua.R"] -= 14 * kl
    p["fa.R"] += 76 * kl
    p["ua.L"] += 14 * kl
    p["fa.L"] -= 76 * kl
    lb = math.sin(2 * math.pi * 3.0 * (t - 5.5)) * ss(5.5, 5.65, t) * (1 - ss(6.15, 6.3, t))
    p["head_tilt"] += 4 * lb
    p["py"] += 5 * abs(lb)
    # confused: the right hand scratches behind the head, the head tilts towards it
    kc = ss(6.45, 6.75, t) * (1 - ss(7.2, 7.5, t))
    p["ua.R"] += (-170 - REST["ua.R"]) * kc
    p["fa.R"] += (-80 - REST["fa.R"]) * kc + 9 * math.sin(2 * math.pi * 4.0 * (t - 6.8)) * ss(6.75, 6.85, t) * (1 - ss(7.1, 7.2, t))
    p["head_tilt"] -= 8 * ss(6.5, 6.8, t) * (1 - ss(7.2, 7.5, t))
    # expression: (from, to, weight of `to`)
    if 0.70 <= t < 0.80 or 7.75 <= t < 7.85:
        ex = ("neutral", "blink", 1.0)
    elif t < 1.05:
        ex = ("neutral", "smile", 0.0)
    elif t < 2.7:
        ex = ("neutral", "smile", ss(1.05, 1.25, t))
    elif t < 3.5:
        ex = ("smile", "surprise", ss(2.74, 2.84, t) * (1 - ss(3.35, 3.5, t)))
    elif t < 5.4:
        ex = ("neutral", "smile", ss(4.3, 4.5, t))
    elif t < 6.45:
        ex = ("smile", "laugh", ss(5.42, 5.52, t) * (1 - ss(6.3, 6.42, t)))
    elif t < 7.5:
        ex = ("neutral", "confused", ss(6.5, 6.65, t) * (1 - ss(7.3, 7.45, t)))
    else:
        ex = ("neutral", "neutral", 0.0)
    behind_head = 6.6 <= t < 7.3
    return p, ex, {"arm.R_behind_head": behind_head}


def expr_params(ex):
    a, b, k = ex
    A, Bx = EXPR[a], EXPR[b]
    mode = Bx["eye_mode"] if k >= 0.5 else A["eye_mode"]
    lerp = lambda u, v: u + (v - u) * k  # noqa: E731
    return {"eye": lerp(A["eye"], Bx["eye"]), "eye_mode": mode,
            "brow": tuple(lerp(u, v) for u, v in zip(A["brow"], Bx["brow"])),
            "mouth": tuple(lerp(u, v) for u, v in zip(A["mouth"], Bx["mouth"])),
            "name": b if k >= 0.5 else a}


# ------------------------------------------------------------------ drawing
def face_polys(J, hu, ep, flip_tilt=0.0):
    """Face features in the image, as (kind, points, role) with role in eye, pupil, outline-stroke, mouth."""
    C, up = J["head"], J["_hup"]
    out = []
    for s, sx in (("R", -1), ("L", 1)):
        ec = rig.local([(sx * 0.19, 0.0)], C, up, hu)[0]
        if ep["eye_mode"] == "open":
            out.append(("poly", rig.local(rig.ellipse((sx * 0.19, 0.0), 0.12, 0.15 * ep["eye"]), C, up, hu), "eye"))
            out.append(("poly", rig.local(rig.ellipse((sx * 0.19, 0.012), 0.055, 0.055), C, up, hu), "pupil"))
        else:
            h = -0.05 if ep["eye_mode"] == "happy" else 0.0
            pts = [(x + sx * 0.19, y + 0.01) for x, y in rig.arc(0.2, h)]
            out.append(("stroke", rig.local(pts, C, up, hu), "outline"))
        br = ep["brow"][0 if s == "R" else 1]
        out.append(("stroke", rig.local([(sx * 0.19 - 0.08, -0.22 - br), (sx * 0.19 + 0.08, -0.22 - br - 0.01 * sx)], C, up, hu), "outline"))
        del ec
    w, op, cu, ox = ep["mouth"]
    if op > 0.02:
        out.append(("poly", rig.local([(x + ox, y + 0.24) for x, y in rig.mouth_shape(w, op, cu)], C, up, hu), "mouth"))
    else:
        out.append(("stroke", rig.local([(x + ox, y + 0.25) for x, y in rig.mouth_stroke(w, cu)], C, up, hu), "outline"))
    return out


def character_layers(pose, ep, flags, B=None, hu=HU, design=DESIGN):
    """Every drawable of the character, back to front: (name, kind, points, color role, outline?)."""
    B = B or bones_px(design, hu)
    R = design["radii_hu"]
    J = rig.fk(pose, B)
    L = []
    for s in ("R", "L"):
        L.append(("leg." + s, "limb", [J["hip." + s], J["knee." + s], J["ankle." + s]], "skin", (R["leg0"] * hu, R["leg1"] * hu)))
    for s, sg in (("R", -1), ("L", 1)):
        L.append(("shoe." + s, "poly", rig.ellipse(J["foot." + s], R["shoe_rx"] * hu, R["shoe_ry"] * hu), "shoe", None))
    up = J["_up"]
    mid = rig.add(J["pelvis"], up, B["spine"] * 0.45)
    L.append(("torso", "poly", rig.local(rig.rounded_box(0.78, 1.0, 0.18), mid, up, hu), "shirt", None))
    L.append(("shorts", "poly", rig.local(rig.rounded_box(0.70, 0.34, 0.08), rig.add(J["pelvis"], up, 0.04 * hu), up, hu), "shorts", None))
    arms = []
    for s in ("R", "L"):
        arms.append(("arm." + s, "limb", [J["shoulder." + s], J["elbow." + s], J["wrist." + s]], "sleeve", (R["arm"] * hu, R["arm"] * hu)))
        arms.append(("glove." + s, "poly", rig.ellipse(J["hand." + s], R["glove"] * hu, R["glove"] * hu * 0.92), "glove", None))
    behind = [a for a in arms if flags.get("arm.R_behind_head") and a[0].endswith(".R")]
    front = [a for a in arms if a not in behind]
    L += behind
    hup = J["_hup"]
    L.append(("head", "poly", rig.ellipse(J["head"], 0.52 * hu, 0.50 * hu, rot=math.degrees(math.atan2(hup[0], -hup[1]))), "skin", None))
    dome = [(0.54 * math.cos(a), -0.12 + 0.36 * math.sin(a)) for a in np.linspace(math.pi, 2 * math.pi, 24)]   # upper half
    L.append(("cap", "poly", rig.local(dome, J["head"], hup, hu), "cap", None))
    brim = [(x, y - 0.15) for x, y in rig.rounded_box(1.06, 0.10, 0.04)]
    L.append(("cap_brim", "poly", rig.local(brim, J["head"], hup, hu), "cap", None))
    L += front
    for kind, pts, role in face_polys(J, hu, ep):
        L.append(("face", "stroke" if kind == "stroke" else "poly", pts, role, None))
    return L, J


def render_layers(layers, design=DESIGN, hu=HU, s=2, bg=None, size=(W, H)):
    pal = {k: hexc(v) for k, v in design["palette"].items()}
    ow = design["radii_hu"]["outline"] * hu
    img = bg.copy().resize((size[0] * s, size[1] * s)) if bg is not None else Image.new("RGB", (size[0] * s, size[1] * s), (255, 255, 255))
    dr = ImageDraw.Draw(img)
    for name, kind, pts, role, extra in layers:
        if kind == "limb":
            r0, r1 = extra
            segs = [(pts[0], pts[1], r0, (r0 + r1) / 2), (pts[1], pts[2], (r0 + r1) / 2, r1)]
            for p, q, a, b in segs:
                rig.draw_poly(dr, rig.capsule(p, q, a + ow, b + ow), pal["outline"], s=s)
            for p, q, a, b in segs:
                rig.draw_poly(dr, rig.capsule(p, q, a, b), pal[role], s=s)
        elif kind == "poly" and role == "pupil":
            rig.draw_poly(dr, pts, pal["outline"], s=s)                       # pupils are solid outline colour
        elif kind == "poly":
            rig.draw_poly(dr, pts, pal[role], pal["outline"], ow, s=s)
        else:
            rig.draw_stroke(dr, pts, pal["outline"], ow * 1.5, s=s)
    return img.resize(size, Image.LANCZOS) if s != 1 else img


def background(design=DESIGN, size=(W, H)):
    top, bot, floor = (np.array(hexc(design["background"][k]), np.float32) for k in ("top", "bottom", "floor"))
    y = np.linspace(0, 1, size[1])[:, None, None]
    img = top * (1 - y) + bot * y
    img = np.repeat(img, size[0], axis=1)
    img[GROUND - 30:] = floor
    return Image.fromarray(img.clip(0, 255).astype(np.uint8))


def visible_fraction(layers, name, size=(W, H)):
    """How much of a part is visible after everything drawn after it (rasterized masks, 1/4 resolution)."""
    k = 0.25
    sz = (int(size[0] * k), int(size[1] * k))
    idx = [i for i, l in enumerate(layers) if l[0] == name][0]
    m = Image.new("L", sz, 0)
    ImageDraw.Draw(m).polygon([(x * k, y * k) for x, y in layers[idx][2]], fill=255)
    cover = Image.new("L", sz, 0)
    dc = ImageDraw.Draw(cover)
    for nm, kind, pts, role, extra in layers[idx + 1:]:
        if kind == "poly":
            dc.polygon([(x * k, y * k) for x, y in pts], fill=255)
    a = np.asarray(m) > 0
    c = np.asarray(cover) > 0
    return float((a & ~c).sum() / max(1, a.sum()))


def make(out_dir):
    """Render the reference video and its ground truth."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    bg = background()
    n = int(round(DUR * FPS))
    video = out / "reference.mp4"
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", "-color_primaries", "bt709",
                           "-color_trc", "bt709", "-colorspace", "bt709", "-movflags", "+faststart", str(video)], stdin=subprocess.PIPE)
    gt = {"fps": FPS, "width": W, "height": H, "head_unit_px": HU, "design": DESIGN, "frames": []}
    for i in range(n):
        t = i / FPS
        pose, ex, flags = pose_at(t)
        ep = expr_params(ex)
        layers, J = character_layers(pose, ep, flags)
        img = render_layers(layers, bg=bg)
        ff.stdin.write(img.tobytes())
        vis = {nm: round(visible_fraction(layers, nm), 3) for nm in ("glove.R", "glove.L", "arm.R", "arm.L")}
        gt["frames"].append({"i": i, "t": round(t, 4), "pose": {k: round(v, 3) for k, v in pose.items()},
                             "joints": {k: [round(v[0], 2), round(v[1], 2)] for k, v in J.items() if not k.startswith("_")},
                             "expression": ep["name"], "expr_params": {"eye": ep["eye"], "eye_mode": ep["eye_mode"], "brow": ep["brow"], "mouth": ep["mouth"]},
                             "visible": vis, "flags": flags})
    ff.stdin.close()
    if ff.wait():
        raise SystemExit("ffmpeg failed")
    (out / "gt.json").write_text(json.dumps(gt), encoding="utf-8")
    bg.save(out / "reference_background.png")
    return video
