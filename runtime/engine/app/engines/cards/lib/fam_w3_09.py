"""Helpers of runners/fam_w3_09.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from pathlib import Path
from .core import fx
import json
import math
import numpy as np
import re
import subprocess


def jw(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return Path(path)


def tw(path, text):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8")
    return Path(path)


def write_mp4(path, frames, fps=30, audio=None):
    arr = [np.asarray(f, dtype=np.uint8) for f in frames]
    h, w = arr[0].shape[:2]
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (w, h),
           "-r", str(fps), "-i", "-"]
    if audio:
        cmd += ["-i", str(audio), *fx.fit_audio(len(arr) / fps), "-c:a", "aac", "-b:a", "128k", "-frames:v", str(len(arr))]
    cmd += ["-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", str(path)]
    p = subprocess.run(cmd, input=b"".join(a.tobytes() for a in arr), capture_output=True, timeout=60)
    if p.returncode:
        raise RuntimeError(p.stderr.decode(errors="replace")[-300:])
    return Path(path)


def canvas(w, h, bg=(12, 14, 20)):
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (w, h), bg)
    return im, ImageDraw.Draw(im)


def blob(frame, thr=128, ch=None):
    a = frame if ch is None else frame[..., ch:ch + 1]
    m = a.max(axis=2) > thr
    if not m.any():
        return None
    ys, xs = np.nonzero(m)
    return {"x0": int(xs.min()), "x1": int(xs.max()), "y0": int(ys.min()), "y1": int(ys.max()),
            "cx": float(xs.mean()), "cy": float(ys.mean()), "n": int(m.sum()), "w": int(xs.max() - xs.min() + 1),
            "h": int(ys.max() - ys.min() + 1)}


def bez(x1, y1, x2, y2):
    """CSS cubic-bezier solver (bisection on x)."""
    def cx(t):
        return 3 * x1 * t * (1 - t) ** 2 + 3 * x2 * t * t * (1 - t) + t ** 3

    def cy(t):
        return 3 * y1 * t * (1 - t) ** 2 + 3 * y2 * t * t * (1 - t) + t ** 3

    def f(x):
        if x <= 0:
            return 0.0
        if x >= 1:
            return 1.0
        lo, hi = 0.0, 1.0
        for _ in range(60):
            mid = (lo + hi) / 2
            if cx(mid) < x:
                lo = mid
            else:
                hi = mid
        return cy((lo + hi) / 2)
    return f


def spring_step(t, k, c, m=1.0):
    """Closed-form step response 0 -> 1 of a damped spring (stiffness k, damping c, mass m)."""
    if t <= 0:
        return 0.0
    w0 = math.sqrt(k / m)
    z = c / (2 * math.sqrt(k * m))
    if z < 1:
        wd = w0 * math.sqrt(1 - z * z)
        return 1 - math.exp(-z * w0 * t) * (math.cos(wd * t) + z * w0 / wd * math.sin(wd * t))
    if abs(z - 1) < 1e-9:
        return 1 - math.exp(-w0 * t) * (1 + w0 * t)
    wd = w0 * math.sqrt(z * z - 1)
    return 1 - math.exp(-z * w0 * t) * (math.cosh(wd * t) + z * w0 / wd * math.sinh(wd * t))


def sim_spring(k, c, m=1.0, dur=3.0, dt=1 / 1000):
    """Semi-implicit Euler integration of x'' = (k(1-x) - c x')/m from rest at 0."""
    x, v, xs = 0.0, 0.0, []
    for _ in range(int(dur / dt)):
        a = (k * (1 - x) - c * v) / m
        v += a * dt
        x += v * dt
        xs.append(x)
    return np.array(xs)


def ease_out_cubic(p):
    return 1 - (1 - p) ** 3


def ease_in_quad(p):
    return p * p


def smoothstep(p):
    p = min(1.0, max(0.0, p))
    return p * p * (3 - 2 * p)


def wav_mono(path):
    data, rate = fx.read_wav(path)
    return data.mean(axis=1), rate


def _pcb_review(d):
    findings = []
    ds = d["datasheets"]
    for ref, p in d["parts"].items():
        sheet = ds[p["mpn"]]
        if p["package"] != sheet["package"]:
            findings.append(("footprint", ref, "package %s != datasheet %s" % (p["package"], sheet["package"])))
        for pin, fn in sheet["pins"].items():
            if p["footprint_pins"].get(pin) != fn:
                findings.append(("pinout", ref, "pin %s is %s on footprint, %s in datasheet" % (pin, p["footprint_pins"].get(pin), fn)))
        for pin, net in p["nets"].items():
            if net in d["rails"] and d["rails"][net] > sheet.get("vmax", 99):
                findings.append(("rail", ref, "%s (%.1f V) exceeds %s abs max %.1f V" % (net, d["rails"][net], p["mpn"], sheet["vmax"])))
    nets = {}
    for ref, p in d["parts"].items():
        for pin, net in p["nets"].items():
            nets.setdefault(net, []).append("%s.%s" % (ref, pin))
    for net, pins in nets.items():
        if len(pins) == 1 and not net.startswith("NC"):
            findings.append(("erc", net, "single-pin net %s" % pins[0]))
    for cap in d["decoupling"]:
        dist = math.dist(d["placement"][cap["cap"]], d["placement"][cap["pin_of"]])
        if dist > 3.0:
            findings.append(("decoupling", cap["cap"], "%.1f mm from %s (> 3 mm)" % (dist, cap["pin_of"])))
    return findings


def _heur_eval(screens, who):
    """Three evaluators, each alone, each with its own inspection method; violation + exact location + evidence only."""
    from html.parser import HTMLParser

    class P(HTMLParser):
        def __init__(self):
            super().__init__()
            self.els, self.labels, self.cur, self.text = [], set(), None, {}

        def handle_starttag(self, tag, a):
            a = dict(a)
            if tag == "label":
                self.labels.add(a.get("for"))
            self.els.append((tag, a))
            self.cur = a.get("id")

        def handle_data(self, d):
            if self.cur and d.strip():
                self.text[self.cur] = self.text.get(self.cur, "") + d.strip()
    out = []
    for name, html in screens.items():
        p = P()
        p.feed(html)
        if who == "E1":   # structure: labels, escape routes, confirmation of destructive actions
            for tag, a in p.els:
                if tag == "input" and a.get("id") not in p.labels:
                    out.append({"heuristic": "H6 recognition rather than recall", "location": "%s #%s" % (name, a["id"]), "evidence": "input has no label"})
                if tag == "a" and "display:none" in (a.get("style") or ""):
                    out.append({"heuristic": "H3 user control and freedom", "location": "%s #%s" % (name, a["id"]), "evidence": "Cancel link is hidden"})
                if tag == "button" and re.search(r"delete", p.text.get(a.get("id"), ""), re.I) and "data-confirm" not in a:
                    out.append({"heuristic": "H5 error prevention", "location": "%s #%s" % (name, a["id"]), "evidence": "destructive button without confirmation"})
        elif who == "E2":  # language: error messages, jargon, vague labels
            for k, v in p.text.items():
                if re.search(r"0x[0-9A-F]+|Error \d", v):
                    out.append({"heuristic": "H9 help users recover from errors", "location": "%s #%s" % (name, k), "evidence": "message is a code: %s" % v})
                if v in ("Submit", "OK"):
                    out.append({"heuristic": "H2 match with the real world", "location": "%s #%s" % (name, k), "evidence": "vague action label '%s'" % v})
        else:              # walkthrough: try the primary task step by step and note where it breaks
            ids = [a.get("id") for t, a in p.els]
            if "pay" in ids and not re.search(r"\d", p.text.get("pay", "")):
                out.append({"heuristic": "H1 visibility of system status", "location": "%s #pay" % name, "evidence": "amount not visible at the pay step"})
            if "cancel" in ids and any(t == "a" and a.get("id") == "cancel" and "display:none" in (a.get("style") or "") for t, a in p.els):
                out.append({"heuristic": "H3 user control and freedom", "location": "%s #cancel" % name, "evidence": "no visible way back from checkout"})
            for t, a in p.els:
                if t == "input" and a.get("id") not in p.labels:
                    out.append({"heuristic": "H6 recognition rather than recall", "location": "%s #%s" % (name, a["id"]), "evidence": "field purpose must be guessed"})
    return out


def _plot(path, curves, size=(360, 240), marks=None):
    from PIL import Image, ImageDraw
    w, h = size
    im = Image.new("RGB", size, (14, 16, 22))
    d = ImageDraw.Draw(im)
    vals = [v for c in curves.values() for v in c]
    lo, hi = min(0.0, min(vals)), max(1.0, max(vals))
    cols = [(231, 182, 90), (91, 209, 165), (120, 160, 255), (255, 107, 107), (200, 200, 200), (190, 120, 255)]
    for k, c in enumerate(curves.values()):
        n = max(1, len(c) - 1)
        d.line([(10 + (w - 20) * i / n, h - 10 - (h - 20) * (v - lo) / (hi - lo or 1)) for i, v in enumerate(c)], fill=cols[k % 6], width=2)
    im.save(path)
    return Path(path)


def _srt_t(t):
    ms = int(round(t * 1000))
    return "%02d:%02d:%02d,%03d" % (ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, ms % 1000)


def _ts_frames(ts, scale_loops):
    fr = []
    for f in range(120):
        t = f / 30
        im, d = canvas(160, 90)
        if t >= 2 * ts:
            d.rectangle([20, 30, 50, 60], fill=(255, 255, 255))
        per = 1.2 * (ts if scale_loops else 1.0)
        y = 5 + 70 * ((t % per) / per)
        d.rectangle([120, y, 124, y + 8], fill=(0, 0, 255))
        fr.append(np.array(im))
    return fr


def _t_to(f, level=0.9):
    return next(x / 1000 for x in range(1001) if f(x / 1000) >= level)


def _spring_stats(k, c, m=1.0):
    xs = sim_spring(k, c, m, dur=4.0)
    peaks = [i for i in range(1, len(xs) - 1) if xs[i] > 1.001 and xs[i] >= xs[i - 1] and xs[i] >= xs[i + 1]]
    over = float(xs.max() - 1) if xs.max() > 1 else 0.0
    out = np.nonzero(np.abs(xs - 1) > 0.02)[0]
    settle = (out[-1] + 1) / 1000 if len(out) else 0.0
    z = c / (2 * math.sqrt(k * m))
    est = math.exp(-math.pi * z / math.sqrt(1 - z * z)) if z < 1 else 0.0
    return {"zeta": z, "overshoot": over, "estimate": est, "bounces": len(peaks), "settle_s": settle}


def _overshoot(k, c):
    z = c / (2 * math.sqrt(k))
    return math.exp(-math.pi * z / math.sqrt(1 - z * z)) if z < 1 else 0.0


BUDGET = {"premium": (0, 0), "feedback": (0.02, 0.05), "success": (0.05, 0.10), "celebration": (0.15, 0.25)}


def _budget_lint(film):
    issues, bouncy = [], 0
    for sc in film:
        scene_bouncy = 0
        for m in sc["moves"]:
            o = _overshoot(*m["spring"]) if "spring" in m else (0.1 if m.get("ease", "").startswith(("back", "elastic")) else 0.0)
            lo, hi = BUDGET[m["intent"]]
            if not lo - 1e-3 <= o <= hi + 1e-3:
                issues.append("%s/%s: overshoot %.1f%% outside %s budget" % (sc["id"], m["el"], 100 * o, m["intent"]))
            if m.get("brand") and (o > 0 or m.get("ease", "").startswith(("back", "elastic"))):
                issues.append("%s/%s: bounce on a brand mark" % (sc["id"], m["el"]))
            if "spring" in m and m["spring"][1] < 16:
                scene_bouncy += 1
            bouncy += o > 0.0
        if scene_bouncy > 1:
            issues.append("%s: %d bouncy springs in one scene" % (sc["id"], scene_bouncy))
    if bouncy > 2:
        issues.append("film: %d snap/pop/land springs (> 2)" % bouncy)
    return issues


def _scale_frames(scales, size=(240, 160), box=40):
    fr = []
    for s in scales:
        im, d = canvas(*size)
        h = box * s / 2
        cx, cy = size[0] / 2, size[1] / 2
        d.rectangle([cx - h, cy - h, cx + h, cy + h], fill=(255, 255, 255))
        fr.append(np.array(im))
    return fr


def _ant_curves(n=36, fps=30, D=200.0):
    """Main part: 5-frame anticipation (-10% of travel), then a 300 ms inOut-quint move; secondary lags 3 frames with a
    spring overshoot."""
    io = bez(.83, 0, .17, 1)
    main = []
    for f in range(n):
        if f < 5:
            main.append(-0.10 * D * math.sin(math.pi / 2 * f / 5))
        else:
            u = min(1, (f - 5) / 9)
            main.append(-0.10 * D + (D + 0.10 * D) * io(u))
    sec = []
    for f in range(n):
        g = f - 3
        base = main[g] if g >= 0 else 0.0
        if g >= 14:
            base = D + 0.07 * D * math.exp(-(g - 14) / 3) * math.cos((g - 14) / 2.2)
        sec.append(base)
    return main, sec


def _back_out(p, s=1.70158):
    p -= 1
    return 1 + (s + 1) * p ** 3 + s * p ** 2


def _cut_times(path, size=(64, 36), thr=40.0, fps=30):
    fr = fx.frames(path, size=size)
    d = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2, 3))
    return [round((i + 1) / fps, 4) for i in np.nonzero(d > thr)[0]], fr


