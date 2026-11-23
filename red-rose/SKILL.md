---
name: red-rose
description: "Makes and checks Arabic-first video and bank-statement work for the owner on Windows: Arabic animated titles, reels and captions from exact words, shot reports with approved recuts, loudness fixes, iPhone exports, and bank reconciliation. Use whenever the owner asks in Arabic or English for الوردة، الوردة الحمراء، مونتاج، ريل، ريلز، قص فيديو، كابشن، عنوان متحرك، موشن، تحليل لقطات، ضبط الصوت، دعاء، ريل دعاء، ذكر/أذكار، تصميم ديني، دعاء يوم الجمعة، دعاء الصباح، تسوية بنك، مطابقة كشف حساب، Red Rose, reel, dua/duaa reel, azkar/islamic/Quran aesthetic video, captions, kinetic title, shot report, loudness, or bank reconciliation, and also when the request is Arabic typed on an English keyboard layout. For dua reels: the maker, 112 dua themes, two measured account styles, a voices-by-day library, Pinterest clip libraries and a song lyric-motion engine (references/DUA_REELS_PLAYBOOK.md); also for أصوات الدعاء، حلل حساب، موشن جرافيك لأغنية. Use it even when the owner does not name the skill."
compatibility: "Windows 11 with Python 3.12 and ffmpeg on PATH is the main target. Read-only commands run anywhere Python 3.12 runs. Private memory exists only on the owner PC."
metadata:
  version: "V29"
  audience: "the owner, through Claude"
---

# Red Rose (الوردة الحمراء)

Use this skill to make and check Arabic video and bank work for the owner. Start with the three commands in section 3, then follow one recipe. Nothing is written to disk until the owner says yes.

## 1. Where are you?

| Situation | What you can run | Private memory |
|---|---|---|
| Claude Code on the owner PC | every command | yes |
| Chat sandbox with the skill folder unzipped | read-only and media commands | no: private ops show `pc_only` |
| No command tool at all | nothing: follow section 11 | no |

## 2. Find the skill folder and run start

The folder that holds this SKILL.md is called `<skill folder>` below. Replace it with the real absolute path that `start` prints.

```
python -X utf8 "<skill folder>/rose.py" start
```

`start` is read-only: it opens no database, writes no file and makes no network call. It prints the skill path, the version, missing programs, the Arabic shaping self-test and how many ops work here. Use that absolute path in every later command.

If `start` fails or the path it prints is not the folder you expected, stop and report that exact line. Do not guess another path.

## 3. The four commands

- `start`: the status above. Run it first in every chat.
- `brief`: turns the owner's words into a route, the approvals needed, at most three must-ask questions, the commands to run and the done-when test. Read-only.
  ```
  python -X utf8 "<skill folder>/rose.py" brief "<the owner's words, exactly as typed>"
  ```
- `run`: one catalogue op as `ADAPTER.OP key=value ...`. Learn the parameters first with `describe`, never from the source.
  ```
  python -X utf8 "<skill folder>/rose.py" describe text.motion.kinetic_text
  python -X utf8 "<skill folder>/rose.py" run text.motion.kinetic_text text="الوردة الحمراء" --out <work>/step.json
  ```
- `check`: the delivery gate. Run it on your draft reply before you send it. Exit 0 passes, 1 fails.
  ```
  python -X utf8 "<skill folder>/rose.py" check --request "<the owner's request>" --draft <work>/reply.txt --evidence <work>/step.json --files <work>/title.png
  ```

Call form: `key=value` tokens for short values. For long or nested input write a JSON object to a file with the file tool and pass `--params-file FILE`. Never inline JSON in PowerShell. Save a result field with `--save FIELD=FILE`, repeated, never comma-separated. `--save`, `--out` and every `recipe run` that writes need `--approve-write`.

Shell rules in short: put the skill path in double quotes; use forward slashes in file arguments; keep Arabic values inside double quotes, as in `text="..."`; never inline JSON in PowerShell 5.1; never send Arabic output to a file with `>`, use `--out` instead. Details are in `references/WINDOWS.md`.

## 4. Choosing a route

