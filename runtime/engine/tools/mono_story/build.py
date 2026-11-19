#!/usr/bin/env python3
"""Mono story film (ST08, v1990.5.0): animated ink-cartoon shots + small two-line subtitles + doodle title card.

Learned from a 9:16 «Stickman» song reel: black-and-white inked cartoon, one AI-animated shot per lyric line
(hard cuts on the line), small white subtitles low in the frame where the second line fades in on its word,
and a white closing card with the song title in heavy Arabic type surrounded by hand-drawn doodles
(stars, notes, arrows, scribbles) that draw on and "boil".

Everything runs on ffmpeg (+ Pillow with raqm for the card); no browser, so it is light on a full disk.

    python build.py JOB spec.json [--out film.mp4] [--keep]
    python build.py --demo JOB          # makes placeholder shots and a spec, then builds (offline self-test)

spec.json
  dur      seconds (the audio length)
  audio    path to the song, stream-copied (relative to JOB)
  mono     true = convert every shot to grayscale (default true; false for colour looks)
  look     "ink" (small white subtitles low, default), "comic" (big bold yellow Lalezar, centre-low)
           or "khawater" (big cream block text in the empty area, per-line y)
  sub_style optional overrides {"font","size","color","y","outline"}
  shots    [{"start":0,"end":4.6,"src":"clips/s1.mp4"}]  video (retimed to fit: slowed with motion
           interpolation, or trimmed) or image (slow push-in). Shots must tile 0..card start.
  subs     [[start, end, "line one", "line two", line_two_at, y]]   line two may be "" ; line_two_at defaults to start;
           y (optional) places this line; "\\N" inside a line breaks it (block text)
  card     {"start":36.8, "title":"كائن تلاتيني", "by":"نور الدين محمد"}   optional white doodle card to the end
  credit   owner's credit, shown on the last 3 s (default «مونتاج وإخراج Mahmoud Elkosif» / «تابعني على فيسبوك»)
  watermark default «© Mahmoud Elkosif»
"""
import json
import math
import random
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FONTS = HERE / "fonts"
W, H, FPS = 1080, 1920, 30
CREDIT = ["مونتاج وإخراج Mahmoud Elkosif", "تابعني على فيسبوك"]
X264 = ["-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p", "-preset", "slow", "-crf", "17",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709"]
IMG = {".jpg", ".jpeg", ".png", ".webp"}
# subtitle looks learned from reels: "ink" = «كائن تلاتيني» (small white, low), "comic" = Samar Sabry (big bold yellow, centre-low)
SUB_LOOKS = {"ink": {"font": "Almarai", "size": 46, "color": "#ffffff", "y": 1745, "outline": 2.2},
             "comic": {"font": "Changa", "size": 84, "color": "#f6b740", "y": 1360, "outline": 3.5},
             # "khawater" = Ahmed AlShamy reflection reels: big cream block text in the empty wall/sky of each shot
             "khawater": {"font": "Changa", "size": 100, "color": "#efe3c8", "y": 520, "outline": 2.0}}
# libass note (tested 11 Nov): Lalezar and Cairo Black render as boxes/tiny in libass; Changa, Almarai work.


def sh(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"ffmpeg failed: {' '.join(map(str, cmd[:6]))} ...\n{r.stderr[-1500:]}")
    return r.stdout


def probe_dur(p):
    return float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).strip())


