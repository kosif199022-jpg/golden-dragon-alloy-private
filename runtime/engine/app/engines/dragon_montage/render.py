"""Station 6 «ينفّذ»: edl.json -> render/final.mp4 (or preview.mp4), captions.srt/.ass, words.json, render.json.

timing   edl.reflow is the single source of truth; events snap to whole frames (render.json events_out);
         src ranges past the media end are clamped (warning) instead of freeze-padded.
pass A   one filter_complex, one `-ss/-t -i` input per event; ffmpeg runs in render/ so filter options only name
         relative files: trim -> speed -> cover crop to WxH around the face -> camera move -> concat / xfade ->
         grade (ev.grade overrides) -> burned RTL ASS captions. Audio: per event (silence when muted), de-click fades,
         acrossfade on transitions, music bed ducked under speech (sidechaincompress).
pass B/C loudnorm measure -> linear apply + true-peak limiter, video copied.
verify   qc.verify (delivery spec + loudness) -> render.json verify
export   render/nle_timeline.json + nle_words.json; an NLE exporter (DRAGON_NLE_EXPORT=path/to/nle_export.py) when set.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
import re
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from . import common as C
from . import edl as E
from . import qc
from ..media import exe, probe

BT709 = ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
         "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709"]
STATION = "6-render"
GRADES = {"natural": "eq=contrast=1.02:saturation=1.04",
          "cinematic": "eq=contrast=1.08:saturation=0.92:gamma=0.98,colorbalance=rs=-0.03:bs=0.04:rh=0.04:bh=-0.03,vignette=angle=PI/5"}
XFADE_NAMES = {"fade", "wipeleft", "wiperight", "wipeup", "wipedown", "slideleft", "slideright", "slideup", "slidedown",
               "circlecrop", "rectcrop", "distance", "fadeblack", "fadewhite", "radial", "smoothleft", "smoothright",
               "smoothup", "smoothdown", "circleopen", "circleclose", "vertopen", "vertclose", "horzopen", "horzclose",
               "dissolve", "pixelize", "diagtl", "diagtr", "diagbl", "diagbr", "hlslice", "hrslice", "vuslice", "vdslice",
               "hblur", "fadegrays", "wipetl", "wipetr", "wipebl", "wipebr", "squeezeh", "squeezev", "zoomin"}
CAMERA = {"none": {"type": "none"}, "punch-in": {"type": "static", "scale": 1.08},
          "slow-push": {"type": "push", "scale": 1.10}, "ken-burns": {"type": "pan", "scale": 1.12}}
_ASS = {"OutlineColour": "&H00000000", "BackColour": "&H80000000", "BorderStyle": 1, "Encoding": -1}
CAPTIONS = {  # ASS V4+ at PlayRes 1080 on the short side (size/outline/shadow) and H=1920 (MarginV)
    "karaoke": {"ass": {**_ASS, "Fontname": "Cairo", "Fontsize": 74, "PrimaryColour": "&H00FFFFFF", "SecondaryColour": "&H0059DEFF",
                        "Bold": -1, "Outline": 6, "Shadow": 3, "Alignment": 2, "MarginV": 300}, "max_words": 5, "pop": 112,
                "highlight": "spoken-word"},
    "punchy": {"ass": {**_ASS, "Fontname": "Cairo", "Fontsize": 88, "PrimaryColour": "&H00FFFFFF", "SecondaryColour": "&H004DE0FF",
                       "Bold": -1, "Outline": 9, "Shadow": 0, "Alignment": 5, "MarginV": 0}, "max_words": 2, "pop": 120,
               "highlight": "spoken-word"},
    "clean": {"ass": {**_ASS, "Fontname": "Cairo", "Fontsize": 54, "PrimaryColour": "&H00F2F2F2", "SecondaryColour": "&H00F2F2F2",
                      "Bold": 0, "Outline": 2, "Shadow": 1, "Alignment": 2, "MarginV": 220}, "max_words": 7, "pop": 100,
              "highlight": "none"}}
SAFE_AREA = {"9:16": {"bottom": 0.22, "top": 0.10}, "4:5": {"bottom": 0.14, "top": 0.08},
             "1:1": {"bottom": 0.10, "top": 0.06}, "16:9": {"bottom": 0.08, "top": 0.06}}
FONT_FALLBACK = ["Cairo", "Tajawal", "Noto Kufi Arabic", "Noto Sans Arabic", "DejaVu Sans"]
DEFAULT_XFADE_SECONDS = 0.3
CUT_DECLICK = 0.012           # seconds of fade at each cut edge (no length change)
TP_CEILING = -1.0             # dBTP the delivered file must stay under
TP_INTERNAL = -1.5            # loudnorm TP target; the limiter sits under it (AAC adds overshoot)


# ----------------------------------------------------------------------------- vocabularies
def grade_filter(gid):
    if not gid or gid == "off":
        return None
    ent = C.lookup("grades.json", gid)
    for k in ("ffmpeg", "vf", "filter"):
        if ent and isinstance(ent.get(k), str) and ent[k].strip():
            return None if ent[k].strip() == "null" else ent[k].strip()
    return None if gid == "none" else GRADES.get(gid.replace("-", "_"), GRADES["natural"])


@lru_cache(maxsize=1)
def xfade_names() -> frozenset:
    """Transitions this ffmpeg's xfade knows (asked once)."""
    try:
        h = subprocess.run([exe("ffmpeg"), "-hide_banner", "-h", "filter=xfade"], capture_output=True, timeout=20, **C.TEXT).stdout
        found = {ln.split()[0] for ln in h[h.find("transition"):h.find("duration")].splitlines()[1:] if ln.strip()}
        return frozenset(found - {"custom"} if "fade" in found else XFADE_NAMES)
    except (OSError, subprocess.SubprocessError):
        return frozenset(XFADE_NAMES)