def _loop_frame(t, D, k_rot=1, k_noise=1):
    im, d = canvas(96, 96, (0, 0, 0))
    t = t % D                                  # every driver is periodic in the duration
    a = 2 * math.pi * k_rot * t / D
    d.ellipse([48 + 30 * math.cos(a) - 6, 48 + 30 * math.sin(a) - 6, 48 + 30 * math.cos(a) + 6, 48 + 30 * math.sin(a) + 6], fill=(255, 255, 255))
    nx, ny = math.cos(2 * math.pi * k_noise * t / D), math.sin(2 * math.pi * k_noise * t / D)
    g = int(80 + 60 * math.sin(3 * nx + 2 * ny))
    d.rectangle([0, 88, 95, 95], fill=(g, g, g))
    return np.array(im)


def _ae_curve(a, n=4001):
    """After Effects temporal ease with zero key speeds and influence a on both keys as a Bezier in (time, value)."""
    u = np.linspace(0, 1, n)
    bx = lambda p1, p2: 3 * p1 * u * (1 - u) ** 2 + 3 * p2 * u ** 2 * (1 - u) + u ** 3
    t = bx(a, 1 - a)
    v = bx(0.0, 1.0)
    return t, v


def _peak_ratio(a):
    t, v = _ae_curve(a)
    sp = np.gradient(v, t)
    return float(np.nanmax(sp[np.isfinite(sp)]))


