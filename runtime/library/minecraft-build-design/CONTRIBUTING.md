# Contributing

Thanks for helping! Issues and pull requests are welcome - bug reports with the output of `mcb doctor` and the failing
command are the most useful.

## Development setup

```bash
git clone https://github.com/yimeng-YM/minecraft-build-design
cd minecraft-build-design
python -m pip install -r scripts/requirements.txt pyyaml
python scripts/mcb.py doctor
python scripts/mcb.py selftest
```

Point an agent at your working copy by cloning (or symlinking) it into its skills folder, e.g.
`~/.claude/skills/minecraft-build-design`.

## Guidelines

- `SKILL.md` stays agent-neutral and short (under 500 lines, ~5k tokens); details go into `references/`.
- Command-line output is English. Anything the player receives (guide, preview page, materials, image labels, video
  labels) goes through `scripts/mcbuild/i18n.py` with both Chinese and English strings.
- Never add game assets (textures, models, sounds, translations, game code) - read them from the player's own
  installation at run time. Factual data in `scripts/mcbuild/data/<version>/` is fine.
- Nothing may write to the player's saves, caches, mods or servers; downloads and installs need the user's OK
  (`mcb fetch` requires `--yes`).
- No machine-specific paths: add discovery to `util.py` or a profile key to `config.py` instead.
- Keep Python 3.10 compatible; core dependencies are numpy and Pillow only.

## Checks before a pull request

```bash
python .github/scripts/validate_skill.py .     # Agent Skills spec: name, description, links …
python scripts/mcb.py selftest                 # end-to-end on a temporary project, zh + en
python .github/scripts/package.py --check      # the release zip builds and contains only the skill
```

CI runs the same on Windows, macOS and Linux.

## Releasing (maintainers)

1. Update `metadata.version` in `SKILL.md` and add a section to `CHANGELOG.md` (same version, today's date).
2. Commit, then tag and push: `git tag -a vX.Y.Z -m "vX.Y.Z"` and `git push origin main vX.Y.Z`.
3. The CI workflow validates, runs the selftests, builds `minecraft-build-design-vX.Y.Z.zip` plus `SHA256SUMS.txt`
   and publishes the GitHub release with the changelog section as notes. The tag must match `metadata.version`.