@lru_cache(maxsize=1)
def graph_file_option() -> str:
    """ffmpeg 7+ reads an option's value from a file with `-/filter_complex`; 9.x dropped -filter_complex_script."""
    v = subprocess.run([exe("ffmpeg"), "-hide_banner", "-version"], capture_output=True, **C.TEXT).stdout
    m = re.search(r"version\s+n?(\d+)\.", v)
    return "-filter_complex_script" if m and int(m.group(1)) < 7 else "-/filter_complex"


def transition_name(tr) -> tuple:
    if not tr:
        return "cut", 0.0
    raw = str(tr.get("xfade") or tr.get("id") or "cut")
    tid = raw[len("xfade-"):] if raw.startswith("xfade-") else raw
    secs = tr.get("seconds") or tr.get("duration")
    ent = C.lookup("transitions.json", raw) or C.lookup("transitions.json", tid)
    if ent:
        name, secs = ent.get("xfade") or "cut", secs or ent.get("seconds")
    else:
        name = tid if tid in ("cut", "fade", "wipeleft", "slideup", "circleopen", "dissolve", "fadeblack") or tid in xfade_names() else "fade"
    if name == "cut":
        return "cut", 0.0
    return (name if name in xfade_names() else "fade"), float(secs or DEFAULT_XFADE_SECONDS)


def camera_filters(cam, W: int, H: int, fps: float, dur: float) -> tuple:
    """(resolved id, filters) on frames already scaled to WxH at fps; data/camera.json templates first."""
    if not cam:
        return "none", []
    cid = str(cam.get("id") or "none")
    params = {k: v for k, v in cam.items() if k != "id"}
    ent = C.lookup("camera.json", cid)
    if ent and isinstance(ent.get("ffmpeg"), str):
        defaults = dict(ent.get("defaults") or {})
        p = {**defaults, **{k: v for k, v in params.items() if k in defaults}}
        if "amount" in defaults and "amount" not in params and params.get("scale"):
            p["amount"] = round(float(params["scale"]) - 1.0, 4)
        try:
            f = ent["ffmpeg"].format(W=W, H=H, W2=W * 2, H2=H * 2, fps=f"{fps:g}", frames=max(1, round(dur * fps)), **p)
            return ent["id"], ([] if f.strip() == "null" else [f])
        except (KeyError, IndexError, ValueError):
            pass
    spec = dict(CAMERA.get(cid) or ({"type": "static", "scale": 1.08} if cid != "none" else {"type": "none"}))
    if params.get("scale"):
        spec["scale"] = float(params["scale"])
    t, sc = spec.get("type", "none"), float(spec.get("scale") or 1.0)
    if t == "none" or sc <= 1.0001:
        return cid, []
    if t == "static":
        return cid, [f"scale={round(W * sc / 2) * 2}:{round(H * sc / 2) * 2}:flags=bicubic", f"crop={W}:{H}:(iw-{W})/2:(ih-{H})/2"]
    z = f"(1+{(sc - 1.0) / max(dur, 0.1):.6f}*t)"          # progressive zoom: per-frame scale then a fixed crop
    pan = f"(iw-{W})*min(t/{max(dur, 0.1):.3f}\\,1)" if t == "pan" else f"(iw-{W})/2"
    return cid, [f"scale=w='2*trunc({W}*{z}/2)':h='2*trunc({H}*{z}/2)':eval=frame:flags=bicubic",
                 f"crop={W}:{H}:x='{pan}':y='(ih-{H})/2'"]


def caption_style(style: str, look) -> dict | None:
    if not style or style == "none":
        return None
    base = CAPTIONS.get(style) or CAPTIONS["karaoke"]
    st = {"ass": dict(base["ass"]), "max_words": base["max_words"], "pop": base["pop"], "highlight": base["highlight"]}
    ent = C.lookup("caption_styles.json", style)
    if ent and isinstance(ent.get("ass"), dict):
        st["ass"].update({k: v for k, v in ent["ass"].items() if v is not None})
        st.update({k: ent[k] for k in ("max_words", "pop", "highlight") if ent.get(k) is not None})
    st["style"], st["max_words"] = style, max(1, int(st["max_words"] or 1))
    lc = (look or {}).get("captions") or {}
    if lc.get("font"):
        st["ass"]["Fontname"] = lc["font"]
    if lc.get("position") in ("center", "middle"):
        st["ass"]["Alignment"], st["ass"]["MarginV"] = 5, 0
    elif lc.get("position") in ("lower", "bottom"):
        st["ass"]["Alignment"], st["ass"]["MarginV"] = 2, st["ass"].get("MarginV") or 300
    fb = C.data("caption_styles.json").get("font_fallback") or FONT_FALLBACK
    st["fallback"] = [st["ass"]["Fontname"]] + [f for f in fb if f != st["ass"]["Fontname"]] + ["DejaVu Sans"]
    return st


def safe_area(W: int, H: int) -> tuple:
    """(aspect key, {bottom, top}) from caption_styles.json safe_area; nearest W/H wins."""
    table = {k: v for k, v in (C.data("caption_styles.json").get("safe_area") or SAFE_AREA).items() if isinstance(v, dict)} or SAFE_AREA
    ratio = lambda k: float(k.split(":")[0]) / float(k.split(":")[1])  # noqa: E731
    key = min(table, key=lambda k: abs(math.log(ratio(k)) - math.log(W / max(1, H))))
    return key, table[key]


