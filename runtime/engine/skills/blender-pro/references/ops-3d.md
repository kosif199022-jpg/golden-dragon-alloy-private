# 3D ops reference (scene, objects, materials, lights, camera, animate, geonodes, text3d, render, presets)

Every op is `func(state, **params)` and is called from a recipe step as `{"op": "name", ...params}`.
Run `python scripts/bl.py ops --module camera` to get the exact signature and full docstring of any op (this file is the summary).
Qualified names (`"objects.transform"`, `"video.fade"`) always work. If two modules share a name, the plain name goes to the module that sorts first alphabetically: `fade` and `transform` resolve to animate/objects, so use `video.fade` and `video.transform` for the VSE versions.

## Conventions
- **Units and axes:** meters, Z up. The default camera side is **-Y**, so text and image planes face -Y.
- **Angles are always degrees** (rotation, spot_size, start_angle, noise strength on rotation...).
- **Colors:** `"#RRGGBB"` / `"#RRGGBBAA"` is sRGB and gets converted. `[r,g,b(,a)]` is taken as linear. Simple names also work (`"gold"`, `"cyan"`...).
- **Object references:** `target`, `source`, `subject` and similar params take the object's name: the `name` you gave it or the name an op returned. The registry lives in `state["objects"]`.
- **Paths:** inputs resolve against the recipe folder and then `assets/`. Outputs resolve against `--out DIR`.
- **Easing:** `linear`, `constant`, `smooth` (bezier), `ease_in`, `ease_out`, `<sine|quad|cubic|quart|quint|expo|circ|back|bounce|elastic>_<in|out|in_out>`. Examples: `expo_out`, `back_out`, `sine_in_out`.
- **Frames:** when `frame_start`/`frame_end` are omitted they default to the scene range.

## scene
| op | key params |
|---|---|
| scene_setup | resolution [w,h] or "1080p","4k","square","vertical"(1080x1920),"portrait"; fps (23.976 ok); frame_start/frame_end or duration(s); engine CYCLES/EEVEE/WORKBENCH; samples; color{view_transform,look,exposure,gamma}; world{...}; units |
| clear_scene | keep [names]. The runner calls this automatically unless `"keep_default_scene": true` |
| color_management | view_transform AgX/Filmic/Standard/"Khronos PBR Neutral"; look "Punchy","Medium High Contrast","High Contrast"... (short name ok); exposure; gamma |
| units | system METRIC/IMPERIAL/NONE, scale, length |
| world | type color/gradient/hdri/sky (inferred if omitted) + params below; fog:{...} |
| world_color | color, strength |
| world_gradient | top, bottom, strength, light_color, light_strength (camera sees the gradient, objects get light_color) |
| world_hdri | path (.hdr/.exr), strength, rotation, background(false = hide from camera, keep lighting), background_color, background_strength |
| world_sky | sun_elevation, sun_rotation, altitude, air, aerosol, ozone, strength, sky_type MULTIPLE_SCATTERING (Nishita) / SINGLE_SCATTERING / PREETHAM / HOSEK_WILKIE, add_sun_light |
| fog | density, color, anisotropy, mode "world" or "box" (volume cube around the scene, needed for god rays), size, emission |
| set_frame / set_var | frame / arbitrary values into state["vars"] |

## objects
| op | key params |
|---|---|
| add_primitive | type cube/plane/grid/sphere/uv_sphere/ico_sphere/cylinder/cone/torus/circle/monkey; name,size,radius,depth,segments,rings,subdivisions,major_radius,minor_radius; location,rotation,scale; material; smooth; bevel (width or dict); subdivide (levels); collection; parent |
| rounded_box | size [x,y,z], radius, segments (+ add_primitive params) |
| empty | name, location, rotation, display, size |
| backdrop | seamless curved studio sweep: width, depth, height, curve_radius, location, rotation_z, color, roughness, material |
| floor | size, color, roughness, material, shadow_catcher (Cycles + transparent film) |
| import_model | path .obj/.fbx/.glb/.gltf/.stl/.ply/.usd*/.abc/.svg/.blend; name; normalize (fit to size and drop to z=0); location/rotation/scale; material; smooth; join; svg: extrude, svg_scale. Returns the root (a parent empty when several objects come in) |
| image_plane | path (image or video), height, emission, emission_strength, alpha; faces -Y by default |
| modifier | target, type (alias or Blender id: BEVEL SUBSURF ARRAY SOLIDIFY BOOLEAN DISPLACE MIRROR WIREFRAME REMESH SCREW SIMPLE_DEFORM WAVE CAST SHRINKWRAP ...), any modifier property; object props take names; angles in degrees; DISPLACE texture{type,noise_scale,...} |
| bevel / subdivision / array / solidify / displace | wrappers with good defaults (any modifier property can be passed) |
| boolean | target, cutter, operation DIFFERENCE/UNION/INTERSECT, solver, hide_cutter, apply |
| apply_modifiers / shade_smooth(auto_angle) / set_origin(BOUNDS_CENTER/BOTTOM/WORLD_ORIGIN) / convert_to_mesh | |
| transform | target (or list), location/rotation/scale (absolute), offset/rotate_by (relative) |
| parent | child (or list), parent, keep_transform |
| duplicate / delete / hide | |
| instance_grid | source, count [x,y,z], spacing, random_scale, random_rotation, seed. Returns the parent empty |
| scatter | source, count, area [x,y,z] or surface=object, scale_min/max, random_rotation [deg xyz], min_distance, seed (Python instances; use gn_scatter when you need thousands) |
| curve_path | points [[x,y,z]...], closed, bevel_depth (>0 gives a tube, good for neon), smooth, material |
| circle_path | radius, height, center |

