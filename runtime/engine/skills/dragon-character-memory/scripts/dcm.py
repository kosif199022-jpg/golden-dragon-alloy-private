#!/usr/bin/env python3
"""Dragon Character Memory & Auto Rotoscope (dcm).

  dcm.py make-ref   OUT_DIR                 render the original demo character "Nabd" to a reference video (+ ground truth, kept apart)
  dcm.py extract    VIDEO WORK              frames as PNG + their original timestamps (frames.json)
  dcm.py analyze    WORK                    per frame: background, palette, parts, joints, expressions -> tracks.json
  dcm.py redraw     WORK                    redraw every frame as vector regions (SVG + raster) and measure it against the reference
  dcm.py memory     WORK OUT.json           build character_memory.json (identity, parts, joints, poses, expressions, clips, confidence)
  dcm.py rebuild    WORK MEMORY.json        re-render the reference from the MEMORY ONLY + pose track, and measure it
  dcm.py animate    MEMORY.json OUT_DIR --do "walk_to 0.8; wave 2; laugh 1.5; sit 2"    new scene from the memory alone
  dcm.py identity   MEMORY.json VIDEO       measure a character found in VIDEO against the memory (palette, proportions)
  dcm.py demo       OUT_DIR                 all of the above on the demo character, with a report

Scope, stated plainly: flat-colour 2D characters on a flat-colour background, one character, limbs that keep their colour.
It measures; it does not guess. Anything it could not see is marked with low confidence, and anything it invents is marked
"synthesized". Needs: python 3.10+, numpy, opencv-python, Pillow, ffmpeg/ffprobe on PATH."""
import argparse, json, math, os, shutil, subprocess, sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

VERSION = "1.0.0"
W, H, FPS = 640, 360, 24
SS = 3                                      # supersampling for every raster this tool draws

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def jdump(o, p):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8")


def jload(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def rot(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s], [s, c]])


def smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def ffmpeg_encode(frames_glob, out, fps=FPS):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", frames_glob, "-c:v", "libx264", "-crf", "12", "-preset", "medium",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)], check=True)


# ====================================================================== 1) demo character (ground truth lives only here)
DEMO = {"skin": (242, 199, 155), "hair": (59, 42, 74), "white": (255, 255, 255), "pupil": (30, 30, 40), "mouth": (184, 50, 60),
        "torso": (31, 163, 154), "arm": (242, 140, 40), "leg": (43, 58, 103), "bg": (234, 230, 218), "floor": (207, 200, 184)}


def capsule(length, thick, n=10):
    r = thick / 2
    pts = [(0, -r), (length, -r)] + [(length + r * math.sin(a), -r * math.cos(a)) for a in np.linspace(0, math.pi, n)[1:-1]] + [(length, r), (0, r)] + \
          [(-r * math.sin(a), r * math.cos(a)) for a in np.linspace(0, math.pi, n)[1:-1]]
    return np.array(pts, float)


def ellipse(rx, ry, n=40, a0=0.0, a1=2 * math.pi):
    return np.array([(rx * math.cos(a), ry * math.sin(a)) for a in np.linspace(a0, a1, n, endpoint=False)], float)


def demo_pose(t):
    """Ground-truth rig state of the demo character at time t (seconds). 6 s: idle+blink, wave+smile, walk, surprise."""
    p = {"x": 250.0, "y": 196.0, "torso": 0.0, "head": 0.0, "armL": 90.0, "armR": 90.0, "legL": 90.0, "legR": 90.0, "eye": 1.0, "mouth": "closed"}
    p["y"] += 1.5 * math.sin(2 * math.pi * t / 2.0)                       # breathing
    if 0.55 < t < 0.75 or 4.6 < t < 4.78:
        p["eye"] = 0.08                                                   # blinks
    if 1.5 <= t < 3.5:                                                    # wave: right arm up and across the face
        k = smooth((t - 1.5) / 0.45) * (1 - smooth((t - 3.1) / 0.4))
        p["armR"] = 90 - k * (215 + 22 * math.sin(2 * math.pi * (t - 1.5) * 2.2))
        p["head"] = -6 * k
        p["mouth"] = "smile" if k > 0.5 else "closed"
    if 3.5 <= t < 5.5:                                                    # walk to the right
        u = (t - 3.5) / 2.0
        ph = 2 * math.pi * (t - 3.5) * 1.6
        amp = smooth(u / 0.12) * (1 - smooth((u - 0.88) / 0.12))
        p["x"] += 210 * smooth(u)
        p["legL"] = 90 + 26 * amp * math.sin(ph); p["legR"] = 90 - 26 * amp * math.sin(ph)
        p["armL"] = 90 - 20 * amp * math.sin(ph); p["armR"] = 90 + 20 * amp * math.sin(ph)
        p["torso"] = 3 * amp
        p["y"] += -3 * amp * abs(math.sin(ph))
    if t >= 5.5:
        p["x"] += 210
        k = smooth((t - 5.5) / 0.2)
        p["eye"] = 1 + 0.25 * k
        p["mouth"] = "open" if k > 0.5 else "closed"
    return p


def demo_shapes(p):
    """[(name, colour, polygon in image px)] in paint order."""
    c = np.array([p["x"], p["y"]]); Rt = rot(math.radians(p["torso"]))
    w = lambda pts, org, R: (np.asarray(pts) @ R.T) + org
    out = []
    limb = lambda j, ang, L, th: w(capsule(L, th), c + Rt @ np.array(j), rot(math.radians(ang) + math.radians(p["torso"])))
    out += [("leg_L", DEMO["leg"], limb((-13, 37), p["legL"], 70, 18)), ("leg_R", DEMO["leg"], limb((13, 37), p["legR"], 70, 18)),
            ("arm_L", DEMO["arm"], limb((-28, -29), p["armL"], 62, 15))]
    tor = np.array([(-28, -39), (28, -39), (28, 33), (22, 39), (-22, 39), (-28, 33)], float)
    out.append(("torso", DEMO["torso"], w(tor, c, Rt)))
    Rh = rot(math.radians(p["torso"] + p["head"])); neck = c + Rt @ np.array((0, -40)); hc = neck + Rh @ np.array((0, -30))
    out.append(("head", DEMO["skin"], w(ellipse(30, 33), hc, Rh)))
    hair = np.array([q for q in ellipse(32, 35, 80) if q[1] < -9])
    out.append(("hair", DEMO["hair"], w(hair, hc, Rh)))
    for nm, ex in (("L", -11), ("R", 11)):
        out.append(("eye_" + nm, DEMO["white"], w(ellipse(6.5, max(0.6, 7.5 * p["eye"])), hc + Rh @ np.array((ex, -3)), Rh)))
        if p["eye"] > 0.3:
            out.append(("pupil_" + nm, DEMO["pupil"], w(ellipse(3, 3, 16), hc + Rh @ np.array((ex + 1, -2)), Rh)))
    m = {"closed": (9, 1.8), "smile": (11, 4.2), "open": (7, 8.5)}[p["mouth"]]
    out.append(("mouth", DEMO["mouth"], w(ellipse(*m), hc + Rh @ np.array((0, 16)), Rh)))
    out.append(("arm_R", DEMO["arm"], limb((28, -29), p["armR"], 62, 15)))
    return out


def draw_polys(size, bg_fn, shapes):
    img = Image.new("RGB", (size[0] * SS, size[1] * SS))
    d = ImageDraw.Draw(img)
    bg_fn(d, size[0] * SS, size[1] * SS)
    for _, col, poly in shapes:
        d.polygon([tuple(q) for q in (np.asarray(poly) * SS)], fill=tuple(int(v) for v in col))
    return img.resize(size, Image.LANCZOS)


def cmd_make_ref(out, seconds=6.0):
    out = Path(out); fr = out / "ref_png"; fr.mkdir(parents=True, exist_ok=True)

    def bg(d, w, h):
        d.rectangle([0, 0, w, h], fill=DEMO["bg"]); d.rectangle([0, int(h * 0.80), w, h], fill=DEMO["floor"])
    gt = []
    n = int(round(seconds * FPS))
    for i in range(n):
        p = demo_pose(i / FPS)
        draw_polys((W, H), bg, demo_shapes(p)).save(fr / f"{i:05d}.png")
        gt.append({"frame": i, "t": round(i / FPS, 5), **p})
    ffmpeg_encode(str(fr / "%05d.png"), out / "reference.mp4")
    jdump({"note": "ground truth of the demo rig; used ONLY by tests to score the tracker, never read by analyze/memory/animate", "fps": FPS, "frames": gt}, out / "ground_truth.json")
    shutil.rmtree(fr)
    print(f"reference: {out / 'reference.mp4'}  frames={n} fps={FPS} size={W}x{H}")
    return out / "reference.mp4"


# ====================================================================== 2) extract
def cmd_extract(video, work):
    work = Path(work); fd = work / "frames"
    if fd.exists():
        shutil.rmtree(fd)
    fd.mkdir(parents=True)
    pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate,nb_frames:frame=best_effort_timestamp_time",
                                    "-of", "json", str(video)], capture_output=True, text=True, check=True).stdout)
    st = pr["streams"][0]; num, den = (int(x) for x in st["r_frame_rate"].split("/"))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-fps_mode", "passthrough", str(fd / "%05d.png")], check=True)
    files = sorted(fd.glob("*.png"))
    ts = [float(f["best_effort_timestamp_time"]) for f in pr.get("frames", [])]
    if len(ts) != len(files):
        raise SystemExit(f"timestamps ({len(ts)}) != frames written ({len(files)}): the video has dropped or duplicated frames")
    for i, f in enumerate(files):                      # ffmpeg numbers from 1; keep 0-based names that match frames.json
        f.rename(fd / f"f{i:05d}.png")
    meta = {"video": str(video), "width": st["width"], "height": st["height"], "fps": num / den, "count": len(files),
            "frames": [{"frame": i, "t": round(t, 6), "file": f"frames/f{i:05d}.png"} for i, t in enumerate(ts)]}
    jdump(meta, work / "frames.json")
    print(f"extracted {len(files)} frames, {st['width']}x{st['height']} @ {num / den:g} fps, t0={ts[0]:.4f} t_last={ts[-1]:.4f}")
    return meta


def load_frame(work, f):
    return cv2.cvtColor(cv2.imread(str(Path(work) / f["file"])), cv2.COLOR_BGR2RGB)


