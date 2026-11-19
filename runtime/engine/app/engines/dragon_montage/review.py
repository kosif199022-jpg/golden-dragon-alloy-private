"""Station 7 «يتفرج وينقد»: render/final.mp4 + edl + analysis + brief -> review.json, frames review/rN_fXX.jpg and
review/VISION_PROMPT.md for Claude's own eyes (--add-note / --fix append taste notes and fixes).

Every automated check carries pass, evidence and (when it failed) output timestamps in "at"; each failure maps to
concrete fixes {event, action, detail, check}; global fixes use event "*" with a target (audio|grade|captions|...).
Measured with qc.verify (spec + loudness), qc.motion (energy, frozen stretches), ffmpeg blackdetect / silencedetect.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from . import common as C
from . import qc
from .think import hook_roles
from ..media import probe

STATION = "review"
ACTIONS = ("trim", "drop", "swap", "retime", "regrade", "extend", "add")
MAX_ROUNDS = 3
DEAD_AIR_SILENCE, DEAD_AIR_FLAT = 0.7, 2.0
HOOK_START, HOOK_WINDOW = 0.5, 3.0
BEAT_TOL, BEAT_RATIO_MIN = 0.08, 0.6
BLACK_MIN, SILENCE_DB, PEAK_MAX = 0.1, -45, -1.0
WEIGHTS = {"technical": 1.0, "hook-in-3s": 2.0, "dead-air": 1.5, "cuts-on-beat": 0.75, "shot-length": 0.75,
           "caption-coverage": 1.0, "repetition": 1.0, "duration": 1.0, "safe-area": 0.75, "black-frames": 1.5,
           "audio-clipping": 1.0}
CRITICAL = {"hook-in-3s", "dead-air", "black-frames", "technical"}
PACING = {"high": (0.8, 2.5), "mid": (1.2, 4.0), "low": (2.0, 7.0)}
SAFE = {"9:16": {"bottom": 0.20, "top": 0.10}, "4:5": {"bottom": 0.12, "top": 0.08},
        "1:1": {"bottom": 0.10, "top": 0.06}, "16:9": {"bottom": 0.08, "top": 0.05}}
SPEECH_PACING = (1.5, 9.0)      # a spoken phrase is judged as a phrase, not as a b-roll beat
CAP_ORDER = ("shot-length", "repetition", "duration", "dead-air", "black-frames", "hook-in-3s")
KEYWORDS = {"hook-in-3s": ["hook", "هوك", "بداية", "اول", "أول", "scroll", "grab", "attention", "انتباه"],
            "dead-air": ["boring", "ممل", "slow", "بطيء", "dead", "silence", "سكوت", "drag"],
            "duration": ["long", "طويل", "short", "قصير", "length", "مدة"],
            "shot-length": ["pace", "pacing", "rhythm", "ايقاع", "إيقاع", "fast", "سريع"],
            "cuts-on-beat": ["beat", "music", "موسيقى", "بيت"],
            "caption-coverage": ["caption", "subtitle", "ترجمة", "كابشن", "نص", "text"],
            "repetition": ["repeat", "تكرار", "مكرر", "same"], "black-frames": ["black", "اسود", "أسود"]}


def r3(x) -> float:
    return round(float(x), 3)


def speech_pacing() -> tuple:
    sp = ((C.data("editor_mind.json").get("pacing_by_kind") or {}).get("speech") or {}).get("shot_s")
    return (float(sp[0]), float(sp[1])) if sp and len(sp) == 2 else SPEECH_PACING


def safe_area(aspect: str) -> dict:
    base = dict(SAFE.get(aspect, {"bottom": 0.1, "top": 0.05}))
    sa = (C.data("caption_styles.json").get("safe_area") or {}).get(aspect) or {}
    return {**base, **{k: float(v) for k, v in sa.items() if k in ("bottom", "top") and v is not None}}


def qscore(shot) -> float:
    v = ((shot or {}).get("quality") or {}).get("score")
    try:
        return float(v) if v is not None else 0.5
    except (TypeError, ValueError):
        return 0.5


def rel(job: Path, p):
    return None if not p else Path(p) if Path(p).is_absolute() else job / p


def speed(ev: dict) -> float:
    return float(ev.get("speed") or 1.0) or 1.0


def out_span(ev: dict) -> tuple:
    a = float(ev["rec_in"])
    return a, a + (float(ev["src_out"]) - float(ev["src_in"])) / speed(ev)


def src_to_out(ev: dict, t: float) -> float:
    return float(ev["rec_in"]) + (t - float(ev["src_in"])) / speed(ev)


def out_to_src(ev: dict, t: float) -> float:
    return float(ev["src_in"]) + (t - float(ev["rec_in"])) * speed(ev)


def events_in(edl: dict, a: float, b: float) -> list:
    return [ev for ev in edl["events"] if min(out_span(ev)[1], b) - max(out_span(ev)[0], a) > 1e-3]


def clip_of(analysis: dict, cid: str) -> dict:
    return next((c for c in analysis.get("clips", []) if c.get("id") == cid), {})


def shot_of(analysis: dict, ev: dict) -> dict:
    clip = clip_of(analysis, ev["clip"])
    s = next((s for s in clip.get("shots", []) if ev.get("shot") and s.get("id") == ev["shot"]), None)
    mid = (float(ev["src_in"]) + float(ev["src_out"])) / 2
    return s or next((s for s in clip.get("shots", []) if s["start"] <= mid < s["end"]), {})


def is_speech_event(ev: dict, analysis: dict) -> bool:
    if ev.get("kind"):
        return ev["kind"] == "speech"
    a, b = float(ev["src_in"]), float(ev["src_out"])
    return sum(1 for w in clip_of(analysis, ev["clip"]).get("words", []) if a <= (w["start"] + w["end"]) / 2 < b) >= 2


def has_speech(analysis: dict) -> bool:
    return any(len(c.get("words") or []) >= 5 for c in analysis.get("clips", []))


def voiced_spans(edl: dict, analysis: dict) -> list:
    """Output spans where silence is dead air: speech events with real, unmuted audio."""
    return [out_span(ev) for ev in edl["events"] if not (ev.get("mute") or clip_of(analysis, ev["clip"]).get("has_audio") is False
                                                        or not is_speech_event(ev, analysis))]


def output_words(edl: dict, analysis: dict) -> list:
    out = []
    for ev in edl["events"]:
        for w in clip_of(analysis, ev["clip"]).get("words", []):
            if float(ev["src_in"]) <= (w["start"] + w["end"]) / 2 < float(ev["src_out"]):
                out.append({"w": w.get("w", ""), "event": ev["id"],
                            "start": r3(src_to_out(ev, max(w["start"], float(ev["src_in"])))),
                            "end": r3(src_to_out(ev, min(w["end"], float(ev["src_out"]))))})
    return sorted(out, key=lambda w: w["start"])


# ----------------------------------------------------------------- measuring (receipted)
def measure(job: Path, video: Path, brief: dict, edl: dict) -> dict:
    info = probe(video)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), {})
    m = {"missing": [], "width": int(v.get("width") or 0), "height": int(v.get("height") or 0),
         "duration": float(info["format"].get("duration") or 0), "has_audio": any(s["codec_type"] == "audio" for s in info["streams"])}
    asp = C.ASPECTS.get(brief.get("aspect") or "") or (m["width"], m["height"])
    m["verify"] = qc.verify(video, asp, float(edl.get("fps") or 30), None, float(edl.get("audio", {}).get("target_lufs", -14)),
                            no_audio=not m["has_audio"])
    C.save(job / "review" / "verify_video.json", m["verify"])
    C.receipt(job, STATION, "verify_video", ["qc.verify", video], 0 if m["verify"]["pass"] else 1, 0.0)
    try:
        m["motion"] = qc.motion(video, fps=10, freeze=DEAD_AIR_FLAT)
        C.receipt(job, STATION, "video_eyes.motion", ["qc.motion", video, "fps=10"], 0, 0.0)
    except (ValueError, StopIteration, OSError):
        m["motion"] = None
        m["missing"].append("video_eyes.motion")
    res = C.run(job, STATION, "ffmpeg.blackdetect", ["ffmpeg", "-v", "info", "-nostats", "-i", video, "-vf",
                f"blackdetect=d={BLACK_MIN}:pix_th=0.10", "-an", "-f", "null", "-"], check=False)
    m["black"] = [{"from": r3(float(a)), "to": r3(float(b))}
                  for a, b in re.findall(r"black_start:\s*([\d.]+)\s+black_end:\s*([\d.]+)", res.stderr)]
    m["silences"], m["true_peak"], m["lufs"] = [], None, None
    if m["has_audio"]:
        err = C.run(job, STATION, "ffmpeg.silencedetect+ebur128", ["ffmpeg", "-v", "info", "-nostats", "-i", video, "-vn", "-af",
                    f"silencedetect=noise={SILENCE_DB}dB:d={DEAD_AIR_SILENCE},ebur128=peak=true", "-f", "null", "-"],
                    check=False).stderr
        starts = [float(x) for x in re.findall(r"silence_start:\s*(-?[\d.]+)", err)]
        ends = [float(x) for x in re.findall(r"silence_end:\s*(-?[\d.]+)", err)]
        ends += [m["duration"]] * (len(starts) - len(ends))
        m["silences"] = [{"from": r3(max(0.0, s)), "to": r3(e)} for s, e in zip(starts, ends)]
        pk = re.search(r"True peak:\s*Peak:\s*(-?[\d.]+|-inf)", err)
        m["true_peak"] = float(pk.group(1)) if pk and pk.group(1) != "-inf" else None
        il = re.search(r"Integrated loudness:\s*I:\s*(-?[\d.]+)", err)
        m["lufs"] = float(il.group(1)) if il else None
    return m


# ----------------------------------------------------------------- checks
class Review:
    def __init__(self, edl: dict):
        self.edl, self.ids = edl, {e["id"] for e in edl["events"]}
        self.checks, self.fixes, self.capped = [], [], []

    def check(self, cid: str, ok: bool, evidence: str, **extra) -> None:
        self.checks.append({"id": cid, "pass": bool(ok), "evidence": evidence, **extra})

    def fix(self, event: str, action: str, detail: str, check: str, **extra) -> None:
        assert action in ACTIONS and (event == "*" or event in self.ids), (event, action)
        if not any((x["event"], x["action"], x["check"]) == (event, action, check) for x in self.fixes):
            self.fixes.append({"event": event, "action": action, "detail": detail, "check": check, "by": "auto", **extra})

    def fix_span(self, a: float, b: float, check: str, why: str) -> None:
        """A bad output interval -> drop (whole event) or trim (keep the longer clean side) on the events under it."""
        for ev in events_in(self.edl, a, b):
            s, e = out_span(ev)
            if a <= s + 0.05 and b >= e - 0.05:
                self.fix(ev["id"], "drop", f"{why} covers the whole event ({r3(s)}–{r3(e)}s): drop it", check)
                continue
            if max(0.0, a - s) >= max(0.0, e - b):
                ns, ne = float(ev["src_in"]), out_to_src(ev, max(s, a))
            else:
                ns, ne = out_to_src(ev, min(e, b)), float(ev["src_out"])
            if ne - ns < 0.3:
                self.fix(ev["id"], "drop", f"{why} at {r3(a)}–{r3(b)}s leaves <0.3s usable: drop it", check)
            else:
                self.fix(ev["id"], "trim", f"{why} at {r3(a)}–{r3(b)}s: trim source to {r3(ns)}–{r3(ne)}s", check,
                         src_in=r3(ns), src_out=r3(ne))


def check_technical(rv: Review, m: dict, edl: dict) -> None:
    vf = m.get("verify")
    if not vf:
        rv.check("technical", True, "verify not available — spec not checked", skipped=True)
        return
    # true peak is its own check (audio-clipping); duration is judged against the brief
    bad = [c for c in vf.get("checks", []) if not c.get("pass") and "true peak" not in c["check"]
           and "duration" not in c["check"] and "frame count" not in c["check"]]
    frozen = (m.get("motion") or {}).get("frozen", [])
    rv.check("technical", not bad, "verify_video: " + ("; ".join(f"{c['check']} = {c['value']}" for c in bad) or
             f"spec ok ({vf.get('codec')} {vf.get('width')}x{vf.get('height')} @ {vf.get('fps')})")
             + (f"; frozen stretches {len(frozen)}" if frozen else ""),
             at=[[f["from"], f["to"]] for f in frozen], tool="verify_video+video_eyes")
    loud = [c for c in bad if "loudness" in c["check"]]
    spec = [c for c in bad if c not in loud]
    if spec:
        rv.fix("*", "regrade", "re-render with delivery spec: " + "; ".join(c["check"] for c in spec), "technical", target="encode")
    if loud:
        rv.fix("*", "regrade", f"loudness {loud[0]['value']}: normalise to {edl.get('audio', {}).get('target_lufs', -14)} LUFS "
               "(loudnorm two-pass)", "technical", target="audio")


def check_hook(rv: Review, m: dict, analysis: dict, words: list) -> None:
    events = rv.edl["events"]
    if not events:
        return
    first = events[0]
    role = str(first.get("role") or first.get("reason", "")).lower()
    head = role.split(":")[0].strip()
    is_hook = bool(first.get("hook")) or head in hook_roles() or "hook" in head or "هوك" in role
    speech0 = next((w["start"] for w in words), None)
    tl = (m.get("motion") or {}).get("timeline", [])
    motion0 = tl[0]["energy"] if tl else None
    silent0 = any(s["from"] <= 0.05 and s["to"] > HOOK_START for s in m["silences"])
    starts = (speech0 is not None and speech0 < HOOK_START) or \
        (motion0 is not None and motion0 >= 0.6 and not any(b["from"] <= 0.05 for b in m["black"]))
    s, e = out_span(first)
    rv.check("hook-in-3s", is_hook and starts,
             f"first event {first['id']} role={'hook' if is_hook else repr(role[:40])}; "
             f"speech starts {speech0 if speech0 is not None else 'never'}s; motion energy 0s={motion0}"
             f"{'; opens on silence' if silent0 else ''}", at=[[0.0, r3(min(HOOK_WINDOW, e))]])
    if not is_hook:
        if has_speech(analysis):   # talking content: the hook is a spoken line, never a b-roll shot
            rv.fix(first["id"], "swap", "first event is not the hook: open on the strongest spoken hook line", "hook-in-3s",
                   role="hook", kind="speech")
        else:
            best = hook_candidate(analysis, events)
            rv.fix(first["id"], "swap", "first event is not the hook: open on the strongest hook shot" + (f" ({best})" if best else ""),
                   "hook-in-3s", role="hook", kind="broll", **({"with_shot": best} if best else {}))
    elif not starts:
        lead = out_to_src(first, speech0) - 0.1 if speech0 is not None and speech0 < e else None
        if lead and lead > float(first["src_in"]):
            rv.fix(first["id"], "trim", f"dead lead-in: speech starts at {speech0}s; start source at {r3(lead)}s", "hook-in-3s",
                   src_in=r3(lead), src_out=r3(float(first["src_out"])))
        else:
            rv.fix(first["id"], "swap", "hook opens without speech or motion in the first 0.5s: swap for a shot that starts "
                   "moving/talking immediately", "hook-in-3s")


def check_dead_air(rv: Review, m: dict, analysis: dict) -> None:
    gaps, dur = [], m["duration"]
    voiced = voiced_spans(rv.edl, analysis)
    for sl in m["silences"]:
        if sl["from"] >= dur - 0.3:
            continue
        for a, b in voiced:                       # only silence where someone should be talking counts
            fa, fb = max(a, sl["from"]), min(b, sl["to"])
            if fb - fa >= DEAD_AIR_SILENCE:
                gaps.append({"from": r3(fa), "to": r3(fb), "kind": "silence"})
    gaps += [{"from": fz["from"], "to": fz["to"], "kind": "flat-motion"} for fz in (m.get("motion") or {}).get("frozen", [])
             if fz["to"] - fz["from"] >= DEAD_AIR_FLAT]
    rv.check("dead-air", not gaps, "; ".join(f"{g['kind']} {r3(g['to'] - g['from'])}s at {g['from']}–{g['to']}s" for g in gaps)
             or f"no silence ≥{DEAD_AIR_SILENCE}s and no flat motion ≥{DEAD_AIR_FLAT}s",
             at=[[g["from"], g["to"]] for g in gaps], music=bool((rv.edl.get("audio", {}).get("music") or {}).get("path")))
    for g in gaps:
        rv.fix_span(g["from"], g["to"], "dead-air", f"{g['kind']} {r3(g['to'] - g['from'])}s")


def check_beats(rv: Review, analysis: dict) -> None:
    events = rv.edl["events"]
    beats = (analysis.get("music") or {}).get("beats") or []
    cuts = [float(ev["rec_in"]) for ev in events[1:]]
    if not (beats and cuts):
        rv.check("cuts-on-beat", True, "no music beats in analysis — not applicable", skipped=True)
        return
    near = lambda t: min(beats, key=lambda b: abs(b - t))  # noqa: E731
    on = [abs(near(t) - t) <= BEAT_TOL for t in cuts]
    ratio = sum(on) / len(on)
    off = [(ev, near(float(ev["rec_in"]))) for ev, k in zip(events[1:], on) if not k]
    rv.check("cuts-on-beat", ratio >= BEAT_RATIO_MIN, f"{sum(on)}/{len(on)} cuts within {BEAT_TOL}s of a beat", ratio=r3(ratio),
             at=[[r3(float(ev["rec_in"])), r3(float(ev["rec_in"]))] for ev, _ in off])
    if ratio < BEAT_RATIO_MIN:
        for ev, b in off:
            rv.fix(ev["id"], "retime", f"cut at {ev['rec_in']}s is off-beat: move it to beat {r3(b)}s", "cuts-on-beat", rec_at=r3(b))


def check_shot_length(rv: Review, analysis: dict, brief: dict) -> None:
    """Speech by phrase pacing (never cut mid-word), b-roll by the look/feeling pace."""
    (lo, hi), (slo, shi) = pacing_range(brief), speech_pacing()
    lens = []
    for ev in rv.edl["events"]:
        sp = is_speech_event(ev, analysis)
        lens.append((ev, out_span(ev)[1] - out_span(ev)[0], sp, (slo, shi) if sp else (lo, hi)))
    off = [x for x in lens if x[1] < x[3][0] - 0.05 or x[1] > x[3][1] + 0.05]
    share = 1 - len(off) / max(1, len(lens))
    rv.check("shot-length", share >= 0.75, f"{len(lens) - len(off)}/{len(lens)} shots inside their pace (speech {slo}–{shi}s "
             f"phrase-led, b-roll {lo}–{hi}s at energy {brief.get('energy')})"
             + ("; off: " + ", ".join(f"{ev['id']}={r3(L)}s" for ev, L, _, _ in off) if off else ""),
             range=[lo, hi], speech_range=[slo, shi], at=[list(map(r3, out_span(ev))) for ev, *_ in off])
    if share >= 0.75:
        return
    for ev, L, sp, (rlo, rhi) in off:
        if L > rhi:
            cut = float(ev["src_in"]) + rhi * float(ev.get("speed") or 1.0)
            if sp:
                cut = phrase_cut(clip_of(analysis, ev["clip"]), float(ev["src_in"]), cut)
                if cut is None:
                    continue
            rv.fix(ev["id"], "trim", f"{r3(L)}s is long for {'a spoken phrase' if sp else 'this pace'}: trim to ≤{rhi}s"
                   f"{' at a word gap' if sp else ''}", "shot-length", src_in=r3(float(ev["src_in"])), src_out=r3(cut))
        elif not sp:
            rv.fix(ev["id"], "extend", f"{r3(L)}s flashes by: hold it to ≥{rlo}s (inside its shot) or merge", "shot-length",
                   seconds=r3(rlo - L))


def check_captions(rv: Review, job: Path, render: dict, words: list) -> None:
    cues = srt_cues(rel(job, render.get("captions")))
    cap_on = bool(rv.edl.get("captions", {}).get("enabled"))
    if not words:
        rv.check("caption-coverage", True, "no speech in the cut — nothing to caption", skipped=True)
        return
    covered = [w for w in words if any(a - 0.15 <= (w["start"] + w["end"]) / 2 <= b + 0.15 for a, b in cues)]
    miss = [w for w in words if w not in covered]
    cov = len(covered) / len(words)
    rv.check("caption-coverage", cov >= 0.9, f"{len(covered)}/{len(words)} spoken words under a caption ({len(cues)} cues"
             f"{', captions disabled in edl' if not cap_on else ''})", ratio=r3(cov), at=[[w["start"], w["end"]] for w in miss[:20]])
    if cov < 0.9:
        rv.fix("*", "regrade", f"captions miss {len(miss)} words: regenerate captions from analysis words"
               + ("" if cap_on else " (enable captions in edl)"), "caption-coverage", target="captions")


def check_repetition(rv: Review, analysis: dict) -> None:
    events, seen, reps = rv.edl["events"], [], []
    for ev in events:
        for prev in seen:
            # a talking head is often ONE long shot: two different lines from it are not a repeat
            same_shot = ev.get("shot") and ev.get("shot") == prev.get("shot") and \
                not is_speech_event(ev, analysis) and not is_speech_event(prev, analysis)
            overlap = ev["clip"] == prev["clip"] and \
                min(float(ev["src_out"]), float(prev["src_out"])) - max(float(ev["src_in"]), float(prev["src_in"])) > 0.25
            if same_shot or overlap:
                reps.append((ev, prev))
                break
        seen.append(ev)
    rv.check("repetition", not reps, "; ".join(f"{a['id']} repeats {b['id']} ({a['clip']} {a['src_in']}–{a['src_out']})"
                                               for a, b in reps) or "no source shot used twice",
             at=[list(map(r3, out_span(a))) for a, _ in reps])
    for a, b in reps:
        rv.fix(a["id"], "drop" if len(events) > 3 else "swap", f"repeats {b['id']} — same source shot shown twice", "repetition")


def check_duration(rv: Review, analysis: dict, brief: dict, dur: float) -> tuple:
    events = rv.edl["events"]
    tgt = float(brief.get("target_seconds") or rv.edl.get("duration") or dur)
    tol = max(2.0, 0.15 * tgt)
    rv.check("duration", abs(dur - tgt) <= tol, f"{r3(dur)}s vs target {tgt}s (±{r3(tol)}s)", target=tgt, actual=r3(dur))
    if abs(dur - tgt) > tol and events:
        if dur > tgt:
            need = dur - tgt
            for ev in sorted(events[1:], key=lambda e: qscore(shot_of(analysis, e))):
                L = out_span(ev)[1] - out_span(ev)[0]
                rv.fix(ev["id"], "drop", f"{r3(dur - tgt)}s over target: drop weakest shot ({r3(L)}s)", "duration")
                need -= L
                if need <= 0:
                    break
        else:
            rv.fix("*", "add", f"{r3(tgt - dur)}s under target: add the best unused lines/shots back toward {tgt}s", "duration",
                   target="timeline", seconds=r3(tgt - dur))
    return tgt, tol


def check_safe_area(rv: Review, job: Path, m: dict, brief: dict, look, render: dict, words: list) -> None:
    want = C.ASPECTS.get(brief.get("aspect", ""))
    w, h = m["width"], m["height"]
    aspect_ok = not want or abs(w / max(1, h) - want[0] / want[1]) < 0.01
    cap_on = bool(rv.edl.get("captions", {}).get("enabled"))
    pos = ((look or {}).get("captions") or {}).get("position") or rv.edl.get("captions", {}).get("position", "lower")
    safe = safe_area(brief.get("aspect", ""))
    margin, align = ass_margin(job, render, h)
    cap_y = None
    if align in ("4", "5", "6", "7", "8", "9"):
        pos = "center" if align in ("4", "5", "6") else "top"     # the burned file decides, not the intent
    elif margin is not None:
        cap_y = margin / max(1, h)
    safe_ok = not cap_on or not words or pos == "center" or cap_y is None or cap_y >= safe["bottom"]
    rv.check("safe-area", aspect_ok and safe_ok, f"{w}x{h} vs brief {brief.get('aspect')}{'' if aspect_ok else ' MISMATCH'}; "
             f"captions {pos}, " + (f"bottom margin {r3(cap_y)} of height (safe ≥{safe['bottom']})" if cap_y is not None
                                    else "caption margin unknown (no .ass style) — check the frames"),
             aspect_ok=aspect_ok, caption_margin=cap_y)
    if not aspect_ok:
        rv.fix("*", "regrade", f"output is {w}x{h}, brief wants {brief.get('aspect')}: re-render at {want}", "safe-area", target="encode")
    if not safe_ok:
        rv.fix("*", "regrade", f"raise captions to ≥{int(safe['bottom'] * 100)}% from the bottom (platform UI covers the lower "
               "band) or use position=center", "safe-area", target="captions", min_bottom=r3(safe["bottom"] + 0.02))


def check_black_and_peak(rv: Review, m: dict) -> None:
    blk = [b for b in m["black"] if b["to"] - b["from"] >= BLACK_MIN]
    rv.check("black-frames", not blk, "; ".join(f"black {r3(b['to'] - b['from'])}s at {b['from']}–{b['to']}s" for b in blk)
             or "no black frames", at=[[b["from"], b["to"]] for b in blk])
    for b in blk:
        rv.fix_span(b["from"], b["to"], "black-frames", f"black {r3(b['to'] - b['from'])}s")
    if not m["has_audio"]:
        rv.check("audio-clipping", True, "no audio stream", skipped=True)
        return
    tp = m["true_peak"]
    rv.check("audio-clipping", tp is None or tp <= PEAK_MAX, f"true peak {tp} dBTP (max {PEAK_MAX}); integrated {m['lufs']} LUFS",
             true_peak=tp, lufs=m["lufs"])
    if not (tp is None or tp <= PEAK_MAX):
        rv.fix("*", "regrade", f"true peak {tp} dBTP: add a -1.5 dBTP limiter / lower voice gain", "audio-clipping", target="audio")


def run_checks(job: Path, rv: Review, m: dict, analysis: dict, brief: dict, look, render: dict) -> None:
    words = output_words(rv.edl, analysis)
    check_technical(rv, m, rv.edl)
    check_hook(rv, m, analysis, words)
    check_dead_air(rv, m, analysis)
    check_beats(rv, analysis)
    check_shot_length(rv, analysis, brief)
    check_captions(rv, job, render, words)
    check_repetition(rv, analysis)
    tgt, tol = check_duration(rv, analysis, brief, m["duration"])
    check_safe_area(rv, job, m, brief, look, render, words)
    check_black_and_peak(rv, m)
    cap_fixes(rv, tgt, tol, m["duration"])


def projected(rv: Review, dur: float) -> float:
    """Output length if every event fix were applied (drops and narrowing trims; extends add)."""
    by = {e["id"]: e for e in rv.edl["events"]}
    lost, dropped, seen = 0.0, set(), {}
    for f in rv.fixes:
        ev = by.get(f["event"])
        if ev is None:
            continue
        s, e = out_span(ev)
        if f["action"] == "drop" and ev["id"] not in dropped:
            dropped.add(ev["id"])
            lost += (e - s) - seen.pop(ev["id"], 0.0)
        elif f["action"] == "trim" and ev["id"] not in dropped and f.get("src_out") is not None:
            keep = (min(float(f["src_out"]), float(ev["src_out"])) - max(float(f.get("src_in", ev["src_in"])), float(ev["src_in"]))) / speed(ev)
            cut = max(0.0, (e - s) - keep)
            if cut > seen.get(ev["id"], 0.0):
                lost += cut - seen.get(ev["id"], 0.0)
                seen[ev["id"]] = cut
        elif f["action"] == "extend":
            lost -= float(f.get("seconds") or 0)
    return dur - lost


def cap_fixes(rv: Review, tgt: float, tol: float, dur: float) -> None:
    """A fix set must not push the cut under the target tolerance: shed the least critical shrinking fixes and ask the
    director to re-fill the rest with an `add` fix."""
    floor = tgt - tol
    if projected(rv, dur) >= floor:
        return
    rank = {c: i for i, c in enumerate(CAP_ORDER)}
    shed = []
    for f in sorted([f for f in rv.fixes if f["action"] in ("drop", "trim") and f["check"] != "duration"],
                    key=lambda f: rank.get(f["check"], 0)):
        if projected(rv, dur) >= floor or f["check"] in ("dead-air", "black-frames", "hook-in-3s"):
            break                                  # critical defects are fixed anyway; re-fill covers the length
        rv.fixes.remove(f)
        shed.append(f)
    after = projected(rv, dur)
    if after < tgt - 0.5:
        rv.fixes = [f for f in rv.fixes if not (f["event"] == "*" and f["action"] == "add")]
        rv.fixes.append({"event": "*", "action": "add", "check": "duration", "by": "auto", "target": "timeline",
                         "seconds": r3(tgt - after),
                         "detail": f"fixes would leave {r3(after)}s of {tgt}s: re-fill {r3(tgt - after)}s from unused material"})
    if shed:
        rv.capped = [{"event": f["event"], "action": f["action"], "check": f["check"]} for f in shed]


def hook_candidate(analysis: dict, events: list):
    used, best, score = {e.get("shot") for e in events}, None, -1.0
    for c in analysis.get("clips", []):
        for s in c.get("shots", []):
            if s["id"] in used:
                continue
            talk = any(s["start"] <= w["start"] < s["end"] for w in c.get("words", []))
            sc = qscore(s) + 0.2 * talk + 0.3 * s.get("motion_energy", 0) + 0.1 * bool(s.get("faces"))
            if sc > score:
                best, score = s["id"], sc
    return best


def phrase_cut(clip: dict, src_in: float, limit: float):
    """Latest cut <= limit in a gap between words (after >= 2 words), or None."""
    ws = sorted((w for w in clip.get("words", []) if float(w["start"]) >= src_in - 0.05), key=lambda w: float(w["start"]))
    best = None
    for i, w in enumerate(ws):
        end = float(w["end"])
        cut = min(end + 0.12, (end + (float(ws[i + 1]["start"]) if i + 1 < len(ws) else end + 0.3)) / 2)
        if cut > limit:
            break
        if i >= 1:
            best = cut
    return best


def pacing_range(brief: dict) -> tuple:
    p = brief.get("pacing") or {}
    if isinstance(p, dict) and p.get("shot_seconds"):
        return float(p["shot_seconds"][0]), float(p["shot_seconds"][1])
    e = float(brief.get("energy") if brief.get("energy") is not None else 0.5)
    return PACING["high" if e >= 0.7 else "low" if e < 0.35 else "mid"]


def srt_cues(path) -> list:
    if not path or not path.exists():
        return []
    ts = lambda s: (lambda h, mm, rest: int(h) * 3600 + int(mm) * 60 + float(rest))(*s.replace(",", ".").split(":"))  # noqa: E731
    return [(ts(a), ts(b)) for a, b in re.findall(r"(\d+:\d+:\d+[,.]\d+)\s*-->\s*(\d+:\d+:\d+[,.]\d+)",
                                                  path.read_text(encoding="utf-8", errors="replace"))]


def ass_margin(job: Path, render: dict, h: int) -> tuple:
    """(bottom margin in output pixels, Alignment) from the burned .ass: the smallest of the style MarginV, non-zero
    per-Dialogue MarginV overrides and \\pos(x,y) on bottom-aligned lines."""
    cands = [rel(job, x) for x in [render.get("captions_ass"), *(render.get("extra") or [])] if x]
    cands += sorted((job / "render").glob("*.ass")) if (job / "render").exists() else []
    for p in cands:
        if not (p and p.suffix == ".ass" and p.exists()):
            continue
        txt = p.read_text(encoding="utf-8", errors="replace")
        ph = re.search(r"PlayResY:\s*(\d+)", txt)
        play_h = int(ph.group(1)) if ph else h
        fmt, styles = re.search(r"^Format:\s*(Name.*)$", txt, re.M), re.findall(r"^Style:\s*(.*)$", txt, re.M)
        if not (fmt and styles):
            continue
        d = dict(zip([k.strip() for k in fmt.group(1).split(",")], [v.strip() for v in styles[0].split(",")]))
        an = re.search(r"\\an(\d)", txt)
        align = an.group(1) if an else d.get("Alignment", "2")
        if align not in ("1", "2", "3") or "MarginV" not in d:
            return None, align
        margins = [float(d["MarginV"])]
        ef = re.search(r"^Format:\s*(Layer.*)$", txt, re.M)
        ek = [k.strip() for k in ef.group(1).split(",")] if ef else []
        if "MarginV" in ek:
            iv = ek.index("MarginV")
            for line in re.findall(r"^Dialogue:\s*(.*)$", txt, re.M):
                parts = line.split(",", len(ek) - 1)
                if len(parts) > iv and parts[iv].strip().isdigit() and int(parts[iv]) > 0:
                    margins.append(float(parts[iv]))
        margins += [max(0.0, play_h - float(y)) for y in re.findall(r"\\pos\(\s*[-\d.]+\s*,\s*([-\d.]+)\s*\)", txt)]
        return min(margins) * h / play_h, align
    return None, None


def critique(concepts, checks: list) -> list:
    """The chosen concept's premortem and risks, marked happened / avoided / needs-eyes by the checks."""
    if not concepts:
        return []
    by, chosen = {c["id"]: c for c in checks}, (concepts.get("decision") or {}).get("chosen")
    items = list(concepts.get("premortem") or []) + [r for c in concepts.get("concepts", []) if c.get("id") == chosen
                                                       for r in c.get("risks") or []]
    out = []
    for risk in items:
        low = str(risk).lower()
        rel_ids = [cid for cid, kws in KEYWORDS.items() if any(k in low for k in kws) and cid in by]
        bad = [cid for cid in rel_ids if not by[cid]["pass"] and not by[cid].get("skipped")]
        out.append({"risk": risk, "related_checks": rel_ids,
                    "status": ("happened" if bad else "avoided") if rel_ids else "needs-eyes",
                    "note": ("premortem came true: " + ", ".join(bad)) if bad else
                    ("checks say this risk was avoided" if rel_ids else "no automatic check covers it — judge from the frames")})
    return out


