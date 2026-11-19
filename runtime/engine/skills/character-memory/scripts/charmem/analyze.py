"""Read one flat-coloured front-view biped out of the frames, from pixels only.

1. Background = per-pixel median over the film; character = what differs from it.
2. Palette = k-means in Lab over character pixels; antialias mixes (a cluster lying between two others) are dropped.
3. Calibration on the first frame (assumed a readable rest pose, the usual rotoscope convention): every part gets a
   colour and a place from geometry (head = biggest blob up top, eyes = brightest blobs inside it, torso = biggest blob
   mid-body, arms/legs = pairs of long blobs, gloves/shoes = pairs at their ends, mouth = a colour seen only in the face).
4. Every frame: blobs per colour, assigned to parts by predicted position (constant velocity) and size; two same-colour
   parts glued into one blob are split; a part with no blob is occluded and its joints are interpolated later.
5. Joints sit where colours meet (shoulder = sleeve touching shirt, wrist = sleeve touching glove, hip, ankle);
   elbow and knee are the bend of the limb's skeleton. Face features are measured in the head's own frame.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np
from scipy.signal import savgol_filter
from skimage.morphology import skeletonize

PAIRS = {"arm": "arm", "glove": "glove", "leg": "leg", "shoe": "shoe", "eye": "eye"}


def rgb(path):
    """cv2.imread cannot open non-ASCII paths on Windows (the owner's folders are Arabic): read the bytes, then decode."""
    return cv2.cvtColor(cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)


def save_rgb(path, img):
    ok, buf = cv2.imencode(Path(path).suffix or ".png", cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
    buf.tofile(str(path))


def lab(img):
    return cv2.cvtColor(img, cv2.COLOR_RGB2LAB).astype(np.float32)


# ------------------------------------------------------------------ background, mask, palette
STATIC_DARK = None   # dark pixels that are dark in (almost) every frame: scenery, not ink (set by find_static_dark)


def find_static_dark(files, dark_thr=70, step=3, frac=0.97):
    """Pixels dark in >= 97% of the frames belong to the set (a dusk sky, a shadow); the character's ink moves.
    A character that never moves at all would be lost here: a documented limit."""
    global STATIC_DARK
    n, acc = 0, None
    for f in files[::step]:
        d = cv2.cvtColor(rgb(f), cv2.COLOR_RGB2GRAY) < dark_thr
        acc = d.astype(np.int32) if acc is None else acc + d
        n += 1
    STATIC_DARK = (acc >= frac * n) if acc is not None else None
    return STATIC_DARK


def silhouette(img, dark_thr=70):
    """The area inside the character's outer dark outline (cartoon characters are closed by one outline colour).
    Needs no background, so it cannot be fooled by a character that stands still for half the film."""
    g = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    d0 = g < dark_thr
    if STATIC_DARK is not None and STATIC_DARK.shape == d0.shape:
        d0 &= ~STATIC_DARK
    dark = cv2.dilate(d0.astype(np.uint8), np.ones((5, 5), np.uint8))   # closes gaps of thin (3 px) antialiased outlines
    cs, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    sil = np.zeros(g.shape, np.uint8)
    cv2.drawContours(sil, [c for c in cs if cv2.contourArea(c) > 2000], -1, 1, -1)
    return sil.astype(bool)


def background(files, step=2):
    """Per-pixel mean over the frames where that pixel is outside the character's silhouette (a clean plate);
    pixels the character never leaves are filled in from their neighbours."""
    acc = cnt = None
    for f in files[::step]:
        img = rgb(f)
        out = ~silhouette(img)
        if acc is None:
            acc, cnt = np.zeros(img.shape, np.float64), np.zeros(img.shape[:2], np.float64)
        acc[out] += img[out]
        cnt[out] += 1
    bg = (acc / np.maximum(cnt, 1)[..., None]).clip(0, 255).astype(np.uint8)
    hole = (cnt == 0).astype(np.uint8)
    if hole.any():
        bg = cv2.inpaint(bg, hole, 5, cv2.INPAINT_TELEA)
    return bg


def char_mask(img, bg, thr=26):
    diff = np.abs(img.astype(np.int16) - bg.astype(np.int16)).max(axis=2)
    m = ((diff > thr) & silhouette(img)).astype(np.uint8)       # inside the outline and unlike the clean plate
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, lab_, st, _ = cv2.connectedComponentsWithStats(m, 8)
    keep = np.zeros_like(m)
    for k in range(1, n):
        if st[k, cv2.CC_STAT_AREA] > 300:
            keep[lab_ == k] = 1
    return keep.astype(bool)


def learn_palette(files, bg, k=16, every=10, per_frame=25000, seed=0):
    rng = np.random.default_rng(seed)
    px = []
    for f in files[::every]:
        img = rgb(f)
        m = char_mask(img, bg)
        L = lab(img)[m]
        if len(L) > per_frame:
            L = L[rng.choice(len(L), per_frame, replace=False)]
        px.append(L)
    X = np.concatenate(px).astype(np.float32)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 60, 0.2)
    cv2.setRNGSeed(seed)
    _, lbl, C = cv2.kmeans(X, k, None, crit, 4, cv2.KMEANS_PP_CENTERS)
    cnt = np.bincount(lbl.ravel(), minlength=k).astype(float)
    order = np.argsort(-cnt)
    C, cnt = C[order], cnt[order]
    keep = []
    for i in range(k):            # merge near-duplicates into the bigger cluster; every near-black is the one outline ink
        if any(np.linalg.norm(C[i] - C[j]) < 14 or (C[i][0] < 50 and C[j][0] < 50) for j in keep):
            continue
        keep.append(i)
    C, cnt = C[keep], cnt[keep]
    share = cnt / cnt.sum()
    good = []
    for i in range(len(C)):                               # drop antialias mixes: small and between two big colours
        if share[i] < 0.0012:     # rare colours stay (an open mouth shows in ~1/5 of the frames)
            continue
        mix = False
        if share[i] < 0.04:
            for a in range(len(C)):
                for b in range(len(C)):
                    if a in (i, b) or b == i or share[a] < share[i] or share[b] < share[i]:
                        continue
                    ab = C[b] - C[a]
                    u = float(np.dot(C[i] - C[a], ab) / (np.dot(ab, ab) + 1e-6))
                    if 0.12 < u < 0.88 and np.linalg.norm(C[a] + u * ab - C[i]) < 9:
                        mix = True
        if not mix:
            good.append(i)
    C, share = C[good], share[good] / share[good].sum()
    rgbc = cv2.cvtColor(C.reshape(1, -1, 3).astype(np.uint8), cv2.COLOR_LAB2RGB).reshape(-1, 3)
    return [{"id": i, "lab": C[i].round(2).tolist(), "rgb": rgbc[i].tolist(), "hex": "#%02X%02X%02X" % tuple(rgbc[i]), "share": round(float(share[i]), 4)}
            for i in range(len(C))]


def refine_palette(files, bg, pal, every=3, min_blob=150):
    """Second pass for rare colours (an open mouth shows in a few frames, so k-means samples miss it): compact blobs of
    pixels no palette colour explains become new colours. Antialias pixels never form such blobs, so they stay out."""
    acc = []
    for f in files[::every]:
        img = rgb(f)
        m = char_mask(img, bg)
        lm = label_map(img, m, pal)
        un = ((lm == -1) & m).astype(np.uint8)
        n, cc, st, _ = cv2.connectedComponentsWithStats(un, 8)
        L = lab(img)
        for j in range(1, n):
            if st[j, cv2.CC_STAT_AREA] >= min_blob:
                acc.append(L[cc == j])
    if not acc:
        return pal
    X = np.concatenate(acc).astype(np.float32)
    k = 1 if len(X) < 4000 else 2
    _, lbl, C = cv2.kmeans(X, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, 0.2), 3, cv2.KMEANS_PP_CENTERS)
    out = list(pal)
    total = sum(p["share"] for p in pal)
    for j in range(k):
        if any(np.linalg.norm(np.array(p["lab"]) - C[j]) < 20 for p in out):
            continue
        rgbc = cv2.cvtColor(C[j].reshape(1, 1, 3).astype(np.uint8), cv2.COLOR_LAB2RGB).reshape(3)
        out.append({"id": len(out), "lab": C[j].round(2).tolist(), "rgb": rgbc.tolist(), "hex": "#%02X%02X%02X" % tuple(rgbc),
                    "share": round(float((lbl == j).sum()) / max(1, len(X)) * 0.002 * total, 5), "rare": True, "found_by": "unexplained blobs"})
    return out


