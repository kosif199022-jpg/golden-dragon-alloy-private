# V56 — `reel.craft`: craft checks for short reels and a gated credit pass

**Where it came from.** On 2026-11-20 the owner merged Maven Toon into the Golden Dragon and had every dragon branch
merged into `main` (black-dragon-skill, the private alloy and kosif-tool). The useful, safe parts of what that work
learned were re-built here as one native module, `reel_craft_v56.py`. Nothing from Maven Toon or the dragons is
imported, called or copied. Each op returns `limits`.

| op | effect | what it does | proof |
|---|---|---|---|
| `script_check` | read | Micro-fable script check: flat hook of 7 words or fewer (no question, no greeting or "in this video"), escalation joined by بس / وبعدين / وفجأة, a turn line in the second half («تعرف ليه؟»), payoff of 9 words or fewer, one picture per line, length for the seconds at the register's speaking rate, and one dialect only (eg / iq / fusha markers) | `ScriptCheck` |
| `story_plan` | read | Light as act structure (day setup, darker middle, golden explanation, sunset/dawn ending), a new scene only when the light changes, a camera beat every ~0.86 s with about 2:1 push-ins, and a key-object close-up in the first second. Exact frames. | `StoryPlan` |
| `tempo_steadiness` | read | Says whether a beat exists. A grid needs 75% or more of the onsets and less than 1% chance over every grid tried (binomial tail × grids, Bonferroni). Otherwise `bpm: null`. | `TempoSteadiness`: 0/200 false positives, 60/60 real tempi, error ≤ 0.68 BPM |
| `delivery_gate` | read | The owner's export standard on a real file: 1080×1920, 30 fps, H.264, yuv420p, an audio stream, faststart (top-level MP4 boxes read in order). Optional: duration and bt709. | `MediaOps` |
| `credit_overlay` | **write** | «© Mahmoud Elkosif» for the whole film plus an end card («مونتاج وإخراج …» / «تابعني على فيسبوك») in the last N seconds, drawn by libass (Arabic shaped). Audio is stream-copied and checked byte-identical by MD5, the frame count is kept, and the file is staged in the output folder and verified before it appears. It never overwrites, and it refuses to run without `--approve-write`. | `MediaOps` + a frame inspected by eye |

Also changed: `media_library_v35._safe_extract` now refuses, before writing a byte, drive paths (`C:`), `..`
written with a Windows backslash, symlink members, and archives that unpack to more than 8 GB (`SafeUnzip`).

```bash
python rose.py describe reel.craft.script_check
python rose.py capability-run reel.craft '{"op":"script_check","params":{"text":"…","seconds":20}}'
python rose.py capability-run reel.craft '{"op":"tempo_steadiness","params":{"onsets":[0.1,0.6,1.1,1.6,2.1,2.6]}}'
python rose.py capability-run reel.craft '{"op":"delivery_gate","params":{"source":"final.mp4"}}'
# after the owner reviews the output path:
python rose.py capability-run reel.craft '{"op":"credit_overlay","params":{"source":"final.mp4","output":"final_credit.mp4","font":"Lalezar"}}' --approve-write
```

**Not claimed.**
- `script_check` and `story_plan` check structure and plan frames. They do not judge story quality, and they render nothing.
- The credit needs a font that has Arabic glyphs. Without one, libass falls back to another font, so look at an end-card frame.
- Tests use synthetic clips. No owner footage was used.
