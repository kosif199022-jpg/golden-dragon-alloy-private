#!/usr/bin/env bash
# Encode frames -> H.264 (Black Dragon export standard), make/mux AAC audio, run the delivery gate.
# usage: bash hf_finish.sh JOB_DIR OUT_NAME.mp4 DURATION_S [SOUND.py | AUDIO_FILE | none] [EXPECT=1080x1920]
set -u
JOB="$1"; NAME="$2"; DUR="$3"; SND="${4:-none}"; EXPECT="${5:-1080x1920}"
cd "$JOB" || exit 2
FPS=30; N=$(python3 -c "print(round($DUR*$FPS))")
ffmpeg -nostdin -v error -y -framerate $FPS -i frames/f_%04d.png -frames:v $N \
  -c:v libx264 -profile:v high -preset slow -crf 17 -maxrate 14M -bufsize 28M -pix_fmt yuv420p \
  -color_primaries bt709 -color_trc bt709 -colorspace bt709 -movflags +faststart video_only.mp4 || { echo "ENCODE_FAILED"; exit 1; }
AUD=""
case "$SND" in
  none) ;;
  *.py) python3 "$SND" score_raw.wav && AUD=score_raw.wav ;;
  *) AUD="$SND" ;;
esac
if [ -n "$AUD" ]; then
  ffmpeg -nostdin -v error -y -i "$AUD" -af loudnorm=I=-14:TP=-1.5:LRA=11 -ar 48000 score.wav
  ffmpeg -nostdin -v error -y -i video_only.mp4 -i score.wav -map 0:v -map 1:a -c:v copy \
    -c:a aac -b:a 320k -ar 48000 -t "$DUR" -movflags +faststart "$NAME"
else
  cp video_only.mp4 "$NAME"
fi
# ---- delivery gate (same checks as Black Dragon verify)
ok=1
frames=$(ffprobe -v error -select_streams v:0 -count_frames -show_entries stream=nb_read_frames -of csv=p=0 "$NAME")
wh=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$NAME")
fps=$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "$NAME")
ac=$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 "$NAME")
[ "$frames" = "$N" ] || { echo "FAIL frames=$frames want=$N"; ok=0; }
[ "$wh" = "$EXPECT" ] || { echo "FAIL size=$wh want=$EXPECT"; ok=0; }
[ "$fps" = "30/1" ] || { echo "FAIL fps=$fps"; ok=0; }
if [ -n "$AUD" ] && [ "$ac" != "aac" ]; then echo "FAIL audio=$ac"; ok=0; fi
errs=$(ffmpeg -nostdin -v error -i "$NAME" -f null - 2>&1 | wc -l); [ "$errs" = 0 ] || { echo "FAIL decode_errors=$errs"; ok=0; }
# black frames outside first 0.6s / last 1.5s (YAVG < 17.5 on 54x96)
blk=$(ffmpeg -nostdin -v error -i "$NAME" -vf "scale=54:96,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-" -an -f null - 2>/dev/null \
  | awk -v d="$DUR" '/pts_time/{split($0,a,"pts_time:");t=a[2]} /YAVG/{split($0,b,"=");if(b[2]<17.5 && t>0.6 && t<d-1.5)c++} END{print c+0}')
[ "$blk" = 0 ] || { echo "FAIL black_frames=$blk"; ok=0; }
lufs=""; [ -n "$AUD" ] && lufs=$(ffmpeg -nostdin -i "$NAME" -af ebur128=peak=true -f null - 2>&1 | awk '/I:/{v=$2} /Peak:/{p=$2} END{print v" LUFS peak "p" dBFS"}')
mbps=$(ffprobe -v error -show_entries format=bit_rate -of csv=p=0 "$NAME" | awk '{printf "%.1f", $1/1e6}')
echo "size=$wh fps=$fps frames=$frames audio=${ac:-none} $lufs bitrate=${mbps}Mbps black=$blk"
ffmpeg -nostdin -v error -y -i "$NAME" -vf "select='not(mod(n\,15))',scale=216:384,tile=5x2:padding=4:color=0x111111" -frames:v 1 qc_sheet.jpg
[ "$ok" = 1 ] && echo "GATE_PASS" || echo "GATE_FAIL"