def label_map(img, mask, pal, max_d=40.0):
    C = np.array([p["lab"] for p in pal], np.float32)
    L = lab(img)
    lm = np.full(mask.shape, -1, np.int16)
    pts = L[mask]
    dd = ((pts[:, None, :] - C[None, :, :]) ** 2).sum(-1)
    idx = dd.argmin(1)
    ok = np.sqrt(dd[np.arange(len(idx)), idx]) < max_d
    lab_vals = np.where(ok, idx, -1).astype(np.int16)
    lm[mask] = lab_vals
    return lm


def blobs(lm, k, min_area=30):
    m = (lm == k).astype(np.uint8)
    n, cc, st, cen = cv2.connectedComponentsWithStats(m, 8)
    out = []
    for j in range(1, n):
        a = int(st[j, cv2.CC_STAT_AREA])
        if a < min_area:
            continue
        x, y, w, h = (int(st[j, c]) for c in (cv2.CC_STAT_LEFT, cv2.CC_STAT_TOP, cv2.CC_STAT_WIDTH, cv2.CC_STAT_HEIGHT))
        ys, xs = np.nonzero(cc[y:y + h, x:x + w] == j)
        pts = np.stack([xs + x, ys + y], 1).astype(np.float32)
        rect = cv2.minAreaRect(pts)
        el = max(rect[1]) / max(1.0, min(rect[1]))
        out.append({"area": a, "c": (float(cen[j][0]), float(cen[j][1])), "bbox": (x, y, w, h), "pts": pts, "elong": float(el)})
    return out


