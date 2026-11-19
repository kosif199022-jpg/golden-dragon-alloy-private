#!/usr/bin/env bash
# fonts.sh — Arabic + Latin OFL fonts from github.com/google/fonts into ~/.local/share/fonts (fontconfig),
# so Chromium (html2mp4/shot) and libass (ASS subtitles) can use them by family name. Idempotent.
set -uo pipefail
D="$HOME/.local/share/fonts/hfc"; mkdir -p "$D"; cd "$D" || exit 1
G=https://github.com/google/fonts/raw/main/ofl
ok=0; miss=()
for p in "cairo/Cairo%5Bslnt,wght%5D.ttf" amiri/Amiri-Regular.ttf amiri/Amiri-Bold.ttf \
         tajawal/Tajawal-Regular.ttf tajawal/Tajawal-Bold.ttf tajawal/Tajawal-ExtraBold.ttf \
         almarai/Almarai-Regular.ttf almarai/Almarai-Bold.ttf almarai/Almarai-ExtraBold.ttf \
         "notonaskharabic/NotoNaskhArabic%5Bwght%5D.ttf" "notokufiarabic/NotoKufiArabic%5Bwght%5D.ttf" \
         "elmessiri/ElMessiri%5Bwght%5D.ttf" "reemkufi/ReemKufi%5Bwght%5D.ttf" "changa/Changa%5Bwght%5D.ttf" \
         lalezar/Lalezar-Regular.ttf arefruqaa/ArefRuqaa-Regular.ttf arefruqaa/ArefRuqaa-Bold.ttf \
         "readexpro/ReadexPro%5BHEXP,wght%5D.ttf" ibmplexsansarabic/IBMPlexSansArabic-Regular.ttf \
         ibmplexsansarabic/IBMPlexSansArabic-Bold.ttf scheherazadenew/ScheherazadeNew-Regular.ttf \
         scheherazadenew/ScheherazadeNew-Bold.ttf "inter/Inter%5Bopsz,wght%5D.ttf" "playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf" \
         bebasneue/BebasNeue-Regular.ttf anton/Anton-Regular.ttf; do
  n=$(basename "$p" | sed 's/%5B/[/; s/%5D/]/'); [ -s "$n" ] && { ok=$((ok+1)); continue; }
  if curl -sSfL -m 30 -o "$n" "$G/$p"; then ok=$((ok+1)); else rm -f "$n"; miss+=("$p"); fi
done
fc-cache -f "$D" >/dev/null 2>&1
echo "fonts: $ok in $D | arabic families: $(fc-list :lang=ar family | sort -u | tr '\n' '|' | head -c 400)"
[ ${#miss[@]} = 0 ] || echo "fonts: missing ${miss[*]}"
