"""Red Rose V43: original measurable thinking and reel-episode adapters.

Independent stdlib code distilled from two owner-supplied archives:
- app-super-mind.skill: 9 evidence gates, 12 intelligence dimensions,
  paired held-out evaluation and correction accountability.
- "Reel Abu Kab".rar: deterministic 30-fps seekable cartoon beat planning,
  actor/prop continuity and credited soundtrack preflight.
This module does NOT import, execute or redistribute source engines, fonts,
footage, music, screenshots or user memories. Outputs are assessments/plans,
never an automatic certification, media render or model retraining.
"""
from __future__ import annotations

import math
import re
from collections import Counter

OPS = ("readiness", "ladder", "paired_eval", "reel_preflight", "reel_seek",
       "reel_rhythm", "feedback_cycle")
ORGANS = ("intent", "context", "memory", "planning", "action", "grounding",
          "verification", "calibration", "safety", "learning",
          "measurement", "resilience")
STEPS = ("understand", "ground", "baseline", "choose", "design",
         "premortem", "build", "prove", "learn")
CATEGORIES = ("normal", "noisy", "ambiguous", "unsafe", "legacy", "out_of_scope")
HEX_SHA = re.compile(r"^[a-fA-F0-9]{12,64}$")
SAFE_ID = re.compile(r"^[a-zA-Z0-9_.:-]{1,80}$")


def _obj(value, label="params"):
    if type(value) is not dict:
        raise ValueError(label + " must be an object")
    return value


def _keys(obj, allowed, required=()):
    extra = set(obj).difference(allowed)
    missing = set(required).difference(obj)
    if extra or missing:
        raise ValueError("unknown/missing keys: " + ",".join(sorted(extra | missing)))


def _str(value, label, limit=300):
    if type(value) is not str or not 1 <= len(value.strip()) <= limit:
        raise ValueError(label + " must be a bounded nonempty string")
    return value.strip()


def _int(value, label, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(label + " must be an integer in range")
    return value


def _list(value, label, low, high):
    if type(value) is not list or not low <= len(value) <= high:
        raise ValueError(label + " must be a bounded list")
    return value


def readiness(params):
    """Score *provided* audit evidence, never self-certify that an app is smart."""
    _keys(params, ("organs", "app"), ("organs",))
    organs = _list(params["organs"], "organs", 12, 12)
    found = set()
    points, known, weak, unknown = 0, 0, [], []
    scores = {}
    for row in organs:
        row = _obj(row, "organ")
        _keys(row, ("id", "score", "evidence"), ("id", "score"))
        oid = _str(row["id"], "organ id", 20)
        if oid not in ORGANS or oid in found:
            raise ValueError("unrecognized or duplicate organ id")
        found.add(oid)
        score = row["score"]
        evidence = _list(row.get("evidence", []), "evidence", 0, 8)
        for item in evidence:
            _str(item, "evidence reference", 240)
        if score is None:
            if oid in ("safety", "learning", "verification", "measurement"):
                raise ValueError("safety/learning/verification/measurement cannot be NA")
            unknown.append(oid)
            scores[oid] = None
            continue
        score = _int(score, "organ score", 0, 4)
        scores[oid] = score
        points += score
        known += 1
        if score >= 3 and not evidence:
            weak.append(oid)
    if set(ORGANS) != found or len(unknown) > 5:
        raise ValueError("12 organs required; maximum five noncritical NA")
    fraction = round(100 * points / (4 * known), 2)
    # Bands are an original reporting convention, NOT a claimed measured IQ.
    band = ("L0" if fraction < 20 else "L1" if fraction < 40 else
            "L2" if fraction < 60 else "L3" if fraction < 75 else
            "L4" if fraction < 90 else "L5")
    return {
        "status": "self_reported_readiness_not_certified",
        "app": _str(params.get("app", "Red Rose"), "app", 150),
        "known_organs": known, "unmeasured_organs": unknown,
        "evidence_missing_for_high_scores": weak,
        "readiness_index": fraction, "provisional_band": band,
        "organ_scores": scores,
        "required_next": ["independent case measurements",
                          "held-out before/after evaluation",
                          "proof of user correction changing later behavior"],
        "warning": "Provided ratings and references are claims until independently checked."
    }


def ladder(params):
    """Sequential evidence checklist: a purported pass is never treated as proof."""
    _keys(params, ("stages",), ("stages",))
    rows = _list(params["stages"], "stages", 0, 9)
    if [row.get("step") if type(row) is dict else None for row in rows] != list(STEPS[:len(rows)]):
        raise ValueError("nine stages must be in order without jumps")
    next_step = None
    submitted = []
    for index, row in enumerate(rows):
        _keys(row, ("step", "passed", "evidence"), ("step", "passed"))
        if type(row["passed"]) is not bool:
            raise ValueError("passed must be boolean")
        evidence = _list(row.get("evidence", []), "evidence", 0, 10)
        for ref in evidence:
            _str(ref, "evidence", 240)
        if row["passed"] and not evidence:
            raise ValueError("no pass without an evidence reference")
        if next_step is not None and row["passed"]:
            raise ValueError("cannot pass a stage after a pending gate")
        submitted.append({"step": row["step"], "claimed_pass": row["passed"],
                          "evidence_refs": len(evidence)})
        if not row["passed"] and next_step is None:
            next_step = row["step"]
    if next_step is None and len(rows) < 9:
        next_step = STEPS[len(rows)]
    return {"status": "evidence_submitted_not_independently_verified",
            "stages": submitted,
            "next_step": next_step,
            "all_stages_claimed_passed": len(rows) == 9 and next_step is None,
            "warning": "A file path or receipt alone is not proof: inspect it and run independent checks."}


def _mcnemar(b, c):
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(min(b, c) + 1))
    return round(min(1.0, 2 * tail / (2 ** n)), 8)


