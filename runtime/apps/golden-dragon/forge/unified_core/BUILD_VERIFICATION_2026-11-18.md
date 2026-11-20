# Golden Dragon Unified Core — isolated Windows build verification

Date: 2026-11-18  
Device: DESKTOP-EUGN3DS (Windows 11, Python 3.12.10, PyInstaller 6.22.3)  
Branch: `feat/golden-dragon-runtime-ledger-20261118`

## What actually succeeded

- Generated the Golden Dragon app twice in temporary directories, including once **without** the external `analysis/` folder, using bundled `fusion/thinking.json` for the 22 thinker tools and eight protocol stages.
- Recovered locally missing forge modules and patches from the same GitHub feature branch. Source-file SHA-1 Git blob IDs were validated before staging.
- 56 legacy application tests passed against the newly generated application.
- 17 unified-core and bundle-verifier unit tests passed. These are not 1,101 runtime capability tests.
- Created an isolated **Windows GoldenDragon.exe** with PyInstaller. No installer or Desktop shortcut was created or updated.
- Verified the resulting EXE's embedded PyInstaller module archive and `_internal` data offline, without launching the application.
- Checked the installed original EXE with the same stricter verifier. It failed exactly because it lacked `gd_runtime`, `capability_ledger`, and `audit_tree`, demonstrating the verifier distinguishes versions.

## Binary evidence

| Fact | New isolated EXE | Original installed EXE |
|---|---:|---:|
| Location | `%TEMP%/gd-unified-selfcontained-20261118/التنين الذهبي/isolated-package/dist/GoldenDragon/GoldenDragon.exe` | `%USERPROFILE%/GoldenDragon/GoldenDragon.exe` |
| Bytes | 141,238,538 | 141,218,645 |
| SHA-256 | `17297ffc9b7d301564b387a4811d484df928a93d308c77289f282097200cf950` | `33405ab2e133c0d8814e82ef1d12cd1f69373b6e77efd07f2bf1e3e1a654ab6e` |
| PYZ module count | 22,480 | 22,475 |
| Required native-core modules missing | 0 | 3 |
| Data files missing | 0 | 0 |
| Fusion units / recipes | 1,101 / 42 | 1,101 / 42 |
| Strict verifier exit | 0 | 1 (expected) |

**Important:** 1,101 is a number of catalog entries, *not* independently verified working capabilities. The new build contains 5 more Python archive modules than the original, which does not prove five added functional capabilities.

The collected output folder is approximately **2.65 GB** (includes many Python binary dependencies), much larger than the EXE alone. This binary remains on the user's Windows PC; it has **not** been uploaded as a GitHub release.

## Warnings and remaining risks

During packaging, PyInstaller warned about optional modules and unresolved native DLLs, including `tbb12.dll` (Numba) and CUDA libraries. These issues require targeted runtime tests if a corresponding capability needs them.

PyInstaller reached `Build complete` after around 2,684 seconds. The package's structural verification passed, but **the new GUI EXE has not been started or exercised**. No Ghidra decompilation or end-to-end video rendering test was performed as part of this isolated build.

Regeneration still depends on Golden Bird and White Bird forge code. The work so far unifies the diagnostic entrypoint and bundles it directly; **it is not a total fusion of all project engines**.

## Safety and handoff

- The original installed EXE SHA-256 was checked after packaging and is unchanged.
- The local `main` checkout was clean (`git status --porcelain` returned no changes).
- All new code is restricted to the feature branch.
- For future builds use `forge/unified_core/build_isolated.ps1`, which has passed PowerShell syntax and dry-run checks and rejects output outside `TEMP`. The successful full package was produced with the same isolated PyInstaller arguments in a direct PowerShell call; the wrapper itself has **not** yet completed a full build.
- Do not install this build as production until the GUI, runtime dependencies, and representative engine operations pass integration tests.

## Next verified milestone

Launch with a *separate* Windows profile/config sandbox and no shared service credentials, then test app startup, `fusion audit`, routing, REA, a video render, and a negative rollback scenario. Establish an explicit runtime capability coverage matrix before claiming all engines operational.
