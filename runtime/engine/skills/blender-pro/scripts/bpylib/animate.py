"""Animation: keyframes on any data path with easing, from/to tweens with stagger, fades,
F-curve noise, drivers, turntables, visibility, physics (rigid body, cloth, collision,
particles) and baking."""
import math

import bpy

from . import util
from .util import warn


# --------------------------------------------------------------------------- id resolution
def resolve_id(state, target, id_type="object", data_path=""):
    """Return the ID that owns data_path.
    id_type: object | data (object's data: camera lens, light energy, text body...) |
             material | world | scene | node_group.
    For material/world/light IDs a data_path starting with 'nodes' resolves on the node tree."""
    t = (id_type or "object").lower()
    if t == "object":
        idd = util.get_obj(state, target)
    elif t == "data":
        idd = util.get_obj(state, target).data
    elif t == "material":
        idd = util.get_mat(state, target)
    elif t == "world":
        idd = bpy.data.worlds[target] if target else bpy.context.scene.world
    elif t == "scene":
        idd = bpy.context.scene
    elif t == "node_group":
        idd = bpy.data.node_groups[target]
    else:
        raise ValueError("id_type must be object|data|material|world|scene|node_group")
    if data_path.startswith("nodes") and hasattr(idd, "node_tree") and idd.node_tree is not None:
        idd = idd.node_tree
    return idd


PROPERTY_ALIASES = {"rotation": "rotation_euler", "position": "location", "loc": "location", "rot": "rotation_euler"}


def _convert(prop, value):
    if prop == "rotation_euler" and value is not None:
        if isinstance(value, (int, float)):
            return math.radians(value)
        return [None if v is None else math.radians(v) for v in value]
    if prop == "scale" and isinstance(value, (int, float)):
        return [value] * 3
    return value


# --------------------------------------------------------------------------- keyframes
def keyframe(state, target=None, data_path="location", keys=None, index=-1, easing=None, id_type="object",
             degrees=None, cyclic=False, **_):
    """Insert keyframes on any data path.
    keys: [{"frame": 1, "value": [0,0,0], "easing": "expo_out"}, ...] - easing of a key affects the
    segment that STARTS at that key. degrees=True converts values to radians (auto for rotation_euler).
    Examples: data_path "modifiers[\"Bevel\"].width"; id_type "data" + "lens";
    id_type "material" + "nodes[\"Principled BSDF\"].inputs[\"Emission Strength\"].default_value"."""
    if not keys:
        raise ValueError("keys list required")
    path = PROPERTY_ALIASES.get(data_path, data_path)
    idd = resolve_id(state, target, id_type, path)
    to_rad = degrees if degrees is not None else path.endswith("rotation_euler")
    for k in keys:
        v = k["value"]
        if to_rad:
            v = math.radians(v) if isinstance(v, (int, float)) else [None if x is None else math.radians(x) for x in v]
        elif path == "scale" and isinstance(v, (int, float)) and index < 0:
            v = [v] * 3
        util.set_key(idd, path, v, int(k["frame"]) if float(k["frame"]).is_integer() else float(k["frame"]),
                     index=int(k.get("index", index)), easing=k.get("easing", easing))
    if cyclic:
        util.set_cyclic(idd, path)
    return {"id": idd.name, "data_path": path, "keys": len(keys)}


