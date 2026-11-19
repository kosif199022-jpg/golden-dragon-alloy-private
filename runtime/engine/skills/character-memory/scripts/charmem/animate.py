"""Bring a remembered character into a new scene from character_memory.json alone (the source video is never opened).

Commands (Arabic or English, in order): walk, go to the other side, laugh, sit, wave, surprise, scratch head, sad,
angry, idle. Observed motions replay their recorded channels (looped when cyclic); generated ones (sit, sad, angry) are
built from the rest pose and the learned skeleton and are marked generated in the scene script.
"""
from __future__ import annotations

import json
import math
import re
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from . import memory as M
from . import rig

POSE_KEYS = M.POSE_KEYS
CMDS = [  # (pattern, action)
    (r"الجانب الآخر|الجانب الاخر|ناحي[هة] (التاني[هة]|الثاني[هة]|الاخرى|الأخرى)|other side|across", "cross"),
    (r"تمش|يمش|امش|مشي|walk", "walk"),
    (r"تضحك|يضحك|اضحك|ضحك|laugh", "laugh"),
    (r"تجلس|يجلس|اجلس|تقعد|يقعد|اقعد|قعد|sit", "sit"),
    (r"تلوح|يلوح|لوح|سلم|تسلم|wave|hello", "wave"),
    (r"تتفاج|يتفاج|مندهش|اتخض|surpris", "surprise"),
    (r"تهرش|يهرش|تحتار|محتار|confus|scratch", "scratch_head"),
    (r"تحزن|حزين|حزينه|زعلان|زعلانه|sad", "sad"),
    (r"تغضب|غضبان|متعصب|angry", "angry"),
    (r"تقف|يقف|استنى|ثابت|idle|stand", "idle"),
]


def parse(text):
    """'خلّي الشخصية تمشي للناحية التانية وبعدين تضحك وبعدين تقعد' -> ['cross', 'laugh', 'sit']."""
    t = re.sub(r"[ًٌٍَُِّْ]", "", str(text).lower())
    clauses = re.split(r"\s*(?:وبعدين|وبعد كده|بعد كده|ثم|بعدها|then|,|،|\band\b)\s*|\s+و(?=\S)", t)
    out = []
    for c in clauses:
        for rx, act in CMDS:
            if re.search(rx, c):
                if act == "walk" and re.search(CMDS[0][0], c):
                    act = "cross"
                out.append(act)
                break
    out = [a for i, a in enumerate(out) if i == 0 or a != out[i - 1]]      # "تحتار وتهرش" is one action
    return out or ["idle"]


