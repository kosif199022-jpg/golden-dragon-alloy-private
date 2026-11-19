"""Scene setup: resolution/fps/frames, units, color management, world
(color, studio gradient, HDRI, physical sky), fog/volumes."""
import math
import os

import bpy

from . import util
from .util import log, warn


# --------------------------------------------------------------------------- engine helpers
def engine_id(name):
    """Map friendly engine names to the identifier accepted by this Blender build.
    Blender 4.2-4.x used 'BLENDER_EEVEE_NEXT'; 5.x uses 'BLENDER_EEVEE'."""
    name = (name or "CYCLES").upper()
    if name in ("EEVEE", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        cands = ["BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"]
    elif name in ("WORKBENCH", "BLENDER_WORKBENCH"):
        cands = ["BLENDER_WORKBENCH"]
    else:
        cands = [name]
    sc = bpy.context.scene
    old = sc.render.engine
    for c in cands:
        try:
            sc.render.engine = c
            sc.render.engine = old
            return c
        except TypeError:
            continue
    raise ValueError(f"render engine '{name}' not available")


def clear_scene(state=None, keep=None):
    """Delete all objects (except names in keep) and purge orphan data."""
    keep = set(keep or [])
    for o in list(bpy.data.objects):
        if o.name not in keep:
            bpy.data.objects.remove(o, do_unlink=True)
    for coll in list(bpy.data.collections):
        if not coll.objects and not coll.children:
            bpy.data.collections.remove(coll)
    util.purge_orphans()
    if state is not None:
        state["objects"] = {k: v for k, v in state.get("objects", {}).items() if k in keep}
    return {"cleared": True}


# --------------------------------------------------------------------------- setup
def scene_setup(state, resolution=None, fps=None, frame_start=None, frame_end=None, duration=None,
                engine=None, samples=None, color=None, world=None, units=None,
                resolution_percentage=None, pixel_aspect=None, background=None, **extra):
    """Configure render size, timing, engine, samples, color management and world.

    resolution: [w, h] or preset "1080p" | "4k" | "square" | "vertical" (1080x1920) | "720p".
    duration: seconds (sets frame_end = frame_start + duration*fps - 1).
    color: {view_transform: "AgX"|"Filmic"|"Standard"|"Khronos PBR Neutral", look: "Punchy"|"High Contrast"|...,
            exposure, gamma}
    world: dict forwarded to world op (see world()).
    """
    sc = bpy.context.scene
    presets = {"1080p": (1920, 1080), "720p": (1280, 720), "4k": (3840, 2160), "square": (1080, 1080),
               "vertical": (1080, 1920), "reel": (1080, 1920), "portrait": (1080, 1350)}
    if resolution is not None:
        w, h = presets[resolution] if isinstance(resolution, str) else resolution
        sc.render.resolution_x, sc.render.resolution_y = int(w), int(h)
    if resolution_percentage:
        sc.render.resolution_percentage = int(resolution_percentage)
    if pixel_aspect:
        sc.render.pixel_aspect_x = pixel_aspect
    if fps:
        f = float(fps)
        if abs(f - round(f)) > 1e-3:  # 23.976, 29.97
            sc.render.fps = int(math.ceil(f))
            sc.render.fps_base = math.ceil(f) / f
        else:
            sc.render.fps, sc.render.fps_base = int(f), 1.0
    if frame_start is not None:
        sc.frame_start = int(frame_start)
    if duration is not None:
        sc.frame_end = sc.frame_start + int(round(float(duration) * sc.render.fps / sc.render.fps_base)) - 1
    if frame_end is not None:
        sc.frame_end = int(frame_end)
    sc.frame_set(sc.frame_start)
    if engine or samples:
        from . import render as _render
        _render.render_settings(state, engine=engine, samples=samples)
    color_management(state, **(color or {"view_transform": "AgX"}))
    if units:
        set_units(state, **(units if isinstance(units, dict) else {"system": units}))
    if world is not None:
        world_op(state, **world)
    elif background is not None:
        world_color(state, color=background)
    if extra:
        warn(f"scene_setup ignored unknown keys: {sorted(extra)}")
    return {"resolution": [sc.render.resolution_x, sc.render.resolution_y], "fps": sc.render.fps,
            "frames": [sc.frame_start, sc.frame_end], "engine": sc.render.engine}


def color_management(state, view_transform="AgX", look=None, exposure=None, gamma=None,
                     display_device=None, **_):
    """Set view transform/look. look accepts short names ('Punchy') or full ('AgX - Punchy')."""
    vs = bpy.context.scene.view_settings
    if display_device:
        bpy.context.scene.display_settings.display_device = display_device
    try:
        vs.view_transform = view_transform
    except TypeError:
        warn(f"view transform '{view_transform}' unavailable, keeping {vs.view_transform}")
    if look:
        tried = [look, f"{vs.view_transform} - {look}", f"AgX - {look}"]
        for l in tried:
            try:
                vs.look = l
                break
            except TypeError:
                continue
        else:
            warn(f"look '{look}' not available for {vs.view_transform}")
    elif look is None:
        try:
            vs.look = "None"
        except TypeError:
            pass
    if exposure is not None:
        vs.exposure = float(exposure)
    if gamma is not None:
        vs.gamma = float(gamma)
    return {"view_transform": vs.view_transform, "look": vs.look}


def set_units(state, system="METRIC", scale=1.0, length="METERS", **_):
    us = bpy.context.scene.unit_settings
    us.system = system.upper()
    us.scale_length = float(scale)
    if us.system != "NONE":
        try:
            us.length_unit = length.upper()
        except TypeError:
            warn(f"length unit {length} not valid for {system}")
    return {"system": us.system}


# --------------------------------------------------------------------------- world
def _world(reset=True):
    sc = bpy.context.scene
    w = sc.world
    if w is None:
        w = bpy.data.worlds.new("World")
        sc.world = w
    if hasattr(w, "use_nodes") and not w.use_nodes:
        w.use_nodes = True  # deprecated in 5.x (always node based) but harmless
    nt = w.node_tree
    if reset:
        nt.nodes.clear()
    return w, nt


def _world_output(nt):
    out = nt.nodes.new("ShaderNodeOutputWorld")
    out.location = (600, 0)
    return out


def world_color(state, color="#0b0b0f", strength=1.0, **_):
    """Uniform world color (also the ambient light)."""
    w, nt = _world()
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value = util.color(color)
    bg.inputs["Strength"].default_value = float(strength)
    nt.links.new(bg.outputs[0], _world_output(nt).inputs["Surface"])
    return {"world": "color"}


def world_gradient(state, top="#1a1d24", bottom="#050507", strength=1.0, light_color=None,
                   light_strength=None, **_):
    """Vertical studio gradient seen by the camera; lighting uses light_color (default: mean)."""
    w, nt = _world()
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = -0.3
    mr.inputs["From Max"].default_value = 0.6
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = util.color(bottom)
    ramp.color_ramp.elements[1].color = util.color(top)
    bg_cam = nt.nodes.new("ShaderNodeBackground")
    bg_cam.inputs["Strength"].default_value = float(strength)
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    nt.links.new(mr.outputs[0], ramp.inputs[0])
    nt.links.new(ramp.outputs[0], bg_cam.inputs["Color"])
    bg_light = nt.nodes.new("ShaderNodeBackground")
    lc = util.color(light_color) if light_color else tuple((a + b) / 2 for a, b in zip(util.color(top), util.color(bottom)))
    bg_light.inputs["Color"].default_value = lc
    bg_light.inputs["Strength"].default_value = float(light_strength if light_strength is not None else strength)
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
    nt.links.new(bg_light.outputs[0], mix.inputs[1])
    nt.links.new(bg_cam.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], _world_output(nt).inputs["Surface"])
    return {"world": "gradient"}


