# Golden Dragon capability evidence ledger

This is an **experimental, passive diagnostic** for the ongoing unified-core rebuild. It is not a completed fusion of engines or a rebuilt Windows EXE.

From `apps/golden-dragon`:

```powershell
python -B forge/unified_core/capability_ledger.py --index forge/data/fusion/index.json --recipes forge/data/fusion/recipes.json --out "$env:TEMP/gd-capability-ledger.json"
python -B -m pytest forge/unified_core/tests/test_capability_ledger.py -q
```

The script reads catalog JSON and optionally writes a **new** report; it refuses to overwrite reports. It never imports target modules, launches programs, calls MCP, or changes the built app.

**Evidence rules:** `status: ok` is an index assertion, not a runtime test; a skill's source file and a program on PATH prove only passive presence. Recipe references are checked, but successful execution of every recipe still requires separate integration tests.

Verified in this development session: four synthetic unit tests passed and one synthetic CLI smoke run passed. **The real 1,101-unit catalog was not scanned with this new script yet** because the remote desktop stopped responding. The legacy app's 50 smoke/routing tests passed previously on its correct original Windows project path. No edits to `main` or installed `GoldenDragon.exe`.

## Native unified diagnostic core (experimental)

`runtime.py` provides one direct Python interface: `GoldenDragonCore.execute(...)`. Its supported read-only operations are `catalog.audit`, `source.audit`, `binary.pe_header`, and `audit` (combined stages). The PE reader uses Python's standard library, not MCP.

From `apps/golden-dragon` on a machine with the project checkout:

```powershell
python -B forge/unified_core/runtime.py audit --root . --index forge/data/fusion/index.json --recipes forge/data/fusion/recipes.json --binary "$env:USERPROFILE/GoldenDragon/GoldenDragon.exe"
python -B -m pytest forge/unified_core/tests -q
```

`forge/make_golden_dragon.py` in this feature branch now copies the three core files into the future generated application and registers **fusion action `audit`** for a read-only catalog check. It also adds the PyInstaller hidden imports.

**Verification performed on DESKTOP-EUGN3DS, 2026-11-18:** the new ledger ran directly against the 1,101-unit / 42-recipe catalog and found zero broken recipe references; the combined core analyzed the 77 files in `apps/golden-dragon` and inspected the installed EXE's PE headers with a SHA-256 matching REA; a memory-only simulation of the generator's `fusion_dispatch({'action':'audit'})` returned the real catalog report successfully. Generator Python syntax, embedded dispatch syntax and the added bundle copy/import statements were independently checked. No installed app or `main` code was changed.

**Not yet verified:** a full regenerated GoldenDragon app, PyInstaller packaging of the new modules, actual runtime behavior of 1,101 indexed units, Ghidra decompilation, or an MP4 render. The catalog's `ok` label cannot substitute for runtime tests.

## Reproducible isolated Windows regeneration — 18 November 2026

The feature branch was checked against the owner's real Windows machine without touching the installed application or `main`.

- A private TEMP-only source regeneration succeeded twice: 39 generated app files with the existing 1,101 indexed units, 42 recipes, and 65 lessons.
- The first regeneration exposed a pre-existing unimplemented `merge_books` import; the original source tree contained no `thinking_books.json`. The generator now preserves the 22 existing thinker tools, and **fails closed** when a book overlay does exist but its merge implementation is missing.
- The generator uses bundled `forge/data/fusion/thinking.json` as fallback when `analysis/thinking_toolkit.json` is absent. The two source JSON files were confirmed equivalent as parsed data (22 tools and 8 protocol stages).
- The second regeneration succeeded with **no `analysis` folder**, although the Golden Bird and White Bird upstream forge sources are **still needed during regeneration**. This is not yet a fully independent build.
- All **56 legacy app tests** passed against the second generated app (including the routing evaluation).
- All **13 new unified-core/portable-thinking tests** passed.
- A separate PyInstaller build was started under the TEMP lab only; do not infer packaging success from the successful source-regeneration tests.

### Safe packaging

The normal generated `app/build.ps1` installs into `%USERPROFILE%/GoldenDragon` and modifies the user's Desktop shortcut. **Do not use it for this isolated trial.** Instead, from a newly generated app checkout:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File forge/unified_core/build_isolated.ps1 -DryRun
powershell -NoProfile -ExecutionPolicy Bypass -File forge/unified_core/build_isolated.ps1
```

The isolated builder refuses destinations outside `TEMP`, refuses overwriting existing output, and does not install to the user home or change Desktop shortcuts. Its PowerShell syntax and `-DryRun` were verified on the owner's Windows device.

## First dependency-breaking standalone build path

The new `build_standalone.py` composes source from **Golden Dragon's own versioned `app/` baseline**, with the current native unified core and updated `fusion` actions, without importing or invoking `make_golden_bird.py` or `make_white_bird.py`.

Run from the repository checkout, with a **new** output directory inside the system TEMP:

```powershell
python -B apps/golden-dragon/forge/unified_core/build_standalone.py --out "$env:TEMP\gd-standalone-trial" --dry-run
python -B apps/golden-dragon/forge/unified_core/build_standalone.py --out "$env:TEMP\gd-standalone-trial"
```

The composition explicitly refuses to overwrite an existing destination. It does not install an EXE and excludes the legacy auto-installing `build.ps1` from the generated app. The only packager it carries forward is the guarded `forge/unified_core/build_isolated.ps1`, which packages inside TEMP.

**Automated verification:** GitHub Actions run `Golden Dragon standalone source build` #4 (ID `44339824543`) succeeded on the feature branch with **6/6 tests passing**, including composition of the *real versioned Golden Dragon source*. The separate existing core integration workflow on the same commit passed as well.

**Limit:** This is a reproducible standalone **source composition** milestone, not a verified Windows EXE rebuilt from this new path and not proof that the sibling engines' runtime capabilities have all been absorbed. It freezes the current Golden Dragon-owned source baseline until remaining source layers are individually consolidated.
