#!/usr/bin/env python3
"""Maven Reels: break a reference reel down so its style can be copied. (c) 2026 Maven.

usage: python analyze.py ref.mp4 out_dir [--lang ar] [--no-words]

Writes into out_dir:
  sheet.jpg      the whole reel, one frame per second, with times     -> look at it
  hook.jpg       the first 3 seconds at 4 frames a second            -> look at it
  shots.jpg      the first frame of every shot (if the reel has cuts)
  words.json     what the voice says, word by word (needs faster-whisper)
  analysis.json  every number below
  analysis.md    the numbers as a short report to read first

Measures: size, length, cuts and shot lengths, how much moves over time, colours, brightness,
loudness, the beat of the music, and speaking speed. It does not judge taste: you do that by
looking at the sheets and filling in references/style-card.md.
"""
import argparse
import json
import math
import os
import shutil
import subprocess
import sys

try:
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit("numpy and pillow are missing. Run: pip install -r requirements.txt")

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "..", "assets", "fonts", "IBMPlexSansArabic-SemiBold.ttf")


def run(args, binary=False):
    p = subprocess.run(args, capture_output=True)
    if p.returncode:
        raise SystemExit(f"{args[0]} failed: {p.stderr.decode('utf8', 'replace')[-400:]}")
    return p.stdout if binary else p.stdout.decode("utf8", "replace")


def probe(path):
    info = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path]))
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    num, den = video.get("avg_frame_rate", "30/1").split("/")
    return {
        "width": int(video["width"]), "height": int(video["height"]),
        "fps": round(float(num) / float(den or 1), 2),
        "seconds": round(float(info["format"]["duration"]), 2),
        "audio": any(s["codec_type"] == "audio" for s in info["streams"]),
    }


def frames(path, fps, w, h, gray=False, start=0.0, length=None):
    """Raw frames as a numpy array (n, h, w[, 3])."""
    args = ["ffmpeg", "-v", "error", "-ss", str(start), "-i", path]
    if length:
        args += ["-t", str(length)]
    args += ["-vf", f"fps={fps},scale={w}:{h}:flags=area", "-f", "rawvideo",
             "-pix_fmt", "gray" if gray else "rgb24", "-"]
    raw = np.frombuffer(run(args, binary=True), np.uint8)
    shape = (h, w) if gray else (h, w, 3)
    return raw.reshape((-1,) + shape)


def font(size):
    try:
        return ImageFont.truetype(FONT, size)
    except OSError:
        return ImageFont.load_default()


