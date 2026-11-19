#!/usr/bin/env python3
"""v1990 — frame-by-frame review, measured. The four checks an animation checker runs before a film goes out.

  framecheck scan VIDEO --out DIR [--sheet-fps 12] [--max-sheets 12] [--pop-min 10] [--cut-min 24]
                                  [--freeze-min 15] [--strict] [--no-images] [--json]

  pops        a frame that jumps away from BOTH neighbours while the neighbours agree (one-frame flash, stale frame, glitch)
  cuts        hard cuts; strips show [last frame before, first three frames after] for every cut
  blend cuts  ONE frame that is a mix of the shot before and the shot after, between two settled shots
              (double exposure / leaked sample at a hard cut)
  transitions fast dissolves, wipes and zoom-throughs (several mixed frames): listed with their length, not a defect
  freezes     runs of identical frames (default >= 15 frames, half a second at 30 fps)
  sheets      numbered contact sheets at --sheet-fps, so every frame number can be quoted in a note

ffmpeg/ffprobe + Python standard library (numpy is used when present, same numbers). Reads VIDEO, writes only inside --out.
Detectors PROPOSE; the sheets and strips are the ground truth. Open them and look before you write «تمام».
Exit: 0 report written, 1 --strict and pops or blend cuts were found, 2 bad input or ffmpeg failure.
"""
import argparse
import json
import math
import os
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

W = 64                                  # analysis width; height follows the aspect (even)
try:                                    # optional speed-up, identical results
    import numpy as _np
    if os.environ.get("FRAMECHECK_NO_NUMPY"):
        _np = None
except Exception:                       # pragma: no cover
    _np = None


def probe(video):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,r_frame_rate,avg_frame_rate:format=duration", "-of", "json", str(video)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise ValueError("ffprobe failed: " + r.stderr.strip()[:300])
    d = json.loads(r.stdout or "{}")
    if not d.get("streams"):
        raise ValueError("no video stream")
    s = d["streams"][0]
    rate = s.get("avg_frame_rate") if s.get("avg_frame_rate") not in (None, "0/0") else s.get("r_frame_rate")
    fps = float(Fraction(rate)) if rate and rate != "0/0" else 0.0
    if not (fps > 0 and s.get("width") and s.get("height")):
        raise ValueError("cannot read size or frame rate")
    return {"width": int(s["width"]), "height": int(s["height"]), "fps": round(fps, 6),
            "duration": float(d.get("format", {}).get("duration") or 0.0)}


def mad(a, b):
    """Mean absolute difference of two equal-length gray frames, 0..255."""
    if _np is not None:
        return float(_np.abs(_np.frombuffer(a, dtype=_np.uint8).astype(_np.int16)
                             - _np.frombuffer(b, dtype=_np.uint8).astype(_np.int16)).mean())
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def luma(a):
    return (float(_np.frombuffer(a, dtype=_np.uint8).mean()) if _np is not None else sum(a) / len(a))


def measure(video, info):
    """One decode pass. Returns d1[i] = diff(i-1, i), d2[i] = diff(i-1, i+1), mean luma per frame."""
    h = max(2, int(round(W * info["height"] / info["width"] / 2)) * 2)
    size = W * h
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-nostdin", "-i", str(video), "-map", "0:v:0", "-fps_mode", "passthrough",
                          "-vf", f"scale={W}:{h}:flags=area,format=gray", "-f", "rawvideo", "-"],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    d1, d2, lum = [0.0], [0.0], []
    prev2 = prev = None
    while True:
        buf = p.stdout.read(size)
        if len(buf) < size:
            break
        lum.append(luma(buf))
        if prev is not None:
            d1.append(mad(prev, buf))
        if prev2 is not None:
            d2.append(mad(prev2, buf))          # belongs to the middle frame (index len(lum)-2)
        prev2, prev = prev, buf
    err = p.stderr.read().decode("utf-8", "replace")
    if p.wait() != 0 or not lum:
        raise ValueError("ffmpeg decode failed: " + err.strip()[:300])
    d2.append(0.0)                              # last frame has no next neighbour
    return d1, d2[:len(lum)], lum