def world_hdri(state, path, strength=1.0, rotation=0.0, background=True, background_color="#000000",
               background_strength=1.0, **_):
    """Image based lighting from an .hdr/.exr. background=False hides the HDRI from camera
    (replaced by background_color) but keeps the lighting/reflections."""
    p = util.resolve_path(state, path)
    w, nt = _world()
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value[2] = math.radians(float(rotation))
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(p, check_existing=True)
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
    nt.links.new(mp.outputs[0], env.inputs["Vector"])
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = float(strength)
    nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    final = bg
    if not background or background_strength != 1.0:
        lp = nt.nodes.new("ShaderNodeLightPath")
        bg2 = nt.nodes.new("ShaderNodeBackground")
        bg2.inputs["Strength"].default_value = float(background_strength)
        if not background:
            bg2.inputs["Color"].default_value = util.color(background_color)
        else:  # visible HDRI at a different brightness than its lighting
            nt.links.new(env.outputs["Color"], bg2.inputs["Color"])
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
        nt.links.new(bg.outputs[0], mix.inputs[1])
        nt.links.new(bg2.outputs[0], mix.inputs[2])
        final = mix
    nt.links.new(final.outputs[0], _world_output(nt).inputs["Surface"])
    return {"world": "hdri", "path": p}


def world_sky(state, sun_elevation=15.0, sun_rotation=0.0, altitude=0.0, air=1.0, aerosol=1.0, ozone=1.0,
              strength=1.0, sun_disc=True, sun_size=0.545, sun_intensity=1.0, sky_type="MULTIPLE_SCATTERING",
              add_sun_light=False, sun_light_strength=3.0, **_):
    """Physical sky (Nishita successor). sky_type: MULTIPLE_SCATTERING | SINGLE_SCATTERING | PREETHAM |
    HOSEK_WILKIE ('NISHITA' maps to MULTIPLE_SCATTERING). Angles in degrees."""
    w, nt = _world()
    sky = nt.nodes.new("ShaderNodeTexSky")
    items = [e.identifier for e in sky.bl_rna.properties["sky_type"].enum_items]
    st = sky_type.upper()
    if st == "NISHITA":
        st = "MULTIPLE_SCATTERING" if "MULTIPLE_SCATTERING" in items else "NISHITA"
    if st not in items:
        warn(f"sky_type {st} not in {items}; using {items[0]}")
        st = items[0]
    sky.sky_type = st
    for prop, val in (("sun_elevation", math.radians(sun_elevation)), ("sun_rotation", math.radians(sun_rotation)),
                      ("altitude", altitude), ("air_density", air), ("aerosol_density", aerosol),
                      ("dust_density", aerosol), ("ozone_density", ozone), ("sun_disc", sun_disc),
                      ("sun_size", math.radians(sun_size)), ("sun_intensity", sun_intensity)):
        if hasattr(sky, prop):
            setattr(sky, prop, val)
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = float(strength)
    nt.links.new(sky.outputs[0], bg.inputs["Color"])
    nt.links.new(bg.outputs[0], _world_output(nt).inputs["Surface"])
    if add_sun_light:
        from . import lights
        el, rot = math.radians(sun_elevation), math.radians(sun_rotation)
        lights.light(state, type="SUN", name="SkySun", energy=sun_light_strength,
                     rotation=[90 - sun_elevation, 0, sun_rotation + 90], angle=sun_size)
    return {"world": "sky", "sky_type": st}


