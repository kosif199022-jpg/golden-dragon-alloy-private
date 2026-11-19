"""Geometry Nodes helpers: surface scatter, animated wave grid (seamless loops), text extruded
through geometry nodes, and a generic JSON graph builder for any custom node group."""
import math

import bpy

from . import util
from .util import warn


# --------------------------------------------------------------------------- plumbing
def new_group(name, geometry_in=True):
    ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    if geometry_in:
        ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    gi = ng.nodes.new("NodeGroupInput")
    gi.location = (-900, 0)
    go = ng.nodes.new("NodeGroupOutput")
    go.location = (900, 0)
    return ng, gi, go


def add_socket(ng, name, socket_type="NodeSocketFloat", default=None, min_value=None, max_value=None):
    s = ng.interface.new_socket(name, in_out="INPUT", socket_type=socket_type)
    if default is not None and hasattr(s, "default_value"):
        s.default_value = default
    if min_value is not None and hasattr(s, "min_value"):
        s.min_value = min_value
    if max_value is not None and hasattr(s, "max_value"):
        s.max_value = max_value
    return s


def N(ng, type, **inputs):
    """Create node of type with input defaults (props via _props dict)."""
    props = inputs.pop("_props", {})
    n = ng.nodes.new(type)
    for k, v in props.items():
        setattr(n, k, v)
    for k, v in inputs.items():
        util.set_input(n, k.replace("_", " "), v)
    return n


def L(ng, a, aout, b, bin_):
    ng.links.new(util.node_output(a, aout), util.node_input(b, bin_))


def attach(state, target, ng, name=None, inputs=None):
    obj = util.get_obj(state, target)
    mod = obj.modifiers.new(name or ng.name, "NODES")
    mod.node_group = ng
    set_inputs(mod, inputs or {})
    return mod


def set_inputs(mod, inputs):
    by_name = {it.name: it for it in mod.node_group.interface.items_tree
               if getattr(it, "in_out", None) == "INPUT"}
    for k, v in inputs.items():
        it = by_name.get(k)
        if it is None:
            warn(f"node group '{mod.node_group.name}' has no input '{k}' ({list(by_name)})")
            continue
        if isinstance(v, str) and it.socket_type == "NodeSocketObject":
            v = bpy.data.objects[v]
        elif isinstance(v, str) and it.socket_type == "NodeSocketMaterial":
            v = bpy.data.materials[v]
        elif isinstance(v, str) and it.socket_type == "NodeSocketCollection":
            v = bpy.data.collections[v]
        elif isinstance(v, str) and it.socket_type == "NodeSocketColor":
            v = util.color(v)
        _, setter = input_slot(mod, it.identifier)
        setter(v)


def input_slot(mod, identifier):
    """(keyframe data path relative to the object, setter) for a modifier input.
    Blender 5.x: mod.properties.inputs.<Socket_N>.value; older: ID property mod["Socket_N"]."""
    props = getattr(mod, "properties", None)
    slot = getattr(getattr(props, "inputs", None), identifier, None) if props is not None else None
    if slot is not None and hasattr(slot, "value"):
        return (f'modifiers["{mod.name}"].properties.inputs.{identifier}.value',
                lambda v: setattr(slot, "value", v))

    def legacy(v):
        mod[identifier] = v
    return f'modifiers["{mod.name}"]["{identifier}"]', legacy


def _host(state, name):
    me = bpy.data.meshes.new(name)
    return util.register(state, util.new_object(name, me), name)


def _rotation_from_euler(ng, vec_socket_node, out_name):
    """Return node whose output 0 is a rotation built from an euler vector."""
    if hasattr(bpy.types, "FunctionNodeEulerToRotation"):
        e2r = ng.nodes.new("FunctionNodeEulerToRotation")
        L(ng, vec_socket_node, out_name, e2r, "Euler")
        return e2r, "Rotation"
    return vec_socket_node, out_name


