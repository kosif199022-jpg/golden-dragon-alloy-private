---
name: black-dragon
description: التنين الأسود (إعادة البناء النظيفة لـ kosif-tool) — باب واحد لكل مهارة وأداة وقدرة من مستودعات KOSIF كلها (kosif-tool وkosif-atlas و100-superskills وfastify-motion-bro والمهارات المثبتة والمستودعات المنزّلة) في كتالوج واحد قابل للبحث بالعربي والمصري والإنجليزي. Use first for any task when the user says «التنين الأسود»، «قدراتك»، «فيه أداة/مهارة لـ…»، or when you need to know which skill, runnable tool, power or superpower fits a request before working.
---

# Black Dragon — التنين الأسود (v1.0، إعادة البناء الكاملة)

Repo: `C:\Users\cinde\OneDrive\Desktop\التنين الأسود` (clean rebuild of kosif-tool; dev copy `C:\Users\cinde\kosif-own\black-dragon`; the original repos stay untouched).
Plan and phase gates: `REBUILD_PLAN.md`.

## Use
```
cd "C:\Users\cinde\OneDrive\Desktop\التنين الأسود"
python -m dragon find "الطلب بكلام المستخدم"      # best tools (with a runnable command), skills (with SKILL.md path), superpowers, powers
python -m dragon show <id|name>                    # one item in full
python -m dragon doctor                            # programs + Python modules this machine really has
python -m dragon stats                             # what the catalog holds
python -m dragon build                             # re-index after adding repos/skills (sources in data/sources.json)
python -m dragon verify out.mp4 --expect 1080x1920 --out evidence.json   # measure: duration, size, fps, LUFS, true peak, audio/video length mismatch
python -m dragon cut in.mp4 12.4 31.0 out.mp4      # frame-accurate smart cut (exact frame count)
python -m dragon beats song.wav --out beats.json   # tempo + beat grid for cuts
python -m dragon words song.wav --lang ar --out words.json   # sung/spoken lines with word timings
python -m dragon mix mix.json out.wav              # song section + voices, song ducks under voice, exact length, -14 LUFS
python -m dragon film spec.json --stills 1.5,7.5,12  # footage cinema: review stills first
python -m dragon film spec.json [--reuse] [--remux]  # full film -> MP4 -> verify (templates: engines/cinema/templates/*.json)
python -m dragon engines                           # every engine with its purpose
python -m dragon run <engine> <subcommand> ...     # run any engine (same as python -m engines.<engine> ...)
```

## Engines (each rewritten from the old kosif module, each with old-vs-new parity tests)
| Engine | Use it for | Main subcommands |
|---|---|---|
| `dragon_montage` | footage + task in the owner's words -> reasoned, reviewed edit (analyze, brief, taste, EDL, render, review) | `edit`, `plan`, `go`, `doctor`, `station <name>`, `tool <module>` |
| `talking_head` | one talking-to-camera recording -> vertical editorial reel (pause cuts, mastered voice, animated text) | `check prepare transcribe words cut master validate stills render sheet` |
| `cinema` (via `dragon film`) | real footage + song -> cinematic 9:16 tribute/celebration films | `dragon film spec.json` |
| `web_film` | motion films built as seek-driven web pages | `plan scaffold check render`, `world example|beats|check|build|review|render` |
| `editorial` | archival editorial look: grain, bloom, kinetic captions | `doctor example check build render` |
| `shadow_theatre` | silhouette / shadow-theatre films from a scene JSON | `doctor library analyze check stills render` |
| `voice_studio` | speech with word timings, voice clone/design, transcription to SRT/VTT | `doctor voices speak transcribe clone design verify` |
| `reel_hooks` | score a reel's first line, beat sheet for a script, Arabic humanizer | `hook beats clean` |
| `kling_director` | Kling short-film prompt pack + 3x3 storyboard + lint (never calls Kling) | `plan build check` |
| `matrices` | invent new visual systems from causal bricks, A/B/C tests, ledger | `experiment generate ideate laws bricks ledger …` |
| `blender` | Blender 5.2 headless (no MCP): run any bpy script/code, render .blend to PNG/MP4, demo scene. Blender/Photoshop/After Effects skill index: `skills/creative-studio/SKILL.md` | `doctor run code render demo` |
| `cards` | one interpreter for the method cards (old generated runners turned into data) | `list`, `run <id>`, `run --family X`, `stats` |

Shared core: `engines/media.py`, `engines/audio.py`, `engines/montage.py`, `engines/render/render.cjs`.
Engines: `engines/media.py`, `engines/audio.py`, `engines/montage.py`, `engines/render/render.cjs` (frames piped to ffmpeg,
full BT.709 tags), `engines/cinema` (spec → graded shots → canvas page → MP4). Gate proof: Mayar film 1 rebuilt = VMAF 99.46.
Tests: `python -m pytest -q tests` (full suite incl. parity tests for every engine).
Then open the chosen SKILL.md / run the tool's command. Report what was really executed separately from what was only consulted.

## What the catalog holds (built from data, no data inside code)
- 15k+ skills from kosif-atlas, 114 from 100-superskills, kosif-tool's skills, fastify-motion-bro, installed skills, downloaded repos.
- 212 runnable tools with commands, 5,917 powers with status (proven / ready / install / key / documented / idea), 485 superpowers.
- Arabic-aware search: diacritics, alef/ya/ta-marbuta forms, Arabic digits and the article «ال» are normalised; BM25 ranking with names weighted 4x.

## Specialised engines already proven (use them for the work itself)
- Footage → cinematic films: `black-dragon-cinema` skill (Mayar films pipeline: engine, build, karaoke text, ducking, delogo, verify).
- Montage folder rules: `C:\Users\cinde\OneDrive\Desktop\المونتاج\CLAUDE.md` (quality first, best tool per job, cinematic not educational).

## Rules
- Status `proven`/`ready` beats `documented`/`idea`; check `requires` with `doctor` before promising.
- Third-party skills (kosif-atlas mirror, dragon-repos) are reference: read scripts before running, respect each licence.
- No spending, publishing or pushing to GitHub without the user's explicit yes.
