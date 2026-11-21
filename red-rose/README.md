# الوردة الحمراء 🌹 V14 — Independent, editable video prototype + offline knowledge

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


## V12 — character IK and cross-dissolve fixes
- actor.rig="ik2d": independent analytical two-bone IK for walking legs and moving arms.
- actor.blink_keys and actor.mouth_keys: normalized 0..1 expression control; expression smile/serious/surprised.
- Fixed duplicate SVG gradient IDs and overlapping outgoing titles during scene fade transitions.
- Demo: python rose.py produce demo_v12.json output --fps 24 --width 540 --height 960
- Locally verified on complete V12 bundle: 68/68 tests, five-second 120-frame MP4 FFprobe/FFmpeg QA.
- This is stylized 2D animation, NOT automatic lip sync, 3D rigging or complete 1,400-capability fusion.

## V13 — shared original character profile and approximate voice lip response

V13 adds two independent components, integrated through `rose.py produce`:

1. `identity.py` validates a named cartoon character profile with four hex colors (`skin`, `hair`, `coat`, `trousers`), uses a deterministic SHA256 fingerprint and applies it across all `director2d` shots with `actor.character_id`. A conflicting per-scene color or missing profile is rejected. This is **style consistency of a drawn figure**, not face recognition or preservation of a real person's appearance.
2. `lip_sync.py` extracts RMS audio energy at 20 Hz via local FFmpeg decode and converts it into scene-local mouth keyframes (up to 64 per shot). Silence closes the mouth. It is amplitude-driven, **not** phoneme/viseme recognition, transcript generation, or word alignment. `--lip-sync` is opt-in and requires `--audio`, `director2d`, and `rig=ik2d`.

Run:
```bash
python rose.py produce demo_v13.json out --fps 18 --width 432 --height 768 --audio voice.wav --lip-sync --profiles profiles_v13.json --srt demo_v13.srt
python rose.py verify out/video.mp4 --fps 18 --width 432 --height 768
python -W error::ResourceWarning -m unittest discover -v
```

**Evidence:** Local V13 tests: 82/82; two-scene 121-frame 432×768 MP4 with locally synthesized original spoken sample, AAC/H.264 passed independent FFprobe/FFmpeg verification. The demo eSpeak voice is not part of the built-in skill or this source repository. No personal SQLite database or legacy executable runtime is included. **Still unimplemented:** user-face fidelity, phoneme-level alignment, professional 3D, high-end editorial automation, full 1,400-requirement fusion.

## V14 — Text-guided mouth poses with silence gating

Adds five illustrated mouth poses: **closed, wide, round, open and teeth**. The
engine uses supplied word timestamps (JSON) or **estimated** word positions
inside SRT caption intervals, combined with the existing 20-Hz audio-energy
mouth track. This is **not** acoustic phoneme recognition or forced alignment.
The SRT approach is not guaranteed to match individual words' real timing.

```bash
python rose.py produce demo_v13.json output-v14 \
  --fps 18 --width 432 --height 768 \
  --audio voice.wav --lip-sync --viseme-sync \
  --profiles profiles_v13.json --srt demo_v13.srt
```

For externally timestamped words, use `--words-json words_v14_example.json`
instead of estimating from SRT. `--words-json` requires `--viseme-sync`;
`--viseme-sync` requires both `--lip-sync` and `--audio`. Word timing is
absolute seconds; character mouth poses are still grapheme-derived heuristics.

Tested in local V14 bundle: 93/93 tests. Video QA: 121 frames, 18 fps, 432x768,
H.264 video + AAC audio, 6.72 seconds, FFprobe and FFmpeg verified. No private
speech recording or private SQLite data uploaded to this repository.