def shot(job, s, i, mono, tmp):
    src = job / s["src"]
    d = round(s["end"] - s["start"], 4)
    nfr = round(s["end"] * FPS) - round(s["start"] * FPS)
    cover = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
    grade = ",format=gray,format=yuv420p" if mono else ",format=yuv420p"
    out = tmp / f"s{i:02d}.mp4"
    if src.suffix.lower() in IMG:
        # slow push-in on a still: 100% -> 108%, centred, smooth (zoompan on an upscaled source)
        vf = (f"scale={W*2}:{H*2}:force_original_aspect_ratio=increase,crop={W*2}:{H*2},"
              f"zoompan=z='1+0.08*on/{max(nfr-1,1)}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={nfr}:s={W}x{H}:fps={FPS}"
              + grade + ",tpad=stop_mode=clone:stop_duration=2")
        sh(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(src), "-vf", vf, "-frames:v", str(nfr), "-an",
            *X264, str(out)])
    else:
        L = probe_dur(src)
        f = max(d / L, 1.0) * 1.0005
        vf = (f"setpts={f:.5f}*PTS," + (f"minterpolate=fps={FPS}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,"
                                         if f > 1.02 else f"fps={FPS},")
              + cover + ",unsharp=5:5:0.6" + grade + ",tpad=stop_mode=clone:stop_duration=2")
        sh(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf", vf, "-frames:v", str(nfr), "-an", *X264, str(out)])
    return out


def card_frames(card, dur_frames, credit_from, tmp):
    """White doodle title card as a frame sequence: title pops, doodles draw on, the whole card boils at 10 fps."""
    from PIL import Image, ImageDraw, ImageFont
    title = ImageFont.truetype(str(FONTS / "Lalezar-Regular.ttf"), 230)
    by = ImageFont.truetype(str(FONTS / "Lalezar-Regular.ttf"), 92)
    small = ImageFont.truetype(str(FONTS / "Almarai-Bold.ttf"), 40)
    words = card["title"].split()
    lines = [" ".join(words[: math.ceil(len(words) / 2)]), " ".join(words[math.ceil(len(words) / 2):])] if len(words) > 1 else words
    R = random.Random(7)
    doodles = []
    for _ in range(26):
        ang = R.uniform(0, 2 * math.pi)
        rx, ry = R.uniform(300, 430), R.uniform(330, 470)
        doodles.append((R.choice("star note arrow dash spiral dot".split()), 540 + rx * math.cos(ang), 880 + ry * math.sin(ang),
                        R.uniform(26, 52), R.uniform(0, 2 * math.pi), R.uniform(0.0, 0.9)))
    d_out = tmp / "card"
    d_out.mkdir(exist_ok=True)

    def jit(boil, k, amt=3.0):
        r = random.Random(boil * 1000 + k)
        return r.uniform(-amt, amt), r.uniform(-amt, amt)

    def doodle(dr, kind, x, y, s, a, boil, k, prog):
        if prog <= 0:
            return
        jx, jy = jit(boil, k)
        x, y = x + jx, y + jy
        ink, wdt = (20, 20, 20), 6
        if kind == "star":
            pts = []
            for j in range(10):
                rr = s if j % 2 == 0 else s * 0.45
                aa = a + j * math.pi / 5
                pts.append((x + rr * math.cos(aa), y + rr * math.sin(aa)))
            n = max(2, int(len(pts) * prog) + 1)
            dr.line((pts + [pts[0]])[:n], fill=ink, width=wdt, joint="curve")
        elif kind == "note":
            dr.ellipse((x - s * .45, y + s * .3, x + s * .25, y + s * .8), fill=ink)
            if prog > .5:
                dr.line((x + s * .2, y + s * .55, x + s * .2, y - s * .7), fill=ink, width=wdt)
                dr.line((x + s * .2, y - s * .7, x + s * .65, y - s * .4), fill=ink, width=wdt)
        elif kind == "arrow":
            ex, ey = x + s * 1.6 * math.cos(a) * prog, y + s * 1.6 * math.sin(a) * prog
            dr.line((x, y, ex, ey), fill=ink, width=wdt)
            if prog > .8:
                for da in (2.6, -2.6):
                    dr.line((ex, ey, ex + s * .5 * math.cos(a + da), ey + s * .5 * math.sin(a + da)), fill=ink, width=wdt)
        elif kind == "dash":
            for j in range(3):
                aa = a + (j - 1) * .35
                dr.line((x, y, x + s * prog * math.cos(aa), y + s * prog * math.sin(aa)), fill=ink, width=wdt - 1)
        elif kind == "spiral":
            pts = [(x + (3 + t * s / 30) * math.cos(t * .5 + a), y + (3 + t * s / 30) * math.sin(t * .5 + a))
                   for t in range(int(30 * prog) + 2)]
            dr.line(pts, fill=ink, width=wdt - 1, joint="curve")
        else:
            dr.ellipse((x - 6, y - 6, x + 6, y + 6), fill=ink)

    for fr in range(dur_frames):
        t = fr / FPS
        boil = int(t * 10) % 3
        im = Image.new("RGB", (W, H), "white")
        dr = ImageDraw.Draw(im)
        k = min(1.0, t / 0.45)
        pop = 1 + 2.70158 * (k - 1) ** 3 + 1.70158 * (k - 1) ** 2
        if pop > 0.02:
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer)
            y = 760 if len(lines) > 1 else 860
            for li, line in enumerate(lines):
                jx, jy = jit(boil, 900 + li, 2)
                ld.text((540 + jx, y + li * 220 + jy), line, font=title, fill=(15, 15, 15), anchor="mm", direction="rtl",
                        language="ar")
            jx, jy = jit(boil, 950, 2)
            ld.text((560 + jx, y + len(lines) * 220 - 40 + jy), card.get("by", ""), font=by, fill=(15, 15, 15), anchor="mm",
                    direction="rtl", language="ar")
            sc = max(pop, 0.05)
            lw, lh = int(W * sc), int(H * sc)
            layer = layer.resize((lw, lh))
            im.paste(layer, ((W - lw) // 2, (H - lh) // 2 + int((1 - sc) * 60)), layer)
        for kk, (kind, x, y, s, a, delay) in enumerate(doodles):
            doodle(dr, kind, x, y, s, a, boil, kk, min(1.0, max(0.0, (t - 0.2 - delay) / 0.35)))
        if t >= credit_from:
            ca = min(1.0, (t - credit_from) / 0.4)
            g = int(255 - 225 * ca)
            dr.text((540, 1580), CREDIT[0], font=small, fill=(g, g, g), anchor="mm", direction="rtl", language="ar")
            dr.text((540, 1636), CREDIT[1], font=small, fill=(g, g, g), anchor="mm", direction="rtl", language="ar")
        im.save(d_out / f"{fr:05d}.png", compress_level=1)
    out = tmp / "card.mp4"
    sh(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", str(d_out / "%05d.png"), *X264, str(out)])
    shutil.rmtree(d_out)
    return out


def ass_time(t):
    t = max(t, 0)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def ass(spec, card_start, path):
    st = dict(SUB_LOOKS.get(spec.get("look", "ink"), SUB_LOOKS["ink"]), **spec.get("sub_style", {}))
    rgb = st["color"].lstrip("#")
    col = f"&H00{rgb[4:6]}{rgb[2:4]}{rgb[0:2]}".upper()
    y1, gap = st["y"], int(st["size"] * 1.3)
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{st["font"]},{st["size"]},{col},{col},&H00000000,&H64000000,{0 if st["font"] == "Lalezar" else 1},0,0,0,100,100,0,0,1,{st["outline"]},1.5,5,40,40,0,178
Style: Mark,Almarai,24,&H66FFFFFF,&H66FFFFFF,&H80000000,&H00000000,1,0,0,0,100,100,0,0,1,1.2,0,1,40,40,0,1
Style: Credit,Almarai,40,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,2.4,0,5,40,40,0,178

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    for row in spec.get("subs", []):
        s, e, a, b = row[0], row[1], row[2], row[3] if len(row) > 3 else ""
        t2 = row[4] if len(row) > 4 else s
        e = min(e, card_start)
        ya = row[5] if len(row) > 5 else y1  # per-line y (text placed in the shot's empty area)
        ev.append(f"Dialogue: 1,{ass_time(s)},{ass_time(e)},Sub,,0,0,0,,{{\\pos(540,{ya})\\fad(220,180)}}{a}")
        if b:
            ev.append(f"Dialogue: 1,{ass_time(t2)},{ass_time(e)},Sub,,0,0,0,,{{\\pos(540,{ya + gap})\\fad(260,180)}}{b}")
    mark = spec.get("watermark", "© Mahmoud Elkosif")
    ev.append(f"Dialogue: 0,{ass_time(0)},{ass_time(spec['dur'])},Mark,,0,0,0,,{{\\pos(40,1880)}}{mark}")
    if card_start >= spec["dur"]:  # no card: credit on the picture, last 3 s
        c0 = spec["dur"] - 3
        ev.append(f"Dialogue: 2,{ass_time(c0)},{ass_time(spec['dur'])},Credit,,0,0,0,,{{\\pos(540,1580)\\fad(300,0)}}{CREDIT[0]}")
        ev.append(f"Dialogue: 2,{ass_time(c0)},{ass_time(spec['dur'])},Credit,,0,0,0,,{{\\pos(540,1636)\\fad(300,0)\\fs32}}{CREDIT[1]}")
    path.write_text(head + "\n".join(ev) + "\n", encoding="utf-8")


def check(spec):
    shots = spec["shots"]
    card_start = spec["card"]["start"] if spec.get("card") else spec["dur"]
    t = 0.0
    for s in shots:
        if abs(s["start"] - t) > 1e-3 or s["end"] <= s["start"]:
            sys.exit(f"shots must tile 0..{card_start} with no gap or overlap (problem at {s})")
        t = s["end"]
    if abs(t - card_start) > 1e-3:
        sys.exit(f"shots end at {t}, the card/film starts at {card_start}")
    return card_start


def build(job, spec_path, out_name="film.mp4", keep=False):
    job = Path(job).resolve()
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    card_start = check(spec)
    tmp = job / "tmp_mono"
    tmp.mkdir(exist_ok=True)
    mono = spec.get("mono", True)
    parts = [shot(job, s, i, mono, tmp) for i, s in enumerate(spec["shots"])]
    if spec.get("card"):
        nfr = round(spec["dur"] * FPS) - round(card_start * FPS)
        parts.append(card_frames(spec["card"], nfr, (spec["dur"] - 3) - card_start, tmp))
    lst = tmp / "cat.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts), encoding="utf-8")
    sub = tmp / "subs.ass"
    ass(spec, card_start, sub)
    video = tmp / "video.mp4"
    sh(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
        "-vf", f"subtitles={sub}:fontsdir={FONTS}", "-r", str(FPS), *X264, "-an", str(video)])
    for p in parts:
        p.unlink(missing_ok=True)
    out = job / out_name
    audio = job / spec["audio"] if spec.get("audio") else None
    if audio and audio.exists():
        ac = ["-c:a", "copy"] if audio.suffix.lower() in (".m4a", ".aac", ".mp4") else ["-c:a", "aac", "-b:a", "320k"]
        sh(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-i", str(audio), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
            *ac, "-t", f"{spec['dur']:.3f}", "-movflags", "+faststart", str(out)])
    else:
        sh(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-c", "copy", "-movflags", "+faststart", str(out)])
    if not keep:
        shutil.rmtree(tmp)
    print(f"wrote {out}  ({probe_dur(out):.2f} s)")
    return out


def demo(job):
    job = Path(job).resolve()
    (job / "clips").mkdir(parents=True, exist_ok=True)
    sh(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=496x864:r=24:d=4.04", "-c:v", "libx264", "-crf", "30",
        str(job / "clips" / "a.mp4")])
    from PIL import Image
    Image.new("RGB", (720, 1280), (120, 120, 120)).save(job / "clips" / "b.jpg")
    spec = {"dur": 9.0, "shots": [{"start": 0, "end": 4.5, "src": "clips/a.mp4"}, {"start": 4.5, "end": 6.0, "src": "clips/b.jpg"}],
            "subs": [[0.2, 4.4, "انا اكتر واحد", "بيحب الناس", 1.5], [4.6, 6.0, "سطر واحد", ""]],
            "card": {"start": 6.0, "title": "اسم الأغنية", "by": "المطرب"}}
    (job / "spec.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    return build(job, job / "spec.json", "demo.mp4")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    if a[0] == "--demo":
        demo(a[1])
    else:
        o = a[a.index("--out") + 1] if "--out" in a else "film.mp4"
        build(a[0], a[1], o, "--keep" in a)
