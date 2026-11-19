#!/usr/bin/env bash
# Parallel frame render on the Higgsfield XL sandbox (v10.16.1, measured 2026-11-10: 732 frames 37 s instead of ~4 min).
# Usage: bash prender.sh WORKERS TOTAL_FRAMES -- command that reads $RANGE ("a,b") and writes frames a..b-1
#   e.g. bash ~/bdtools/prender.sh 4 732 -- env NODE_PATH=/usr/local/lib/node_modules node rs.js fr 30 24.4
# Run it inside ONE sandbox_exec with background:true. Never detach with nohup/&-and-exit; this script waits.
set -uo pipefail
N=$1; TOT=$2; shift 2; [ "${1:-}" = "--" ] && shift
step=$(( (TOT + N - 1) / N )); pids=(); s=$(date +%s)
for ((i=0; i<N; i++)); do a=$((i*step)); b=$(( (i+1)*step )); [ $b -gt $TOT ] && b=$TOT; [ $a -ge $b ] && continue
  RANGE="$a,$b" "$@" > "prender_$i.log" 2>&1 & pids+=($!); done
fail=0; for p in "${pids[@]}"; do wait "$p" || fail=1; done
echo "prender: workers=$N frames=$TOT seconds=$(( $(date +%s)-s )) fail=$fail"; exit $fail
