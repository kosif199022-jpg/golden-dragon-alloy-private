# Developing Red Rose

Read this only when you change the code or the docs. An agent that uses the skill reads `SKILL.md` and stops there.

## Reading order for a developer

1. `references/INTERFACE.md`: the frozen names, exit codes, call form and envelope. Changing any of them needs the owner.
2. `references/VERIFIED_STATUS.json`: what was run, and its outcome, per op. Only this file may say that something is verified.
3. `AGENTS.md`, then `START_NEXT_AGENT.md`, then `NEXT_AGENT_HANDOFF.md`: the history and the open work. These are long and are not needed to use the skill.
4. `references/OPS.md` and `references/OPS_CATALOG.json`: generated from the code. Do not edit them by hand.
5. `references/RECIPES.md` and `recipes/*.json`: the eight recipes. A recipe is a JSON file checked by `recipe validate`.

## Modules

| Module | Job |
|---|---|
| `rose.py` | the one CLI; loads extensions through `rose_ext.py` |
| `rose_ext.py` | loads each extension's `register()`; a broken one is reported, not fatal |
| `rose_io.py` | parameters, saved fields, JSON output, exit codes |
| `rose_run.py` | runs one `ADAPTER.OP`; the approval gate for writes |
| `rose_catalog.py` | `ops`, `describe`, `find`, `catalog-build` |
| `rose_env.py` | `start`, `doctor-deps`, the usable-here counts |
| `rose_selfcheck.py` | `selfcheck` (runs the catalogue examples in a temp folder) |
| `rose_recipes.py` | `recipes`, `recipe show|validate|run|selftest` |
| `rose_check.py` | `check`, the delivery gate |
| `rose_agent.py` | `understand`, `brief` |
| `rose_pack.py` | `check-skill`, `pack`, `pack-verify`, `install-skill` |
| `capability_runtime.py` and the `*_v2x.py` modules | the operations themselves |

## Tests

Run the tests that matter for the front door and the packaging:

```
python -X utf8 -W error::ResourceWarning -m unittest test_skill_package_v29 test_entry_docs_v29 -v
python -X utf8 -m unittest test_run_v29 test_catalog_v29 test_check_v29 -v
```

Set `RED_ROSE_DB` to a file in a temp folder before any test that may open memory. Never let a test open `~/.red-rose`.

Do not run the whole suite for a small change. Run the tests of the modules you touched, then the front-door tests above.

## Regenerating generated files (write: needs `--approve-write`)

```
python -X utf8 "<skill folder>/rose.py" catalog-build --approve-write
python -X utf8 "<skill folder>/rose.py" selfcheck --quick --json
python -X utf8 "<skill folder>/rose.py" selfcheck --save-status --approve-write
python -X utf8 "<skill folder>/rose.py" recipe validate
python -X utf8 "<skill folder>/rose.py" recipe selftest title-frame-ar
```

- `catalog-build` regenerates `references/OPS_CATALOG.json` and `references/OPS.md` after any signature change.
- `selfcheck --save-status` rewrites `references/VERIFIED_STATUS.json`. Run it only on the build PC, and only after the owner approves the write.
- `recipe validate` checks every recipe file against the schema and the catalogue.

## Packaging

The policy is `PACKAGE_MANIFEST.json`: an allowlist of files, the forbidden names, the content scan patterns and the verify commands. It is not shipped as is. Changing the policy changes what the owner receives, so show the owner the change first.

```
python -X utf8 "<skill folder>/rose.py" check-skill
python -X utf8 "<skill folder>/rose.py" pack --out <work>/dist --approve-write
python -X utf8 "<skill folder>/rose.py" pack-verify <work>/dist/red-rose.skill
```

- `check-skill` is read-only. Run it after any change to find a forbidden name or a finding before you pack.
- The archive holds one top folder, `red-rose/`, and a generated `red-rose/PACKAGE_MANIFEST.json` with file list, sha256 per file and version. It holds no dates.
- The scan refuses secret-looking strings, user-profile paths and imports or shell calls of legacy code. A placeholder such as `/home/user/` is allowed. Never add a real value to a file to get past the scan: remove the value.
- Tests, drafts, evals, questions, databases, media and caches are never packed.

## Rules for code changes

- No import of legacy Golden or Black Dragon code. No network call in the skill. No install.
- Ops that write say so in their catalogue entry, and require the approval gate.
- Do not hard-code counts of ops or recipes in documents. Take them from `start` or from `VERIFIED_STATUS.json`.
- A document may say a thing is verified only if `VERIFIED_STATUS.json` says so. The front-door test checks the drafts for this.
- When you add a subcommand, give it `help=` text, a parser default, and a test that runs it with `--help`.
- Rename nothing in `INTERFACE.md` without the owner.

## Drafts

`drafts/SKILL.draft.md` and `drafts/README_TOP.draft.md` are not live yet. The owner's orchestrator copies them into `SKILL.md` and the README top after review. Until then the live files are the old ones. `drafts/` is never packed.