# --------------------------------------------------------------------------- scatter
def gn_scatter(state, target, instance, density=20.0, seed=0, scale_min=0.6, scale_max=1.2, random_rotation=360.0,
               align_to_normal=True, keep_surface=True, max_count=None, name="Scatter", realize=False,
               distance_min=0.0, **_):
    """Scatter instances of an object over target's surface via Geometry Nodes (handles thousands).
    density = points per square unit. distance_min > 0 uses Poisson disk spacing.
    random_rotation = max degrees around the local Z (normal) axis."""
    inst = util.get_obj(state, instance)
    ng, gi, go = new_group(f"{name}_GN")
    dist = N(ng, "GeometryNodeDistributePointsOnFaces",
             _props={"distribute_method": "POISSON" if distance_min else "RANDOM"})
    L(ng, gi, "Geometry", dist, "Mesh")
    util.set_input(dist, "Density" if not distance_min else "Density Max", float(density))
    if distance_min:
        util.set_input(dist, "Distance Min", float(distance_min))
    util.set_input(dist, "Seed", int(seed))
    oi = N(ng, "GeometryNodeObjectInfo", _props={"transform_space": "ORIGINAL"})
    util.node_input(oi, "Object").default_value = inst
    iop = N(ng, "GeometryNodeInstanceOnPoints")
    L(ng, dist, "Points", iop, "Points")
    L(ng, oi, "Geometry", iop, "Instance")
    rs = N(ng, "FunctionNodeRandomValue", _props={"data_type": "FLOAT"})
    util.set_input(rs, "Min", float(scale_min))
    util.set_input(rs, "Max", float(scale_max))
    util.set_input(rs, "Seed", int(seed) + 11)
    L(ng, rs, "Value", iop, "Scale")
    # random spin around the normal, then align to normal
    rr = N(ng, "FunctionNodeRandomValue", _props={"data_type": "FLOAT_VECTOR"})
    util.set_input(rr, "Min", [0, 0, 0])
    util.set_input(rr, "Max", [0, 0, math.radians(random_rotation)])
    util.set_input(rr, "Seed", int(seed) + 23)
    spin, spin_out = _rotation_from_euler(ng, rr, "Value")
    if align_to_normal and hasattr(bpy.types, "FunctionNodeRotateRotation"):
        rot = N(ng, "FunctionNodeRotateRotation", _props={"rotation_space": "LOCAL"})
        L(ng, dist, "Rotation", rot, "Rotation")
        L(ng, spin, spin_out, rot, "Rotate By")
        L(ng, rot, "Rotation", iop, "Rotation")
    else:
        L(ng, spin, spin_out, iop, "Rotation")
    last = iop
    if realize:
        rz = N(ng, "GeometryNodeRealizeInstances")
        L(ng, iop, "Instances", rz, "Geometry")
        last = rz
    if keep_surface:
        j = N(ng, "GeometryNodeJoinGeometry")
        L(ng, gi, "Geometry", j, "Geometry")
        L(ng, last, 0, j, "Geometry")
        last = j
    L(ng, last, 0, go, "Geometry")
    inst.hide_render = True
    inst.hide_viewport = True
    mod = attach(state, target, ng, name)
    return {"object": util.get_obj(state, target).name, "modifier": mod.name}


