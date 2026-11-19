"""Materials: Principled BSDF presets (metals, glass, plastics, car paint, fabric, neon...),
procedural noise/marble/wood, image and video textures, custom node graphs.

Every material made here multiplies its alpha by Object Info > Alpha, so any object can be
faded by animating its object color alpha (see animate.fade)."""
import os

import bpy

from . import util
from .util import warn

# name -> Principled input overrides (+ optional "_kind" for procedural builders)
PRESETS = {
    "gold":          {"Base Color": "#f7c86b", "Metallic": 1.0, "Roughness": 0.16},
    "gold_brushed":  {"Base Color": "#f2c063", "Metallic": 1.0, "Roughness": 0.32, "Anisotropic": 0.7},
    "rose_gold":     {"Base Color": "#f0b39a", "Metallic": 1.0, "Roughness": 0.2},
    "silver":        {"Base Color": "#f2f2f2", "Metallic": 1.0, "Roughness": 0.12},
    "chrome":        {"Base Color": "#f6f6f6", "Metallic": 1.0, "Roughness": 0.03},
    "brushed_metal": {"Base Color": "#c9ccd1", "Metallic": 1.0, "Roughness": 0.3, "Anisotropic": 0.8},
    "aluminum":      {"Base Color": "#d6d9dd", "Metallic": 1.0, "Roughness": 0.22},
    "copper":        {"Base Color": "#f0a37f", "Metallic": 1.0, "Roughness": 0.2},
    "black_metal":   {"Base Color": "#1a1a1c", "Metallic": 1.0, "Roughness": 0.25},
    "glass":         {"Base Color": "#ffffff", "Roughness": 0.0, "IOR": 1.45, "Transmission Weight": 1.0},
    "frosted_glass": {"Base Color": "#ffffff", "Roughness": 0.28, "IOR": 1.45, "Transmission Weight": 1.0},
    "tinted_glass":  {"Base Color": "#7fb8ff", "Roughness": 0.02, "IOR": 1.5, "Transmission Weight": 1.0},
    "diamond":       {"Base Color": "#ffffff", "Roughness": 0.0, "IOR": 2.42, "Transmission Weight": 1.0},
    "water":         {"Base Color": "#e8f6ff", "Roughness": 0.02, "IOR": 1.333, "Transmission Weight": 1.0},
    "plastic":       {"Base Color": "#e8e8e8", "Roughness": 0.35},
    "glossy_plastic": {"Base Color": "#e8e8e8", "Roughness": 0.12, "Coat Weight": 0.6, "Coat Roughness": 0.05},
    "rubber":        {"Base Color": "#1d1d1f", "Roughness": 0.85},
    "matte":         {"Base Color": "#bfbfbf", "Roughness": 0.9, "Specular IOR Level": 0.3},
    "clay":          {"Base Color": "#d8cfc4", "Roughness": 0.85, "Specular IOR Level": 0.25},
    "ceramic":       {"Base Color": "#f4f1ea", "Roughness": 0.25, "Coat Weight": 0.5, "Coat Roughness": 0.08},
    "car_paint":     {"Base Color": "#b3121f", "Metallic": 0.55, "Roughness": 0.35, "Coat Weight": 1.0,
                      "Coat Roughness": 0.02, "_kind": "flakes"},
    "pearl":         {"Base Color": "#f3efe9", "Roughness": 0.2, "Coat Weight": 1.0, "Thin Film Thickness": 450.0,
                      "Thin Film IOR": 1.4},
    "iridescent":    {"Base Color": "#cfd5e0", "Metallic": 1.0, "Roughness": 0.12, "Thin Film Thickness": 600.0,
                      "Thin Film IOR": 1.6},
    "fabric":        {"Base Color": "#3b4a6b", "Roughness": 0.95, "Sheen Weight": 1.0, "Sheen Roughness": 0.4,
                      "Specular IOR Level": 0.2},
    "velvet":        {"Base Color": "#5a0f22", "Roughness": 1.0, "Sheen Weight": 1.0, "Sheen Roughness": 0.25,
                      "Specular IOR Level": 0.1},
    "wax":           {"Base Color": "#f1e4c8", "Roughness": 0.4, "Subsurface Weight": 1.0, "Subsurface Scale": 0.1},
    "skin":          {"Base Color": "#e0ac8f", "Roughness": 0.45, "Subsurface Weight": 0.6, "Subsurface Scale": 0.02},
    "emission":      {"Base Color": "#000000", "Emission Color": "#ffffff", "Emission Strength": 8.0, "Roughness": 1.0},
    "neon":          {"Base Color": "#000000", "Emission Color": "#ff2fb4", "Emission Strength": 18.0, "Roughness": 1.0},
    "noise":         {"Base Color": "#4a6cff", "Roughness": 0.4, "_kind": "noise"},
    "marble":        {"Base Color": "#f2f0ec", "Roughness": 0.12, "Coat Weight": 0.3, "_kind": "marble"},
    "wood":          {"Base Color": "#8a5a32", "Roughness": 0.45, "_kind": "wood"},
    "concrete":      {"Base Color": "#8d8b87", "Roughness": 0.9, "_kind": "noise"},
}

