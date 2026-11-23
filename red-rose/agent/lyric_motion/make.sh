#!/usr/bin/env bash
# Lyric motion reel, steps 2-3: render the frames (resumable) and encode with the song at -14 LUFS.
# usage: bash make.sh song.json out.mp4 [workers]   (needs web/fonts/ArefRuqaa-Bold.ttf and Montserrat.ttf)
set -e
J=$1; OUT=$2; W=${3:-4}
N=$(python3 -c "import json,sys;print(round(float(json.load(open('$J'))['dur'])*30))")
A=$(python3 -c "import json;print(json.load(open('$J'))['audio'])")
[ -e node_modules ] || ln -sfn "$(npm root -g)" node_modules
node render.mjs web frames 0-$((N-1)) $W
[ "$(ls frames | wc -l)" -ge "$N" ] || { echo "frames incomplete: run again (render resumes)"; exit 3; }
ffmpeg -nostdin -v error -y -framerate 30 -i frames/f%04d.jpg -i "$A" -map 0:v -map 1:a -c:v libx264 -preset slow -crf 17 \
  -pix_fmt yuv420p -c:a aac -b:a 256k -af "loudnorm=I=-14:TP=-1:LRA=11" -shortest -movflags +faststart "$OUT"
echo "done $OUT"
