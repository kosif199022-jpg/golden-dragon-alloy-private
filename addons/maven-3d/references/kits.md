# Kit reference (engine/core.js and engine/kits/*.js)

Units: an avatar is 5.3 tall (feet at y 0, face centre about y 4.65). Sets sit 4000 apart. All builders add themselves to the scene and return a `THREE.Group`. Things that animate expose `userData.tick(t, ...)`. Things that open expose `userData.open(k)` with k from 0 to 1.

## core.js
| export | what it does |
|---|---|
| `run(shots, {tail, whip, whipAmount, noWhip, end})` | the shot runner. It makes `window.seek(t)`, adds whip-pans at cuts, puts the sky on the camera and keeps the camera out of extras |
| `C(i)`, `ws(i)`, `we(i)`, `wi(word, n)` | timing helpers. `C` is the cut time (40 ms before word i), `ws`/`we` are the start and end of word i, and `wi` is the index of the n-th occurrence of a word (English or Arabic, ignoring diacritics) |
| `look(pos, target, fov, roll)` | sets the camera |
| `CAM.push`, `dolly`, `orbit`, `tiltUp`, `punch`, `follow`, `fly` | ready-made moves, each driven by the shot's 0–1 progress `u` |
| `handheld(t, amount)` | a small drift vector to add to a camera position |
| `faceOf(avatar)` | world position of an avatar's face |
| `dof(focus, aperture, maxblur)` | depth of field. Focus is the distance from the camera. Use aperture .005–.009 for faces and .0003–.001 for wides |
| `gradeSet(sat, con, [r,g,b], vignette)` | sets the colour grade |
| `flash(v, [r,g,b])` | a screen flash, as for lightning or a reveal |
| `setTOD(a, b, k)` | sets the lighting preset, or a blend between two. Presets: day, golden, sunset, night, spooky, ice, storm, indoor. Add your own with `TOD.name = {...TOD.day, sd: [...]}` |
| `shadowAt(x, z, size)` | centres sun shadows on the set you are filming. Call it after `setTOD` in every shot away from the origin |
| `onReset(fn)` | runs before every frame. Restore anything a shot hides, so that seek stays pure |
| `extras(list)` | objects the camera hides when it passes through them (`crowd()` registers itself) |
| `overlay((ctx, t) => …)` | a 2D layer under the captions, for HUD pills, sound words and cards |
| `followCam(obj)` | keeps an object centred under the camera (clouds use it) |
| primitives | `box`, `rbox`, `cyl`, `ball`, `mat`, `glow`, `at`, `canvasTex`, `seed`, `R`, `pick`, `lerp`, `lerpV`, `eio`, `eo`, `clamp`, `V` |

## kits/characters.js
- **`avatar(o)`**: the blocky avatar. Options:
  - Colours: `skin`, `shirt`, `dark`, `sleeves`, `pants`, `shoe`.
  - `kind`: hoodie, stripe, puffer, tee, overall, suit, dress, police, doctor, king, armor, pajamas, number, plain.
  - `hair`: swoop, pony, long, bun, spiky, curly, mohawk, buzz, bald, none. `hairCol` sets its colour.
  - `acc`: a list such as `['crown', ['partyHat', {cols}], 'glasses']`.
  - `face` sets the starting expression and `scale` the size.
  - Extras: `logo` and `logoCol` (the hoodie star), `tie` (suit), `num` (number shirt).
- **`ACC`** (accessories): partyHat, crown, cap, policeHat, topHat, glasses, shades, beard, mustache, backpack, cape, watch (glowing wrist timer), sword, phone, wand.
- **`cast(name, extra)`**: presets hero, heroine, puffer, mom, dad, grandpa, explorer, bully, king, police, doctor, teacher, knight, mayor, sleepy. `randomPerson()` makes a random extra.
- **`pose(a, {e, aL, aR, lL, lR, hx, hy, hz, lean, twist, bob})`**:
  - Arms: x < 0 raises an arm forward, and z moves it sideways (+ for the left arm, - for the right).
  - Legs: `lL`/`lR` rotate them; -1.57 is seated.
  - `hx`/`hy`/`hz` turn the head (-.5 looks up).
- **Expressions (`e`)**: smile, neutral, grin, joy, wish, squeeze, blow, shock, scared, sad, cry, angry, smirk, evil, sleep, wink, love, dizzy, determined, worried, blank. Add one with `FACE_DRAW.name = g => {…}` (a 512px canvas).
- **`POSES`**: idle, wave, cheer, point, pointUp, wish, shrug, scared, lookUp, facepalm, hug, sit, think, angry, cry. Spread one and add fields: `pose(a, {...POSES.cheer(t), e: 'joy'})`.
- **`walk(t)`, `runCycle(t)`**: these return the pose fields only. Move `position` yourself, at about 4.5 units/s walking and 10 running.
- **`crowd(n, centre, r0, r1, {hats})`** makes a ring of extras facing the centre. `crowdPose(list, t, mode)` poses them; modes are idle, party, cheer, up, scared and run.