# ------------------------------------------------------------------ calibration: which colour/blob is which part
def calibrate(img, bg, pal):
    m = char_mask(img, bg)
    lm = label_map(img, m, pal)
    ys, xs = np.nonzero(m)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    Hm, cx = y1 - y0, (x0 + x1) / 2
    Ls = [p["lab"][0] for p in pal]
    outline = int(np.argmin(Ls))
    eye = int(np.argmax(Ls))
    B = {k: blobs(lm, k) for k in range(len(pal))}
    cand = [(b["area"], k, b) for k, bl in B.items() if k not in (outline, eye) for b in bl if b["c"][1] < y0 + 0.42 * Hm]
    head = max(cand, key=lambda x: x[0])
    skin, hb = head[1], head[2]
    parts = {"head": {"label": skin, "area": hb["area"], "c": hb["c"]}}
    hx, hy, hw, hh = hb["bbox"]
    caps = [(b["area"], k, b) for k, bl in B.items() if k not in (outline, eye, skin) for b in bl
            if b["c"][1] < hb["c"][1] and abs(b["c"][0] - hb["c"][0]) < hw * 0.6 and b["area"] > 0.08 * hb["area"]]
    if caps:
        cap = max(caps, key=lambda x: x[0])
        parts["cap"] = {"label": cap[1], "area": sum(b["area"] for b in B[cap[1]] if abs(b["c"][1] - cap[2]["c"][1]) < hh), "c": cap[2]["c"]}
    used = {outline, eye, skin, parts.get("cap", {}).get("label")}
    mid = [(b["area"], k, b) for k, bl in B.items() if k not in used for b in bl
           if y0 + 0.35 * Hm < b["c"][1] < y0 + 0.75 * Hm and abs(b["c"][0] - cx) < 0.18 * (x1 - x0) + 40]
    torso = max(mid, key=lambda x: x[0])
    parts["torso"] = {"label": torso[1], "area": torso[2]["area"], "c": torso[2]["c"]}
    used.add(torso[1])
    tb = torso[2]["bbox"]
    below = [(b["area"], k, b) for k, bl in B.items() if k not in used for b in bl
             if b["c"][1] > torso[2]["c"][1] and abs(b["c"][0] - torso[2]["c"][0]) < tb[2] * 0.4 and b["area"] > 0.12 * torso[2]["area"]]
    sh = max(below, key=lambda x: x[0])
    parts["shorts"] = {"label": sh[1], "area": sh[2]["area"], "c": sh[2]["c"]}
    used.add(sh[1])

    def pair_of(k, cond):
        bl = sorted([b for b in B[k] if cond(b)], key=lambda b: -b["area"])[:2]
        return sorted(bl, key=lambda b: b["c"][0]) if len(bl) == 2 else None
    # arms: a colour with two long blobs either side of the torso, starting at shoulder height
    best = None
    for k in range(len(pal)):
        if k in used:
            continue
        pr = pair_of(k, lambda b: b["elong"] > 2.0 and b["bbox"][1] < tb[1] + tb[3] * 0.5)
        if pr and pr[0]["c"][0] < torso[2]["c"][0] < pr[1]["c"][0]:
            best = (k, pr) if not best or sum(b["area"] for b in pr) > sum(b["area"] for b in best[1]) else best
    parts["arm.R"], parts["arm.L"] = ({"label": best[0], "area": b["area"], "c": b["c"]} for b in best[1])
    used.add(best[0])
    legs = pair_of(skin, lambda b: b["c"][1] > sh[2]["c"][1] and b["elong"] > 2.0)
    parts["leg.R"], parts["leg.L"] = ({"label": skin, "area": b["area"], "c": b["c"]} for b in legs)
    # gloves: two blobs of one colour nearest the arms' far ends; shoes: two at the bottom
    for nm, ref in (("glove", ("arm.R", "arm.L")), ("shoe", ("leg.R", "leg.L"))):
        best = None
        for k in range(len(pal)):
            if k in used:
                continue
            pr = pair_of(k, lambda b: b["area"] > 200)
            if not pr:
                continue
            ends = [max(B_pts(lm, parts[r]), key=lambda p: p[1]) for r in ref]
            dist = sum(min(np.hypot(*(np.array(b["c"]) - e)) for b in pr) for e in ends)
            best = (dist, k, pr) if not best or dist < best[0] else best
        parts[nm + ".R"], parts[nm + ".L"] = ({"label": best[1], "area": b["area"], "c": b["c"]} for b in best[2])
        used.add(best[1])
    eyes = pair_of(eye, lambda b: hx - 10 < b["c"][0] < hx + hw + 10 and hy - 10 < b["c"][1] < hy + hh + 10)
    parts["eye.R"], parts["eye.L"] = ({"label": eye, "area": b["area"], "c": b["c"]} for b in eyes)
    roles = {"outline": outline, "eye": eye, "skin": skin, "cap": parts.get("cap", {}).get("label"), "shirt": parts["torso"]["label"],
             "shorts": parts["shorts"]["label"], "sleeve": parts["arm.R"]["label"], "glove": parts["glove.R"]["label"], "shoe": parts["shoe.R"]["label"]}
    return parts, roles, {"bbox": [int(x0), int(y0), int(x1), int(y1)]}


def B_pts(lm, part):
    bl = blobs(lm, part["label"])
    b = min(bl, key=lambda b: np.hypot(b["c"][0] - part["c"][0], b["c"][1] - part["c"][1]))
    return b["pts"]


def find_mouth_label(files, bg, pal, roles, every=4):
    """The colour that only ever shows inside the face (the open mouth); None if the mouth never opens."""
    seen = {}
    taken = {v for v in roles.values() if v is not None}
    for f in files[::every]:
        img = rgb(f)
        lm = label_map(img, char_mask(img, bg), pal)
        heads = [b for b in blobs(lm, roles["skin"], 2000)]
        if not heads:
            continue
        hb = min(heads, key=lambda b: b["c"][1])                  # the face is the highest big skin blob
        x, y, w, h = hb["bbox"]
        for k in range(len(pal)):
            if k in taken:
                continue
            for b in blobs(lm, k, 150):
                if b["elong"] < 6 and x < b["c"][0] < x + w and y < b["c"][1] < y + h:
                    seen.setdefault(k, []).append(b["area"])
    if not seen:
        return None
    return max(seen, key=lambda k: len(seen[k]))


