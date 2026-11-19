# Blender Pro × Black Dragon — integration v10.5.0

The user's Blender Pro source is bundled under `tools/blender-pro/`. Original operation modules and launcher are preserved except removal of Python bytecode caches; `runner.py` has a path-safety/portability patch to place VSE and Grease Pencil outputs in the chosen `--out` folder, and bundled example files use relative media placeholders instead of a machine-specific Windows user directory. Includes JSON recipes, a Blender headless runner, twelve operation modules (discovered statically), readme, and tests.

**Entry point**: `python scripts/dragon.py tool blender-pro doctor|ops|validate|plan|render|verify`.

- `doctor` performs static dependency checks, including whether `blender`, `ffprobe`, and Arabic text shaping imports exist. It does not render or install anything.
- `ops` parses the bundled OPS mapping via AST and lists operations without importing Blender/bpy. Counts are *static source entries*, not verified run results.
- `validate RECIPE.json` validates JSON structure and operation names; does not prove a render.
- `plan PRESET` displays a validated example recipe and source path without rendering (option `--out` to write a copy, never overwrites).
- `render RECIPE.json --out DIR --execute [--preview]` explicitly invokes Blender if installed. Use preview first, visually inspect contact-sheet then choose final. Without `--execute`, dry-run only. No automatic installation or paid calls. Don't feed external untrusted recipes directly into Blender without inspection.
- `verify FILE` makes a read-only SHA256 + media probe report and checks the output exists. It does not replace visual review.

**Scope**: Blender itself is not bundled. The source documents Blender 5.2 and 139 ops; counts are evaluated against the actual bundled source and not considered proof of compatibility with the user's installed Blender. No Blender was available on the build machine, so no 3D render claims or frame QA of Blender output should be made.

**Ownership**: `old_note.txt` contained only `old` and `script.md` contained only `# سكريبت`; neither supplied executable features. The other archive roots (`synced`, app-specific tool builders, unrelated connector skills) are intentionally not installed or made part of the automatic runtime.

**Example inputs:** the VSE/green-screen/trace examples need media you supply in `tools/blender-pro/examples/media/` (or edit the recipe to point to media you own). No example stock footage was provided.
