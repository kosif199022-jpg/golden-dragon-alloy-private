# Production guide: shots, sound, checks, troubleshooting

## Shot vocabulary (with the call that makes each one)
| shot | use it for | code |
|---|---|---|
| Fly-over | the rule line at 0 s, and new worlds | `CAM.fly(u, from, to, tgtFrom, tgtTo, 46)`, travelling 100+ units in about 1 s |
| Low angle up at something huge | cubes, statues, creatures, the sky | `look(V(x, 1.5, z), V(x2, 40, z2), 55)` with deep focus `dof(80, .0004)` |
| Medium walk-away | the hero going somewhere | `CAM.follow(u, hero)` with `pose(hero, walk(t))` |
| Face punch-in | every emotional beat (shock, joy, fear) | `CAM.punch(u, faceOf(hero))` with `dof(4, .007)` and a big-eyes expression |
| Insert | objects named in the voice: timer, note, door, cake | push from 4 to 2 units, `dof(3, .008)` |
| Over the shoulder | the hero acting on something | camera behind and above the shoulder, aimed at the object |
| Orbit | crowds, reveals, magic moments | `CAM.orbit(u, centre, r, a0, a1, y)` |
| Crane down | arriving in a new place | `CAM.dolly(u, high, low, tgtHigh, tgtLow)` |
| Tilt up into the sky | the final reveal | `CAM.tiltUp(u, pos, tgtLow, tgtHigh, 60)` |

**Timing rules**
- Cut 40 ms before the noun, using `C(wi('noun'))`. Never cut mid-word.
- Shots run 0.5–1.6 s, with an average near 1 s. A shot longer than 1.6 s needs strong motion.
- Two cuts must sit at least 0.4 s apart.
- The reaction punch-in lands on the word that carries the emotion ("froze", "dark", «قديمة»).

**Framing checks**
- The caption band (y 1230–1400) should sit over something readable but not over the eyes.
- A face in a close-up belongs in the upper half of the frame.
- Check nothing sits between the camera and the subject: candles, balloons, trees, tower roofs.

## Sound recipe (cues.json)
| moment | sound (shared library `LIB:` or Mixkit) | level |
|---|---|---|
| fly-in at 0 s | transitions/whoosh_air | -3 |
| whip cuts (about every other cut) | whoosh_fast, whoosh_arrow, whoosh_sparkle, whoosh_cinematic (rotate them, no sample more than twice) | -7 to -13, `align: peak` on the cut |
| magic | magic/sparkle, glitter, fairy_whoosh, sparkle_wand, poof | -5 to -12 |
| reaction punch-in | impacts/bass_hit or impacts/horror_hit | -12 |
| reveal or twist sting | impacts/cinematic_impact, or thunder (Mixkit 1294 from 3.0 s) | -3 to -6, after the last word |
| creatures | Mixkit 309 dragon roar, animals/beast_roar, animals/wings_flap | -2 to -12 |
| places | nature/birds_forest, animals/rooster, Mixkit 580 school bell, Mixkit 722 fanfare | -7 to -14 |
| doors | ui/door_creak_open, ui/key_in_lock | -9 |

- **Cue times**:
  - A number of seconds.
  - `word:dragon+0.5`: half a second after "dragon".
  - `word:the#3`: the third "the".
  - `cut:5`: the start of shot 5. This needs `shots.json`, which any render writes.
  - `end-1.0`: one second before the end.
- **Ducking**: `duck_db` -16 keeps effects about 16 dB under the voice. mix.py prints the voice-vs-everything-else number; aim for the worst window at 9 dB or more and the median at 18 dB or more.
- **Music**: the house rule is no music on narrated reels, because the user adds it in-app. When asked for it, add `"music": {"file": …, "lufs": -34}` to cues.json. The reference used a constant bright pop bed with pizzicato and vocal chops.
- Never synthesize effects. Download missing sounds from Mixkit, using `https://assets.mixkit.co/active_storage/sfx/<id>/<id>-preview.mp3` (ids appear on the mixkit.co category pages), then pick between candidates with earshot `rank`.

## Checks before delivering
1. `build.py <p> shots` gives one still per shot. Look for: is the subject readable, is anything blocking it, is the caption over the eyes.
2. `build.py <p> stills a,b,c` for the moments around reveals and punch-ins.
3. After `final`, look at `check/final.jpg` (3 fps). Look for empty-sky frames, white blow-outs, and the camera inside props.
4. Run earshot `timeline` on the mp4: loudness should read -14 LUFS / about -1.8 dBTP, and cue sync should be within 100 ms. Say what still needs a human listen.

## Troubleshooting
| symptom | cause and fix |
|---|---|
| black frames | NaN in exposure or colours, usually `setTOD` with a missing preset name |
| "rendering on SwiftShader" | the GPU flags were lost. render.mjs launches Chromium with `--use-angle=d3d11 --enable-gpu`; check the NVIDIA driver |
| a person is missing | they were built with `add: false`, or a shot hid them and `onReset` doesn't restore them |
| one frame suddenly darkens | the camera went through a head or prop. Register the object with `extras([...])` or move the camera |
| everything white or blown out | an emissive surface (door light, window) or a strong room light. Lower `glow` or `light`, or use a darker TOD |
| face in shadow | the sun is behind the character. Make a TOD variant with `sd` pointing from the camera side |
| Arabic timings in the 30 s range | whisper got a garbled prompt. voice.py only sends the prompt for ASCII text, so re-run with `--timing-only` |
| a cue lands on a word | move it to `word:<last>+0.4`, use `align: peak` for whooshes, or lower its gain |
| `word not in timing` error | `wi()` text doesn't match the script. Punctuation and diacritics are ignored, but spelling must match |
