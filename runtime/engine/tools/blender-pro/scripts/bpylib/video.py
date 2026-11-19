"""
blender-pro :: video  --  Video Sequence Editor (VSE) + compositor control, Blender 5.x.

Every op: op(state, **params) -> dict, exported in OPS.  Strips are stored in
state["strips"][name] and referenced by later steps with "target" (or "a"/"b").
Blender 5.x API notes (verified on 5.2.3):
  * scene.sequence_editor.strips / strips_all   (was .sequences / sequences_all)
  * strip.left_handle / right_handle / duration (frame_final_* deprecated)
  * strip.content_trim_start / content_trim_end trim the source (frames)
  * strip.blend_alpha is the opacity, strip.blend_type the blend mode
  * movie strips do NOT carry audio: a separate sound strip is added (add_movie does it)
  * channels: audio strips get channel `audio_channel`, video `channel`

Time params: unless a name says `_frames`, "seconds" are used for in/out/duration/fade
values; they are converted with the scene fps.  Start positions (`start`) are in
timeline FRAMES (1-based) unless `start_sec` is given.
"""
import math
import os
import warnings

try:
    import bpy  # noqa
except ImportError:
    bpy = None

try:
    from . import draw as _draw
except Exception:  # standalone harness / direct sys.path import
    try:
        import draw as _draw
    except Exception:
        _draw = None

warnings.filterwarnings("ignore", message=".*expected to be removed in Blender 6.0.*")


# ---------------------------------------------------------------- helpers
def _scene():
    return bpy.context.scene


def _ed():
    sc = _scene()
    return sc.sequence_editor or sc.sequence_editor_create()


def _fps():
    r = _scene().render
    return r.fps / (r.fps_base or 1.0)


def _fr(sec):
    return int(round(float(sec) * _fps()))


def _store(state):
    return state.setdefault("strips", {})


def _get(state, name):
    ed = _ed()
    s = _store(state).get(name, None)
    if s is not None:
        try:
            return ed.strips_all[s.name]
        except Exception:
            pass
    if name in ed.strips_all:
        return ed.strips_all[name]
    raise ValueError("strip not found: %r (known: %s)" % (name, list(_store(state))))


def _reg(state, key, strip):
    _store(state)[key] = strip
    return strip


def _path(p, state=None):
    p = os.path.expanduser(str(p))
    if not os.path.isabs(p) and state and state.get("recipe_dir"):
        cand = os.path.join(state["recipe_dir"], p)
        if os.path.exists(cand):
            p = cand
    return os.path.abspath(p)


def _free_channel(start, end, first=1, avoid=()):
    ed = _ed()
    for ch in range(first, 129):
        if ch in avoid:
            continue
        ok = True
        for s in ed.strips_all:
            if s.channel == ch and s.left_handle < end and s.right_handle > start:
                ok = False
                break
        if ok:
            return ch
    raise RuntimeError("no free VSE channel")


def _place(strip, start):
    """Move strip so its first visible frame is `start`."""
    delta = int(start) - int(strip.left_handle)
    if delta:
        strip.frame_start = strip.frame_start + delta
    return strip


def _end(strip):
    return int(strip.right_handle)


def _key(strip, path, frame, value=None):
    """Keyframe a strip property (path relative to strip)."""
    sc = _scene()
    if value is not None:
        obj = strip
        parts = path.split(".")
        for p in parts[:-1]:
            obj = getattr(obj, p)
        setattr(obj, parts[-1], value)
    dp = 'sequence_editor.strips_all["%s"].%s' % (strip.name, path)
    sc.keyframe_insert(data_path=dp, frame=int(frame))


def _fcurves_for(sc, path_prefix):
    ad = sc.animation_data
    if not ad or not ad.action:
        return []
    act = ad.action
    out = []
    try:
        for layer in act.layers:
            for st in layer.strips:
                for cb in st.channelbags:
                    out.extend(cb.fcurves)
    except Exception:
        pass
    if not out and hasattr(act, "fcurves"):
        out = list(act.fcurves)
    return [f for f in out if f.data_path.startswith(path_prefix)]


def _interp(strip, easing="LINEAR"):
    for fc in _fcurves_for(_scene(), 'sequence_editor.strips_all["%s"]' % strip.name):
        for kp in fc.keyframe_points:
            if easing == "LINEAR":
                kp.interpolation = "LINEAR"
            else:
                kp.interpolation = "BEZIER"
                kp.easing = "EASE_IN_OUT" if easing == "EASE" else "AUTO"
                if easing == "EASE":
                    kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"


def _col(c, default=(1, 1, 1, 1)):
    if _draw is not None:
        return _draw.parse_color(c, default)
    if c is None:
        return default
    c = list(c)
    return tuple(c + [1.0] * (4 - len(c)))


def _fit_frame_end(end):
    sc = _scene()
    if end > sc.frame_end:
        sc.frame_end = int(end)


# ---------------------------------------------------------------- setup
def vse_setup(state, resolution=None, fps=None, from_clip=None, frame_start=1, clear=True,
              percentage=100, channels_hint=None):
    """Prepare the scene for video editing.
    params: resolution=[w,h] (default: from_clip's size, else 1920x1080), fps (default: from_clip's
      fps, else 30), from_clip=None (media path whose resolution/fps are adopted),
      frame_start=1, clear=True (remove existing strips), percentage=100 (render scale %).
    Also disables proxies/caching surprises and makes sure the sequencer is used for rendering."""
    sc = _scene()
    ed = _ed()
    if clear:
        for s in list(ed.strips_all):
            ed.strips.remove(s) if s.parent_meta is None else None
        state["strips"] = {}
    w, h, f = 1920, 1080, 30.0
    if from_clip:
        tmp = ed.strips.new_movie("_probe", _path(from_clip, state), 1, 1)
        try:
            e = tmp.elements[0]
            w, h = e.orig_width, e.orig_height
            f = tmp.fps or 30.0
        finally:
            ed.strips.remove(tmp)
    if resolution:
        w, h = int(resolution[0]), int(resolution[1])
    if fps:
        f = float(fps)
    sc.render.resolution_x, sc.render.resolution_y = int(w), int(h)
    sc.render.resolution_percentage = int(percentage)
    base = 1.001 if abs(f - round(f)) > 1e-3 and abs(f * 1.001 - round(f * 1.001)) < 1e-2 else 1.0
    sc.render.fps = int(round(f * base))
    sc.render.fps_base = base
    sc.frame_start = int(frame_start)
    sc.render.use_sequencer = True
    sc.render.use_compositing = False
    try:
        sc.view_settings.view_transform = "Standard"
    except Exception:
        pass
    return {"resolution": [w, h], "fps": _fps()}


def _add_sound_for(state, key, filepath, start, channel, trim_in_f, trim_out_f, volume, pan=0.0):
    ed = _ed()
    try:
        snd = ed.strips.new_sound(key + "_audio", filepath, channel, start - trim_in_f)
    except Exception:
        return None
    if snd.duration <= 0:
        ed.strips.remove(snd)
        return None
    if trim_in_f:
        snd.content_trim_start = trim_in_f
    if trim_out_f:
        snd.content_trim_end = trim_out_f
    _place(snd, start)
    snd.volume = volume
    snd.pan = pan
    _reg(state, key + "_audio", snd)
    return snd


