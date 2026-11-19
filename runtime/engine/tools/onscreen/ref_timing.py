#!/usr/bin/env python3
"""reftiming — measure WHEN each on-screen lyric line appears in a reference video (v10.16.1).

  dragon.py tool reftiming REF.mp4 [--band 0.42,0.14] [--thr 150] [--min-px 8] [--json out.json]

Why: «بنفس الستايل» lyric reels (andrew.music style etc.) show one line at a time over the
same audio. If we reuse the audio, the exact on-screen timing of the reference is the right
timing for our lines — no whisper needed, and it already matches the singer.

How: crop a horizontal band where the text sits (default: 42% from top, 14% tall), downscale,
count bright pixels per frame, and return the runs where text is visible. A run that changes
shape a lot in the middle is split (two lines back to back).

Output: one line per run: `start end` in seconds (+ JSON with --json). Needs ffmpeg + numpy.
Pair it with the verified lyric text (two sources) — this tool gives timing only, never words.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,r_frame_rate", "-of", "csv=p=0", path],
                         capture_output=True, text=True, check=True).stdout.strip().split(",")
    w, h = int(out[0]), int(out[1])
    n, d = out[2].split("/")
    return w, h, float(n) / float(d or 1)


def runs_from_frames(frames, fps, thr=150, min_px=8, split_px=40):
    import numpy as np
    on = (frames > thr).reshape(len(frames), -1).sum(axis=1) > min_px
    runs, s = [], None
    for i, v in enumerate(on):
        if v and s is None:
            s = i
        if not v and s is not None:
            runs.append((s, i)); s = None
    if s is not None:
        runs.append((s, len(on)))
    out = []
    for a, e in runs:
        cuts = [a]
        seg = frames[a:e] > thr
        for i in range(1, len(seg)):
            if np.abs(seg[i].astype(int) - seg[i - 1].astype(int)).sum() > split_px:
                cuts.append(a + i)
        cuts.append(e)
        for x, y in zip(cuts, cuts[1:]):
            if y - x >= 3:
                out.append((round(x / fps, 2), round(y / fps, 2)))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="dragon.py tool reftiming", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--band", default="0.42,0.14", help="top,height as fractions of frame height")
    ap.add_argument("--thr", type=int, default=150)
    ap.add_argument("--min-px", type=int, default=8)
    ap.add_argument("--json", default="")
    a = ap.parse_args(argv)
    if not shutil.which("ffmpeg"):
        print("ffmpeg not found", file=sys.stderr); return 2
    try:
        import numpy as np
    except ImportError:
        print("numpy not found", file=sys.stderr); return 2
    w, h, fps = probe(a.video)
    top, hh = (float(x) for x in a.band.split(","))
    y0, bh = int(h * top), max(8, int(h * hh))
    sw, sh = 144, max(8, int(144 * bh / w))
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", a.video, "-vf",
                          f"crop={w}:{bh}:0:{y0},scale={sw}:{sh},format=gray", "-f", "rawvideo", "-"],
                         capture_output=True, check=True).stdout
    frames = np.frombuffer(raw, np.uint8).reshape(-1, sh, sw).astype(float)
    runs = runs_from_frames(frames, fps, a.thr, a.min_px)
    for s, e in runs:
        print(f"{s:.2f} {e:.2f}")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump({"fps": fps, "band": [top, hh], "runs": runs}, fh, indent=1)
    return 0 if runs else 1


if __name__ == "__main__":
    sys.exit(main())