def detect(d1, d2, lum, fps, pop_min, cut_min, freeze_min):
    n = len(lum)
    pops, cuts, blends, transitions, freezes = [], [], [], [], []
    pop_set = set()
    for i in range(1, n - 1):
        away = min(d1[i], d1[i + 1])
        if away >= pop_min and d2[i] <= 0.35 * away:
            kind = "white" if lum[i] > 200 else "black" if lum[i] < 20 else "other"
            pops.append({"frame": i, "t": round(i / fps, 3), "away": round(away, 2), "neighbours_agree": round(d2[i], 2), "kind": kind})
            pop_set.add(i)
    # a frame that sits between the shot before and the shot after
    mixed = []
    for i in range(1, n - 1):
        if i in pop_set or (i - 1) in pop_set:
            continue
        span = d2[i]                             # frame before vs frame after
        if span >= cut_min and d1[i] >= 0.25 * span and d1[i + 1] >= 0.25 * span and max(d1[i], d1[i + 1]) <= 0.8 * span:
            mixed.append(i)
    runs = []
    for i in mixed:
        if runs and i == runs[-1][-1] + 1:
            runs[-1].append(i)
        else:
            runs.append([i])
    in_transition = set()
    for run in runs:
        i = run[0]
        before = d1[i - 1] if i - 1 >= 1 else 0.0
        after = d1[i + 2] if i + 2 < n else 0.0
        if len(run) == 1 and before <= 0.35 * d1[i] and after <= 0.35 * d1[i + 1]:
            # ONE mixed frame between two settled shots: a double exposure / leaked sample at a hard cut
            blends.append({"frame": i, "t": round(i / fps, 3), "to_prev": round(d1[i], 2), "to_next": round(d1[i + 1], 2),
                           "prev_to_next": round(d2[i], 2)})
            in_transition.update((i, i + 1))
            continue
        # several moving frames: a fast dissolve, wipe or zoom-through. Informational; widen to where the motion settles
        peak = max(d1[j] for j in range(run[0], min(n, run[-1] + 2)))
        a, b = run[0], min(n - 1, run[-1] + 1)
        while a - 1 >= 1 and d1[a - 1] >= 0.3 * peak and run[0] - a < 45:
            a -= 1
        while b + 1 < n and d1[b + 1] >= 0.3 * peak and b - run[-1] < 45:
            b += 1
        transitions.append({"first": a, "last": b, "frames": b - a + 1, "seconds": round((b - a + 1) / fps, 3), "t": round(a / fps, 3)})
        in_transition.update(range(a, b + 2))
    for i in range(1, n):
        if i in pop_set or (i - 1) in pop_set or i in in_transition:
            continue
        nxt = d1[i + 1] if i + 1 < n else 0.0
        if d1[i] >= cut_min and d1[i] >= 2.5 * max(d1[i - 1], nxt, 1.0):
            cuts.append({"frame": i, "t": round(i / fps, 3), "jump": round(d1[i], 2)})
    run = 0
    for i in range(1, n + 1):
        if i < n and d1[i] < 0.02:
            run += 1
            continue
        if run >= freeze_min:
            freezes.append({"first": i - run - 1, "last": i - 1, "frames": run + 1, "seconds": round((run + 1) / fps, 2)})
        run = 0
    return pops, cuts, blends, transitions, freezes


def _ffmpeg_images(video, vf_variants, out_pattern):
    """Try the labelled filter first, then the plain one (ffmpeg builds without drawtext / fonts)."""
    for vf in vf_variants:
        r = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-i", str(video), "-map", "0:v:0", "-fps_mode", "passthrough",
                            "-vf", vf, "-q:v", "4", str(out_pattern)], capture_output=True, text=True)
        if r.returncode == 0:
            return "labelled" if "drawtext" in vf else "plain"
    return None


def images(video, out, info, n, cuts, blends, transitions, sheet_fps, max_sheets):
    label = "drawtext=text='%{n}':x=6:y=6:fontsize=h/14:fontcolor=white:box=1:boxcolor=black@0.7:boxborderw=4,"
    made = {"sheets": [], "strips": [], "labels": None}
    cols, rows = 10, 8
    step = max(1, int(round(info["fps"] / sheet_fps)))
    while math.ceil(math.ceil(n / step) / (cols * rows)) > max_sheets:
        step += 1
    rows = max(1, min(rows, math.ceil(math.ceil(n / step) / cols)))      # a short clip gets a short sheet, not a black page
    sel = f"select='not(mod(n\\,{step}))'"
    tail = f"scale=160:-2,tile={cols}x{rows}:padding=2:margin=2"
    (out / "sheets").mkdir(parents=True, exist_ok=True)
    mode = _ffmpeg_images(video, [f"{label}{sel},{tail}", f"{sel},{tail}"], out / "sheets" / "sheet_%03d.jpg")
    made["labels"] = mode
    made["sheet_step"] = step
    made["sheets"] = sorted(p.name for p in (out / "sheets").glob("sheet_*.jpg"))
    marks = sorted({c["frame"] for c in cuts} | {b["frame"] for b in blends} | {t["last"] for t in transitions})[:96]
    if marks:
        want = sorted({f for c in marks for f in (c - 1, c, c + 1, c + 2) if 0 <= f < n})
        # a row is normally [before, +0, +1, +2]; marks closer than four frames share frames, so read the burned-in numbers
        sel = "select='" + "+".join(f"eq(n\\,{f})" for f in want) + "'"
        tail = f"scale=270:-2,tile=4x{max(1, min(8, math.ceil(len(want) / 4)))}:padding=3:margin=3"
        (out / "strips").mkdir(parents=True, exist_ok=True)
        _ffmpeg_images(video, [f"{label}{sel},{tail}", f"{sel},{tail}"], out / "strips" / "cuts_%02d.jpg")
        made["strips"] = sorted(p.name for p in (out / "strips").glob("cuts_*.jpg"))
        made["strip_frames"] = want
    return made


