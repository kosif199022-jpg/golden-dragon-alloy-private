"""Red Rose V29 — bounded evidence director, storyboard planner, and frame layout.

Self-contained deterministic Python. No model call, network, filesystem I/O,
legacy imports, or reliance on source ZIPs. Implements original review and
planning methods informed by, but does not reproduce, uploaded references.
A score or shot plan is NOT proof of creative quality or factual truth.
"""
from __future__ import annotations

import math
import re

OPS = ("decision_review", "storyboard_plan", "layout_audit")
_STYLES = ("faceless", "reel", "saas", "toon", "3d", "clay", "editorial", "map")
_ASPECTS = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)}
_EVIDENCE = {"verified": 1.0, "measured": 0.8, "reviewed": 0.65, "anecdotal": 0.2}
_RTL = re.compile(r"[\u0590-\u08ff\uFB1D-\uFEFF]")


def _object(value):
    if type(value) is not dict:
        raise ValueError("params must be a JSON object")
    return value


def _fields(data, allowed, required=()):
    if set(data) - set(allowed):
        raise ValueError("unknown parameters: " + ",".join(sorted(set(data)-set(allowed))))
    if set(required)-set(data):
        raise ValueError("required parameters missing: " + ",".join(sorted(set(required)-set(data))))


def _str(value, name, maxlen=240):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= maxlen:
        raise ValueError(name + " must be a nonempty bounded string")
    return value.strip()


def _num(value, name, lo, hi):
    if type(value) not in (float, int) or not math.isfinite(value) or not lo <= value <= hi:
        raise ValueError(name + " out of range")
    return float(value)


def _integer(value, name, lo, hi):
    if type(value) is not int or not lo <= value <= hi:
        raise ValueError(name + " must be a bounded integer")
    return value


def _list(value, name, minimum, maximum):
    if type(value) is not list or not minimum <= len(value) <= maximum:
        raise ValueError(name + " list length invalid")
    return value


def decision_review(params):
    """Compare declared alternatives with calibrated uncertainty and counterchecks."""
    _fields(params, ("goal", "options", "high_stakes", "deadline_hours"), ("goal", "options"))
    goal = _str(params["goal"], "goal", 450)
    if type(params.get("high_stakes", False)) is not bool:
        raise ValueError("high_stakes must be boolean")
    urgent = params.get("deadline_hours")
    if urgent is not None:
        _num(urgent, "deadline_hours", 0, 8760)
    options = _list(params["options"], "options", 2, 8)
    seen, results = set(), []
    for item in options:
        item = _object(item)
        _fields(item, ("id", "benefit", "risk", "cost", "reversible", "estimated_success",
                       "base_rate", "evidence"), ("id", "benefit", "risk", "cost",
                                               "reversible", "estimated_success"))
        ident = _str(item["id"], "id", 60)
        if ident in seen:
            raise ValueError("duplicate option id")
        seen.add(ident)
        benefit = _num(item["benefit"], "benefit", 0, 10)
        risk = _num(item["risk"], "risk", 0, 10)
        cost = _num(item["cost"], "cost", 0, 10)
        reversible = _num(item["reversible"], "reversible", 0, 1)
        estimate = _num(item["estimated_success"], "estimated_success", 0, 1)
        evidence = _list(item.get("evidence", []), "evidence", 0, 10)
        if any(e not in _EVIDENCE for e in evidence):
            raise ValueError("unknown evidence class")
        strength = min(1.0, sum(_EVIDENCE[e] for e in evidence) / 3)
        base_rate = item.get("base_rate")
        if base_rate is not None:
            base_rate = _num(base_rate, "base_rate", 0, 1)
        anchor = base_rate if base_rate is not None else 0.5
        calibrated = anchor + (estimate-anchor) * strength
        score = calibrated * benefit - .65*risk - .35*cost + .4*reversible
        flags = []
        if base_rate is None:
            flags.append("missing_outside_view_baseline")
        if strength < 0.5:
            flags.append("weak_evidence")
        if estimate - anchor > .3 and strength < .7:
            flags.append("possible_overconfidence")
        if risk >= 7 or reversible < .2:
            flags.append("high_downside_or_irreversibility")
        results.append({"id": ident, "declared_success": round(estimate, 4),
                        "calibrated_success": round(calibrated, 4),
                        "evidence_strength": round(strength, 4), "expected_score": round(score, 4),
                        "flags": flags})
    ordered = sorted(results, key=lambda x: (-x["expected_score"], x["id"]))
    gate = (params.get("high_stakes", False) or
            any("high_downside_or_irreversibility" in v["flags"] for v in results))
    if urgent is not None and urgent < 24:
        gate = True
    return {"status": "advisory_not_executed", "goal": goal,
            "ranking": ordered, "leading_option": ordered[0]["id"],
            "human_review_required": bool(gate), "checks": [
                "Check base rates before trusting vivid examples.",
                "Compare options against a measurable outside-view baseline.",
                "Ask what evidence would falsify the leading estimate.",
                "Review worst-case consequences and reversibility.",
                "Evaluate the actual goal; do not substitute an easier question.",
                "Avoid sunk-cost and loss-framing distortions."
            ], "warning": "Scores reflect user-supplied assumptions; not a probability forecast or a substitute for expert review."}


