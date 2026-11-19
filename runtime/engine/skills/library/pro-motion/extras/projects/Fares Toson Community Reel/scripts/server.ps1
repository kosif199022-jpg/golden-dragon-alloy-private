# Local static server for the reel page + POST /save?name=file.mp4 to write renders.
$root = "G:\Fares Motion\Fares Toson Community Reel"
$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add("http://localhost:8765/")
$listener.Start()
Write-Output "listening on http://localhost:8765/"
$types = @{ ".html" = "text/html; charset=utf-8"; ".js" = "text/javascript"; ".jpg" = "image/jpeg"; ".png" = "image/png"; ".mp4" = "video/mp4"; ".css" = "text/css" }
while ($listener.IsListening) {
    $ctx = $listener.GetContext()
    $req = $ctx.Request; $res = $ctx.Response
    try {
        if ($req.HttpMethod -eq "POST" -and $req.Url.AbsolutePath -eq "/save") {
            $name = [IO.Path]::GetFileName($req.QueryString["name"])
            $out = Join-Path "$root\render" $name
            $fs = [IO.File]::Create($out); $req.InputStream.CopyTo($fs); $fs.Close()
            Write-Output "saved $out"
            $bytes = [Text.Encoding]::UTF8.GetBytes("ok")
        } else {
            $rel = [Uri]::UnescapeDataString($req.Url.AbsolutePath.TrimStart("/"))
            if ($rel -eq "") { $rel = "index.html" }
            $path = Join-Path $root $rel
            if (Test-Path $path -PathType Leaf) {
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