def paired_eval(params):
    """Paired before/after *reported* pass/fail outcomes on unchanged cases."""
    _keys(params, ("before_sha", "after_sha", "cases", "heldout_systems_seen",
                   "minimum_heldout"), ("before_sha", "after_sha", "cases"))
    a, b = params["before_sha"], params["after_sha"]
    if type(a) is not str or not HEX_SHA.fullmatch(a):
        raise ValueError("before_sha must be a source version hash")
    if type(b) is not str or not HEX_SHA.fullmatch(b) or a.lower() == b.lower():
        raise ValueError("before and after must be distinct real source-version hashes")
    systems = _int(params.get("heldout_systems_seen", 2),
                   "heldout_systems_seen", 1, 100)
    minimum = _int(params.get("minimum_heldout", 20), "minimum_heldout", 10, 200)
    cases = _list(params["cases"], "cases", 1, 400)
    seen, splits = set(), {"dev": [], "heldout": []}
    for row in cases:
        row = _obj(row, "case")
        _keys(row, ("id", "case_sha", "split", "category", "before_pass",
                    "after_pass", "before_error", "after_error"),
              ("id", "case_sha", "split", "category", "before_pass", "after_pass"))
        cid = _str(row["id"], "case id", 80)
        if not SAFE_ID.fullmatch(cid) or cid in seen:
            raise ValueError("case IDs must be distinct safe tokens")
        seen.add(cid)
        if type(row["case_sha"]) is not str or not HEX_SHA.fullmatch(row["case_sha"]):
            raise ValueError("case_sha required for immutable case identity")
        if row["split"] not in ("dev", "heldout") or row["category"] not in CATEGORIES:
            raise ValueError("unknown split or category")
        for field in ("before_pass", "after_pass", "before_error", "after_error"):
            if type(row.get(field, False)) is not bool:
                raise ValueError("case outcomes must be booleans")
        splits[row["split"]].append(row)
    ho = splits["heldout"]
    improved = sum(not r["before_pass"] and r["after_pass"] for r in ho)
    regressed = sum(r["before_pass"] and not r["after_pass"] for r in ho)
    error_rows = [r["id"] for r in cases if r.get("before_error", False)
                  or r.get("after_error", False)]
    unsafe_regressions = [r["id"] for r in ho if r["category"] == "unsafe"
                          and r["before_pass"] and not r["after_pass"]]
    difference = (improved - regressed) / len(ho) if ho else 0
    p = _mcnemar(regressed, improved)
    gate = (len(ho) >= minimum and systems <= 2 and not error_rows
            and not unsafe_regressions)
    candidate = gate and difference >= 0.05 and p <= .05
    verdict = ("candidate_improved_requires_independent_review" if candidate else
               "regression_detected" if difference < 0 else "not_established")
    return {
        "status": "reported_outcomes_not_verified_externally",
        "verdict": verdict, "cases_total": len(cases),
        "dev_count": len(splits["dev"]), "heldout_count": len(ho),
        "heldout_before_passed": sum(r["before_pass"] for r in ho),
        "heldout_after_passed": sum(r["after_pass"] for r in ho),
        "heldout_improved": improved, "heldout_regressed": regressed,
        "heldout_gain": round(difference, 5), "mcnemar_exact_p": p,
        "heldout_contaminated": systems > 2,
        "unsafe_regressions": unsafe_regressions, "execution_errors": error_rows,
        "minimum_heldout": minimum, "gate_met": gate,
        "limitations": "Supplied pass/fail flags are not independently executed or verified; "
                       "the old and new binaries, case hashes and held-out provenance "
                       "must be checked before claiming real improvement."
    }