def add_movie(state, filepath, name=None, start=None, start_sec=None, channel=None, trim_in=0.0,
              trim_out=None, duration=None, with_audio=True, audio_channel=None, fit="FIT",
              volume=1.0, opacity=1.0, blend="ALPHA_OVER", fade_in=0.0, fade_out=0.0, speed=None,
              use_proxy=False):
    """Add a video clip (and its audio as a linked sound strip).
    params: filepath (required), name=None (default: file stem), start=None (timeline frame; default =
      end of the timeline), start_sec (alternative to start), channel=None (auto: first free >=2),
      trim_in=0.0 (seconds cut from clip head), trim_out=None (source second where the clip ENDS;
      i.e. use [trim_in, trim_out]), duration=None (seconds to keep after trim_in; alternative to trim_out),
      with_audio=True, audio_channel=None (auto, below video), fit="FIT"|"FILL"|"STRETCH"|"ORIGINAL",
      volume=1.0, opacity=1.0, blend="ALPHA_OVER"|"REPLACE"|"CROSS"|"ADD"|"MULTIPLY"|"SCREEN"|...,
      fade_in=0.0, fade_out=0.0 (seconds, video opacity + audio volume), speed=None (e.g. 2.0, see set_speed),
      use_proxy=False.
    Registers state['strips'][name] (video) and state['strips'][name+'_audio']."""
    ed = _ed()
    fp = _path(filepath, state)
    key = name or os.path.splitext(os.path.basename(fp))[0]
    if start is None:
        start = _fr(start_sec) + 1 if start_sec is not None else (max([s.right_handle for s in ed.strips_all] or [_scene().frame_start]))
    start = int(start)
    tmp_ch = channel or 2
    st = ed.strips.new_movie(key, fp, tmp_ch, start, fit_method=fit)
    src_frames = st.content_duration
    tin = _fr(trim_in)
    tout = 0
    if trim_out is not None:
        tout = max(0, src_frames - _fr(trim_out))
    elif duration is not None:
        tout = max(0, src_frames - tin - _fr(duration))
    st.frame_start = start - tin  # so that the trimmed head starts at `start`
    if tin:
        st.content_trim_start = tin
    if tout:
        st.content_trim_end = tout
    _place(st, start)
    if channel is None:
        st.channel = _free_channel(st.left_handle, st.right_handle, first=2)
    st.blend_type = blend
    st.blend_alpha = opacity
    st.use_proxy = use_proxy
    _reg(state, key, st)
    snd = None
    if with_audio:
        ach = audio_channel or _free_channel(st.left_handle, st.right_handle, first=1, avoid=(st.channel,))
        if ach >= st.channel and audio_channel is None:
            ach = _free_channel(st.left_handle, st.right_handle, first=1, avoid=(st.channel,))
        snd = _add_sound_for(state, key, fp, start, ach, tin, tout, volume)
    if speed and speed != 1.0:
        set_speed(state, target=key, factor=speed)
    if fade_in or fade_out:
        fade(state, target=key, fade_in=fade_in, fade_out=fade_out)
    _fit_frame_end(_end(st))
    return {"strip": st.name, "channel": st.channel, "start": st.left_handle, "end": st.right_handle,
            "audio": snd.name if snd else None, "source_frames": src_frames}


def add_image(state, filepath, name=None, start=None, duration=3.0, channel=None, fit="FIT",
              opacity=1.0, blend="ALPHA_OVER"):
    """Add a still image for `duration` seconds.
    params: filepath, name, start (frame; default end of timeline), duration=3.0 (s), channel=None,
      fit="FIT"|"FILL"|"STRETCH"|"ORIGINAL", opacity=1.0, blend="ALPHA_OVER"."""
    ed = _ed()
    fp = _path(filepath, state)
    key = name or os.path.splitext(os.path.basename(fp))[0]
    if start is None:
        start = max([s.right_handle for s in ed.strips_all] or [_scene().frame_start])
    n = max(1, _fr(duration))
    ch = channel or _free_channel(start, start + n, first=2)
    st = ed.strips.new_image(key, fp, ch, int(start), fit_method=fit)
    st.right_handle = int(start) + n
    st.blend_type = blend
    st.blend_alpha = opacity
    _reg(state, key, st)
    _fit_frame_end(_end(st))
    return {"strip": st.name, "channel": st.channel, "start": st.left_handle, "end": st.right_handle}


def add_image_sequence(state, directory, pattern="*.png", name=None, start=None, frame_hold=1, channel=None,
                       fit="FIT", fps_override=None):
    """Add a numbered image sequence (frames sorted by name).
    params: directory, pattern="*.png" (glob), name, start, frame_hold=1 (timeline frames per image),
      channel=None, fit="FIT"."""
    import glob
    ed = _ed()
    files = sorted(glob.glob(os.path.join(_path(directory, state), pattern)))
    if not files:
        raise ValueError("no files for %s/%s" % (directory, pattern))
    key = name or os.path.basename(os.path.normpath(directory))
    if start is None:
        start = max([s.right_handle for s in ed.strips_all] or [_scene().frame_start])
    ch = channel or _free_channel(start, start + len(files) * frame_hold, first=2)
    st = ed.strips.new_image(key, files[0], ch, int(start), fit_method=fit)
    for f in files[1:]:
        st.elements.append(os.path.basename(f))
    if frame_hold > 1:
        st.strobe = float(frame_hold)
        st.right_handle = int(start) + len(files) * frame_hold
    _reg(state, key, st)
    _fit_frame_end(_end(st))
    return {"strip": st.name, "images": len(files), "end": st.right_handle}


def add_color(state, color="#000000", name="Color", start=None, duration=3.0, channel=None, opacity=1.0):
    """Solid colour strip (backgrounds, flashes, fade-to-black plates).
    params: color="#000000", name, start, duration=3.0 (s), channel=None, opacity=1.0."""
    ed = _ed()
    if start is None:
        start = max([s.right_handle for s in ed.strips_all] or [_scene().frame_start])
    n = max(1, _fr(duration))
    ch = channel or _free_channel(start, start + n, first=1)
    st = ed.strips.new_effect(name, "COLOR", ch, int(start), length=n)
    st.color = _col(color)[:3]
    st.blend_alpha = opacity
    _reg(state, name, st)
    _fit_frame_end(_end(st))
    return {"strip": st.name, "channel": st.channel, "start": st.left_handle, "end": st.right_handle}


