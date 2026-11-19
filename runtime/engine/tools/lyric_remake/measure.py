# -*- coding: utf-8 -*-
"""Render a single ASS text and return its pixel bbox (to place multi-colour RTL lines correctly)."""
import subprocess, sys, os, json
import numpy as np, cv2

def bbox(font, size, text, bold=0):
    ass = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: A,{font},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,{bold},0,0,0,100,100,0,0,1,0,0,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:05.00,A,,0,0,0,,{{\\pos(960,540)}}{text}
"""
    open("_m.ass", "w", encoding="utf-8-sig").write(ass)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    "color=c=black:s=1920x1080:d=1", "-vf", "subtitles=_m.ass:fontsdir=../fonts",
                    "-frames:v", "1", "_m.png"], check=True)
    g = cv2.imread("_m.png", 0)
    ys, xs = np.where(g > 60)
    return int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())

USAGE = """usage: measure.py ITEMS.json OUT.json [--force]

ITEMS.json: {"key": ["font name", size, "text"], ...}
Writes {"key": [xmin, xmax, ymin, ymax], ...} to OUT.json.
Refuses to overwrite an existing OUT.json unless --force is given.
Renders a scratch _m.ass / _m.png in the current folder (ffmpeg + subtitles filter).
"""

if __name__ == "__main__":
    argv = sys.argv[1:]
    if any(a in ("-h", "--help") for a in argv):
        print(USAGE); sys.exit(0)
    force = "--force" in argv
    argv = [a for a in argv if a != "--force"]
    if len(argv) != 2:
        print(USAGE, file=sys.stderr); sys.exit(2)
    items_path, out_path = argv
    if os.path.exists(out_path) and not force:
        sys.exit(f"refusing to overwrite {out_path} (use --force)")
    items = json.loads(open(items_path, encoding="utf-8").read())
    out = {}
    for k, (font, size, text) in items.items():
        out[k] = bbox(font, size, text)
        print(k, out[k])
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