def world_op(state, type=None, **params):
    """Dispatch: {"type": "color"|"gradient"|"hdri"|"sky", ...}. Type inferred if omitted."""
    t = (type or ("hdri" if "path" in params else "gradient" if "top" in params else
                  "sky" if "sun_elevation" in params else "color")).lower()
    fns = {"color": world_color, "gradient": world_gradient, "hdri": world_hdri, "sky": world_sky}
    if t not in fns:
        raise ValueError(f"world type '{t}' must be one of {list(fns)}")
    vol = params.pop("fog", None)
    res = fns[t](state, **params)
    if vol:
        fog(state, **(vol if isinstance(vol, dict) else {"density": float(vol)}))
    return res


def fog(state, density=0.02, color="#ffffff", anisotropy=0.3, mode="world", size=None, name="Fog",
        emission=0.0, **_):
    """Atmospheric volume. mode='world' (whole world, simple) or 'box' (a volume cube around the
    scene - required for crisp god rays; size defaults to scene bounds * 2.5)."""
    if mode == "world":
        w = bpy.context.scene.world or _world(reset=False)[0]
        if bpy.context.scene.world is None:
            world_color(state)
            w = bpy.context.scene.world
        nt = w.node_tree
        out = next((n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputWorld"), None) or _world_output(nt)
        vol = nt.nodes.new("ShaderNodeVolumePrincipled")
        vol.inputs["Density"].default_value = float(density)
        vol.inputs["Color"].default_value = util.color(color)
        vol.inputs["Anisotropy"].default_value = float(anisotropy)
        nt.links.new(vol.outputs[0], out.inputs["Volume"])
        return {"fog": "world"}
    mn, mx = util.world_bbox(util.renderable_objects())
    center = (mn + mx) / 2
    ext = max((mx - mn).length, 4.0) * 1.25
    sz = util.vec3(size) if size is not None else util.vec3([ext, ext, ext])
    me = bpy.data.meshes.new(name)
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(me)
    bm.free()
    obj = util.new_object(name, me)
    obj.location = center
    obj.scale = sz
    obj["blpro_backdrop"] = True  # exclude from auto-framing
    mat = bpy.data.materials.new(name + "_vol")
    nt = mat.node_tree
    nt.nodes.clear()
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Density"].default_value = float(density)
    vol.inputs["Color"].default_value = util.color(color)
    vol.inputs["Anisotropy"].default_value = float(anisotropy)
    if emission:
        vol.inputs["Emission Strength"].default_value = float(emission)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    obj.data.materials.append(mat)
    obj.visible_shadow = False
    util.register(state, obj, name)
    return {"fog": "box", "object": obj.name}


def set_frame(state, frame, **_):
    bpy.context.scene.frame_set(int(frame))
    return {"frame": int(frame)}


def set_var(state, **values):
    """Store arbitrary values in state['vars'] (for exec scripts / later ops)."""
    state.setdefault("vars", {}).update(values)
    return dict(values)


OPS = {
    "scene_setup": scene_setup,
    "clear_scene": clear_scene,
    "color_management": color_management,
    "units": set_units,
    "world": world_op,
    "world_color": world_color,
    "world_gradient": world_gradient,
    "world_hdri": world_hdri,
    "world_sky": world_sky,
    "fog": fog,
    "set_frame": set_frame,
    "set_var": set_var,
}
