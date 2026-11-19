param(
    [ValidateSet('own-video','own-extended','own','filming','editing','vfx','ai-video','audio','motion-extras','all')]
    [string]$Group = 'own-video',
    [switch]$Execute,
    [string]$Destination = ''
)
Set-Location $PSScriptRoot
$cmd = @('kosif.py','install','--group',$Group)
if ($Destination) { $cmd += @('--dest',$Destination) }
if ($Execute) { $cmd += '--execute' }
python @cmd
if ($LASTEXITCODE -ne 0) { throw "KOSIF installer failed with code $LASTEXITCODE" }
