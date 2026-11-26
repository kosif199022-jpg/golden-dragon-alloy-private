#!/usr/bin/env bash
# «الراجل والست» render: beats, frames (resumable), mux with the ORIGINAL audio copied untouched.
# usage: bash make.sh JOBDIR out.mp4 [workers]
#   JOBDIR holds song.json (see song.example.json), img/n*.png (from poll.py) and the audio named in song.json.
#   Fonts: put Amiri-Bold.ttf (+ ArefRuqaa-Bold.ttf, IBMPlexSerif-Bold.ttf) in JOBDIR/fonts or web/fonts (Google Fonts, OFL; not in git).
set -e
HERE=$(cd "$(dirname "$0")" && pwd); J=$(cd "$1" && pwd); OUT=$2; NW=${3:-4}
A="$J/$(python3 -c "import json;print(json.load(open('$J/song.json'))['audio'])")"
W="$J/web"; mkdir -p "$W"; cp "$HERE/web/index.html" "$HERE/web/main.js" "$W/"; cp "$J/song.json" "$W/"
rm -rf "$W/img"; cp -r "$J/img" "$W/img"
[ -d "$W/fonts" ] || cp -r "${FONTS:-$J/fonts}" "$W/fonts" 2>/dev/null || cp -r "$HERE/web/fonts" "$W/fonts"
ls "$W/fonts/Amiri-Bold.ttf" >/dev/null || { echo "missing fonts/Amiri-Bold.ttf"; exit 2; }
ffmpeg -nostdin -v error -y -i "$A" -ac 1 -ar 22050 "$J/s.wav"
python3 -c "
import librosa,json
y,sr=librosa.load('$J/s.wav');_,b=librosa.beat.beat_track(y=y,sr=sr,units='time')
json.dump([round(float(x),3) for x in b],open('$W/beats.json','w'))" || echo '[]' > "$W/beats.json"
# frames cover the whole audio so -shortest never cuts the song
N=$(python3 -c "import subprocess,math;print(math.ceil(float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0','$A']))*30))")
cd "$J"; [ -e node_modules ] || ln -sfn "$(npm root -g)" node_modules
cp "$HERE/render.mjs" "$J/render.mjs"; node "$J/render.mjs" "$W" "$J/frames" 0-$((N-1)) "$NW"
ffmpeg -nostdin -v error -y -framerate 30 -start_number 0 -i "$J/frames/f%04d.jpg" -i "$A" -map 0:v -map 1:a \
  -c:v libx264 -preset veryfast -crf 18 -pix_fmt yuv420p -c:a copy -shortest -movflags +faststart "$OUT"
echo "done $OUT"
