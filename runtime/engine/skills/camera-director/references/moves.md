# Moves: meaning, spec, defaults, pitfalls

Common 2D fields: `source`, `size:[w,h]`, `fps`, `dur`, `subject:[x,y]` (0..1 of source), `strength` (1 = tuned default),
`zoom` (base, ≥1), `ease`, `shake`, `shutter` (deg, default 180; `motion_blur:false` to disable), `seed`, `safe` (default true).
Common 3D fields: `mode:"3d"`, `pos`, `target`, `lens`, `fstop`, `roll`, `shutter`, `shake`, `dir`, `distance`.

## 2D (stills, footage, HTML stage)
| move | spec extras | default | notes |
|---|---|---|---|
| static | `zoom` | hold | with `shake` gets auto headroom |
| push_in | `subject` | +18 % zoom, centre glides 80 % toward subject, inOutSine | 4–8 s. The workhorse. |
| pull_out | `subject` | mirror of push_in | ends wide; good last shot |
| ken_burns | `subject` | 1.05→1.20, drift toward subject | stills; 5–8 s; pair alternate directions across a sequence |
| reveal | `subject` | starts ×1.9 on subject, lands wide, `dolly` ease | detail → whole |
| pan_left/right | `subject` (y) | zoom 1.25, travels 92 % of available room, `operator` ease | needs zoom > 1 for room. Check RED speed |
| tilt_up/down | `subject` (x) | same as pan, vertical | |
| drift | | zoom 1.12, slow linear lateral | B-roll life |
| punch_in | `at`, `move_dur` | +30 % in 0.22 s outExpo at `at` | on a beat/word (use speech_sync marks for `at`) |
| crash_zoom | `at`, `move_dur` | ×2.2 in 0.45 s outExpo | comedy/shock; motion blur makes it |
| whip_pan | `dir` | zoom 1.6, inOutExpo, 0.25–0.45 s | transition: cut at the blur peak into the next shot's whip |
| dutch_roll | `angle` | 8° inOutSine | coverage auto-zooms for rotation (WARN tells you) |
| handheld | `shake` | static + preset | presets: breath, float, handheld, nervous, run, impact(`at`,`decay`) |
| keys | `keys:[{t,cx,cy,zoom,rot,ease}]` | — | full control; `ease` on a key shapes the segment arriving at it |

Shake object form: `{"preset":"handheld","amount":0.6}` (trauma; effect ∝ amount²), or override `rot` (deg), `pos`
(fraction of frame), `freq` (Hz). `impact`: `{"preset":"impact","at":2.4,"decay":0.45}`.

## 3D (Blender / three.js)
| move | extras | default | notes |
|---|---|---|---|
| static | | | add `shake:"breath"` for a living tripod |
| dolly_in / dolly_out | `distance` | 35 % of camera–target distance, `dolly` ease | perspective changes, unlike zoom |
| truck | `dir` left/right, `distance` | 40 % of distance | heading kept → parallax |
| pedestal | `dir` up/down | 25 % | heading kept |
| crane_up | `distance` | rises 60 % + backs off 15 %, keeps target framed | endings, grandeur |
| orbit | `arc` deg, `dir`, `rise`, `radius_end` | 45°, inOutSine | check occlusion in Blender output; 20–90° |
| dolly_zoom | `ratio` | end distance ×2 with lens ×2 (subject size locked) | ratio > 1 = pull back + zoom in (background grows); < 1 the reverse |
| flythrough | `path:[[x,y,z],…]`, `target` or `lookahead` | Catmull-Rom, look-ahead 0.08 | space the points evenly; avoid sharp corners |
| rack_focus | `focus_from`, `focus_to:[x,y,z]` | inOutSine | needs `fstop` ≤ 2.8 to read |
| keys | `keys:[{t,pos,target,lens,focus?,ease}]` | | |

## Combos that work
- **Push-in + breath** (interview, product): strength 0.7, shake breath.
- **Orbit + rise** (hero reveal): `arc 60, rise 0.6`, lens 50→ keep, fstop 2.8.
- **Whip chain**: shot A whip_pan dir right (end), shot B whip_pan dir right (start) → cut at the blur peak.
- **Vertigo on realisation**: dolly_zoom 2–4 s, ratio 2–2.5, no shake.
- **Beat punches on a talking head**: static + punch_in at word marks (`speech_sync` → `at`), never more than one per sentence.

## Pitfalls
- Zooming a 1080p still beyond ×1.15 looks soft — check `peak_magnification`.
- Vertical 9:16 from a landscape still leaves no vertical room at zoom 1: a tilt needs zoom > 1.
- A subject near the source edge can't be centred; the INFO `edge_clamp` tells you the frame was held inside.
- Linear ease = robotic start/stop. Use `inOutSine`/`dolly` unless cutting on motion.
