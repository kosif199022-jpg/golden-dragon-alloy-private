# Evidence: how Windows actually reads a command (measured 2026-11-11)

**Machine**
- OS: Windows 11 Pro 10.0.26300.
- Windows PowerShell 5.1.26100.9818. pwsh 7 is not installed.
- cmd.exe 10.0.26100.9818.
- Git Bash: MSYS2 runtime 3.6.10, MSYSTEM=UCRT64.
- Python 3.12.10.
- Code pages: console 65001 inside the Claude tools, ACP 1252, OEMCP 437.
- Environment: PYTHONUTF8=1 and PYTHONIOENCODING=utf-8 are set.

**Case folder:** `C:\Users\<user>\re-tools\cases\wincmd-20261111` (copies of the binaries, probes, raw outputs).

## The model in one paragraph

A Windows command is read in **two independent stages**:
1. **The shell rewrites the line.**
   - PowerShell binds and joins the arguments.
   - cmd expands `%`, removes `^`, and splits on `& | < >`.
   - Git Bash removes quotes and converts POSIX-looking paths.
2. **The shell hands ONE string to `CreateProcessW`.**
3. **The child program re-splits that string itself** with its C runtime rules (MSVC CRT: `\"` is a quote, `2n` backslashes before `"` become `n`, quotes toggle).

cmd.exe does not import `CommandLineToArgvW` (pefile, rz-bin, REA). Each program parses its own line, so two programs can read the same line differently. Every failure measured below is a disagreement between stage 1 and stage 3.

## Results

### Argument matrix (`references/matrix.md`)
26 tricky arguments were sent through 5 routes. Correct argv received:

| route | correct |
|---|---|
| Python `subprocess` with a list | 26 |
| Git Bash, single-quoted | 23 |
| `cmd /c` line | 20 |
| PS 5.1, single-quoted | 18 |
| cmd batch | 18 |

### Fix matrix (`references/fixes.md`)
- Every failure has a verified fix except one: in PS 5.1, a literal `--%` value cannot be passed even through a variable.
- `Invoke-NativeExact` (scripts/NativeExact.ps1) passes all 27 cases, including `--%`, an empty string and Arabic.

### Encoding (`references/encoding.md`)
The tests ran in a fresh `powershell -NoProfile`:
- A BOM-less .ps1 reads Arabic as 1252: 5 letters became 10 chars.
- `>` and `Out-File` write UTF-16LE.
- `Set-Content` writes ANSI, and Arabic becomes `?`.
- Piping Arabic to a native program sends `?????`.
- Capturing native UTF-8 output decodes it as 437.
- `python -I` raises UnicodeEncodeError, because `-I` ignores PYTHONUTF8.

The fixes are:
- `-X utf8` for Python.
- `-Encoding UTF8` on Set-Content and Out-File.
- One line that sets `$OutputEncoding` and both `[Console]` encodings to UTF-8 without BOM (verified).

## Per-tool findings

### omni (classify, probe, plan, hyp)
- cmd.exe and SMA.dll are PE files.
- cmd.exe entropy is 5.9, with no packer hints.
- Its signature is not embedded, which is normal for catalog-signed OS files.
- A depth-3 plan was generated, and 4 competing hypotheses were written: quoting, encoding, shell-rule differences, and genuine program errors.

### die (Detect It Easy)
- cmd.exe and powershell.exe: MSVC 19.38 / VS2022 17.8, LTCG, REPRO debug record.
- The REPRO record explains the fake 1978 build date.
- SMA.dll: .NET Framework 4.5 (CLR 4.0.30319).

### upx
`cmd.exe: NotPackedException`, so there was nothing to unpack.

### rz-bin
- cmd.exe: x86-64 CUI, canary on, NX on, not stripped (cmd.pdb).
- Relevant imports: `CreateProcessW`, `CreateProcessAsUserW`, `SearchPathW`, `ExpandEnvironmentStringsW`, `GetEnvironmentVariableW`, `SetEnvironmentVariableW`, `GetCommandLineW`, `ShellExecuteExW`, `GetConsoleOutputCP`.
- `CommandLineToArgvW` is not imported.

### rz-diff
- `-t imports` between System32 (x64) and SysWOW64 (x86) cmd.exe.
- They differ only in exception-handling ABI imports, so the command logic is the same for 32-bit callers.
- The `-d ssdeep` mode failed on these files (tool limitation).

### rizin
- `izz` shows the control strings as plain UTF-16: `PATHEXT`, `.COM;.EXE;.BAT;.CMD;.VBS;.JS;.WS;.MSC`, `ENABLEDELAYEDEXPANSION`, `DelayedExpansion`, `AutoRun`, `CMDCMDLINE`, `=ExitCode`, `COMSPEC`, `PROMPT`.
- `axt` found two readers of PATHEXT: `fcn.14000d2d0` (executable search) and `fcn.14001c83c` (startup defaults).

### ghidra (through `rea decompile`, provider ghidra, with snapshot)

