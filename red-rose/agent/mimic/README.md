# Mimic: copy a reference video's text to the pixel

When the owner says «قلّده بالظبط / بنفس الخط / بالملي», measure the reference instead of guessing.
Everything runs locally (no network except `google`), about 20 s per element over ~1,400 fonts.

| Step | Command | What it gives |
|---|---|---|
| 0. Font pool (once) | `python3 -I mimic.py google --set all` then `mimic.py fonts` | Google Fonts Arabic + Latin, the font library, calligraphy fonts: one index |
| 1. Find the text | `mimic.py detect ref.mp4 --t0 0.5 --t1 20` | boxes of text that stays still over the footage + `detect.jpg` |
| 2. Measure each element | `mimic.py measure ref.mp4 --static T0,T1 --box x0,y0,x1,y1 --text "..." [--ltr] --preview p.jpg --out e.json` | exact ink box, fill / outline colour and width, shadow, ranked fonts, and a ready `draw` object |
| 3. No font close enough | done inside `measure` (`verdict: trace`): the word's outline is traced from the reference into an SVG path (a font built for that word) | pixel-exact shape; `fallback` keeps the closest font for a different word |
| 4. Render | put the `draw` objects into `spec.json` → `elements`, the line font into `spec.line` | the fast-lane engine draws them on every frame |
| 5. Check before delivery | `mimic.py verify ref.png ours.jpg --elements els.json` (boxes + `fill`) | ✅/❌ per element: overlap, colour Δ, box shift in px |

Rules that came from the first run (@oaun.11 Wednesday reel, 2026-11-24):
- Use `--static` with a span **inside one shot**: the header is redrawn on each shot, so a long span blurs it.
- For a line that changes, measure one frame (`--t`) with `--polarity light`.
- Keep the box off neighbours (an underline, the line above); pieces touching the box edge are dropped.
- Scores: ≥ 0.62 use the font; below that trace the word. Verify passes at overlap ≥ 0.80, colour Δ ≤ 60, shift ≤ 8 px.

Measured result on that reel: day name, date and underline 100 % overlap, Hijri month 96 %, the number 89 %,
all colours within Δ 33; the line font found on its own was Sultan Display (the original's family).

- (2026-11-24, @alrihanii) Header pieces: trace with `--static` inside one shot. Dua lines with tashkeel: trace from **one frame** (`--t` mid-line, `--polarity light`): the static mask drops dots and harakat when the line animates. Check every trace on black before rendering (a bright background patch shows up as a block), keep traced outlines at 2 px, and give traced text `shadow` on bright footage.
- (2026-11-25, @alrihanii «صباح») Lines over moving footage (a Quran page behind): `trace --tmin T0,T1 --colour #fbfbfb --tol 90` takes the per-pixel minimum over the shot: the background darkens, the still white text stays, dots and hamzas kept. A multi-colour header is one trace per colour (`--colour #fee800 --tol 150`, `--colour #19c95f`, white date …); thin parts over a bright patch: trace that piece from a frame where its background is dark. Colour traces keep pieces down to 12 px (dots).
- (2026-11-26, @oaun.11) `--tmin` needs a span where the text stays still: oaun whips shake the whole frame, so header spans go inside one shot, and lines that zoom while held are set in the measured font instead. Hairline Latin caps: use `measure --ltr` (Cinzel matched) rather than a trace.
