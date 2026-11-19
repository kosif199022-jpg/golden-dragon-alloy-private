"""The one canonical edit decision list (kosif.dm.edl.v1): timing (reflow) and converters.

  reflow                rec_in + duration from src ranges, speed and xfade overlaps (the single source of timing)
  record_words          analysis words that survive the edit, on the record timeline
  to_timeline / from_timeline   kosif.timeline.v1
  from_cut_plan         kosif.edl.v1 (cinematic cut planner) -> edl
  to_pve                pro-video-editor EDL JSON
  to_nle                timeline project + words.json for an NLE exporter

CLI: convert --job DIR --to timeline|pve|nle|words [--out] · import --job DIR --cut-plan P | --timeline T · check --job DIR
"""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path

from . import common as C

TIMELINE_SCHEMA = "kosif.timeline.v1"
CUT_PLAN_SCHEMA = "kosif.edl.v1"
XFADE = {"fade", "wipeleft", "wiperight", "wipeup", "wipedown", "slideleft", "slideright", "slideup", "slidedown",
         "circleopen", "circleclose", "dissolve", "pixelize", "radial", "smoothleft", "smoothright", "fadeblack",
         "fadewhite", "distance", "hblur", "zoomin", "squeezeh", "squeezev"}


def r3(x) -> float:
    return round(float(x) + 0.0, 3)


def _key(s) -> str:
    return str(s).strip().lower().replace("_", "-")


def _transitions() -> dict:
    """data/transitions.json: normalised id/alias -> entry (first listed wins)."""
    if "t" not in _transitions.__dict__:
        table = {}
        for it in C.data("transitions.json")["transitions"]:
            for k in [it["id"], *(it.get("aliases") or [])]:
                table.setdefault(_key(k), it)
        _transitions.t = table
    return _transitions.t


def xfade_name(tr: dict | None) -> str | None:
    """'xfade-fade' / 'fade' / {'xfade': 'wipeleft'} / a transitions.json id or alias -> ffmpeg xfade name, None = cut."""
    if not tr:
        return None
    raw = str(tr.get("xfade") or tr.get("type") or tr.get("id") or "cut")
    name = raw[len("xfade-"):] if raw.startswith("xfade-") else raw
    if name in XFADE:
        return name
    xf = (_transitions().get(_key(raw)) or {}).get("xfade")
    return str(xf) if xf and xf != "cut" else None


def overlap(ev: dict) -> float:
    """Seconds this event overlaps the previous one (xfade), 0 for a cut."""
    tr = ev.get("transition_in") or {}
    if xfade_name(tr) is None:
        return 0.0
    secs = tr.get("seconds", tr.get("duration"))
    if secs is None:
        secs = (_transitions().get(_key(tr.get("id") or "")) or {}).get("seconds") or 0.25
    return float(secs)


def event_seconds(ev: dict) -> float:
    return (float(ev["src_out"]) - float(ev["src_in"])) / float(ev.get("speed", 1.0) or 1.0)


def reflow(edl: dict) -> dict:
    """Recompute rec_in for every event (list order) and the total duration. Mutates and returns edl."""
    t, evs = 0.0, edl["events"]
    for i, ev in enumerate(evs):
        ov = 0.0 if i == 0 else min(overlap(ev), event_seconds(ev) / 2, event_seconds(evs[i - 1]) / 2)
        if i == 0 and ev.get("transition_in") and xfade_name(ev["transition_in"]):
            ev["transition_in"] = {"id": "cut"}
        if ov and ev.get("transition_in"):
            ev["transition_in"]["seconds"] = r3(ov)
        ev["src_in"], ev["src_out"] = r3(ev["src_in"]), r3(ev["src_out"])
        ev["rec_in"] = r3(max(0.0, t - ov))
        t = ev["rec_in"] + event_seconds(ev)
    edl["duration"] = r3(t)
    return edl


def check(edl: dict) -> list:
    """Contract validation plus timeline sanity; [] = fine."""
    try:
        C.validate("edl", edl)
    except C.ContractError as exc:
        return [str(exc)]
    problems, prev_end = [], 0.0
    for ev in edl["events"]:
        if ev["rec_in"] < prev_end - overlap(ev) - 0.002:
            problems.append(f"{ev['id']}: overlaps the previous event more than its transition")
        prev_end = ev["rec_in"] + event_seconds(ev)
    if abs(prev_end - edl["duration"]) > 0.01:
        problems.append(f"duration {edl['duration']} != last event end {prev_end:.3f}")
    return problems


