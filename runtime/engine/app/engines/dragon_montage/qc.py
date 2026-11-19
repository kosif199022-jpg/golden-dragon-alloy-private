"""Measurements of a delivered video: the delivery spec (verify) and motion energy / frozen stretches (motion)."""
from __future__ import annotations

import json
import re
import subprocess

from ..media import exe, fps as rate


def loudness(path) -> dict | None:
    """EBU R128 integrated loudness, LRA and true peak of the default audio stream."""
    err = subprocess.run([exe("ffmpeg"), "-nostats", "-i", str(path), "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    i = err.rfind("Integrated loudness")
    if i < 0:
        return None
    g = lambda pat: (lambda m: float(m.group(1)) if m else None)(re.search(pat, err[i:]))  # noqa: E731
    return {"integrated_lufs": g(r"I:\s*(-?[\d.]+) LUFS"), "lra": g(r"LRA:\s*(-?[\d.]+) LU"),
            "true_peak_dbfs": g(r"Peak:\s*(-?[\d.]+) dBFS")}


def verify(video, aspect: tuple | None = None, fps: float | None = None, duration: float | None = None,
           lufs: float = -14.0, no_audio: bool = False) -> dict:
    """Delivery gate: H.264 4:2:0, even size, aspect, fps, duration/frame count, AAC >= 44.1 kHz, loudness ±1.5 LU,
    true peak <= -1 dBFS. Returns {checks: [{check, pass, value}], pass, codec, width, height, fps, ...}."""
    out = subprocess.run([exe("ffprobe"), "-v", "error", "-show_format", "-show_streams", "-count_frames", "-of", "json",
                          str(video)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    info = json.loads(out.stdout or "{}")
    v = next((s for s in info.get("streams", []) if s["codec_type"] == "video"), None)
    a = next((s for s in info.get("streams", []) if s["codec_type"] == "audio"), None)
    if not v:
        return {"file": str(video), "checks": [{"check": "video stream present", "pass": False, "value": "absent"}], "pass": False}
    w, h = int(v["width"]), int(v["height"])
    f = rate(v.get("avg_frame_rate") or v.get("r_frame_rate"))
    frames = int(v.get("nb_read_frames") or v.get("nb_frames") or 0)
    dur = float(info["format"].get("duration") or 0)
    rep = {"file": str(video), "codec": v.get("codec_name"), "width": w, "height": h, "fps": round(f, 3), "frames": frames,
           "duration_s": round(dur, 3), "pix_fmt": v.get("pix_fmt")}
    checks = [("video codec is H.264", v.get("codec_name") == "h264", v.get("codec_name", "?")),
              ("pixel format is 4:2:0 8-bit (universal playback)", v.get("pix_fmt") in ("yuv420p", "yuvj420p"), v.get("pix_fmt", "?")),
              ("even dimensions", w % 2 == 0 and h % 2 == 0, f"{w}x{h}")]
    if aspect:
        checks.append((f"aspect is {aspect[0]}:{aspect[1]}", abs(w / h - aspect[0] / aspect[1]) < 0.01, f"{w}x{h} = {w / h:.3f}"))
    if fps:
        checks.append((f"frame rate is {fps:g}", abs(f - fps) < 0.05, f"{f:.3f}"))
    if duration:
        checks.append((f"duration is {duration:g} s (±1 frame)", abs(dur - duration) <= (1 / f if f else 0.05) + 0.001, f"{dur:.3f} s"))
        if f:
            checks.append(("frame count matches duration × fps", abs(frames - round(duration * f)) <= 1, f"{frames} frames"))
    if no_audio:
        checks.append(("no audio stream (silent deliverable)", a is None, "present" if a else "absent"))
    else:
        checks.append(("audio stream present", a is not None, a.get("codec_name", "?") if a else "absent"))
        if a:
            rep.update({"audio_codec": a.get("codec_name"), "channels": a.get("channels"), "sample_rate": a.get("sample_rate")})
            checks.append(("audio codec is AAC", a.get("codec_name") == "aac", a.get("codec_name", "?")))
            checks.append(("sample rate ≥ 44.1 kHz", int(a.get("sample_rate") or 0) >= 44100, str(a.get("sample_rate"))))
            lu = loudness(video)
            if lu:
                rep["loudness"] = lu
                if lu.get("integrated_lufs") is not None:
                    checks.append((f"integrated loudness {lufs:g} LUFS ±1.5", abs(lu["integrated_lufs"] - lufs) <= 1.5,
                                   f"{lu['integrated_lufs']} LUFS"))
                if lu.get("true_peak_dbfs") is not None:
                    checks.append(("true peak ≤ -1 dBFS", lu["true_peak_dbfs"] <= -1.0, f"{lu['true_peak_dbfs']} dBFS"))
    rep["checks"] = [{"check": c, "pass": bool(ok), "value": val} for c, ok, val in checks]
    rep["pass"] = all(c["pass"] for c in rep["checks"])
    return rep


def motion(path, fps: float = 10.0, freeze: float = 1.5, still: float = 0.6, cut: float = 25.0, w: int = 64) -> dict:
    """Per-frame mean absolute difference (0-255) of small grey frames; per-second energy and frozen stretches."""
    import numpy as np
    from ..media import probe
    v = next(s for s in probe(path)["streams"] if s["codec_type"] == "video")
    h = max(2, int(round(w * (v.get("height") or 9) / (v.get("width") or 16) / 2) * 2))
    raw = subprocess.run([exe("ffmpeg"), "-v", "error", "-i", str(path), "-vf", f"fps={fps},scale={w}:{h},format=gray",
                          "-f", "rawvideo", "-"], capture_output=True).stdout
    frames = np.frombuffer(raw[: len(raw) // (w * h) * w * h], dtype=np.uint8).reshape(-1, w * h).astype(np.int32)
    diffs = [(round(i / fps, 3), float(np.abs(frames[i] - frames[i - 1]).sum()) / (w * h)) for i in range(1, len(frames))]
    per_sec: dict = {}
    for t, d in diffs:
        per_sec.setdefault(int(t), []).append(d)
    frozen, run_start = [], None
    for t, d in diffs + [(diffs[-1][0] + 1 / fps if diffs else 0, 999)]:
        if d < still and run_start is None:
            run_start = t - 1 / fps
        elif d >= still and run_start is not None:
            if t - run_start >= freeze:
                frozen.append({"from": round(max(0, run_start), 2), "to": round(t - 1 / fps, 2),
                               "seconds": round(t - 1 / fps - run_start, 2)})
            run_start = None
    return {"fps_sampled": fps, "frames": len(diffs) + 1,
            "share_moving": round(sum(1 for _, d in diffs if d >= still) / max(1, len(diffs)), 3),
            "timeline": [{"second": s, "energy": round(sum(v) / len(v), 2), "peak": round(max(v), 2)} for s, v in sorted(per_sec.items())],
            "frozen": frozen, "cuts": [round(t, 2) for t, d in diffs if d >= cut],
            "thresholds": {"still": still, "cut": cut, "freeze_seconds": freeze}}


def similarity(ref, test, vmaf: bool = True) -> dict:
    """SSIM (and VMAF when this ffmpeg has libvmaf) of `test` against `ref`, both scaled to ref's size."""
    from ..media import probe
    v = next(s for s in probe(ref)["streams"] if s["codec_type"] == "video")
    W, H = v["width"], v["height"]
    pre = f"[0:v]scale={W}:{H},setpts=PTS-STARTPTS,format=yuv420p[t];[1:v]scale={W}:{H},setpts=PTS-STARTPTS,format=yuv420p[r]"
    out = {}
    err = subprocess.run([exe("ffmpeg"), "-hide_banner", "-nostats", "-i", str(test), "-i", str(ref), "-lavfi",
                          pre + ";[t][r]ssim", "-f", "null", "-"], capture_output=True, text=True, errors="replace").stderr
    m = re.search(r"All:([\d.]+)", err)
    out["ssim"] = float(m.group(1)) if m else None
    if vmaf:
        err = subprocess.run([exe("ffmpeg"), "-hide_banner", "-nostats", "-i", str(test), "-i", str(ref), "-lavfi",
                              pre + ";[t][r]libvmaf", "-f", "null", "-"], capture_output=True, text=True, errors="replace").stderr
        m = re.search(r"VMAF score:\s*([\d.]+)", err)
        out["vmaf"] = float(m.group(1)) if m else None
    return out

