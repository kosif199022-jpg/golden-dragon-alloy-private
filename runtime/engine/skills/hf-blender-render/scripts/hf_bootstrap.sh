#!/usr/bin/env bash
# Higgsfield Blender pilot. Does not download unless explicit opt-in is set.
set -euo pipefail
WANT="${1:-5.2.3}"
BASE=/home/user/bd_blender
if [[ ! "$WANT" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then echo 'INVALID_VERSION'; exit 2; fi
if [[ -x "$BASE/current/blender" ]]; then
  "$BASE/current/blender" -b --factory-startup --version 2>/dev/null | head -n 1
  echo 'BLENDER_READY_PREINSTALLED';exit 0
fi
if [[ "${HF_BLENDER_ALLOW_DOWNLOAD:-}" != 'YES' ]]; then
  echo 'BLENDER_MISSING: install not attempted. Check billing and approve official download first.'
  echo 'To explicitly allow official Blender download in an approved session: HF_BLENDER_ALLOW_DOWNLOAD=YES bash hf_bootstrap.sh [VERSION]'
  exit 3
fi
mkdir -p "$BASE"
# Download from Blender Foundation only. Checksums not bundled: verify official checksum separately.
for v in "$WANT" 5.2.2 5.2.1 5.2.0 5.1.1 5.0.1 4.5.4; do
  mm="${v%.*}"
  url="https://download.blender.org/release/Blender${mm}/blender-${v}-linux-x64.tar.xz"
  echo "Official source: $url"
  if curl --fail --location --retry 1 --connect-timeout 15 --max-time 240 --output "$BASE/b.tar.xz" "$url"; then
    if tar -tJf "$BASE/b.tar.xz" >/dev/null 2>&1 && tar -xJf "$BASE/b.tar.xz" -C "$BASE"; then
      rm -f "$BASE/b.tar.xz"
      if [[ -x "$BASE/blender-${v}-linux-x64/blender" ]]; then
        ln -sfn "$BASE/blender-${v}-linux-x64" "$BASE/current"
        echo 'BLENDER_READY_BINARY_PRESENT — run a separate smoke test before production.'
        exit 0
      fi
    fi
  fi
  rm -f "$BASE/b.tar.xz"
done
echo 'BLENDER_INSTALL_FAILED; no system packages or pip were installed.' >&2
exit 2
