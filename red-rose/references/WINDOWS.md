# Windows rules for Red Rose

The owner works on Windows 11 with PowerShell 5.1 as the default shell. Git Bash is also used. Every rule below was measured with `test_crossshell_v29.py` in PowerShell 5.1, cmd and Git Bash, unless it is marked otherwise.

## Always

- Start Python with `python -X utf8`. Do not use `python -I` for these commands: it ignores the UTF-8 setting and Arabic text fails with `UnicodeEncodeError`.
- Put the skill path in double quotes every time.
- Use forward slashes in file arguments, for example `--save svg=<work>/title.svg`.
- Keep Arabic inside double quotes: `text="الوردة الحمراء"`. Measured in all three shells.

## Forms that work (measured)

```
python -X utf8 "<skill folder>/rose.py" run text.motion.kinetic_text text="الوردة الحمراء" style=fade_up t=0.8
python -X utf8 "<skill folder>/rose.py" run text.motion.kinetic_text --params-file <work>/params.json --out <work>/step.json --approve-write
python -X utf8 "<skill folder>/rose.py" run text.motion.kinetic_text text="الوردة الحمراء" --save svg=<work>/title.svg --approve-write
```

- `key=value` tokens, with the value in double quotes when it has Arabic or spaces.
- `--params-file FILE` for anything long or nested. Write the JSON with the file tool, never inline.
- `--save FIELD=FILE`, repeated for each field. Never comma-separated.

## Forms that fail (do not use)

- **Arabic typed without quotes (PowerShell 5.1).** `text=الوردة الحمراء` reaches the skill as two tokens: `text=الوردة` and `الحمراء`. The skill answers `not a key=value parameter: 'الحمراء'` with exit 1, and its hint repeats this rule. This is PowerShell's quoting, not the skill's. Fix: wrap the whole pair in double quotes, `text="الوردة الحمراء"`.
- **Inline JSON in PowerShell 5.1.** The quotes are stripped and the JSON fails with `JSONDecodeError`. Backslash-escaping works only for JSON without spaces, and fails with an Arabic phrase. Use `--params-file` instead.
- **Long inline input.** Windows refuses a command line that is too long: about 200 rows of ledger and bank data per side fail with `WinError 206`. Use a params file.
- **Shell redirection for Arabic output.** `>` in PowerShell 5.1 writes the console code page: Arabic becomes mojibake. Use `--out FILE`, which the CLI writes as UTF-8 itself. A file written with a byte-order mark (BOM) must be read with `utf-8-sig`.
- **`&&` in PowerShell 5.1.** Not supported. Use `;` and check `$LASTEXITCODE`.
- **Stop-parsing token.** `--%` was seen to pass one inline argument in an earlier audit. It is not a rule for JSON: use `--params-file`.

## Exit codes in PowerShell

PowerShell shows `$LASTEXITCODE` after a native command. Read it right after the call. A script that checks only for a printed error will believe a blocked write happened, so check the exit code: 3 means nothing was written.

## Paths and programs

- ffmpeg and ffprobe are on PATH on the owner PC. `start` lists the versions it found, and names any program that is missing.
- The skill runs its own files from the folder it lives in. It does not need the current directory to be that folder.
- Use `<work>` for the work folder the owner allows. Do not write into the skill folder or the owner's originals.

## Git clone on Windows

A full clone of the repository fails on Windows because of long paths. Use the sparse-clone lines in the README top block. They include `-c core.longpaths=true`, which is needed. These lines are the same in PowerShell 5.1 and Git Bash. They were measured earlier, not re-run in this build.

## Database and cache files

- Without `RED_ROSE_DB`, a command that needs memory uses `~/.red-rose/memory.sqlite3`. On a trial, set `RED_ROSE_DB` to a file inside the work folder.
- Use `PYTHONDONTWRITEBYTECODE=1` on a trial copy so that no `__pycache__` folder appears in the skill folder.
- `start` and `check-skill` open no database and create no file. Other read commands may open the database: use `RED_ROSE_DB` on a trial.
