"""burn_captions.py — burn correctly shaped Arabic captions onto a video with khatt (HarfBuzz + FreeType) and ffmpeg.
No Raqm, no moviepy: every caption becomes a full-frame transparent PNG drawn by khatt, and ffmpeg overlays them in
one pass from a concat list (one input, any number of captions).

  python -X utf8 burn_captions.py VIDEO CAPTIONS OUT.mp4 [options]
    CAPTIONS        .srt, or sync.json written by the Golden Bird's speech_sync (its "captions" list)
    --font NAME     amiri (default) | cairo | noto-naskh | rubik | path to a .ttf/.otf
    --size PX       font size in pixels (default: 5.5% of the video height)
    --color C       text colour (default white)        --stroke C / --stroke-width PX   outline (default black / 4)
    --box C         optional background box, e.g. "#000000a0"
    --bottom F      distance of the caption from the bottom, as a fraction of the height (default 0.12)
    --align A       center (default) | right | left: alignment of wrapped lines
    --width F       max caption width as a fraction of the video width (default 0.86; longer lines wrap)
    --crf N         x264 quality (default 18)          --preview T  also save the frame at T seconds as OUT.preview.png
Exit 0 = written and measured (duration within 0.1 s of the source).
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import khatt
from PIL import Image


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)],
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout
    d = json.loads(out)
    v = next(s for s in d["streams"] if s["codec_type"] == "video")
    num, den = (v.get("avg_frame_rate") or "30/1").split("/")
    fps = float(num) / float(den or 1) if float(num) else 30.0
    return int(v["width"]), int(v["height"]), fps, float(d["format"]["duration"]), any(s["codec_type"] == "audio" for s in d["streams"])


def _t(s):
    h, m, rest = s.strip().replace(".", ",").split(":")
    sec, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms) / 1000


def read_captions(path):
    p = Path(path)
    text = p.read_text(encoding="utf-8-sig")
    if p.suffix.lower() == ".json":
        caps = json.loads(text)["captions"]
        return [(float(c["start"]), float(c["end"]), c["text"]) for c in caps]
    caps = []
    for block in re.split(r"\r?\n\s*\r?\n", text.strip()):
        lines = [l for l in block.splitlines() if l.strip()]
        i = next((k for k, l in enumerate(lines) if "-->" in l), None)
        if i is None:
            continue
        a, b = lines[i].split("-->")
        caps.append((_t(a), _t(b.split()[0]), "\n".join(lines[i + 1:])))
    return caps


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video"), ap.add_argument("captions"), ap.add_argument("out")
    ap.add_argument("--font", default="amiri"), ap.add_argument("--size", type=int)
    ap.add_argument("--color", default="white"), ap.add_argument("--stroke", default="black")
    ap.add_argument("--stroke-width", type=float, default=4), ap.add_argument("--box")
    ap.add_argument("--bottom", type=float, default=0.12), ap.add_argument("--width", type=float, default=0.86)
    ap.add_argument("--crf", type=int, default=18), ap.add_argument("--preview", type=float)
    ap.add_argument("--align", default="center", choices=["center", "right", "left"])
    a = ap.parse_args(argv)

    W, H, fps, dur, has_audio = probe(a.video)
    caps = sorted(read_captions(a.captions))
    if not caps:
        raise SystemExit("✗ مفيش كابشن في الملف")
    size = a.size or max(24, round(H * 0.055))
    tmp = Path(tempfile.mkdtemp(prefix="khatt_caps_"))
    try:
        blank = tmp / "blank.png"
        Image.new("RGBA", (W, H), (0, 0, 0, 0)).save(blank)
        entries, t = [], 0.0
        for n, (s, e, text) in enumerate(caps):
            s, e = max(s, t), min(e, dur)
            if e <= s:
                continue
            img = khatt.caption_image(text, font=a.font, font_size=size, size=(int(W * a.width), None), method="caption", text_align=a.align,
                                      color=a.color, stroke_color=a.stroke, stroke_width=a.stroke_width,
                                      bg_color=a.box, margin=(size // 3, size // 5) if a.box else (None, None))
            frame = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            frame.alpha_composite(img, ((W - img.width) // 2, max(0, H - img.height - int(H * a.bottom))))
            f = tmp / f"cap_{n:04d}.png"
            frame.save(f)
            if s > t:
                entries.append((blank, s - t))
            entries.append((f, e - s))
            t = e
        entries.append((blank, max(0.04, dur - t)))
        lst = tmp / "list.txt"
        body = "".join(f"file '{p.as_posix()}'\nduration {d:.3f}\n" for p, d in entries) + f"file '{entries[-1][0].as_posix()}'\n"
        lst.write_text(body, encoding="utf-8")
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(a.video), "-f", "concat", "-safe", "0", "-i", str(lst),
               "-filter_complex", f"[1:v]format=rgba,fps={fps:.6f}[c];[0:v][c]overlay=0:0:format=auto:eof_action=pass[v]",
               "-map", "[v]"] + (["-map", "0:a", "-c:a", "copy"] if has_audio else []) + [
               "-c:v", "libx264", "-crf", str(a.crf), "-preset", "medium", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(a.out)]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            raise SystemExit("✗ ffmpeg فشل:\n" + r.stderr[-1500:])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    _, _, _, out_dur, _ = probe(a.out)
    ok = abs(out_dur - dur) <= 0.1
    if a.preview is not None:
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(a.preview), "-i", str(a.out), "-frames:v", "1",
                        str(Path(a.out).with_suffix(".preview.png"))], check=False)
    print(f"{'✓' if ok else '✗'} {a.out}: {len(caps)} كابشن، {W}x{H}، المدة {out_dur:.2f} ث (الأصل {dur:.2f} ث)، خط {a.font} {size}px")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
