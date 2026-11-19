# draw-math: formulas, sources, confidence

Confidence levels:
- **exact**: pure geometry or definition. Correct to floating-point precision, and checked by the tests.
- **high**: a published value or model I can cite with confidence.
- **medium**: a published value, but recalled without re-checking the page, or a convention that varies between sources.
- **low / rule of thumb**: a widely repeated number with no peer-reviewed origin that I can name.

## Anthropometry (`body`)

| Item | Formula / value | Source | Confidence |
|---|---|---|---|
| Segment fractions marked `fig` | eye 0.936H, chin 0.870H, shoulder 0.818H, hip (greater trochanter) 0.530H, knee 0.285H, ankle/foot height 0.039H, head+neck 0.182H, upper arm 0.186H, forearm 0.146H, hand 0.108H, thigh 0.245H, shank 0.246H, foot length 0.152H, shoulder width 0.259H, hip width 0.191H | Drillis, R. & Contini, R. (1966) *Body Segment Parameters*, Report 1166-03, Office of Vocational Rehabilitation, DHEW; NYU School of Engineering and Science. As tabulated in D. A. Winter, *Biomechanics and Motor Control of Human Movement* (Wiley; 4th ed. 2009), Fig. 4.1 | high (the values match the brief and my reading of the figure) |
| Fractions marked `fig?` | chest (nipple line) 0.720H, elbow 0.630H, wrist 0.485H, fingertip 0.377H, foot width 0.055H | Same figure, but recalled from memory. The arm chain is self-consistent: 0.630-0.146 = 0.484, 0.485-0.108 = 0.377 | medium. The *label* "chest" for 0.720 is the least certain |
| `derived` rows | head = 1-0.870 = 0.130H, neck = 0.870-0.818 = 0.052H, trunk = 0.818-0.530 = 0.288H | Differences of figure values | inherits the figure's error |
| Known inconsistency | shoulder minus elbow height = 0.188H, but the upper arm is 0.186H | in the figure itself | n/a |
| Sex | One set of fractions for everyone. `--sex` does not change them | Winter's figure is not split by sex. I did not verify the composition of the original sample | n/a |
| Artist canons | real adult about 7.5 heads (head = H/7.5); heroic/idealised 8 heads (H/8) | Figure-drawing convention, e.g. A. Loomis, *Figure Drawing for All It's Worth* (1943) | medium (a convention, not a measurement). D&C's own head of 0.130H gives 7.69 heads, between the two canons |

All anthropometric fractions are population averages. Real individuals differ by several percent, and limb ratios differ between populations.

## Points and joints

| Item | Formula | Source | Confidence |
|---|---|---|---|
| `dist` | sqrt(sum (q_i - p_i)^2), via `math.hypot` | Euclidean geometry | exact |
| `angle` | atan2(\|u x v\|, u . v), u = A-B, v = C-B. 2D signed: atan2(u x v, u . v) | Standard. More stable than acos near 0 and 180 deg | exact |
| `midpoint`, `lerp` | (P+Q)/2; P(1-t) + Qt | definition | exact |
| `ik2` | D = \|T\|; cos(th2) = (D^2 - L1^2 - L2^2) / (2 L1 L2); th1 = atan2(x, -y) - atan2(L2 sin th2, L1 + L2 cos th2). Angles from the down-vector, CCW positive. Unreachable targets clamp to the reach circle (straight) or the inner circle (fully folded) | Law of cosines; analytic two-link planar IK as in robotics texts (e.g. J. J. Craig, *Introduction to Robotics*) | exact. The tests check FK on 50 random targets to within 1e-9 |

## Camera and size (`cam`, `cam-size`, `frame-fit`, `angular`)

| Item | Formula | Source | Confidence |
|---|---|---|---|
| Projection | Basis as in three.js `Matrix4.lookAt` (up +Y; nudge z by 1e-4 when looking straight up or down). NDC x = x_c / (depth tan(vfov/2) aspect), y = y_c / (depth tan(vfov/2)). px = (x+1)/2 W, py = (1-y)/2 H | Pinhole model; three.js `PerspectiveCamera` (fov = vertical degrees, aspect = W/H) | exact for the pinhole model. three.js `zoom`, `filmOffset` and `setViewOffset` are not modelled |
| Horizontal FOV | hfov = 2 atan(tan(vfov/2) W/H). 50 deg vertical at 9:16 gives 29.39 deg horizontal | trigonometry | exact |
| On-screen height | px = S H_px / (2 D tan(vfov/2)). D is depth along the view axis. Exact for an object facing the camera anywhere in the frame | similar triangles | exact |
| Framing distance | D = S / (2 fill tan(vfov/2)). With `--width`, also uses the hfov and takes the larger distance | inverse of the line above | exact |
| Angular size | theta = 2 atan(S / 2D). Inverse: S = 2D tan(theta/2) | trigonometry | exact |
| Sun check | 2 atan(1.3927e9 / (2 x 1.496e11)) = 0.5334 deg | diameter and 1 AU as given in the brief. Over a year the sun's apparent size varies from about 0.524 to 0.542 deg | high |
| Blender caution | With sensor fit "Auto", Blender applies the lens/FOV to the larger frame dimension: vertical for 9:16, horizontal for 16:9. fov = 2 atan(sensor / 2f), with a 36 mm default sensor | Blender camera documentation (recalled) | medium. Check sensor fit before reusing a three.js FOV in Blender |