def extract_frames(job: Path, video: Path, edl: dict, rnd: int, dur: float) -> list:
    for old in (job / "review").glob(f"r{rnd}_f*.jpg"):
        old.unlink()
    hook_end = min(HOOK_WINDOW, dur)
    plan = [{"t": r3(t), "event": None, "why": "hook"} for t in (0.05, hook_end / 2, max(0.05, hook_end - 0.1))]
    plan += [{"t": r3(min(out_span(ev)[0] + 0.04, max(0.0, dur - 0.05))), "event": ev["id"], "why": "event-start"} for ev in edl["events"]]
    frames = []
    for i, p in enumerate(plan, 1):
        if p["t"] >= dur:
            continue
        if p["event"] is None:
            p["event"] = next((ev["id"] for ev in edl["events"] if out_span(ev)[0] <= p["t"] < out_span(ev)[1]), None)
        name = f"review/r{rnd}_f{i:02d}.jpg"
        res = C.run(job, STATION, "ffmpeg.frame", ["ffmpeg", "-y", "-v", "error", "-ss", f"{p['t']:.3f}", "-i", video, "-frames:v",
                    "1", "-vf", "scale=480:-2", "-q:v", "4", job / name], out=job / name, check=False)
        if res.returncode == 0 and (job / name).exists():
            frames.append({"path": name, **p})
    return frames


