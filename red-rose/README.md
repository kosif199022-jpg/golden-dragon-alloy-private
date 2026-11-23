# Red Rose (الوردة الحمراء)

## If you are an AI agent arriving from the link

Red Rose is a private skill for Arabic video and bank-statement work. The skill folder is `red-rose/` in this repository. Do this, in order:

1. **Check for an installed copy first.** If a skill named `red-rose` is loaded, or `~/.claude/skills/red-rose/SKILL.md` exists, use that folder and go to step 4. Do not clone.
2. **No installed copy: ask one question.** A pasted link is not approval for a network clone. Ask the owner, in Arabic, exactly this: «أنزّل نسخة الوردة من الرابط؟ (فولدر red-rose بس، للقراية والتشغيل)». Only a clear yes counts. «كمل» or «تمام» are not a yes for this.
3. **After a yes, sparse-clone the folder only.** A full clone fails on Windows long paths. These three lines are the same in PowerShell 5.1 and Git Bash. They were measured earlier, not re-run since: run them one at a time.

   ```
   gh repo clone kosif199022-jpg/golden-dragon-alloy-private rr-src -- -c core.longpaths=true --depth 1 --filter=blob:none --no-checkout
   git -C rr-src sparse-checkout set --no-cone "red-rose/"
   git -C rr-src checkout main
   ```

   The working copy is `rr-src/red-rose`. For a trial, set `RED_ROSE_DB` to a file inside your work folder and `PYTHONDONTWRITEBYTECODE=1` (see `references/BOOTSTRAP.md`).
4. **Run the first command.** Replace `<skill folder>` with the folder that holds `SKILL.md`:

   ```
   python -X utf8 "<skill folder>/rose.py" start
   ```

   It is read-only and prints the absolute skill path. Use that path in every later command.

Then read `SKILL.md` in the skill folder, and use only that file to work. Use the four commands it lists: `start`, `brief`, `run`, `check`.

## Notes for the owner

- On claude.ai a pasted private link loads nothing, and the sandbox cannot reach the repository. Save `red-rose.skill` once (Customize, then Skills, then upload) and the skill works in new chats. Whether that Save step appears on your account is not measured yet.
- The link shows GitHub `main`. Work that is not pushed is not reachable from the link. Until the owner approves a push and merge, the link gives the older skill.
- To install a copy into your Claude Code profile so new chats need no link, run `rose.py install-skill --approve-write` only after the owner's explicit yes. The old copy is moved to a dated backup beside it, and nothing is deleted.

Do not read the rest of this file to use the skill. Developer notes are in `references/DEVELOPING.md`.

---

# الوردة الحمراء 🌹 V17 — Independent, editable video prototype + offline knowledge

**Incoming agents:** Read [AGENTS.md](AGENTS.md), [NEXT_AGENT_HANDOFF.md](NEXT_AGENT_HANDOFF.md), [QUESTIONS_AND_ANSWERS.md](QUESTIONS_AND_ANSWERS.md) and [QUESTION_COVERAGE.json](QUESTION_COVERAGE.json) **before modifying code**. The 35 Q&A entries are attributed *paraphrases*, not the complete historical 1–1400 questions; never invent the missing original texts.

**Project status:** working local prototype, NOT full fusion of the Golden/Black Dragon engines. The owner's approval of 1,400 design requirements is not evidence of 1,400 implemented abilities.

## Demonstrated functionality

- One CLI entry point (`rose.py`): local SQLite memory and named style recipes; source-aware text ingestion; safe (summary-only) Alloy SQLite migration; relevance search; video rendering.
- **Director 2D**, a newly implemented SVG motion engine: art-directed backgrounds, 2.5D parallax, original illustrated character, camera/actor x/y/scale animation with normalized keyframes, crossfades, and text cues from user-provided SRT.
- **Editable output**: each production includes `project.json` with complete shot data, `video.mp4`, `qa.json`, and `manifest.json`.
- **QA**: FFprobe checks video geometry, codec, fps, exact decoded frame count, duration and audio presence; FFmpeg does an independent full-decode test and SHA256 is recorded.
- **Audio**: optional user-owned sound track; pads a short audio input to the intended timeline. No music generated or bundled; respect user rights.
- `produce` CLI result asks whether the user wants to save the style and under which name; save only on explicit instruction using `style-save`.

