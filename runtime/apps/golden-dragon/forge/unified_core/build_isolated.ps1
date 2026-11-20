# Build Golden Dragon in TEMP only. Never install, copy to USERPROFILE, or create shortcuts.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File build_isolated.ps1 [-RunTests] [-DryRun]
param(
    [string]$OutputRoot = "",
    [switch]$RunTests,
    [switch]$DryRun
)
$ErrorActionPreference = "Continue"
$gd = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$app = Join-Path $gd "app"
if (-not (Test-Path -LiteralPath (Join-Path $app "app.py"))) {
    throw "Generated app missing. Run forge/make_golden_dragon.py in a safe checkout first."
}
if (-not $OutputRoot) {
    $OutputRoot = Join-Path $env:TEMP ("golden-dragon-isolated-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
}
$temp = [IO.Path]::GetFullPath($env:TEMP).TrimEnd([char]'\') + '\'
$out = [IO.Path]::GetFullPath($OutputRoot).TrimEnd([char]'\')
if (-not $out.StartsWith($temp, [StringComparison]::OrdinalIgnoreCase)) {
    throw "OutputRoot must be inside TEMP; refusing to touch an installed application."
}
if (Test-Path -LiteralPath $out) {
    throw "Output already exists; refusing to overwrite: $out"
}
$dest = Join-Path $out "dist"
$work = Join-Path $out "build"
$exe = Join-Path $dest "GoldenDragon\GoldenDragon.exe"
Write-Output "ISOLATED_BUILD_ROOT=$out"
Write-Output "NO_INSTALL=TRUE"
Write-Output "NO_SHORTCUT=TRUE"
if ($DryRun) {
    Write-Output "DRY_RUN=TRUE"
    return
}
if ($RunTests) {
    $tests = Join-Path $gd "tests"
    if (-not (Test-Path -LiteralPath $tests)) { throw "Test directory missing: $tests" }
    $env:GD_APP_DIR = $app
    $env:PYTHONDONTWRITEBYTECODE = '1'
    $env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
    & python -B -X utf8 -m pytest $tests -q -p no:cacheprovider --tb=short
    if ($LASTEXITCODE -ne 0) { throw "Tests failed; packaging cancelled" }
}
New-Item -ItemType Directory -Path $out | Out-Null
$pyArgs = @(
    '-m','PyInstaller','--noconfirm','--windowed','--name','GoldenDragon',
    '--icon',(Join-Path $app 'ui\golden-dragon.ico'),
    '--add-data',"$app\ui;ui",
    '--add-data',"$app\chrome_extension;chrome_extension",
    '--add-data',"$app\mcp_control.py;.",
    '--add-data',"$app\voice.py;.",
    '--add-data',"$app\golden;golden",
    '--add-data',"$app\fusion;fusion",
    '--hidden-import','anthropic',
    '--hidden-import','keyring.backends.Windows',
    '--hidden-import','webview.dom',
    '--hidden-import','control',
    '--hidden-import','golden_tools',
    '--hidden-import','dragon_fusion',
    '--hidden-import','gd_discover',
    '--hidden-import','anatomy_bridge',
    '--hidden-import','gd_core_integrations',
    '--hidden-import','gd_runtime',
    '--hidden-import','capability_ledger',
    '--hidden-import','audit_tree',
    '--hidden-import','native_registry',
    '--hidden-import','blender_engine',
    '--hidden-import','golden_steer',
    '--distpath',$dest,'--workpath',$work,'--specpath',$out,
    (Join-Path $app 'app.py')
)
& python @pyArgs
if ($LASTEXITCODE -ne 0) { throw "PyInstaller packaging failed with exit $LASTEXITCODE" }
if (-not (Test-Path -LiteralPath $exe)) { throw "Expected isolated EXE not produced: $exe" }
Write-Output "ISOLATED_EXE=$exe"
Write-Output "NO_INSTALL=TRUE"