def _needle_steps(k1, k2, a, fps=30):
    """Per-frame value steps of an AE ease between key frames k1 and k2 (influence a on both)."""
    t, v = _ae_curve(a, 20001)
    T = k1 + (k2 - k1) * t
    vals = np.interp(np.arange(k1, k2 + 1), T, v)
    return {int(k1 + i): float(vals[i + 1] - vals[i]) for i in range(len(vals) - 1)}


def _relay(s, n=4001):
    t = np.linspace(0, 1 + s, n)
    e = lambda x: smoothstep(x) if np.isscalar(x) else np.where(x <= 0, 0, np.where(x >= 1, 1, x * x * (3 - 2 * x)))
    x = e(np.clip(t, 0, 1))
    y = e(np.clip(t - s, 0, 1))
    pos = np.stack([x, y], 1)
    sp = np.hypot(np.gradient(x, t), np.gradient(y, t))
    closest = float(np.hypot(pos[:, 0] - 1, pos[:, 1]).min())
    corner = (t >= 0.5) & (t <= s + 0.5)              # between the two moves' own speed peaks
    return closest, float(sp[corner].min() / 1.5)


EASES = {"linear": lambda p: p, "expoOut": lambda p: 1 if p >= 1 else 1 - 2 ** (-10 * p), "inOut": smoothstep}