def add_text(state, text, name=None, start=None, duration=3.0, channel=None, font=None, size=60.0,
             color="#FFFFFF", position=(0.5, 0.1), anchor_x="CENTER", anchor_y="BOTTOM", align="CENTER",
             shadow=True, shadow_color=(0, 0, 0, 0.8), shadow_offset=0.04, shadow_blur=0.1, outline=0.0,
             outline_color="#000000", box=False, box_color=(0, 0, 0, 0.5), box_margin=0.01,
             wrap_width=0.0, bold=False, italic=False, fade_in=0.0, fade_out=0.0, shape_arabic=True,
             rtl=None, opacity=1.0, line_spacing=0.0):
    """Burn-in title / subtitle text strip.
    params: text (required, "\\n" = new line), name, start (frame; default 1), duration=3.0 (s), channel=None
      (auto, high), font=None (TTF/OTF path; default: Arial on Windows, which supports Arabic),
      size=60 (px at render height), color="#FFFFFF", position=[0.5,0.1] (x,y 0..1 of frame, origin bottom-left),
      anchor_x=LEFT|CENTER|RIGHT, anchor_y=TOP|CENTER|BOTTOM, align=LEFT|CENTER|RIGHT, shadow=True,
      shadow_color, shadow_offset=0.04, shadow_blur=0.1, outline=0.0 (width 0..1; >0 enables),
      outline_color, box=False, box_color=[0,0,0,0.5], box_margin=0.01, wrap_width=0 (0..1 of width),
      bold/italic, fade_in/fade_out (s), shape_arabic=True (Arabic letters are joined + reordered
      to visual order since the VSE text engine has no shaping), rtl=None (reserved), opacity=1.0.
    Arabic example: {"op":"add_text","text":"مرحبا بالعالم","font":"C:/Windows/Fonts/arial.ttf"}"""
    ed = _ed()
    if start is None:
        start = _scene().frame_start
    n = max(1, _fr(duration))
    ch = channel or _free_channel(int(start), int(start) + n, first=6)
    key = name or "Text"
    st = ed.strips.new_effect(key, "TEXT", ch, int(start), length=n)
    st.text = _draw.shape_arabic(text) if (shape_arabic and _draw) else text
    fpath = font
    if not fpath and _draw:
        fpath = _draw._font_default()
    if fpath and os.path.exists(fpath):
        st.font = bpy.data.fonts.load(fpath, check_existing=True)
    st.font_size = float(size)
    st.color = _col(color)
    st.location = (float(position[0]), float(position[1]))
    st.anchor_x, st.anchor_y, st.alignment_x = anchor_x, anchor_y, align
    st.use_shadow = bool(shadow)
    if shadow:
        st.shadow_color = _col(shadow_color)
        st.shadow_offset = shadow_offset
        st.shadow_blur = shadow_blur
    st.use_outline = outline > 0
    if outline > 0:
        st.outline_width = outline
        st.outline_color = _col(outline_color)
    st.use_box = bool(box)
    if box:
        st.box_color = _col(box_color)
        st.box_margin = box_margin
    st.wrap_width = wrap_width
    st.use_bold, st.use_italic = bold, italic
    st.blend_alpha = opacity
    if line_spacing:
        st.space_line = line_spacing
    _reg(state, key, st)
    if fade_in or fade_out:
        fade(state, target=key, fade_in=fade_in, fade_out=fade_out)
    _fit_frame_end(_end(st))
    return {"strip": st.name, "channel": st.channel, "shown": st.text, "start": st.left_handle, "end": st.right_handle}


def add_audio(state, filepath, name=None, start=None, channel=None, volume=1.0, trim_in=0.0, trim_out=None,
              duration=None, fade_in=0.0, fade_out=0.0, pan=0.0, loop_to=None):
    """Add an audio file (music, voice-over, SFX).
    params: filepath, name, start (frame; default scene start), channel=None (auto, from 1 up),
      volume=1.0, trim_in=0 (s), trim_out=None (source second where it ends), duration=None (s to keep),
      fade_in=0, fade_out=0 (s, volume ramps), pan=0.0 (-1..1), loop_to=None (reserved).
    Tip: volume can be keyframed through `volume_keys`-like use of the `fade` op or ducking op `duck`."""
    ed = _ed()
    fp = _path(filepath, state)
    key = name or os.path.splitext(os.path.basename(fp))[0]
    start = int(start if start is not None else _scene().frame_start)
    tin = _fr(trim_in)
    probe = ed.strips.new_sound("_p", fp, 1, 1)
    total = probe.duration
    ed.strips.remove(probe)
    tout = 0
    if trim_out is not None:
        tout = max(0, total - _fr(trim_out))
    elif duration is not None:
        tout = max(0, total - tin - _fr(duration))
    ch = channel or _free_channel(start, start + max(1, total - tin - tout), first=1)
    st = ed.strips.new_sound(key, fp, ch, start - tin)
    if tin:
        st.content_trim_start = tin
    if tout:
        st.content_trim_end = tout
    _place(st, start)
    st.volume = volume
    st.pan = pan
    _reg(state, key, st)
    if fade_in or fade_out:
        fade(state, target=key, fade_in=fade_in, fade_out=fade_out)
    _fit_frame_end(_end(st))
    return {"strip": st.name, "channel": st.channel, "start": st.left_handle, "end": st.right_handle}


def fade(state, target, fade_in=0.0, fade_out=0.0, easing="LINEAR", to_value=0.0):
    """Fade a strip in/out with keyframes: video/text/image/color -> opacity (blend_alpha), sound -> volume.
    params: target, fade_in=0.0 (s), fade_out=0.0 (s), easing="LINEAR"|"EASE"|"BEZIER", to_value=0.0
      (level at the faded ends). Fading video to 0 reveals what is below (black if nothing)."""
    st = _get(state, target)
    prop = "volume" if st.type == "SOUND" else "blend_alpha"
    full = getattr(st, prop)
    a, b = int(st.left_handle), int(st.right_handle)
    fi, fo = _fr(fade_in), _fr(fade_out)
    if fi:
        _key(st, prop, a, to_value)
        _key(st, prop, a + fi, full)
    if fo:
        if not fi:
            _key(st, prop, b - fo, full)
        else:
            _key(st, prop, b - fo, full)
        _key(st, prop, b, to_value)
    _interp(st, easing)
    # linked audio of the same clip
    if st.type != "SOUND":
        lk = _store(state).get(target + "_audio")
        if lk is not None:
            fade(state, target + "_audio", fade_in, fade_out, easing, to_value)
    return {"strip": st.name, "property": prop}


def cut(state, target, at=None, at_sec=None, hard=False, names=None):
    """Split a strip in two (razor). Also splits the linked audio strip at the same frame.
    params: target, at (absolute timeline frame) or at_sec (seconds from strip start), hard=False
      (HARD removes the cut parts' trims), names=[left, right] to register results.
    Result strips: left keeps the target name, right is registered as <target>_b (or names[1])."""
    st = _get(state, target)
    frame = int(at) if at is not None else int(st.left_handle) + _fr(at_sec or 0)
    method = "HARD" if hard else "SOFT"
    right = st.split(frame=frame, split_method=method)
    out = {"left": st.name, "right": right.name if right else None}
    nm = (names or [None, None])[1] or (target + "_b")
    if right:
        _reg(state, nm, right)
    lk = _store(state).get(target + "_audio")
    if lk is not None:
        try:
            lk = _get(state, target + "_audio")
            r2 = lk.split(frame=frame, split_method=method)
            if r2:
                _reg(state, nm + "_audio", r2)
        except Exception:
            pass
    return out