Pick the first recipe that matches what the owner asked for. If none matches, run `brief` with his words, then `find` and `describe` to learn the ops.

| The owner asks for | Start with |
|---|---|
| An animated Arabic title for a reel, as a picture | `title-frame-ar` |
| The same title as a short video clip | `title-clip-mp4` |
| The best shots of a clip, and a 30-second reel cut | `shot-report-recut` |
| Captions from his own timed words | `captions-from-words` |
| Louder or quieter audio, or a target loudness | `loudness-fix` |
| A vertical video that plays on an iPhone | `iphone-export` |
| A cut that follows the music | `beat-synced-cut` |
| A bank statement matched against a ledger | `bank-reconcile` |
| A dua reel, a dua account analysed, dua voices by day, a song's lyric motion | read `references/DUA_REELS_PLAYBOOK.md` first |

A typical title job, in order:

1. Run `start` and quote its status line in the first reply.
2. Run `brief` with the owner's exact words. Send «فهمت إنك عايز» and «هعمل».
3. Run `recipe run title-frame-ar text="..." --work <work>`. It exits 3 first: show `would_write` to the owner.
4. After his yes, run the same command with `--approve-write`.
5. Open the PNG with the image reader, run `check` on the reply, and deliver the full path first.

## 5. Exit codes

| Exit | Outcome | What to do |
|---|---|---|
| 0 | ok | Read the result, verify the file, then deliver. |
| 1 | error | Fix the call from `allowed` and `hint`. No traceback is shown. |
| 2 | usage | Fix the arguments and run again. |
| 3 | approval_required | Nothing was written. Show `would_write` to the owner. Rerun with `--approve-write` only after an explicit yes. |
| 4 | unavailable_here | Say what is missing and what still works. Install nothing without a yes. |
| 5 | example_only | Built-in sample data, not the owner's data. Never deliver it. |
| 6 | needs_input | One answer is missing from the owner. Nothing ran. Ask the one question in `question_ar`, suggestion first, and run nothing else. |

`outcome` and `status` in every envelope are the same word. Exit 3 is not an error: it means the work is ready and waits for the owner's yes. Exit 6 is not an error either: it means one answer is missing. Exit 0 is not proof of quality: verify the file, and look at it, before you say it is done. Details and the input file shapes are in `references/USE.md`.

## 6. The eight recipes

A recipe is a fixed chain of ops with a gate after each step. Run one with `recipe run ID key=value ... --work DIR`. Add `--approve-write` only after the yes. Use the owner's own files, never the sample data.

- `title-frame-ar`: Arabic animated title as a PNG frame, 1080x1920, with its SVG. Request: «اعمل عنوان متحرك للريلز باسم الوردة الحمراء». `recipe run title-frame-ar text="الوردة الحمراء" --work <work>`
- `title-clip-mp4`: the same title as a short MP4 clip. Request: «اعمل كليب MP4 للعنوان المتحرك باسم الوردة الحمراء». `recipe run title-clip-mp4 text="..." --work <work>`
- `shot-report-recut`: a shot report, then a proposed cut, then the recut only after yes. Request: «شوف الفيديو ده وقولي انهي لقطات احسن وقصهالي ريل ٣٠ ثانية». `source=<video> max_duration=30`
- `captions-from-words`: captions from the owner's exact timed words, never from transcription. Request: «حط كابشن على الريل ده بكلامي بالظبط من غير ما تغير ولا كلمة». `words=<words.json> t=1.2`
- `loudness-fix`: normalises the audio to a target in LUFS and writes m4a. Request: «ظبطلي صوت الفيديو ده على مستوى مريح للسماع». `source=<video> target_lufs=-16`
- `bank-reconcile`: matches the bank statement against the ledger and lists the differences. Request: «عايز اطابق كشف حساب البنك مع الدفتر وطلعلي الفروقات». `ledger_csv=<ledger.csv> bank_csv=<bank.csv>`
- `iphone-export`: a vertical MP4 that plays on an iPhone, AAC audio. Request: «صدّرلي الفيديو ده يشتغل على الآيفون». `source=<video>`
- `beat-synced-cut`: cuts on the beats of the music. Request: «اقطع الفيديو ده على إيقاع الموسيقى». `source=<video> audio_rights_confirmed=true`. Set the rights flag only when the owner has confirmed the rights in chat.

