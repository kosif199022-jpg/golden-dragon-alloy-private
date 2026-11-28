"""V69 storyboard continuity ledger check (read-only).

Method reviewed from an owner-supplied storyboard guide (see V69_INTAKE_CONTINUITY_GUIDE.md); this is an
original implementation. It checks a shot list's structure: whole-frame contiguous timeline, tracked state
(location / wardrobe / props / scale) that only changes with a stated reason, no repeated shot type in
consecutive shots, real motion in every beat (no slideshow), actions that land in the next shot, and
justified hard cuts. It never generates media and does not judge rendered frames: pair it with
media-contract verify and visual review of the actual output.
"""
from __future__ import annotations
import json
from pathlib import Path

SHOT_TYPES = {"wide", "medium", "close", "close-up", "extreme-close", "macro", "low-angle", "high-angle",
              "over-the-shoulder", "pov", "dynamic", "insert", "two-shot", "establishing", "aerial"}
STATIC = {"static", "locked", "locked-off", "none", "still", ""}
CUTS = {"motion", "match", "hard", "dissolve", "whip"}


def _txt(v):
    return v.strip() if isinstance(v, str) else ""


def check(spec: dict) -> dict:
    if type(spec) is not dict:
        raise ValueError("spec must be an object")
    fps = spec.get("fps", 30)
    if type(fps) is not int or not 1 <= fps <= 240:
        raise ValueError("fps must be an integer 1-240")
    shots = spec.get("shots")
    if type(shots) is not list or not 1 <= len(shots) <= 400:
        raise ValueError("shots must be a list of 1-400 items")
    allow_static = spec.get("allow_static") is True
    max_same_cam = spec.get("max_same_camera_seconds", 3)
    if not isinstance(max_same_cam, (int, float)) or max_same_cam <= 0:
        raise ValueError("max_same_camera_seconds must be positive")
    issues, ledger_changes = [], []

    def issue(sev, sid, code, msg):
        issues.append({"severity": sev, "shot": sid, "code": code, "message": msg})

    ids, cursor, prev = set(), 0, None
    cam_run = (None, 0)
    for n, s in enumerate(shots):
        if type(s) is not dict:
            raise ValueError(f"shot {n} must be an object")
        sid = str(s.get("id", n + 1))
        if sid in ids:
            raise ValueError(f"duplicate shot id {sid}")
        ids.add(sid)
        a, b = s.get("start_frame"), s.get("end_frame")
        if type(a) is not int or type(b) is not int:
            raise ValueError(f"shot {sid}: start_frame/end_frame must be whole-frame integers")
        if b <= a:
            issue("error", sid, "empty_shot", "end_frame must be after start_frame")
        if a != cursor:
            issue("error", sid, "timeline_gap" if a > cursor else "timeline_overlap",
                  f"starts at frame {a}, previous shot ended at {cursor}")
        if b - a < fps // 2:
            issue("warning", sid, "very_short_beat",
                  f"{b - a} frames (<0.5 s): add motion inside beats instead of shortening them")
        cursor = max(cursor, b)

        stype = _txt(s.get("shot_type")).lower()
        if stype not in SHOT_TYPES:
            issue("error", sid, "unknown_shot_type", f"shot_type '{stype}' not in {sorted(SHOT_TYPES)}")
        cam = _txt(s.get("camera_move")).lower()
        if cam in STATIC and not allow_static:
            issue("error", sid, "static_camera", "camera does nothing for the whole beat (slideshow risk); "
                  "add a slow push/drift or set allow_static for a deliberate locked-off style")
        if not _txt(s.get("subject_motion")) and not allow_static:
            issue("error", sid, "no_subject_motion", "no continuous on-screen motion described for this beat")
        frames = b - a
        cam_run = (cam, cam_run[1] + frames) if cam == cam_run[0] else (cam, frames)
        if cam not in STATIC and cam_run[1] > max_same_cam * fps:
            issue("warning", sid, "camera_not_varied",
                  f"same camera move '{cam}' for {cam_run[1] / fps:.1f} s (> {max_same_cam} s)")

        cut = _txt(s.get("cut_in", "motion")).lower()
        if n and cut not in CUTS:
            issue("error", sid, "unknown_cut", f"cut_in '{cut}' not in {sorted(CUTS)}")
        if n and cut == "hard" and not _txt(s.get("hard_cut_reason")):
            issue("error", sid, "unjustified_hard_cut", "hard cut needs hard_cut_reason (scene jump, reveal)")

        state = s.get("state", {})
        changes = s.get("changes", {})
        if type(state) is not dict or type(changes) is not dict:
            raise ValueError(f"shot {sid}: state and changes must be objects")
        # Keys not restated in this shot keep their previous value (explicit carried ledger).
        carried = dict(prev["state"]) if prev else {}
        carried.update(state)
        if prev is not None:
            pstate, psid = prev["state"], prev["id"]
            for key, old in pstate.items():
                new = carried.get(key)
                if new != old:
                    reason = _txt(changes.get(key))
                    if not reason:
                        issue("error", sid, "continuity_drift",
                              f"'{key}' changed from {old!r} to {new!r} since shot {psid} with no stated reason")
                    else:
                        ledger_changes.append({"shot": sid, "key": key, "from": old, "to": new, "reason": reason})
            for key in changes:
                if carried.get(key) == pstate.get(key):
                    issue("warning", sid, "unused_change_reason", f"'{key}' has a change reason but did not change")
            if prev["action"] and not _txt(s.get("action_result")):
                issue("error", sid, "dangling_action",
                      f"shot {psid} starts '{prev['action']}' but this shot does not show its result")
            if stype and stype == prev["type"]:
                issue("error", sid, "repeated_shot_type", f"same shot type '{stype}' as shot {psid}")
        elif changes:
            issue("warning", sid, "unused_change_reason", "first shot has nothing to change from")
        prev ={"id": sid, "state": carried, "action": _txt(s.get("action_start")), "type": stype}

    total = spec.get("duration_frames")
    if total is not None:
        if type(total) is not int:
            raise ValueError("duration_frames must be an integer")
        if cursor != total:
            issue("error", "timeline", "duration_mismatch", f"shots end at frame {cursor}, expected {total}")
    if prev and prev["action"] and spec.get("final_action_resolved") is not True:
        issue("warning", prev["id"], "dangling_action", "last shot starts an action that never lands")
    errors = sum(i["severity"] == "error" for i in issues)
    return {"status": "pass" if not issues else ("review_required" if errors else "pass_with_warnings"),
            "errors": errors, "warnings": len(issues) - errors, "issues": issues,
            "shots": len(shots), "frames": cursor, "seconds": round(cursor / fps, 3), "fps": fps,
            "justified_changes": ledger_changes,
            "structure_only": True, "rendered_frames_checked": False, "generation_performed": False,
            "note": "Checks the written plan only. Verify the rendered video's continuity, motion and timing separately."}


def handle(a):
    try:
        p = Path(a.spec)
        if p.stat().st_size > 512 * 1024:
            raise ValueError("input too large")
        print(json.dumps(check(json.loads(p.read_text(encoding="utf-8-sig"))), ensure_ascii=False))
        return 0
    except (ValueError, OSError, TypeError, KeyError, json.JSONDecodeError) as e:
        print(json.dumps({"error": str(e)[:300]}))
        return 1


def register(sub):
    p = sub.add_parser("continuity", help="V69 read-only storyboard continuity ledger check")
    p.add_argument("action", choices=["check"])
    p.add_argument("spec")
    p.set_defaults(ext_func=handle)
