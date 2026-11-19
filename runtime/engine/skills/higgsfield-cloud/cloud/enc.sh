#!/usr/bin/env bash
# enc.sh IN OUT [options] [-- extra ffmpeg output args]
#   --vcodec libx264|libx265|libsvtav1|prores_ks (libx264)   --preset slow   --crf 18   --pix yuv420p
#   --size WxH        fit inside + pad (keeps aspect)          --fps N       force constant frame rate
#   --vf "CHAIN"      extra video filters (after size/fps)     --af "CHAIN"  extra audio filters
#   --lufs -14        single-pass loudnorm (TP -1.5)           --audio aac|copy|none (aac) --abr 192k
#   --maxrate 14M     cap bitrate (bufsize = 2x)               --threads N
#   --start-frame A --frames N   frame-exact VIDEO-ONLY part (for >15-min jobs or local+cloud hybrid).
#                                Parts are renumbered to clean CFR timestamps; join with `hfc concat`.
# Writes ffmpeg -progress to $HFC_JOB_DIR when run under `hfc job run`, so `hfc job status` shows % and ETA.
set -uo pipefail
[ $# -ge 2 ] || { sed -n '2,13p' "$0"; exit 2; }
IN=$1; OUT=$2; shift 2
VC=libx264 PRESET=slow CRF=18 PIX=yuv420p VF="" AF="" SIZE="" FPS="" SF="" NF="" AUDIO=aac ABR=192k LUFS="" MAXRATE="" THREADS=""
EXTRA=()
while [ $# -gt 0 ]; do case $1 in
  --vcodec) VC=$2; shift 2;; --preset) PRESET=$2; shift 2;; --crf) CRF=$2; shift 2;; --pix) PIX=$2; shift 2;;
  --vf) VF=$2; shift 2;; --af) AF=$2; shift 2;; --size) SIZE=$2; shift 2;; --fps) FPS=$2; shift 2;;
  --start-frame) SF=$2; shift 2;; --frames) NF=$2; shift 2;; --audio) AUDIO=$2; shift 2;; --abr) ABR=$2; shift 2;;
  --lufs) LUFS=$2; shift 2;; --maxrate) MAXRATE=$2; shift 2;; --threads) THREADS=$2; shift 2;;
  --) shift; EXTRA=("$@"); break;;
  *) echo "enc: unknown option $1" >&2; exit 2;; esac; done
[ -f "$IN" ] || { echo "enc: no input $IN" >&2; exit 2; }
PY=python3; { command -v python3 >/dev/null 2>&1 && python3 -c 1 >/dev/null 2>&1; } || PY=python
# probe: fps as rational, duration, audio presence
read -r RFPS DUR HASA < <(ffprobe -v error -show_entries stream=codec_type,r_frame_rate:format=duration -of json "$IN" | $PY -c '
import json,sys
d=json.load(sys.stdin); v=[s for s in d["streams"] if s.get("codec_type")=="video"]; a=[s for s in d["streams"] if s.get("codec_type")=="audio"]
print(v[0]["r_frame_rate"] if v else "30/1", d.get("format",{}).get("duration","0"), 1 if a else 0)')
[ -n "$FPS" ] && RFPS=$FPS
chain=()
[ -n "$SIZE" ] && { W=${SIZE%x*}; H=${SIZE#*x}; chain+=("scale=$W:$H:force_original_aspect_ratio=decrease:flags=lanczos,pad=$W:$H:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1"); }
[ -n "$FPS" ] && chain+=("fps=$FPS")
[ -n "$VF" ] && chain+=("$VF")
IARGS=(); OARGS=()
if [ -n "$SF" ] || [ -n "$NF" ]; then
  SF=${SF:-0}; [ -n "$NF" ] || { echo "enc: --start-frame needs --frames" >&2; exit 2; }
  # seek half a frame early so rounding can never drop frame A; renumber timestamps to exact CFR from 0
  SS=$($PY -c "from fractions import Fraction as F;r=F('$RFPS');a=int('$SF');print(f'{max(0,(a-0.5)/float(r)):.6f}')")
  [ "$SF" -gt 0 ] && IARGS+=(-ss "$SS")
  chain+=("setpts=N/($RFPS)/TB")
  OARGS+=(-frames:v "$NF" -an -r "$RFPS")
  TOTAL_US=$($PY -c "from fractions import Fraction as F;print(int(int('$NF')/F('$RFPS')*1000000))")
  AUDIO=none
else
  TOTAL_US=$($PY -c "print(int(float('${DUR:-0}' or 0)*1000000))")
fi
VARGS=(-c:v "$VC")
case $VC in
  libx264|libx265) VARGS+=(-preset "$PRESET" -crf "$CRF" -pix_fmt "$PIX"); [ "$VC" = libx265 ] && VARGS+=(-tag:v hvc1);;
  libsvtav1) VARGS+=(-preset "$PRESET" -crf "$CRF" -pix_fmt "${PIX/yuv420p/yuv420p10le}");;
  prores_ks) VARGS+=(-profile:v 3 -pix_fmt yuv422p10le);;
esac
[ -n "$MAXRATE" ] && VARGS+=(-maxrate "$MAXRATE" -bufsize "$(( ${MAXRATE%M} * 2 ))M")
[ -n "$THREADS" ] && VARGS+=(-threads "$THREADS")
AARGS=()
if [ "$AUDIO" = none ] || [ "$HASA" = 0 ]; then AARGS=(-an)
elif [ "$AUDIO" = copy ]; then AARGS=(-c:a copy)
else achain=(); [ -n "$AF" ] && achain+=("$AF"); [ -n "$LUFS" ] && achain+=("loudnorm=I=$LUFS:TP=-1.5:LRA=11")
  AARGS=(-c:a aac -b:a "$ABR" -ar 48000); [ ${#achain[@]} -gt 0 ] && AARGS+=(-af "$(IFS=,; echo "${achain[*]}")"); fi
[ ${#chain[@]} -gt 0 ] && VARGS+=(-vf "$(IFS=,; echo "${chain[*]}")")
PROG=(); if [ -n "${HFC_JOB_DIR:-}" ]; then echo "$TOTAL_US" > "$HFC_JOB_DIR/total_us"; PROG=(-progress "$HFC_JOB_DIR/progress" -stats_period 2); fi
MOV=(); case "$OUT" in *.mp4|*.mov|*.m4v) MOV=(-movflags +faststart);; esac
mkdir -p "$(dirname "$OUT")"
MAPA=(); [ "${AARGS[0]}" = -an ] || MAPA=(-map "0:a:0?")
s=$(date +%s)
ffmpeg -nostdin -hide_banner -loglevel error -y "${IARGS[@]}" -i "$IN" -map 0:v:0 "${MAPA[@]}" \
  "${VARGS[@]}" "${AARGS[@]}" "${OARGS[@]}" "${MOV[@]}" "${PROG[@]}" "${EXTRA[@]}" "$OUT" 2>&1 | tr '\r' '\n' | grep -v '^\s*$' | tail -n 3
rc=${PIPESTATUS[0]}
[ $rc = 0 ] || { echo "enc: ffmpeg failed rc=$rc" >&2; exit $rc; }
info=$(ffprobe -v error -select_streams v:0 -count_packets -show_entries stream=width,height,nb_read_packets:format=duration,size -of csv=p=0:s=, "$OUT" | tr -d '\r' | tr '\n' ',')
echo "enc: $OUT [w,h,frames,dur,bytes]=${info%,} seconds=$(( $(date +%s) - s ))"
