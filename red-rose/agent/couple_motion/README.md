# «الراجل والست»: موشن جرافيك الأغاني بشخصيتين كرتون (Red Rose)

Read this when the owner sends a song reel (Instagram / TikTok) and says any of:
الراجل والست، الراجل والمرأة، الرجل والمرأة، اعمل الأغنية دي، موشن جرافيك للأغنية، بنفس الستايل، صور رومانسية، المطر، اللبس الحلو،
or sends one of the style images in `refs/`.
It works in any Claude conversation or account that can read this repo. No memory of earlier chats is needed:
everything that made the delivered songs is written here.

Delivered with this exact recipe (2026-11-25/26), all approved by the owner:
| song | reel | page |
|---|---|---|
| ردتلي / حبك بقى محفور (meena) | uploaded file | https://claude.ai/artifact/T4wzV7T9aneLCoMf7tZtH4 |
| نام الليل (Fadel Chaker) | lyrics pasted by the owner | https://claude.ai/artifact/L8nqzsYBjzfx83C6pnpse2 |
| حبيت فيك حنيتك (meena) | DfRpFDXMGG9 | https://claude.ai/artifact/UJHaXdfU4SHse8Uje63QvH |
| طمنيني (the man redrawn to look like the owner) | DeewDSZoLDD | https://claude.ai/artifact/GSK5jVTBqjoDNmDcaj6aMX |
| على حبك قلبي عايش | CTMe0oWAkeh | https://claude.ai/artifact/HMpDekNTXK8dg9ZJMKsx5m |
| وماله لو ليلة توهنا بعيد | DTdcvVcjLW6 | https://claude.ai/artifact/H3pRUFvCKQVmUwDaM2SBCa |
| انا حبيتك حب كبير (8 scenes, petals + fireflies) | DcG-pUQst0v | https://claude.ai/artifact/3fajc66sCbyWjYgVPPhEns |
| اول حب يعدي علينا (10 scenes following the reel's shots) | DFIllQUtZCk | https://claude.ai/artifact/W8tk1teT6faRaXYcnHE7Jv |

Look: `examples/ana_7abbetak_scenes.jpg`, `examples/awel_7ob_scenes.jpg`, `examples/awel_7ob_frames.jpg`.

## 1. الستايل (لا يتغير)

> **2026-11-26 correction from the owner: «الملامح متغيرة، عايزها شبه الراجل والست تماما».** The references
> are now the original character pictures (`characters/el-ragel-wel-sit/ref_couple.jpg`, `ref_ragel.jpg`,
> `ref_sit.jpg`, uploaded as 40b14133…, 033dc628…, f497d860…). In them she wears a **red belted wool coat-dress
> with red ankle boots and dark tights** (not velvet, not sneakers), and he wears a **grey coat, a burgundy
> scarf, round glasses and messy curly hair**. The art is a painted storybook look, not glossy 3D. `gen.py`
> sends these refs and this description. The velvet notes below are history.
> Lyrics in an exact remake: typeset them crisp with Amiri at the source's rows and times (the owner asked
> «اكتب الكتابة»), rather than lifting a 720p source.

- **Art:** soft 3D-cartoon digital painting (Disney/Pixar-like), big expressive eyes, polished, cinematic,
  richly detailed. **VERY saturated** colours: the owner asked for exactly this saturation («نفس درجة التشبّع»).
- **She:** long dark-brown hair in a thick **side braid**, big brown eyes, rosy cheeks, **deep crimson velvet
  coat-dress with gold buttons**, cream silk scarf.
- **He:** **curly** dark-brown hair, **thin round black glasses**, **burgundy wool scarf**, charcoal long coat
  over a cream knit sweater.
- The character sentence is the constant `CHARACTERS` in `gen.py`. Never edit it per song: it is what keeps
  the couple identical across songs.
- **Style references** (sent with every request as `image_urls`), copies in `refs/`:
  `style_flower_shop.jpg` (f1a055a9…), `style_rain.jpg` (51b8b30b…), `style_shop.jpg` (03fb31c5…), on
  `d2ol7oe51mr4n9.cloudfront.net/user_36qP6wVjfYmaRqhniKJVy5dJHoh/`. If those links ever stop working,
  upload the three `refs/` files again (Higgsfield `media_upload`, PUT, `media_confirm`) and put the new URLs in
  `"refs"` in scenes.json.
- **Model: Grok Imagine 2.0** (`POST https://api.higgsfield.ai/xai/grok-imagine-image-2.0`,
  `{prompt, image_urls, aspect_ratio:"9:16"}`). The owner chose Grok over Seedream and GPT-image after comparing
  them. The MCP `generate_image` hits a daily limit, so use the direct API.