def scan(a):
    video, out = Path(a.video), Path(a.out)
    if not video.is_file():
        raise ValueError("video not found")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise ValueError("ffmpeg and ffprobe are required")
    out.mkdir(parents=True, exist_ok=True)
    info = probe(video)
    d1, d2, lum = measure(video, info)
    n = len(lum)
    pops, cuts, blends, transitions, freezes = detect(d1, d2, lum, info["fps"], a.pop_min, a.cut_min, a.freeze_min)
    made = {} if a.no_images else images(video, out, info, n, cuts, blends, transitions, a.sheet_fps, a.max_sheets)
    rep = {"schema": "black-dragon.framecheck.v1990", "video": video.name, "width": info["width"], "height": info["height"],
           "fps": info["fps"], "frames": n, "seconds": round(n / info["fps"], 3),
           "thresholds": {"pop_min": a.pop_min, "cut_min": a.cut_min, "freeze_min": a.freeze_min, "analysis_width": W},
           "pops": pops, "blend_cuts": blends, "cuts": cuts, "transitions": transitions, "freezes": freezes, "images": made,
           "engine": "numpy" if _np is not None else "stdlib",
           "verdict": "LOOK" if (pops or blends) else "CLEAN_BY_METRIC",
           "note": "A metric cannot see a hand through a prop or a floating foot. Open the strips and sheets; quote frame numbers in notes."}
    (out / "framecheck.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    return rep


def main(argv):
    ap = argparse.ArgumentParser(prog="framecheck", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("scan")
    s.add_argument("video")
    s.add_argument("--out", required=True)
    s.add_argument("--sheet-fps", type=float, default=12.0)
    s.add_argument("--max-sheets", type=int, default=12)
    s.add_argument("--pop-min", type=float, default=10.0)
    s.add_argument("--cut-min", type=float, default=24.0)
    s.add_argument("--freeze-min", type=int, default=15)
    s.add_argument("--strict", action="store_true")
    s.add_argument("--no-images", action="store_true")
    s.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd != "scan":
        ap.print_help()
        return 2
    if a.sheet_fps <= 0 or a.max_sheets < 1 or a.freeze_min < 2:
        print("bad options", file=sys.stderr)
        return 2
    try:
        rep = scan(a)
    except ValueError as e:
        print(f"framecheck: {e}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=1))
    else:
        print(f"{rep['video']}: {rep['frames']} فريم · {rep['fps']} fps · {rep['seconds']} ث")
        print(f"pops={len(rep['pops'])} · blend cuts={len(rep['blend_cuts'])} · cuts={len(rep['cuts'])} · transitions={len(rep['transitions'])} · freezes={len(rep['freezes'])}"
              f" · sheets={len(rep['images'].get('sheets', []))} · strips={len(rep['images'].get('strips', []))}")
        for p in rep["pops"][:12]:
            print(f"  pop    f{p['frame']} ({p['t']} ث) {p['kind']}  away={p['away']} agree={p['neighbours_agree']}")
        for b in rep["blend_cuts"][:12]:
            print(f"  blend  f{b['frame']} ({b['t']} ث) بين لقطتين: {b['to_prev']} / {b['to_next']} من {b['prev_to_next']}")
        for t in rep["transitions"][:12]:
            print(f"  trans  f{t['first']}–f{t['last']} ({t['frames']} فريم ≈ {t['seconds']} ث): نقلة سريعة، للعلم")
        for z in rep["freezes"][:8]:
            print(f"  freeze f{z['first']}–f{z['last']} ({z['seconds']} ث)")
        print(f"التقرير: {Path(a.out) / 'framecheck.json'}  ←  افتح الـstrips والـsheets وبُص بعينك قبل «تمام».")
    return 1 if a.strict and (rep["pops"] or rep["blend_cuts"]) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
