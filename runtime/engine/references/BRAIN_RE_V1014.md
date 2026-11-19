# v10.14.0 — Brain + reverse engineering inside the Dragon (2026-11-10)

## Sources used (the owner's `~/.claude/skills`)
| Skill | Use in v10.14 | Why |
|---|---|---|
| ultra-mind | 7-stage loop + 12 model failure modes + confidence language → `tools/brain/protocol.json` | bundled copy identical to installed (SHA-256 of SKILL.md equal) |
| expert-council | lenses for editing, cinematography, directing, literary, audio, design → protocol.json | identical to installed |
| rea-ultra / reverse-engineer-anything | chains per file type, evidence/inference/unknown discipline → `tools/re` | reverse-engineer-anything has no LICENSE in its folder: routed (brain lists it), not copied |
| re-tools (`~/re-tools/retool.py`, 34 tools) | `tool re triage/run/investigate`, YARA-X second opinion | static vs runtime split taken from the box's own categories |
| theme-factory | copied to `skills/theme-factory` (Apache-2.0, without the 121 KB showcase PDF) | small, redistributable, titles/cards |
| black-dragon v10.8.1 (installed, separate branch) | features missing from this line merged (see "v10.8.1 merge") | 119 files existed only there |
| absolute-creativity, physics-math, visual-forge, blender-pro, media-hunter | kept the bundled copies | bundled ones are newer/safer (portable paths, no eval, alpha kept) |
| video-grabber, saas-animation, kosif-downloads, montage-repos-hub, creative-studio | route-only (brain finds them on the PC) | no licence file, policy-sensitive proxies, or index-only |
| canvas-design, algorithmic-art, webapp-testing, mcp-builder, frontend-design, web-artifacts-builder, doc-coauthoring | route-only / skip | too big (fonts) or off-topic for montage |