def _frame_alloc(weights, total, min_each):
    count = len(weights)
    if total < count*min_each:
        raise ValueError("video too short for the supplied shot count")
    remaining = total-count*min_each
    raw = [remaining*w/sum(weights) for w in weights]
    additional = [math.floor(t) for t in raw]
    leftovers = remaining-sum(additional)
    for idx in sorted(range(count), key=lambda i: (-(raw[i]-additional[i]), i))[:leftovers]:
        additional[idx] += 1
    return [min_each+a for a in additional]


def storyboard_plan(params):
    """Produce frame-exact, editable beats, preserving Arabic words as whole strings."""
    _fields(params, ("goal","seconds","fps","style","aspect","language","beats",
                     "has_voice","assets_rights_confirmed"),
            ("goal","seconds","fps","style"))
    goal = _str(params["goal"], "goal", 450)
    seconds = _num(params["seconds"], "seconds", 5, 90)
    fps = _integer(params["fps"], "fps", 12, 60)
    style = _str(params["style"], "style", 30)
    if style not in _STYLES:
        raise ValueError("unsupported style")
    aspect = params.get("aspect", "9:16")
    if aspect not in _ASPECTS:
        raise ValueError("unsupported aspect ratio")
    lang = params.get("language", "ar")
    if lang not in ("ar","en"):
        raise ValueError("language must be ar or en")
    voice = params.get("has_voice", False)
    rights = params.get("assets_rights_confirmed", False)
    if type(voice) is not bool or type(rights) is not bool:
        raise ValueError("voice/rights flags must be boolean")
    beats = params.get("beats")
    if beats is None:
        labels = (("خطاف", "سياق", "حدث", "دليل", "خاتمة") if lang == "ar" else
                  ("Hook", "Context", "Action", "Evidence", "Closing"))
        beats = [{"label": label, "weight": weight, "caption": label}
                 for label, weight in zip(labels, (1,2,3,2,1))]
    beats = _list(beats, "beats", 2, 12)
    cleaned = []
    for i, beat in enumerate(beats):
        beat = _object(beat)
        _fields(beat, ("label", "caption", "weight", "visual"), ("label",))
        label = _str(beat["label"], "beat label", 80)
        caption = _str(beat.get("caption", label), "caption", 140)
        weight = _num(beat.get("weight", 1), "weight", .1, 10)
        visual = _str(beat.get("visual", style), "visual", 80)
        cleaned.append({"label":label,"caption":caption,"weight":weight,"visual":visual})
    total = round(seconds * fps)
    durations = _frame_alloc([b["weight"] for b in cleaned],total,max(1,round(.45*fps)))
    start, out = 0, []
    for i, (beat, n) in enumerate(zip(cleaned,durations)):
        direction = "rtl" if _RTL.search(beat["caption"]) else "ltr"
        out.append({"index":i+1,"label":beat["label"],"visual":beat["visual"],
                    "start_frame":start,"end_frame_exclusive":start+n,
                    "duration_frames":n,"duration_seconds":round(n/fps,4),
                    "caption_text":beat["caption"],"text_direction":direction,
                    "text_animation_unit":"whole_word"})
        start += n
    issues = []
    if voice:
        issues.append("word_alignment_requires_real_audio_or_trusted_timestamps")
    if not rights:
        issues.append("verify_asset_rights_before_render_or_publish")
    if len(out)>8:
        issues.append("review_pacing_high_shot_count")
    return {"status":"editable_plan_not_rendered","goal":goal,"style":style,
            "fps":fps,"aspect":aspect,"canvas":{"width":_ASPECTS[aspect][0],
                                              "height":_ASPECTS[aspect][1]},
            "total_frames":total,"total_seconds":round(total/fps,4),"shots":out,
            "shot_count":len(out),"open_reviews":issues,
            "editing_contract":{"frame_end":"exclusive","captions":"word-level no Arabic glyph splitting",
                                "safe_area_ratio":.85,"human_review_before_export":True},
            "limitations":"No language understanding, voice generation, 3D render or video output."}