def animate(state, target=None, targets=None, property="location", from_value=None, to_value=None,
            frame_start=None, frame_end=None, duration=None, easing="smooth", stagger=0, relative=False,
            id_type="object", index=-1, order="as_given", hold=False, **_):
    """Tween a property from -> to between frames. Works on a list of targets with a per-target
    stagger (frames) - the motion-design workhorse.
    property: location | rotation (degrees) | scale (number = uniform) | alpha (object fade)
              | any data path (with id_type).
    relative=True: from/to are offsets added to the current value.
    order: as_given | reverse | x | -x (sort targets by X; use '-x' for right-to-left Arabic).
    from_value/to_value may be None to use the current value."""
    names = targets if targets is not None else target
    objs = names if isinstance(names, list) else [names]
    if order in ("x", "-x", "z", "-z"):
        axis = 0 if order.endswith("x") else 2
        objs = sorted(objs, key=lambda n: util.get_obj(state, n).matrix_world.translation[axis],
                      reverse=order.startswith("-"))
    elif order == "reverse":
        objs = list(reversed(objs))
    fs = int(frame_start if frame_start is not None else bpy.context.scene.frame_start)
    if frame_end is None:
        frame_end = fs + int(duration) if duration else bpy.context.scene.frame_end
    length = int(frame_end) - fs
    if property == "alpha":
        for i, n in enumerate(objs):
            s = fs + i * stagger
            fade(state, n, from_value if from_value is not None else 0.0,
                 to_value if to_value is not None else 1.0, s, s + length, easing)
        return {"targets": len(objs)}
    prop = PROPERTY_ALIASES.get(property, property)
    for i, n in enumerate(objs):
        idd = resolve_id(state, n, id_type, prop)
        owner, attr = util.resolve_owner(idd, prop)
        cur = util.get_value(owner, attr)
        curv = list(cur) if hasattr(cur, "__len__") and not isinstance(cur, str) else cur
        fv, tv = _convert(prop, from_value), _convert(prop, to_value)

        def combine(v):
            if v is None:
                return curv
            if not relative:
                return v
            if isinstance(curv, list):
                vv = v if isinstance(v, list) else [v] * len(curv)
                return [c + (x or 0) for c, x in zip(curv, vv)]
            return curv + v
        a, b = combine(fv), combine(tv)
        s = fs + i * stagger
        if hold and s > bpy.context.scene.frame_start:
            util.set_key(idd, prop, a, bpy.context.scene.frame_start, index=index, easing="constant")
        util.set_key(idd, prop, a, s, index=index, easing=easing)
        util.set_key(idd, prop, b, s + length, index=index, easing=easing)
    return {"targets": len(objs), "frames": [fs, fs + length + stagger * (len(objs) - 1)]}


def fade(state, target, from_value=0.0, to_value=1.0, frame_start=1, frame_end=24, easing="smooth", **_):
    """Fade object(s) via object color alpha (works with every bpylib material).
    For imported materials, wire Object Info > Alpha yourself."""
    for obj in util.get_objs(state, target):
        objs = [obj] + [c for c in obj.children_recursive]
        for o in objs:
            c = list(o.color)
            c[3] = float(from_value)
            o.color = c
            o.keyframe_insert("color", index=3, frame=int(frame_start))
            c[3] = float(to_value)
            o.color = c
            o.keyframe_insert("color", index=3, frame=int(frame_end))
            fc = util.find_fcurve(o, "color", 3)
            if fc:
                interp, ease = util.parse_easing(easing)
                for kp in fc.keyframe_points:
                    kp.interpolation, kp.easing = interp, ease
    return {"faded": util.get_objs(state, target)[0].name}


def noise(state, target, data_path="location", strength=0.1, scale=10.0, phase=None, index=-1, id_type="object",
          seed=0, frame_start=None, frame_end=None, blend_in=0, blend_out=0, **_):
    """Add an F-curve noise modifier (organic jitter / floating / flicker).
    strength in property units (degrees for rotation). scale = period in frames (bigger = slower).
    Keys the current value first if the property is not animated yet."""
    path = PROPERTY_ALIASES.get(data_path, data_path)
    idd = resolve_id(state, target, id_type, path)
    owner, attr = util.resolve_owner(idd, path)
    cur = util.get_value(owner, attr)
    n = len(cur) if hasattr(cur, "__len__") and not isinstance(cur, str) else 1
    indices = range(n) if index < 0 else [index]
    if path.endswith("rotation_euler"):
        strength = math.radians(strength)
    r = util.rng(seed)
    for i in indices:
        fc = util.find_fcurve(idd, path, i)
        if fc is None:
            idd.keyframe_insert(data_path=path, index=i if n > 1 else -1, frame=bpy.context.scene.frame_start)
            fc = util.find_fcurve(idd, path, i)
        m = fc.modifiers.new("NOISE")
        m.strength = float(strength) * 2  # blender strength is peak-to-peak
        m.scale = float(scale)
        m.phase = float(phase if phase is not None else r.uniform(0, 100))
        if frame_start is not None or frame_end is not None:
            m.use_restricted_range = True
            m.frame_start = float(frame_start if frame_start is not None else bpy.context.scene.frame_start)
            m.frame_end = float(frame_end if frame_end is not None else bpy.context.scene.frame_end)
            m.blend_in, m.blend_out = float(blend_in), float(blend_out)
    return {"id": idd.name, "data_path": path}


def driver(state, target, data_path, expression, index=-1, id_type="object", **_):
    """Add a scripted driver. Simple expressions (frame, sin, cos, pi, min, max...) run without
    auto-exec, e.g. "sin(frame/12)*0.5". Values in radians for rotations."""
    path = PROPERTY_ALIASES.get(data_path, data_path)
    idd = resolve_id(state, target, id_type, path)
    res = idd.driver_add(path, index) if index >= 0 else idd.driver_add(path)
    fcs = res if isinstance(res, list) else [res]
    for fc in fcs:
        fc.driver.type = "SCRIPTED"
        fc.driver.expression = expression
    return {"id": idd.name, "drivers": len(fcs)}


