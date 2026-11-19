#!/usr/bin/env python3
"""sheet.py IN [IN..] -o OUT.jpg [--n 6] [--cols 3] [--width 900] [--max-kb 480] [--times 0.5,2,4.9]
Contact sheet to LOOK at results through sandbox_exec image_paths (limit: 4 images, 512 KiB total).
IN = one video (n evenly spaced frames, or --times) or several images. Each tile is labelled.
"""
import argparse, io, os, subprocess, sys
from PIL import Image, ImageDraw


def grab(video, t):
    r = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1",
                        "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
    return Image.open(io.BytesIO(r.stdout)).convert("RGB") if r.stdout else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+"); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--n", type=int, default=6); ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--width", type=int, default=900); ap.add_argument("--max-kb", type=int, default=480)
    ap.add_argument("--times", default=None)
    a = ap.parse_args()
    tiles = []
    vid_ext = (".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi")
    if len(a.inputs) == 1 and a.inputs[0].lower().endswith(vid_ext):
        v = a.inputs[0]
        d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", v],
                                 capture_output=True, text=True).stdout.strip() or 0)
        times = [float(x) for x in a.times.split(",")] if a.times else [d * (i + 0.5) / a.n for i in range(a.n)]
        for t in times:
            im = grab(v, min(t, max(0, d - 0.05)))
            if im: tiles.append((im, f"{t:.2f}s"))
    else:
        for f in a.inputs:
            tiles.append((Image.open(f).convert("RGB"), os.path.basename(f)[:28]))
    if not tiles:
        sys.exit("sheet: nothing to show")
    cols = min(a.cols, len(tiles)); rows = (len(tiles) + cols - 1) // cols
    tw = a.width // cols; th = max(int(tw * im.height / im.width) for im, _ in tiles)
    sheet = Image.new("RGB", (tw * cols, th * rows), (20, 20, 20))
    dr = ImageDraw.Draw(sheet)
    for i, (im, lab) in enumerate(tiles):
        im = im.copy(); im.thumbnail((tw, th))
        x, y = (i % cols) * tw, (i // cols) * th
        sheet.paste(im, (x + (tw - im.width) // 2, y + (th - im.height) // 2))
        dr.rectangle([x, y, x + 8 + 7 * len(lab), y + 16], fill=(0, 0, 0)); dr.text((x + 4, y + 2), lab, fill=(255, 220, 0))
    q = 88
    while True:
        buf = io.BytesIO(); sheet.save(buf, "JPEG", quality=q, optimize=True)
        if buf.tell() <= a.max_kb * 1024 or q <= 35: break
        q -= 8
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    open(a.out, "wb").write(buf.getvalue())
    print(f"sheet: {a.out} {sheet.width}x{sheet.height} tiles={len(tiles)} kb={buf.tell() // 1024} q={q}")


if __name__ == "__main__":
    main()
