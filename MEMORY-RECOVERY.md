# Owner memory integrity and recovery

This is the complete, **private** Golden Dragon Alloy repository. Do not make it
public: the database contains the original 163 private memory units and
`owner-memory/live/` contains the owner's plans, lessons, and chats.

## Verify before syncing

Run in the full repository checkout:

```powershell
python -X utf8 forge/memory_integrity.py
python -m unittest discover -s forge -p test_memory_integrity.py -v
python -X utf8 alloy.py memory stats
```

The audit checks all files listed in `owner-memory/snapshot_manifest.json`
against their original SHA-256 values, checks that no extra snapshot files are
unlisted, validates JSONL journal structure and duplicate IDs, and verifies
the historical private memory count has **not fallen below 163**. It is
read-only and never logs the content of private memories.

The private repository's GitHub workflow runs these checks on changes and
pull requests. This does not capture changes sitting only on the PC.

## Keep learning safely

```powershell
python -X utf8 alloy.py memory remember "تعليمات جديدة" --kind correction
python -X utf8 alloy.py memory recall "تعليمات"
python -X utf8 alloy.py learn "درس جديد" --domain general
python -X utf8 alloy.py memory snapshot
python -X utf8 forge/memory_integrity.py
python -X utf8 alloy.py memory sync --push
```

Memory is learned when given an explicit `remember` or `learn` command.
It is **not** automatically distilled from every conversation or pushed in
the background. The push checks that the remote GitHub repository is private.

If verification fails, **do not run snapshot/sync to conceal the failure**.
Inspect the issue codes without printing private text. Keep the original live
memory directory unchanged; copy the suspected file to a separate recovery
folder and compare it with a historical copy in private Git history.

## Recovery without destructive overwrite

Prefer restoring a missing file into a fresh recovery folder instead of
overwriting the active memory. For example, while inside the private repo:

```powershell
git show HEAD:owner-memory/snapshot_manifest.json
git log --oneline -- owner-memory/
```

Use the desired historical commit with `git show COMMIT:path/to/file`, saving
the content to a separate location, and verify its SHA-256. Do **not** run a
bulk `git restore` into the live user directory automatically.

The complete original archival download is also preserved under the private
release `v4.0.0-original`. A private GitHub repository is access-controlled,
but **not equivalent to client-side encryption**; keep credentials out of
new memory entries and manage collaborator access carefully.
