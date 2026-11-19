# Claude AI Motion Graphics

Code-driven motion graphics, explainer animations and sound design, rendered frame by frame in Python (skia / OpenCV / PIL) and encoded with ffmpeg. Created by **Tao Prompts** (AI-video education on YouTube).

## Styles (switch any time: "switch to the 2D Animated Explainer")
| Style | For |
|---|---|
| Editorial Explainer | 9:16 news / money / history shorts, Vox-style |
| AI Film FX | graphics living inside AI-generated scenes |
| 2D Animated Explainer | fully animated, voiceover-driven cartoon explainers |
| 3D Voxel Animation | block-world 3D zooms through scales ("Powers of Ten") |
| Cartoon Music Video | hand-painted cartoon music videos with characters and lyrics, synced to a song |

## Install
1. Claude app: turn on code execution (Settings -> Capabilities), then Customize -> Skills -> + -> Upload a skill, and pick the ZIP. Claude Code: copy this folder into `~/.claude/skills/`.
2. That's it. On first use Claude runs `scripts/setup_env.py`, which installs the Python packages and sets up the Poppins fonts (bundled under their SIL Open Font License in `assets/fonts/`). The only thing it can't install silently is ffmpeg - Claude will give you (or run) the one-line command for your OS.

## Try it
- "Write a 40-second explainer script about black holes, then make it a 2D Animated Explainer" (record or generate the VO, drop the audio in your folder, and ask Claude to build it).
- "Turn my clip into an Editorial Explainer short with subtitles" (with a video file).
- Run `python scripts/examples/flat25d_example.py out 120` to render a 4-second 2D Animated Explainer sample.

## Contents
- `SKILL.md` - the instructions Claude follows (workflow, modes, transitions, sound).
- `references/` - style rules, techniques, sandbox notes, 2D Animated Explainer notes.
- `scripts/` - `mg_kit.py`, `sfx_kit.py`, `flat25d_kit.py`, analysis helpers and worked examples.
- `music-video/` - the Cartoon Music Video style (guide, engine, example, fonts).
- `assets/fonts/` - Poppins (SIL Open Font License, see `OFL.txt`).
