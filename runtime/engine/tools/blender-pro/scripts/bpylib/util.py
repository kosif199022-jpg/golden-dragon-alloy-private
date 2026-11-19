"""Shared helpers for bpylib ops (Blender 5.x).

Conventions used by every op:
  * Angles in recipes are DEGREES; this module converts to radians.
  * Colors: "#RRGGBB" / "#RRGGBBAA" hex strings are sRGB and converted to linear;
    lists [r, g, b(, a)] are taken as linear values as-is.
  * Object references ("target", "source", ...) are names looked up in
    state["objects"] first, then bpy.data.objects.
  * Relative file paths resolve against the recipe directory, then the skill
    assets directory.
"""
import math
import os
import random
import re

import bpy
import mathutils

SKILL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ASSETS_DIR = os.path.join(SKILL_DIR, "assets")


# --------------------------------------------------------------------------- logging
def log(msg, level="info"):
    print(f"[bpylib:{level}] {msg}", flush=True)


def warn(msg):
    log(msg, "warn")


# --------------------------------------------------------------------------- state
def new_state(out_dir=None, recipe_dir=None, preview=False):
    """Create the shared state dict passed to every op."""
    return {
        "objects": {},
        "materials": {},
        "scene": bpy.context.scene,
        "out_dir": out_dir or os.getcwd(),
        "recipe_dir": recipe_dir or os.getcwd(),
        "preview": bool(preview),
        "outputs": [],
        "warnings": [],
        "vars": {},
    }


def register(state, obj, name=None):
    """Put an object into the state registry (and rename it if name given)."""
    if name:
        obj.name = name
    if state is not None:
        state.setdefault("objects", {})[name or obj.name] = obj
    return obj


def get_obj(state, ref, required=True):
    """Resolve an object reference (name or object)."""
    if ref is None:
        if required:
            raise ValueError("object reference is required (e.g. \"target\": \"name\")")
        return None
    if isinstance(ref, bpy.types.Object):
        return ref
    obj = None
    if state is not None:
        obj = state.get("objects", {}).get(ref)
        # registry may hold a deleted object
        try:
            if obj is not None:
                obj.name  # noqa: B018  (raises ReferenceError if removed)
        except ReferenceError:
            obj = None
    if obj is None:
        obj = bpy.data.objects.get(ref)
    if obj is None and required:
        known = sorted(set(list((state or {}).get("objects", {}).keys()) + [o.name for o in bpy.data.objects]))
        raise KeyError(f"object '{ref}' not found. Known: {known}")
    return obj


def get_objs(state, refs):
    if refs is None:
        return []
    if isinstance(refs, (str, bpy.types.Object)):
        refs = [refs]
    return [get_obj(state, r) for r in refs]


def get_mat(state, ref, required=True):
    if isinstance(ref, bpy.types.Material):
        return ref
    m = (state or {}).get("materials", {}).get(ref) or bpy.data.materials.get(ref)
    if m is None and required:
        raise KeyError(f"material '{ref}' not found. Known: {[x.name for x in bpy.data.materials]}")
    return m


def resolve_path(state, path, must_exist=True):
    """Resolve a file path relative to the recipe dir / assets dir; expands ~ and %VARS%."""
    if not path:
        raise ValueError("empty path")
    p = os.path.expandvars(os.path.expanduser(str(path)))
    cands = [p] if os.path.isabs(p) else [
        os.path.join((state or {}).get("recipe_dir", os.getcwd()), p),
        os.path.join(ASSETS_DIR, p),
        os.path.abspath(p),
    ]
    for c in cands:
        if os.path.exists(c):
            return os.path.abspath(c)
    if must_exist:
        raise FileNotFoundError(f"file not found: {path} (tried {cands})")
    return os.path.abspath(cands[0])


def out_path(state, path):
    """Resolve an output path relative to state['out_dir'] and create parent dirs."""
    p = os.path.expandvars(os.path.expanduser(str(path)))
    if not os.path.isabs(p):
        p = os.path.join(state.get("out_dir", os.getcwd()), p)
    p = os.path.abspath(p)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


# --------------------------------------------------------------------------- values
def color(c, alpha=1.0):
    """Return a linear RGBA 4-tuple from hex (sRGB) / list (linear) / float (gray)."""
    if c is None:
        return (0.8, 0.8, 0.8, alpha)
    if isinstance(c, (int, float)):
        return (float(c), float(c), float(c), alpha)
    if isinstance(c, str):
        named = NAMED_COLORS.get(c.lower())
        if named:
            c = named
        h = c.lstrip("#")
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        if len(h) not in (6, 8):
            raise ValueError(f"bad color '{c}'")
        vals = [int(h[i:i + 2], 16) / 255.0 for i in range(0, len(h), 2)]
        rgb = [srgb_to_linear(v) for v in vals[:3]]
        a = vals[3] if len(vals) == 4 else alpha
        return (rgb[0], rgb[1], rgb[2], a)
    c = list(c)
    if len(c) == 3:
        c.append(alpha)
    return tuple(float(x) for x in c[:4])