## Quickstart

```bash
python -m pip install cairosvg
# Also install FFmpeg and FFprobe on PATH
python -m unittest discover -v
python rose.py produce demo_v11.json output --fps 24 --width 480 --height 852
python rose.py verify output/video.mp4 --fps 24 --width 480 --height 852
python rose.py --db ~/.red-rose/memory.sqlite3 remember "A lesson"
python rose.py --db ~/.red-rose/memory.sqlite3 recall "lesson"
```

### Knowledge migration (on the owner's device only)

```bash
python rose.py --db ~/.red-rose/memory.sqlite3 fuse-alloy "/path/to/golden-dragon-alloy/kb/alloy.db"
python rose.py --db ~/.red-rose/memory.sqlite3 route "motion animation"
```

Migrates **descriptions/metadata only**, not original executable body blobs, credentials or private memories. It is a heuristic filter; manual privacy review remains essential. `source_distillation.md` records the reviewed sources. The destination SQLite database is local, excluded from this package and must **never** be committed. No previous skill is imported at runtime.

## Limitations

- Character art is an **original simplified 2D cartoon**, not AI image-to-video, motion capture, photorealism or a professional 3D rig.
- The timeline synchronizes manually supplied SRT timestamps; **no automatic speech-to-word alignment** is claimed.
- Does not include the original dragons' runtime engines or the personal 163 memory entries.
- Does not implement all 1,400 requirements or guarantee every third-party skill's licensing.
- Expected text support in SVG depends on installed fonts and CairoSVG; complex Arabic shaping should be tested in the target rendering environment before production use.

## Releases

V10.1: 43 legacy local tests. V11: tests for keyframes, art-directed illustration, editable projects, audio padding, FFprobe QA and resource-clean SQLite tests added. The source package and tests must be verified on each target host before calling them fully portable.

## V12 — IK rig and corrected cross-dissolve (2026-11-21)

- Optional `actor.rig="ik2d"` enables an original 2D character with analytic two-bone inverse kinematics for each arm and leg. No legacy skill executed or model API required.
- New numeric `actor.blink_keys` and `actor.mouth_keys` support timeline expressions; `expression` is `smile`, `serious`, or `surprised`. This is a **keyframed facial animation**, not automatic phoneme/lip synchronization.
- Corrected two-shot cross-dissolve to scope duplicate SVG paint-server IDs and prevent outgoing title superimposition.
- Existing `director2d` projects without `actor.rig` retain the previous drawing style.
- `demo_v12.json` produces an original five-second two-shot MP4 at 540×960, 24 FPS (120 frames), with an editable `project.json` and independent QA.
- Local regression tests: 68/68 passed. See `test_rig.py` and `test_crossfade_v12.py`.
- Still NOT a professional 3D character rig, model-driven video generation, source-engine fusion, or implementation of all 1,400 design requirements.

## V13 — shared original character profile and approximate voice lip response

V13 adds two independent components, integrated through the existing `rose.py produce` command:

1. `identity.py` validates a named cartoon profile with **four hex colors**, uses a deterministic SHA256 fingerprint and applies it consistently across all `director2d` shots with `actor.character_id`. A conflicting per-scene color or missing character profile is rejected. Scene timelines (position, expression, camera) stay independently editable. This is **style consistency for a drawn figure**, *not* recognition/preservation of any real person's facial features.
2. `lip_sync.py` extracts RMS energy at 20 Hz from an audio file decoded locally by FFmpeg and converts it into scene-local mouth keyframes (`mouth_keys`, at most 64 per shot). Silence closes the mouth. The algorithm is amplitude-triggered, not phoneme/viseme recognition, transcript generation, or automatic word alignment. `--lip-sync` is opt-in and requires `--audio` and `director2d` + `rig=ik2d`. Existing manual mouth keyframes are never overwritten without notice; the process raises an error instead.

