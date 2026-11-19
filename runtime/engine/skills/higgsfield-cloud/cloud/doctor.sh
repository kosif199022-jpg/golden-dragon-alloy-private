#!/usr/bin/env bash
# doctor.sh [--json] — what this sandbox is right now (size, tools, caches, jobs). Read-only.
set -uo pipefail
PY=python3; command -v python3 >/dev/null 2>&1 || PY=python
aff=$($PY -c 'import os;print(len(os.sched_getaffinity(0)))' 2>/dev/null || nproc)
mem=$(awk '/MemTotal/{printf "%.1f", $2/1048576}' /proc/meminfo 2>/dev/null)
disk=$(df -h "$HOME" 2>/dev/null | awk 'NR==2{print $4}')
size=standard; [ "${aff:-1}" -ge 4 ] && size=xl
have() { command -v "$1" >/dev/null 2>&1 && echo y || echo -; }
tools=""; for t in ffmpeg ffprobe node npm npx convert magick sox git jq curl zip unzip rsvg-convert pdftoppm gs yt-dlp aria2c 7z blender; do tools+="$t:$(have $t) "; done
pyl=$($PY - <<'EOF' 2>/dev/null
import importlib
out=[]
for m in ["PIL","numpy","cv2","faster_whisper","librosa","scipy","onnxruntime","yt_dlp","torch","fontTools","moviepy"]:
    try: importlib.import_module(m); out.append(m+":y")
    except Exception: out.append(m+":-")
print(" ".join(out))
EOF
)
models=$(ls "$HOME/.cache/huggingface/hub" 2>/dev/null | grep '^models--' | sed 's/^models--//' | tr '\n' ' ')
fonts=$(fc-list 2>/dev/null | wc -l); arfonts=$(fc-list :lang=ar family 2>/dev/null | sort -u | tr '\n' '|' | head -c 300)
jobs=""; for d in "$HOME"/hfc_jobs/*/; do [ -d "$d" ] || continue; n=$(basename "$d"); jobs+="$n:$(cat "$d/state" 2>/dev/null) "; done
marker=$(cat "$HOME/.hfc_marker" 2>/dev/null || echo none)
[ -f "$HOME/.hfc_marker" ] || date -u +%FT%TZ > "$HOME/.hfc_marker"
ver=$(cat "$(dirname "$(readlink -f "$0")")/VERSION" 2>/dev/null)
if [ "${1:-}" = "--json" ]; then
  $PY - "$size" "$aff" "$mem" "$disk" "$tools" "$pyl" "$models" "$fonts" "$arfonts" "$jobs" "$marker" "$ver" <<'EOF'
import json,sys
k=["size","cpus","ram_gb","disk_free","tools","python","hf_models","fonts","arabic_fonts","jobs","workspace_marker","hfc_version"]
print(json.dumps(dict(zip(k,sys.argv[1:])),ensure_ascii=False))
EOF
else
  echo "hfc $ver | size=$size cpus=$aff ram=${mem}GB free=$disk | workspace since $marker"
  echo "tools: $tools"
  echo "python: $pyl"
  echo "whisper models cached: ${models:-none}"
  echo "fonts: $fonts total | arabic: ${arfonts:-none (run: hfc fonts)}"
  echo "jobs: ${jobs:-none}"
  [ -e /dev/nvidia0 ] && echo "gpu: yes" || echo "gpu: none (CPU only)"
fi