ALIASES = {"base_color": "Base Color", "color": "Base Color", "metallic": "Metallic", "roughness": "Roughness",
           "ior": "IOR", "alpha": "Alpha", "transmission": "Transmission Weight", "coat": "Coat Weight",
           "coat_roughness": "Coat Roughness", "sheen": "Sheen Weight", "subsurface": "Subsurface Weight",
           "emission": "Emission Color", "emission_color": "Emission Color", "emission_strength": "Emission Strength",
           "specular": "Specular IOR Level", "anisotropic": "Anisotropic", "thin_film": "Thin Film Thickness"}


def _principled(mat):
    nt = mat.node_tree
    p = next((n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None)
    out = next((n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial"), None)
    if p is None:
        p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    if out is None:
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        out.location = (400, 0)
    if not out.inputs["Surface"].is_linked:
        nt.links.new(p.outputs[0], out.inputs["Surface"])
    return p


def _wire_object_alpha(mat, p, alpha=1.0):
    """Principled Alpha = alpha * ObjectInfo.Alpha (object color alpha, animatable per object)."""
    nt = mat.node_tree
    oi = nt.nodes.new("ShaderNodeObjectInfo")
    oi.location = (-600, -500)
    mul = nt.nodes.new("ShaderNodeMath")
    mul.name = "AlphaMul"
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = float(alpha)
    mul.location = (-300, -500)
    nt.links.new(oi.outputs["Alpha"], mul.inputs[0])
    nt.links.new(mul.outputs[0], p.inputs["Alpha"])


def make_material(state, name=None, preset="plastic", color=None, color2=None, scale=5.0, bump=0.2,
                  emission_strength=None, alpha=1.0, object_alpha=True, inputs=None, **params):
    """Create a Principled material from a preset with overrides.

    preset: one of PRESETS (gold, chrome, glass, plastic, car_paint, fabric, neon, marble, wood, noise...).
    color: base color (or emission color for emission/neon). color2: secondary color for procedurals.
    Any Principled input by Blender name in `inputs` or by alias kwarg (roughness, metallic, ior,
    transmission, coat, sheen, subsurface, emission_strength, specular, anisotropic, thin_film).
    Returns the material name.
    """
    preset = (preset or "plastic").lower()
    if preset not in PRESETS:
        raise KeyError(f"unknown material preset '{preset}'. Available: {sorted(PRESETS)}")
    spec = dict(PRESETS[preset])
    kind = spec.pop("_kind", None)
    name = name or preset.capitalize()
    mat = bpy.data.materials.new(name)
    if hasattr(mat, "use_nodes") and not mat.use_nodes:
        mat.use_nodes = True
    p = _principled(mat)
    if color is not None:
        spec["Emission Color" if preset in ("emission", "neon") else "Base Color"] = color
    if emission_strength is not None:
        spec["Emission Strength"] = emission_strength
    for k, v in params.items():
        if k in ALIASES:
            spec[ALIASES[k]] = v
        else:
            warn(f"material param '{k}' ignored (use inputs={{'Input Name': value}})")
    spec.update(inputs or {})
    for k, v in spec.items():
        try:
            util.set_input(p, k, v)
        except KeyError:
            warn(f"Principled BSDF has no input '{k}' in this Blender version")
    if object_alpha:
        _wire_object_alpha(mat, p, alpha)
    else:
        p.inputs["Alpha"].default_value = float(alpha)
    if kind:
        BUILDERS[kind](mat, p, spec.get("Base Color", "#808080"), color2, float(scale), float(bump))
    if spec.get("Transmission Weight", 0) > 0 and hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "DITHERED"
        if hasattr(mat, "use_raytrace_refraction"):
            mat.use_raytrace_refraction = True
    state.setdefault("materials", {})[mat.name] = mat
    return mat.name


# --------------------------------------------------------------------------- procedural builders
def _coords(nt, scale):
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (scale, scale, scale)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    return mp


def _bump(nt, p, height_socket, strength):
    if strength <= 0:
        return
    b = nt.nodes.new("ShaderNodeBump")
    b.inputs["Strength"].default_value = strength
    b.inputs["Distance"].default_value = 0.02
    nt.links.new(height_socket, b.inputs["Height"])
    nt.links.new(b.outputs["Normal"], p.inputs["Normal"])


def _ramp(nt, c1, c2, positions=(0.0, 1.0)):
    r = nt.nodes.new("ShaderNodeValToRGB")
    r.color_ramp.elements[0].position, r.color_ramp.elements[1].position = positions
    r.color_ramp.elements[0].color = util.color(c1)
    r.color_ramp.elements[1].color = util.color(c2)
    return r


def _darker(c, f=0.35):
    lc = util.color(c)
    return [lc[0] * f, lc[1] * f, lc[2] * f, 1.0]


def build_noise(mat, p, base, color2, scale, bump):
    nt = mat.node_tree
    mp = _coords(nt, scale)
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Detail"].default_value = 8.0
    nz.inputs["Roughness"].default_value = 0.6
    nt.links.new(mp.outputs[0], nz.inputs["Vector"])
    r = _ramp(nt, color2 or _darker(base), base, (0.3, 0.7))
    nt.links.new(nz.outputs["Fac"], r.inputs[0])
    nt.links.new(r.outputs[0], p.inputs["Base Color"])
    _bump(nt, p, nz.outputs["Fac"], bump)


def build_marble(mat, p, base, color2, scale, bump):
    nt = mat.node_tree
    mp = _coords(nt, scale * 0.4)
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "DIAGONAL"
    wave.inputs["Scale"].default_value = 0.5
    wave.inputs["Distortion"].default_value = 9.0
    wave.inputs["Detail"].default_value = 10.0
    wave.inputs["Detail Scale"].default_value = 2.0
    wave.inputs["Detail Roughness"].default_value = 0.6
    nt.links.new(mp.outputs[0], wave.inputs["Vector"])
    r = _ramp(nt, color2 or "#6b6e75", base, (0.0, 0.07))
    nt.links.new(wave.outputs["Fac"], r.inputs[0])
    nt.links.new(r.outputs[0], p.inputs["Base Color"])
    _bump(nt, p, wave.outputs["Fac"], bump * 0.1)


def build_wood(mat, p, base, color2, scale, bump):
    nt = mat.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (scale * 0.25, scale * 0.25, scale * 3.0)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 2.0
    nz.inputs["Detail"].default_value = 4.0
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "VECTOR"
    mix.inputs["Factor"].default_value = 0.08
    nt.links.new(mp.outputs[0], nz.inputs["Vector"])
    nt.links.new(mp.outputs[0], util.node_input(mix, "A"))
    nt.links.new(nz.outputs["Color"], util.node_input(mix, "B"))
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "RINGS"
    wave.inputs["Scale"].default_value = 3.0
    wave.inputs["Distortion"].default_value = 3.0
    nt.links.new(util.node_output(mix, "Result"), wave.inputs["Vector"])
    r = _ramp(nt, color2 or _darker(base, 0.45), base, (0.1, 0.9))
    nt.links.new(wave.outputs["Fac"], r.inputs[0])
    nt.links.new(r.outputs[0], p.inputs["Base Color"])
    _bump(nt, p, wave.outputs["Fac"], bump * 0.3)


def build_flakes(mat, p, base, color2, scale, bump):
    nt = mat.node_tree
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 900.0
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nt.links.new(tc.outputs["Object"], vor.inputs["Vector"])
    b = nt.nodes.new("ShaderNodeBump")
    b.inputs["Strength"].default_value = 0.15
    nt.links.new(vor.outputs["Distance"], b.inputs["Height"])
    nt.links.new(b.outputs["Normal"], p.inputs["Normal"])  # coat keeps its own smooth normal


BUILDERS = {"noise": build_noise, "marble": build_marble, "wood": build_wood, "flakes": build_flakes}


# --------------------------------------------------------------------------- textures
def image_material(state, path, name=None, emission=False, emission_strength=1.0, alpha=True, video=False,
                   roughness=0.5, loop=True, projection="UV", scale=1.0, **_):
    """Material using an image (or movie when video=True or the file is a video).
    emission=True makes it self-lit (screens, posters). Returns material name."""
    p = util.resolve_path(state, path)
    ext = os.path.splitext(p)[1].lower()
    is_video = video or ext in (".mp4", ".mov", ".mkv", ".webm", ".avi", ".gif")
    name = name or os.path.splitext(os.path.basename(p))[0] + "_mat"
    mat = bpy.data.materials.new(name)
    bsdf = _principled(mat)
    nt = mat.node_tree
    tex = nt.nodes.new("ShaderNodeTexImage")
    img = bpy.data.images.load(p, check_existing=True)
    if is_video:
        img.source = "MOVIE"
        tex.image = img
        iu = tex.image_user
        iu.frame_duration = max(1, img.frame_duration)
        iu.frame_start = bpy.context.scene.frame_start
        iu.use_auto_refresh = True
        iu.use_cyclic = bool(loop)
    else:
        tex.image = img
    tex.projection = projection
    if scale != 1.0:
        tc = nt.nodes.new("ShaderNodeTexCoord")
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (scale, scale, scale)
        nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])
        nt.links.new(mp.outputs[0], tex.inputs["Vector"])
    bsdf.inputs["Roughness"].default_value = float(roughness)
    if emission:
        bsdf.inputs["Base Color"].default_value = (0, 0, 0, 1)
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = float(emission_strength)
    else:
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    if alpha:
        _wire_object_alpha(mat, bsdf)
        mul = nt.nodes["AlphaMul"]
        nt.links.new(tex.outputs["Alpha"], mul.inputs[1])
    state.setdefault("materials", {})[mat.name] = mat
    return mat.name


def video_material(state, path, **kw):
    """Image material with movie playback synced to the timeline (emission by default)."""
    kw.setdefault("emission", True)
    return image_material(state, path, video=True, **kw)


def material_graph(state, name, nodes=None, links=None, keep_principled=True, **_):
    """Fully custom shader graph. Default nodes 'Principled BSDF' and 'Material Output' exist
    (unless keep_principled=False). Spec format: see util.build_node_graph."""
    mat = bpy.data.materials.new(name)
    _principled(mat)
    if not keep_principled:
        mat.node_tree.nodes.clear()
    util.build_node_graph(mat.node_tree, {"nodes": nodes or {}, "links": links or []})
    state.setdefault("materials", {})[mat.name] = mat
    return mat.name


# --------------------------------------------------------------------------- assignment / ops
def assign(state, obj, material, slot=None, append=False):
    """Assign a material (name, preset name, dict spec, or bpy Material) to an object."""
    if isinstance(material, dict):
        material = make_material(state, **material)
    if isinstance(material, str):
        mat = util.get_mat(state, material, required=False)
        if mat is None and material.lower() in PRESETS:
            mat = util.get_mat(state, make_material(state, name=material, preset=material.lower()))
        if mat is None:
            raise KeyError(f"material '{material}' not found and not a preset ({sorted(PRESETS)})")
    else:
        mat = material
    if obj.data is None or not hasattr(obj.data, "materials"):
        for ch in obj.children_recursive:
            if ch.data is not None and hasattr(ch.data, "materials"):
                assign(state, ch, mat, slot, append)
        return mat.name
    mats = obj.data.materials
    if slot is not None and slot < len(mats):
        mats[slot] = mat
    elif append or not len(mats):
        mats.append(mat)
    else:
        for i in range(len(mats)):
            mats[i] = mat
    return mat.name


def material_op(state, target=None, targets=None, **params):
    """Create a material (preset + overrides) and optionally assign it to target(s). Returns name.
    Example: {"op":"material","name":"Gold","preset":"gold","target":"Logo"}"""
    name = make_material(state, **params)
    for obj in util.get_objs(state, targets or target):
        assign(state, obj, name)
    return name


def assign_material(state, target, material, slot=None, **_):
    for obj in util.get_objs(state, target):
        assign(state, obj, material, slot)
    return {"material": material if isinstance(material, str) else getattr(material, "name", None)}


def set_material_input(state, material, input, value, node="Principled BSDF", **_):
    """Change one input of a node in an existing material."""
    mat = util.get_mat(state, material)
    util.set_input(mat.node_tree.nodes[node], input, value)
    return {"material": mat.name}


def list_presets(state, **_):
    return sorted(PRESETS)


OPS = {
    "material": material_op,
    "assign_material": assign_material,
    "image_material": lambda state, target=None, **kw: _assign_ret(state, target, image_material(state, **kw)),
    "video_material": lambda state, target=None, **kw: _assign_ret(state, target, video_material(state, **kw)),
    "material_graph": lambda state, target=None, **kw: _assign_ret(state, target, material_graph(state, **kw)),
    "set_material_input": set_material_input,
    "material_presets": list_presets,
}


def _assign_ret(state, target, name):
    for obj in util.get_objs(state, target):
        assign(state, obj, name)
    return name


OPS["image_material"].__doc__ = image_material.__doc__ + " Optional target to assign to."
OPS["video_material"].__doc__ = video_material.__doc__ + " Optional target to assign to."
OPS["material_graph"].__doc__ = material_graph.__doc__ + " Optional target to assign to."