def vision_prompt(job: Path, rnd: int, frames: list, checks: list, crit: list, brief: dict) -> Path:
    L = [f"# Dragon Montage — عين المخرج (round {rnd})", "",
         "انت دلوقتي المخرج اللي بيتفرج. بص على الصور دي بعينك (Read كل صورة)، وقول رأيك بذوق بني آدم مش بأرقام.",
         "You are the director watching the cut. Open every frame below (Read tool), then add taste notes.", "",
         f"**Brief:** {brief.get('one_truth') or brief.get('task', '')} · feeling: {brief.get('feeling')} · "
         f"platform: {brief.get('platform')} {brief.get('aspect')} · target {brief.get('target_seconds')}s", "",
         "## الفريمات / Frames", "", "| frame | t (s) | event | why |", "|---|---|---|---|"]
    L += [f"| `{f['path']}` | {f['t']} | {f['event'] or '—'} | {f['why']} |" for f in frames]
    L += ["", "## اللي الماكينة لقيته / What the machine already flagged", ""]
    L += [f"- ❌ **{c['id']}** — {c['evidence']}" for c in checks if not c["pass"]] or ["- كله عدّى في الفحص الآلي / all automatic checks passed"]
    if crit:
        L += ["", "## مخاطر الـ premortem / Premortem risks to judge", ""] + [f"- [{c['status']}] {c['risk']}" for c in crit]
    L += ["", "## Checklist — جاوب على كل سؤال", "",
          "1. **الهوك** — أول 3 فريمات: هل توقف الصباع عن السكرول؟ فيه وش/حركة/سؤال؟",
          "2. **التكوين** — الموضوع في التلت؟ الراس مش مقصوص؟ headroom, rule of thirds, crop.",
          "3. **الإحساس** — الصور بتوصل الإحساس المطلوب؟ does each shot serve the one truth?",
          "4. **اللون** — الألوان متسقة بين اللقطات؟ جلد طبيعي؟",
          "5. **الاستمرارية** — فيه نطة غريبة بين لقطتين؟ jump cut غير مقصود؟",
          "6. **الكابشن والمنطقة الآمنة** — مقروء؟ بعيد عن أزرار المنصة؟",
          "7. **التكرار** — فيه لقطتين شبه بعض؟", "8. **النهاية** — آخر لقطة فيها قفلة أو CTA واضح؟", "",
          "## إزاي تضيف رأيك / How to append", "", "```bash",
          f"python -m engines.dragon_montage station review --job {job} \\",
          "  --add-note \"الهوك ضعيف: الوش صغير ومفيش حركة في أول ثانية\" \\",
          "  --fix e001:swap:\"open on c02-s003 (close-up, starts talking at 0.1s)\" \\",
          "  --fix e004:trim:\"cut the dead 1s before the line seconds=1 side=head\"", "```", "",
          f"Fix format: `EVENT:ACTION:DETAIL` — ACTION ∈ {', '.join(ACTIONS)}; EVENT is an edl id (e001…) or `*` for global.",
          "Numbers go in as key=value inside DETAIL (seconds=, side=head|tail, src_in=, src_out=, speed=, rec_at=, with_shot=, "
          "target=) — the director never reads numbers out of prose.",
          "Any --fix turns the verdict into `fix`; the director applies them with `station direct --apply-review`.", ""]
    p = job / "review" / "VISION_PROMPT.md"
    p.write_text("\n".join(L), encoding="utf-8")
    return p


