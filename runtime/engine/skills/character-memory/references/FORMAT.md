# character_memory.json — `dragon.character-memory.v1`

All lengths are in **head units (hu)**: multiply by the head height you want, in px. Angles use the rig convention:
0° points straight down, +90° points to image-right, 180° points up. `.R` is the character's right (image left when it
faces us). Every learned item carries `confidence` (0–1) and where it came from (`frames`, `from_frames`, `method`).
Anything the system invented is `observed: false, generated: true` with `derived_from`.

| Section | Contents |
|---|---|
| `character` | name, view, `source`: video path, sha256, fps, frames, size |
| `units.hu_px` | head height in px in the source (the scale everything is divided by) |
| `identity.palette[]` | role (`skin`, `cap`, `shirt`, `sleeve`, `glove`, `shorts`, `shoe`, `eye`, `mouth`, `outline`), hex, rgb, Lab, share, found_by, confidence |
| `identity.outline` | ink colour and line width (hu) |
| `identity.proportions` | height, every bone length, shoulder and hip width (hu) |
| `skeleton.bones[]` | name, parent, from/to joints, `length_hu`, `std_hu`, `frames_measured`, confidence, method |
| `skeleton.attach_hu` | neck, shoulders, hips in the torso frame (x across, y up from the pelvis) |
| `skeleton.foot_offset_hu`, `learned_limb_ratios` | ankle→shoe-centre, and where the elbow/knee sit along each limb (learned from bent frames) |
| `parts[]` | head, cap, torso, shorts (radial templates, 72 rays, in their own frame), arm/leg (tube radius), glove/shoe (ellipse radii), eyes (ellipse pair + pupil), brows (stroke pair) — each with `from_frames` |
| `layers` | back-to-front `order`, plus `relations` observed in the video (e.g. head above the right glove while scratching, frames listed) |
| `face.rest`, `face.expressions[]` | measured eyes/brows/mouth per expression: neutral, smile, surprise, laugh, confused, blink (observed, with frames); sad, angry (generated) |
| `poses[]` | the 8 most different observed poses (joint angles) with their frame |
| `motions[]` | observed: idle, wave, surprise, walk, laugh, scratch_head — `t0/t1`, `frames`, every pose channel per frame, period and periodicity (autocorrelation), speed for walk, layer swap for scratch; generated: sit (`pose_delta`, thigh foreshortening) |
| `timeline[]` | what happened when: motion + expression per segment |
| `provenance` | the method behind each kind of data |
| `quality.redraw` | the redraw's measured error |

Pose channels (`motions[].channels`): `px, py` (px in the source; the animator re-scales by `hu_px`), `spine`,
`head_tilt`, `ua.R/L` (upper arm), `fa.R/L` (forearm bend), `th.R/L` (thigh), `sh.R/L` (shin bend).
