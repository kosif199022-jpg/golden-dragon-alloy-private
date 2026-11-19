"""Optional station «المحاكاة» («اعمل زي الفيديو ده»): measure a reference video's rhythm and look.

  mimic --job DIR --reference ref.mp4

Writes reference_rhythm.json (kosif.dm.reference_rhythm.v1: shots, transitions, stats, pacing hints the director
uses for shot lengths) and look_override.json (a kosif.dm.look.v1 measured from the reference: grade preset,
transitions, caption hint) that the taste station lets override its pick. Reads the reference only.
The reference is measured natively: shot cuts (PySceneDetect / scdet) and per-shot colour (OpenCV); every boundary
is a hard cut (no transition-kind re-synthesis, on-screen text OCR or Ken-Burns detection).
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from . import common as C
import importlib
A = importlib.import_module(".analyze", __package__)   # the module (the package exports a function of the same name)

SCHEMA = "kosif.dm.reference_rhythm.v1"


def measure_reference(job: Path, ref: Path) -> dict:
    """A small spec of the reference: {reference, shots[{id,start_s,end_s,dur_s,sat,lum,lab}], transitions, texts, look}."""
    ctx = A.Ctx(job)
    info = A.probe_clip(ctx, ref)
    dur = info["duration"] or 0.0
    cuts = A.shots_pyscenedetect(ctx, ref) if C.have_module("scenedetect") else None
    cuts = cuts if cuts is not None else (A.shots_scdet(ctx, ref) or [])
    bounds = A.build_shots(cuts, dur)
    stats = [[] for _ in bounds]
    if C.have_module("cv2"):
        import cv2
        k = 0
        for t, f in A.iter_frames(ctx, ref, info):
            while k < len(bounds) - 1 and t >= bounds[k][1]:
                k += 1
            hsv, lab = cv2.cvtColor(f, cv2.COLOR_RGB2HSV), cv2.cvtColor(f, cv2.COLOR_RGB2LAB).reshape(-1, 3).mean(axis=0)
            stats[k].append((hsv[..., 1].mean() / 255.0, hsv[..., 2].mean() / 255.0, float(lab[2]) - 128.0))
    shots = []
    for i, ((s, e), st) in enumerate(zip(bounds, stats), 1):
        mean = lambda j: statistics.fmean(x[j] for x in st) if st else None  # noqa: E731
        shots.append({"id": i, "start_s": round(s, 3), "end_s": round(e, 3), "dur_s": round(e - s, 3), "sat": mean(0),
                      "lum": mean(1), "lab": {"mean": [None, None, mean(2)]} if st else None, "kenburns": None, "palette": []})
    return {"reference": {"duration": dur, "w": info["width"], "h": info["height"], "fps": info["fps"],
                          "audio": {"has_audio": info["has_audio"]}},
            "shots": shots, "transitions": [{"ts_s": s, "te_s": s, "type": "cut", "confidence": 1.0} for s, _ in bounds[1:]],
            "texts": [], "look": {}}


def grade_from(spec: dict) -> dict:
    shots, look = spec.get("shots", []), spec.get("look", {})
    sat = statistics.fmean([float(s.get("sat") or 0) for s in shots]) if shots else 0.3
    lum = statistics.fmean([float(s.get("lum") or 0) for s in shots]) if shots else 0.5
    lab = [x for x in ((s.get("lab") or {}).get("mean") for s in shots if isinstance(s.get("lab"), dict))
           if isinstance(x, (list, tuple)) and len(x) >= 3 and x[2] is not None]
    warm = statistics.fmean([float(x[2]) for x in lab]) if lab else 0.0  # Lab b*: + yellow, - blue
    vig = float((look.get("vignette") or {}).get("strength") or 0)
    gid = ("mono" if sat < 0.06 else "night-dua" if lum < 0.3 and warm < 0 else "dramatic" if lum < 0.35 or vig > 0.35 else
           "vivid" if sat > 0.45 else "warm" if warm > 12 else "cool" if warm < -12 else "faded" if sat < 0.18 else
           "bright" if lum > 0.62 else "cinematic")
    return {"id": gid, "engine": "look_pipeline", "lut": None,
            "measured": {"saturation": round(sat, 3), "luminance": round(lum, 3), "warmth_b": round(warm, 2), "vignette": round(vig, 3),
                         "grain": (look.get("grain") or {}).get("sigma"), "letterbox": look.get("letterbox"),
                         "fade_in_frames": look.get("fade_in_frames"), "fade_out_frames": look.get("fade_out_frames")}}


def rhythm(spec: dict, ref: Path) -> dict:
    r = spec["reference"]
    dur = float(r.get("duration") or 0)
    shots = [{"n": s["id"], "start": float(s["start_s"]), "end": float(s["end_s"]), "seconds": float(s["dur_s"]),
              "motion": (s.get("motion") or {}).get("speed"), "kenburns": s.get("kenburns"),
              "palette": [p.get("name") for p in s.get("palette", [])[:3]]} for s in spec.get("shots", [])]
    trans = [{"at": float(t.get("ts_s", 0)), "type": t["type"], "xfade": "cut" if t["type"] == "cut" else "fade",
              "seconds": round(float(t.get("te_s", 0)) - float(t.get("ts_s", 0)), 3), "confidence": t.get("confidence")}
             for t in spec.get("transitions", [])]
    lens = [s["seconds"] for s in shots if s["seconds"] > 0] or [dur or 1.0]
    mean = statistics.fmean(lens)
    cuts = sum(1 for t in trans if t["xfade"] == "cut")
    mix: dict = {}
    for t in trans:
        mix[t["xfade"]] = mix.get(t["xfade"], 0) + 1
    mix = {k: round(v / len(trans), 3) for k, v in mix.items()} if trans else {"cut": 1.0}
    pace = "fast" if mean < 1.5 else "medium" if mean < 3.5 else "slow"
    hints = [f"متوسط طول اللقطة في المرجع {mean:.2f} ث — الإيقاع {'سريع' if pace == 'fast' else 'متوسط' if pace == 'medium' else 'هادي'}",
             f"عدد القطعات في الدقيقة {60 * len(trans) / dur:.1f}" if dur else "المدة غير معروفة",
             f"نسبة القطع المباشر {cuts}/{len(trans)}" if trans else "المرجع لقطة واحدة من غير انتقالات"]
    return {"schema": SCHEMA, "reference": {"path": str(ref), "duration": dur, "w": r.get("w"), "h": r.get("h"), "fps": r.get("fps"),
                                            "has_audio": (r.get("audio") or {}).get("has_audio")},
            "shots": shots, "transitions": trans, "texts": spec.get("texts", []),
            "stats": {"shot_count": len(shots), "mean_shot_s": round(mean, 3), "median_shot_s": round(statistics.median(lens), 3),
                      "min_shot_s": round(min(lens), 3), "max_shot_s": round(max(lens), 3),
                      "cuts_per_min": round(60 * len(trans) / dur, 2) if dur else None},
            "pacing": {"pace": pace, "mean_shot_s": round(mean, 3), "shot_lengths_s": [round(x, 3) for x in lens],
                       "shot_pattern": [round(x / mean, 3) for x in lens], "cut_ratio": round(cuts / len(trans), 3) if trans else 1.0,
                       "transition_mix": mix, "hints_ar": hints},
            "source": {"tool": "engines.dragon_montage.mimic", "spec": "mimic/spec.json"}}


def look_override(spec: dict, rh: dict) -> dict:
    trans, seen = [], set()
    for t in rh["transitions"]:
        if t["xfade"] not in seen:
            seen.add(t["xfade"])
            trans.append({"id": "cut"} if t["xfade"] == "cut" else {"id": t["xfade"], "seconds": max(0.1, round(t["seconds"], 3) or 0.25)})
    pace = rh["pacing"]["pace"]
    return C.new("look", style_id="mimic-reference", style_source="mimic", grade=grade_from(spec), transitions=trans or [{"id": "cut"}],
                 camera=[], captions={"style": ("punchy" if pace == "fast" else "clean") if rh["texts"] else "none", "font": "Cairo",
                                      "position": "lower"},
                 music={"mood": None, "bpm_range": {"fast": [110, 140], "medium": [90, 115], "slow": [60, 90]}[pace]},
                 why=f"مقاس من الفيديو المرجعي: {rh['stats']['shot_count']} لقطة، متوسط {rh['stats']['mean_shot_s']} ث، "
                     f"انتقالات {', '.join(t['id'] for t in trans or [{'id': 'cut'}])}")


def mimic(job, reference, exact: bool = False) -> dict:
    """exact (--reference-exact): the director cuts at the reference's own cut times, not at its mean shot length."""
    job, ref = C.job_dir(job), Path(reference).resolve()
    if not ref.is_file():
        raise SystemExit(f"reference {ref} not found")
    (job / "mimic").mkdir(exist_ok=True)
    spec = measure_reference(job, ref)
    C.save(job / "mimic" / "spec.json", spec)
    rh = rhythm(spec, ref)
    rh["exact"] = bool(exact)
    lk = C.validate("look", look_override(spec, rh))
    C.save(job / "reference_rhythm.json", rh)
    C.save(job / "look_override.json", lk)
    return {"rhythm": rh, "look": lk}


def main(argv=None) -> int:
    C.utf8_stdio()
    p = argparse.ArgumentParser(prog="dragon_montage mimic", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("mimic")
    m.add_argument("--job", required=True)
    m.add_argument("--reference", required=True)
    m.add_argument("--skip-text", action="store_true", help="kept for compatibility (no OCR here)")
    m.add_argument("--sensitivity", type=float, default=1.0)
    a = p.parse_args(argv)
    res = mimic(a.job, a.reference)
    print(json.dumps({"job": str(Path(a.job).resolve()), "shots": res["rhythm"]["stats"]["shot_count"],
                      "mean_shot_s": res["rhythm"]["stats"]["mean_shot_s"], "grade": res["look"]["grade"]["id"],
                      "transitions": [t["id"] for t in res["look"]["transitions"]]}, ensure_ascii=False))
    return 0
