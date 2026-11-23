#!/usr/bin/env bash
# Resumable render on the Higgsfield sandbox (run with size xl, background true).
# usage: bash render_job.sh WORKDIR FRAMES AUDIO OUT.mp4 [WORKERS] [UPLOAD_URL]
#   WORKDIR has web/ (index.html, main.js, clips.json, fx/, fonts/) and render.mjs
#   FRAMES = total frame count at 30 fps; AUDIO = voice or song file; UPLOAD_URL = signed PUT url (optional)
set -u
W=$1; N=$2; A=$3; OUT=$4; P=${5:-4}; U=${6:-}
cd "$W" || exit 2
echo "nproc $(nproc)"
[ -e node_modules ] || ln -sfn "$(npm root -g)" node_modules
node render.mjs web frames 0-$((N-1)) "$P" 2>&1 | tail -2
n=$(ls frames 2>/dev/null | wc -l); echo "frames $n / $N"
[ "$n" -ge "$N" ] || { echo "not finished: run again (finished frames are kept)"; exit 3; }
ffmpeg -nostdin -v error -y -framerate 30 -i frames/f%04d.jpg -i "$A" -map 0:v -map 1:a -c:v libx264 -preset slow -crf 17 \
  -pix_fmt yuv420p -profile:v high -c:a aac -b:a 192k -af "loudnorm=I=-14:TP=-1:LRA=11" -shortest -movflags +faststart "$OUT" || exit 1
ffprobe -v error -show_entries format=duration,size -of csv=p=0 "$OUT"
[ -n "$U" ] && curl -sf -o /dev/null -w "upload %{http_code}\n" -X PUT -H 'Content-Type: video/mp4' --upload-file "$OUT" "$U"
exit 0