# ------------------------------------------------------------------ the remembered character, drawn
class Character:
    def __init__(self, mem, head_px):
        self.m = mem
        self.k = head_px                                     # px per head unit in the new scene
        self.pal = {p["role"]: tuple(p["rgb"]) for p in mem["identity"]["palette"] if p["role"] != "unassigned"}
        self.ink = tuple(int(mem["identity"]["outline"]["hex"][i:i + 2], 16) for i in (1, 3, 5))
        self.ow = max(2.0, mem["identity"]["outline"]["width_hu"] * head_px)
        self.B = {b["name"]: (b["length_hu"] or 0.0) * head_px for b in mem["skeleton"]["bones"]}
        self.att = {k: v for k, v in mem["skeleton"]["attach_hu"].items() if k != "frame"}
        self.foot = mem["skeleton"]["foot_offset_hu"]
        self.parts = {p["name"]: p for p in mem["parts"]}
        self.expr = {e["name"]: e for e in mem["face"]["expressions"]}
        self.rest = mem["face"]["rest"]

    def fk(self, c, thigh_scale=1.0):
        k = self.k
        P = np.array([c["px"], c["py"]])
        sp = math.radians(c["spine"])
        up = np.array([math.sin(sp), -math.cos(sp)])
        side = np.array([math.cos(sp), math.sin(sp)])
        J = {"pelvis": P}
        for jn in ("neck", "shoulder.R", "shoulder.L", "hip.R", "hip.L"):
            a = self.att[jn]
            J[jn] = P + side * a[0] * k + up * a[1] * k
        ht = sp + math.radians(c["head_tilt"])
        J["head"] = J["neck"] + np.array([math.sin(ht), -math.cos(ht)]) * self.B["head"]
        for s in ("R", "L"):
            d1, d2 = rig.d(c["ua." + s]), rig.d(c["ua." + s] + c["fa." + s])
            J["elbow." + s] = J["shoulder." + s] + np.array(d1) * self.B["upper_arm." + s]
            J["wrist." + s] = J["elbow." + s] + np.array(d2) * self.B["forearm." + s]
            J["hand." + s] = J["wrist." + s] + np.array(d2) * self.B["hand." + s]
            t1, t2 = rig.d(c["th." + s]), rig.d(c["th." + s] + c["sh." + s])
            J["knee." + s] = J["hip." + s] + np.array(t1) * self.B["thigh." + s] * thigh_scale
            J["ankle." + s] = J["knee." + s] + np.array(t2) * self.B["shin." + s]
            J["foot." + s] = J["ankle." + s] + np.array(self.foot[s]) * k
        return J, math.degrees(sp), math.degrees(ht)

    def radial_poly(self, part, c, rot_deg, scale=1.0):
        r = np.array(self.parts[part]["shape"]["radii_hu"]) * self.k * scale
        r = (np.roll(r, 1) + r * 2 + np.roll(r, -1)) / 4                    # soften the 5-degree steps
        n = len(r)
        th = np.radians((np.arange(n) + 0.5) * 360 / n)
        lx, ly = r * np.cos(th), r * np.sin(th)
        a = math.radians(rot_deg)
        return list(zip(c[0] + lx * math.cos(a) - ly * math.sin(a), c[1] + lx * math.sin(a) + ly * math.cos(a)))

    def head_pt(self, J, tilt, x, y):
        a = math.radians(tilt)
        return (J["head"][0] + (x * math.cos(a) - y * math.sin(a)) * self.k, J["head"][1] + (x * math.sin(a) + y * math.cos(a)) * self.k)

    def layers(self, c, expr_name, behind_head=False, thigh_scale=1.0):
        J, sp, ht = self.fk(c, thigh_scale)
        k = self.k
        L = []
        rl, ra = self.parts["leg"]["shape"]["radius_hu"] * k, self.parts["arm"]["shape"]["radius_hu"] * k
        g = self.parts["glove"]["shape"]["radii_hu"]
        sh = self.parts["shoe"]["shape"]["radii_hu"]
        for s in ("R", "L"):
            L.append(("limb", [J["hip." + s], J["knee." + s], J["ankle." + s]], "skin", rl))
        for s in ("R", "L"):
            L.append(("poly", rig.ellipse(tuple(J["foot." + s]), sh[0] * k, sh[1] * k), "shoe", None))   # radii_hu are radii (2 sigma of a disc)
        up = np.array([math.sin(math.radians(sp)), -math.cos(math.radians(sp))])
        side = np.array([math.cos(math.radians(sp)), math.sin(math.radians(sp))])
        for part, role in (("torso", "shirt"), ("shorts", "shorts")):
            o = self.parts[part]["shape"]["offset_hu"]
            cc = J["pelvis"] + side * o[0] * k + up * o[1] * k
            L.append(("poly", self.radial_poly(part, cc, sp), role, None))
        arms = []
        for s in ("R", "L"):
            arms.append((s, [("limb", [J["shoulder." + s], J["elbow." + s], J["wrist." + s]], "sleeve", ra),
                             ("poly", rig.ellipse(tuple(J["hand." + s]), g[0] * k, g[1] * k), "glove", None)]))
        for s, items in arms:
            if behind_head and s == "R":
                L += items
        L.append(("poly", self.radial_poly("head", J["head"], ht), "skin", None))
        co = self.parts["cap"]["shape"]["offset_hu"]
        L.append(("poly", self.radial_poly("cap", self.head_pt(J, ht, co[0], co[1]), ht), "cap", None))
        for s, items in arms:
            if not (behind_head and s == "R"):
                L += items
        L += self.face(J, ht, expr_name)
        return L, J

    def face(self, J, ht, name):
        e = self.expr.get(name) or self.expr["neutral"]
        p = e["params"]
        k = self.k
        out = []
        eyes, pr = self.parts["eyes"]["shape"], self.parts["eyes"]["shape"]["pupil_radius_hu"]
        for s in ("R", "L"):
            E = eyes[s]
            cx, cy = E["c"]
            if p.get("eye_state", "open") == "open":
                op = p.get("eye_open", 1.0) or 1.0
                pts = [self.head_pt(J, ht, cx + E["w"] / 2 * math.cos(t), cy + E["h"] / 2 * op * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 40, endpoint=False)]
                out.append(("poly", pts, "eye", None))
                pts = [self.head_pt(J, ht, cx + pr * math.cos(t), cy + 0.01 + pr * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 24, endpoint=False)]
                out.append(("fill", pts, "ink", None))
            else:
                h = -0.05 if p.get("eye_state") == "happy" else 0.0
                pts = [self.head_pt(J, ht, cx + x, cy + y + 0.01) for x, y in rig.arc(E["w"] * 0.85, h)]
                out.append(("stroke", pts, "ink", 1.5))
            b = self.parts["brows"]["shape"][s]
            by = p.get("brow_y." + s, b["y"])
            tilt = math.radians(p.get("brow_tilt", 0.0)) * (1 if s == "R" else -1)
            dx, dy = b["len"] / 2 * math.cos(tilt), b["len"] / 2 * math.sin(tilt)
            out.append(("stroke", [self.head_pt(J, ht, b["x"] - dx, by - dy), self.head_pt(J, ht, b["x"] + dx, by + dy)], "ink", b["thick"] * k / self.ow))
        w, cu, x, y = p.get("mouth_w", 0.26), p.get("mouth_curve", 0.02), p.get("mouth_x", 0.0), p.get("mouth_y", 0.27)
        if p.get("mouth_state") == "open":
            op = max(p.get("mouth_open", 0.0), 0.12)
            pts = [self.head_pt(J, ht, x + a, y - op / 2 + b) for a, b in rig.mouth_shape(w, op, cu * 0.6)]
            out.append(("poly", pts, "mouth", None))
        else:
            pts = [self.head_pt(J, ht, x + a, y + b - cu / 2) for a, b in rig.mouth_stroke(w * 0.9, cu)]
            out.append(("stroke", pts, "ink", 1.5))
        return out

    def draw(self, img, layers, s=2):
        dr = ImageDraw.Draw(img)
        for kind, pts, role, extra in layers:
            col = self.ink if role == "ink" else self.pal.get(role, (255, 0, 255))
            if kind == "limb":
                r = extra
                segs = [(pts[0], pts[1]), (pts[1], pts[2])]
                for a, b in segs:
                    rig.draw_poly(dr, rig.capsule(tuple(a), tuple(b), r + self.ow), self.ink, s=s)
                for a, b in segs:
                    rig.draw_poly(dr, rig.capsule(tuple(a), tuple(b), r), col, s=s)
            elif kind == "poly":
                rig.draw_poly(dr, pts, col, self.ink, self.ow, s=s)
            elif kind == "fill":
                rig.draw_poly(dr, pts, col, s=s)
            else:
                rig.draw_stroke(dr, pts, col, self.ow * extra, s=s)


