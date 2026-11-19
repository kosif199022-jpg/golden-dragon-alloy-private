# Style: sizes, layout, textures, colours

All numbers are for a 1080x1920 frame. They were measured on 360x640 sources and multiplied by 3, so a size is good to about +-3 px and anything under 12 px is a rough figure. "Ink height" is the height of the actual pixels of a text line, not the font size. Format below: median (10th to 90th percentile).

## Text sizes (measured on the settled frame of every shot, 691 shots)

| Scene | Key line ink height | Key line width | Key line centre Y | Small word ink height | Key / small ratio |
|---|---|---|---|---|---|
| Face (captions) | 86 (42-167) | 465 (147-705) | 1140 (958-1353) | 27 (9-54) | 3.8 (1.3-11) |
| B-roll + text | 126 (42-194) | 544 (152-786) | 1029 (734-1312) | 24 (9-60) | 3.9 |
| Painting + text | 108 (57-201) | 520 (152-717) | 983 (738-1117) | 26 (12-60) | 4.0 |
| Text-centric | 126 (52-192) | 703 (372-843) | 948 (744-1018) | 42 (10-72) | 3.2 |
| Object, side, centre illustration | 135 (33-189) | 486 (77-814) | 595 (230-1531) | 18 (9-83) | 4.3 |
| Line and graph | 147 (51-189) | 393 (48-675) | 978 (240-1268) | 30 (18-60) | 4.8 |

- Text is centred horizontally: key line centre X is 537 on faces, B-roll, paintings and text-centric (frame centre is 540). Off-centre only in side illustrations and graphs.
- Median 2 text lines on screen at once on faces and in line scenes; 1 on B-roll and text-centric.
- Rough font sizes, derived from ink height using Inter's measured glyph heights (H = 0.73 em, a full word with ascender and descender = 0.97 em): key word about 100 px on a face, about 150 px on a canvas or B-roll; small words about 34-38 px. These font sizes are derived, not measured directly.
- Largest measured key line: 1080 wide, a word bleeding off both edges behind the head. Rare.

## The look of the words (by eye, from the board)

- The line is a bold grotesque sans, tight tracking, white on image, near-black or blue on white.
- The key word is one of: much larger bold sans; large bold serif italic; or set inside a blue block.
- Small words sit tight against the key word, above or below it, often on both sides of it: "small / BIG / small". Not on a separate far-away line.
- Word spacing inside the "small small" line is often wide, because each word holds its slot before the next is spoken.
- Ending punctuation is kept (a full stop or comma stays on the word).

## Hook title (10 of the 20 videos open with it, median 2.9 s)

- Serif title, 3 lines, left aligned, starting at about x 75, y 177. Each line 85-117 px ink height.
- One phrase in blue italic serif.
- The speaker's head is cut out and sits in front of the end of the title, on a dark navy glow. The caption keeps running on his chest.
- Sometimes a very small uppercase note under the title.

## Blue block (highlight), 45 measured

- Height 48 (25-131), width 639 (242-844), centre of the frame vertically in most (top edge Y 933, 815-1313).
- By eye, not measured: square or barely rounded corners, white text inside, tight fit around the word.
- Used on: text-centric 14, face 14, B-roll 8, painting 3, object 3, side 2, centre 1.

## Lines and dots

- Line thickness: 12-30 px, median 24 (14 of 17 lines). Hairlines sit near 12-18, bold arcs near 24-30. The other 3 readings came out at 66-100 px and may not be lines; I did not check them.
- Line colour: blue on dark; near-black on white; soft glow on dark.
- Dot on line: white, about 21 px core (13-62 including glow, 78 blobs). In graphs the dot is blue.
- Grid lines in graphs: 1-3 px, low-contrast white. Dashed blue line marks a level.

## Colours (median of pixels)

| Thing | RGB | Hex |
|---|---|---|
| White canvas | 249, 249, 253 | #F9F9FD |
| Blue canvas, centre | 21, 108, 241 | #156CF1 |
| Blue canvas, corners (vignetted ones) | 6, 86, 246 | #0656F6 |
| Pure flat blue (seen in 5 of the videos) | about 0, 78, 253 | #004EFD |
| Dark canvas, centre | 15, 18, 22 | #0F1216 |
| Dark canvas, corners | 9, 9, 10 | #09090A |

Accent blue isn't one colour across the references. Block blue per video, by median:
- Saturated royal, 5 videos: #004EFD, #024CFE, #054DFF, #074CFC, #0343E0.
- Clean mid blue, 6 videos: #136BFA, #1E6EFB, #266DF2, #0F6DD6, #066CDD, #198EE2.
- Pale or muted, 4 videos: #5BA8EE, #4495F6, #4B7FCB, #407CA2.

Rule: one blue per video, never two. (5 videos had too few blocks to score.)

Starter blues if you have no brand colour: #1F7EF2 for lines, blocks and canvases, #4EA6FF for glows on dark, #1642DE for print or cloth textures.

Canvas counts in graphic scenes: white 37, blue 31, dark 30, other 40 (other = images and gradients).

## Textures: what could and could not be seen

- At 360p with YouTube compression the grain measures near nothing: std 0.8 on white, 0.5 on blue, 0.3 on dark (out of 255). **That is a limit of the source, not proof the originals are clean.** Rough paper may be there in the originals; in these sources it only shows clearly in a few places.
- What is visible: soft blue glow in the white canvas (a pale blue cloud from the edges), vignette on blue canvases, faint dotted or wavy pattern on some white canvases, soft fade to black at the bottom of face shots.
- Face shots get darker towards the bottom: median brightness runs 82 at half height down to 29 at 95% height. I could not separate this from dark clothes, but by eye most have a gradient under the caption.
- Add your own paper or cloth texture subtly if you want it. It is a choice, not something measured here.

## Scene recipes

1. **Captions (face).** Face fills the frame on black or a dim set, caption on the chest. 42% of face-to-face cuts change scale by 1.2x or more, so a jump cut is also a punch in or out. Head stays in the top half.
2. **B-roll + text.** Moody, dark, filmic clip. 1-3 words, white, centred, placed over the darkest calm area. Text can sit behind a subject (rare).
3. **Painting + text.** Classical oil painting, single figure centred, full bleed. Text on the chest. Portraits and old black-and-white photos behave the same for a named person.
4. **Line + text.** Dark or white canvas. Line enters from an edge, passes through or just above the text, leaves to another edge. White dot sits where the line meets the text. Next phrase: camera follows the line to a new spot.
5. **Line + illustration.** Same line ending at an object, or zigzag with objects on both sides, or vertical with a label beside each bend.
6. **Text-centric.** Flat white, blue or dark. Either (a) a quote: large marks on both sides, small words above and below the key words; (b) a key word; (c) block highlight; (d) a list down a dark canvas with glowing dots.
7. **Centre illustration.** One figure in the middle or lower half, text in the space above and below. Blue-tinted anatomy, a silhouette, a body outline, a glowing figure.
8. **Side illustration.** Half circle or scan bleeding off one edge, text on the other side. The same half circle returns for each list item.
9. **Object + text.** One object, big: a sphere, a target, a sheet of paper, numbered circles, overlapping circles with icons, an image card on white.
10. **Graph + stats.** Dark, faint horizontal grid, white thin axes, white curve, blue dot at the tip, label in small caps with a thin arrow. Bars with a soft glow. A quadrant chart that fills a point at a time and returns between face shots.
