# v10.13.0 — Superpowers live bridge + Atlas picks (2026-11-10)

## What was found (evidence)
| Item | Evidence |
|---|---|
| Two kosif-tool checkouts on the owner's PC | `~/kosif-tool` last HEAD move 1794264812 (merge of black-dragon-rea-repo-fusion, 2026-11-10); `~/kosif-own/kosif-tool` 1794134563 (clone, 2026-11-08) |
| v10.0–v10.12 used the older one | `superpowers.candidates()`, `capabilities.ecosystem()`, `data/sources.json`, `scripts/dragon.py OLD_REPOS` all named `~/kosif-own/kosif-tool` only |
| File times mislead | the older clone has newer `manifest.json` mtime (11-08 13:42 vs 01:55); first live run picked it — fixed by reading `.git/logs/HEAD` |
| Engine version frozen | `app/dragon/__init__.py` said 10.10.0 while SKILL.md said 10.12.0; `test_v1010_guardian.test_content_version` hard-coded 10.10.0 |
| Superpowers hub | 212 tools, 5,917 powers, 12 areas; `find/doctor/tool/list --json`; `run` refuses consent tools with exit 3 unless `--yes`; doctor: 205/212 ready (6 need Chromium, 1 needs TypeScript) |
| `tool sp qc` on a 3 s 1080×1920 test film | 11/12 PASS, FAIL loudness −21.8 LUFS (quiet sine tone) → exit 1, report JSON written |

## What changed
- `app/dragon/superpowers.py`: all candidates (`~/kosif-tool`, `~/kosif-own/kosif-tool`, `~/.claude/skills`), `survey()`, `pick()` (explicit env > freshest git HEAD > file mtime), `repo_of()`, absolute commands with the running Python. Still never executes anything; v10.0 `command_template` kept.
- `app/dragon/capabilities.py` `ecosystem()`: one row per checkout + `chosen`, `superpowers_root`.
- `app/dragon/catalog.py` `load_sources()`: rewrites `~/kosif-own/kosif-tool…` to the chosen checkout (no-op when it is already the freshest).
- `tools/superpowers/sp.py` (`tool sp`): where / find / doctor / tool / qc / run.
- `tools/atlas/atlas.py` (`tool atlas`): list / show / find; `skills/atlas-picks/` (5 skills, SOURCE.md + licence).
- Version 10.13.0 in `__init__.py`; version test follows the SKILL.md title.
- Tests: `app/tests/test_v1013_superpowers_atlas.py` (9, fake checkouts and a fake hub only).

## Atlas review
Index: 14,708 skills (5,253 READ_ONLY_OK, 9,455 REVIEW_BEFORE_INSTALL). Filter: media keywords + READ_ONLY_OK + no risk flags + complete + permissive licence → 254 unique. Four reviewers scored relevance/concreteness/novelty (0–10 each, ≥18 kept), then the shortlist and near-misses were read again by the lead.

| Pick | Licence / source | Why |
|---|---|---|
| joined-audio-transcript-drift | MIT · voitta-ai/skillz @feb9ceb | measured drift (+9.1 s over 181 joins); dua/Quran/TTS concat |
| legibility-contrast-and-spacing | MIT · HDeibler/universal-design-principles @9cc4f3e | contrast ratios, tracking, leading for text on footage |
| social-video-hooks | MIT · adamperlis/adam-plugins @e41984f | hook types + timed beat sheet + sound-off check |
| awwwards-motion | MIT · adamperlis/adam-plugins @e41984f | spring constants, GLSL, particles for web/canvas films |
| ffmpeg | MIT · alivirgo/major-ai-skills @ba3a572 | NVENC flags, filter_complex, ffprobe VFR/PTS diagnosis |

Rejected on purpose: ElevenLabs workflows (paid API: spending needs approval), YouTube caption skills (paid transcriptapi.com), creator-* templates (placeholder `[Channel]` prompts), generic web/UI and vendor-ops skills.

## Limits (honest)
- Atlas picks are third-party reference text, not tested methods; nothing of theirs is executed.
- `tool sp` depends on a local checkout; on claude.ai cloud it exits 4 with the searched paths.
- The full legacy test suite was not re-run in this session (the review environment blocked running the archive's code); only the new test file and the files written here were executed.
