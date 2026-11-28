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

## Theory stack (owner request 2026-11-28): every theory maps to a pen capability and a test
### Light (how marks look)
| Theory | Pen capability | Test |
|---|---|---|
| Rendering equation, energy conservation | Lit paper/canvas, raking light that reveals texture | Albedo ≤ 1; white furnace test |
| Microfacet BRDF (GGX) + Fresnel (Schlick) | Wet-ink sheen, varnish, gold-leaf highlights that move with light | Reciprocity; Fresnel at 0°/90° |
| Thin-film interference | Iridescent ink, oil-on-water, mother-of-pearl | Colour vs. film thickness vs. analytic curve |
| Subsurface scattering (dipole/diffusion) | Glow through paper, skin in portrait styles | Diffusion profile integrates to 1 |
| Spectral rendering + CIE 1931 → OKLab | Accurate pigment colours, dispersion, metamerism | Known swatches ΔE2000 < 2 |
| Atmospheric scattering (Rayleigh/Mie) | Sky, haze, depth in landscape styles | Sky gradient vs. reference sun angles |
### Physics (how marks are made)
| Theory | Capability | Test |
|---|---|---|
| Cosserat rods / elastic bristles, Hertz contact | Brush splay, dry-brush, pressure footprints | Static deflection vs. beam formula |
| Thin-film lubrication + Navier–Stokes (shallow water) | Paint flow, puddles, back-runs | Mass conservation; flat-pool steady state |
| Lucas–Washburn capillarity, anisotropic diffusion | Ink wicking along paper fibres | Penetration ∝ √t |
| Evaporation + sedimentation | Edge darkening (coffee ring), granulation | Ring forms only with pinned edges |
| Non-Newtonian (shear-thinning) rheology | Oil impasto, palette-knife ridges | Flow curve vs. power law |
| Height field + normal mapping | 3D paint relief lit by any light | Normal unit length; relief preserved under resize |
| Spring–damper dynamics | Secondary motion: hair, cloth, follow-through | Damping ratio gives expected overshoot |
### Mathematics (shape, motion, optimisation)
| Theory | Capability | Test |
|---|---|---|
| Differential geometry of curves (Frenet, G2 continuity), Euler spirals (clothoids) | Beautiful strokes with smooth curvature, calligraphic swashes | Curvature continuous at joins |
| B-splines/NURBS, arc length | Exact stroke paths, uniform speed | Arc length vs. analytic |
| Minimum-jerk / minimum-snap trajectories | Human-like hand speed and stroke timing | Jerk integral minimal vs. linear timing |
| Optimal transport (Sinkhorn), Hausdorff distance | Morph one drawing into another; match cuts by shape | Mass error; symmetric distance |
| Variational methods, Poisson/biharmonic solves | Smooth fills, shading from sketches, seamless edits | Residual below tolerance |
| Fourier / wavelets, Perlin/Worley/fBm | Paper grain, canvas weave, stroke jitter with controlled spectrum | Power spectrum slope |
| Constraint optimisation (augmented Lagrangian) | Calligraphy proportions, layout composition | Constraints met within tolerance |
| Differentiable rendering + Adam/L-BFGS | Inverse painting; fit any style to a reference | Loss decreases; gradient check vs. finite differences |
| As-rigid-as-possible deformation, optical flow | Drawn characters move; strokes stay attached | Jitter metric on static regions |
| Lie groups SO(3)/SE(3), quaternion squad | Smooth camera over the drawn world | No gimbal flips; continuous angular velocity |
### Art, directing and montage (why it reads well)
| Theory | Capability | Test |
|---|---|---|
| Value structure (notan), lost-and-found edges | Strong silhouettes; edges sharp only where the eye should go | Value histogram has ≥3 clear groups |
| Colour harmony in OKLab (analogous, complementary, triad) | Palettes per style and per beat | Hue angles match the chosen scheme |
| Composition: thirds, golden ratio, leading lines, Gestalt | Auto-placement of subject and text | Subject centroid on a power point (tolerance) |
| 12 animation principles in math (volume-preserving squash & stretch, arcs, ease, overlap) | Living characters | Area preserved within 2% while squashing |
| Kuleshov effect, Eisenstein montage types (metric, rhythmic, tonal, intellectual) | Cut decisions inside `rose.py direct` | Each cut labelled with its montage type |
| 180° rule, eyeline and match cuts, shot-size grammar | Continuity across drawn shots | `continuity check` passes; match-cut shape distance below threshold |
| Rhythm: cut on beat/word onsets, breath pauses | Edit synced to voice and music | Onset offset ≤ 1 frame |
### Style = parameters
A style is a JSON vector (tools, media, paper, stroke grammar, palette, light, motion grammar). Styles mix by
interpolating these vectors; a new style is learned by fitting the vector to reference images with the
differentiable renderer (stage 5). Each theory above is added in the stage that needs it, with its test.

## Role in Red Rose (owner decision 2026-11-28)
The Living Pen is Red Rose's primary drawing/visual tool: for any task that draws, paints, writes calligraphy,
designs a frame or animates drawn material, Claude plans with `direct`/`styles`, then draws with `rose.py pen`,
alongside the other Red Rose capabilities (montage-code, continuity, media-contract, audio, dua gate). Until a
stage is built and tested, Claude uses the existing engines for that need and says so; it never claims a pen
stage works before its tests pass.