def move(state, target, start=None, start_sec=None, channel=None, ripple_gap=None, with_linked=True):
    """Move a strip to a new start frame / channel (linked audio follows).
    params: target, start (frame) | start_sec, channel=None, with_linked=True."""
    st = _get(state, target)
    if start is None and start_sec is not None:
        start = _fr(start_sec) + _scene().frame_start
    delta = 0
    if start is not None:
        delta = int(start) - int(st.left_handle)
        _place(st, int(start))
    if channel:
        st.channel = int(channel)
    lk = _store(state).get(target + "_audio")
    if with_linked and lk is not None and delta:
        a = _get(state, target + "_audio")
        _place(a, int(a.left_handle) + delta)
    _fit_frame_end(_end(st))
    return {"strip": st.name, "start": st.left_handle, "end": st.right_handle}


def trim(state, target, trim_in=0.0, trim_out=None, duration=None):
    """Re-trim an existing strip (seconds into the source, relative to current head/tail).
    params: target, trim_in=0.0 (extra seconds cut from head), trim_out=None (extra seconds cut from the tail),
      duration=None (set final visible length in seconds)."""
    st = _get(state, target)
    for s in [st] + ([_get(state, target + "_audio")] if target + "_audio" in _store(state) else []):
        start = int(s.left_handle)
        if trim_in:
            s.content_trim_start += _fr(trim_in)
            _place(s, start)
        if trim_out:
            s.content_trim_end += _fr(trim_out)
        if duration is not None:
            s.right_handle = int(s.left_handle) + _fr(duration)
    return {"strip": st.name, "start": st.left_handle, "end": st.right_handle}


def set_speed(state, target, factor=2.0, mode="SPEED_EFFECT", keep_audio_pitch=True):
    """Change playback speed of a clip (retime).
    params: target, factor=2.0 (>1 faster, <1 slow motion), mode="SPEED_EFFECT" (Speed effect strip
      placed on top; target strip is hidden by the effect and the visible length shrinks/stretches).
    The linked audio strip's length is adjusted (and pitch_correction enabled) but audio is not
    time-stretched by the VSE; for exact audio at other speeds pre-process with ffmpeg atempo.
    Registers the effect strip as <target>_speed."""
    ed = _ed()
    st = _get(state, target)
    a = int(st.left_handle)
    n_src = int(st.duration)
    fx = ed.strips.new_effect(target + "_speed", "SPEED", _free_channel(a, a + max(1, int(n_src / factor)), first=st.channel + 1),
                              a, length=max(1, int(round(n_src / factor))), input1=st)
    fx.speed_control = "MULTIPLY"
    fx.speed_factor = float(factor)
    fx.use_frame_interpolate = factor < 1.0
    _reg(state, target + "_speed", fx)
    lk = _store(state).get(target + "_audio")
    if lk is not None:
        au = _get(state, target + "_audio")
        au.right_handle = int(au.left_handle) + max(1, int(round(au.duration / factor)))
        try:
            au.pitch_correction = bool(keep_audio_pitch)
        except Exception:
            pass
    _fit_frame_end(_end(fx))
    return {"strip": fx.name, "start": fx.left_handle, "end": fx.right_handle, "factor": factor}


def transition(state, a, b, type="CROSS", duration=1.0, overlap=True, direction="IN", wipe_type="SINGLE",
               angle=0.0, blur=0.1, audio_crossfade=True, name=None):
    """Transition between two clips (b follows a).
    params: a, b (strip names), type="CROSS"|"GAMMA_CROSS"|"WIPE"|"ADD"|"SUBTRACT"|"ALPHA_OVER"|"MULTIPLY",
      duration=1.0 (s), overlap=True (if b does not overlap a yet, b -- and its audio -- is moved earlier
      so that it overlaps the tail of a by `duration`), wipe_type="SINGLE"|"DOUBLE"|"IRIS"|"CLOCK" (WIPE only),
      direction="IN"|"OUT", angle=0.0 (deg), blur=0.1 (wipe softness 0..1), audio_crossfade=True
      (volume ramps on the linked audio strips). Registers the effect as `name` (default <a>_to_<b>).
    The effect strip is placed on a channel above both inputs."""
    ed = _ed()
    A, B = _get(state, a), _get(state, b)
    d = max(1, _fr(duration))
    if overlap and int(B.left_handle) >= int(A.right_handle) - 0:
        target_start = int(A.right_handle) - d
        move(state, b, start=target_start)
    elif overlap:
        d = max(1, int(A.right_handle) - int(B.left_handle))
    s0 = int(B.left_handle)
    ch = _free_channel(s0, s0 + d, first=max(A.channel, B.channel) + 1)
    fx = ed.strips.new_effect(name or ("%s_to_%s" % (a, b)), type, ch, s0, length=d, input1=A, input2=B)
    if type == "WIPE":
        fx.transition_type = wipe_type
        fx.direction = direction
        fx.angle = math.radians(angle)
        fx.blur_width = blur
    _reg(state, name or ("%s_to_%s" % (a, b)), fx)
    if audio_crossfade:
        for nm, mode in ((a, "out"), (b, "in")):
            if nm + "_audio" in _store(state):
                au = _get(state, nm + "_audio")
                full = au.volume
                if mode == "out":
                    _key(au, "volume", s0, full)
                    _key(au, "volume", s0 + d, 0.0)
                else:
                    _key(au, "volume", s0, 0.0)
                    _key(au, "volume", s0 + d, full)
    _fit_frame_end(max(_end(A), _end(B)))
    return {"strip": fx.name, "channel": fx.channel, "start": s0, "frames": d}


def transform(state, target, scale=None, position=None, rotation=None, origin=None, keyframes=None, easing="LINEAR",
              flip_x=None, flip_y=None, filter=None):
    """Scale / move / rotate a strip (optionally animated).
    params: target, scale=None (1.0 or [sx,sy]; relative to fitted size), position=None ([x,y] pixels offset
      from centre), rotation=None (degrees), origin=None ([0..1,0..1], default centre), flip_x/flip_y,
      keyframes=[{"frame":N | "sec":S (from strip start), "scale":..,"position":[..],"rotation":..}, ...],
      easing="LINEAR"|"EASE"|"BEZIER".
    Ken Burns = two keyframes with different scale/position (or use op `ken_burns`)."""
    st = _get(state, target)
    t = st.transform

    def apply(sc_, pos, rot, frame=None):
        if sc_ is not None:
            sx, sy = (sc_, sc_) if isinstance(sc_, (int, float)) else (sc_[0], sc_[1])
            if frame is None:
                t.scale_x, t.scale_y = sx, sy
            else:
                _key(st, "transform.scale_x", frame, sx)
                _key(st, "transform.scale_y", frame, sy)
        if pos is not None:
            if frame is None:
                t.offset_x, t.offset_y = pos[0], pos[1]
            else:
                _key(st, "transform.offset_x", frame, pos[0])
                _key(st, "transform.offset_y", frame, pos[1])
        if rot is not None:
            if frame is None:
                t.rotation = math.radians(rot)
            else:
                _key(st, "transform.rotation", frame, math.radians(rot))

    if origin is not None:
        t.origin = (origin[0], origin[1])
    if flip_x is not None:
        st.use_flip_x = flip_x
    if flip_y is not None:
        st.use_flip_y = flip_y
    if filter:
        t.filter = filter
    apply(scale, position, rotation)
    for k in keyframes or []:
        fr = int(k["frame"]) if "frame" in k else int(st.left_handle) + _fr(k.get("sec", 0))
        apply(k.get("scale"), k.get("position"), k.get("rotation"), fr)
    if keyframes:
        _interp(st, easing)
    return {"strip": st.name, "keyframes": len(keyframes or [])}


