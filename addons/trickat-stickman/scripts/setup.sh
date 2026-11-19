#!/usr/bin/env bash
# One-time setup for the Trickat StickMan engine.
# Installs the Python packages for drawing, Arabic text shaping (HarfBuzz) and audio.
# Timing comes from the user's SRT file, so no speech model is needed.
# Optional: `bash setup.sh --with-asr` also downloads the English speech model (~460 MB) used by the old `align` path.
set -e
PY=${PYTHON:-python3}
command -v ffmpeg >/dev/null || { echo "ffmpeg missing: install it (apt-get install -y ffmpeg / brew install ffmpeg)"; exit 1; }
PKGS="skia-python numpy scipy soundfile uharfbuzz"
[ "$1" = "--with-asr" ] && PKGS="$PKGS sherpa-onnx"
$PY -m pip install -q $PKGS 2>/dev/null || $PY -m pip install -q --break-system-packages $PKGS
$PY -c "import skia, numpy, scipy, soundfile, uharfbuzz; print('python packages ok (skia, numpy, scipy, soundfile, uharfbuzz)')"
if [ "$1" = "--with-asr" ]; then
  M=${RM_MODELS:-$HOME/models}; mkdir -p "$M"; cd "$M"
  NAME=sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8
  if [ ! -f "$NAME/encoder.int8.onnx" ]; then
    echo "downloading English speech model (~460 MB, GitHub release)..."
    curl -sSL -O "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/$NAME.tar.bz2" && tar xjf "$NAME.tar.bz2" && rm -f "$NAME.tar.bz2" \
      || echo "WARNING: model download failed."
  fi
fi
echo "cpus: $(nproc 2>/dev/null || sysctl -n hw.ncpu)"
