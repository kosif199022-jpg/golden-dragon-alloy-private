#!/usr/bin/env python3
"""song-map — energy map + beats per song, to pick a section (e.g. ~45 s) and cut on the beat.

    dragon.py tool song-map SONG.mp3 [SONG2.wav ...] [--window 5] [--out-dir DIR] [--json] [--force]

Prints, per song: duration, tempo, beat count and the mean loudness (dB under the song's peak RMS) of every
WINDOW-second block, so a quiet intro, applause or the full band are visible at a glance.
Writes <song>.beats.json (duration, tempo, beats in seconds) next to the song or into --out-dir;
an existing file is kept unless --force.
Needs librosa + numpy (pip, part of `setup`).
"""
import argparse, json, sys
from pathlib import Path


def analyse(path, window=5.0):
    import numpy as np, librosa
    y, sr = librosa.load(str(path), sr=22050, mono=True)
    dur = len(y) / sr
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
    bt = librosa.frames_to_time(beats, sr=sr)
    hop = sr // 2                                           # 0.5 s hops
    rms = librosa.feature.rms(y=y, hop_length=hop)[0]
    rms_db = 20 * np.log10(rms / (rms.max() + 1e-12) + 1e-9)
    per = max(1, int(round(window * 2)))
    blocks = []
    for i, s in enumerate(range(0, len(rms_db), per)):
        seg = rms_db[s:s + per]
        blocks.append({"t": round(i * window, 2), "db": round(float(seg.mean()), 1)})
    return {"file": str(path), "duration": round(dur, 3), "tempo": round(float(np.atleast_1d(tempo)[0]), 2),
            "beats": [round(float(b), 3) for b in bt], "window": window, "energy": blocks}


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="dragon.py tool song-map", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("songs", nargs="+")
    ap.add_argument("--window", type=float, default=5.0, help="seconds per energy block (default 5)")
    ap.add_argument("--out-dir", help="write the .beats.json files here instead of next to each song")
    ap.add_argument("--json", action="store_true", help="print the full result as JSON")
    ap.add_argument("--force", action="store_true", help="overwrite an existing .beats.json")
    a = ap.parse_args(argv)
    if a.window <= 0:
        ap.error("--window must be > 0")
    results, code = [], 0
    for s in a.songs:
        p = Path(s)
        if not p.is_file():
            print(f"مش لاقي: {p}", file=sys.stderr); code = 2; continue
        r = analyse(p, a.window)
        out = (Path(a.out_dir) if a.out_dir else p.parent) / (p.stem + ".beats.json")
        if out.exists() and not a.force:
            r["beats_json"] = f"kept existing {out} (use --force)"
        else:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps({k: r[k] for k in ("duration", "tempo", "beats")}, ensure_ascii=False), encoding="utf-8")
            r["beats_json"] = str(out)
        results.append(r)
        if not a.json:
            print(f"\n== {p.name}  dur {r['duration']:.1f}s  tempo {r['tempo']:.1f} bpm  beats {len(r['beats'])}")
            line = [f"{b['t']:>5.0f}s:{b['db']:5.1f}" for b in r["energy"]]
            for i in range(0, len(line), 8):
                print("  " + "  ".join(line[i:i + 8]))
            print(f"  -> {r['beats_json']}")
    if a.json:
        print(json.dumps(results, ensure_ascii=False, indent=1))
    return code


if __name__ == "__main__":
    sys.exit(main())