def caption_margin_v(st: dict, W: int, H: int, min_bottom_frac=None) -> int:
    """MarginV in output pixels; bottom-aligned captions are lifted out of the platform UI band."""
    a = st["ass"]
    mv, al, sa = float(a.get("MarginV", 0)) * H / 1920.0, int(a.get("Alignment", 2)), safe_area(W, H)[1]
    if al in (1, 2, 3):
        mv = max(mv, float(sa.get("bottom", 0)) * H, float(min_bottom_frac or 0) * H)
    elif al in (7, 8, 9):
        mv = max(mv, float(sa.get("top", 0)) * H)
    return int(math.ceil(mv))


def find_font(families: list) -> tuple:
    """First family found in the repo font folders (-> libass fontsdir) or installed (fc-list)."""
    installed = ""
    if shutil.which("fc-list"):
        installed = subprocess.run(["fc-list", ":", "family"], capture_output=True, timeout=30, **C.TEXT).stdout.lower()
    for fam in families:
        key = fam.lower().replace(" ", "")
        for d in C.FONT_DIRS:
            if d.is_dir() and any(p.name.lower().replace(" ", "").startswith(key) for p in d.glob("*.[ot]tf")):
                return fam, d
        if fam.lower() in installed:
            return fam, None
    return "DejaVu Sans", None


def ff_quote(rel: str) -> str:
    """Quote a *relative* filename for a filtergraph option (absolute Windows paths break the parser)."""
    return "'" + str(rel).replace("\\", "/").replace("'", "") + "'"


def stage_fonts(font_dir, family: str, rdir: Path):
    """Copy the caption family's font files to render/_fonts so libass gets a relative fontsdir."""
    if not font_dir or not Path(font_dir).is_dir():
        return None
    key = family.lower().replace(" ", "")
    files = [p for p in Path(font_dir).glob("*.[ot]tf") if p.name.lower().replace(" ", "").startswith(key)]
    if not files:
        return None
    (rdir / "_fonts").mkdir(parents=True, exist_ok=True)
    for f in files:
        t = rdir / "_fonts" / f.name
        if not t.exists() or t.stat().st_size != f.stat().st_size:
            shutil.copyfile(f, t)
    return "_fonts"


def ratio_size(ratio: str, base_w: int, base_h: int) -> tuple:
    if ratio in C.ASPECTS:
        w, h = C.ASPECTS[ratio]
    else:
        a, b = (float(x) for x in re.split(r"[:x]", ratio))
        long = max(base_w, base_h)
        w, h = (long, long * b / a) if a >= b else (long * a / b, long)
    return int(w) // 2 * 2, int(h) // 2 * 2


def atempo_chain(speed: float) -> list:
    out, s = [], speed
    while s > 2.0:
        out, s = out + ["atempo=2.0"], s / 2.0
    while s < 0.5:
        out, s = out + ["atempo=0.5"], s / 0.5
    return out + ([f"atempo={s:.6f}"] if abs(s - 1.0) > 1e-6 else [])


def resolve_media(job: Path, raw):
    if not raw:
        return None
    p = Path(raw).expanduser()
    return p if p.is_absolute() else job / p


def face_center(ev: dict, clip: dict) -> tuple:
    """Crop anchor: event.crop_center, else the shot's face_center / faces_box, else the frame centre."""
    if isinstance(ev.get("crop_center"), (list, tuple)) and len(ev["crop_center"]) == 2:
        return float(ev["crop_center"][0]), float(ev["crop_center"][1])
    for sh in clip.get("shots") or []:
        if sh.get("id") == ev.get("shot") or (sh.get("start", 0) <= ev["src_in"] < sh.get("end", -1)):
            fc, fb = sh.get("face_center"), sh.get("faces_box")
            if isinstance(fc, (list, tuple)) and len(fc) == 2:
                return float(fc[0]), float(fc[1])
            if isinstance(fb, (list, tuple)) and len(fb) == 4:
                return float(fb[0]) + float(fb[2]) / 2, float(fb[1]) + float(fb[3]) / 2
    return 0.5, 0.5


def event_grade(ev: dict):
    g = ev.get("grade")
    return (g.get("id") if isinstance(g, dict) else g) or None


# ----------------------------------------------------------------------------- plan
def plan_timeline(edl: dict, fps: float) -> list:
    """Every event in whole frames around its reflowed rec_in; a transition overlaps by the frames between the
    previous end and that start. Cuts are contiguous, so frame drift never builds up."""
    plan, prev_end = [], 0
    for i, ev in enumerate(E.reflow(copy.deepcopy(edl))["events"]):
        rec_in = float(ev["rec_in"])
        a_f = round(rec_in * fps)
        n = max(2, round((rec_in + E.event_seconds(ev)) * fps) - a_f)
        tname, td_f = "cut", 0
        if i and E.overlap(ev) > 0:
            td_f = min(prev_end - a_f, n - 1, plan[-1]["frames"] - 1)
            if td_f >= 1:
                tname = transition_name(ev.get("transition_in"))[0]
                tname = "fade" if tname == "cut" else tname
            else:
                td_f = 0
        start_f = prev_end - td_f
        plan.append({"ev": ev, "i": i, "speed": float(ev.get("speed") or 1.0), "frames": n, "dur": n / fps,
                     "start": start_f / fps, "start_f": start_f, "end_f": start_f + n, "trans": tname,
                     "td": td_f / fps, "td_f": td_f})
        prev_end = start_f + n
    return plan


