"""character_memory.json: what was learned about the character, so it can be moved to new scenes without the video.

Every learned item says where it came from (frames, method) and how sure it is (confidence 0-1). Items the system
invents (an expression or a pose never seen) are marked observed=false, generated=true, with what they derive from.
Lengths are in head units (hu = the median head height in px) so the character can be drawn at any size.
"""
from __future__ import annotations

import datetime
import json
import math
from pathlib import Path

import cv2
import numpy as np
from skimage.morphology import skeletonize

from . import VERSION
from . import analyze as A

POSE_KEYS = ["px", "py", "spine", "head_tilt", "ua.R", "fa.R", "ua.L", "fa.L", "th.R", "sh.R", "th.L", "sh.L"]
SCHEMA = "dragon.character-memory.v1"


def ang(v):
    """Rig convention: 0 = straight down, +90 = image-right, 180 = up."""
    return math.degrees(math.atan2(v[0], v[1]))


def wrap(a):
    return (a + 180) % 360 - 180


def channels(fr, hu):
    J = {k: np.asarray(v, float) for k, v in fr["joints"].items()}
    need = ["pelvis", "neck", "shoulder.R", "elbow.R", "wrist.R", "shoulder.L", "elbow.L", "wrist.L", "hip.R", "knee.R", "ankle.R", "hip.L", "knee.L", "ankle.L"]
    if any(n not in J for n in need):
        return None
    up = J["neck"] - J["pelvis"]
    spine = math.degrees(math.atan2(up[0], -up[1]))
    c = {"px": float(J["pelvis"][0]), "py": float(J["pelvis"][1]), "spine": spine,
         "head_tilt": wrap(fr.get("head", {}).get("tilt", 0.0) - spine)}
    for s in ("R", "L"):
        ua = ang(J["elbow." + s] - J["shoulder." + s])
        c["ua." + s] = ua
        c["fa." + s] = wrap(ang(J["wrist." + s] - J["elbow." + s]) - ua)
        th = ang(J["knee." + s] - J["hip." + s])
        c["th." + s] = th
        c["sh." + s] = wrap(ang(J["ankle." + s] - J["knee." + s]) - th)
    return c


def torso_frame(J):
    up = np.asarray(J["neck"], float) - np.asarray(J["pelvis"], float)
    up /= np.linalg.norm(up) or 1.0
    side = np.array([-up[1], up[0]])          # image-right when upright
    return up, side


def radial(mask, c, rot_deg, n=72, hu=1.0):
    """Radius of a star-shaped region along n rays from c, in a frame rotated by rot_deg, in head units."""
    ys, xs = np.nonzero(mask)
    if len(xs) < 20:
        return None
    v = np.stack([xs - c[0], ys - c[1]], 1)
    r = math.radians(rot_deg)
    loc = np.stack([v[:, 0] * math.cos(r) + v[:, 1] * math.sin(r), -v[:, 0] * math.sin(r) + v[:, 1] * math.cos(r)], 1)
    a = (np.degrees(np.arctan2(loc[:, 1], loc[:, 0])) % 360) / (360 / n)
    d = np.hypot(loc[:, 0], loc[:, 1])
    out = np.zeros(n)
    idx = a.astype(int) % n
    np.maximum.at(out, idx, d)
    for k in range(n):                          # fill rays that hit no pixel from their neighbours
        if out[k] == 0:
            out[k] = max(out[(k - 1) % n], out[(k + 1) % n])
    return (out / hu).round(4).tolist()


