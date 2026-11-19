#!/usr/bin/env python3
"""Black Dragon styles kit (v1.2): one JSON spec -> a canvas film page in one of the owner's proven styles -> stills / MP4.

    python build_style.py SPEC.json --out DIR [--stills 1.5,6,12] [--render] [--embed-fonts] [--force] [--tidy]
    python build_style.py SPEC.json --check        # validate the spec only (no ffmpeg, no browser)
    python build_style.py --list                   # the styles and their knobs

Steps: read the spec -> cut 9:16 1080x1920 frames for every shot with ffmpeg (crop from focus/box/zoom, setpts for
speed, 30 fps, -q:v 5) -> write DIR/index.html with common.js, the style's js and its fonts -> mix the song (fades,
loudnorm -14) into DIR/mix.m4a -> --stills: PNG stills in DIR/stills; --render: the film through
app/engines/render/render.cjs, a black-frame scan + patch (engines.qa / engines.deliver), then an exact-length mux
(engines.deliver.mux, never -shortest) into DIR/<name>.mp4. Without --stills/--render it stops after the page.
Paths in the spec are relative to the spec's own folder; Arabic names are fine. Styles and knobs: README.md.
Exit codes: 0 done, 1 a step failed (render, page error, black frames left, mux), 2 bad spec or usage.
"""
import argparse, base64, concurrent.futures as cf, html, json, math, os, re, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent.parent                      # black-dragon/ (tools/styles/build_style.py)
FONTS_DIR, STYLES_DIR = HERE / "fonts", HERE / "styles"
W, H = 1080, 1920
TILE_SIZE, TILE_FPS, TILE_Q = (360, 640), 15, 6
TAIL_PAD = 0.7                                   # extra seconds cut after each shot so dissolves never run out of frames
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
PATCH_MAX_FRAMES = 3                             # black runs up to this many frames are patched; longer ones are re-rendered
RECYCLE = 120                                    # same default as render.cjs; page reload every N frames when render.cjs supports --recycle


def _app_dirs():
    """Folders that hold the dragon engines: the skill's own app/ (same version as this kit) first, then DRAGON_HOME."""
    found = []
    for d in (SKILL / "app", os.environ.get("DRAGON_HOME")):
        if d and (Path(d) / "engines" / "media.py").exists() and Path(d) not in found:
            found.append(Path(d))
    return found


APP_DIRS = _app_dirs()
if APP_DIRS and str(APP_DIRS[0]) not in sys.path:
    sys.path.insert(0, str(APP_DIRS[0]))
try:
    from engines.media import exe as _engine_exe
except Exception:  # running outside the skill: plain PATH lookup
    _engine_exe = None

FONTS = {  # CSS family -> (file in fonts/, weight)
    "Ruqaa": ("ArefRuqaa-Bold.ttf", 700),
    "Tajawal": ("Tajawal-Bold.ttf", 700),
    "Lalezar": ("Lalezar-Regular.ttf", 400),
    "Messiri": ("ElMessiri-700.ttf", 700),
    "Amiri": ("Amiri-Bold.ttf", 700),
    "Scheherazade": ("ScheherazadeNew-Bold.ttf", 700),  # Quran verses (Amiri lifts U+0670 until it reads «١»)
}

STYLES = {
    "nil": {
        "about": "slow and warm: letterbox bars, warm grade, long pushes, 0.7 s eased dissolves, gold Ruqaa title",
        "fonts": ["Ruqaa", "Tajawal"],
        "knobs": {"grade": "sepia(.14) saturate(1.1) contrast(1.07) brightness(1.02)", "push": 0.08, "dissolve": 0.7,
                  "letterbox": 150, "leak": False, "vignette": 0.5, "grain": 0.04},
    },
    "beat": {
        "about": "cut on the beat: punch-in on every cut, whip smear on every second cut, three-panel split, Lalezar slams",
        "fonts": ["Lalezar", "Tajawal"],
        "knobs": {"grade": "contrast(1.12) saturate(1.15)", "punch": 0.12, "whip": True, "bar": "#c8102e",
                  "vignette": 0.45, "grain": 0.04},
    },
    "wall": {
        "about": "living wall of looping tiles; the camera dives into hero tiles, ends pulled back on the whole wall",
        "fonts": ["Ruqaa", "Tajawal"],
        "knobs": {"cols": 3, "loop": 2.9, "vignette": 0.5, "grain": 0.03},
    },
    "medal": {
        "about": "one shape carries the film: a gold medal grows into each shot (iris, card flip, gold flood), no dissolves",
        "fonts": ["Ruqaa", "Tajawal"],
        "knobs": {"field": "#b5121b", "ink": "#0b0b10", "medal_text": "١", "grain": 0.03},
    },
    "chapters": {
        "about": "organised film: chapter title top (numerals off unless numbers: true), her words bottom, Quran verses "
                 "in ScheherazadeNew-Bold with ﴿ ﴾ outside the RTL line, lyric band, cards",
        "fonts": ["Ruqaa", "Tajawal"],
        "knobs": {"dissolve": 0.16, "dissolve_broll": 0.5, "push": 0.06, "numbers": False, "vignette": 0.42, "grain": 0.03},
    },
    "clean": {
        "about": "clean cinematic tribute: full bleed, gentle push, short dissolves, white Ruqaa quotes word by word",
        "fonts": ["Ruqaa", "Tajawal"],
        "knobs": {"dissolve": 0.14, "dissolve_broll": 0.5, "push": 0.06, "vignette": 0.42, "grain": 0.035},
    },
}
MOVES = ("iris", "flip", "flood")
ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
EXPLAINER_WORDS = ("الفصل", "المرحلة")


class SpecError(ValueError):
    """The spec is wrong; the message names the field."""


class BuildError(RuntimeError):
    """A build step failed (ffmpeg, node, render, mux)."""


# ---------------------------------------------------------------- tools

def exe(name):
    if _engine_exe:
        try:
            return _engine_exe(name)
        except FileNotFoundError:
            pass
    p = shutil.which(name)
    if not p:
        raise BuildError(f"{name} not found (Windows: winget install -e --id Gyan.FFmpeg)")
    return p


def run(cmd, what):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise BuildError(f"{what} failed ({r.returncode}): {(r.stderr or r.stdout).strip()[-600:]}")
    return r


