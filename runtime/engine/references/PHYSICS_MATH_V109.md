# Physics & Math — Black Dragon v10.9.0

The supplied archive `physics-math(1).zip` contained two substantive files: `physics-math/SKILL.md` and the stdlib-only `physics-math/scripts/phys.py`. It did **not** contain Blender, a physics renderer, a calibrated camera profile, or a media-analyzer. The original files are retained verbatim under `skills/physics-math/upstream/`; the guarded executable copy is `skills/physics-math/scripts/phys.py`.

## 18 numeric command families
`calc`, `convert`, `shape`, `material`, `motion`, `fall`, `projectile`, `bounce`, `spring`, `ease`, `camera`, `tc`, `speed`, `beats`, `frame`, `audio`, `track`, `scale`. They output numeric JSON and optionally keyframe CSV/JSON. Counting 18 command families does not mean 18 external applications were installed.

## Integration and repairs
- `scripts/dragon.py tool physics ...` dispatches to `tools/physics_math/bridge.py` and calls the corrected source in-process, without network calls or paid APIs.
- An AST-only expression evaluator replaces the original `eval`, whitelists math operators/functions, and caps exponentiation, expression complexity, and non-finite results.
- Export paths are exclusive-create, no overwriting existing files; if `--receipt` is present, the adapter stores the result, SHA-256 source hash and exported-file hash. `verify` checks local integrity.
- Bounded parameters (FPS, duration, beats, motion keyframe count, spring integration steps, and numeric arguments). Invalid inputs return explicit error rather than crashing or clobbering data in the tested cases.
- Added entry in `app/data/own_tools.json` and static entrypoint in `app/dragon/capabilities.py`; keywords in Arabic and English route relevant tasks. Registration is not evidence of execution in other sessions.

## Formula quality and limits
- `fall`: idealized constant-gravity motion by default; its optional terminal-velocity model is a simplification, not a full aerodynamics solver.
- `bounce`, `spring`: simple visual motion curves without measured damping/contact properties.
- `camera`: idealized thin-lens geometry; account for real sensor dimensions and lens characteristics.
- `tc`: non-drop only. 29.97/59.94 drop-frame projects need a dedicated SMPTE converter.
- `audio`: gain math for supplied LUFS, *not* an audio loudness measurement or compliance test.
- `frame`: safe margins are illustrative; check the target platform at delivery.
- Pixel tracking assumes a known scale on the same depth plane.

## Validation
Run `PYTHONPATH=app python -m pytest -q app/tests/test_v109_physics_math.py` from the bundle root. Use `tool physics doctor` for source presence plus 2 numerical smoke checks. Technical QA and aesthetic QA still belong to the video pipeline. This bridge never calls Blender, FFmpeg, social APIs, GitHub, or a paid generator.
