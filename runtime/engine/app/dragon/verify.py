"""Measure real outputs before anyone says "done": media, images, text/JSON. Same LUFS method as the old dragon.py
(ffmpeg ebur128 integrated), plus per-stream durations, fps, true peak and delivery warnings.

v1.2: verify is the delivery gate (checks from engines.qa). A file FAILS (ok False, reasons in r["errors"]) when
  * its video has black frames inside the film ("body" runs), or a black run at the start/end too long to be a fade;
  * an MP4/MOV carries audio that phones play silent (MP3 in MP4);
  * the intended `duration` is given and the video does not have exactly round(duration * fps) frames
    (an audio-only file must be within 0.05 s of it).
Warnings never fail a file: loudness outside -16..-12 LUFS, true peak above -1.0 dBTP, a size other than `expect`,
an audio/video length gap, a frame count more than one frame off the container length, a VFR video (its frame count
is not checked), a non-H.264 video inside .mp4.
Short fades from/to black at the very start/end are listed in r["info"].
v1.3: a film whose audio is silent FAILS (integrated loudness below SILENT_LUFS or max_volume at or below SILENT_MAX_DB):
the «من غير صوت» failure. With expect_audio (the CLI default when --duration is given, unless --silent-ok) a video with
no audio stream at all fails too."""
import datetime, json, re, subprocess
from pathlib import Path

MEDIA = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".oga",
         ".opus", ".aiff", ".aif", ".mka", ".avi", ".3gp", ".ts"}
IMAGE = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
TEXT = {".html", ".md", ".txt", ".json", ".srt", ".vtt", ".ass"}

TRUE_PEAK_MAX = -1.0                 # owner standard, dBTP
FADE_HEAD_S, FADE_TAIL_S = 0.6, 1.5  # same windows as engines.qa.black_runs defaults
FADE_MAX_S = 2.0                     # longest black run accepted at the start/end (real fades: 1-5 frames)
SHORT_CLIP_S = 6.0                   # below this the windows shrink in proportion, so a short clip keeps a middle
AUDIO_ONLY_TOL = 0.05                # s, audio-only file vs intended duration (AAC pads up to one frame)
COVER_CODECS = {"png", "mjpeg", "bmp", "gif", "webp", "tiff"}
SILENT_LUFS = -40.0                  # integrated loudness below this = the film lost its sound
SILENT_MAX_DB = -60.0                # volumedetect max_volume at or below this = digital silence


