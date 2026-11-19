# What already existed in Red Dragon, and what this skill adds (survey of 2026-11-13)

| Component | Kind | Relevant to this skill | Used? |
|---|---|---|---|
| `engine/skills/paint-studio` | executable (Pillow, numpy, OpenCV, rembg; SD-Turbo venv for AI paint; some Windows-only commands) | flood-fill colour regions, AI subject mask, line art, inpaint; raster only | no: per-frame colour clustering and vector output were missing; nothing duplicated |
| `engine/app/engines/shadow_theatre` | executable package (numpy, Pillow, ffmpeg) | 10-joint skeleton, pose blending, keyframes, cycles, 2-bone IK, SDF figures, MP4 encode | idea of a pose-channel skeleton; this skill's front-view rig is separate (different joint set, flat-colour cut-out drawing) |
| `engine/skills/teardown` | executable (Node + Playwright + ffmpeg; Python stdlib) | deterministic render(t) → MP4, beat analysis, contact sheets, loudness | the "frame = pure function of t" rule (reference renderer and animator follow it) |
| `engine/skills/physics-math` | executable (stdlib) | easing, springs, beat/frame maths | timing conventions (no new easing table written) |
| `engine/tools/reel_dna` | executable (ffmpeg for render) | time→frame normalisation, sha256 provenance | the provenance habit: the memory stores the source video's sha256 |
| `library/blender-character-rigging` | executable inside Blender 5.2 only | rig rules: pivots, `.L/.R`, DEF/MCH layers, validation | its rules: joints at pivots, `.R/.L` naming, chains, a validation step (the tests) |
| `engine/tools/framecheck`, `engine/app/engines/qa.py` | executable | pops, freezes, black frames, frame counts | delivery checks (with dragon-genius `media_gate.py`) |

Gaps this skill fills (none of the above did them): per-frame colour-cluster segmentation, part tracking with
occlusion and merge handling, joints from colour junctions and limb centre lines, face measurement, SVG redraw with a
measured error, motion periodicity, and a reusable per-character memory that new scenes are drawn from.