## kits/sets.js
Each set takes `(x, z, opts)`:

| set | contents | anchors / options |
|---|---|---|
| `town` | plaza, ring road, two rings of houses, trees, lamps, hills | `night: true` lights the windows |
| `party` | table, cake with number candles, presents, balloons | `age: 10`; `userData.tick(t, lit)` animates the candles and balloons |
| `room` | interior box with a window, bed, desk, lamp, shelf, rug, poster, door | `kind: 'empty'`, `w`, `d`, `h`, `wallTex`, `floor`, `light`, `skyCol` |
| `classroom` | chalkboard, 9 desks, teacher desk, clock | `userData.board`, `userData.desks` |
| `forest` | pines, round trees, dirt path, rocks | `snow`, `dark` |
| `spookyStreet` | dark houses with lit windows, lamps, a church with a clock tower | `userData.church` |
| `castle` | courtyard, 8 towers, walls, banners, throne dais | put `props.throne()` at (x, 1.2, z - 32) |
| `iceWorld` | snow, ice spikes, mountains | — |
| `beach` | sand, sea, palms | `userData.sea` |
| `city` | road and towers | `night: true` |

Shared builders: `house`, `tree`, `pine`, `lamp`, `fence`, `clouds` (call once), `hills`, `bunting`, and `TEX` (grass, sand, snow, dirt, road, tiles, planks, bricks, stone, wallpaper, windows, tower).

## kits/creatures.js
- **`dragon({cute, body, wing, belly, horn, eye, scale})`**: `tick(t, rate, amp)` flaps the wings and sways the tail. Cute ones have big eyes and blush.
- **`flock({kind: 'dragon'|'bat'|'bird', n, center, rMin, rMax, t0, speed, size, col, eye})`**: hundreds of instanced flyers. `tick(t)` moves them.
- **`beast({eyes, tentacles, scale})`**: a black mass with glowing eyes. `tick(t, lookAt)` turns every eye toward a point.
- **`stranger({height, col, dial})`**: a tall thin figure with a wide grin and a glowing chest dial.
- **`ghost()`**, **`slime({col})`**, **`pet({kind: 'dog'|'cat', col})`**: `tick(t, moving)` animates each.

## kits/props.js
- **`mysteryCube({size, inside})`**: `open(k)`, plus `userData.countdown.userData.set(seconds)`.
- **`portalDoor({w, h, col, glow})`**: `open(k)`. Put `fx.portal()` 0.4 in front of it.
- **`chest()`**: `open(k)` shows glowing coins and light.
- **`countdown({w, col})`**: a 7-segment panel. `userData.set(seconds)`.
- **`textPanel(text, {w, h, post, size, bg, col, lines, dir, align})`**: signs, notes and boards. Arabic is right-to-left automatically.
- **`clock({r})`**: `set(h, m, s)`.
- **`car({col})`**: `tick(t, wheelSpeed)`.
- **`remote()`**, **`trophy()`**, **`throne({col})`**.
- **`goldify(avatar)`**: turns any avatar into a gold statue on a pedestal.

## kits/fx.js
Create each effect once at the top of the story, then call `.at(...)` inside the shot. Effects hide themselves every frame.
- **`burst()`**: `.at(t, t0, centre)`, a firework of sparks.
- **`twinkle()`**: `.at(t, centre, radius, height)`.
- **`confetti()`**: `.at(t, centre)`.
- **`poof()`**: `.at(t, t0, pos, scale)`.
- **`weather({kind: 'snow'|'rain'})`**: `.at(t, centre)`.
- **`motes({rise})`**: fireflies or embers.
- **`lightning()`**: `.at(t, t0, from, to)`, which also flashes the screen.
- **`portal({r, c1, c2})`**: a swirl disc. Call `.userData.tick(t)` each frame.
- **`orb()`**: `.at(pos, size, light)`.
- **`dust()`**: `.at(t, t0, centre, size)`.
- **2D overlays**: `soundWord(ctx, t, t0, 'BOOM!', x, y)`, `hudPill(ctx, value, {icon})`, `chapterCard(ctx, t, t0, t1, 'DAY 1')` and `rewind(ctx, t, t0)`. Use them inside `overlay((ctx, t) => …)`. Arabic text works.
