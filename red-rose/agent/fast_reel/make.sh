#!/usr/bin/env bash
# Fast lane step 3 (Higgsfield XL, background): frames -> render -> encode -> upload, in one job (~4 min / min of video).
# usage: bash make.sh WORKDIR OUT.mp4 [UPLOAD_URL]   ONLY="30,165,660" renders just those test frames into WORKDIR/test   (WORKDIR has spec.json with dua_gate, sel.txt, voice.m4a; approved local fonts only)
set -euo pipefail
W=$1; OUT=$2; U=${3:-}; HERE="$(cd "$(dirname "$0")" && pwd)"
GATE="$HERE/../../rose_dua_gate_v69.py"
python3 "$GATE" dua-gate fast-check "$W"
cd "$W"
mkdir -p web/fonts
cp "$HERE"/web/index.html "$HERE"/web/main.js web/
python3 "$GATE" dua-gate fast-stage "$PWD" --approve-write
[ -e node_modules ] || ln -sfn "$(npm root -g)" node_modules
T0=$(date +%s)
python3 - <<'PY'
import json, os, subprocess
from concurrent.futures import ThreadPoolExecutor
with open('spec.json', encoding='utf-8-sig') as fh: S = json.load(fh)
with open('sel.txt', encoding='utf-8-sig') as fh: sel = [l.strip() for l in fh if l.strip()]
def cut(i):
    sc = S['scenes'][i]; f = sel[i]; length = sc['b'] - sc['a'] + 0.2 + max((x.get('xf', 0) for x in S['scenes']), default=0)
    d = float(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',f],capture_output=True,text=True).stdout or 0)
    ss = sc['ss']
    if ss + length > d + .001: raise ValueError('registered source trim exceeds duration')
    out = f'web/fx/c{i:02d}'; os.makedirs(out, exist_ok=True)
    for x in os.listdir(out): os.remove(f'{out}/{x}')
    subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-ss',f'{ss:.3f}','-i',f,'-t',f'{length:.3f}','-vf','fps=30,scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280','-q:v','3',f'{out}/%04d.jpg'], check=True)
    return dict(src=os.path.basename(f), frames=len(os.listdir(out)))
with ThreadPoolExecutor(4) as ex: clips = list(ex.map(cut, range(len(sel))))
with open('web/clips.json','w',encoding='utf-8') as fh: json.dump(dict(dur=S['dur'], clips=clips), fh)
PY
python3 "$GATE" dua-gate fast-seal "$PWD" --approve-write
T1=$(date +%s); N=$(python3 -c "import json;print(round(json.load(open('spec.json'))['dur']*30))")
if [ -n "${ONLY:-}" ]; then rm -rf test; node "$HERE/render.mjs" web test "$ONLY" 4 > render.log 2>&1; echo "test frames in test/ ($(( $(date +%s)-T0 ))s)"; exit 0; fi
rm -rf frames; node "$HERE/render.mjs" web frames 0-$((N-1)) 4 > render.log 2>&1; T2=$(date +%s)
ffmpeg -nostdin -v error -y -framerate 30 -i frames/f%04d.jpg -i voice.m4a -map 0:v -map 1:a -c:v libx264 -preset veryfast -crf 18 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -af "loudnorm=I=-14:TP=-1:LRA=11" -shortest -movflags +faststart "$OUT"; T3=$(date +%s)
if [ -n "$U" ]; then curl -sf -o /dev/null -w "upload %{http_code}\n" -X PUT -H 'Content-Type: video/mp4' --upload-file "$OUT" "$U"; fi
echo "timing frames $((T1-T0))s render $((T2-T1))s encode $((T3-T2))s total $(( $(date +%s)-T0 ))s"
