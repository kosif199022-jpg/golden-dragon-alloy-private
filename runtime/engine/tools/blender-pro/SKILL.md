---
name: blender-pro
description: Headless Blender 5.2 control for 3D, drawing and video through JSON recipes or raw bpy scripts. Covers product shots, Arabic/English 3D logo reveals, title cards, turntables, abstract motion loops, materials (gold, chrome, glass...), studio lighting, camera moves, geometry nodes, physics, Grease Pencil drawing, video editing in the VSE, and renders to PNG/MP4 with ffmpeg checks. Use for بلندر، تصميم 3D، لوجو 3D، شعار ثلاثي الأبعاد، رندر، موشن ثلاثي الأبعاد، أنيميشن، تصوير منتج، Blender, 3D render, logo reveal, product shot, turntable, motion loop, bpy script.
---

# blender-pro

Drive Blender headless from the CLI. A **recipe** is JSON (a scene, then steps, then a render). Each step calls one **op** from `scripts/bpylib` (139 ops in 12 modules). For anything the ops don't cover, write a raw **bpy script** that can still call any op.

## Quick start
```bash
S=~/.claude/skills/blender-pro/scripts
python $S/bl.py info                                   # Blender version, engines, GPU, Arabic shaping, op list
python $S/bl.py ops [--module camera]                  # full catalog with signatures and docs
python $S/bl.py run recipe.json --out OUTDIR --preview # fast, small check render
python $S/bl.py run recipe.json --out OUTDIR           # final quality
python $S/bl.py exec my_script.py --out OUTDIR -- arg1 # raw bpy script (bpylib importable)
python $S/bl.py inspect file.blend                     # objects/materials/frames as JSON
python $S/bl.py thumb file.blend --out t.png           # quick preview render of a .blend
```
Every command ends with one JSON line: `{"ok":..., "outputs":[{path,type,...}], "error":{step,op,message,params,signature}}`. The exit code is non-zero on failure. Videos get an ffprobe summary (`probe`).

Examples you can copy and edit (`examples/`): `product_shot.json`, `arabic_gold_logo.json`, `turntable.json`, `abstract_loop.json`, `draw_*.json`, `video_*.json`.

## Recipe format
```json
{
  "scene": {"resolution": "1080p", "fps": 30, "duration": 5, "engine": "EEVEE", "samples": 64,
            "color": {"view_transform": "AgX", "look": "Punchy"},
            "world": {"type": "gradient", "top": "#1b1d22", "bottom": "#050506"},
            "motion_blur": true, "transparent": false},
  "steps": [
    {"op": "text3d", "text": "مرحبا", "name": "Logo", "split": true, "material": "gold", "extrude": 0.12},
    {"op": "text_reveal", "target": "Logo", "style": "rise", "frame_start": 10},
    {"op": "three_point", "target": "Logo"},
    {"op": "camera", "target": "Logo", "lens": 50},
    {"op": "frame_objects", "targets": ["Logo"], "margin": 1.3}
  ],
  "post": {"bloom": {"threshold": 0.8, "strength": 0.5}, "vignette": {"strength": 0.4}},
  "render": {"type": "animation", "out": "logo.mp4"},
  "save_blend": "logo.blend"
}
```
- `render` can be a list. `type` is `still` (uses `frame`) or `animation`. The format comes from the extension (`.png/.jpg/.exr`, `.mp4/.mov/.webm`, `name_####.png`).
- **Step options:** `"enabled": false` skips a step. `"preview_skip": true` skips it only in `--preview` (good for heavy volumes or physics).
- **Recipe-level options:** `"continue_on_error": true` keeps going past a failing step. `"keep_default_scene": true` keeps the cube, light and camera.
- If no step creates a camera, the runner auto-frames everything.
- **Conventions:** degrees everywhere, `#hex` colors are sRGB, Z is up, and the camera side is -Y. Objects are referenced by `name`.

## Op catalog
- 3D modules (`scene objects materials lights camera animate geonodes text3d render presets`): **references/ops-3d.md**
- Grease Pencil drawing (`draw`): **references/draw.md**
- Video editing / VSE (`video`): **references/video.md**
- One-op cinematic scenes: `product_shot`, `logo_reveal`, `title_card`, `turntable_scene`.