## materials (all multiply alpha by the object color alpha, so `fade` works on every one)
| op | key params |
|---|---|
| material | name, preset, color, color2, scale, bump, emission_strength, alpha, roughness/metallic/ior/transmission/coat/coat_roughness/sheen/subsurface/specular/anisotropic/thin_film, inputs{"Principled input": v}; target/targets assigns it |
| presets | gold gold_brushed rose_gold silver chrome brushed_metal aluminum copper black_metal glass frosted_glass tinted_glass diamond water plastic glossy_plastic rubber matte clay ceramic car_paint (flakes) pearl iridescent (thin film) fabric velvet wax skin emission neon noise marble wood concrete |
| assign_material | target, material (name, preset name, or dict spec), slot |
| image_material | path, emission, emission_strength, alpha, roughness, scale, target |
| video_material | path (movie synced to the timeline, emission by default), loop, target |
| material_graph | name, nodes{id:{type,inputs,props,location}}, links[["a.Out","b.In"]]. "Principled BSDF" and "Material Output" already exist; keep_principled=false gives an empty graph |
| set_material_input | material, input, value, node |
| material_presets | lists the presets |

## lights
| op | key params |
|---|---|
| light | type POINT/SPOT/AREA/SUN, name, location, rotation or target (name or [x,y,z]), energy (W), color or temperature (K), size, size_y, shape, spot_size, spot_blend, angle, spread, visible_camera (default false) |
| three_point | target, distance, intensity, key/fill/rim_temperature, fill_ratio, rim_ratio, azimuth, softness. Energy scales with distance² |
| rim_light | target, side left/right, temperature/color, energy |
| light_sweep | target, frame_start/end, color, energy, easing, link (default true: light-linked to the target so no streak shows in the floor). The moving glint on metal |
| light_link | light, receivers: the light only affects those objects (Cycles + EEVEE light linking) |
| hdri_light | path, strength, rotation, background |
| god_rays | target, azimuth (0 = camera side), elevation, density, energy, color, spot_size: a spot light plus a fog box. Cycles only and slow on CPU |

## camera
A camera made with `target` tracks an aim empty `<Camera>_Aim` through a Track To constraint. Moving that empty re-aims the camera.
| op | key params |
|---|---|
| camera | name, location, target (name or [x,y,z]), lens, sensor, type PERSP/ORTHO, ortho_scale, fstop (turns DOF on), focus, shift_x/y, follow_target, active |
| frame_objects | targets (default: everything renderable except backdrops), direction [x,y,z] from subject toward camera, margin (1.1-1.5), lens. Auto-framing; creates a camera if there is none |
| dof | camera, fstop, focus (object) or distance, blades |
| track_to | target (object that turns), aim (object or point) |
| camera_move | keys [{frame, location?, aim?, lens?, fstop?, easing?}] |
| camera_orbit | target, radius, height, start_angle, end_angle, easing, cyclic (0→360 linear cyclic gives a perfect loop) |
| camera_dolly | from_location, to_location |
| camera_push_in | amount (fraction of the distance), reverse=true pulls out |
| camera_crane | from_height, to_height |
| camera_zoom | from_lens, to_lens, dolly_zoom (vertigo) |
| rack_focus | from_target, to_target, fstop |
| camera_shake | strength (m), speed (frames per noise period), rotation (deg; only for untracked cameras) |
| follow_path | path (curve), target (default: camera), follow |

## animate
| op | key params |
|---|---|
| keyframe | target, data_path, keys [{frame,value,easing?}], index, id_type object/data/material/world/scene/node_group, cyclic. Example data paths: `modifiers["Bevel"].width`; `nodes["Principled BSDF"].inputs["Emission Strength"].default_value` (id_type material); `lens` (id_type data); `modifiers["GN"].properties.inputs.Socket_2.value` (5.x GN modifier input) |
| animate | target or targets, property location/rotation/scale/alpha/any path, from_value, to_value (null = current), frame_start/frame_end or duration, easing, stagger (frames between targets), relative, order x/-x/reverse, hold |
| fade | target, from_value, to_value, frame_start, frame_end, easing (object alpha, children included) |
| noise | target, data_path, strength, scale (period in frames), seed, restricted range: organic jitter, floating, flicker |
| driver | target, data_path, expression (simple expressions like `sin(frame/12)*0.3` run without auto-exec), index |
| turntable | target, degrees, axis, easing linear, cyclic (seamless) |
| visibility | target, keys [{frame, visible}] |
| rigid_body | target(s), type ACTIVE/PASSIVE, mass, friction, bounciness, shape |
| rigid_drop | source, count, area, height, floor: rains copies onto a passive floor |
| collision / cloth(preset silk/cotton/leather/denim, pin_group) / particles(emitter, count, lifetime, velocity, gravity, size, instance, emit_from) / bake_physics | |
Physics stills: `render_still` steps every frame from the start, so simulations are correct at any frame.

