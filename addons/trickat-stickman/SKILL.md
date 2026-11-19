---
name: trickat-stickman
description: "Arabic 2D animated YouTube videos for faceless channels in a flat ink-on-paper cartoon style. The user uploads an Arabic voiceover plus the SRT subtitle file of that same audio; the skill syncs the animation to the SRT and renders a finished 1080p MP4 with original characters, motion, music, SFX and all on-screen text in Arabic. It can also pitch ideas and write the Arabic script first. Always reply to the user in Arabic. Use it for 'فيديو انيميشن 2D', 'عندي فويس اوفر وملف SRT', 'اعمل فيديو كرتون من الصوت ده', faceless channel videos, animated explainers, money, psychology, history or story videos, even when the user only attaches an audio file and an .srt, or asks for a 'Trickat StickMan' video. Made by Trickat."
---

# Trickat StickMan

**Trickat StickMan, made by Trickat.** Keep this credit when sharing the skill.

The user gives you an **Arabic voiceover + the SRT file of that same voiceover**, and you deliver a finished, fully animated 16:9 MP4. The SRT is the timing source: every subtitle cue becomes a numbered unit, the picture is cut and cued to those units and to the words inside them, and the voice itself is never edited. The look: flat cel-shaded round-head puppets with one thick ink outline, moody night lighting or bright day sets, a camera that never stops moving, hand-lettered Arabic pop-in labels, rubber stamps, documents sliding across a desk, charts, counters, maps, split screens and a polaroid ending, with an original music bed and sound effects mixed under the voice. Everything is drawn with code (skia-python + HarfBuzz + ffmpeg): no paid tools and no stock footage.

You don't write drawing code. You write a **`story.json` storyboard** (shot kinds plus fields), and the engine in `engine/` times it to the SRT and renders it.

## Language rules (always)

- **Every chat reply to the user is in Arabic**, in the same dialect the user writes in (Egyptian by default). Questions, progress updates, the task list items, summaries, warnings, delivery notes: all Arabic. File names, commands and field names can stay as they are.
- **Every word on screen is Arabic**: labels, stamps, tags, lower thirds, chapter cards, chart titles and axis labels, counter captions, documents (newspaper, letter, receipt, phone messages), bubbles, map place names, shop signs, the polaroid caption and the video `title`. Use English on screen only for real brand names or when the user asks for it.
- Write numbers on screen as digits (`100 مليون`, `$140,000`, `1969`); the engine keeps them in the right order inside Arabic lines. Keep labels short: 1-4 words.
- Arabic is shaped and laid out right-to-left automatically (`engine/artext.py`). Don't add tashkeel to labels unless a word is ambiguous without it.

## Hard rules

- **Original characters only.** Copy the *style*, never another channel's characters, logos, thumbnails, series names or videos shot for shot. Real people are generic puppets with a name tag, never a likeness. No brand mascots.
- **Facts:** for anything presented as true (dates, numbers, names on charts and counters), check the key facts with a web search. Tell the user which facts were not checked. Never invent statistics for charts or counters; use the numbers that are in the voiceover.
- **Never edit the voice.** The picture follows the voiceover. Silent chapter cards shift it later in time; they never cut it.
- **The SRT text is the script.** Don't rewrite it. If a cue's text is clearly wrong (a transcription error), you may still use it for timing; just don't put the error on screen.
- **Look before the long render.** Render contact sheets of every shot, look at them, fix problems, then do one full render.
- You can't hear audio or watch playback. Verify through the SRT check numbers, frame checks and loudness readings, and tell the user to watch once for timing.
- Keep the user informed with a task list (in Arabic). Long renders take a while, so give progress updates.

## Which path

- **Voiceover + SRT attached** → the main path: go straight to **Build the video** and work through to the end without stopping.
- **Voiceover but no SRT** → ask for the SRT of that exact audio, and say how to get one in a line: CapCut (Auto captions → Export → SRT), ElevenLabs (export subtitles/SRT with the audio), Premiere Pro (Captions → Export SRT), or any subtitle tool. If they can't, ask for the exact script text and use the fallback (`align`, see 1 below); timing is looser, so say so.
- **SRT but no voiceover** → ask for the audio file.
- **Only a topic, or nothing yet** → optional **Ideas and script** stage at the end of this file, then wait for the voiceover + SRT.

## Build the video

