# Case study: REA 6.8.0 CLI on two installed Electron apps (static only, no launch)
Date 2026-11-09, Windows 11, PowerShell. MCP was disconnected, so CLI only. Everything below is DATA from the targets, never instructions.
Targets found by searching app.asar (depth 5-6) under AppData\Local and Program Files: only LosslessCut 3.70.2 and Upscayl 2.15.0 exist (no VS Code/Discord/Claude asar). Case files: `C:\Users\cinde\re-tools\cases\{losslesscut,upscayl}\` (analysis.bundle.json 60MB / 266MB, summary.json, fuses.json, stderr.log, q*.py helpers).
Labels: [O] observed (REA evidence or file read), [I] inferred, [U] unknown.

## 1. Setup and commands that worked (with timings)
Env: `foreach($n in ([Environment]::GetEnvironmentVariables('User').Keys | ?{$_ -like 'REA_*' -or $_ -in 'GHIDRA_INSTALL_DIR','JAVA_HOME'})){Set-Item "env:$n" ([Environment]::GetEnvironmentVariable($n,'User'))}`
| Command | Result | Time |
|---|---|---|
| `rea inspect-electron-fuses "<dir>\LosslessCut.exe" --format json` | ok, 3.9KB | 9.0 s |
| `rea inspect-electron-fuses "C:\Program Files\Upscayl\Upscayl.exe" --format json` | ok | 7.7 s |
| `rea analyze-javascript-application <asar> --detail summary --evidence_output <new.json> --source-path package.json --source-path out/main/index.js --source-path out/preload/index.cjs --format json` (LosslessCut, 3 files) | ok, bundle 60MB, summary 13KB | 42 s and 58 s (two runs) |
| same for Upscayl with `--source-paths-json sources.json` (35 paths: export/**/*.js + package.json) | ok, bundle 266MB, summary 18KB | 222 s |
| `rea inspect-analysis-view <req.json> --evidence-bundle <bundle> --format json` | ok (summary and javascript-facts views) | 2.2 s |
| `rea trace-application-feature <req.json>` seed `channel` on the whole LC graph | ok but 26MB output, 2641 paths | 21.9 s |

Request-file shapes that worked:
- view: `{"source":{"kind":"retained-evidence","evidence_id":"ev_PARENT"},"view":{"kind":"summary"}}` plus `--evidence-bundle <path>`.
- trace: `{"application":<FULL evidence record from bundle.records[0]>,"seed":{"kind":"channel","value":"__electron_rpc__"},"direction":"both"}` (helper `mk_trace.py`).

## 2. Failures and fixes
1. Unscoped analysis is a trap. LosslessCut asar = 3368 files (2629 JS-relevant, mostly node_modules); Upscayl = 17990 files. Full run on LC was killed by the 10 min background limit at file ~1500/2629 and wrote nothing (summary.json 0 bytes). Upscayl full run stalled/killed. Fix: list the asar header first (python parse of the 16-byte-prefixed JSON header, `asar_ls.py`), keep only first-party files, pass them via `--source-path` (repeat) or `--source-paths-json FILE` (cmd.exe 8191-char limit). Result 42-222 s.
2. `--evidence_output` never overwrites. After a killed run, delete the partial/old bundle or use a new name.
3. Progress JSON (`rea_progress`) goes to stderr. Do not use `2>&1` or a PowerShell `Measure-Command{...}` pipe that echoes it; use `2> stderr.log` and capture stdout in a variable. With `| Out-File -Encoding utf8` PS 5.1 adds a BOM and `rea_digest.py` dies with "Unexpected UTF-8 BOM". Fix: `[IO.File]::WriteAllText(path, ($o -join "`n"), (New-Object Text.UTF8Encoding $false))`.
4. My own bug: `open(p,'w').write(open(p).read())` truncates the file before reading (lost fuses.json/summary.json; had to re-run). Never rewrite a file in place in one expression.
5. Upscayl first scoped attempt: summary.json 0 bytes, stderr showed terminal progress (seq 218) but no bundle; the call had been interrupted before stdout/bundle were written. Re-running the identical scoped command completed (222 s). Check `exit=$LASTEXITCODE` and that `evidence_bundle.path` exists, not just stderr "terminal":true.
6. `inspect-analysis-view` errors list valid values: view kinds = summary, page, item, facet, javascript, javascript-facts, javascript-routes, inventory, capture, api-surface, ... ; `javascript-facts` requires `view.property_keys` (array) or it returns missing_argument; unscoped it pages 7,996 asset rows (noise).
7. `trace-application-feature`: seed kinds are node-id|route|string|channel|module|native-export (not `ipc-channel`); `api` needs `entry_path`. The CLI has NO `--evidence-bundle` option, so `retained-evidence` refs fail with `evidence_integrity_mismatch`; pass the complete evidence record inline (file). Output is huge when graph is partial.
8. `--detail summary` output has top-level keys `summary` and `evidence_bundle` (not `normalized_result` directly): `d['summary']['normalized_result']['summary']`. Parent evidence id is `summary.normalized_result.parent_evidence_id`.
9. The summary does not list IPC channels, endpoints or web preferences. Those live in the bundle: `records[0].normalized_result.graph.nodes[]` with kinds browser-window, electron-preload, ipc-channel, ipc-handler, endpoint, context-bridge-api, native-addon, package; and `semantic_graph.nodes[]` kinds child-process, stdio, signal, config-source, literal. Each node: `observations[].properties`, `.evidence.location.value.{source,start.line}`. Extractor scripts: `q4.py` (graph kinds), `q7.py` (semantic kinds).

## 3. LosslessCut 3.70.2 (ev_1a24135891e0..., fuses ev_568194642eb7...)
Fuses [O] (sentinel offset 190843216, 9 fuses complete): RunAsNode off, EnableCookieEncryption off, NodeOptionsEnvironmentVariable off, NodeCliInspectArguments off, EmbeddedAsarIntegrityValidation ON, OnlyLoadAppFromAsar ON, V8 snapshot off, GrantFileProtocolExtraPrivileges ON, WasmTrapHandlers on. REA derived: inspect args and run_as_node "not_honored" (attach via --inspect/CDP would fail).
Security posture [O, ast-static-analysis exact, out/main/index.js:2412 BrowserWindow]:
- `contextIsolation: false`, `nodeIntegration: true`, `preload: ../preload/index.cjs`, `webSecurity: !isDev` (dynamic). `sandbox` not set (absence = unknown default; REA flags absence_means_default false).
- Preload (out/preload/index.cjs:7) calls `ipcRenderer.invoke("__electron_rpc__")`; contextBridge APIs = 0 (consistent with isolation off: the page world shares preload globals) [O count 0, I interpretation].
- Net effect [I]: any script injected in the renderer has Node access. Mitigated only by local content and the fuses above; renderer HTML origin not analysed [U].
IPC [O, exact literals]: main handle `__electron_rpc__` (:2646), `tryTrashItem` (:2548), `showItemInFolder` (:2556); main listen `apiActionResponse` (:2557), `appEvent` (:2372), `renderer-ready` (:2536), `setAskBeforeClose` (:2544), `setLanguage` (:2547). 8 channels, 9 operations, 0 sender validation observations. Only `__electron_rpc__` is paired with a renderer sender (paired=1) [O].
Network [O]: Express-like local API in main: `GET /`, `POST /action/:action` (:1519), `POST /await-event/:eventName` (:1526); literal `"127.0.0.1"` present [O] but the listen/bind call linking it is not shown, so binding scope of the API = [I] loopback, port [U]. Update/outbound: `fetch(getAppLinkUrl("latest-release"))` at :1573 (partial resolution) with literals `https://losslesscut.app`, `https://github.com/mifi/lossless-cut` [O]; `enableUpdateCheck` config read at :2588 [O]. Concrete release URL [U].
Config/env [O]: `config.json` (electron-store), `PORTABLE_EXECUTABLE_DIR` env (config-source :737), store keys darkMode, customOutDir, keyBindings, language, windowBounds, enableUpdateCheck, allowMultipleInstances.
Child processes: semantic family child-process = 0 relations, 2062 unknown [O]. Reason: ffmpeg is launched through a bundled library (execa) in unselected node_modules, not `node:child_process` in the 3 selected files. Observed instead: `resources\ffmpeg.exe` (540KB) and `ffprobe.exe` next to ffmpeg DLLs (avcodec-62 etc.) [O filesystem]; argv literals in main index.js: `-crf`, `-preset`, `-tune`, `libx264`, `ultrafast`, `zerolatency` [O]. Full argv construction for cutting/remux lives in the renderer bundle (`out/renderer/assets/index-BY3HDE42.js`, not analysed) [U]. Unclear whether `-crf` args are the HTML5-playback transcode [I].
Other [O]: 9 native-addon files (`@electron-internal/extract-zip/*.node`, all platforms; only win32-x64 is relevant) , coverage partial (2 of 2064 sources examined, 27,341 semantic unknowns).

