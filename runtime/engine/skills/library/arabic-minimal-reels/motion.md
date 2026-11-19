# Motion: measured frame counts

Frame counts are at each source's own rate: 14 videos at 30 fps, 2 at 29.97, 3 at 23.976, 1 at 25. At 30 fps, 1 frame = 33 ms. To build at another rate, keep the milliseconds. Format: median (10th-90th), n = samples.

Two methods, labelled in each row:
- **Auto:** a script stepped through every frame and tracked pixels (ink contrast, blue pixels, sharpness). A sample of 28 word entrances was checked by eye against frame-by-frame crops.
- **Hand:** I read the frame strip myself. Strips at step 1 are exact; step 2 is +-2 frames, step 3 is +-3, step 6 is +-6. Each hand row is 1 to 3 examples, not a statistic.

## Text entering (auto)

"Frames to 90%" counts frames from the first visible frame until the word reaches 90% of its final contrast. 1 means it is fully there on its first frame.

| Where | n | Pop (1 frame) | Fade | Fade length, frames |
|---|---|---|---|---|
| On the face | 447 | **58%** | 30% | 5.5 (4-7) |
| On B-roll | 158 | 41% | 47% | 5 (4-6.6) |
| On a painting | 38 | 16% | **66%** | 5 (5-7.6) |
| On a canvas | 170 | 15% | **71%** | 6 (5-8) |

The rest (12%, 12%, 18%, 14%) sit at 2-3 frames or could not be scored.

- **So the same word treatment is not used everywhere.** On a moving, busy face a word slams in. On a clean canvas the same word breathes in over 200 ms. A fade on a face is usually the serif italic word; I saw this in the strips but did not count it.
- **Fade curve on canvas,** level per frame, median: 33%, 40%, 64%, 66%, 72%, 88%, 92%, 100%. Fast at first, then eases.
- **It also sharpens.** Median sharpness inside the word: 72% of final on frame 1, 88% on frame 3, 98% on frame 6. So it is a small blur-in plus opacity. The blur radius itself was not measured; start low, about 2-4 px at 1080, and compare by eye.
- **Small words on canvas and B-roll** behave like the fade row: 6 frames (few samples: 4 and 17).
- **Scale during entrance could not be measured.** Width changes in the first frames are smaller than what blur and thresholding cause at 360p. By eye in strips, some words start 3-5% larger and settle over about 5 frames. Treat as optional.
- **No letter-by-letter anywhere:** a word enters whole in all 28 rows checked by eye and in every strip I read.
- **No slide-in on words.** Vertical shift during entrance has a median of 0 px.

## Blue block wipe (auto, n = 45)

- 12 frames (4-19). Two clusters: 3-6 frames (fast) and 14-18 frames (slow).
- Direction: left edge fixed 60% (27), grows from both sides 38% (17), right edge fixed 2% (1). For Arabic, mirror: right edge fixed.
- Width over the move: at 0/20/40/60/80/100% of its time it is 25/52/68/82/95/100% of full. Strong ease-out, and it starts at a quarter, not at zero.
- Hand (step 1): the block's edge reveals the white word inside as it travels. The text does not fade separately.

## Lines and camera

| Move | Method | Frames |
|---|---|---|
| Line tip drawing, blue pixels growing | Auto, n = 26 | 11.5 (5.5-21) |
| Whole zigzag line with objects | Hand, step 5 | about 25 |
| Thick arc entering | Hand, step 5 | about 20-30 |
| Camera whip to the next place on the line, with motion blur | Auto, n = 7 | 8 (5.6-19) |
| Same whips by hand | Hand, step 1-5 | 7 to 9 |
| Graph camera push-in | Hand, step 6 | about 12 |
| Graph camera pull-out to show the whole curve | Hand, step 6 | about 6 |

The whip comes **after** the current phrase has been held, and the next word arrives only after it lands.

## Objects (hand)