def track_sample(keys, t):
    """Keys [[t, value, ease?]]: the ease on a key shapes the segment ARRIVING at it."""
    if t <= keys[0][0]:
        return keys[0][1]
    for a, b in zip(keys, keys[1:]):
        if t <= b[0]:
            p = (t - a[0]) / (b[0] - a[0])
            return a[1] + (b[1] - a[1]) * EASES[b[2] if len(b) > 2 else "linear"](p)
    return keys[-1][1]


SR = 48000


WORDS = [("مرحبا", 0.50, 0.90), ("بكم", 0.95, 1.30), ("في", 1.35, 1.50), ("البرنامج", 1.55, 2.20),
         ("اليوم", 2.80, 3.20), ("نتكلم", 3.25, 3.70), ("عن", 3.75, 3.90), ("الصوت", 3.95, 4.50)]


def words_json(words=WORDS):
    return [{"text": w, "start": a, "end": b} for w, a, b in words]


def burst_track(onsets, secs, f0=220.0, dur=0.25, sr=SR, amp=0.5, low=False):
    """Voiced bursts that start exactly at each onset (sharp attack, decaying), silence elsewhere."""
    t = np.arange(int(secs * sr)) / sr
    x = np.zeros_like(t)
    for o in onsets:
        m = (t >= o) & (t < o + dur)
        tt = t[m] - o
        tone = (np.sin(2 * np.pi * f0 * tt) if low else sum(np.sin(2 * np.pi * f0 * k * tt) / k for k in range(1, 6)))
        x[m] += amp * tone * np.exp(-tt / (dur / 3)) * np.minimum(1, tt / 0.002) * np.minimum(1, (dur - tt) / 0.02)
    return x


