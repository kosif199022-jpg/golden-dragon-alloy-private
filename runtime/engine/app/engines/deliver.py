"""Delivery (v1.2): an exact-length mux and a black-frame patcher, ffmpeg/ffprobe only.

mux          video + audio -> MP4 with exactly N = round(duration * fps) frames (or the video's own count) and audio
             of exactly N / fps seconds. No -shortest: it ended a film 3 frames short (807 of 810, AAC priming).
             Audio that is not AAC becomes AAC 320k 48 kHz: MP3 inside MP4 played silent on the owner's iPhone.
patch_black  clones the last good frame over black runs inside a film (headless Chromium sometimes drew nothing
             for a stretch of seeks), re-encodes, then scans the result again.
"""
import inspect, os, shutil, subprocess
from pathlib import Path
from . import qa
from .media import exe, ffmpeg, probe, fps as _fps

# Owner export standard: H.264 High, CRF 17, preset slow, yuv420p, BT.709 tagged in the stream and the container.
H264 = ["-c:v", "libx264", "-crf", "17", "-preset", "slow", "-profile:v", "high", "-pix_fmt", "yuv420p",
        "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]
AAC_RATE = 48000
LOUDNORM = "loudnorm=I=-14:TP=-1.5:LRA=11"
MAX_RUNS = 1000                                     # keeps the select expression far below the Windows command limit
SHORT_CLIP_S = 6.0                                  # same rule as dragon verify: shorter clips get smaller fade windows


def fit_audio(seconds):
    """-af chain that pads (silence) or trims an audio stream to exactly `seconds` at its own sample rate: with
    -frames:v N it replaces -shortest, which ended films frames short (AAC priming) or cut the video to a short score."""
    s = f"{float(seconds):.6f}"
    return f"apad=whole_dur={s},atrim=end={s}"


def _stream(path, kind):
    j = probe(path)
    s = next((x for x in j.get("streams", []) if x.get("codec_type") == kind), None)
    if s is None:
        raise ValueError(f"no {kind} stream in {path}")
    return s, j


def _frame_count(path, v):
    """Frames in the first video stream: container count, else counted packets (MKV/WebM carry no count)."""
    n = v.get("nb_frames")
    if n in (None, "", "N/A", "0"):
        r = subprocess.run([exe("ffprobe"), "-v", "error", "-count_packets", "-select_streams", "v:0",
                            "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", str(path)],
                           capture_output=True, text=True, encoding="utf-8", errors="ignore")
        n = (r.stdout or "0").strip().split(",")[0] or 0
    return int(n)


def _rate(v, path):
    text = v.get("r_frame_rate") or ""
    rate = _fps(text)
    if rate <= 0:
        raise ValueError(f"no frame rate for the video of {path}")
    return text, rate


def _first_frames_copyable(path, n, rate):
    """True when the first n packets (decode order) are exactly frames 0..n-1. With B-frames a later frame is often
    stored before earlier ones, so copying n packets would keep a frame from after the cut and lose one before it."""
    r = subprocess.run([exe("ffprobe"), "-v", "error", "-select_streams", "v:0", "-read_intervals", f"%+#{n}",
                        "-show_entries", "packet=pts_time", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True, encoding="utf-8", errors="ignore")
    ts = []
    for ln in (r.stdout or "").splitlines():
        cell = ln.strip().split(",")[0]
        if not cell:
            continue
        try:
            ts.append(float(cell))
        except ValueError:  # N/A: cannot prove the cut is clean, so re-encode
            return False
    if len(ts) != n:
        return False
    t0 = min(ts)
    return sorted(round((t - t0) * rate) for t in ts) == list(range(n))


def _faststart(out):
    return ["-movflags", "+faststart"] if out.suffix.lower() in qa.MP4_LIKE else []


def _part(out):
    """Write next to the target first, then replace it: a failed run never leaves half a file (in-place works too)."""
    return out.with_name(out.stem + ".part" + out.suffix)


def _run(args, out):
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = _part(out)
    try:
        ffmpeg(*args, tmp, capture=True)
        os.replace(tmp, out)
    finally:
        if tmp.exists():
            tmp.unlink()


def _verify_row(path, seconds):
    """dragon.verify row without the black scan (fast); older verify versions lack the keywords, so pass what exists."""
    from dragon.verify import probe_file
    params = inspect.signature(probe_file).parameters
    kw = {k: val for k, val in (("duration", seconds), ("black", False)) if k in params}
    return probe_file(path, **kw)


def _audio_out(row):
    """(codec, seconds) of the first audio stream in a verify row, as measured."""
    a = next((s for s in row.get("streams", []) if s.get("codec_type") == "audio"), None)
    if not a:
        return None, None
    try:
        return a.get("codec_name"), round(float(a["duration"]), 3)
    except (KeyError, TypeError, ValueError):
        return a.get("codec_name"), None


def mux(video, audio, out, duration=None, normalize=False, bitrate="320k"):
    """Video + audio -> `out` with exactly N frames and N / fps seconds of audio.

    video: stream copy of the first N frames when the source has them (and the first N packets are frames 0..N-1);
           fewer frames: the last frame is cloned (tpad) and the video re-encoded at the delivery standard.
    audio: AAC is copied when `normalize` is off and it is long enough (trimmed at a packet edge, within one AAC
           frame); anything else becomes AAC `bitrate` 48 kHz padded/trimmed to the exact sample
           (loudnorm I=-14:TP=-1.5:LRA=11 first when `normalize`).
    Returns frames, fps, modes, audio codec and the verify row of the output (black scan skipped for speed)."""
    video, audio, out = Path(video), Path(audio), Path(out)
    if not out.suffix:
        out = out.with_suffix(".mp4")
    v, vj = _stream(video, "video")
    rate_text, rate = _rate(v, video)
    have = _frame_count(video, v)
    vfr = qa.is_vfr(v)
    if vfr:  # phone clips: r_frame_rate is a guess, nb_frames / r_frame_rate is not the length -> re-encode CFR
        vdur = _secs(v.get("duration")) or _secs(vj["format"].get("duration"))
        have = round(vdur * rate) if vdur > 0 else have
    n = round(float(duration) * rate) if duration else have
    if n <= 0:
        raise ValueError(f"nothing to mux: {n} frames (video {video} has {have})")
    secs = n / rate
    cfr = ["-fps_mode", "cfr", "-r", rate_text]  # every re-encode is constant frame rate: n frames really last n / rate

    copyable = v.get("codec_name") == "h264" and not vfr  # delivery is H.264: VP9/HEVC/ProRes get re-encoded
    if copyable and have >= n and _first_frames_copyable(video, n, rate):
        vmode, vargs = "copy", ["-c:v", "copy"]
    elif have >= n:
        vmode, vargs = "encode", [*H264, *cfr]  # B-frames, VFR or not H.264: a packet copy would not give n frames
    elif vfr:
        vmode, vargs = "pad", ["-vf", f"tpad=stop_mode=clone:stop_duration={(n - have + 1) / rate:.6f}", *H264, *cfr]
    else:
        vmode, vargs = "pad", ["-vf", f"tpad=stop={n - have}:stop_mode=clone", *H264, *cfr]
    vargs += ["-frames:v", str(n)]

    a, aj = _stream(audio, "audio")
    src_codec = a.get("codec_name")
    sr = int(a.get("sample_rate") or AAC_RATE)
    a_secs = float(a.get("duration") or aj["format"].get("duration") or 0)
    if src_codec == "aac" and not normalize and a_secs >= secs - 1024 / sr:
        amode, ain, aargs = "copy", ["-t", f"{secs:.6f}"], ["-c:a", "copy"]
    else:
        samples = round(secs * AAC_RATE)
        chain = ([LOUDNORM] if normalize else []) + [f"aresample={AAC_RATE}", f"apad=whole_len={samples}",
                                                     f"atrim=end_sample={samples}"]
        amode = "normalize" if normalize else "encode"
        ain = ["-t", f"{secs + 0.5:.3f}"]  # read only what is needed; the filter cuts to the exact sample
        aargs = ["-af", ",".join(chain), "-c:a", "aac", "-b:a", str(bitrate), "-ar", str(AAC_RATE)]

    _run(["-i", video, *ain, "-i", audio, "-map", "0:v:0", "-map", "1:a:0", *vargs, *aargs, *_faststart(out)], out)
    row = _verify_row(out, secs)
    fc = row.get("frame_check") or {}
    a_codec, a_out = _audio_out(row)
    return {"out": str(out), "frames": fc.get("frames", n), "expected_frames": n, "fps": round(rate, 3), "rate": rate_text,
            "duration_s": round(secs, 3), "video_mode": vmode, "source_frames": have, "vfr": vfr,
            "video_source_codec": v.get("codec_name"),
            "audio_codec": a_codec, "audio_mode": amode, "audio_source_codec": src_codec, "audio_s": a_out,
            "padded_s": round(max(0, n - have) / rate, 3) if vmode == "pad" else 0.0,
            "verify": row, "ok": bool(row.get("ok"))}


def _patch_audio_args(src, out):
    """Copy the audio, unless phones would play it silent in the output container (MP3 inside MP4/MOV, PCM inside MP4;
    the rule of engines.qa.audio_fits that verify fails on): then AAC 320k 48 kHz. PCM inside .mov is copied."""
    try:
        a, _ = _stream(src, "audio")
    except ValueError:
        return ["-c:a", "copy"], "none"
    fits = qa.audio_fits(a.get("codec_name") or "", out.suffix)
    return (["-c:a", "copy"], "copy") if fits else (["-c:a", "aac", "-b:a", "320k", "-ar", str(AAC_RATE)], "encode")


def _secs(x):
    try:
        return float(x)
    except (TypeError, ValueError):  # missing or "N/A"
        return 0.0


def patch_black(src, out, threshold=qa.BLACK_Y, allow_head=0.6, allow_tail=1.5):
    """Replace every black run inside the film ('body' runs of engines.qa.black_runs) with the last good frame before
    it: the black frames are dropped and the fps filter repeats the previous frame in their slots, so the frame count
    and timing stay exact. Video is re-encoded (CRF 17 slow, BT.709); audio is copied (MP3 in an MP4 becomes AAC 320k,
    see _patch_audio_args). The result is scanned again: `remaining` lists body runs still there (must be empty).
    A file with no body runs is copied unchanged (re-encoded when OUT is another container, e.g. .webm -> .mp4).
    Runs at the very start/end are fades and stay. Below SHORT_CLIP_S the fade windows shrink in proportion, the same
    rule as dragon verify, so what verify fails on a short clip is what gets patched."""
    src, out = Path(src), Path(out)
    if not out.suffix:
        out = out.with_suffix(src.suffix if src.suffix.lower() in qa.MP4_LIKE else ".mp4")
    if out.suffix.lower() not in qa.MP4_LIKE | {".mkv"}:
        raise ValueError(f"patch-black writes H.264: give OUT as .mp4 (or .mov/.mkv), not {out.suffix or 'no extension'}")
    v, j = _stream(src, "video")
    rate_text, _ = _rate(v, src)
    length = _secs(v.get("duration")) or _secs(j["format"].get("duration"))
    k = min(1.0, length / SHORT_CLIP_S) if length > 0 else 1.0
    win = {"threshold": threshold, "allow_head": round(allow_head * k, 3), "allow_tail": round(allow_tail * k, 3)}
    before = qa.black_runs(src, **win)
    total, body = before["frames"], before["body"]
    if not total:
        raise ValueError(f"no video frames decoded from {src}")
    res = {"src": str(src), "out": str(out), "source_frames": total, "patched": body,
           "patched_frames": sum(r["frames"] for r in body), "windows": win}
    if not body and src.suffix.lower() == out.suffix.lower():
        out.parent.mkdir(parents=True, exist_ok=True)
        if src.resolve() != out.resolve():
            shutil.copy2(src, out)
        return {**res, "mode": "copy", "frames": total, "remaining": [], "edge": before["edge"], "audio_mode": "copy", "ok": True}
    if len(body) > MAX_RUNS:
        raise ValueError(f"{len(body)} black runs in {src}: too broken to patch, render it again")
    drop = "+".join(f"between(n,{r['start_frame']},{r['end_frame']})" for r in body)
    vf = f"select='not({drop})',fps={rate_text}" if body else f"fps={rate_text}"  # no runs: only a new container (webm)
    if body and body[0]["start_frame"] == 0:  # nothing before it: the first good frame after it fills the gap
        vf += f":start_time={body[0]['start']}"
    aargs, amode = _patch_audio_args(src, out)
    tmp = _part(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        ffmpeg("-i", src, "-map", "0:v:0", "-map", "0:a?", "-vf", vf, "-frames:v", total, *H264, *aargs,
               *_faststart(out), tmp, capture=True)
        after = qa.black_runs(tmp, **win)
        os.replace(tmp, out)
    finally:
        if tmp.exists():
            tmp.unlink()
    return {**res, "mode": "patched" if body else "encoded", "frames": after["frames"], "remaining": after["body"], "edge": after["edge"],
            "audio_mode": amode, "ok": not after["body"] and after["frames"] == total}