def color3(c):
    return color(c)[:3]


def srgb_to_linear(v):
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def kelvin(temp):
    """Approximate blackbody color (linear RGB) for a temperature in Kelvin."""
    t = max(1000.0, min(40000.0, float(temp))) / 100.0
    if t <= 66:
        r = 255.0
        g = 99.4708025861 * math.log(t) - 161.1195681661
        b = 0.0 if t <= 19 else 138.5177312231 * math.log(t - 10) - 305.0447927307
    else:
        r = 329.698727446 * ((t - 60) ** -0.1332047592)
        g = 288.1221695283 * ((t - 60) ** -0.0755148492)
        b = 255.0
    return tuple(srgb_to_linear(max(0.0, min(255.0, x)) / 255.0) for x in (r, g, b))


NAMED_COLORS = {
    "white": "#ffffff", "black": "#000000", "gold": "#d4a640", "red": "#e02424",
    "blue": "#2f6bff", "cyan": "#22d3ee", "magenta": "#ff2fb4", "orange": "#ff8a1f",
    "green": "#22c55e", "purple": "#8b5cf6", "gray": "#808080", "grey": "#808080",
}


def vec3(v, default=(0.0, 0.0, 0.0)):
    if v is None:
        return mathutils.Vector(default)
    if isinstance(v, (int, float)):
        return mathutils.Vector((v, v, v))
    v = list(v)
    while len(v) < 3:
        v.append(0.0)
    return mathutils.Vector([float(x) for x in v[:3]])


def rad3(v):
    """Degrees list -> radians Euler."""
    return mathutils.Euler([math.radians(x) for x in vec3(v)], "XYZ")


def scale3(v):
    if v is None:
        return mathutils.Vector((1, 1, 1))
    return vec3(v)


def set_transform(obj, location=None, rotation=None, scale=None):
    if location is not None:
        obj.location = vec3(location)
    if rotation is not None:
        obj.rotation_euler = rad3(rotation)
    if scale is not None:
        obj.scale = scale3(scale)


def rng(seed=0):
    return random.Random(seed)


# --------------------------------------------------------------------------- scene graph
def link_object(obj, collection=None):
    coll = collection or bpy.context.scene.collection
    if obj.name not in coll.objects:
        coll.objects.link(obj)
    return obj


def new_object(name, data=None, collection=None):
    obj = bpy.data.objects.new(name, data)
    return link_object(obj, collection)


def get_collection(name, parent=None):
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(coll)
    return coll


def set_active(obj, select_only=True):
    view_layer = bpy.context.view_layer
    if select_only:
        for o in view_layer.objects:
            o.select_set(False)
    obj.select_set(True)
    view_layer.objects.active = obj


def op_context(obj=None, objs=None):
    """Context override dict for bpy.ops operating on objects in background mode."""
    objs = objs or ([obj] if obj else [])
    ctx = {"selected_objects": objs, "selected_editable_objects": objs}
    if obj:
        ctx.update(object=obj, active_object=obj)
    return ctx


def world_bbox(objs):
    """World-space (min, max) over evaluated bounding boxes of objects."""
    mn = mathutils.Vector((1e18,) * 3)
    mx = mathutils.Vector((-1e18,) * 3)
    found = False
    deps = bpy.context.evaluated_depsgraph_get()
    for o in objs:
        if o.type not in {"MESH", "CURVE", "FONT", "SURFACE", "META", "EMPTY", "CURVES", "POINTCLOUD", "VOLUME", "GREASEPENCIL"}:
            continue
        oe = o.evaluated_get(deps)
        corners = [oe.matrix_world @ mathutils.Vector(c) for c in oe.bound_box]
        if o.type == "EMPTY":
            corners = [o.matrix_world.translation]
        for c in corners:
            found = True
            for i in range(3):
                mn[i] = min(mn[i], c[i])
                mx[i] = max(mx[i], c[i])
    if not found:
        return mathutils.Vector((-1, -1, -1)), mathutils.Vector((1, 1, 1))
    return mn, mx


def renderable_objects():
    return [o for o in bpy.context.scene.objects
            if o.type in {"MESH", "CURVE", "FONT", "SURFACE", "META", "CURVES", "POINTCLOUD", "VOLUME"}
            and not o.hide_render and not o.get("blpro_backdrop")]


def look_at(obj, target):
    """Rotate obj so its -Z axis (camera/light forward) points at target (Vector)."""
    direction = vec3(target) - obj.location
    if direction.length < 1e-9:
        return
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