## Self-learning and self-improvement (stage 8, built on V64 `evolution`)
Loop after every pen job, local only:
1. Measure: every acceptance metric of the job (ΔE, proportion error, flicker, onset offset, render time,
   inverse-painting loss) is written to `~/.red-rose/pen/runs.sqlite3` with the job's parameter vector and hashes.
2. Learn from feedback: the owner's verdict (accepted / rejected + reason) is recorded with
   `rose.py evolution record`; rejections reopen any related approved lesson.
3. Self-tune parameters (allowed automatically): Bayesian optimisation / CMA-ES over style and tool
   parameters inside declared bounds, maximising the measured metrics on a fixed benchmark set; a new preset
   is kept only if it beats the current one on the benchmark without breaking any gate.
4. Grow the style library: a style the owner approved becomes a named preset (JSON vector + reference
   thumbnails + metrics); styles are fitted from new references by inverse rendering.
5. Self-improve code (proposal only): when a metric plateaus or a failure repeats, the pen writes a
   diagnosis, a minimal reproduction and a proposed patch with new tests into `~/.red-rose/pen/proposals/`.
   Code changes are never applied automatically: they need passing tests, regression of the full suite and the
   owner's OK (same rule as V64: no auto-promotion of code).
6. Benchmarks are frozen: the evaluation set and its expected values cannot be edited by the tuning loop
   (prevents "learning" by moving the target); any benchmark change is a reviewed commit.
7. Reversible: every promoted preset keeps its predecessor; `rose.py pen rollback PRESET` restores it.
Tests: tuning never leaves bounds; frozen benchmark hash checked before each run; a worse candidate is never
promoted; proposals never modify code on disk; rollback restores the exact previous vector.

## Numerical foundations from Atkinson & Han, *Theoretical Numerical Analysis* (3rd ed., 2009)
Owner-supplied copy, indexed locally only: `rose.py intake search "…" --label atkinson-han-numerical-analysis-2009`
(chapter files; read the original section before implementing; summarise, never copy text into the repo).
| Ch. | Topic | Pen module → what it guarantees | Test |
|---|---|---|---|
| 1 | Normed, Banach, Hilbert, Hölder, Lp spaces | Strokes, pressure and pigment fields as functions in stated spaces; every error reported in a named norm (L2, L∞, H1) | Norm helpers vs. analytic values |
| 2 | Operators, Riesz, adjoints, geometric-series theorem, Fredholm | `inverse.py`: gradients via adjoint operators; perturbation bound decides when a linear solve is safe | Adjoint identity ⟨Au,v⟩=⟨u,A*v⟩ to 1e-10 |
| 3 | Hermite/piecewise interpolation, best approximation, projection on convex sets, orthogonal polynomials, uniform error bounds | `strokes.py`: C1 Hermite stroke paths with proven error bound; pressure profiles in Legendre/Chebyshev bases; `calligraphy.py`: proportion constraints as projection onto convex sets | Interpolation error ≤ theoretical bound on known functions |
| 4 | Fourier series/transform, DFT, Haar wavelets, multiresolution | `paper.py`: paper/canvas grain with a prescribed spectrum; `inverse.py`: coarse→fine via multiresolution | Spectrum slope; perfect reconstruction of Haar MRA |
| 5 | Banach fixed point, Fréchet/Gâteaux derivatives, Newton–Kantorovich, conjugate gradient | Implicit drying/flow steps proven contractive before use; Newton for nib–paper footprint; CG for Poisson/diffusion solves | Contraction constant < 1 measured; CG residual ↓; Newton quadratic rate |
| 6 | Finite differences, Lax equivalence (consistency + stability ⇔ convergence) | `media.py`/`paper.py`: wicking, diffusion and shallow-water schemes with stated stability limits (CFL) | Grid-refinement order matches theory; unstable step size refused |
| 7 | Sobolev spaces, weak derivatives | Regularisers for inverse painting and fills (H1 smoothness, H2 bending) | Energy decreases; weak-derivative identity on test functions |
| 8–9 | Weak formulations, Lax–Milgram, elliptic BVPs | Smooth fills and shading from a sketch as well-posed elliptic problems (unique solution guaranteed) | Coercivity check; solution vs. manufactured solution |
| 10 | Finite element analysis, interpolation error estimates | `animate.py`: elastic/ARAP deformation of drawn characters on triangle meshes; paper cockling under wet paint; mesh refinement by estimate | Convergence order on manufactured solutions |
| 11 | Elliptic variational inequalities, obstacle and Signorini contact, friction | `tools.py`: nib/bristle contact with paper (no penetration), paint thickness ≥ 0, friction for dry-brush | Complementarity residual ≈ 0; obstacle solution vs. analytic 1D case |
| 12 | Integral equations: Galerkin, collocation, Nyström, product integration, iteration | Light scattering inside paper (integral form), blur/bleed kernels | Nyström convergence on a known kernel |
| 13 | Boundary integral equations (Laplace, Kelvin transform, exterior problems) | Harmonic flow fields around glyph outlines: ink and ornaments flowing around letters, computed from the outline only | Harmonic test (mean-value property); exterior decay |
| 14 | Approximation on the sphere/ball, hyperinterpolation | Spherical-harmonic environment lighting for paint relief and gold; globe-style drawings | Exactness for low-degree polynomials |
Rule: every solver added to the pen states its space, norm, stability condition and expected convergence order,
and ships a test that measures them. This is what makes the pen's self-tuning (stage 8) safe: tuning may move
parameters only inside the proven stable region.