# ------------------------------------------------------------------ the scene
def background(W, H, ground):
    """An evening park (unlike the reference's plain room): sky, low sun, grass, a bench, a tree."""
    y = np.linspace(0, 1, H)[:, None, None]
    top, mid = np.array([58, 44, 112], float), np.array([255, 170, 120], float)
    img = top * (1 - y) + mid * y
    img = np.repeat(img, W, axis=1)
    im = Image.fromarray(img.clip(0, 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    d.ellipse([W * 0.62, H * 0.47, W * 0.82, H * 0.47 + W * 0.2], fill=(255, 226, 150))
    d.rectangle([0, ground - 10, W, H], fill=(86, 150, 84))
    d.rectangle([0, ground - 10, W, ground + 6], fill=(70, 128, 70))
    tx = int(W * 0.12)
    d.rectangle([tx - 22, ground - 520, tx + 22, ground], fill=(122, 88, 62))
    d.ellipse([tx - 190, ground - 900, tx + 190, ground - 430], fill=(52, 112, 66))
    return im


def bench(d, x0, x1, seat_y, ground):
    """Set pieces stay lighter than the character's ink, so the scene can be re-analysed (a test) without confusion."""
    d.rectangle([x0, seat_y, x1, seat_y + 26], fill=(150, 104, 66), outline=(118, 82, 52), width=4)
    d.rectangle([x0, seat_y - 120, x1, seat_y - 90], fill=(150, 104, 66), outline=(118, 82, 52), width=4)
    for x in (x0 + 24, x1 - 24):
        d.rectangle([x - 10, seat_y, x + 10, ground], fill=(118, 82, 52))


def motion_frames(mem, name):
    m = next((x for x in mem["motions"] if x["name"] == name and x.get("observed")), None)
    if not m:
        return None, None
    return {k: np.array(v, float) for k, v in m["channels"].items()}, m


def build_script(mem, actions, W, head_px, fps, start_x):
    """Per-frame channels for the whole scene: each action's channels, root motion retargeted to the new scale, a
    0.25 s crossfade between actions. Returns frames [(channels, expression, flags)] and the script with provenance."""
    src_k = mem["units"]["hu_px"]
    sc = head_px / src_k
    rest, _ = motion_frames(mem, "idle")
    base = {k: float(rest[k][0]) for k in POSE_KEYS}
    ground_off = None
    frames, script = [], []
    x = start_x
    cur = dict(base)

    def emit(ch, ex, flags, n):
        for i in range(n):
            frames.append(({k: ch[k][i] for k in POSE_KEYS}, ex, flags))
    for act in actions:
        if act in ("walk", "cross"):
            ch, m = motion_frames(mem, "walk")
            per = int(round((m.get("period_s") or 0.75) * fps))
            mid = len(ch["px"]) // 2 - per // 2
            cyc = {k: v[mid:mid + per] for k, v in ch.items()}
            speed = (m.get("speed_hu_s") or 0.4) * head_px / fps
            target = W - start_x if act == "cross" else x + 0.25 * W * (1 if x < W / 2 else -1)
            n = int(abs(target - x) / max(speed, 1e-6))
            dirn = 1 if target > x else -1
            out = {k: np.array([cyc[k][i % per] for i in range(n)]) for k in POSE_KEYS}
            out["px"] = x + dirn * speed * np.arange(1, n + 1)
            out["py"] = (cyc["py"][np.arange(n) % per] - cyc["py"].mean()) * sc
            emit(out, "smile", {}, n)
            x = float(out["px"][-1])
            script.append({"action": act, "source": "observed walk cycle", "frames": n, "period_s": m.get("period_s"), "speed_hu_s": m.get("speed_hu_s")})
        elif act in ("laugh", "wave", "surprise", "scratch_head", "idle"):
            ch, m = motion_frames(mem, act)
            n = len(ch["px"])
            reps = 2 if act == "laugh" else 1
            out = {k: np.tile(v, reps) for k, v in ch.items()}
            out["px"] = x + (out["px"] - ch["px"][0]) * sc
            out["py"] = (out["py"] - ch["py"][0]) * sc
            ex = {"laugh": "laugh", "wave": "smile", "surprise": "surprise", "scratch_head": "confused", "idle": "neutral"}[act]
            flags = {"behind_head": act == "scratch_head"}
            emit(out, ex, flags, n * reps)
            script.append({"action": act, "source": f"observed {act} ({m['t0']}-{m['t1']} s of the source)", "frames": n * reps})
        elif act == "sit":
            gm = next(x_ for x_ in mem["motions"] if x_["name"] == "sit")
            dlt = gm["pose_delta"]
            n_in, n_hold = int(0.6 * fps), int(1.6 * fps)
            outs = {k: [] for k in POSE_KEYS}
            ts = []
            for i in range(n_in + n_hold):
                u = min(1.0, i / n_in)
                u = u * u * (3 - 2 * u)
                for k in POSE_KEYS:
                    v = base[k] + (dlt.get(k, 0.0) * u if k not in ("px", "py") else 0.0)
                    outs[k].append(v)
                ts.append(1 - (1 - dlt["thigh_scale"]) * u)
            out = {k: np.array(v) for k, v in outs.items()}
            out["px"] = np.full(len(ts), x)
            out["py"] = np.array([dlt["py"] * head_px * (1 - t) / (1 - dlt["thigh_scale"]) for t in ts])
            for i, t in enumerate(ts):
                frames.append(({k: out[k][i] for k in POSE_KEYS}, "smile", {"thigh_scale": t}))
            script.append({"action": "sit", "source": "GENERATED from the rest pose and the learned thigh (never seen in the video)", "frames": len(ts),
                           "confidence": gm["confidence"]})
        elif act in ("sad", "angry"):
            ch, m = motion_frames(mem, "idle")
            n = len(ch["px"])
            out = {k: v.copy() for k, v in ch.items()}
            out["px"] = np.full(n, x)
            out["py"] = (out["py"] - ch["py"][0]) * sc
            emit(out, act, {}, n)
            script.append({"action": act, "source": "GENERATED expression on the observed idle", "frames": n})
    # absolute root: py is relative to standing; crossfade 0.25 s at every action boundary
    fade = int(0.25 * fps)
    bounds = np.cumsum([s["frames"] for s in script])[:-1]
    for b in bounds:
        for j in range(fade):
            i = b + j
            if i >= len(frames):
                break
            u = (j + 1) / (fade + 1)
            prev = frames[b - 1][0]
            ch = frames[i][0]
            frames[i] = ({k: (prev[k] * (1 - u) + ch[k] * u) if k not in ("px",) else ch[k] for k in POSE_KEYS}, frames[i][1], frames[i][2])
    return frames, script


def render(memory_path, command, out_dir, W=1080, H=1920, fps=30, head_px=210):
    mem = M.load(memory_path)
    actions = parse(command)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ch = Character(mem, head_px)
    ground = int(H * 0.86)
    frames, script = build_script(mem, actions, W, head_px, fps, start_x=W * 0.28)
    # stand the rest pose on the ground: pelvis height from the learned legs
    leg = (ch.B["thigh.R"] + ch.B["shin.R"]) + mem["skeleton"]["foot_offset_hu"]["R"][1] * head_px + mem["parts"][[p["name"] for p in mem["parts"]].index("shoe")]["shape"]["radii_hu"][1] * head_px / 2
    stand_y = ground - leg
    bgim = background(W, H, ground)
    sit_i = next((i for i, f in enumerate(frames) if "thigh_scale" in f[2]), None)
    if sit_i is not None:                   # the bench is part of the set from the start, where the character will sit
        sx = frames[sit_i][0]["px"]
        bench(ImageDraw.Draw(bgim), int(sx - 0.75 * head_px), int(sx + 0.75 * head_px), int(stand_y + 0.30 * head_px), ground)
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
                           "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709",
                           "-colorspace", "bt709", "-movflags", "+faststart", str(out / "new_scene.mp4")], stdin=subprocess.PIPE)
    stills = []
    for i, (c, ex, fl) in enumerate(frames):
        c = dict(c)
        c["py"] = stand_y + c["py"]
        big = bgim.resize((W * 2, H * 2))
        L, J = ch.layers(c, ex, behind_head=fl.get("behind_head", False), thigh_scale=fl.get("thigh_scale", 1.0))
        ch.draw(big, L, s=2)
        fr = big.resize((W, H), Image.LANCZOS)
        ff.stdin.write(fr.tobytes())
        if i % max(1, len(frames) // 8) == 0:
            stills.append(fr.resize((W // 4, H // 4)))
    ff.stdin.close()
    ff.wait()
    sheet = Image.new("RGB", ((W // 4) * len(stills), H // 4))
    for j, s in enumerate(stills):
        sheet.paste(s, ((W // 4) * j, 0))
    sheet.save(out / "new_scene_sheet.png")
    info = {"command": command, "actions": actions, "script": script, "frames": len(frames), "fps": fps, "head_px": head_px,
            "memory": str(Path(memory_path).resolve()), "uses_video": False}
    (out / "scene_script.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    return info