# ====================================================================== 3) analyze
def bg_palette(img, band=6, tol=26):
    """Background colours = the colours that fill the frame border (flat-background assumption)."""
    b = np.concatenate([img[:band].reshape(-1, 3), img[-band:].reshape(-1, 3), img[:, :band].reshape(-1, 3), img[:, -band:].reshape(-1, 3)]).astype(int)
    q = (b // 8) * 8 + 4
    cols, cnt = np.unique(q, axis=0, return_counts=True)
    out = []
    for i in np.argsort(-cnt):
        if cnt[i] < 0.02 * len(b):
            break
        if all(np.abs(cols[i] - o).max() > tol for o in out):
            sel = np.abs(b - cols[i]).max(axis=1) <= 12
            out.append(b[sel].mean(axis=0) if sel.any() else cols[i].astype(float))
    return [tuple(float(v) for v in o) for o in out]


def nearest(img, pal):
    d = np.stack([np.abs(img.astype(int) - np.array(p)).sum(axis=2) for p in pal], axis=0)
    return d.argmin(axis=0), d.min(axis=0)


def fg_palette(frames_rgb, bgp, tol=34):
    """Flat colours of the character, found from the pixels that are not background. Antialiasing blends are ignored (few pixels)."""
    px = []
    for img in frames_rgb:
        _, dist = nearest(img, bgp)
        px.append(img[dist > 45])
    px = np.concatenate(px).astype(int)
    q = (px // 8) * 8 + 4
    cols, cnt = np.unique(q, axis=0, return_counts=True)
    out, n_out = [], []
    anchors = [np.array(b) for b in bgp]

    def is_blend(c, n):
        """An antialiasing / chroma-bleed colour sits on the line between two stronger flat colours."""
        known = anchors + out
        for i in range(len(known)):
            for j in range(i + 1, len(known)):
                a, b = known[i], known[j]; ab = b - a; t = float((c - a) @ ab / max(1e-9, ab @ ab))
                if 0.10 < t < 0.90 and np.linalg.norm(c - (a + t * ab)) < 16:
                    return True
        return False
    for i in np.argsort(-cnt):
        if cnt[i] < max(40, 0.0003 * len(px)):
            break
        c = cols[i].astype(float)
        if all(np.linalg.norm(c - o) > tol for o in out) and not is_blend(c, cnt[i]):
            sel = np.abs(px - cols[i]).max(axis=1) <= 10
            out.append(px[sel].mean(axis=0)); n_out.append(int(sel.sum()))
    return [tuple(float(v) for v in o) for o in out]


def components(labels, k, min_area=5):
    m = cv2.morphologyEx((labels == k).astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))      # drops 1-px ringing strips along edges
    n, lab, stats, cen = cv2.connectedComponentsWithStats(m, connectivity=8)
    out = []
    for i in range(1, n):
        a = int(stats[i, cv2.CC_STAT_AREA])
        if a >= min_area:
            x, y, w, h = (int(stats[i, j]) for j in (0, 1, 2, 3))
            out.append({"area": a, "bbox": [x, y, w, h], "c": [float(cen[i][0]), float(cen[i][1])], "mask": lab == i})
    return sorted(out, key=lambda c: -c["area"])


def pca(mask):
    ys, xs = np.nonzero(mask)
    pts = np.stack([xs, ys], 1).astype(float); c = pts.mean(0)
    ev, evec = np.linalg.eigh(np.cov((pts - c).T))
    ax = evec[:, 1]; proj = (pts - c) @ ax; minor = (pts - c) @ evec[:, 0]
    return c, ax, float(proj.min()), float(proj.max()), float(minor.max() - minor.min()), float(ev[1] / max(ev[0], 1e-6))


def limb_geom(mask, anchor):
    """Joint end (nearest the anchor), far end, angle (deg, image coords) and thickness of an elongated blob."""
    c, ax, lo, hi, thick, _ = pca(mask)
    e0, e1 = c + ax * (lo + thick / 2), c + ax * (hi - thick / 2)
    near, far = (e0, e1) if np.linalg.norm(e0 - anchor) <= np.linalg.norm(e1 - anchor) else (e1, e0)
    return near, far, math.degrees(math.atan2(far[1] - near[1], far[0] - near[0])), thick, float(hi - lo)


def fit_pose(pairs, bgmask, c0, a0, span=14.0, step=2.0, shift=6):
    """Rigid fit of a part's template to what is visible of it. pairs: [(polygon in local coords, mask of that colour)].
    Score = template∩mask − 0.6·template∩background − 0.6·mask outside the template. Pixels hidden behind another part cost
    nothing, so a half-covered part still lands where its visible edges say. Returns centre, angle (deg), coverage (0..1)."""
    Hh, Ww = bgmask.shape
    rad = int(max(np.abs(np.asarray(q)).max() for q, _ in pairs) + shift + 8)
    x0, y0 = int(max(0, c0[0] - rad)), int(max(0, c0[1] - rad)); x1, y1 = int(min(Ww, c0[0] + rad)), int(min(Hh, c0[1] + rad))
    crop = [(np.asarray(q, float), m[y0:y1, x0:x1]) for q, m in pairs]; bgc = bgmask[y0:y1, x0:x1]; off = np.array([x0, y0], float)
    tot = sum(int(m.sum()) for _, m in crop)

    def score(c, a):
        R = rot(math.radians(a)); sc = 0.0; hit = 0
        for q, m in crop:
            T = np.zeros(bgc.shape, np.uint8)
            cv2.fillPoly(T, [np.round(q @ R.T + (c - off)).astype(np.int32)], 1)
            T = T.astype(bool); h = int((T & m).sum()); hit += h
            sc += h - 0.6 * int((T & bgc).sum()) - 0.6 * (int(m.sum()) - h)
        return sc, hit
    best = (-1e18, np.asarray(c0, float), a0, 0)
    for a in np.arange(a0 - span, a0 + span + 1e-6, step):
        for dx in range(-shift, shift + 1, 2):
            for dy in range(-shift, shift + 1, 2):
                c = np.asarray(c0, float) + (dx, dy); sc, hit = score(c, a)
                if sc > best[0]:
                    best = (sc, c, a, hit)
    _, cb, ab, _ = best
    for a in np.arange(ab - step, ab + step + 1e-6, 0.5):
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                c = cb + (dx, dy); sc, hit = score(c, a)
                if sc > best[0]:
                    best = (sc, c, a, hit)
    return best[1], float(best[2]), best[3] / max(1, tot)


def fit_limb(tmpl, cmask, bgmask, jw, a_prev, prior=0.3):
    """A limb turns about its joint: one angle. tmpl is in joint-local coords (x along the limb). cmask = every pixel of the
    limb's colour (both limbs of a pair), so no left/right bookkeeping is needed; the joint tells them apart.
    Score = template∩colour − 0.6·template∩background − prior·|turn since the last frame|. Returns angle (deg), visible fraction."""
    Hh, Ww = bgmask.shape; tmpl = np.asarray(tmpl, float)
    rad = int(np.abs(tmpl).max() + 6)
    x0, y0 = int(max(0, jw[0] - rad)), int(max(0, jw[1] - rad)); x1, y1 = int(min(Ww, jw[0] + rad)), int(min(Hh, jw[1] + rad))
    M = cmask[y0:y1, x0:x1]; B = bgmask[y0:y1, x0:x1]; org = np.asarray(jw, float) - (x0, y0)

    def score(a):
        T = np.zeros(M.shape, np.uint8)
        cv2.fillPoly(T, [np.round(tmpl @ rot(math.radians(a)).T + org).astype(np.int32)], 1)
        T = T.astype(bool); hit = int((T & M).sum()); n = max(1, int(T.sum()))
        d = abs((a - a_prev + 180) % 360 - 180) if a_prev is not None else 0.0
        return hit - 0.6 * int((T & B).sum()) - prior * d, hit / n
    best = max(((score(a), a) for a in np.arange(0, 360, 6.0)), key=lambda x: x[0][0])
    for step, span in ((1.0, 6.0), (0.25, 1.0)):
        best = max(((score(a), a) for a in np.arange(best[1] - span, best[1] + span + 1e-6, step)), key=lambda x: x[0][0])
    return float((best[1] + 180) % 360 - 180), float(best[0][1])


def classify_frame(img, bgp, fgp):
    lab, dist = nearest(img, list(bgp) + list(fgp))
    lab = lab.copy(); nb = len(bgp)
    return lab, nb


def name_parts(lab, nb, fgp):
    """Give the colour blobs of a clean standing frame their names. Returns {part: {'k': palette index, 'side': None|'L'|'R'}}."""
    comps = {k: components(lab, nb + k) for k in range(len(fgp))}
    allm = cv2.morphologyEx(cv2.morphologyEx((lab >= nb).astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)), cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    n_, cc, st_, _ = cv2.connectedComponentsWithStats(allm, connectivity=8)
    big_i = 1 + int(np.argmax(st_[1:, cv2.CC_STAT_AREA])); x0, y0 = int(st_[big_i, 0]), int(st_[big_i, 1]); x1, y1 = x0 + int(st_[big_i, 2]), y0 + int(st_[big_i, 3]); hgt = y1 - y0
    for k in comps:                                                 # only blobs that belong to the character
        comps[k] = [c for c in comps[k] if x0 - 3 <= c["c"][0] <= x1 + 3 and y0 - 3 <= c["c"][1] <= y1 + 3]
    big = sorted(((c[0]["area"], k) for k, c in comps.items() if c), reverse=True)
    roles = {}
    def band(c):
        return (c["c"][1] - y0) / hgt
    two = {k: c[:2] for k, c in comps.items() if len(c) >= 2 and c[1]["area"] > 0.12 * c[0]["area"]}      # a back arm can show only a sliver
    legs = max((k for k in two if band(two[k][0]) > 0.62), key=lambda k: two[k][0]["area"], default=None)
    arms = max((k for k in two if k != legs and 0.28 < band(two[k][0]) < 0.72 and two[k][0]["area"] > 120 and abs(two[k][0]["c"][0] - two[k][1]["c"][0]) > 0.12 * hgt), key=lambda k: two[k][0]["area"], default=None)
    singles = [k for _, k in big if k not in (legs, arms)]
    torso = next((k for k in singles if 0.33 < band(comps[k][0]) < 0.72), None)
    head = next((k for k in singles if k != torso and band(comps[k][0]) < 0.36 and comps[k][0]["area"] > 300), None)
    if None in (legs, arms, torso, head):
        raise SystemExit(f"could not name the parts in the rest frame (legs={legs} arms={arms} torso={torso} head={head}); see SKILL.md > limits")
    hb = comps[head][0]["bbox"]; hx0, hy0, hx1, hy1 = hb[0], hb[1], hb[0] + hb[2], hb[1] + hb[3]
    inside = lambda c: hx0 - 4 <= c["c"][0] <= hx1 + 4 and hy0 - 0.6 * hb[3] <= c["c"][1] <= hy1 + 4      # a hair cap sits above the visible skin
    rest = [k for k in singles if k not in (torso, head)]
    hair = next((k for k in rest if comps[k] and inside(comps[k][0]) and comps[k][0]["c"][1] < comps[head][0]["c"][1] and comps[k][0]["area"] > 120), None)
    small2 = [k for k in two if k not in (legs, arms) and all(inside(c) for c in two[k])]
    eyes = max(small2, key=lambda k: sum(fgp[k]), default=None)                      # the brighter pair
    def in_eyes(k):                                                 # a pupil pair sits inside the two eye blobs
        if eyes is None:
            return False
        boxes = [c["bbox"] for c in two[eyes]]
        return all(any(b[0] - 2 <= c["c"][0] <= b[0] + b[2] + 2 and b[1] - 2 <= c["c"][1] <= b[1] + b[3] + 2 for b in boxes) for c in two[k])
    pupils = min((k for k in small2 if k != eyes and in_eyes(k)), key=lambda k: sum(fgp[k]), default=None)        # the darkest such pair
    mouth = next((k for k in rest if k not in (hair, eyes, pupils) and comps[k] and inside(comps[k][0]) and comps[k][0]["c"][1] > comps[head][0]["c"][1]), None)
    roles = {"torso": torso, "head": head, "hair": hair, "mouth": mouth, "arm": arms, "leg": legs, "eye": eyes, "pupil": pupils}
    return roles


SINGLE = ("torso", "head", "hair", "mouth")
PAIRED = ("arm", "leg", "eye", "pupil")


def cmd_analyze(work):
    work = Path(work); meta = jload(work / "frames.json"); F = meta["frames"]
    sample = [load_frame(work, F[i]) for i in np.linspace(0, len(F) - 1, min(16, len(F))).astype(int)]
    bgp = bg_palette(sample[0]); fgp = fg_palette(sample, bgp)
    labs = [classify_frame(img, bgp, fgp)[0] for img in sample]                 # keep only colours that form a real blob somewhere
    fgp = [c for k, c in enumerate(fgp) if any(components(l, len(bgp) + k, 10) for l in labs)]
    lab0, nb = classify_frame(load_frame(work, F[0]), bgp, fgp)
    roles = name_parts(lab0, nb, fgp)
    tracks, prev = [], {}
    med_area = {}
    for f in F:
        img = load_frame(work, f); lab, _ = classify_frame(img, bgp, fgp)
        row = {"frame": f["frame"], "t": f["t"], "parts": {}, "_bg": lab < nb, "_lab": lab.astype(np.uint8)}
        tc = None
        for nm in SINGLE:
            k = roles.get(nm)
            cs = components(lab, nb + k) if k is not None else []
            if not cs:
                row["parts"][nm] = {"present": False}
                continue
            c = cs[0]
            if nm == "mouth" and "head" in row["parts"] and row["parts"]["head"].get("present"):   # the mouth blob nearest the expected place
                c = cs[0]
            row["parts"][nm] = {"present": True, "c": c["c"], "area": c["area"], "bbox": c["bbox"], "_mask": c["mask"]}
        for nm in PAIRED:
            k = roles.get(nm)
            cs = (components(lab, nb + k, 3)[:2]) if k is not None else []
            keyL, keyR = nm + "_L", nm + "_R"
            if len(cs) == 2:
                a, b = cs
                if keyL in prev and keyR in prev:                       # keep identities by continuity, not by x order (legs cross)
                    d_keep = np.hypot(*(np.array(a["c"]) - prev[keyL])) + np.hypot(*(np.array(b["c"]) - prev[keyR]))
                    d_swap = np.hypot(*(np.array(a["c"]) - prev[keyR])) + np.hypot(*(np.array(b["c"]) - prev[keyL]))
                    L, R = (a, b) if d_keep <= d_swap else (b, a)
                else:
                    L, R = (a, b) if a["c"][0] <= b["c"][0] else (b, a)
                for key, c in ((keyL, L), (keyR, R)):
                    row["parts"][key] = {"present": True, "c": c["c"], "area": c["area"], "bbox": c["bbox"], "_mask": c["mask"]}
                    prev[key] = np.array(c["c"])
            elif len(cs) == 1:                                           # one blob: merged pair, or one of them hidden
                c = cs[0]
                both = keyL in med_area and c["area"] > 1.45 * med_area[keyL]
                for key in (keyL, keyR):
                    near = key not in prev or np.hypot(*(np.array(c["c"]) - prev[key])) < 40
                    if both or near and (key == min((keyL, keyR), key=lambda q: np.hypot(*(np.array(c["c"]) - prev.get(q, np.array(c["c"])))))):
                        row["parts"][key] = {"present": True, "merged": bool(both), "c": c["c"], "area": c["area"] / (2 if both else 1), "bbox": c["bbox"], "_mask": c["mask"]}
                        if not both:
                            prev[key] = np.array(c["c"])
                    else:
                        row["parts"][key] = {"present": False}
            else:
                row["parts"][keyL] = {"present": False}; row["parts"][keyR] = {"present": False}
        tracks.append(row)
        if len(tracks) == min(12, len(F)):                                # reference areas from the first clean frames
            for key in tracks[0]["parts"]:
                v = [r["parts"][key]["area"] for r in tracks if r["parts"][key].get("present")]
                if v:
                    med_area[key] = float(np.median(v))
    # geometry pass: torso frame, joints, limb angles, head tilt, expressions, confidence
    for key in tracks[0]["parts"]:
        v = [r["parts"][key]["area"] for r in tracks if r["parts"][key].get("present") and not r["parts"][key].get("merged")]
        med_area[key] = float(np.percentile(v, 90)) if v else 0.0
    joints_local = {k: [] for k in ("arm_L", "arm_R", "leg_L", "leg_R")}
    full = lambda key, r: r["parts"][key].get("present") and r["parts"][key]["area"] >= 0.97 * med_area[key]
    t_star = max(range(len(tracks)), key=lambda i: tracks[i]["parts"]["torso"].get("area", 0))    # the frame that shows the most torso: its own axis is the unbiased reference
    T0 = tracks[t_star]["parts"]["torso"]; c0, ax0, lo0, hi0, th0, _ = pca(T0["_mask"])
    # orientation of the reference frame: the long side of the tightest box around the torso's hull. PCA is pulled off-axis by
    # the bite a front arm takes out of one shoulder (measured: -4.4 deg on the demo); straight edges are not.
    ys_, xs_ = np.nonzero(T0["_mask"]); box = cv2.boxPoints(cv2.minAreaRect(cv2.convexHull(np.stack([xs_, ys_], 1).astype(np.float32))))
    e1, e2 = box[1] - box[0], box[2] - box[1]; ax0 = e1 if np.linalg.norm(e1) >= np.linalg.norm(e2) else e2
    if ax0[1] < 0:
        ax0 = -ax0                                                      # torso axis points down
    ang0 = math.degrees(math.atan2(ax0[1], ax0[0])) - 90
    hi0, lo0, th0 = float(max(np.linalg.norm(e1), np.linalg.norm(e2))), 0.0, float(min(np.linalg.norm(e1), np.linalg.norm(e2)))
    tor_poly = np.array(local_poly(T0["_mask"], c0, ang0, hull=True)); prev_a = ang0
    vis = lambda key, r: (r["parts"][key]["area"] / max(med_area[key], 1)) if r["parts"][key].get("present") else 0.0
    h_star = max(range(len(tracks)), key=lambda i: (round(min(vis("head", tracks[i]), vis("hair", tracks[i]) if roles.get("hair") is not None else 1.0), 2), -i))   # the frame that shows the most head and hair
    skin = lambda r: np.logical_or.reduce([r["parts"][k]["_mask"] for k in ("head", "eye_L", "eye_R", "pupil_L", "pupil_R", "mouth") if r["parts"][k].get("_mask") is not None])
    for r in tracks:
        P = r["parts"]; t = P["torso"]
        if not t.get("present"):
            continue
        cfit, ang, cov = fit_pose([(tor_poly, t["_mask"])], r["_bg"], np.array(t["c"]), prev_a)
        prev_a = ang
        t.update(c_blob=t["c"], c=[float(cfit[0]), float(cfit[1])], angle=round(ang, 3), height=round(hi0 - lo0, 2), width=round(th0, 2), fit_coverage=round(cov, 3))
        Rt = rot(math.radians(ang))
        for key in joints_local:
            q = P[key]
            if q.get("present") and not q.get("merged"):
                near, far, a, th, ln = limb_geom(q["_mask"], np.array(t["c"]))
                q.update(near=[float(near[0]), float(near[1])], far=[float(far[0]), float(far[1])], angle_raw=round(a, 3), thick=round(th, 2), length=round(ln, 2))
                if q["area"] > 0.9 * med_area[key]:
                    joints_local[key].append(Rt.T @ (near - np.array(t["c"])))
    J = {k: (np.median(np.array(v), axis=0), np.array(v).std(axis=0)) for k, v in joints_local.items() if len(v) >= 3}
    limb_tmpl, prev_la = {}, {}
    for key, (jl, _) in J.items():                                 # each limb's shape, from its earliest fully visible frame
        i = next((i for i, r in enumerate(tracks) if "far" in r["parts"][key] and r["parts"][key]["area"] >= 0.95 * med_area[key]), None)
        if i is None:
            continue
        q = tracks[i]["parts"][key]; t = tracks[i]["parts"]["torso"]; jw = np.array(t["c"]) + rot(math.radians(t["angle"])) @ jl
        far, near = np.array(q["far"]), np.array(q["near"]); tip = far if np.linalg.norm(far - jw) >= np.linalg.norm(near - jw) else near
        a_abs = math.degrees(math.atan2(tip[1] - jw[1], tip[0] - jw[0]))
        limb_tmpl[key] = np.array(local_poly(q["_mask"], jw, a_abs)); prev_la[key] = a_abs
    for r in tracks:
        P = r["parts"]; t = P["torso"]
        if not t.get("present"):
            continue
        Rt = rot(math.radians(t["angle"]))
        for key, (jl, _) in J.items():
            q = P[key]
            jw = np.array(t["c"]) + Rt @ jl
            if key not in limb_tmpl:
                q["conf"] = 0.0
                continue
            a_abs, vis = fit_limb(limb_tmpl[key], r["_lab"] == nb + roles[key[:-2]], r["_bg"], jw, prev_la[key])
            if vis >= 0.5:
                prev_la[key] = a_abs
            q["angle"] = round((a_abs - t["angle"] + 180) % 360 - 180, 3)                # relative to the torso
            q["conf"] = round(vis, 3); q["joint_world"] = [round(float(jw[0]), 2), round(float(jw[1]), 2)]
        for key in ("eye_L", "eye_R", "pupil_L", "pupil_R", "mouth", "head", "hair", "torso"):
            q = P[key]
            q["conf"] = round(min(1.0, q["area"] / max(med_area.get(key, 1), 1)), 3) if q.get("present") else 0.0
    Hs = tracks[h_star]["parts"]; a_ref = Hs["torso"]["angle"]; hc0 = np.array(Hs["head"]["c"])
    head_poly = np.array(local_poly(skin(tracks[h_star]), hc0, a_ref, hull=True))
    hair_poly = np.array(local_poly(Hs["hair"]["_mask"], hc0, a_ref)) if Hs["hair"].get("_mask") is not None else None
    prev_h = a_ref
    for r in tracks:                                              # head = skin blob + hair cap fitted together (the cap gives the tilt)
        P = r["parts"]; h = P["head"]
        if not h.get("present"):
            continue
        pairs = [(head_poly, skin(r))] + ([(hair_poly, P["hair"]["_mask"])] if hair_poly is not None and P["hair"].get("present") else [])
        cfit, ang, cov = fit_pose(pairs, r["_bg"], np.array(h["c"]), prev_h, span=16.0)
        prev_h = ang
        h.update(c_blob=h["c"], c=[float(cfit[0]), float(cfit[1])], fit_coverage=round(cov, 3), tilt_raw=ang - P["torso"].get("angle", 0.0))
    tilt0 = np.median([r["parts"]["head"]["tilt_raw"] for r in tracks[:8] if "tilt_raw" in r["parts"]["head"]])
    eye_h = np.percentile([r["parts"][k]["bbox"][3] for r in tracks for k in ("eye_L", "eye_R") if r["parts"][k].get("present")], 80)
    mo = [(r["parts"]["mouth"]["bbox"][2], r["parts"]["mouth"]["bbox"][3]) for r in tracks if r["parts"]["mouth"].get("present")]
    mh_closed = np.percentile([h for _, h in mo], 20)
    for r in tracks:
        P = r["parts"]; h = P["head"]
        if "tilt_raw" in h:
            h["tilt"] = round(h.pop("tilt_raw") - tilt0, 3)
    eye_local = {}
    for k in ("eye_L", "eye_R"):                                  # where each eye sits on the head, from the first clean frames
        v = [rot(math.radians(r["parts"]["torso"]["angle"] + r["parts"]["head"].get("tilt", 0))).T @ (np.array(r["parts"][k]["c"]) - np.array(r["parts"]["head"]["c"]))
             for r in tracks[:10] if r["parts"][k].get("present") and r["parts"]["head"].get("present")]
        if v:
            eye_local[k] = np.median(np.array(v), axis=0)
    for r in tracks:
        P = r["parts"]; h = P["head"]
        vis = [P[k]["bbox"][3] for k in ("eye_L", "eye_R") if P[k].get("present")]
        occ = []
        for k, el in eye_local.items():                           # an eye that is not seen is either shut or behind something: look what is on top of its place
            if not P[k].get("present") and h.get("present"):
                ew = np.array(h["c"]) + rot(math.radians(P["torso"]["angle"] + h.get("tilt", 0))) @ el
                x, y = int(round(ew[0])), int(round(ew[1]))
                for a in ("arm_L", "arm_R"):
                    m = P[a].get("_mask")
                    if m is not None and m[max(0, y - 4):y + 5, max(0, x - 4):x + 5].any():
                        occ.append(k); P[k]["occluded_by"] = a
        e = {"openness": round(float(np.mean(vis) / eye_h), 3) if vis else None, "eyes_visible": len(vis), "eyes_occluded": occ}
        if vis:
            e["eyes"] = "closed" if e["openness"] < 0.45 else "wide" if e["openness"] > 1.13 else "open"
        else:
            e["eyes"] = None if len(occ) == len(eye_local) else "closed"       # hidden by an arm = unknown; simply not there = lids shut (thinner than the 2-px floor)
        m = P["mouth"]
        if m.get("present"):
            mw, mhh = m["bbox"][2], m["bbox"][3]
            e["mouth"] = "open" if mhh >= 2.2 * mh_closed and mhh >= 0.8 * mw else "smile" if mhh >= 1.4 * mh_closed else "closed"
            e["mouth_wh"] = [mw, mhh]
        else:
            e["mouth"] = None
        r["expr"] = e
    out = {"version": VERSION, "size": [meta["width"], meta["height"]], "fps": meta["fps"], "bg_palette": bgp, "fg_palette": fgp, "roles": roles, "ref_area": med_area,
           "joints_local": {k: {"xy": [round(float(v), 3) for v in jl], "std": [round(float(v), 3) for v in sd]} for k, (jl, sd) in J.items()},
           "frames": [{"frame": r["frame"], "t": r["t"], "expr": r["expr"],
                       "parts": {k: {kk: vv for kk, vv in v.items() if not kk.startswith("_")} for k, v in r["parts"].items()}} for r in tracks]}
    jdump(out, work / "tracks.json")
    pres = {k: sum(1 for r in tracks if r["parts"][k].get("present")) for k in tracks[0]["parts"]}
    print(f"analyzed {len(tracks)} frames · bg colours {len(bgp)} · character colours {len(fgp)} · parts named: {sorted(k for k, v in roles.items() if v is not None)}")
    print("frames where each part was seen:", pres)
    return out, tracks


# ====================================================================== 4) redraw (auto rotoscope) + metrics
def ssim(a, b):
    a = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY).astype(np.float64); b = cv2.cvtColor(b, cv2.COLOR_RGB2GRAY).astype(np.float64)
    g = lambda x: cv2.GaussianBlur(x, (11, 11), 1.5)
    mu_a, mu_b = g(a), g(b)
    va, vb, cab = g(a * a) - mu_a ** 2, g(b * b) - mu_b ** 2, g(a * b) - mu_a * mu_b
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    return float((((2 * mu_a * mu_b + c1) * (2 * cab + c2)) / ((mu_a ** 2 + mu_b ** 2 + c1) * (va + vb + c2))).mean())


