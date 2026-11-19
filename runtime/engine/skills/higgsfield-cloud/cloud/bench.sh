#!/usr/bin/env bash
# bench.sh — the SAME fixed benchmark on the Higgsfield sandbox (standard / xl) and on Windows (Git Bash),
# so speed ratios are measured, not guessed. Prints one JSON line. ~20-60 s.
#   A: 10 s 1920x1080@30 testsrc2  -> libx264 medium crf20   (typical 16:9 export)
#   B: 10 s 1080x1920@30 testsrc2+noise -> libx264 slow crf18 (hard 9:16 reel export)
#   C: pure-Python single-core loop (scripts, captions, analysis)
#   --quick : A only (~5-8 s). XL speed varied 1.9x between two allocations on 2026-11-11, so run this
#             at the start of every heavy session and pass A to `hfc.py plan/split --xl-a SECONDS`.
set -uo pipefail
PY=python3; { command -v python3 >/dev/null 2>&1 && python3 -c 1 >/dev/null 2>&1; } || PY=python
now() { $PY -c 'import time;print(f"{time.time():.3f}")'; }
el()  { awk "BEGIN{printf \"%.2f\", $2-$1}"; }
FF=(ffmpeg -nostdin -hide_banner -loglevel error -y)
t0=$(now); "${FF[@]}" -f lavfi -i testsrc2=size=1920x1080:rate=30 -t 10 -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -f null - ; t1=$(now)
if [ "${1:-}" = "--quick" ]; then
  printf '{"cpus":%s,"A_1080p_medium_s":%s}\n' "$($PY -c 'import os
try: print(len(os.sched_getaffinity(0)))
except Exception: print(os.cpu_count())')" "$(el $t0 $t1)"; exit 0; fi
"${FF[@]}" -f lavfi -i "testsrc2=size=1080x1920:rate=30,noise=alls=20:allf=t+u" -t 10 -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p -f null - ; t2=$(now)
$PY -c 'import math
s=0.0
for i in range(1,6_000_001): s+=math.sqrt(i)' ; t3=$(now)
cpus=$($PY -c 'import os
try: print(len(os.sched_getaffinity(0)))
except Exception: print(os.cpu_count())')
host=$(uname -s | cut -c1-10)
ffv=$(ffmpeg -hide_banner -version | head -1 | awk '{print $3}')
printf '{"host":"%s","cpus":%s,"ffmpeg":"%s","A_1080p_medium_s":%s,"B_reel_slow_noise_s":%s,"C_python_s":%s}\n' \
  "$host" "$cpus" "$ffv" "$(el $t0 $t1)" "$(el $t1 $t2)" "$(el $t2 $t3)"