def score_and_verdict(checks: list) -> tuple:
    tot = sum(WEIGHTS.get(c["id"], 1.0) for c in checks)
    score = round(sum(WEIGHTS.get(c["id"], 1.0) for c in checks if c["pass"]) / tot, 3) if tot else 0.0
    crit_fail = any(not c["pass"] and c["id"] in CRITICAL for c in checks)
    return score, "ship" if score >= 0.85 and not crit_fail else "fix"


def review(job, rnd: int | None = None) -> dict:
    job = Path(job).resolve()
    render, edl, analysis, brief = (C.read(job, k) for k in ("render", "edl", "analysis", "brief"))
    concepts, look, prev = C.read_opt(job, "concepts"), C.read_opt(job, "look"), C.read_opt(job, "review")
    rnd = rnd if rnd is not None else (prev["round"] + 1 if prev else 1)
    video = rel(job, render["final"])
    if not video or not video.exists():
        raise FileNotFoundError(f"final video not found: {video}")
    (job / "review").mkdir(parents=True, exist_ok=True)
    m = measure(job, video, brief, edl)
    rv = Review(edl)
    run_checks(job, rv, m, analysis, brief, look, render)
    crit = critique(concepts, rv.checks)
    frames = extract_frames(job, video, edl, rnd, m["duration"])
    score, verdict = score_and_verdict(rv.checks)
    if verdict == "fix" and not rv.fixes:
        verdict = "ship" if score >= 0.7 else "fix"
    vp = vision_prompt(job, rnd, frames, rv.checks, crit, brief)
    out = C.new("review", round=rnd, checks=rv.checks, fixes=rv.fixes, frames=[f["path"] for f in frames], frame_index=frames,
                verdict=verdict, score=score, critique=crit, notes=[], capped_fixes=rv.capped,
                rounds_left=max(0, MAX_ROUNDS - rnd), final=str(video.relative_to(job)) if video.is_relative_to(job) else str(video),
                vision_prompt=str(vp.relative_to(job)), missing=m["missing"],
                measured={"duration": r3(m["duration"]), "width": m["width"], "height": m["height"], "lufs": m["lufs"],
                          "true_peak": m["true_peak"], "silences": m["silences"], "black": m["black"]})
    C.write(job, "review", out)
    C.save(job / "review" / f"review_r{rnd}.json", out)
    return out


