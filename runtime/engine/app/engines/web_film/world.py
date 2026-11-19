"""World Film: one world, one continuous camera, every frame drawn by code (assets/engine.js + assets/camera.cjs).

check() enforces the measurable rules of the brief: one hero per beat, every on-screen phrase once, no typed phrase the
narrator also says, big type at the beat's camera, no unused decoration, hits inside their beat (and on their word),
beats cover the voiceover exactly, and a camera that never stops dead, jerks or cuts. It proves structure, not taste.
"""
from __future__ import annotations

import html
import json
import math
import re
import shutil
import subprocess
from pathlib import Path

from .page import ASSETS, DATA, PRESETS, fill

R = PRESETS["world"]
KINDS, ACTIONS, WORLD_KINDS = set(R["kinds"]), set(R["actions"]), set(R["world_kinds"])
CAMERA_JS = ASSETS / "camera.cjs"

AR_DIAC = re.compile(r"[ً-ْٰـ]")
STOP = {"يا", "في", "من", "على", "و", "ال", "the", "a", "of", "to", "and"}


def norm_words(s: str) -> list[str]:
    """Words for comparing narration and type: no diacritics, unified alef/ta-marbuta/ya, no clitics or stop words."""
    s = AR_DIAC.sub("", s or "")
    s = re.sub("[أإآ]", "ا", s).replace("ة", "ه").replace("ى", "ي")
    out = []
    for w in re.findall(r"[\w]+", s.lower()):
        w = re.sub(r"^(وال|بال|لل|ال|و|ب)(?=\w{3,})", "", w)
        if w and w not in STOP:
            out.append(w)
    return out