def psnr(a, b):
    mse = float(((a.astype(np.float64) - b.astype(np.float64)) ** 2).mean())
    return 99.0 if mse == 0 else 10 * math.log10(255 ** 2 / mse)


def cmd_redraw(work, eps=0.45):
    work = Path(work); meta = jload(work / "frames.json"); tr = jload(work / "tracks.json")
    pal = [tuple(p) for p in tr["bg_palette"]] + [tuple(p) for p in tr["fg_palette"]]; nb = len(tr["bg_palette"])
    out_png, out_svg = work / "redraw_png", work / "redraw_svg"
    for d in (out_png, out_svg):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir()
    Wd, Hd = tr["size"]; rows = []; prev_c = None
    for f in meta["frames"]:
        img = load_frame(work, f); lab, _ = nearest(img, pal)
        canvas = np.zeros((Hd * SS, Wd * SS, 3), np.uint8); svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {Wd} {Hd}" width="{Wd}" height="{Hd}">']
        npts = 0
        for k in list(range(nb)) + sorted(range(nb, len(pal)), key=lambda k: -(lab == k).sum()):      # background first, then big regions under small ones
            m = (lab == k).astype(np.uint8)
            if not m.any():
                continue
            cs, hier = cv2.findContours(cv2.resize(m, (Wd * SS, Hd * SS), interpolation=cv2.INTER_NEAREST), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
            cs = [cv2.approxPolyDP(c, eps * SS, True) for c in cs]
            keep = [i for i, c in enumerate(cs) if len(c) >= 3]
            col = tuple(int(round(v)) for v in pal[k])
            cv2.drawContours(canvas, cs, -1, col, cv2.FILLED, cv2.LINE_8, hier)
            d = " ".join("M" + " L".join(f"{p[0][0] / SS:.2f},{p[0][1] / SS:.2f}" for p in cs[i]) + " Z" for i in keep)
            svg.append(f'<path fill="rgb{col}" fill-rule="evenodd" d="{d}"/>'); npts += sum(len(cs[i]) for i in keep)
        svg.append("</svg>")
        (out_svg / f"f{f['frame']:05d}.svg").write_text("\n".join(svg), encoding="utf-8")
        red = cv2.resize(canvas, (Wd, Hd), interpolation=cv2.INTER_AREA)
        cv2.imwrite(str(out_png / f"{f['frame']:05d}.png"), cv2.cvtColor(red, cv2.COLOR_RGB2BGR))
        fg_ref = lab >= nb; lab2, _ = nearest(red, pal); fg_red = lab2 >= nb
        iou = float((fg_ref & fg_red).sum() / max(1, (fg_ref | fg_red).sum()))
        ys, xs = np.nonzero(fg_red); c = np.array([xs.mean(), ys.mean()]); ys, xs = np.nonzero(fg_ref); c0 = np.array([xs.mean(), ys.mean()])
        rows.append({"frame": f["frame"], "psnr": round(psnr(img, red), 2), "ssim": round(ssim(img, red), 4), "fg_iou": round(iou, 4), "points": npts,
                     "centroid_err_px": round(float(np.linalg.norm(c - c0)), 3)})
    ffmpeg_encode(str(out_png / "%05d.png"), work / "redraw.mp4", tr["fps"])
    agg = lambda k: {"mean": round(float(np.mean([r[k] for r in rows])), 4), "min": round(float(np.min([r[k] for r in rows])), 4), "max": round(float(np.max([r[k] for r in rows])), 4)}
    rep = {"what": "every frame redrawn as flat vector regions (SVG paths) and rasterised again; compared with the reference frame it came from",
           "frames": len(rows), "psnr_db": agg("psnr"), "ssim": agg("ssim"), "fg_iou": agg("fg_iou"), "centroid_err_px": agg("centroid_err_px"),
           "vector_points_per_frame": agg("points"), "per_frame": rows}
    jdump(rep, work / "redraw_report.json")
    print(f"redraw: {len(rows)} frames · PSNR mean {rep['psnr_db']['mean']} dB (min {rep['psnr_db']['min']}) · SSIM mean {rep['ssim']['mean']} (min {rep['ssim']['min']}) · "
          f"silhouette IoU mean {rep['fg_iou']['mean']} (min {rep['fg_iou']['min']}) · {int(rep['vector_points_per_frame']['mean'])} vector points/frame")
    return rep


# ====================================================================== 5) character memory
def local_poly(mask, origin, angle_deg, hull=False, eps=0.6):
    big = cv2.resize(mask.astype(np.uint8) * 255, None, fx=SS, fy=SS, interpolation=cv2.INTER_LINEAR)
    big = (cv2.GaussianBlur(big, (0, 0), SS * 0.6) > 127).astype(np.uint8)          # smooth the pixel staircase before tracing
    cs, _ = cv2.findContours(big, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cs, key=cv2.contourArea)
    if hull:
        c = cv2.convexHull(c)
    c = cv2.approxPolyDP(c, eps * SS, True)[:, 0, :].astype(float) / SS
    return [[round(float(v), 2) for v in p] for p in ((c - np.asarray(origin)) @ rot(math.radians(angle_deg)))]      # world -> local = R^T, written as row-vector product


def head_box(parts):
    """Bounding box (w, h) of the whole head: the skin blob together with the hair cap when there is one."""
    bs = [parts[k]["bbox"] for k in ("head", "hair") if parts[k].get("present")]
    if not bs:
        return None
    x0, y0 = min(b[0] for b in bs), min(b[1] for b in bs); x1, y1 = max(b[0] + b[2] for b in bs), max(b[1] + b[3] for b in bs)
    return float(x1 - x0), float(y1 - y0)


def segments(flags):
    out, s = [], None
    for i, f in enumerate(flags + [False]):
        if f and s is None:
            s = i
        if not f and s is not None:
            out.append((s, i - 1)); s = None
    return out


def cmd_memory(work, out_json, name="character"):
    work = Path(work); tr, tracks = cmd_analyze(work)                        # re-run to have the masks in memory
    fps = tr["fps"]; fr = tr["frames"]; n = len(fr)
    pal = tr["fg_palette"]; roles = tr["roles"]
    col = lambda role: [int(round(v)) for v in pal[roles[role]]]
    P0 = lambda i, k: tracks[i]["parts"][k]
    def best(key, pred=lambda q: True):
        c = [(q["conf"], i) for i, r in enumerate(tracks) if (q := r["parts"][key]).get("present") and not q.get("merged") and "c" in q and pred(q)]
        if not c:
            return None
        clean = [i for v, i in c if v >= 0.95]                    # the earliest fully visible frame (closest to the rest pose), not just any full one
        return clean[0] if clean else max(c)[1]
    th = float(np.median([r["parts"]["torso"]["height"] for r in fr if r["parts"]["torso"].get("present")]))       # the ruler: torso height
    parts, src = {}, {}
    i = best("torso"); t = P0(i, "torso")
    parts["torso"] = {"parent": None, "color": col("torso"), "z": 30, "template": local_poly(t["_mask"], t["c"], t["angle"], hull=True), "template_frame": i, "hull": True,
                      "size": {"height": round(th, 2), "width": float(np.median([r["parts"]["torso"]["width"] for r in fr if r["parts"]["torso"].get("present")]))}, "confidence": t["conf"]}
    zmap = {"leg_L": 10, "leg_R": 11, "arm_L": 20, "arm_R": 90}
    # paint order is measured, not assumed: an arm is in front of the torso if it stays whole while it overlaps the torso's area
    for key in ("arm_L", "arm_R"):
        inside = [r["parts"][key]["conf"] for r in fr if r["parts"][key].get("present") and "far" in r["parts"][key]
                  and abs(r["parts"][key]["c"][0] - r["parts"]["torso"]["c"][0]) < parts["torso"]["size"]["width"] * 0.42]
        if len(inside) >= 3:
            zmap[key] = 90 if np.median(inside) > 0.8 else 20
        src["z_" + key] = {"frames_overlapping_torso": len(inside), "median_visible_fraction": round(float(np.median(inside)), 3) if inside else None}
    for key in ("arm_L", "arm_R", "leg_L", "leg_R"):
        i = best(key, lambda q: "far" in q)
        q = P0(i, key); tor = P0(i, "torso"); jl = np.array(tr["joints_local"][key]["xy"])
        jw = np.array(tor["c"]) + rot(math.radians(tor["angle"])) @ jl
        absang = q["angle"] + tor["angle"]
        lens = [r["parts"][key]["length"] for r in fr if r["parts"][key].get("conf", 0) > 0.9 and "length" in r["parts"][key]]
        parts[key] = {"parent": "torso", "color": col(key[:-2]), "z": zmap[key], "joint_in_parent": [round(float(v), 2) for v in jl], "joint_std_px": tr["joints_local"][key]["std"],
                      "template": local_poly(q["_mask"], jw, absang), "template_frame": i, "length": round(float(np.median(lens)), 2), "thickness": q["thick"],
                      "rest_angle": round(float(np.median([r["parts"][key]["angle"] for r in fr[:8] if "angle" in r["parts"][key]])), 2),
                      "confidence": round(min(1.0, q["conf"]) * (1.0 if max(tr["joints_local"][key]["std"]) < 2.5 else 0.6), 3)}
    i = best("head"); h = P0(i, "head"); tor = P0(i, "torso"); Rt = rot(math.radians(tor["angle"]))
    head_local = [np.array(r["parts"]["head"]["c"]) - np.array(r["parts"]["torso"]["c"]) for r in fr[:10] if r["parts"]["head"].get("present")]
    neck = np.array([0.0, -th / 2]); hoff = np.median(np.array(head_local), axis=0) - neck
    parts["head"] = {"parent": "torso", "color": col("head"), "z": 40, "joint_in_parent": [0.0, round(-th / 2, 2)], "center_from_joint": [round(float(v), 2) for v in hoff],
                     "template": local_poly(h["_mask"], h["c"], tor["angle"] + h.get("tilt", 0), hull=True), "template_frame": i, "hull": True,
                     "size": {"height": float(np.median([head_box(r["parts"])[1] for r in fr[:10] if head_box(r["parts"])])),
                              "width": float(np.median([head_box(r["parts"])[0] for r in fr[:10] if head_box(r["parts"])])), "measured": "skin + hair, first 10 frames"},
                     "confidence": h["conf"]}
    def face(key, role, z, frame, hull=False):
        q = P0(frame, key); hh = P0(frame, "head"); a = P0(frame, "torso")["angle"] + hh.get("tilt", 0)
        return {"parent": "head", "color": col(role), "z": z, "template": local_poly(q["_mask"], hh["c"], a, hull=hull), "template_frame": frame, "confidence": q["conf"]}
    if roles.get("hair") is not None:
        parts["hair"] = face("hair", "hair", 50, best("hair"))
    expr_obs = {"eyes": {}, "mouth": {}}
    for st in ("open", "wide"):
        c = [(min(r["parts"]["eye_L"]["conf"], r["parts"]["eye_R"]["conf"]), k) for k, r in enumerate(fr) if r["expr"]["eyes"] == st and r["expr"]["eyes_visible"] == 2]
        if c:
            k = max(c)[1]
            ent = {"observed": True, "frames_seen": len(c), "source_frame": k, "shape_source": "traced from the source frame",
                   "shapes": {e: face(e, "eye", 60, k)["template"] for e in ("eye_L", "eye_R")}}
            if roles.get("pupil") is not None:
                ent["shapes"].update({p: face(p, "pupil", 70, k)["template"] for p in ("pupil_L", "pupil_R") if P0(k, p).get("present")})
            expr_obs["eyes"][st] = ent
    shut = [k for k, r in enumerate(fr) if r["expr"]["eyes"] == "closed"]
    if shut and "open" in expr_obs["eyes"]:                        # the blink was seen, but shut lids are thinner than the tracker can trace
        flat = {}
        for e in ("eye_L", "eye_R"):
            p = np.array(expr_obs["eyes"]["open"]["shapes"][e]); cy = p[:, 1].mean()
            flat[e] = [[round(float(x), 2), round(float(cy + (y - cy) * 0.12), 2)] for x, y in p]
        expr_obs["eyes"]["closed"] = {"observed": True, "frames_seen": len(shut), "source_frame": shut[0], "shapes": flat,
                                      "shape_source": "the blink was observed; its lid shape is the open eye flattened to 12 % (estimated shape)"}
    for st in ("closed", "smile", "open"):
        c = [(r["parts"]["mouth"]["area"], k) for k, r in enumerate(fr) if r["expr"]["mouth"] == st]
        if c:
            k = sorted(c)[len(c) // 2][1]
            expr_obs["mouth"][st] = {"observed": True, "frames_seen": len(c), "source_frame": k, "shapes": {"mouth": face("mouth", "mouth", 80, k)["template"]}}
    # pose track (what the rig needs per frame), with holes filled by interpolation and marked as such
    keys = ["arm_L", "arm_R", "leg_L", "leg_R"]
    A = {k: np.array([r["parts"][k].get("angle", np.nan) if r["parts"][k].get("conf", 0) >= 0.5 else np.nan for r in fr], float) for k in keys}
    filled = {}
    for k in keys:
        nanm = np.isnan(A[k]); filled[k] = int(nanm.sum())
        if nanm.any() and (~nanm).any():
            A[k][nanm] = np.interp(np.flatnonzero(nanm), np.flatnonzero(~nanm), A[k][~nanm])
    tx = np.array([r["parts"]["torso"]["c"][0] for r in fr]); ty = np.array([r["parts"]["torso"]["c"][1] for r in fr]); ta = np.array([r["parts"]["torso"]["angle"] for r in fr])
    tilt = np.array([r["parts"]["head"].get("tilt", np.nan) if r["parts"]["head"].get("fit_coverage", 0) >= 0.93 and not r["expr"].get("eyes_occluded") else np.nan for r in fr], float)
    head_interp = np.isnan(tilt); filled["head"] = int(head_interp.sum())
    if head_interp.any() and (~head_interp).any():
        tilt[head_interp] = np.interp(np.flatnonzero(head_interp), np.flatnonzero(~head_interp), tilt[~head_interp])
    ground = float(np.percentile([r["parts"][k]["bbox"][1] + r["parts"][k]["bbox"][3] for r in fr for k in ("leg_L", "leg_R") if r["parts"][k].get("present")], 90))
    track = [{"frame": r["frame"], "t": r["t"], "x": round(float(tx[i]), 2), "y": round(float(ty[i]), 2), "torso": round(float(ta[i]), 2), "head": round(float(tilt[i]), 2),
              **{k: round(float(A[k][i]), 2) for k in keys}, "eyes": r["expr"]["eyes"], "mouth": r["expr"]["mouth"],
              "interpolated": [k for k in keys if not (r["parts"][k].get("conf", 0) >= 0.5 and "angle" in r["parts"][k])] + (["head"] if head_interp[i] else [])} for i, r in enumerate(fr)]
    # actions seen in the video
    vx = np.gradient(tx) * fps
    walk = [abs(v) > 0.25 * th for v in np.convolve(vx, np.ones(5) / 5, "same")]
    up = {k: [(A[k][i] - parts[k]["rest_angle"] + 180) % 360 - 180 for i in range(n)] for k in ("arm_L", "arm_R")}
    wave = [max(abs(up["arm_L"][i]), abs(up["arm_R"][i])) > 70 and not walk[i] for i in range(n)]
    timeline, clips = [], {}
    for nm, fl in (("walk", walk), ("wave", wave)):
        for s, e in segments(list(fl)):
            if e - s + 1 >= int(0.35 * fps):
                timeline.append({"action": nm, "from_frame": s, "to_frame": e, "from_t": fr[s]["t"], "to_t": fr[e]["t"], "observed": True})
    for s, e in segments([r["expr"]["eyes"] == "closed" for r in fr]):
        timeline.append({"action": "blink", "from_frame": s, "to_frame": e, "from_t": fr[s]["t"], "to_t": fr[e]["t"], "observed": True})
    for s, e in segments([not (walk[i] or wave[i]) for i in range(n)]):
        if e - s + 1 >= int(0.4 * fps):
            timeline.append({"action": "idle", "from_frame": s, "to_frame": e, "from_t": fr[s]["t"], "to_t": fr[e]["t"], "observed": True})
    timeline.sort(key=lambda a: a["from_frame"])
    for seg in [a for a in timeline if a["action"] == "walk"][:1]:           # one clean walk cycle, by the leg-angle zero crossings
        s, e = seg["from_frame"], seg["to_frame"]; d = A["leg_L"][s:e + 1] - A["leg_R"][s:e + 1]
        zc = [i for i in range(1, len(d)) if d[i - 1] < 0 <= d[i]]
        if len(zc) >= 2:
            a, b = s + zc[0], s + zc[1]
            ph = np.linspace(a, b, 17)[:-1]
            clips["walk_cycle"] = {"observed": True, "source_frames": [int(a), int(b)], "period_s": round((b - a) / fps, 4), "stride_px": round(float(abs(tx[b] - tx[a])), 2),
                                   "direction": 1 if tx[b] > tx[a] else -1, "phases": 16,
                                   "keys": {k: [round(float(np.interp(p, np.arange(n), A[k])), 2) for p in ph] for k in keys},
                                   "bob": [round(float(np.interp(p, np.arange(n), ty) - np.mean(ty[a:b])), 2) for p in ph], "torso": round(float(np.median(ta[a:b])), 2)}
    for seg in [a for a in timeline if a["action"] == "wave"][:1]:
        s, e = seg["from_frame"], seg["to_frame"]; arm = "arm_L" if np.abs(up["arm_L"][s:e + 1]).max() > np.abs(up["arm_R"][s:e + 1]).max() else "arm_R"
        ph = np.linspace(s, e, 24)
        clips["wave"] = {"observed": True, "source_frames": [int(s), int(e)], "duration_s": round((e - s) / fps, 4), "arm": arm,
                         "keys": {arm: [round(float(np.interp(p, np.arange(n), A[arm])), 2) for p in ph], "head": [round(float(np.interp(p, np.arange(n), tilt)), 2) for p in ph]},
                         "mouth": max(("closed", "smile", "open"), key=lambda m: sum(1 for r in fr[s:e + 1] if r["expr"]["mouth"] == m))}
    poses = {"rest": {"observed": True, "source_frame": 0, **{k: parts[k]["rest_angle"] for k in keys}, "torso": 0.0, "head": 0.0}}
    if "wave" in clips:
        a = clips["wave"]["arm"]; k = int(np.argmax(np.abs(up[a])))
        poses["arm_raised"] = {"observed": True, "source_frame": k, **{q: round(float(A[q][k]), 2) for q in keys}, "torso": round(float(ta[k]), 2), "head": round(float(tilt[k]), 2)}
    conf = {k: round(float(np.mean([r["parts"][k].get("conf", 0.0) for r in fr])), 3) for k in fr[0]["parts"]}
    occl = {k: {"hidden_frames": sum(1 for r in fr if not r["parts"][k].get("present")), "partly_hidden_frames": sum(1 for r in fr if r["parts"][k].get("present") and r["parts"][k].get("conf", 1) < 0.8),
                "merged_frames": sum(1 for r in fr if r["parts"][k].get("merged"))} for k in fr[0]["parts"]}
    mem = {"format": "dragon-character-memory/1", "tool_version": VERSION, "name": name,
           "source": {"video": jload(work / "frames.json")["video"], "frames": n, "fps": fps, "size": tr["size"], "seconds": round(fr[-1]["t"] - fr[0]["t"] + 1 / fps, 4)},
           "identity": {"palette": {r: col(r) for r in roles if roles[r] is not None}, "unit": "torso_height_px", "torso_height_px": round(th, 2),
                        "proportions": {"head_height": round(parts["head"]["size"]["height"] / th, 4), "head_width": round(parts["head"]["size"]["width"] / th, 4),
                                        "torso_width": round(parts["torso"]["size"]["width"] / th, 4), "arm_length": round(np.mean([parts[k]["length"] for k in ("arm_L", "arm_R")]) / th, 4),
                                        "leg_length": round(np.mean([parts[k]["length"] for k in ("leg_L", "leg_R")]) / th, 4),
                                        "total_height": round((ground - float(np.median([r["parts"]["hair" if roles.get("hair") is not None else "head"]["bbox"][1] for r in fr[:10]]))) / th, 4)},
                        "ground_y_px": round(ground, 2), "facing": "front"},
           "parts": parts, "layers": sorted(((v["z"], k) for k, v in parts.items()), key=lambda x: x[0]),
           "expressions": expr_obs, "poses": poses, "clips": clips, "timeline": timeline, "pose_track": track,
           "confidence": {"per_part_mean_visibility": conf, "occlusion": occl, "interpolated_angle_frames": filled, "paint_order_evidence": src,
                          "note": "confidence = visible area / the part's own full area; angles below 0.5 are interpolated and listed per frame in pose_track[].interpolated"},
           "synthesized": {"note": "nothing in this file is invented. Poses and expressions that the renderer makes up at animation time (sit, laugh, look, …) are reported by `animate` as synthesized."}}
    jdump(mem, out_json)
    print(f"memory: {out_json} · parts {len(parts)} · expressions seen: eyes {sorted(expr_obs['eyes'])} mouth {sorted(expr_obs['mouth'])} · clips {sorted(clips)} · timeline {len(timeline)} segments")
    return mem


# ====================================================================== 6) rig renderer: the character from memory alone
class Rig:
    def __init__(self, mem):
        self.m = mem; self.P = mem["parts"]; self.th = mem["identity"]["torso_height_px"]

    def shapes(self, s, scale=1.0):
        """s: x,y (torso centre, px), torso, head, arm_L.. (deg), eyes, mouth, optional eye_scale / mouth_scale (synthesized)."""
        P = self.P; out = []; c = np.array([s["x"], s["y"]]); ta = s.get("torso", 0.0); Rt = rot(math.radians(ta))
        tf = lambda poly, org, ang: (np.asarray(poly) * scale) @ rot(math.radians(ang)).T + org
        out.append((P["torso"]["z"], P["torso"]["color"], tf(P["torso"]["template"], c, ta)))
        for k in ("arm_L", "arm_R", "leg_L", "leg_R"):
            jw = c + Rt @ (np.array(P[k]["joint_in_parent"]) * scale)
            out.append((P[k]["z"], P[k]["color"], tf(P[k]["template"], jw, s.get(k, P[k]["rest_angle"]) + ta)))
        ha = ta + s.get("head", 0.0); neck = c + Rt @ (np.array(P["head"]["joint_in_parent"]) * scale)
        hc = neck + rot(math.radians(ha)) @ (np.array(P["head"]["center_from_joint"]) * scale)
        out.append((P["head"]["z"], P["head"]["color"], tf(P["head"]["template"], hc, ha)))
        if "hair" in P:
            out.append((P["hair"]["z"], P["hair"]["color"], tf(P["hair"]["template"], hc, ha)))
        E = self.m["expressions"]
        ey = E["eyes"].get(s.get("eyes") or "open") or E["eyes"].get("open") or next(iter(E["eyes"].values()))
        for nm, poly in ey["shapes"].items():
            poly = np.asarray(poly, float)
            if s.get("eye_scale") and nm.startswith("eye"):
                cy = poly[:, 1].mean(); poly = np.stack([poly[:, 0], cy + (poly[:, 1] - cy) * s["eye_scale"]], 1)
            role = "eye" if nm.startswith("eye") else "pupil"
            out.append((60 if role == "eye" else 70, self.m["identity"]["palette"][role], tf(poly, hc, ha)))
        mo = E["mouth"].get(s.get("mouth") or "closed") or next(iter(E["mouth"].values()))
        poly = np.asarray(mo["shapes"]["mouth"], float)
        if s.get("mouth_scale"):
            cx, cy = poly.mean(0); poly = np.stack([cx + (poly[:, 0] - cx) * s["mouth_scale"][0], cy + (poly[:, 1] - cy) * s["mouth_scale"][1]], 1)
        out.append((80, self.m["identity"]["palette"]["mouth"], tf(poly, hc, ha)))
        return sorted(out, key=lambda x: x[0])

    def draw(self, canvas_ss, s, scale=1.0):
        for _, col, poly in self.shapes(s, scale):
            pts = [np.round(poly * SS).astype(np.int32)]; c = tuple(int(v) for v in col)
            cv2.fillPoly(canvas_ss, pts, c, lineType=cv2.LINE_8)
            cv2.polylines(canvas_ss, pts, True, c, thickness=SS, lineType=cv2.LINE_8)        # +0.5 px outline in the part's own colour


def cmd_rebuild(work, mem_json):
    """Reference frames re-rendered from the memory + pose track only: how much of the video the memory really holds."""
    work = Path(work); mem = jload(mem_json); tr = jload(work / "tracks.json"); meta = jload(work / "frames.json"); rig = Rig(mem)
    pal = [tuple(p) for p in tr["bg_palette"]] + [tuple(p) for p in tr["fg_palette"]]; nb = len(tr["bg_palette"]); Wd, Hd = tr["size"]
    out = work / "rebuild_png"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(); rows = []
    first = load_frame(work, meta["frames"][0]); lab0, _ = nearest(first, pal)
    bg = first.copy()                                                          # background plate: flat bands, each row takes its own background colour
    for y in range(Hd):
        row = lab0[y]; b = row[row < nb]
        k = int(np.bincount(b).argmax()) if len(b) else 0
        bg[y, :] = [int(round(v)) for v in pal[k]]
    bg_ss = cv2.resize(bg, (Wd * SS, Hd * SS), interpolation=cv2.INTER_NEAREST)
    for f, s in zip(meta["frames"], mem["pose_track"]):
        cv = bg_ss.copy(); rig.draw(cv, s)
        img = cv2.resize(cv, (Wd, Hd), interpolation=cv2.INTER_AREA)
        cv2.imwrite(str(out / f"{f['frame']:05d}.png"), cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
        ref = load_frame(work, f); a = nearest(ref, pal)[0] >= nb; b = nearest(img, pal)[0] >= nb
        rows.append({"frame": f["frame"], "fg_iou": round(float((a & b).sum() / max(1, (a | b).sum())), 4), "ssim": round(ssim(ref, img), 4), "psnr": round(psnr(ref, img), 2)})
    ffmpeg_encode(str(out / "%05d.png"), work / "rebuild_from_memory.mp4", tr["fps"])
    agg = lambda k: {"mean": round(float(np.mean([r[k] for r in rows])), 4), "min": round(float(np.min([r[k] for r in rows])), 4)}
    worst = sorted(rows, key=lambda r: r["fg_iou"])[:5]
    rep = {"what": "reference re-rendered from character_memory.json + its pose track (no pixels from the video except the background plate)",
           "fg_iou": agg("fg_iou"), "ssim": agg("ssim"), "psnr_db": agg("psnr"), "worst_frames": worst, "per_frame": rows}
    jdump(rep, work / "rebuild_report.json")
    print(f"rebuild from memory: silhouette IoU mean {rep['fg_iou']['mean']} (min {rep['fg_iou']['min']}, worst frame {worst[0]['frame']}) · SSIM mean {rep['ssim']['mean']} · PSNR mean {rep['psnr_db']['mean']} dB")
    return rep


# ====================================================================== 7) animate: a new scene from the memory alone
def parse_do(text):
    acts = []
    for part in [p.strip() for p in text.replace("\n", ";").split(";") if p.strip()]:
        w = part.split(); acts.append({"do": w[0], "arg": float(w[1]) if len(w) > 1 else None})
    return acts


BG_CHOICES = [((176, 214, 240), (132, 186, 104), (92, 142, 76)), ((255, 222, 150), (214, 170, 110), (150, 110, 80)), ((205, 190, 235), (150, 130, 190), (104, 88, 150)),
              ((250, 200, 200), (200, 120, 130), (140, 80, 96)), ((225, 238, 215), (170, 205, 150), (120, 160, 110))]


def pick_bg(palette):
    """The band set whose nearest colour is farthest from every colour of the character."""
    cols = [np.array(c, float) for c in palette.values()]
    far = lambda bands: min(np.linalg.norm(np.array(b, float) - c) for b in bands for c in cols)
    return max(BG_CHOICES, key=far)


def cmd_animate(mem_json, out_dir, do, size=(640, 360), fps=24, scale=1.0, start_x=0.15, bg=None):
    mem = jload(mem_json); rig = Rig(mem); out = Path(out_dir); png = out / "scene_png"
    bg = bg or pick_bg(mem["identity"]["palette"])
    if png.exists():
        shutil.rmtree(png)
    png.mkdir(parents=True)
    Wd, Hd = size; th = rig.th * scale; ident = mem["identity"]; P = mem["parts"]
    ground = Hd * 0.82
    stand_y = ground - (ident["ground_y_px"] - np.median([p["y"] for p in mem["pose_track"][:10]])) * scale       # torso centre height above the feet, as measured
    rest = {k: P[k]["rest_angle"] for k in ("arm_L", "arm_R", "leg_L", "leg_R")}
    st = {"x": start_x * Wd, "y": stand_y, "torso": 0.0, "head": 0.0, **rest, "eyes": "open", "mouth": "closed"}
    frames, log, t = [], [], 0
    def emit(s):
        frames.append(dict(s))
    wc = mem["clips"].get("walk_cycle"); wv = mem["clips"].get("wave")
    for a in parse_do(do):
        f0 = len(frames); nm = a["do"]; src = "observed"; note = ""
        if nm == "idle":
            for i in range(int((a["arg"] or 1.0) * fps)):
                emit({**st, "y": st["y"] + 0.012 * th * math.sin(2 * math.pi * i / (2.0 * fps))})
        elif nm == "walk_to":
            tx = a["arg"] * Wd; d = 1 if tx >= st["x"] else -1
            if wc:
                per = max(2, int(round(wc["period_s"] * fps))); stride = wc["stride_px"] * scale
                nfr = max(per, int(round(abs(tx - st["x"]) / stride * per))); x0 = st["x"]
                for i in range(nfr):
                    u = i / max(1, nfr - 1); amp = smooth(u / 0.12) * (1 - smooth((u - 0.88) / 0.12)); ph = (i % per) / per * wc["phases"]
                    lo, fr_ = int(ph) % wc["phases"], ph - int(ph); hi = (lo + 1) % wc["phases"]
                    lerp = lambda arr: arr[lo] + (arr[hi] - arr[lo]) * fr_
                    s = {**st, "x": x0 + (tx - x0) * smooth(u), "y": st["y"] + lerp(wc["bob"]) * scale * amp, "torso": wc["torso"] * amp * d * wc["direction"]}
                    for k in rest:
                        kk = k if d == wc["direction"] else (k[:-1] + ("R" if k.endswith("L") else "L"))      # walking the other way swaps the limbs' roles
                        s[k] = rest[k] + (lerp(wc["keys"][kk]) - P[kk]["rest_angle"]) * amp * (1 if d == wc["direction"] else -1)
                    emit(s)
                note = f"walk cycle from frames {wc['source_frames']} of the source, {nfr} frames"
                if d != wc["direction"]:
                    src = "observed cycle, mirrored (estimated)"
            else:
                src = "synthesized"; nfr = int(abs(tx - st["x"]) / (0.9 * th) * fps) + 1; x0 = st["x"]
                for i in range(nfr):
                    u = i / max(1, nfr - 1); w = math.sin(2 * math.pi * i / (0.6 * fps))
                    emit({**st, "x": x0 + (tx - x0) * smooth(u), "leg_L": rest["leg_L"] + 24 * w, "leg_R": rest["leg_R"] - 24 * w, "arm_L": rest["arm_L"] - 18 * w, "arm_R": rest["arm_R"] + 18 * w})
            st["x"] = tx
        elif nm == "wave":
            dur = a["arg"] or (wv["duration_s"] if wv else 1.5); nfr = int(dur * fps)
            if wv:
                arm = wv["arm"]; K = wv["keys"]
                for i in range(nfr):
                    p = i / max(1, nfr - 1) * (len(K[arm]) - 1); lo = int(p); hi = min(lo + 1, len(K[arm]) - 1); fr_ = p - lo
                    emit({**st, arm: K[arm][lo] + (K[arm][hi] - K[arm][lo]) * fr_, "head": K["head"][lo] + (K["head"][hi] - K["head"][lo]) * fr_,
                          "mouth": wv["mouth"] if 0.2 < i / nfr < 0.85 else "closed"})
                note = f"wave clip from frames {wv['source_frames']} of the source, retimed to {dur:.2f}s"
            else:
                src = "synthesized"
                for i in range(nfr):
                    k = smooth(i / (0.3 * nfr)) * (1 - smooth((i - 0.75 * nfr) / (0.25 * nfr)))
                    emit({**st, "arm_R": rest["arm_R"] - k * (200 + 20 * math.sin(i * 0.8))})
        elif nm == "laugh":                                     # never seen as such: built from the widest mouth shape seen + body bounce
            src = "synthesized"; dur = a["arg"] or 1.5; nfr = int(dur * fps); has_open = "open" in mem["expressions"]["mouth"]
            note = "mouth: " + ("the 'open' shape seen in the source" if has_open else "the closed shape stretched") + "; eyes squeezed and shoulders bouncing are invented"
            for i in range(nfr):
                k = smooth(i / (0.15 * nfr)) * (1 - smooth((i - 0.85 * nfr) / (0.15 * nfr))); b = abs(math.sin(2 * math.pi * i / (0.28 * fps)))
                emit({**st, "y": st["y"] - 0.035 * th * b * k, "head": -5 * k + 3 * b * k, "mouth": ("open" if has_open else "closed") if k > 0.3 else "closed",
                      "mouth_scale": (1.25, 1.0) if has_open else (1.2, 3.0), "eye_scale": 1 - 0.55 * k, "arm_L": rest["arm_L"] + 8 * b * k, "arm_R": rest["arm_R"] - 8 * b * k})
        elif nm == "sit":                                       # never seen: legs forward, body lowered by the measured leg length
            src = "synthesized"; dur = a["arg"] or 2.0; nfr = int(dur * fps); drop = P["leg_L"]["length"] * scale * 0.80
            note = "sitting pose is invented from the measured leg length and joints; the source has no sitting frame"
            for i in range(nfr):
                k = smooth(i / (0.35 * nfr)) * (1 - smooth((i - 0.8 * nfr) / (0.2 * nfr)))
                emit({**st, "y": st["y"] + drop * k, "leg_L": rest["leg_L"] - 68 * k, "leg_R": rest["leg_R"] - 82 * k, "torso": -4 * k, "arm_L": rest["arm_L"] + 10 * k, "arm_R": rest["arm_R"] - 14 * k})
        elif nm == "blink":
            for i in range(max(3, int(0.18 * fps))):
                emit({**st, "eyes": "closed" if "closed" in mem["expressions"]["eyes"] else "open"})
            src = "observed" if "closed" in mem["expressions"]["eyes"] else "synthesized"
        elif nm == "surprise":
            src = "observed" if "wide" in mem["expressions"]["eyes"] and "open" in mem["expressions"]["mouth"] else "synthesized"
            for i in range(int((a["arg"] or 0.8) * fps)):
                emit({**st, "eyes": "wide" if "wide" in mem["expressions"]["eyes"] else "open", "mouth": "open" if "open" in mem["expressions"]["mouth"] else "closed"})
        else:
            raise SystemExit(f"unknown action: {nm} (idle, walk_to X, wave [s], laugh [s], sit [s], blink, surprise [s])")
        log.append({"action": nm, "arg": a["arg"], "frames": [f0, len(frames) - 1], "source": src, "note": note})
    bg_ss = np.zeros((Hd * SS, Wd * SS, 3), np.uint8)
    bg_ss[:] = bg[0]; bg_ss[int(Hd * SS * 0.62):] = bg[1]; bg_ss[int(ground * SS):] = bg[2]
    for i, s in enumerate(frames):
        cv = bg_ss.copy(); rig.draw(cv, s, scale)
        cv2.imwrite(str(png / f"{i:05d}.png"), cv2.cvtColor(cv2.resize(cv, (Wd, Hd), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2BGR))
    ffmpeg_encode(str(png / "%05d.png"), out / "new_scene.mp4", fps)
    rep = {"memory": str(mem_json), "reads_reference_video": False, "frames": len(frames), "fps": fps, "size": list(size), "scale": scale, "actions": log, "states": frames}
    jdump(rep, out / "new_scene_report.json")
    print(f"new scene: {out / 'new_scene.mp4'} · {len(frames)} frames · " + " · ".join(f"{l['action']}={l['source']}" for l in log))
    return rep


# ====================================================================== 8) identity: is the character in VIDEO the one in the memory?
def cmd_identity(mem_json, video, work):
    mem = jload(mem_json); cmd_extract(video, work); tr, _ = cmd_analyze(work)
    pal = tr["fg_palette"]; roles = tr["roles"]; ref = mem["identity"]
    dcol = {r: round(float(np.abs(np.array(pal[roles[r]]) - np.array(ref["palette"][r])).max()), 1) for r in ref["palette"] if roles.get(r) is not None}
    missing = [r for r in ref["palette"] if roles.get(r) is None]
    fr = tr["frames"][:10]; th = float(np.median([r["parts"]["torso"]["height"] for r in fr]))
    hd = [head_box(r["parts"]) for r in fr if head_box(r["parts"])]
    L = lambda k: float(np.median([r["parts"][k]["length"] for r in fr if "length" in r["parts"][k]]))
    got = {"head_height": float(np.median([b[1] for b in hd])) / th, "head_width": float(np.median([b[0] for b in hd])) / th,
           "torso_width": float(np.median([r["parts"]["torso"]["width"] for r in fr])) / th,
           "arm_length": (L("arm_L") + L("arm_R")) / 2 / th, "leg_length": (L("leg_L") + L("leg_R")) / 2 / th}
    err = {k: round(100 * abs(got[k] - ref["proportions"][k]) / ref["proportions"][k], 2) for k in got}
    rep = {"video": str(video), "palette_max_channel_diff": dcol, "roles_not_found": missing, "proportions_measured": {k: round(v, 4) for k, v in got.items()},
           "proportions_in_memory": {k: ref["proportions"][k] for k in got}, "proportion_error_pct": err, "torso_height_px": round(th, 2),
           "details_not_resolved": [r for r in missing if r in ("pupil", "mouth", "eye", "hair")],
           "same_character": bool(not [r for r in missing if r in ("torso", "head", "arm", "leg")] and max(dcol.values()) <= 14 and max(err.values()) <= 6.0),
           "rule": "same_character = torso, head, arms and legs found, every colour that was found within 14/255 per channel, every proportion within 6 %. "
                   "Small details the analyzer could not resolve at this size are listed in details_not_resolved and are not counted for or against."}
    jdump(rep, Path(work) / "identity_report.json")
    print(f"identity: colours max diff {max(dcol.values())}/255 · proportion error max {max(err.values())}% ({max(err, key=err.get)}) · same_character={rep['same_character']}")
    return rep


# ====================================================================== 9) sheets + demo
def sheet(rows, out, cell=(320, 180), labels=None):
    """rows: list of lists of image paths -> a contact sheet (comparison)."""
    Hh = len(rows); Ww = max(len(r) for r in rows); pad = 18
    im = Image.new("RGB", (Ww * cell[0], Hh * (cell[1] + pad)), (24, 24, 28)); d = ImageDraw.Draw(im)
    for y, r in enumerate(rows):
        for x, p in enumerate(r):
            im.paste(Image.open(p).convert("RGB").resize(cell, Image.LANCZOS), (x * cell[0], y * (cell[1] + pad) + pad))
        if labels:
            d.text((6, y * (cell[1] + pad) + 3), labels[y], fill=(235, 235, 235))
    im.save(out)


def cmd_demo(out, reuse=False):
    out = Path(out); out.mkdir(parents=True, exist_ok=True); work = out / "work"
    if reuse and (out / "character_memory.json").is_file() and (work / "rebuild_report.json").is_file():      # keep the slow analysis, redo the scene and the report
        red, reb, mem = jload(work / "redraw_report.json"), jload(work / "rebuild_report.json"), jload(out / "character_memory.json")
    else:
        ref = cmd_make_ref(out / "reference"); cmd_extract(ref, work); cmd_analyze(work); red = cmd_redraw(work)
        mem = cmd_memory(work, out / "character_memory.json", name="نبض (Nabd) — demo character"); reb = cmd_rebuild(work, out / "character_memory.json")
    scn = cmd_animate(out / "character_memory.json", out / "new_scene", "idle 0.6; walk_to 0.72; wave 1.6; laugh 1.5; sit 2.2; blink; idle 0.5", scale=1.0)
    idn = cmd_identity(out / "character_memory.json", out / "new_scene" / "new_scene.mp4", out / "identity_work")
    pick = [0, 15, 48, 60, 100, 118, 138]
    ex = lambda v, i, o: subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(v), "-vf", f"select=eq(n\\,{i})", "-frames:v", "1", str(o)], check=True)
    tmp = out / "work" / "sheet"; tmp.mkdir(exist_ok=True)
    rows = [[work / "frames" / f"f{i:05d}.png" for i in pick], [work / "redraw_png" / f"{i:05d}.png" for i in pick], [work / "rebuild_png" / f"{i:05d}.png" for i in pick]]
    sheet(rows, out / "compare_reference_redraw_memory.png", labels=["1) reference video", "2) auto-rotoscope redraw (vector regions)", "3) rebuilt from character_memory.json only"])
    n2 = scn["frames"]; p2 = [int(n2 * q) for q in (0.02, 0.2, 0.36, 0.5, 0.62, 0.8, 0.97)]
    sheet([[out / "new_scene" / "scene_png" / f"{i:05d}.png" for i in p2]], out / "new_scene_sheet.png", labels=["new scene from the memory alone (walk, wave, laugh*, sit*)   * = synthesized"])
    shutil.copy2(work / "redraw.mp4", out / "redraw.mp4"); shutil.copy2(work / "rebuild_from_memory.mp4", out / "rebuild_from_memory.mp4")
    rep = {"tool": "dragon-character-memory " + VERSION, "reference": {"video": "reference/reference.mp4", "frames": red["frames"]},
           "redraw": {k: red[k] for k in ("psnr_db", "ssim", "fg_iou", "centroid_err_px", "vector_points_per_frame")},
           "rebuild_from_memory": {k: reb[k] for k in ("fg_iou", "ssim", "psnr_db", "worst_frames")},
           "memory": {"parts": sorted(mem["parts"]), "expressions_seen": {k: sorted(v) for k, v in mem["expressions"].items()}, "clips": sorted(mem["clips"]),
                      "timeline": [(a["action"], a["from_frame"], a["to_frame"]) for a in mem["timeline"]], "confidence": mem["confidence"]["per_part_mean_visibility"],
                      "occlusion": {k: v for k, v in mem["confidence"]["occlusion"].items() if any(v.values())}},
           "new_scene": {"video": "new_scene/new_scene.mp4", "actions": scn["actions"]}, "identity_check_on_new_scene": idn}
    jdump(rep, out / "REPORT.json")
    print("demo done ->", out)
    return rep


def main():
    ap = argparse.ArgumentParser(prog="dcm.py", description="Dragon Character Memory & Auto Rotoscope")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("make-ref"); s.add_argument("out")
    s = sub.add_parser("extract"); s.add_argument("video"); s.add_argument("work")
    s = sub.add_parser("analyze"); s.add_argument("work")
    s = sub.add_parser("redraw"); s.add_argument("work")
    s = sub.add_parser("memory"); s.add_argument("work"); s.add_argument("out"); s.add_argument("--name", default="character")
    s = sub.add_parser("rebuild"); s.add_argument("work"); s.add_argument("memory")
    s = sub.add_parser("animate"); s.add_argument("memory"); s.add_argument("out"); s.add_argument("--do", required=True); s.add_argument("--scale", type=float, default=1.0)
    s.add_argument("--size", default="640x360"); s.add_argument("--fps", type=int, default=24); s.add_argument("--start-x", type=float, default=0.15)
    s = sub.add_parser("identity"); s.add_argument("memory"); s.add_argument("video"); s.add_argument("--work", default=None)
    s = sub.add_parser("demo"); s.add_argument("out"); s.add_argument("--reuse", action="store_true", help="keep an existing analysis in OUT, redo the new scene and the report")
    a = ap.parse_args()
    if a.cmd == "make-ref":
        cmd_make_ref(a.out)
    elif a.cmd == "extract":
        cmd_extract(a.video, a.work)
    elif a.cmd == "analyze":
        cmd_analyze(a.work)
    elif a.cmd == "redraw":
        cmd_redraw(a.work)
    elif a.cmd == "memory":
        cmd_memory(a.work, a.out, a.name)
    elif a.cmd == "rebuild":
        cmd_rebuild(a.work, a.memory)
    elif a.cmd == "animate":
        cmd_animate(a.memory, a.out, a.do, tuple(int(v) for v in a.size.split("x")), a.fps, a.scale, a.start_x)
    elif a.cmd == "identity":
        cmd_identity(a.memory, a.video, a.work or str(Path(a.video).parent / "identity_work"))
    elif a.cmd == "demo":
        cmd_demo(a.out, a.reuse)


if __name__ == "__main__":
    main()