def reel_preflight(params):
    """Validate a frame-exact storyboard contract, not binary footage."""
    _keys(params, ("title", "width", "height", "fps", "frames", "shots",
                   "frame_inventory_count", "music", "seekable"), 
          ("title", "width", "height", "fps", "frames", "shots"))
    _str(params["title"], "title", 160)
    w = _int(params["width"], "width", 160, 8192)
    h = _int(params["height"], "height", 160, 8192)
    fps = _int(params["fps"], "fps", 1, 120)
    frames = _int(params["frames"], "frames", 1, 14400)
    shots = _list(params["shots"], "shots", 1, 80)
    frame_inventory = params.get("frame_inventory_count")
    if frame_inventory is not None:
        frame_inventory = _int(frame_inventory, "frame_inventory_count", 0, 14400)
    seekable = params.get("seekable", False)
    if type(seekable) is not bool:
        raise ValueError("seekable must be boolean")
    music = params.get("music")
    if music is not None:
        music = _obj(music, "music")
        _keys(music, ("title", "artist", "license", "attribution", "url"),
              ("title", "artist", "license"))
        for key in ("title", "artist", "license"):
            _str(music[key], "music " + key, 200)
    seen, ordered, problems, prev = set(), [], [], 0
    for shot in shots:
        shot = _obj(shot, "shot")
        _keys(shot, ("id", "start_frame", "end_frame", "actors", "props",
                     "tag", "caption"), ("id", "start_frame", "end_frame"))
        ident = _str(shot["id"], "shot id", 80)
        if ident in seen:
            raise ValueError("duplicate shot id")
        seen.add(ident)
        start = _int(shot["start_frame"], "shot start", 0, frames)
        end = _int(shot["end_frame"], "shot end", 1, frames)
        if end <= start:
            raise ValueError("shot end must exceed start")
        if start != prev:
            problems.append("gap_or_overlap_before_" + ident)
        prev = end
        actors = _list(shot.get("actors", []), "actors", 0, 12)
        props = _list(shot.get("props", []), "props", 0, 16)
        for token in actors + props:
            _str(token, "actor/prop", 80)
        tag = _str(shot.get("tag", "scene"), "tag", 30)
        caption = shot.get("caption", "")
        if type(caption) is not str or len(caption) > 240:
            raise ValueError("caption too long")
        ordered.append({"id": ident, "start_frame":start, "end_frame":end,
                        "duration_frames":end-start, "actors":actors,
                        "props":props,"tag":tag,"caption":caption})
        if end-start < 6:
            problems.append("very_short_shot_" + ident)
    if prev != frames:
        problems.append("timeline_does_not_cover_all_frames")
    if frame_inventory is not None and frame_inventory != frames:
        problems.append("frame_inventory_mismatch")
    if w*16 != h*9:
        problems.append("not_exact_9_to_16_vertical")
    if not any(s["tag"] == "cta" for s in ordered):
        problems.append("no_explicit_end_card")
    if music and (not music.get("attribution") or
                  not music.get("url")):
        problems.append("music_credit_or_license_link_missing")
    if not seekable:
        problems.append("stateless_seek_not_declared")
    return {"status":"metadata_preflight_not_media_verified",
            "frames":frames,"fps":fps,"duration_seconds":round(frames/fps,4),
            "resolution":[w,h],"shot_count":len(ordered),"shots":ordered,
            "warnings":problems,"preflight_passed":not problems,
            "music_attribution":music.get("attribution") if music else None,
            "limitations":"No browser JS, frame pixels, soundtrack rights or actual MP4 were verified."}


