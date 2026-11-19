"""Delivery QA shared by verify, mux and patch-black (v1.2).

Three failures shipped to the owner in Nov 2026 before these checks existed:
  * runs of pure-black frames inside films rendered from canvas pages (browser drew nothing for a stretch of seeks);
  * an MP4 whose audio stream was MP3: it played silent on iPhone / Safari although ffprobe listed audio;
  * a mux with -shortest that ended 3 frames short (807 instead of 810) because of AAC priming.
Each helper below measures one of them with ffmpeg/ffprobe only (no Python media libraries).
"""
import re, subprocess
from pathlib import Path
from .media import exe, probe, fps as _fps

BLACK_Y = 17.5          # mean luma of a fully black frame in TV range is 16.0; any real picture sits well above 17.5
BLACK_PEAK_Y = 40       # ...but a small title on black ("والفائز...") also averages ~16; a black frame has no pixel above this
MP4_LIKE = {".mp4", ".m4v", ".mov"}
SAFE_AUDIO_IN_MP4 = {"aac", "alac", "ac3", "eac3"}
# QuickTime (.mov) plays linear PCM on iPhone/Mac (AVFoundation); .mp4/.m4v do not. MP3 fails in both.
SAFE_AUDIO_IN_MOV = SAFE_AUDIO_IN_MP4 | {"pcm_s16le", "pcm_s16be", "pcm_s24le", "pcm_s24be", "pcm_s32le", "pcm_s32be",
                                         "pcm_f32le", "pcm_f32be"}


def audio_fits(codec, ext):
    """True when `codec` audio plays on phones inside a file with extension `ext` (non-MP4 containers: no rule)."""
    ext = (ext or "").lower()
    if ext not in MP4_LIKE:
        return True
    return codec in (SAFE_AUDIO_IN_MOV if ext == ".mov" else SAFE_AUDIO_IN_MP4)


def luma_series(path, scale="54:96", peak=False):
    """[(time_s, mean_luma)] for every decoded frame (small scale keeps it fast: ~3 min of 1080x1920 in well under a minute).
    Luma is read at 8 bits (format=yuv420p): signalstats reports the source bit depth, and 10-bit black is Y=64.
    peak=True returns [(time_s, mean_luma, max_luma)] instead."""
    r = subprocess.run([exe("ffmpeg"), "-hide_banner", "-nostdin", "-i", str(path), "-map", "0:v:0",
                        "-vf", f"scale={scale},format=yuv420p,signalstats,metadata=mode=print" + ("" if peak else ":key=lavfi.signalstats.YAVG"),
                        "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="ignore")
    out, t, avg = [], None, None
    for ln in r.stderr.splitlines():
        m = re.search(r"pts_time:([-\d.]+)", ln)
        if m:
            t, avg = float(m.group(1)), None; continue
        m = re.search(r"lavfi\.signalstats\.YAVG=([\d.]+)", ln)
        if m and t is not None:
            if not peak:
                out.append((t, float(m.group(1)))); t = None
            else:
                avg = float(m.group(1))
            continue
        m = re.search(r"lavfi\.signalstats\.YMAX=([\d.]+)", ln)
        if m and peak and t is not None and avg is not None:
            out.append((t, avg, float(m.group(1)))); t = avg = None
    return out


def black_runs(path, threshold=BLACK_Y, allow_head=0.6, allow_tail=1.5, min_frames=1):
    """Find runs of fully black frames. A run is 'edge' (an intended fade from/to black) only when it touches the first
    decoded frame (and starts within `allow_head` s) or touches the last decoded frame (and `allow_tail` > 0). A run
    with picture on both sides is 'body' and must not ship, however close to the start or end it sits: a glitch at
    0.2-0.4 s or 1 s before the end is not a fade. The length cap for edge runs is verify's job (FADE_MAX_S)."""
    series = luma_series(path, peak=True)
    if not series:
        return {"frames": 0, "runs": [], "body": [], "edge": []}
    dur = series[-1][0]
    step = (series[-1][0] - series[0][0]) / max(1, len(series) - 1) if len(series) > 1 else 1 / 30
    runs, cur = [], None
    for i, (t, y, ymax) in enumerate(series):
        if y < threshold and ymax < BLACK_PEAK_Y:
            if cur is None:
                cur = {"start_frame": i, "start": round(t, 3)}
            cur["end_frame"], cur["end"] = i, round(t, 3)
        elif cur is not None:
            runs.append(cur); cur = None
    if cur is not None:
        runs.append(cur)
    last, t0 = len(series) - 1, series[0][0]
    for r in runs:
        r["frames"] = r["end_frame"] - r["start_frame"] + 1
        head = r["start_frame"] == 0 and r["start"] - t0 <= allow_head + step / 2
        tail = r["end_frame"] == last and allow_tail > 0
        r["kind"] = "edge" if (head or tail) else "body"
    runs = [r for r in runs if r["frames"] >= min_frames]
    return {"frames": len(series), "duration_s": round(dur + step, 3), "runs": runs,
            "body": [r for r in runs if r["kind"] == "body"], "edge": [r for r in runs if r["kind"] == "edge"]}


def audio_check(path):
    """Container/codec problems that make a file silent or rejected on phones. Returns a list of problem strings."""
    p = Path(path)
    j = probe(p)
    probs = []
    auds = [s for s in j.get("streams", []) if s.get("codec_type") == "audio"]
    if p.suffix.lower() in MP4_LIKE:
        for a in auds:
            if not audio_fits(a.get("codec_name"), p.suffix):
                probs.append(f"audio codec {a.get('codec_name')} inside {p.suffix.lower()}: iPhone/Safari play it silent; "
                             f"remux with `dragon mux` (AAC 320k)")
    return probs


def is_vfr(v):
    """True when a video stream is variable frame rate (phone clips): r_frame_rate and avg_frame_rate differ by > 0.5 %."""
    r, a = _fps(v.get("r_frame_rate")), _fps(v.get("avg_frame_rate"))
    return r > 0 and a > 0 and abs(r - a) / r > 0.005


def frame_check(path, expect_duration=None):
    """Real video frame count against the intended length: `expect_duration` when the caller knows it (a spec), otherwise
    the container duration (the longest stream). A video that ends frames before its audio (-shortest + AAC priming
    gave 807 frames for a 27.0 s film) is caught here; verify's 0.25 s audio/video tolerance does not see 3 frames."""
    j = probe(path)
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), None)
    if not v:
        return {}
    rate = _fps(v.get("r_frame_rate"))
    n = v.get("nb_frames")
    if n in (None, "", "N/A"):
        r = subprocess.run([exe("ffprobe"), "-v", "error", "-count_packets", "-select_streams", "v:0",
                            "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", str(path)], capture_output=True, text=True)
        n = (r.stdout or "0").strip().split(",")[0] or 0
    n = int(n)
    ref = float(expect_duration) if expect_duration else float(j["format"].get("duration") or v.get("duration") or 0)
    if is_vfr(v):  # frame count against r_frame_rate means nothing here; count against the average rate, never fail
        avg = _fps(v.get("avg_frame_rate"))
        expected = round(ref * avg)
        return {"frames": n, "fps": round(rate, 3), "avg_fps": round(avg, 3), "vfr": True, "reference_s": round(ref, 3),
                "expected_frames": expected, "frames_ok": True}
    expected = round(ref * rate)
    return {"frames": n, "fps": round(rate, 3), "reference_s": round(ref, 3), "expected_frames": expected,
            "frames_ok": abs(n - expected) <= (0 if expect_duration else 1)}
