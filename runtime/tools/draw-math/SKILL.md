---
name: draw-math
description: >-
  Precise geometry, measurement and proportion calculator for drawing and animating
  people and scenes (shadow-puppet films, 3D silhouette films, 2D figures, three.js or
  Blender cameras). Body segment lengths from height (Drillis & Contini), distance,
  angle, midpoint/lerp, two-bone IK for legs and arms, pinhole camera to pixels,
  on-screen size and framing distance for 9:16, angular size, sun-shadow length,
  shadow-puppet size and blur, walking step and cadence, per-frame easing, arc and
  Bezier length. Use whenever a drawing or animation needs a real number instead of a
  guess: "how long is the arm", "how far is the camera", "how big on screen", "shadow
  length", "can the foot reach", "spacing chart". Arabic triggers: «احسب المسافة»،
  «نسب الجسم»، «طول الدراع/الرجل»، «الكاميرا تبعد قد إيه»، «الشخص هيطلع قد إيه على
  الشاشة»، «طول الظل»، «ظل الدمية»، «منظور»، «زاوية»، «IK»، «توقيت الحركة».
---

# draw-math

Measure before you draw. One stdlib-only script, no installs. Paths are relative to this skill folder:

```
python -I -X utf8 scripts/dmath.py <subcommand> [args] [--json]
python -I -X utf8 scripts/dmath.py <subcommand> --help
```

Every subcommand prints a short answer; `--json` prints `{"ok": true, ...}` for code. Bad input exits 2 (with `--json`: `{"ok": false, "error": ...}`).

## Which subcommand

| Need | Subcommand |
|---|---|
| Limb/torso lengths, joint heights, widths from stature (m, px, head units) | `body H [--px-per-m N] [--heads] [--canon 8] [--only keys]` |
| Distance, angle at a joint, midpoint, in-between point | `dist P Q`, `angle A B C`, `midpoint P Q`, `lerp P Q t` |
| Pose a leg/arm so the foot/hand lands on a point | `ik2 L1 L2 X Y [--bend +1/-1] [--root x,y]` |
| Where a 3D point lands in the frame (px, depth, in frame?) | `cam --fov --res --pos --target --point ...` |
| How tall an object will look on screen | `cam-size --fov --res --dist D --size S` |
| How far the camera must be to fill the frame | `frame-fit --fov --res --height S --fill 0.8 [--width W]` |
| Angle an object subtends, or the inverse | `angular --size --dist` / `angular --deg --dist` / `--deg --size` |
| Shadow length and bearing from sun elevation | `sun-shadow --height --elev [--az]` |
| Shadow-theatre shadow size, blur, puppet placement | `puppet-shadow --light-dist L --puppet-dist d --size s [--light-size w] [--want S]` |
| Walk timing: step, stride, cadence, frames per step | `gait --height H [--speed v] [--fps n]` |
| Per-frame values for a move (spacing chart) | `ease --dur --fps --from --to --curve linear/in/out/inout/minjerk/smoothstep` |
| Arc length/chord; Bezier path length and midpoint | `arc --radius --deg`, `bezier P0 P1 P2 P3 [--n] [--at t]` |

## Rules

1. Units are meters and degrees. Points are comma lists `x,y` or `x,y,z`; negatives work (`-1,2,0`); if a shell eats one, write `--pos=-1,2,0`.
2. `--fov` is the VERTICAL field of view, as in three.js `PerspectiveCamera`. In 9:16 (1080x1920) the horizontal FOV is much narrower (50 deg vertical = 29.4 deg horizontal); fit wide poses with `frame-fit --width`.
3. Default camera is three.js-like: fov 50, 1080x1920, up +Y, pixel origin top-left, near 0.1, far 2000.
4. Verify a drawing by projecting its key joints: `body` gives the joint heights, `frame-fit` the distance, then `cam --point` for head top, shoulders, hands and feet. Every point must be IN, with margin from the edges.
5. IK: angles are measured from straight down, counter-clockwise positive. Character facing +X: knee `--bend -1`, elbow `--bend +1`. If the result is UNREACHABLE, shorten the pose or move the root; never stretch the bones.
6. Numbers marked `*` (recalled) or `d` (derived) and all `gait` output are approximations. Say so when you pass them on.
7. Shadow puppets: «كل ما الدمية تبعد عن الشاشة وتقرب من اللمبة، ظلها يكبر ويغبّش». Pressed to the screen it is true size and sharp.

## Examples (real output)

```
$ body 1.75 --only shoulder,hip,knee,upper_arm,forearm,thigh,shank --px-per-m 500 --heads
Body for H = 1.750 m (sex m): Drillis & Contini 1966 fractions, Winter Fig. 4.1
head unit = H/7.5 = 0.2333 m | real 7.5 heads = 0.2333 m | heroic 8 heads = 0.2188 m | D&C head 0.130H = 0.2275 m (= 7.69 heads)
HEIGHTS above floor                            xH        m       px   heads
    shoulder (acromion) height              0.818   1.4315    715.8    6.13
    hip (greater trochanter) height         0.530   0.9275    463.8    3.98
    knee height                             0.285   0.4987    249.4    2.14
LENGTHS                                        xH        m       px   heads
    upper arm                               0.186   0.3255    162.8    1.40
    forearm                                 0.146   0.2555    127.8    1.09
    thigh (femur)                           0.245   0.4287    214.4    1.84
    shank (lower leg)                       0.246   0.4305    215.2    1.84
* recalled from the figure, approximate   d derived (difference of two heights)
Population averages: real people vary by several %. --sex does not change the fractions.
```

