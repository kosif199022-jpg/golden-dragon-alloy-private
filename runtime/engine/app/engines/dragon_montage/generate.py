"""Optional station «التوليد»: generation proposals for what the footage cannot give (consent-gated, spends nothing).

  gaps   --job DIR [--min-quality 0.45] [--json]   -> generate.json (kosif.dm.generate.v1) + GENERATE_AR.md
  attach --job DIR --proposal ID --file F.mp4      register a file the owner generated (after his yes) as clip cNN

Gaps: an arc role with no usable footage, footage shorter than the target, no music when the look wants music,
a weak hook shot. Video prompts follow the Kling director method (15-header master prompt, one move per shot,
shots <= 6 s). HARD RULE: every proposal carries consent_required; the MCP call is made only after the owner's yes.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import time
from pathlib import Path

from . import common as C
from ..media import probe, fps as rate

SCHEMA = "kosif.dm.generate.v1"
METHOD = "living-site/references/level-2-kling-director.md"
SHOT_MAX = 6.0
FEELING_EN = {"tense": "tense, suspenseful", "warm": "warm, intimate", "epic": "grand, rising", "playful": "playful, light",
              "calm": "calm, unhurried", "inspiring": "hopeful, uplifting", "sad": "melancholic, quiet", "funny": "light, comic timing"}
LIGHT_EN = {"tense": "one hard practical source frame-left at 3200K, deep shadows on the far side",
            "warm": "low golden sun at 3400K from frame-right, soft bounce fill",
            "epic": "late sun backlight at 4000K, long shadows, haze catching the light",
            "playful": "bright open daylight at 5600K, soft shadows", "calm": "soft overcast daylight at 6000K, even and gentle",
            "inspiring": "sunrise backlight at 3800K, gentle rim on the subject",
            "sad": "cool window light at 6500K, low contrast, dim corners", "funny": "bright even daylight at 5600K"}
ROLE_ACTION = {"hook": "a striking first image that makes the viewer stop scrolling: strong shape, clear subject",
               "setup": "the place and subject are introduced calmly so the viewer knows where we are",
               "turn": "something changes: a reveal, a new angle or a shift in light",
               "payoff": "the strongest image of the piece: the promise of the hook is delivered",
               "cta": "a clean, held closing image with empty space for a call-to-action title",
               "broll": "texture and detail shots of the same world as the owner's footage"}
ASPECT_KLING = {"9:16": "9:16", "16:9": "16:9", "1:1": "1:1", "4:5": "9:16"}
FRAMINGS = ("Wide establishing frame, 84° diagonal FOV, lens at waist height, three-quarter angle",
            "Medium shot, 47° FOV, lens at chest height", "Close-up, 47° FOV, eye level, focus on the eyes",
            "Over-the-shoulder medium shot, 57° FOV", "Insert on the key prop, 29° FOV",
            "Medium-full shot, 63° FOV, low-angle")
MOVES = ["slow dolly-in", "side-tracking", "locked-off", "crane up", "locked-off", "slow push-in"]


def blocks(seconds: float) -> list:
    """Generation blocks (whole seconds, <= 30 each) covering `seconds`."""
    s = max(3, int(math.ceil(seconds)))
    n = max(1, math.ceil(s / 30))
    base, extra = divmod(s, n)
    return [base + (1 if i < extra else 0) for i in range(n)]


def cuts(duration: float, parts: int) -> list:
    edges = [round(duration * i / parts, 1) for i in range(parts)] + [float(duration)]
    return list(zip(edges, edges[1:]))


def _clean(text: str) -> str:
    t = re.sub(r"(?i)\b(flawless|perfect(ly)?|8k|4k|hyper-?realistic|ultra[- ]detailed|masterpiece)\b", "", " ".join(str(text).split()))
    return re.sub(r"\s{2,}", " ", t).strip()


def kling_prompt(*, role: str, seconds: int, ratio: str, brief: dict, people: int) -> str:
    """15-header master prompt, one move per shot."""
    feeling = brief.get("feeling", "calm")
    mood, task = FEELING_EN.get(feeling, feeling), _clean(brief.get("task", ""))
    truth = _clean(brief.get("one_truth", "")) or task
    shots = cuts(seconds, max(1, math.ceil(seconds / SHOT_MAX)))
    framings = [f for f in FRAMINGS if "eyes" not in f and "shoulder" not in f] if people == 0 else list(FRAMINGS)
    who = "Exactly 1 person" if people else "Exactly 0 people"
    action = ROLE_ACTION.get(role, ROLE_ACTION["broll"])
    timing = [f"{a:.1f}-{b:.1f}s — SHOT {n} — {framings[(n - 1) % len(framings)]}, {MOVES[(n - 1) % len(MOVES)]}. "
              f"{action[0].upper() + action[1:]}; the motion settles on a clear image. "
              f"{'Hard cut.' if n < len(shots) else 'Final image holds to the last frame.'}" for n, (a, b) in enumerate(shots, 1)]
    subject = "the main subject from the owner's footage" if people else "the place and objects from the owner's footage"
    return "\n".join([
        "SCENE CONTEXT", f"Block 1 of 1. {seconds} s, {ratio}. Role in the edit: {role}. Owner's brief: {task}",
        f"This block is {role} material for a short {brief.get('platform', 'reel')} montage. It shows {subject}. "
        f"Core idea: {truth}. Mood: {mood}.", "",
        "ACTIVE REFERENCES", "@Image1 — LOCATION — a still frame from the owner's own footage: controls layout, materials, palette "
        "and practical lights. The reference's camera angle and framing are not inherited.", "",
        "LOCATION MAP", "The space of @Image1: subject at frame-center about 3 m from the lens, background 10 m behind, "
        "screen direction frame-left to frame-right, camera works from the open side.", "",
        "FIRST FRAME AND SPATIAL BLOCKING", f"Frame 1 matches the composition of @Image1 at eye level. {who} in the shot.", "",
        "FORMAT MODE", f"Controlled multi-shot sequence, {len(shots)} shots, hard cuts between shots." if len(shots) > 1
        else "Single continuous shot.", "",
        "OPTICS", "Close-ups 47°, medium-wide 63°, wide 84°, inserts 29°; lens locked within each shot; focus on the subject at "
        "held moments.", "",
        "CAMERA", "One motivated move per shot, at most two; steady gimbal or dolly.", "",
        "ACTION TIMING", *timing, "",
        "ACTING TASK — SUBJECT", "SCENE DIRECTION (shared, unspoken): the world of the owner's footage continues. "
        "MOTIVE: carry the montage's idea. GOAL: one readable action per shot. OBSTACLE: time. TACTIC: simple natural movement "
        "with a natural blink cadence.", "",
        "PHYSICS", "Real weight and inertia; cloth, dust and light particles move with the air and the action.", "",
        "LIGHTING", LIGHT_EN.get(feeling, LIGHT_EN["calm"]) + "; matches the light seen in @Image1.", "",
        "AUDIO", "Silent acting; ambience and SFX timed to the action. Arabic voice-over is added in the edit. No music. No subtitles.", "",
        "STYLE", f"{mood.capitalize()} documentary-real look matching the owner's footage, fine film grain, natural skin texture "
        "with pores, one consistent grade.", "",
        "QUALITY", "Readable faces and hands at held moments; natural 180° shutter motion blur on fast moves; stable temporal "
        "continuity; consistent anatomy; each object stays one consistent object.", "",
        "POSITIVE CONSTRAINTS", f"{who} in every shot; screen direction stays frame-left to frame-right; the last frame is a "
        "clean, steady image that cuts well into the owner's footage.", ""])


def music_prompt(look, brief: dict, seconds: float) -> tuple:
    music = (look or {}).get("music") or {}
    mood, bpm = music.get("mood") or brief.get("feeling", "calm"), music.get("bpm_range") or [90, 110]
    mid = int(round(sum(bpm) / len(bpm))) if bpm else 100
    return (f"Instrumental only, {FEELING_EN.get(mood, mood)} mood, {bpm[0]}-{bpm[-1]} BPM (aim {mid}), clear steady beat for "
            f"cutting, strong first 3 seconds, builds to a peak near {int(seconds * 0.7)} s, clean ending at "
            f"{int(math.ceil(seconds))} s, for a {brief.get('platform', 'reel')} montage. No vocals."), list(bpm)


def _role_of(ev: dict):
    if ev.get("role"):
        return str(ev["role"]).lower()
    m = re.match(r"\s*([a-zA-Z-]+)\s*:", str(ev.get("reason", "")))
    return m.group(1).lower() if m else None


def find_gaps(job: Path, min_q: float) -> tuple:
    brief, concepts = C.read_opt(job, "brief", {}), C.read_opt(job, "concepts", {})
    analysis = C.read_opt(job, "analysis", {"clips": [], "music": {}})
    look, edl = C.read_opt(job, "look"), C.read_opt(job, "edl")
    target = float(brief.get("target_seconds") or 0)
    shots = [s for c in analysis.get("clips", []) for s in c.get("shots", [])]
    score = lambda s: float(((s.get("quality") or {}).get("score")) or 0.0)  # noqa: E731
    footage = sum(float(c.get("duration") or 0) for c in analysis.get("clips", []))
    usable = sum(s["end"] - s["start"] for s in shots if score(s) >= min_q) if shots else footage
    people = max([int(s.get("faces") or 0) for s in shots] + [0])
    best = sorted(shots, key=score, reverse=True)
    chosen = next((c for c in concepts.get("concepts", []) if c.get("id") == (concepts.get("decision") or {}).get("chosen")), None)
    arc = [str(r).lower() for r in (chosen or {}).get("arc", [])] or ["hook", "setup", "turn", "payoff", "cta"]
    gaps = []
    if target and target - usable > 1.0:
        gaps.append({"kind": "short-footage", "role": "broll", "seconds": round(target - usable, 2),
                     "evidence": f"usable footage {usable:.1f}s (quality>={min_q}) of {footage:.1f}s total; target {target:.0f}s"})
    if edl:
        covered = {r for r in (_role_of(e) for e in edl.get("events", [])) if r}
        gaps += [{"kind": "missing-role", "role": r, "seconds": 3.0 if r in ("hook", "cta") else 5.0,
                  "evidence": f"edl has no event for arc role '{r}' (covered: {sorted(covered)})"}
                 for r in (arc if covered else []) if r not in covered]
    elif arc and usable < 1.5 * len(arc):
        gaps += [{"kind": "missing-role", "role": r, "seconds": 3.0,
                  "evidence": f"{usable:.1f}s usable footage cannot cover {len(arc)} arc roles"} for r in arc]
    hook_q = None
    if edl and edl.get("events"):
        sid = edl["events"][0].get("shot")
        hook_q = next((score(s) for s in shots if s["id"] == sid), None)
    elif best:
        hook_q = score(best[0])
    if hook_q is not None and hook_q < min_q and not any(g["role"] == "hook" for g in gaps):
        gaps.append({"kind": "weak-hook", "role": "hook", "seconds": 3.0, "evidence": f"hook shot quality {hook_q:.2f} < {min_q}"})
    have_music = bool((analysis.get("music") or {}).get("path")) or bool((((edl or {}).get("audio") or {}).get("music") or {}).get("path"))
    wants = bool(look and (look.get("music") or {}).get("mood")) or (
        look is None and brief.get("content_type") in ("montage", "travel", "product", "event"))
    if wants and not have_music:
        gaps.append({"kind": "no-music", "role": "music", "seconds": target or (edl or {}).get("duration") or 30,
                     "evidence": "look.music asks for a mood but no music file in analysis/edl"})
    guard = likeness_guard(brief, people)
    thumb = None if guard else next((s.get("thumb") for s in best if s.get("thumb")), None)
    ctx = {"brief": brief, "look": look, "people": 0 if guard else (1 if people else 0), "thumb": thumb,
           "aspect": brief.get("aspect", "9:16"), "usable": round(usable, 2), "footage": round(footage, 2), "target": target,
           "faces_in_footage": people, "forbidden_subject": guard}
    return gaps, ctx


REAL_PERSON_WORDS = ("ميار", "مايار", "mayar", "بنتي", "بنتى", "طفل", "طفله", "طفلة", "child", "kid", "minor")


def likeness_guard(brief: dict, faces: int):
    """SKILL §10 / LESSONS: never an AI likeness of a real person. Faces in his footage, or a brief naming Mayar or a
    child -> proposals show places and objects only, with no face still as reference. Returns the reason or None."""
    text = " ".join(str((brief or {}).get(k) or "") for k in ("task", "one_truth", "topic")).lower()
    if any(w in text for w in REAL_PERSON_WORDS):
        return "minor"
    if faces:
        return "real-person"
    return None


def build_proposals(gaps: list, ctx: dict) -> list:
    brief = ctx["brief"] or {"task": "", "feeling": "calm"}
    ratio, props = ASPECT_KLING.get(ctx["aspect"], "9:16"), []
    for g in gaps:
        if g["kind"] == "no-music":
            text, bpm = music_prompt(ctx["look"], brief, float(g["seconds"]))
            props.append({"id": f"g{len(props) + 1:02d}", "kind": "music", "role": "music", "gap": g["kind"], "evidence": g["evidence"],
                          "seconds": round(float(g["seconds"]), 1), "prompt": text, "negative": "vocals, lyrics, spoken words",
                          "bpm_range": bpm, "model_suggestion": "suno (instrumental)", "tool": "suno.audio-create",
                          "mcp_call": {"tool": "mcp__suno__audio-create", "args": {"prompt": text, "instrumental": True},
                                       "note": "check the tool schema first; credits are taken from the owner's Suno plan"},
                          "est_credits": "ask quote", "quote_call": {"tool": "mcp__suno__account-usage", "args": {}},
                          "consent_required": True, "status": "proposed"})
            continue
        for sec in blocks(float(g["seconds"])):
            props.append({"id": f"g{len(props) + 1:02d}", "kind": "video", "role": g["role"], "gap": g["kind"], "evidence": g["evidence"],
                          "seconds": sec, "aspect": ratio,
                          "prompt": kling_prompt(role=g["role"], seconds=sec, ratio=ratio, brief=brief, people=ctx["people"]),
                          "negative": "text, watermark, logos, extra people, warped hands, flicker", "reference_still": ctx["thumb"],
                          "model_suggestion": "kling4_0", "tool": "higgsfield.generate_video",
                          "mcp_call": {"tool": "mcp__Higgsfield__generate_video",
                                       "args": {"model": "kling4_0", "prompt": "<prompt>", "duration": sec, "aspect_ratio": ratio,
                                                "resolution": "1080p", "mode": "image-to-video" if ctx["thumb"] else "text-to-video"},
                                       "note": "uploading the reference still (media_upload) is also an upload: same yes"},
                          "est_credits": "ask quote",
                          "quote_call": {"tool": "mcp__Higgsfield__models_explore", "args": {"action": "get", "model": "kling4_0"}},
                          "takes": 2, "method": METHOD, "people": ctx["people"],
                          **({"forbidden_subject": ctx["forbidden_subject"]} if ctx.get("forbidden_subject") else {}), "lint": {"tool": "kling_lint", "available": False, "result": "SKIPPED"},
                          "consent_required": True, "status": "proposed"})
    return props


def write_ar(job: Path, doc: dict) -> Path:
    c = doc["context"]
    L = ["# اقتراحات التوليد — محتاجة موافقتك", "",
         "**القاعدة:** مفيش أي صرف كريدت ولا رفع ولا نشر غير لما صاحب الشغل يوافق صراحة على السعر نفسه في الشات.", "",
         "**ممنوع:** أي اقتراح هنا عمره ما يطلّع شبه بالـ AI لشخص حقيقي (ميار أو أي طفل أو أي حد من الفوتيج): "
         "الاقتراحات أماكن وحاجات بس، من غير صورة وش كمرجع.", "",
         f"- المطلوب: {c['target']:.0f} ث · المادة الصالحة: {c['usable']:.1f} ث من {c['footage']:.1f} ث",
         f"- عدد الاقتراحات: {len(doc['proposals'])}", ""]
    if not doc["proposals"]:
        L.append("المادة كفاية — مفيش حاجة محتاجة توليد.")
    for p in doc["proposals"]:
        L += [f"## {p['id']} — {p['kind']} لـ «{p['role']}» ({p['seconds']} ث)", f"- السبب: {p['evidence']}",
              f"- الأداة: `{p['tool']}` · الموديل: {p['model_suggestion']} · التكلفة: {p['est_credits']} "
              f"(اسأل عن السعر بـ `{p['quote_call']['tool']}` قبل ما تعرض)", "",
              "**اللي تعرضه على صاحب الشغل:** البرومبت ده + السعر + عدد المحاولات" + (f" ({p['takes']})" if p.get("takes") else ""), "",
              "```text", p["prompt"], "```", "", "**الاستدعاء — بعد «أيوه» بس:**", "", "```json",
              json.dumps(p["mcp_call"], ensure_ascii=False, indent=1), "```", ""]
    L += ["## بعد التوليد", "", "1. سجّل الكريدت اللي اتصرف.",
          f"2. ضيف الملف كلقطة: `python -m engines.dragon_montage tool generate attach --job {job} --proposal <id> --file <file>`",
          "3. شغّل direct تاني عشان المونتاج يستخدم اللقطة الجديدة.", ""]
    f = job / "GENERATE_AR.md"
    f.write_text("\n".join(L), encoding="utf-8")
    return f


def gaps(job, min_quality: float = 0.45) -> dict:
    job = C.job_dir(job)
    found, ctx = find_gaps(job, min_quality)
    doc = {"schema": SCHEMA, "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "rule": "consent_required: no credits, uploads or publishing without the owner's explicit yes in chat",
           "credits_spent": 0, "gaps": found,
           "context": {k: ctx.get(k) for k in ("usable", "footage", "target", "aspect", "people", "thumb", "forbidden_subject")},
           "proposals": build_proposals(found, ctx)}
    C.save(job / "generate.json", doc)
    write_ar(job, doc)
    return doc


def attach(job, proposal: str, file) -> dict:
    job = C.job_dir(job)
    gen_f = job / "generate.json"
    doc = json.loads(gen_f.read_text(encoding="utf-8")) if gen_f.exists() else {"schema": SCHEMA, "proposals": []}
    prop = next((p for p in doc["proposals"] if p["id"] == proposal), None)
    src = Path(file).resolve()
    if prop is None or not src.is_file():
        raise SystemExit(f"proposal {proposal} not in generate.json" if prop is None else f"{src} not found")
    analysis = C.read_opt(job, "analysis") or C.new("analysis", clips=[], music={"path": None, "bpm": None, "beats": [], "downbeats": []},
                                                    tools_used=[], missing=[])
    jobf = job / "job.json"
    jd = json.loads(jobf.read_text(encoding="utf-8")) if jobf.exists() else C.new("job", clips=[])
    k = max([int(c["id"][1:]) for c in analysis["clips"] if re.fullmatch(r"c\d+", c["id"])] + [len(jd.get("clips") or [])]) + 1
    cid = f"c{k:02d}"
    (job / "generated").mkdir(exist_ok=True)
    dst = job / "generated" / f"{cid}_{proposal}{src.suffix.lower()}"
    shutil.copy2(src, dst)
    clip_id = None
    if prop["kind"] == "music":
        analysis["music"] = {**(analysis.get("music") or {}), "path": str(dst), "generated": True, "proposal": proposal}
    else:
        info = probe(dst)
        v = next((s for s in info["streams"] if s.get("codec_type") == "video"), {})
        dur = round(float(info["format"].get("duration") or v.get("duration") or prop.get("seconds") or 0), 3)
        analysis["clips"].append({"id": cid, "path": str(dst), "duration": dur, "width": v.get("width"), "height": v.get("height"),
                                  "fps": round(rate(v.get("r_frame_rate", "30/1")), 3) or 30.0,
                                  "has_audio": any(s.get("codec_type") == "audio" for s in info["streams"]),
                                  "loudness_lufs": None, "generated": True, "proposal": proposal, "role": prop.get("role"),
                                  "shots": [{"id": f"{cid}-s001", "start": 0.0, "end": dur,
                                             "quality": {"sharpness": None, "exposure": None, "shake": None, "score": 0.7, "estimated": True},
                                             "faces": 0, "motion_energy": None, "color": {}, "thumb": None, "role": prop.get("role")}],
                                  "words": [], "silences": [], "energy": []})
        jd.setdefault("clips", []).append(str(dst))
        C.save(jobf, jd)
        clip_id = cid
    C.write(job, "analysis", analysis)
    prop.update({"status": "attached", "clip": clip_id, "file": str(dst.relative_to(job)), "sha256": C.sha256(dst)})
    C.save(gen_f, doc)
    C.receipt(job, "generate", "attach", [proposal, str(src)], 0, 0.0, dst, owner_media=False)
    return {"clip": clip_id, "file": str(dst), "proposal": proposal, "next": "rerun the direct station so the edit can use it"}


def main(argv=None) -> int:
    C.utf8_stdio()
    p = argparse.ArgumentParser(prog="dragon_montage generate", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gaps")
    g.add_argument("--job", required=True)
    g.add_argument("--min-quality", type=float, default=0.45)
    g.add_argument("--json", action="store_true")
    t = sub.add_parser("attach")
    t.add_argument("--job", required=True)
    t.add_argument("--proposal", required=True)
    t.add_argument("--file", required=True)
    a = p.parse_args(argv)
    if a.cmd == "attach":
        print(json.dumps(attach(a.job, a.proposal, a.file), ensure_ascii=False))
        return 0
    doc = gaps(a.job, a.min_quality)
    print(json.dumps(doc if a.json else {"job": str(Path(a.job).resolve()), "gaps": len(doc["gaps"]), "proposals": len(doc["proposals"]),
                                         "lint_fail": []}, ensure_ascii=False))
    return 0
