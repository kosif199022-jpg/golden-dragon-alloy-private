#!/usr/bin/env bash
# Install Blender (Linux x64, official build) into the Higgsfield sandbox once; cached ~24h in /home/user.
# usage: bash hf_bootstrap.sh [VERSION]   (default 5.2.3; falls back through older LTS builds)
set -u
WANT="${1:-5.2.3}"
BASE=/home/user/bd_blender
mkdir -p "$BASE"
if [ -x "$BASE/current/blender" ]; then
  echo "BLENDER_READY $("$BASE/current/blender" -b --factory-startup --version 2>/dev/null | head -1)"
  exit 0
fi
try() {  # $1 = full version e.g. 5.2.3
  v="$1"; mm="${v%.*}"
  url="https://download.blender.org/release/Blender${mm}/blender-${v}-linux-x64.tar.xz"
  echo "trying $url"
  curl -fsSL --retry 3 -o "$BASE/b.tar.xz" "$url" || return 1
  tar -xJf "$BASE/b.tar.xz" -C "$BASE" || return 1
  rm -f "$BASE/b.tar.xz"
  ln -sfn "$BASE/blender-${v}-linux-x64" "$BASE/current"
}
for v in "$WANT" 5.2.2 5.2.1 5.2.0 5.1.1 5.0.1 4.5.4; do
  try "$v" && break
done
[ -x "$BASE/current/blender" ] || { echo "BLENDER_FAILED"; exit 2; }
# runtime libs Blender needs on a bare image (no-op if present / no apt)
missing=$(ldd "$BASE/current/blender" 2>/dev/null | awk '/not found/{print $1}')
if [ -n "$missing" ]; then
  echo "missing libs: $missing"
  (command -v sudo >/dev/null && SUDO=sudo || SUDO=""; $SUDO apt-get update -qq && \
   $SUDO apt-get install -y -qq libxi6 libxxf86vm1 libxfixes3 libxrender1 libgl1 libxkbcommon0 libsm6 libegl1 >/dev/null 2>&1) || true
fi
echo "BLENDER_READY $("$BASE/current/blender" -b --factory-startup --version 2>/dev/null | head -1)"
python3 -c "import numpy; print('numpy', numpy.__version__)" 2>/dev/null || pip install -q numpy
nproc; free -g | head -2