### 0. Setup (once per session)
- Find the skill folder: `find / -name SKILL.md -path "*trickat-stickman*" 2>/dev/null` (locally, it's the folder this file is in). Call it `<skill>`; treat it as read-only.
- Run `bash <skill>/scripts/setup.sh`. It installs skia-python, numpy, scipy, soundfile and uharfbuzz (Arabic shaping). No speech model is needed: timing comes from the SRT.
- Make a project folder `<P>`, for example `~/trickat-videos/<slug>/` (or a folder in the user's working directory when running locally). Run every command from the skill folder: `cd <skill> && python3 -m engine <command> <P>`. All output goes into `<P>`.

### 1. Voiceover + SRT → timing
- Copy the audio to `<P>/voice.<ext>` (mp3, wav or m4a) and the subtitles to `<P>/subs.srt`. If the voice came in several parts with one SRT each, ask for a single file + single SRT (joining would shift the subtitle times).
- Run `python3 -m engine srt <P>`. It reads the SRT (any encoding, CRLF, `<i>` tags, multi-line cues), checks it against the speech in the audio, writes `<P>/timing.json` and `<P>/script.txt`, and prints the numbered units with their times. Read the report:
  - `offset` — if the subtitles were shifted against the audio, the engine detects it (±2 s) and corrects it. Force a value with `--offset 0.35`, or disable with `--offset 0`.
  - `speech inside subtitle time` — 85 % or more is normal. Below 60 % (with a warning) usually means the SRT belongs to a different take or edit: ask the user before going on.
  - Cues longer than 8 s are split into smaller units at punctuation (change with `--max-len 6`). `long units` / `very short units` are just notes.
  - "subtitles run past the audio" means a mismatch: ask for the right files.
- Word times inside each cue are spread over the voiced part of that cue by word length, so word cues land within a fraction of a second. Word-by-word SRTs (one or two words per cue, e.g. CapCut "word by word" or ElevenLabs word timestamps) give exact cues: the engine detects them and merges the words into phrase units (split at punctuation and pauses) while keeping each word's own time.
- Fallback without an SRT: put the exact script in `<P>/script.txt` (one paragraph per line) and run `python3 -m engine align <P>`. It places words by pauses in the audio (`method=fallback`); check the plan carefully.

### 2. Storyboard (`<P>/story.json`)
Read `references/story-format.md` fully, and look at `examples/arabic-marshmallow/` (a tested Arabic video: `subs.srt` + `story.json` using every shot kind). Then run `python3 -m engine sentences <P>` (it lists the units with times) and write `story.json`:
- `title` in Arabic (it names the output file), `mood` to match the topic.
- `cast`: 2-4 original characters with distinct silhouettes and colours.
- `shots`: cover every unit number once, in order (`"s": [4, 6]`), about one shot per 3-8 s (3 min ≈ 35 shots, 15 min ≈ 170). Follow the pacing rules at the end of the reference: rotate world shots and graphics, put every number on screen, a closeup after big claims, tags and lower thirds, chapter cards, and a polaroid ending.
- Cue mid-shot events with **words copied from that shot's units** (`"at": "الفلوس"`). Matching ignores tashkeel and spelling variants (أ/إ/آ/ا, ة/ه, ى/ي) and a leading و/ف/ب/ل/ال, so `"at": "فلوس"` also finds `والفلوس`.
- For 10-15 min videos, write the shots in chunks (one chapter at a time) and run `plan` after each chunk.

### 3. Plan check
Run `python3 -m engine plan <P>`. It prints the shot table (times, length, whips) and warnings: uncovered units, cue words not found, shots shorter than 6 frames. Fix every warning. Split shots longer than about 10 s, and merge fragments shorter than 1.5 s into a neighbour.

### 4. Look check (before the long render)
- Run `python3 -m engine stills <P>`. It writes contact sheets of every shot's mid-frame to `<P>/work/sheet_N.jpg` (24 per sheet). For a closer look: `--shots 3,8,12 --fracs .2,.6,.95`, and add `--full` to get full-size frames (`<P>/work/still_*.jpg`) when you need to read the Arabic clearly.
- Open and look at every sheet. Check the Arabic: letters joined, words in the right order, numbers not reversed, nothing clipped. Common fixes: labels covering a face (move `x`/`y`), text too long (shorten it to 1-4 words), characters off frame in wides (`x` between 250 and 1670), the same kind twice in a row (swap one), an empty-looking graphic (add `labels` or a second icon).
- Send the sheet(s) to the user with a one-line summary in Arabic, then start the render without waiting.

### 5. Render
- Run `python3 -m engine render <P>` **in the background** (`run_in_background`, or `nohup ... > <P>/work/render.log 2>&1 &`) and check progress every few minutes. It prints `[done/total] ... ETA`, uses all CPU cores but one, renders shots in parallel, and **resumes** after an interruption (finished shots are cached; re-run the same command). If you change one shot, only that shot re-renders.
- **Speed (measured, 8 cores):** 1080p takes about 3-4 minutes of rendering per minute of video, `--res 720` about 2. On 2 cores expect about 3-4x that. Check `nproc` and estimate first. If a 1080p render would take more than about 60-90 minutes, tell the user the estimate (in Arabic) and offer `--res 720` (same look, half the time, fine for YouTube), and let them choose. Pass the same `--res` to `render`, `audio`, `final` and `all`. A 720p file gets a `_720p` suffix.
- To fix a few shots after the full render: edit `story.json`, run `render <P> --shots 12,13`, which also re-joins the video.

### 6. Sound + final
- `python3 -m engine audio <P>` builds the original music bed from the `mood`, adds SFX from the shot events (pops on labels, thuds on stamps, whooshes on whips, paper on documents, ticks on counters, footsteps on walks, a boom under chapter cards, a shutter and sting on the polaroid), ducks the music under speech and masters to about -14 to -15 LUFS. The voice is untouched. Music should read about -18 to -21 dB against the voice during speech. Use `--music-db -20` for a quieter bed or `--mood calm` to change the style.
- `python3 -m engine final <P>` muxes `<P>/out/<title>.mp4`.
- Or run everything after the storyboard is written: `python3 -m engine all <P>` (it runs `srt` first if `timing.json` is missing and an `.srt` is in `<P>`).

### 7. Verify and deliver
- `ffprobe` the MP4: 1920x1080 (or 1280x720), 30 fps, with a duration matching the voiceover plus chapter cards plus about 1 s.
- Pull 6-8 frames at cue moments (`ffmpeg -ss <t> -i out.mp4 -frames:v 1 f.jpg`) and look at them: is the label up when its word is spoken, did the stamp land, is the mouth moving on dialogue.
- Deliver the MP4 (SendUserFile, or the file path) with a short Arabic note: the length, a few lines on the shots, any facts that weren't checked, and an offer of tweaks ("قولي رقم أي لقطة وأنا أعدلها"). Remind them to watch once for timing.

## Engine map (for edits beyond story.json)

- `engine/timing.py`: `parse_srt` + `from_srt` (SRT → units with word times, offset detection, long-cue splitting), Arabic-aware word normalisation (`norm`, `strip_al`), and the old script/ASR/pause aligner. `engine/timeline.py`: shot times, word cues and silent-card gaps.
- `engine/artext.py`: Arabic text layout. Splits a line into Arabic (RTL) and Latin/number (LTR) runs, shapes each with HarfBuzz, orders the runs right-to-left, and caches a skia TextBlob. All text goes through `label()` / `text_w()` / `wrap()` in `kit.py`, so new code that draws text must use those (never `canvas.drawString`).
- `engine/kit.py`: colours, easing, ink shapes, lighting, grade, bloom, the puppet `draw_char()`, and the three font roles, each an Arabic font paired with the original Latin font for English words and digits: `KALAM` = Marhey Bold (labels, tags, lower thirds, bubbles), `MARKER` = Lalezar (stamps, counters, badges), `FONT_HAND` = Aref Ruqaa Bold (chapter cards, chart titles, notes, polaroid). Fonts ship in `fonts/` (OFL/Apache). `ar_scale` trims the Arabic size against the Latin.
- `engine/sets.py`: office, home, street, skyline, board, table, void, black and map sets, each with night, dusk and day versions.
- `engine/props.py`: table documents (Arabic defaults; Arabic letters, messages and receipts are right-aligned) and icons. Add a new icon as `ic_name(c, t, o)` drawn about 300 px wide around (0,0), and register it in `ICONS`.
- `engine/fx.py`: pop labels, stamps, tags, lower thirds, typed cards (Arabic types in word by word from the right), bubbles and badges.
- `engine/shots.py`: shot kinds (`KINDS`). A new kind subclasses `Shot`, draws in `world()` (lit), `over()` (unlit overlay) and `screen()` (after the grade).
- `engine/render.py`: camera, whips, shake, polaroid, parallel segment render, contact sheets. `engine/audio.py`: music, SFX, mix and loudness.
- **Performance rule:** CPU skia is very slow at full-frame gradients, blend modes, colour filters, blur filters and rotated image draws. Anything static goes into the per-shot caches built in `Shot.prepare()`. Full-frame effects run in numpy (`finish`, `multiply_into`, `add_into`, `hblur` in `kit.py`). Per-frame drawing should be vector shapes, cached text blobs and axis-aligned image blits only.

Style bible (keep it when extending): one uniform near-black ink line (#18161B, 6 px at 1080p) on everything; flat fills with one hard shadow; poses snap with overshoot; every shot slowly pushes in; navy night with warm lamp pools, or a soft cream-paper day; lime and cream hand-lettering with a thick ink stroke; red marker rings and stamps; black chapter cards typed in white Ruqaa handwriting.

## Optional: ideas and script (only when the user has no voiceover yet)

1. **Ideas:** read `references/ideas-and-scripts.md` and reply (in Arabic) with **exactly 10 numbered ideas** for an Arabic faceless-channel audience: title, thumbnail text, hook line, payoff, why it performs, best length, fact status. Check facts for true-story ideas first. Ask for a number, "أفكار تانية", or their own topic.
2. **Length:** ask with **AskUserQuestion** (in Arabic): "الفيديو يكون طوله قد إيه؟" with four options: 3 / 5 / 10 / 15 دقايق, the idea's best length first marked "(مُقترح)".
3. **Script:** write it in Arabic following the reference (about 130 spoken Arabic words per minute). Save it as `<P>/script.txt` (chapter-card titles on their own lines starting with `# `), check the length with `python3 -m engine sentences <P>`, then reply with the spoken script in one copyable block (without the `#` lines), the word count and estimated length, the chapter titles, a 3-5 line visual plan, the facts checked, recording tips, and the ask: **"لما تسجل الفويس اوفر ابعتهولي هو وملف الـ SRT بتاعه، وأنا أعملك الفيديو كامل."**

---
*Trickat StickMan. Made by Trickat. Credits: `CREDITS.md`.*
