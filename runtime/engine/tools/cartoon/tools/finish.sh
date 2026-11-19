#!/usr/bin/env bash
# Encode frames -> silent BT.709 video, then put the master audio on it with the exact-length mux, then QA.
#   bash finish.sh "Title Of Short" [MASTER_AUDIO]
# MASTER_AUDIO: his song (extracted with -c copy, never through mix.py) or, for a voice + music + sfx short, mix.wav
# made here from mix_raw.wav. v1.3: no -shortest, no AAC 192k: `dragon.py mux` keeps AAC by copy or encodes 320k.
set -e; T="${1:-short}"; A="${2:-}"; F="out/${T// /-}.mp4"; V="out/${T// /-}.video.mp4"
D="${DRAGON:-$(cat .dragon 2>/dev/null || true)}"
if [ -z "$D" ]; then echo "set DRAGON='python3 <skill>/scripts/dragon.py' (setup.sh writes it to .dragon)"; exit 2; fi
if [ -z "$A" ]; then
  [ -f mix_raw.wav ] || { echo "no MASTER_AUDIO and no mix_raw.wav: pass the song file"; exit 2; }
  ffmpeg -v error -y -i mix_raw.wav -af "loudnorm=I=-14:TP=-1.5:LRA=7" -ar 48000 -ac 2 mix.wav; A=mix.wav
fi
N=$(ls frames/f*.jpg | wc -l)
ffmpeg -v error -y -framerate 30 -i frames/f%04d.jpg -an -vf "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p" \
  -c:v libx264 -preset slow -crf 17 -profile:v high -pix_fmt yuv420p -colorspace bt709 -color_primaries bt709 \
  -color_trc bt709 -color_range tv -x264-params colorprim=bt709:transfer=bt709:colormatrix=bt709 -frames:v "$N" \
  -movflags +faststart "$V"
$D mux "$V" "$A" "$F" --duration "$(python3 -c "print($N/30)")"
$D verify "$F" --expect 1080x1920 --duration "$(python3 -c "print($N/30)")"
echo "--- QA (empty = no black/frozen spans)"; ffmpeg -i "$F" -vf "freezedetect=n=0.0005:d=0.4,blackdetect=d=0.05" -an -f null - 2>&1 | grep -E "freeze_start|black_start" || true
ffmpeg -v error -y -i "$F" -vf "fps=2,scale=180:-1,tile=10x4" -frames:v 1 out/qa_sheet.jpg; rm -f "$V"; echo "$F"
