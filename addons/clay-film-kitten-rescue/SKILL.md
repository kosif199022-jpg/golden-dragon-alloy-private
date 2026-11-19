---
name: clay-film-kitten-rescue
description: "3D clay (claymation-look) short film built entirely in code with Three.js + GSAP, 9:16 1080x1920 30 fps, no AI generator: clay characters with lumpy material and rim light, a fitted shot camera smoothed over time, depth of field, a soundtrack made in code, and a frame-by-frame Playwright export. Worked example: «Kitten Rescue», 20 s. Use as the template for any clay or plasticine 3D short. Arabic triggers: فيلم صلصال، كلايميشن، أنميشن صلصال ثلاثي الأبعاد، شخصيات صلصال، قصة القطة."
---

# Clay film (Kitten Rescue template)

A finished 20-second clay film written as code: a clay man sees a kitten drowning, runs for a lifebuoy, throws it, pulls her to the bank, and the two hug. The full run and export steps are in `README.md` next to this file.

## When to use it
- The owner wants a 3D short that looks like clay or plasticine (كلايميشن، صلصال).
- An original story with one or two characters, a single place and a clear rescue, gift or meeting beat.

## Steps
1. Copy this folder to a new work dir, then run `npm install` there.
2. **Story:** write the beats as times in seconds. Change the choreography in `src/pond.js` (GSAP timeline) and the world in the same file.
3. **Characters:** build them in `src/man.js` and `src/cat.js` from the helpers in `src/shapes.js` and the material in `src/clay.js`. Check them with `node scripts/sheet.mjs` (character sheet) before you animate.
4. **Camera:** each shot names its subjects and the side to look from. The distance fits the subjects to the frame, then a Gaussian smoothing (σ = 0.3 s) softens the moves.
5. **Stills first:** `node scripts/export.mjs --stills 3.95,7.2,16.5` → `out/stills_grid.jpg`. Show them to the owner before the long render.
6. **Sound:** `python3 scripts/sound.py out/soundtrack.wav`, all made in code, at -14 LUFS. If the owner has a voiceover, keep it untouched and put the music under it.
7. **Export:** `node scripts/export.mjs --audio out/soundtrack.wav` → H.264 High, CRF 17, BT.709. About 1.6 s per frame on CPU (SwiftShader). Run it in the background and watch it with a job/Monitor, never with sleep.

## Rules
- Original characters and stories only. Never recreate another creator's film shot for shot.
- Delivery follows the dragon's export standard (1080×1920, 30 fps, faststart) and its video-page step.

Source: uploaded by the owner on 2026-11-19 (`kitten_rescue_code.zip`). Libraries: three.js (MIT), GSAP (GreenSock standard licence, free use), Vite (MIT).