def clip_index(analysis) -> dict:
    return {c["id"]: c for c in (analysis or {}).get("clips", [])}


def word_text(w: dict) -> str:
    return str(w.get("w") or w.get("word") or w.get("text") or "")


def record_words(edl: dict, analysis: dict) -> list:
    clips, out = clip_index(analysis), []
    for ev in edl["events"]:
        if ev.get("mute"):
            continue
        sp = float(ev.get("speed", 1.0) or 1.0)
        for w in (clips.get(ev["clip"]) or {}).get("words") or []:
            s, e = float(w["start"]), float(w["end"])
            if s >= ev["src_in"] - 1e-6 and e <= ev["src_out"] + 1e-6:
                out.append({"word": word_text(w), "start": r3(ev["rec_in"] + (s - ev["src_in"]) / sp),
                            "end": r3(ev["rec_in"] + (e - ev["src_in"]) / sp), "event": ev["id"]})
    return out


def _music(edl: dict, analysis) -> tuple:
    m = (edl.get("audio") or {}).get("music") or {}
    return m, m.get("path") or ((analysis or {}).get("music") or {}).get("path")


def to_timeline(edl: dict, analysis: dict, *, include_music: bool = True, name: str | None = None) -> dict:
    """One video track (xfades become fade_in on the incoming clip) + optional music; `dm` metadata round-trips."""
    clips, edl, vclips, warnings = clip_index(analysis), reflow(copy.deepcopy(edl)), [], []
    for ev in edl["events"]:
        c = clips.get(ev["clip"])
        if c is None:
            raise ValueError(f"{ev['id']}: clip {ev['clip']} not in analysis")
        if abs(float(ev.get("speed", 1.0)) - 1.0) > 1e-6:
            warnings.append(f"{ev['id']}: speed {ev['speed']} is not carried by kosif.timeline.v1")
        vclips.append({"id": ev["id"], "path": c["path"], "start": ev["rec_in"], "duration": r3(event_seconds(ev)),
                       "in": ev["src_in"], "include_audio": bool(c.get("has_audio", True)) and not ev.get("mute", False),
                       "fade_in": r3(overlap(ev) if ev is not edl["events"][0] else 0.0), "fade_out": 0,
                       "dm": {k: ev[k] for k in ("clip", "shot", "reason", "role", "kind", "camera", "transition_in",
                                                  "speed", "src_out") if k in ev}})
    tracks = [{"id": "V1", "kind": "video", "layer": 0, "clips": vclips}]
    music, mpath = _music(edl, analysis)
    if include_music and mpath:
        tracks.append({"id": "A1", "kind": "audio", "layer": 0, "clips": [{
            "id": "music", "path": mpath, "start": 0, "duration": edl["duration"], "in": 0,
            "volume": r3(min(3.0, 10 ** (float(music.get("gain_db", -18)) / 20))), "fade_in": 0,
            "fade_out": r3(min(2.0, edl["duration"] / 2))}]})
    doc = {"schema": TIMELINE_SCHEMA, "name": name or "dragon-montage", "width": int(edl["width"]),
           "height": int(edl["height"]), "fps": int(round(float(edl["fps"]))), "duration": edl["duration"],
           "background": "#000000", "tracks": tracks,
           "dm": {"grade": edl.get("grade"), "captions": edl.get("captions"), "audio": edl.get("audio")}}
    if warnings:
        doc["dm"]["warnings"] = warnings
    return doc