def clamp_to_media(job: Path, edl: dict, clips: dict) -> tuple:
    """Copy of edl whose src ranges stay inside each clip's real duration (clamped, or the event dropped)."""
    edl, fps = copy.deepcopy(edl), float(edl.get("fps") or 30)
    warnings, keep, durs = [], [], {}
    for ev in edl["events"]:
        cid = ev["clip"]
        if cid not in durs:
            d = (clips.get(cid) or {}).get("duration")
            src = resolve_media(job, ev.get("path") or (clips.get(cid) or {}).get("path"))
            if not d and src and src.is_file():
                try:
                    d = float(probe(src).get("format", {}).get("duration") or 0) or None
                except (ValueError, OSError):
                    d = None
            durs[cid] = float(d) if d else None
        d = durs[cid]
        if d and float(ev["src_out"]) > d + 1e-3:
            if float(ev["src_in"]) >= d - 2 / fps:
                warnings.append(f"{ev['id']}: src {ev['src_in']}–{ev['src_out']}s is past the end of {cid} ({d:.3f}s): event dropped")
                continue
            warnings.append(f"{ev['id']}: src_out {ev['src_out']}s > {cid} duration {d:.3f}s: clamped to {d:.3f}s")
            ev["src_out"] = round(d, 3)
        keep.append(ev)
    if not keep:
        raise RuntimeError("no event left inside its media after clamping src ranges to clip durations")
    edl["events"] = keep
    return edl, warnings


# ----------------------------------------------------------------------------- captions
def remap_words(plan: list, clips: dict) -> list:
    """Source-time words -> output-timeline words (only words inside each event's window, no overlaps)."""
    out = []
    for p in plan:
        ev, clip = p["ev"], clips.get(p["ev"]["clip"]) or {}
        if ev.get("mute"):                     # muted b-roll is not heard, so no captions
            continue
        a, b, s = float(ev["src_in"]), float(ev["src_out"]), p["speed"]
        lo, hi = p["start"] + (p["td"] / 2 if p["td"] else 0), p["start"] + p["dur"]
        for w in clip.get("words") or []:
            text = E.word_text(w).strip()
            ws, we = float(w["start"]), float(w["end"])
            if not text or we <= a or ws >= b or not (a <= (max(ws, a) + min(we, b)) / 2 <= b):
                continue
            t0, t1 = max(lo, p["start"] + (max(ws, a) - a) / s), min(hi, p["start"] + (min(we, b) - a) / s)
            if t1 - t0 >= 0.04:
                out.append({"word": text, "start": round(t0, 3), "end": round(t1, 3), "event": ev["id"]})
    out.sort(key=lambda w: w["start"])
    for i in range(1, len(out)):
        if out[i]["start"] < out[i - 1]["end"]:
            out[i - 1]["end"] = out[i]["start"]
    return [w for w in out if w["end"] - w["start"] >= 0.03]


def phrases(words: list, max_words: int, pause: float = 0.45, max_chars: int = 32) -> list:
    out, cur = [], []
    for w in words:
        if cur and (w["start"] - cur[-1]["end"] > pause or len(cur) >= max_words or w.get("event") != cur[-1].get("event")
                    or len(" ".join(x["word"] for x in cur)) + len(w["word"]) + 1 > max_chars):
            out, cur = out + [cur], []
        cur.append(w)
    return out + ([cur] if cur else [])


def _ts(t: float, ass: bool) -> str:
    unit = 100 if ass else 1000
    n = max(0, round(t * unit))
    h, n = divmod(n, 3600 * unit)
    m, n = divmod(n, 60 * unit)
    s, n = divmod(n, unit)
    return f"{h}:{m:02d}:{s:02d}.{n:02d}" if ass else f"{h:02d}:{m:02d}:{s:02d},{n:03d}"


def write_srt(path: Path, words: list) -> int:
    ph = phrases(words, 7, max_chars=42)
    path.write_text("\n".join(f"{i}\n{_ts(p[0]['start'], False)} --> {_ts(p[-1]['end'], False)}\n{' '.join(w['word'] for w in p)}\n"
                              for i, p in enumerate(ph, 1)), encoding="utf-8")
    return len(ph)