# --------------------------------------------------------------------------- wave grid
def gn_wave_grid(state, name="WaveGrid", count=24, spacing=0.42, cell=0.36, height=0.15, amplitude=1.2,
                 frequency=1.6, loop_frames=None, pattern="radial", shape="cube", material=None,
                 bevel=0.0, location=(0, 0, 0), **_):
    """Procedural grid of cubes/cylinders whose heights ripple. Loops seamlessly every loop_frames
    (default: scene length). pattern: radial | linear | diagonal. The 0..1 wave value is stored as
    instance attribute 'wave' (shader: Attribute node, type Instancer, name 'wave')."""
    sc = bpy.context.scene
    loop = float(loop_frames or (sc.frame_end - sc.frame_start + 1))
    host = _host(state, name)
    ng, gi, go = new_group(f"{name}_GN", geometry_in=False)
    size = count * spacing
    grid = N(ng, "GeometryNodeMeshGrid")
    util.set_input(grid, "Size X", size)
    util.set_input(grid, "Size Y", size)
    util.set_input(grid, "Vertices X", int(count))
    util.set_input(grid, "Vertices Y", int(count))
    if shape == "cylinder":
        prim = N(ng, "GeometryNodeMeshCylinder")
        util.set_input(prim, "Vertices", 24)
        util.set_input(prim, "Radius", cell / 2)
        util.set_input(prim, "Depth", 1.0)
    else:
        prim = N(ng, "GeometryNodeMeshCube")
        util.set_input(prim, "Size", [cell, cell, 1.0])
    tr = N(ng, "GeometryNodeTransform")
    util.set_input(tr, "Translation", [0, 0, 0.5])
    L(ng, prim, "Mesh", tr, "Geometry")
    geo_inst = tr
    if material:
        sm = N(ng, "GeometryNodeSetMaterial")
        util.node_input(sm, "Material").default_value = util.get_mat(state, material)
        L(ng, tr, "Geometry", sm, "Geometry")
        geo_inst = sm
    iop = N(ng, "GeometryNodeInstanceOnPoints")
    L(ng, grid, "Mesh", iop, "Points")
    L(ng, geo_inst, "Geometry", iop, "Instance")
    # wave = (sin(d*freq - 2pi*frame/loop) + 1) / 2
    pos = N(ng, "GeometryNodeInputPosition")
    if pattern == "radial":
        d = N(ng, "ShaderNodeVectorMath", _props={"operation": "LENGTH"})
        L(ng, pos, "Position", d, 0)
        d_out = ("Value",)
    else:
        sep = N(ng, "ShaderNodeSeparateXYZ")
        L(ng, pos, "Position", sep, 0)
        if pattern == "diagonal":
            d = N(ng, "ShaderNodeMath", _props={"operation": "ADD"})
            L(ng, sep, "X", d, 0)
            L(ng, sep, "Y", d, 1)
        else:
            d = N(ng, "ShaderNodeMath", _props={"operation": "ADD"})
            L(ng, sep, "X", d, 0)
            util.set_input(d, 1, 0.0)
        d_out = ("Value",)
    mf = N(ng, "ShaderNodeMath", _props={"operation": "MULTIPLY"})
    L(ng, d, d_out[0], mf, 0)
    util.node_input(mf, 1).default_value = float(frequency)
    st = N(ng, "GeometryNodeInputSceneTime")
    ph = N(ng, "ShaderNodeMath", _props={"operation": "MULTIPLY"})
    L(ng, st, "Frame", ph, 0)
    util.node_input(ph, 1).default_value = 2 * math.pi / loop
    sub = N(ng, "ShaderNodeMath", _props={"operation": "SUBTRACT"})
    L(ng, mf, "Value", sub, 0)
    L(ng, ph, "Value", sub, 1)
    sn = N(ng, "ShaderNodeMath", _props={"operation": "SINE"})
    L(ng, sub, "Value", sn, 0)
    w01 = N(ng, "ShaderNodeMapRange")
    L(ng, sn, 0, w01, "Value")
    util.set_input(w01, "From Min", -1.0)
    util.set_input(w01, "From Max", 1.0)
    hz = N(ng, "ShaderNodeMath", _props={"operation": "MULTIPLY_ADD"})
    L(ng, w01, "Result", hz, 0)
    util.node_input(hz, 1).default_value = float(amplitude)
    util.node_input(hz, 2).default_value = float(height)
    cx = N(ng, "ShaderNodeCombineXYZ")
    util.set_input(cx, "X", 1.0)
    util.set_input(cx, "Y", 1.0)
    L(ng, hz, "Value", cx, "Z")
    L(ng, cx, "Vector", iop, "Scale")
    store = N(ng, "GeometryNodeStoreNamedAttribute", _props={"data_type": "FLOAT", "domain": "INSTANCE"})
    util.set_input(store, "Name", "wave")
    L(ng, iop, "Instances", store, "Geometry")
    L(ng, w01, "Result", store, "Value")
    L(ng, store, "Geometry", go, "Geometry")
    attach(state, host.name, ng, name)
    host.location = util.vec3(location)
    return host.name