## Workflow (always)
1. Write the recipe and run `--preview`. Preview means 40% resolution, few samples, and about 24 frames for animations. Outputs are `*_preview.png` / `*_preview.mp4` plus `*_preview_contact.png`, a sheet of 6 frames.
2. **Look at the PNG or contact sheet with the Read tool.** Check that it isn't black or empty, the subject is framed with breathing room, highlights aren't blown, and Arabic letters are joined and in the right order.
3. Refine: change lights, camera, `margin` or materials, and re-run the preview. Errors give you the step index, the op, its signature and a traceback.
4. Final render without `--preview`, then verify: `ffprobe` data comes back in `outputs[].probe` (codec h264, size, duration, frames). Read one final still or the contact sheet.

## Machine notes (this PC)
- **CPU only** (Intel Core 5 120U, no CUDA/OptiX/HIP). Cycles 1080p at about 128 spp takes minutes per frame. For animations use **EEVEE** (`"engine": "EEVEE"`, 32-64 samples), keep Cycles for stills. On other machines `gpu_setup` picks OPTIX > CUDA > HIP > ONEAPI > METAL automatically.
- ffmpeg must be on PATH. It encodes MP4s and contact sheets; without it Blender's own writer is used.
- **Arabic:** Blender's python has no shaper, so text is shaped through system python (`pip install arabic-reshaper python-bidi`; `bl.py` passes its interpreter as `BLPRO_SYSPY`). Use a font with Arabic presentation forms: arialbd, tahomabd, segoeuib, majalla, trado, Amiri, Cairo... If none is given, an Arabic font is chosen automatically.

## Blender 5.x API pitfalls (verified on 5.2.3)
- **EEVEE engine id:** it is `BLENDER_EEVEE` in 5.x; `BLENDER_EEVEE_NEXT` (4.2-4.4) is rejected. Use `scene.engine_id("EEVEE")`.
- **Compositor:** `scene.node_tree` is gone. The compositor is `scene.compositing_node_group`, a `CompositorNodeTree` whose output is a `NodeGroupOutput` (there is no Composite node). Glare/Lens Distortion types are now **menu input sockets** (`node.inputs["Type"].default_value = "Bloom"`). `CompositorNodeMixRGB` and `CompositorNodeMath` were removed, so use `ShaderNodeMix` and `ShaderNodeMath`.
- **Sequencer:** use `sequence_editor.strips` (not `sequences`) and `strips.new_movie(...)`.
- **Animation:** actions are layered/slotted and `action.fcurves` is gone. Get F-curves through `bpy_extras.anim_utils.action_get_channelbag_for_slot(action, slot)` (`util.fcurves(id)` does this).
- **Video output:** set `image_settings.media_type = "VIDEO"` before `file_format = "FFMPEG"`.
- **Sky:** `sky_type` is `MULTIPLE_SCATTERING` / `SINGLE_SCATTERING` / `PREETHAM` / `HOSEK_WILKIE` ("Nishita" is now MULTIPLE_SCATTERING). Density props are `air_density`, `aerosol_density` and `ozone_density`.
- `World.use_nodes` / `Material.use_nodes` / `Scene.use_nodes` are deprecated (always node based). Setting them only gives warnings.
- Enum lists for `render.engine`, `view_transform` and `denoiser` are dynamic, and `enum_items` can look empty in background mode. Set the value inside try/except.
- In background mode, `--factory-startup` disables Python drivers. Simple driver expressions (`sin(frame/10)`) still work.
- Paths: pass Windows absolute paths to Blender. `/tmp/x` becomes `C:\tmp\x` inside Blender.

## Raw scripts
```python
# my_script.py  ->  python bl.py exec my_script.py --out OUT
import bpy
bpylib.run_op(STATE, "add_primitive", type="torus", name="Ring", material="chrome")
bpylib.run_op(STATE, "frame_objects")
bpylib.run_op(STATE, "render", type="still", out="ring.png")
```
Globals available to the script: `STATE`, `OUT_DIR`, `PREVIEW`, `bpylib`.
