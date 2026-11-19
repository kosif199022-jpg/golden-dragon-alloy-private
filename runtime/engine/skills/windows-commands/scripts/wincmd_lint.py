#!/usr/bin/env python3
"""wincmd_lint: predict how Windows will MISREAD a command before you run it.

  python -X utf8 wincmd_lint.py --shell powershell "python -c 'print(\"ok\")'"
  python -X utf8 wincmd_lint.py --shell bash --file cmd.txt
  python -X utf8 wincmd_lint.py --shell cmd --json "..."
  echo CMD | python -X utf8 wincmd_lint.py --shell powershell -

Shells: powershell (Windows PowerShell 5.1), bash (Git Bash / MSYS2), cmd (cmd.exe line or .bat).
Levels: error = Windows will misread it (measured); warn = likely problem; info = know this before judging the result.
Exit code: 0 clean or info only, 1 warnings, 2 at least one error.
Every rule is backed by a measurement on this PC or by the 4,246-command corpus (see references/).
"""
import argparse, json, os, re, sys

NATIVE_NAMES = (r"python3?|py|node|npx|npm|ffmpeg|ffprobe|git|gh|jq|curl\.exe|magick|blender|yt-dlp|aria2c|7z|pandoc|"
                r"uv|uvx|pip|whisperx|demucs|rea|rizin|cmd|bash|wsl|docker|winget|java|dotnet|robocopy|[\w.-]+\.exe")
NATIVE_FIRST = re.compile(r"^\s*(?:&\s*)?(?:\$[\w:]+|['\"]?(?:[\w.\\/:~ ()-]*[\\/])?(?:" + NATIVE_NAMES + r")['\"]?)(?=\s|$)", re.I)
PS_BUILTIN = set("""if elseif else foreach for while do switch try catch finally function filter param return throw break continue exit
begin process end trap data class enum using cd chdir ls dir gci echo write cat gc type cp copy cpi mv move mi rm del erase ri rmdir rd
select where sort group measure tee ft fl fw iex icm iwr irm ni mkdir md pwd gl sleep start saps kill spps ps gps clear cls set sv gv
history h r compare diff sls gm foreach-object where-object % ? new-object ren rni gi gp sp sal nal epal ipal cpp popd pushd man help
add-type out-null out-string out-file select-object sort-object test-path join-path split-path resolve-path""".split())
PS_VERBS = set("add approve assert backup block build checkpoint clear close compare complete compress confirm connect convert convertfrom convertto copy debug deny deploy disable disconnect dismount edit enable enter exit expand export find foreach format get grant group hide import initialize install invoke join limit lock measure merge mount move new open optimize out ping pop protect publish push read receive redo register remove rename repair request reset resize resolve restart restore resume revoke save search select send set show skip sort split start step stop submit suspend switch sync tee test trace unblock undo uninstall unlock unprotect unpublish unregister update use wait watch where write".split())


def is_cmdlet_name(tok):
    return bool(re.match(r"^[A-Za-z]+-[A-Za-z]+$", tok)) and tok.split("-")[0].lower() in PS_VERBS


HERESTR = re.compile(r"@(['\"])[ \t]*\r?\n([\s\S]*?)\r?\n\1@")
HEREDOC = re.compile(r"(<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n)([\s\S]*?)(\n\2\b)")


def blank_keep_newlines(s):
    return re.sub(r"[^\n]", " ", s)


def outside_quotes(s, shell):
    """Return s with quoted regions blanked (same length), so operators can be searched safely."""
    out, q, i = [], None, 0
    while i < len(s):
        c = s[i]
        if q is None:
            if c in "'\"":
                q = c
                out.append(" ")
            elif shell == "powershell" and c == "`" and i + 1 < len(s):
                out.append("  ")
                i += 1
            elif shell == "bash" and c == "\\" and i + 1 < len(s):
                out.append("  ")
                i += 1
            else:
                out.append(c)
        else:
            if c == q:
                if shell == "powershell" and i + 1 < len(s) and s[i + 1] == q:
                    out.append("  ")
                    i += 1
                else:
                    q = None
                    out.append(" ")
            elif q == '"' and c == ("\\" if shell == "bash" else "`") and i + 1 < len(s):
                out.append("  ")
                i += 1
            else:
                out.append("\n" if c == "\n" else " ")
        i += 1
    return "".join(out)