# --------------------------------------------------------------------------- GN text
def gn_text(state, text, name="GNText", font=None, size=1.0, depth=0.15, location=(0, 0, 0), rotation=(90, 0, 0),
            material=None, align_x="CENTER", character_spacing=1.0, **_):
    """Text built with Geometry Nodes (String to Curves -> Fill -> Extrude). Arabic is shaped.
    The modifier inputs "Depth" and "Size" can be animated with gn_set_input(frame=...).
    (5.x data path: modifiers["<name>"].properties.inputs.Socket_N.value)"""
    from . import text3d
    raw = str(text)
    arabic = text3d.has_arabic(raw)
    body = text3d.shape(raw) if arabic else raw
    host = _host(state, name)
    ng, gi, go = new_group(f"{name}_GN", geometry_in=False)
    add_socket(ng, "Depth", "NodeSocketFloat", float(depth), 0.0, 100.0)
    add_socket(ng, "Size", "NodeSocketFloat", float(size), 0.0, 1000.0)
    s2c = N(ng, "GeometryNodeStringToCurves")
    util.set_input(s2c, "String", body)
    f = text3d.load_font(font, arabic)
    if f is not None:
        fs = [s for s in s2c.inputs if s.type == "FONT" or s.name == "Font"]
        if fs:
            fs[0].default_value = f
        elif hasattr(s2c, "font"):
            s2c.font = f
    for k, v in (("Character Spacing", character_spacing),):
        try:
            util.set_input(s2c, k, v)
        except KeyError:
            pass
    try:
        s2c.align_x = align_x.upper()
    except (AttributeError, TypeError):
        try:
            util.set_input(s2c, "Align X", align_x.title())
        except Exception:
            pass
    L(ng, gi, "Size", s2c, "Size")
    real = N(ng, "GeometryNodeRealizeInstances")
    L(ng, s2c, "Curve Instances", real, "Geometry")
    fill = N(ng, "GeometryNodeFillCurve")
    try:
        fill.mode = "NGONS"
    except (AttributeError, TypeError):
        pass
    L(ng, real, "Geometry", fill, "Curve")
    ext = N(ng, "GeometryNodeExtrudeMesh")
    L(ng, fill, "Mesh", ext, "Mesh")
    L(ng, gi, "Depth", ext, "Offset Scale")
    j = N(ng, "GeometryNodeJoinGeometry")
    flip = N(ng, "GeometryNodeFlipFaces")
    L(ng, fill, "Mesh", flip, "Mesh")
    L(ng, flip, "Mesh", j, "Geometry")
    L(ng, ext, "Mesh", j, "Geometry")
    weld = N(ng, "GeometryNodeMergeByDistance")
    L(ng, j, "Geometry", weld, "Geometry")
    last = weld
    if material:
        sm = N(ng, "GeometryNodeSetMaterial")
        mat = util.get_mat(state, material, False) if isinstance(material, str) else None
        util.node_input(sm, "Material").default_value = mat or _mat(state, material)
        L(ng, weld, "Geometry", sm, "Geometry")
        last = sm
    L(ng, last, 0, go, "Geometry")
    attach(state, host.name, ng, name)
    util.set_transform(host, location, rotation)
    return host.name


def _mat(state, spec):
    from . import materials
    if isinstance(spec, dict):
        return util.get_mat(state, materials.make_material(state, **spec))
    return util.get_mat(state, materials.make_material(state, name=spec, preset=spec))


# --------------------------------------------------------------------------- generic
def gn_graph(state, target=None, name="CustomGN", nodes=None, links=None, interface=None, inputs=None,
             geometry_in=True, **_):
    """Build any Geometry Nodes group from JSON and attach it to target (new empty mesh object if
    target is None). Pre-made nodes: 'Group Input', 'Group Output'.
    interface: [{"name": "Amount", "type": "NodeSocketFloat", "default": 1.0}] (extra inputs).
    nodes/links: see util.build_node_graph, e.g.
      nodes {"cube": {"type": "GeometryNodeMeshCube", "inputs": {"Size": [1,1,1]}}}
      links [["cube.Mesh", "Group Output.Geometry"]]"""
    ng, gi, go = new_group(f"{name}_GN", geometry_in=geometry_in)
    gi.name, go.name = "Group Input", "Group Output"
    for s in interface or []:
        add_socket(ng, s["name"], s.get("type", "NodeSocketFloat"), s.get("default"), s.get("min"), s.get("max"))
    util.build_node_graph(ng, {"nodes": nodes or {}, "links": links or []})
    host = util.get_obj(state, target) if target else _host(state, name)
    mod = attach(state, host.name, ng, name, inputs)
    return {"object": host.name, "modifier": mod.name, "group": ng.name}


def gn_set_input(state, target, input, value, modifier=None, frame=None, easing=None, **_):
    """Set (and optionally keyframe at `frame`) an input of a Geometry Nodes modifier by its name."""
    obj = util.get_obj(state, target)
    mod = obj.modifiers.get(modifier) if modifier else next(m for m in obj.modifiers if m.type == "NODES")
    set_inputs(mod, {input: value})
    if frame is not None:
        ident = next(it.identifier for it in mod.node_group.interface.items_tree
                     if getattr(it, "in_out", None) == "INPUT" and it.name == input)
        path, _ = input_slot(mod, ident)
        util.set_key(obj, path, value, int(frame), easing=easing)
    return {"object": obj.name, "modifier": mod.name}


OPS = {
    "gn_scatter": gn_scatter,
    "gn_wave_grid": gn_wave_grid,
    "gn_text": gn_text,
    "gn_graph": gn_graph,
    "gn_set_input": gn_set_input,
}