# ------------------------------------------------------------------ per-frame measurement
def pick(cands, pred, area_ref, gate):
    best, bs = None, 1e9
    for b in cands:
        d = math.hypot(b["c"][0] - pred[0], b["c"][1] - pred[1])
        if d > gate:
            continue
        s = d / gate + 0.6 * abs(math.log(max(1, b["area"]) / max(1, area_ref)))
        if s < bs:
            best, bs = b, s
    return best


def split_blob(b, preds):
    """Two same-colour parts glued into one blob: 2-means on the pixel coordinates, seeded at the predictions."""
    P = b["pts"]
    c = np.array(preds, np.float32)
    for _ in range(12):
        lab_ = np.argmin(((P[:, None, :] - c[None]) ** 2).sum(-1), 1)
        c = np.array([P[lab_ == j].mean(0) if (lab_ == j).any() else c[j] for j in range(2)], np.float32)
    outs = []
    for j in range(2):
        Q = P[lab_ == j]
        x, y = Q.min(0).astype(int)
        w, h = (Q.max(0) - Q.min(0) + 1).astype(int)
        outs.append({"area": int(len(Q)), "c": (float(Q[:, 0].mean()), float(Q[:, 1].mean())), "bbox": (int(x), int(y), int(w), int(h)), "pts": Q, "elong": 1.0})
    return outs


def touching(ptsA, maskB, shape, r=4):
    """Points of A within r px of B (a colour junction): where a joint sits."""
    if maskB is None or not maskB.any():
        return None
    dt = cv2.distanceTransform((~maskB).astype(np.uint8), cv2.DIST_L2, 3)
    xi, yi = ptsA[:, 0].astype(int), ptsA[:, 1].astype(int)
    near = ptsA[dt[yi, xi] <= r]
    return near.mean(0) if len(near) >= 3 else None


def to_mask(pts, shape):
    m = np.zeros(shape, bool)
    m[pts[:, 1].astype(int), pts[:, 0].astype(int)] = True
    return m


def centerline(pts, n=28):
    """A limb's centre line: cut it into slices across its principal axis and take each slice's centre. Unlike a
    thinning skeleton this has no spurs where a shoe or the shorts cut the limb straight. Returns points and the
    limb's median half-width."""
    P = np.asarray(pts, np.float64)
    c = P.mean(0)
    _, _, vt = np.linalg.svd(P - c, full_matrices=False)
    ax, nr = vt[0], np.array([-vt[0][1], vt[0][0]])
    u = (P - c) @ ax
    v = (P - c) @ nr
    edges = np.linspace(u.min(), u.max(), n + 1)
    line, half = [], []
    for k in range(n):
        sel = (u >= edges[k]) & (u <= edges[k + 1])
        if sel.sum() < 3:
            continue
        line.append(P[sel].mean(0))
        half.append((v[sel].max() - v[sel].min()) / 2)
    return np.array(line), float(np.median(half)) if half else 0.0


def limb_ends(pts):
    line, _ = centerline(pts)
    if len(line) < 2:
        return None, None
    return line[0].astype(np.float32), line[-1].astype(np.float32)


def bend_point(pts, a, b, frac=0.5):
    """Elbow/knee: the centre-line point farthest from the chord a-b (bent), else the point at `frac` (straight)."""
    if a is None or b is None:
        return None, 0.0
    line, _ = centerline(pts)
    if len(line) < 5:
        return None, 0.0
    a, b = np.asarray(a, np.float64), np.asarray(b, np.float64)
    ab = b - a
    L = float(np.hypot(*ab)) or 1.0
    u = ((line - a) @ ab) / (L * L)
    dist = np.abs(ab[0] * (line[:, 1] - a[1]) - ab[1] * (line[:, 0] - a[0])) / L
    inside = (u > 0.15) & (u < 0.85)
    if inside.any() and dist[inside].max() > 0.02 * L:
        j = int(np.argmax(np.where(inside, dist, -1)))
        return line[j].astype(np.float32), float(dist[j] / L)
    return (a + ab * frac).astype(np.float32), 0.0


def head_frame(mask_head):
    cs, _ = cv2.findContours(mask_head.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cs, key=cv2.contourArea)
    (cx, cy), (a1, a2), ang = cv2.fitEllipse(c)
    # 'up' is the ellipse axis nearest to vertical, whichever is longer: a head with a cap is about round, so the long
    # axis can lie flat (a first version took the long axis and turned the face 90 degrees). Heads seldom tilt past 45.
    t1 = ((ang - 90 + 90) % 180) - 90          # the first axis (length a1) is at `ang` from x; its tilt from vertical
    t2 = ((ang + 90) % 180) - 90               # the second axis (length a2)
    tilt, size = (t1, a1) if abs(t1) <= abs(t2) else (t2, a2)
    return (cx, cy), size, min(a1, a2), tilt


def to_head(p, hc, tilt, size):
    r = math.radians(tilt)
    dx, dy = p[0] - hc[0], p[1] - hc[1]
    return ((dx * math.cos(r) + dy * math.sin(r)) / size, (-dx * math.sin(r) + dy * math.cos(r)) / size)


