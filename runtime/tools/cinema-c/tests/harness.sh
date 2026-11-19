#!/bin/sh
# Offline harness for Cinema C V36 (V35 checks + V36 SmartMedia). Usage: dash harness.sh Cinema_C_V36_iPhone.sh
# Network is never used: yt-dlp is a stub, ffmpeg is the local one with
# libx264/VideoToolbox hidden (a-Shell-like encoder set).
set -u
APPF=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
ROOT=$(cd "$(dirname "$0")/.." && pwd)
T="$ROOT/harness_run"
rm -rf "$T"; mkdir -p "$T/home/Documents"
export HOME="$T/home"
export PATH="$ROOT/tests/stubbin:$PATH"
PASS=0; FAIL=0
check() { if [ "$2" = "$3" ]; then PASS=$((PASS+1)); echo "PASS $1"; else FAIL=$((FAIL+1)); echo "FAIL $1: expected [$2] got [$3]"; fi; }

# media samples (local lavfi, 3 s)
/usr/bin/ffmpeg -nostdin -loglevel error -f lavfi -i testsrc2=size=640x360:rate=30:duration=3 \
  -f lavfi -i sine=frequency=440:duration=3 -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest "$T/h264.mp4"
/usr/bin/ffmpeg -nostdin -loglevel error -f lavfi -i testsrc2=size=640x360:rate=30:duration=3 \
  -f lavfi -i sine=frequency=440:duration=3 -c:v mpeg2video -c:a mp2 -shortest -f mpegts "$T/src.ts"
export STUB_MEDIA="$T/src.ts" STUB_LOG="$T/stub.log"

# 1) interactive single download: Arabic share text, wrong menu number, Arabic digits
out=$(printf '%s\n' 'شوف ده https://vt.tiktok.com/ZSx1/،حلو' '٩٩' ' ٧ ' '٢' | dash "$APPF" 2>&1)
rc=$?
check 'download rc' 0 "$rc"
check 'url cut before arabic comma' 1 "$(grep -c 'URL: https://vt.tiktok.com/ZSx1/$' <<EOF2
$out
EOF2
)"
check 'wrong number re-asks' 1 "$(printf '%s\n' "$out" | grep -c 'Wrong number: 99')"
n_ts=$(ls "$HOME/Documents/Cinema_Downloads" | grep -c '\.ts$')
check '.ts download kept (V34 deleted it)' 1 "$n_ts"
check 'no .part piece moved' 0 "$(ls "$HOME/Documents/Cinema_Downloads" | grep -c 'part$')"
check 'job folder cleaned' 0 "$(ls -d "$HOME/Documents/.cinema"/job_* 2>/dev/null | wc -l | tr -d ' ')"
check 'history line' 1 "$(grep -c 'vt.tiktok.com/ZSx1/' "$HOME/Documents/Cinema_Downloads/history.txt")"

# 2) same title again -> unique name, nothing overwritten
printf '%s\n' 'https://vt.tiktok.com/ZSx1/' '7' '2' | dash "$APPF" >/dev/null 2>&1
check 'second copy gets unique name' 2 "$(ls "$HOME/Documents/Cinema_Downloads" | grep -c '\.ts$')"

# 3) batch: earlier failed_links.txt must survive a batch that has no failures
printf '%s\n' 'https://old.example/fail-1' > "$HOME/Documents/Cinema_Downloads/failed_links.txt"
printf '%s\n' 'https://a.example/v1 https://a.example/v1' '' '١' | dash "$APPF" --batch >/dev/null 2>&1
check 'old failed list kept' 1 "$(grep -c 'old.example/fail-1' "$HOME/Documents/Cinema_Downloads/failed_links.txt")"
printf '%s\n' 'https://b.example/fail-2' '' '1' | dash "$APPF" --batch >/dev/null 2>&1
check 'new failure appended' 2 "$(wc -l < "$HOME/Documents/Cinema_Downloads/failed_links.txt" | tr -d ' ')"
printf '%s\n' '1' | dash "$APPF" --batch failed_links.txt >/dev/null 2>&1
check 'retry of failed list rewrites it' 2 "$(wc -l < "$HOME/Documents/Cinema_Downloads/failed_links.txt" | tr -d ' ')"

