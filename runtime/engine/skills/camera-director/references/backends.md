# Backends: one path, every engine

## cam.py 2D renderer (stills & footage)
OpenCV `warpAffine` per frame with float precision (Lanczos; cubic for blur sub-frames) → raw pipe → ffmpeg x264
`-crf 16 -preset slow -pix_fmt yuv420p -movflags +faststart`; footage audio is mapped and re-encoded AAC 256k.
Oversized sources are pre-shrunk so peak magnification ≈ 1 (same detail, far less work).
Measured: 150 frames 1080×1920 from a 4000 px still with motion blur ≈ 55 s on this PC; `--preview` is ~4× faster.
Why not ffmpeg `zoompan`: it rounds x/y to whole pixels → jitter (trac #4298). If you must use it, upscale first and
drive zoom from the frame number: `scale=8000:-1,zoompan=z='1+0.25*on/250':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=250:s=1920x1080:fps=25`.

## Blender (bpy)
`cam.py blender shot.json --out cam.py [--camera NAME]` writes a script that:
creates/uses the camera, removes constraints, sets sensor 36 mm AUTO fit, resolution, fps, frame range, DOF (`fstop`),
motion blur (`shutter/360`), then keys location + quaternion rotation (look-at + noise) + lens + focus distance every
frame with LINEAR interpolation (works with Blender 5 layered actions), and finally ray-casts camera→target on every
frame and prints `OCCLUDED` frames. Run: `blender -b scene.blend -P cam.py -a` (or `-P scene.py -P cam.py` for a generated scene).
Alternatives: Blender's bundled *Add Camera Rigs* (Dolly / Crane / 2D rigs, Aim bone, "Set DOF to Aim") for hand-tuned rigs.

## three.js
`cam.py three shot.json --out track.js` → ES module with `TRACK`, `frameAt(t)`, `applyCam3(camera,i)` (converts Z-up→Y-up,
`filmGauge=36` + `setFocalLength` to match Blender) and `applyCam2(el,i)` (CSS transform for a 2D stage).
Render deterministically by frame index (never wall-clock). For interactive pages, yomotsu/camera-controls (MIT):
`CameraControls.install({THREE})`, `controls.setLookAt(px,py,pz,tx,ty,tz,true)`, `smoothTime` (default 0.25 s; 0.6–1.2 feels
cinematic), `fitToBox(mesh,true,{paddingTop…})`, event `rest` = move finished; in a film call `controls.update(1/fps)` per frame.
Spline paths: `new THREE.CatmullRomCurve3(pts,false,'centripetal')`, `getPointAt(u)` is arc-length (constant speed) — wrap `u` in an ease, look ahead 0.01–0.03.

## GSAP / HyperFrames / HTML films
Keep the timeline seekable: tween a proxy and apply the baked frame:
```js
import { TRACK, applyCam2 } from "./track.js";
const o = { f: 0 };
tl.to(o, { f: TRACK.frames.length - 1, duration: TRACK.frames.length / TRACK.fps, ease: "none",
           onUpdate: () => applyCam2(stage, Math.round(o.f)) }, 0);
```
`stage` = an element sized to the source (`src_size`) inside a viewport of `size` with `overflow:hidden`.
Follow motion-doctrine for scene-to-scene vectors (the camera move across a seam must continue, not restart).
Theatre.js: `@theatre/core` Apache-2.0 is fine to ship; `@theatre/studio` is AGPL — editor only, don't bundle.

## Remotion
Compute the frame with `useCurrentFrame()` and read `TRACK.frames[frame]`; apply the same transform as `applyCam2`.

## Manim
2D: `MovingCameraScene` → `self.camera.frame.animate.scale(0.5).move_to(obj)`, `frame.save_state()` / `Restore`.
3D: `ThreeDScene.set_camera_orientation(phi=75*DEGREES, theta=30*DEGREES)`, `move_camera(...)`, `begin_ambient_camera_rotation(rate=0.1)`.
Map: zoom → `frame.scale(1/zoom)`, cx/cy → `frame.move_to`.

## AI video generators (paid — ask before spending)
Describe camera in CameraBench words for Kling/Higgsfield/etc.: "slow dolly in", "arc left 30°", "pedestal up", "handheld minimal shake",
"dolly zoom". Then `cam.py analyze` the result to check the generator actually did that move.