def turntable(state, target, frame_start=None, frame_end=None, degrees=360.0, axis="Z", easing="linear",
              cyclic=True, **_):
    """Rotate target around an axis over the frame range (seamless loop with linear easing)."""
    obj = util.get_obj(state, target)
    fs = int(frame_start or bpy.context.scene.frame_start)
    fe = int(frame_end or bpy.context.scene.frame_end)
    i = "XYZ".index(axis.upper())
    start = obj.rotation_euler[i]
    util.set_key(obj, "rotation_euler", start, fs, index=i, easing=easing)
    # loop end lands one frame after the last rendered frame so frame fe != frame fs
    util.set_key(obj, "rotation_euler", start + math.radians(degrees), fe + (1 if cyclic else 0), index=i, easing=easing)
    if cyclic:
        util.set_cyclic(obj, "rotation_euler")
    return {"object": obj.name}


def visibility(state, target, keys=None, frame=None, visible=True, **_):
    """Keyframe render+viewport visibility. keys: [{"frame": 1, "visible": false}, ...]."""
    keys = keys or [{"frame": frame, "visible": visible}]
    for obj in util.get_objs(state, target):
        for k in keys:
            obj.hide_render = not k["visible"]
            obj.hide_viewport = not k["visible"]
            obj.keyframe_insert("hide_render", frame=int(k["frame"]))
            obj.keyframe_insert("hide_viewport", frame=int(k["frame"]))
    return {}


# --------------------------------------------------------------------------- physics
def _physics_world(frame_start=None, frame_end=None):
    sc = bpy.context.scene
    if sc.rigidbody_world is None:
        with bpy.context.temp_override(scene=sc):
            bpy.ops.rigidbody.world_add()
    rw = sc.rigidbody_world
    if rw.collection is None:
        rw.collection = util.get_collection("RigidBodyWorld")
    rw.point_cache.frame_start = int(frame_start or sc.frame_start)
    rw.point_cache.frame_end = int(frame_end or sc.frame_end)
    return rw


def rigid_body(state, target=None, targets=None, type="ACTIVE", mass=1.0, friction=0.5, bounciness=0.2,
               shape="CONVEX_HULL", margin=0.0, damping=0.1, animated=False, **_):
    """Make object(s) rigid bodies. type ACTIVE (falls) | PASSIVE (static collider: floors).
    shape: CONVEX_HULL | MESH | BOX | SPHERE | CYLINDER | CAPSULE | CONE."""
    rw = _physics_world()
    names = []
    for obj in util.get_objs(state, targets or target):
        if obj.name not in rw.collection.objects:
            rw.collection.objects.link(obj)
        rb = obj.rigid_body
        if rb is None:
            raise RuntimeError(f"could not add rigid body to {obj.name} (type {obj.type}; mesh required)")
        rb.type = type.upper()
        rb.mass = float(mass)
        rb.friction = float(friction)
        rb.restitution = float(bounciness)
        rb.collision_shape = shape.upper()
        rb.linear_damping = rb.angular_damping = float(damping)
        rb.kinematic = bool(animated)
        if margin:
            rb.use_margin, rb.collision_margin = True, float(margin)
        names.append(obj.name)
    return {"rigid_bodies": names}


def rigid_drop(state, source, count=20, area=(4, 4), height=(3, 8), seed=3, floor=True, floor_size=30,
               mass=1.0, bounciness=0.3, name="Drop", **_):
    """Rain copies of source onto a floor (rigid body). Creates a passive floor if floor=True."""
    from . import objects
    src = util.get_obj(state, source)
    r = util.rng(seed)
    made = []
    for i in range(int(count)):
        n = objects.duplicate(state, src.name, name=f"{name}_{i:03d}", linked=True,
                              location=[r.uniform(-area[0] / 2, area[0] / 2), r.uniform(-area[1] / 2, area[1] / 2),
                                        r.uniform(height[0], height[1])],
                              rotation=[r.uniform(0, 360) for _ in range(3)])
        made.append(n)
    src.hide_render = src.hide_viewport = True
    rigid_body(state, targets=made, mass=mass, bounciness=bounciness)
    if floor:
        fl = state["objects"].get("Floor") or util.get_obj(state, objects.floor(state, name="Floor", size=floor_size))
        rigid_body(state, target=fl.name, type="PASSIVE", shape="BOX")
    return made


