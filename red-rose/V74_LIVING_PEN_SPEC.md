# V74 «القلم الحي» (Living Pen) — specification (2026-11-28, not built yet)

Goal: one physically based drawing engine inside Red Rose that can draw ANY style (calligraphy, ink, watercolour,
pencil, charcoal, oil, chalk, gouache, comic line, sumi-e, engraving…) stroke by stroke, then animate the drawn
scene while the strokes stay coherent. The owner will draw every future style with it. Original code only;
no paid generators; runs on Windows CPU (no GPU assumed); deterministic per frame.

## Architecture (package `living_pen/` inside red-rose, CLI `rose.py pen …`)
| Module | Responsibility | Core math |
|---|---|---|
| `tools.py` | Tool models: reed qalam (cut nib angle/width), pointed pen, round/flat brush (bristle bundle), pencil (graphite grain), charcoal, chalk, airbrush, palette knife | Cosserat rods / mass–spring bristles, contact with paper, pressure→footprint |
| `media.py` | Ink/paint/pigment: viscosity, wetness, deposition, pickup, drying; pigment mixing by Kubelka–Munk (per-wavelength K/S, ≥16 bands) | Shallow-water/thin-film flow, KM theory, spectral→sRGB |
| `paper.py` | Paper/canvas height field, fibres, sizing, absorbency; capillary wicking, edge darkening, granulation, back-runs | Procedural noise + anisotropic diffusion (Fick), percolation |
| `calligraphy.py` | Arabic scripts (naskh, thuluth, diwani, ruq'ah, kufi): letter skeletons, Ibn Muqla dot-proportions, baseline/ascender rules, joining forms, tashkeel placement, composition solver | Constraint satisfaction + nonlinear optimisation (SLSQP/augmented Lagrangian) |
| `strokes.py` | Stroke data model: centreline spline (Catmull-Rom/B-spline), pressure, tilt, speed, tool, pigment, time stamps | Arc-length parameterisation, curvature, minimum-jerk timing |
| `plan.py` | Stroke ordering like a human artist (layering, dark→light or light→dark per medium, calligraphic stroke order) | Graph ordering, TSP-like heuristics |
| `inverse.py` | Inverse painting: find strokes that reproduce a target image/vector/word under the physics | Differentiable rasterisation, Adam/L-BFGS, coarse→fine, perceptual + edge losses |
| `animate.py` | Animate the drawn scene: strokes bound to a deforming mesh/skeleton or optical flow; temporal coherence (no swimming/flicker); re-ink only what must change | Optical flow, ARAP deformation, Lagrangian stroke advection, stroke lifetime |
| `styles/` | Style = tool preset + media + paper + stroke grammar (density, direction, hatch angles, randomness) as JSON | Parameter spaces; style transfer by fitting parameters to a reference |
| `render.py` | Frame renderer (numpy, optional numba), tiled, checkpointed, resumable; ffmpeg encode | Deterministic RNG per (frame, stroke) |
| `audio_sync.py` | Word onsets (whisperx JSON) → stroke start times; voice energy → pressure/speed | Time warping, envelope following |

## Capabilities the owner asked for
- Draw any style from a style JSON; mix styles per layer (ink outline + watercolour fill + pencil shadows).
- Write Arabic calligraphy in classical proportions, compose new layouts (not copied), animate it being written in true stroke order, synced to the spoken word.
- Draw from a photo/frame (inverse painting) and from vector art; draw characters such as الراجل والست in any style.
- Animate after drawing: characters move, camera moves, rain/petals, while strokes stay attached and stable.
- Timelapse mode (the drawing being made), live mode (the drawn world moving), and both in one film.
- Export: MP4 (H.264 + AAC), PNG sequences, layered stroke JSON for re-render, SVG for line styles.

## Stages (each a PR with tests; owner reviews a sample before the next)
1. Strokes + qalam: one reed-pen stroke with nib-angle width law; sample vs. reference photo of a real stroke.
2. Media + paper: ink deposition, wicking, edge darkening, drying; KM mixing of 3 pigments.
3. Calligraphy: 10 naskh letters with Ibn Muqla proportions + joining; one word composed and written in order.
4. Brush + other tools: bristle brush, pencil, charcoal; 5 style presets.
5. Inverse painting: reproduce a 256×256 target with ≤N strokes; loss curve and side-by-side.
6. Animation: strokes on a deforming mesh; flicker metric under threshold; 3-second animated sample.
7. Audio sync + full film pipeline; integrate with `rose.py direct`, `continuity check`, `styles` registry.

## Acceptance (measured, not taste only)
- Calligraphy: letter heights/widths within ±0.25 dot of the Ibn Muqla table; joins continuous (C1).
- Ink mass conservation error < 1e-6 relative; pigment mixing matches KM reference values (unit tests).
- Inverse painting: SSIM / LPIPS-proxy vs. target reported; stroke count reported.
- Animation: stroke-position jitter between frames below a set pixel threshold on static regions.
- Determinism: same frame → same SHA-256; resumable renders.
- Word onset vs. stroke start ≤ 1 frame. Media verify on every MP4.
- Every module: unit tests with known answers; `python -X utf8 -W error::ResourceWarning -m unittest`.

## Constraints
Python 3.12, numpy (numba optional, must fall back), Pillow, ffmpeg; no network at render time; no GPU
assumed; Windows paths and UTF-8 Arabic; fonts only from the owner's approved libraries when text is set in
type (calligraphy is drawn, not typed); dua work keeps the mandatory dua footage/font gate.
