# Machine inventory — جرد قدرات الجهاز (Black Dragon / التنين الأسود)

Generated / وقت القياس: 2026-11-12 09:58:14 · machine: DESKTOP-EUGN3DS · python: `C:\Users\cinde\AppData\Local\Programs\Python\Python312\python.exe`

Status legend / المفتاح: **VERIFIED** = ran OK (اشتغل فعلاً) · **FAILED** = ran with an error (اشتغل بخطأ، السطر مذكور) · **NOT FOUND** = not installed (مش موجود).
Every row was measured by running the command on this PC (اتقاس بالتشغيل مش بالتخمين). Python: always `python -X utf8`; set `PYTHONIOENCODING=utf-8` for Arabic output.

## Key facts — أهم الحقائق (measured 2026-11-12)

| # | Fact (EN) | الحقيقة (عربي) |
|---|---|---|
| 1 | **No NVIDIA GPU / no CUDA.** Intel Core 5 120U (10 cores / 12 threads), 15.7 GB RAM, Intel Graphics only; `torch 2.8.0+cpu`, `cuda_available=False`. Every AI model (toon, whisper, demucs, rembg) runs on CPU. | **مفيش كارت NVIDIA ولا CUDA.** معالج Intel Core 5 120U (10 أنوية / 12 خيط)، رام 15.7 جيجا، كارت Intel بس. كل الموديلات بتشتغل على المعالج. |
| 2 | Disk: C: 204 GB free of 471 GB; D: only 0.9 GB free. | الديسك: C فيه 204 جيجا فاضية؛ D فيه 0.9 جيجا بس. |
| 3 | Dragon CLI (Black Dragon 0.1.0): **15 engines**, 14 answer `--help`; `cards` has its own parser → use `run cards stats` (5,361 cards, 2,901 runnable). | التنين: **15 محرك**، 14 بيردّوا على `--help`؛ `cards` بيتشغّل بـ `run cards stats` (5,361 كارت). |
| 4 | `toon` styles: `3d` (DCT-Net), `hayao`, `shinkai`, `paint`, `ai3d` (SD-Turbo, slower). `image --style --max-side`; `video --style --fps --seconds --max-side --no-deflicker`; `setup` downloads models (not run). | ستايلات الكرتون: 3d، hayao، shinkai، paint، ai3d. |
| 5 | RE: `retool` **34/34 installed**; `rea` CLI 6.8.0 works; `rea doctor` = healthy:false (Hopper/IDA/kuna not installed + stale registrations for codex/gemini/antigravity + skill-identity drift); Ghidra 12.1.4 and JADX healthy. | الهندسة العكسية: 34 من 34 أداة متثبتة؛ rea شغال، و`rea doctor` بيقول مش سليم بسبب محركات اختيارية وتسجيلات قديمة بس. |
| 6 | KOSIF hub: **212 tools / 12 areas, 205 ready**; 7 need `chromium` (6) or `typescript` (1). SKILL.md states 5,917 powers (stated, not re-counted). | مركز KOSIF: 212 أداة، 205 جاهزة؛ 7 محتاجين chromium أو typescript. |
| 7 | MCP (`claude mcp list`): **7 servers — 5 connected** (Claude Docs, suno, Higgsfield, rea, black-dragon), **2 need auth** (Remote Desktop Commander, graphify). The session also has `blackdragon` (browser/computer/system) and `claude-in-chrome` (20 tools), which are not in `claude mcp list`. | MCP: 7 سيرفرات، 5 متوصلين و2 محتاجين تسجيل دخول. |
| 8 | PATH: 32 of 35 checks verified. **Not found:** `faster-whisper` CLI (the Python package exists), `rg` (use Claude's Grep tool), `nvidia-smi` (no NVIDIA). | البرامج: 32 من 35 شغالين. مش موجود: faster-whisper كأمر، rg، nvidia-smi. |
| 9 | Call `npm` as `npm.cmd` from Python/PowerShell (the extension-less `npm` shim gives WinError 193). `upscayl-bin` has no `--version`; `-h` prints usage with a non-zero exit code. | استخدم `npm.cmd` من بايثون. upscayl-bin مالوش `--version`. |
| 10 | Python 3.12.10: all **16/16** packages import. **moviepy is the legacy 0.2.3.1** → use `from moviepy.editor import ...` (the v2 `from moviepy import VideoFileClip` fails). Cold `mediapipe` import took ~35 s. | بايثون: الـ16 مكتبة شغالين. **moviepy نسخة قديمة 0.2.3.1** → استخدم `moviepy.editor`. |
| 11 | Skills: **39** folders with SKILL.md (6,622 files) + 5 without (bd_src, kosif-claude-app, kosif-tool-main, output, synced). Four Black Dragon copies: black-dragon v10.18.0, -2 v10.16.1, -3 v1990, -4 v1990.3 candidate. | المهارات: 39 مهارة؛ 4 نسخ من التنين الأسود بإصدارات مختلفة. |
| 12 | `claude mcp list` shows Arabic paths reversed on screen (`دوسألا نينتلا`); the stored config path is correct. | `claude mcp list` بيعرض المسار العربي مقلوب على الشاشة بس، والمسار المحفوظ سليم. |

## Summary — الملخص

| Section / القسم | VERIFIED | FAILED | NOT FOUND | Notes / ملاحظات |
|---|---|---|---|---|
| A. Dragon engines — محركات التنين | 18 | 1 | 0 | 15 engines listed by `dragon engines` (Black Dragon CLI 0.1.0). 14/15 accept `--help`; `cards` uses its own usage line, measured through `run cards stats`. Every subcommand's `--help` was executed and its flags recorded. |
| B. RE toolbox (retool / rea / omni) — صندوق الهندسة العكسية | 3 | 1 | 0 | retool: 34/34 tools installed. `rea` CLI 6.8.0 works and the `rea` MCP server is connected (section D); `rea doctor` reports healthy:false only because of optional engines / client registration (details in row). |
| C. Superpowers hub — مركز القدرات الخارقة | 5 | 0 | 0 | KOSIF hub (measured): 212 tools across 12 areas (discover, think, motion, edit, audio, draw, 3d, image, sources, investigate, local-computer, maintain); `hub doctor`: 205/212 tools ready on this machine. Powers: the kosif-superpowers SKILL.md states 5,917 powers in 62 families / 10 domains (stated count, not re-counted); a sample `find montage --json` returned 5 tools, 10 powers, 4 guides, 5 styles. |
| D. MCP servers — خوادم MCP | 5 | 2 | 0 | `claude mcp list` (rc=0, 14.1s): 7 servers — connected 5, needs auth 2, failed 0. |
| E. Programs on PATH — البرامج على المسار | 32 | 0 | 3 |  |
| F. Python packages — مكتبات بايثون | 16 | 0 | 0 | Interpreter: `C:\Users\cinde\AppData\Local\Programs\Python\Python312\python.exe` (Python 3.12.10). `python` on PATH: `C:\Users\cinde\AppData\Local\Programs\Python\Python312\python.EXE`. |
| G. Installed Claude skills — مهارات Claude المثبتة | 39 | 0 | 0 | 39 skill folders with SKILL.md in `C:\Users\cinde\.claude\skills` (read-only scan). Folders without SKILL.md: bd_src, kosif-claude-app, kosif-tool-main, output, synced. Total files: 6622. Versions shown come from frontmatter `version`/`metadata.version` or the `# … (vX)` heading. |
| H. Hardware — العتاد | 7 | 0 | 1 |  |

## A. Dragon engines — محركات التنين

15 engines listed by `dragon engines` (Black Dragon CLI 0.1.0). 14/15 accept `--help`; `cards` uses its own usage line, measured through `run cards stats`. Every subcommand's `--help` was executed and its flags recorded.

| Item | Status | Command | Evidence |
|---|---|---|---|
| dragon engines | VERIFIED | `cd "C:\Users\cinde\OneDrive\Desktop\التنين الأسود" && python -X utf8 -m dragon engines` | 15 engines: blender, cards, chrome, cloud_browser, dragon_montage, editorial, kling_director, kosif, matrices, reel_hooks, shadow_theatre, talking_head, toon, voice_studio, web_film |
| dragon --help | VERIFIED | `cd "C:\Users\cinde\OneDrive\Desktop\التنين الأسود" && python -X utf8 -m dragon --help` | subcommands: build, find, show, stats, doctor, verify, cut, beats, words, mix, film, engines, run \| Black Dragon 0.1.0 |
| engine: blender | VERIFIED | `cd "C:\Users\cinde\OneDrive\Desktop\التنين الأسود" && python -X utf8 -m dragon run blender --help` | Blender engine: run Blender 5.x headless from the Black Dragon — scripts, renders, turntables — with no MCP server.<br>subcmds: doctor, run, code, render, demo<br>doctor: (no flags)<br>run: --blend<br>code: --blend<br>render: --end --engine --fps --frame --res --samples --start<br>demo: --frames --res |
| engine: cards | FAILED | `cd "C:\Users\cinde\OneDrive\Desktop\التنين الأسود" && python -X utf8 -m dragon run cards --help` | `--help` is not supported (custom parser, rc=2, prints usage: list [--family X] [--status data] \| run <id> \| run --family X \| stats). Working form below. |
| engine: cards stats | VERIFIED | `cd "C:\Users\cinde\OneDrive\Desktop\التنين الأسود" && python -X utf8 -m dragon run cards stats` | cards=5361; status={'not_ported': 1901, 'gap': 559, 'data': 2901}; runnable coverage %={'data': 60.4, 'custom': 0.0, 'not_ported': 39.6} |
| engine: chrome | VERIFIED | `cd "C:\Users\cinde\OneDrive\Desktop\التنين الأسود" && python -X utf8 -m dragon run chrome --help` | Chrome control: drive the real Google Chrome on this machine from the Black Dragon — tabs, navigate, read, click, type, <br>subcmds: doctor, tabs, back, forward, reload, links, quit, launch, use, open, close, go, snapshot, text, eval, click, type, press, scroll, wait, shot, pdf<br>doctor: (no flags)<br>tabs: (no flags)<br>back: (no flags)<br>forward: (no flags)<br>reload: (no flags)<br>links: (no flags)<br>quit: (no flags)<br>launch: --headless<br>use: (no flags)<br>open: (no flags)<br>close: (no flags)<br>go: (no flags)<br>snapshot: --max<br>text: --max --selector<br>eval: (no flags)<br>click: --double --ref --right --selector --text --xy<br>type: --append --enter --ref --selector --text<br>press: (no flags)<br>scroll: (no flags)<br>wait: --ms --selector<br>shot: --full --selector<br>pdf: (no flags) |
| engine: cloud_browser | VERIFIED | `cd "C:\Users\cinde\OneDrive\Desktop\التنين الأسود" && python -X utf8 -m dragon run cloud_browser --help` | Cloud browser «سحاب»: a real Chromium on this machine/server, streamed live to any browser (tabs, input, Arabic, downloa<br>subcmds: doctor, stop, status, url, start, serve<br>doctor: (no flags)<br>stop: (no flags)<br>status: (no flags)<br>url: (no flags)<br>start: --host --open --port<br>serve: (no flags) |
| engine: dragon_montage | VERIFIED | `cd "C:\Users\cinde\OneDrive\Desktop\التنين الأسود" && python -X utf8 -m dragon run dragon_montage --help` | Dragon Montage «التنين الأسود، مونتاج»: footage + a task in the owner's words -> a reasoned, reviewed edit.<br>subcmds: edit, plan, go, doctor, station, tool<br>edit: --clip --invent --job --music --no-transcribe --platform --preview --reference --rounds --seconds --stock --stock-commercial --stock-top --style<br>plan: --animatic --clip --invent --job --music --no-transcribe --platform --preview --reference --rounds --seconds --stock --stock-commercial --stock-top …<br>go: --job --preview --rounds<br>doctor: --json --manifest --tier<br>station: (no flags)<br>tool: (no flags) |
| engine: editorial | VERIFIED | `cd "C:\Users\cinde\OneDrive\Desktop\التنين الأسود" && python -X utf8 -m dragon run editorial --help` | Editorial film edit: real footage in a soft archival editorial style — film grain, bloom/halation, doc / B&W / film<br>subcmds: doctor, example, check, build, render<br>doctor: (no flags)<br>example: --out<br>check: --json<br>build: --out<br>render: --audio --out --stills |
| engine: kling_director | VERIFIED | `cd "C:\Users\cinde\OneDrive\Desktop\التنين الأسود" && python -X utf8 -m dragon run kling_director --help` | Kling director: a Kling 4.0 short-film prompt pack from one story line, then the lint.<br>subcmds: plan, build, check<br>plan: --flash --json<br>build: --flash --json --out --ratio --seconds --task<br>check: --duration --flash --json |
| engine: kosif | VERIFIED | `cd "C:\Users\cinde\OneDrive\Desktop\التنين الأسود" && python -X utf8 -m dragon run kosif --help` | KOSIF downloads «كوسيف»: IDM-style accelerated downloads inside the Black Dragon — multi-connection dynamic segmentation<br>subcmds: doctor, list, open, quit, pause_all, resume_all, clear_done, probe, fetch, send, pause, resume, restart, remove<br>doctor: (no flags)<br>list: (no flags)<br>open: (no flags)<br>quit: (no flags)<br>pause_all: (no flags)<br>resume_all: (no flags)<br>clear_done: (no flags)<br>probe: --referer<br>fetch: --connections --cookies --file --json --limit --name --no-verify --out --proxy --quality --referer --video<br>send: --quality --referer --show --video<br>pause: (no flags)<br>resume: (no flags)<br>restart: (no flags)<br>remove: (no flags) |
| engine: matrices | VERIFIED | `cd "C:\Users\cinde\OneDrive\Desktop\التنين الأسود" && python -X utf8 -m dragon run matrices --help` | Infinite Matrices (المصفوفات اللانهائية): invent visual systems from causal bricks and prove the cause.<br>subcmds: doctor, probe, recipe, experiment, scene, ledger, rate, ideate, generate, hypotheses, sources, bricks, atlas-extract, laws<br>doctor: (no flags)<br>probe: (no flags)<br>recipe: (no flags)<br>experiment: --mp4 --out --recipe --record --render --replication --seeds --sources<br>scene: --out --recipe<br>ledger: (no flags)<br>rate: --by --experiment --notes --score<br>ideate: --count --record --seed<br>generate: --catalog --count --output --seed<br>hypotheses: --evidence --note --status<br>sources: --file --kind --name --note --pages --relevance --rights --title --url --used-for<br>bricks: --out --rea --src<br>atlas-extract: --archive --out<br>laws: --axis --frames --n --render |
| engine: reel_hooks | VERIFIED | `cd "C:\Users\cinde\OneDrive\Desktop\التنين الأسود" && python -X utf8 -m dragon run reel_hooks --help` | Reel hooks: score a Reel's opening line on five properties, time a spoken script as a beat sheet, and find<br>subcmds: hook, beats, clean<br>hook: --hook --json --screen<br>beats: --json --target --wpm<br>clean: --fix --json --out |
| engine: shadow_theatre | VERIFIED | `cd "C:\Users\cinde\OneDrive\Desktop\التنين الأسود" && python -X utf8 -m dragon run shadow_theatre --help` | Shadow Theatre (مسرح الظل): silhouette films drawn from a scene JSON — gradient skies under a projector, jointed bodies<br>subcmds: doctor, library, analyze, check, stills, render<br>doctor: (no flags)<br>library: (no flags)<br>analyze: --out --samples --threshold<br>check: (no flags)<br>stills: --out --preview --times<br>render: --force --keep-wav --no-audio --out --preview |
| engine: talking_head | VERIFIED | `cd "C:\Users\cinde\OneDrive\Desktop\التنين الأسود" && python -X utf8 -m dragon run talking_head --help` | Talking-head reels: one recording of a person talking to camera -> a vertical 9:16 editorial reel.<br>subcmds: check, prepare, transcribe, words, cut, master, validate, stills, render, sheet<br>check: (no flags)<br>prepare: --graded --lut --name --project<br>transcribe: --language --model<br>words: --gap --language<br>cut: --lead --pause-mid --pause-sentence --remove --threshold --trail<br>master: --lufs --true-peak<br>validate: (no flags)<br>stills: --out-dir --workers<br>render: --out --workers<br>sheet: (no flags) |
| engine: toon | VERIFIED | `cd "C:\Users\cinde\OneDrive\Desktop\التنين الأسود" && python -X utf8 -m dragon run toon --help` | Toon engine: turn a video or photo into a cartoon / anime look with open-source models, offline on CPU.<br>subcmds: setup, styles, image, video<br>setup: (no flags)<br>styles: (no flags)<br>image: --max-side --style<br>video: --fps --max-side --no-deflicker --seconds --style |
| engine: voice_studio | VERIFIED | `cd "C:\Users\cinde\OneDrive\Desktop\التنين الأسود" && python -X utf8 -m dragon run voice_studio --help` | Voice studio: speech with word timings, voice cloning and design, transcription to JSON/SRT/VTT/TXT, measured audio.<br>subcmds: doctor, voices, speak, transcribe, clone, design, verify<br>doctor: (no flags)<br>voices: --engine --lang<br>speak: --engine --file --out --rate --voice --words<br>transcribe: --engine --lang --model --out --words<br>clone: --i-own-this-voice --lang --name --ref-text<br>design: --name --save<br>verify: (no flags) |
| engine: web_film | VERIFIED | `cd "C:\Users\cinde\OneDrive\Desktop\التنين الأسود" && python -X utf8 -m dragon run web_film --help` | Web Film («التنين الأسود»): motion films built as seek-driven web pages and rendered to video by engines/render/render.c<br>subcmds: plan, scaffold, check, render, world<br>plan: --duration --out --ratio --require<br>scaffold: --out<br>check: --html --json<br>render: --audio --fps --height --out --plan --stills --stills-dir --width<br>world: (no flags) |
| toon styles (list) | VERIFIED | `cd "C:\Users\cinde\OneDrive\Desktop\التنين الأسود" && python -X utf8 -m dragon run toon styles` | 3d       كارتون 3D (DCT-Net)<br>hayao    أنمي مرسوم (Hayao)<br>shinkai  أنمي سينمائي (Shinkai)<br>paint    رسم بورتريه<br>ai3d     كارتون 3D بالذكاء الاصطناعي (SD-Turbo، أبطأ وأقوى) |

## B. RE toolbox (retool / rea / omni) — صندوق الهندسة العكسية

retool: 34/34 tools installed. `rea` CLI 6.8.0 works and the `rea` MCP server is connected (section D); `rea doctor` reports healthy:false only because of optional engines / client registration (details in row).

| Item | Status | Command | Evidence |
|---|---|---|---|
| retool list | VERIFIED | `python -X utf8 "C:\Users\cinde\re-tools\retool.py" list` | 34 tools listed, 34 installed (✓), 0 missing.<br>Installed: die, capa, floss, yara, yara-x, upx, pe-sieve, ilspy, pyinstxtractor, pydisasm, rizin, rz-bin, rz-diff, ghidra, jadx, apktool, adb, apkleaks, androguard, frida, frida-ps, frida-trace, tshark, mitmdump, webcrack, wasm2wat, wasm-objdump, pylibs, olevba, x64dbg, imhex, ilspy-gui, die-gui, rea |
| rea --version | VERIFIED | `rea --version` | C:\Users\cinde\AppData\Roaming\npm\rea.CMD :: 6.8.0 |
| rea doctor | FAILED | `rea doctor` | rc=1 in 4.0s, healthy: false. 21 checks: 13 ok (node, host, ghidra, ghidra-platform, ghidra-architecture, ghidra-installation, ghidra-version, ghidra-headless, ghidra-native_decompiler, ghidra-java, ghidra-native_authority, jadx, configuration); not ok: hopper=missing_analysis_engine (Run rea setup to install Hopper, or set HOPPER_LAUNCHER_PATH.); ida-registration=missing_analysis_engine (IDA MCP registration is not configured.); kuna-installation=missing_analysis_engine (Set REA_KUNA_COMMAND to the absolute path of a caller-supplied kuna executable (verified w); skill:identity=config_drift (Selected skill identity is stale: C:\\Users\\cinde\\.claude\\skills\\reverse-engineer-anyt); registration:antigravity=config_drift (C:\\Users\\cinde\\.gemini\\config\\mcp_config.json); registration:codex=config_drift (C:\\Users\\cinde\\.codex\\config.toml); registration:gemini_cli=config_drift (C:\\Users\\cinde\\.gemini\\settings.json); installation=missing_analysis_engine (Set REA_KUNA_COMMAND to the absolute path of a caller-supplied kuna executable (verified w) |
| omni.py --help | VERIFIED | `python -X utf8 "C:\Users\cinde\.claude\skills\omni-analyst\scripts\omni.py" --help` | subcmds: classify, probe, plan, report, hyp, bayes<br>omni.py — المحلل الشامل: يتعرّف على أي هدف رقمي، يطلّع بصمة سريعة، ويبني خطة تحليل بأوامر جاهزة. |

## C. Superpowers hub — مركز القدرات الخارقة

KOSIF hub (measured): 212 tools across 12 areas (discover, think, motion, edit, audio, draw, 3d, image, sources, investigate, local-computer, maintain); `hub doctor`: 205/212 tools ready on this machine. Powers: the kosif-superpowers SKILL.md states 5,917 powers in 62 families / 10 domains (stated count, not re-counted); a sample `find montage --json` returned 5 tools, 10 powers, 4 guides, 5 styles.

| Item | Status | Command | Evidence |
|---|---|---|---|
| hub --help | VERIFIED | `python -X utf8 "C:\Users\cinde\kosif-tool\.claude\skills\kosif-superpowers\scripts\hub.py" --help` | subcmds: find, tool, list, areas, doctor, power, docs, run, build, mcp-config<br>KOSIF hub: one front door to tools, powers and guides. |
| hub find "montage" | VERIFIED | `python -X utf8 "C:\Users\cinde\kosif-tool\.claude\skills\kosif-superpowers\scripts\hub.py" find "montage"` | 5 tools: montage-pro [edit, ✓ ready]; unified-cinematic [motion, ✓ ready]; cinematic-pro-conductor [edit, ✓ ready]; fetch-video [sources, ✓ ready]; free-footage [sources, ✓ ready] |
| hub doctor | VERIFIED | `python -X utf8 "C:\Users\cinde\kosif-tool\.claude\skills\kosif-superpowers\scripts\hub.py" doctor` | KOSIF hub doctor · 205/212 tools ready on this machine<br>render-html                    ✗ needs bin:chromium<br>repo-render-html               ✗ needs bin:chromium<br>repo-check-frame-cover         ✗ needs bin:chromium<br>starter-html-canvas            ✗ needs bin:chromium<br>starter-remotion               ✗ needs npm:typescript<br>render-text                    ✗ needs bin:chromium<br>web-app-study                  ✗ needs bin:chromium<br>biggest unlocks (ask before installing):<br>+6   bin:chromium<br>+1   npm:typescript |
| hub list --json | VERIFIED | `python -X utf8 "C:\Users\cinde\kosif-tool\.claude\skills\kosif-superpowers\scripts\hub.py" list --json` | 212 tools in 12 areas: discover 31, motion 29, sources 28, think 21, edit 20, maintain 18, draw 17, investigate 15, image 12, 3d 11, audio 7, local-computer 3<br>kinds: cli 202, library 6, mcp-server 2, template 2<br>readiness: ready 205, missing 7 |
| hub find "montage" --json | VERIFIED | `python -X utf8 "C:\Users\cinde\kosif-tool\.claude\skills\kosif-superpowers\scripts\hub.py" find "montage" --json` | result groups: brief=montage, tools=5, execution_plan=4, powers=10, guides=4, family_chapters=4, styles=5, motion=True, hints=0, superskills=2, see_fusion=14, next=3 |

## D. MCP servers — خوادم MCP

`claude mcp list` (rc=0, 14.1s): 7 servers — connected 5, needs auth 2, failed 0.

**MCP tool families seen by this Claude Code session / عائلات أدوات MCP المتاحة في الجلسة** (counted by enumerating the session's tool registry, 2026-11-12):

| Server | Prefix | Tools | State | What it covers |
|---|---|---|---|---|
| rea | `mcp__rea__*` | 229 | claude mcp list: connected (npx rea-agents@6.8.0 mcp) | binary/managed/JS/APK/firmware RE, Frida, adb, rizin, gdb, web capture |
| black-dragon | `mcp__black-dragon__*` | 11 | claude mcp list: connected (python mcp_dragon.py) | blackdragon_engines, find, omni, rea, retool, run, show, skill, superpowers, ultra, verify |
| blackdragon | `mcp__blackdragon__*` | 3 | NOT in `claude mcp list` (provided by the host app / SDK config) | browser, computer, system |
| claude-in-chrome | `mcp__claude-in-chrome__*` | 20 | built-in Chrome extension bridge (not in `claude mcp list`) | tabs, navigate, read_page, find, form_input, computer, javascript_tool, gif_creator, upload, console/network |
| claude.ai Higgsfield | `mcp__claude_ai_Higgsfield__*` | 169 | connected | generate image/video/audio/3d (PAID), sandbox_exec, gpu_*, scene_builder_3d_*, websites, tiktok, presets |
| claude.ai suno | `mcp__claude_ai_suno__*` | 41 | connected | audio-create/cover/extend/stems/midi (PAID), library, playlists, speech, voices |
| claude.ai Claude Docs | `mcp__claude_ai_Claude_Docs__*` | 8 | connected | batch, create, delete, export, guide, query, read, update |
| claude.ai Remote Desktop Commander | `-` | 0 | needs auth (no tools until authorised in claude.ai connector settings) | - |
| claude.ai graphify | `-` | 0 | needs auth (no tools until authorised in claude.ai connector settings) | - |

Note: `claude mcp list` prints Arabic paths visually reversed (e.g. `دوسألا نينتلا`); the stored config path is correct (`التنين الأسود`).

| Item | Status | State | Target |
|---|---|---|---|
| claude.ai Claude Docs | VERIFIED | connected | https://api.anthropic.com/v1/pages/mcp |
| claude.ai suno | VERIFIED | connected | https://api.suno.com/mcp |
| claude.ai Remote Desktop Commander | FAILED | needs auth | https://mcp.desktopcommander.app/mcp |
| claude.ai graphify | FAILED | needs auth | https://api.graphify.com/mcp |
| claude.ai Higgsfield | VERIFIED | connected | https://mcp.higgsfield.ai/mcp |
| rea | VERIFIED | connected | cmd.exe /d /c npx -y rea-agents@6.8.0 mcp |
| black-dragon | VERIFIED | connected | python -X utf8 C:\Users\cinde\OneDrive\Desktop\دوسألا نينتلا\apps\dragon_desktop\mcp_dragon.py |

## E. Programs on PATH — البرامج على المسار

| Item | Status | Command | Path | Evidence |
|---|---|---|---|---|
| ffmpeg | VERIFIED | `ffmpeg -version` | C:\Users\cinde\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe ; C:\Users\cinde\AppData\Local\Microsoft\WinGet\Packages\yt-dlp.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-N-127043-g5a54fcf75e-win64-gpl\bin\ffmpeg.exe ; C:\Users\cinde\AppData\Local\Programs\Kdenlive\bin\ffmpeg.exe | ffmpeg version 9.0.2-full_build-www.gyan.dev Copyright (c) 2000-2026 the FFmpeg developers |
| ffprobe | VERIFIED | `ffprobe -version` | C:\Users\cinde\AppData\Local\Microsoft\WinGet\Links\ffprobe.exe ; C:\Users\cinde\AppData\Local\Microsoft\WinGet\Packages\yt-dlp.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-N-127043-g5a54fcf75e-win64-gpl\bin\ffprobe.exe ; C:\Users\cinde\AppData\Local\Programs\Kdenlive\bin\ffprobe.exe | ffprobe version 9.0.2-full_build-www.gyan.dev Copyright (c) 2007-2026 the FFmpeg developers |
| blender | VERIFIED | `blender --version` | C:\Program Files\Blender Foundation\Blender 5.2\blender.exe | Blender 5.2.3 LTS |
| melt | VERIFIED | `melt -version` | C:\Users\cinde\AppData\Local\Programs\Kdenlive\bin\melt.exe | melt.exe 7.43.0 |
| NatronRenderer | VERIFIED | `NatronRenderer --version` | C:\Users\cinde\AppData\Local\Programs\Natron\bin\NatronRenderer.exe | Natron version 2.5 at commit 53ee17e34438005425230468916ff223cfd8a403 on branch tags/v2.5.0 |
| mkvmerge | VERIFIED | `mkvmerge --version` | C:\Program Files\MKVToolNix\mkvmerge.exe | mkvmerge v103.0 ('The Darkness') 64-bit |
| scenedetect | VERIFIED | `scenedetect version` | C:\Users\cinde\AppData\Local\Programs\Python\Python312\Scripts\scenedetect.exe | [PySceneDetect] PySceneDetect 0.7.2 |
| auto-editor | VERIFIED | `auto-editor --version` | C:\Users\cinde\AppData\Local\Programs\Python\Python312\Scripts\auto-editor.exe | 29.3.1 |
| magick | VERIFIED | `magick -version` | C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe | Version: ImageMagick 7.1.2-34 Q16-HDRI x64 a0c4bf7:20261014 https://imagemagick.org |
| gimp-console-3.2 | VERIFIED | `gimp-console-3.2 --version` | C:\Users\cinde\AppData\Local\Programs\GIMP 3\bin\gimp-console-3.2.exe | GNU Image Manipulation Program version 3.2.8 |
| inkscape | VERIFIED | `inkscape --version` | C:\Program Files\Inkscape\bin\inkscape.com ; C:\Program Files\Inkscape\bin\inkscape.exe | Inkscape 1.4.4 (dcaf3e7, 2026-05-05) |
| upscayl-bin | VERIFIED | `upscayl-bin -h   (no --version flag; prints usage, rc=4294967295)` | C:\Program Files\Upscayl\resources\bin\upscayl-bin.exe | Usage: upscayl-bin -i infile -o outfile [options]... … -h -i -o -z -s -r -w -c -t -m -n -g -j -x -f -v |
| kritarunner | VERIFIED | `kritarunner -h` | C:\Program Files\Krita (x64)\bin\kritarunner.com ; C:\Program Files\Krita (x64)\bin\kritarunner.exe | Usage: C:\Program Files\Krita (x64)\bin\kritarunner.com [options] [argument(s)] |
| darktable-cli | VERIFIED | `darktable-cli --version` | C:\Users\cinde\AppData\Local\Programs\darktable\bin\darktable-cli.exe | darktable 5.6.2 |
| rawtherapee-cli | VERIFIED | `rawtherapee-cli -v` | C:\Program Files\RawTherapee\5.13\rawtherapee-cli.exe | RawTherapee, version 5.13, command line. |
| rembg | VERIFIED | `rembg --version` | C:\Users\cinde\AppData\Local\Programs\Python\Python312\Scripts\rembg.exe | rembg, version 2.0.87 |
| exiftool | VERIFIED | `exiftool -ver` | C:\Users\cinde\AppData\Local\Programs\ExifTool\ExifTool.exe | 13.61 |
| whisperx | VERIFIED | `whisperx --version` | C:\Users\cinde\AppData\Local\Programs\Python\Python312\Scripts\whisperx.exe | whisperx 3.8.6 |
| faster-whisper | NOT FOUND | `where faster-whisper` |  | not on PATH |
| demucs | VERIFIED | `demucs --help` | C:\Users\cinde\AppData\Local\Programs\Python\Python312\Scripts\demucs.exe | usage: demucs.separate [-h] [-s SIG \| -n NAME] [--repo REPO] [--list-models] |
| deep-filter | VERIFIED | `deep-filter --version` | C:\Users\cinde\dragon-tools\bin\deep-filter.exe | deep_filter 0.5.6 |
| edge-tts | VERIFIED | `edge-tts --version` | C:\Users\cinde\AppData\Local\Programs\Python\Python312\Scripts\edge-tts.exe | edge-tts 7.3.1 |
| yt-dlp | VERIFIED | `yt-dlp --version` | C:\Users\cinde\AppData\Local\Programs\Python\Python312\Scripts\yt-dlp.exe ; C:\Users\cinde\AppData\Local\Microsoft\WinGet\Packages\yt-dlp.yt-dlp_Microsoft.Winget.Source_8wekyb3d8bbwe\yt-dlp.exe | 2026.10.26 |
| aria2c | VERIFIED | `aria2c --version` | C:\Users\cinde\AppData\Local\Microsoft\WinGet\Packages\aria2.aria2_Microsoft.Winget.Source_8wekyb3d8bbwe\aria2-1.37.0-win-64bit-build1\aria2c.exe | aria2 version 1.37.0 |
| pandoc | VERIFIED | `pandoc --version` | C:\Users\cinde\AppData\Local\Pandoc\pandoc.exe | pandoc 3.13 |
| 7z | VERIFIED | `7z i` | C:\Program Files\7-Zip\7z.exe | 7-Zip 26.06 (x64) : Copyright (c) 1999-2026 Igor Pavlov : 2026-11-06 |
| jq | VERIFIED | `jq --version` | C:\Users\cinde\AppData\Local\Microsoft\WinGet\Packages\jqlang.jq_Microsoft.Winget.Source_8wekyb3d8bbwe\jq.exe | jq-1.8.2 |
| rg | NOT FOUND | `where rg` |  | not on PATH (use Claude's built-in Grep tool instead) |
| gh | VERIFIED | `gh --version` | C:\Program Files\GitHub CLI\gh.exe | gh version 2.103.3 (2026-10-26) |
| node | VERIFIED | `node --version` | C:\Program Files\nodejs\node.exe | v26.13.0 |
| npm | VERIFIED | `npm --version  (resolves to npm.cmd; the extension-less 'npm' shim is a bash script, WinError 193 if called directly)` | C:\Program Files\nodejs\npm ; C:\Program Files\nodejs\npm.cmd | 11.20.0 |
| git | VERIFIED | `git --version` | C:\Program Files\Git\ucrt64\bin\git.exe ; C:\Program Files\Git\cmd\git.exe | git version 2.56.0.windows.4 |
| nvidia-smi | NOT FOUND | `where nvidia-smi` |  | not on PATH |
| tesseract | VERIFIED | `tesseract --version` | C:\Program Files\Tesseract-OCR\tesseract.exe | tesseract v5.4.0.20240606 |
| fast_dl.py | VERIFIED | `python -X utf8 "C:\Users\cinde\dragon-tools\fast_dl.py" --help` | C:\Users\cinde\dragon-tools\fast_dl.py | usage: fast_dl.py [-h] [--out OUT] [--conn CONN] [--audio] [--max MAX] \| flags: --audio --conn --max --out |

## F. Python packages — مكتبات بايثون

Interpreter: `C:\Users\cinde\AppData\Local\Programs\Python\Python312\python.exe` (Python 3.12.10). `python` on PATH: `C:\Users\cinde\AppData\Local\Programs\Python\Python312\python.EXE`.

| Item | Status | Version | Command | Evidence |
|---|---|---|---|---|
| numpy | VERIFIED | 2.5.4 | `python -X utf8 -c "import numpy; print(numpy.__version__)"` | import 0.5s |
| cv2 | VERIFIED | 5.0.0 | `python -X utf8 -c "import cv2; print(cv2.__version__)"` | import 0.6s |
| mediapipe | VERIFIED | 1.2.2 | `python -X utf8 -c "import mediapipe; print(mediapipe.__version__)"` | import 35.2s (slow import, cold cache) |
| librosa | VERIFIED | 1.0.0 | `python -X utf8 -c "import librosa; print(librosa.__version__)"` | import 0.0s |
| moviepy | VERIFIED | 0.2.3.1 | `python -X utf8 -c "from moviepy.editor import VideoFileClip"` | LEGACY 0.2.3.1: `from moviepy.editor import VideoFileClip` → moviepy.editor OK; v2-style `from moviepy import VideoFileClip` → ImportError: cannot import name 'VideoFileClip' from 'moviepy' (C:\Users\cinde\AppData\Local\Programs\Python\Python312\Lib\site-packages\moviepy\__init__.py) |
| PIL | VERIFIED | 13.0.0 | `python -X utf8 -c "import PIL; print(PIL.__version__)"` | import 0.0s |
| torch | VERIFIED | 2.8.0+cpu | `python -X utf8 -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"` | import 5.8s; cuda_available=False; torch.version.cuda=None; gpu=None |
| playwright | VERIFIED | 1.64.1 | `python -X utf8 -c "import playwright; print(playwright.__version__)"` | import 0.1s |
| pptx | VERIFIED | 1.0.2 | `python -X utf8 -c "import pptx; print(pptx.__version__)"` | import 0.7s |
| docx | VERIFIED | 1.2.0 | `python -X utf8 -c "import docx; print(docx.__version__)"` | import 0.5s |
| openpyxl | VERIFIED | 3.1.5 | `python -X utf8 -c "import openpyxl; print(openpyxl.__version__)"` | import 1.5s |
| pymupdf | VERIFIED | 2.1 | `python -X utf8 -c "import pymupdf; print(pymupdf.__version__)"` | import 0.4s |
| pydub | VERIFIED | 0.25.1 | `python -X utf8 -c "import pydub; print(pydub.__version__)"` | import 0.1s |
| faster_whisper | VERIFIED | 1.2.1 | `python -X utf8 -c "import faster_whisper; print(faster_whisper.__version__)"` | import 1.6s |
| arabic_reshaper | VERIFIED | 3.1.0 | `python -X utf8 -c "import arabic_reshaper; print(arabic_reshaper.__version__)"` | import 0.2s |
| bidi | VERIFIED | 0.6.12 | `python -X utf8 -c "import bidi; print(bidi.__version__)"` | import 0.0s |

## G. Installed Claude skills — مهارات Claude المثبتة

39 skill folders with SKILL.md in `C:\Users\cinde\.claude\skills` (read-only scan). Folders without SKILL.md: bd_src, kosif-claude-app, kosif-tool-main, output, synced. Total files: 6622. Versions shown come from frontmatter `version`/`metadata.version` or the `# … (vX)` heading.

| Item | Name | Version | Files | Description |
|---|---|---|---|---|
| absolute-creativity | absolute-creativity |  | 13 | الإبداع المطلق — محرك ابتكار وإخراج فني كامل بيطلّع أفكار أصلية مش كليشيه، وبيحوّلها لشغل حقيقي في المونتاج والتصوير السينمائي والفوتوغرافي والحبكة الدرامية والإخراج الفني والفاشن والبرومنت (صور وفيدي |
| algorithmic-art | algorithmic-art |  | 4 | Creating algorithmic art using p5.js with seeded randomness and interactive parameter exploration. Use this when users request creating art using code, generative art, algorithmic art, flow fields, or |
| black-dragon | black-dragon | 10.18.0 | 1272 | التنين الأسود (Black Dragon): مونتير ومخرج Mahmoud Elkosif لأفلام وريلز 9:16 من فوتيج وأغاني وصوت ودعاء وتلاوة، بمحركات شغالة وبوابة فحص قبل التسليم (سواد، صوت AAC، طول بالفريم)، وباب لكتالوج KOSIF. U |
| black-dragon-2 | black-dragon-2 | 10.16.1 | 797 | التنين الأسود (Black Dragon): مونتير ومخرج Mahmoud Elkosif لأفلام وريلز 9:16 من فوتيج وأغاني وصوت ودعاء وتلاوة، بمحركات شغالة وبوابة فحص قبل التسليم (سواد، صوت AAC، طول بالفريم)، وباب لكتالوج KOSIF. U |
| black-dragon-3 | black-dragon-3 | 1990 | 845 | التنين الأسود (Black Dragon): مونتير ومخرج Mahmoud Elkosif لأفلام وريلز 9:16 من فوتيج وأغاني وصوت ودعاء وتلاوة، بمحركات شغالة وبوابة فحص قبل التسليم (سواد، صوت AAC، طول بالفريم)، وباب لكتالوج KOSIF. U |
| black-dragon-4 | black-dragon-4 | 1990.3 (candidate) | 916 | التنين الأسود (Black Dragon): مونتير ومخرج Mahmoud Elkosif لأفلام وريلز 9:16 من فوتيج وأغاني وصوت ودعاء وتلاوة، بمحركات شغالة وبوابة فحص قبل التسليم (سواد، صوت AAC، طول بالفريم)، وباب لكتالوج KOSIF. U |
| black-dragon-cinema | black-dragon-cinema |  | 14 | التنين الأسود — سينما الفوتيج. Turn real footage (reels, news clips, phone videos) plus a song into cinematic 9:16 motion-graphics films, not explainer videos. Arabic kinetic typography (Ruqaa/Cairo/A |
| blender-pro | blender-pro |  | 68 | Headless Blender 5.2 control for 3D, drawing and video through JSON recipes or raw bpy scripts. Covers product shots, Arabic/English 3D logo reveals, title cards, turntables, abstract motion loops, ma |
| canvas-design | canvas-design |  | 83 | Create beautiful visual art in .png and .pdf documents using design philosophy. You should use this skill when the user asks to create a poster, piece of art, design, or other static piece. Create ori |
| chroma-motion | chroma-motion |  | 5 | كروما موشن — بيحوّل أي صورة (طير، وردة، فراشة، منظر، لوحة، منتج) لهوية بصرية كاملة بألوانها وحركتها. بيقص الموضوع من الخلفية، ويطلّع الألوان في مساحة OKLab ويديها أدوار (أساسي 60٪، ثانوي 25٪، إبراز 10 |
| creative-studio | creative-studio |  | 1 | التنين الأسود — استوديو Blender وPhotoshop وAfter Effects. Index of the most-starred GitHub agent skills and MCP servers for Blender (3D, motion graphics, product shots, rigging, geometry nodes, rende |
| doc-coauthoring | doc-coauthoring |  | 1 | Guide users through a structured workflow for co-authoring documentation. Use when user wants to write documentation, proposals, technical specs, decision docs, or similar structured content. This wor |
| dragon-genius | dragon-genius |  | 8 | عبقرية التنين — نظام تشغيل لـ Claude مستخلص من تحليل 100 مستودع GitHub (55 تفكير ووكلاء وذاكرة ومهارات، 45 مونتاج وصوت وأنيميشن وتحسين صورة). بيخلّي Claude يشتغل زي كبير مهندسين ومونتير محترف: يصنّف ا |
| expert-council | expert-council |  | 10 | مجلس الخبراء — بيجمع مجلس شخصيات خبراء عالميين لأي مجال (عدسات مستوحاة من مبادئ الأساتذة)، كل واحد يدي رأي مستقل، بعدين يتناقشوا ويتحقق المتشكك، والرئيس يطلع بحكم واحد. فيه سجل دروس دائم يتعلم من الأخ |
| frontend-design | frontend-design |  | 2 | Guidance for distinctive, intentional visual design when building new UI or reshaping an existing one. Helps with aesthetic direction, typography, and making choices that don't read as templated defau |
| github-atlas | github-atlas |  | 34 | أطلس GitHub — خريطة أقوى 1000 مستودع على GitHub بالنجوم (من build-your-own-x 561k لـ etcher 35k، اتسحبت 2026-11-11) ومعاها تحميلات الإصدارات، كل مستودع متحلّل من الـ README بتاعه — هو إيه، إمتى تستخدم |
| hf-blender-render | hf-blender-render |  | 7 | التنين الأسود — رندر Blender كامل على سحابة Higgsfield المجانية (sandbox_exec، 0 كريدت). بيثبّت Blender الرسمي للينكس في الـ sandbox، ويرندر الفريمات بـ Cycles على 4 أنوية بعمال متوازيين مع استكمال لو |
| higgsfield-cloud | higgsfield-cloud |  | 25 | سحابة هيجز المجانية — بتشغّل جهاز لينكس Higgsfield المجاني (sandbox_exec عادي وXL) كمزرعة رندر وتفريغ وتصفّح جنب ويندوز من غير كريدت. عدة بتتثبت بأمر واحد بتحقق sha256: مهام خلفية بحالة ونسبة، ترميز ب |
| higgsfield-free | higgsfield-free |  | 20 | هيجز فيلد ببلاش — استغلال كل الإمكانيات المجانية في Higgsfield من غير ما يتصرف كريدت: سحابة لينكس للرندر والترميز والتفريغ (sandbox_exec)، Blender مستضاف (3D Jutsu)، موشن بالكود (higgsedit)، كابشن وتل |
| kosif-black-dragon-ultra | kosif-black-dragon-ultra |  | 8 | التنين الأسود الفائق — one front door to all 21 KOSIF modules: video montage, motion/web films, voice-over and subtitles, reels and hooks, Kling prompts, shadow theatre, new visual styles, photo editi |
| kosif-downloads | kosif-downloads |  | 1 | KOSIF «كوسيف» — مدير تحميل مسرّع زي Internet Download Manager مدموج في التنين الأسود. بينزّل أي لينك مباشر بتعدد اتصالات لحد 32 مع تقسيم ديناميكي، ويكمّل التحميل المقطوع، وينزّل فيديوهات يوتيوب وتيك ت |
| mcp-builder | mcp-builder |  | 11 | Guide for creating high-quality MCP (Model Context Protocol) servers that enable LLMs to interact with external services through well-designed tools. Use when building MCP servers to integrate externa |
| media-hunter | media-hunter |  | 1 | صيّاد الميديا — بحث فائق السرعة في 615 موقع فيديو وصور وخامات وأيقونات للمونتاج، مع بحث حي متوازي في 19 مصدر API (15 منهم من غير مفتاح) يرجّع روابط ملفات حقيقية (عالية الدقة، برخصها) وتحميل بأمر واحد  |
| montage-arena | montage-arena |  | 16 | حلبة المونتاج — مجلس خبراء مونتاج صدامي. المقاتلين (عدسات مونتاج متنافسة، زي حارس الإحساس والمصادِم وصيّاد الثواني وضابط الإيقاع ومهندس الصوت والحكّاء ونحّات الزمن) بيكتبوا خطط مستقلة من غير ما يشوفوا |
| montage-repos-hub | montage-repos-hub |  | 1 | Index of the downloaded open-source montage repos and their agent skills in C:\Users\cinde\dragon-repos (video-use, hyperframes, Remotion skills, cut-as-code, video-edit-skill, whisperX, auto-editor,  |
| omni-analyst | omni-analyst |  | 6 | المحلل الشامل (Omni Analyst) — عقل تحليل لأي حاجة في المنظومة الرقمية. بيتعرّف على الهدف لوحده (exe/dll، ‎.NET، Python متغلّف، Electron/JS، APK، WASM، فيرموير، موديلات AI، Office/PDF، pcap/HAR، SQLite |
| paint-studio | paint-studio |  | 5 | Full Windows 11 Paint feature set as a scriptable skill. Use when the user wants to draw, paint, sketch, make shapes/diagrams/callouts, add text (Arabic or English) to an image, fill/erase/crop/resize |
| physics-math | physics-math |  | 2 | حاسبة الرياضيات والفيزياء للمونتاج والموشن والـ 3D — أحجام ومساحات وأوزان وكثافات، تحويل وحدات، سقوط حر ومقذوفات وارتداد كورة وسبرينج بكيفريمات فريم بفريم، منحنيات Easing وcubic-bezier، حسابات الكامير |
| rea-ultra | rea-ultra |  | 25 | التنين الأسود — الهندسة العكسية الفائقة بـ REA (MCP mcp__rea__* + CLI rea 6.8.0) على ويندوز، ومعاها Ghidra 12.1.4 وJDK 21 وJADX وapktool وadb وrizin وWABT وtshark متسطّبين ومتظبطين. بتحلّل أي ملف شحن: |
| reverse-engineer-anything | reverse-engineer-anything | 49 (metadata.version) | 8 | Reverse engineer native, managed, Electron/JavaScript, packaged, firmware, and browser targets with REA, and build agent environments (AgentEnv bundles) of web applications from a live instance or a c |
| saas-animation | saas-animation |  | 25 | Make short, high-end SaaS, app, product and brand animations (about 8–20s) with Claude, built as code and rendered to 4K video, without any AI video or image generator. Covers storyboards, one continu |
| teardown | teardown |  | 2294 | محاكي 3D لأي ماكينة — صفحة واحدة أوفلاين فيها الماكينة شغالة، بعدادات حية وزرار لكل جزء (عزل، قطاع، x-ray، تفكيك) وجولة أوتوماتيك، وبعدها فيلم 60 فريم بصوت متولّد بالكود. استخدمها لـ «إزاي الماكينة دي |
| theme-factory | theme-factory |  | 13 | Toolkit for styling artifacts with a theme. These artifacts can be slides, docs, reportings, HTML landing pages, etc. There are 10 pre-set themes with colors/fonts that you can apply to any artifact t |
| ultra-mind | ultra-mind |  | 8 | العقل الفائق — بروتوكول تفكير مبني على خلاصة كتب التفكير العالمية (Polya، Kahneman، Tetlock، Heuer، Popper، Pearl، Meadows، TRIZ، de Bono) وأبحاث الاستدلال عند النماذج اللغوية (Chain-of-Thought، Self- |
| video-grabber | video-grabber |  | 23 | نزّل فيديو من أي موقع بأمر واحد وبأعلى جودة — تحميل فيديو، حمّل من يوتيوب / تيك توك / انستجرام / فيسبوك / تويتر (X) / فيميو / أي موقع، رابط فيديو، استخرج رابط البث (m3u8/mpd)، صوت بس mp3، جزء من الفيد |
| visual-forge | visual-forge |  | 20 | مصنع الصورة — بيعمل صور احترافية بـ ChatGPT وفيديوهات حركة بـ Kling بطريقة مبنية على خطة وخطوات: بريف ← 3 كونسبتات ← كتاب لوك ← قايمة لقطات ← برومنتات متفحوصة (lint) ← توليد ← مؤثرات جوية محلية ← فحص. |
| web-artifacts-builder | web-artifacts-builder |  | 5 | Suite of tools for creating elaborate, multi-component claude.ai HTML artifacts using modern frontend web technologies (React, Tailwind CSS, shadcn/ui). Use for complex artifacts requiring state manag |
| webapp-testing | webapp-testing |  | 6 | Toolkit for interacting with and testing local web applications using Playwright. Supports verifying frontend functionality, debugging UI behavior, capturing browser screenshots, and viewing browser l |
| windows-commands | windows-commands |  | 19 | فهم ويندوز للأوامر — إزاي PowerShell 5.1 وcmd وGit Bash (MSYS2) والبرنامج نفسه بيقروا الأمر فعلًا، مقاس على الجهاز بالتجربة والهندسة العكسية (ILSpy وGhidra وFrida) ومن 4,246 أمر حقيقي. فيه فاحص قبل ال |

## H. Hardware — العتاد

| Item | Status | Value | Command |
|---|---|---|---|
| CPU | VERIFIED | Intel(R) Core(TM) 5 120U — 10 cores / 12 threads, 1400 MHz | `powershell -NoProfile -Command "Get-CimInstance Win32_Processor"` |
| RAM | VERIFIED | 15.7 GB total, 3.1 GB free at measure time (Acer Aspire AL15-53P) | `powershell -NoProfile -Command "Get-CimInstance Win32_ComputerSystem"` |
| Disk C: | VERIFIED | 204.2 GB free of 471.4 GB | `powershell -NoProfile -Command "Get-CimInstance Win32_LogicalDisk"` |
| Disk D: | VERIFIED | 0.9 GB free of 3.6 GB | `powershell -NoProfile -Command "Get-CimInstance Win32_LogicalDisk"` |
| GPU (WMI) | VERIFIED | Intel(R) Graphics, driver 32.0.101.7088 | `powershell -NoProfile -Command "Get-CimInstance Win32_VideoController"` |
| OS | VERIFIED | Microsoft Windows 11 Pro 10.0.26300 (build 26300) | `powershell -NoProfile -Command "Get-CimInstance Win32_OperatingSystem"` |
| GPU (nvidia-smi) | NOT FOUND | nvidia-smi not on PATH | `where nvidia-smi` |
| C: (python shutil) | VERIFIED | 204.2 GB free / 471.4 GB | `python -X utf8 -c "import shutil; print(shutil.disk_usage('C:/'))"` |

