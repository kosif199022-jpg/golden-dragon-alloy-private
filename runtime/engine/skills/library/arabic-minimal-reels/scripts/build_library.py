#!/usr/bin/env python3
"""Build your own reference library from videos you chose.

Needs ffmpeg on the path, plus: pip install numpy pillow
Optional, for word-level transcripts: pip install faster-whisper

  python build_library.py shots  --videos DIR --out WORK [--whisper small.en]
      Finds the shots of every .mp4 in DIR, writes WORK/shots.json,
      one numbered contact sheet per video (WORK/sheets/<video>.jpg)
      and a labels template (WORK/labels.json).

  (now look at each sheet and fill in labels.json:
   {"<video>": {"<shot number>": "<scene type>"}}. Unlisted shots count as face.)

  python build_library.py build  --videos DIR --out WORK --library LIB
      Writes LIB/<scene-type>/<nn>/ with keyframes.jpg, first.jpg, peak.jpg,
      last.jpg and info.json for every labelled moment.

The library holds other people's frames. Keep it private. Don't publish it.
"""
import argparse, glob, json, os, subprocess
import numpy as np
from PIL import Image, ImageDraw

W, H = 180, 320
TYPES = ["captions", "broll-text", "painting-text", "line-text", "line-illustration",
         "text-centric", "center-illustration", "side-illustration", "object-text", "graph-stats"]


