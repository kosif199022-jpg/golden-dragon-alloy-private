# Red Rose knowledge distillation register — first independently implemented behaviors

Review scope (not the full repositories):
- [black-dragon-skill/references/APPS_CAPABILITIES.md](https://github.com/kosif199022-jpg/black-dragon-skill/blob/main/references/APPS_CAPABILITIES.md): describes `speech_sync` (word timestamps and SRT), motion-library/studio, and approval gates.
- [black-dragon-skill/references/ENGINE_POWERS.md](https://github.com/kosif199022-jpg/black-dragon-skill/blob/main/references/ENGINE_POWERS.md): identifies runtime/cloud distinctions, media QA, and consent requirements.
- [golden-dragon-alloy-private/SKILL.md](https://github.com/kosif199022-jpg/golden-dragon-alloy-private/blob/main/SKILL.md): describes persistent memory and source attribution; source contains private owner information and must not be copied into public artifacts.

Status of extraction:
- **Implemented and tested in Red Rose**: subtitle timeline SRT parsing, shot-relative caption mapping, deterministic timeline/render pipeline, SQLite memory, style recipes. Newly authored `speech.py` does not call old `speech_sync` or read old binaries at runtime.
- **Known from reference, but NOT implemented**: word-level forced alignment from raw audio, professional lip sync, automatic transcription, media editing by semantic events, full 3D rigs, original dragon's 18 engine capabilities.
- **Not inventoried or fused**: full `runtime/`, `owner-memory/`, catalog, entire 26k-unit DB, all historical branches, complete library.

No copyrighted third-party skill content, fonts, private learning journals, tokens, or passwords copied. The existence of a source is never treated as proof a capability works.
