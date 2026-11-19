#!/usr/bin/env python3
"""sheets — timestamped contact sheets: N frames per clip in one image, the time printed on each tile.

    dragon.py tool sheets CLIP.mp4 [CLIP2.mov ...] [--out DIR] [--n 24] [--cols 8] [--width 200] [--force]
    dragon.py tool sheets 7462 8812 --refs REFS_DIR   # pick clips by an id fragment of their file name

Use it to read a reference edit or check your own render by eye before saying it is done.
Writes <clip>.jpg into --out (default ./sheets); an existing sheet is kept unless --force.
--refs defaults to $BDC_REFS, --out to $BDC_WORK/sheets when those are set (v10.8 cinema layout).
Needs ffmpeg + ffprobe.
"""
import argparse, os, platform, subprocess, sys
from pathlib import Path

VIDEO_EXT = (".mp4", ".mov", ".mkv", ".webm", ".m4v")


def find_font():
    cands = [r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\arial.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]
    for c in cands:
        if Path(c).is_file():
            return c
    return None


def ff_font(path):
    """drawtext needs the drive colon escaped on Windows: C\\:/Windows/Fonts/arialbd.ttf"""
    p = Path(path).as_posix()
    return p.replace(":", "\\:", 1) if platform.system() == "Windows" else p


def duration(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def resolve(item, refs):
    p = Path(item)
    if p.is_file():
        return p
    if refs and Path(refs).is_dir():
        hits = sorted(x for x in Path(refs).iterdir() if item in x.name and x.suffix.lower() in VIDEO_EXT)
        if hits:
            return hits[0]
    return None


def sheet(clip, out, n=24, cols=8, width=200, font=None):
    d = duration(clip)
    rows = -(-n // cols)
    step = d / n
    text = (f"drawtext=fontfile='{ff_font(font)}':" if font else "drawtext=") + \
        "text='%{pts\\:hms}':x=4:y=4:fontsize=18:fontcolor=yellow:box=1:boxcolor=black@0.6,"
    vf = f"fps=1/{step:.4f},scale={width}:-2,{text}tile={cols}x{rows}:padding=3"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(clip), "-vf", vf, "-frames:v", "1", str(out)], check=True)
    return d, step


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="dragon.py tool sheets", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clips", nargs="+", help="video files, or id fragments looked up in --refs")
    ap.add_argument("--refs", default=os.environ.get("BDC_REFS"), help="folder to look up id fragments (env BDC_REFS)")
    work = os.environ.get("BDC_WORK")
    ap.add_argument("--out", default=str(Path(work) / "sheets") if work else "sheets", help="output folder (default ./sheets)")
    ap.add_argument("--n", type=int, default=24, help="frames per sheet (default 24)")
    ap.add_argument("--cols", type=int, default=8)
    ap.add_argument("--width", type=int, default=200, help="tile width in pixels")
    ap.add_argument("--force", action="store_true", help="overwrite an existing sheet")
    a = ap.parse_args(argv)
    if a.n < 1 or a.cols < 1 or a.width < 16:
        ap.error("--n, --cols must be >= 1 and --width >= 16")
    out_dir = Path(a.out); out_dir.mkdir(parents=True, exist_ok=True)
    font, code = find_font(), 0
    for item in a.clips:
        clip = resolve(item, a.refs)
        if clip is None:
            print(f"مش لاقي: {item}" + ("" if a.refs else " (حدد --refs لو ده جزء من اسم ملف)"), file=sys.stderr)
            code = 2; continue
        out = out_dir / f"{clip.stem}.jpg"
        if out.exists() and not a.force:
            print(f"موجود: {out} (استخدم --force)"); continue
        try:
            d, step = sheet(clip, out, a.n, a.cols, a.width, font)
        except (subprocess.CalledProcessError, ValueError, FileNotFoundError) as e:
            print(f"فشل {clip.name}: {type(e).__name__}", file=sys.stderr); code = 1; continue
        print(f"{out}  ({d:.1f}s, كل {step:.2f}s)")
    return code


if __name__ == "__main__":
    sys.exit(main())
