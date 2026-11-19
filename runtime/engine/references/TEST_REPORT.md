# Black Dragon v10.1.0 — test and provenance report (2026-11-09)

## Inputs and integration

Reviewed the three *newly supplied* archives and compared their full path / SHA-256 inventories against the existing `black-dragon-v10.0.0.zip`:

- `black-dragon-v1.3.zip` (435 non-directory entries): newer media and montage bug fixes, bundled stock-search tools, fixtures and regression tests.
- `black-dragon-v1.2(2).zip` (418 non-directory entries): predecessor snapshot; relevant implementations were superseded by v1.3 or already in v10.
- `black-dragon-skill-v1.2(1).zip` (389 non-directory entries): independent alternative structure; useful for architecture comparison, but not a replacement for the more complete v10 implementation.

Imported or updated **58 file paths** from the supplied v1.3 source before local compatibility edits. See `references/UPSTREAM_V13_DIFF.md` for the file-by-file import inventory. Preserved v10's cognitive review, 22,349-record catalog audit, 7-stage video QA, offline reference links index, Kling text planner, non-destructive installs and tooling. This is a selective merge; not a claim that all three archives' code was installed wholesale.

## Confirmed results in this development environment

| Test group | Actual result | Interpretation |
|---|---|---|
| `PYTHONPATH=app python -m pytest -q app/tests/test_v13_stock.py app/tests/test_v13_montage.py app/tests/test_v13_gate.py app/tests/test_v12_exact_length.py --maxfail=1` | **61 passed** | New stock/search stub fixtures, actual local ffmpeg test clips, silence/mux/visual QA, montage constraints, routing and fallback cases. No external downloading in tests. |
| `PYTHONPATH=app python -m pytest -q app/tests/test_v10.py app/tests/test_v13_capabilities.py app/tests/test_v12.py app/tests/test_v12_docs.py app/tests/test_phase1.py app/tests/test_phase2.py app/tests/test_phase3.py app/tests/test_phase5.py app/tests/test_v12_integration.py --maxfail=1` | **65 passed, 28 skipped, 2 warnings** | Maintains the v10 baseline and old modules. One old v1.2 integration test was updated to expect explicit `DRAGON_HOME` guidance instead of the removed `DRAGON_MODE=cloud` guidance. This expectation changed intentionally for owner-repo safety. |
| CLI smoke tests | Passed | `tool stock sources`, `tool stock check`, `v10 catalog-audit`, `v10 think`, `verify --help`, safe `setup --dry-run`, `where`, and `words` friendly missing dependency message. |
| Python import/bytecode compilation | Passed | `dragon`, bundled engines, and launcher. |

An additional group, `test_v12_deliver.py test_v12_verify.py test_mod_dragon_montage.py`, produced progress but **timed out without a final summary**; it is **not** recorded as passed. The complete full suite, Playwright browser rendering, Blender, paid external model endpoints, and Windows host behavior were not all verified here.

## Functional fixes from v1.3

- **Stock sources:** `python scripts/dragon.py tool stock sources|search|download|credits`. Tests use prerecorded NASA fixtures and license sidecars; source listing is NOT proof of a license for an arbitrary asset. Any real network calls require user-driven commands and provider terms.
- **Output audio:** `verify --duration` requires an audio track by default. A digitally silent audio track now fails measured volume/loudness; intentionally silent output may use `--silent-ok` (no track), not a fabricated audio receipt.
- **Mux padding:** a last-frame freeze exceeding 0.5 seconds returns failure unless explicitly acknowledged with `--allow-pad`.
- **Speech words:** local model cache only unless user explicitly selects `--download`; failures are reported without a Python traceback. Non-WAV/FLAC goes through temporary WAV.
- **Montage:** better Egyptian/Arabic negation parsing, literal owner-specified duration, don't infer 1:1 from the word فيديو, and preserve personal likeness/rights constraints.
- **Launcher:** never overwrites an owner repo, runs delivery gates on the updated embedded engine when local version is older, fingerprints code changes by contents, and supports old single-line stamp layout using separate local metadata.
- **Styles and lyrics:** v1.3 structural checks, paginated lyrics contact sheets, and source-aware references. They remain tools that require actual input files to prove delivery.

## Truth and consent boundaries

- Listed/referenced tools are **not** counted as executed. Earlier reports of 72/7,000+ abilities remain environment-specific history and were not adopted as fresh proof.
- No external stock was downloaded, no private video was included, no paid API (Kling / Suno / Higgsfield) was called, and no GitHub change was pushed.
- No font binaries, copyrighted book text or original attached videos are distributed in the archive.
- `setup` is a dry run unless an explicit `--yes` is given following owner approval. Even with `--yes`, winget system commands are only suggestions.
- A SHA-256 receipt is a local integrity check, **not** an independent signature or proof of creative quality.
