---
name: camera-director
description: مدير التصوير — makes Claude shoot like a cinematographer whenever it composes a video, whatever the engine. Decides shot size, angle, lens and ONE motivated camera move per beat, writes the move once as a JSON spec, checks it against real operator limits (RED pan-speed judder, zoom rate, magnification softness, ease-in/out, 180° and 30° rules, occlusion), draws a storyboard before rendering, then renders 2D moves on stills/footage with sub-pixel warps + true shutter-angle motion blur, or exports the identical path to Blender (bpy keys + DOF + motion blur), three.js and HTML/GSAP/HyperFrames. It can also measure the camera motion of any video (pan/tilt/zoom/roll/steadiness) to copy a reference reel's camera or verify a render. Use for «حركة كاميرا»، «تحريك الكاميرا»، «زووم»، «push in»، «Ken Burns»، «pan»، «orbit»، «dolly»، «vertigo / dolly zoom»، «اهتزاز كاميرا / handheld»، «whip pan»، «crash zoom»، «لقطات سينمائية»، «زاوية التصوير»، «عدسة»، «ستوري بورد»، «حلّل حركة الكاميرا في الفيديو ده»، «انسخ حركة كاميرا الريل ده», camera move, cinematography, shot list, camera path, camera shake, virtual camera, and any time Claude animates a still, builds a 3D/HTML film or edits a reel where the frame should move.
---

# مدير التصوير — camera-director

The difference between a slideshow and a film is a camera with intent. This skill gives Claude
the operator's judgement (what move, why, how fast) and one engine (`scripts/cam.py`) that turns
a move into frames for every backend, with measured checks before and after.

```
CAM="python -X utf8 ~/.claude/skills/camera-director/scripts/cam.py"
$CAM doctor            # numpy, cv2, ffmpeg (+ optional blender)
$CAM moves             # vocabulary, defaults, shake presets, eases
```

## The operator's loop (follow in order)

1. **Motivate.** For every shot write one line: *what the audience should feel/learn* → that picks the move.
   No motivation → `static` (a locked frame is a choice, not a failure). One move per beat.
   | Intent | Move |
   |---|---|
   | importance rising, realisation, intimacy | `push_in` / 3D `dolly_in` (slow, 4–8 s) |
   | isolation, ending, context reveal | `pull_out`, `reveal`, `crane_up` |
   | follow action / reveal across space | `pan_*`, `truck` (move the camera, keep its heading → parallax) |
   | scale, aspiration / weight, discovery | `tilt_up` / `tilt_down`, `pedestal` |
   | hero product / character reveal | `orbit` 20–90° |
   | dread, a world tilting | `dolly_zoom` (vertigo), `dutch_roll` 5–15° |
   | beat emphasis, comedy, shock | `punch_in` (0.15–0.3 s), `crash_zoom` |
   | transition between scenes | `whip_pan` (cut inside the blur) |
   | presence, documentary, tension | any move + `shake: handheld / nervous / run` |
   | keep a still alive | `ken_burns`, `drift`, `shake: breath` |
2. **Frame.** Shot size + lens + subject point (rules and numbers: `references/grammar.md`).
   Subject on a thirds power point (0.33 / 0.67), eyes on the upper third line, lead room in front of gaze/motion.
3. **Write the spec** (one JSON per shot, or `{"axis":…,"shots":[…]}` for a sequence). See `references/moves.md`.
4. **Check** → `$CAM check shot.json`. FAIL blocks the render. Read every WARN and either fix it or say why it's intended.
5. **Storyboard before render** → `$CAM board shot.json --out board.png`, look at it (Read the PNG).
   For owner work, send the board and wait for «موافق» unless they said «نفّذ مباشرة».
6. **Render** the right backend (`references/backends.md`):
   - stills / footage → `$CAM render shot.json --out shot.mp4` (`--preview` = half-res fast)
   - Blender → `$CAM blender shot.json --out cam.py` then `blender -b scene.blend -P cam.py -a` (prints OCCLUDED frames)
   - three.js / HTML / HyperFrames → `$CAM three shot.json --out track.js` (`applyCam3` / `applyCam2`)
7. **Verify with a different method** → `$CAM verify shot.json shot.mp4` measures the output with optical flow
   (zoom, travel, frames, size) and compares with the spec. Then view 2–3 frames yourself.
   Report: what was measured ✅, what was only inferred 🟡.

