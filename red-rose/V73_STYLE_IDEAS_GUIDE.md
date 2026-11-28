# V73 style ideas as Red Rose knowledge (2026-11-28)

`rose.py styles ideas ["words"] [--family F]` lists 125 entries from `agent/style_ideas_v73.json`:
100 original style ideas the owner approved as knowledge (families: heritage, egyptian, calligraphy, art,
cinema, explainer, games, nature, fairytale, romance, fantasy, experimental, civilization, urban, elements,
music) and 25 borrowable styles from skills/engines already on the PC. Status is honest: `idea_not_built`
or `borrowable_not_tested`. When the owner asks for "a new style" or "what else can you make", search here
first, then offer. Build path: style card → 3-second sample → owner OK → native engine + tests → registry.
Rules kept with the ideas: `classic_fairytale_look` (storybook feeling with original characters only; no
studio characters, logos, names or copied shots) and `couple_animated_background` (الراجل والست stills over a
moving background in four layers; hair/cloth warp from one still must be sampled first).

## Flagship proposal: «النقش الحي» (Living Girih) — mathematics-heavy, not built yet
An Arabic word or dua line becomes a living Islamic geometric universe, driven by the voice:
1. Quasi-periodic girih tiling from de Bruijn's pentagrid (5-fold, never repeats) plus the 17 wallpaper
   groups for classic star patterns; tiles subdivide by inflation rules as the camera zooms (infinite zoom).
2. Hyperbolic plane: the pattern lives on the Poincaré disk ({7,3} or {8,3} tilings, Möbius transforms) so the
   camera "falls" toward an edge that never arrives.
3. Glyph morph by optimal transport: each word's outline → signed distance field → particle cloud; consecutive
   words morph by entropic Sinkhorn transport (mass conserved, no particle invented or lost).
4. Ink as fluid: stable-fluids Navier–Stokes (Stam) with vorticity confinement and curl noise; gold ink is
   advected through the tiling's channels.
5. Growth: Gray–Scott reaction–diffusion fills the tiles with organic arabesque, its feed/kill rates following
   the voice spectrum (FFT) and the word timing (whisperx).
6. Light: physically based gold and lapis materials, rendered in Blender 5.2 (geometry nodes + Python) or a
   numpy/numba CPU pipeline; deterministic per frame for resumable renders.
Measured acceptance (not taste only): fluid divergence norm, OT mass error, tiling vertex-rule violations = 0,
word-onset vs. visual-event offset ≤ 1 frame, frame determinism (same frame → same hash), media verify.
Paid tools: none needed. Status: idea_not_built; build in stages with tests, sample first.