def from_timeline(doc: dict, analysis: dict | None = None) -> dict:
    if doc.get("schema") != TIMELINE_SCHEMA:
        raise ValueError(f"expected {TIMELINE_SCHEMA}")
    by_path = {str(Path(c["path"])): c["id"] for c in clip_index(analysis).values()}
    meta, events, music_path, music_gain = doc.get("dm") or {}, [], None, -18.0
    for t in doc["tracks"]:
        if t.get("kind") == "audio" and t.get("clips"):
            music_path, vol = t["clips"][0]["path"], float(t["clips"][0].get("volume", 1.0))
            music_gain = r3(20 * math.log10(vol)) if vol > 0 else music_gain
    vtracks = sorted([t for t in doc["tracks"] if t.get("kind") in ("video", "image")], key=lambda t: int(t.get("layer", 0)))
    flat = sorted([c for t in vtracks for c in t.get("clips", [])], key=lambda c: (float(c["start"]), c["id"]))
    for i, c in enumerate(flat):
        m = c.get("dm") or {}
        src_in, speed = float(c.get("in", 0)), float(m.get("speed", 1.0))
        ev = {"id": c["id"] if str(c["id"]).startswith("e") else f"e{i + 1:03d}",
              "clip": m.get("clip") or by_path.get(str(Path(c["path"]))) or f"x{i + 1:02d}",
              "src_in": r3(src_in), "src_out": r3(m.get("src_out", src_in + float(c["duration"]) * speed)),
              "rec_in": r3(c["start"]), "speed": speed,
              "transition_in": m.get("transition_in") or (
                  {"id": "xfade-fade", "xfade": "fade", "seconds": r3(c["fade_in"])} if float(c.get("fade_in", 0)) > 0 and i
                  else {"id": "cut"}),
              "camera": m.get("camera") or {"id": "static"},
              "reason": m.get("reason") or f"imported from kosif.timeline.v1 clip {c['id']} | مستورد من التايملاين"}
        ev.update({k: m[k] for k in ("shot", "role", "kind") if k in m})
        if not c.get("include_audio", False):
            ev["mute"] = True
        events.append(ev)
    audio = meta.get("audio") or {"music": {"path": music_path, "gain_db": music_gain, "duck_under_speech_db": -10},
                                  "voice_from": "events", "target_lufs": -14}
    return reflow(C.new("edl", width=int(doc["width"]), height=int(doc["height"]), fps=doc["fps"], events=events, audio=audio,
                        captions=meta.get("captions") or {"enabled": False, "style": "none", "words_from": "analysis"},
                        grade=meta.get("grade") or {"id": "none"}, duration=0.0))


def from_cut_plan(doc: dict, analysis: dict | None = None) -> dict:
    """Cut-planner scenes -> events. The planner keeps the voice-over as the bed, so footage events are muted."""
    if doc.get("schema") != CUT_PLAN_SCHEMA:
        raise ValueError(f"expected {CUT_PLAN_SCHEMA}")
    video = doc.get("video") or {}
    fps = video.get("fps", 30)
    by_path = {str(Path(c["path"])): c["id"] for c in clip_index(analysis).values()}
    extra, events = {}, []
    scenes = [s for s in doc.get("scenes") or [] if s.get("footage_path")]
    for sc in scenes:
        p = str(Path(sc["footage_path"]))
        cid = by_path.get(p) or extra.setdefault(p, f"c{len(by_path) + len(extra) + 1:02d}")
        seconds = (int(sc["end_frame_exclusive"]) - int(sc["start_frame"])) / float(fps)
        tin = float((sc.get("video_trim") or {}).get("in", 0.0))
        tout = float((sc.get("video_trim") or {}).get("out", tin + seconds))
        text = str(sc.get("spoken_text") or "").strip()
        events.append({"id": f"e{len(events) + 1:03d}", "clip": cid, "src_in": r3(tin), "src_out": r3(max(tout, tin + 1 / fps)),
                       "rec_in": r3(int(sc["start_frame"]) / float(fps)), "speed": 1.0, "transition_in": {"id": "cut"},
                       "camera": {"id": (sc.get("camera") or {}).get("move") or "static"}, "mute": True, "role": "cover",
                       "reason": f"cut plan {sc.get('id')}: covers “{text[:60]}” | لقطة تغطي الجملة المنطوقة"})
    edl = C.new("edl", width=int(video.get("width", 1080)), height=int(video.get("height", 1920)), fps=fps, events=events,
                audio={"music": {"path": None, "gain_db": -18, "duck_under_speech_db": -10}, "voice_from": "external",
                       "target_lufs": -14},
                captions={"enabled": True, "style": "clean", "words_from": "analysis"}, grade={"id": "none"}, duration=0.0)
    if extra:
        edl["unmapped_sources"] = {v: k for k, v in extra.items()}
    reflow(edl)
    for ev, sc in zip(edl["events"], scenes):   # the planner timeline may have gaps: keep its record positions
        ev["rec_in"] = r3(int(sc["start_frame"]) / float(fps))
    if edl["events"]:
        edl["duration"] = r3(edl["events"][-1]["rec_in"] + event_seconds(edl["events"][-1]))
    return edl