| Move | Step | Frames |
|---|---|---|
| Seed dot holding before it grows | 1 | 5 |
| Group of circles growing from the dot, ease-out | 1 | 11 |
| Cut into one circle, then settle | 1 | 6 |
| Whip from one circle to the next | 1 | 7, then holds about 16 |
| Card with motion blur sliding in and settling | 1 | 5-6 |
| Card to card on white, with blur | 1 | 6-8 |
| Card pop (scale up from small) | 1 | 3-4 |
| Image triangle sliding out from behind a circle, with blur | 1 | 7 |
| Same triangle swinging to the other side | 1 | 10 |
| Half circle arriving | 2 | 4-5, then slow drift while it holds |
| White ball growing from nothing | 2 | 8 |
| Thin arrow drawing | 2 | 18 |
| Sphere growing from a dot to full size, ease-out | 2 | 20 |
| Sheet of paper flying in with rotation | 2 | 8-9 |
| Bar filling, first bar | 3 | 15 |
| Bar filling, the key bar | 3 | 30 |

## Cuts (auto)

- 700 scene changes: 81% are one-frame hard cuts. 8% run 3 frames. The rest are 2 to 12 or more.
- Blur at the cut, measured from the face side where there is detail to measure:

| Cut | n | With blur | Frames when blurred |
|---|---|---|---|
| Face to graphic | 170 | 12% | 4 (1-5) |
| Graphic to face | 169 | 28% | 5 (2-11) |
| Face to face, leaving | 121 | 13% | 2 (1-4) |
| Face to face, arriving | 121 | 24% | 5 (2-10) |

**Blur is the exception.** Most changes are plain cuts. Where it exists it is more common when arriving on a face. Blur from a graphic's side could not be scored reliably, because a canvas has little detail.

## Inside a scene (auto, frames)

| Scene | Frames from cut to first word | Frames from last word to the cut |
|---|---|---|
| Face | 6 (1-16) | 8 (0-20) |
| B-roll | 4 (1-15) | 4 (0-16) |
| Painting | 5.5 (2-18) | 6 (0-18) |
| Text-centric | 6 (2-16) | 8 (0-18) |
| Object | 7 (2-15) | 10 (1-23) |
| Side | 7 (5-10) | 3 (1-14) |
| Centre | 2 (1-11) | 11 (2-26) |
| Line | 6.5 (2-28) | 8 (0-34) |
| Line + illustration | 15 (5-60) | 21 (10-34) |
| Graph | 7 (2-15) | 11.5 (6-28) |

Practical meaning: open empty for about 6 frames, end about 8 frames after the last word lands.

Exit: in about 2 of 3 scenes the text is still fully on screen at the cut, so the next scene does the exit. In about 1 of 3 (29% canvas, 36% B-roll, 32% painting, 34% face) the text ink fell by 30% or more in the last 14 frames. That covers both caption line changes and real fades or blurs, and I did not separate them. When a text fade-out appears in the strips, it takes 3-5 frames.

## Slow drift: low confidence

Estimated scale change per second from frames at 20% and 92% of the shot, keeping only good matches (correlation above 0.6):

- Face: 0.9%/s in absolute size, but no direction (44% in, 56% out, mean 0.02%/s). Head motion may be most of this.
- B-roll: 2.1%/s (n = 67), 52% in. Painting: 1.6%/s (n = 16), 25% in. Text-centric: 0.8%/s (n = 12), 25% in.

A "quick camera slide-in" on paintings is often described. I did **not** confirm this. In the painting strips I read at step 1, the painting mostly arrives on a hard cut and drifts slowly. Build a slow drift of 1-2%/s and test a slide only if it needs energy.

## The feel

- Words hit in time with speech and never travel.
- Graphics ease out: fast start, slow land, with no bounce and no overshoot seen in any strip.
- Long holds, about 16 frames or more, between short moves. Motion takes about 200-700 ms, then stillness.
- Motion blur on anything crossing the frame, none on what is holding.
