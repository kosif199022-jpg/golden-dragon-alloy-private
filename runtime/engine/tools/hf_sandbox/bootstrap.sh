#!/usr/bin/env bash
# Black Dragon on the Higgsfield sandbox — paste into sandbox_exec (free, measured 2026-11-10).
# Usage inside the sandbox:  bash bootstrap.sh JOBNAME
# Creates ~/JOB/{hd,seg,txt,qc,fonts}, fetches Arabic/Latin OFL fonts from google/fonts, reports tools.
set -uo pipefail
JOB=${1:-job}; R=~/$JOB; mkdir -p "$R"/{hd,seg,txt,qc,fonts}; cd "$R/fonts"
G=https://github.com/google/fonts/raw/main/ofl
for p in amiri/Amiri-Bold.ttf amiri/Amiri-Regular.ttf arefruqaa/ArefRuqaa-Bold.ttf arefruqaaink/ArefRuqaaInk-Bold.ttf \
         "notonaskharabic/NotoNaskhArabic%5Bwght%5D.ttf" "elmessiri/ElMessiri%5Bwght%5D.ttf" "reemkufi/ReemKufi%5Bwght%5D.ttf" \
         "tajawal/Tajawal-Bold.ttf" "changa/Changa%5Bwght%5D.ttf" lalezar/Lalezar-Regular.ttf "scheherazadenew/ScheherazadeNew-Bold.ttf" \
         "playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf"; do
  n=$(basename "$p" | sed 's/%5B/[/;s/%5D/]/'); [ -s "$n" ] && continue
  curl -sSfL -m 30 -o "$n" "$G/$p" || echo "font miss: $n"
done
curl -sSfL -m 20 -o hands.svg https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/svg/1f932.svg || true
echo "job=$R  cpus=$(nproc)  fonts=$(ls *.ttf 2>/dev/null | wc -l)"
for t in ffmpeg ffprobe node convert sox yt-dlp; do printf "%s:%s " $t "$(command -v $t >/dev/null && echo y || echo -)"; done; echo
python3 -c "import faster_whisper,cv2,librosa;print('py: faster_whisper cv2 librosa OK')" 2>/dev/null || echo "py libs missing"
echo "playwright: NODE_PATH=/usr/local/lib/node_modules node render.js  (load fonts via page.goto('file://...'))"
echo "pip is blocked: curl the .whl from PyPI, python3 -m zipfile -e X.whl ~/pylib, PYTHONPATH=~/pylib"
