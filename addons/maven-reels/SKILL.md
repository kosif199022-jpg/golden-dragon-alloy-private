---
name: maven-reels
description: Maven Reels. Copies the style of any Instagram reel, TikTok or Short and makes new ones in that style, drawn entirely in code - brand ads, founder stories, app promos, explainers - Arabic first (right-to-left word-by-word captions) and English too. It measures the reference (cuts, pace, colours, loudness, voice speed), turns what it sees into a style card, writes the script in the same structure, then builds and renders a 9:16 MP4 with no paid image or video tools. Use it when the user sends a reel and says "make one like this", "copy this style", "make a reel/ad for my brand/shop/app", or asks for a Maven Reels video.
---

# Maven Reels

By **Maven**. Instagram [@maven.iqq](https://instagram.com/maven.iqq), YouTube **maveniqq**. See `rights/MAVEN-RIGHTS.txt`.

You copy a **style**, never the content: the way a reel is built (its structure, pace, look and motion) is free to learn from. Its brand, characters, logo, script and music are not: make new ones for the user.

| Path | What it is |
|---|---|
| `scripts/analyze.py` | reference reel -> contact sheets + numbers (`analysis.md`) |
| `references/style-card.md` | how to turn what you see into a style card. Read it after analyzing |
| `references/style-cards/` | finished cards, e.g. `founder-story.md` (the brand-story format) |
| `kit/reel.js` | the drawing kit: world + camera, sky, street, shops, rooms, people, captions, dock, phone, end card |
| `references/kit.md` | every kit function. Read before writing a reel |
| `scripts/new.py` | starts a reel folder from `templates/reel.html` |
| `scripts/render.mjs` | reel.html -> MP4, contact sheet or still, plus sound cues |
| `scripts/timestamps.py` | voiceover -> word times (`words.json` + `words.js`) |
| `examples/tannour-ar/` | a full Arabic founder-story ad for a made-up bakery app |
| `examples/stemmy-en/` | the same format in English for a made-up flower-shop app, with a Kokoro voice (`vo.mp3`) and `words.js` |
| `extras/` | other people's Instagram, marketing and Remotion skills, installed with `scripts/install_extras.py` (see `extras/README.md`) |

## Setup
Needs Node 18+, ffmpeg and Python 3.9+.
- `powershell -ExecutionPolicy Bypass -File setup.ps1` (Windows) or `bash setup.sh` (macOS, Linux).
- By hand: `npm install && npx playwright install chromium`, then `pip install -r requirements.txt`.

## Workflow
1. **Get the reference.** The user sends a file or a link. For a link, download it with `yt-dlp -o ref.mp4 <url>` if it is installed; otherwise ask the user to send the file. Put each reference in its own folder.
2. **Measure.** `python scripts/analyze.py ref.mp4 ref-analysis`. Read `analysis.md`, then **look at** `sheet.jpg`, `hook.jpg` and `shots.jpg`. The numbers tell you pace and loudness; the pictures tell you the look.
3. **Style card.** Fill in the card in `references/style-card.md` and show it to the user in a few lines: "this is what I'll copy". If a card in `references/style-cards/` already fits, start from it.
4. **Brief.** Ask once for anything missing: the brand or topic, what it sells or teaches, the one thing viewers should do at the end, language (Arabic by default; ask which dialect), and whether they will record a voiceover.
5. **Script.** Write it in the reference's structure (the card's beat list), one short line per beat, about the same number of words a second as the reference. Show it and wait for a yes. The user makes the voice (ElevenLabs or their own) and sends it.
6. **Timing.** `python scripts/timestamps.py vo.mp3 words.json --lang ar` writes `words.js` next to it; the reel loads it. Whisper misspells Arabic, so the reel takes the spelling from `SCRIPT` and only the times from the voice. With no voice yet, `R.timing` assumes 2.5 words a second, and the voice can be added later without changing anything else.
7. **Build.** `python scripts/new.py <folder>`, then write `reel.html` with the kit (read `references/kit.md` and the example). One picture event per line, landing on the stressed word. Copy the card's camera, caption and colour rules.
8. **Check.** `node scripts/render.mjs reel.html sheet.jpg --sheet`, then look at it. Check for text over faces, empty frames, things off screen, and that the hook shows something happening in the first second. For one moment: `--still 3.4`.
9. **Render.** `node scripts/render.mjs reel.html out.mp4 --voice vo.mp3` (add `--music bed.mp3 --music-db -18` if the user wants music). Sound is mastered to -14 LUFS. `out.cues.json` lists every pop, land, tick and notification with its time, ready for sound effects in any editor.
10. **Compare.** Run `analyze.py` on your own render and compare it with the reference: shot length, movement, colours, words a second. Fix big gaps, then deliver the MP4 and `reel.html`.

## Extras
When the user wants the extra skills (hooks and captions for Instagram, marketing, Remotion, Skill Creator), run `python scripts/install_extras.py` and tell them to start a new session. They are third-party, each under its own licence in `extras/`; credit them, never present them as Maven's.

## Rules
- Never reuse the reference's brand, logo, characters, slogan, script or music. Make up the brand only for demos and say it is made up.
- Facts and numbers on screen must be true for the user's business. Ask; don't invent prices, reviews or results.
- Arabic: set `lang: "ar"`. Never split a word into letters or add letter spacing. Keep words whole in captions.
- One idea per beat, one caption word at a time, and something moves in every second.
- Keep the `rights/` folder with every copy.
