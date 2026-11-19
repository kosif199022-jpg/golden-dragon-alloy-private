"""Energy map + beats for each song, to choose a ~45 s section and cut on the beat."""
import json, sys
import numpy as np, librosa
sys.stdout.reconfigure(encoding="utf-8")

for path in sys.argv[1:]:
    y, sr = librosa.load(path, sr=22050, mono=True)
    dur = len(y) / sr
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
    bt = librosa.frames_to_time(beats, sr=sr)
    rms = librosa.feature.rms(y=y, hop_length=sr // 2)[0]  # 0.5 s hops
    rms_db = 20 * np.log10(rms / rms.max() + 1e-9)
    onset = librosa.onset.onset_strength(y=y, sr=sr)
    print(f"\n== {path.split(chr(92))[-1]}  dur {dur:.1f}s  tempo {float(np.atleast_1d(tempo)[0]):.1f} bpm  beats {len(bt)}")
    # per 5 s window: loudness, so we can see quiet intro / applause / full band
    line = []
    for s in range(0, int(dur), 5):
        seg = rms_db[s * 2:(s + 5) * 2]
        line.append(f"{s:>3}s:{seg.mean():5.1f}")
    for i in range(0, len(line), 8):
        print("  " + "  ".join(line[i:i + 8]))
    out = path.rsplit(".", 1)[0] + ".beats.json"
    json.dump({"duration": dur, "tempo": float(np.atleast_1d(tempo)[0]), "beats": [round(float(b), 3) for b in bt]},
              open(out, "w", encoding="utf-8"))