def layout_audit(params):
    """Original constrained row/column allocation; doesn't read the binary Figma file."""
    _fields(params, ("width","height","padding","gap","direction","rtl","items"),
            ("width","height","items"))
    width = _integer(params["width"],"width",120,8192)
    height = _integer(params["height"],"height",120,8192)
    padding = _integer(params.get("padding",16),"padding",0,256)
    gap = _integer(params.get("gap",8),"gap",0,128)
    direction = params.get("direction","column")
    if direction not in ("row","column"):
        raise ValueError("direction must be row/column")
    rtl = params.get("rtl", False)
    if type(rtl) is not bool:
        raise ValueError("rtl must be boolean")
    items = _list(params["items"],"items",1,24)
    major = width if direction == "row" else height
    cross = height if direction == "row" else width
    usable = major-2*padding-gap*(len(items)-1)
    cross_usable = cross-2*padding
    if cross_usable <= 0:
        raise ValueError("padding exceeds available cross-axis space")
    clean, total_min, seen = [], 0, set()
    for x in items:
        x = _object(x)
        _fields(x, ("id","min_size","weight"),("id",))
        ident=_str(x["id"],"item id",60)
        if ident in seen:
            raise ValueError("duplicate item id")
        seen.add(ident)
        minimum = _integer(x.get("min_size",40),"min_size",1,4096)
        weight = _num(x.get("weight",1),"weight",.1,100)
        total_min+=minimum
        clean.append((ident,minimum,weight))
    overflow= max(0,total_min-usable)
    extras=max(0,usable-total_min)
    allocation = _frame_alloc([t[2] for t in clean],extras+len(clean),1)
    sizes=[item[1]+additional-1 for item,additional in zip(clean,allocation)]
    pos=padding
    placements=[]
    for (ident,_,_),size in zip(clean,sizes):
        if direction=="row":
            x=width-padding-(pos-padding)-size if rtl else pos
            rect={"x":x,"y":padding,"width":size,"height":cross_usable}
        else:
            rect={"x":padding,"y":pos,"width":cross_usable,"height":size}
        placements.append({"id":ident,**rect})
        pos+=size+gap
    flags=[]
    if overflow:
        flags.append("items_overflow_major_axis")
    if cross_usable<48:
        flags.append("cross_axis_too_small_for_controls")
    return {"status":"geometry_only_not_rendered","width":width,"height":height,
            "direction":direction,"rtl":rtl,"overflow_pixels":overflow,
            "placements":placements,"warnings":flags,
            "note":"Abstract layout geometry only; Figma binary layers are not imported or editable."}


def run(op, params):
    params=_object(params)
    if op not in OPS:
        raise ValueError("unknown intelligence director op")
    return {"decision_review":decision_review,
            "storyboard_plan":storyboard_plan,
            "layout_audit":layout_audit}[op](params)
