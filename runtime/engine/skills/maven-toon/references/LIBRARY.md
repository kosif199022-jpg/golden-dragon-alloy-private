# Library reference

Preview sheets: `library_characters.jpg`, `library_sets.jpg`.

## Moods (`"mood"`)
`day`, `interior`, `night`, `dream`, `golden`, `sunset`, `dawn`. Every set works in every mood. Practicals
(lamps, lit windows, screens) glow automatically in `night`.

## Sets (`"set"`): placement hints in set pixels (frame 1080x1920 = `h` 1920)

| set | what | actors stand at | notes |
|---|---|---|---|
| `street` | suburban street, houses both sides, lamps, fences, hydrants, wires | y 1550-1800, z 1.0 | night = lit windows + wet-cobble lamp reflections |
| `kitchen` | farmhouse kitchen: sage plaster + white tile, wood floor, centred window over the sink, terracotta cabinets, black range with copper hood, plate dresser on the left wall, copper pans, rattan pendant, striped runner | y 1500-1700, z 1.0 | near plane = table corner |
| `office` | brick office, blinds (noir stripes), sales bar chart, cork board with notes, desk, monitor, brass desk bell, rubber stamp | behind desk y 1300 z 1.2; in front y 1700 z 0.95 | |
| `shop_counter` | general store shelves (blurred), counter with a glowing brass balance scale (coins vs a loaf, "LOT 8" tag), coins | behind counter y 1330, z 1.6 | explanation close-ups |
| `planet_shop` | space shop: planet shelves with price tags, "PLANETS" sign, counter, register, Earth with "99¢" tag | seller x 640 y 1290 z 1.04; customer y 1720 z 0.95 | `earth`=(300,1160), tag=(450,1255) |
| `ship_deck` | wooden deck in perspective, rails, mast and sails, barrels, crate, wheel, sea + island | y 1500-1800, z 1.0 | |
| `desert_rails` | railway to the horizon, hoodoo rock towers, low mesas, grey stone ballast, cacti, wooden water tower | y 1600-2000, z 0.98 | low wide close-ups work best |
| `castle_hall` | stone hall, three lancet windows with god-rays, arch, green key pennants, oak chair of state, green runner, torches, chandelier | y 1450-1700, z 1.0 | chair=(540,1150) |
| `field` | meadow with a dirt road bending away left, lone oak with a rope swing, hay bales, farmhouse + silo, hot-air balloon, low sun right | y 1900-2100 z 0.9 (further up the road the ground hides the feet) | good for calm `dawn`/`sunset` scenes |
| `town_top` | top-down tilted view of a river town: street grid, winding river with plank bridges, gabled houses, off-centre market square with striped stalls, trees | small figures in the square (~(300, 1300)), scale 0.28, z 0.92 | layouts, "the whole town" |
| `prehistoric` | valley with a smoking volcano, long-necked dinosaur on the horizon, two flying reptiles, giant ferns and cycads, river, tar pit, boulders, rock outcrop with a cave mouth and cave paintings, campfire (glows in sunset/night/dawn) | y 1600-1750, z 1.0 (horizon is low, y 1230) | fire=(3.6 m, 12 m) world |

To add a set: write `def myset(mood): return [(name, plane_z, painter(cv), opts), ...], meta` in a module and add
it to a registry (`sets.REGISTRY`, `outdoor.py` or `interiors.REGISTRY`). Paint with the helpers in
`setkit.py`, `textures.py` and `props.py`. Put the subject plane at z = 1.0, far planes at 2-14, the sky at ~30
(`grade=False`), and a blurred near plane at 0.55-0.65 (`blur=8-14`). Register light sources in an `E` list and
re-draw them in `lights=` so they glow after the mood grade. Outdoor sets use `Ground` (a pinhole floor in metres)
and depth bands (see `outdoor.py`).