def reel_seek(params):
    _keys(params, ("project", "time_seconds"), ("project", "time_seconds"))
    project = reel_preflight(_obj(params["project"], "project"))
    sec = params["time_seconds"]
    if type(sec) not in (int, float) or not math.isfinite(sec):
        raise ValueError("time_seconds must be finite")
    if not 0 <= sec < project["duration_seconds"]:
        raise ValueError("time outside reel duration")
    frame = min(project["frames"]-1, int(sec * project["fps"]))
    matches = [shot for shot in project["shots"]
               if shot["start_frame"] <= frame < shot["end_frame"]]
    if len(matches) != 1:
        raise ValueError("timeline has a gap or overlap at this time")
    shot = matches[0]
    span = max(1, shot["duration_frames"]-1)
    return {"status":"deterministic_state_not_svg_rendered",
            "frame":frame,"time_seconds":round(frame/project["fps"],6),
            "shot_id":shot["id"],
            "local_progress":round((frame-shot["start_frame"])/span,6),
            "actors":shot["actors"],"props":shot["props"],
            "caption":shot["caption"],"tag":shot["tag"],
            "limitations":"State lookup only; no animation or source media execution."}



def reel_rhythm(params):
    """Read-only shot timing/caption-density review; not a visual quality verdict."""
    params = _obj(params)
    _keys(params, ("project", "caption_cps_limit", "minimum_cta_frames"), ("project",))
    project = reel_preflight(_obj(params["project"], "project"))
    limit = _int(params.get("caption_cps_limit", 22), "caption_cps_limit", 4, 100)
    minimum_cta = _int(params.get("minimum_cta_frames", 30), "minimum_cta_frames", 1, 1200)
    shots, warnings = [], list(project["warnings"])
    ever_seen, previous = set(), set()
    for shot in project["shots"]:
        duration = shot["duration_frames"] / project["fps"]
        chars = sum(not ch.isspace() for ch in shot["caption"])
        density = round(chars / duration, 3)
        notes = []
        if density > limit:
            notes.append("review_caption_density")
        if shot["tag"] == "cta" and shot["duration_frames"] < minimum_cta:
            notes.append("review_short_end_card")
        current = set(shot["actors"])
        returning = sorted((current & ever_seen) - previous)
        if returning:
            notes.append("review_actor_reentry")
        shots.append({
            "id": shot["id"],
            "start_seconds": round(shot["start_frame"] / project["fps"], 4),
            "duration_seconds": round(duration, 4),
            "caption_codepoints_per_second": density,
            "reappearing_actors": returning,
            "review_flags": notes
        })
        warnings.extend(shot["id"] + ":" + flag for flag in notes)
        ever_seen.update(current)
        previous = current
    return {
        "status": "metadata_rhythm_review_not_media_verified",
        "preflight_passed": project["preflight_passed"],
        "shot_count": len(shots),
        "shots": shots,
        "warnings": warnings,
        "review_required": bool(warnings),
        "limitations": "Caption codepoint density is a heuristic, not reading speed; "
                       "actor re-entry is a review prompt, not an error. "
                       "No frames, animation, soundtrack, or source footage were inspected."
    }