def source_size(path):
    """(width, height) as decoded, i.e. after the rotation a phone stored in the file."""
    r = run([exe("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=width,height:stream_tags=rotate:stream_side_data=rotation", "-of", "json", path], f"ffprobe {path}")
    streams = json.loads(r.stdout or "{}").get("streams") or []
    if not streams:
        raise BuildError(f"no picture in {path}")
    s = streams[0]
    w, h = int(s["width"]), int(s["height"])
    rot = (s.get("tags") or {}).get("rotate")
    for sd in s.get("side_data_list") or []:
        if "rotation" in sd:
            rot = sd["rotation"]
    try:
        if abs(int(float(rot or 0))) % 180 == 90:
            w, h = h, w
    except ValueError:
        pass
    return w, h


def media_seconds(path):
    try:
        r = run([exe("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], "ffprobe")
        return float((r.stdout or "0").strip() or 0)
    except (BuildError, ValueError):
        return 0.0


def crop_rect(sw, sh, focus=(0.5, 0.42), box=None, zoom=1.0, aspect=9 / 16):
    """The 9:16 window to cut from a sw x sh picture: the largest one inside `box` ([x, y, w, h] in source pixels,
    clamped to the picture), made smaller by `zoom`, centred on `focus` (fractions of the box) and kept inside the box.
    Returns (w, h, x, y, fy): even sizes, the corner, and the focus height inside the window (the page's push anchor)."""
    bx, by, bw, bh = [float(v) for v in (box or (0, 0, sw, sh))]
    bx, by = min(max(0.0, bx), sw - 2), min(max(0.0, by), sh - 2)
    bw, bh = min(max(2.0, bw), sw - bx), min(max(2.0, bh), sh - by)
    ch = min(bh, bw / aspect) / max(1.0, zoom)
    cw = ch * aspect
    cw, ch = max(2, int(cw) // 2 * 2), max(2, int(ch) // 2 * 2)
    fxa, fya = bx + focus[0] * bw, by + focus[1] * bh
    x = int(round(min(max(fxa - cw / 2, bx), bx + bw - cw)))
    y = int(round(min(max(fya - ch / 2, by), by + bh - ch)))
    fy = min(1.0, max(0.0, (fya - y) / ch))
    return cw, ch, x, y, round(fy, 3)


# ---------------------------------------------------------------- spec

def _num(v, where, lo=None, hi=None, default=None):
    if v is None:
        if default is None:
            raise SpecError(f"{where} is required")
        return default
    if isinstance(v, bool):
        raise SpecError(f"{where} must be a number, got {v!r}")
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise SpecError(f"{where} must be a number, got {v!r}")
    if not math.isfinite(x) or (lo is not None and x < lo) or (hi is not None and x > hi):
        rng = f" between {lo} and {hi}" if lo is not None and hi is not None else (f" >= {lo}" if lo is not None else "")
        raise SpecError(f"{where} must be a number{rng}, got {v!r}")
    return x


def _pair(v, where, default):
    if v is None:
        return tuple(default)
    if not isinstance(v, (list, tuple)) or len(v) != 2:
        raise SpecError(f"{where} must be [x, y] (fractions 0..1), got {v!r}")
    return tuple(_num(c, f"{where}[{i}]", 0.0, 1.0) for i, c in enumerate(v))


def _box(v, where):
    if v is None:
        return None
    if not isinstance(v, (list, tuple)) or len(v) != 4:
        raise SpecError(f"{where} must be [x, y, w, h] in source pixels, got {v!r}")
    b = [_num(c, f"{where}[{i}]", 0.0) for i, c in enumerate(v)]
    if b[2] < 2 or b[3] < 2:
        raise SpecError(f"{where} needs a width and height of at least 2 px, got {v!r}")
    return b


def _path(v, base, where, check):
    if not isinstance(v, str) or not v.strip():
        raise SpecError(f"{where} must be a file path")
    p = Path(os.path.expanduser(v.strip()))
    p = p if p.is_absolute() else (base / p)
    if check and not p.is_file():
        raise SpecError(f"{where} not found: {p}")
    return p


def _safe_name(s):
    """A file name that works on Windows too (Arabic letters are kept)."""
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", s or "").strip(". ") or "film"


def _text(v):
    if v is None:
        return ""
    if not isinstance(v, (str, int, float)) or isinstance(v, bool):
        raise SpecError(f"text must be a string, got {v!r}")
    return str(v).strip()


def _when(x, where, key, grid, default=None):
    """start/end of an item in seconds; in the beat style 'beats': [n0, n1] places it on the beat grid."""
    if grid and isinstance(x, dict) and x.get("beats") is not None:
        b = x["beats"]
        if not isinstance(b, (list, tuple)) or len(b) != 2:
            raise SpecError(f"{where}.beats must be [first beat, last beat], got {b!r}")
        n = _num(b[0 if key == "start" else 1], f"{where}.beats", lo=0)
        return grid(n)
    names = {"start": ("start", "s"), "end": ("end", "e")}[key]
    for k in names:
        if isinstance(x, dict) and x.get(k) is not None:
            return _num(x.get(k), f"{where}.{k}", lo=0)
    if default is not None:
        return default
    raise SpecError(f"{where}.{key} is required")


def _timed(x, where, grid=None, extra=()):
    """A timed text item: {text|t, start|s, end|e, ...} or a list holding one string and two numbers in order."""
    if isinstance(x, (list, tuple)):
        txt = [v for v in x if isinstance(v, str)]
        nums = [v for v in x if isinstance(v, (int, float)) and not isinstance(v, bool)]
        if len(txt) != 1 or len(nums) != 2:
            raise SpecError(f"{where} must be [text, start, end] or an object, got {x!r}")
        item = {"t": txt[0].strip(), "s": float(nums[0]), "e": float(nums[1])}
    elif isinstance(x, dict):
        item = {"t": _text(x.get("text", x.get("t"))), "s": _when(x, where, "start", grid), "e": _when(x, where, "end", grid)}
        for k in extra:
            if x.get(k) is not None:
                item[k] = x[k]
    else:
        raise SpecError(f"{where} must be an object or a list, got {x!r}")
    if item["e"] <= item["s"]:
        raise SpecError(f"{where}: end ({item['e']}) must be after start ({item['s']})")
    return item


def _line(x, where, grid=None):
    item = _timed(x, where, grid, extra=("font", "size", "gold", "y"))
    if "font" in item and item["font"] not in FONTS:
        raise SpecError(f"{where}.font must be one of {', '.join(FONTS)}, got {item['font']!r}")
    if "size" in item:
        item["size"] = _num(item["size"], f"{where}.size", 12, 400)
    if "y" in item:
        item["y"] = _num(item["y"], f"{where}.y", 0, H)
    if "gold" in item:
        item["gold"] = bool(item["gold"])
    return item


def _clip(x, where, base, check):
    """Footage fields shared by shots, tiles and heroes."""
    if not isinstance(x, dict):
        raise SpecError(f"{where} must be an object")
    return {"src": _path(x.get("src"), base, f"{where}.src", check),
            "ss": _num(x.get("ss"), f"{where}.ss", lo=0, default=0.0),
            "focus": _pair(x.get("focus"), f"{where}.focus", (0.5, 0.42)),
            "box": _box(x.get("box"), f"{where}.box"),
            "zoom": _num(x.get("zoom"), f"{where}.zoom", 1.0, 8.0, default=1.0),
            "speed": _num(x.get("speed"), f"{where}.speed", 0.05, 8.0, default=1.0),
            "broll": bool(x.get("broll")), "where": where}


def _beat_grid(spec, plan):
    b = spec.get("beat")
    if b is None:
        return None, None
    if b == "auto" and not plan.get("_measure", True):  # --check: no ffmpeg, no librosa
        plan["warnings"].append('beat "auto": measured from the song at build time (--check uses a 0.5 s grid)')
        period, phase = 0.5, 0.0
    elif b == "auto":
        period, phase = measure_beat(plan.get("song"), plan["duration"])
    elif isinstance(b, (int, float)) and not isinstance(b, bool):
        period, phase = _num(b, "beat", 0.1, 4.0), 0.0
    elif isinstance(b, dict):
        if b.get("period") is not None:
            period = _num(b["period"], "beat.period", 0.1, 4.0)
        else:
            period = 60.0 / _num(b.get("bpm"), "beat.bpm (or beat.period)", 15, 600)
        phase = _num(b.get("phase"), "beat.phase", 0.0, 60.0, default=0.0)
    else:
        raise SpecError(f"beat must be a period in seconds, {{\"period\"|\"bpm\", \"phase\"}} or \"auto\", got {b!r}")
    return (lambda n: round(phase + n * period, 3)), period


def measure_beat(song, duration):
    """Beat period and phase of the song section, from engines.audio.beats (librosa), fitted by fit_beat_grid."""
    if not song:
        raise SpecError('beat "auto" needs a song')
    if not Path(song["path"]).is_file():
        raise SpecError(f"song.path not found: {song['path']}")
    try:
        from engines import audio
    except Exception as e:
        raise SpecError(f'beat "auto" needs the dragon engines with librosa ({e}); give "beat": {{"period": s, "phase": s}}')
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "section.wav"
        run([exe("ffmpeg"), "-nostdin", "-v", "error", "-y", "-ss", f"{song['start']:.3f}", "-t", f"{duration:.3f}",
             "-i", song["path"], "-ac", "1", "-ar", "22050", wav], "ffmpeg (beat section)")
        try:
            got = audio.beats(wav)
        except ImportError as e:
            raise SpecError(f'beat "auto" needs librosa ({e}); give "beat": {{"period": s, "phase": s}}')
    bts = got.get("beats") or []
    if len(bts) < 4:
        raise SpecError('beat "auto": too few beats found; give "beat": {"period": s, "phase": s}')
    return fit_beat_grid(bts)


def fit_beat_grid(bts):
    """(period, phase) of a beat list. librosa's beat times are quantised to 512/22050 s (23 ms), so the median gap is
    ~2 % off and a grid built on it drifts a frame more every few beats (0.44 s late by beat 40 at 120 bpm). Instead:
    the median gap is only a first guess; each beat gets an index counted gap by gap (a dropped beat counts as 2, a
    stray half-beat is merged), and a least-squares line through (index, time) gives period and phase."""
    bts = sorted(float(b) for b in bts)
    gaps = sorted(b - a for a, b in zip(bts, bts[1:]))
    if not gaps:
        raise SpecError('beat "auto": too few beats found; give "beat": {"period": s, "phase": s}')
    p0 = gaps[len(gaps) // 2]
    kept = [bts[0]]
    for b in bts[1:]:
        if b - kept[-1] >= 0.6 * p0:   # an extra onset between two beats would tilt the fit
            kept.append(b)
    idx = [0]
    for a, b in zip(kept, kept[1:]):
        idx.append(idx[-1] + max(1, round((b - a) / p0)))
    n = len(idx)
    mi, mb = sum(idx) / n, sum(kept) / n
    den = sum((i - mi) ** 2 for i in idx)
    period = sum((i - mi) * (b - mb) for i, b in zip(idx, kept)) / den if den else p0
    return period, (mb - period * mi) % period


def _beat_shots(spec, plan, grid, base, check):
    shots, tri, n = [], [], 0.0
    rest_at = None
    for k, x in enumerate(spec.get("shots") or []):
        where = f"shots[{k}]"
        if not isinstance(x, dict):
            raise SpecError(f"{where} must be an object")
        if x.get("tri") is not None:
            subs = x["tri"]
            if not isinstance(subs, list) or len(subs) != 3:
                raise SpecError(f"{where}.tri must list exactly 3 shots")
            nb = _num(x.get("beats"), f"{where}.beats", lo=3)
            a, b = grid(n), grid(n + nb)
            tri.append({"st": a, "en": b, "ix": [len(shots), len(shots) + 1, len(shots) + 2]})
            for j, sub in enumerate(subs):
                shots.append({**_clip(sub, f"{where}.tri[{j}]", base, check), "st": a, "en": b})
            n += nb
        elif x.get("rest"):
            a = grid(n) if shots else 0.0
            rest_at = a
            shots.append({**_clip(x, where, base, check), "st": a, "en": plan["duration"]})
        elif x.get("beats") is not None:
            nb = _num(x.get("beats"), f"{where}.beats", lo=0.25)
            shots.append({**_clip(x, where, base, check), "st": grid(n), "en": grid(n + nb)})
            n += nb
        else:
            shots.append({**_clip(x, where, base, check), "st": _when(x, where, "start", None),
                          "en": _when(x, where, "end", None)})
    if shots and shots[0]["st"] == grid(0):  # the film opens on the first shot, not on the first beat
        first = shots[0]["st"]
        for s in shots:
            if s["st"] == first:
                s["st"] = 0.0
        if tri and tri[0]["ix"][0] == 0:
            tri[0]["st"] = 0.0
    plan["tri"] = tri
    return shots, (rest_at if rest_at is not None else (grid(n) if n else None))


def normalise(spec, base, check_files=True):
    """Validate a spec and fill in defaults. Returns the build plan (plan['warnings'] lists the lints).
    Raises SpecError naming the field that is wrong. With check_files False (--check) nothing is run: beat "auto" is
    not measured."""
    if not isinstance(spec, dict):
        raise SpecError("the spec must be a JSON object")
    base = Path(base)
    warn = []
    style = spec.get("style")
    if style not in STYLES:
        raise SpecError(f"style must be one of {', '.join(STYLES)}, got {style!r}")
    dur = _num(spec.get("duration"), "duration", 0.5, 3600)
    fps = int(_num(spec.get("fps"), "fps", 1, 120, default=30))
    plan = {"style": style, "duration": dur, "fps": fps, "warnings": warn, "_measure": bool(check_files)}
    _unknown_keys(spec, warn)
    plan["name"] = _safe_name(_text(spec.get("name")))
    plan["watermark"] = _text(spec.get("watermark"))
    cr = spec.get("credit") or []
    if isinstance(cr, str):
        cr = [c for c in re.split(r"[\n|]", cr)]
    if not isinstance(cr, list):
        raise SpecError("credit must be a list of lines")
    plan["credit"] = [_text(c) for c in cr if _text(c)][:3]
    if not plan["watermark"] or not plan["credit"]:
        warn.append("no watermark or credit in the spec: the owner's films carry «© Mahmoud Elkosif» and "
                    "«مونتاج وإخراج Mahmoud Elkosif» / «تابعني على فيسبوك»")

    song = spec.get("song")
    if song:
        if isinstance(song, str):
            song = {"path": song}
        if not isinstance(song, dict):
            raise SpecError("song must be a path or {path, start, fade_in, fade_out, copy, normalize}")
        copy = bool(song.get("copy"))
        plan["song"] = {"path": _path(song.get("path"), base, "song.path", check_files),
                        "start": _num(song.get("start"), "song.start", lo=0, default=0.0),
                        "fade_in": 0.0 if copy else _num(song.get("fade_in"), "song.fade_in", 0, 30, default=0.8),
                        "fade_out": 0.0 if copy else _num(song.get("fade_out"), "song.fade_out", 0, 30, default=2.5),
                        "copy": copy, "normalize": False if copy else song.get("normalize", True) is not False}
        if copy and (song.get("fade_in") or song.get("fade_out")):
            warn.append("song.copy: the song is copied byte for byte, so fade_in / fade_out are ignored")
    else:
        plan["song"] = None

    grid, period = (None, None)
    if style == "beat":
        grid, period = _beat_grid(spec, plan)
        uses_beats = any(isinstance(x, dict) and (x.get("beats") is not None or x.get("tri") or x.get("rest"))
                         for x in spec.get("shots") or [])
        if uses_beats and not grid:
            raise SpecError('the beat style places shots on the beat grid: add "beat": {"period": s, "phase": s}')
        plan["beat"] = period or 0.5

    # shots
    raw = spec.get("shots") or []
    if not isinstance(raw, list):
        raise SpecError("shots must be a list")
    end_default = None
    if style == "wall" and raw:
        warn.append("the wall style draws tiles and heroes, not shots: shots ignored")
        raw = []
    if style == "beat" and grid:
        shots, end_default = _beat_shots(spec, plan, grid, base, check_files)
    else:
        shots = []
        for k, x in enumerate(raw):
            where = f"shots[{k}]"
            sh = {**_clip(x, where, base, check_files), "st": _when(x, where, "start", None),
                  "en": _when(x, where, "end", None)}
            if style == "medal":
                mv = x.get("move")
                if k and mv is not None and mv not in MOVES:
                    raise SpecError(f"{where}.move must be one of {', '.join(MOVES)}, got {mv!r}")
                sh["move"] = (mv or "iris") if k else "grow"
                if x.get("at") is not None:
                    sh["at"] = _num(x["at"], f"{where}.at", lo=0)
                if x.get("fill") is not None:
                    sh["fill"] = _text(x["fill"])
            shots.append(sh)
        if style == "beat":
            plan["tri"] = []
    for s in shots:
        if s["st"] >= dur:
            raise SpecError(f"{s['where']} starts at {s['st']} s, when the film has ended ({dur} s)")
        if s["en"] <= s["st"]:
            raise SpecError(f"{s['where']}: end ({s['en']}) must be after start ({s['st']})")
        if s["en"] > dur + 1e-6:
            warn.append(f"{s['where']} ends at {s['en']} s, after the film ({dur} s): cut at {dur} s")
            s["en"] = dur
    if style != "beat":
        for k in range(1, len(shots)):
            if shots[k]["st"] < shots[k - 1]["st"]:
                raise SpecError(f"shots must be in time order: shots[{k}] starts before shots[{k - 1}]")
    if style not in ("wall",) and not shots:
        raise SpecError(f"the {style} style needs at least one shot")
    seq = [s for i, s in enumerate(shots) if style != "beat" or not any(i in t["ix"][1:] for t in plan.get("tri", []))]
    for a, b in zip(seq, seq[1:]):
        if b["st"] - a["en"] > 1 / fps:
            warn.append(f"gap between shots at {a['en']:.2f}-{b['st']:.2f} s: the earlier shot's last frame is held")
    if seq and style not in ("medal",) and seq[0]["st"] > 1 / fps:
        warn.append(f"the first shot starts at {seq[0]['st']} s: its first frame is held before that")
    if seq and seq[-1]["en"] < dur - 0.05 and style != "medal":
        warn.append(f"the last shot ends at {seq[-1]['en']} s, before the film ends ({dur} s): its last frame is held")
    if style == "medal":
        _medal_checks(shots, spec, dur, warn)
    plan["shots"] = shots

    # wall tiles and heroes
    if style == "wall":
        tiles = spec.get("tiles") or []
        if not isinstance(tiles, list) or not tiles:
            raise SpecError("the wall style needs tiles: a list of clips (3 per row)")
        plan["tiles"] = [_clip(x, f"tiles[{k}]", base, check_files) for k, x in enumerate(tiles)]
        heroes = []
        for k, x in enumerate(spec.get("heroes") or []):
            where = f"heroes[{k}]"
            if not isinstance(x, dict):
                raise SpecError(f"{where} must be an object")
            i = int(_num(x.get("tile"), f"{where}.tile", 0, len(tiles) - 1))
            a, b = _when(x, where, "start", None), _when(x, where, "end", None)
            if b <= a:
                raise SpecError(f"{where}: end ({b}) must be after start ({a})")
            if heroes and a < heroes[-1]["b"]:
                raise SpecError(f"{where} starts before the hero before it ends: heroes must follow each other")
            if heroes and b - a < 2.4:
                warn.append(f"{where} lasts {b - a:.1f} s: the dive takes 2.2 s, give a hero 2.4 s or more")
            ss = x.get("ss")
            heroes.append({"i": i, "a": a, "b": b,
                           "ss": _num(ss, f"{where}.ss", lo=0) if ss is not None else None})
        if heroes and heroes[0]["a"] > 0.5:
            warn.append("the camera opens inside the first hero tile: start heroes[0] at 0")
        plan["heroes"] = heroes

    # text
    title = spec.get("title")
    if isinstance(title, str):
        title = {"text": title}
    if title is not None and not isinstance(title, dict):
        raise SpecError("title must be a string or {text, sub, start, end, size}")
    if title and _text(title.get("text")):
        t = {"text": _text(title.get("text"))}
        if _text(title.get("sub")):
            t["sub"] = _text(title.get("sub"))
        for k in ("start", "end", "size", "y"):
            if title.get(k) is not None:
                t[k] = _num(title[k], f"title.{k}", lo=0)
        if title.get("font") is not None:
            if title["font"] not in FONTS:
                raise SpecError(f"title.font must be one of {', '.join(FONTS)}")
            t["font"] = title["font"]
        plan["title"] = t
    else:
        plan["title"] = None
    lines = spec.get("lines") or []
    if not isinstance(lines, list):
        raise SpecError("lines must be a list")
    plan["lines"] = [_line(x, f"lines[{k}]", grid) for k, x in enumerate(lines)]
    if style == "wall" and plan["title"]:  # the wall's title is its first line, in gold Ruqaa
        t = plan["title"]
        plan["lines"].insert(0, {"t": t["text"], "s": t.get("start", 1.2), "e": t.get("end", 4.0),
                                 "font": t.get("font", "Ruqaa"), "size": t.get("size", 120), "gold": True})
        plan["title"] = None
    if style == "beat" and plan["title"]:
        warn.append("the beat style has no title slot: put the name in slams instead (title ignored)")
        plan["title"] = None
    plan["slams"] = [_timed(x, f"slams[{k}]", grid) for k, x in enumerate(spec.get("slams") or [])] if style == "beat" else []
    if style != "chapters":
        used = [k for k in CHAPTER_ONLY if spec.get(k)]
        if used:
            raise SpecError(f"{', '.join(used)} {'are' if len(used) > 1 else 'is'} drawn only by the chapters style: "
                            f"with style {style} {'they' if len(used) > 1 else 'it'} would never show (use style chapters, "
                            f"or lines)")
    if style == "chapters":
        plan["chapters"] = []
        for k, x in enumerate(spec.get("chapters") or []):
            where = f"chapters[{k}]"
            if not isinstance(x, dict):
                raise SpecError(f"{where} must be an object")
            c = {"n": _text(x.get("n", x.get("num"))), "t": _text(x.get("t", x.get("title", x.get("text")))),
                 "s": _when(x, where, "start", None)}
            if not c["t"]:
                raise SpecError(f"{where}.title is required")
            if x.get("d", x.get("dur")) is not None:
                c["d"] = _num(x.get("d", x.get("dur")), f"{where}.dur", 0.5, 30)
            plan["chapters"].append(c)
        plan["verses"] = [_timed(x, f"verses[{k}]", None, extra=("u",)) for k, x in enumerate(spec.get("verses") or [])]
        for k, (v, x) in enumerate(zip(plan["verses"], spec.get("verses") or [])):
            if isinstance(x, dict) and x.get("ref") and "u" not in v:
                v["u"] = _text(x["ref"])
        plan["lyrics"] = [_timed(x, f"lyrics[{k}]", None, extra=("y",)) for k, x in enumerate(spec.get("lyrics") or [])]
        plan["labels"] = [_card(x, f"labels[{k}]", "sub") for k, x in enumerate(spec.get("labels") or [])]
        plan["lowers"] = [_card(x, f"lowers[{k}]", "kicker") for k, x in enumerate(spec.get("lowers") or [])]

    # end card
    end = spec.get("end", {})
    if end is None:
        plan["end"] = None
    else:
        if not isinstance(end, dict):
            raise SpecError("end must be {at, title, sub, sub2, flag} or null")
        tail = 4.1 if style == "medal" else 3.0  # medal: 0.7 s shrink, the medal lands, then the end title and credit
        at_default = end_default if end_default is not None else (dur - tail if dur >= 2 * tail else round(dur * 0.75, 3))
        e = {"at": _num(end.get("at"), "end.at", 0, dur, default=at_default)}
        for k in ("title", "sub", "sub2"):
            if _text(end.get(k)):
                e[k] = _text(end.get(k))
        if end.get("size") is not None:
            e["size"] = _num(end["size"], "end.size", 12, 400)
        if end.get("flag"):
            e["flag"] = True
        plan["end"] = e

    # knobs
    knobs = {}
    for k, d in STYLES[style]["knobs"].items():
        v = spec.get(k, d)
        if isinstance(d, bool):
            v = bool(v)
        elif isinstance(d, (int, float)) and v is not None:
            v = _num(v, k, 0)
        knobs[k] = v
    if spec.get("cache") is not None:
        knobs["cache"] = int(_num(spec["cache"], "cache", 1, 16))
    if style == "wall":
        knobs["cols"] = int(knobs["cols"]) or 3
        knobs["loop"] = _num(knobs["loop"], "loop", 0.5, 10)
    plan["knobs"] = knobs

    _lint(plan, warn)
    plan["fonts"] = _fonts_needed(plan)
    plan.pop("_measure", None)
    return plan


TOP_KEYS = {"style", "duration", "fps", "name", "watermark", "credit", "song", "shots", "title", "lines", "end", "cache",
            "beat", "slams", "tiles", "heroes", "chapters", "verses", "lyrics", "labels", "lowers", "requirements"}
SHOT_KEYS = {"src", "ss", "start", "end", "focus", "box", "zoom", "speed", "broll", "beats", "rest", "tri", "move", "at",
             "fill", "covers"}
CHAPTER_ONLY = ("chapters", "verses", "lyrics", "labels", "lowers")


def _unknown_keys(spec, warn):
    """Typos ('duraton', 'foucs') would be ignored silently: name them. Keys that start with '_' are notes."""
    knobs = {k for s in STYLES.values() for k in s["knobs"]}
    for k in spec:
        if not k.startswith("_") and k not in TOP_KEYS | knobs:
            warn.append(f"unknown field '{k}' (ignored)")
    clips = list(spec.get("shots") or []) + list(spec.get("tiles") or [])
    for x in list(clips):
        if isinstance(x, dict) and isinstance(x.get("tri"), list):
            clips += x["tri"]
    bad = sorted({k for x in clips if isinstance(x, dict) for k in x if not k.startswith("_") and k not in SHOT_KEYS})
    if bad:
        warn.append(f"unknown shot field(s) {', '.join(bad)} (ignored)")


def _card(x, where, sub_key):
    item = _timed(x, where, None, extra=("u",))
    if isinstance(x, dict) and x.get(sub_key) and "u" not in item:
        item["u"] = _text(x[sub_key])
    return item


def _medal_checks(shots, spec, dur, warn):
    moves = [s.get("move") for s in shots]
    for k in range(1, len(shots)):
        if moves[k - 1] == "flip" and moves[k] == "iris":
            raise SpecError(f"shots[{k}].move: after a 'flip' the card has to open again with 'flood' (or flip on)")
    if moves and moves[-1] == "flip":
        raise SpecError("medal: the last move is 'flip', so the card never opens: end the flips with a 'flood'")
    end = spec.get("end") or {}
    last_at = max((s.get("at", s["st"]) for s in shots[1:]), default=shots[0]["st"] if shots else 0)
    if end.get("at") is not None and float(end["at"]) < last_at + 0.9:
        warn.append(f"end.at ({end['at']}) comes less than 0.9 s after the last move: it cuts the move short")
    if shots and shots[0]["st"] < 0.5:
        warn.append("the first shot starts before 0.5 s: the medal has almost no time to drop")


def _texts(plan):
    out = []
    if plan.get("title"):
        out += [plan["title"].get("text", ""), plan["title"].get("sub", "")]
    for key in ("lines", "slams", "verses", "lyrics", "labels", "lowers", "chapters"):
        for q in plan.get(key) or []:
            out += [q.get("t", ""), q.get("u", ""), q.get("n", "")]
    if plan.get("end"):
        out += [plan["end"].get(k, "") for k in ("title", "sub", "sub2")]
    return [t for t in out if t]


def _lint(plan, warn):
    style = plan["style"]
    # Lalezar has no '…' glyph and draws '.': use the Arabic comma instead
    lalezar = list(plan.get("slams") or []) + [q for q in plan["lines"] if q.get("font") == "Lalezar"]
    fixed = 0
    for q in lalezar:
        if "…" in q["t"]:
            q["t"] = q["t"].replace("…", "،")
            fixed += 1
    if style == "beat" and plan.get("end") and "…" in plan["end"].get("title", ""):
        plan["end"]["title"] = plan["end"]["title"].replace("…", "،")
        fixed += 1
    if fixed:
        warn.append(f"Lalezar has no '…' glyph (it draws '.'): replaced it with '،' in {fixed} text(s)")
    for t in _texts(plan):
        if re.search(f"·\\s*[{ARABIC_DIGITS}]|[{ARABIC_DIGITS}]\\s*·", t):
            warn.append(f"'·' next to Arabic digits reads as a zero («١١ · سنة» -> «١١٠»): use '،' in «{t}»")
        if style != "chapters" and any(w in t for w in EXPLAINER_WORDS):
            warn.append(f"«{t}» reads as an explainer chapter: the owner turned that look down for cinematic films")
    if style == "chapters" and plan["knobs"].get("numbers") and any(c.get("n") for c in plan.get("chapters", [])):
        warn.append("numbered chapter cards: the owner turned them down for cinematic films (2026-11-04/05/08); "
                    'keep them only when he asks for chapters, otherwise set "numbers": false')
    if style == "nil" and plan["knobs"].get("leak"):
        warn.append("leak is on: the owner removed sun / light-leak washes from his films on 2026-11-01")


def _fonts_needed(plan):
    fams = list(STYLES[plan["style"]]["fonts"])
    for q in plan["lines"]:
        if q.get("font") and q["font"] not in fams:
            fams.append(q["font"])
    if plan.get("title") and plan["title"].get("font") and plan["title"]["font"] not in fams:
        fams.append(plan["title"]["font"])
    if plan.get("verses") and "Scheherazade" not in fams:
        fams.append("Scheherazade")
    return fams


# ---------------------------------------------------------------- frames

def _jobs(plan):
    """One ffmpeg cut per shot, tile and hero: (key, clip, seconds to cut, size, fps, quality)."""
    fps = plan["fps"]
    jobs = []
    for k, s in enumerate(plan["shots"]):
        jobs.append({"key": f"S{k:02d}", "clip": s, "len": s["en"] - s["st"] + TAIL_PAD, "size": (W, H), "fps": fps,
                     "q": 5, "where": s.get("where", f"shots[{k}]")})
    if plan["style"] == "wall":
        loop = plan["knobs"]["loop"]
        for k, s in enumerate(plan["tiles"]):
            jobs.append({"key": f"T{k:02d}", "clip": s, "len": loop + 0.1, "size": TILE_SIZE, "fps": TILE_FPS,
                         "q": TILE_Q, "where": f"tiles[{k}]"})
        for k, h in enumerate(plan["heroes"]):
            clip = dict(plan["tiles"][h["i"]])
            if h["ss"] is not None:
                clip["ss"] = h["ss"]
            jobs.append({"key": f"H{k:02d}", "clip": clip, "len": (h["b"] + 0.8 - h["a"]) + TAIL_PAD, "size": (W, H),
                         "fps": fps, "q": 5, "where": f"heroes[{k}]"})
    return jobs


def extract(job, frames_dir, force=False):
    """Cut one clip into numbered JPEG frames; reuses the folder when the same cut was made before."""
    c = job["clip"]
    src = Path(c["src"])
    d = frames_dir / job["key"]
    sw, sh = source_size(src)
    cw, ch, cx, cy, fy = crop_rect(sw, sh, c["focus"], c["box"], c["zoom"])
    st = src.stat()
    params = {"src": str(src.resolve()), "mtime": int(st.st_mtime), "bytes": st.st_size, "ss": round(c["ss"], 3),
              "len": round(job["len"], 3), "size": list(job["size"]), "fps": job["fps"], "q": job["q"],
              "crop": [cw, ch, cx, cy], "speed": round(c["speed"], 4)}
    stamp = d / "cut.json"
    have = sorted(d.glob("f*.jpg")) if d.is_dir() else []
    if not force and have and stamp.is_file():
        try:
            if json.loads(stamp.read_text(encoding="utf-8")) == params:
                return {"n": len(have), "fy": fy, "reused": True, "crop_h": ch, "wide": sw > sh}
        except ValueError:
            pass
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    vf = (f"crop={cw}:{ch}:{cx}:{cy},scale={job['size'][0]}:{job['size'][1]}:flags=lanczos,setsar=1,"
          f"setpts={1 / c['speed']:.6f}*PTS,fps={job['fps']}")
    if src.suffix.lower() in IMAGE_EXT:
        inp = ["-loop", "1", "-framerate", str(job["fps"]), "-i", src]
    else:
        inp = ["-ss", f"{c['ss']:.3f}", "-i", src]
    run([exe("ffmpeg"), "-nostdin", "-hide_banner", "-v", "error", "-y", *inp, "-map", "0:v:0", "-an", "-vf", vf,
         "-t", f"{job['len']:.3f}", "-q:v", job["q"], d / "f%04d.jpg"], f"ffmpeg cut of {job['where']} ({src.name})")
    n = len(list(d.glob("f*.jpg")))
    if not n:
        raise BuildError(f"no frames from {src} at {c['ss']} s ({job['where']}): is the in-point past the end of the clip?")
    stamp.write_text(json.dumps(params, ensure_ascii=False), encoding="utf-8")
    return {"n": n, "fy": fy, "reused": False, "crop_h": ch, "wide": sw > sh}


def cut_all(plan, out, force=False, log=print):
    frames = out / "frames"
    frames.mkdir(parents=True, exist_ok=True)
    jobs = _jobs(plan)
    with cf.ThreadPoolExecutor(max_workers=max(1, min(4, os.cpu_count() or 2))) as pool:
        got = list(pool.map(lambda j: extract(j, frames, force), jobs))
    keep = {j["key"] for j in jobs}
    for d in frames.iterdir():  # folders of shots that left the spec
        if d.is_dir() and d.name not in keep and re.fullmatch(r"[STH]\d{2}", d.name):
            shutil.rmtree(d)
    rows = []
    for j, r in zip(jobs, got):
        need = round(j["len"] - TAIL_PAD, 3)
        held = max(0.0, need - r["n"] / j["fps"]) if j["key"][0] != "T" else 0.0
        rows.append({"key": j["key"], "where": j["where"], "src": str(j["clip"]["src"]), "frames": r["n"], "fy": r["fy"],
                     "reused": r["reused"], **({"held_s": round(held, 2)} if held > 0.05 else {})})
        if held > 0.05:
            plan["warnings"].append(f"{j['where']}: the clip runs out {held:.1f} s early (its last frame is held)")
        if j["key"][0] != "T" and r.get("crop_h") and r["crop_h"] < 1280:
            plan["warnings"].append(f"{j['where']}: only {r['crop_h']} px tall after the 9:16 crop: upscaled "
                                    f"{1920 / r['crop_h']:.1f}x (soft); use a bigger source or a blurred-background frame")
        elif r.get("wide") and j["key"][0] != "T" and tuple(j["clip"]["focus"]) == (0.5, 0.42) and not j["clip"].get("box"):
            plan["warnings"].append(f"{j['where']}: a landscape picture cut to a 9:16 strip around the centre: set "
                                    f"focus on the subject (or box)")
    log(f"FRAMES {len(jobs)} cuts, {sum(r['frames'] for r in rows)} frames ({sum(r['reused'] for r in rows)} reused)")
    return rows


# ---------------------------------------------------------------- page

PAGE = """<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8"><title>{title}</title>
<style>
{faces}
html,body{{margin:0;background:#000;overflow:hidden}}canvas{{display:block}}
</style></head><body>
<canvas id="c" width="1080" height="1920"></canvas>
<script>window.CFG={cfg};</script>
<script src="common.js"></script>
<script src="{style}.js"></script>
</body></html>
"""


def page_cfg(plan, rows):
    by = {r["key"]: r for r in rows}
    fps = plan["fps"]
    shots = []
    for k, s in enumerate(plan["shots"]):
        r = by[f"S{k:02d}"]
        sh = {"d": f"frames/S{k:02d}", "n": r["frames"], "st": round(s["st"], 4), "en": round(s["en"], 4),
              "fy": r["fy"], "fps": fps}
        if s.get("broll"):
            sh["broll"] = True
        for key in ("move", "at", "fill"):
            if key in s:
                sh[key] = s[key]
        shots.append(sh)
    cfg = {"style": plan["style"], "duration": plan["duration"], "fps": fps, "watermark": plan["watermark"],
           "credit": plan["credit"], "fonts": [[f, FONTS[f][1]] for f in plan["fonts"]], "shots": shots,
           "title": plan["title"], "lines": plan["lines"], "end": plan["end"], **plan["knobs"]}
    if plan["style"] == "beat":
        cfg.update(beat=plan["beat"], tri=plan["tri"], slams=plan["slams"])
    if plan["style"] == "wall":
        loop = plan["knobs"]["loop"]
        cfg["tiles"] = [{"d": f"frames/T{k:02d}", "n": by[f"T{k:02d}"]["frames"], "st": 0, "en": loop,
                         "fy": by[f"T{k:02d}"]["fy"], "fps": TILE_FPS} for k in range(len(plan["tiles"]))]
        cfg["heroes"] = [{"i": h["i"], "a": h["a"], "b": h["b"],
                          "s": {"d": f"frames/H{k:02d}", "n": by[f"H{k:02d}"]["frames"], "st": h["a"],
                                "en": round(h["b"] + 0.8, 4), "fy": by[f"H{k:02d}"]["fy"], "fps": fps}}
                         for k, h in enumerate(plan["heroes"])]
    if plan["style"] == "chapters":
        for key in ("chapters", "verses", "lyrics", "labels", "lowers"):
            cfg[key] = plan[key]
    return cfg


def write_page(plan, rows, out, embed=False):
    """index.html + common.js + <style>.js (+ fonts/ unless embedded) in `out`."""
    style = plan["style"]
    shutil.copyfile(HERE / "common.js", out / "common.js")
    shutil.copyfile(STYLES_DIR / f"{style}.js", out / f"{style}.js")
    faces = []
    for fam in plan["fonts"]:
        fname, weight = FONTS[fam]
        src = FONTS_DIR / fname
        if not src.is_file():
            raise BuildError(f"font missing from the kit: {src}")
        if embed:
            url = "data:font/ttf;base64," + base64.b64encode(src.read_bytes()).decode("ascii")
        else:
            (out / "fonts").mkdir(exist_ok=True)
            dst = out / "fonts" / fname
            if not dst.is_file() or dst.stat().st_size != src.stat().st_size:
                shutil.copyfile(src, dst)
            url = f"fonts/{fname}"
        faces.append(f"@font-face{{font-family:{fam};src:url({url});font-weight:{weight}}}")
    cfg = json.dumps(page_cfg(plan, rows), ensure_ascii=False).replace("</", "<\\/")
    text = PAGE.format(title=html.escape(plan["name"]), faces="\n".join(faces), cfg=cfg, style=style)
    (out / "index.html").write_text(text, encoding="utf-8")
    return out / "index.html"


# ---------------------------------------------------------------- audio

def _lufs(path):
    try:
        from dragon.verify import loudness
        return loudness(path).get("loudness_lufs")
    except Exception:
        return None


def _audio_md5(path):
    r = run([exe("ffmpeg"), "-nostdin", "-v", "error", "-i", path, "-map", "0:a:0", "-c", "copy", "-f", "md5", "-"],
            "ffmpeg audio md5")
    return (r.stdout or "").strip().replace("MD5=", "")


def copy_song(song, out_m4a, log=print):
    """song.copy: the AAC song stream copied as it is (no fades, no loudnorm), MD5 of the audio packets checked; the
    exact-length mux then cuts it at a packet edge (engines.deliver.mux copies AAC that is long enough)."""
    src = Path(song["path"])
    probe = run([exe("ffprobe"), "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=codec_name", "-of",
                 "csv=p=0", src], "ffprobe song codec")
    codec = (probe.stdout or "").strip().splitlines()[0] if (probe.stdout or "").strip() else ""
    if codec != "aac":
        raise BuildError(f"song.copy needs an AAC song (.m4a), this one is {codec or 'unknown'}: drop copy (it is "
                         f"re-encoded once to AAC 320k) or convert it yourself")
    if song["start"]:
        run([exe("ffmpeg"), "-nostdin", "-hide_banner", "-v", "error", "-y", "-ss", f"{song['start']:.3f}", "-i", src,
             "-vn", "-map", "0:a:0", "-c:a", "copy", out_m4a], "ffmpeg song copy")
        same = None
        log("MIX copy from song.start: packets copied, no MD5 claim (the head was cut)")
    else:
        run([exe("ffmpeg"), "-nostdin", "-hide_banner", "-v", "error", "-y", "-i", src, "-vn", "-map", "0:a:0",
             "-c:a", "copy", out_m4a], "ffmpeg song copy")
        same = _audio_md5(src) == _audio_md5(out_m4a)
        log(f"MIX copy {out_m4a.name}: audio packets MD5 {'identical' if same else 'DIFFERENT'}")
    lufs = _lufs(out_m4a)
    return {"out": str(out_m4a), "reused": False, "mode": "copy", "md5_identical": same, "lufs_before": lufs,
            "lufs_after": lufs}


def mix_song(song, duration, out_m4a, log=print):
    """Song section [start, start + duration]: square-root fade in, linear fade out, loudnorm -14 LUFS (true peak -1.5)
    unless song.normalize is false, padded / cut to exactly `duration`, AAC 320k 48 kHz. Reused when the same mix was
    made before. song.copy: copy_song (byte copy, no fades). The report keeps the LUFS before and after."""
    if song.get("copy"):
        return copy_song(song, out_m4a, log=log)
    params = {"path": str(Path(song["path"]).resolve()), "start": song["start"], "fade_in": song["fade_in"],
              "fade_out": song["fade_out"], "duration": duration, "bytes": Path(song["path"]).stat().st_size,
              "normalize": song.get("normalize", True)}
    stamp = out_m4a.with_suffix(".json")
    if out_m4a.is_file() and stamp.is_file():
        try:
            if json.loads(stamp.read_text(encoding="utf-8")) == params:
                log(f"MIX reused {out_m4a.name}")
                return {"out": str(out_m4a), "reused": True}
        except ValueError:
            pass
    fi, fo = min(song["fade_in"], duration / 2), min(song["fade_out"], duration / 2)
    af = []
    if fi > 0:
        af.append(f"afade=t=in:st=0:d={fi:.3f}:curve=squ")
    if fo > 0:
        af.append(f"afade=t=out:st={duration - fo:.3f}:d={fo:.3f}")
    af += (["loudnorm=I=-14:TP=-1.5:LRA=11"] if song.get("normalize", True) else []) + [
        "aresample=48000", f"apad=whole_dur={duration:.3f}", f"atrim=0:{duration:.3f}"]
    run([exe("ffmpeg"), "-nostdin", "-hide_banner", "-v", "error", "-y", "-ss", f"{song['start']:.3f}",
         "-t", f"{duration + 0.5:.3f}", "-i", song["path"], "-vn", "-af", ",".join(af), "-ac", "2", "-c:a", "aac",
         "-b:a", "320k", "-ar", "48000", out_m4a], "ffmpeg song mix")
    stamp.write_text(json.dumps(params, ensure_ascii=False), encoding="utf-8")
    have = media_seconds(song["path"])
    if have and have < song["start"] + duration - 0.05:
        log(f"MIX note: the song ends at {have:.1f} s, before {song['start'] + duration:.1f} s; the rest is silence")
    before, after = _lufs(song["path"]), _lufs(out_m4a)
    log(f"MIX {out_m4a.name} {duration:.3f} s, LUFS {before} -> {after}"
        + ("" if song.get("normalize", True) else " (normalize off)"))
    return {"out": str(out_m4a), "reused": False, "mode": "normalize" if song.get("normalize", True) else "encode",
            "lufs_before": before, "lufs_after": after}


# ---------------------------------------------------------------- render

def find_renderer(explicit=None):
    cands = [explicit, os.environ.get("DRAGON_RENDERER")] + [d / "engines" / "render" / "render.cjs" for d in APP_DIRS]
    for c in cands:
        if c and Path(c).is_file():
            return Path(c)
    raise BuildError("render.cjs not found (app/engines/render/render.cjs); pass --renderer PATH")


def renderer_flags(path):
    """Options the renderer documents in its header (its help text): read, not guessed."""
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    return set(re.findall(r"--([a-z][a-z-]+)", text))


def _node_env():
    env = dict(os.environ)
    try:  # render.cjs spawns plain `ffmpeg`: make sure the one we use is on PATH (winget installs are not)
        ff_dir = str(Path(exe("ffmpeg")).parent)
        if ff_dir not in env.get("PATH", "").split(os.pathsep):
            env["PATH"] = ff_dir + os.pathsep + env.get("PATH", "")
    except BuildError:
        pass
    return env


def run_node(args, log_file):
    node = shutil.which("node")
    if not node:
        raise BuildError("node not found: install Node.js (Windows: winget install -e --id OpenJS.NodeJS.LTS)")
    r = subprocess.run([node, *map(str, args)], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=_node_env())
    text = (r.stdout or "") + (r.stderr or "")
    log_file.write_text(text, encoding="utf-8")
    errors = [ln.strip() for ln in text.splitlines() if "[page error]" in ln]
    return r, text, errors


def render_stills(index, times, fps, renderer, out, log=print):
    sdir = out / "stills"
    sdir.mkdir(exist_ok=True)
    r, text, errors = run_node([renderer, "--in", index, "--stills", ",".join(f"{t:g}" for t in times),
                                "--stills-dir", sdir, "--fps", fps], out / "stills.log")
    if r.returncode:
        raise BuildError(f"stills failed: {text.strip()[-600:]}")
    files = [sdir / f"still_{t:.3f}.png" for t in times]
    missing = [str(f) for f in files if not f.is_file()]
    if missing:
        raise BuildError(f"stills missing: {missing}")
    log(f"STILLS {len(files)} -> {sdir}")
    return {"files": [str(f) for f in files], "page_errors": errors}


def render_film(index, plan, renderer, video, out, recycle=RECYCLE, log=print):
    args = [renderer, "--in", index, "--out", video, "--fps", plan["fps"], "--duration", f"{plan['duration']:.3f}"]
    flags = renderer_flags(renderer)
    if "recycle" in flags and recycle:
        args += ["--recycle", int(recycle)]
    log(f"RENDER {plan['duration']:.2f} s at {plan['fps']} fps ({round(plan['duration'] * plan['fps'])} frames)...")
    r, text, errors = run_node(args, out / "render.log")
    if r.returncode not in (0, 3) or not Path(video).is_file():
        raise BuildError(f"render failed: {text.strip()[-800:]}")
    summary = {}
    for ln in text.splitlines():
        if ln.startswith("SUMMARY "):
            summary = dict(kv.split("=", 1) for kv in ln.split()[1:] if "=" in kv)
    log(f"RENDER done: {summary or 'no summary line'}")
    return {"video": str(video), "summary": summary, "page_errors": errors,
            "recycle": "--recycle" in map(str, args)}


def black_check(video, plan, out, log=print):
    """Scan for black runs inside the film (engines.qa) and clone the last good frame over them (engines.deliver)."""
    try:
        from engines import qa, deliver
    except Exception as e:
        return {"skipped": f"engines.qa / engines.deliver not importable: {e}"}
    k = min(1.0, plan["duration"] / getattr(deliver, "SHORT_CLIP_S", 6.0))
    scan = qa.black_runs(video, allow_head=round(0.6 * k, 3), allow_tail=round(1.5 * k, 3))
    res = {"frames": scan.get("frames"), "body_runs": scan.get("body", []), "edge_runs": len(scan.get("edge", []))}
    if not res["body_runs"]:
        log(f"QA no black frames inside the film ({res['frames']} frames scanned)")
        return {**res, "patched": False, "ok": True}
    long_runs = [r for r in res["body_runs"] if int(r.get("frames") or 0) > PATCH_MAX_FRAMES]
    if long_runs:   # QA §4: a long black run is a render fault: render those seconds again, never freeze them
        for r in long_runs:
            log(f"BLACK_RERENDER t={float(r['start']):.3f}-{float(r['end']):.3f} ({r.get('frames')} frames): render "
                f"these seconds again (render.cjs --start), a freeze of this length would show")
        return {**res, "patched": False, "patched_frames": 0, "rerender": long_runs, "ok": False}
    fixed = out / "video_patched.mp4"
    pr = deliver.patch_black(video, fixed)
    os.replace(fixed, video)
    res.update(patched=True, patched_frames=pr.get("patched_frames"), remaining=pr.get("remaining", []),
               ok=bool(pr.get("ok")))
    log(f"QA patched {pr.get('patched_frames')} black frame(s) with the previous good frame; left: {len(res['remaining'])}")
    return res


def mux_film(video, audio, final, plan, log=print):
    """Exact-length mux: engines.deliver.mux when it can be imported, else ffmpeg without -shortest."""
    try:
        from engines import deliver
    except Exception:
        deliver = None
    if deliver:
        r = deliver.mux(video, audio, final, duration=plan["duration"])
        keep = ("out", "frames", "expected_frames", "fps", "duration_s", "video_mode", "audio_codec", "audio_mode",
                "audio_source_codec", "audio_s", "ok")
        res = {k: r.get(k) for k in keep}
        res["via"] = "engines.deliver.mux"
    else:
        n = round(plan["duration"] * plan["fps"])
        run([exe("ffmpeg"), "-nostdin", "-hide_banner", "-v", "error", "-y", "-i", video, "-t", f"{plan['duration']:.6f}",
             "-i", audio, "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "copy", "-frames:v", n,
             "-movflags", "+faststart", final], "ffmpeg mux")
        res = {"out": str(final), "expected_frames": n, "via": "ffmpeg", "ok": Path(final).is_file()}
    log(f"MUX {'ok' if res.get('ok') else 'FAILED'} -> {final} ({res.get('frames', res.get('expected_frames'))} frames, "
        f"audio {res.get('audio_codec', 'aac')})")
    return res


# ---------------------------------------------------------------- build

def load_spec(path):
    p = Path(path)
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise SpecError(f"spec not found: {p}")
    except ValueError as e:
        raise SpecError(f"{p.name} is not valid JSON: {e}")


def build(spec_path, out, stills=None, render=False, embed_fonts=False, force=False, tidy=False, renderer=None,
          recycle=RECYCLE, log=print):
    """Spec -> frames + page (+ mix) (+ stills) (+ film). Returns the build report (also written to out/build_report.json)."""
    spec_path = Path(spec_path).resolve()
    spec = load_spec(spec_path)
    plan = normalise(spec, spec_path.parent)
    if not _text(spec.get("name")):
        plan["name"] = _safe_name(spec_path.stem)
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    for w in plan["warnings"]:
        log(f"WARN {w}")
    if stills:
        bad = [t for t in stills if not 0 <= t <= plan["duration"]]
        if bad:
            raise SpecError(f"--stills {bad} outside the film (0..{plan['duration']} s)")
    report = {"spec": str(spec_path), "style": plan["style"], "duration": plan["duration"], "fps": plan["fps"],
              "out": str(out), "warnings": plan["warnings"], "ok": True}
    try:
        rows = cut_all(plan, out, force=force, log=log)
        report["cuts"] = rows
        index = write_page(plan, rows, out, embed=embed_fonts)
        report["page"] = str(index)
        log(f"PAGE {index}")
        mix = None
        if plan["song"]:
            report["mix"] = mix_song(plan["song"], plan["duration"], out / "mix.m4a", log=log)
            mix = out / "mix.m4a"
        if stills or render:
            rend = find_renderer(renderer)
            report["renderer"] = str(rend)
        if stills:
            report["stills"] = render_stills(index, stills, plan["fps"], rend, out, log=log)
            if report["stills"]["page_errors"]:
                report["ok"] = False
                log(f"FAIL page errors: {report['stills']['page_errors'][:3]}")
        if render:
            video = out / "video.mp4"
            report["render"] = render_film(index, plan, rend, video, out, recycle=recycle, log=log)
            if report["render"]["page_errors"]:
                report["ok"] = False
                log(f"FAIL page errors: {report['render']['page_errors'][:3]}")
            report["qa"] = black_check(video, plan, out, log=log)
            if report["qa"].get("ok") is False:
                report["ok"] = False
            final = out / f"{plan['name']}.mp4"
            if mix:
                report["mux"] = mux_film(video, mix, final, plan, log=log)
                report["ok"] = report["ok"] and bool(report["mux"].get("ok"))
                if tidy and report["mux"].get("ok"):
                    video.unlink(missing_ok=True)
            else:
                os.replace(video, final)
                log("MUX skipped: no song in the spec (silent film)")
            report["final"] = str(final)
            if tidy and report["ok"]:
                shutil.rmtree(out / "frames", ignore_errors=True)
            log(f"FINAL {final}")
    except SpecError:
        raise
    except (BuildError, RuntimeError, ValueError, OSError, subprocess.SubprocessError) as e:
        report.update(ok=False, error=f"{e}" if isinstance(e, BuildError) else f"{type(e).__name__}: {e}")
        log(f"FAIL {report['error']}")
    (out / "build_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return report


def _times(text):
    try:
        ts = [float(x) for x in text.split(",") if x.strip()]
    except ValueError:
        raise argparse.ArgumentTypeError(f"stills must be seconds separated by commas, got {text!r}")
    if not ts:
        raise argparse.ArgumentTypeError("--stills needs at least one time")
    return ts


def list_styles():
    lines = []
    for name, s in STYLES.items():
        lines.append(f"{name:9s} {s['about']}")
        lines.append(f"{'':9s} fonts: {', '.join(s['fonts'])}; knobs: " +
                     ", ".join(f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in s["knobs"].items()))
    return "\n".join(lines)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(prog="build_style.py", description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="examples: tools/styles/examples/*.json   docs: tools/styles/README.md")
    ap.add_argument("spec", nargs="?", help="the film spec (JSON)")
    ap.add_argument("--out", help="build folder (frames, page, mix, stills, film)")
    ap.add_argument("--stills", type=_times, help="render PNG stills at these seconds, e.g. 1.5,6,12")
    ap.add_argument("--render", action="store_true", help="render the film and mux it with the song")
    ap.add_argument("--check", action="store_true", help="validate the spec only (exit 2 on an error)")
    ap.add_argument("--allow-missing", action="store_true",
                    help="with --check: a template; missing files and example placeholders are warnings")
    ap.add_argument("--list", action="store_true", help="list the styles and their knobs")
    ap.add_argument("--embed-fonts", action="store_true", help="put the fonts inside index.html (one portable page)")
    ap.add_argument("--force", action="store_true", help="cut every frame again even when the cut is unchanged")
    ap.add_argument("--tidy", action="store_true", help="after a good film: delete frames/ and the silent video.mp4")
    ap.add_argument("--renderer", help="path to render.cjs (default: the skill's app/engines/render/render.cjs)")
    ap.add_argument("--recycle", type=int, default=RECYCLE, help=f"page reload every N frames (default {RECYCLE})")
    a = ap.parse_args(argv)
    if a.list:
        print(list_styles())
        return 0
    if not a.spec:
        ap.print_usage()
        return 2
    try:
        if a.check:
            spec_path = Path(a.spec).resolve()
            spec = load_spec(spec_path)
            plan = normalise(spec, spec_path.parent, check_files=False)
            for w in plan["warnings"]:
                print(f"WARN {w}")
            errors, warns = check_spec(spec, plan, allow_missing=a.allow_missing)
            for w in warns:
                print(w if w.startswith("MISSING ") else f"WARN {w}")
            for e in errors:
                print(e if e.startswith("MISSING ") else f"ERROR {e}")
            missing = [x for x in errors + warns if x.startswith("MISSING ")]
            what = (f"{len(plan['tiles'])} tiles, {len(plan['heroes'])} heroes" if plan["style"] == "wall"
                    else f"{len(plan['shots'])} shots")
            print(f"{'FAILED' if errors else 'OK'} {plan['style']} spec: {what}, {plan['duration']} s"
                  + (f", {len(missing)} file(s) missing" if missing else "")
                  + (f", {len(errors)} error(s)" if errors else ""))
            return 2 if errors else 0
        if not a.out:
            print("--out DIR is required to build", file=sys.stderr)
            return 2
        rep = build(a.spec, a.out, stills=a.stills, render=a.render, embed_fonts=a.embed_fonts, force=a.force,
                    tidy=a.tidy, renderer=a.renderer, recycle=a.recycle)
    except SpecError as e:
        print(f"SPEC ERROR {e}", file=sys.stderr)
        return 2
    except BuildError as e:
        print(f"BUILD ERROR {e}", file=sys.stderr)
        return 1
    print(("OK " if rep["ok"] else "FAILED ") + str(Path(a.out) / "build_report.json"))
    return 0 if rep["ok"] else 1


BANS_FILE = HERE / "bans.json"
CREDIT_HOLD = 2.5                                # the credit must stay on screen at least this long
TEXT_BOTTOM = 1700                               # y + size/2 below this collides with the credit / TikTok UI
CHAPTER_SHOW = 2.6                               # chapters.js shows a chapter card this long when dur is not given


def _placeholders():
    """Every text of the kit's own examples: left in a real spec they are template leftovers."""
    out = set()
    for f in sorted((HERE / "examples").glob("*.json")):
        try:
            sp = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        t = sp.get("title")
        out |= {_text(t.get(k)) for k in ("text", "sub") if isinstance(t, dict)} if isinstance(t, dict) else {_text(t)}
        for key in ("lines", "verses", "lyrics", "labels", "lowers"):     # not chapter titles: «البداية» is real text
            for x in sp.get(key) or []:
                if isinstance(x, dict):
                    out |= {_text(x.get(k)) for k in ("text", "t", "title", "sub", "kicker", "ref")}
        e = sp.get("end") or {}
        if isinstance(e, dict):
            out |= {_text(e.get(k)) for k in ("title", "sub", "sub2")}
    return {x for x in out if x}


def _bans():
    try:
        return json.loads(BANS_FILE.read_text(encoding="utf-8")).get("banned", [])
    except (OSError, ValueError):
        return []


def text_windows(plan):
    """(name, start, end) of every text item the page draws (one text at a time is the owner's «نسّق» rule)."""
    out, dur = [], plan["duration"]
    t = plan.get("title")
    if t and t.get("end") is not None:          # a title without times is placed by the style itself
        out.append(("title", t.get("start", 0.0), t["end"]))
    for c in plan.get("chapters") or []:
        out.append((f"chapter «{c['t']}»", c["s"], c["s"] + c.get("d", CHAPTER_SHOW)))
    for key in ("lines", "verses", "lyrics", "labels", "lowers", "slams"):
        for k, q in enumerate(plan.get(key) or []):
            out.append((f"{key}[{k}]", q["s"], q["e"]))
    if plan.get("end"):
        out.append(("end card", plan["end"]["at"], dur))
    return sorted(out, key=lambda w: (w[1], w[2]))


def check_spec(spec, plan, allow_missing=False):
    """The --check gate (v1.3). Returns (errors, warnings); errors make --check exit 2.
    errors: a requirement no shot or text covers; missing files (unless allow_missing, for templates); ss past the
    clip's end; banned names (bans.json, from LESSONS); a song under Quran verses; leftover example placeholders
    (warnings with allow_missing). warnings: overlapping text windows, a credit on screen under 2.5 s, text below
    y 1700."""
    errors, warns = [], []
    reqs = spec.get("requirements") or []
    if reqs and not isinstance(reqs, list):
        errors.append("requirements must be a list of strings or {id, text}")
        reqs = []
    ids = []
    for k, r in enumerate(reqs):
        ids.append(str(r.get("id", f"r{k + 1}")) if isinstance(r, dict) else f"r{k + 1}")
    covered = set()
    for key in ("shots", "tiles", "lines", "title", "end") + CHAPTER_ONLY:
        v = spec.get(key)
        for x in (v if isinstance(v, list) else [v] if isinstance(v, dict) else []):
            if isinstance(x, dict):
                cv = x.get("covers")
                covered |= {str(c) for c in (cv if isinstance(cv, list) else [cv] if cv is not None else [])}
    for i, r in zip(ids, reqs):
        if i not in covered:
            text = r.get("text") if isinstance(r, dict) else r
            errors.append(f"requirement {i} «{text}» is not covered: add \"covers\": [\"{i}\"] to the shot or text that "
                          f"delivers it")
    missing = sorted({str(f) for f in _spec_files(plan) if not Path(f).is_file()})
    for m in missing:
        (warns if allow_missing else errors).append(f"MISSING {m}")
    for s in list(plan["shots"]) + list(plan.get("tiles") or []):
        if Path(s["src"]).is_file() and Path(s["src"]).suffix.lower() not in IMAGE_EXT:
            have = media_seconds(s["src"])
            need = s["ss"] + (s["en"] - s["st"]) * s.get("speed", 1.0) if "en" in s else s["ss"]
            if have and need > have + 0.05:
                errors.append(f"{s['where']}: ss {s['ss']} + {need - s['ss']:.2f} s runs past the clip's end ({have:.2f} s)")
    texts = _texts(plan)
    for b in _bans():
        word = b.get("text") if isinstance(b, dict) else b
        if word and any(word in t for t in texts):
            errors.append(f"banned on screen: «{word}»" + (f" ({b.get('why')})" if isinstance(b, dict) and b.get("why") else ""))
    left = sorted({t for t in texts if t in _placeholders()})
    for t in left:
        (warns if allow_missing else errors).append(f"example placeholder left in the spec: «{t}»")
    if plan.get("verses") and plan.get("song"):
        errors.append("a song plays under Quran verses: a recitation film has no song (drop song, or the verses)")
    wins = text_windows(plan)
    for (na, a0, a1), (nb, b0, b1) in zip(wins, wins[1:]):
        if b0 < a1 - 0.02:
            warns.append(f"two texts at once: {na} ({a0:g}-{a1:g}) and {nb} ({b0:g}-{b1:g}): one text at a time")
    for i, (na, a0, a1) in enumerate(wins):
        for nb, b0, b1 in wins[i + 2:]:
            if b0 < a1 - 0.02:
                warns.append(f"two texts at once: {na} ({a0:g}-{a1:g}) and {nb} ({b0:g}-{b1:g}): one text at a time")
    e = plan.get("end")
    if e and plan.get("credit"):
        delay = CREDIT_DELAY.get(plan["style"], 1.0)
        start = min(e["at"] + delay, plan["duration"] - 3)
        if plan["duration"] - start < CREDIT_HOLD:
            warns.append(f"the credit shows only {plan['duration'] - start:.1f} s: the film is too short for it")
        elif start < e["at"]:
            warns.append(f"end.at {e['at']:g} + {delay:g} s is too late for the credit (it needs {CREDIT_HOLD:g} s or more): "
                         f"the page pulls it to {start:g} s, before the end card: move end.at to "
                         f"{plan['duration'] - 3 - delay:g} or earlier")
    for q in plan.get("lines") or []:
        if q.get("y") and q["y"] + q.get("size", 50) / 2 > TEXT_BOTTOM:
            warns.append(f"line «{q['t']}» at y {q['y']} size {q.get('size', 50)} goes below y {TEXT_BOTTOM}")
    t = plan.get("title")
    if t and t.get("y") and t["y"] + t.get("size", 100) / 2 > TEXT_BOTTOM:
        warns.append(f"title at y {t['y']} goes below y {TEXT_BOTTOM}")
    return errors, warns


CREDIT_DELAY = {"chapters": 2.0, "clean": 1.0, "nil": 1.0, "beat": 1.6, "wall": 1.4, "medal": 1.4}


def _spec_files(plan):
    files = [s["src"] for s in plan["shots"]] + [t["src"] for t in plan.get("tiles", [])]
    if plan.get("song"):
        files.append(plan["song"]["path"])
    return files


if __name__ == "__main__":
    sys.exit(main())
