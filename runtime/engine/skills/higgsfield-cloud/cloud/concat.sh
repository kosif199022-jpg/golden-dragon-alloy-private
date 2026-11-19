#!/usr/bin/env bash
# concat.sh OUT PART1 PART2 ... [--audio-from SRC] [--abr 192k] [--lufs -14]
# Joins same-codec parts by stream copy (no re-encode), then optionally adds SRC's first audio track
# (re-encoded once to AAC, so there are no AAC gaps at part boundaries). Prints frame count for checking.
set -uo pipefail
[ $# -ge 2 ] || { sed -n '2,4p' "$0"; exit 2; }
OUT=$1; shift; PARTS=(); SRC=""; ABR=192k; LUFS=""
while [ $# -gt 0 ]; do case $1 in
  --audio-from) SRC=$2; shift 2;; --abr) ABR=$2; shift 2;; --lufs) LUFS=$2; shift 2;;
  *) PARTS+=("$1"); shift;; esac; done
[ ${#PARTS[@]} -ge 1 ] || { echo "concat: no parts" >&2; exit 2; }
L=$(mktemp "${TMPDIR:-/tmp}/hfc_concat.XXXX.txt")
for p in "${PARTS[@]}"; do [ -s "$p" ] || { echo "concat: missing part $p" >&2; exit 2; }
  a=$(cd "$(dirname "$p")" && pwd)/$(basename "$p"); printf "file '%s'\n" "${a//\'/\'\\\'\'}" >> "$L"; done
mkdir -p "$(dirname "$OUT")"
if [ -n "$SRC" ]; then
  AF=(); [ -n "$LUFS" ] && AF=(-af "loudnorm=I=$LUFS:TP=-1.5:LRA=11")
  ffmpeg -nostdin -hide_banner -loglevel error -y -f concat -safe 0 -i "$L" -i "$SRC" -map 0:v:0 -map "1:a:0?" \
    -c:v copy -c:a aac -b:a "$ABR" -ar 48000 "${AF[@]}" -shortest -movflags +faststart "$OUT" || exit 1
else
  ffmpeg -nostdin -hide_banner -loglevel error -y -f concat -safe 0 -i "$L" -c copy -movflags +faststart "$OUT" || exit 1
fi
rm -f "$L"
fr=$(ffprobe -v error -select_streams v:0 -count_packets -show_entries stream=nb_read_packets -of csv=p=0 "$OUT" | tr -d '\r')
du=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT" | tr -d '\r')
echo "concat: $OUT parts=${#PARTS[@]} frames=$fr duration=$du"
