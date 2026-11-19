#!/usr/bin/env bash
# Render JOB/film/index.html, add JOB/song.m4a at its exact length, verify.   v1990.5
#   bash render.sh JOB OUT.mp4            full render
#   bash render.sh JOB OUT.mp4 --from S   keep the frames before S from JOB/video.mp4 and render only S..end
# Run it with run_in_background and a long timeout (the harness stops a task after its time limit).
# --from is how a render that died near the end (Page.captureScreenshot, a dark dip in the last seconds)
# was saved on 10 Nov without starting over. Needs ~2x the film size free on disk.
set -u
JOB="$(cd "$1" && pwd)"; OUT="$2"; FROM="${4:-}"
[ "${3:-}" = "--from" ] || FROM=""
SK="$(cd "$(dirname "$0")/../.." && pwd)"
export DRAGON_HOME="$SK/app"
cd "$JOB/film" || exit 1
mkdir -p "$JOB/tmp"
if [ -n "$FROM" ]; then
  FR=$(python3 -c "print(int(round($FROM*30)))")
  ffmpeg -v error -y -i "$JOB/video.mp4" -an -frames:v "$FR" -c copy "$JOB/part1.mp4" || exit 1
  TMPDIR="$JOB/tmp" node "$SK/app/engines/render/render.cjs" --in index.html --out "$JOB/part2.mp4" --start "$FROM" --recycle 20 > "$JOB/render.log" 2>&1
  rc=$?
  if [ $rc = 0 ]; then
    printf "file '%s'\nfile '%s'\n" "$JOB/part1.mp4" "$JOB/part2.mp4" > "$JOB/cat.txt"
    ffmpeg -v error -y -f concat -safe 0 -i "$JOB/cat.txt" -c copy "$JOB/video.mp4" && rm -f "$JOB/part1.mp4" "$JOB/part2.mp4" "$JOB/cat.txt"
  fi
else
  TMPDIR="$JOB/tmp" node "$SK/app/engines/render/render.cjs" --in index.html --out "$JOB/video.mp4" --recycle 30 > "$JOB/render.log" 2>&1
  rc=$?
fi
rm -rf -- "$JOB/tmp"
[ $rc = 0 ] || { echo "EXIT=$rc  (video.mp4 kept: re-run with --from <seconds before the failure>)" >> "$JOB/render.log"; exit $rc; }
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$JOB/song.m4a")
python3 "$SK/scripts/dragon.py" mux "$JOB/video.mp4" "$JOB/song.m4a" "$JOB/$OUT" --duration "$DUR" >> "$JOB/render.log" 2>&1 && rm -f "$JOB/video.mp4"
python3 "$SK/scripts/dragon.py" verify "$JOB/$OUT" --expect 1080x1920 --duration "$DUR" > "$JOB/verify.txt" 2>&1
echo "EXIT=0 verify=$?" >> "$JOB/render.log"