- **Mood per song** (one sentence, the `mood` in scenes.json): the place and the light, plus the colour list
  «VERY vivid saturated rich colours: …». It must fit the song and the reel:
  - rain at night with neon-blue and gold puddles: «ماله لو ليلة»;
  - an old Damascus rose alley at night with lanterns and fireflies: «انا حبيتك»;
  - a golden-hour stone stairway with ivy and roses: «اول حب».
- **Scenes:** one per lyric line, or per shot of the reel. Follow the reel's own shots when it has them
  (in «اول حب»: eyes covered with a bouquet, the books on the stairs, the instant camera, the shadows, sitting alone with a rose).
  Then add **beautiful details** the owner loves: petals, fireflies, lanterns, stained glass, moon,
  string lights. Also add a dreamy beat such as his face in the clouds, or a glowing memory of him hugging her.
  The story arc is meeting, love, then a sad or longing line, then the closing embrace.

## 2. قواعد صاحب الشغل (اتقالت صراحة)

1. **The audio stays exactly as it is.** Mux it with `-c:a copy`: no loudnorm, no cut, no fade. The frames must
   cover the whole audio (make.sh does this). He complained twice: once a video had no sound (the ScrapeCreators
   `video_url` is video-only, so fetch the audio with yt-dlp `-f ba`), and once the loudness was changed.
2. **The on-screen words are the reel's own caption text, in the same dialect and spelling**, shown word by word
   in sync with the voice. Do not use Whisper's text (it garbles singing), and do not fetch full lyrics from the
   web. If there are no captions, ask the owner to paste the lyrics.