def code_bodies(c):
    """Source code handed to python/node: -c/-e arguments, heredocs, PowerShell here-strings."""
    bodies = []
    for m in re.finditer(r"(?:python[0-9.]*|py|node)(?:\.exe)?['\"]?((?:\s+-[A-Za-z]+(?:\s+utf8)?)*)\s+-[ce]\s+", c, re.I):
        i = m.end()
        if i < len(c) and c[i] in "'\"":
            q, j = c[i], i + 1
            while j < len(c):
                if q == '"' and c[j] in "\\`" and j + 1 < len(c):
                    j += 2
                    continue
                if c[j] == q:
                    if j + 1 < len(c) and c[j + 1] == q:
                        j += 2
                        continue
                    break
                j += 1
            bodies.append(c[i + 1:j])
    for m in re.finditer(r"(?:python|node)[^\n]*<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n([\s\S]*?)\n\1\b", c):
        bodies.append(m.group(2))
    for m in HERESTR.finditer(c):
        bodies.append(m.group(2))
    return bodies


def single_quoted(s):
    return [m.group(1) for m in re.finditer(r"'((?:[^']|'')*)'", s)]


class Lint:
    def __init__(self, shell, cmd):
        self.shell, self.cmd, self.hits = shell, cmd, []
        # PowerShell here-string bodies are data: hide them from operator/argument rules
        if shell == "powershell":
            self.c2 = HERESTR.sub(lambda m: "@'" + blank_keep_newlines(m.group(0)[2:-2]) + "'@", cmd)
        elif shell == "bash":  # heredoc bodies are data, not commands
            self.c2 = HEREDOC.sub(lambda m: m.group(1) + blank_keep_newlines(m.group(3)) + m.group(4), cmd)
        else:
            self.c2 = cmd
        self.bare = outside_quotes(self.c2, shell)
        self.codes = code_bodies(cmd)

    def add(self, rid, level, msg, fix):
        if not any(h["rule"] == rid for h in self.hits):
            self.hits.append({"rule": rid, "level": level, "message": msg, "fix": fix})

    def segments(self):
        """Pipeline/statement segments of the command: list of (text, bare_text)."""
        segs, start = [], 0
        for i, ch in enumerate(self.bare + "\n"):
            if ch in ";|\n{}" or i == len(self.bare):
                if i > start:
                    t, bt = self.c2[start:i], self.bare[start:i]
                    m = re.match(r"\s*(?:\$[\w:.]+\s*=\s*|\(\s*|return\s+)", bt)
                    if m:
                        t, bt = t[m.end():], bt[m.end():]
                    if t.strip():
                        segs.append((t, bt))
                start = i + 1
        return segs

    @staticmethod
    def ps_is_native(t):
        """First token of a PowerShell segment names a native program (not a cmdlet, alias, keyword or expression)."""
        if NATIVE_FIRST.match(t) and not re.match(r"\s*\$[\w:]+\s*[.\[=]", t):
            return True
        m = re.match(r"\s*(&\s*)?(['\"]?)([^\s'\"]+)\2(?=\s|$)", t)
        if not m:
            return False
        tok = m.group(3)
        if tok.startswith(("$", "[", "(", "@", "-", "'", '"', "#", ".")) or is_cmdlet_name(tok):
            return bool(m.group(1)) and not is_cmdlet_name(tok)
        if tok.lower() in PS_BUILTIN or not re.match(r"^[\w.\\/:~-]+$", tok):
            return False
        return True

    # ---------------- PowerShell 5.1 ----------------
    def powershell(self):
        c, c2, b = self.cmd, self.c2, self.bare
        segs = self.segments()
        natives = [(t, bt) for t, bt in segs if self.ps_is_native(t)]
        if re.search(r"&&|\|\|", b):
            self.add("PS001", "error", "Windows PowerShell 5.1 has no && or || (ParserError: token is not a valid statement separator).",
                     "Use `A; if ($?) { B }` or run the line in the Bash tool.")
        for t, bt in natives:
            reparses = bool(re.match(r"\s*&?\s*['\"]?(cmd|cmd\.exe)['\"]?\s", t, re.I))  # cmd re-parses the raw line itself
            for lit in ([] if reparses else single_quoted(t)):
                body = lit.replace("''", "'")
                if '"' in body and not re.search(r'\\"', body):
                    self.add("PS002", "error", "A native program will NOT receive the inner double quotes of '" + body[:40] +
                             "' (PS 5.1 passes them raw; the program's C runtime strips them). Measured: 'print(\"ok\")' arrives as print(ok).",
                             "Escape them as \\\" inside the literal, use single quotes inside the code, put the code in a file, "
                             "or call Invoke-NativeExact (scripts/NativeExact.ps1).")
            if re.search(r"(?:^|\s)(''|\"\")(?=\s|$)", t):
                self.add("PS003", "error", "An empty-string argument is dropped by PS 5.1 (appendOneNativeArgument skips empty text).",
                         "Pass '\"\"' (two double quotes inside single quotes) or use Invoke-NativeExact.")
            for lit in single_quoted(t):
                if re.search(r"\s", lit) and re.search(r"(?<!\\)\\$", lit):
                    self.add("PS004", "error", "Path with spaces ending in a backslash: PS 5.1 wraps it in quotes and the program reads \\\" as a literal quote, merging it with the next argument.",
                             "Drop the trailing backslash or double it ('C:\\dir with space\\\\').")
            if re.search(r"\S\s+.*(?<![\w-])['\"]?--%['\"]?(?=\s|$)", t) and not re.match(r"\s*&?\s*\S+\s+--%", t):
                self.add("PS010", "warn", "Any argument whose VALUE is --% (even quoted or from a variable) is swallowed by PS 5.1 as the stop-parsing marker.",
                         "If you need a literal --% use Invoke-NativeExact.")
            if re.search(r"2>&1", bt):
                self.add("PS005", "warn", "2>&1 on a native program in PS 5.1 wraps each stderr line as an ErrorRecord (NativeCommandError) and can set $? = $false even on exit 0.",
                         "Do not redirect stderr; the tool captures it. Check $LASTEXITCODE instead.")
            if re.match(r"\s*&?\s*['\"]?[\w.\\/: ()-]*robocopy", t, re.I) and "LASTEXITCODE" not in c:
                self.add("PS016", "info", "robocopy exit codes 0-7 mean success (1 = files copied, measured); only >= 8 is failure. The tool will report exit 1 as an error.",
                         "Append: ; if ($LASTEXITCODE -lt 8) { $global:LASTEXITCODE = 0 }")
        # native | Select-Object -First
        for i, (t, bt) in enumerate(segs[:-1]):
            if NATIVE_FIRST.match(t) and re.match(r"\s*(Select-Object|select)\s+(-First|-f)\b", segs[i + 1][0], re.I):
                self.add("PS014", "warn", "native | Select-Object -First N stops the native program early: $LASTEXITCODE = -1 (tool shows exit 255) and $? = False although the output is fine (measured).",
                         "Use | Select-Object -Last N, | Out-String, or redirect to a file and read the head.")
        alias = [
            (r"curl\s(?!.*\.exe)", "warn", "curl is an alias of Invoke-WebRequest in PS 5.1", "Call curl.exe"),
            (r"wget\s", "warn", "wget is an alias of Invoke-WebRequest in PS 5.1", "Use curl.exe or Invoke-WebRequest -OutFile"),
            (r"where\s+(?!-)\w", "warn", "where is an alias of Where-Object in PowerShell", "Call where.exe"),
            (r"sc\s", "warn", "sc is an alias of Set-Content", "Call sc.exe"),
            (r"(ls|dir)\s+-[a-zA-Z]{2,}\b", "error", "ls/dir is Get-ChildItem; bundled unix flags like -la fail", "Get-ChildItem -Force"),
            (r"rm\s+-rf\b", "error", "rm is Remove-Item; -rf is invalid", "Remove-Item -Recurse -Force -Confirm:$false"),
            (r"mkdir\s+-p\b", "error", "mkdir -p is not valid in PowerShell", "New-Item -ItemType Directory -Force PATH"),
            (r"(head|tail|grep|touch|which|export|sed|awk)\s", "error", "unix command does not exist in PowerShell", "Select-Object -First/-Last, Select-String, Get-Command, $env:X='v'"),
            (r"rg\s", "error", "rg exists only as a function inside Claude's Bash tool on this PC; PowerShell and Python cannot find it (measured)", "Use the Grep tool, or Select-String"),
        ]
        for pat, lvl, msg, fix in alias:
            if any(re.match(r"\s*" + pat, bt) for _, bt in segs):
                self.add("PS019" if pat.startswith("rg") else "PS006", lvl, msg + ".", fix + ".")
        if re.search(r"(?<![0-9&])>>?\s*['\"]?[^\s'\"|;]+\.(txt|json|csv|srt|ass|vtt|list|md|xml|yaml|yml|py|js|html|ini|cfg|log)\b", b) or \
                re.search(r"\bOut-File\b(?![^|;\n]*-Encoding)", c2):
            self.add("PS007", "warn", "In PS 5.1, > / >> / Out-File write UTF-16LE (FF FE). ffmpeg concat lists, jq, Python open() and most tools misread it (measured).",
                     "Use Out-File -Encoding utf8, Set-Content -Encoding UTF8, or [IO.File]::WriteAllText(path, text) for BOM-less UTF-8.")
        if re.search(r"\b(Set-Content|Add-Content)\b(?![^|;\n]*-Encoding)", c2) and re.search(r"[^\x00-\x7f]", c):
            self.add("PS008", "error", "Set-Content/Add-Content without -Encoding write ANSI (1252): Arabic becomes '?'. Measured: مرحبا -> 3f 3f 3f 3f 3f.",
                     "Add -Encoding UTF8.")
        if re.search(r"\b(Get-Content|gc)\b(?![^|;\n]*-Encoding)", c2, re.I):
            self.add("PS015", "warn", "Get-Content without -Encoding reads BOM-less UTF-8 as ANSI 1252: Arabic turns into Ø§Ù„... (measured: 5 letters -> 10 chars; 20 corpus cases).",
                     "Get-Content -Encoding UTF8 PATH (add -Raw for one string).")
        if natives and re.search(r"[^\x00-\x7f]", c) and re.search(r"\|\s*&?\s*['\"]?[\w.\\:/ -]*(python|node|ffmpeg|jq|\w+\.exe)", c2, re.I) \
                and "OutputEncoding" not in c:
            self.add("PS009", "info", "Non-ASCII text piped into a native program: fine inside Claude's PowerShell tool (it sets UTF-8), but a fresh powershell.exe / .ps1 sends '?' ($OutputEncoding is ASCII, measured).",
                     "In scripts start with: $OutputEncoding = [Console]::InputEncoding = [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false")
        if re.search(r"2>\s*/dev/null|(?<!<)<<(?!<)\s*['\"]?\w+|\[\s+-[fdez]\s", b) or \
                any(re.match(r"\s*[A-Za-z_]\w*=\S+\s+\w", bt) for _, bt in segs):
            self.add("PS011", "error", "Bash syntax inside PowerShell (heredoc, [ -f ], VAR=x cmd, /dev/null).",
                     "Use PowerShell syntax (2>$null, Test-Path, $env:VAR='x'; cmd) or switch to the Bash tool.")
        if re.search(r"^[ \t]+['\"]@\s*$", c, re.M):
            self.add("PS012", "error", "Here-string terminator '@ / \"@ must start at column 0.", "Move the closing '@ to the start of the line.")
        if re.search(r"python[0-9.]*(\.exe)?['\"]?(\s+-\w+(\s+utf8)?)*\s+-c\s", c, re.I) and any(b_.count("\n") > 3 or len(b_) > 600 for b_ in self.codes):
            self.add("PS013", "warn", "Long python -c code inside PowerShell is the #1 source of quoting breakage.",
                     "Write the code to a .py file with the Write tool and run python -X utf8 file.py.")
        if re.search(r"-ErrorAction\s+SilentlyContinue|2>\s*\$null|\|\s*Out-Null", c2, re.I) and not re.search(r"try\s*\{", c2):
            self.add("PS017", "info", "SilentlyContinue / 2>$null / Out-Null hide the message but a failed cmdlet still makes the tool report exit 1.",
                     "Wrap in try { ... -ErrorAction Stop } catch {} when the failure is expected.")
        if self.ps_backslash_quote_in_dq(c2):
            self.add("PS020", "error", "\\\" inside a PowerShell double-quoted string: backslash is NOT an escape in PowerShell, so the string ends at that quote (corpus: 'unterminated string literal', \"'.*' is not recognized\").",
                     "Inside \"...\" write `\" (backtick) or \"\"; better: a single-quoted literal with \\\" for native programs, or a here-string / file.")
        if re.search(r"&\s*\$[\w:]+[\\/][^\s'\"]*", b):
            self.add("PS021", "error", "& $var\\path without quotes: PowerShell takes $var alone as the command name and the rest as an argument (corpus: 'The term C:\\...\\re-tools is not recognized').",
                     'Quote it: & "$var\\path\\tool.ps1".')
        for mm in re.finditer(r"((?:[A-Za-z]:|\$HOME|\$env:USERPROFILE)[^'\"\n|;]*?\.ps1)\b", c):
            path = mm.group(1).replace("$HOME", os.path.expanduser("~")).replace("$env:USERPROFILE", os.path.expanduser("~"))
            try:
                head = open(path, "rb").read(200000)
            except OSError:
                continue
            if not head.startswith((b"\xef\xbb\xbf", b"\xff\xfe")) and re.search(rb"[\xd8-\xdb][\x80-\xbf]", head):
                self.add("PS022", "error", os.path.basename(path) + " is UTF-8 without BOM and contains Arabic: Windows PowerShell 5.1 reads it as ANSI 1252 (measured: 5 letters -> 10 chars; corpus: Unexpected token '\u00d8\u00aa\u00d9\u2020\u00d9\u0160\u00d9\u2020').",
                         "Re-save it as UTF-8 WITH BOM, e.g. [IO.File]::WriteAllText(p, t, (New-Object System.Text.UTF8Encoding $true)).")
        if re.search(r"[\u201c\u201d\u2018\u2019]", b):
            self.add("PS018", "error", "Curly quotes (“ ” ‘ ’) outside a string are real quote characters to the PowerShell parser and break the line.",
                     "Replace them with straight quotes, or keep text with curly quotes in a file.")

    @staticmethod
    def ps_backslash_quote_in_dq(s):
        q, i = None, 0
        while i < len(s):
            ch = s[i]
            if q is None:
                if ch in "'\"":
                    q = ch
                elif ch == "`":
                    i += 1
            elif q == '"':
                if ch == "`":
                    i += 1
                elif ch == '"':
                    if i + 1 < len(s) and s[i + 1] == '"':
                        i += 1
                    elif i > 0 and s[i - 1] == "\\" and i + 1 < len(s) and s[i + 1] not in " \t\n;)":
                        return True
                    else:
                        q = None
            elif q == "'":
                if ch == "'":
                    if i + 1 < len(s) and s[i + 1] == "'":
                        i += 1
                    else:
                        q = None
            i += 1
        return False

    # ---------------- Git Bash (MSYS2) ----------------
    def bash(self):
        c, b = self.c2, self.bare
        win_tools = r"(?:cmd|cmd\.exe|taskkill|tasklist|findstr|robocopy|xcopy|schtasks|reg|sc|icacls|net|netsh|wmic|attrib|timeout|start|where|shutdown|msiexec|certutil|choice)"
        m = re.search(r"(?:^|[;&|(]\s*|\s)" + win_tools + r"\s+(?:[^;&|\n]*\s)?(/[A-Za-z?]{1,4})(?=\s|$)", b, re.I | re.M)
        if m and "MSYS_NO_PATHCONV" not in c and "MSYS2_ARG_CONV_EXCL" not in c:
            self.add("SH001", "error", f"Git Bash converts the switch {m.group(1)} into a Windows path before the program sees it (measured: /c -> C:/, so cmd /c starts an interactive shell).",
                     "Prefix MSYS_NO_PATHCONV=1, or write //c, or run the Windows tool from the PowerShell tool.")
        for mm in re.finditer(r"(?<![\w'\"/])([A-Za-z]:\\[^\s'\";|&]*)", c):
            if b[mm.start()] == c[mm.start()] and "\\" in mm.group(1):
                self.add("SH002", "error", f"Unquoted Windows path {mm.group(1)[:40]}: bash eats the backslashes (measured: C:\\Users\\x -> C:Usersx).",
                         "Quote it ('C:\\Users\\x') or use forward slashes (C:/Users/x or /c/Users/x).")
                break
        if re.search(r"\b(printf|echo\s+-e)\s+['\"][^'\"]*[A-Za-z]:\\[^'\"]*['\"]", c):
            self.add("SH003", "error", "printf/echo -e interpret \\U \\a \\r \\t inside Windows paths (measured: \\re-tools -> e-tools, \\argv -> BEL rgv).",
                     "Write files with the Write tool, or use printf '%s' with the path as an argument, or forward slashes.")
        if re.search(r"\$env:\w+|(?:^|[;&|]\s*)(Get|Set|New|Remove)-[A-Z]\w+|2>\$null", b, re.M):
            self.add("SH004", "error", "PowerShell syntax inside Bash.", "Use the PowerShell tool, or bash syntax ($VAR, 2>/dev/null, heredoc).")
        if re.search(r">\s*nul\b", b, re.I):
            self.add("SH005", "warn", "'> nul' in bash creates a file, it is not the Windows null device.", "Use > /dev/null.")
        if re.search(r"\b(gh\s+api|git\s+\S+.*\s--format=)\s+['\"]?/[a-z]", c) and "MSYS_NO_PATHCONV" not in c:
            self.add("SH006", "warn", "An argument that starts with / is rewritten by MSYS to C:/Program Files/Git/... for native programs (gh api /repos/... is a common victim).",
                     "Drop the leading slash (gh api repos/...), or prefix MSYS_NO_PATHCONV=1.")
        last = re.split(r"[;&|\n]", b.strip())[-1].strip() if b.strip() else ""
        if re.match(r"(grep|egrep|ls|diff|cmp|test|\[|find\s.*-quit)\b", last):
            self.add("SH010", "info", "The exit code of a bash list is the LAST command's: grep with no match, ls of a missing path, diff with differences all return 1 although everything before worked (15 corpus 'failures').",
                     "Read the output before judging; append '|| true' when no-match is acceptable.")
        eff = len(self.cmd) + 3 * self.cmd.count("'")
        heredoc_file = bool(re.search(r"cat\s*>>?\s*\S+\s*<<|<<-?\s*['\"]?\w+['\"]?\s*>\s*\S+", self.cmd))
        if eff > 7500:
            self.add("SH007", "error", f"Command is ~{eff} effective characters (each ' counts as 4 because the Bash tool wraps it in eval '...'). "
                     "MSYS2 bash truncates a -c script at 8,186 characters (measured): with an open quote you get 'unexpected EOF while looking for matching'; "
                     "without one the tail is DROPPED SILENTLY (a 12,000-char heredoc wrote only 8,167 bytes, exit 0). Corpus: 35/35 commands above 7,500 failed.",
                     "Write the script/content with the Write tool, then run the file.")
        elif eff > 6000 and heredoc_file:
            self.add("SH007", "warn", f"Heredoc writing a file in a ~{eff}-char command: close to the 8,186-char MSYS2 limit where heredocs are truncated silently.",
                     "Use the Write tool for file content.")
        for code in self.codes:
            if re.search(r"['\"]/(c|d|[a-z])/(Users|Program|Windows)", code):
                self.add("SH008", "error", "POSIX path /c/... inside Python/Node code: MSYS converts only whole arguments, never paths inside code, and Windows Python cannot open /c/Users/... (13 corpus failures).",
                         "Use C:/Users/... inside code, or pass the path as an argument (MSYS converts arguments).")
            elif re.search(r"['\"]/tmp/", code):
                self.add("SH009", "warn", "'/tmp/...' inside Python/Node code means C:\\tmp\\... to Windows Python, not bash's /tmp (which is %TEMP%).",
                         "Pass the path as an argument, or use $(cygpath -m /tmp/x).")

    # ---------------- cmd.exe ----------------
    def cmdexe(self):
        c = self.cmd
        if re.search(r"(?<!%)%(?![%\w~*])|(?<![%\w])%\s", c) and "%%" not in c:
            self.add("CMD001", "warn", "In a .bat/.cmd file a lone % is deleted and %NAME% pairs are expanded before the program runs (measured with frida-trace: \"100%\" -> 100).",
                     "Write %% for a literal percent inside batch files.")
        if "!" in c and re.search(r"enabledelayedexpansion", c, re.I):
            self.add("CMD002", "warn", "With delayed expansion on, ! characters are consumed.", "Escape as ^! or disable delayed expansion.")
        if re.search(r'"[^"\s]*\s[^"]*"[^"\s]+"', c):
            self.add("CMD003", "warn", "Nested double quotes: cmd passes them through and the program's C runtime strips them (measured: \"say \"hi\"\" -> say hi).",
                     'Escape inner quotes as \\" for C-runtime programs.')
        if len(c) > 8191:
            self.add("CMD004", "error", "cmd.exe line limit is 8191 characters (0x1fff check in cmd.exe).", "Use a response file, a script file, or Python subprocess.")

    def common(self):
        c = self.c2
        if re.search(r"python[0-9.]*(\.exe)?['\"]?(\s+-\w+)*\s+-I\b", c, re.I) and not re.search(r"-X\s*utf8", c, re.I):
            self.add("X001", "warn", "python -I ignores PYTHONUTF8/PYTHONIOENCODING; printing Arabic to a pipe raises UnicodeEncodeError cp1252 (measured; 21 of 104 corpus calls crashed).",
                     "Use python -I -X utf8.")
        if re.search(r"-filter_complex_script\b", c):
            self.add("X002", "error", "ffmpeg 9 removed -filter_complex_script.", "Use -/filter_complex FILE.")
        if re.search(r"\bimport\s+fitz\b", c):
            self.add("X003", "warn", "PyMuPDF: import fitz is legacy.", "import pymupdf.")
        if len(c) > 32000:
            self.add("X004", "error", "CreateProcess command lines are limited to 32767 characters.", "Pass data through a file or stdin.")
        for code in self.codes:
            if re.search(r"(?<![rRbBfF\w])(['\"])[A-Za-z]:\\(U|N|x|u)", code):
                self.add("X006", "warn", "A Windows path like \"C:\\Users\" inside Python source is an escape sequence (\\U, \\N, \\x) -> SyntaxError unicodeescape.",
                         "Use r\"C:\\Users\\...\" or forward slashes \"C:/Users/...\".")
                break

    def run(self):
        {"powershell": self.powershell, "bash": self.bash, "cmd": self.cmdexe}[self.shell]()
        self.common()
        return self.hits


def lint(cmd, shell):
    return Lint(shell, cmd).run()


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--shell", required=True, choices=["powershell", "bash", "cmd"])
    ap.add_argument("--file")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("command", nargs="?")
    a = ap.parse_args()
    if a.file:
        cmd = open(a.file, encoding="utf-8-sig").read()
    elif a.command == "-" or a.command is None:
        cmd = sys.stdin.read()
    else:
        cmd = a.command
    hits = lint(cmd, a.shell)
    if a.json:
        print(json.dumps(hits, ensure_ascii=False, indent=1))
    elif not hits:
        print("clean: no known Windows misreading for this shell")
    else:
        for h in hits:
            print(f"[{h['level'].upper()}] {h['rule']}: {h['message']}\n        fix: {h['fix']}")
    sys.exit(2 if any(h["level"] == "error" for h in hits) else 1 if any(h["level"] == "warn" for h in hits) else 0)


if __name__ == "__main__":
    main()
