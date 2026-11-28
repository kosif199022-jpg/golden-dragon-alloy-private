"""Red Rose V56 — reel.craft: native short-reel craft checks and a gated credit pass.

Distilled (re-written, nothing imported or copied) from what the Golden Dragon / KOSIF sessions of
2026-11-20 learned while integrating Maven Toon and merging the dragon branches:

  script_check      read   micro-fable script check: flat hook, escalation, turn, short payoff,
                           length for the given seconds, one picture per line, one dialect only
  story_plan        read   light as act structure + a camera that never stops (frame-exact plan)
  tempo_steadiness  read   is there a steady beat at all? a grid that onsets hit far above chance,
                           else NO bpm (never invent a tempo from unrelated impacts)
  delivery_gate     read   the owner's export standard on a real file (ffprobe + MP4 box walk)
  credit_overlay    write  owner credit for the whole film + end card in the last seconds, drawn by
                           libass (Arabic shaped and joined), audio stream-copied byte for byte,
                           same frame count, staged then verified before the output appears

Only the stdlib plus the ffmpeg/ffprobe programs. Every op returns `limits`: these are measurements
and checks, not taste. A passing script_check is not a good story; a passing gate is not a good film.
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

OPS = ("script_check", "story_plan", "tempo_steadiness", "delivery_gate", "credit_overlay")
EFFECTS = {"script_check": "read", "story_plan": "read", "tempo_steadiness": "read",
           "delivery_gate": "read", "credit_overlay": "write"}

# ----------------------------------------------------------------------------- helpers

def _no_extra(params: dict, allowed: set, required=()):
    if not isinstance(params, dict):
        raise ValueError("params must be an object")
    extra = set(params) - set(allowed)
    if extra:
        raise ValueError(f"unknown params: {sorted(extra)}")
    missing = [k for k in required if k not in params]
    if missing:
        raise ValueError(f"missing params: {missing}")


def _num(v, lo, hi, name):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not lo <= v <= hi:
        raise ValueError(f"{name} must be a number in [{lo}, {hi}]")
    return float(v)


def _words(line: str) -> list[str]:
    return [w for w in re.split(r"\s+", re.sub(r"[^\w؀-ۿ\s]", " ", line)) if w]


# ----------------------------------------------------------------------------- script_check

BAD_OPENERS = ("النهارده هحكي", "النهاردة هحكي", "اليوم راح", "اليوم سأحكي", "في الفيديو ده", "فى الفيديو ده",
               "في هذا الفيديو", "استنى للآخر", "استنوا للآخر", "انتظر للنهاية", "أهلا", "اهلا", "السلام عليكم",
               "مرحبا", "هل تعلم", "in this video", "wait till the end", "hey guys", "hello")
TURNS = {"eg": ("تعرف ليه", "تعرفي ليه", "عارف ليه", "والسبب", "والسر", "أصل ", "اصل ", "الحكاية إن", "الحكاية ان"),
         "iq": ("تدري ليش", "تدرين ليش", "والسبب", "والسر"),
         "fusha": ("والسبب", "والسر", "ذلك لأن", "لماذا؟"),
         "en": ("you see", "here's why", "the reason", "that's because")}
ESCALATION = ("بس", "فـ", "وبعدين", "وفجأة", "وفي يوم", "وفى يوم", "ولما", "هسه", "ثم", "لكن", "but", "then", "so")
MARKERS = {"eg": ("إزاي", "ازاي", "ليه", "دلوقتي", "عشان", "النهارده", "بتاع", "مش ", "كده"),
           "iq": ("هسه", "شلون", "ماكو", "اكو ", "كلش", "هواية", "لعد", "چ", "گ", "باچر", "ليش"),
           "fusha": ("لكنّ", "لذلك", "إنّ", "حيث إن", "في تلك الليلة", "سوف", "لماذا")}
DEFAULT_RATE = {"eg": 2.1, "iq": 2.1, "fusha": 2.0, "en": 2.3, "any": 2.1}


def script_check(params: dict) -> dict:
    _no_extra(params, {"text", "seconds", "register", "words_per_second", "voice_recorded"}, ("text", "seconds"))
    text = params["text"]
    if not isinstance(text, str) or not text.strip() or len(text) > 20000:
        raise ValueError("text must be a non-empty string (one sentence per line)")
    seconds = _num(params["seconds"], 3, 600, "seconds")
    register = params.get("register", "eg")
    if register not in ("eg", "iq", "fusha", "en", "any"):
        raise ValueError("register must be eg, iq, fusha, en or any")
    rate = _num(params.get("words_per_second", DEFAULT_RATE[register]), 1.0, 4.0, "words_per_second")
    recorded = bool(params.get("voice_recorded", False))
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    counts = [len(_words(ln)) for ln in lines]
    checks = []

    def check(ok, name, why=""):
        checks.append({"ok": bool(ok), "check": name, "why": "" if ok else why})

    total, target = sum(counts), seconds * rate
    if recorded:
        checks.append({"ok": True, "check": "length (voice already recorded: words are fixed)", "why": ""})
    else:
        check(abs(total - target) <= max(3, 0.12 * target), f"length {total} words for {seconds:g} s (~{target:.0f} at {rate:g} w/s)",
              "cut or add a beat before recording")
    check(len(lines) >= 3, f"at least 3 lines ({len(lines)})", "hook, middle and payoff need their own lines")
    if lines:
        low0 = lines[0].lower()
        check(counts[0] <= 7, f"hook <= 7 words ({counts[0]})", "say the strange fact in fewer words")
        check(not lines[0].rstrip().endswith(("؟", "?")), "hook is a flat statement, not a question",
              "state the strange fact; questions in the first line lose the viewer")
        check(not any(low0.startswith(b.lower()) for b in BAD_OPENERS), "no greeting / 'in this video' / 'wait till the end' opener",
              "open inside the action")
        k = len(lines)
        turns = sum((TURNS[r] for r in TURNS), ()) if register == "any" else TURNS.get(register, ())
        half = lines[max(1, k // 2 - (1 if k % 2 == 0 else 0)):max(2, k - 1)] or lines[1:]
        check(any(t.lower() in ln.lower() for ln in half for t in turns),
              "a turn line in the second half", "add the mechanism line (e.g. «تعرف ليه؟»)")
        check(any(ln.lower().startswith(e.lower()) or f" {e.lower()} " in f" {ln.lower()} " for ln in lines[1:] for e in ESCALATION),
              "escalation joined by بس / وبعدين / وفجأة / ولما ...", "chain the middle beats")
        check(counts[-1] <= 9, f"payoff <= 9 words ({counts[-1]})", "end on a short line, ideally a callback to the hook")
        check(max(counts) <= 14, f"one picture per line (longest {max(counts)} words <= 14)", "split long lines")
    found = {r: [m for m in MARKERS[r] if m in text] for r in MARKERS}
    if register in ("eg", "iq", "fusha"):
        others = {r: m for r, m in found.items() if r != register and m}
        check(not others, f"one register ({register}) from first word to last",
              "; ".join(f"{r}: {', '.join(m)}" for r, m in others.items()))
    return {"op": "script_check", "ok": all(c["ok"] for c in checks), "lines": len(lines), "words": total,
            "seconds": seconds, "register": register, "markers_found": found, "checks": checks,
            "limits": ["Structure and length only: it cannot judge whether the story is true, funny or moving.",
                       "Dialect markers are a short word list; a clean result does not prove the register.",
                       "Facts in the script still need sources listed under it."]}


# ----------------------------------------------------------------------------- story_plan

MOODS = {"setup": "day", "middle": "night", "memory": "dream", "explain": "golden", "ending": "sunset"}


def story_plan(params: dict) -> dict:
    _no_extra(params, {"lines", "seconds", "fps", "explain_line", "memory_lines", "ending", "beat_seconds"},
              ("lines", "seconds"))
    lines = params["lines"]
    if isinstance(lines, int) and not isinstance(lines, bool):
        lines = [f"line {i + 1}" for i in range(lines)]
    if not isinstance(lines, list) or not 3 <= len(lines) <= 60 or not all(isinstance(x, str) and x.strip() for x in lines):
        raise ValueError("lines must be 3-60 sentences (or their count)")
    seconds = _num(params["seconds"], 3, 600, "seconds")
    fps = int(_num(params.get("fps", 30), 12, 60, "fps"))
    beat = _num(params.get("beat_seconds", 0.86), 0.4, 3.0, "beat_seconds")
    ending = params.get("ending", "sunset")
    if ending not in ("sunset", "dawn"):
        raise ValueError("ending must be sunset or dawn")
    n = len(lines)
    explain = params.get("explain_line")
    if explain is None:
        explain = next((i for i, s in enumerate(lines) if any(t in s for v in TURNS.values() for t in v)), max(1, int(n * 0.7)))
    explain = int(_num(explain, 0, n - 1, "explain_line"))
    memory = set(params.get("memory_lines", []))
    weights = [max(1, len(_words(s))) for s in lines]
    frames_total = round(seconds * fps)
    scenes, start = [], 0
    for i, s in enumerate(lines):
        length = round(frames_total * sum(weights[:i + 1]) / sum(weights)) - start
        pos = i / max(1, n - 1)
        if i == n - 1:
            act, mood = "ending", ending
        elif i >= explain:
            act, mood = "explain", "golden"
        elif i in memory:
            act, mood = "memory", "dream"
        elif pos < 0.2 or i == 0:
            act, mood = "setup", "day"
        else:
            act, mood = "middle", "night"
        scenes.append({"line": i, "text": s, "act": act, "light": mood, "start_frame": start, "frames": length,
                       "camera_calm": act == "explain"})
        start += length
    merged = []
    for sc in scenes:   # a new scene only when the light changes
        if merged and merged[-1]["light"] == sc["light"]:
            merged[-1]["frames"] += sc["frames"]
            merged[-1]["lines"].append(sc["line"])
        else:
            merged.append({"act": sc["act"], "light": sc["light"], "start_frame": sc["start_frame"],
                           "frames": sc["frames"], "lines": [sc["line"]], "camera_calm": sc["camera_calm"]})
    step = max(1, round(beat * fps))
    beats, f, k = [], 0, 0
    while f < frames_total:
        if f == 0:
            move = "extreme_close_up_key_object"
        else:
            move = "push_in" if k % 3 != 2 else "pull_out"     # about 2:1 push-ins over pull-outs
            k += 1
        beats.append({"frame": f, "move": move, "ease_frames": min(19, step)})
        f += step
    dark = sum(s["frames"] for s in scenes if s["light"] in ("night", "dream")) / max(1, frames_total)
    checks = [{"ok": 0.5 <= dark <= 0.7, "check": f"darker middle {dark:.0%} of runtime (aim 50-70%)"},
              {"ok": scenes[-1]["light"] in ("sunset", "dawn"), "check": "ending in sunset or dawn light"},
              {"ok": beats[0]["move"] == "extreme_close_up_key_object" and step <= fps, "check": "key object close-up inside the first second"}]
    return {"op": "story_plan", "fps": fps, "frames": frames_total, "scenes": merged, "lines": scenes, "camera_beats": beats,
            "rules": ["Scenes change only when the place or the light changes.",
                      "Explanations live inside the world (a sign, a tag, a board, a newspaper), never a floating card.",
                      "If a frame looks flat: a near-foreground object, a practical light or a stronger light change, not more text.",
                      "Critic loop before the full render: score every still 1-10 (characters, set, light, depth, caption); fix anything under 8."],
            "checks": checks,
            "limits": ["A plan, not a render: frame numbers are exact, taste is not measured.",
                       "Moods are labels for the renderer that the owner chooses; nothing is drawn here."]}


# ----------------------------------------------------------------------------- tempo_steadiness

def tempo_steadiness(params: dict) -> dict:
    _no_extra(params, {"onsets", "duration", "min_bpm", "max_bpm", "tolerance"}, ("onsets",))
    raw = params["onsets"]
    if not isinstance(raw, list) or len(raw) > 20000:
        raise ValueError("onsets must be a list of seconds")
    ev = sorted(_num(x, 0, 36000, "onset") for x in raw)
    lo = _num(params.get("min_bpm", 60), 30, 300, "min_bpm")
    hi = _num(params.get("max_bpm", 200), lo, 400, "max_bpm")
    tol = _num(params.get("tolerance", 0.06), 0.01, 0.2, "tolerance")
    duration = _num(params.get("duration", (ev[-1] + 0.5) if ev else 1.0), 0.5, 36000, "duration")
    limits = ["Constant tempo only: no tempo changes, bars or downbeats.",
              "Onsets come from the caller (e.g. an energy-flux peak picker); bad onsets give a bad answer."]
    if len(ev) < 6:
        return {"op": "tempo_steadiness", "steady_beat": False, "bpm": None, "reason": "fewer than 6 onsets", "limits": limits}
    best, tried = None, 0
    anchors = ev[: min(len(ev), 16)]                                # phase from the onsets themselves
    for b10 in range(int(lo * 10), int(hi * 10) + 1, 5):           # 0.5 BPM steps
        bpm = b10 / 10
        period = 60.0 / bpm
        for anchor in anchors:
            tried += 1
            errs = [abs(((t - anchor + period / 2) % period) - period / 2) for t in ev]
            hits = [e for e in errs if e <= tol]
            mean_err = sum(hits) / max(1, len(hits))
            cand = (len(hits), -round(mean_err, 4), -abs(bpm - 120), bpm, period)
            if best is None or cand > best:
                best = cand
    m, neg_err, _, bpm, period = best
    n = len(ev)
    chance = min(1.0, 2 * tol / period)
    # P(at least m of n onsets land on one given grid by chance), times every grid we tried (Bonferroni).
    tail = sum(math.comb(n, k) * chance ** k * (1 - chance) ** (n - k) for k in range(m, n + 1))
    p_any = min(1.0, tail * tried)
    match = m / n
    steady = match >= 0.75 and p_any < 0.01
    return {"op": "tempo_steadiness", "steady_beat": steady, "bpm": bpm if steady else None, "bpm_candidate": bpm,
            "grid_match": round(match, 3), "chance_match": round(chance, 3), "p_chance_any_grid": float(f"{p_any:.3g}"),
            "grids_tried": tried, "mean_error_s": round(-neg_err, 4), "onsets": n, "duration": duration,
            "note": None if steady else "no steady beat: onsets do not sit on a tempo grid above chance; cut on energy/onsets instead",
            "limits": limits + ["Steady means: >=75% of onsets on one grid and < 1% chance of that over all grids tried."]}


# ----------------------------------------------------------------------------- delivery_gate

STANDARD = {"width": 1080, "height": 1920, "fps": 30.0, "codec": "h264", "pix_fmt": "yuv420p"}


def _probe(path: Path) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                       capture_output=True, text=True, timeout=120)
    if r.returncode:
        raise ValueError("ffprobe could not read the file: " + r.stderr.strip()[-200:])
    return json.loads(r.stdout)


def _top_boxes(path: Path, limit=64):
    """Top-level MP4 boxes in file order (size, type); stops at the end or after `limit`."""
    out = []
    with open(path, "rb") as f:
        size_total = path.stat().st_size
        pos = 0
        while pos < size_total and len(out) < limit:
            f.seek(pos)
            head = f.read(16)
            if len(head) < 8:
                break
            size, kind = struct.unpack(">I4s", head[:8])
            if size == 1 and len(head) >= 16:
                size = struct.unpack(">Q", head[8:16])[0]
            elif size == 0:
                size = size_total - pos
            if size < 8:
                break
            out.append(kind.decode("latin-1"))
            pos += size
    return out


def _existing_file(p, name="source"):
    if not isinstance(p, str) or not p or len(p) > 1024 or "://" in p:
        raise ValueError(f"{name} must be a local file path")
    path = Path(p).expanduser()
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{name} must be an existing regular file")
    return path


def delivery_gate(params: dict) -> dict:
    _no_extra(params, {"source", "width", "height", "fps", "need_audio", "expected_duration", "duration_tolerance",
                       "require_bt709"}, ("source",))
    path = _existing_file(params["source"])
    w = int(_num(params.get("width", STANDARD["width"]), 16, 8192, "width"))
    h = int(_num(params.get("height", STANDARD["height"]), 16, 8192, "height"))
    fps = _num(params.get("fps", STANDARD["fps"]), 1, 240, "fps")
    info = _probe(path)
    vs = [s for s in info.get("streams", []) if s.get("codec_type") == "video"]
    au = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]
    v = vs[0] if vs else {}
    num, _, den = (v.get("r_frame_rate") or "0/1").partition("/")
    got_fps = float(num) / float(den or 1) if float(den or 1) else 0.0
    dur = float(info.get("format", {}).get("duration") or 0)
    boxes = _top_boxes(path)
    checks = [
        ("size", v.get("width") == w and v.get("height") == h, f"{v.get('width')}x{v.get('height')}", f"{w}x{h}"),
        ("fps", abs(got_fps - fps) < 0.01, round(got_fps, 3), fps),
        ("codec", v.get("codec_name") == STANDARD["codec"], v.get("codec_name"), "h264"),
        ("pix_fmt", v.get("pix_fmt") == STANDARD["pix_fmt"], v.get("pix_fmt"), "yuv420p"),
        ("faststart", "moov" in boxes and ("mdat" not in boxes or boxes.index("moov") < boxes.index("mdat")),
         ">".join(boxes[:6]), "moov before mdat"),
    ]
    if params.get("need_audio", True):
        checks.append(("audio", bool(au), au[0].get("codec_name") if au else "none", "an audio stream"))
    if params.get("require_bt709", False):
        checks.append(("bt709", v.get("color_primaries") == "bt709" and v.get("color_transfer") == "bt709",
                       f"{v.get('color_primaries')}/{v.get('color_transfer')}", "bt709/bt709"))
    if "expected_duration" in params:
        want = _num(params["expected_duration"], 0.1, 36000, "expected_duration")
        tol = _num(params.get("duration_tolerance", 0.05), 0.0, 5, "duration_tolerance")
        checks.append(("duration", abs(dur - want) <= tol, round(dur, 3), want))
    rows = [{"check": c[0], "ok": bool(c[1]), "got": c[2], "want": c[3]} for c in checks]
    return {"op": "delivery_gate", "ok": all(r["ok"] for r in rows), "file": str(path), "duration": round(dur, 3),
            "frames": int(v.get("nb_frames") or 0) or None, "checks": rows,
            "limits": ["Container and stream facts only; watch the decoded frames before calling it delivered."]}


# ----------------------------------------------------------------------------- credit_overlay

DEFAULT_CREDIT = "© Mahmoud Elkosif"
DEFAULT_END = ["مونتاج وإخراج Mahmoud Elkosif", "تابعني على فيسبوك"]


def _ass_time(t: float) -> str:
    t = max(0.0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def _ass_text(s: str) -> str:
    return s.replace("\\", "⧵").replace("{", "(").replace("}", ")").replace("\n", " ")


def ass_document(duration: float, width: int, height: int, font: str, credit: str, end_lines: list[str],
                 end_seconds: float) -> str:
    end0 = max(0.0, duration - end_seconds)
    small = max(18, round(height * 0.0177))
    big = max(28, round(height * 0.0323))
    events = []
    if credit:
        events.append(f"Dialogue: 0,{_ass_time(0)},{_ass_time(duration)},Credit,,0,0,0,,{_ass_text(credit)}")
    if end_lines:
        events.append(f"Dialogue: 1,{_ass_time(end0)},{_ass_time(duration)},End,,0,0,0,,{{\\fad(250,0)}}"
                      + "\\N".join(_ass_text(x) for x in end_lines))
    return ("[Script Info]\nScriptType: v4.00+\nWrapStyle: 2\nScaledBorderAndShadow: yes\n"
            f"PlayResX: {width}\nPlayResY: {height}\n\n[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
            "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
            "MarginR, MarginV, Encoding\n"
            f"Style: Credit,{font},{small},&H50FFFFFF,&H000000FF,&H64000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,8,40,40,"
            f"{round(height * 0.036)},1\n"
            f"Style: End,{font},{big},&H00FFFFFF,&H000000FF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,4,2,2,60,60,"
            f"{round(height * 0.088)},1\n\n[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n" + "\n".join(events) + "\n")


def _audio_md5(path: Path) -> str | None:
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0", "-c", "copy", "-f", "md5", "-"],
                       capture_output=True, text=True, timeout=600)
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def credit_overlay(params: dict) -> dict:
    _no_extra(params, {"source", "output", "credit", "end_lines", "end_seconds", "font", "font_file", "preset",
                       "crf", "approve_write"}, ("source", "output"))
    if params.get("approve_write") is not True:
        raise PermissionError("credit_overlay writes a new video: explicit --approve-write required")
    src = _existing_file(params["source"])
    out_text = params["output"]
    if not isinstance(out_text, str) or not out_text or len(out_text) > 1024:
        raise ValueError("output must be a new .mp4 path")
    original = Path(out_text).expanduser()
    if original.is_symlink():
        raise ValueError("refusing symlink output")
    target = original.absolute()
    if target.suffix.lower() != ".mp4" or target.exists() or not target.parent.is_dir():
        raise ValueError("output must be a new .mp4 in an existing folder (never overwritten)")
    if target.resolve() == src.resolve():
        raise ValueError("output must differ from source")
    credit = params.get("credit", DEFAULT_CREDIT)
    end_lines = params.get("end_lines", DEFAULT_END)
    if not isinstance(credit, str) or len(credit) > 120:
        raise ValueError("credit must be a short string")
    if not isinstance(end_lines, list) or len(end_lines) > 4 or not all(isinstance(x, str) and len(x) <= 120 for x in end_lines):
        raise ValueError("end_lines must be up to 4 short strings")
    end_seconds = _num(params.get("end_seconds", 3.0), 0.5, 30, "end_seconds")
    font = params.get("font", "Lalezar")
    if not isinstance(font, str) or not re.fullmatch(r"[\w .\-]{1,64}", font):
        raise ValueError("font must be a family name")
    font_file = params.get("font_file")
    if font_file is not None:
        font_file = _existing_file(font_file, "font_file")
        if font_file.suffix.lower() not in (".ttf", ".otf"):
            raise ValueError("font_file must be .ttf or .otf")
    preset = params.get("preset", "slow")
    if preset not in ("veryfast", "faster", "fast", "medium", "slow"):
        raise ValueError("preset must be veryfast, faster, fast, medium or slow")
    crf = int(_num(params.get("crf", 17), 0, 30, "crf"))
    for prog in ("ffmpeg", "ffprobe"):
        if not shutil.which(prog):
            return {"op": "credit_overlay", "status": "blocked", "reason": f"{prog} not installed"}
    info = _probe(src)
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    if v is None:
        raise ValueError("source has no video stream")
    has_audio = any(s.get("codec_type") == "audio" for s in info.get("streams", []))
    duration = float(info.get("format", {}).get("duration") or 0)
    if duration <= 0:
        raise ValueError("source duration unknown")
    width, height = int(v["width"]), int(v["height"])
    frames = int(v.get("nb_frames") or 0)
    with tempfile.TemporaryDirectory(dir=target.parent, prefix=".rose-v56-") as tmp:
        work = Path(tmp)
        (work / "fonts").mkdir()
        if font_file:
            shutil.copy2(font_file, work / "fonts" / font_file.name)
        (work / "credit.ass").write_text(ass_document(duration, width, height, font, credit, end_lines, end_seconds),
                                          encoding="utf-8")
        staged = work / "staged.mp4"
        cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-v", "error", "-y", "-i", str(src),
               "-vf", "ass=credit.ass:fontsdir=fonts", "-map", "0:v:0", "-map", "0:a?",
               "-c:v", "libx264", "-profile:v", "high", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p",
               "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
               "-c:a", "copy", "-movflags", "+faststart"]
        if frames:
            cmd += ["-frames:v", str(frames)]
        r = subprocess.run(cmd + [str(staged)], cwd=work, capture_output=True, text=True, timeout=3600)
        if r.returncode or not staged.is_file():
            raise RuntimeError("ffmpeg failed: " + r.stderr.strip()[-400:])
        out_info = _probe(staged)
        ov = next(s for s in out_info["streams"] if s.get("codec_type") == "video")
        out_frames = int(ov.get("nb_frames") or 0)
        audio_same = None
        if has_audio:
            a, b = _audio_md5(src), _audio_md5(staged)
            audio_same = bool(a) and a == b
        problems = []
        if frames and out_frames != frames:
            problems.append(f"frame count {out_frames} != source {frames}")
        if has_audio and not audio_same:
            problems.append("audio is not byte-identical to the source")
        if (int(ov["width"]), int(ov["height"])) != (width, height):
            problems.append("size changed")
        if problems:
            raise RuntimeError("verification failed, nothing written: " + "; ".join(problems))
        os.link(staged, target) if hasattr(os, "link") else shutil.copy2(staged, target)
    gate = delivery_gate({"source": str(target), "width": width, "height": height,
                          "fps": round(eval_fps(v), 3), "need_audio": has_audio,
                          "expected_duration": duration, "duration_tolerance": 0.1})
    return {"op": "credit_overlay", "status": "written", "output": str(target), "frames": out_frames or None,
            "source_frames": frames or None, "audio_byte_identical": audio_same, "credit": credit,
            "end_card_from": round(max(0.0, duration - end_seconds), 3), "font": font, "gate": gate,
            "limits": ["Look at a frame from the end card: the font must contain Arabic glyphs, or libass falls back.",
                       "Video is re-encoded (H.264 CRF 17); audio is stream-copied."]}


def eval_fps(stream: dict) -> float:
    num, _, den = (stream.get("r_frame_rate") or "0/1").partition("/")
    return float(num) / float(den or 1) if float(den or 1) else 0.0


# ----------------------------------------------------------------------------- dispatcher

def run(op: str, params: dict):
    """IO_ADAPTERS dispatcher: approve_write is injected by capability_runtime only for effect=write."""
    if op not in OPS:
        raise ValueError("unknown reel.craft op")
    params = dict(params or {})
    if EFFECTS[op] == "read":
        params.pop("approve_write", None)
    return {"script_check": script_check, "story_plan": story_plan, "tempo_steadiness": tempo_steadiness,
            "delivery_gate": delivery_gate, "credit_overlay": credit_overlay}[op](params)
