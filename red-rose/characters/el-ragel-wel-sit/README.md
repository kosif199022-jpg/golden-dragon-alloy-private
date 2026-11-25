# الراجل والست (the owner's two recurring characters)

When the owner says «الراجل والست» (or «الراجل» / «الست») he means these two, from his own illustrated love-song
reels (© Mahmoud Elkosif). Use them for every image, scene or style he asks for with them.

| | Look | Higgsfield element (reuse in prompts as `<<<id>>>`) |
|---|---|---|
| **الست** | young woman, long brown hair in one side braid, big brown eyes, burgundy belted coat-dress, burgundy ankle boots | `5a4c7129-98c4-4a38-a8f6-ffbd8ec64fbc` (name «الست») |
| **الراجل** | young man, messy black hair, thin round glasses, long grey coat, burgundy scarf, dark trousers | `d6758c5d-f2af-4bc0-83fa-0bb20567512e` (name «الراجل») |

- Style: soft digital painting, warm cinematic storybook light, rain and street lamps, Arabic lyric text on top.
- References here: `ref_sit.jpg`, `ref_ragel.jpg`, `ref_couple.jpg` (frames from his reels).
- Model that keeps them consistent (tested 2026-11-24): GPT Image 2.6 with both elements in the prompt, 9:16,
  "in the exact art style of the references", "No text, no letters, no watermark". 0.75 credits per image.
- Paid generation still needs his «أيوه» each time (the price per image is above).

## Lyric / poem motion engine (`lyric_engine/`)
Five saved images of the two (street with roses, cafe tea, hand on heart, dance in the rain, balcony) are reused
for any song or poem without new credits: slow camera per image, beat breathing, golden bokeh, word-by-word
verses (Amiri with diacritics, key word in shimmering gold, beating heart), optional rain and setting-sun light.
Edit `SH` (images and times) and `LY` (verse start/end and word times from Whisper, text from the original's
captions), render with `../../agent/fast_reel/render.mjs`, mux the voice at -14 LUFS. «وضيئة الوجه» (22.4 s): 20 s render.
