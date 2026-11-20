# Golden Dragon — Video Style & Font Studio (integration staging)

This folder is a non-destructive integration index. Existing engines remain at their original runtime paths; no binary font files are copied without license verification.

## Required workflow
1. Analyze the reference and create a style record with palette, characters, motion timing, typography, preview and provenance.
2. Render video, inspect decoded frames and verify MP4 output. Do not treat a render command as proof of quality.
3. After each completed video, ask the owner: **«تحب تحفظ الستايل؟ وباسم إيه؟»**. Do not save under an invented name.
4. When the owner confirms a name, save a named record under `studio/styles/<slug>/` with STYLE.md, style.json, preview image and render settings. Preserve provenance and licensing.
5. Reuse a saved style by name, with stable character and palette descriptions.

## Existing engines to reuse, not duplicate
- `runtime/library/motion-cartoon/` — 2D character animation and render checks.
- `runtime/engine/skills/reference-lock/` — visual reference lock.
- `runtime/engine/tools/fonts/` — font recovery and verification.
- Other source repositories: `100-superskills/skills/kosif-mimic/` (reference analysis), `kosif-tool` owner-upload review (motion methods).

## Status
This is an integration specification and inventory, not a claim that a new executable router or finished video is installed. Source engines must be inspected and tested before adapters are added.