def to_pve(edl: dict, analysis: dict, *, captions: str | None = None, lut: str | None = None) -> dict:
    """The JSON pro-video-editor's edl_render.py reads (it needs an audio stream in every source)."""
    clips, edl = clip_index(analysis), reflow(copy.deepcopy(edl))
    sources, out_clips, notes = {}, [], []
    for ev in edl["events"]:
        c = clips.get(ev["clip"])
        if c is None:
            raise ValueError(f"{ev['id']}: clip {ev['clip']} not in analysis")
        sources.setdefault(ev["clip"], c["path"])
        if not c.get("has_audio", True):
            notes.append(f"{ev['clip']} has no audio stream; edl_render.py needs one (add a silent track)")
        name = xfade_name(ev.get("transition_in"))
        item = {"src": ev["clip"], "in": ev["src_in"], "out": ev["src_out"], "speed": float(ev.get("speed", 1.0)),
                "transition": {"type": "cut"} if name is None or not out_clips else {"type": name, "duration": r3(overlap(ev))}}
        if ev.get("audio_lead"):
            item["audio_lead"] = float(ev["audio_lead"])
        out_clips.append(item)
    doc = {"fps": int(round(float(edl["fps"]))), "size": [int(edl["width"]), int(edl["height"])], "sources": sources,
           "clips": out_clips,
           "audio": {"loudnorm": {"I": float((edl.get("audio") or {}).get("target_lufs", -14)), "TP": -1.0, "LRA": 11}}}
    music, mpath = _music(edl, analysis)
    if mpath:
        doc["sources"]["music"] = mpath
        doc["music"] = {"src": "music", "gain_db": float(music.get("gain_db", -18)), "fade_out": 2.0}
    if lut or (edl.get("grade") or {}).get("lut"):
        doc["lut"] = lut or edl["grade"]["lut"]
    if captions:
        doc["captions"] = captions
    if notes:
        doc["notes"] = sorted(set(notes))
    return doc


def to_nle(edl: dict, analysis: dict, out_dir, *, name: str = "dragon-montage") -> dict:
    """nle_timeline.json (absolute media paths) + nle_words.json (record time) for an NLE exporter."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    proj = to_timeline(edl, analysis, name=name)
    for t in proj["tracks"]:
        for c in t["clips"]:
            c["path"] = str(Path(c["path"]).resolve())
    words = record_words(edl, analysis)
    pf = C.save(out_dir / "nle_timeline.json", proj)
    wf = C.save(out_dir / "nle_words.json", {"words": [{k: w[k] for k in ("word", "start", "end")} for w in words]})
    return {"project": str(pf), "words": str(wf), "has_words": bool(words)}


def main(argv=None) -> int:
    C.utf8_stdio()
    ap = argparse.ArgumentParser(prog="dragon_montage edl", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    cv = sub.add_parser("convert")
    cv.add_argument("--job", required=True)
    cv.add_argument("--to", required=True, choices=["timeline", "pve", "nle", "words"])
    cv.add_argument("--out")
    im = sub.add_parser("import")
    im.add_argument("--job", required=True)
    g = im.add_mutually_exclusive_group(required=True)
    g.add_argument("--cut-plan")
    g.add_argument("--timeline")
    sub.add_parser("check").add_argument("--job", required=True)
    a = ap.parse_args(argv)
    job = Path(a.job)
    analysis = C.read(job, "analysis")
    if a.cmd == "import":
        src = json.loads(Path(a.cut_plan or a.timeline).read_text(encoding="utf-8"))
        edl = from_cut_plan(src, analysis) if a.cut_plan else from_timeline(src, analysis)
        print(json.dumps({"written": str(C.write(job, "edl", edl)), "events": len(edl["events"])}))
        return 0
    edl = C.read(job, "edl")
    if a.cmd == "check":
        probs = check(edl)
        print(json.dumps({"ok": not probs, "problems": probs}, ensure_ascii=False))
        return 0 if not probs else 1
    if a.to == "nle":
        print(json.dumps(to_nle(edl, analysis, a.out or job / "render"), ensure_ascii=False))
        return 0
    doc = {"timeline": lambda: to_timeline(edl, analysis), "pve": lambda: to_pve(edl, analysis),
           "words": lambda: {"words": record_words(edl, analysis)}}[a.to]()
    out = C.save(Path(a.out or job / f"edl.{a.to}.json"), doc)
    print(json.dumps({"written": str(out)}))
    return 0