## Characters (`"type"`)
`worker` (hard hat, rust shirt, overalls, blue bandana, wrench), `boss` (slick grey hair, moustache, bottle-green double-breasted suit, mustard tie, watch
chain, mug), `cop` (light-blue shirt, peaked cap with silver shield, pockets, belt, silver badge, radio, baton), `cook` (toque, double-breasted
jacket, neckerchief, apron, ladle), `knight` (open-face brimmed kettle hat, plate, red tabard with white cross, sword),
`king` (crown with gems, ermine collar, robe, medal chain, beard, sceptre), `scientist` (wild white hair, round
glasses, lab coat, pens, flask), `cashier` (mustard visor, blue polo, mustard apron, name tag, scanner), `sailor` (round cap with
ribbons, striped shirt, sailor collar, telescope), `caveman` (messy black hair, one-shoulder spotted fur tunic, wooden club), `kid` (propeller cap, star tee, shorts, balloon, smaller),
`alien` (green head, bobbing antennae).

Overrides per actor: `torso`, `accent`, `skin`, `hat`, `hair`.

**Poses:** `stand`, `walk`, `run`, `point`, `shrug`, `arms_crossed`, `hips`, `hold`, `think`, `wave`, `cheer`, `sit`.
**Expressions:** `neutral`, `smug`, `angry` (red face + steam), `shocked`, `laughing`, `scared` (sweat drop), `sad`,
`sly`, `happy`, `deadpan`.
Always on: blinks, breathing, hat/plume/antenna/ribbon sway, scarf flutter. `talk: true` flaps the mouth.
`look: [x, y]` moves the pupils (-1..1).

## Hold props (`"hold"`)
`earth`, `planet:gas|red|ringed|shiny|moon|purple|earth`, `sign:TEXT`, `tag:TEXT`, `newspaper:LINE1|LINE2`.

## In-world explanation props (`props.py`, for sets)
`planet`, `price_tag`, `register`, `newspaper`, `sign_board`, `counter_display` (chalk number slate),
`cross_section` (ground cut-away), `calendar_page`; in `setkit.py`: `calendar`, `wall_clock`, `frame_pic`,
`crate`, `plant_pot`, `window`, `door`, `house`, `lamp_post`, `tree`, `foliage`, `cactus`, `rock`, `mesa`, `cloud`.

## Frame shorthand (`"frame"`)
`[cx, cy, h]`, `"wide"`, `"two"`/`"all"` (fits the cast), `"<id>"` (medium), `"<id>:face"`, `"<id>:full"`.
Camera roll per key: `"roll": 2.0` (degrees; costs ~0.2 s per frame, use sparingly).

### Non-human cast

`"type": "dino"`: a small friendly two-legged dinosaur (round body, cream belly, orange back plates, big eye). Cast fields: `x`, `y`, `scale` (0.6-0.9 next to a character), `z`, `dir`, `expr` (`happy` or `shocked`), `torso` (body colour). No poses; it breathes, blinks and wags its tail on its own.

### Captions-only Shorts

No voice-over: `python toon.py silent PROJECT --script script.txt --duration 15` writes a silent `voice.wav`, reading-pace timings (~2.3 words/s, 0.35 s after sentences) and `words.json`. `join` skips loudness normalisation when the track peaks below -70 dBFS; `check` prints "silent track, loudness not applicable".

---

# Maven kit (Iraqi + Arab everyday life)

Preview sheets: `maven_cast.jpg`, `maven_sets.jpg` (make fresh ones any time with
`python toon.py library OUT --sets chaikhana,souq,shatt,classroom,rooftop --moods day,night --cast`).

## Maven sets (`"set"`)

