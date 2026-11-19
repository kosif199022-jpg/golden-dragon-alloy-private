#!/usr/bin/env bash
# QC gate for a final MP4 inside the Higgsfield sandbox (mirrors `dragon.py verify`; QA.md).
# Usage: bash qc.sh FINAL.mp4 DURATION_SECONDS     -> exit 0 = deliverable, 1 = fix first
F=$1; D=$2; fail=0
WH=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0:s=x "$F"); W=${WH%x*}; H=${WH#*x}
FR=$(ffprobe -v error -select_streams v:0 -count_frames -show_entries stream=nb_read_frames -of csv=p=0 "$F")
AC=$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 "$F")
EXP=$(python3 -c "print(round($D*30))")
ERR=$(ffmpeg -nostdin -v error -i "$F" -f null - 2>&1 | wc -l)
ffmpeg -nostdin -v error -i "$F" -vf "scale=54:96,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=/tmp/yavg_qc.txt" -f null -
BLK=$(python3 -c "
import re;v=[float(x) for x in re.findall(r'YAVG=([\d.]+)',open('/tmp/yavg_qc.txt').read())];n=len(v)
print(sum(1 for i in range(18,max(18,n-45)) if v[i]<17.5))")
LOUD=$(ffmpeg -nostdin -i "$F" -af ebur128=peak=true -f null - 2>&1 | grep -E "^\s+(I|Peak):" | tail -2 | awk '{print $2}' | tr '\n' ' ')
read I TP <<<"$LOUD"
[ "$W"x"$H" = "1080x1920" ] || { echo "FAIL size ${W}x${H}"; fail=1; }
[ "$FR" = "$EXP" ] || { echo "FAIL frames $FR != $EXP"; fail=1; }
[ "$AC" = "aac" ] || { echo "FAIL audio codec '$AC' (must be AAC)"; fail=1; }
[ "$ERR" = "0" ] || { echo "FAIL decode errors: $ERR lines"; fail=1; }
[ "$BLK" = "0" ] || { echo "FAIL black frames inside: $BLK"; fail=1; }
SZ=$(stat -c%s "$F"); MBPS=$(python3 -c "print(round($SZ*8/$D/1e6,1))")
python3 -c "import sys;sys.exit(0 if $MBPS<=20 else 1)" || { echo "FAIL size $((SZ/1048576)) MB = ${MBPS} Mbps avg (> 20): re-encode -crf 19 -maxrate 14M -bufsize 28M -c:a copy"; fail=1; }
python3 -c "import sys;sys.exit(0 if float('$TP')<=-1.0 else 1)" || { echo "FAIL true peak $TP dBFS (> -1.0): run an audio-only pass with -c:v copy"; fail=1; }
echo "QC: ${W}x${H} · frames $FR/$EXP · audio $AC · decode_err $ERR · black $BLK · I $I LUFS · TP $TP · $((SZ/1048576)) MB (${MBPS} Mbps)"
[ $fail = 0 ] && echo "✅ PASS" || echo "⚠️ FAIL"
exit $fail