```bash
python rose.py produce demo_v13.json out \
  --fps 18 --width 432 --height 768 \
  --audio /path/to/speech.wav --lip-sync \
  --profiles profiles_v13.json --srt demo_v13.srt
python rose.py verify out/video.mp4 --fps 18 --width 432 --height 768
python -W error::ResourceWarning -m unittest discover -v
```

**Evidence:** local V13 tests: 82/82, generated a two-scene 121-frame 432×768 MP4 with a locally synthesized spoken demo, verified AAC/H.264 and full decode via FFprobe/FFmpeg. The demo speech was produced separately with eSpeak and is not part of the skill's built-in engine. The source-code ZIP never includes the owner's private knowledge SQLite database, secrets, original dragons' executable runtimes, or proprietary fonts.

**Remaining:** real-person visual identity fidelity, high-end character animation, speech phoneme alignment, advanced editorial automation, and the entire 1,400 requirement backlog.

## V14 — Text-guided viseme mouth poses (new)

`visemes.py` adds **five original, hand-drawn pose families** (`closed`, `wide`,
`round`, `open`, `teeth`) to the existing IK character rig, with `neutral` for
pauses. A valid speech-energy track closes the lips during silence. This uses
written letters only as an **approximation** of visible speech mouth shapes:
there is **no automatic phoneme detection, speech recognition or forced
alignment**. It is not suitable for claims of ±100ms word accuracy unless you
supply externally timed words and validate against the audio.

Run with existing SRT captions (word position estimated inside subtitle cues):

```bash
python rose.py produce demo_v13.json output-v14 \
  --fps 18 --width 432 --height 768 \
  --audio voice.wav --lip-sync --viseme-sync \
  --profiles profiles_v13.json --srt demo_v13.srt
```

For more accurate timing, use `--words-json words_v14_example.json`, a list of
`{"start": 0.1, "end": 0.35, "text": "hello"}` entries in **absolute seconds**.
Use `--words-json` with `--viseme-sync --lip-sync --audio`; the word positions
are taken from the supplied file, but the mouth shapes remain heuristics.

The output `project.json` stores scene-local `viseme_keys` and `mouth_keys`,
so the animation remains editable. `manifest.json` reports the timing method.
Rejects overlapping/out-of-range word events and existing manually authored
viseme tracks. This is all in the new Red Rose engine, not a call to a legacy
skill.

## V15 — executable Red Rose core (2026-11-21)

V15 closes part of the gap between *reference search* and *actually executing* a verified
native capability. It includes **11 explicitly registered local adapters** in
`capability_runtime.py`, plus `pipeline_v15.py` to reuse the **same** video pipeline
through the traditional `produce` CLI and the controlled capability interface.

No original Golden/Black Dragon programs are imported or run. The user's migrated
knowledge index is independent, private, and **not packaged or uploaded**.

### Inspect, plan and execute

```bash
python rose.py capabilities
python rose.py capability-plan 'اعمل مونتاج فيديو لشخصية'
python rose.py capability-run video.preview '{"storyboard":"examples/demo_v15.json","fps":12,"width":320,"height":568}'
# The preceding preview is read-only, except for a local hashed invocation audit.
python rose.py capability-run video.produce '{"storyboard":"examples/demo_v15.json","output":"v15-output","fps":12,"width":320,"height":568}' --approve-write
python rose.py capability-run video.verify '{"video":"v15-output/video.mp4","fps":12,"width":320,"height":568}'
python rose.py capability-audit
```

To save a lesson **after a real execution**:

```bash
python rose.py capability-run learning.record '{"lesson":"Verify H264 with FFprobe","source_audit_id":2,"category":"improvement"}' --approve-write
python rose.py capability-run memory.recall '{"query":"FFprobe"}'
```

Replace `source_audit_id` with an **actual** `audit_id` returned by a successful call.
The lesson is saved in a local private SQLite database; its content and any user
media must never be committed to GitHub. No model-weight training takes place.

### Verification scope

