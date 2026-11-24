#!/usr/bin/env bash
# Fast lane step 1 (Higgsfield sandbox): download a reel and measure everything in ~2 min.
# usage: bash prep.sh URL WORKDIR  -> src.mp4 voice.m4a words.json scenes.json sheet.jpg caps.jpg
set -u; URL=$1; W=$2; mkdir -p "$W" && cd "$W"
export HOME=/home/user PYTHONPATH=/home/user/pylib
T0=$(date +%s)
[ -s src.mp4 ] || timeout 110 python3 -m yt_dlp --impersonate chrome -f b -o src.mp4 --no-part -q --no-progress --write-info-json "$URL"
ffmpeg -nostdin -v error -y -i src.mp4 -vn -c:a copy voice.m4a
ffmpeg -nostdin -v error -y -i src.mp4 -vn -ac 1 -ar 16000 -af loudnorm=I=-18 a16.wav
python3 - <<'PY' &
import json
from faster_whisper import WhisperModel
m = WhisperModel('small', compute_type='int8', cpu_threads=3)
segs, _ = m.transcribe('a16.wav', language='ar', word_timestamps=True, vad_filter=False)
W = [[w.word.strip(), round(w.start, 2), round(w.end, 2)] for s in segs for w in s.words]
json.dump(W, open('words.json', 'w'), ensure_ascii=False)
PY
python3 - <<'PY'
import subprocess, json, numpy as np
p = subprocess.run(['ffmpeg','-nostdin','-v','error','-i','src.mp4','-vf','scale=54:96','-f','rawvideo','-pix_fmt','rgb24','-'], capture_output=True)
a = np.frombuffer(p.stdout, np.uint8).reshape(-1, 96, 54, 3).astype(float)
g = a.mean(axis=3); foot = g[:, 50:, :]
d = [np.abs(foot[i] - foot[i-1]).mean() for i in range(1, len(a))]
cuts = [0.0]
for i, v in enumerate(d):
    t = (i + 1) / 30
    if v > 14 and t - cuts[-1] > 0.6: cuts.append(round(t, 2))
dur = len(a) / 30; sc = []
for k, c in enumerate(cuts):
    e = cuts[k + 1] if k + 1 < len(cuts) else dur
    m = a[int((c + e) / 2 * 30)]
    R, G, B = m[..., 0].mean(), m[..., 1].mean(), m[..., 2].mean()
    sc.append(dict(a=c, b=round(e, 2), luma=round(.299*R+.587*G+.114*B, 1), warm=round(R - B, 1)))
json.dump(dict(dur=round(dur, 3), scenes=sc), open('scenes.json', 'w'))
print('scenes', len(sc), 'dur', round(dur, 2))
PY
ffmpeg -nostdin -v error -y -i src.mp4 -vf "fps=1,scale=110:-1,tile=12x6:padding=2" -frames:v 1 sheet.jpg
ffmpeg -nostdin -v error -y -i src.mp4 -vf "fps=1,crop=iw:ih*0.14:0:ih*0.42,scale=360:-1,tile=4x16:padding=2" -frames:v 1 caps.jpg
wait
echo "prep done in $(( $(date +%s) - T0 )) s"