def probe_fps(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=r_frame_rate", "-of", "json", path], capture_output=True, text=True).stdout
    n, d = json.loads(out)["streams"][0]["r_frame_rate"].split("/")
    return int(n) / int(d)


def load(path, w=W, h=H):
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-fps_mode", "passthrough", "-vf",
                        f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
    a = np.frombuffer(p.stdout, dtype=np.uint8)
    n = a.size // (w * h * 3)
    return a[: n * w * h * 3].reshape(n, h, w, 3)


def find_shots(frames):
    """Hard cuts, plus runs of 3 or more very different frames (soft transitions)."""
    g = (frames[..., 0].astype(np.int16) * 3 + frames[..., 1].astype(np.int16) * 6 + frames[..., 2].astype(np.int16)) // 10
    n = len(g)
    diff, act = np.zeros(n), np.zeros(n)
    d = np.abs(g[1:] - g[:-1])
    diff[1:], act[1:] = d.mean((1, 2)), (d > 12).mean((1, 2))
    base = np.array([np.median(diff[max(0, i - 6): i + 7]) for i in range(n)])
    cut = (diff > 14) & (act > 0.18) & (diff > 2.5 * base + 4)
    hi = (diff > 10) & (act > 0.25)
    i = 0
    while i < n:
        if hi[i]:
            j = i
            while j + 1 < n and hi[j + 1]:
                j += 1
            if j - i + 1 >= 3:
                cut[i: j + 1] = True
            i = j + 1
        else:
            i += 1
    shots, start, i = [], 0, 1
    while i < n:
        if cut[i]:
            j = i
            while j + 1 < n and (cut[j + 1] or (j + 2 < n and cut[j + 2])):
                j += 1
            if i - start >= 3:
                shots.append((start, i - 1))
            start = j + 1 if j > i else i
            i = j + 1
        else:
            i += 1
    if n - start >= 3:
        shots.append((start, n - 1))
    return shots, diff


def sheet(frames, shots, fps, out, tw=100, cols=12):
    th = int(tw * 16 / 9)
    rows = (len(shots) + cols - 1) // cols
    im = Image.new("RGB", (cols * tw, rows * (th + 12)), (255, 255, 255))
    dr = ImageDraw.Draw(im)
    for i, (a, b) in enumerate(shots):
        x, y = (i % cols) * tw, (i // cols) * (th + 12)
        f = a + int((b - a) * 0.85)
        im.paste(Image.fromarray(frames[f]).resize((tw, th)), (x, y + 12))
        dr.text((x + 1, y), f"{i} {a / fps:.1f}+{(b - a + 1) / fps:.1f}", fill=(0, 0, 0))
    im.save(out, quality=82)


def transcribe(path, model):
    from faster_whisper import WhisperModel
    segs, _ = WhisperModel(model, device="cpu", compute_type="int8").transcribe(path, word_timestamps=True)
    return [dict(w=w.word.strip(), s=round(w.start, 3), e=round(w.end, 3)) for s in segs for w in s.words]


def cmd_shots(a):
    os.makedirs(f"{a.out}/sheets", exist_ok=True)
    data, labels = {}, {}
    for path in sorted(glob.glob(f"{a.videos}/*.mp4")):
        key = os.path.basename(path)[:-4]
        fps = probe_fps(path)
        frames = load(path)
        shots, _ = find_shots(frames)
        sheet(frames, shots, fps, f"{a.out}/sheets/{key}.jpg")
        words = transcribe(path, a.whisper) if a.whisper else []
        data[key] = dict(fps=fps, frames=len(frames), shots=shots, words=words)
        labels[key] = {}
        print(key, len(shots), "shots", round(len(frames) / fps, 1), "s")
    json.dump(data, open(f"{a.out}/shots.json", "w", encoding="utf-8"), ensure_ascii=False)
    if not os.path.exists(f"{a.out}/labels.json"):
        json.dump(labels, open(f"{a.out}/labels.json", "w"), indent=1)


def cmd_build(a):
    data = json.load(open(f"{a.out}/shots.json", encoding="utf-8"))
    labels = json.load(open(f"{a.out}/labels.json"))
    count = {}
    for key, v in data.items():
        lab = labels.get(key, {})
        frames = load(f"{a.videos}/{key}.mp4", 360, 640)
        moments, cur = [], None
        for i, (s, e) in enumerate(v["shots"]):
            t = lab.get(str(i))
            if t is None:
                cur = None
                continue
            if t not in TYPES:
                raise SystemExit(f"Unknown scene type {t!r} for {key} shot {i}. Use one of {TYPES}")
            if cur and cur["type"] == t and t != "broll-text":
                cur["b"] = e
                continue
            cur = dict(type=t, a=s, b=e)
            moments.append(cur)
        for m in moments:
            fs = list(range(m["a"], min(m["b"], len(frames) - 1) + 1))
            pick = [fs[int(t * (len(fs) - 1))] for t in np.linspace(0, 1, 10)]
            pick = sorted(set(pick))
            # busiest late frame stands in for the settled layout
            late = fs[len(fs) // 3:] or fs
            peak = max(late[:-1] or late, key=lambda f: float(np.abs(frames[f].astype(np.int16) - np.median(frames[f])).mean()))
            count[m["type"]] = count.get(m["type"], 0) + 1
            d = f"{a.library}/{m['type']}/{count[m['type']]:03d}"
            os.makedirs(d, exist_ok=True)
            tw, th = 150, 267
            im = Image.new("RGB", (len(pick) * tw, th + 18), (255, 255, 255))
            dr = ImageDraw.Draw(im)
            for j, f in enumerate(pick):
                im.paste(Image.fromarray(frames[f]).resize((tw - 2, th)), (j * tw, 18))
                dr.text((j * tw + 2, 3), f"f{f} +{(f - m['a']) / v['fps']:.2f}s", fill=(180, 0, 0))
            im.save(f"{d}/keyframes.jpg", quality=78)
            for name, f in (("first", fs[min(1, len(fs) - 1)]), ("peak", peak), ("last", fs[max(0, len(fs) - 2)])):
                Image.fromarray(frames[f]).save(f"{d}/{name}.jpg", quality=85)
            t0, t1 = m["a"] / v["fps"], (m["b"] + 1) / v["fps"]
            words = [x for x in v["words"] if t0 <= (x["s"] + x["e"]) / 2 < t1]
            json.dump(dict(source=key, scene_type=m["type"], start_s=round(t0, 3), end_s=round(t1, 3),
                           start_frame=m["a"], end_frame=m["b"], fps=round(v["fps"], 3),
                           spoken=" ".join(x["w"] for x in words), word_times=words, keyframes=pick),
                      open(f"{d}/info.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(count, sum(count.values()), "moments")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("shots")
    s.add_argument("--videos", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--whisper")
    b = sp.add_parser("build")
    b.add_argument("--videos", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--library", required=True)
    a = ap.parse_args()
    (cmd_shots if a.cmd == "shots" else cmd_build)(a)
