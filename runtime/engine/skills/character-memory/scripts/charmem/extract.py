"""Frames out of a video with their real timing: every decoded frame (no duplicates, no drops: fps_mode passthrough)
as PNG, and each frame's presentation time read from ffprobe (not computed from the frame rate)."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def probe(video):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,r_frame_rate,avg_frame_rate,nb_frames,duration,pix_fmt,codec_name:frame=best_effort_timestamp_time",
                        "-of", "json", str(video)], capture_output=True, text=True, check=True)
    d = json.loads(r.stdout)
    st = d["streams"][0]
    num, den = (int(x) for x in st["r_frame_rate"].split("/"))
    times = [float(f["best_effort_timestamp_time"]) for f in d.get("frames", []) if "best_effort_timestamp_time" in f]
    return {"width": st["width"], "height": st["height"], "fps": num / den, "fps_rational": st["r_frame_rate"], "codec": st.get("codec_name"),
            "pix_fmt": st.get("pix_fmt"), "duration": float(st.get("duration") or 0), "times": times}


def extract(video, out_dir):
    out = Path(out_dir)
    fdir = out / "frames"
    fdir.mkdir(parents=True, exist_ok=True)
    info = probe(video)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-fps_mode", "passthrough", "-start_number", "0", str(fdir / "%05d.png")], check=True)
    files = sorted(fdir.glob("*.png"))
    if len(files) != len(info["times"]):
        raise SystemExit(f"decoded {len(files)} frames but ffprobe lists {len(info['times'])}")
    timing = {"schema": "dragon.frames.v1", "video": str(Path(video).resolve()), "sha256": sha256(video),
              "width": info["width"], "height": info["height"], "fps": info["fps"], "fps_rational": info["fps_rational"],
              "codec": info["codec"], "pix_fmt": info["pix_fmt"], "duration": info["duration"],
              "frames": [{"i": i, "t": round(t, 6), "file": f.name} for i, (t, f) in enumerate(zip(info["times"], files))]}
    (out / "timing.json").write_text(json.dumps(timing, indent=1), encoding="utf-8")
    return timing
