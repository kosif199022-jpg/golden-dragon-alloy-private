# Build the Black Dragon desktop app.
#   1) stamps ui\version.txt (the app compares it with the staged build and offers «حدّث دلوقتي»)
#   2) builds into %TEMP%\bd_build\dist_new, then stages it in %TEMP%\bd_build\dist (never a half-built folder)
#   3) installs to %LOCALAPPDATA%\BlackDragon only if the app is closed (otherwise the app's update button does it)
#   4) makes sure the Desktop shortcut exists
$ErrorActionPreference = "Continue"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$work = Join-Path $env:TEMP "bd_build"
Set-Location $here
(Get-Date -Format "yyyy.MM.dd-HHmm") | Set-Content -Encoding ascii (Join-Path $here "ui\version.txt")
Remove-Item -Recurse -Force (Join-Path $here "__pycache__") -ErrorAction SilentlyContinue
python -m PyInstaller --noconfirm --windowed --name BlackDragon --icon "$here\ui\red-dragon.ico" `
  --add-data "$here\ui;ui" --add-data "$here\chrome_extension;chrome_extension" --add-data "$here\mcp_control.py;." --add-data "$here\voice.py;." `
  --hidden-import keyring.backends.Windows --hidden-import webview.dom --hidden-import control `
  --distpath "$work\dist_new" --workpath "$work\build" --specpath $work app.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
robocopy "$work\dist_new\BlackDragon" "$work\dist\BlackDragon" /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
$dst = Join-Path $env:LOCALAPPDATA "BlackDragon"
$exe = Join-Path $dst "BlackDragon.exe"
if (Get-Process BlackDragon -ErrorAction SilentlyContinue) {
  Write-Output "staged (app is open: use the update button inside the app)"
} else {
  # only the app's own files (other Black Dragon parts keep data in $dst\chrome and $dst\sahab)
  robocopy "$work\dist\BlackDragon\_internal" "$dst\_internal" /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
  Copy-Item "$work\dist\BlackDragon\BlackDragon.exe" $exe -Force
  Write-Output "installed: $exe"
}
$desk = [Environment]::GetFolderPath("Desktop")
$arabic = Join-Path $desk ((-join [char[]](0x627,0x644,0x62a,0x646,0x64a,0x646,0x20,0x627,0x644,0x623,0x633,0x648,0x62f,0x20,0x2d,0x20,0x62a,0x637,0x628,0x64a,0x642)) + ".lnk")
if (-not (Test-Path -LiteralPath $arabic)) {
  $ws = New-Object -ComObject WScript.Shell
  $lnk = $ws.CreateShortcut("$desk\BlackDragon.lnk")
  $lnk.TargetPath = $exe; $lnk.WorkingDirectory = $dst; $lnk.IconLocation = "$exe,0"; $lnk.Save()
  Move-Item -LiteralPath "$desk\BlackDragon.lnk" -Destination $arabic -Force
}
