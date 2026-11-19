#!/usr/bin/env bash
# html2mp4.sh PAGE.html|URL OUT.mp4 [--w 1080] [--h 1920] [--fps 30] [--dur 5] [--workers N]
#             [--audio FILE] [--crf 18] [--preset slow] [--format png|jpeg] [--no-clock] [--keep]
# Parallel deterministic render of an HTML/CSS/JS animation (see render_frames.js), then one x264 encode.
# Workers default to the sandbox CPUs (xl = 4). Run long renders under `hfc job run NAME --` with background:true.
set -uo pipefail
[ $# -ge 2 ] || { sed -n '2,5p' "$0"; exit 2; }
SRC=$1; OUT=$2; shift 2
W=1080 H=1920 FPS=30 DUR=5 WK="" AUD="" CRF=18 PRESET=slow FMT=png CLOCK="" KEEP=0
while [ $# -gt 0 ]; do case $1 in
  --w) W=$2; shift 2;; --h) H=$2; shift 2;; --fps) FPS=$2; shift 2;; --dur) DUR=$2; shift 2;; --workers) WK=$2; shift 2;;
  --audio) AUD=$2; shift 2;; --crf) CRF=$2; shift 2;; --preset) PRESET=$2; shift 2;; --format) FMT=$2; shift 2;;
  --no-clock) CLOCK=--no-clock; shift;; --keep) KEEP=1; shift;; *) echo "html2mp4: unknown $1" >&2; exit 2;; esac; done
HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
export NODE_PATH="${NODE_PATH:-/usr/local/lib/node_modules}"
[ -n "$WK" ] || WK=$(python3 -c 'import os;print(len(os.sched_getaffinity(0)))')
TOT=$(python3 -c "print(round($DUR*$FPS))")
FR=$(mktemp -d "$HOME/.hfc_frames.XXXX"); ext=png; [ "$FMT" = jpeg ] && ext=jpg
[ -n "${HFC_JOB_DIR:-}" ] && python3 -c "print(int($TOT/$FPS*1e6))" > "$HFC_JOB_DIR/total_us"
s=$(date +%s); step=$(( (TOT + WK - 1) / WK )); pids=()
for ((i=0; i<WK; i++)); do a=$((i*step)); b=$(( (i+1)*step )); [ $b -gt $TOT ] && b=$TOT; [ $a -ge $b ] && continue
  node "$HERE/render_frames.js" "$SRC" "$FR" --w "$W" --h "$H" --fps "$FPS" --from $a --to $b --format "$FMT" $CLOCK > "$FR/worker_$i.log" 2>&1 &
  pids+=($!); done
while :; do  # progress for `hfc job status`, until all workers exit
  n=$(find "$FR" -name "*.$ext" | wc -l)
  [ -n "${HFC_JOB_DIR:-}" ] && echo "out_time_us=$(python3 -c "print(int($n/$FPS*1e6))")" >> "$HFC_JOB_DIR/progress"
  alive=0; for p in "${pids[@]}"; do kill -0 "$p" 2>/dev/null && alive=1; done; [ $alive = 0 ] && break; sleep 2; done
fail=0; for p in "${pids[@]}"; do wait "$p" || fail=1; done
n=$(find "$FR" -name "*.$ext" | wc -l); r=$(( $(date +%s) - s ))
if [ $fail = 1 ] || [ "$n" != "$TOT" ]; then echo "html2mp4: render failed frames=$n/$TOT"; cat "$FR"/worker_*.log | tail -20; exit 1; fi
AARGS=(-an); AIN=(); [ -n "$AUD" ] && { AIN=(-i "$AUD"); AARGS=(-map 0:v -map 1:a:0 -c:a aac -b:a 192k -ar 48000 -shortest); }
e0=$(date +%s)
ffmpeg -nostdin -hide_banner -loglevel error -y -framerate "$FPS" -i "$FR/%06d.$ext" "${AIN[@]}" \
  -c:v libx264 -preset "$PRESET" -crf "$CRF" -pix_fmt yuv420p "${AARGS[@]}" -movflags +faststart "$OUT" || exit 1
[ "$KEEP" = 1 ] && echo "frames kept in $FR" || rm -rf "$FR"
echo "html2mp4: $OUT ${W}x${H}@${FPS} frames=$TOT workers=$WK render_s=$r encode_s=$(( $(date +%s) - e0 )) ms_per_frame=$(( r*1000*WK/TOT ))/worker bytes=$(stat -c%s "$OUT")"
