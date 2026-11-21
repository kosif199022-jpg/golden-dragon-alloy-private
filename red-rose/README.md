# الوردة الحمراء 🌹 V11 — Independent, editable video prototype + offline knowledge

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
