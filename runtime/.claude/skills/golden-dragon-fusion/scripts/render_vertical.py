"""Render and verify a vertical MP4 using the local Golden Dragon media tools."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile


def render(source, destination):
    source = source.resolve(strict=True)
    destination = destination.resolve()
    if destination.exists() or destination.suffix.lower() != ".mp4":
        raise ValueError("Choose a new .mp4 output path")
    with tempfile.TemporaryDirectory(dir=destination.parent) as folder:
        staged = Path(folder) / "render.mp4"
        filters = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30"
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(source),
                        "-map", "0:v:0", "-map", "0:a?", "-vf", filters,
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                        "-movflags", "+faststart", str(staged)], check=True)
        raw = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                       "-show_entries", "stream=width,height,avg_frame_rate,nb_frames",
                                       "-of", "json", str(staged)])
        stream = json.loads(raw)["streams"][0]
        if (stream["width"], stream["height"], stream["avg_frame_rate"]) != (1080, 1920, "30/1") or int(stream["nb_frames"]) < 1:
            raise ValueError("Output verification failed")
        os.link(staged, destination)
        return {"output": str(destination), **stream}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(json.dumps(render(args.source, args.destination), ensure_ascii=False))