def measure_shapes(work, track, hu, every=6):
    """Part shapes from sampled frames where the part is clearly visible (not merged): radial templates in the part's
    own frame, limb radii, ellipse radii for gloves and shoes, with the frames used."""
    timing = json.loads((work / "timing.json").read_text(encoding="utf-8"))
    bg = A.rgb(work / "background.png")
    sd = work / "static_dark.png"
    A.STATIC_DARK = (A.rgb(sd)[..., 0] > 127) if sd.exists() else None
    pal, roles = track["palette"], track["roles"]
    acc = {k: [] for k in ("head", "cap", "torso", "shorts", "arm", "leg", "glove", "shoe", "outline_w", "eye", "pupil", "brow")}
    used = {k: [] for k in acc}
    for f in track["frames"][::every]:
        i = f["i"]
        if any(not f["parts"][p]["visible"] or f["parts"][p].get("merged") for p in f["parts"]):
            continue
        img = A.rgb(work / "frames" / timing["frames"][i]["file"])
        m = A.char_mask(img, bg)
        lm = A.label_map(img, m, pal)
        J = f["joints"]
        up, side = torso_frame(J)
        spine_deg = math.degrees(math.atan2(up[0], -up[1]))
        hd = f.get("head")
        if hd:
            hm = np.zeros(m.shape, np.uint8)
            near = [b for k in (roles["skin"], roles["cap"]) for b in A.blobs(lm, k, 200) if np.hypot(b["c"][0] - hd["c"][0], b["c"][1] - hd["c"][1]) < hd["size"] * 0.75]
            for b in near:
                hm[b["pts"][:, 1].astype(int), b["pts"][:, 0].astype(int)] = 1
            hm = cv2.morphologyEx(hm, cv2.MORPH_CLOSE, np.ones((21, 21), np.uint8))
            rr = radial(hm.astype(bool), hd["c"], hd["tilt"], hu=hu)
            if rr:
                acc["head"].append(rr)
                used["head"].append(i)
            caps = [b for b in A.blobs(lm, roles["cap"], 200) if np.hypot(b["c"][0] - hd["c"][0], b["c"][1] - hd["c"][1]) < hd["size"]]
            if caps:
                cm = np.zeros(m.shape, np.uint8)
                for b in caps:
                    cm[b["pts"][:, 1].astype(int), b["pts"][:, 0].astype(int)] = 1
                cm = cv2.morphologyEx(cm, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
                ys, xs = np.nonzero(cm)
                cc = (xs.mean(), ys.mean())
                off = A.to_head(cc, hd["c"], hd["tilt"], hu)
                acc["cap"].append({"radial": radial(cm.astype(bool), cc, hd["tilt"], hu=hu), "offset": off})
                used["cap"].append(i)
            fc = f.get("face", {})
            for s in ("R", "L"):
                e = fc.get("eye." + s)
                if e and e.get("state") == "open":
                    eb = [b for b in A.blobs(lm, roles["eye"], 40) if np.hypot(*(np.array(A.to_head(b["c"], hd["c"], hd["tilt"], hu)) - e["c"])) < 0.05]
                    if eb:
                        b = eb[0]
                        acc["eye"].append({"side": s, "c": e["c"], "w": (b["pts"][:, 0].max() - b["pts"][:, 0].min() + 1) / hu,
                                           "h": (b["pts"][:, 1].max() - b["pts"][:, 1].min() + 1) / hu})
                        dk = [d for d in A.blobs(lm, roles["outline"], 10) if abs(d["c"][0] - b["c"][0]) < b["bbox"][2] / 2 and abs(d["c"][1] - b["c"][1]) < b["bbox"][3] / 2]
                        if dk:
                            acc["pupil"].append(math.sqrt(dk[0]["area"] / math.pi) / hu)
                br = fc.get("brow." + s)
                if br:
                    db = [d for d in A.blobs(lm, roles["outline"], 12) if d["elong"] > 2.5 and abs(A.to_head(d["c"], hd["c"], hd["tilt"], hu)[1] - br["y"]) < 0.02]
                    if db:
                        rect = cv2.minAreaRect(db[0]["pts"])
                        acc["brow"].append({"side": s, "len": max(rect[1]) / hu, "thick": min(rect[1]) / hu, "y": br["y"],
                                            "x": A.to_head(db[0]["c"], hd["c"], hd["tilt"], hu)[0]})
        for name, key in (("torso", "shirt"), ("shorts", "shorts")):
            bl = A.blobs(lm, roles[key], 500)
            if bl:
                b = max(bl, key=lambda b: b["area"])
                pm = np.zeros(m.shape, bool)
                pm[b["pts"][:, 1].astype(int), b["pts"][:, 0].astype(int)] = True
                rel = np.asarray(b["c"]) - np.asarray(J["pelvis"])
                acc[name].append({"radial": radial(pm, b["c"], spine_deg, hu=hu), "offset": [float(rel @ side / hu), float(rel @ up / hu)]})
                used[name].append(i)
        for base, key in (("arm", "sleeve"), ("leg", "skin")):
            for b in A.blobs(lm, roles[key], 500):
                if base == "leg" and b["c"][1] < f["joints"]["pelvis"][1]:
                    continue
                if b["elong"] > 2.0:
                    _, half = A.centerline(b["pts"])
                    acc[base].append(half / hu)
            used[base].append(i)
        for base, key in (("glove", "glove"), ("shoe", "shoe")):
            for b in A.blobs(lm, roles[key], 200):
                P = b["pts"] - b["pts"].mean(0)
                ev = np.sqrt(np.maximum(np.linalg.eigvalsh(np.cov(P.T)), 1e-6)) * 2
                acc[base].append(sorted((ev / hu).tolist(), reverse=True))
            used[base].append(i)
        # line width from the dark pixels themselves (antialiased edge pixels count), at the ink's centre line:
        # 2 x the distance to the nearest non-ink pixel. The palette labels drop edge pixels and read ~35% thin.
        ink = (cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) < 110) & m
        ys, xs = np.nonzero(ink)
        if len(xs):
            crop = ink[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
            dt = cv2.distanceTransform(np.pad(crop, 1).astype(np.uint8), cv2.DIST_L2, 5)[1:-1, 1:-1]
            sk = skeletonize(crop)
            if sk.any():
                acc["outline_w"].append(float(np.median(dt[sk])) * 2 / hu)
    return acc, used


def med_radial(lst):
    return np.median(np.array(lst), axis=0).round(4).tolist() if lst else None


def conf_from(values, scale):
    if len(values) < 2:
        return 0.3
    v = np.asarray(values, float)
    return round(float(max(0.0, min(1.0, 1 - np.std(v) / (abs(np.median(v)) * scale + 1e-9)))), 3)


EXPR_RULES = "laugh: squinting eyes + open mouth · blink: both eyes shut flat · surprise: open mouth narrower than 0.2 hu, or eyes wider than rest by 8% · confused: brows uneven by >0.04 hu or mouth off-centre by >0.03 · smile: mouth corners up (curve > 0.04 hu) · neutral: the rest"


def classify_face(fc, rest):
    eR, eL = fc.get("eye.R") or {}, fc.get("eye.L") or {}
    mo = fc.get("mouth") or {}
    if eR.get("state") == "happy" or eL.get("state") == "happy":
        return "laugh"
    if eR.get("state") == "closed" and eL.get("state") == "closed":
        return "blink"
    if mo.get("state") == "open" and (mo.get("w", 1) < 0.2 or (eR.get("open", 1) > 1.08 and eL.get("open", 1) > 1.08)):
        return "surprise"
    bR, bL = (fc.get("brow.R") or {}).get("y"), (fc.get("brow.L") or {}).get("y")
    if (bR is not None and bL is not None and abs(bR - bL) > 0.04) or (abs(mo.get("x", 0)) > 0.03 and mo.get("curve", 0) < 0.02):
        return "confused"               # a crooked mouth that is flat or turned down (a smile can sit off-centre)
    if mo.get("state") == "open":
        return "laugh"
    if mo.get("curve", 0) > 0.04 + (rest or 0):          # y points down in the head frame: corners up = positive
        return "smile"
    return "neutral"


def autocorr_period(x, fps, lo=0.25, hi=2.0):
    x = np.asarray(x, float) - np.mean(x)
    if len(x) < 8 or np.allclose(x, 0):
        return None, 0.0
    ac = np.correlate(x, x, "full")[len(x) - 1:]
    ac /= ac[0] or 1.0
    a, b = int(lo * fps), min(len(ac) - 1, int(hi * fps))
    if b <= a:
        return None, 0.0
    k = a + int(np.argmax(ac[a:b]))
    return round(k / fps, 3), round(float(ac[k]), 3)


def segments(mask_bool, min_len):
    out, s = [], None
    for i, v in enumerate(list(mask_bool) + [False]):
        if v and s is None:
            s = i
        if not v and s is not None:
            if i - s >= min_len:
                out.append((s, i - 1))
            s = None
    return out


def build(work_dir, out_path=None, name="Tamtam (تمتم)"):
    work = Path(work_dir)
    track = json.loads((work / "track.json").read_text(encoding="utf-8"))
    timing = json.loads((work / "timing.json").read_text(encoding="utf-8"))
    fps = timing["fps"]
    fr = track["frames"]
    hu = float(np.median([f["head"]["size"] for f in fr if f.get("head")]))
    ch = [channels(f, hu) for f in fr]
    acc, used = measure_shapes(work, track, hu)
    pal, roles = track["palette"], track["roles"]
    role_of = {v: k for k, v in roles.items() if v is not None}
    # ---------------------------------------------------------------- identity
    palette = [{"role": role_of.get(p["id"], "unassigned"), "hex": p["hex"], "rgb": p["rgb"], "lab_cv8": p["lab"], "share": p["share"],
                "found_by": p.get("found_by", "k-means over character pixels"),
                "confidence": 0.95 if p["id"] in role_of else 0.3} for p in pal]
    J0 = fr[0]["joints"]
    up0, side0 = torso_frame(J0)

    def L(a, b):
        v = [np.hypot(*(np.asarray(f["joints"][a]) - np.asarray(f["joints"][b]))) / hu for f in fr
             if a in f["joints"] and b in f["joints"] and f.get("joint_src", {}).get(b, "measured") == "measured"]
        return {"length_hu": round(float(np.median(v)), 4), "std_hu": round(float(np.std(v)), 4), "frames_measured": len(v),
                "confidence": conf_from(v, 0.25)} if v else None
    learned = fr[0].get("_learned_limbs", {})
    bones = []
    for nm, par, a, b in [("spine", None, "pelvis", "neck"), ("head", "spine", "neck", "head"),
                          ("upper_arm.R", "spine", "shoulder.R", "elbow.R"), ("forearm.R", "upper_arm.R", "elbow.R", "wrist.R"), ("hand.R", "forearm.R", "wrist.R", "hand.R"),
                          ("upper_arm.L", "spine", "shoulder.L", "elbow.L"), ("forearm.L", "upper_arm.L", "elbow.L", "wrist.L"), ("hand.L", "forearm.L", "wrist.L", "hand.L"),
                          ("thigh.R", "spine", "hip.R", "knee.R"), ("shin.R", "thigh.R", "knee.R", "ankle.R"), ("foot.R", "shin.R", "ankle.R", "foot.R"),
                          ("thigh.L", "spine", "hip.L", "knee.L"), ("shin.L", "thigh.L", "knee.L", "ankle.L"), ("foot.L", "shin.L", "ankle.L", "foot.L")]:
        ln = L(a, b)
        bones.append({"name": nm, "parent": par, "from": a, "to": b, **(ln or {"length_hu": None, "confidence": 0.0}),
                      "method": "median distance between the joints over frames where the far joint was measured"})
    attach = {}
    for jn in ("neck", "shoulder.R", "shoulder.L", "hip.R", "hip.L"):
        v = []
        for f in fr:
            if jn in f["joints"] and "neck" in f["joints"]:
                up, side = torso_frame(f["joints"])
                rel = np.asarray(f["joints"][jn]) - np.asarray(f["joints"]["pelvis"])
                v.append([rel @ side / hu, rel @ up / hu])
        attach[jn] = np.median(np.array(v), axis=0).round(4).tolist()
    foot_off = {}
    for s in ("R", "L"):
        v = [(np.asarray(f["joints"]["foot." + s]) - np.asarray(f["joints"]["ankle." + s])) / hu for f in fr if "foot." + s in f["joints"] and "ankle." + s in f["joints"]]
        foot_off[s] = np.median(np.array(v), axis=0).round(4).tolist()
    height = float(np.median([(max(f["joints"]["foot.R"][1], f["joints"]["foot.L"][1]) - f["head"]["c"][1]) / hu + 0.5 for f in fr if f.get("head")]))
    eyes = {s: {"c": np.median([e["c"] for e in acc["eye"] if e["side"] == s], axis=0).round(4).tolist(),
                "w": round(float(np.median([e["w"] for e in acc["eye"] if e["side"] == s])), 4),
                "h": round(float(np.median([e["h"] for e in acc["eye"] if e["side"] == s])), 4)} for s in ("R", "L")}
    brows = {}
    for s in ("R", "L"):                    # a brow seen too rarely (it touches the cap brim) is mirrored from the other side
        bs = [b for b in acc["brow"] if b["side"] == s]
        brows[s] = {k: round(float(np.median([b[k] for b in bs])), 4) for k in ("len", "thick", "y", "x")} if len(bs) >= 5 else None
        if brows[s]:
            brows[s]["measured_in"] = len(bs)
    for s, o in (("R", "L"), ("L", "R")):
        if brows[s] is None and brows[o]:
            brows[s] = {**brows[o], "x": -brows[o]["x"], "measured_in": 0, "inferred": "mirrored from the other brow (symmetry)"}
    parts = [
        {"name": "head", "bone": "head", "color_role": "skin", "shape": {"type": "radial", "rays": 72, "radii_hu": med_radial(acc["head"]), "frame": "head (centre, tilt)"},
         "from_frames": used["head"], "confidence": round(min(1.0, len(acc["head"]) / 20), 3)},
        {"name": "cap", "bone": "head", "color_role": "cap", "shape": {"type": "radial", "rays": 72, "radii_hu": med_radial([c["radial"] for c in acc["cap"]]),
                                                                        "offset_hu": np.median([c["offset"] for c in acc["cap"]], axis=0).round(4).tolist()},
         "from_frames": used["cap"], "confidence": round(min(1.0, len(acc["cap"]) / 20), 3)},
        {"name": "torso", "bone": "spine", "color_role": "shirt", "shape": {"type": "radial", "rays": 72, "radii_hu": med_radial([c["radial"] for c in acc["torso"]]),
                                                                             "offset_hu": np.median([c["offset"] for c in acc["torso"]], axis=0).round(4).tolist()},
         "from_frames": used["torso"], "confidence": round(min(1.0, len(acc["torso"]) / 20), 3)},
        {"name": "shorts", "bone": "spine", "color_role": "shorts", "shape": {"type": "radial", "rays": 72, "radii_hu": med_radial([c["radial"] for c in acc["shorts"]]),
                                                                               "offset_hu": np.median([c["offset"] for c in acc["shorts"]], axis=0).round(4).tolist()},
         "from_frames": used["shorts"], "confidence": round(min(1.0, len(acc["shorts"]) / 20), 3)},
        {"name": "arm", "bone": "upper_arm+forearm", "color_role": "sleeve", "shape": {"type": "tube", "radius_hu": round(float(np.median(acc["arm"])), 4)},
         "from_frames": used["arm"], "confidence": conf_from(acc["arm"], 0.3)},
        {"name": "leg", "bone": "thigh+shin", "color_role": "skin", "shape": {"type": "tube", "radius_hu": round(float(np.median(acc["leg"])), 4)},
         "from_frames": used["leg"], "confidence": conf_from(acc["leg"], 0.3)},
        {"name": "glove", "bone": "hand", "color_role": "glove", "shape": {"type": "ellipse", "radii_hu": np.median(np.array(acc["glove"]), axis=0).round(4).tolist()},
         "from_frames": used["glove"], "confidence": conf_from([g[0] for g in acc["glove"]], 0.3)},
        {"name": "shoe", "bone": "foot", "color_role": "shoe", "shape": {"type": "ellipse", "radii_hu": np.median(np.array(acc["shoe"]), axis=0).round(4).tolist()},
         "from_frames": used["shoe"], "confidence": conf_from([g[0] for g in acc["shoe"]], 0.3)},
        {"name": "eyes", "bone": "head", "color_role": "eye", "shape": {"type": "ellipse_pair", "R": eyes["R"], "L": eyes["L"],
                                                                         "pupil_radius_hu": round(float(np.median(acc["pupil"])), 4) if acc["pupil"] else 0.05},
         "from_frames": used["head"], "confidence": round(min(1.0, len(acc["eye"]) / 30), 3)},
        {"name": "brows", "bone": "head", "color_role": "outline", "shape": {"type": "stroke_pair", **brows}, "from_frames": used["head"],
         "confidence": round(min(1.0, len(acc["brow"]) / 30), 3)},
    ]
    # ---------------------------------------------------------------- face: expressions observed, then generated
    faces = [(f["i"], f.get("face", {})) for f in fr if f.get("face")]
    rest_curve = 0.0
    lab = {i: classify_face(fc, rest_curve) for i, fc in faces}
    expressions = []
    for nm in ("neutral", "smile", "surprise", "laugh", "confused", "blink"):
        ids = [i for i, l in lab.items() if l == nm]
        if not ids:
            continue
        mo = [dict(fc["mouth"]) for i, fc in faces if lab[i] == nm and fc.get("mouth", {}).get("w") is not None]
        params = {"mouth_state": max({m.get("state") for m in mo}, key=lambda s: sum(1 for m in mo if m.get("state") == s)) if mo else "closed"}
        for k in ("w", "open", "curve", "x", "y"):
            vals = [m[k] for m in mo if k in m]
            if vals:
                params["mouth_" + k] = round(float(np.median(vals)), 4)
        eyes_state = [fc.get("eye.R", {}).get("state") for i, fc in faces if lab[i] == nm]
        params["eye_state"] = max(set(eyes_state), key=eyes_state.count) if eyes_state else "open"
        opens = [fc.get("eye.R", {}).get("open", 1) for i, fc in faces if lab[i] == nm if fc.get("eye.R", {}).get("state") == "open"]
        params["eye_open"] = round(float(np.median(opens)), 3) if opens else 0.0
        for s in ("R", "L"):
            ys = [fc.get("brow." + s, {}).get("y") for i, fc in faces if lab[i] == nm if fc.get("brow." + s)]
            if ys:
                params["brow_y." + s] = round(float(np.median(ys)), 4)
        spread = np.std([m.get("w", 0) for m in mo]) if mo else 0.0
        expressions.append({"name": nm, "observed": True, "generated": False, "params": params, "frames": ids, "count": len(ids),
                            "first_t": round(ids[0] / fps, 3), "confidence": round(min(1.0, len(ids) / 10) * max(0.3, 1 - float(spread) * 5), 3),
                            "method": "rules on measured eyes, brows and mouth: " + EXPR_RULES})
    # generated faces start from neutral; a video may never show one (the new scene smiles throughout), so then from
    # the most-seen observed face, and say so
    base_e = next((e for e in expressions if e["name"] == "neutral"), None) or max(expressions, key=lambda e: e["count"])
    neutral = {**base_e["params"], "mouth_state": "closed", "eye_state": "open", "eye_open": base_e["params"].get("eye_open") or 1.0}
    expressions += [
        {"name": "sad", "observed": False, "generated": True, "params": {**neutral, "mouth_curve": round(abs(neutral.get("mouth_curve", 0.0)) + 0.06, 4),
                                                                           "brow_y.R": neutral.get("brow_y.R", -0.22) + 0.02, "brow_y.L": neutral.get("brow_y.L", -0.22) + 0.02,
                                                                           "brow_tilt": 12, "eye_open": 0.85},
         "derived_from": "neutral (or the most-seen face if no neutral was seen): mouth corners turned down, brows lowered and slanted up inwards, eyes a little closed", "confidence": 0.4},
        {"name": "angry", "observed": False, "generated": True, "params": {**neutral, "mouth_w": round(neutral.get("mouth_w", 0.26) * 0.8, 4), "mouth_curve": 0.03,
                                                                             "brow_y.R": neutral.get("brow_y.R", -0.22) + 0.04, "brow_y.L": neutral.get("brow_y.L", -0.22) + 0.04,
                                                                             "brow_tilt": -16},
         "derived_from": "neutral (or the most-seen face): brows down and slanted down inwards, mouth tighter", "confidence": 0.35},
    ]
    # ---------------------------------------------------------------- motions: segments of activity, with their channels
    valid = [i for i, c in enumerate(ch) if c]
    C = {k: np.array([ch[i][k] if ch[i] else np.nan for i in range(len(ch))]) for k in POSE_KEYS}
    for k in POSE_KEYS:
        x = C[k]
        ok = ~np.isnan(x)
        C[k] = np.interp(np.arange(len(x)), np.where(ok)[0], x[ok])
    vx = np.abs(np.gradient(C["px"])) * fps / hu
    hidden_R = np.array([not f["parts"]["glove.R"]["visible"] for f in fr])
    raised_L = C["ua.L"] > 90
    motions, timeline_marks = [], []

    def add_motion(name, s, e, extra=None, conf=0.8, expr=None):
        sl = slice(s, e + 1)
        motions.append({"name": name, "observed": True, "generated": False, "t0": round(s / fps, 3), "t1": round(e / fps, 3), "frames": [s, e],
                        "channels": {k: [round(float(v), 3) for v in C[k][sl]] for k in POSE_KEYS}, "channel_units": "px for px/py, degrees for the rest (rig convention)",
                        "expression": expr, "confidence": conf, **(extra or {})})
    walk_segs = []
    for s, e in segments(vx > 0.08, int(0.3 * fps)):            # join pieces of one walk split by a slow frame or two
        if walk_segs and s - walk_segs[-1][1] <= 4:
            walk_segs[-1] = (walk_segs[-1][0], e)
        else:
            walk_segs.append((s, e))
    for s, e in walk_segs:
        if e - s < int(0.4 * fps):
            continue
        per, strength = autocorr_period(C["th.R"][s:e + 1], fps, 0.5, 1.5)    # one leg: the full stride, not half
        add_motion("walk", s, e, {"period_s": per, "periodicity": strength, "speed_hu_s": round(float(np.median(vx[s:e + 1])), 4), "loop": True},
                   conf=round(0.5 + 0.5 * max(0, strength), 3), expr=None)
    for s, e in segments(raised_L, int(0.3 * fps)):
        per, strength = autocorr_period(C["fa.L"][s:e + 1], fps, 0.2, 1.0)
        add_motion("wave", s, e, {"side": "L", "period_s": per, "periodicity": strength, "loop": False}, conf=round(0.5 + 0.5 * max(0, strength), 3), expr="smile")
    for s, e in segments(hidden_R, 3):
        a, b = max(0, s - 8), min(len(fr) - 1, e + 8)
        add_motion("scratch_head", a, b, {"side": "R", "layer_swap": {"below": "arm.R", "above": "head", "frames": [s, e]}, "loop": False}, conf=0.85, expr="confused")
    for nm in ("laugh", "surprise"):
        ids = sorted(i for i, l in lab.items() if l == nm)
        for s, e in segments(np.isin(np.arange(len(fr)), ids), 4):
            per, strength = autocorr_period(C["head_tilt"][s:e + 1], fps, 0.15, 0.8) if nm == "laugh" else (None, 0.0)
            add_motion(nm, s, e, {"period_s": per, "periodicity": strength, "loop": nm == "laugh"}, conf=0.8, expr=nm)
    busy = np.zeros(len(fr), bool)
    for m in motions:
        busy[m["frames"][0]:m["frames"][1] + 1] = True
    for s, e in segments(~busy, int(0.4 * fps)):
        per, strength = autocorr_period(C["py"][s:e + 1], fps, 0.8, 3.0)
        add_motion("idle", s, e, {"breath_period_s": per, "breath_amp_px": round(float(np.ptp(C["py"][s:e + 1]) / 2), 2), "loop": True}, conf=0.7, expr="neutral")
    motions.sort(key=lambda m: m["t0"])
    motions.append({"name": "sit", "observed": False, "generated": True, "pose_delta": {"py": 0.55, "th.R": -10, "th.L": 10, "sh.R": 0, "sh.L": 0, "thigh_scale": 0.35,
                                                                                           "ua.R": -8, "ua.L": 8, "fa.R": 30, "fa.L": -30},
                    "units": "py in hu (down), angles in degrees, thigh_scale = foreshortening of the thighs seen from the front",
                    "derived_from": "the rest pose and the learned thigh length: the pelvis drops by ~ the thigh, thighs point at the camera (foreshortened), shins hang",
                    "confidence": 0.35})
    for m in motions:
        if m["observed"]:
            timeline_marks.append({"t0": m["t0"], "t1": m["t1"], "motion": m["name"], "expression": m.get("expression")})
    # ---------------------------------------------------------------- key poses: the most distinct observed poses
    V = np.array([[C[k][i] for k in POSE_KEYS[2:]] for i in range(len(fr))])
    keys, picked = [], []
    for _ in range(8):
        if not picked:
            j = 0
        else:
            d = np.min([np.linalg.norm(V - V[p], axis=1) for p in picked], axis=0)
            j = int(np.argmax(d))
        picked.append(j)
        seg = next((m["name"] for m in motions if m["observed"] and m["frames"][0] <= j <= m["frames"][1]), "idle")
        keys.append({"name": f"{seg}@{j / fps:.2f}s", "observed": True, "frame": j, "t": round(j / fps, 3), "angles": {k: round(float(C[k][j]), 2) for k in POSE_KEYS[2:]}})
    redraw_q = None
    rq = work.parent / "03_redraw" / "redraw_metrics.json"
    if rq.exists():
        redraw_q = json.loads(rq.read_text(encoding="utf-8"))["summary"]
    mem = {
        "schema": SCHEMA, "created": datetime.datetime.now().isoformat(timespec="seconds"), "made_by": f"charmem {VERSION}",
        "character": {"name": name, "view": "front", "source": {"video": track["source"]["video"], "sha256": track["source"]["sha256"], "fps": fps,
                                                                  "frames": len(fr), "size": [timing["width"], timing["height"]]}},
        "units": {"hu_px": round(hu, 2), "note": "lengths in head units (hu): multiply by the head height you want in px"},
        "identity": {"palette": palette, "outline": {"hex": pal[roles["outline"]]["hex"], "width_hu": round(float(np.median(acc["outline_w"])), 4),
                                                     "confidence": conf_from(acc["outline_w"], 0.3)},
                     "proportions": {"height_hu": round(height, 3), "head_hu": 1.0,
                                     **{b["name"] + "_hu": b["length_hu"] for b in bones if b["length_hu"]},
                                     "shoulder_width_hu": round(float(abs(attach["shoulder.L"][0] - attach["shoulder.R"][0])), 4),
                                     "hip_width_hu": round(float(abs(attach["hip.L"][0] - attach["hip.R"][0])), 4)}},
        "skeleton": {"root": "pelvis", "naming": ".R = the character's right (image left when it faces us), .L its left",
                     "bones": bones, "attach_hu": {"frame": "torso (x = across, y = up from the pelvis)", **attach},
                     "foot_offset_hu": foot_off, "learned_limb_ratios": learned},
        "parts": parts,
        "layers": {"order": ["leg.R", "leg.L", "shoe.R", "shoe.L", "torso", "shorts", "arm.R", "glove.R", "arm.L", "glove.L", "head", "cap", "eyes", "brows", "mouth"],
                   "order_source": "inferred from which part covers which in the frames (default for a front-view biped)",
                   "relations": [{"above": "head", "below": "glove.R", "condition": "right hand raised behind the head (scratch_head)",
                                  "frames": [f["i"] for f in fr if any(l.get("below") == "glove.R" for l in f.get("layers", []))], "evidence": "hand hidden, sleeve ends in the head",
                                  "confidence": 0.9},
                                 {"touching": ["glove.R", "glove.L"], "condition": "hands together (laugh)",
                                  "frames": [f["i"] for f in fr if f["parts"]["glove.R"].get("merged")], "evidence": "one glove blob split in two", "confidence": 0.7}]},
        "face": {"rest": {"eyes": eyes, "brows": brows}, "expressions": expressions},
        "poses": keys, "motions": motions,
        "timeline": timeline_marks,
        "provenance": {"frames_analysed": len(fr), "palette": "k-means in Lab + a second pass for rare colours", "parts": "colour blobs + geometry, tracked by prediction",
                       "joints": "colour junctions + limb centre lines; middle joints from learned bone ratios", "shapes": f"sampled every 6th clean frame",
                       "expressions": EXPR_RULES},
        "quality": {"redraw": redraw_q},
    }
    out = Path(out_path) if out_path else work.parent / "character_memory.json"
    out.write_text(json.dumps(mem, ensure_ascii=False, indent=1, default=A.jsonable), encoding="utf-8")
    return mem


def load(path):
    mem = json.loads(Path(path).read_text(encoding="utf-8"))
    if mem.get("schema") != SCHEMA:
        raise ValueError(f"not a character memory: {mem.get('schema')}")
    return mem