- `python -W error::ResourceWarning -m unittest discover -q`: **130/130 tests** passed locally, including 37 new tests over the V14 baseline of 93.
- Executed a new V15 test movie end-to-end: **24 decoded H.264 frames**, **320×568**, **12 FPS**, **2 seconds**; independent FFprobe + full FFmpeg decode passed.
- Tested the default denial when `--approve-write` was missing; after opt-in, generated editable `project.json`, `manifest.json`, and `video.mp4`.
- Successfully saved and recalled one **synthetic** evidence-linked lesson from the video verification step. This is reproducible demo data, not the user's private experience.
- Out-of-budget exports, unknown action names, unrecognized overwrite directories, malformed parameters and unapproved writes are rejected.

### What this DOES NOT prove

Eleven tested adapters are **not** 11,000 skills, 25,675 executable units or 1,400
completed requirements. The original Alloy description entries remain references;
turning an entry into a native adapter takes separate implementation and tests.
The 1,400 detailed requirement statements have not been fully enumerated or
mapped, so no completion percentage is justified. The current video character
is an original stylized 2D rig, not photoreal footage or professional 3D.

## V16 — Actual local footage cuts and real-media recut (2026-11-21)

Two **new** native adapters bring the Red Rose's explicit capability registry to **13**:

- `video.scene_analyze` (read): FFprobe metadata + FFmpeg sampled 80×45 RGB frames; detects large frame-wide differences. Outputs approximate cut times, strengths, shot boundaries and an editable segment list. This is **NOT** semantic scene understanding and may miss subtle cuts or mistake flashes for cuts.
- `video.recut` (approved write): takes an explicit EDL (ordered `[{"start":0,"end":1}, ...]`), uses FFmpeg's trim/setpts/atrim/asetpts/concat to reassemble segments from a **local source video**, maintains an audio stream if present, encodes H.264/AAC and independently verifies full decode via FFprobe + FFmpeg. Does not overwrite an existing output. Up to 16 segments / 300 seconds of output.

**Analyze, edit the plan, then explicitly approve the output**:

```bash
python rose.py scene-analyze /path/to/footage.mp4
# Copy and reorder the `suggested_edl` list from the JSON output into edits.json
python rose.py recut /path/to/footage.mp4 edits.json /path/to/edited.mp4 --fps 24
# Result: approval_required; no video written
python rose.py recut /path/to/footage.mp4 edits.json /path/to/edited.mp4 --fps 24 --approve-write
python rose.py verify /path/to/edited.mp4 --fps 24
```

Alternatively use `capability-run video.scene_analyze` and `capability-run video.recut`. Unlike `video.produce`, these operations work directly with supplied **original media**, not synthetic SVG character frames. Source videos are analyzed locally and **not uploaded to GitHub**.

**Verified demo:** a synthetic three-shot source with audio yielded cut marks at **1.50s** and **3.00s**. The reordered shot 3→shot 1 compilation was **3.0s, 72 frames, 432×768, H.264/AAC**, verified by FFprobe and full FFmpeg decode. The proof is synthetic footage (not a real-world film), and the algorithm performs hard cuts only; no optical-flow interpolation, cinematic transitions, automatic storyboarding, or professional editor replacement is claimed.