# --------------------------------------------------------------------------- animation
EASING_INTERP = {
    "constant": "CONSTANT", "linear": "LINEAR", "bezier": "BEZIER", "sine": "SINE",
    "quad": "QUAD", "cubic": "CUBIC", "quart": "QUART", "quint": "QUINT", "expo": "EXPO",
    "circ": "CIRC", "back": "BACK", "bounce": "BOUNCE", "elastic": "ELASTIC",
}
EASING_DIR = {"in": "EASE_IN", "out": "EASE_OUT", "in_out": "EASE_IN_OUT", "inout": "EASE_IN_OUT", "auto": "AUTO"}


def parse_easing(easing):
    """'expo_out' -> ('EXPO','EASE_OUT'); 'linear' -> ('LINEAR','AUTO');
    'ease_in_out'/'smooth' -> ('BEZIER','AUTO') with auto-clamped handles."""
    if not easing:
        return "BEZIER", "AUTO"
    e = str(easing).lower().replace("-", "_").replace(" ", "_")
    if e in ("smooth", "ease", "ease_in_out", "bezier"):
        return "BEZIER", "AUTO"
    if e in ("ease_in", "ease_out"):
        return "CUBIC", EASING_DIR[e[5:]]
    for k, interp in EASING_INTERP.items():
        if e == k:
            return interp, "EASE_IN_OUT" if k not in ("constant", "linear", "bezier") else "AUTO"
        if e.startswith(k + "_"):
            return interp, EASING_DIR.get(e[len(k) + 1:], "EASE_IN_OUT")
    raise ValueError(f"unknown easing '{easing}'. Use e.g. linear, smooth, sine_in_out, expo_out, back_out, bounce_out, elastic_out, constant")


def fcurves(id_data):
    """All F-curves of an ID's active action (Blender 5.x layered actions + legacy)."""
    ad = getattr(id_data, "animation_data", None)
    if not ad or not ad.action:
        return []
    act = ad.action
    legacy = getattr(act, "fcurves", None)
    if legacy is not None and not getattr(act, "is_action_layered", True):
        return list(legacy)
    try:
        from bpy_extras import anim_utils
        cb = anim_utils.action_get_channelbag_for_slot(act, ad.action_slot)
        return list(cb.fcurves) if cb else []
    except Exception:  # pragma: no cover - API drift guard
        out = []
        for layer in act.layers:
            for strip in layer.strips:
                for cb in getattr(strip, "channelbags", []):
                    out.extend(cb.fcurves)
        return out


def find_fcurve(id_data, data_path, index=0):
    for fc in fcurves(id_data):
        if fc.data_path == data_path and fc.array_index == index:
            return fc
    return None


class _ItemRef:
    """Wraps owner[key] (ID/custom properties such as Geometry Nodes modifier inputs)."""
    def __init__(self, owner, key):
        self.owner, self.key = owner, key


def resolve_owner(id_data, data_path):
    """Split 'modifiers["Bevel"].width' -> (owner_struct, 'width').
    'modifiers["GN"]["Socket_2"]' -> (_ItemRef(modifier, 'Socket_2'), None)."""
    m = re.match(r'^(.*)\[(["\'])(.+?)\2\]$', data_path)
    if m and m.group(1):
        return _ItemRef(id_data.path_resolve(m.group(1)), m.group(3)), None
    if "." in data_path and not data_path.endswith("]"):
        head, attr = data_path.rsplit(".", 1)
        return id_data.path_resolve(head), attr
    return id_data, data_path


def get_value(owner, attr):
    return owner.owner[owner.key] if isinstance(owner, _ItemRef) else getattr(owner, attr)


def set_value(owner, attr, value):
    if isinstance(owner, _ItemRef):
        owner.owner[owner.key] = value
    else:
        setattr(owner, attr, value)


def set_key(id_data, data_path, value, frame, index=-1, easing=None):
    """Set value(s) and insert keyframe(s). value may be scalar or sequence.
    Applies interpolation/easing to the inserted keyframes."""
    owner, attr = resolve_owner(id_data, data_path)
    cur = get_value(owner, attr)
    is_seq = hasattr(cur, "__len__") and not isinstance(cur, str)
    if is_seq and index < 0:
        vals = list(value) if hasattr(value, "__len__") else [value] * len(cur)
        new = list(cur)
        for i, v in enumerate(vals[:len(cur)]):
            if v is not None:
                new[i] = v
        set_value(owner, attr, new)
        indices = [i for i, v in enumerate(vals[:len(cur)]) if v is not None]
    elif is_seq:
        new = list(cur)
        new[index] = value
        set_value(owner, attr, new)
        indices = [index]
    else:
        set_value(owner, attr, type(cur)(value) if isinstance(cur, (bool, int, float)) else value)
        indices = [-1]
    for i in indices:
        id_data.keyframe_insert(data_path=data_path, index=i, frame=frame)
    if easing is not None:
        interp, ease = parse_easing(easing)
        for i in indices:
            fc = find_fcurve(id_data, data_path, max(i, 0))
            if not fc:
                continue
            for kp in fc.keyframe_points:
                if abs(kp.co.x - frame) < 0.01:
                    kp.interpolation = interp
                    kp.easing = ease
                    if interp == "BEZIER":
                        kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"
            fc.update()


