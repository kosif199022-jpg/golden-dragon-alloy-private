---
name: maven-3d
description: Make "In this world…" story Shorts in the blocky-avatar 3D style (Roblox-look stories like the Braids Reacts / Skylox compilations), in English or Arabic. It covers the script formula, a fast narrator voice, word-timed one-word captions, real 3D renders (three.js, GPU) with depth of field, bloom, whip-pans and motion blur, real SFX ducked under the voice, and a -14 LUFS master. Use it whenever the user says maven 3d, asks for a Roblox-style story, an "in this world / in this town / what if" story short, a blocky 3D cartoon short, or an Arabic version (في هذا العالم…), even if they only paste a premise or a script.
---

# Maven 3D

A complete kit for 9:16 story Shorts in the "In this world…" 3D blocky-avatar style. **Read `references/style.md` first** (the frame-by-frame analysis and the checklist), then `references/scripts.md` when writing.

**What is in the skill**
- `engine/`: core.js (renderer, lighting presets, camera moves, captions, shot runner) and kits/: characters, sets, creatures, props, fx. It also holds three.js, the fonts (Poppins ExtraBold, Lalezar) and `gallery.js`, a 15-shot test of every kit.
- `scripts/`: new.py, voice.py, build.py, mix.py, render.mjs, sheet.py.
- `examples/`:
  - `dragons-en`: a 10 s English story.
  - `door-ar`: a 13 s Arabic story. Both are verified end to end.
- `templates/`: a blank story, scripts, configs and cues.
- `references/`: style.md, scripts.md (the formula, the 8 analysed stories, hook banks in English and Arabic), kits.md (the API), production.md (shots, sound, checks, troubleshooting).

## Commands (this PC)
```
PY = D:/reels/earshot/.venv/Scripts/python.exe -P      # has numpy, scipy, soundfile, PIL
S  = C:/Users/Orbit/.claude/skills/maven-3d/scripts
$PY $S/new.py D:/reels/<slug> [--lang ar] [--from dragons-en|door-ar]
$PY $S/voice.py D:/reels/<slug>                  # voice + web/timing.json (--timing-only to re-align)
$PY $S/build.py D:/reels/<slug> shots            # one still per shot -> check/shots.jpg
$PY $S/build.py D:/reels/<slug> stills 1.2,3.4   # chosen moments -> check/sheet.jpg
$PY $S/build.py D:/reels/<slug> all              # 240 fps frames -> mix -> master -> <slug>.mp4 + check/final.jpg
$PY $S/build.py D:/reels/<slug> resume 3.0 4.2   # re-render 3.0-4.2 s after a small fix, then final
```
Tools it relies on:
- Kokoro: `D:/reels/tools/kokoro`, for English.
- Edge TTS: `py -3.12 -m edge_tts`, for Arabic and English (free, needs internet).
- whisper-cli: `D:/reels/tools/whisper-cpp`.
- ffmpeg and node, with Playwright installed in the skill folder.
- The shared SFX library `D:/reels/assets-shared/sfx` (`LIB:` in cues).

Override any path with the env vars `MAVEN_*` (see the top of voice.py and mix.py).
On another PC, unzip into `~/.claude/skills/maven-3d`, then run `npm install` and `npx playwright install chromium` in that folder, plus `pip install edge-tts numpy scipy soundfile pillow`.

## Workflow
1. **Script.** Use the formula in `references/scripts.md`: rule, examples, stakes, hook, "then one morning", escalation, twist, payoff. Budget about 4.0 words/s in English and about 2.4 in Arabic (10 s ≈ 38 English or 23 Arabic words). Write an original premise; never copy the analysed stories' text. Show the script to the user before voicing if they didn't write it.
2. **Project.** Run `new.py`. Put the script in `script.txt` (lines starting with `#` are notes) and set the voice in `config.json`.
3. **Voice.** Run `voice.py`.
   - The **Maven pace** default is Kokoro `am_liam` at speed **1.18** with pauses squeezed to **0.18 s**. That is a touch slower than the refs, at the user's request.
   - For Arabic, use Edge `ar-SA-HamedNeural` (or `ar-IQ-BasselNeural` for Iraqi), rate `+6%`.
   - For ElevenLabs or a real recording, set `"engine": "file"` and drop the file at `vo/raw.wav`. **Ask before spending ElevenLabs credits.**
   - Check that the output says `whisper matched N/N`.
4. **Shots.** Edit `web/story.js`.
   - Build the world once (sets, cast, creatures, props, fx), then write a SHOTS list keyed to words with `C(wi('word'))`.
   - One shot per noun, about 1 s each, the camera always moving, and a punch-in on every reaction. The shot vocabulary is in `references/production.md` and the API in `references/kits.md`.
   - Run `build.py shots` and look at `check/shots.jpg` for blocked subjects, blow-outs, the caption over the eyes, or the camera inside props. Fix and repeat.
5. **Sound.** Edit `cues.json`, keying cues to words and cuts (`word:dragon+0.4`, `cut:5`).
   - Use real recordings only: the shared library, or Mixkit downloads (allowed without asking; report them after). Never synthesize effects.
   - No sample more than twice. No music unless the user asks (house rule for narrated reels).
   - mix.py prints voice-vs-effects. Keep the worst 100 ms window at 9 dB or more.
6. **Build.** Run `build.py all`. Look at `check/final.jpg`, then run earshot `timeline` on the mp4. Report the measured loudness, true peak and sync, and say that the mix still needs a human listen.
7. **Deliver** `<slug>.mp4` (1080x1920, 60 fps, -14 LUFS / -1.8 dBTP). Mention the size of `frames/` (about 500 MB per 10 s), which can be deleted.

## Rules
- **Every frame is a pure function of time.** Anything a shot hides or moves must be reset in `onReset`, because frames render out of order during resumes and stills.
- **Original look.** Blocky avatars are fine, but never use Roblox names, logos or UI, and never recreate a specific creator's characters (Ryan, Mr Tick and so on) or their exact scenes. The kits are generic on purpose.
- **Arabic.**
  - Captions are right-to-left in Lalezar, and a short word joins the next one.
  - `wi()` ignores diacritics and أ/إ/آ differences.
  - Signs use `textPanel()`, which detects the direction automatically.
  - Write numbers as words in the script.
- **GPU.** render.mjs warns if Chromium falls back to SwiftShader. A 10 s film is 2400 frames at about 40–60 ms each.
- **Long films** (60 s or more): split the story into chapters of about 20 shots in one story.js. The same pipeline works; frames run about 3 GB a minute at 240 fps, so use `"fps": 120` in config.json to halve that.

## Extending the kit
- New expression: `FACE_DRAW.name = g => {...}` (a 512 canvas).
- New outfit: `OUTFIT.name = (g, o) => {...}`.
- New hair: `HAIR.name = (g, m) => {...}`.
- New preset: `CAST.name = {...}`.
- New set: write a function like those in sets.js that returns a Group at (x, z), and give it its own `TOD` preset if it needs special light.

Run `index.html?story=gallery.js` (with `PAGE="index.html?story=gallery.js" node render.mjs <project> stills 0.5,1.5,…`) to see every kit after changes.