```
$ frame-fit --fov 50 --res 1080x1920 --height 1.75 --fill 0.8
distance = 2.3456 m so 1.75 m fills 80% of the frame height (1536.0 of 1920 px); limited by height
fov 50 deg vertical / 29.3950 deg horizontal at 1080x1920; visible 1.230 x 2.187 m
level camera for an object standing on y=0: --pos 0,0.875,2.346 --target 0,0.875,0
```

```
$ cam --fov 50 --res 1080x1920 --pos 0,0.875,2.3456 --target 0,0.875,0 --point 0,1.75,0 --point 0,0,0 --point -0.2266,1.4315,0 --point 0.2266,1.4315,0
camera fov 50 deg vertical / 29.3950 deg horizontal, 1080x1920 (aspect 0.5625), focal 2058.73 px
pos (0, 0.875, 2.3456) -> target (0, 0.875, 0); pixels origin top-left
  (0, 1.75, 0): px (540.00, 192.01)  depth 2.3456 m  IN (in frame)
  (0, 0, 0): px (540.00, 1727.99)  depth 2.3456 m  IN (in frame)
  (-0.2266, 1.4315, 0): px (341.11, 471.56)  depth 2.3456 m  IN (in frame)
  (0.2266, 1.4315, 0): px (738.89, 471.56)  depth 2.3456 m  IN (in frame)
```

```
$ ik2 0.4287 0.4305 0.15 -0.80 --bend -1
2-bone IK  L1=0.4287 L2=0.4305  root=(0, 0)  target=(0.15, -0.8)  bend=-1
distance 0.813941 (reach 0.0018..0.8592) -> REACHABLE, margin 0.045259 to full extension
root angle   = 29.3399 deg from straight down (CCW +, toward +X)
middle joint = -37.3593 deg flexion (0 = straight; interior angle 142.6407 deg); bone 2 at -8.0194 deg from down
middle joint at (0.210059, -0.37371); end at (0.15, -0.8)
FK check: |FK - target| = 8.3e-17  OK
```

```
$ puppet-shadow --light-dist 3 --puppet-dist 1 --size 0.4 --light-size 0.05 --want 1.2
magnification = 1.5000  shadow size = 0.6000 m  penumbra (blur) = 0.0250 m per edge
full extent 0.6250 m, dark core (umbra) 0.5750 m
for a 1.2 m shadow put the puppet 2.0000 m from the screen
Moving the puppet away from the screen (toward the lamp) makes its shadow bigger (M = L/(L-d)) and blurrier (penumbra = w*d/(L-d)); pressed to the screen it is true size and sharp.
```

```
$ sun-shadow --height 1.75 --elev 30 --az 135
shadow length = 3.0311 m (1.7321 x height) at sun elevation 30 deg
shadow points to azimuth 315.00 deg (compass, 0=N, 90=E); unit (E,N) = (-0.7071, 0.7071), tip at (E,N) = (-2.1433, 2.1433)
sun direction (E,N,Up) = (0.61237, -0.61237, 0.5)  [three.js: x=E, y=Up, z=-N]
```

```
$ gait --height 1.75 --fps 24
step 0.723 m, stride 1.446 m (0.413 x H, rule of thumb)
at 1.3 m/s (assumed comfortable speed): cadence 107.9 steps/min, step 0.556 s, stride (gait cycle) 1.112 s
at 24 fps: 13.34 frames/step, 26.69 frames/stride
typical adult cadence 100-120 steps/min; approximations only
```

```
$ ease --dur 0.25 --fps 24 --from 0 --to 90 --curve minjerk
ease minjerk  0 -> 90  over 0.25 s at 24 fps = 6 frames (7 keys incl. frame 0)
frame    time       s       value      delta
    0   0.000  0.0000     0.00000
    1   0.042  0.0355     3.19444    3.19444
    2   0.083  0.2099    18.88889   15.69444
    3   0.125  0.5000    45.00000   26.11111
    4   0.167  0.7901    71.11111   26.11111
    5   0.208  0.9645    86.80556   15.69444
    6   0.250  1.0000    90.00000    3.19444
largest step 26.11111 into frame 3 (spacing chart: small steps = slow, big = fast)
```

## Body table (fraction of stature H)

Drillis & Contini (1966), as tabulated in Winter, *Biomechanics and Motor Control of Human Movement*, Fig. 4.1. `*` = recalled from the figure (approximate), `d` = derived.

| Height above floor | xH | Length | xH | Width / canon | xH |
|---|---|---|---|---|---|
| eye | 0.936 | head + neck | 0.182 | shoulder width | 0.259 |
| chin | 0.870 | head (d) | 0.130 | hip width | 0.191 |
| shoulder | 0.818 | neck (d) | 0.052 | foot width * | 0.055 |
| chest * | 0.720 | trunk (d) | 0.288 | head, real 7.5 heads | 0.1333 |
| elbow * | 0.630 | upper arm | 0.186 | head, heroic 8 heads | 0.125 |
| hip (trochanter) | 0.530 | forearm | 0.146 | | |
| wrist * | 0.485 | hand | 0.108 | | |
| fingertip * | 0.377 | thigh / shank | 0.245 / 0.246 | | |
| knee | 0.285 | foot length | 0.152 | | |
| ankle (foot height) | 0.039 | foot height | 0.039 | | |

Formulas, sources and confidence levels: `references/sources.md`. Tests: `python -I -X utf8 tests/test_dmath.py`.