def feedback_cycle(params):
    """Rank evidence-linked corrections; drafts never mutate files, memory, or model."""
    params = _obj(params)
    _keys(params, ("task", "observations", "max_proposals"),
          ("task", "observations"))
    task = _str(params["task"], "task", 300)
    rows = _list(params["observations"], "observations", 1, 100)
    maximum = _int(params.get("max_proposals", 10), "max_proposals", 1, 25)
    remedies = {
        "routing": "Freeze held-out intents and rerun abstention/Top-1 evaluation",
        "timing": "Add frame-boundary and exact-duration regression cases",
        "caption": "Check Arabic shaping, exact text and caption timing on frames",
        "identity": "Compare approved character/style reference across adjacent shots",
        "audio": "Check source-to-output sync and independently decode audio",
        "export": "Probe H264/AAC MP4 and fully decode final media",
        "safety": "Test permission gates, untrusted source handling and negative cases",
        "general": "Create a reproducible before/after regression test"
    }
    severities = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    seen, suggestions = set(), []
    for row in rows:
        row = _obj(row, "observation")
        _keys(row, ("id", "category", "severity", "recurrences",
                    "summary", "evidence_sha", "reproduced"),
              ("id", "category", "severity", "recurrences", "summary", "reproduced"))
        ident = _str(row["id"], "observation id", 80)
        if not SAFE_ID.fullmatch(ident) or ident in seen:
            raise ValueError("observation id must be unique and a safe token")
        seen.add(ident)
        category = _str(row["category"], "category", 32)
        severity = _str(row["severity"], "severity", 16)
        if category not in remedies or severity not in severities:
            raise ValueError("unrecognized category or severity")
        occurrences = _int(row["recurrences"], "recurrences", 1, 1000)
        _str(row["summary"], "summary", 300)
        if type(row["reproduced"]) is not bool:
            raise ValueError("reproduced must be boolean")
        evidence_sha = row.get("evidence_sha")
        if evidence_sha is not None:
            if type(evidence_sha) is not str or len(evidence_sha) != 64 or not HEX_SHA.fullmatch(evidence_sha):
                raise ValueError("evidence_sha must be SHA256 hex")
        if row["reproduced"] and not evidence_sha:
            raise ValueError("reproduced feedback needs an evidence_sha")
        score = 5 * severities[severity] + min(occurrences, 5) + (5 if row["reproduced"] else 0)
        suggestions.append({
            "id": ident, "category": category, "severity": severity,
            "priority": score, "reported_reproduced": row["reproduced"],
            "evidence_sha": evidence_sha,
            "regression_test_proposal": remedies[category],
            "status": "pending_independent_review"
        })
    suggestions.sort(key=lambda x: (-x["priority"], x["id"]))
    return {
        "status": "feedback_proposals_only_not_saved",
        "task": task, "observations_count": len(rows),
        "proposals": suggestions[:maximum],
        "not_shown": max(0, len(suggestions) - maximum),
        "local_memory_write": "explicit_owner_approval_required",
        "next_action": "Independently inspect evidence, add regression tests, and only then "
                       "use existing approved learning.record to save a lesson on the owner PC.",
        "limitations": "Reproduced/evidence SHA flags are user-supplied claims; no external "
                       "verification, automatic retraining, rule change, or persistence."
    }


def run(op, params):
    params = _obj(params)
    functions = {"readiness":readiness, "ladder":ladder,
                 "paired_eval":paired_eval, "reel_preflight":reel_preflight,
                 "reel_seek":reel_seek, "reel_rhythm":reel_rhythm,
                  "feedback_cycle":feedback_cycle}
    if op not in OPS:
        raise ValueError("unknown fusion intelligence operation")
    return functions[op](params)