def parse_fix(spec: str, ids: set) -> dict:
    parts = spec.split(":", 2)
    if len(parts) < 2:
        raise SystemExit(f"--fix must be EVENT:ACTION[:DETAIL], got {spec!r}")
    ev, act, detail = parts[0].strip(), parts[1].strip().lower(), parts[2].strip() if len(parts) > 2 else ""
    if act not in ACTIONS:
        raise SystemExit(f"--fix action must be one of {ACTIONS}, got {act!r}")
    if ev != "*" and ev not in ids:
        raise SystemExit(f"--fix event {ev!r} is not in edl.json ({', '.join(sorted(ids))})")
    fx = {"event": ev, "action": act, "detail": detail or f"{act} (claude vision)", "check": "vision", "by": "claude"}
    # structured fields ride in the detail as key=value; prose is never parsed for numbers
    fx.update({k: float(v) for k, v in re.findall(r"\b(seconds|src_in|src_out|speed|rec_at|lufs|min_bottom)=(-?\d+(?:\.\d+)?)", detail)})
    fx.update(dict(re.findall(r"\b(side|with_shot|target|grade|role|kind)=([\w.-]+)", detail)))
    return fx


def add_notes(job, notes: list, fixes: list) -> dict:
    job = Path(job).resolve()
    rv = C.read(job, "review")
    new = [parse_fix(f, {e["id"] for e in C.read(job, "edl")["events"]}) for f in fixes]
    rv.setdefault("notes", []).extend({"text": n, "by": "claude-vision", "round": rv["round"]} for n in notes)
    rv["fixes"].extend(new)
    if new:
        rv["verdict"] = "fix"
    C.write(job, "review", rv)
    if (job / "review").exists():
        C.save(job / "review" / f"review_r{rv['round']}.json", rv)
    return rv


def main(argv=None) -> int:
    C.utf8_stdio()
    ap = argparse.ArgumentParser(prog="dragon_montage review", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("review")
    r.add_argument("--job", required=True)
    r.add_argument("--round", type=int)
    r.add_argument("--add-note", action="append", default=[])
    r.add_argument("--fix", action="append", default=[], help="EVENT:ACTION:DETAIL")
    r.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    rv = add_notes(a.job, a.add_note, a.fix) if a.add_note or a.fix else review(a.job, a.round)
    if a.json:
        print(json.dumps(rv, ensure_ascii=False, indent=1))
    else:
        print(f"round {rv['round']}: verdict={rv['verdict']} score={rv.get('score')} "
              f"failed={[c['id'] for c in rv['checks'] if not c['pass']] or 'none'} fixes={len(rv['fixes'])} "
              f"frames={len(rv.get('frames', []))} notes={len(rv.get('notes', []))}")
    return 0
