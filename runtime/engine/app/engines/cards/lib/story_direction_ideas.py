"""Helpers of power_programs/story_direction_ideas.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from PIL import Image
from PIL import ImageDraw
import math
import numpy as np
import random
import re
from ._mind_common import require_fields
from ._mind_common import words


FPS = 30


def ease_out_cubic(t):
    t = min(max(t, 0.0), 1.0)
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    t = min(max(t, 0.0), 1.0)
    return 3 * t * t - 2 * t ** 3


def back_out(t, s=1.70158):
    t = min(max(t, 0.0), 1.0) - 1
    return t * t * ((s + 1) * t + s) + 1


def frames_of(sec, fps=FPS):
    return int(round(sec * fps))


def luminance(img):
    a = np.asarray(img, float)
    if a.ndim == 3:
        a = a[..., 0] * 0.2126 + a[..., 1] * 0.7152 + a[..., 2] * 0.0722
    return a.mean() / 255


def word_count(s):
    return len(words(s))


SEVEN = ["message", "production", "duration_platform", "language", "assets", "rhythm", "preview_or_final"]


DEFAULTS = {"duration_platform": "9:16, 30 s", "preview_or_final": "preview first", "rhythm": "medium"}


BLOCKING = {"message", "production", "language"}


def intake(given):
    missing = [k for k in SEVEN if k not in given]
    ask = [k for k in missing if k in BLOCKING]
    filled = {k: DEFAULTS[k] for k in missing if k in DEFAULTS}
    return ask, filled


ROUTES = {"talking_reel": ["كلام", "talking", "speech"], "song_reel": ["أغنية", "song"], "motion_2d": ["موشن", "motion"], "cinematic_3d": ["3d", "سينمائي"],
          "edit_my_footage": ["مونتاج", "footage"], "launch_video": ["launch", "إطلاق"]}


ADDONS = {"captions": ["ترجمة", "captions"], "music": ["موسيقى", "music"]}


def route(text):
    t = text.lower()
    hits = {r: sum(k in t for k in kws) for r, kws in ROUTES.items()}
    main = max(hits, key=lambda r: (hits[r], r)) if any(hits.values()) else "analyze_reference"
    adds = [a for a, kws in ADDONS.items() if any(k in t for k in kws)]
    return main, adds


CUTS = [0, 0.12, 0.36, 0.62, 0.84, 1.0]


BEATS = ["hook", "setup", "contrast", "payoff", "end_card"]


def proplan(seconds, fps, aspect):
    n = int(seconds * fps)
    edges = [round(c * n) for c in CUTS]
    shots = [{"beat": b, "f0": edges[i], "f1": edges[i + 1], "audio": "impact" if i in (0, 3) else "bed"} for i, b in enumerate(BEATS)]
    safe = (0.15, 0.80) if aspect == "9:16" else (0.08, 0.92)
    return shots, safe


def compose_review(edits, notes):
    parts = ["## Edits (apply exactly)"] + edits + ["## Notes"] + [f"{n['tc']} {n['scene']} {n['element']}: {n['text']}" for n in notes]
    return "\n".join(parts)


def full_power(film):
    fails = []
    if not 2 <= film["directions"] <= 3:
        fails.append("directions")
    if film["hook_s"] > 2:
        fails.append("hook")
    if film["height"] < 1080:
        fails.append("resolution")
    media = []
    if film["script"] and not film["voice"]:
        media.append("TTS")
    if film["silent_cuts"]:
        media.append("transition SFX")
    if film["duration"] > 10 and not film["music"]:
        media.append("music bed")
    return fails, media


def shots_from_boards(panels, total):
    t0s = [p["t"] for p in panels]
    return [{"t0": t0, "t1": (t0s[i + 1] if i + 1 < len(t0s) else total)} for i, t0 in enumerate(t0s)]


def digest(boards):
    import hashlib, json
    return hashlib.sha256(json.dumps(boards, sort_keys=True).encode()).hexdigest()[:12]


def lock_check(prompts, lock):
    missing = [i for i, p in enumerate(prompts) if lock not in p]
    if missing:
        raise ValueError(f"lock missing in {missing}")
    return True


def taste_keep(exports, key):
    last = exports[-12:]
    vals = [e[key] for e in last]
    out = []
    for v in set(vals):
        c = vals.count(v)
        if c >= 2 and c / len(last) >= 0.6:
            out.append(v)
    return out


def render_hook(move_start_frame, n=10):
    frames = []
    for f in range(n):
        im = Image.new("L", (32, 18), 0)
        x = 4 + max(0, f - move_start_frame) * 2
        ImageDraw.Draw(im).rectangle([x, 6, x + 4, 10], fill=255)
        frames.append(np.asarray(im, float))
    return frames


def first_motion(frames):
    for i in range(1, len(frames)):
        if np.abs(frames[i] - frames[i - 1]).mean() > 0.5:
            return i
    return None


CONFLICTS = {"character vs character", "character vs society", "character vs nature", "character vs technology", "character vs supernatural", "character vs self"}


def story_lint(story):
    issues, warns = [], []
    if story["central_conflict"] not in CONFLICTS:
        issues.append("conflict label")
    if len(story["beats"]) < 3:
        issues.append("fewer than 3 beats")
    for i, b in enumerate(story["beats"]):
        miss = [k for k in ("goal", "motivation", "conflict", "stakes", "choice") if not b.get(k)]
        if miss:
            issues.append(f"beat {i} missing {miss}")
    intro = sum(1 for b in story["beats"] if b.get("mode") == "introspection") / max(1, len(story["beats"]))
    if intro > 0.3:
        warns.append("introspection > 30%")
    return 100 - 12 * len(issues) - 4 * len(warns), issues, warns


def act_shares(acts, total):
    return {k: v / total for k, v in acts.items()}


def edit_metrics(cuts, duration):
    lens = np.diff(cuts + [duration])
    return float(np.mean(lens)), int(sum(1 for c in cuts if 0 < c < 60)), float(max(lens))


def bar_grid(bpm, bars, beats_per_bar=4):
    return [round(i * beats_per_bar * 60 / bpm, 4) for i in range(bars + 1)]


def choreo_check(els):
    errs = []
    for e in els:
        if e["exit"] > e["enter"] * 0.7:
            errs.append(f"{e['id']} exit not faster")
    if max(e["delay"] for e in els) >= 0.5:
        errs.append("stagger >= 500 ms")
    if sum(e["moving"] for e in els) > len(els) / 3:
        errs.append("more than 1/3 moving")
    return errs


def cut_detect(frames, thr=30):
    return [i for i in range(1, len(frames)) if np.abs(frames[i].astype(float) - frames[i - 1]).mean() > thr]


def headline(cue):
    nums = re.findall(r"\d+(?:[.,]\d+)?%?", cue)
    if nums:
        return nums[0]
    return max(cue.split(), key=len)


def path_samples(n=60):
    t = np.linspace(0, 1, n)
    return np.stack([t * 100, 50 + 30 * np.sin(t * math.pi)], 1)


def pulse(t_since_beat):
    if t_since_beat < 0.06:
        return 1 + 0.25 * t_since_beat / 0.06
    if t_since_beat < 0.28:
        return 1.25 - 0.25 * ease_out_cubic((t_since_beat - 0.06) / 0.22)
    return 1.0


def payoff_plan(lines, dur):
    counts = {l: lines.count(l) for l in lines}
    refrain = [l for l, c in counts.items() if c >= 2]
    idx = max(i for i, l in enumerate(lines) if l in refrain) if refrain else len(lines) - 1
    return {"payoff": lines[idx], "scale": 1.22, "hold": 2.2, "in_last_40pct": idx / len(lines) >= 0.6}


CONCEPTS = {"شمس": "sun", "قمر": "moon", "قلب": "heart", "ساع": "clock", "مال": "money", "طريق": "road", "بيت": "home", "مطر": "rain", "نور": "light", "sun": "sun", "heart": "heart"}


def concept_of(word):
    w = re.sub(r"^(و|ف|ب|ل)?(ال)?", "", word)
    for root, c in CONCEPTS.items():
        if w.startswith(root) or word.lower().startswith(root):
            return c
    return None


def darkness_frame():
    im = Image.new("L", (64, 36), 2)
    ImageDraw.Draw(im).ellipse([30, 16, 33, 19], fill=255)
    return im


def mood_lerp(start, target, k=0.04, frames=60):
    v = start
    for _ in range(frames):
        v += (target - v) * k
    return v


def pop(t):
    if t < 0.15:
        return 1.1 * t / 0.15
    if t < 0.3:
        return 1.1 - 0.1 * (t - 0.15) / 0.15
    return 1.0


def beacon_interval(r):
    return 1 / math.sqrt(1 - 1 / r)


def direct_plan(words_json):
    hook = words_json[1]["start"]
    end = words_json[-1]["end"] + 0.35
    lines, cur = [], []
    for w in words_json:
        cur.append(w["w"])
        if len(cur) == 6:
            lines.append(cur)
            cur = []
    if cur:
        lines.append(cur)
    stress = max(words_json, key=lambda w: w["loud"] * (w["end"] - w["start"]))["w"]
    return {"hook_release": hook, "end": round(end, 3), "lines": lines, "keyword": stress}


def pick_stages(stages, n):
    if n < 1 or n > 200:
        raise ValueError("1-200 clips")
    if n == 1:
        return [stages[-1]]
    asm = stages[:-1]
    out = [asm[min(len(asm) - 1, i * len(asm) // (n - 1))] for i in range(n - 1)]
    return out + [stages[-1]]


def viral_session(replies):
    stage, log = 1, []
    for r in replies:
        if r == "NEXT" and stage < 5:
            stage += 1
        elif r in "12345":
            log.append((stage, int(r)))
    return stage, log, stage == 5 and len({s for s, _ in log}) == 5


def caption_windows(cuts, end):
    out = []
    for a, b in zip(cuts, cuts[1:] + [end]):
        out.append((round(a + 0.25, 2), round(b - 0.3, 2)))
    return out


def face_segments(flags, fps=1):
    segs, start = [], None
    for i, f in enumerate(flags + [False]):
        if f and start is None:
            start = i
        if not f and start is not None:
            segs.append((start / fps, i / fps))
            start = None
    return segs


def wrap(text, n=18):
    lines, cur = [], ""
    for w in text.split():
        if len(cur) + len(w) + (1 if cur else 0) > n:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    lines.append(cur)
    return lines


CONTRACTS = {"plotter": (4, 7, 2, 5), "stickman": (4, 7, None, None), "whiteboard": (4, 6, None, None)}


def script_ok(style, lines):
    lo, hi, wlo, whi = CONTRACTS[style]
    if not lo <= len(lines) <= hi:
        return False
    if wlo and any(not wlo <= word_count(l) <= whi for l in lines):
        return False
    return True


def draw_router(req):
    r = req.lower()
    if "as is" in r or "code" in r:
        return "to_python"
    if "realistic" in r or "reflection" in r:
        return "three.js"
    if "film" in r:
        return "painter film"
    return "kosif scene + judge"


def ideate(problem, concepts, n, seed):
    if n > 30:
        raise ValueError("n <= 30")
    rng = random.Random(seed)
    ops = ["contiguity", "similarity", "contrast"]
    return [f"{ops[i % 3]}: {problem} x {rng.choice(concepts)}" for i in range(n)]


SURPRISE = re.compile(r"\b(surpris|actually|turns out|nobody|\d+%|instead)", re.I)


def cta_plan(duration):
    if duration <= 60:
        return [("end", duration - 3)]
    return [("mid", round(duration * 0.5)), ("end", duration - 5)]


def jev(p_yes):
    return "keep" if p_yes >= 0.6 else "drop" if p_yes < 0.4 else "ask"


SLOTS = ["PRODUCT", "STORY", "FORMAT", "LOOK", "MOTION", "SOUND", "QUALITY", "OUTPUT"]


def brief_lint(b):
    errs = require_fields(b, SLOTS)
    if b.get("LOOK") and not re.search(r"#[0-9a-fA-F]{6}", b["LOOK"]):
        errs.append("LOOK needs hex colours")
    if b.get("has_speech") and "voice" not in b.get("SOUND", "").lower():
        errs.append("voice must be master clock")
    return errs


def spring_closed(t, zeta=0.7, w=12):
    wd = w * math.sqrt(1 - zeta ** 2)
    return 1 - math.exp(-zeta * w * t) * (math.cos(wd * t) + zeta * w / wd * math.sin(wd * t))