## geonodes
| op | key params |
|---|---|
| gn_scatter | target (surface), instance (object), density, distance_min (Poisson), seed, scale_min/max, random_rotation, align_to_normal, keep_surface, realize |
| gn_wave_grid | name, count, spacing, cell, height, amplitude, frequency, pattern radial/linear/diagonal, shape cube/cylinder, material, loop_frames (seamless). Writes the 0..1 instance attribute `wave` (shader: Attribute node, type INSTANCER, name "wave") |
| gn_text | text (Arabic gets shaped), font, size, depth, material. Inputs Depth/Size can be animated with gn_set_input |
| gn_graph | target (or a new host object), interface [{name,type,default}], nodes, links ("Group Input"/"Group Output" already exist), inputs |
| gn_set_input | target, input (interface name), value, frame (keys it), easing |

## text3d
| op | key params |
|---|---|
| text3d | text, name, font (path / "arialbd" / "Amiri-Bold": searched in C:\Windows\Fonts, the user font folder and assets/fonts), size, extrude, bevel_depth, bevel_resolution, align_x/align_y, location, rotation (default [90,0,0], upright facing -Y), material, letter_spacing, word_spacing, line_spacing, split, to_mesh |
| text_reveal | target, style rise/drop/scale/fade/slide/flip/typewriter (these need split=true) or extrude/bevel (FONT objects only), frame_start, duration, stagger, easing, fade, order |
| shape_text | returns the shaped visual string (for debugging) |
Arabic: the text is reshaped and bidi-reordered (in-process if available, otherwise through system python `arabic_reshaper` + `python-bidi`), and if no font is given an Arabic-capable one is chosen (arialbd). `split=true` creates one object per connected glyph cluster (for Arabic, per joined word piece; dots stay with their letter), ordered right-to-left.

## render
| op | key params |
|---|---|
| render_settings | engine, samples, denoise, motion_blur, shutter, transparent, resolution_percentage, device AUTO/CPU/GPU, bounces, clamp_indirect, adaptive_threshold, caustics, raytracing (EEVEE), frame_step |
| gpu_setup | prefer OPTIX>CUDA>HIP>ONEAPI>METAL; falls back to CPU |
| compositor | glare/bloom {type Bloom/Fog Glow/Streaks/Ghosts/Simple Star/Sun Beams, threshold, strength, size, quality, streaks, angle, tint} (or true), lens {distortion, dispersion}, vignette {strength, size}, exposure, saturation, contrast. Recipe shortcut: top-level `"post": {...}` |
| render / render_still / render_animation | type still/animation; out (.png .jpg .exr .webp / .mp4 .mov .webm / name_####.png); frame; transparent; crf (default 16); preset; audio; keep_frames; contact_sheet |
How video is made: PNG frames go to `<out>_frames/`, system ffmpeg encodes them (H.264 yuv420p CRF 16 +faststart; a transparent .mov becomes ProRes 4444; .webm becomes VP9), then the frames are deleted. `<out>_contact.png` tiles 6 frames for a quick look. Without ffmpeg, Blender's own FFMPEG writer is used.

## presets (one op = a whole scene)
| op | key params |
|---|---|
| product_shot | subject (name) or model (path) or neither (a placeholder box); material; theme dark/warm/cool/light/black; plinth, plinth_material; size; angle; elevation; lens; fstop; margin; accent; bloom |
| logo_reveal | text (Arabic ok), subtitle, font, subtitle_font, material (gold/chrome/rose_gold...), theme, style (see text_reveal), frame_start, reveal_frames, stagger, size, extrude, bevel, sweep, dust, reflective_floor, push_in, accent, bloom |
| title_card | title, subtitle, palette midnight/sunset/emerald/mono/royal, font, style, material, glow_line |
| turntable_scene | product_shot params + frames, degrees, rotate subject/camera (always a seamless loop) |

## Raw bpy scripts (`bl.py exec script.py -- args`)
The script runs as `__main__` with these globals: `STATE` (a ready state dict), `OUT_DIR`, `PREVIEW` and `bpylib`.
`bpylib.run_op(STATE, "add_primitive", type="cube", name="Box")` calls any op. `bpylib.run_steps(STATE, [steps])` runs a list of steps. `sys.argv` holds the args after `--`.
To render inside a script: `bpylib.run_op(STATE, "render", type="still", out="x.png")`. Outputs are collected in `STATE["outputs"]`.
