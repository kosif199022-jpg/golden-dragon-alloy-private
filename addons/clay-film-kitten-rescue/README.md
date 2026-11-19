# Kitten Rescue — 3D clay animation built in code (Three.js + GSAP)

A 20-second, 9:16 (1080×1920, 30 fps) clay film: a clay man spots a kitten drowning, runs for the lifebuoy, throws it, pulls her to the bank, and the two end in a hug.

## Run it
```bash
npm install            # three 0.170, gsap 3.12, vite 5
npm run dev            # preview in the browser: Play/Pause, Restart, scrub bar
```

## Export
```bash
python3 scripts/sound.py out/soundtrack.wav             # soundtrack (-14 LUFS)
node scripts/export.mjs --audio out/soundtrack.wav      # -> out/kitten_rescue.mp4
node scripts/export.mjs --stills 3.95,7.2,16.5          # -> out/stills_grid.jpg
node scripts/sheet.mjs                                  # -> out/preview_man.jpg (character sheet + story frames)
```
- Rendering uses headless Chromium with WebGL through SwiftShader, so it needs no graphics card. It takes about 1.6 s per frame.
- It needs Playwright (`npm i -D playwright` or a global install) and ffmpeg.

## Files
| File | What it does |
|---|---|
| `src/main.js` | Renderer: ACES tone mapping, soft shadows, depth of field (BokehPass), the controls, the `?sheet=` character-sheet mode, and `window.__kosif.seek(t)` |
| `src/pond.js` | The world (pond, banks, trees, hills, lifebuoy, rope, ripples, splashes, hearts), the GSAP choreography and the camera |
| `src/man.js` | The clay man: legs, hips, torso, head, sculpted hair, eyes with lids and brows, 3 mouths, arms that reach for targets, walking |
| `src/cat.js` | The clay kitten: ears, eyes, whiskers, fur fluff, front paws that paddle, wagging tail, shake, wet look |
| `src/buddy.js` | The original bean character (no longer used here; kept for reference) |
| `src/clay.js` | Clay material: MeshStandardMaterial with lumpy vertices, thumb-press noise and a soft rim light |
| `src/shapes.js` | Geometry helpers: bean, rounded boxes, blobs, gradient sky, soft contact shadows |
| `scripts/export.mjs` | Build, preview server, frame-by-frame capture, ffmpeg encode (H.264 High, CRF 17, BT.709) |
| `scripts/sheet.mjs` | Writes the character preview image |
| `scripts/sound.py` | The soundtrack, made entirely in code: music, water, meows, effects, purring |

## How the camera works
Each shot names its subjects (the man, the kitten, the lifebuoy) and the side the camera looks from. The distance is fitted so the subjects fill the frame. The track is then smoothed (Gaussian, σ = 0.3 s), so the moves between shots stay soft.
