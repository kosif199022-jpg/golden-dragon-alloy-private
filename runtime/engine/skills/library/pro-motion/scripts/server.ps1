# Local static server for a generated-video project + POST /save?name=file.mp4 to write renders into <Root>\render.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File server.ps1 -Root "<project folder>" [-Port 8765]
param(
    [Parameter(Mandatory = $true)][string]$Root,
    [int]$Port = 8765
)
if (-not [IO.Path]::IsPathRooted($Root)) { $Root = Join-Path (Get-Location).Path $Root }   # a project folder named from the working folder
New-Item -ItemType Directory -Force (Join-Path $Root "render") | Out-Null
$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add("http://localhost:$Port/")
$listener.Start()
Write-Output "listening on http://localhost:$Port/ (root: $Root)"
$types = @{ ".html" = "text/html; charset=utf-8"; ".js" = "text/javascript"; ".jpg" = "image/jpeg"; ".jpeg" = "image/jpeg"; ".png" = "image/png"; ".mp4" = "video/mp4"; ".css" = "text/css"; ".json" = "application/json"; ".csv" = "text/csv" }
while ($listener.IsListening) {
    $ctx = $listener.GetContext()
    $req = $ctx.Request; $res = $ctx.Response
    try {
        if ($req.HttpMethod -eq "POST" -and $req.Url.AbsolutePath -eq "/save") {
            $name = [IO.Path]::GetFileName($req.QueryString["name"])
            $out = Join-Path (Join-Path $Root "render") $name
            $fs = [IO.File]::Create($out); $req.InputStream.CopyTo($fs); $fs.Close()
            Write-Output "saved $out"
            $bytes = [Text.Encoding]::UTF8.GetBytes("ok")
        } else {
            $rel = [Uri]::UnescapeDataString($req.Url.AbsolutePath.TrimStart("/"))
            if ($rel -eq "") { $rel = "index.html" }
            $path = Join-Path $Root $rel
            if (Test-Path -LiteralPath $path -PathType Leaf) {
                $bytes = [IO.File]::ReadAllBytes($path)
                $ext = [IO.Path]::GetExtension($path).ToLower()
                if ($types.ContainsKey($ext)) { $res.ContentType = $types[$ext] }
                $res.Headers.Add("Cache-Control", "no-store")
            } else { $res.StatusCode = 404; $bytes = [Text.Encoding]::UTF8.GetBytes("not found") }
        }
        $res.OutputStream.Write($bytes, 0, $bytes.Length)
    } catch { Write-Output "error $_" }
    $res.Close()
}
