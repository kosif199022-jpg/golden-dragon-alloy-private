#!/usr/bin/env bash
# Maven Reels setup (macOS, Linux). By Maven: @maven.iqq on Instagram, maveniqq on YouTube.
set -e
cd "$(dirname "$0")"
command -v node >/dev/null || { echo "Install Node 18 or newer from https://nodejs.org, then run this again."; exit 1; }
[ "$(node -p 'process.versions.node.split(".")[0]')" -ge 18 ] || { echo "Node 18 or newer is needed."; exit 1; }
command -v ffmpeg >/dev/null || { echo "Install ffmpeg (brew install ffmpeg, or apt install ffmpeg), then run this again."; exit 1; }
npm install --silent
npx playwright install chromium
if command -v python3 >/dev/null; then python3 -m pip install -q -r requirements.txt || echo "Python packages not installed: analyze.py needs numpy and pillow."; fi
node scripts/render.mjs examples/tannour-ar/reel.html first-test.mp4 --res 720 --to 3
echo "Ready. first-test.mp4 was made."
