# Golden Dragon: native capabilities, startup investigation, and safety — 2026-11-18

Branch: `feat/golden-dragon-runtime-ledger-20261118`; draft PR #23. **No merge or production install.**

## Verified implementation milestones on DESKTOP-EUGN3DS

1. **Windows EXE build:** Earlier isolated PyInstaller build created an executable of 141,238,538 bytes, SHA-256 `17297ffc9b7d301564b387a4811d484df928a93d308c77289f282097200cf950`. A structural PyInstaller check passed with 22,480 embedded Python modules and zero missing mandatory modules/data files.
2. **GUI smoke test:** Launched *that earlier build* with isolated TEMP-based HOME/APPDATA/LOCALAPPDATA settings and removed model API keys from the child process environment. A genuine window titled `التنين الذهبي` appeared at approximately 135 seconds, with `start` in the isolated lifecycle log and no startup crash entry. The harness terminated only its own test process afterward. **No GUI interaction or end-to-end user task was verified**.
3. **Import-time profiling:** Normal generated app module import measured ~26.4 s, mostly the `anthropic` SDK import (~24.7 s). After a forge change to lazy-load that SDK, app module import measured 0.978 s on one run and 0.847 s on another; `anthropic` was absent from `sys.modules` at the end of initialization. First actual attribute access to `anthropic.Anthropic` loaded the real SDK in ~13.4 seconds. This is **source module import timing, not a benchmark of a rebuilt EXE**. PyInstaller's generator and the safe isolated builder explicitly include the hidden `anthropic` module.
4. **Media metadata:** The native `GoldenDragonCore` and generated `fusion probe_media` route used the installed FFprobe to analyze a real WAV and a real synthetic MP4 (2 seconds, 320×180, 24 fps, AAC audio), without opening remote URLs or transcoding the input.
5. **Reverse engineering:** The generated `fusion inspect_binary_imports` route used real REA CLI on the original installed GoldenDragon.exe and returned a concrete `evidence_id`, 5 DLLs and 150 imported functions with complete parser coverage. The source binary was never executed during inspection. REA evidence is static import metadata, not Ghidra decompilation or proof imports are called at runtime.
6. **Media conversion:** New `fusion transcode_media` route converted a local WAV to MP3 via the installed FFmpeg; verified output existence, codec, and untouched input. The core also has tested profiles `mp4-compatible` and `mp4-h264` and uses fresh TEMP output directories, fixed codecs, no unrestricted shell, and a local-only protocol whitelist. A unit integration test converted a short synthetic video+audio MP4.

## Validation (latest source checkout)

- Unified-core tests: **32 passed**, after regeneration with the latest native FFmpeg/REA/lazy-loading changes.
- Legacy application regression tests: **56 passed** on the final regenerated media-transcode source (60.10 seconds), after the 32 unified-core tests passed. **88 total passing test cases** across the two suites, with no failures.
- Source regeneration: succeeded in TEMP with 39 files, preserving 1,101 indexed catalog units, 42 recipes, and 65 lessons. This catalog is **not** 1,101 executed capabilities.
- Installed EXE SHA-256: `33405ab2e133c0d8814e82ef1d12cd1f69373b6e77efd07f2bf1e3e1a654ab6e`; do not replace it without explicit later go-ahead.

## Pending / not verified

- The *latest* FFprobe/FFmpeg/REA and lazy-import changes are in source and feature branch; **the earlier isolated EXE has not been rebuilt with these new changes**.
- There is still no proof all indexed skills and external engines execute. Some external programs are absent from PATH.
- One-off GUI window detection does not establish a healthy chat service, renderer, user interactions, settings isolation across the complete runtime, or a working model call.
- First cold start of the *earlier* isolated EXE was approximately 135 seconds. New lazy loading might reduce some of that cost, but a repeat full binary build and controlled GUI startup benchmark are needed.
- Regeneration still uses Golden Bird/White Bird forge sources.
- Earlier packaging reported missing optional CUDA DLLs and `tbb12.dll` for a Numba component; targeted runtime coverage is needed.
- Direct end-to-end video editor UI, Blender animations, Ghidra decompilation and full synthesis of all project engines remain separate milestones.

## Next technical gates

Re-run the full legacy test suite, build the latest EXE *only* inside TEMP with `build_isolated.ps1`, run `verify_unified_bundle.py`, smoke GUI startup on a fresh profile, check a sample model request only with explicit owner credentials and permission, then test genuine export/render workflows. Remain on draft PR #23 until reviewed.
