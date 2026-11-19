# Fares Motion installer for Windows: the After Effects panel + the skill(s), and Claude Code if it is missing.
# Whisper (captions, ~560 MB) is NOT downloaded here, so the install takes seconds: the panel downloads it itself
# the first time it has to listen.
# Started by "Install - Windows.bat". -TestRoot installs into a test folder instead (no registry, no Claude Code).
param([string]$TestRoot = '')
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$userHome = if ($TestRoot) { $TestRoot } else { $env:USERPROFILE }
$appData = if ($TestRoot) { Join-Path $TestRoot 'AppData' } else { $env:APPDATA }
function Say([string]$t, [string]$c = 'Gray') { Write-Host $t -ForegroundColor $c }

try {
  Say ''
  Say '==  Fares Motion  ==' Green
  Say ''

  # 1) the panel -> After Effects' extensions folder
  $ext = Join-Path $appData 'Adobe\CEP\extensions\com.farestoson.faresmotion'
  $item = Get-Item $ext -Force -ErrorAction SilentlyContinue
  if ($item -and $item.LinkType) {
    Say '1/3البانل موجودة هنا كـ link (جهاز تطوير)، فسبتها زي ما هي.' Yellow
  } else {
    if ($item) { Remove-Item $ext -Recurse -Force }
    New-Item -ItemType Directory -Force $ext | Out-Null
    Copy-Item (Join-Path $here 'panel\*') $ext -Recurse -Force
    Say '1/3البانل اتسطّبت في After Effects.' Green
  }

  # After Effects only loads panels that are not signed by Adobe when this switch is on (one value per CEP version)
  if (-not $TestRoot) {
    foreach ($v in 9..16) {
      $k = "HKCU:\Software\Adobe\CSXS.$v"
      if (-not (Test-Path $k)) { New-Item $k | Out-Null }
      Set-ItemProperty $k -Name PlayerDebugMode -Value '1' -Type String
    }
  }

  # 2) the skill(s) -> Documents\Fares Motion\.claude\skills = the panel's working folder
  $work = Join-Path $userHome 'Documents\Fares Motion'
  $skills = Join-Path $work '.claude\skills'
  New-Item -ItemType Directory -Force $skills | Out-Null
  foreach ($s in Get-ChildItem (Join-Path $here 'skills') -Directory) {
    $dest = Join-Path $skills $s.Name
    if (Test-Path $dest) {                                   # an older copy is kept, never deleted
      $bk = Join-Path $work ('.claude\skill-backups\' + $s.Name + '-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
      New-Item -ItemType Directory -Force (Split-Path $bk) | Out-Null
      Move-Item $dest $bk
      Say "     (النسخة القديمة من $($s.Name) اتنقلت لـ $bk)"
    }
    Copy-Item $s.FullName $dest -Recurse
    Say "2/3السكيل $($s.Name) اتحطت في $work" Green
  }
  # the episode's example projects, next to the skill (an existing folder of the same name is the user's: left alone)
  $proj = Join-Path $here 'projects'
  if (Test-Path $proj) {
    foreach ($p in Get-ChildItem $proj -Directory) {
      $dest = Join-Path $work $p.Name
      if (-not (Test-Path $dest)) { Copy-Item $p.FullName $dest -Recurse }
    }
    Say '     والأمثلة بتاعة الحلقة اتحطت جنبها.' Green
  }

  # 3) Claude Code (the panel runs it with the user's own Claude account)
  $cands = @(Join-Path $userHome '.local\bin\claude.exe')
  if ($env:LOCALAPPDATA) {
    Get-ChildItem (Join-Path $env:LOCALAPPDATA 'Packages') -Directory -Filter 'Claude_*' -ErrorAction SilentlyContinue | ForEach-Object {
      $cands += @(Get-ChildItem (Join-Path $_.FullName 'LocalCache\Roaming\Claude\claude-code') -Recurse -Filter claude.exe -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
    }
  }
  $cands += @(Get-ChildItem (Join-Path $env:APPDATA 'Claude\claude-code') -Recurse -Filter claude.exe -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
  $found = $cands | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
  if ($found) {
    Say '3/3Claude Code موجود عندك.' Green
  } elseif ($TestRoot) {
    Say '3/3(تجربة) مفيش فحص لـ Claude Code.'
  } else {
    Say '3/3Claude Code مش متسطّب، والبانل محتاجاه، فبيتسطّب دلوقتي…' Yellow
    try { Invoke-RestMethod https://claude.ai/install.ps1 | Invoke-Expression }
    catch { Say ('     تسطيب Claude Code وقف (' + $_.Exception.Message + '). تقدر تسطّبه بعدين من claude.com/code') Yellow }
  }

  Say ''
  Say 'خلاص! افتح After Effects (ولو كان مفتوح اقفله وافتحه تاني):' Green
  Say '      Window  >  Extensions  >  Fares Motion' Green
  Say 'أول مرة بس: دوس على علامة الترس ثم «تسجيل الدخول» وسجّل بحساب Claude بتاعك.' Green
} catch {
  Say ''
  Say ('حصلت مشكلة: ' + $_.Exception.Message) Red
}
