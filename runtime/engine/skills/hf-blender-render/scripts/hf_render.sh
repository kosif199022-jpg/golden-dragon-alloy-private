#!/usr/bin/env bash
# Bounded resumable Cycles render (sandbox pilot). Only for approved Higgsfield session.
set -euo pipefail
if (( $# < 4 )); then echo 'usage: hf_render.sh JOB_DIR SCENE.py TOTAL_FRAMES WORKERS [ENGINE] [SAMPLES] [RES_PCT]' >&2; exit 2; fi
JOB="$1";SCENE="$2";TOTAL="$3";W="$4";ENGINE="${5:-CYCLES}";SAMPLES="${6:-24}";RES="${7:-100}"
[[ "$TOTAL" =~ ^[0-9]+$ && "$W" =~ ^[0-9]+$ && "$SAMPLES" =~ ^[0-9]+$ && "$RES" =~ ^[0-9]+$ ]] || { echo 'INVALID_NUMERIC_ARGUMENT' >&2;exit 2; }
(( TOTAL>=1 && TOTAL<=1000000 && W>=1 && W<=16 && SAMPLES>=1 && SAMPLES<=100000 && RES>=10 && RES<=100 )) || { echo 'INVALID_RANGE' >&2;exit 2; }
[[ "$ENGINE" = CYCLES || "$ENGINE" = EEVEE ]] || { echo 'INVALID_ENGINE' >&2;exit 2; }
[[ -f "$SCENE" ]] || { echo "SCENE_NOT_FOUND $SCENE" >&2;exit 2; }
B="${BLENDER:-/home/user/bd_blender/current/blender}"
[[ -x "$B" ]] || { echo 'BLENDER_NOT_INSTALLED' >&2;exit 2; }
mkdir -p "$JOB/frames" "$JOB/logs"
# Remove only zero-size/clearly incomplete output frames inside the given job directory.
for f in "$JOB"/frames/f_*.png; do
  [[ -f "$f" ]] || continue
  sz=$(stat -c%s "$f")
  if (( sz<25 )) || [[ "$(tail -c 12 "$f" | head -c 8 | tail -c 4)" != IEND ]]; then
    echo "incomplete frame: $(basename "$f")";rm -f -- "$f"
  fi
done
echo "RUNNING $(date +%s) workers=$W engine=$ENGINE samples=$SAMPLES" > "$JOB/status"
T=$(( $(nproc) / W ));(( T>=1 )) || T=1
per=$(( (TOTAL + W - 1) / W ))
pids=()
for ((i=0;i<W;i++)); do
  f0=$((i*per+1));f1=$(((i+1)*per));(( f1>TOTAL )) && f1=$TOTAL
  (( f0>TOTAL )) && continue
  OUT_DIR="$JOB" MODE=anim ENGINE="$ENGINE" SAMPLES="$SAMPLES" RES_PCT="$RES" F0="$f0" F1="$f1" \
    "$B" -b --factory-startup --python "$SCENE" -t "$T" > "$JOB/logs/w$i.log" 2>&1 &
  pids+=("$!")
done
fail=0
for p in "${pids[@]}"; do wait "$p" || fail=1; done
# Name/size checks only; full PNG verification is handled by tool hf-blender check-frames.
done_n=$(find "$JOB/frames" -maxdepth 1 -type f -name 'f_*.png' -size +1k | wc -l)
if (( done_n >= TOTAL && fail == 0 )); then
 echo "DONE $(date +%s) frames=$done_n" > "$JOB/status"
else
 echo "PARTIAL $(date +%s) frames=$done_n fail=$fail" > "$JOB/status"
fi
cat "$JOB/status"
[[ "$(cut -d' ' -f1 "$JOB/status")" = 'DONE' ]]
