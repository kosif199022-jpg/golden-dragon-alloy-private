"""Timestamped contact sheets for reference clips: N frames per clip, time printed on each tile."""
import subprocess, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

import os
SRC = Path(os.environ.get("BDC_REFS", r"C:\Users\cinde\OneDrive\Desktop\المونتاج\01_raw\refs"))
OUT = Path(os.environ.get("BDC_WORK", r"C:\Users\cinde\bdc_work")) / "sheets"
OUT.mkdir(parents=True, exist_ok=True)
FONT = "C\\:/Windows/Fonts/arialbd.ttf"

def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                capture_output=True, text=True).stdout.strip())

ids = sys.argv[1:]
for cid in ids:
    p = next(SRC.glob(f"*{cid}*.mp4"))
    d = dur(p)
    n = 24
    step = d / n
    vf = (f"fps=1/{step:.4f},scale=200:-2,"
          f"drawtext=fontfile='{FONT}':text='%{{pts\\:hms}}':x=4:y=4:fontsize=18:fontcolor=yellow:box=1:boxcolor=black@0.6,"
          f"tile=8x3:padding=3")
    out = OUT / f"{cid}.jpg"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(p), "-vf", vf, "-frames:v", "1", str(out)], check=True)
    print(out, f"{d:.1f}s step {step:.2f}s")
