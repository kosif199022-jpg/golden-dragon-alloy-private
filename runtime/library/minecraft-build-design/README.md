# minecraft-build-design

[![CI](https://github.com/yimeng-YM/minecraft-build-design/actions/workflows/ci.yml/badge.svg)](https://github.com/yimeng-YM/minecraft-build-design/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/yimeng-YM/minecraft-build-design)](https://github.com/yimeng-YM/minecraft-build-design/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE.txt)
[![Agent Skill](https://img.shields.io/badge/Agent%20Skill-SKILL.md-8A2BE2)](https://agentskills.io)

[中文说明](README.zh-CN.md)

An [Agent Skill](https://agentskills.io) that lets your AI coding agent design **Minecraft Java Edition builds that
paste straight into your own world**. It bundles **mcbuild**, a tested Python toolkit, and gives the agent the whole
workflow: read your real terrain, find the spot, match your style, design in code, check the result automatically,
and hand you files you can use right away.

Ask things like *"build a fishing hut next to my house"*, *"设计一个中式亭子，放在我截图的位置"* or *"a medieval
gatehouse about 20 wide, I'll place it myself"*.

## What you get

- a **Litematica `.litematic`** (and optionally a WorldEdit/Axiom `.schem`) aligned to your real terrain, or a
  portable one you can place anywhere;
- an **offline 3D preview page** (orbit, cut-aways per floor, day/night, materials, before/after against your
  screenshot);
- a **survival materials list** (CSV) and a **placement guide** in your language (Chinese or English);
- automatic **verification**: every block state valid, connections and supports right, every walkable surface lit,
  every room reachable (walk test with the game's collision boxes), nothing of yours overwritten;
- optional: a **real-client paste test** (Minecraft opens, Litematica pastes the file, every cell is compared) and a
  narrated **making-of video**.

Terrain can come from a singleplayer save, a server you visited with **Voxy** or **Bobby**, an area you saved with
**Litematica**, or nothing at all.

## Requirements

- An agent that supports [Agent Skills](https://agentskills.io/clients) and can run shell commands - Claude Code,
  Codex, Cursor, Gemini CLI, GitHub Copilot, OpenCode, Goose, Trae, Qwen Code, Kiro, …
- **Python 3.10+** with `numpy` and `Pillow` (`scripts/requirements.txt`).
- Optional, only for the features that need them - the agent tells you and asks before installing anything:
  `zstandard` + Java 17+ (Voxy caches), Playwright (preview screenshots), JDK 21 + Litematica (in-game test),
  ffmpeg + edge-tts + scipy (video). See `scripts/requirements-optional.txt`.
- Windows, macOS or Linux; works offline. Minecraft itself is optional (without it, previews draw block shapes in map
  colours and block names fall back to readable ids).

## Install

The repository root **is** the skill folder, so any of these works. Keep the folder name `minecraft-build-design`.

**1 · git clone** (recommended - update later with `git pull`)

```bash
git clone https://github.com/yimeng-YM/minecraft-build-design ~/.claude/skills/minecraft-build-design
```

Replace `~/.claude/skills/` with your agent's skills folder:

| Agent | Personal (all projects) | Project only |
|---|---|---|
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| Codex, Cline, Warp, Zed, … | `~/.agents/skills/` | `.agents/skills/` |
| Cursor | `~/.cursor/skills/` | `.agents/skills/` |
| Gemini CLI | `~/.gemini/skills/` | `.agents/skills/` |
| GitHub Copilot | `~/.copilot/skills/` | `.agents/skills/` |
| OpenCode | `~/.config/opencode/skills/` | `.agents/skills/` |
| Trae / Qwen Code / Kiro CLI / Windsurf | `~/.trae/skills/` / `~/.qwen/skills/` / `~/.kiro/skills/` / `~/.codeium/windsurf/skills/` | `.trae/` `.qwen/` `.kiro/` `.windsurf/` + `skills/` |

(Paths from [vercel-labs/skills](https://github.com/vercel-labs/skills/blob/main/docs/agents.md); check your
agent's docs if it is missing.)

**2 · skills CLI**

```bash
npx skills add yimeng-YM/minecraft-build-design          # current project; add -g for all projects
```

**3 · release zip** - download `minecraft-build-design-vX.Y.Z.zip` from
[Releases](https://github.com/yimeng-YM/minecraft-build-design/releases), check it against `SHA256SUMS.txt`, and unzip
it into the skills folder (the zip contains the `minecraft-build-design/` folder). In the Claude apps you can upload
the zip as a skill; the code then runs in a sandbox without your game, so send it your save or schematic files when
asked.

Then install the Python packages and check the setup:

```bash
python -m pip install -r ~/.claude/skills/minecraft-build-design/scripts/requirements.txt
python ~/.claude/skills/minecraft-build-design/scripts/mcb.py doctor
python ~/.claude/skills/minecraft-build-design/scripts/mcb.py selftest
```

## Using it well (and saving tokens)

The first time, the agent asks one short round of questions and saves the answers in a local profile
(`~/.mcbuild/config.json`), so later jobs start right away. You can speed things up:

- **Where to build**: stand on the spot, look at it, press **F3+C** and paste the copied line
  (`/execute in … run tp @s x y z yaw pitch`) - exact position and view, no guessing. Or send a screenshot taken
  with **F3 open**.
- **Your game folder**: in game *Options → Resource Packs → Open Pack Folder*, then go one folder up. Singleplayer
  world: *Singleplayer → select world → Edit → Open World Folder*.
- **On a server**: with Voxy or Bobby installed, the agent reads the real terrain you have seen; otherwise save the
  area with Litematica (area selection → save schematic) and give the selection origin.
- **Older game version** (e.g. 1.20.1 / 1.21.1 modpacks): say so - the schematic is written for your version and
  blocks your version lacks are flagged.

## Game versions

Block data for **Java 1.21.11** is bundled. Schematics load in newer versions (Litematica converts them). For 1.20.1
– 1.21.10 the agent sets a target version: the right DataVersion, old ids for renamed blocks (`chain`, `grass`) and a
check that every block exists in your version.

## Privacy and safety

Everything runs locally. Your saves, caches, mods and servers are only read, never changed; new files go into the
project folder (and, if you agree, a new file in your `schematics` folder). Nothing is downloaded or installed and no
game window is opened without your OK. The optional video narration sends its script text to Microsoft's TTS service
- it never contains personal data.

## Repository layout

```
SKILL.md                     instructions the agent loads (Agent Skills format)
references/                  detailed guides the agent reads on demand
scripts/mcb.py               command line of the toolkit
scripts/mcbuild/             the toolkit (Python), data per game version, preview viewer, in-game harness
LICENSE.txt, THIRD_PARTY_NOTICES.md, CHANGELOG.md, CONTRIBUTING.md
.github/                     CI (validation + selftest on Windows/macOS/Linux) and release scripts
```

Development and release process: [CONTRIBUTING.md](CONTRIBUTING.md). Changes: [CHANGELOG.md](CHANGELOG.md).

## License

MIT © yimeng-YM - see [LICENSE.txt](LICENSE.txt); third-party notices in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

NOT AN OFFICIAL MINECRAFT PRODUCT. NOT APPROVED BY OR ASSOCIATED WITH MOJANG OR MICROSOFT. No game assets are
included; textures and names are read from your own installation.
