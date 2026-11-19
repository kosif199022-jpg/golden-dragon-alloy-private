#!/usr/bin/env bash
# Black Dragon v1990 — free reel teardown on the Higgsfield sandbox (analysis only, no generation).
# Ran on 2026-11-11 on a 50 s reference: 78 s total, balance unchanged. Paste into sandbox_exec with background:true.
#   bash trend_dna.sh SLUG 'URL-or-path'
# Output: W/analysis/{analysis,energy}.json, W/audio/{beats,cutsync}.json, W/analysis/words.json, W/sheets/*.jpg
# Then, on the dragon:  tool reel-dna extract --analysis analysis.json --energy energy.json --beats beats.json --out DNA.json
# The reference is evidence for timing/energy/layout only. Never ship its footage, music, wording or characters.
set -u
SLUG="${1:?slug}"; SRC="${2:?url or path}"
R="$HF_WORKFLOWS/katana/scripts"; W="/home/user/dna/$SLUG"; mkdir -p "$W"; cd "$W" || exit 1
if [ ! -f "$SRC" ]; then curl -sfL -o "$W/src.mp4" "$SRC" || { echo "download failed"; exit 1; }; SRC="$W/src.mp4"; fi
t0=$(date +%s)
step(){ n="$1"; shift; "$@" > "$W/$n.log" 2>&1; echo "$n exit $? $(( $(date +%s)-t0 ))s"; }
step fetch    python3 "$R/fetch_ref.py" "$W" "$SRC"
step analyze  python3 "$R/analyze_ref.py" "$W" --review-size --quiet
step energy   python3 "$R/energy.py" map "$W"
step extract  python3 "$R/audio.py" extract "$W"
step beats    python3 "$R/audio.py" beats "$W"
step cutsync  python3 "$R/audio.py" cutsync "$W"
step keyframes python3 "$R/frames.py" keyframes "$W" --which best
step words    python3 "$R/audio.py" words "$W"
python3 - "$W" <<'PY'
import json,sys,os
W=sys.argv[1]
def j(p):
    try: return json.load(open(os.path.join(W,p)))
    except Exception: return {}
a,e,b=j("analysis/analysis.json"),j("analysis/energy.json"),j("audio/beats.json")
print(json.dumps({"cuts":len(a.get("cuts",[])),"flashes":len(a.get("flashes",[])),"rates":e.get("rates"),
 "bpm":b.get("bpm"),"beats":len(b.get("beats",[])),"sections":len(b.get("sections",[])),
 "sheets":len(os.listdir(os.path.join(W,"sheets"))) if os.path.isdir(os.path.join(W,"sheets")) else 0},ensure_ascii=False))
PY