def onsets_flux(x, sr=SR, hop=240, thr=0.3):
    """Spectral-flux onsets (s): positive log-magnitude differences, normalised, local maxima above thr."""
    n = 1024
    win = np.hanning(n)
    frames = [np.abs(np.fft.rfft(x[i:i + n] * win)) for i in range(0, len(x) - n, hop)]
    L = np.log1p(np.array(frames) * 10)
    flux = np.concatenate([[0], np.maximum(0, np.diff(L, axis=0)).sum(1)])
    flux /= flux.max() + 1e-9
    peaks = [i for i in range(1, len(flux) - 1) if flux[i] > thr and flux[i] >= flux[i - 1] and flux[i] > flux[i + 1]]
    return [(p * hop + n / 2) / sr + 0.0045 for p in peaks], flux


def word_budget(sec):
    table = [((3, 4), (8, 12)), ((5, 6), (15, 22)), ((7, 8), (22, 30))]
    for (a, b), r in table:
        if a <= sec <= b:
            return r
    return (round(sec * 2.5 * 0.8), round(sec * 2.5))


def _beat_lint(table, pauses):
    iss = []
    for row in table:
        for a in row.get("actions", []):
            if a["kind"] == "counter" and not (abs(a["end"] - row["number_word"]) <= 0.1 and 0.7 <= a["end"] - a["start"] <= 1.0):
                iss.append("%s: counter must finish on the number word, starting 0.7-1.0 s earlier" % row["line"])
            if a["kind"] == "node" and abs(a["at"] - row["name_word"]) > 0.1:
                iss.append("%s: node pops off its name" % row["line"])
            if a["kind"] == "camera" and not any(p0 <= a["at"] and a["at"] + a["dur"] <= p1 and p1 - p0 > 0.4 for p0, p1 in pauses):
                iss.append("%s: camera moves outside a pause" % row["line"])
            if a["kind"] == "photo_cut" and abs((row["word"] - a["at"]) * 30 - 2) > 0.5:
                iss.append("%s: photo cut not 2 frames before the word" % row["line"])
            if a["kind"] == "gesture" and not 2 <= (row["stress"] - a["at"]) * 30 <= 4:
                iss.append("%s: gesture not 2-4 frames before the stress" % row["line"])
        if len(row["visuals"]) != 1:
            iss.append("%s: %d visual proofs (want exactly 1)" % (row["line"], len(row["visuals"])))
    return iss
