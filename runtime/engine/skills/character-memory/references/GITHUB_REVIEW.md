# The five reference repositories (checked 2026-11-13 through the GitHub API: metadata, LICENSE and README only)

Nothing was cloned, downloaded or run. The skill contains no code from any of them.

| Repository | Exists / state | Licence | What it is | Verdict | Idea taken (re-implemented here) |
|---|---|---|---|---|---|
| rtous/lester-code | yes · last push 2024-11-11 · 3★ | **none** (no LICENSE: all rights reserved) | research rotoscoping: text prompt → GroundingDINO → SAM → tracking → low-poly flat-colour frames (paper: Algorithms 2024) | **ideas only, no code** | segment → track → simplify to flat colour, then rebuild frames |
| hkchengrex/XMem | yes · 2024-11-15 · ~2k★ | MIT (weights/datasets not checked) | long-video object segmentation with sensory/working/long-term memory; PyTorch, CUDA, pretrained weights | reusable with attribution, but needs a GPU and weights; the author has moved on (Cutie/DEVA) | a memory that carries a part's identity across frames (here: predicted position + size per part, plus a learned calibration) |
| DragonBones/DragonBonesJS | yes · 2026-01-23 · 862★ | MIT (demo assets CC BY-NC-SA, not used) | runtime for 2D skeletal (cut-out) animation | data model worth borrowing | armature / bone / slot / display / animation → `export` writes `character_skeleton.json` in that spirit (own format) |
| opentoonz/opentoonz | yes · 2026-11-12 · 8.2k★ | BSD-3-Clause, with third-party parts under other licences | full 2D animation suite (C++/Qt) | a tool to hand frames to, not code to copy | cels/levels/x-sheet thinking: per-frame layers in z-order |
| jaisurya-dev-art/rigby2d | yes · 2026-11-12 · 231★ | Apache-2.0 / MIT (logos and demo assets excluded) | beta 2D rigging editor: AutoRig from layered PSD/SVG, IK, lip-sync, MCP server | promising but beta; borrow ideas | auto-rig a cut-out from layers; tool access for AI agents (here: `rd.py character …`) |

Production note: XMem/SAM-class models are research tools that need a GPU and model weights with their own licences.
For flat-colour cartoons the colour-and-geometry approach here measured 0.999 mask IoU with no model at all; a
photographic or textured character would need a segmentation model (XMem/Cutie/SAM 2) behind the same memory format.
