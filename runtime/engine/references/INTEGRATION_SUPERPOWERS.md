# Black Dragon v1.3 × KOSIF Superpowers (USIP v6.5)

**Upstream verified on 2026-11-09:** `https://github.com/kosif199022-jpg/kosif-tool` branch `main`, with `.claude/skills/kosif-superpowers/SKILL.md`, `LOADER.md`, `PROTOCOL.md`, `scripts/hub.py`.

## Local integration workflow
1. Put Black Dragon in `~/.claude/skills/black-dragon/`, leaving the existing Superpowers checkout untouched.
2. If Superpowers is local, set `DRAGON_SUPERPOWERS_ROOT` to its `.claude/skills/kosif-superpowers` directory. Otherwise, the bundled SQLite index is only historical discovery metadata, **not live connection**.
3. Call `python scripts/dragon.py ecosystem` and `python scripts/dragon.py probe-tools --json`. Read `missing` vs `discoverable`; neither proves an operation ran.
4. Call `python scripts/dragon.py plan "<task>" --mode smart --json` or `--mode full`. The `superpowers_bridge` field provides *command templates*, not shell invocations.
5. If the skill actually exists on disk, read its `LOADER.md`; run `scripts/skill_loader.py need "<task>"` (or `full` only when requested) through an authorized development environment. Then run `scripts/hub.py find "<task>" --json`, study the matching protocol, check requirements, propose alternatives. This v1.3 bridge DOES NOT run that command itself.
6. For substantial tasks follow USIP canonical stages: intake, evidence inventory, counterarguments, alternatives A/B/C, risk and approval gates, execution receipt, verification. Use `fusionforge.py` only where a project-approved local installation exists, maintaining project isolation and proof receipts.
7. **Never** treat 5,917 descriptive powers or 15,056 indexed Atlas skills as verified executors. For `full` mode inspect everything in the registry but run only applicable verified executors with permission.

## Why no auto-install / auto-git-push?
A CLI plan is safe to inspect; package installation, writing to GitHub, publishing, paid credits and third-party upload change outside systems. This release intentionally requires explicit approval for such operations. Setup defaults to a dry run, and downloaded assets must be attributed with their actual license.

## If Superpowers is not cloned
The GitHub connector can inspect a repo for an assistant, but that does not place its files on your Windows PC or inside this ZIP. `ecosystem` checks LOCAL paths only, never falsely reports a remote GitHub connection as a local installation.