def set_cyclic(id_data, data_path=None):
    """Add a Cycles modifier to (matching) F-curves so they loop forever."""
    for fc in fcurves(id_data):
        if data_path and fc.data_path != data_path:
            continue
        if not any(m.type == "CYCLES" for m in fc.modifiers):
            fc.modifiers.new("CYCLES")


def scene_frames(state=None):
    sc = bpy.context.scene
    return sc.frame_start, sc.frame_end


# --------------------------------------------------------------------------- nodes
def node_input(node, name_or_index):
    """Get a node input by name (first enabled match) or index."""
    if isinstance(name_or_index, int):
        return node.inputs[name_or_index]
    cands = [s for s in node.inputs if s.name == name_or_index or s.identifier == name_or_index]
    enabled = [s for s in cands if getattr(s, "enabled", True)]
    if not (enabled or cands):
        raise KeyError(f"node {node.bl_idname} has no input '{name_or_index}'. Inputs: {[s.name for s in node.inputs]}")
    return (enabled or cands)[0]


def node_output(node, name_or_index):
    if isinstance(name_or_index, int):
        return node.outputs[name_or_index]
    cands = [s for s in node.outputs if s.name == name_or_index or s.identifier == name_or_index]
    enabled = [s for s in cands if getattr(s, "enabled", True)]
    if not (enabled or cands):
        raise KeyError(f"node {node.bl_idname} has no output '{name_or_index}'. Outputs: {[s.name for s in node.outputs]}")
    return (enabled or cands)[0]


def set_input(node, name, value):
    sock = node_input(node, name)
    dv = sock.default_value
    if hasattr(dv, "__len__") and not isinstance(dv, str):
        if isinstance(value, str) and len(dv) in (3, 4):
            value = color(value)[:len(dv)]
        elif isinstance(value, (int, float)):
            value = [value] * len(dv)
        else:
            value = list(value)
            if len(value) == 3 and len(dv) == 4:
                value.append(1.0)
    sock.default_value = value
    return sock


def build_node_graph(tree, spec, clear=False):
    """Build nodes from a JSON-friendly spec.

    spec = {"nodes": {"id": {"type": "ShaderNodeTexNoise", "inputs": {"Scale": 5},
                              "props": {"noise_dimensions": "4D"}, "location": [x, y]},
                      "r": {"type": "ShaderNodeValToRGB", "ramp": [[0, "#000000"], [1, "#ff00aa"]]}},
            "links": [["id.Out", "id2.In"], ...]}
    Existing nodes can be referenced by their Blender node name.
    Returns dict id -> node.
    """
    if clear:
        tree.nodes.clear()
    nodes = {}
    for nid, nd in (spec.get("nodes") or {}).items():
        n = tree.nodes.get(nid) if nd.get("type") is None else tree.nodes.new(nd["type"])
        if n is None:
            raise KeyError(f"node '{nid}' has no type and is not an existing node")
        n.name = nid
        n.label = nd.get("label", "")
        for k, v in (nd.get("props") or {}).items():
            setattr(n, k, v)
        for k, v in (nd.get("inputs") or {}).items():
            set_input(n, int(k) if str(k).isdigit() else k, v)
        if "location" in nd:
            n.location = nd["location"]
        if nd.get("ramp") and hasattr(n, "color_ramp"):  # [[pos, color], ...]
            els = n.color_ramp.elements
            while len(els) > 1:
                els.remove(els[-1])
            for i, (pos, col) in enumerate(nd["ramp"]):
                e = els[0] if i == 0 else els.new(float(pos))
                e.position = float(pos)
                e.color = color(col)
        nodes[nid] = n
    for link in spec.get("links") or []:
        a, b = link
        an, asock = a.split(".", 1)
        bn, bsock = b.split(".", 1)
        na = nodes.get(an) or tree.nodes[an]
        nb = nodes.get(bn) or tree.nodes[bn]
        asock = int(asock) if asock.isdigit() else asock
        bsock = int(bsock) if bsock.isdigit() else bsock
        tree.links.new(node_output(na, asock), node_input(nb, bsock))
    return nodes


def purge_orphans():
    try:
        bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    except Exception:
        pass
