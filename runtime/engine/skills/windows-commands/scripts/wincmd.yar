// Rules for files that Windows shells will misread, plus fingerprints of the parser code found in this analysis.

rule ps1_utf8_without_bom_non_ascii
{
    meta:
        why = "Windows PowerShell 5.1 reads a BOM-less script as ANSI (1252): Arabic literals turn into mojibake"
    strings:
        $ar = { (D8|D9|DA|DB) (80|81|82|83|84|85|86|87|88|89|8A|8B|8C|8D|8E|8F|90|91|92|93|94|95|96|97|98|99|9A|9B|9C|9D|9E|9F|A0|A1|A2|A3|A4|A5|A6|A7|A8|A9|AA|AB|AC|AD|AE|AF|B0|B1|B2|B3|B4|B5|B6|B7|B8|B9|BA|BB|BC|BD|BE|BF) }
        $ps1 = /(\$[A-Za-z_]\w*\s*=|Write-Host|Get-[A-Z]\w+|Set-[A-Z]\w+|\[Console\]::)/
    condition:
        uint16(0) != 0x5A4D and filesize < 2MB and
        uint16(0) != 0xFEFF and not (uint16(0) == 0xBBEF and uint8(2) == 0xBF) and $ar and $ps1
}

rule text_utf16le_from_ps51_redirect
{
    meta:
        why = "PS 5.1 '>' and Out-File write UTF-16LE; ffmpeg concat lists, jq, python open() default will misread it"
    condition:
        uint16(0) == 0xFEFF and filesize < 10MB
}

rule ps51_legacy_native_arg_binder
{
    meta:
        why = "System.Management.Automation 5.1: native args joined without escaping; value '--%' anywhere = verbatim marker"
    strings:
        $m1 = "appendOneNativeArgument" ascii
        $m2 = "NativeCommandParameterBinder" ascii
        $vb = "--%" wide
    condition:
        uint16(0) == 0x5A4D and all of them
}

rule cmd_default_pathext_and_cwd_search
{
    meta:
        why = "cmd.exe: hard-coded PATHEXT fallback and current-directory-first search (NeedCurrentDirectoryForExePathW)"
    strings:
        $pe = ".COM;.EXE;.BAT;.CMD;.VBS;.JS;.WS;.MSC" wide
        $api = "NeedCurrentDirectoryForExePathW" ascii
        $de = "DelayedExpansion" wide
    condition:
        uint16(0) == 0x5A4D and all of them
}
