# Restyle: same video, new lettering, light and motion

For «قلّده تماما بس غيّر الكتابة / الإضاءة / الموشن» (first used 2026-11-24 on a @youma.design reel, 27.5 s).

1. `python3 clean_regrade.py src.mp4 clean/` removes burned-in white lyric text inside the caption box
   (y 930-1135 on 1080x1920: top-hat of thin bright strokes, low saturation, inpaint Telea) and regrades every
   frame (soft S-curve, teal shadows / warm highlights, bloom on lights). ~0.5 s a frame.
   Move the box (`Y0, Y1, X0, X1`) if the text sits elsewhere; check 3 frames first.
2. `web/main.js`: lines with word times (`L`), key words in warm gold with a moving glint, words rise from
   blur, a light line draws under each line, two-line couplets, projector beam over a cinema shot, warm leak,
   vignette, grain, slow push-in. Render with `../fast_reel/render.mjs web frames 0-N 4` (825 frames: 27 s).
3. Mux the original sound at -14 LUFS.
Reusing another creator's footage and sound is for private drafts; publish with the owner's own footage.