def write_ass(path: Path, words: list, st: dict, W: int, H: int) -> int:
    """RTL-safe ASS: one Dialogue per word showing the whole phrase with the spoken word recoloured (+ a pop).
    No \\k sweep (left-to-right, breaks on Arabic); Encoding -1 lets libass (fribidi + HarfBuzz) pick direction."""
    a, k = st["ass"], min(W, H) / 1080.0
    marg_lr = round(W * 0.07)
    head = ("[Script Info]\nScriptType: v4.00+\nWrapStyle: 0\nScaledBorderAndShadow: yes\n"
            f"PlayResX: {W}\nPlayResY: {H}\nYCbCr Matrix: TV.709\n\n"
            "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
            "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
            "MarginR, MarginV, Encoding\n"
            f"Style: Cap,{st['font']},{max(14, round(float(a['Fontsize']) * k))},{a['PrimaryColour']},{a['SecondaryColour']},"
            f"{a['OutlineColour']},{a['BackColour']},{-1 if int(a.get('Bold', 0)) else 0},0,0,0,100,100,0,0,{a.get('BorderStyle', 1)},"
            f"{round(float(a.get('Outline', 4)) * k, 1)},{round(float(a.get('Shadow', 0)) * k, 1)},{a.get('Alignment', 2)},"
            f"{marg_lr},{marg_lr},{caption_margin_v(st, W, H, st.get('min_bottom_frac'))},{a.get('Encoding', -1)}\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    txt = lambda s: s.replace("\\", "⧵").replace("{", "(").replace("}", ")").replace("\n", " ")  # noqa: E731
    hl = st.get("highlight") not in (None, "none", False) and a["SecondaryColour"] != a["PrimaryColour"]
    tag = f"\\c{a['SecondaryColour'].rstrip('&')}&" + (f"\\fscx{st['pop']}\\fscy{st['pop']}" if int(st.get("pop") or 100) != 100 else "")
    lines = []
    for ph in phrases(words, st["max_words"]):
        if not hl:
            lines.append(f"Dialogue: 0,{_ts(ph[0]['start'], True)},{_ts(ph[-1]['end'], True)},Cap,,0,0,0,," + " ".join(txt(x["word"]) for x in ph))
            continue
        for i, w in enumerate(ph):
            end = ph[i + 1]["start"] if i + 1 < len(ph) else w["end"]
            body = " ".join("{" + tag + "}" + txt(x["word"]) + "{\\r}" if j == i else txt(x["word"]) for j, x in enumerate(ph))
            lines.append(f"Dialogue: 0,{_ts(w['start'], True)},{_ts(end, True)},Cap,,0,0,0,," + body)
    path.write_text(head + "\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)


# ----------------------------------------------------------------------------- graph
def build_graph(job: Path, plan: list, clips: dict, W: int, H: int, fps: float, grade, ass, font_dir, music,
                global_grade_id=None) -> tuple:
    """inputs + filtergraph. Every event is its own `-ss in -t len` input, so events of one source in any order never
    share a decoder and nothing past the event is decoded."""
    inputs, has_audio = [], {}
    for p in plan:
        cid = p["ev"]["clip"]
        src = resolve_media(job, p["ev"].get("path") or (clips.get(cid) or {}).get("path"))
        if not src or not src.is_file():
            raise FileNotFoundError(f"event {p['ev']['id']}: media for clip {cid} not found ({src})")
        if cid not in has_audio:
            c = clips.get(cid) or {}
            has_audio[cid] = bool(c["has_audio"]) if "has_audio" in c else any(
                s.get("codec_type") == "audio" for s in probe(src)["streams"])
        a, b = float(p["ev"]["src_in"]), float(p["ev"]["src_out"])
        inputs += ["-ss", f"{a:.4f}", "-t", f"{b - a + 0.25:.4f}", "-i", str(src.resolve())]
    per_event_grade = any(event_grade(p["ev"]) for p in plan)
    F, g = f"{fps:g}", []
    for i, p in enumerate(plan):
        ev, k = p["ev"], p["i"]
        a, b, s = float(ev["src_in"]), float(ev["src_out"]), p["speed"]
        cx, cy = (min(max(v, 0.0), 1.0) for v in face_center(ev, clips.get(ev["clip"]) or {}))
        gf = None
        if per_event_grade:
            gid = event_grade(ev) or global_grade_id
            gf = grade_filter(gid) if gid else grade
        vf = ["setpts=PTS-STARTPTS", f"trim=end={b - a:.4f}", f"setpts=(PTS-STARTPTS)/{s:.6f}",
              f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=bicubic",
              f"crop={W}:{H}:x='clip(iw*{cx:.4f}-{W / 2:g},0,iw-{W})':y='clip(ih*{cy:.4f}-{H / 2:g},0,ih-{H})'", "setsar=1",
              f"fps={F}", "tpad=stop_mode=clone:stop_duration=2", f"trim=end_frame={p['frames']}", "setpts=PTS-STARTPTS",
              *camera_filters(ev.get("camera"), W, H, fps, p["dur"])[1], *([gf] if gf else []),
              f"fps={F}", "setsar=1", "format=yuv420p", "settb=AVTB"]
        g.append(f"[{i}:v]" + ",".join(vf) + f"[v{k}]")
        d = f"{p['dur']:.6f}"
        if has_audio[ev["clip"]] and not ev.get("mute"):
            af = ["asetpts=PTS-STARTPTS", f"atrim=end={b - a:.4f}", "asetpts=PTS-STARTPTS", *atempo_chain(s), "aresample=48000",
                  "aformat=sample_fmts=fltp:channel_layouts=stereo", "apad", f"atrim=end={d}", "asetpts=PTS-STARTPTS",
                  f"afade=t=in:d={CUT_DECLICK}", f"afade=t=out:st={p['dur'] - CUT_DECLICK:.6f}:d={CUT_DECLICK}"]
            g.append(f"[{i}:a]" + ",".join(af) + f"[a{k}]")
        else:
            g.append(f"anullsrc=r=48000:cl=stereo,atrim=end={d},aformat=sample_fmts=fltp[a{k}]")
    vacc, aacc = "v0", "a0"
    for p in plan[1:]:
        k = p["i"]
        if p["trans"] == "cut":
            g += [f"[{vacc}][v{k}]concat=n=2:v=1:a=0[vj{k}]", f"[{aacc}][a{k}]concat=n=2:v=0:a=1[aj{k}]"]
        else:
            g += [f"[{vacc}][v{k}]xfade=transition={p['trans']}:duration={p['td']:.6f}:offset={p['start']:.6f}[vj{k}]",
                  f"[{aacc}][a{k}]acrossfade=d={p['td']:.6f}:c1=tri:c2=tri[aj{k}]"]
        vacc, aacc = f"vj{k}", f"aj{k}"
    L = plan[-1]["end_f"] / fps
    post = ([grade] if grade and not per_event_grade else [])
    if ass:
        post.append(f"ass=filename={ff_quote(ass)}" + (f":fontsdir={ff_quote(font_dir)}" if font_dir else ""))
    g.append(f"[{vacc}]" + ",".join(post + ["format=yuv420p"]) + "[vout]")
    any_voice = any(has_audio[p["ev"]["clip"]] and not p["ev"].get("mute") for p in plan)
    if music:
        inputs += ["-stream_loop", "-1", "-i", str(Path(music["path"]).resolve())]
        duck = abs(float(music.get("duck_under_speech_db", -10)))
        g.append(f"[{len(plan)}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,atrim=end={L:.6f},"
                 f"asetpts=PTS-STARTPTS,volume={float(music.get('gain_db', -18))}dB,afade=t=in:d=0.5,"
                 f"afade=t=out:st={max(0.0, L - 1.0):.3f}:d=1.0[mus]")
        if any_voice and duck > 0:
            g += [f"[{aacc}]asplit=2[vo][sc]",
                  f"[mus][sc]sidechaincompress=threshold=0.03:ratio={min(20.0, max(2.0, 10 ** (duck / 20) * 2)):.2f}:"
                  "attack=15:release=350:makeup=1[duck]",
                  f"[vo][duck]amix=inputs=2:duration=first:normalize=0,apad,atrim=end={L:.6f}[aout]"]
        else:
            g.append(f"[{aacc}][mus]amix=inputs=2:duration=first:normalize=0,apad,atrim=end={L:.6f}[aout]")
    else:
        g.append(f"[{aacc}]apad,atrim=end={L:.6f}[aout]")
    return inputs, ";\n".join(g), L


# ----------------------------------------------------------------------------- loudness
def measure_true_peak(job: Path, media: Path):
    res = C.run(job, STATION, "ffmpeg.ebur128-truepeak", ["ffmpeg", "-hide_banner", "-nostats", "-i", media, "-map", "0:a:0",
                "-af", "ebur128=peak=true", "-f", "null", "-"], check=False)
    m = re.findall(r"Peak:\s+(-?[\d.]+|-inf)\s+dBFS", res.stderr)
    return None if not m else float("-inf") if m[-1] == "-inf" else float(m[-1])


def loudnorm(job: Path, master: Path, out: Path, target: float, tp: float, limiter_tp=None) -> dict:
    """Two-pass loudnorm, then a 4x-oversampled limiter; re-encoded once more if the AAC still peaks too high."""
    ceiling = min(TP_CEILING, float(limiter_tp)) if limiter_tp is not None else TP_CEILING
    tp, lim_db = min(tp, ceiling - 0.5), ceiling - 0.8          # head-room for AAC inter-sample overshoot
    res = C.run(job, STATION, "ffmpeg.loudnorm-measure", ["ffmpeg", "-hide_banner", "-nostats", "-i", master, "-map", "0:a:0",
                "-af", f"loudnorm=I={target}:TP={tp}:LRA=11:print_format=json", "-f", "null", "-"])
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", res.stderr, re.S)
    meas = json.loads(m.group(0)) if m else {}
    norm = f"loudnorm=I={target}:TP={tp}:LRA=11"
    if meas and all(math.isfinite(float(meas.get(k, "nan"))) for k in ("input_i", "input_tp", "input_lra", "input_thresh")):
        norm += (f":measured_I={meas['input_i']}:measured_TP={meas['input_tp']}:measured_LRA={meas['input_lra']}"
                 f":measured_thresh={meas['input_thresh']}:offset={meas.get('target_offset', 0)}:linear=true")
    vdur = next((float(s["duration"]) for s in probe(master)["streams"] if s["codec_type"] == "video" and s.get("duration")), None)
    if vdur is None:   # mkv keeps the stream length in tags.DURATION
        out_ = subprocess.run([exe("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries", "stream_tags=DURATION",
                               "-of", "csv=p=0", str(master)], capture_output=True, **C.TEXT).stdout.strip()
        try:
            hh, mm, ss = out_.split(":")
            vdur = int(hh) * 3600 + int(mm) * 60 + float(ss)
        except ValueError:
            vdur = None

    def apply(extra_db: float = 0.0):
        chain = [norm, *([f"volume={extra_db:.2f}dB"] if extra_db else []), "aresample=192000",
                 f"alimiter=limit={10 ** (lim_db / 20):.5f}:attack=1:release=60:level=disabled", "aresample=48000"]
        if vdur:   # keep the audio exactly as long as the picture
            chain.append(f"atrim=end={max(0.0, vdur - 1024 / 48000):.6f}")
        C.run(job, STATION, "ffmpeg.loudnorm-apply", ["ffmpeg", "-y", "-hide_banner", "-v", "error", "-i", master, "-map", "0:v:0",
              "-map", "0:a:0", "-c:v", "copy", "-af", ",".join(chain), "-c:a", "aac", "-b:a", "320k", "-ar", "48000",
              "-movflags", "+faststart", out], out=out)
        return measure_true_peak(job, out)
    peak, passes = apply(), 1
    if peak is not None and math.isfinite(peak) and peak > ceiling - 0.1:
        peak, passes = apply(-(peak - ceiling + 0.4)), 2
    return {**meas, "limiter": {"ceiling_dbtp": ceiling, "limit_db": round(lim_db, 2), "loudnorm_tp": tp,
                                "output_true_peak": peak, "passes": passes}}


# ----------------------------------------------------------------------------- one render
def render_one(job: Path, edl: dict, analysis: dict, look, W: int, H: int, out: Path, preview: bool, fast: bool, tag: str = "") -> dict:
    fps = float(edl.get("fps") or 30)
    clips = E.clip_index(analysis)
    plan, rdir = plan_timeline(edl, fps), job / "render"
    words = remap_words(plan, clips)
    cap = edl.get("captions") or {}
    st = caption_style(cap.get("style") or ((look or {}).get("captions") or {}).get("style") or "karaoke", look) \
        if cap.get("enabled", True) else None
    ass, font_dir, safe = None, None, None
    if st:
        st["min_bottom_frac"] = cap.get("min_bottom_frac")        # set by apply_review on a safe-area fail
        if words:
            st["font"], font_dir = find_font(st["fallback"])
            ass = rdir / f"captions{tag}.ass"
            write_ass(ass, words, st, W, H)
        akey, sa = safe_area(W, H)
        mv = caption_margin_v(st, W, H, st.get("min_bottom_frac"))
        safe = {"aspect": akey, "bottom_frac": sa.get("bottom"), "alignment": int(st["ass"].get("Alignment", 2)),
                "margin_v": mv, "margin_v_frac": round(mv / H, 4)}
    fonts_rel = stage_fonts(font_dir, st["font"], rdir) if (st and ass) else None
    gid = (edl.get("grade") or {}).get("id") or ((look or {}).get("grade") or {}).get("id")
    gf = grade_filter(gid)
    mus, music, warnings = (edl.get("audio") or {}).get("music") or {}, None, []
    if mus.get("path"):
        mp = resolve_media(job, mus["path"])
        if mp and mp.is_file():
            music = {**mus, "path": mp}
        else:
            warnings.append(f"music bed not found: {mus['path']}")
    inputs, graph, L = build_graph(job, plan, clips, W, H, fps, gf, ass.name if ass else None, fonts_rel, music, gid)
    gfile = rdir / f"graph{tag}.txt"
    gfile.write_text(graph, encoding="utf-8")
    master = rdir / f"_master{tag}.mkv"
    # owner standard (ROADMAP T14): H.264 High CRF 17 preset slow, BT.709 tagged; drafts stay fast
    venc = (["-c:v", "libx264", "-preset", "ultrafast", "-crf", "30"] if preview else
            ["-c:v", "libx264", "-preset", "veryfast" if fast else "slow", "-crf", "20" if fast else "17",
             *([] if fast else ["-profile:v", "high"])]) + BT709
    C.run(job, STATION, "ffmpeg.render", ["ffmpeg", "-y", "-hide_banner", "-v", "error", *inputs, graph_file_option(),
          gfile.name, "-map", "[vout]", "-map", "[aout]", *venc, "-pix_fmt", "yuv420p", "-r", f"{fps:g}", "-c:a", "pcm_s16le",
          "-ar", "48000", master.name], out=master, timeout=3600, cwd=rdir)
    audio = edl.get("audio") or {}
    meas = loudnorm(job, master, out, float(audio.get("target_lufs", -14)), TP_INTERNAL, audio.get("limiter_tp"))
    master.unlink(missing_ok=True)
    return {"out": out, "duration": round(L, 3), "words": words, "ass": ass, "font_dir": str(font_dir) if font_dir else None,
            "font": st["font"] if st and ass else None, "grade": gid, "grade_filter": gf, "music": bool(music),
            "loudnorm_measured": meas, "plan": plan, "warnings": warnings, "fps": fps, "safe": safe}


# ----------------------------------------------------------------------------- verify + export

def verify(job: Path, video: Path, W: int, H: int, fps: float, duration: float, lufs: float) -> dict:
    rep = qc.verify(video, (W, H), fps, duration, lufs)
    vj = C.save(video.with_suffix(".verify.json"), rep)
    lu = rep.get("loudness") or {}
    C.receipt(job, STATION, "verify_video", ["qc.verify", video], 0 if rep["pass"] else 1, 0.0)
    return {"tool": "verify_video", "pass": rep["pass"], "rc": 0 if rep["pass"] else 1, "lufs": lu.get("integrated_lufs"),
            "true_peak": lu.get("true_peak_dbfs"), "duration": rep.get("duration_s"), "width": rep.get("width"),
            "height": rep.get("height"), "failed": [c["check"] for c in rep["checks"] if not c["pass"]],
            "report": str(vj.relative_to(job))}


def _absolute(job: Path, edl: dict, analysis: dict) -> tuple:
    edl, analysis = copy.deepcopy(edl), copy.deepcopy(analysis or {"clips": []})
    for c in analysis.get("clips", []):
        if c.get("path"):
            c["path"] = str(resolve_media(job, c["path"]).resolve())
    mus = (edl.get("audio") or {}).get("music") or {}
    if mus.get("path"):
        mp = resolve_media(job, mus["path"])
        mus["path"] = str(mp.resolve()) if mp and mp.is_file() else None
    return edl, analysis


def export_project(job: Path, edl: dict, analysis: dict, fps: float) -> dict:
    """render/nle_timeline.json + nle_words.json; with DRAGON_NLE_EXPORT (nle_export.py) also FCPXML/Premiere/OTIO/CapCut."""
    rdir = job / "render"
    nle = E.to_nle(*_absolute(job, edl, analysis), rdir, name="project")
    out = {"files": [str(Path(nle[k]).relative_to(job)) for k in ("project", "words")], "converter": "edl.to_nle",
           "warnings": [f"speed {p['speed']}x on {p['ev']['id']} not carried by the NLE export"
                        for p in plan_timeline(edl, fps) if abs(p["speed"] - 1) > 1e-6]}
    script = Path(os.environ.get("DRAGON_NLE_EXPORT", ""))
    if not script.is_file():
        return {**out, "fcpxml": None, "note": "no NLE exporter configured (DRAGON_NLE_EXPORT): timeline JSON only"}
    formats = "fcpxml,xmeml,edl,otio,capcut" + (",srt" if nle["has_words"] else "")
    argv = [sys.executable, str(script), "export", "--project", nle["project"], "--out", str(rdir / "nle"), "--formats", formats,
            "--name", "project", "--force"] + (["--words", nle["words"]] if nle["has_words"] else [])
    res = C.run(job, STATION, "nle_export", argv, check=False, owner_media=False)
    fx = rdir / "nle" / "project.fcpxml"
    if res.returncode != 0 or not fx.exists():
        return {**out, "error": (res.stdout or res.stderr)[-400:]}
    shutil.copyfile(fx, rdir / "project.fcpxml")
    return {**out, "fcpxml": "render/project.fcpxml",
            "files": out["files"] + sorted(str(p.relative_to(job)) for p in (rdir / "nle").iterdir() if p.is_file())}


# ----------------------------------------------------------------------------- station
def render(job, extra_ratios=(), preview: bool = False, fast: bool = False, do_verify: bool = True, do_export: bool = True) -> dict:
    job = Path(job).resolve()
    edl_in = C.read(job, "edl")
    analysis = C.read_opt(job, "analysis", {"clips": []})
    look = C.read_opt(job, "look")
    rdir = job / "render"
    rdir.mkdir(parents=True, exist_ok=True)
    W, H = int(edl_in["width"]), int(edl_in["height"])
    if preview:
        W, H = max(2, W // 3 // 2 * 2), max(2, H // 3 // 2 * 2)
    main_out = rdir / ("preview.mp4" if preview else "final.mp4")
    edl, warnings = clamp_to_media(job, edl_in, E.clip_index(analysis))
    clamped = bool(warnings)
    r = render_one(job, edl, analysis, look, W, H, main_out, preview, fast)
    fps = r["fps"]
    warnings += r["warnings"]
    C.save(rdir / "words.json", {"words": r["words"]}, indent=1)
    srt = rdir / "captions.srt"
    n_srt = write_srt(srt, r["words"]) if r["words"] else 0
    if not r["words"]:
        srt.write_text("", encoding="utf-8")
        warnings.append("no words in analysis: captions.srt is empty and nothing was burned")
    if abs(r["duration"] - float(edl_in["duration"])) > 0.3:
        warnings.append(f"timeline is {r['duration']}s but edl.duration says {edl_in['duration']}s "
                        + ("(src ranges clamped to the media)" if clamped else "(edl.json was not reflowed: run edl.reflow)"))
    target = float((edl.get("audio") or {}).get("target_lufs", -14))
    extra = []
    for ratio in (x.strip() for x in extra_ratios if x.strip()):
        ew, eh = ratio_size(ratio, int(edl["width"]), int(edl["height"]))
        if preview:
            ew, eh = max(2, ew // 3 // 2 * 2), max(2, eh // 3 // 2 * 2)
        tag = "_" + ratio.replace(":", "x")
        o = rdir / f"{'preview' if preview else 'final'}{tag}.mp4"
        render_one(job, edl, analysis, look, ew, eh, o, preview, fast, tag)
        extra.append({"ratio": ratio, "path": str(o.relative_to(job)), "width": ew, "height": eh})
    v = verify(job, main_out, W, H, fps, r["duration"], target) if do_verify else {"tool": "verify_video", "pass": None, "skipped": True}
    for e in extra:
        e["verify"] = verify(job, job / e["path"], e["width"], e["height"], fps, r["duration"], target) if do_verify else None
    proj = export_project(job, edl, analysis, fps) if do_export else {"skipped": True}
    if proj.get("error"):
        warnings.append(f"nle export failed: {proj['error']}")
    warnings += proj.get("warnings", [])
    lim = r["loudnorm_measured"].get("limiter") or {}
    doc = C.new("render", final=str(main_out.relative_to(job)), extra=[e["path"] for e in extra], extra_detail=extra, preview=preview,
                captions=str(srt.relative_to(job)), captions_ass=str(r["ass"].relative_to(job)) if r["ass"] else None,
                caption_cues=n_srt, caption_font=r["font"], font_dir=r["font_dir"], caption_safe_area=r["safe"],
                project=proj.get("fcpxml"), project_files=proj.get("files", []), project_converter=proj.get("converter"),
                width=W, height=H, fps=fps, duration=r["duration"], edl_duration=edl_in["duration"],
                grade={"id": r["grade"], "filter": r["grade_filter"],
                       "per_event": {p["ev"]["id"]: event_grade(p["ev"]) for p in r["plan"] if event_grade(p["ev"])}},
                music=r["music"], muted=[p["ev"]["id"] for p in r["plan"] if p["ev"].get("mute")],
                loudness={"target_lufs": target, "true_peak_ceiling": lim.get("ceiling_dbtp", TP_CEILING),
                          "internal_tp": lim.get("loudnorm_tp", TP_INTERNAL), "limiter_tp": (edl.get("audio") or {}).get("limiter_tp"),
                          "measured_before": r["loudnorm_measured"]},
                events=[{"id": p["ev"]["id"], "start": round(p["start"], 3), "dur": round(p["dur"], 3), "transition": p["trans"],
                         "td": round(p["td"], 3), "camera": camera_filters(p["ev"].get("camera"), W, H, fps, p["dur"])[0]}
                        for p in r["plan"]],
                # exact output span of every event in final.mp4 (frame-snapped, xfade overlaps included)
                events_out=[{"id": p["ev"]["id"], "out_in": round(p["start_f"] / fps, 3), "out_out": round(p["end_f"] / fps, 3)}
                            for p in r["plan"]],
                verify=v, warnings=warnings, graph="render/graph.txt")
    C.write(job, "render", doc)
    return doc


def main(argv=None) -> int:
    C.utf8_stdio()
    ap = argparse.ArgumentParser(prog="dragon_montage render", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render")
    r.add_argument("--job", required=True)
    r.add_argument("--extra-ratios", default="", help="comma list, e.g. 1:1,16:9")
    r.add_argument("--preview", action="store_true", help="fast low-res render (render/preview.mp4)")
    r.add_argument("--fast", action="store_true")
    r.add_argument("--no-verify", action="store_true")
    r.add_argument("--no-export", action="store_true")
    a = ap.parse_args(argv)
    try:
        doc = render(a.job, a.extra_ratios.split(","), a.preview, a.fast, not a.no_verify, not a.no_export)
    except (FileNotFoundError, C.ContractError, RuntimeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)[-1200:]}, ensure_ascii=False))
        return 2
    print(json.dumps({"status": "rendered", "final": doc["final"], "duration": doc["duration"],
                      "verify_pass": doc["verify"].get("pass"), "lufs": doc["verify"].get("lufs"), "extra": doc["extra"],
                      "project": doc["project"], "warnings": doc["warnings"]}, ensure_ascii=False))
    return 0