def ken_burns(state, target, zoom_from=1.0, zoom_to=1.25, pan_from=(0, 0), pan_to=(0, 0), easing="EASE"):
    """Slow zoom / pan across the whole strip (documentary still-image or video move).
    params: target, zoom_from=1.0, zoom_to=1.25, pan_from=[0,0], pan_to=[0,0] (pixels), easing="EASE".
    Zoom >1 crops into the picture; keep pans modest to avoid black edges."""
    st = _get(state, target)
    return transform(state, target, keyframes=[
        {"frame": int(st.left_handle), "scale": zoom_from, "position": list(pan_from)},
        {"frame": int(st.right_handle) - 1, "scale": zoom_to, "position": list(pan_to)}], easing=easing)


def crop(state, target, left=0, right=0, top=0, bottom=0):
    """Crop a strip's source (pixels removed from each side).
    params: target, left=0, right=0, top=0, bottom=0."""
    st = _get(state, target)
    st.crop.min_x, st.crop.max_x, st.crop.min_y, st.crop.max_y = int(left), int(right), int(bottom), int(top)
    return {"strip": st.name}


def blend(state, target, blend_type=None, opacity=None, mute=None, lock=None, volume=None):
    """Blend mode / opacity (and mute/lock) of a strip.
    params: target, blend_type="REPLACE"|"CROSS"|"ADD"|"SUBTRACT"|"MULTIPLY"|"SCREEN"|"OVERLAY"|"SOFT_LIGHT"|
      "DARKEN"|"LIGHTEN"|"ALPHA_OVER"|"ALPHA_UNDER"|"DIFFERENCE"|..., opacity=0..1, mute, lock, volume (sound)."""
    st = _get(state, target)
    if blend_type:
        st.blend_type = blend_type
    if opacity is not None:
        st.blend_alpha = float(opacity)
    if mute is not None:
        st.mute = bool(mute)
    if lock is not None:
        st.lock = bool(lock)
    if volume is not None and st.type == "SOUND":
        st.volume = float(volume)
    return {"strip": st.name, "blend": st.blend_type, "opacity": st.blend_alpha}


def adjustment_layer(state, name="Adjust", start=None, duration=None, channel=None, opacity=1.0):
    """Adjustment strip: modifiers/effects added to it (color_grade / compositor_fx with target=name)
    affect everything beneath for its duration.
    params: name, start (default scene start), duration (s; default = whole timeline so far), channel=None (auto: top)."""
    ed = _ed()
    start = int(start if start is not None else _scene().frame_start)
    end = (start + _fr(duration)) if duration else max([s.right_handle for s in ed.strips_all] or [start + 30])
    ch = channel or _free_channel(start, end, first=max([s.channel for s in ed.strips_all] or [1]) + 1)
    st = ed.strips.new_effect(name, "ADJUSTMENT", ch, start, length=max(1, end - start))
    st.blend_alpha = opacity
    _reg(state, name, st)
    return {"strip": st.name, "channel": st.channel, "start": start, "end": end}


def color_grade(state, target, brightness=None, contrast=None, saturation=None, multiply=None, lift=None,
                gamma=None, gain=None, white_balance=None, curves=None, hue_shift=None, tonemap=None, mask=None,
                clear=False):
    """Color grading via non-destructive strip modifiers (works on movie/image/adjustment strips).
    params: target, brightness=None / contrast=None (BRIGHT_CONTRAST, -100..100), saturation=None
      (strip saturation 0..2, 1=neutral), multiply=None (strip color_multiply),
      lift/gamma/gain=None (COLOR_BALANCE, RGB lists around [1,1,1]; Lift-Gamma-Gain method),
      white_balance=None ([r,g,b] colour of a neutral grey, WHITE_BALANCE), curves=None
      ({"c":[[x,y],...],"r":..,"g":..,"b":..} points 0..1 -> CURVES modifier), hue_shift=None (reserved),
      tonemap=None ("RH_SIMPLE"|"RD_PHOTORECEPTOR"), clear=False (drop existing modifiers first).
    LUT files (.cube/.3dl): not supported by VSE modifiers in 5.2 -> use render_mp4(lut=path) (ffmpeg lut3d)."""
    st = _get(state, target)
    if clear:
        for m in list(st.modifiers):
            st.modifiers.remove(m)
    made = []
    if saturation is not None:
        st.color_saturation = float(saturation)
    if multiply is not None:
        st.color_multiply = float(multiply)
    if brightness is not None or contrast is not None:
        m = st.modifiers.new("BrightContrast", "BRIGHT_CONTRAST")
        m.bright = float(brightness or 0)
        m.contrast = float(contrast or 0)
        made.append(m.name)
    if any(v is not None for v in (lift, gamma, gain)):
        m = st.modifiers.new("ColorBalance", "COLOR_BALANCE")
        cb = m.color_balance
        cb.correction_method = "LIFT_GAMMA_GAIN"
        if lift is not None:
            cb.lift = lift
        if gamma is not None:
            cb.gamma = gamma
        if gain is not None:
            cb.gain = gain
        made.append(m.name)
    if white_balance is not None:
        m = st.modifiers.new("WhiteBalance", "WHITE_BALANCE")
        m.white_value = _col(white_balance)[:3]
        made.append(m.name)
    if curves:
        m = st.modifiers.new("Curves", "CURVES")
        cm = m.curve_mapping
        idx = {"c": 3, "r": 0, "g": 1, "b": 2}
        for k, pts in curves.items():
            cur = cm.curves[idx[k]]
            while len(cur.points) > 2:
                cur.points.remove(cur.points[1])
            cur.points[0].location = pts[0]
            cur.points[-1].location = pts[-1]
            for p in pts[1:-1]:
                cur.points.new(p[0], p[1])
        cm.update()
        made.append(m.name)
    if tonemap:
        m = st.modifiers.new("Tonemap", "TONEMAP")
        m.tonemap_type = tonemap
        made.append(m.name)
    return {"strip": st.name, "modifiers": made}