**Tests:** V15 baseline 131/131 plus V16 feature/integration tests, total **146/146** locally on Linux with FFmpeg 7.1; resource warnings treated as failures. A blank/source-only Git checkout must re-run tests in CI before being declared portable. Knowledge summaries (25,675 on owner's PRIVATE local machine in an earlier migration) are NOT 25,675 executable tools. The 1,400-item requirements roadmap is NOT complete.

## V17 — original-video sound-aware edit suggestions (2026-11-21)

Two new **read-only** native adapters bring registry total to **15**:

- `video.timeline_analyze`: FFmpeg's silencedetect + downsampled RGB cut detection. Reports acoustic-silence intervals, visual-shot boundaries and quiet/audible fraction per shot. **Audio activity is not a speech detector.**
- `video.edit_suggest`: ranks full visual shots by sound activity and duration, returning a bounded editable EDL. It only proposes edits, never writes, chooses story meaning or renders autonomously.

```bash
python rose.py timeline-analyze /path/to/footage.mp4
python rose.py edit-suggest /path/to/footage.mp4 --max-clips 3 --max-duration 30 --min-audible-ratio .2
# Review result.suggested_edl and save that array to edits.json
python rose.py recut /path/to/footage.mp4 edits.json new-edit.mp4 --fps 24 --approve-write
python -W error::ResourceWarning -m unittest discover -v
```

The existing `video.recut` remains approval-gated and creates new outputs only, with FFprobe/full-decode verification. Unit+integration evidence: local 154/154 tests and a three-color original video with audio only in the middle shot; cuts at 1 s and 2 s, quiet endpoints, proposed EDL 1–2 s, exported one-second H.264/AAC output after explicit approval.

**Limitations:** no semantic scene understanding, speaker classification, true transcript, dialogue comprehension or AI montage. Local original footage and user SQLite data are never committed to GitHub. Reference descriptions are not executable skills; the full 1,400 requirements remain incomplete.


## V18 — verifiable Q&A-to-capability trace (read only)

\`QUESTIONS_AND_ANSWERS.md\` contains **35 paraphrased decisions** (A01–A35), not the original 1,400 individual questions. Their source classifications and current native capability relationships are in \`QA_TRACEABILITY.json\`; \`QUESTION_COVERAGE.json\` still marks the missing historical originals unresolved.

New **read-only** native adapter \`qa.trace\` and database-free CLI commands:

\`\`\`bash
python rose.py question-audit
python rose.py question-trace A17
python rose.py capability-run qa.trace '{"question_id":"A27"}'
python -W error::ResourceWarning -m unittest discover -v
\`\`\`

The first two commands do not open or create the user's private SQLite database. The normal \`capability-run\` path writes a locally hashed audit receipt, as do other native capabilities.

The trace enforces that every linked capability belongs to the *current* \`capability_runtime.REGISTRY\`; it rejects unknown legacy/nonexecutable names, false verbatim-original flags, missing/extra Q&A IDs, or historical question numbers masquerading as recovered source text. A link means **partially related implementation**, not full requirement satisfaction. The original 1,400 questions have **not** been restored or implemented.

The 16th adapter \`qa.trace\` provides project-level provenance and validation, not a new image/AI/video engine. Existing V17 video algorithms and limitations are unchanged.

## V19 — measured per-shot technical quality (read only)

New native read-only adapter `video.shot_score` (17 registered adapters). It measures exposure, black/white clipping, coarse detail and motion for every detected shot on a 64x36 grayscale proxy, joins the V17 audible fraction, ranks the shots and returns a reviewable `suggested_edl`. It never writes; exporting still needs an approved `video.recut`.

```bash
python rose.py shot-score footage.mp4 --max-clips 3
python rose.py capability-run video.shot_score '{"source":"footage.mp4","max_duration":20}'
# review the EDL, save it as edits.json, then only with approval:
python rose.py recut footage.mp4 edits.json new.mp4 --approve-write
```

Evidence and limits are in `CAPABILITY_LEDGER_V19.md`: 185 local tests passed; measurements are technical proxies, not focus, composition, story or aesthetic judgement, and the thresholds have not been tuned on real footage.
## V20 — five user-supplied media archives distilled to one independent runtime

Five source ZIP files were inspected and SHA256-registered in SOURCE_FUSION_AUDIT_V20.json. Original independently written fusion_studio_v20.py adds 5 registered native adapters: fusion.route, fusion.plan, fusion.frame (read-only), fusion.render and media.iphone_export (write approval required). See FUSION_V20_GUIDE.md for CLI usage and limitations. This is partial independent reimplementation, NOT wholesale functional equivalence or legacy engine invocation. V19 PR #16/#17 remain separate open developments.

## V20–V22 roadmap — owner-approved 1,400 questions, executed in batches

The owner approved all 1,400 suggested answers on 2026-11-21. They are stored unchanged in `questions/owner_1400/` and tracked per topic by `roadmap_1400.py`; a topic counts only with a real module, symbol and passing test.

New read adapters (stdlib only, no file or network I/O), each called as `python rose.py capability-run <id> '{"op":"…","params":{…}}'`:

| adapter | module | chapter |
|---|---|---|
| `physics.simulate` | physics_v20 | 08 motion physics |
| `math.geometry` | geometry_v20 | 05 maths and dimensions |
| `science.compute` | science_v20 | 19 maths and science |
| `thinking.reason` | thinking_v21 | 04 thinking and creativity |
| `decision.make` | decision_v21 | 09 decisions |
| `code.analyze` | code_analysis_v21 | 11 code analysis |
| `accounting.check` | accounting_v21 | 24 accounting checks (no professional opinion) |
| `governance.audit` | governance_v22 | 01 fusion governance |
| `architecture.check` | architecture_v22 | 02 architecture |
| `agents.coordinate` | agents_v22 | 03 agents and handoff |
| `learning.evolve` | learning_v22 | 26 evidence-based learning |
| `compose.pipeline` | compose_v22 | 27 combining capabilities |
| `roadmap.status` | roadmap_1400 | progress on the 1,400 |

Progress at commit `b4d784b`: 129 of 280 topics, 632 of 1,400 questions answered in tested code; 574 tests OK. Not complete. Run `python rose.py roadmap` for the live figure.

## V26 — 1,400 roadmap: final measured state

`python rose.py roadmap` reports **1,398 of 1,400** owner-approved questions answered in tested code (278 topics unit-tested, 2 end-to-end verified with sha256 receipts). The last two need the owner: real device screenshots (28.05) and a human edit review (28.08). New adapters since V23: `library.evaluate`, `app.build`, `vfx.compose`, `security.guard`, and the file/media adapters `knowledge.store`, `database.manage`, `video.analyze`, `video.edit`, `audio.process`, `automation.run`, `release.verify` (per-op read/write; every write needs `--approve-write`). 51 adapters in total.



## V29 — source-guided intelligence (limited independent distillation)

Read `SOURCE_INTELLIGENCE_AUDIT_V29.json`, `V29_INTELLIGENCE_GUIDE.md`, `intelligence_director_v29.py` and its two regression test files. The owner attached ten sources (one includes eight nested skills), including video/motion reference skills, an iPhone utility, a Figma binary and *Thinking, Fast and Slow*. They were reviewed, **not copied whole** or loaded as runtime engines.

`intelligence.director` is a new **read-only** native adapter with three explicit ops: `decision_review`, `storyboard_plan`, `layout_audit`. It adds evidence calibration, bias review, frame-exact storyboard allocation and overflow detection. It is deterministic and cannot understand content like a trained video model. It does not overwrite or render user files. It also cannot guarantee the user's professional/creative outcome. See the guide for commands and limitations.

The V27/V28 set of 8 `CODED_UNTESTED` adapters **remains unverified**. Do not call this full fusion of the source code or a wholesale increase in model IQ.

## V30 — approved V29-to-V20 original video bridge

New native mixed adapter `storyboard.pipeline`: read-only `compile` and approved `render`. Produces actual H264/MP4 from a frame-exact V29 beat plan using the independent V20 illustrated clay/schematic-map renderer, with full FFprobe+decode verification, no-overwrite stage and hash receipt. No silent downgrade from 3D/Remotion/Figma: unsupported visual styles are rejected, or a specific limited fallback must be opted into. See [V30_STORYBOARD_RENDER_GUIDE.md](V30_STORYBOARD_RENDER_GUIDE.md). Other eight coded V27/V28 adapters remain untested.

## V43 — independent app-intelligence and cartoon-reel source fusion

`intelligence.fusion` is a new **read-only** native adapter derived from the uploaded `app-super-mind.skill` (12 readiness dimensions, 9 evidence gates, paired dev/heldout results) and the Abu Kab cartoon RAR (22s/30fps/660-frame scene timeline, deterministic seekable beat contract, character/prop and licensed music checks). Five bounded operations: `readiness`, `ladder`, `paired_eval`, `reel_preflight`, `reel_seek`. See [V43_FUSION_GUIDE.md](V43_FUSION_GUIDE.md), [SOURCE_FUSION_AUDIT_V43.json](SOURCE_FUSION_AUDIT_V43.json) and `examples/abu_kab_reel_v43.json`.

No original archives or media/music/font assets are imported or committed. V43 adds measurable **assessment tools**, not full neural training or an actual replication of the full reel. Do not claim all archived skills are rendered or fully fused. Verify all new tests and existing routing quality gates before merge.