def face(lm, hm, hc, size, tilt, roles, mouth_label, eye_rest):
    out = {}
    ys, xs = np.nonzero(hm)
    inside = lambda b: hm[int(b["c"][1]), int(b["c"][0])]  # noqa: E731
    eyes = sorted([b for b in blobs(lm, roles["eye"], 40) if inside(b)], key=lambda b: -b["area"])[:2]
    eyes = sorted(eyes, key=lambda b: to_head(b["c"], hc, tilt, size)[0])
    dark = [b for b in blobs(lm, roles["outline"], 12) if inside(b)]
    for s, ex in (("R", -0.19), ("L", 0.19)):
        e = [b for b in eyes if (to_head(b["c"], hc, tilt, size)[0] < 0) == (s == "R")]
        if e:
            b = e[0]
            hgt = (b["pts"][:, 1].max() - b["pts"][:, 1].min() + 1) / size
            pup = [d for d in dark if abs(d["c"][0] - b["c"][0]) < b["bbox"][2] / 2 and abs(d["c"][1] - b["c"][1]) < b["bbox"][3] / 2]
            g = to_head(pup[0]["c"], hc, tilt, size) if pup else None
            el = to_head(b["c"], hc, tilt, size)
            out["eye." + s] = {"state": "open", "open": round(hgt / (eye_rest or hgt), 3), "c": [round(el[0], 4), round(el[1], 4)],
                               "gaze": [round(g[0] - el[0], 4), round(g[1] - el[1], 4)] if g else None}
        else:   # closed: a dark stroke where the eye was; its bend tells a blink (flat) from a happy squint (^)
            cand = [d for d in dark if abs(to_head(d["c"], hc, tilt, size)[0] - ex) < 0.12 and abs(to_head(d["c"], hc, tilt, size)[1]) < 0.12]
            state, bend = "closed", 0.0
            if cand:
                P = np.array([to_head(p, hc, tilt, size) for p in cand[0]["pts"][:: max(1, len(cand[0]["pts"]) // 200)]])
                a = np.polyfit(P[:, 0] - P[:, 0].mean(), P[:, 1], 2)[0]
                bend = float(a)
                state = "happy" if a > 2.0 else "closed"
            out["eye." + s] = {"state": state, "open": 0.0, "bend": round(bend, 3)}
    # brows: thin dark blobs above the eyes
    for s, ex in (("R", -0.19), ("L", 0.19)):
        bb = [d for d in dark if d["elong"] > 2.5 and abs(to_head(d["c"], hc, tilt, size)[0] - ex) < 0.14 and -0.36 < to_head(d["c"], hc, tilt, size)[1] < -0.14]
        out["brow." + s] = {"y": round(to_head(bb[0]["c"], hc, tilt, size)[1], 4)} if bb else None
    # mouth: the open-mouth colour, else a dark stroke low in the face
    # an open mouth is a real area (> 0.006 hu², ~400 px here); compression specks of mouth colour along a closed
    # mouth line are not (30-260 px measured)
    mo = [b for b in blobs(lm, mouth_label, int(0.006 * size * size)) if inside(b)] if mouth_label is not None else []
    if mo:
        P = np.array([to_head(p, hc, tilt, size) for p in mo[0]["pts"]])
        out["mouth"] = {"state": "open"}
    else:
        st = [d for d in dark if d["elong"] > 2.0 and 0.12 < to_head(d["c"], hc, tilt, size)[1] < 0.4 and abs(to_head(d["c"], hc, tilt, size)[0]) < 0.3]
        P = np.array([to_head(p, hc, tilt, size) for p in st[0]["pts"]]) if st else None
        out["mouth"] = {"state": "closed"} if st else {"state": "unseen"}
    if P is not None and len(P) > 5:
        xl, xr = P[:, 0].min(), P[:, 0].max()
        w = xr - xl
        mid = P[np.abs(P[:, 0] - (xl + xr) / 2) < w * 0.12]
        ends = P[(P[:, 0] < xl + w * 0.1) | (P[:, 0] > xr - w * 0.1)]
        top, bot = (mid[:, 1].min(), mid[:, 1].max()) if len(mid) else (0, 0)
        out["mouth"].update({"w": round(float(w), 4), "open": round(float(bot - top), 4) if mo else 0.0,
                             "curve": round(float((top + bot) / 2 - ends[:, 1].mean()), 4) if len(ends) else 0.0,
                             "x": round(float((xl + xr) / 2), 4), "y": round(float((top + bot) / 2), 4)})
    return out


def analyze(work_dir, progress=print):
    work = Path(work_dir)
    timing = json.loads((work / "timing.json").read_text(encoding="utf-8"))
    files = [work / "frames" / f["file"] for f in timing["frames"]]
    sd = find_static_dark(files)
    save_rgb(work / "static_dark.png", np.repeat((sd * 255).astype(np.uint8)[..., None], 3, 2))
    bg = background(files)
    save_rgb(work / "background.png", bg)
    pal = refine_palette(files, bg, learn_palette(files, bg))
    img0 = rgb(files[0])
    parts0, roles, cal = calibrate(img0, bg, pal)
    mouth = find_mouth_label(files, bg, pal, roles)
    roles["mouth"] = mouth
    progress(f"palette {len(pal)} colours; roles {roles}")
    prev = {k: {"c": v["c"], "v": (0.0, 0.0), "area": v["area"], "last": 0} for k, v in parts0.items()}
    eye_rest = None
    frames = []
    for i, f in enumerate(files):
        img = rgb(f)
        m = char_mask(img, bg)
        lm = label_map(img, m, pal)
        Bc = {}
        rec = {"i": i, "t": timing["frames"][i]["t"], "parts": {}, "joints": {}}
        masks = {}

        def cands(label):
            if label not in Bc:
                Bc[label] = blobs(lm, label)
            return Bc[label]
        assigned = set()
        for name in ["torso", "shorts", "head", "cap"]:
            if name not in prev:
                continue
            pr = prev[name]
            pred = (pr["c"][0] + pr["v"][0], pr["c"][1] + pr["v"][1])
            cs = [b for b in cands(parts0[name]["label"]) if id(b) not in assigned]
            if name == "head":
                cs = [b for b in cs if b["c"][1] < prev["torso"]["c"][1]]
            b = pick(cs, pred, pr["area"], 260)
            if b is not None:
                assigned.add(id(b))
                if name == "cap":   # the cap is a dome and a brim: take every cap blob next to the head
                    near = [x for x in cands(parts0[name]["label"]) if abs(x["c"][1] - b["c"][1]) < 120 and abs(x["c"][0] - b["c"][0]) < 200]
                    pts = np.concatenate([x["pts"] for x in near])
                    b = {"area": len(pts), "c": tuple(pts.mean(0)), "bbox": None, "pts": pts}
                masks[name] = to_mask(b["pts"], lm.shape)
                rec["parts"][name] = {"visible": True, "c": [round(b["c"][0], 2), round(b["c"][1], 2)], "area": int(b["area"]), "conf": 1.0}
                prev[name] = {"c": b["c"], "v": (b["c"][0] - pr["c"][0], b["c"][1] - pr["c"][1]), "area": b["area"], "last": i}
            else:
                rec["parts"][name] = {"visible": False, "conf": 0.0}
        for base in ("arm", "glove", "leg", "shoe"):
            R, L = base + ".R", base + ".L"
            label = parts0[R]["label"]
            preds = [(prev[s]["c"][0] + prev[s]["v"][0], prev[s]["c"][1] + prev[s]["v"][1]) for s in (R, L)]
            cs = [b for b in cands(label) if id(b) not in assigned]
            if base == "leg":
                cs = [b for b in cs if b["c"][1] > prev["shorts"]["c"][1] - 20]
            if base == "arm":
                cs = [b for b in cs if b["area"] > 0.15 * parts0[R]["area"]]
            gate = 300 if base in ("arm", "glove") else 200
            near = [b for b in cs if min(math.hypot(b["c"][0] - p[0], b["c"][1] - p[1]) for p in preds) < gate]
            res = {R: None, L: None}
            merged = False
            if len(near) >= 2:
                best, bs = None, 1e9
                for a in near:
                    for b in near:
                        if a is b:
                            continue
                        s = math.hypot(a["c"][0] - preds[0][0], a["c"][1] - preds[0][1]) + math.hypot(b["c"][0] - preds[1][0], b["c"][1] - preds[1][1])
                        if s < bs:
                            best, bs = (a, b), s
                res[R], res[L] = best
            elif len(near) == 1:
                b = near[0]
                single = (prev[R]["area"] + prev[L]["area"]) / 2
                dR = math.hypot(b["c"][0] - preds[0][0], b["c"][1] - preds[0][1])
                dL = math.hypot(b["c"][0] - preds[1][0], b["c"][1] - preds[1][1])
                if b["area"] > 1.45 * single and max(dR, dL) < gate:      # two parts glued together
                    res[R], res[L] = split_blob(b, preds)
                    merged = True
                elif dR <= dL:
                    res[R] = b
                else:
                    res[L] = b
            for s in (R, L):
                b = res[s]
                pr = prev[s]
                if b is not None:
                    assigned.add(id(b))
                    masks[s] = to_mask(b["pts"], lm.shape)
                    rec["parts"][s] = {"visible": True, "c": [round(b["c"][0], 2), round(b["c"][1], 2)], "area": int(b["area"]),
                                       "conf": 0.6 if merged else 1.0, "merged": merged}
                    prev[s] = {"c": b["c"], "v": ((b["c"][0] - pr["c"][0]) * 0.7, (b["c"][1] - pr["c"][1]) * 0.7), "area": b["area"] if not merged else pr["area"], "last": i}
                else:
                    rec["parts"][s] = {"visible": False, "conf": 0.0}
                    prev[s] = {**pr, "v": (0.0, 0.0)}
        # head frame (skin + cap + features filled), joints at colour junctions
        hm = masks.get("head")
        if hm is not None:
            hm2 = hm | masks.get("cap", np.zeros_like(hm))
            hm2 = cv2.morphologyEx(hm2.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8)).astype(bool)
            cs, _ = cv2.findContours(hm2.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            filled = np.zeros_like(hm2, np.uint8)
            cv2.drawContours(filled, [max(cs, key=cv2.contourArea)], -1, 1, -1)
            hm_full = filled.astype(bool) & ~masks.get("cap", np.zeros_like(hm))
            hc, ax_long, ax_short, tilt = head_frame(filled.astype(bool))   # the whole head: skin, cap, features
            size = ax_long
            rec["head"] = {"c": [round(hc[0], 2), round(hc[1], 2)], "size": round(size, 2), "tilt": round(tilt, 2)}
            rec["joints"]["head"] = rec["head"]["c"]
            if eye_rest is None:
                e = [b for b in blobs(lm, roles["eye"], 40) if hm_full[int(b["c"][1]), int(b["c"][0])]]
                if e:
                    eye_rest = float(np.median([(b["pts"][:, 1].max() - b["pts"][:, 1].min() + 1) / size for b in e]))
            rec["face"] = face(lm, hm_full, hc, size, tilt, roles, mouth, eye_rest)
        tm = masks.get("torso")
        if tm is not None:
            ys, xs = np.nonzero(tm)
            top = ys.min()
            rec["joints"]["neck"] = [round(float(xs[ys < top + 6].mean()), 2), float(top)]
        if "shorts" in masks:
            ys, xs = np.nonzero(masks["shorts"])
            rec["joints"]["pelvis"] = [round(float(xs.mean()), 2), round(float(ys.mean()), 2)]
        for s in ("R", "L"):
            arm, glove, leg, shoe = "arm." + s, "glove." + s, "leg." + s, "shoe." + s
            rec.setdefault("limbs", {})
            if rec["parts"][arm]["visible"]:
                ap = np.argwhere(masks[arm])[:, ::-1].astype(np.float32)
                e1, e2 = limb_ends(ap)
                nk = rec["joints"].get("neck")
                sh, far = (e1, e2) if nk is None or np.hypot(*(e1 - nk)) <= np.hypot(*(e2 - nk)) else (e2, e1)
                _, half = centerline(ap)
                dv = far - sh
                sh = sh + dv / (np.hypot(*dv) or 1.0) * half          # rounded end: the pivot is one radius in
                wg = touching(ap, masks.get(glove), lm.shape) if rec["parts"][glove]["visible"] else None
                bp, bend = bend_point(ap, sh, wg if wg is not None else far)
                rec["limbs"][arm] = {"root": sh, "far": far, "touch": wg, "bend_pt": bp, "bend": bend,
                                     "end_part": rec["parts"][glove]["c"] if rec["parts"][glove]["visible"] else None}
            if rec["parts"][glove]["visible"]:
                rec["joints"]["hand." + s] = rec["parts"][glove]["c"]
            if rec["parts"][leg]["visible"]:
                lp = np.argwhere(masks[leg])[:, ::-1].astype(np.float32)
                e1, e2 = limb_ends(lp)
                top, far = (e1, e2) if e1[1] < e2[1] else (e2, e1)
                ag = touching(lp, masks.get(shoe), lm.shape) if rec["parts"][shoe]["visible"] else None
                bp, bend = bend_point(lp, top, ag if ag is not None else far)
                rec["limbs"][leg] = {"root": top, "far": far, "touch": ag, "bend_pt": bp, "bend": bend,
                                     "end_part": rec["parts"][shoe]["c"] if rec["parts"][shoe]["visible"] else None}
            if rec["parts"][shoe]["visible"]:
                rec["joints"]["foot." + s] = rec["parts"][shoe]["c"]
        # layer evidence: a hidden hand whose sleeve ends inside the head silhouette is behind the head
        rec["layers"] = []
        for s in ("R", "L"):
            w = (rec.get("limbs", {}).get("arm." + s) or {}).get("far")       # the visible end of the sleeve
            if not rec["parts"]["glove." + s]["visible"] and w is not None and hm is not None:
                if hm_full[min(lm.shape[0] - 1, int(w[1])), min(lm.shape[1] - 1, int(w[0]))] or np.hypot(w[0] - hc[0], w[1] - hc[1]) < size * 0.7:
                    rec["layers"].append({"below": "glove." + s, "above": "head", "evidence": "hand hidden, sleeve ends in the head"})
            if rec["parts"]["glove." + s].get("merged"):
                rec["layers"].append({"touching": ["glove.R", "glove.L"], "evidence": "one blob split in two"})
        frames.append(rec)
        if i % 40 == 0:
            progress(f"frame {i}/{len(files)}")
    assemble_joints(frames)
    track = {"schema": "dragon.track.v1", "source": {k: timing[k] for k in ("video", "sha256", "fps", "width", "height")},
             "palette": pal, "roles": roles, "calibration": {"frame": 0, **cal, "parts": {k: {"label": v["label"], "area": v["area"]} for k, v in parts0.items()}},
             "frames": frames}
    finish(track)
    (work / "track.json").write_text(json.dumps(track, default=jsonable), encoding="utf-8")
    return track


def _u(v):
    n = float(np.hypot(v[0], v[1])) or 1.0
    return np.asarray(v, np.float64) / n


def _smooth01(x, a, b):
    u = min(1.0, max(0.0, (x - a) / (b - a)))
    return u * u * (3 - 2 * u)


def assemble_joints(frames):
    """Second pass. From frames where a limb is clearly bent and its end is seen, learn where along the limb its middle
    joint sits and how long its bones are; then place every frame's joints with those numbers. The middle joint blends
    smoothly from the learned ratio (straight limb) to the measured bend point (bent limb), so it never jumps between
    the two; an end hidden behind something is completed from the learned lengths and marked inferred."""
    learned = {}
    for limb in ("arm.R", "arm.L", "leg.R", "leg.L"):
        rs, up, lo, off = [], [], [], []
        for f in frames:
            L = f.get("limbs", {}).get(limb)
            if not L or L["touch"] is None:
                continue
            r, b, t = np.asarray(L["root"]), np.asarray(L["bend_pt"]), np.asarray(L["touch"])
            if L["bend"] > 0.08:
                a1, a2 = np.hypot(*(b - r)), np.hypot(*(t - b))
                rs.append(a1 / (a1 + a2))
                up.append(a1)
                lo.append(a2)
            if L["end_part"] is not None:
                off.append(np.hypot(*(np.asarray(L["end_part"]) - t)))
        learned[limb] = {"ratio": float(np.median(rs)) if rs else 0.5, "upper": float(np.median(up)) if up else None,
                         "lower": float(np.median(lo)) if lo else None, "end_offset": float(np.median(off)) if off else 0.0,
                         "bent_frames": len(rs)}
    for f in frames:
        f.setdefault("joint_kind", {})
        for limb, (j0, j1, j2, j3) in {"arm.R": ("shoulder.R", "elbow.R", "wrist.R", "hand.R"), "arm.L": ("shoulder.L", "elbow.L", "wrist.L", "hand.L"),
                                       "leg.R": ("hip.R", "knee.R", "ankle.R", "foot.R"), "leg.L": ("hip.L", "knee.L", "ankle.L", "foot.L")}.items():
            L = f.get("limbs", {}).get(limb)
            if not L:
                continue
            k = learned[limb]
            root = np.asarray(L["root"], np.float64)
            end = np.asarray(L["touch"] if L["touch"] is not None else L["far"], np.float64)
            w = _smooth01(L["bend"], 0.03, 0.09)
            mid_ratio = root + (end - root) * k["ratio"]
            mid = mid_ratio * (1 - w) + np.asarray(L["bend_pt"], np.float64) * w if L["bend_pt"] is not None else mid_ratio
            kind = "measured"
            if L["touch"] is None and k["lower"]:                 # the end is hidden: complete it from the learned forearm/shin
                far = np.asarray(L["far"], np.float64)
                if k["upper"] and np.hypot(*(far - root)) < 1.15 * k["upper"] and L["bend"] < 0.09:
                    mid = root + _u(far - root) * min(k["upper"], np.hypot(*(far - root)))   # only the upper bone shows
                    end = mid + _u(far - root) * k["lower"]
                else:
                    end = mid + _u(far - mid) * k["lower"]
                kind = "inferred"
            if limb.startswith("leg"):                            # the hip pivot is under the shorts: extend the chord to the pelvis line
                pel = f["joints"].get("pelvis")
                if pel is not None and abs(root[1] - end[1]) > 1:
                    q = (pel[1] - root[1]) / (root[1] - end[1])
                    root = np.array([root[0] + (root[0] - end[0]) * q, pel[1]])
            f["joints"][j0] = [round(float(root[0]), 2), round(float(root[1]), 2)]
            f["joints"][j1] = [round(float(mid[0]), 2), round(float(mid[1]), 2)]
            f["joints"][j2] = [round(float(end[0]), 2), round(float(end[1]), 2)]
            f["joint_kind"][j2] = kind
            if L["end_part"] is None and j3 not in f["joints"] and kind == "inferred":
                hand = end + _u(end - mid) * k["end_offset"]
                f["joints"][j3] = [round(float(hand[0]), 2), round(float(hand[1]), 2)]
                f["joint_kind"][j3] = "inferred"
        f.pop("limbs", None)
    for f in frames:            # a hidden hand known to be behind the head: keep the inferred hand/wrist inside the head
        hd = f.get("head")
        for lay in f.get("layers", []):
            if lay.get("above") == "head" and hd:
                s_ = lay["below"].split(".")[1]
                for jn in ("wrist." + s_, "hand." + s_):
                    if f.get("joint_kind", {}).get(jn) == "inferred" and jn in f["joints"]:
                        c, r = np.asarray(hd["c"]), hd["size"] / 2 * 0.6
                        v = np.asarray(f["joints"][jn]) - c
                        n = float(np.hypot(*v))
                        if n > r:
                            q = c + v / n * r
                            f["joints"][jn] = [round(float(q[0]), 2), round(float(q[1]), 2)]
    frames[0]["_learned_limbs"] = learned


def jsonable(o):
    """numpy scalars and arrays into plain JSON."""
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o).__name__)


def finish(track):
    """Fill joints of occluded frames (linear between seen frames, marked interpolated) and smooth every joint
    (Savitzky-Golay, 7 frames, order 2) so the measurement noise does not shake the redraw; raw values are kept."""
    fr = track["frames"]
    names = sorted({j for f in fr for j in f["joints"]})
    n = len(fr)
    for jn in names:
        xs = np.full(n, np.nan)
        ys = np.full(n, np.nan)
        for i, f in enumerate(fr):
            if jn in f["joints"]:
                xs[i], ys[i] = f["joints"][jn]
        ok = ~np.isnan(xs)
        if ok.sum() < 3:
            continue
        idx = np.arange(n)
        xi, yi = np.interp(idx, idx[ok], xs[ok]), np.interp(idx, idx[ok], ys[ok])
        if jn.split('.')[0] in ('hand', 'foot', 'head', 'pelvis'):   # blob centres are already sub-pixel: smoothing only adds lag
            xsm, ysm = xi, yi
        else:
            xsm, ysm = savgol_filter(xi, 7, 2), savgol_filter(yi, 7, 2)
        for i, f in enumerate(fr):
            f.setdefault("joints_raw", {})
            if ok[i]:
                f["joints_raw"][jn] = f["joints"][jn]
            f["joints"][jn] = [round(float(xsm[i]), 2), round(float(ysm[i]), 2)]
            f.setdefault("joint_src", {})[jn] = f.get("joint_kind", {}).get(jn, "measured") if ok[i] else "interpolated"
