# Maven Reels setup (Windows). By Maven: @maven.iqq on Instagram, maveniqq on YouTube.
# Run: powershell -ExecutionPolicy Bypass -File setup.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { Write-Host "Install Node 18 or newer from https://nodejs.org, then run this again."; exit 1 }
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { Write-Host "Install ffmpeg (winget install Gyan.FFmpeg), reopen PowerShell, then run this again."; exit 1 }
npm install --silent
npx playwright install chromium
$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) { py -3 -m pip install -q -r requirements.txt } else { Write-Host "Python not found. Python is needed for analyze.py: install it from python.org." }
node scripts/render.mjs examples/tannour-ar/reel.html first-test.mp4 --res 720 --to 3
Write-Host "Ready. first-test.mp4 was made."
