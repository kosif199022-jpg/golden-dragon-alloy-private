"""Montage engine: frame-accurate smart cut, 9:16 reframe, logo / burned-subtitle removal, graded frame extraction."""
import tempfile
from pathlib import Path
from .media import ascii_path, ffmpeg, probe, fps, exe
import subprocess


def keyframes(path, start, end):
    out = subprocess.run([exe("ffprobe"), "-v", "error", "-select_streams", "v:0", "-read_intervals", f"{start}%{end}",
                          "-show_entries", "packet=pts_time,flags", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout
    ks = []
    for line in out.splitlines():
        t, _, flags = line.partition(",")
        if "K" in flags and t not in ("", "N/A"):
            ks.append(float(t))
    return sorted(ks)


def smart_cut(src, start, end, dst, crf=17):
    """Re-encode only start -> next keyframe, stream-copy the rest, join. Frame counts are exact
    (copy mode alone keeps 1-2 extra frames around B-frames, so both parts are capped by -frames:v)."""
    start, end = float(start), float(end)
    streams = probe(src)["streams"]
    v = next((s for s in streams if s["codec_type"] == "video"), None)
    if v is None:
        if not any(s["codec_type"] == "audio" for s in streams):
            raise ValueError(f"{src} has no video or audio stream")
        # audio only (a recitation, a song): copy the packets between start and end (AUDIO_SONGS_QURAN §19 for an
        # exact cut at a breath: atrim + apad, AAC 320k)
        ffmpeg("-ss", start, "-i", src, "-t", end - start, "-map", "0:a:0", "-c", "copy", dst)
        return {"mode": "audio-copy", "seconds": round(end - start, 3)}
    enc = {"h264": "libx264", "hevc": "libx265"}.get(v["codec_name"])
    rate = fps(v["r_frame_rate"])
    total = round(end * rate) - round(start * rate)
    after = [k for k in keyframes(src, start, end) if start + 0.001 <= k < end]
    common = ["-c:a", "aac", "-b:a", "320k"]
    if not after or enc is None:
        ffmpeg("-ss", start, "-i", src, "-t", end - start, "-frames:v", total, "-c:v", enc or "libx264", "-crf", crf,
               "-preset", "slow", "-pix_fmt", v.get("pix_fmt", "yuv420p"), *common, "-movflags", "+faststart", dst)
        return {"mode": "encoded", "frames": total}
    k = after[0]
    head_frames = round((k - start) * rate)
    tmp = Path(tempfile.mkdtemp(prefix="bd_cut_"))
    head, tail, lst = tmp / "head.mp4", tmp / "tail.mp4", tmp / "list.txt"
    ffmpeg("-ss", start, "-i", src, "-t", k - start, "-frames:v", head_frames, "-c:v", enc, "-crf", crf, "-preset", "slow",
           "-pix_fmt", v.get("pix_fmt", "yuv420p"), "-r", v["r_frame_rate"], *common, head)
    ffmpeg("-ss", k, "-i", src, "-t", end - k, "-frames:v", total - head_frames, "-c", "copy", "-avoid_negative_ts", "make_zero", tail)
    lst.write_text(f"file '{head.as_posix()}'\nfile '{tail.as_posix()}'\n", encoding="utf-8")
    ffmpeg("-f", "concat", "-safe", 0, "-i", lst, "-c", "copy", "-movflags", "+faststart", dst)
    return {"mode": "smart", "encoded_s": round(k - start, 3), "copied_s": round(end - k, 3), "frames": total}


def crop_9x16(z=1.0, cx=0.5, cy=0.5):
    """Largest 9:16 window of any source, zoomed by z, placed by cx/cy in [0,1]."""
    w = f"min(iw,ih*9/16)/{z}"
    return f"crop=w='{w}':h='{w}*16/9':x='(iw-{w})*{cx}':y='(ih-{w}*16/9)*{cy}'"


def delogo(rects, iw, ih):
    """rects in source fractions [x, y, w, h] -> chained delogo filters (channel bugs, burned subtitles)."""
    parts = []
    for x, y, w, h in rects or []:
        X, Y = max(1, int(x * iw)), max(1, int(y * ih))
        parts.append(f"delogo=x={X}:y={Y}:w={min(int(w * iw), iw - X - 1)}:h={min(int(h * ih), ih - Y - 1)}")
    return ",".join(parts)


def extract_frames(src, start, dur, out_dir, z=1.0, cx=0.5, cy=0.5, lut=None, grade="eq=contrast=1.06:saturation=1.05",
                   rects=None, size=(1080, 1920), rate=30):
    """Graded JPEG frames of one shot: delogo -> 9:16 crop -> lanczos scale -> sharpen -> LUT -> grade -> fps."""
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    chain = []
    if rects:
        v = next(s for s in probe(src)["streams"] if s["codec_type"] == "video")
        chain.append(delogo(rects, v["width"], v["height"]))
    chain += [crop_9x16(z, cx, cy), f"scale={size[0]}:{size[1]}:flags=lanczos", "unsharp=5:5:0.5"]
    if lut:
        chain.append(f"lut3d=file='{ascii_path(lut).as_posix().replace(':', chr(92) + ':')}':interp=tetrahedral")
    if grade:
        chain.append(grade)
    chain.append(f"fps={rate}")
    ffmpeg("-ss", start, "-i", src, "-t", f"{dur:.3f}", "-vf", ",".join(chain), "-q:v", 2, out_dir / "%05d.jpg")
    return len(list(out_dir.glob("*.jpg")))