# ------------------------------------------------------------ compositor fx
def _build_fx_group(name, effects, width, height):
    ng = bpy.data.node_groups.new(name, "CompositorNodeTree")
    ng.interface.new_socket("Image", in_out="INPUT", socket_type="NodeSocketColor")
    ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    N, L = ng.nodes, ng.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    gi.location = (-300, 0)
    cur = gi.outputs[0]
    x = 0
    for e in effects:
        e = dict(e)
        t = e.pop("type")
        x += 300
        if t == "glare":
            n = N.new("CompositorNodeGlare")
            n.inputs["Type"].default_value = e.get("glare_type", "Fog Glow")
            n.inputs["Quality"].default_value = e.get("quality", "Medium")
            n.inputs["Threshold"].default_value = e.get("threshold", 0.8)
            n.inputs["Strength"].default_value = e.get("strength", 1.0)
            n.inputs["Size"].default_value = e.get("size", 0.5)
            if "Smoothness" in n.inputs:
                n.inputs["Smoothness"].default_value = e.get("smoothness", 0.5)
            L.new(cur, n.inputs["Image"])
            cur = n.outputs["Image"]
        elif t == "blur":
            n = N.new("CompositorNodeBlur")
            n.inputs["Type"].default_value = e.get("blur_type", "Gaussian")
            s = e.get("size", 10)
            n.inputs["Size"].default_value = (s, s) if isinstance(s, (int, float)) else (s[0], s[1])
            L.new(cur, n.inputs["Image"])
            cur = n.outputs["Image"]
        elif t == "lens_distortion":
            n = N.new("CompositorNodeLensdist")
            n.inputs["Distortion"].default_value = e.get("distortion", 0.1)
            n.inputs["Dispersion"].default_value = e.get("dispersion", 0.05)
            n.inputs["Jitter"].default_value = False
            n.inputs["Fit"].default_value = True
            L.new(cur, n.inputs["Image"])
            cur = n.outputs["Image"]
        elif t == "chroma_key":
            n = N.new("CompositorNodeKeying")
            n.inputs["Key Color"].default_value = _col(e.get("key_color", "#00FF00"))
            n.inputs["Black Level"].default_value = e.get("black", 0.1)
            n.inputs["White Level"].default_value = e.get("white", 0.9)
            n.inputs["Balance"].default_value = e.get("balance", 0.5)
            n.inputs["Tolerance"].default_value = e.get("tolerance", 0.1)
            n.inputs["Feather Size"].default_value = e.get("feather", 2)
            n.inputs["Dilate Size"].default_value = e.get("dilate", 0)
            L.new(cur, n.inputs["Image"])
            cur = n.outputs["Image"]
        elif t == "vignette":
            m = N.new("CompositorNodeEllipseMask")
            m.inputs["Operation"].default_value = "Add"
            m.inputs["Position"].default_value = (0.5, 0.5)
            sz = e.get("size", 0.9)
            m.inputs["Size"].default_value = (sz, sz * 0.9)
            m.location = (x, -300)
            b = N.new("CompositorNodeBlur")
            b.inputs["Type"].default_value = "Gaussian"
            bs = e.get("softness", 0.5) * max(width, height) * 0.25
            b.inputs["Size"].default_value = (bs, bs)
            b.location = (x + 200, -300)
            L.new(m.outputs["Mask"], b.inputs["Image"])
            mx = N.new("ShaderNodeMix")
            mx.data_type = "RGBA"
            mx.blend_type = "MULTIPLY"
            mx.inputs[0].default_value = e.get("strength", 1.0)
            # sockets: [0]=factor float, [6]=A rgba, [7]=B rgba
            L.new(cur, mx.inputs[6])
            L.new(b.outputs["Image"], mx.inputs[7])
            cur = [o for o in mx.outputs if o.type == "RGBA"][0]
        elif t == "brightness":
            n = N.new("CompositorNodeBrightContrast")
            n.inputs["Bright"].default_value = e.get("bright", 0.0)
            n.inputs["Contrast"].default_value = e.get("contrast", 0.0)
            L.new(cur, n.inputs["Image"])
            cur = n.outputs["Image"]
        elif t == "pixelate":
            n = N.new("CompositorNodePixelate")
            L.new(cur, n.inputs[0])
            cur = n.outputs[0]
        elif t == "posterize":
            n = N.new("CompositorNodePosterize")
            L.new(cur, n.inputs[0])
            if "Steps" in n.inputs:
                n.inputs["Steps"].default_value = e.get("steps", 6)
            cur = n.outputs[0]
        else:
            raise ValueError("unknown compositor fx %r (glare, blur, lens_distortion, chroma_key, vignette, brightness, pixelate, posterize)" % t)
        n_loc = x
    go.location = (x + 300, 0)
    L.new(cur, go.inputs[0])
    return ng


def compositor_fx(state, target, effects, name="CompFX"):
    """Attach compositor effects to a strip as a Compositor strip-modifier (non-destructive).
    params: target (strip; use an adjustment layer to affect many clips), name,
      effects = ordered list of dicts with "type":
        glare       {glare_type:"Fog Glow"|"Bloom"|"Streaks"|"Ghosts"|"Simple Star"|"Sun Beams", threshold:0.8, strength:1, size:0.5, quality}
        blur        {size:10 | [x,y], blur_type:"Gaussian"|"Flat"|"Tent"|...}
        lens_distortion {distortion:0.1, dispersion:0.05}   (chromatic aberration look)
        chroma_key  {key_color:"#00FF00", black:0.1, white:0.9, balance:0.5, tolerance:0.1, feather:2, dilate:0}
                    -> green screen; the keyed strip gets alpha, put a background on a lower channel
        vignette    {size:0.9, softness:0.5, strength:1.0}
        brightness  {bright, contrast}   pixelate   posterize {steps}
    Registers nothing new; returns modifier name."""
    st = _get(state, target)
    sc = _scene()
    ng = _build_fx_group("%s_%s" % (name, st.name), effects, sc.render.resolution_x, sc.render.resolution_y)
    m = st.modifiers.new(name, "COMPOSITOR")
    m.node_group = ng
    if any(e["type"] == "chroma_key" for e in effects):
        st.blend_type = "ALPHA_OVER"
    return {"strip": st.name, "modifier": m.name, "node_group": ng.name}


def scene_strip(state, scene_name, name=None, start=None, duration=None, channel=None, camera=None,
                use_sequencer=False):
    """Put another Blender scene (3D shot, Grease Pencil drawing scene) into the edit as a strip.
    params: scene_name, name, start (frame), duration (s; default scene's frame range), channel=None,
      camera=None (camera object name to render through), use_sequencer=False (render the scene's own VSE).
    The strip renders the scene with its own engine/camera at strip time (frame_start..frame_end of that scene)."""
    ed = _ed()
    sc = bpy.data.scenes[scene_name]
    n = _fr(duration) if duration else max(1, sc.frame_end - sc.frame_start + 1)
    start = int(start if start is not None else max([s.right_handle for s in ed.strips_all] or [_scene().frame_start]))
    ch = channel or _free_channel(start, start + n, first=2)
    key = name or scene_name
    st = ed.strips.new_scene(key, sc, ch, start)
    st.right_handle = start + n
    if camera:
        st.scene_camera = bpy.data.objects[camera]
    try:
        st.scene_input = "SEQUENCER" if use_sequencer else "CAMERA"
    except Exception:
        pass
    _reg(state, key, st)
    _fit_frame_end(_end(st))
    return {"strip": st.name, "start": st.left_handle, "end": st.right_handle}


