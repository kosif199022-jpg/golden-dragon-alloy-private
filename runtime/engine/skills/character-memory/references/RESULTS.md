# Results on «Tamtam», the original test character (made by `charmem_cli.py demo`)

Folder: `C:\Users\cinde\OneDrive\Desktop\هام\output\character_memory`

## Videos and images
- `01_reference/reference.mp4`: the reference performance (8 s, 1080x1920, 30 fps); `gt.json` = ground truth, used by tests only
- `03_redraw/redraw.mp4`: every frame redrawn from vector layers; `03_redraw/svg/*.svgz`: one SVG per frame
- `03_redraw/compare_ref_redraw_diff.mp4` and `compare_ref_redraw_diff_sheet.png`: reference | redraw | difference x4
- `04_new_scene/new_scene.mp4`: a new scene drawn from `character_memory.json` alone (the source video was hidden while it rendered)
- `transfer_proof.png`: the source character, the new scene, and each colour learned from the source (top) and re-learned from the new scene (bottom)
- `06_export/character_rest.svg`, `character_skeleton.json`: vector export and a bones/slots/displays file

## Redraw (240 frames, character box)
| metric | mean | worst frame |
|---|---|---|
| mask_iou | 0.9987 | 0.998 (frame 95) |
| label_agree | 0.9755 | 0.9719 (frame 101) |
| psnr_db | 28.9337 | 27.69 (frame 189) |
| ssim | 0.9601 | 0.9483 (frame 165) |
| delta_e_mean | 3.5424 | 3.1737 (frame 188) |

Where the error comes from (frames rendered again without compression):
- frame 0: lossless vs H.264 34.64 dB; lossless vs redraw 22.54 dB
- frame 57: lossless vs H.264 34.81 dB; lossless vs redraw 23.5 dB
- frame 126: lossless vs H.264 33.05 dB; lossless vs redraw 22.54 dB
- frame 175: lossless vs H.264 33.13 dB; lossless vs redraw 22.95 dB
- frame 208: lossless vs H.264 33.93 dB; lossless vs redraw 22.93 dB
(those numbers were measured with the first vectoriser, pixel contours + dilation; the shipped one uses marching squares)

## Tracking vs ground truth (head = 270 px)
All joints, median of medians: 5.23 px. Joints marked inferred/interpolated were hidden (no pixels).

| joint | median px | p95 px | jitter px/frame² | frames not measured |
|---|---|---|---|---|
| ankle.L | 5.06 | 8.42 | 1.804 | 0 |
| ankle.R | 6.25 | 9.14 | 1.741 | 0 |
| elbow.L | 5.46 | 9.47 | 2.492 | 0 |
| elbow.R | 5.23 | 46.79 | 2.724 | 0 |
| foot.L | 0.71 | 0.79 | 0.151 | 0 |
| foot.R | 0.72 | 0.79 | 0.153 | 0 |
| hand.L | 0.73 | 0.8 | 0.159 | 0 |
| hand.R | 0.69 | 115.35 | 10.658 | 19 |
| head | 1.7 | 3.86 | 1.264 | 0 |
| hip.L | 13.58 | 22.61 | 2.356 | 0 |
| hip.R | 13.1 | 22.22 | 2.306 | 0 |
| knee.L | 1.3 | 8.23 | 3.318 | 0 |
| knee.R | 2.19 | 4.85 | 3.12 | 0 |
| neck | 6.32 | 21.33 | 1.432 | 0 |
| pelvis | 11.76 | 23.6 | 6.414 | 0 |
| shoulder.L | 5.02 | 7.97 | 0.916 | 0 |
| shoulder.R | 5.33 | 7.96 | 1.095 | 0 |
| wrist.L | 12.66 | 17.17 | 4.237 | 0 |
| wrist.R | 12.81 | 89.79 | 6.337 | 19 |

Occlusion: glove.R: truth 19 hidden frames, said 19, precision 1.0, recall 1.0; glove.L: truth 0 hidden frames, said 0, precision 0.0, recall 0.0

