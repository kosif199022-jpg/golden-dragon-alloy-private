# Styles kit — the owner's proven canvas film looks, as data (v1.2)

Six canvas film engines that were delivered to the owner in Nov 2026, rebuilt as one shared kit (`common.js`) plus one
small file per style (`styles/*.js`). Every style reads `window.CFG`, written from one JSON spec by `build_style.py`:
no paths, names, credits or timings live in the code any more.

## Quick start

```bash
python3 scripts/dragon.py tool styles my_film.json --check                      # copy examples/<style>.json first; checks every field
python3 scripts/dragon.py tool styles my_film.json --out job --stills 2,9.5,20  # stills of the hard moments: look, fix, repeat
python3 scripts/dragon.py tool styles my_film.json --out job --render           # the film: job/<name>.mp4 (exact length, verified mux)
```

On Windows use `python`. `scripts/dragon.py tool styles …` runs `tools/styles/build_style.py …`; both work.
`--list` prints the styles and their knobs.

## What a build does

1. **Spec** (`--check` stops here): every field is checked and named in the error; typos (`"duraton"`) are reported;
   lints from real incidents (Lalezar has no `…`: replaced with `،`; `·` next to Arabic digits; explainer words such
   as «الفصل»; numbered chapters; the light leak). Paths are relative to the spec's folder; Arabic names are fine.
2. **Frames**: one ffmpeg cut per shot into `job/frames/S00/f0001.jpg…`: a 9:16 crop from `focus`/`box`/`zoom`
   (phone rotation handled), scaled to 1080x1920, `setpts` for `speed`, 30 fps, `-q:v 5`, plus 0.7 s of tail so a
   dissolve never runs out of frames. A cut that did not change is reused (`--force` cuts again).
3. **Page**: `job/index.html` + `common.js` + `<style>.js` + `fonts/` (`--embed-fonts` puts them inside the page).
   Open it in a browser to scrub; `window.__kosif.seek(t)` draws any moment.
4. **Song** (when `song` is given): the section `[start, start + duration]`, square-root fade in, linear fade out,
   `loudnorm` to −14 LUFS (true peak −1.5), padded/cut to exactly the film length, AAC 320k 48 kHz → `job/mix.m4a`.