`fcn.14000d2d0` is the search for an executable:
- It calls `NeedCurrentDirectoryForExePathW(name)`. When that returns TRUE, it puts the **current directory before PATH**. PowerShell never runs a program from the current directory without `.\`.
- It reads `PATHEXT` only when command extensions are on. Otherwise it uses the hard-coded list.
- It splits PATH and PATHEXT on `;` and strips quotes from PATH entries.
- It returns an error when the combined string exceeds `0x1fff` (8191) characters.
- It special-cases `.CMD` and `.BAT`.

`fcn.14001c83c` is the startup routine:
- It sets `PATH=""` if missing.
- It sets the default `PATHEXT` if missing.
- It sets `PROMPT=$P$G` and normalises `COMSPEC` to `...\CMD.EXE`.

### rea
- `rea inspect-pe-imports` independently confirms that `NeedCurrentDirectoryForExePathW`, `CreateProcessW` and `ExpandEnvironmentStringsW` are present and `CommandLineToArgvW` is absent.
- `rea decompile` drove Ghidra, as described above.

### capa (in `retool triage --deep`)
- create process ×5, accept command-line arguments ×2, query env ×4, set env ×5.
- search for file via WinAPI ×3, set current directory ×3.
- ATT&CK: Command and Scripting Interpreter [T1059].
- This is consistent with an interpreter. Nothing unexpected.

### floss
No meaningful decoded or stack strings, only noise. All control strings are plain text, so nothing in cmd's parser is hidden.

### ilspy (`ilspycmd -t System.Management.Automation.NativeCommandParameterBinder`)
This is the PS 5.1 native-argument algorithm, line by line (`out/ilspy/NativeCommandParameterBinder.cs`):
- **L73:** `if (string.Equals("--%", argumentValue as string, OrdinalIgnoreCase))` sets the verbatim marker. The check is on the VALUE, so a quoted or variable `--%` is swallowed.
- **L104:** `if (string.IsNullOrEmpty(text)) continue;` drops empty arguments.
- **L118:** after `--%`, text goes through `Environment.ExpandEnvironmentVariables`, so `%VAR%` is expanded.
- **L122-143:** the argument is wrapped in `"..."` only if it contains whitespace outside an even number of quotes. There is **no escaping**: inner `"` and trailing `\` are emitted raw.

### pylibs (pefile + dnfile)
- pefile confirms the cmd.exe imports listed above.
- dnfile finds `NativeCommandParameterBinder.BindParameters` (RVA 0x2ecd8) and `appendOneNativeArgument` (RVA 0x2ee24) in SMA.dll, independently of ILSpy.

### frida (spawn + hook `KERNELBASE!CreateProcessW`)
PS 5.1 running `& python probe 'print("ok")' '' 'C:\dir with space\' 'say "hi there"'` produced:

```
"...python.exe" ...argv_probe.py print("ok")  "C:\dir with space\" "say "hi there""
```

The child read this as 3 arguments, `print(ok)` | `C:\dir with space" say` | `hi there"`, instead of the 4 that were sent. This matches ILSpy and the child's own `GetCommandLineW`.

### frida-trace (`-f cmd.exe -i KERNELBASE.dll!CreateProcessW`, custom handler)
A batch line `"100%%" "%%PATH%%" "%USERNAME%" "a&b" a^&b !x!` reached CreateProcessW as:

```
"100%" "%PATH%" "<user>" "a&b" a&b !x!
```

So cmd expands `%`, removes `^` **before** CreateProcess, and keeps the quotes for the child to strip.

During the run, two live mistakes reproduced the failures being studied:
- bash `printf` ate `\U`, `\r` and `\a` inside a Windows path.
- `/d /c` were rewritten by MSYS, so cmd started interactive.

### frida-ps
Used to enumerate attachable processes. It listed the running bash.exe sessions.

### pe-sieve
- Scanned a live `cmd.exe /d /k`: 9 modules, 0 patched, 0 IAT hooks, 0 implants.
- So no injector (for example Clink) is changing how cmd parses on this PC.

### yara / yara-x (`scripts/wincmd.yar`)
Four rules:
- PS 5.1-unsafe BOM-less .ps1 with Arabic.
- UTF-16LE text.
- PS 5.1 legacy binder fingerprint.
- cmd PATHEXT/CWD-search fingerprint.

The first draft flagged PE files (3 false positives), so `uint16(0) != 0x5A4D` was added. After the fix, YARA 4.6 and YARA-X give the same 6 hits:
- `lit_nobom.ps1`, `redir.txt`, `outfile.txt`.
- SMA.dll.
- cmd.exe and cmd32.exe.

### pydisasm (CPython 3.12 `subprocess.cpython-312.pyc`, `list2cmdline`)
- The bytecode shows the CRT-inverse algorithm that PS 5.1 lacks: quote on space or tab, double the backslashes before `"` (const 2), emit `\"`, and emit `""` for an empty argument.
- This is why Python list calls got 26/26 and why NativeExact.ps1 copies the algorithm.

