# KOSIF Cinema Craft — archive intake (2026-11-11)

User supplied `_skills.rar` and `dragon-genius.zip` following Black Dragon v10.17.2.

## Verified overlap

- `dragon-genius.zip`: 8/8 files match the installed `skills/dragon-genius/` SHA-256. No duplicate installation.
- `creative-studio/SKILL.md` identical to `references/skills/creative-studio.md` (already available).
- `example_beat_cut.json` identical to bundled Cinema template.
- `engine.js`, `sheets.py`, `skill_atlas.py`, `song_map.py` already have extended/modified implementations. Do not overwrite the newer copies with the original scripts.
- Legacy black-dragon SKILL and REBUILD_PLAN are older; archived only.

## Added safely

- Archive original 17 source files under `references/source_archives/skills-rar/`, with a hash manifest `SOURCE_CINEMA_ARCHIVE.json`. These are reference files, not launched by the skill.
- `tools/cinema_craft/cinema_craft.py`: reviewed code supporting `doctor`, `spec-audit`, `style`, and `cut`.
- `style` writes a new JSON spec: iris transitions, push-in scale, 9:16 caption safe zones, restrained glow.
- `cut` re-encodes instead of mixing GOP-copy fragments, does not overwrite originals, and independently verifies actual frame count. No remote downloads, generation, shell chaining or GPU. It is a CFR output by design, not a guarantee of preserving every source VFR timestamp.

## Intentionally not executed or automatically enabled

- `black-dragon-cinema/scripts/build.py`: original Windows-specific folders and media assumptions; the modern Cinema engine already exists in `app/engines/cinema/`.
- `black-dragon-cinema/scripts/fast_dl.py`: network downloader; owners and licences must be checked independently.
- `black-dragon-cinema/scripts/apply_style.py`: overwrites original specs in place, replaced by non-destructive `cinema-craft style`.
- `black-dragon-cinema/scripts/smart_cut.py`: GOP head + stream-copy tail can cause timestamp/audio seams, replaced by full re-encode and verification.
- Other original files kept for inspection but not executed.

## Scope and caveats

No external model, Higgsfield server, credit-generating API, or unknown file source executed in this intake. Local tests demonstrate only the covered commands. Creation of a ZIP does not publish it to GitHub or enable remote workflows.
