# kit/reel.js

A reel is one HTML page that loads `kit/reel.js` (global `R`) and builds everything at load time. Nothing animates
by itself: every element registers an updater with `reel.on(t => ...)`, and `reel.seek(t)` puts the whole page at
second `t`. That is why renders are exact and repeatable. Never use CSS animations, `setTimeout` or `Date.now()`.

Sizes are CSS pixels of a 1080 x 1920 stage. `--res 4k` renders the same page sharper.

## Clock and maths
| Call | Does |
|---|---|
| `R.reel({w, h, fps, lang, duration, bg})` | makes the stage; `lang:"ar"` makes text and the dock right-to-left |
| `reel.on(fn)` | `fn(t)` runs every frame |
| `reel.cue(t, kind, note)` | asks for a sound at `t` (written to `out.cues.json`) |
| `R.k(t, [[t0, v0], [t1, v1, "back"]])` | keyframes; values may be arrays; easings `linear in out inOut back soft` |
| `R.pop(t, t0, d)` | 0 -> 1 with a springy overshoot; `R.fade(t, t0, d)` plain 0 -> 1 |
| `R.wob(t, speed, seed)` | small repeatable wobble for idle motion |

## Timing
`R.timing(SCRIPT, window.VOICE, {wps, gap})` -> `{words: [[word, t]], ends, lines, end}`. `lines[i]` is when line
`i` starts. In the template, `W(line, n)` is the time of word `n` of a line: put events on words, not on seconds.

## World and camera
| Call | Does |
|---|---|
| `cam = R.world(reel, w, h)` | a big world; `cam.el` is its root, add everything to it |
| `cam.to(t, cx, cy, zoom, ease)` | the screen centre looks at (cx, cy) at time t. A key 0.001 s after another = hard cut |
| `cam.punch(t, amount, d)` | quick zoom kick on a key word |

Keep a ground line `G` (e.g. 1700) and build around it. Zoom 1.2 = close, 0.8 = wide.

## Scenery (all soft, shaded, toy-like)
`R.sky(reel, parent, {w, h, top, bottom, night:[[t, 0..1]], clouds})` · `R.skyline(parent, x, groundY, w, {color})` ·
`R.street(parent, x, groundY, w, {h})` · `R.palm(parent, x, groundY, scale)` · `R.bush(parent, x, groundY, scale, colour)` ·
`R.shop(parent, centreX, groundY, {w, h, sign, color, wall, awning})` -> `{root, parts:{wall, window, door, sign, awning}}` ·
`R.room(parent, x, y, w, h, {wall, floor})` · `R.sofa(parent, x, floorY, scale, colour)`

`R.svg(parent, w, h, '<svg markup>', {x, y})` draws anything else; `R.clay("#hex")` returns a shaded gradient fill
for the soft 3D look and `filter="url(#soft)"` adds the soft shadow. `R.box(parent, x, y, w, h, style)` makes a div.

## Making things appear
| Call | Does |
|---|---|
| `R.drop(reel, node, t0, {height})` | falls in from above and lands with a squash (cue "land") |
| `R.popIn(reel, node, t0, {origin, out, sound})` | grows from nothing; `out` = time it shrinks away (cue "pop") |
| `R.anim(reel, node, {x, y, s, r, o})` | any keyframed move, scale, turn or fade |

## People
`p = R.person(reel, parent, feetX, feetY, {shirt, skin, hair, beard, apron, face:"sad"|"wow", s})`, skins in `R.SKIN`.
`p.show(t0, t1)` visible between t0 and t1 · `p.move(t0, t1, dx, dy)` walks (legs and arms swing) ·
`p.waveAt(t0, d)` · `p.face(-1)` turns left. Add props into `p.root` with `R.svg(p.root, 120, 300, ...)`.

## Text and graphics
| Call | Does |
|---|---|
| `R.caption(reel, TM.words, {y, size, color, font, ends, hold, until, emph:{index: colour}})` | one word at a time, pops on its time |
| `R.dock(reel, [{icon, at, color}], {from, accent, y})` | the story dock; each icon lights up at `at` |
| `R.phone(reel, parent, centreX, bottomY, {w, html, bg})` -> `{root, screen}` | a phone; build the app in `screen` with HTML |
| `R.notify(reel, phone, t0, title, body, {accent, icon, until})` | a notification drops in on the phone |
| `R.count(reel, node, [[t, value]], {digits:"arab"})` | a live number |
| `R.endcard(reel, t0, {name, tagline, color, icon, logo})` | the logo card |
| `R.icon(name, size, colour)` | line icons: store clock people ticket phone home bell check bread fire sad star heart walk chart car cup |

## Sound cues
Every drop, pop, dock tick and notification adds a cue. Render writes them to `out.cues.json` as `{t, kind, note}`.
Lay sound effects on those times in any editor, or skip them: the voice carries these reels.

## Tips
- Build the look of the style card first and check one `--still` before animating.
- Keep text out of the top 200 px and the bottom 330 px when the dock is used (Instagram covers them too).
- Hidden things cost nothing: build every scene in one world at different x positions and cut the camera between them.