def video_as_texture(state, filepath, name="VideoPlane", size=(16, 9), location=(0, 0, 0), emission=1.0,
                     frame_offset=0, loop=True, auto_refresh=True, frames=None, rotation=(90, 0, 0), alpha=False):
    """Create a 3D plane that plays a movie as its texture (screens, billboards, TV props).
    params: filepath, name="VideoPlane", size=[w,h] (plane size, scene units), location=[x,y,z],
      rotation=[90,0,0] deg (default stands the plane up facing -Y), emission=1.0 (self-lit strength),
      frame_offset=0, loop=True, auto_refresh=True, frames=None (frames to play; default = all),
      alpha=False (use movie alpha). Registers state['objects'][name].
    Combine with scene_strip to put the 3D shot in the VSE timeline."""
    img = bpy.data.images.load(_path(filepath, state), check_existing=True)
    img.source = "MOVIE"
    mesh = bpy.data.meshes.new(name)
    w, h = size[0] / 2.0, size[1] / 2.0
    mesh.from_pydata([(-w, -h, 0), (w, -h, 0), (w, h, 0), (-w, h, 0)], [], [(0, 1, 2, 3)])
    uv = mesh.uv_layers.new(name="UVMap")
    for lp, co in zip(mesh.loops, [(0, 0), (1, 0), (1, 1), (0, 1)]):
        uv.data[lp.index].uv = co
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    obj.rotation_euler = [math.radians(r) for r in rotation]
    _scene().collection.objects.link(obj)
    mat = bpy.data.materials.new(name + "_mat")
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.image_user.use_auto_refresh = auto_refresh
    tex.image_user.use_cyclic = loop
    tex.image_user.frame_offset = frame_offset
    tex.image_user.frame_duration = frames or img.frame_duration or 1
    tex.image_user.frame_start = 1
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = emission
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    if alpha:
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(tex.outputs["Alpha"], mix.inputs[0])
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs["Surface"])
    else:
        nt.links.new(em.outputs[0], out.inputs["Surface"])
    obj.data.materials.append(mat)
    state.setdefault("objects", {})[name] = obj
    return {"object": obj.name, "image": img.name, "frames": img.frame_duration}


def duck(state, music, voice, duck_to=0.25, attack=0.3, release=0.5, pad=0.2):
    """Auto-duck music volume under a voice/dialogue strip using volume keyframes.
    params: music (sound strip), voice (sound strip or video strip name; its _audio is used), duck_to=0.25
      (relative level while voice plays), attack=0.3 s, release=0.5 s, pad=0.2 s."""
    m = _get(state, music)
    v = voice + "_audio" if voice + "_audio" in _store(state) else voice
    V = _get(state, v)
    full = m.volume
    a, b = int(V.left_handle), int(V.right_handle)
    at, rl, pd = _fr(attack), _fr(release), _fr(pad)
    for f, val in ((a - pd - at, full), (a - pd, full * duck_to), (b + pd, full * duck_to), (b + pd + rl, full)):
        _key(m, "volume", max(int(m.left_handle), f), val)
    return {"strip": m.name}


# ---------------------------------------------------------------- render
def render_mp4(state, filepath, quality="HIGH", preset="GOOD", fps=None, start=None, end=None, audio=True,
               audio_bitrate=192, mixrate=48000, gop=None, lut=None, crf=None, still_frame=None, container="MPEG4",
               codec="H264", denoise=False, overwrite=True):
    """Render the VSE timeline to MP4 (H.264 + AAC), optionally a single PNG.
    params: filepath (required, .mp4), quality="HIGH"|"MEDIUM"|"LOW"|"PERC_LOSSLESS"|"LOSSLESS"|"VERYLOW"|
      "LOWEST"|"CUSTOM" (ffmpeg constant_rate_factor), crf=None (int; sets CUSTOM), preset="GOOD"|"BEST"|"REALTIME"
      (encoder speed), start/end=None (frames; default = scene range, auto-fitted to the strips),
      audio=True (AAC), audio_bitrate=192 kbps, mixrate=48000, gop=None (keyframe interval),
      lut=None (.cube/.3dl path applied after render with ffmpeg lut3d), codec="H264"|"H265"|"AV1",
      still_frame=None (render only this frame to PNG at filepath),
      container="MPEG4"|"MKV"|"QUICKTIME"|"WEBM".
    Proxies are never used; compositing is disabled unless the scene has its own node tree."""
    sc = _scene()
    ed = _ed()
    sc.render.use_sequencer = True
    ends = [int(s.right_handle) for s in ed.strips_all]
    sc.frame_start = int(start if start is not None else sc.frame_start)
    sc.frame_end = int(end if end is not None else (max(ends) - 1 if ends else sc.frame_end))
    if fps:
        sc.render.fps = int(fps)
        sc.render.fps_base = 1.0
    for s in ed.strips_all:
        try:
            s.use_proxy = False
        except Exception:
            pass
    out = os.path.abspath(filepath)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    ims = sc.render.image_settings
    if still_frame is not None:
        ims.media_type = "IMAGE"
        ims.file_format = "PNG"
        sc.render.filepath = out
        sc.frame_set(int(still_frame))
        bpy.ops.render.render(write_still=True)
        return {"filepath": out, "frame": still_frame}
    ims.media_type = "VIDEO"
    ims.file_format = "FFMPEG"
    ff = sc.render.ffmpeg
    ff.format = container
    ff.codec = codec
    if crf is not None:
        ff.constant_rate_factor = "CUSTOM"
        ff.custom_constant_rate_factor = int(crf)
    else:
        ff.constant_rate_factor = quality
    ff.ffmpeg_preset = preset
    if gop:
        ff.gopsize = int(gop)
    if audio:
        ff.audio_codec = "AAC" if container != "WEBM" else "OPUS"
        ff.audio_bitrate = int(audio_bitrate)
        ff.audio_mixrate = int(mixrate)
        ff.audio_channels = "STEREO"
    else:
        ff.audio_codec = "NONE"
    ims.color_mode = "RGB"
    final = out
    if lut:
        out = os.path.splitext(out)[0] + "_prelut" + os.path.splitext(out)[1]
    sc.render.filepath = out
    bpy.ops.render.render(animation=True)
    res = {"filepath": final, "frames": [sc.frame_start, sc.frame_end], "fps": _fps()}
    if lut:
        import subprocess
        lp = _path(lut, state).replace("\\", "/").replace(":", r"\:")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", out, "-vf", "lut3d='%s'" % lp, "-c:v", "libx264",
                        "-crf", "16", "-c:a", "copy", final], check=True)
        os.remove(out)
    return res


