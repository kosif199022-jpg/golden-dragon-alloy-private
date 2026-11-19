#!/usr/bin/env bash
# Parallel frame render inside the Higgsfield sandbox. Run with background:true.
# usage: bash hf_render.sh JOB_DIR SCENE.py TOTAL_FRAMES WORKERS [ENGINE] [SAMPLES] [RES_PCT]
# Each worker renders a contiguous range with use_overwrite=False + placeholders, so re-running resumes.
set -u
JOB="$1"; SCENE="$2"; TOTAL="$3"; W="${4:-4}"; ENGINE="${5:-CYCLES}"; SAMPLES="${6:-24}"; RES="${7:-100}"
B="${BLENDER:-/home/user/bd_blender/current/blender}"
mkdir -p "$JOB/frames" "$JOB/logs"
# resume safety: a run killed by the 15-min background cap leaves 0-byte placeholders and maybe a
# half-written PNG. Drop both so they get rendered again (a valid PNG ends with the IEND chunk).
find "$JOB/frames" -name 'f_*.png' -size -1k -delete
for f in "$JOB"/frames/f_*.png; do
  [ -e "$f" ] || break
  tail -c 12 "$f" | grep -q IEND || { echo "truncated: $f"; rm -f "$f"; }
done
echo "RUNNING $(date +%s) workers=$W engine=$ENGINE samples=$SAMPLES" > "$JOB/status"
# threads per worker: split cores evenly
T=$(( $(nproc) / W )); [ "$T" -lt 1 ] && T=1
per=$(( (TOTAL + W - 1) / W ))
pids=()
for i in $(seq 0 $((W-1))); do
  f0=$(( i*per + 1 )); f1=$(( (i+1)*per )); [ "$f1" -gt "$TOTAL" ] && f1=$TOTAL
  [ "$f0" -gt "$TOTAL" ] && continue
  OUT_DIR="$JOB" MODE=anim ENGINE="$ENGINE" SAMPLES="$SAMPLES" RES_PCT="$RES" F0=$f0 F1=$f1 \
    "$B" -b --factory-startup --python "$SCENE" -t "$T" > "$JOB/logs/w$i.log" 2>&1 &
  pids+=($!)
done
fail=0
for p in "${pids[@]}"; do wait "$p" || fail=1; done
# placeholders are 0-byte files: a frame is done only if its PNG is non-empty
done_n=$(find "$JOB/frames" -name 'f_*.png' -size +1k | wc -l)
if [ "$done_n" -ge "$TOTAL" ]; then echo "DONE $(date +%s) frames=$done_n" > "$JOB/status"
else
  find "$JOB/frames" -name 'f_*.png' -size -1k -delete   # clear placeholders so a resume re-renders them
  echo "PARTIAL $(date +%s) frames=$done_n fail=$fail" > "$JOB/status"
fi
cat "$JOB/status"
