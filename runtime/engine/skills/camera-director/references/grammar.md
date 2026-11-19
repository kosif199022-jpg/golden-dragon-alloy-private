# Camera grammar with numbers

Verified = read on the source during research (2026-11-16). Textbook = standard practice, not re-verified.

## Shot sizes (human subject)
| Size | Frame cuts at | Use |
|---|---|---|
| ELS / extreme wide | person tiny in the world | location, scale, isolation |
| LS / wide | full body + space | geography, action |
| MLS / cowboy | knees | groups, walking dialogue |
| MS | waist | default conversation |
| MCU | chest | emotion with context |
| CU | head + shoulders top | emotion, reaction |
| ECU | eyes / detail | intensity, product detail, a clue |
Size is distance × lens. Changing size between cuts by at least one step (or 30°+ angle) avoids a jump cut.

## Angles
Eye level = neutral · low angle = power, heroic · high angle = vulnerable, overview ·
overhead / bird's-eye = pattern, fate (CameraBench: "forward" in bird's-eye = top of frame) ·
dutch (roll 5–15°) = unease · POV = identification · over-the-shoulder = relation.

## Lenses (full-frame 36 mm sensor; Blender `sensor_width=36`, three `filmGauge=36`)
| mm | Feel | Use |
|---|---|---|
| 14–24 | wide, immersive, stretches depth, distorts faces | spaces, action, claustrophobia |
| 28–35 | natural documentary | establishing, walk-and-talk |
| 50 | ≈ eye | neutral storytelling |
| 85 | flattering compression | portraits, CU |
| 100–135+ | compressed, isolating, voyeuristic | product hero, surveillance |
Horizontal FOV = 2·atan(18 / f). Subject size on screen ∝ f / distance → **dolly zoom: f₂ = f₁ · d₂ / d₁** (exact, used by `dolly_zoom`).
Zoom ≠ dolly: zoom only magnifies (no parallax); dolly changes perspective (CameraBench separates them).

## Depth of field
f/1.4–2 razor (hero portrait, keep focus keyed) · f/2.8 portrait · f/4 two people · f/5.6–8 groups/product · f/11+ landscape.
Rack focus 1–2.5 s, inOutSine. Blender: `dof.focus_distance` is keyed per frame by the exporter.

## Shutter and motion blur
Exposure = (angle / 360) / fps → 180° at 24 fps = 1/48 s (baseline, verified RED). 45–90° = crisp/staccato (action, war),
270–360° = smeary/dreamy. Blender `motion_blur_shutter = angle/360`. cam.py 2D renderer integrates true sub-frames
over the open shutter, centred on the frame time.

## Movement speed (judder)
RED (verified): at 24 fps pan no faster than one image width per ~7 s; 3 s/width judders visibly. Longer lens or
smaller sensor → slower rotation for the same on-screen speed. Exempt: tracking a subject, whip/swish pans.
2D rule of thumb: max ≈ frame_width / (7·fps) px per frame (1920 px @24 fps ≈ 11.4 px/frame).
Natural ranges seen in AI camera datasets (ReCamMaster): pan 5–60°, tilt 5–45°, arc 5–60°, translation
0.25–1× the camera-to-subject distance.

## Composition
Thirds power points (0.33/0.67). Eyes on the upper third line. Lead/nose room ≈ 2/3 of the frame in front of gaze or
motion. Headroom small (≈5–10 % of frame height in MCU). One focal point; hierarchy by size > contrast > colour > position.
Vertical 9:16 from a 16:9 master: restack around the subject, keep critical content in the centre band, captions
inside title-safe.

## Cutting rules
- **180°**: keep the camera on one side of the line of action; cross only on screen, with a neutral (on-axis) shot, or a move that carries the camera across.
- **30°**: consecutive shots of the same subject differ ≥ 30° in angle and/or one shot size.
- **Cut on motion**: cut while the move is travelling and continue the vector in the next shot (same direction, similar speed). Exits and entries mirror (motion-doctrine's vector law).
- **Motivate every move**; hold 0.5–1 s before a reveal; end on stillness before a climax.
- Push → pull across a cut reads as recoil; pan direction reversal across a cut reads as a mistake.

## Steadiness vocabulary (CameraBench)
static · no-shake · minimal · unsteady · very unsteady. `cam.py analyze` reports the same scale.
Cinemachine noise practice (verified): rotation noise first, layered Perlin per axis (low 0.1–0.5 Hz, mid 0.8–1.5 Hz,
high 3–4 Hz), keep frequencies far below fps, reduce amplitude on telephoto.