def collision(state, target, thickness=0.02, friction=0.5, **_):
    """Make object a collider for cloth/particles."""
    for obj in util.get_objs(state, target):
        if not any(m.type == "COLLISION" for m in obj.modifiers):
            obj.modifiers.new("Collision", "COLLISION")
        obj.collision.thickness_outer = float(thickness)
        obj.collision.cloth_friction = float(friction) * 10
    return {}


def cloth(state, target, quality=6, mass=0.3, stiffness=15.0, pin_group=None, self_collision=False,
          frame_start=None, frame_end=None, preset=None, **_):
    """Cloth simulation on a (subdivided) mesh. preset: silk | cotton | leather | denim."""
    presets = {"silk": (0.15, 5.0), "cotton": (0.3, 15.0), "leather": (0.4, 80.0), "denim": (1.0, 40.0)}
    if preset:
        mass, stiffness = presets[preset]
    obj = util.get_obj(state, target)
    m = obj.modifiers.new("Cloth", "CLOTH")
    s = m.settings
    s.quality = int(quality)
    s.mass = float(mass)
    s.tension_stiffness = s.compression_stiffness = s.shear_stiffness = float(stiffness)
    s.bending_stiffness = float(stiffness) / 30
    if pin_group:
        s.vertex_group_mass = pin_group
    m.collision_settings.use_self_collision = bool(self_collision)
    sc = bpy.context.scene
    m.point_cache.frame_start = int(frame_start or sc.frame_start)
    m.point_cache.frame_end = int(frame_end or sc.frame_end)
    return {"object": obj.name}


def particles(state, emitter, count=500, frame_start=None, frame_end=None, lifetime=60, velocity=1.0,
              normal_velocity=None, random_velocity=0.3, gravity=1.0, size=0.05, size_random=0.5,
              instance=None, collection=None, emit_from="FACE", seed=0, render_emitter=False, rotation=True,
              **_):
    """Particle system on an emitter mesh. instance: object name rendered per particle (default a
    small ico sphere). gravity 0 = floating dust/embers."""
    from . import objects
    obj = util.get_obj(state, emitter)
    sc = bpy.context.scene
    mod = obj.modifiers.new("Particles", "PARTICLE_SYSTEM")
    psys = mod.particle_system
    ps = psys.settings
    psys.seed = int(seed)
    ps.count = int(count)
    ps.frame_start = float(frame_start or sc.frame_start)
    ps.frame_end = float(frame_end or sc.frame_end)
    ps.lifetime = float(lifetime)
    ps.emit_from = emit_from
    ps.normal_factor = float(normal_velocity if normal_velocity is not None else velocity)
    ps.factor_random = float(random_velocity)
    ps.effector_weights.gravity = float(gravity)
    ps.particle_size = float(size)
    ps.size_random = float(size_random)
    ps.use_rotations = bool(rotation)
    if rotation:
        ps.rotation_factor_random = 1.0
    if collection:
        ps.render_type = "COLLECTION"
        ps.instance_collection = bpy.data.collections[collection]
    else:
        if instance is None:
            instance = objects.add_primitive(state, "ico_sphere", name=f"{obj.name}_particle", size=1.0,
                                             subdivisions=1, location=(0, 0, -1000))
            util.get_obj(state, instance).hide_render = True
        inst = util.get_obj(state, instance)
        ps.render_type = "OBJECT"
        ps.instance_object = inst
    obj.show_instancer_for_render = bool(render_emitter)
    return {"emitter": obj.name, "system": psys.name}


def bake_physics(state, **_):
    """Bake all point caches (rigid body, cloth, particles) for the scene frame range."""
    sc = bpy.context.scene
    try:
        with bpy.context.temp_override(scene=sc):
            bpy.ops.ptcache.bake_all(bake=True)
        return {"baked": True}
    except Exception as e:  # fall back to stepping frames, which fills caches in order
        warn(f"bake_all failed ({e}); stepping frames to fill caches")
        for f in range(sc.frame_start, sc.frame_end + 1):
            sc.frame_set(f)
        sc.frame_set(sc.frame_start)
        return {"baked": "stepped"}


OPS = {
    "keyframe": keyframe,
    "animate": animate,
    "fade": fade,
    "noise": noise,
    "driver": driver,
    "turntable": turntable,
    "visibility": visibility,
    "rigid_body": rigid_body,
    "rigid_drop": rigid_drop,
    "collision": collision,
    "cloth": cloth,
    "particles": particles,
    "bake_physics": bake_physics,
}
