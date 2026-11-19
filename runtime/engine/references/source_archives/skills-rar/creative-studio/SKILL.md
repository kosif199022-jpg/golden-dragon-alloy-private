---
name: creative-studio
description: التنين الأسود — استوديو Blender وPhotoshop وAfter Effects. Index of the most-starred GitHub agent skills and MCP servers for Blender (3D, motion graphics, product shots, rigging, geometry nodes, rendering), Photoshop (layers, retouch, background removal, batch resize) and After Effects (compositions, keyframes, expressions, render queue), plus code-only motion-design skill packs that replace After Effects. Use for «بلندر»، «فوتوشوب»، «افتر افكت»، 3D, logo reveal, product render, motion design, title sequence, or when a Blender/Adobe skill's method is needed. Runs Blender headless through the Black Dragon `blender` engine (no MCP needed).
---

# Creative Studio — Blender · Photoshop · After Effects (part of the Black Dragon)

Repos: `C:\Users\cinde\dragon-repos\creative\` (shallow clones, all MIT/CC0 unless noted; reference + methods, read scripts before running).
Engine: `python -m dragon run blender ...` from `C:\Users\cinde\OneDrive\Desktop\التنين الأسود`.

## What runs on this machine right now
| App | Status | How Claude drives it |
|---|---|---|
| Blender 5.2.3 LTS | installed | `engines/blender`: headless, no MCP. The Blender skills below write bpy code; save it to a .py and run it |
| Photoshop | **not installed** | Skills are kept as reference. Free equivalents that run now: GIMP (`gimp-console-3.2`), Krita (`kritarunner`), ImageMagick, `image-studio` |
| After Effects | **not installed** | Use the code-only motion packs (charlie947, howseen, iart-ai) through `web_film` / `engines/render/render.cjs`; they need no AE |

## Blender engine (verified: 3 tests pass, still + MP4 rendered with EEVEE)
```
python -m dragon run blender doctor
python -m dragon run blender run scene.py -- --my-arg 1        # any bpy script, headless; print("@@"+json) lines come back as results
python -m dragon run blender code "import bpy; print('@@{\"n\": %d}' % len(bpy.data.objects))"
python -m dragon run blender render film.blend out.mp4 --start 1 --end 120 --res 1080x1920 --engine CYCLES --samples 128
python -m dragon run blender render film.blend still.png --frame 60
python -m dragon run blender demo proof.mp4                    # self-contained proof scene (gold cube, 3-point light, push-in)
```
MP4 output follows the Black Dragon export standard (H.264 High, CRF 17, BT.709 tagged).
To use a skill written for an MCP's `execute_blender_code`, take the code it would send and pass it to `run`/`code` instead.

## Blender skills (best first)
| Repo | ★ | What to open |
|---|---|---|
| `EL4CTEO__blender-skills` | 791 | 28 pro Blender 5.2 workflows: core, lighting-lookdev, pbr-materials, geometry-nodes, hardsurface, rigging, animation, render/video, export, QA → `skills/<name>/SKILL.md` |
| `arjun988__blender-skills` | 2.2k | 94 specialist skills (styles, animation, look-dev, genres) → `.claude/skills/<name>/SKILL.md` |
| `RobLe3__cc-blender-skill` | 149 | 30 chain-loaded skills; `text-to-blender` orchestrator → modeling, materials, lighting, cameras, rendering, animation |
| `viettranx__3dviz-pro-max` | 1.1k | idea → Three.js/Blender scene worth showing (3D visualization) |
| `LobzyJay__motion-design-with-claude-and-codex` | 38 | `blender-motion`, `aftereffects-motion`, `motion-design`, `motion-design-critique` (taste for motion designers) |
| `sunxiayi__make-blender-education-video-skill` | 67 | cinematic explainer videos in Blender (use its craft, not the lecture tone) |
| `majidmanzarpour__blender-game-skills` | 174 | concept art → rigged game-ready assets |
| `agmmnn__awesome-blender` | 7.6k | curated list of add-ons, MCP tools, tutorials (CC0) |
| `~/dragon-repos/blender-mcp` (ahujasid) | 33k | the MCP add-on itself (install needs your approval; the engine above already covers headless use) |

## Photoshop (for when Photoshop is installed)
| Repo | ★ | Notes |
|---|---|---|
| `alisaitteke__photoshop-mcp` | 820 | 118 tools; skills `photoshop-recipes`, `photoshop-remove-background` |
| `loonghao__photoshop-python-api-mcp-server` | 349 | Windows COM via photoshop-python-api |
| `MastroMimmo__claude-photoshop-skill` | 9 | Claude Code skill on top of adb-mcp |

## After Effects (for when AE is installed) and code-only replacements
| Repo | ★ | Notes |
|---|---|---|
| `Dakkshin__after-effects-mcp` | 867 | compositions, text, shapes, layers, keyframes via ExtendScript bridge |
| `kumoproductions__mcp-aftereffects` | 169 | TypeScript MCP, AE 2024–2026, Node 24+ |
| `docsforadobe__Types-for-Adobe` | 649 | TypeScript types for AE/Photoshop/Illustrator scripting |
| `charlie947__motion-graphics-skills` | 610 | **no AE needed**: 15 skills — apple-launch-film, title-sequence-3d, animated-chart, milestone-reveal, motion-effects, reel-export … |
| `howseen-ai__claude-motion-design` | 796 | **no AE needed**: seek(t) HTML + Playwright + ffmpeg, motion blur, beat cuts (same contract as `engines/render/render.cjs`) |
| `iart-ai__motion-design-skills` | 208 | after-effects, animation-principles, beat-sync-editing, color-motion, logo-animation, shot-composition, remotion-video |

## Rules
- Montage folder rules apply: highest quality, best tool per job (Blender for 3D/design), cinematic not educational.
- Installing an MCP server or an Adobe app needs the user's explicit yes. Never bypass a denied install.
- Third-party skills are reference: read their scripts before running; respect each licence.
- Report what was really rendered (path, size, duration from `dragon verify`) separately from what was only consulted.