If a required input is missing, the run exits 6 with outcome `needs_input`, `question_ar` and `missing[]` (each item with the Arabic question, the allowed values and a suggestion). Ask that one question. Run nothing else. Never invent the value. The input file shapes (bank CSV header, words JSON) are in `references/USE.md`; `sample-media --out <folder> --approve-write` creates sample files for trying the commands.

## 7. Owner rules (every job)

1. No file is written, rendered, cut, saved or installed without the owner's explicit yes in chat. Show `would_write` first.
2. Audio inside an MP4 is AAC. MP3 plays silent on iPhone.
3. No black first frame and no fade from black.
4. Captions are the owner's exact words, tashkeel included. Never transcribe, guess or invent them.
5. No overlay, bloom, haze or filter over footage unless the owner names it.
6. No invented text, names, dates, numbers or amounts. Ask for the missing item.
7. Bank work uses the owner's own files. Built-in example rows are never delivered.
8. Arabic is shaped before it is drawn. An `arabic_unshaped` warning means do not deliver that raster: deliver the SVG or render it again.
9. Never ask the owner to retype a request. Decode what he typed.
10. Never print or save a password, key, cookie, card or bank account number.
11. Images (generate or edit) are made with ChatGPT in the browser the owner opens for Claude. No other image generator unless he names it. No browser connected: say so and ask him to open it.

## 8. Reply contract

- First reply, before heavy work, in Egyptian Arabic: «فهمت إنك عايز: …» then «هعمل: …» then «⏱ التقدير ~N د». Ask only the must-ask questions, your suggestion first.
- Put the full path of the deliverable on the first line.
- Then «اللي اتعمل» as short bullets with measured numbers.
- Mark each important sentence as measured, inferred or unknown. Say what was not tried.
- Open every PNG and check it with the image reader. Check every MP4 with `rose.py verify <file>`.
- Run `check` on the reply file. Fix every failure until it exits 0.

## 9. Trial copy or installed copy

- A trial copy, for testing in a work folder, keeps the owner's memory untouched. Set a database inside the work folder and turn off bytecode:
  - Git Bash: `export RED_ROSE_DB="$PWD/rose.sqlite3" PYTHONDONTWRITEBYTECODE=1`
  - PowerShell: `$env:RED_ROSE_DB="$PWD\rose.sqlite3"; $env:PYTHONDONTWRITEBYTECODE=1`
- The installed copy on the owner PC: do not set `RED_ROSE_DB`. The owner's memory and playbook index are then used.

## 10. What pc_only means

An op that needs the owner's private memory, playbook index or local catalogue is labelled `pc_only`. Outside the owner PC it returns `unavailable_here` (exit 4). `start` lists how many ops work where you are.

## 11. Rules without tools

If no command can run, do not claim that anything was rendered, measured, checked or cut. Give the reply contract and the owner rules only. Say in one Arabic line that commands cannot run in this chat, and name the two ways to get a running copy: Claude Code with the README link, or saving the red-rose.skill file once.

## 12. Where to go next

- `references/USE.md`: each recipe in detail, its inputs, gates and limits.
- `references/OWNER_RULES.md`: the full rules and the approval list.
- `references/BOOTSTRAP.md`: how to get a copy and how to update an old one.
- `references/WINDOWS.md`: PowerShell 5.1 and Git Bash rules.
- `references/INTERFACE.md`: exit codes, call form and the envelope.
- `references/RECIPES.md` and `references/OPS.md`: the generated catalogue.
- `references/DEVELOPING.md`: only when you change the code.
- `references/DUA_REELS_PLAYBOOK.md`: **dua reels, voices, account analysis and song lyric motion: start here.**
- `references/SOCIAL_FETCH.md`: how to see Instagram, TikTok and Pinterest from the cloud (what worked).
- `references/STYLE_OAUN.md` and `references/STYLE_DXHMEN.md`: measured style cards of two dua accounts.
- `agent/dua_audio/dua_audio.py`: collect any dua account's voices sorted by day (list, label, catalogue);
  `rose.py library fetch dua_audio|dxh_pins|pins --approve-write` gets the ready libraries.