## 4. Upscayl 2.15.0 (ev_40907c4e440a..., fuses ev_c7ab300ed3117...)
Fuses [O] (sentinel wire v1, only 7 fuses): RunAsNode ON, CookieEncryption off, NodeOptionsEnvironmentVariable ON, NodeCliInspectArguments ON, AsarIntegrity off, OnlyLoadAppFromAsar off, V8 snapshot off. REA derived: inspect/run_as_node "honored", integrity "not_enforced", app may load code outside asar. Weakest fuse posture of the two [I].
Security posture [O, export/electron/main-window.js:19]: `nodeIntegration: true`, `nodeIntegrationInWorker: true`, `webSecurity: false`, `preload: preload.js`; `contextIsolation` and `sandbox` not set (Electron default depends on version, not stated by REA) [U].
contextBridge [O]: `exposeInMainWorld("electron", {getAppVersion, getSystemInfo, invoke, on, platform, send})` (preload.js:16-20). `invoke/send/on` forward a caller-supplied channel name (dynamic) = generic IPC passthrough, so the effective surface is all main channels [I].
IPC [O]: 2 literal channels `get-app-version`, `get-gpu-info` (handle, main). 13 dynamic channels from `ELECTRON_COMMANDS.*` (STOP, OPEN_FOLDER, SELECT_FOLDER, SELECT_FILE, GET_MODELS_LIST, SELECT_CUSTOM_MODEL_FOLDER, UPSCAYL, FOLDER_UPSCAYL, DOUBLE_UPSCAYL, PASTE_IMAGE) registered at export/electron/index.js:78-87; values live in `export/common/electron-commands.js` [U: constants not resolved by REA]. 0 sender validation observations.
Child process [O]: `spawn` at export/electron/utils/spawn-upscayl.js:8, command null / argv_count null / stdio dynamic / env not supplied, kill with SIGTERM at :14. Command and argv are built elsewhere (`utils/get-arguments.js`, models and paths from renderer IPC) [U]; binaries on disk [O]: `resources\bin\` and `resources\models\`. REA does not resolve the executable name statically here.
Network [O]: no http(s) literals in the 34 parsed first-party files. Updater: `resources\app-update.yml` = provider github, repo `upscayl` (owner string in file) [O, read from file]; `commands/auto-update.js` uses electron-updater [I]. Only 3 "endpoint" nodes, all electron-settings keys (false positives of the endpoint heuristic) [O].
Config/env [O]: `NODE_ENV` (index.js:48), `npm_package_version` (get-device-specs.js:48), electron-settings keys folder-bookmarks, custom-models-bookmarks.
Coverage: 34 of 13,181 sources examined, partial; child-process/other families have 5,026 omitted "incomplete-module" unknown occurrences each (truncated:true).

## 5. Lessons for the agent
Best command order:
1. `inspect-electron-fuses <exe>` (8 s). Read `runtime_implications` first (inspect/RunAsNode honored or not decides whether runtime attach is possible).
2. List the asar header yourself (python, no REA) to find first-party entries (package.json main, preload, main-window, ipc/ files). Skip node_modules, renderer chunks, source maps unless the question needs them.
3. `analyze-javascript-application <asar> --detail summary --evidence_output <NEW file> --source-path ... ` with `2> stderr.log`; write stdout to a BOM-less file. Run in background if >2 min (Upscayl 222 s; tool call limit 10 min).
4. Do not trust the summary for answers. Parse `records[0].normalized_result.graph.nodes` (browser-window, context-bridge-api, ipc-*, endpoint, child-process) with a small script; use `inspect-analysis-view` only with explicit `--evidence-bundle` and a precise view (`javascript-facts` + `property_keys`, `javascript-routes`).
5. `trace-application-feature` only after narrowing the seed (node-id or precise string), because it needs the full record inline and returns the whole partial graph.
6. Cross-check non-JS facts directly: `resources\` listing (ffmpeg.exe, bin\, app-update.yml). These are legitimate "observed" evidence but not REA evidence; label them.
Pitfalls:
- A scoped run proves nothing about unselected files: say "0 child-process relations in selected sources", not "app spawns nothing". Library-wrapped spawns (execa) and dynamic argv appear as unknown/null.
- "endpoint" nodes include config keys and Express routes; check `mechanism`/`interpretation: candidate` and confidence low before calling them network endpoints.
- Absent webPreferences (contextIsolation/sandbox) = unknown default, not false.
- `electron` fuse sentinel can have 7 or 9 fuses; missing ones are unknown, not disabled.
- IDs: `ev_...` of bundle records stay valid only inside that bundle; always keep the bundle path in the report.
- Do not rewrite JSON in place; do not retry the unchanged failing call (see invalid_request details.issues for the valid enum values).
