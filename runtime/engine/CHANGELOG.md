## v1990.10.0 — 2026-11-12 — كل القدرات والاتصالات + دمج التلات نسخ
- **Merged:** base v1990.9.0 + 250 files from v1990.4-all-powers (11 bundled skills) + v10.18 `tool package` and the 20 library fonts that closed the v1990.9 gap (`tool library doctor`: base ok=false/4 problems → merged ok=true) + the live desktop app 2026.11.12-0814. Decisions and evidence: `references/MERGE_V199010.md`.
- **New `tool powers`** (`tools/powers/`): one registry of 50 powers in 9 layers (Claude Code, MCP, Higgsfield cloud, engines, RE, programs, skills, hubs, desktop app) with cost gates; `route` (ties go to the free road), `first` (the owner's first-reply skeleton), `map [--md]`, `show`, `doctor [--mcp]` (live `claude mcp list`; session-injected tools reported as 🔌 not ❌). `tool brain` gains section ⑪ from it.
- **Machine measured 2026-11-12** (`references/MACHINE_INVENTORY_20261112.md`): no NVIDIA GPU, 15 engines, retool 34/34, hub 205/212, MCP 5 connected + 2 need auth.
- SKILL.md now opens with the first-reply rule, the powers front door and a tool index; the long version blocks moved verbatim to `references/VERSION_NOTES.md` (line-level check: no line lost). `tools/package` header regex accepts a label like `candidate`.
- Tests: `test_v199010_powers.py` (8).

## v1990.10.0 — 2026-11-12 — كل القدرات والاتصالات + دمج النسخ التلاتة
- **Merge:** base v1990.9.0 (1,569 files) + 250 files from the parallel v1990.4-all-powers branch (11 bundled skills: teardown, blender-pro, github-atlas, higgsfield-free, higgsfield-cloud, saas-animation, black-dragon-cinema, reverse-engineer-anything, kosif-black-dragon-ultra, chroma-motion, creative-studio, kosif-downloads, montage-repos-hub) + 22 files from installed v10.18.0 (`tool package`, its test, and the 20 fonts that closed the library gap: `tool library doctor` ok:false with 4 problems → ok:true) + the live desktop app 2026.11.12-0814. v10.17.0 had no file the base lacked (SHA-256).
- **New `tool powers`** (tools/powers/powers.py + powers.json, 50 powers in 9 layers: Claude Code, MCP, cloud, engines, RE, programs, skills, hubs, desktop app): route / first / map [--md] / show / doctor [--mcp] [--save]. Cost gates in data and in ranking (free before ask before paid on ties); cloud alternative for laptop-only powers; session-injected tools (blackdragon, claude-in-chrome) reported as 🔌 session, not missing.
- **`tool brain`** briefing gains ⑪ connections from the same registry (in-process, never raises).
- **Desktop app copy:** live app features + the v1990.3.1 safety review restored (auto-approve off by default; `_approval` tools always ask). The running app on the laptop was not modified.
- **SKILL.md:** front door first (first-reply rule, router, routes table, measured laptop facts, `tool` index); ⛔ rules, start door and sections 0–12 kept verbatim; version blocks moved verbatim to references/VERSION_NOTES.md (45,316 → ~31k chars). §0 table corrected: no NVIDIA GPU on the laptop (measured).
- **`tool package`:** header regex accepts a label after the version (`v1990.9.0 candidate، …`).
- **References:** ALL_POWERS_V199010.md (generated), MACHINE_INVENTORY_20261112.md (measured by running every command), MERGE_V199010.md, LESSONS 2026-11-12.
- **Tests:** app/tests/test_v199010_powers.py. Results and pre-existing failures: TEST_REPORT_V199010.md.

## v1990.9.0 candidate — 2026-11-12 — كل اللي وصلنا له + مكتبة v10.17 رجعت
- **Merged the owner's v10.17.0 release** (github.com/kosif199022-jpg/black-dragon-skill): its 472 files that this line lacked were added (`skills/library/` 12 skill packs, `references/prompts/` 4 prompt files, `tools/library/library.py`, `references/LIBRARY_V1017.md`, one data file, one test). Its 19 other differing files are older copies of files already here and were not taken. `tool library` is registered again.
- **Known gap carried over from the release zip:** four packs have fewer files than their index counts (ai-motion-graphics 37/43, faceless-shorts 175/187, motion-reel 54/55, talking-head-reels 27/28), so `tool library doctor` reports not-ok and 3 tests in `test_v1017_library.py` fail. The missing 20 files were not in the zip.
- `references/SESSION_HARVEST_V19909.md`: styles ST06–ST14, the «قلده» method, verify/font/engine lessons, toolkits, measured machine speeds and Higgsfield GPU prices, open requests.
- Registry `app/data/own_tools.json`: +library, looks, mono, codekit, video12, palette, chroma (83 tools).
- LESSONS.md: dated entries for 11–12 Nov.

## v1990.8.0 candidate — 2026-11-11 — عدّة الفيديو بالكود (12 أداة) + ST12–ST14
- **`tool codekit`** (`tools/codekit/`): status / map / install / demo / vendor-gsap for Remotion, HyperFrames, Motion Canvas, Three.js, Manim, Rough.js, GSAP, anime.js, mo.js, WhisperX, auto-editor, FFmpeg. Vendored and stills-tested: Three.js (bundled to one classic script because pages load over file://), anime.js, mo.js, Rough.js (all MIT, licences included). GSAP is copied on demand, not vendored. Motion Canvas, Manim (needs pangocairo) and WhisperX (torch) are registered for install on the owner's PC; nothing about them was run here.
- New styles since 1990.7.0's first pack: ST12 pulse line, ST13 glowing line on black (two templates), ST14 chalk on a navy board.
- Lyric-overlay lesson: when the owner asks only for the words on someone's video, PIL (raqm) line cards + ffmpeg overlay work with any font; if the source fades to dark at the end, hold the last bright frame.
- **`tool video12`** and `resources/hf-blender-render/` merged from the owner's `v1990.5.0-video12-updated` build (the only parts of it newer than this tree); its other changed files were older copies of files already here and were not taken.
- **`tool chroma`**: the owner's `chroma-motion` skill (from `chroma-motion.rar`, 5 files, RAR5 read with libarchive; the stray `.pyc` was dropped) bundled unchanged under `tools/chroma_motion/`. Run here with `--subject off`: board + 9:16 motion video produced.
- **`tool palette`**: the owner's `nature-palette` skill bundled unchanged under `tools/nature_palette/` (colour card, CSS/JSON, dropper reel, reference contact sheet).
- Sweeper template rebuilt from measurements of the reference frame (sketch strokes, swept hair, hollow gold worker, paper rubble).
- Tests: `test_v19908_codekit.py` (13). `test_v19908_palette.py` (2).

## v1990.7.0 candidate — 2026-11-11 — ستايلات «قلده واحفظه» (ST07–ST11) + أداة mono
- Built on the owner's v1990.6.0 (PM01–PM15, `looks find/remind`) without dropping any of it.
- **`tool mono`** (`tools/mono_story/build.py`): ffmpeg-only film from animated shots or stills (push-in), subtitle looks `ink` (small white, 2 lines, 2nd fades on its word), `comic` (big yellow), `khawater` (big cream block per shot, per-line y), white doodle title card that draws on and boils, owner credit + watermark, exact frame count. Tested on two delivered films.
- **5 new style cards with pictures and film links:** ST07 painted khawater, ST08 ink-cartoon story, ST09 surreal minimal (Hossein Zare study), ST10 shadow play, ST11 ink on paper, ST12 pulse line (`tools/pulse_line/`), ST13 glowing line on black (`tools/glow_line/`), ST14 chalk on a navy board (`tools/chalk_board/`). Templates: `tools/surreal_minimal/`, `tools/shadow_play/`, `tools/ink_essay/`.
- Lessons: Lalezar/Cairo Black break in libass (boxes, tiny) → Changa/Almarai; shadow puppets drawn solid on an offscreen layer then composited once (no dark joints); disk needs ~3× the film for mono builds.
- Tests: `test_v19905_mono.py` (7) + ST11 checks; v1990.6 count test relaxed to >= 59.

## v1990.6.0 candidate — 2026-11-11 — خلاصة كل المحادثات + طرق الشغل بصورها + «فكّرني» قبل الاستخدام
- **Project harvest:** `references/PROJECT_HARVEST_V19906.md` distils the 82 threads of the project (24 Oct – 11 Nov): Mayar films, montage and video protocols, colour, export/audio, downloads, Higgsfield/Suno money rules, tools built, and the questions still waiting for the owner.
- **15 new looks (kind `method`, PM01–PM15)** with 360×640 pictures taken from the delivered films in the project folder: the seven Mayar films, one-world map film, shadow theatre, glass-remembers-light, debate montage, 8 s coffee kinetic reel, cinema reframe, code cartoon engine, storyboard + movement matrix. Each card has use, how-to and the film path. 59 looks in total.
- **`tool looks find "…"`** (Arabic-normalised search over id, name, aliases, use, notes; strips ال/بال/وال and filler words) and **`tool looks remind "…" --out DIR [--top 3]`** (writes a 540×960 picture card per match with the id, prints the question to send, and says to wait for a yes before using it). Aliases added to the main cards (الراجل والست، إسكندرية، قهوة، مطر…).
- SKILL.md: new top rule «send the picture first, then use». Version 1990.6.0. New test `test_v19906_project_looks.py`.

## v1990.5.0 candidate — 2026-11-11 — النماذج بصورها + خلاصة الجلسة + المؤثرات الذكية
- **Looks library (`tool looks list|show|sheet|prompt`):** 43 cards with 36 small pictures (360×640) under `tools/looks/`: the two couple references (Higgsfield media ids), 11 outfit+place looks, 3 singer looks, 7 facial expressions, 7 scenes, 5 working styles, 2 lyric layouts and 5 measured model prices. Each card has its prompt and the link of a delivered film. `sheet` draws one picture with the ids on it to send the owner; `prompt` prints ready `generate_image_batch` params with both references and the modesty rule.
- **Lyric film kit (`tool lyric JOB spec.json` + `tools/lyric_couple/render.sh`):** the page used for ~40 films (lyrics low or top, white Ruqaa + red line, still images or animated-clip frame sequences), Aref Ruqaa/Tajawal/Amiri fonts (OFL), `imgs.py` (download, brighten dark images, rembg depth map, sheet), and a render script that muxes the song, verifies, and can resume from second S (`--from S`) after a crash near the end.
- **Fix:** the page's WebGL setup is guarded (`const PRG=!G?null:`); without it a browser recycle crashed renders at 60%.
- **Smart-effects gate (`dragon.py fx rules|new|check`)** ported from v10.3.0 (it was not in the v10.17/v1990 line), with `references/EFFECTS_SMART.md` and 10 tests.
- **Session harvest:** `references/SESSION_HARVEST_V19905.md` (requests and how they are done, modesty, lyric verification, loudness, model prices measured with get_cost, downloads incl. TikTok photo posts and SoundCloud, rights, disk and render failures, delivery format); LESSONS.md gains four dated entries.
- New tests: `test_v19905_looks.py`, `test_v19905_effects.py`. Pre-existing suite failures are not claimed fixed (see TEST_REPORT_V19905.md).

## v1990.4.0 — Higgsfield Blender Render pilot (2026-11-11)
- Inspected user-supplied `hf-blender-render.rar` (7 files, RAR5); imported reviewed standalone Blender scene/sound and three scripts under `skills/hf-blender-render`.
- Added offline `tool hf-blender` (doctor/plan/pack/check-frames/policy/source), no remote execution.
- Hardened script packing against shell/filename injection and accidental overwrite, made Blender installation opt-in, and ensured delivery QC gates exit nonzero on failure.
- Added explicit node initialization for sample Blender scene; actual Blender version compatibility and Higgsfield XL behavior still require separate tests.
- Nine other newly uploaded ZIPs were older or byte-identical by content to previously scanned packages, so no obsolete tools were copied over the current baseline.
- No cloud commands run, no XL session created, no credit used; candidate, not deployed.

## v1990.3.1 candidate — 2026-11-11 — local safety hotfix on uploaded v1990.3
- Preserved the new desktop app, machine map, local browser bridge and v1990.2 tool integrations.
- Desktop app new-chat auto approval now defaults OFF; all tools marked as requiring approval always show the user approval prompt, even if an older session/settings enabled auto approval.
- Clarified UI label; no installer or Windows machine changes were performed here.
- Added focused static safeguards/tests and audit notes; do not imply the 51 pre-existing/all-suite failures are resolved.
- Machine map includes owner-specific Windows paths; do not publish the ZIP openly without redacting those paths first.

## v1990.2 (candidate, 2026-11-11)
- Imported user-provided Montage Arena skill as a **separate** CLI `tool montage-arena` (adversarial edit evaluation, evidence, A/B trials and decision log); preserved `tool arena`.
- Imported Windows Commands skill and added `tool windows-lint` for read-only parsing/quoting/encoding diagnostics; PowerShell helper remains manual.
- Deduplicated byte-identical github-atlas and windows-commands archives; added source provenance, focused tests and Linux-only test caveats.

## v1990.3 candidate — 2026-11-11 — باب التشغيل + خريطة الجهاز + قدرات التطبيق

- **باب التشغيل:** `python start.py` (أو `dragon.py start`) و`START_HERE.md`: أول خطوة لما الحزمة توصل Claude في أي محادثة. بيطبع الحزمة فيها إيه والدليل على المكان، وبيلزم Claude يسأل صاحب التنين: على اللابتوب ولا في محادثة سحابية؟
- **القرار قراره:** `tool machine mode laptop|cloud` بيطبع ترتيب الشغل والبدائل لكل مكان. لو قال «لابتوب» والدليل بيقول غير كده، الأمر بيطبع إزاي يتقاله بصراحة.
- **خريطة الجهاز (`tool machine map|find|path|env|doctor|scan`):** 108 بند اتفحصوا على لابتوب صاحب التنين، منهم 97 موجود بمساره الكامل (38 للهندسة العكسية)، و22 مكتبة بايثون، و34 مجلد PATH. `references/MACHINE_MAP.md` و`tools/machine/machine_map.json`.
- **الهندسة العكسية (`tool machine re`):** صندوق re-tools كله بمساراته وأمثلته + REA + omni + rea_digest.
- **قدرات تطبيق التنين:** كود التطبيق جوه الحزمة (`app/apps/dragon_desktop/`)، و`tool machine pc ACTION` للتحكم في الكمبيوتر كله (الخطير بـ `--yes` بعد موافقته)، و`tool machine app status|chats|read|send|ask` للكلام مع التطبيق المفتوح.
- **قدرات Claude في كل مكان:** `references/CLAUDE_AND_APP_POWERS_V19903.md` (أدوات Claude Code، خوادم MCP، مميزات التطبيق، وبديل كل واحدة في السحابة).
- **تصليح:** `app/dragon/__init__.py` كان `1990` والعنوان `1990.1`، فاختبار `test_content_version` كان بيفشل في v1990.2 نفسها. بقوا `1990.3` الاتنين.
- الأدوات المسجّلة 59. التفاصيل والقياسات: `TEST_REPORT_V19903.md`.

## v1990.1 candidate — 2026-11-11

Added a safe, offline, read-only GitHub Atlas search CLI over 1,000 user-supplied repository metadata records and 22 categories; `tool github-atlas find|show|top|cats|stats|lessons|doctor`. Atlas data in dragon-research.rar is byte-identical to github-atlas.zip; we bundled only the final atlas records and safety/methodology summaries, not the redundant 827 RAR research entries or downloaded READMEs. No external repository installs, network requests or code execution. See `SOURCE_GITHUB_ATLAS.json` and `references/GITHUB_ATLAS_V19901.md`. Existing v1990 features remain, no merge into main/GitHub.

## v1990 — 2026-11-11

Measured-free Higgsfield kit on top of v10.17.3 candidate. Every "measured" row was executed on 2026-11-11 with `balance` 347.88 before and after and no new `transactions` row (three rounds; each re-checked the one before). `tool hf free` (28-item catalog with evidence and limits), `tool hf trend live|list|find|show|commands` (TikTok commercial trending, Genjutsu trending presets, 56 public What-If references, 100 Katana preset slugs; `commands` prints one sandbox script that tears a reel down to cuts/energy/BPM/cutsync/keyframes/words), `tool hf blender rules|template` (3D Jutsu = hosted Blender 5.2; the template ran: scene + EEVEE still + .blend + GLB in 41 s; 994-asset catalog search measured; animation-to-MP4 render NOT confirmed; `/use-blender` local bridge documented), `tool hf higgsedit` (Arabic renders nothing without an Arabic `fontFamily`), `tool hf apps` (Match Cut + Tracelab, 28 actions, `create_typewriter` measured), `tool hf codefilm` (study of the Higgsfield blog «Claude Fable 5.2 Made a 3-Minute Cartoon in Code», `references/CODE_FILM_V1990.md`). reel-effects slash commands classified from their instructions: 8 no-credit, 7 with one paid matte step. New tools: `tool framecheck scan` (pops, blend cuts, first frames after cuts, freezes, numbered sheets), `tool critic brief|score|compare|ledger` (blind eight-axis scorecard; builder's score is SELF), `tool pack list|card|inspect|install` (13 uploaded skill packs as reviewed-by-hash cards; none carries a licence so no kit is copied into the skill; safe unpack outside it). `tool reel-dna extract` now reads real Katana output (`rr.analysis/1`; fixture from a real 60 s run: 38 shots, 1440 frames exact). `hf check`: non-generating `scene_builder_3d_*` free, `scene_builder_3d_generate_*` paid, `apps_invoke` still asks. Bug fix: `tool pack inspect/install` crashed (KeyError) on a non-archive file. Removed the old advice to fetch TikTok CDN audio with a forged Referer. Registry 69 → 75 cards. `references/MONTAGE_CRAFT_V1990.md` (eight working rules, style study from references, plan-before-build, v1990 gate order). Not measured: XL, `video_analysis_create`, `virality_predictor`, `media_import_url`, asset import, the other 27 Match Cut actions. Tests: `TEST_REPORT_V1990.md`.

## v10.17.2 candidate — 2026-11-11

KOSIF Reel DNA: new offline `tool reel-dna` command (doctor, katana-commands, extract, apply, render, compare, library). Imports known JSON cut/energy/beat/word structures without making up missing measurements; preserves exact frame edit decisions and source SHA-256 fingerprints. Local FFmpeg preview renders owner-supplied shots with strict total-frame verification and a simple `flash` implementation. Motion shake/pan/punch is metadata only; Arabic captions and visual matching require separate engines. Library supports explicit save/search/display of reusable recipes. Katana scripts not bundled, remote workflow schemas unverified, and external Sandbox cost unconfirmed. Tests: see `TEST_REPORT_V10172.md`.

## v10.17.1 candidate — 2026-11-11

Higgsfield report-driven integration (no remote service calls). Added an auditable 14-entry workflow catalog and read-only `tool hf workflows`, `tool hf workflow NAME`, `tool hf route TASK` commands. Conservatively annotated workflow prerequisites, external paid hand-offs, and duplicate drama/microdrama code. Preserved the 2026-11-10 XL measurements as historical and flagged that 2026-11-11 XL hardware/cost was not retested. Adjusted `media_import_url` to unknown cost instead of incorrectly listing it free. Existing generation approvals remain mandatory. New local tests: `app/tests/test_v10171_hf_workflows.py`.

## v10.17.0 — 2026-11-11

Merged the two thinking/analysis skills that the sessions produced but had not yet been folded into the dragon: **dragon-genius** and **omni-analyst**. Both are bundled under `skills/` (brain auto-discovers them via `skills/*/SKILL.md`) with SHA-256 source records (`SOURCE_DRAGON_GENIUS.json`, `SOURCE_OMNI_ANALYST.json`). `tool genius` (tools/genius/bridge.py — doctor/gate/qa) wraps `media_gate.py` (delivery gate that actually measures the video: duration, audio codec, yuv420p, even dims, faststart, black/freeze, LUFS, true peak; needs ffprobe/ffmpeg) and `transcript_qa.py` (CPS, line length, noise ratio, order; stdlib-only). `tool omni` (tools/omni/bridge.py — doctor/classify/probe/plan/report/hyp/bayes) wraps `omni.py`: classify any target from magic bytes, a safe fingerprint, a layered analysis plan that routes to re/rea-ultra, an ACH matrix and Bayesian updates — never runs the target or the network. Privacy: the three hard-coded owner paths in omni (`omni.py` RETOOL/DRAGON_DIR, `references/playbooks.md`, `evals/evals.json`) now resolve from the home folder, overridable via `OMNI_RETOOL`/`OMNI_DRAGON_DIR`/`DRAGON_HOME`; no owner identity remains in the shipped source. Registry 67 → 69 cards (catalog re-registered: `find` returns `genius` first for «عبقرية التنين»/«فائق الذكاء»/«بوابة التسليم», `omni` first for «المحلل الشامل»). `capabilities.py` entrypoints + NEEDS (genius→ffprobe; omni stdlib-only). Tests: test_v1017_merge (7). The two new skills are offline and do not render, download, or spend credit.

## v10.16.1 — 2026-11-10

Merged the last session's measured lessons into v10.16.0 and fixed two bugs. New `tool reftiming` (tools/onscreen/ref_timing.py): start/end of every on-screen lyric line measured from a reference video's text band, so «same style» lyric reels reuse the reference timing exactly (tested on «كلام» 8 lines and «كل حياتي» 13 lines). New `tools/hf_sandbox/prender.sh` (parallel frame render on Higgsfield XL; 732 HTML/SVG frames 37 s instead of ~4 min), written by `tool hf paste`. `qc.sh` now fails above 20 Mbps average (94 Mbps grain export → FAIL, 14.2 → PASS) with the re-encode command. Docs: speed table (Claude 586 s / HF 383 s / HF XL 147 s), `-crf 19 -maxrate 14M -bufsize 28M`, upload 400 → new URL one file at a time, chat images → media_upload_widget → CloudFront in sandbox. Bug fixes: `tool re` crashed everywhere because tools/re/re.py imported itself instead of the stdlib `re` (its folder is now dropped from sys.path first; test_v1014_re_brain 3 failures → pass); test_mod_cloud_browser imported aiohttp before importorskip, so a missing optional dependency stopped the whole suite at collection (now skips). Tests: test_v10161_merge (4). Full suite here: 634 passed, 34 failed — all environment (fonts excluded from the ZIP by design, httpx, librosa, yt-dlp not installed), none from this change.

## v10.16.0 — 2026-11-10

Skills from the recent sessions folded into the dragon, plus a links registry. `tool paint` (paint-studio bundled verbatim under skills/paint-studio with SHA-256 source record; bridge: doctor/verify, passthrough to paint.py, `ai` runs paint_ai.py on the SD-Turbo venv with HF offline, no-overwrite except same-file .dpaint, print/wallpaper need --yes, rembg ops refused when the model is not on disk so nothing downloads, UTF-8 stdout fix for Arabic paths). `tool grab` (video-grabber bundled verbatim with its 56 offline tests; bridge: doctor, offline `plan URL` ordering fetch → grab → user proxy file → ghost sniff; blocks --update/--tor/--free-proxies/newnym, proxies only from the user's file, credentials masked). `tool toon` (desktop-app toon engine ported to tools/toon/engine: 3d/ai3d/hayao/shinkai/paint; safe_path for Arabic model paths; ai3d re-runs on the venv python; setup is dry run; no overwrite). `tool links` (app/data/links.json: 1500 of 3139 unique links from 165 transcripts, 456 dropped for privacy — tokens, signatures, sessions, emails, localhost, signed CDN; route/find/list/stats/add, offline; references/LINKS.md with gaps). Registry 63 → 67 cards; catalog re-registered; the 4 new tools rank first for Arabic queries. Release ZIP built by a packager that excludes fonts and caches, refuses private strings, and verifies every manifest hash from inside the ZIP. Tests: test_v1016_paint (14), test_v1016_grab (18), test_v1016_toon (9), test_v1016_links (15).

## v10.15.0 — 2026-11-10

Merged v10.12.1 (the owner's two hard rules: no on-screen description, no Higgsfield credit without explicit yes to tool + price each time; 5 new lessons) into v10.14, and made the rules executable: `tool onscreen check` (his words / confirmed lyrics / credit only; FAIL on description, ASK without a source), `tool onscreen lint-web` (fill:'both', xfade without tpad), `tool hf check|ask` (free vs paid/unknown, exact approval text). brain acceptance and gates updated. Registry 63 cards (catalog re-registered: `find` now returns re/brain/onscreen/sp/atlas). Bug fix: face detection (YuNet) silently disappeared when the skill lived under a non-ASCII folder (OpenCV on Windows); the model is now opened from an ASCII copy (`cv_safe_path`), and the cards engine reads images with imdecode. SKILL.md 429 → 287 lines (v10.0–v10.12 notes moved verbatim to references/VERSION_NOTES.md). `probe-tools` 25 → 63/63 discoverable (an engine copy now finds the skill's tools/ via DRAGON_SKILL; the 7 external programs got program entrypoints). `onscreen check` also requires verbatim ORDER for 3+ word lines (attached و/ف/ب/ل stripped on both sides). OpenCV VideoCapture/VideoWriter tested from an Arabic folder: works, no change needed. New `tool fonts doctor|list|fetch [--from DIR] [--download] --yes`: the 19 OFL fonts the engines read (Aref Ruqaa, Cairo, Amiri, El Messiri, Tajawal, Reem Kufi, Instrument Serif, Anton, Lalezar, Scheherazade New, KOSIF Jumuah) are placed from local copies or google/fonts with SHA-256 + source + licence in fonts.lock.json; never overwrites; the ZIP stays font-free. Bug fix (same class as YuNet): ffmpeg `drawtext fontfile=` / `ass=` / `lut3d=` fail with exit -22 when the path has Arabic characters (measured: same font, Arabic path -22, ASCII path 0); new `engines.media.ascii_path()` copies such a file/folder once to an ASCII temp folder, used by talking_head (contact sheet font, ass + fontsdir, LUT) and montage (LUT). Portability: the last 8 hard-coded owner paths in runtime code (6 card libs, cinema MONTAGE, tools/extract_cards) now resolve from the home folder with env overrides (KOSIF_FONTS, DRAGON_MONTAGE_DIR, KOSIF_SKILLS_OLD). Tests out of date with the code: styles medal example checked with `--allow-missing` (template flag), chapters numerals only with `"numbers": true`, a verses spec also loads Scheherazade, cartoon `bash -n` skipped when bash is not on PATH. Test hygiene: symlink tests skip when Windows lacks the privilege, test_cli_plan_audit_calibrate forwards USERPROFILE/SYSTEMROOT, test_phase2 skips when the old dragon cannot load.

## v10.14.0 — 2026-11-10

Brain + reverse engineering. `tool brain` (one briefing from Dragon tools, bundled+installed skills, Superpowers, Atlas, LESSONS + learned lessons, ultra-mind stages and failure guards, expert-council lenses, acceptance criteria, gates; `learn`/`lessons`). `tool re` (byte-level identification, re-tools/REA chains, `investigate` with auto evidence, `audit` with code/doc/test contexts and reviewed hits, gated runtime tools). theme-factory bundled. v10.8.1 executables merged (chrome, sahab cloud browser, kosif downloads, psd, lyric-ass, BLACK_PEAK_Y, large-v3-turbo) and cinema extras rewritten as safe CLIs (song-map, sheets, skill-atlas: no owner paths, no overwrite, --help exits 0). Registry 62 cards. See references/BRAIN_RE_V1014.md.

## v10.13.0 — 2026-11-10

Superpowers becomes live: `tool sp` (where/find/doctor/tool/qc/run) calls the freshest local kosif-superpowers hub; checkout choice by git HEAD time (v10.0–v10.12 read the older ~/kosif-own clone). Second delivery gate `tool sp qc` (verify-video, 12 checks). Atlas: 254 media skills reviewed, 5 bundled in `skills/atlas-picks/` with source and licence, `tool atlas list|show|find`. Engine version unfrozen (was 10.10.0). 9 new tests. See references/SUPERPOWERS_ATLAS_V1013.md.

## v10.10.0 — 2026-11-10

Selective fusion of the Guardian v10.8 parallel branch into v10.9: phone playability diagnostic and copy-only repair, local job status and output discovery, resource preflight, keyboard layout, local 615-site catalog and repo fusion tools, cached Whisper fallback. Fix malformed SKILL frontmatter. See README_V1010.md and TEST_REPORT.md.

## v10.9.0 · 2026-11-09
- Integrated user-supplied Physics & Math calculator (18 local command families) into `tool physics`.
- Kept the exact original Python source and SKILL.md under `skills/physics-math/upstream/`.
- Patched executable copy: bounded AST math instead of raw eval, exclusive `--out` writes, non-finite input rejection.
- Added guard checks and SHA-256-based optional export receipts, verification, and source disclosure.
- Registered `physics-math` as the 38th local tool card and discoverable adapter, with Arabic/English numeric routing.
- 50 new tests passed; 223 selected backward-compatibility tests passed; 24 compatibility tests were deselected. No full-suite claim.


## 10.8.0 — 2026-11-09

- Integrate Visual Forge as separate offline engine with its original reference package.
- Plan+prompt+lint+SHA256 receipts, 21 actually-defined atmospheric presets, local FX.
- Preserve alpha channel, stream-copy compatible compressed audio, prevent source/output overwrites.
- Full test evidence in `TEST_REPORT.md` and `references/VISUAL_FORGE_V108.md`.

## 10.7.0 — REA Ultra (9 Nov 2026)

- Included REA Ultra source skill and references from user archive, preserving the upstream MIT notice.
- Added read-only offline `tool rea-ultra` with doctor, triage, plan, compare, verify, digest.
- Added the tool registry card and Arabic routing synonyms, plus a static entrypoint check.
- Added regression suite and documented limits: source paths on a different Windows PC are **not** current runtime availability.

## 10.6.0 — 2026-11-09
- Added `absolute-creativity` workflow from supplied ZIP: nine reference guides, idea collision deck, and portable Arabic shaping lab.
- Added `tool creativity` scaffold, deterministic seed generation, explicit 3-concept human rubric audit, style-bible and rights preflight, font capability checks and no-overwrite RTL title dispatch.
- Registered 35th local catalog entry, bumped engine version, preserved all 10.5 functions and tests.
- Excluded source `.font_cache.json` with another machine's paths. No binary fonts, AI credits or installs.

## 10.5.0 — Blender Pro source integration (2026-11-09)

- Bundled Blender Pro source and example recipes, excluding bytecode caches; added strict dry-run first bridge.
- Static AST operation discovery + JSON recipe validation without bpy, and content-preserving source verification.
- Added Blender Pro as separate indexed adapter (34 registered tools), preserving prior Blender engine and all v10.4 features.
- Kept Black Dragon Ultra integration as route/verify/learn reference; did not overwrite the established launcher.
- Out-of-scope synced/plugin snapshots, license-unclear binaries and user-local code paths are not installed.
- Blender runtime unavailable in test environment: no actual Blender render claim.

## 10.4.0 — 2026-11-09
- Added the 10-source-file Expert Council skill package, domain decks and learning-loop as user-provided source files.
- Added native `v10 council plan|audit|lessons` commands with 3/5/7 different-lens councils, meaningful debates, required red-team and dissent, optional real file SHA-256, and private correction ledger.
- Extended registration from 32 to 33 indexed tool entries. No claimed model weights training, agent calls, human expert consultation or actual cinematic evaluation.
- Added focused regression tests and release receipts.

## 10.3.0 — 2026-11-09
- Analyzed user-uploaded `ultra-mind.rar` (8 source files). Kept its SKILL, references, scaffold and manual eval cases as supplied, including evaluation caveats.
- Added `v10 ultra plan` (L0–L3 / eight task domains), `v10 ultra audit` (competing hypotheses, falsifiers, local SHA-256 receipts, negative cases) and `v10 ultra calibrate` (real binary forecast Brier score and calibration bins).
- Integrated Ultra Mind into the bundled SQLite tool catalog, kept the 10.2 media hunter/video capabilities intact.
- No automatic web access, remote upload, external process invocation, credit spending, model retraining or GitHub push.

## 10.2.0 — 2026-11-09
- Integrated the uploaded Media Hunter SKILL.md as a **referenced source**, not as code; no proprietary `mh.py` or 615-site index was supplied.
- Added `tool hunter` CLI supporting offline `sites`, `links`, `keys`, `build`, and provider-backed network `hunt`, `search`, and explicitly-requested numbered `get` using v10.1 stock clients.
- Curated 31 unique sources (including discovery-only links) and recorded source capabilities and licensing limitations honestly; API keys never printed; unknown or restricted rights blocked by default.
- Registered tool in the local SQLite catalog and added independent offline tests; no media, installation, credit spending or GitHub changes performed.

## 10.1.0 — 2026-11-09
- Merged selected v1.3 features missing from v10.0: stock search/download/attribution, montage constraint fixes, audio silence/stream gate, mux padding veto, offline-only speech model by default, richer storyboards, and safer old-repo routing.
- Added upstream regression tests, provenance and stock mock fixtures.
- Kept v10 cognitive/7-stage/catalog/Kling features and opt-in package setup.
- Font binaries, original user media and proprietary book contents excluded.

# CHANGELOG — Black Dragon

## v10.0.0 — 2026-11-09

- Migrated to major version 10 on top of the bundled v1.3.0 core, preserving existing video/audio/visual modules and index.
- Added 7 working v10 CLI capabilities and registered them in own_tools.json/SQLite (30 total adapters, static probe only).
- Implemented a 7-stage job gate, SHA-256-fingerprinted stage/artifact records, explicit preview approval before `gate render --execute`, and real FFmpeg output receipts.
- Added real video technical scan with frame-count / black-frame QA and seven-frame approximate CIELAB76 color compliance measurement (separate from creative QA).
- Added source-aware, original cognitive decision checks based on the user's Kahneman book without including book text.
- Added Kling text-only block director with built-in prompt lint, continuity plan and 3x3 board briefs; no credits spent.
- Added metadata inspection and case study from six provided Aghnam Alwadi MP4 assets without redistributing footage.
- Added link index from 115 main / 12 extra user-provided references, rights marked unknown.
- Added comprehensive reference documentation, samples and tests. No GitHub push, no merge, no external platform generation.

## Previous version notes (historical; environment and counts may differ)

# سجل التغييرات

## v1.2 (2026-11-09)
**قدرات جديدة**
- محرك **`image_studio`**: عنوان عربي متشكّل صح، ريفريم 9:16 بخلفية مغبشة، 7 لوكات تلوين، غلاف ريل/يوتيوب، تكبير 4× بـ Upscayl، شيل خلفية بـ rembg، شيت فريمات للمراجعة. (11 اختبار)
- محرك **`blender`** اتنقل من الريبو المحلي للمهارة: Blender 5.x في الخلفية من غير MCP. (3 اختبارات)
- أداة **`tool fetch`**: تحميل بأعلى جودة (yt-dlp / aria2c) وتسجيل كل ملف في `sources.txt` بالترخيص.
- دليل **creative-studio** (Blender وPhotoshop وAfter Effects) بقى جوه المهارة في `references/skills/creative-studio.md`.

**بحث أذكى**
- المرادفات المصرية بقت 124 كلمة بدل 36 (دوشة، كابشن، تفريغ، تكبير، غلاف، مزيكا، كلر، تيك توك…)، والراوتر بيستخدمها.
- محركات التنين وأدواته والبرامج المحلية (23 عنصر) بقت جوه الكتالوج بعلامة `proven`، فبتطلع الأول. `dragon build --own` يعيد فهرستها لوحدها.

**تصليحات**
- `where` كان بيقول إن tesseract مش موجود وهو متثبت (كان بيدوّر في PATH بس). دلوقتي بيستخدم نفس فحص `doctor`.
- `doctor` بقى بيفحص 23 برنامج بدل 10 (upscayl-bin، rembg، inkscape، gimp، melt، mkvmerge، deep-filter، whisperx، demucs، pandoc، 7z…).
- بناء الكتالوج التجريبي (fixtures) فضل نضيف من غير أدوات التنين.

**الاختبارات:** راجع آخر سطر في `app/REBUILD_PLAN.md`.

## v1.1 (2026-11-08)
11 محرك، الحلبة، استوديو 3D، الكرتون، الستيك مان، صور مجانية، والبروتوكول الإجباري للفيديو.


## v1.3.0 — 2026-11-09 (merged local release)
- Merged the complementary v1.2 archives, keeping media delivery QA while restoring image_studio/blender/fetch and Egyptian synonyms.
- Added inspection-only `probe-tools`, local `ecosystem`, non-executing smart/full `plan`, and read-only USIP Superpowers bridge.
- Changed `setup` to safe dry-run default; an explicit `--yes` is required for installation.
- Content-sensitive engine bundle stamp; no code or secrets pushed to GitHub.
- Added regression tests and safe offline `build --own`.
- Fonts not redistributed (see references/FONTS_REQUIRED.md).
