# Windows command failures: evidence corpus (2026-11-11)

Written by the corpus sub-agent; saved by the main session because sub-agents could not write .md files.

**Sources and method**
- Claude Code transcripts plus 40 Black Dragon chats. The current session (011f99db) was skipped.
- Calls were de-duplicated by tool_use id.
- A failure is either `is_error=true` (hard), or exit 0 with a shell-level error in the output (soft).
- Each failure got one category, by regex, checked by reading samples.

## Totals

| Shell | Calls | Hard fails | Rate | Soft |
|---|---|---|---|---|
| PowerShell tool (5.1) | 1,786 | 301 | 16.9% | 28 |
| Bash tool (Git Bash) | 2,273 | 134 | 5.9% | 21 |
| Black Dragon run_command (PS 5.1) | 185 | 16 | 8.6% | 7 |
| terminal-mcp | 2 | 0 | 0% | 0 |
| **All** | **4,246** | **451** | **10.6%** | **56** |

## Top categories (507 rows)

1. genuine-program-error: 115 (not Windows)
2. exitcode-misread/hidden-error: 94
3. encoding-unicode: 89
4. file-not-found/state: 42
5. too-long (cmdline/MAX_PATH): 39
6. command-not-found/PATH: 32
7. permission/sandbox-denied: 29
8. other: 15
9. path-translation/backslash: 13
10. user-interrupted: 11

The rest:
- ps-quoting-native-args: 6
- ps-parse-error: 6
- file-locked: 6
- wrong-tool-flags: 4
- ps-stderr-NativeCommandError: 2
- ps-alias/unix-ism: 2
- ps7-feature: 1
- path-spaces-arabic: 1

## Agent's 10 rules (the main session verified 4 of them independently)

1. Run Python with `-X utf8`, never rely on PYTHONIOENCODING under `-I`.
   Corpus: 21 of 104 `-I` calls that relied on PYTHONIOENCODING crashed, against 1 of 77 calls with `-X utf8`.
2. Keep each Bash-tool command under about 7,500 effective chars (every `'` counts as 4).
   Verified: 35 of 35 commands above that failed. The root cause was then found: MSYS2 bash truncates `-c` at 8,186 chars.
3. `native | Select-Object -First N` in PS 5.1 gives exit 255. Verified: `$LASTEXITCODE = -1`.
4. Don't trust PowerShell exit codes blindly:
   - SilentlyContinue, `2>$null` and Out-Null still give exit 1.
   - For robocopy, exit codes 1-7 mean success. Verified: exit 1 after a successful copy.
5. Always use `Get-Content -Encoding UTF8`. Verified: 5 letters were read as 10 characters.
6. Check the tool exists in the current shell. Verified: `rg` exists only as a function in the Bash tool.
7. Never pass `/c/...` or `/tmp/...` paths inside code to Windows programs.
8. Put inline code in a file or a here-string. PowerShell does not escape with `\"`.
9. Use Monitor or run_in_background instead of `sleep N`. Pass literal paths to Remove-Item.
10. Keep paths short (MAX_PATH 260). Close xlsx files that are open in Excel before writing.