## Identity carried to the new scene (re-learned from scratch from the new scene video)
ΔE per colour role (source memory vs new-scene memory): skin 1.84, shirt 1.4, sleeve 1.25, cap 0.89, shorts 1.33, outline 0.97, shoe 1.15, glove 1.33, eye 0.96, mouth 1.43

## Tests: 34/35 passed

| | test | measured | needs |
|---|---|---|---|
| PASS | T1a frame count = duration x fps (8 s x 30) | 240 timed, 240 files | 240 and 240 |
| PASS | T1b timing from the stream: steps of 1/fps | max |dt-1/30| = 0.001 ms, monotonic True | < 1 ms, monotonic |
| PASS | T2a redraw mask IoU (mean / worst frame) | 0.9987 / 0.998 | >= 0.995 / >= 0.99 |
| PASS | T2b colour-label agreement | 0.9755 | >= 0.96 |
| PASS | T2c PSNR in the character box (mean / worst) | 28.9337 / 27.69 dB | >= 27 / >= 26 dB |
| PASS | T2d SSIM in the character box | 0.9601 | >= 0.94 |
| PASS | T2e one SVG per frame | 240 | 240 |
| PASS | T3a joints median error vs truth (visible joints) | 5.23 px of a 270-px head | <= 7 px |
| PASS | T3b worst visible joint (median) | hip.L 13.58 px | <= 15 px |
| PASS | T3c hidden hand found (precision / recall) | 1.0 / 1.0 on 19 frames | >= 0.9 / >= 0.9 |
| PASS | T3d hidden hand position (inferred, information-limited) | p95 115.35 px | <= 150 px (documented limit) |
| PASS | T4a jitter of blob-centre joints (worst) | head 1.264 px/frame² | <= 1.5 |
| PASS | T4b jitter of derived joints (worst) | knee.L 3.318 px/frame² | <= 4.0 |
| PASS | T5a expressions recognised vs truth | 0.983 | >= 0.95 |
| PASS | T5b observed and generated kept apart | observed ['blink', 'confused', 'laugh', 'neutral', 'smile', 'surprise']; generated ['sad', 'angry'] | 6 observed + generated with derived_from |
| PASS | T6a save -> load round trip | identical | identical |
| PASS | T6b sections present | all | identity, skeleton, parts, layers, face, poses, motions, timeline, provenance, quality |
| PASS | T6c every item has a confidence in [0,1] | all | all |
| PASS | T6d every observed item cites its frames | all | all |
| PASS | T7a new scene rendered from memory (uses_video = false) | 253 frames, uses_video=False | frames = script, false |
| PASS | T7b a command renders with the source video hidden | ['laugh'] in 10.9 s | renders |
| PASS | T7c command «خلّي الشخصية تمشي» | ['walk'] | ['walk'] |
| PASS | T7c command «تضحك» | ['laugh'] | ['laugh'] |
| PASS | T7c command «تجلس» | ['sit'] | ['sit'] |
| PASS | T7c command «انتقل بها إلى الجانب الآخر من ال» | ['cross'] | ['cross'] |
| PASS | T7c command «تمشي للناحية التانية وبعدين تضحك» | ['cross', 'laugh', 'sit'] | ['cross', 'laugh', 'sit'] |
| PASS | T8a same colours re-learned from the new scene (worst ΔE) | 10 roles, worst skin ΔE 1.84 | >= 9 roles, <= 8 |
| FAIL | T8b same proportions re-learned (worst bone) | thigh.R 16.3% | <= 12% |
| PASS | T8c same head shape re-learned (radial correlation) | 0.994 | >= 0.9 |
| PASS | T9a a wider laugh changes only the face | 1719 px changed, farthest 114 px from the head centre | all within 0.6 head |
| PASS | T9b identity, skeleton and parts untouched by the edit | True | true |
| PASS | T10a red-dragon selftest | "playbooks": 38 | ok |
| PASS | T10b names the desktop app calls | all 11 | all 11 |
| PASS | T10c routing on the held-out requests (exact/ok/top3) | [52, 58, 66] | >= 52 / 58 / 66 % |
| PASS | T10d new route present | True | true |