# 4) Photos SAFE (offline, --safe): H.264 -> lossless copy; MPEG-2 .ts -> MPEG-4 fallback
cp "$T/h264.mp4" "$HOME/Documents/Cinema_Downloads/clip h264 عربي.mp4"
o=$(dash "$APPF" --safe "clip h264 عربي.mp4" 2>&1)
check 'safe h264 remux' 1 "$(printf '%s\n' "$o" | grep -c 'Method: lossless copy (h264)')"
ts=$(ls "$HOME/Documents/Cinema_Downloads"/*.ts | head -n 1)
o=$(dash "$APPF" --safe "$ts" 2>&1)
check 'safe mpeg2 -> mpeg4 fallback (no libx264)' 1 "$(printf '%s\n' "$o" | grep -c 'Method: built-in MPEG-4')"
check 'no tmp left in Downloads' 0 "$(ls "$HOME/Documents/Cinema_Downloads" | grep -c 'tmp')"
check 'no tmp left in .cinema' 0 "$(ls "$HOME/Documents/.cinema" | grep -c 'photos_safe_')"

# 5) Studio: compress to 1 MB (custom), cover, trim fast — then Done
src="$HOME/Documents/Cinema_Downloads/clip h264 عربي.mp4"
printf '%s\n' '٣' '4' '1' 'n' 'n' '6' '١' 'n' '1' '0:01' '0:02' 'n' 'n' '0' | dash "$APPF" --studio "$src" > "$T/studio.log" 2>&1
check 'studio rc' 0 "$?"
sd="$HOME/Documents/Cinema_Downloads/Studio"
check 'compress output exists' 1 "$(ls "$sd" | grep -c ' - 1MB\.mp4$')"
kb=$(du -k "$sd"/*1MB.mp4 | awk '{print $1}')
check 'compress within 1 MB' yes "$( [ "$kb" -le 1024 ] && echo yes || echo "no ($kb KB)")"
check 'cover jpg' 1 "$(ls "$sd" | grep -c 'COVER\.jpg$')"
check 'trim fast' 1 "$(ls "$sd" | grep -c 'TRIM\.mp4$')"

# 6) Ctrl-C cleanup: a half-written output is removed, the source is not
cat > "$T/int.sh" <<EOF3
CINEMA_NO_MAIN=1
. "$APPF"
STUDIO_SRC="$src"
: > "$T/half - CUT.mp4"
PARTIAL="$T/half - CUT.mp4"
LAB_JOB="$T/labjob"; mkdir -p "\$LAB_JOB"; : > "\$LAB_JOB/source.wav"
kill -INT \$\$
sleep 1
EOF3
dash "$T/int.sh"; rc=$?
check 'INT exit code 130' 130 "$rc"
check 'partial output removed' no "$( [ -e "$T/half - CUT.mp4" ] && echo yes || echo no)"
check 'lab job removed' no "$( [ -d "$T/labjob" ] && echo yes || echo no)"
check 'source kept' yes "$( [ -f "$src" ] && echo yes || echo no)"

# 7) picker lists Studio results and skips temp files
: > "$HOME/Documents/Cinema_Downloads/x.mp4.tmp.mp4"
o=$(printf '0\n' | dash "$APPF" --safe 2>&1)
check 'picker shows Studio folder' yes "$(printf '%s\n' "$o" | grep -q '1MB.mp4' && echo yes || echo no)"
check 'picker hides tmp' 0 "$(printf '%s\n' "$o" | grep -c 'tmp.mp4')"

# 8) V36 SmartMedia: Instagram photo/carousel posts via gallery-dl (stub)
dl="$HOME/Documents/Cinema_Downloads"
o=$(dash "$APPF" --files --smart 'https://www.instagram.com/p/PHOTO123/?igsh=x' 2>&1); rc=$?
check 'smart rc' 0 "$rc"
gd=$(ls -d "$dl"/Instagram_PHOTO123_* 2>/dev/null | head -1)
check 'smart album folder' yes "$( [ -d "$gd" ] && echo yes || echo no)"
check 'smart 3 media kept' 3 "$(ls "$gd" 2>/dev/null | wc -l | tr -d ' ')"
check 'smart json skipped' 0 "$(ls "$gd" 2>/dev/null | grep -c json)"
check 'smart summary' 1 "$(printf '%s\n' "$o" | grep -c '2 photo(s), 1 video(s)')"
rm -rf "$dl"/Instagram_PHOTO123_*
o=$(printf '1\n' | dash "$APPF" --files 'https://www.instagram.com/p/PHOTO456/' 2>&1); rc=$?
check 'auto fallback rc' 0 "$rc"
check 'auto fallback message' 1 "$(printf '%s\n' "$o" | grep -c 'Switching to gallery-dl')"
check 'no yt-dlp update loop for a photo post' 0 "$(printf '%s\n' "$o" | grep -c 'Update yt-dlp now')"
check 'auto fallback folder' 1 "$(ls -d "$dl"/Instagram_PHOTO456_* 2>/dev/null | wc -l | tr -d ' ')"
o=$(dash "$APPF" --files --gallery 'https://www.instagram.com/p/empty1/' 2>&1); rc=$?
check 'gallery nothing -> rc 1' 1 "$rc"
check 'gallery nothing -> clear error' 1 "$(printf '%s\n' "$o" | grep -c 'did not produce any complete media')"
o=$(dash "$APPF" --self-test 2>&1); rc=$?
check 'self-test passes' 0 "$rc"
o=$(dash "$APPF" --doctor 2>&1)
check 'doctor shows gallery-dl' 1 "$(printf '%s\n' "$o" | grep -c '^gallery-dl: 1.99.0-stub')"

echo "harness: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