| set | what | actors stand at | notes |
|---|---|---|---|
| `chaikhana` | Iraqi tea house: blue kashi-tile walls, brass samovar on a tiled counter (glows in night/interior/golden), shelf of istikan glasses, old radio, wall clock, framed photos, benches with carpet seats, ceiling fan, two hanging lanterns; near plane = a table with an open backgammon board and a tea glass | y 1500-1760, z 1.0, scale 1.0-1.1 | samovar=(800, 900); `golden` close-ups on the samovar or the near istikan |
| `souq` | covered market alley in deep perspective: brick vault, arches, skylights with light shafts, shops with striped awnings, spice cones, hanging carpets, lanterns down the middle, bright exit at the end | y 1500-1700, z 1.0, scale 1.25-1.5 (deep floor: further = higher and smaller) | night = lit shop fronts + lanterns; a camel or far figure at y ~1240 scale 0.45 |
| `shatt` | riverside (Tigris / Shatt al-Arab): stone promenade with iron railing, lamps, bench, a balam boat on the water, shanasheel houses, a blue dome and minaret and palms on the far bank | y 1700-1900, z 1.0, scale 1.0-1.15 | best in `sunset`/`dawn` (sun glints on the water) and `night` (lit oriels) |
| `classroom` | green chalkboard with Arabic chalk text, wall clock, map and alphabet posters, teacher's desk, window light, two rows of desks | teacher x 500-850 y 1300-1360 scale 0.85; students y 1700-1900 scale 1.0 | `"set_args": {"board": "درس اليوم"}` writes your own chalk line |
| `rooftop` | Baghdad flat roof: parapet with diamond breeze-blocks, metal beds with white mosquito nets, air cooler, water tank, satellite dish, string of bulbs, skyline with a dome, minaret and palms | y 1650-1850, z 1.0, scale 1.0-1.1 | made for `night` (stars, moon, lit windows, bulbs) and `sunset` |

## Maven cast (`"type"`)

`hajji` (white dishdasha, red-white shmagh with black agal, white beard and moustache, misbaha beads),
`hajjiya` (black abaya and head cover, tea tray with two istikans), `mom` (coloured hijab, long dress, phone),
`grandma` (white head scarf, glasses, cardigan, samoon bread), `teacher` (shirt, tie, waistcoat, glasses,
moustache, pointer stick), `student` (white school shirt, grey trousers, backpack, book), `schoolgirl` (white hijab,
navy pinafore, pink backpack, book; smaller), `chaichi` (tea seller: kufi cap, embroidered vest, sash, teapot),
`fallah` (farmer: wrapped head cloth, brown dishdasha, sash, shovel), `doctor` (white coat, stethoscope,
clipboard), `footballer` (green jersey with a number, white shorts, ball), `shopkeeper` (bald with side hair,
waistcoat, banknotes).

Overrides per actor (as for every type): `torso`, `accent`, `skin`, `hat`, `hair`, plus `prop` (what the front hand
holds), `number` (jersey), `hijab_col`, `backpack` (colour), `beard` (colour). An act can change `prop` mid-scene.

## Maven animals (`"type"`)

`cat` (round orange street cat, ~230 units tall; `scale` 0.6-0.9 next to a person) and `camel` (one hump, woven
saddle blanket, lead rope; ~520 units tall, `scale` 0.4-0.6). Cast fields: `x`, `y`, `scale`, `z`, `dir`, `expr`
(`happy`, `shocked`, `angry`, `sad`, `sly`; camel: `happy`, `shocked`), `pose` (`stand`, `sit`, `walk`; a move in
`acts` walks it), `torso` (fur colour). They breathe, blink and wag on their own. Actors on the same `z` draw in cast
order, so list far actors first.

## Maven hold items (`"hold"` in acts)

`tea` (istikan on a saucer, steaming), `tray`, `teapot`, `book`, `phone`, `ball`, `samoon`, `money`, `dates`,
`misbaha`, plus the originals `sign:TEXT`, `tag:TEXT`, `newspaper:LINE1|LINE2`, `earth`, `planet:KIND`.
Signs, tags, newspapers and the chalkboard accept Arabic: it is shaped and drawn right to left automatically.

## Arabic

- Captions: Arabic words are drawn in Lalezar (OFL, bundled), shaped and right to left, 1-2 words per caption.
  Short words (و، في، من، على، يا، ما، بس ...) join the next word. Set `"lowercase": false` in the storyboard.
- In-world text: any Arabic string in a sign, tag, newspaper, the chalkboard or `draw_text` is shaped automatically.
- `words` detects an Arabic script and uses whisper `small` (multilingual) with the script as a hint; the built-in
  aligner counts Arabic syllables. Imported ElevenLabs timestamps work the same in Arabic.
- `silent` reads Arabic at 2.0 words/s with 0.4 s after each sentence.