def vse_from_edl(state, clips, resolution=None, fps=None, music=None, music_volume=0.3, titles=None,
                 transition_default=None, transition_duration=0.5, fit="FIT", clear=True, duck_music=False,
                 fade_in=0.0, fade_out=0.0, end_card=None, grade=None):
    """Build a complete timeline in one shot from a clip list (an EDL).
    params:
      clips = [{"file": path, "in": sec (source start, default 0), "out": sec (source end, default clip end),
                "transition": None|"CROSS"|"GAMMA_CROSS"|"WIPE" (into THIS clip from the previous one),
                "transition_duration": s, "volume": 1.0, "speed": None, "text": None (caption for the clip),
                "text_opts": {add_text params}, "name": None, "kenburns": [zoom_from, zoom_to] (stills/video),
                "image": bool (force still; duration = out-in or 3 s), "mute": False}]
      resolution=None (default: first clip), fps=None (default: first clip), music={"file":..,"volume":0.3,
      "fade_in":1,"fade_out":2} or just a path, titles=[{"text":..,"start_sec":..,"duration":..,+add_text params}],
      transition_default=None (applied to clips without own "transition" except the first),
      transition_duration=0.5, fit="FIT", clear=True, duck_music=False, fade_in/fade_out=0 (s, whole edit
      fade from/to black), end_card=None ({"text":..,"duration":..,"color":..,"background":..}),
      grade=None (color_grade params applied through an adjustment layer over everything).
    Channel layout: audio 1-2, video 3-4 (alternating so transitions can overlap), effects/transitions 5,
    titles/captions 6+, music on channel 8-ish (auto)."""
    first = clips[0]["file"]
    vse_setup(state, resolution=resolution, fps=fps, from_clip=first if not clips[0].get("image") else None, clear=clear)
    pos = _scene().frame_start
    prev = None
    names = []
    for i, c in enumerate(clips):
        key = c.get("name") or "clip%02d" % (i + 1)
        vch, ach = (3, 1) if i % 2 == 0 else (4, 2)
        tr = c.get("transition") or (transition_default if i > 0 else None)
        td = _fr(c.get("transition_duration", transition_duration))
        start = pos
        if prev and tr:
            start = pos - td
        fp = _path(c["file"], state)
        ext = os.path.splitext(fp)[1].lower()
        if c.get("image") or ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"):
            dur = (c.get("out", 0) - c.get("in", 0)) or 3.0
            r = add_image(state, fp, name=key, start=start, duration=dur, channel=vch, fit=fit)
        else:
            r = add_movie(state, fp, name=key, start=start, trim_in=c.get("in", 0.0), trim_out=c.get("out"),
                          channel=vch, audio_channel=ach, fit=fit, volume=0.0 if c.get("mute") else c.get("volume", 1.0))
        if c.get("speed"):
            set_speed(state, key, c["speed"])
            r["end"] = _get(state, key + "_speed").right_handle
        if c.get("kenburns"):
            ken_burns(state, key, *c["kenburns"])
        st = _get(state, key)
        if prev and tr:
            tname = "%s_to_%s" % (prev, key)
            ch = 5
            ed = _ed()
            A = _get(state, prev)
            fx = ed.strips.new_effect(tname, tr, ch, int(st.left_handle), length=td, input1=A, input2=st)
            if tr == "WIPE":
                fx.transition_type = c.get("wipe_type", "SINGLE")
                fx.blur_width = 0.1
            _reg(state, tname, fx)
            for nm, mode in ((prev, "out"), (key, "in")):
                if nm + "_audio" in _store(state):
                    au = _get(state, nm + "_audio")
                    full = au.volume
                    s0 = int(st.left_handle)
                    if mode == "out":
                        _key(au, "volume", s0, full)
                        _key(au, "volume", s0 + td, 0.0)
                    else:
                        _key(au, "volume", s0, 0.0)
                        _key(au, "volume", s0 + td, full)
        if c.get("text"):
            o = dict(c.get("text_opts") or {})
            o.setdefault("start", int(st.left_handle) + (td if prev and tr else 0))
            o.setdefault("duration", (st.right_handle - o["start"]) / _fps())
            o.setdefault("fade_in", 0.3)
            o.setdefault("fade_out", 0.3)
            add_text(state, c["text"], name=key + "_text", **o)
        pos = int(st.right_handle)
        if c.get("speed"):
            pos = int(_get(state, key + "_speed").right_handle)
        prev = key
        names.append(key)
    total_end = pos
    if end_card:
        ec = dict(end_card)
        dur = ec.pop("duration", 3.0)
        add_color(state, ec.pop("background", "#000000"), "end_card_bg", start=pos, duration=dur, channel=3)
        add_text(state, ec.pop("text", ""), name="end_card_text", start=pos, duration=dur, position=ec.pop("position", (0.5, 0.5)),
                 anchor_y="CENTER", fade_in=0.5, **ec)
        total_end = pos + _fr(dur)
    for t in titles or []:
        t = dict(t)
        if "start_sec" in t:
            t["start"] = _scene().frame_start + _fr(t.pop("start_sec"))
        add_text(state, t.pop("text"), **t)
    if music:
        m = {"file": music} if isinstance(music, str) else dict(music)
        mr = add_audio(state, m["file"], name="music", start=_scene().frame_start, volume=m.get("volume", music_volume),
                       duration=(total_end - _scene().frame_start) / _fps(), fade_in=m.get("fade_in", 1.0),
                       fade_out=m.get("fade_out", 2.0), channel=m.get("channel", 7))
        if duck_music:
            for nm in names:
                if nm + "_audio" in _store(state):
                    duck(state, "music", nm)
    if grade:
        adjustment_layer(state, "Grade", start=_scene().frame_start, duration=(total_end - _scene().frame_start) / _fps())
        color_grade(state, "Grade", **grade)
    if fade_in or fade_out:
        bg = add_color(state, "#000000", "fade_plate", start=_scene().frame_start, duration=(total_end - _scene().frame_start) / _fps(), channel=2)
        # a black plate below video fades the picture in/out via the top-level adjustment of opacity
        pl = _get(state, "fade_plate")
        pl.channel = max(s.channel for s in _ed().strips_all) + 1
        pl.blend_type = "ALPHA_OVER"
        fb = _fr(fade_in)
        fo = _fr(fade_out)
        a, b = int(pl.left_handle), int(pl.right_handle)
        pts = [(a, 1.0 if fb else 0.0)]
        if fb:
            pts.append((a + fb, 0.0))
        if fo:
            pts += [(b - fo, 0.0), (b, 1.0)]
        for f, v in pts:
            _key(pl, "blend_alpha", f, v)
        _interp(pl, "LINEAR")
    _scene().frame_end = int(total_end - 1)
    return {"clips": names, "duration_sec": (total_end - _scene().frame_start) / _fps(), "frame_end": _scene().frame_end}


def vse_list(state):
    """List all strips (name, type, channel, start, end) - handy for debugging recipes."""
    return {"strips": [{"name": s.name, "type": s.type, "channel": s.channel, "start": s.left_handle, "end": s.right_handle}
                       for s in sorted(_ed().strips_all, key=lambda s: (s.channel, s.left_handle))]}


OPS = {
    "vse_setup": vse_setup,
    "add_movie": add_movie,
    "add_image": add_image,
    "add_image_sequence": add_image_sequence,
    "add_color": add_color,
    "add_text": add_text,
    "add_audio": add_audio,
    "fade": fade,
    "cut": cut,
    "move": move,
    "trim": trim,
    "set_speed": set_speed,
    "transition": transition,
    "transform": transform,
    "ken_burns": ken_burns,
    "crop": crop,
    "blend": blend,
    "adjustment_layer": adjustment_layer,
    "color_grade": color_grade,
    "compositor_fx": compositor_fx,
    "scene_strip": scene_strip,
    "video_as_texture": video_as_texture,
    "duck": duck,
    "render_mp4": render_mp4,
    "vse_from_edl": vse_from_edl,
    "vse_list": vse_list,
}
