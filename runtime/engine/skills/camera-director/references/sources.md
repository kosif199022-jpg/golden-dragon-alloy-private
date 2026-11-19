# Sources (research 2026-11-16). Only ideas/numbers were taken; no code copied.

| Source | Licence | Taken |
|---|---|---|
| CameraBench — github.com/sy77777en/CameraBench (arXiv 2504.15376, NeurIPS 2025) | not confirmed | motion taxonomy (dolly/pedestal/truck, pan/tilt/roll, zoom≠dolly, arc, tracking, steadiness levels) |
| yomotsu/camera-controls | MIT | smoothTime/rest/fitToBox/setLookAt patterns |
| theatre-js/theatre | core Apache-2.0, studio AGPL-3.0 | licence warning, sequence-driven camera idea |
| three.js CatmullRomCurve3 | MIT | arc-length path + look-ahead pattern |
| Squirrel Eiserloh, GDC 2016 "Juicing your cameras with math" | talk | trauma² shake with continuous noise, rotational shake first (constants unverified) |
| Bevy 2d_screen_shake example | MIT/Apache | trauma decay numbers as sanity check |
| Unity Cinemachine docs (noise, composer) | docs | layered Perlin bands, dead/soft zone, lookahead vocabulary |
| sniklaus/3d-ken-burns | CC BY-NC-SA 4.0 (non-commercial) | defaults only (zoom 1.25 over 3 s, centred 0.97 crop) — do NOT ship its code commercially |
| ffmpeg trac #4298 | — | zoompan integer-rounding jitter → why cam.py warps itself |
| RED "camera panning speed" guide | article | 7 s per frame width at 24 fps judder rule, shutter angle baseline |
| Blender manual: Add Camera Rigs | GPL (Blender) | rig vocabulary |
| Manim docs (MovingCameraScene, ThreeDScene) | MIT | camera API mapping |
| KwaiVGI/ReCamMaster | not stated | natural move ranges (pan 5–60°, tilt 5–45°, arc 5–60°, translation 0.25–1× distance) |
| Local skills: blender-cameras, shot-composition, motion-doctrine, cut-the-curve | local | lens/DOF tables, vector law across seams — this skill links to them instead of repeating |