### Not run (not applicable to this target)

| tool | reason |
|---|---|
| pyinstxtractor | No PyInstaller binary involved. |
| jadx, apktool, adb, apkleaks, androguard | Android only; no APK in scope. |
| tshark, mitmdump | Command parsing involves no network traffic. |
| webcrack, wasm2wat, wasm-objdump | No JavaScript bundle or WASM in scope. |
| olevba | No Office document. |
| x64dbg, imhex, ilspy-gui, die-gui | Interactive GUIs. The same questions were answered headlessly by frida/frida-trace (runtime), pylibs and rz-bin (bytes), ilspycmd and diec. They can be opened for manual inspection on request. |

## Real-world corpus (`references/corpus.md`, 4,246 commands Claude actually ran on this PC)

| shell | calls | hard failures |
|---|---|---|
| PowerShell tool | 1,786 | 16.9% |
| Bash tool | 2,273 | 5.9% |
| Black Dragon run_command | 185 | 8.6% |

Ranking of the competing hypotheses (ACH):

| hypothesis | finding |
|---|---|
| H1, quoting is the main cause | **weakened.** Only 6 PS-quoting + 6 PS-parse + 12 inline-code cases. The quoting failures are real, but Claude mostly avoided them. |
| H2, encoding | **supported.** 89 cases. |
| H3, rule differences between shells | **partly supported.** 13 path-translation and 32 PATH differences. |
| H4, genuine program errors dominate | **refuted as "most".** 115 of 507 failure rows (23%). |

A cause that was not on the list came out at the top: **how PowerShell reports success** (94 exit-code misreads).

### Corpus claims verified independently in a fresh PS 5.1 (`verify/v.ps1`)
- `native | Select-Object -First 3` gives `$LASTEXITCODE = -1` (the tool shows 255) and `$? = False`. `-Last` gives 0.
- robocopy that copied a file successfully returns exit 1.
- `Get-Content` on BOM-less UTF-8 Arabic gives 10 mojibake characters. With `-Encoding UTF8` it gives 5.
- `rg` is a **bash function** injected by Claude Code (`type rg` says "rg is a function"). `Get-Command rg` in PowerShell is False.

### The Bash-tool length limit, explained by measurement
Corpus, effective length (each `'` counts as 4):

| effective length | failed |
|---|---|
| under 5k | 97 of 2,221 |
| 5k to 7.5k | 2 of 17 |
| 7.5k to 10k | 15 of 15 |
| over 10k | 20 of 20 |

**Process chain** (Win32_Process): `claude.exe` → `Git\bin\bash.exe -c "source <snapshot> ... eval '<command>'"` → `usr\bin\bash.exe`. There is **no cmd.exe** in the chain, so the hypothesis "cmd's 8191 limit" was refuted. Each `'` in the command is written as `'\''`: a command with ~13 quotes showed 50 in the process command line.

`probe/launcher_limit.py` and `probe/msys_limit.py`:
- The launcher is innocent. **`usr\bin\bash.exe -c` itself works up to 8,186 characters and fails at 8,187.**
- A positional argument of 30,000 characters is fine. Two 6,000-character arguments are fine.
- The limit counts characters, not UTF-8 bytes: 4,116 Arabic characters (8,216 bytes) work.

`probe/msys_limit2.py`, behaviour past the limit:
- A quoted token gives `unexpected EOF while looking for matching '`.
- **Unquoted text is truncated SILENTLY:** a trailing `echo ok` never ran, with rc 0.
- **A 12,000-character quoted heredoc produced 8,167 bytes with rc 0.** So `cat > file <<'EOF'` can write a truncated file without any error.

The cause inside msys-2.0.dll or bash was not reverse-engineered (see Open questions). The rule does not depend on it.

### Linter score (`references/lint_eval.md`)
- Lintable, Windows-caused failures flagged: 212/289 (73%).
- Successful commands with an ERROR flag: 5/600 (0.8%).
- WARN flags appear on 26.8% of successes, mostly X001: `python -I` without `-X utf8`, a cheap hygiene fix.
- SH007 alone, over all 2,273 Bash calls: 35 flagged, 35 failed, 0 false alarms.

During development the first draft raised ERROR on 22.7% of successful commands. Blanking here-string and heredoc bodies, plus checking only the program segment that actually receives the argument, brought this to 0.8%.

## Open questions and what would settle them
- Why exactly MSYS2 bash cuts `-c` at 8,186 characters: reverse-engineer how msys-2.0.dll/bash builds the `-c` string (rizin/Ghidra on `msys-2.0.dll`, look for an 8192-sized buffer).
- PowerShell 7.3+ (`$PSNativeCommandArgumentPassing = 'Windows'`) fixes most PS failures. It is not installed here. Installing pwsh and re-running `selftest.py` would measure it.
- Some programs do not use the MSVC CRT to split arguments (for example some Go/Node/MinGW builds or custom parsers). The CRT rules were measured with Python. Run `argv_probe`-style checks if a tool behaves oddly.