## Light and shadow (`sun-shadow`, `puppet-shadow`)

| Item | Formula | Source | Confidence |
|---|---|---|---|
| Sun shadow | length = h / tan(elev). Bearing = sun azimuth + 180 (compass: 0 = N, 90 = E). Refuses elev <= 0 | Flat ground and a vertical object; trigonometry | exact. The tool does not compute sun position from date and place; use an ephemeris such as the NOAA solar calculator for that |
| Puppet magnification | M = L / (L - d). Lamp at L from the screen, puppet at d from the screen | Central projection, similar triangles | exact for a flat puppet parallel to the screen |
| Penumbra | per-edge blur = w d / (L - d) for a lamp of width w. Outer size = sM + blur, umbra = sM - blur | Extended-source geometric optics (umbra/penumbra). Diffraction is negligible at stage scale | exact (geometric optics) |
| Placement | d = L (1 - s / S_wanted) | inverse of M | exact |

Check: at d = 0, M = 1 and the penumbra is 0. Both grow as d grows, so a puppet moved toward the lamp casts a bigger, blurrier shadow.

## Walking (`gait`)

| Item | Value | Source | Confidence |
|---|---|---|---|
| Step length | about 0.413 x stature, same factor for both sexes | **Rule of thumb** from pedometer calibration guides. The common version is 0.413 for women and 0.415 for men. I cannot name a peer-reviewed origin. In pedometer guides "stride" means one *step* | low |
| Stride | 2 steps (one gait cycle, heel strike to heel strike of the same foot) | gait-analysis definition | exact (definition) |
| Comfortable speed | 1.3 m/s default | Bohannon, R. W. (1997) "Comfortable and maximum walking speed of adults aged 20-79 years", *Age and Ageing* 26:15-19. Comfortable speeds were roughly 1.27-1.46 m/s | medium (recalled) |
| Cadence | v x 60 / step. Typical adults walk at 100-120 steps/min | widely reported adult free-walking range, e.g. M. Whittle, *Gait Analysis: An Introduction* | medium |
| Phases | stance about 60%, swing about 40%, double support about 10% twice per cycle | J. Perry & J. Burnfield, *Gait Analysis: Normal and Pathological Function* | high |

Real step length grows with speed. With a fixed 0.413H step, cadence is only approximate away from about 1.3 m/s.

## Timing and paths (`ease`, `arc`, `bezier`)

| Item | Formula | Source | Confidence |
|---|---|---|---|
| Frames | N = round(dur x fps); keys at frames 0..N; value = a(1-s) + b s, so the end values are exact | definition | exact |
| in / out / inout | t^3; 1-(1-t)^3; 4t^3 for t < 0.5, else 1 - (2-2t)^3 / 2 | cubic easing equations (R. Penner, 2002) | exact (definition) |
| smoothstep | 3t^2 - 2t^3 | cubic Hermite (same as GLSL `smoothstep`) | exact |
| minjerk | 10t^3 - 15t^4 + 6t^5. Peak speed = 1.875 x the average speed, at t = 0.5 | Flash, T. & Hogan, N. (1985) "The coordination of arm movements: an experimentally confirmed mathematical model", *J. Neuroscience* 5(7):1688-1703 | high |
| Arc | s = r theta; chord = 2r sin(theta/2); sagitta = r(1 - cos(theta/2)) | circle geometry | exact |
| Cubic Bezier | B(t) = (1-t)^3 P0 + 3(1-t)^2 t P1 + 3(1-t) t^2 P2 + t^3 P3; B(0.5) = (P0 + 3P1 + 3P2 + P3) / 8 | Bernstein form | exact |
| Bezier length | Polyline with n segments. Error estimate = \|L_n - L_(n/2)\| / 3 (Richardson; the polyline error falls as 1/n^2) | numerical analysis | numeric; the error estimate is printed |