def sheet(images, times, cols, out, label_size=22):
    if not len(images):
        return
    h, w = images[0].shape[:2]
    rows = math.ceil(len(images) / cols)
    canvas = Image.new("RGB", (cols * w + (cols - 1) * 4, rows * h + (rows - 1) * 4), (20, 20, 20))
    draw = ImageDraw.Draw(canvas)
    f = font(label_size)
    for i, (img, t) in enumerate(zip(images, times)):
        x, y = (i % cols) * (w + 4), (i // cols) * (h + 4)
        canvas.paste(Image.fromarray(img), (x, y))
        tag = f"{t:.1f}s" if t < 60 else f"{int(t // 60)}:{t % 60:04.1f}"
        box = draw.textbbox((0, 0), tag, font=f)
        draw.rectangle((x, y, x + box[2] + 12, y + box[3] + 8), fill=(0, 0, 0))
        draw.text((x + 6, y + 2), tag, font=f, fill=(255, 220, 0))
    canvas.save(out, quality=88)


def cuts_and_motion(path, seconds):
    """Hard cuts and a 'how much changes' curve from small grey frames at 15 fps."""
    fps = 15
    g = frames(path, fps, 72, 128, gray=True).astype(np.float32)
    if len(g) < 3:
        return [], [], fps
    diff = np.abs(np.diff(g, axis=0)).mean(axis=(1, 2)) / 255.0          # 0..1 per frame step
    # histogram distance catches cuts between frames that are similar on average
    hist = np.stack([np.histogram(f, bins=32, range=(0, 255))[0] for f in g]).astype(np.float32)
    hist /= hist.sum(axis=1, keepdims=True)
    hd = np.abs(np.diff(hist, axis=0)).sum(axis=1) / 2
    score = 0.6 * diff / max(diff.max(), 1e-6) + 0.4 * hd
    base = np.median(score)
    cuts = []
    for i in range(1, len(score) - 1):
        local = np.median(score[max(0, i - 8): i + 8])
        if score[i] > max(0.18, 4 * local, 3 * base) and score[i] >= score[i - 1] and score[i] >= score[i + 1]:
            t = round((i + 1) / fps, 2)
            if not cuts or t - cuts[-1] > 0.25:
                cuts.append(t)
    # motion per half second, 0..100
    per = fps // 2
    motion = [round(float(diff[i:i + per].mean()) * 1000, 1) for i in range(0, len(diff), per)]
    return cuts, motion, fps


def palette(path, seconds, k=7):
    imgs = frames(path, max(0.5, 24 / max(seconds, 1)), 54, 96)
    px = imgs.reshape(-1, 3).astype(np.float32)
    rng = np.random.default_rng(1)
    px = px[rng.choice(len(px), min(len(px), 40000), replace=False)]
    centres = px[rng.choice(len(px), k, replace=False)]
    for _ in range(20):
        lab = np.argmin(((px[:, None] - centres[None]) ** 2).sum(-1), axis=1)
        centres = np.array([px[lab == j].mean(0) if (lab == j).any() else centres[j] for j in range(k)])
    share = np.bincount(lab, minlength=k) / len(lab)
    order = np.argsort(-share)
    cols = [{"hex": "#%02x%02x%02x" % tuple(int(v) for v in centres[j]), "share": round(float(share[j]), 3)} for j in order]
    hsv = np.array(Image.fromarray(imgs.reshape(-1, 54, 3)).convert("HSV")).reshape(-1, 3)
    return cols, round(float(hsv[:, 2].mean() / 2.55), 1), round(float(hsv[:, 1].mean() / 2.55), 1)


def audio_stats(path, seconds):
    out = {}
    log = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"],
                         capture_output=True).stderr.decode("utf8", "replace")
    for key, name in (("I:", "lufs"), ("LRA:", "lra"), ("Peak:", "true_peak")):
        idx = log.rfind(key)
        if idx >= 0:
            try:
                out[name] = float(log[idx + len(key):].split()[0])
            except ValueError:
                pass
    pcm = np.frombuffer(run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", "8000", "-f", "s16le", "-"], binary=True), np.int16)
    if not len(pcm):
        return out
    x = pcm.astype(np.float32) / 32768
    hop = 80                                                       # 100 envelope points a second
    env = np.sqrt(np.convolve(x ** 2, np.ones(hop) / hop, "same")[::hop] + 1e-9)
    onset = np.maximum(np.diff(np.log(env)), 0)
    onset -= onset.mean()
    ac = np.correlate(onset, onset, "full")[len(onset) - 1:]
    lo, hi = int(100 * 60 / 180), int(100 * 60 / 70)               # 70-180 BPM
    if hi < len(ac):
        lag = lo + int(np.argmax(ac[lo:hi]))
        strength = float(ac[lag] / (ac[0] + 1e-9))
        out["bpm_guess"] = round(6000 / lag, 1)
        out["beat_strength"] = round(strength, 2)                 # > 0.3 means a clear steady beat
    quiet = env < 10 ** (-40 / 20)
    out["silent_share"] = round(float(quiet.mean()), 2)
    return out


def words(path, lang, outdir):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None, "faster-whisper is not installed, so the voice was not transcribed"
    model = WhisperModel(os.environ.get("MAVEN_WHISPER_MODEL", "medium"), compute_type="int8")
    parts, info = model.transcribe(path, language=lang or None, word_timestamps=True, vad_filter=True)
    said = [w for p in parts for w in (p.words or [])]
    data = {"words": [[w.word.strip(), round(w.start, 2)] for w in said], "ends": [round(w.end, 2) for w in said]}
    with open(os.path.join(outdir, "words.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=0)
    return data, None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("out")
    ap.add_argument("--lang", default="ar", help="voice language for the transcript (ar, en, ...); 'auto' to detect")
    ap.add_argument("--no-words", action="store_true", help="skip the transcript")
    a = ap.parse_args()
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg is missing")
    os.makedirs(a.out, exist_ok=True)
    info = probe(a.video)
    secs = info["seconds"]
    tw = 216 if info["height"] >= info["width"] else 384
    th = round(tw * info["height"] / info["width"] / 2) * 2

    every = 1.0 if secs <= 60 else secs / 60
    imgs = frames(a.video, 1 / every, tw, th)
    sheet(imgs, [i * every for i in range(len(imgs))], 10, os.path.join(a.out, "sheet.jpg"))
    hook = frames(a.video, 4, tw, th, length=3)
    sheet(hook, [i / 4 for i in range(len(hook))], 6, os.path.join(a.out, "hook.jpg"))

    cuts, motion, _ = cuts_and_motion(a.video, secs)
    if cuts:
        shot_imgs = [frames(a.video, 1, tw, th, start=t + 0.05, length=0.5)[:1] for t in [0.0] + cuts]
        shot_imgs = np.concatenate([s for s in shot_imgs if len(s)])
        sheet(shot_imgs, [0.0] + cuts, 10, os.path.join(a.out, "shots.jpg"))
    edges = [0.0] + cuts + [secs]
    shots = [round(b - a_, 2) for a_, b in zip(edges, edges[1:])]

    cols, bright, sat = palette(a.video, secs)
    report = {
        "file": os.path.abspath(a.video), **info,
        "aspect": "9:16" if abs(info["width"] / info["height"] - 9 / 16) < 0.02 else f"{info['width']}x{info['height']}",
        "cuts": cuts, "shot_count": len(shots),
        "shot_seconds": {"mean": round(float(np.mean(shots)), 2), "shortest": min(shots), "longest": max(shots)},
        "motion_per_half_second": motion,
        "palette": cols, "brightness": bright, "saturation": sat,
    }
    if info["audio"]:
        report["audio"] = audio_stats(a.video, secs)
        if not a.no_words:
            data, why = words(a.video, None if a.lang == "auto" else a.lang, a.out)
            if data and data["words"]:
                n, first, last = len(data["words"]), data["words"][0][1], data["ends"][-1]
                report["voice"] = {"words": n, "first_word_at": first, "last_word_ends": last,
                                   "words_per_second": round(n / max(last - first, 0.1), 2)}
            elif why:
                report["voice"] = {"note": why}

    with open(os.path.join(a.out, "analysis.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)

    m = motion or [0]
    still = sum(1 for v in m if v < 4) / len(m)
    lines = [
        f"# Reel analysis: {os.path.basename(a.video)}", "",
        f"- {report['aspect']}, {secs} s, {info['fps']} fps",
        f"- {len(shots)} shots, {len(cuts)} hard cuts, average shot {report['shot_seconds']['mean']} s "
        f"(shortest {report['shot_seconds']['shortest']}, longest {report['shot_seconds']['longest']})"
        + ("  -> one continuous camera: changes come from moves and pops, not cuts" if len(cuts) <= 2 and secs > 12 else ""),
        f"- Movement: average {round(float(np.mean(m)), 1)}, busiest half-second {max(m)} at {m.index(max(m)) / 2:.1f} s, "
        f"{round(still * 100)}% of the time nearly still",
        f"- Colours: " + ", ".join(f"{c['hex']} {round(c['share'] * 100)}%" for c in cols),
        f"- Brightness {bright}/100, saturation {sat}/100",
    ]
    au = report.get("audio")
    if au:
        lines.append(f"- Sound: {au.get('lufs')} LUFS, true peak {au.get('true_peak')} dB, range {au.get('lra')} LU, "
                     f"beat ~{au.get('bpm_guess')} BPM (strength {au.get('beat_strength')}, >0.3 = steady beat), "
                     f"{round(au.get('silent_share', 0) * 100)}% silent")
    v = report.get("voice")
    if v and "words" in v:
        lines.append(f"- Voice: {v['words']} words, first word at {v['first_word_at']} s, "
                     f"{v['words_per_second']} words a second -> see words.json")
    elif v:
        lines.append(f"- Voice: {v['note']}")
    lines += ["", "Now look at sheet.jpg and hook.jpg" + (" and shots.jpg" if cuts else "")
              + ", then fill in references/style-card.md."]
    with open(os.path.join(a.out, "analysis.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
