# NativeExact.ps1 - call a native program from Windows PowerShell 5.1 so it receives EXACTLY the argv you meant.
#
# Why: PS 5.1's NativeCommandParameterBinder (System.Management.Automation.dll, appendOneNativeArgument)
# joins arguments without escaping: inner " are passed raw (the child's CRT strips them), empty strings are
# dropped, a trailing \ eats the closing quote, and any argument whose value is '--%' is swallowed.
# This helper builds the command line with the MSVC/CRT rules (same algorithm as Python's list2cmdline)
# and starts the process directly, reading stdout/stderr as UTF-8.
#
# Usage:
#   . "$env:USERPROFILE\.claude\skills\windows-commands\scripts\NativeExact.ps1"
#   $r = Invoke-NativeExact python @('-c', 'print("ok")', '', 'C:\dir with space\')
#   $r.ExitCode; $r.StdOut; $r.StdErr; $r.CommandLine

function ConvertTo-NativeCommandLineArg {
    param([AllowEmptyString()][string]$Arg)
    if ($Arg.Length -gt 0 -and $Arg -notmatch '[\s"]') { return $Arg }
    $sb = New-Object System.Text.StringBuilder
    [void]$sb.Append('"')
    $bs = 0
    foreach ($ch in $Arg.ToCharArray()) {
        if ($ch -eq '\') { $bs++; continue }
        if ($ch -eq '"') { [void]$sb.Append('\' * ($bs * 2 + 1)); [void]$sb.Append('"'); $bs = 0; continue }
        if ($bs) { [void]$sb.Append('\' * $bs); $bs = 0 }
        [void]$sb.Append($ch)
    }
    if ($bs) { [void]$sb.Append('\' * ($bs * 2)) }
    [void]$sb.Append('"')
    return $sb.ToString()
}

function Invoke-NativeExact {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [AllowEmptyString()][AllowEmptyCollection()][string[]]$ArgumentList = @(),
        [string]$WorkingDirectory = (Get-Location).ProviderPath,
        [string]$StdIn = $null,
        [int]$TimeoutSec = 0
    )
    $exe = $FilePath
    if (-not (Test-Path -LiteralPath $exe)) {
        $cmd = Get-Command $FilePath -CommandType Application -ErrorAction Stop | Select-Object -First 1
        $exe = $cmd.Source
    }
    $line = ($ArgumentList | ForEach-Object { ConvertTo-NativeCommandLineArg $_ }) -join ' '
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $exe
    $psi.Arguments = $line
    $psi.WorkingDirectory = $WorkingDirectory
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.RedirectStandardInput = [bool]$StdIn
    $utf8 = New-Object System.Text.UTF8Encoding $false
    $psi.StandardOutputEncoding = $utf8
    $psi.StandardErrorEncoding = $utf8
    $p = [System.Diagnostics.Process]::Start($psi)
    $outTask = $p.StandardOutput.ReadToEndAsync()
    $errTask = $p.StandardError.ReadToEndAsync()
    if ($StdIn) {
        $w = New-Object System.IO.StreamWriter($p.StandardInput.BaseStream, $utf8)
        $w.Write($StdIn); $w.Close()
    }
    if ($TimeoutSec -gt 0) {
        if (-not $p.WaitForExit($TimeoutSec * 1000)) { $p.Kill(); throw "Timed out after $TimeoutSec s: $exe" }
    }
    $p.WaitForExit()
    [pscustomobject]@{
        ExitCode    = $p.ExitCode
        StdOut      = $outTask.Result
        StdErr      = $errTask.Result
        CommandLine = "`"$exe`" $line"
    }
}