5. **Stills** (`--stills t1,t2`): PNGs in `job/stills/still_<t>.png` through `app/engines/render/render.cjs`.
6. **Film** (`--render`): `render.cjs` (with `--recycle 120`, the renderer's own default, when it has that flag, read from its header),
   black-frame guard on; then `engines.qa.black_runs` scans the result and `engines.deliver.patch_black` clones the last
   good frame over any black run left inside the film; then `engines.deliver.mux` gives exactly `round(duration*fps)`
   frames and AAC audio (never `-shortest`; plain ffmpeg without `-shortest` when the engines are not importable).
   `job/build_report.json` records every step; `render.log` / `stills.log` keep the renderer's output.
   A JavaScript error in the page fails the build (`[page error]` lines). `--tidy` deletes `frames/` and the silent
   `video.mp4` after a good film.

Exit codes: `0` done, `1` a step failed, `2` bad spec or usage.

## The six styles

| style | first film | owner verdict | use it for |
|---|---|---|---|
| `nil` | «بنت النيل» (Sherine), 2026-11-08 | none yet | a slow, emotional song |
| `beat` | «قوم يا مصري» (Mohsen), 2026-11-08 | none yet | only when he asks for energy («حماسي») |
| `wall` | «حلوة يا بلدي» (Dalida), 2026-11-08 | none yet | many moments, one camera |
| `medal` | «ميار عثمان» (saas-animation manner), 2026-11-06 | none on the film (approved the storyboard only: «نفذ» 2026-11-06) | one shape carrying a short film |
| `chapters` | «ميار… بنت مصر», 2026-11-06 | criticised: he asked to organise («نسّق» = chronological order + fixed text slots), not for chapters; numbered chapters rejected 2026-11-08 | an organised film, verses, interviews |
| `clean` | 40 s «ميار، بنت مصر», 2026-11-06 | criticised: organisation unclear (2026-11-06 11:27) | an elegant tribute, her words only |

The trio (`nil`, `beat`, `wall`) was made the same morning as three deliberately different films; the owner had asked
for three films «not like explaining to students». Pick a different style per film in a series.

### `nil` — slow and warm
Letterbox bars grow to 150 px in the first 1.6 s, a warm grade, an 8 % push per shot, 0.7 s eased dissolves, vignette
and grain; a gold Ruqaa title (190 px) scaling 1.05 → 1.0; her words in Tajawal 62 at y 1620, word by word; the end
card is a gold Ruqaa name with the credit 1 s later.
Knobs: `grade`, `push` (0.08), `dissolve` (0.7), `letterbox` (150), `leak` (false), `vignette` (0.5), `grain` (0.04).
`leak: true` brings back the warm light-leak sweep of the original film; it is off because the owner removed sun /
light-leak washes from his films on 2026-11-01 (and asked on 2026-10-29 to drop the sun-light look, «بدون الإضاءة
الشمس»); «بنت النيل» was delivered on 2026-11-08 with the sweep in every dissolve and he did not reply.

### `beat` — cut on the beat
Shots are placed on the beat grid (`beat: {period, phase}` in film time, or `bpm`, or `"auto"` with librosa): each
`shots[].beats` long, the film opens at 0 s. A punch-in on every cut (`1 + 0.12·e^(−9t)`), a 0.16 s whip smear on every
second cut (skipped next to `broll`), one three-panel split (`{"tri": [3 shots], "beats": 8}`: panels arrive one per
beat, the middle one opens to full frame), heavy Lalezar `slams` (`{text, beats: [a, b]}`) with a red underline, and an
end card in white Lalezar over a 50 % dim. A `{"rest": true}` shot runs from the last beat to the end.
Knobs: `beat`, `grade`, `punch` (0.12), `whip` (true), `bar` (`#c8102e`, null hides), `vignette`, `grain`.
On 2026-10-26 the owner called fast flash/glitch cutting annoying: keep this style for briefs that ask for energy.

### `wall` — a living wall
`tiles` (3 per row) loop 2.9 s each at 360x640 / 15 fps, every tile at its own offset so they never pulse together.
The camera opens inside the first hero tile, rises out to see three tiles across, dives into the next hero (2.2 s,
zoom eased in log space) where full-size frames take over, and ends pulled back on the whole wall under the end title.
Tiles away from the centre sit a little darker; gold hairline borders. The `title` becomes the first line in gold Ruqaa.
Fields: `tiles`, `heroes: [{tile, start, end, ss?}]` (start the first at 0; give each 2.4 s or more).
Knobs: `cols` (3), `loop` (2.9), `vignette` (0.5), `grain` (0.03).

### `medal` — one shape carries the film
A gold «١» medal drops onto a red field, squashes, then grows into the first shot (which starts at about 2.5 s). Each
later shot arrives by its `move`: `iris` (a circle opens from the centre; irises alternate ink / red), `flip` (the frame
closes into a rounded card over a blurred world and flips edge-on to the next shot), `flood` (the card floods gold and
grows to fill the frame; the next shot eases in out of the gold). Flips must end with a flood. At `end.at` the frame
shrinks back into a circle that becomes the medal again, with the end title under it. Nothing cross-dissolves.
Shot fields: `move`, `at` (the move's time when it differs from `start`), `fill` (iris colour).
Knobs: `field` (`#b5121b`), `ink` (`#0b0b10`), `medal_text` («١»), `grain` (0.03).
Send the owner a numbered storyboard (time, shot, line, how it becomes the next) and wait for his yes before building.

### `chapters` — the organised film
Full-bleed shots, 0.16 s dissolves between shots of her (no ghost double faces), 0.5 s next to `broll`. Every text type
has one fixed slot for the whole film: `chapters` at the top (y 300: white Tajawal title and a gold line drawing in; the
numeral only with `"numbers": true`), her words as subtitles at the bottom (`lines`, Tajawal 50 at y 1580), a Quran verse layer in ScheherazadeNew-Bold
(`verses`: lines split by `|`, ﴿ right of the first line and ﴾ left of the last, each drawn alone outside the RTL line,
`ref` in gold below without brackets; the text comes from verses.json letter for letter, references/AUDIO_SONGS_QURAN.md §19), and optional `lyrics` (gold Ruqaa band), `labels` (top card) and `lowers`
(TV lower-third with a flag strip) from the references the owner liked on 2026-11-06 («شوف المونتاج ده عجبني جدا»).
End card: gold Ruqaa title, white and gold lines, optional `flag` strip, credit 2 s later.
Knobs: `numbers` (default false; true draws the numerals), `dissolve` (0.16), `dissolve_broll` (0.5), `push`, `vignette`, `grain`.
On 2026-11-08 the owner asked for films «ليس بأسلوب شرح للطلاب يتقول الفصل الأول»: numerals stay off unless he
asks for chapters (`"numbers": true` makes the build warn). Never show two text items at once; caption a voice only with a verified name;
no song under a recitation.

### `clean` — the clean tribute
Full-bleed shots, a 6 % eased push, 0.14 s dissolves (0.5 s next to `broll`), vignette 0.42 and grain; a gold Ruqaa
title (250 px) over the opening aerial; her words (`lines`) in white Ruqaa 76, word by word in the lower band (`|`
breaks a line, long quotes wrap at 900 px); the footage dims before a gold Ruqaa end title and the credit.
Knobs: `dissolve` (0.14), `dissolve_broll` (0.5), `push` (0.06), `vignette` (0.42), `grain` (0.035).

## Spec fields (all styles)

| field | meaning |
|---|---|
| `style` | `nil`, `beat`, `wall`, `medal`, `chapters` or `clean` |
| `duration`, `fps` | film length in seconds, frames per second (30) |
| `name` | final file `job/<name>.mp4` (default: the spec's file name) |
| `watermark` | persistent text bottom left; the owner's is `© Mahmoud Elkosif` |
| `credit` | 1–2 end-card lines; the owner's: `مونتاج وإخراج Mahmoud Elkosif`, `تابعني على فيسبوك` |
| `song` | `{path, start, fade_in, fade_out, normalize?, copy?}`: the section of the song under the film. `normalize: false` skips loudnorm (still AAC 320k). `copy: true` copies an AAC song as it is (no fades, no loudnorm; MD5 of the packets checked when `start` is 0) and the exact mux cuts it. LUFS before / after go in `build_report.json` |
| `requirements[]` | the owner's demands word for word (strings, ids r1, r2 … or `{id, text}`); a shot or text with `"covers": ["r1"]` delivers one. `--check` exits 2 on a requirement nothing covers |
| `shots[]` | `src` (video or image), `ss` (in-point), `start`/`end` (film time), `focus` [x, y] in the box (0.5, 0.42), `box` [x, y, w, h] source pixels (cuts burnt captions / logos), `zoom` (≥ 1), `speed` (< 1 slow motion), `broll`, `covers` |
| `title` | `{text, sub?, start?, end?, size?, y?, font?}` or a string |
| `lines[]` | `{text, start, end, font?, size?, gold?, y?}` or `[text, start, end]`; drawn in the style's slot |
| `end` | `{at, title?, sub?, sub2?, size?, flag?}`; `null` = no end card (and so no credit). The credit starts 1–2 s after `at` but never after `duration − 3`, so it holds about 3 s |
| `chapters`, `verses`, `lyrics`, `labels`, `lowers` | drawn by the `chapters` style only; in any other style they are a spec error (v1.3: they used to pass and never show) |
| `cache` | image cache size, at most 16 |

Fonts by name: `Ruqaa` (Aref Ruqaa Bold), `Tajawal` (Bold), `Lalezar`, `Messiri` (El Messiri 700), `Amiri` (Bold; not for Quran: it lifts U+0670), `Scheherazade` (ScheherazadeNew-Bold, the Quran font, added to the page whenever `verses` is used).
Keys that start with `_` are notes and are ignored (the examples use `_doc`).

Credit slot per style (y of the first line, sizes): `nil`, `wall`, `beat` 1500 (40/30) · `clean` 1440 (44/34) ·
`chapters` 1420 (42/32) · `medal` 1560 (36/30). Each sits under its own end card on purpose (OWNER.md §9).

## `--check` (v1.3)

`python3 build_style.py SPEC.json --check [--allow-missing]` runs no ffmpeg render and no browser. Exit 2 on:
a requirement nobody covers; a missing file (with `--allow-missing`, for templates, a warning); `ss` + the shot's
length past the clip's end; a banned name from `bans.json` (seeded from LESSONS.md «ممنوع على الشاشة»); a song under
Quran verses; text left from the examples (a warning with `--allow-missing`). Warnings: two texts at once (title,
chapters s..s+2.6, lines, verses, lyrics, labels, lowers, end card), a credit pulled before the end card, text below
y 1700. `--render` patches black runs of up to 3 frames; a longer run prints `BLACK_RERENDER t=a-b` and exits 1
(render those seconds again with `render.cjs --start`).

Disk: `--stills` cuts every frame of every shot first (about 2 MB per film second). On a tight disk run `df -h .`
first, and delete `job/frames` between big spec changes. A landscape or small picture gets a warning when no
`focus` is set or the 9:16 crop is under 1280 px tall (it would be upscaled).

## Engine lessons kept on purpose

- **Image cache ≤ 16, no `img.decode()`**: 120–160 decoded 1080x1920 images made headless Chromium draw runs of black
  frames (Y = 16, watermark gone) that grew with the number of frames one page had rendered.
- **A frame that fails to load** is retried 4 times (150 ms apart), then the shot's last good frame is drawn; with none
  yet, an earlier frame of the shot. The canvas never shows an empty frame.
- **Deterministic frames**: drawing depends on `t` only; grain is seeded by the frame number (no `Date.now`,
  `Math.random`), so any frame can be re-rendered in a fresh page and match.
- **Pushes only grow**; transitions are made by the camera or a shape, never a long crossfade between two faces.
- **Arabic**: RTL word-by-word reveals (blur → sharp, small rise), lines too wide are scaled to fit; Lalezar gets no `…`.
- **Delivery**: render.cjs reloads the page every 120 frames (`--recycle 40` for heavy photo pages) and retries black frames in a fresh page; leftovers are
  patched by cloning the previous frame; the mux is exact (an earlier `-shortest` mux ended 3 frames short) and the
  audio is AAC (MP3 inside MP4 played silent on the owner's iPhone).

## Files

`common.js` shared kit · `styles/*.js` the six styles · `build_style.py` the builder · `examples/*.json` one spec per
style (placeholder paths) · `fonts/` the five TTFs and `OFL.txt` (SIL Open Font License 1.1, unchanged) · tests:
`app/tests/test_v12_styles.py`.
