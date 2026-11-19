---
name: kosif-black-dragon-ultra
description: "التنين الأسود الفائق — one front door to all 21 KOSIF modules: video montage, motion/web films, voice-over and subtitles, reels and hooks, Kling prompts, shadow theatre, new visual styles, photo editing (RAW, PSD, background removal), living 3D websites, site snapshots, Instagram research, documents, data, code workflows, reverse engineering with REA, and the Superpowers catalog of 5,800+ powers. Thinks with Dragon Mind, plans with Black Dragon from 7,400+ sources, and checks every needed tool before work. Use for any creative, media, web, data or engineering task, or when the user says التنين، التنين الأسود، عقل التنين، قدراتك، سوبر باور، فكّر، خطّط، مونتاج، موشن، ريلز، صورة، صوت، موقع."
---

# التنين الأسود الفائق — Black Dragon Ultra

One skill that holds the whole KOSIF system. The 21 modules stay intact inside the repo. This skill is their front door: it routes the task to the right module, thinks with Dragon Mind, plans with Black Dragon, and runs the unified tool protocol.

Engine: `python scripts/dragon.py` (relative to this skill). It finds the repo through `KOSIF_ROOT`, then `dragon.json`, then its own location. It runs every module from the repo root, so their original paths keep working.

## 0. Tool protocol (first time in a session)

    python scripts/dragon.py doctor            # every tier: system, core, node, heavy, agents
    python scripts/dragon.py needs <module>    # exactly what one module imports or calls

- **system** and **core** must show READY before media work. Install them with `python scripts/dragon.py install system` and `python scripts/dragon.py install core`.
- Install **node** only for web-film, living-site or Remotion work.
- Install **heavy** (several GB) only when the chosen module needs it. Ask the user first.
- **agents** are paid or keyed SDKs. Never install or call them without the user's approval (`install agents --yes`).
- Never report a step as done when its tool is missing. Details are in `TOOLS.md`.

## 1. The dragon cycle

| Task size | What to run |
|---|---|
| Small, clearly one module | `route "<task>"`, open that module's `SKILL.md`, follow it |
| Substantial or creative | `cycle "<task>"`: route + Superpowers find + Dragon Mind think + Black Dragon plan, written to `out/dragon/<date-slug>/DRAGON.md` |
| Only thinking | `think "<task>"` |
| Only a method plan | `plan "<task>"` (first run needs `--build-index`, about 5 min) |
| "What can you do for X?" | `find "<task>"` |

After the cycle:
1. Read `DRAGON.md` and the chosen modules' `SKILL.md` files.
2. Run only the commands the task needs.
3. Check the real outputs: open images, probe videos, play or measure audio.
4. Report paths, sizes and durations.

A plan is not an execution receipt.

## 1b. Run, verify, learn

    python scripts/dragon.py exec <module> <script> [args]   # e.g. exec kosif-web-film scripts/web_film.py check job/film.plan.json
    python scripts/dragon.py verify out.mp4 cover.png --out <job>/evidence.json
    python scripts/dragon.py learn "<task>" --modules video-montage kosif-voice-studio --result passed --evidence <job>/evidence.json

- **exec**
  - Use it instead of the `python3 .claude/skills/...` lines in module docs.
  - It runs from the repo root with the right Python or Node, the tool folders on PATH, and `KOSIF_ROOT` set.
  - It refuses scripts outside the module.
- **verify**
  - Measures each output:
    - Video and audio: duration, streams, resolution, codec, loudness (LUFS).
    - Images: size.
    - JSON: validity.
    - Text: length.
  - Exits with code 1 if any file is missing, empty or unreadable.
  - Quote these numbers in the final report.
- **learn**
  - After the user accepts (`passed`) or rejects (`failed`) a result, record it.
  - Later, `route` and `cycle` boost modules that passed on similar tasks and demote ones that failed (the `learned` column).
  - The ledger is `<repo>/out/dragon/ledger.jsonl`.
- **Engine tests:** `python -m unittest discover -s tests -v`. They cover:
  - Routing for 9 typical tasks.
  - Arabic normalisation.
  - The learning boost.
  - `verify` on a real image and a real video.
  - The `exec` sandbox.

## 2. Modules (all under `<repo>/.claude/skills/`)

| Area | Module | Use it for |
|---|---|---|
| Brain | `kosif-dragon-mind` | 26 faculties, readiness tiers, six-stage thinking before big jobs |
| Brain | `kosif-black-dragon` | source-linked fusion of the full catalog; `plan` gives merged methods with source IDs |
| Brain | `kosif-superpowers` | capability map, `hub.py find`, 5,800+ powers, typography atlas, FusionForge |
| Video | `video-montage` | FFmpeg cut, merge, transitions, Arabic titles, subtitles, music ducking, 9:16 |
| Video | `kosif-web-film` | motion-design films built as web pages and rendered to video |
| Video | `editorial-film-edit` | archival editorial edits, kinetic text, grain, bloom, presenter splits |
| Video | `kosif-shadow-theatre` | silhouette and shadow-theatre motion films |
| Video | `kosif-kling-director` | Kling short-film prompt packs, 3×3 storyboards, lint before spending credits |
| Style | `kosif-infinite-matrices` | invent new visual systems from causal bricks, A/B/C tests, research ledger |
| Voice | `kosif-voice-studio` | TTS with word timings, voice clone or design, transcription to SRT/VTT |
| Writing | `kosif-reel-hooks` | reel scripts, three scored hooks, beat sheet, Arabic humanizer |
| Image | `image-studio` | crop, grade, curves, HSL, split tone, RAW, PSD layers, inpaint, background removal, Arabic text |
| Web | `living-site` | living websites: Spline 3D, Higgsfield scroll film, code motion graphics |
| Web | `kosif-site-snapshot` | offline copy of the user's own site and its measured design system |
| Research | `kosif-instagram-discovery` | public reel references by topic |
| Research | `kosif-instagram-video-research` | ranked public reel library with evidence labels |
| Files | `kosif-upload-link` | big-file upload link and pulling what the user uploaded |
| Library | `kosif-skills-atlas` | 335 curated skills: languages, DevOps, MCP, agents, product, research |
| Library | `kosif-superskills-library` | 114 super skills: copy, code, data, Excel, design, business |
| Engineering | `obra-superpowers` | brainstorm, write and execute plans, TDD, debugging, code review |
| Engineering | `reverse-engineer-anything` | REA reverse engineering of binaries, apps and web pages, AgentEnv bundles |

`python scripts/dragon.py modules` prints the live list. Any new module dropped into `.claude/skills/` appears there automatically.

## 3. Rules that apply across all modules

- **Rights:**
  - Original work only. Never clone a specific existing game, brand or site design.
  - Never analyse or rebuild pirated software.
  - Use only fonts and media the user has rights to.
- **Evidence:**
  - Keep source linking, extraction, implementation and real execution as separate claims.
  - Mark a result done only when its output file has been checked.
- **Files:**
  - Never overwrite the user's originals.
  - Write job outputs under `<repo>/out/`.
  - Name files clearly. Arabic names are fine; quote paths.
- **Windows:** use `python`, not `python3`, unless `python3` is a real interpreter. FFmpeg comes from winget `Gyan.FFmpeg`.
- **Arabic:**
  - Never letter-space Arabic.
  - Shape Arabic text before rendering it in images or video.