def load(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def example_plan() -> dict:
    """A 12-second world film that passes every check: a map, a book, a route, a stamp, one title."""
    return load(DATA / "world_example.json")


def camera_samples(plan_path, fps: int) -> dict:
    r = subprocess.run(["node", str(CAMERA_JS), str(plan_path), "--fps", str(fps)], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def _num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _hits(beat: dict) -> list[dict]:
    return beat.get("hits") or ([beat["hit"]] if beat.get("hit") else [])


def _cam_ok(cam: dict) -> bool:
    return all(_num(cam.get(k)) for k in ("x", "y", "zoom")) and cam.get("zoom", 0) > 0


def _check_timing(beats, dur) -> list[str]:
    errs, t = [], 0.0
    for i, b in enumerate(beats):
        a, e = b.get("start"), b.get("end")
        if not _num(a) or not _num(e) or e <= a:
            errs.append(f"beat {i}: start/end invalid")
            continue
        if abs(a - t) > 1e-3:
            errs.append(f"beat {i} starts at {a}, expected {round(t, 3)}: beats must follow each other with no gap")
        t = e
    if beats and abs(t - dur) > 1e-3:
        errs.append(f"beats end at {round(t, 3)} but the film is {dur} s")
    return errs


def _check_text(i, b, by, hero, z, narr_all, seen_text, used) -> list[str]:
    errs, tid = [], b.get("text")
    if not tid:
        return errs
    if tid not in by or by[tid].get("kind") != "text":
        return [f"beat {i}: text {tid!r} is not a text object"]
    used.add(tid)
    to = by[tid]
    phrase = " ".join(norm_words(to.get("text", "")))
    if phrase in seen_text:
        errs.append(f"beat {i}: on-screen text {to['text']!r} already appeared in beat {seen_text[phrase]}: every phrase appears once")
    seen_text[phrase] = i
    tw = norm_words(to.get("text", ""))
    said = [w for w in tw if w in narr_all]
    if tw and len(said) * 2 >= len(tw):
        errs.append(f"beat {i}: {to['text']!r} is typed while the narrator says it ({' '.join(said)}): show it or type it, never both")
    px = to.get("size", 0) * z
    need = R["min_hero_text_px"] if hero == tid else R["min_label_px"]
    if px < need:
        errs.append(f"beat {i}: text {to['text']!r} is {px:.0f}px on screen, needs {need}px+ to read on a phone in one second")
    if len(tw) > 7:
        errs.append(f"beat {i}: {to['text']!r} has {len(tw)} words: too much to read in one beat")
    return errs


def _check_hits(i, b, by, hero, words, fps, used) -> list[str]:
    errs = []
    for hh in _hits(b):
        tgt = hh.get("target", hero)
        used.add(tgt)
        if hh.get("action") not in ACTIONS:
            errs.append(f"beat {i}: hit action must be one of {', '.join(sorted(ACTIONS))}")
        if tgt not in by:
            errs.append(f"beat {i}: hit target {tgt!r} is not an object")
        ht = hh.get("t")
        if not _num(ht) or not (b["start"] - 1e-6 <= ht <= b["end"] + 1e-6):
            errs.append(f"beat {i}: hit at {ht} is outside the beat {b['start']}-{b['end']}")
        elif hh.get("word") and words:
            cand = [w for w in words if norm_words(w["w"]) == norm_words(hh["word"]) and b["start"] - 0.05 <= w["start"] <= b["end"]]
            if not cand:
                errs.append(f"beat {i}: hit word {hh['word']!r} is not spoken in this beat")
            elif min(abs(w["start"] - ht) for w in cand) > 1.5 / fps:
                errs.append(f"beat {i}: hit at {ht} misses the word {hh['word']!r} (said at {cand[0]['start']}): land it on the word")
        if hh.get("action") == "draw" and not _num(hh.get("from")):
            errs.append(f"beat {i}: a draw hit needs 'from' (when the line starts drawing)")
    return errs


def _check_camera(camera, W, fps, stats) -> list[str]:
    s = camera["samples"]
    speeds = []
    for a, b in zip(s, s[1:]):
        z = (a[3] + b[3]) / 2
        speeds.append(math.hypot((b[1] - a[1]) * z, (b[2] - a[2]) * z) + abs(math.log(b[3] / a[3])) * W * 0.5)
    run = best = 0
    stop_at = None
    for i, v in enumerate(speeds):
        run = run + 1 if v < R["stop_speed"] else 0
        if run > best:
            best, stop_at = run, s[i][0]
    jerk = max((abs(b - a) for a, b in zip(speeds, speeds[1:])), default=0)
    stats["camera"] = {"max_speed_px_per_frame": round(max(speeds), 2), "min_speed_px_per_frame": round(min(speeds), 3),
                       "longest_stop_s": round(best / fps, 3), "max_jerk": round(jerk, 3), "keys": len(camera["keys"])}
    errs = []
    if best / fps > R["max_stop_s"]:
        errs.append(f"camera stops dead for {best / fps:.2f}s near {stop_at}s: keep it drifting toward the next move")
    if jerk > R["max_jerk"]:
        i = max(range(len(speeds) - 1), key=lambda k: abs(speeds[k + 1] - speeds[k]))
        errs.append(f"camera jerks near {s[i][0]}s (speed changes by {jerk:.1f}px/frame in one frame): ease the move")
    if max(speeds) > R["max_jump"]:
        errs.append(f"camera moves {max(speeds):.0f}px in one frame: that reads as a cut, slow the travel")
    return errs


def check(plan: dict, plan_path=None, camera: dict | None = None) -> tuple[list[str], dict]:
    stats: dict = {}
    fmt = plan.get("format") or {}
    W, H, fps = fmt.get("width"), fmt.get("height"), fmt.get("fps", 30)
    if not (isinstance(W, int) and isinstance(H, int) and W > 0 and H > 0):
        return ["format.width/height must be positive whole numbers"], stats
    dur = plan.get("duration")
    if not _num(dur) or dur <= 0:
        return ["duration must be a positive number (the voiceover's exact length)"], stats
    errs: list[str] = []
    if plan.get("audio_duration") and abs(plan["audio_duration"] - dur) > 1.0 / fps:
        errs.append(f"duration {dur} does not match the voiceover ({plan['audio_duration']} s): length must match exactly")
    objs = plan.get("objects") or []
    by = {}
    for o in objs:
        if o.get("kind") not in KINDS:
            errs.append(f"object {o.get('id')}: kind must be one of {', '.join(sorted(KINDS))}")
        if o.get("id") in by:
            errs.append(f"object id {o.get('id')} is used twice")
        by[o.get("id")] = o
    if sum(o.get("kind") == "map" for o in objs) > 1:
        errs.append("one world only: at most one map")
    beats = plan.get("beats") or []
    if len(beats) < 2:
        errs.append("need at least 2 beats")
    errs += _check_timing(beats, dur)
    seen_text: dict[str, int] = {}
    # "never both" holds across the whole film: a typed phrase may not be one the narrator says anywhere
    narr_all = {w for b in beats for w in norm_words(b.get("narration", ""))}
    used: set = set()
    words = plan.get("words") or []
    for i, b in enumerate(beats):
        hero = b.get("hero")
        if isinstance(hero, list):
            errs.append(f"beat {i}: one hero only, found {len(hero)}")
            continue
        if hero not in by:
            errs.append(f"beat {i}: hero {hero!r} is not an object")
            continue
        used.add(hero)
        used.update(b.get("also") or [])
        if not (_num(b.get("start")) and _num(b.get("end"))):
            continue  # already reported as invalid start/end
        if not _cam_ok(b.get("camera") or {}):
            errs.append(f"beat {i}: camera needs x, y and a positive zoom")
            continue
        z = b["camera"]["zoom"]
        errs += _check_text(i, b, by, hero, z, narr_all, seen_text, used)
        h = by[hero]
        if h.get("kind") == "photo" and h.get("w", 0) * z < R["min_photo_share"] * W:
            errs.append(f"beat {i}: hero photo {hero} is {h.get('w', 0) * z:.0f}px wide, push in to {R['min_photo_share'] * W:.0f}px+")
        if h.get("kind") == "text" and h.get("size", 0) * z < R["min_hero_text_px"]:
            errs.append(f"beat {i}: hero text is {h.get('size', 0) * z:.0f}px, needs {R['min_hero_text_px']}px+")
        if h.get("kind") == "text" and b.get("text") is None:
            tw = norm_words(h.get("text", ""))
            if tw and sum(w in narr_all for w in tw) * 2 >= len(tw):
                errs.append(f"beat {i}: hero text {h['text']!r} repeats the narration")
        errs += _check_hits(i, b, by, hero, words, fps, used)
    errs += [f"object {o.get('id')} ({o.get('kind')}) is never a hero, a text or a hit target: leave it out (less is more)"
             for o in objs if o.get("kind") not in WORLD_KINDS | {"pin"} and o.get("id") not in used]
    sampleable = all(_num(b.get("start")) and _num(b.get("end")) and _cam_ok(b.get("camera") or {}) for b in beats)
    if camera is None and plan_path is not None and sampleable:
        try:
            camera = camera_samples(plan_path, fps)
        except (OSError, subprocess.CalledProcessError) as e:
            errs.append(f"camera could not be sampled with node: {e}")
    if camera:
        errs += _check_camera(camera, W, fps, stats)
    return errs, stats


def beats_md(plan: dict) -> str:
    """The beat table to show the owner before building."""
    by = {o["id"]: o for o in plan.get("objects", [])}
    rows = ["| الوقت | الكلام | البطل الوحيد | نص على الشاشة | اللحظة على الكلمة |", "|---|---|---|---|---|"]
    for b in plan["beats"]:
        h = by.get(b["hero"], {})
        hero = (h.get("label") or h.get("text") or b["hero"]).replace("\n", " ")
        txt = by.get(b.get("text") or "", {}).get("text", "—").replace("\n", " · ")
        hit = "؛ ".join(f"{x['action']} على «{x.get('word', '')}» ({x['t']:.2f})" for x in _hits(b)) or "—"
        rows.append(f"| {b['start']:.2f}–{b['end']:.2f} | {b.get('narration') or '(موسيقى)'} | {hero} | {txt} | {hit} |")
    return f"# {plan.get('title', 'World film')}\n\n**العالم:** {plan.get('world_note', '')}\n\n" + "\n".join(rows) + "\n"


def review_times(plan: dict) -> dict:
    """Stills for every beat (mid and hit) plus 8-frame sequences across every camera move."""
    beats, moves = [], []
    for i, b in enumerate(plan["beats"]):
        ts = {round(b["start"] + (b["end"] - b["start"]) * 0.55, 3)} | {round(h["t"] + 0.35, 3) for h in _hits(b)}
        beats += sorted(ts)
        if i + 1 < len(plan["beats"]):
            c = plan["beats"][i + 1]["start"]
            moves.append([round(max(0, c - 1.0 + k * (2.0 / 7)), 3) for k in range(8)])
    return {"beats": beats, "moves": moves, "fps": plan["format"].get("fps", 30)}


def _font_source(base: Path, f: dict) -> Path:
    """A plan font is found next to the plan first, then (its `from`) in this package's assets or as given."""
    cands = [base / f["src"]] + ([ASSETS / f["from"], Path(f["from"])] if f.get("from") else [])
    return next((p for p in cands if p.is_file()), cands[0])


def build(plan_path, out) -> Path:
    """Page = engine + camera + plan; photos and fonts are copied next to the page (paths must stay inside the job)."""
    plan_path, out = Path(plan_path), Path(out)
    plan = load(plan_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    base = plan_path.parent
    for rel in [o["src"] for o in plan["objects"] if o.get("kind") == "photo"] + [f["src"] for f in plan.get("fonts", [])]:
        if Path(rel).is_absolute() or ".." in Path(rel).parts:
            raise SystemExit(f"asset path {rel!r} must stay inside the job folder (relative, no '..')")
    # photos must exist; a missing font only falls back to the browser's font
    copies = [(base / o["src"], out.parent / o["src"], True) for o in plan["objects"] if o.get("kind") == "photo"]
    copies += [(_font_source(base, f), out.parent / f["src"], False) for f in plan.get("fonts", [])]
    for src, dst, required in copies:
        if not src.is_file():
            if required:
                raise FileNotFoundError(f"photo not found: {src}")
            continue
        if src.resolve() != dst.resolve():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    page = fill((ASSETS / "world.html").read_text(encoding="utf-8"),
                TITLE=html.escape(str(plan.get("title", "world film"))),
                PLAN=json.dumps(plan, ensure_ascii=False).replace("</", "<\\/"),
                CAMERA=CAMERA_JS.read_text(encoding="utf-8"), ENGINE=(ASSETS / "engine.js").read_text(encoding="utf-8"))
    out.write_text(page, encoding="utf-8")
    return out
