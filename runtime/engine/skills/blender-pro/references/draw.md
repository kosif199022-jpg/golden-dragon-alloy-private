# draw - Grease Pencil drawing control (Blender 5.2, GPv3)

Module: `scripts/bpylib/draw.py`. Ops are `op(state, **params)`; the docstrings of `draw.OPS` list every parameter.
Standalone test harness (no CLI needed):
`blender -b --factory-startup -P tests/draw_video/harness.py -- examples/draw_poster.json`

## Canvas and coordinates
`gp_canvas` builds an ortho camera looking at the XZ plane. Point `[x, y]` maps to world `(x, 0, y)`, origin at centre,
width = `width` units (16 default), height follows the aspect ratio (1920x1080 -> x in [-8, 8], y in [-4.5, 4.5]).
`radius` = half line thickness in world units (0.05 is about 12 px at 1920 px / 16 units).
Colours: `"#RRGGBB[AA]"` (sRGB hex, converted to linear, Standard view transform so it renders as typed) or `[r,g,b,a]` linear.
`gp_canvas` deletes the default cube/light/camera (`clear=True`).

## Ops
| op | purpose / key params |
|---|---|
| gp_canvas | width, resolution, background, transparent, name, layer, fps, frame_start/end, clear, samples |
| gp_layer | name, opacity, blend_mode, hide, tint, onion, active |
| draw_stroke | points [[x,y(,pressure)]], radius, color, fill, cyclic, pressure, opacity, jitter, passes (doodle redraw), taper, smooth, material, vertex_colors, target, layer, frame |
| draw_shape | shape: line/rect/circle/ellipse/polygon/star/arc/bezier/spiral/polyline plus center,size,r,rx,ry,sides,r_inner,start_angle,end_angle,turns,rotation,corner,points and all draw_stroke params |
| draw_text_outline | text to outline strokes via a FONT curve. Arabic auto-shaped (arabic_reshaper+bidi if importable, else a built-in shaper). font,size,position,align,color,fill,radius, order="rtl" for right-to-left write-on |
| draw_svg | native SVG import; fit_width, position. Creates (and activates) a NEW object |
| draw_image_trace | method "opencv" (runs `python draw.py trace` in SYSTEM python because Blender has no cv2), "contours"/contours_file (precomputed), "potrace" (bpy.ops.grease_pencil.trace_image, needs UI context, falls back). mode contours/edges, threshold, width, position |
| animate_draw_on | Build modifier + keyframed percentage: start,end,mode SEQUENTIAL/CONCURRENT/ADDITIVE,transition GROW/SHRINK/FADE,reverse |
| gp_materials | name,color,fill,gradient(+gradient_type),mode LINE/DOTS/BOX,texture,holdout. Use `material=name` in draw ops |
| gp_effects | list of {type,...}: shader FX glow/shadow/blur/wave/rim/pixel/colorize/swirl/flip; modifiers noise/smooth/thickness/tint/color/opacity/offset/dash/envelope/array/subdiv/simplify/outline/length/mirror/multiply/time/build/texture. Any RNA property can be passed |
| line_art | Line Art modifier over a 3D scene/collection/object (toon ink). Needs a scene camera |
| draw_frames | frame-by-frame animation: frames=[{frame?,items:[draw_* params]}], hold, onion, loop |
| gp_onion | onion skin settings |
| doodle_style | Noise modifier "boiling line" (wobble, boil_step, thickness_var) |
| gp_transform | move/rotate/scale object with keyframes |
| gp_render | still PNG / PNG sequence / MP4 (H.264) for drawing-only recipes |

## Verified 5.2 API facts and gotchas
* `bpy.data.grease_pencils.new` gives an object of type `GREASEPENCIL`; `layer.frames.new(n).drawing.add_strokes([npoints])`; per stroke `.points[i].position/radius/opacity/vertex_color`, `stroke.cyclic/material_index/fill_opacity/fill_id`.
* **Fill needs a non-zero `stroke.fill_id`** (the default 0 renders no fill even with material show_fill). draw_* assign one automatically when `fill` or a filling material is used; strokes sharing an id cut holes (text glyphs).
* A layer has no frame until a drawing is created; frames hold until the next keyframe. Ops without `frame` draw at scene `frame_start` on the active layer.
* `state["gp_active"]` is the default target; `draw_svg` switches it to the imported object, so pass `target` explicitly afterwards.
* Modifier ids: `GREASE_PENCIL_BUILD`, `GREASE_PENCIL_NOISE`, `LINEART`...; shader FX `FX_GLOW`... (screen space, sizes in pixels).
* Actions are layered (`action.layers[].strips[].channelbags[].fcurves`), handled by `_fcurves`.
* Handwriting look: `jitter` (smooth wobble), `passes`=2-3 (re-drawn lines), `taper`, plus `doodle_style` boil.

## Limitations
* Arabic outlines come from the chosen TTF (Arial default on Windows); text is shaped to presentation forms, no mark positioning beyond the font defaults.
* Shader FX (glow/wave) are screen-space EEVEE effects; verify intensity per scene (glow did not visibly change the test PNG).
* opencv tracing needs `pip install opencv-python numpy` in the system Python (env `BLENDER_PRO_PYTHON` overrides the interpreter). The potrace operator depends on UI context.
* Line Art is cached per frame; render animations normally.