## `tool brain`
- Domains: video, audio, typography, image, motion, 3d, re, sources, creative, physics (Arabic-normalised tokens: alef forms, ة/ه, ى/ي, «ال»).
- Ranks Dragon TOOLS (parsed from `scripts/dragon.py`), bundled + installed SKILL.md frontmatter, LESSONS.md bullets, learned lessons (`~/.black-dragon/lessons.jsonl`, `DRAGON_STATE` overrides).
- Live: `tool sp find` (Superpowers) and `tool atlas find` (Arabic requests are searched in Atlas by the domains' English words: the index is English). `--no-live` skips both.
- Adds per domain: failure-mode guards, council lenses, acceptance criteria (verify + sp qc for video, contrast ≥4.5:1 for text, evidence sections for RE), approval gates.
- Never executes the plan (`executed: false`).

## `tool re`
- Identification is from bytes: PE header (CLR data directory → .NET; `UPX*` sections; PyInstaller cookie/_MEIPASS; Electron/NSIS/Inno strings), ELF, Mach-O, ZIP members (APK / Office+VBA / SKILL.md), OLE, WASM, pcap/pcapng, SQLite, GGUF.
- Chains follow the re-tools box and rea-ultra: identify → unpack (on a copy) → language tool → REA → runtime (gated).
- `investigate` runs only triage, DIE and audit automatically; everything else is listed as pending with its exact command.
- `audit` contexts: code (.py/.js/.sh/.ps1/...), test/fixture, doc/data. Verdict REVIEW only for unreviewed high hits in code.

## Evidence from this session
| Check | Result |
|---|---|
| `re audit` on black-dragon-v10.12.0.zip (v10.13 rules) | 12 "high in code" — data cards and docs counted as code |
| same, v10.14 contexts + reviewed hits | CLEAN_STATIC · 0 in running code · 3 reviewed (plugin-scanner fixture in fam_skills_part7.py, read by eye) · 9 in docs/data |
| `re investigate python.exe` | triage + DIE ran: PE64, MSVC 19.43, Python 3.12, Authenticode; 13 steps pending |
| `brain` on «ريل تكريم 30 ثانية على أغنية وطنية…» | video+audio; 6 LESSONS hits; Superpowers suno-bridge/montage-pro/song-preview; Atlas joined-audio-transcript-drift, video-transcript, social-video-hooks |
| tests | test_v1014_re_brain.py 14 passed; test_v1013 9 passed |

## v10.8.1 merge (executables that were missing from this line)
| Added | Command | Notes |
|---|---|---|
| `app/engines/chrome` | `dragon.py chrome …` | control the owner's Chrome over CDP |
| `app/engines/cloud_browser` | `dragon.py sahab …` | «سحاب» cloud browser (server + static UI) |
| `app/engines/kosif` | `dragon.py kosif …` | multi-connection resumable downloads with SHA-256 |
| `tools/psd_studio/psd.py` | `tool psd inspect|export|build|cutout|doctor` | repos folder now `DRAGON_REPOS` / `~/dragon-repos` (was a fixed owner path) |
| `tools/lyric_remake/*` | `tool lyric-ass` | `--help` exits 0; lyric_ass, measure and the example refuse to overwrite without `--force` |
| `tools/cinema_extras/song_map.py` | `tool song-map SONG…` | rewritten as a CLI: `--window`, `--out-dir`, `--json`; keeps an existing .beats.json unless `--force` |
| `tools/cinema_extras/sheets.py` | `tool sheets CLIP…` | rewritten: no owner paths (BDC_REFS/BDC_WORK optional), `--n/--cols/--width`, no overwrite |
| `tools/cinema_extras/skill_atlas.py` | `tool skill-atlas [--write|--out]` | was rebuilding the bundled atlas on any argument (even `--help`); now summary by default, `~` paths |
| `references/SKILL_ATLAS.md` | — | rebuilt on this PC: 538 skills, home folder shown as `~` |
| `app/engines/qa.py`, `audio.py` | — | hand-merged: BLACK_PEAK_Y (a small title on black is not a black frame), `large-v3-turbo` |
| registry | `probe-tools` | 62 cards: 5 merged + 4 v10.8.1 ids mapped to their tools here + song-map, contact-sheets, skill-atlas + sp/atlas/re/brain |

Not copied on purpose: video-grabber (proxy rotation, no licence), apk_extractor (prebuilt APK), kosif_app, excel_lab.
Known, older than this release: `test_v12_styles` needs the font files listed in FONTS_REQUIRED.md (never bundled);
`test_v12_docs::test_skill_md_shape` limit 320 lines (SKILL.md was 392 before v10.13).

## v10.15 — v10.12.1 merged and its rules made executable
| Input | Evidence |
|---|---|
| black-dragon-v10.12.1.zip vs v10.12.0 | 3 files differ: SKILL.md (2 ⛔ rules + title), LESSONS.md (+2 rules, +5 table rows), SHA256SUMS.txt. No code change. `re audit`: CLEAN_STATIC |
| `tool onscreen check` on a 4-line .ass + lyrics | ✓ lyric · ✗ «وقهوتها الدافية» (description) · © credit · ✓ lyric with full tashkeel and «و» prefix → FAIL exit 1; without a source → ASK exit 3 with the question |
| `tool onscreen lint-web` | catches `fill:'both'` (line) and `xfade` without `tpad` (file) |
| `tool hf check` | sandbox_exec → free exit 0; generate_video → paid exit 3; unknown names → treated as paid |
| Full suite vs the untouched v10.12.0 tree (same machine) | v10.12.0 fails 27 of the same tests (fonts not bundled, parity with old repos, Windows symlinks); the only extra failure here, `test_analyze_parity`, was a real bug: YuNet reported missing from an Arabic folder. Fixed (`cv_safe_path`), `missing: []`, test passes |
| `probe-tools` | before: 25 discoverable / 37 unverified (the launcher's engine copy looked for tools/ next to itself); after: 63/63 discoverable |
| OpenCV video I/O in «التنين الأسود» folder | VideoWriter opened, 10 frames written and read back: no fix needed (only file-path model/imread calls were affected) |
| `onscreen check` order | «يا حبيبي شتا الرياض» against «شتا الرياض يا حبيبي» → ORDER (not verbatim) |
| SKILL.md | 429 → 287 lines: v10.0–v10.12 sections moved verbatim to `VERSION_NOTES.md`, one-line summary per version kept; the old 320-line test passes again |

## Limits
- Audit is a static pattern scan: a hit proves the text exists, not that it runs; CLEAN_STATIC is not a guarantee.
- `rea doctor` on the PC reports healthy=false for optional providers (Hopper, IDA registration, some agent registrations); Ghidra and JADX pass.
- The x64dbg registry entry in re-tools points at `x96dbg.exe` (launcher); verify before use.