## Spec in 20 seconds

2D (coordinates are fractions of the SOURCE, `zoom` 1 = cover-fit, shake keeps its own zoom headroom):
```json
{"source":"photo.jpg","size":[1080,1920],"fps":30,"move":"push_in","dur":5,
 "subject":[0.65,0.38],"strength":1.0,"ease":"inOutSine","shake":"float","shutter":180}
```
3D (Blender convention: metres, Z up, lens mm on 36 mm sensor):
```json
{"mode":"3d","move":"orbit","dur":6,"fps":24,"size":[1920,1080],
 "pos":[0,-6,1.6],"target":[0,0,0.9],"lens":50,"arc":60,"fstop":2.8,"shake":"breath"}
```
Raw control: `"move":"keys","keys":[{"t":0,"cx":.5,"cy":.5,"zoom":1},{"t":4,"cx":.6,"cy":.4,"zoom":1.2,"ease":"dolly"}]`
(3D keys: `pos`, `target`, `lens`, optional `focus`). Eases: `inOutSine` (default), `dolly`, `operator`, `settle`,
`outExpo`, `inOutExpo`, any `[x1,y1,x2,y2]` cubic-bezier. Zoom interpolates in log space (constant perceived speed).

## Measured limits the checker enforces

| Check | Limit (source) |
|---|---|
| pan / turn speed | ≥ 7 s per frame width at 24 fps, scaled by fps (RED pan-speed guide). < 2 s = whip, not a pan |
| zoom rate | calm push 2–6 %/s; > 12 %/s warns (ffmpeg Ken Burns reference ≈ 1.25× over 10 s) |
| magnification | > 1.15× source pixels warns, > 1.5× FAILS (soft) — use a bigger source or less zoom |
| coverage | window may never leave the source; zoom forced = WARN, small edge clamp = INFO |
| min duration | motivated move ≥ ~1.5–2 s (whip/punch/crash exempt) |
| ease | move must land at zero velocity unless `cut_on_motion:true` |
| 180° rule | sequence with `axis` → camera side flips = FAIL (`cross_line_ok` to override) |
| 30° rule | same subject, < 30° and lens ratio < 1.5 → jump-cut WARN |
| occlusion (Blender) | ray from camera to target blocked → OCCLUDED frames printed |
| shake | trauma² × smooth value noise, 2 octaves (Eiserloh GDC 2016; Cinemachine layering) |

## Reading a reference video's camera

`$CAM analyze ref.mp4` → moves (`pan_right`, `push_in/zoom_in`, `roll`, `handheld(minimal|unsteady|very-unsteady)`),
travel in frame widths, total zoom, roll, steadiness, peak speed, tracking-lost times (≈ cuts).
Content moving left = camera panning right (the tool already flips it). To copy a reel's camera: analyze each
shot (split at cuts with `scenedetect` first), then write keys with the same zoom/travel/duration.
Steadiness was calibrated on renders with known shake (6/6 correct); on real footage, treat it as a strong hint 🟡.

## Rules that save renders

- One move per shot; moves across a cut keep their direction (pan right → next shot keeps flowing right).
- Hold 0.5–1 s still before a move starts on a reveal; start/end slightly outside the needed range and trim.
- Telephoto magnifies shake: lower shake `amount` above ~85 mm. Never shake + push at full strength together.
- Never add overlay/bloom/fog/vignette "for cinema" unless asked — the camera is the cinema.
- Don't zoom past the source's real pixels; don't dolly into geometry; don't pan faster than the RED limit unless it's a whip.
- The video's audio stays untouched (AAC in MP4). Frame count = round(dur × fps) — `verify` checks it.

## Files

- `scripts/cam.py` — the engine (pure Python + OpenCV + ffmpeg; Unicode/Arabic paths safe).
- `references/grammar.md` — shot sizes, angles, lenses, DOF, shutter, composition, cutting rules, numbers.
- `references/moves.md` — every move: meaning, spec, tuned defaults, pitfalls, combos.
- `references/backends.md` — Blender, three.js (+ camera-controls), GSAP/HyperFrames, Remotion, Manim, ffmpeg zoompan.
- `references/sources.md` — the repos/papers this was distilled from, with licences.
- `required_tools.json` — what doctor checks. Installation of anything missing = ask the owner first.