def max_volume(path):
    from engines.media import exe
    o = subprocess.run([exe("ffmpeg"), "-hide_banner", "-nostats", "-i", str(path), "-map", "0:a:0", "-af", "volumedetect",
                        "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="ignore")
    m = re.search(r"max_volume:\s*(-?[\d.]+|-inf) dB", o.stderr)
    if not m:
        return None
    return -999.0 if m.group(1) == "-inf" else float(m.group(1))


def loudness(path) -> dict:
    from engines.media import exe
    o = subprocess.run([exe("ffmpeg"), "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=framelog=quiet:peak=true",
                        "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="ignore")
    r = {}
    m = re.search(r"I:\s*(-?[\d.]+) LUFS", o.stderr)
    if m:
        r["loudness_lufs"] = float(m.group(1))
    m = re.search(r"Peak:\s*(-?[\d.]+|-inf) dBFS", o.stderr)
    if m and m.group(1) != "-inf":
        r["true_peak_dbtp"] = float(m.group(1))
    return r


def _run_text(x) -> str:
    return f"t={x['start']:.2f}-{x['end']:.2f} ({x['frames']} frame{'' if x['frames'] == 1 else 's'})"


def _secs(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):  # missing or "N/A"
        return 0.0


def _is_cover(v) -> bool:
    """Cover art inside an audio file shows up as a one-picture 'video' stream at 90000 fps: not a picture track."""
    from engines.media import fps
    return v.get("codec_name") in COVER_CODECS and fps(v.get("r_frame_rate")) >= 1000


def _black_gate(p, r, length):
    """Body runs fail; edge runs are fades (info) unless longer than FADE_MAX_S (a render that went black to the end)."""
    from engines import qa
    k = min(1.0, length / SHORT_CLIP_S) if length > 0 else 1.0
    win = {"allow_head": round(FADE_HEAD_S * k, 3), "allow_tail": round(FADE_TAIL_S * k, 3)}
    cap = round(FADE_MAX_S * k, 3)
    try:
        b = qa.black_runs(p, **win)
    except Exception as e:  # a scan that cannot run is a failure, never a silent pass
        r["errors"].append(f"black scan failed: {type(e).__name__}: {e}")
        return
    r["black"] = {"frames": b["frames"], "body": b["body"], "edge": b["edge"], **win, "max_fade_s": cap}
    if not b["frames"]:
        r["errors"].append("black scan read no frames")
        return
    step = b["duration_s"] / b["frames"]
    r["errors"] += [f"black frames {_run_text(x)}" for x in b["body"]]
    for x in b["edge"]:
        where = "start" if x["start_frame"] == 0 else "end"
        if x["frames"] >= b["frames"]:
            x["too_long"] = True
            r["errors"].append(f"whole video is black ({x['frames']} frames)")
        elif x["end"] - x["start"] + step > cap + 1e-6:
            x["too_long"] = True
            r["errors"].append(f"black at {where} {_run_text(x)}: longer than {cap:g} s, not a fade")
        else:
            r["info"].append(f"fade black at {where} {_run_text(x)}")


def _frame_gate(p, r, duration):
    """Exact frame count when the intended length is known (failure), else within one frame of the container (warning)."""
    from engines import qa
    try:
        fc = qa.frame_check(p, duration)
    except Exception as e:
        r["errors"].append(f"frame count failed: {type(e).__name__}: {e}")
        return
    if not fc:
        return
    r["frame_check"] = fc
    if fc.get("vfr"):
        r["warnings"].append(f"VFR video (r {fc['fps']:g}, avg {fc['avg_fps']:g} fps): frame count is not meaningful; "
                             f"`dragon mux` re-encodes it at a constant rate")
    if not fc["frames_ok"]:
        n, want = fc["frames"], fc["expected_frames"]
        what = "intended" if duration else "container"
        msg = f"frames {n} vs {want} for {what} {fc['reference_s']:g} s at {fc['fps']:g} fps ({n - want:+d})"
        (r["errors"] if duration else r["warnings"]).append(msg)


def _audio_gate(p, r):
    from engines import qa
    try:
        r["errors"] += qa.audio_check(p)
    except Exception as e:
        r["errors"].append(f"audio check failed: {type(e).__name__}: {e}")


def _silence_gate(p, r):
    lufs = r.get("loudness_lufs")
    mv = max_volume(p)
    if mv is not None:
        r["max_volume_db"] = mv
    if (lufs is not None and lufs < SILENT_LUFS) or (mv is not None and mv <= SILENT_MAX_DB):
        r["errors"].append(f"audio is silent (loudness {lufs} LUFS, max_volume {mv} dB): the film lost its sound "
                           f"(«من غير صوت»); mux the master audio again")


def probe_file(p, expect=None, duration=None, black=True, expect_audio=False) -> dict:
    p = Path(p)
    duration = float(duration) if duration else None
    r = {"path": str(p), "exists": p.exists(), "warnings": [], "errors": [], "info": []}
    if not p.exists():
        r["errors"].append("file not found")
        return {**r, "ok": False}
    r["bytes"] = p.stat().st_size
    if not r["bytes"]:
        r["errors"].append("empty file (0 bytes)")
    ext = p.suffix.lower()
    try:
        if ext in MEDIA:
            from engines.media import probe, fps
            j = probe(p)
            r["duration_s"] = round(float(j["format"].get("duration", 0)), 3)
            r["streams"] = j.get("streams", [])
            v = next((s for s in r["streams"] if s.get("codec_type") == "video"), None)
            a = next((s for s in r["streams"] if s.get("codec_type") == "audio"), None)
            if v:
                r.update(width=v.get("width"), height=v.get("height"), codec=v.get("codec_name"), fps=round(fps(v.get("r_frame_rate")), 3))
            if a:
                r.update(loudness(p))
            if v and a and v.get("duration") and a.get("duration"):
                dv, da = float(v["duration"]), float(a["duration"])
                r["video_s"], r["audio_s"] = round(dv, 3), round(da, 3)
                if abs(dv - da) > 0.25:  # the bug that cut Mayar film 2 at 34.9 s would show here
                    r["warnings"].append(f"audio {da:.2f}s vs video {dv:.2f}s")
            if v and not _is_cover(v) and ext in (".mp4", ".m4v") and v.get("codec_name") != "h264":
                r["warnings"].append(f"video codec {v.get('codec_name')} in {ext}: delivery is H.264 (`dragon mux` re-encodes)")
            if expect and v and f"{v.get('width')}x{v.get('height')}" != expect:
                r["warnings"].append(f"size {v.get('width')}x{v.get('height')} != {expect}")
            if "loudness_lufs" in r and not -16.5 <= r["loudness_lufs"] <= -11.5:
                r["warnings"].append(f"loudness {r['loudness_lufs']} LUFS outside social range (-16..-12)")
            if r.get("true_peak_dbtp", -99) > TRUE_PEAK_MAX:
                r["warnings"].append(f"true peak {r['true_peak_dbtp']} dBTP above {TRUE_PEAK_MAX:g} (owner limit)")
            picture = v is not None and not _is_cover(v)
            if picture and black:
                _black_gate(p, r, _secs(v.get("duration")) or r["duration_s"])
            elif picture:
                r["black"] = {"skipped": True, "body": [], "edge": []}
            if a:
                _audio_gate(p, r)
                _silence_gate(p, r)
            elif picture and expect_audio:
                r["errors"].append("no audio stream: a song/voice film must carry its audio (pass --silent-ok for a "
                                   "deliberately silent film)")
            if picture:
                _frame_gate(p, r, duration)
            elif a and duration and abs(r["duration_s"] - duration) > AUDIO_ONLY_TOL:
                r["errors"].append(f"duration {r['duration_s']:g} s vs intended {duration:g} s ({r['duration_s'] - duration:+.3f} s)")
            b, fc = r.get("black") or {}, r.get("frame_check") or {}
            if b.get("frames") and fc and abs(b["frames"] - fc["frames"]) > 1:
                r["warnings"].append(f"decoded {b['frames']} of {fc['frames']} frames (damaged stream?)")
        elif ext in IMAGE:
            from PIL import Image
            with Image.open(p) as im:
                im.verify()
            with Image.open(p) as im:
                r.update(width=im.width, height=im.height, mode=im.mode, format=im.format)
        elif ext in TEXT:
            txt = p.read_text(encoding="utf-8", errors="ignore")
            r.update(chars=len(txt), lines=txt.count("\n") + 1)
            if ext == ".json":
                json.loads(txt)
                r["json_valid"] = True
    except Exception as e:  # unreadable is a failure, never a silent pass
        r["error"] = f"{type(e).__name__}: {e}"
        if ext == ".json":
            r["json_valid"] = False
    r["ok"] = r["exists"] and r.get("bytes", 0) > 0 and "error" not in r and not r["errors"]
    return r


def line(r) -> str:
    bits = [f"{k}={r[k]}" for k in ("duration_s", "loudness_lufs", "true_peak_dbtp", "fps", "chars", "json_valid") if k in r]
    if r.get("width"):
        bits.append(f"{r['width']}x{r['height']} {r.get('codec') or r.get('format') or ''}".strip())
    fc, b = r.get("frame_check"), r.get("black")
    if fc:
        bits.append(f"frames={fc['frames']}" + ("" if fc["frames_ok"] else f"/{fc['expected_frames']}"))
    body = (b or {}).get("body") or []
    if b:
        n = len(body) + sum(1 for x in b.get("edge", []) if x.get("too_long"))
        bits.append("black=skipped" if b.get("skipped") else f"black={n} run{'s' if n > 1 else ''}" if n else "black=clean")
    # one entry for all body runs: start-end (frames) each, then the totals
    errs = [e for e in r.get("errors", []) if not e.startswith("black frames t=")]
    if len(body) == 1:
        errs.insert(0, f"black frames {_run_text(body[0])}")
    elif body:
        runs = ", ".join(f"{x['start']:.2f}-{x['end']:.2f} ({x['frames']})" for x in body)
        errs.insert(0, f"black frames t={runs}: {len(body)} runs, {sum(x['frames'] for x in body)} frames")
    tail = "".join(f"  {label} " + "; ".join(items)
                   for label, items in (("ERRORS", errs), ("WARN", r.get("warnings")), ("INFO", r.get("info"))) if items)
    return f"{'OK ' if r.get('ok') else 'FAIL'} {r['path']}  {r.get('bytes', 0) // 1024} KB  " + "  ".join(bits) + tail + \
           (f"  ERROR {r['error']}" if "error" in r else "")


def verify(files, out=None, expect=None, duration=None, black=True, expect_audio=False):
    if isinstance(files, (str, Path)):
        files = [files]
    rows = [probe_file(f, expect, duration, black, expect_audio) for f in files]
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        doc = {"verified_at": datetime.datetime.now().isoformat(timespec="seconds"), "ok": all(r.get("ok") for r in rows),
               "checks": {"expect": expect, "duration": float(duration) if duration else None, "black": bool(black),
                          "true_peak_max_dbtp": TRUE_PEAK_MAX, **({"expect_audio": True} if expect_audio else {})},
               "files": rows}
        Path(out).write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return rows
