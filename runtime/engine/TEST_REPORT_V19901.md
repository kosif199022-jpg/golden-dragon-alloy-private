# Black Dragon v1990.1 — GitHub Atlas bridge (candidate)

**Date:** 2026-11-11. **Base:** user-uploaded `black-dragon-v1990.zip` (844 files).

## Source audit (static)

- `black-dragon-v10.16.1.zip` and `black-dragon-v10.16.1_1.zip` are byte-for-byte identical.
- `black-dragon-v10.12.0.zip` vs `v10.12.1.zip`: same 667 filenames; 3 content changes.
- `v10.17.3` -> `v1990`: 22 new paths, 18 changed paths, zero removed paths.
- `dragon-research.rar`: 827 archive entries, including cached README/research notes and a nested copy of the `github-atlas` finished skill. No research scripts were executed.
- `github-atlas.zip`: 34 file entries and `data/atlas.jsonl` with 1,000 parseable JSON objects, each with unique repository ID, across 22 categories.
- The `atlas.jsonl` dataset inside both new archives has identical SHA-256 fingerprints.
- The 8 `blocked` and 30 `consent` labels are from the provided catalogue; not an independent security assessment of current repo states.

## Integration

Added an offline `tool github-atlas` CLI with `find`, `show`, `top`, `cats`, `stats`, `lessons`, `doctor`; a reproducible SHA-256 source manifest; descriptive docs; static entrypoint and registry registrations. Existing `tool atlas` (curated skills), Higgsfield routing, Reel DNA, Cinema Craft, v1990 framecheck/critic/pack tools are not overwritten. Raw cached third-party READMEs are not bundled.

## Local evidence

`python -m unittest discover -s app/tests -p test_v19901_github_atlas.py -v` → **9 passed**. Covered dataset SHA-256 and counts, Arabic/English lookup, refusal of blocked entry, consent notice, stats/categories, missing repository, top filters, absence of obvious process/network calls in the new adapter.

`ast.parse` on changed Python entrypoint and capability registry files → **4 parsed**. Tool registry IDs unique: **76**.

These do NOT establish that repositories work on the user's Windows PC, that 1,000 install commands are verified, or that Higgsfield/XL is free. No external programs were installed or run for the new atlas. No code from RAR research caches was executed; base v1990 remote test claims were not independently reproduced.

## Boundary and security

Read-only catalogue, no network, no installs, no scraping, no clone, no spending. Repo descriptions and install commands are untrusted data. Every external tool needs independent permission, licence check and version check before use. The `show` command refuses installation instructions for source-flagged blocked records. User approval required for privileged, expensive or sensitive execution.

## Version status

Development-only candidate on the local filesystem; no GitHub branch, PR or release has been updated.
