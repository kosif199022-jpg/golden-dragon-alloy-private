# video - Video Sequence Editor + compositor control (Blender 5.2)

Module: `scripts/bpylib/video.py`. Test harness:
`blender -b --factory-startup -P tests/draw_video/harness.py -- examples/video_edit.json`
Time: seconds for in/out/duration/fade params; `start` is a timeline frame (1-based).
Strips live in `state["strips"][name]`; a clip's audio is `<name>_audio`; `cut` creates `<name>_b`; `set_speed` creates `<name>_speed`; `transition` creates `<a>_to_<b>`.

## Ops
| op | purpose / key params |
|---|---|
| vse_setup | resolution/fps (or adopt from `from_clip`), clear, frame_start |
| add_movie | filepath,name,start,trim_in,trim_out or duration,channel,audio_channel,fit,volume,opacity,blend,fade_in/out,speed |
| add_image / add_image_sequence | duration, fit; directory+pattern, frame_hold |
| add_color | color, duration (plates, flashes) |
| add_text | text,font,size,color,position(0..1),anchor_x/y,align,shadow*,outline*,box*,wrap_width,fade_in/out; Arabic shaped (VSE text has no shaping) |
| add_audio | volume,trim,fade_in/out,pan |
| fade | opacity (video/text) or volume (sound) keyframes, easing |
| cut / move / trim | razor split (audio split too), reposition (audio follows), re-trim |
| set_speed | Speed effect strip, factor (audio length adjusted, not time-stretched) |
| transition | CROSS/GAMMA_CROSS/WIPE/ADD/... between a and b, auto-overlap, audio crossfade |
| transform / ken_burns | scale/position/rotation/origin + keyframes (EASE/LINEAR/BEZIER) |
| crop / blend | crop px; blend_type/opacity/mute/volume |
| adjustment_layer | effect strip that affects everything below |
| color_grade | BRIGHT_CONTRAST, COLOR_BALANCE (lift/gamma/gain), WHITE_BALANCE, CURVES, TONEMAP, saturation, multiply |
| compositor_fx | Compositor modifier node group: glare, blur, lens_distortion, chroma_key (green screen), vignette, brightness, pixelate, posterize |
| scene_strip | put another scene (3D or drawing) in the timeline |
| video_as_texture | movie on a 3D plane (emission material, auto refresh) |
| duck | auto-duck music under a voice strip |
| render_mp4 | H.264 + AAC; quality (constant_rate_factor enum) or crf, preset GOOD/BEST/REALTIME, codec, container, audio_bitrate, lut (ffmpeg lut3d post step), still_frame |
| vse_from_edl | whole timeline from a clip list (in/out, transitions, captions, music, end card, grade, fades) |
| vse_list | debug listing |

## Verified 5.2 API facts
* `scene.sequence_editor.strips` / `strips_all`; `strips.new_movie/new_sound/new_image/new_effect/new_scene`; movie strips carry NO audio (separate `new_sound`).
* Position and length: `left_handle`, `right_handle`, `duration`, `content_trim_start/end` (frames). Create at `start - trim_in`, set trims, then `_place` so the first visible frame equals `start`.
* Opacity `blend_alpha`, mode `blend_type`; keyframes via `scene.keyframe_insert('sequence_editor.strips_all["X"].blend_alpha')`.
* Output: `image_settings.media_type='VIDEO'`, `file_format='FFMPEG'`, `ffmpeg.format='MPEG4'`, `codec='H264'`, `constant_rate_factor` in NONE/LOSSLESS/PERC_LOSSLESS/HIGH/MEDIUM/LOW/VERYLOW/LOWEST/CUSTOM, `audio_codec='AAC'`.
* Compositor modifier: `strip.modifiers.new(name,'COMPOSITOR').node_group` is a CompositorNodeTree with NodeGroupInput/Output. Menu inputs take strings ("Fog Glow"); Blur Size is a 2-vector; mixing uses `ShaderNodeMix` (no MixRGB in 5.2).
* Channel layout of vse_from_edl: audio 1-2, video 3-4 (alternating for overlaps), transitions 5, text 6+, music 7.

## Limitations
* LUT only via render_mp4(lut=...) (ffmpeg post step); the VSE has no LUT modifier.
* Speed changes do not time-stretch audio. Text strips have no native RTL shaping (handled by shape_arabic; mixed Latin/Arabic lines use visual order).
* Chroma key quality depends on the Keying node tolerances; put a background strip on a lower channel.
* `scene_strip` renders the other scene with its own engine (slow for EEVEE 3D).