3. **No text inside the images.** Grok sometimes paints English words (it happened once: «don't be harsh with me»),
   so check the contact sheet and regenerate that scene with `--only N`.
4. **Delivery:** a download page (`tools/video-page/video_page.py build`, Artifact with `capabilities {downloads:true}`,
   icon `video`), plus an Instagram caption with these 5 hashtags, measured on Egyptian and Saudi TikTok search:
   `#اغاني_حب #اغاني_رومانسية #تصميم_فيديوهات🎶🎤🎬 #حالات_واتس #اغاني_عربيه`
5. **Paid:** every Grok image costs credits. The owner asked for Higgsfield himself for this series. In a new
   context, say the scene count before generating.
6. **Optional: the man looks like the owner.** `likeness.py` keeps the scene and redraws only his face, using the
   owner's two face references: slim long oval face, short black hair, thick eyebrows, light stubble, no glasses,
   head about 1/7 of his height. Do this only when he asks.
7. Reply to him in Egyptian Arabic, short, with the link.

## 3. الطريق (≈ 15 دقيقة)

```bash
K=red-rose/agent/couple_motion; J=~/work/song1; mkdir -p $J
# 1) the reel: video and audio (yt-dlp; from a cloud session Instagram is blocked, so run it in the Higgsfield
#    sandbox, PUT both to media_upload URLs, media_confirm, then curl them down from the cdn)
python3 -m yt_dlp -f bv -o "$J/v.%(ext)s" URL; python3 -m yt_dlp -f ba -o "$J/a.%(ext)s" URL
# 2) the lyrics and when each caption shows (read caps.jpg yourself), plus Whisper word onsets
python3 -I $K/captions.py $J/v.mp4 $J/cap            # --band x,y,w,h if the captions sit elsewhere
python3 -c "from faster_whisper import WhisperModel as M;s,_=M('small',device='cpu',compute_type='int8').transcribe('$J/a.m4a',language='ar',word_timestamps=True);[print(' '.join(f'{w.word.strip()}@{w.start:.2f}' for w in x.words)) for x in s]"
# 3) scenes: write $J/scenes.json (copy scenes.example.json: song, mood, scenes[]) then
python3 $K/gen.py $J/scenes.json $J && python3 $K/poll.py $J      # look at $J/scenes.jpg; redo a bad one: gen.py … --only N
# 4) timing: write $J/song.json (copy song.example.json)
#    shots: one per scene [a,b) end to end;  lines: [start, end, [[word, onset, 1 if gold]]]
#    the word = the caption's spelling, onset = the Whisper time of that word (or the caption's on-time)
#    gold = the 1-2 words that carry the line (حب، ذكراه، محفوظ، مخصوص …); finale = when the hearts start
# 5) render + mux with the original audio (needs fonts/Amiri-Bold.ttf in $J/fonts)
bash $K/make.sh $J $J/song.mp4 4
# 6) page + caption, then publish with the Artifact tool (see tools/video-page/README.md)
```

- **Timing rule:** a line appears at its first word's onset minus 0.05 s and leaves 0.45 s after its end; each
  word blurs in and rises over 0.38 s from its own onset. Shot cuts land on line starts, with a 0.7 s crossfade
  and a soft bloom flash.
- **Line windows:** `captions.py` prints the caption on and off times. Use them as line windows, and use
  Whisper's word times inside each window. When the reel shows one or two words at a time, join them into lines
  of 3 to 6 words.
- **Engine (`web/main.js`, all values come from song.json):**
  - Ken-Burns push and pull, alternating, on each shot.
  - Saturate 1.35.
  - The camera breathes on the beat (librosa beats).
  - Golden bokeh, blinking fireflies and tumbling rose petals.
  - A warm light leak and a vignette.
  - The lyric band sits at y ≈ 1560 in Amiri Bold, cream white, with key words in shimmering gold that pulse
    on the beat.
  - A small heart beats under each line.
  - Hearts float up in the finale, then a 0.6 s fade to black.
  - Credit «© Mahmoud Elkosif».
- Fonts are not in git (repo rule). Amiri-Bold.ttf, ArefRuqaa-Bold.ttf and IBMPlexSerif-Bold.ttf are from
  Google Fonts (OFL), or the owner's font library on the laptop.

## 4. الملفات

| file | what |
|---|---|
| `gen.py` | Grok submit: CHARACTERS + scene + mood, with the 3 style refs, writes sub.json (`--only N` to redo one) |
| `poll.py` | waits and saves img/n*.png, plus the contact sheet scenes.jpg |
| `captions.py` | caption on/off times, caption crops (caps.jpg) and a 1 fps sheet of the reel |
| `make.sh` | beats, frames (resumable, 4 Chromium workers, ≈ 40 s for 32 s), mux with `-c:a copy` |
| `web/` | the canvas engine (index.html, main.js) |
| `render.mjs` | Playwright frame renderer |
| `song.example.json`, `scenes.example.json` | «اول حب يعدي علينا», exactly as delivered |
| `examples/ana_7abbetak.scenes.json` | «انا حبيتك حب كبير» scenes and mood |
| `likeness.py` | (private) the man redrawn as the owner |
| `refs/` | the three style references |

Check (2026-11-26): `make.sh` on the «اول حب» job reproduced the delivered frames (mean pixel difference 0.0)
and an audio stream byte-identical to the source.

## 5. «نفس الريل بالظبط بس الراجل والست» (exact remake of one reel)

When the owner says «بنفس الموشن تماما، نفس القعدة ونفس اللوكيشن، بس الشخصيات راجل وست», do not use the
scene-per-line engine. Copy the reel itself. Done this way for «الدنيا بنعيشا مرّة» (Df8wcfrIMdi,
https://claude.ai/artifact/AjJ4YQVGqpAapemh5pSxv5):

1. **Measure the motion first** (ECC between frames 1 s apart). That reel was a single still photo with a
   linear pan of +4.85 px/s at 720 wide and no movement of the people (the difference after alignment was about 2/255).
   So no video model was needed: one image and the same pan.
2. **The image:** Grok with `image_urls = [a frame of the reel, refs…]` and "Recreate image 1 exactly: same
   composition, camera angle, poses and location … painted in the art style of images 2-4 with their
   characters", followed by the two character descriptions. Then ask for it again in **3:4** ("wider shot, full
   bodies, extra space left and right") so the pan has room without zooming in. Scale it to 1920 high and crop
   `x = x0 - v·t` with the same speed ×1.5.
3. **The text, pixel for pixel:** use `agent/mimic/lift.py` with one item per stacked word row.
   - Get the row on/off times from a white-pixel count per row band.
   - Set `steady` to the fully visible part, `show` to [on-0.1, off+0.1], `neutral_edges`, and 24 samples.
   - Result: all 23 words ✅, a 5 to 8 out of 255 difference from the source.
4. **Mux:** background, then the `lift/ov` overlay, then the original audio with `-c:a copy`.
   - When Instagram returns 429 to yt-dlp, use the ScrapeCreators `/v1/instagram/post` `video_url` instead,
     fetched in the Higgsfield sandbox: the progressive mp4 has the AAC audio inside.
   - Take the audio out with `-c:a copy`.

If the people in a reel really move, that needs image-to-video (Higgsfield motion control). It is paid, so ask
the owner first.