## V29 — evidence-based direction
Use the original native `intelligence.director` via `capability-run` for bounded alternative scoring, frame-exact storyboarding and RTL layout checks. Its outputs are proposals only. Source hashes and limitations: `SOURCE_INTELLIGENCE_AUDIT_V29.json` and `V29_INTELLIGENCE_GUIDE.md`. No foreign engine is invoked. New engine's 18 tests and full suite must pass on the current PR before merge.

## V30 — supervised original MP4 production
Use `storyboard.pipeline` `compile` to review a V29 story, then `render` with explicit `--approve-write` only for 2D illustrated clay or schematic map output. The render is silent H264/MP4 with a checked frame count and hash receipt. Unsupported visual fidelity (3D, true SaaS screenshot video, full Remotion) is refused unless a disclosed 2D clay fallback is explicitly allowed for supported names. See `V30_STORYBOARD_RENDER_GUIDE.md`; no legacy runtime imports.

## V43 — قياس الذكاء وفحص الريل
اقرأ `V43_FUSION_GUIDE.md` و`SOURCE_FUSION_AUDIT_V43.json`. محرك `intelligence.fusion` للقراءة فقط: يقيس 12 معيارًا، يتتبع 9 بوابات، يقارن heldout قبل/بعد، ويدقق مخطط ريل أبو كاب و`seek` الحتمي. لا يعتبر النتائج شهادة ذكاء، ولا يصدر صوتًا أو فيديو، ولا يعتمد وقت التشغيل على الأرشيفات. تحقق من نتائج الاختبارات ومراجعة الحقوق قبل أي نشر.

## V44 — reviewable timing and evidence-linked improvement

For a supplied frame-exact cartoon storyboard, run `python rose.py describe intelligence.fusion.reel_rhythm`, then `run intelligence.fusion.reel_rhythm --params-file INPUT.json` with an object holding `project` (the V43 storyboard). This reports caption density, end-card duration and character re-entry for human review, **not** verified video quality.

For a measured problem, `python rose.py describe intelligence.fusion.feedback_cycle` and `run intelligence.fusion.feedback_cycle --params-file INPUT.json` produce ranked proposals for tests. This operation **never stores memory, modifies production rules or retrains a model**. A lesson can enter the existing owner-local memory only after verified evidence and explicit owner authorization using the established `learning.record` write gate. See `V44_QUALITY_FEEDBACK_GUIDE.md`; no claim that the generated catalogue or full CI is current until it is regenerated and tested.

## V43 — continue with source-provenance discipline

Two original read-only native adapters: `reel.motion` (story / pose / svg for the Abu Cap two-lion-and-ladder 22s animation) and `mind.audit` (ladder / organ_audit / paired_compare for the app-super-mind nine-stage measured intelligence improvement process). Read `V43_ABU_CAP_SUPER_MIND_GUIDE.md` for actual commands, claims, and limitations. The imported archives/media are not runtime dependencies. Do not claim model re-training, automatic permanent learning, end-to-end 22s render or solved V42 abstention routing until independently tested.

## V45 — dua reels, voices and lyric motion (measured)

Everything learned from two dua accounts (@oaun.11: 1,384 posts, 114 reels measured; @dxhmen: 757 posts,
85 reels measured) is in `references/DUA_REELS_PLAYBOOK.md` with the numbers in
`agent/dua_style/presets.json`: layout, shot length, camera moves, transitions, loudness, captions,
hashtags, posting hours and audience. Tools: `agent/reel_analyzer/` (measure any account),
`agent/dua_audio/` (voices sorted by day), `agent/lyric_motion/` (scene-per-line song motion).
Libraries: `rose.py library fetch pins|dxh_pins|dua_audio --approve-write`. Other creators' footage and
voices are for private study; publish only the owner's voice and footage he may use.
