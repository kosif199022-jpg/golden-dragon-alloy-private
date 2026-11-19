#!/usr/bin/env bash
# Frame encode + delivery gate. No external API or installs. Nonzero exit on gate failure.
set -euo pipefail
if (( $# < 3 )); then echo 'usage: hf_finish.sh JOB_DIR OUTPUT.mp4 DURATION_S [SOUND.py|AUDIO_FILE|none] [EXPECT=1080x1920]' >&2;exit 2;fi
JOB="$1";NAME="$2";DUR="$3";SND="${4:-none}";EXPECT="${5:-1080x1920}"
[[ "$DUR" =~ ^[0-9]+(\.[0-9]+)?$ ]] || { echo 'INVALID_DURATION';exit 2; }
[[ "$EXPECT" =~ ^[0-9]+x[0-9]+$ ]] || { echo 'INVALID_EXPECT';exit 2; }
[[ "$NAME" = "$(basename "$NAME")" && "$NAME" = *.mp4 ]] || { echo 'INVALID_OUTPUT';exit 2; }
[[ -d "$JOB/frames" ]] || { echo 'MISSING_FRAMES_DIR';exit 2; }
cd "$JOB"
FPS=30
N=$(python3 - "$DUR" <<'PY'
import sys
n=round(float(sys.argv[1])*30)
if not 1<=n<=1000000:raise SystemExit(2)
print(n)
PY
)
for ((i=1;i<=N;i++)); do
  printf -v f 'frames/f_%04d.png' "$i"
  [[ -s "$f" ]] || { echo "FRAME_MISSING $f"; exit 1; }
done
ffmpeg -nostdin -hide_banner -v error -y -framerate "$FPS" -i frames/f_%04d.png -frames:v "$N" \
  -c:v libx264 -profile:v high -preset slow -crf 17 -maxrate 14M -bufsize 28M -pix_fmt yuv420p \
  -color_primaries bt709 -color_trc bt709 -colorspace bt709 -movflags +faststart video_only.mp4 || { echo 'ENCODE_FAILED';exit 1; }
AUD=''
case "$SND" in
  none) ;;
  *.py) python3 "$SND" score_raw.wav;AUD=score_raw.wav ;;
  *) AUD="$SND" ;;
esac
if [[ -n "$AUD" ]]; then
  [[ -s "$AUD" ]] || { echo 'AUDIO_MISSING';exit 1; }
  ffmpeg -nostdin -hide_banner -v error -y -i "$AUD" -af loudnorm=I=-14:TP=-1.5:LRA=11 -ar 48000 score.wav
  ffmpeg -nostdin -hide_banner -v error -y -i video_only.mp4 -i score.wav -map 0:v:0 -map 1:a:0 -c:v copy \
    -c:a aac -b:a 320k -ar 48000 -t "$DUR" -movflags +faststart "$NAME"
else cp video_only.mp4 "$NAME";fi
ok=1
frames=$(ffprobe -v error -select_streams v:0 -count_frames -show_entries stream=nb_read_frames -of csv=p=0 "$NAME")
wh=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$NAME")
fps=$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "$NAME")
ac=$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 "$NAME")
[[ "$frames" = "$N" ]] || { echo "FAIL frames=$frames want=$N";ok=0; }
[[ "$wh" = "$EXPECT" ]] || { echo "FAIL size=$wh want=$EXPECT";ok=0; }
[[ "$fps" = '30/1' ]] || { echo "FAIL fps=$fps";ok=0; }
if [[ -n "$AUD" && "$ac" != aac ]]; then echo "FAIL audio=$ac";ok=0;fi
errs=$(ffmpeg -nostdin -v error -i "$NAME" -f null - 2>&1 | wc -l)
[[ "$errs" = 0 ]] || { echo "FAIL decode=$errs";ok=0; }
blk=$(ffmpeg -nostdin -v error -i "$NAME" -vf 'scale=54:96,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-' -an -f null - 2>/dev/null |
  awk -v d="$DUR" '/pts_time/{split($0,a,"pts_time:");t=a[2]} /YAVG/{split($0,b,"=");if(b[2]<17.5 && t>0.6 && t<d-1.5)c++} END{print c+0}')
[[ "$blk" = 0 ]] || { echo "FAIL black_frames=$blk";ok=0; }
ffmpeg -nostdin -v error -y -i "$NAME" -vf "select='not(mod(n\,15))',scale=216:384,tile=5x2:padding=4:color=0x111111" -frames:v 1 qc_sheet.jpg || { echo 'FAIL QC_SHEET';ok=0; }
echo "frames=$frames/$N size=$wh fps=$fps audio=${ac:-none} black=$blk"
if [[ "$ok" = 1 ]];then echo 'GATE_PASS';exit 0;else echo 'GATE_FAIL';exit 1;fi
