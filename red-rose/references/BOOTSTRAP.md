# Getting a running copy of Red Rose

Read this when `SKILL.md` is not yet in context or when a copy looks old. The short path is in the README top block.

## Where the copy comes from

| Surface | How the skill arrives | What works |
|---|---|---|
| Claude Code on the owner PC, with the installed copy | `~/.claude/skills/red-rose` (made by `install-skill`) | everything, including private memory |
| Claude Code, sparse clone from the private repository | `rr-src/red-rose` after the three clone lines | everything except private memory, unless the owner PC is the one cloning |
| claude.ai with the skill saved | `red-rose.skill` uploaded once in Customize, then Skills | read-only and media commands; `pc_only` ops are labelled |
| Chat with no command tool | nothing runs | the reply rules only |

Facts that matter:

- The link shows the GitHub `main` branch. Work that is not pushed is not reachable from the link.
- Until the owner approves a push and a merge, a pasted link gives the older skill.
- A pasted private link loads nothing on claude.ai, and the sandbox cannot reach the repository.
- The sparse-clone lines were measured earlier in PowerShell 5.1 and Git Bash, and were not re-run in this build. Mark them that way in any report.

## The first run

```
python -X utf8 "<skill folder>/rose.py" start
```

`start` is read-only. It creates no database, writes no file and makes no network call. Its output names the absolute skill path, the version, the commit (`none` when the folder is not a git checkout), missing programs, the Arabic shaping result and the number of ops usable here. Quote its status line in your first reply.

## Trial copy (testing, not the owner's memory)

A trial copy must never touch the owner's private database. Set a database inside the work folder and turn off bytecode files before the first command:

- Git Bash: `export RED_ROSE_DB="$PWD/rose.sqlite3" PYTHONDONTWRITEBYTECODE=1`
- PowerShell 5.1: `$env:RED_ROSE_DB="$PWD\rose.sqlite3"; $env:PYTHONDONTWRITEBYTECODE=1`

The variable is read by `--db`. Without it, a command that needs memory opens the owner's default database, which is `~/.red-rose/memory.sqlite3`.

On the installed copy on the owner PC, do not set `RED_ROSE_DB`. The owner's memory and playbook index are then used on purpose.

## Installing or updating the copy (needs the owner's yes)

```
python -X utf8 "<skill folder>/rose.py" check-skill
python -X utf8 "<skill folder>/rose.py" pack --out <work>/dist
python -X utf8 "<skill folder>/rose.py" pack --out <work>/dist --approve-write
python -X utf8 "<skill folder>/rose.py" pack-verify <work>/dist/red-rose.skill
python -X utf8 "<skill folder>/rose.py" install-skill
python -X utf8 "<skill folder>/rose.py" install-skill --approve-write
```

- `check-skill` is read-only. It lists what a package would hold, the largest files and the content scan result.
- `pack` without `--approve-write` exits 3 and writes nothing. With it, `red-rose.skill` is written into the `--out` folder. An existing archive is never overwritten.
- `pack-verify` checks every file hash and the forbidden names, then unzips the archive into a temp folder outside the repository and runs `start`, `selfcheck --quick` and one recipe self-test from there. Exit 0 means all of that passed.
- `install-skill` without `--approve-write` exits 3 and writes nothing. With it, the skill is copied to `~/.claude/skills/red-rose`. An existing copy is moved to a dated backup folder beside it named `red-rose.backup-YYYYMMDD-HHMMSS`. Nothing is deleted.

Known limit: the backup folder keeps its `SKILL.md`, whose name is also `red-rose`. Delete the backup yourself once it is no longer needed. Where backups should live is an open decision for the owner (see `OWNER_RULES.md`).

## Updating an old copy

1. Confirm the owner has pushed and merged the new work, or that they gave you the new `red-rose.skill`.
2. Get the new folder or archive.
3. Run `start` from the new copy and note the version.
4. Run `pack-verify` on the new archive if you have one.
5. Ask for the yes, then run `install-skill --approve-write`. The old copy goes to the backup folder.

Never copy files over the installed folder by hand. That mixes two versions.
