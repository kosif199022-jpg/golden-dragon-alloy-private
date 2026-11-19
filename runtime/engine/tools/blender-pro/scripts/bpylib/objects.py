"""Objects: primitives, imports (obj/fbx/glb/stl/ply/usd/abc/svg/image planes), modifiers,
transforms, parenting, duplication, instancing and scatter, curves and backdrops."""
import math
import os

import bmesh
import bpy
import mathutils

from . import util
from .util import log, warn


# --------------------------------------------------------------------------- helpers
def _finish(state, obj, name=None, location=None, rotation=None, scale=None, material=None,
            smooth=None, collection=None, parent=None):
    if name:
        obj.name = name
        if obj.data is not None and hasattr(obj.data, "name"):
            obj.data.name = name
    util.set_transform(obj, location, rotation, scale)
    if collection:
        coll = util.get_collection(collection)
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        coll.objects.link(obj)
    if smooth is not None and obj.type == "MESH":
        shade_smooth(state, obj, smooth=bool(smooth))
    if material:
        from . import materials
        materials.assign(state, obj, material)
    if parent:
        set_parent(state, child=obj, parent=parent)
    util.register(state, obj, obj.name)
    return obj


def _alive(obj):
    try:
        obj.name  # noqa: B018
        return True
    except ReferenceError:
        return False


def _mesh_from_bmesh(name, build):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    build(bm)
    bm.to_mesh(me)
    bm.free()
    return me


# --------------------------------------------------------------------------- primitives
def add_primitive(state, type="cube", name=None, size=1.0, location=None, rotation=None, scale=None,
                  segments=48, rings=24, subdivisions=3, radius=None, depth=None, major_radius=None,
                  minor_radius=None, material=None, smooth=None, bevel=None, subdivide=None,
                  collection=None, parent=None, **_):
    """Add a mesh primitive without bpy.ops (context-free, fast).

    type: cube | plane | uv_sphere (sphere) | ico_sphere | cylinder | cone | torus | circle | grid | monkey
    size: edge length (cube/plane/grid) or diameter (spheres, cylinder, cone, circle).
    bevel: width (float) or dict for the bevel modifier; subdivide: levels int.
    """
    t = type.lower()
    r = float(radius) if radius is not None else float(size) / 2.0
    d = float(depth) if depth is not None else float(size)
    name = name or t.capitalize()

    def build(bm):
        if t == "cube":
            bmesh.ops.create_cube(bm, size=float(size))
        elif t == "plane":
            bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=float(size) / 2)
        elif t == "grid":
            bmesh.ops.create_grid(bm, x_segments=int(segments), y_segments=int(segments), size=float(size) / 2)
        elif t in ("sphere", "uv_sphere"):
            bmesh.ops.create_uvsphere(bm, u_segments=int(segments), v_segments=int(rings), radius=r)
        elif t == "ico_sphere":
            bmesh.ops.create_icosphere(bm, subdivisions=int(subdivisions), radius=r)
        elif t == "cylinder":
            bmesh.ops.create_cone(bm, cap_ends=True, segments=int(segments), radius1=r, radius2=r, depth=d)
        elif t == "cone":
            bmesh.ops.create_cone(bm, cap_ends=True, segments=int(segments), radius1=r, radius2=0.0, depth=d)
        elif t == "circle":
            bmesh.ops.create_circle(bm, cap_ends=True, segments=int(segments), radius=r)
        elif t == "monkey":
            bmesh.ops.create_monkey(bm)
            if size != 1.0:
                bmesh.ops.scale(bm, vec=(size / 2,) * 3, verts=bm.verts)
        elif t == "torus":
            R = float(major_radius) if major_radius is not None else r * 0.75
            rr = float(minor_radius) if minor_radius is not None else r * 0.25
            _torus(bm, R, rr, int(segments), max(12, int(rings)))
        else:
            raise ValueError("type must be cube|plane|grid|sphere|uv_sphere|ico_sphere|cylinder|cone|torus|circle|monkey")

    me = _mesh_from_bmesh(name, build)
    if t in ("sphere", "uv_sphere", "ico_sphere", "torus", "monkey") and smooth is None:
        smooth = True
    obj = util.new_object(name, me)
    _uv_unwrap_simple(obj)
    if bevel:
        add_modifier(state, obj, "BEVEL", **(bevel if isinstance(bevel, dict) else {"width": float(bevel)}))
    if subdivide:
        add_modifier(state, obj, "SUBSURF", levels=int(subdivide), render_levels=int(subdivide))
    return _finish(state, obj, name, location, rotation, scale, material, smooth, collection, parent).name


def _torus(bm, R, r, seg, ring):
    verts = []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        row = []
        for j in range(ring):
            b = 2 * math.pi * j / ring
            x = (R + r * math.cos(b)) * math.cos(a)
            y = (R + r * math.cos(b)) * math.sin(a)
            z = r * math.sin(b)
            row.append(bm.verts.new((x, y, z)))
        verts.append(row)
    for i in range(seg):
        for j in range(ring):
            bm.faces.new((verts[i][j], verts[(i + 1) % seg][j], verts[(i + 1) % seg][(j + 1) % ring], verts[i][(j + 1) % ring]))


def _uv_unwrap_simple(obj):
    """Cheap box-projected UVs so image textures work without bpy.ops."""
    me = obj.data
    if me.uv_layers:
        return
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        n = poly.normal
        ax = max(range(3), key=lambda k: abs(n[k]))
        u_i, v_i = [(1, 2), (0, 2), (0, 1)][ax]
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = (co[u_i] + 0.5, co[v_i] + 0.5)


def rounded_box(state, size=(1, 1, 1), radius=0.08, segments=6, name="RoundedBox", **kw):
    """Box with beveled (rounded) edges. size [x, y, z]."""
    s = util.vec3(size)
    n = add_primitive(state, "cube", name=name, size=1.0, smooth=True,
                      bevel={"width": float(radius), "segments": int(segments)}, **kw)
    obj = util.get_obj(state, n)
    obj.data.transform(mathutils.Matrix.Diagonal((s.x, s.y, s.z, 1)))
    return n


def empty(state, name="Empty", location=None, rotation=None, display="PLAIN_AXES", size=1.0, **_):
    obj = util.new_object(name, None)
    obj.empty_display_type = display
    obj.empty_display_size = size
    util.set_transform(obj, location, rotation)
    return util.register(state, obj, obj.name).name


def backdrop(state, name="Backdrop", width=30.0, depth=20.0, height=12.0, curve_radius=4.0, location=(0, 0, 0),
             rotation_z=0.0, material=None, color="#16171b", roughness=0.45, **_):
    """Seamless curved studio backdrop (cyclorama): floor that sweeps up into a wall behind
    the subject (wall faces +Y direction toward camera at -Y)."""
    segs = 16
    prof = []  # profile in (y, z)
    prof.append((-depth / 2, 0.0))
    y0 = depth / 2 - curve_radius
    prof.append((y0, 0.0))
    for i in range(1, segs + 1):
        a = (math.pi / 2) * i / segs
        prof.append((y0 + math.sin(a) * curve_radius, curve_radius - math.cos(a) * curve_radius))
    prof.append((y0 + curve_radius, height))

    def build(bm):
        rows = []
        for x in (-width / 2, width / 2):
            rows.append([bm.verts.new((x, y, z)) for y, z in prof])
        for k in range(len(prof) - 1):
            bm.faces.new((rows[0][k], rows[1][k], rows[1][k + 1], rows[0][k + 1]))

    me = _mesh_from_bmesh(name, build)
    for p in me.polygons:
        p.use_smooth = True
    obj = util.new_object(name, me)
    obj.location = util.vec3(location)
    obj.rotation_euler[2] = math.radians(rotation_z)
    obj["blpro_backdrop"] = True
    from . import materials
    if material:
        materials.assign(state, obj, material)
    else:
        m = materials.make_material(state, name=name + "_mat", preset="matte", color=color, roughness=roughness)
        materials.assign(state, obj, m)
    return util.register(state, obj, name).name


def floor(state, name="Floor", size=60.0, location=(0, 0, 0), material=None, color="#111214",
          roughness=0.35, shadow_catcher=False, **_):
    """Large ground plane. shadow_catcher=True makes it only catch shadows (Cycles, film transparent)."""
    n = add_primitive(state, "plane", name=name, size=size, location=location)
    obj = util.get_obj(state, n)
    obj["blpro_backdrop"] = True
    from . import materials
    if material:
        materials.assign(state, obj, material)
    else:
        materials.assign(state, obj, materials.make_material(state, name=name + "_mat", preset="matte",
                                                             color=color, roughness=roughness))
    if shadow_catcher:
        obj.is_shadow_catcher = True
    return n


# --------------------------------------------------------------------------- import
def import_model(state, path, name=None, location=None, rotation=None, scale=None, normalize=None,
                 material=None, smooth=None, join=False, extrude=None, svg_scale=None, **_):
    """Import obj/fbx/glb/gltf/stl/ply/usd(a/c/z)/abc/svg/blend(append objects).

    normalize: fit the import into a cube of this size (e.g. 2.0) and drop it onto z=0.
    svg: curves are created; extrude (float) gives them depth; svg_scale multiplies size.
    Returns the name of the root (a parent empty when several objects were imported, unless join).
    """
    p = util.resolve_path(state, path)
    ext = os.path.splitext(p)[1].lower()
    before = set(bpy.data.objects)
    if ext == ".obj":
        bpy.ops.wm.obj_import(filepath=p)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=p)
    elif ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=p)
    elif ext == ".stl":
        bpy.ops.wm.stl_import(filepath=p)
    elif ext == ".ply":
        bpy.ops.wm.ply_import(filepath=p)
    elif ext in (".usd", ".usda", ".usdc", ".usdz"):
        bpy.ops.wm.usd_import(filepath=p)
    elif ext == ".abc":
        bpy.ops.wm.alembic_import(filepath=p)
    elif ext == ".svg":
        bpy.ops.import_curve.svg(filepath=p)
    elif ext == ".blend":
        with bpy.data.libraries.load(p, link=False) as (src, dst):
            dst.objects = list(src.objects)
        for o in dst.objects:
            if o is not None:
                util.link_object(o)
    else:
        raise ValueError(f"unsupported import format {ext}")
    new = [o for o in bpy.data.objects if o not in before]
    if not new:
        raise RuntimeError(f"import produced no objects: {p}")
    if ext == ".svg":
        for o in new:
            if o.type == "CURVE":
                o.data.dimensions = "2D"
                o.data.fill_mode = "BOTH"
                if extrude:
                    o.data.extrude = float(extrude)
            s = float(svg_scale or 1.0)
            o.scale = (o.scale[0] * s, o.scale[1] * s, o.scale[2] * s)
    base = name or os.path.splitext(os.path.basename(p))[0]
    if join and len([o for o in new if o.type == "MESH"]) > 1:
        meshes = [o for o in new if o.type == "MESH"]
        with bpy.context.temp_override(**util.op_context(meshes[0], meshes)):
            bpy.ops.object.join()
        new = [o for o in new if _alive(o)]
    roots = [o for o in new if o.parent is None or o.parent not in new]
    if len(roots) == 1:
        root = roots[0]
        root.name = base
    else:
        root = util.new_object(base, None)
        for o in roots:
            o.parent = root
    for o in new:
        util.register(state, o, o.name)
    if normalize:
        bpy.context.view_layer.update()
        mn, mx = util.world_bbox([o for o in new if o.name in bpy.data.objects] + [root])
        dim = max((mx - mn)) or 1.0
        f = float(normalize) / dim
        root.scale = root.scale * f
        bpy.context.view_layer.update()
        mn, mx = util.world_bbox([o for o in new if o.name in bpy.data.objects])
        c = (mn + mx) / 2
        root.location -= mathutils.Vector((c.x, c.y, mn.z))
    if location is not None:
        root.location += util.vec3(location)
    if rotation is not None:
        root.rotation_euler = util.rad3(rotation)
    if scale is not None:
        root.scale = root.scale * util.scale3(scale)[0] if isinstance(scale, (int, float)) else util.scale3(scale)
    if material:
        from . import materials
        for o in new:
            if o.type in ("MESH", "CURVE", "FONT"):
                materials.assign(state, o, material)
    if smooth is not None:
        for o in new:
            if o.type == "MESH":
                shade_smooth(state, o, smooth=bool(smooth))
    util.register(state, root, root.name)
    log(f"imported {len(new)} object(s) from {os.path.basename(p)} -> root '{root.name}'")
    return root.name


def image_plane(state, path, name=None, height=2.0, location=None, rotation=(90, 0, 0), emission=False,
                emission_strength=1.0, alpha=True, double_sided=True, video=False, **_):
    """Plane with the image (or video when video=True or .mp4/.mov) mapped at correct aspect.
    Default rotation stands it upright facing -Y (toward a camera on -Y)."""
    from . import materials
    p = util.resolve_path(state, path)
    is_video = video or os.path.splitext(p)[1].lower() in (".mp4", ".mov", ".mkv", ".webm", ".avi", ".gif")
    img = bpy.data.images.load(p, check_existing=True)
    if is_video:
        img.source = "MOVIE"
    w, h = img.size[:] if img.size[0] else (1, 1)
    aspect = w / h if h else 1.0
    name = name or os.path.splitext(os.path.basename(p))[0]
    me = _mesh_from_bmesh(name, lambda bm: bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5))
    me.transform(mathutils.Matrix.Diagonal((height * aspect, height, 1, 1)))
    obj = util.new_object(name, me)
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = (co.x / (height * aspect) + 0.5, co.y / height + 0.5)
    mat = materials.image_material(state, path=p, name=name + "_mat", emission=emission,
                                   emission_strength=emission_strength, alpha=alpha, video=is_video)
    materials.assign(state, obj, mat)
    util.set_transform(obj, location, rotation)
    return util.register(state, obj, name).name


# --------------------------------------------------------------------------- modifiers
MOD_ALIASES = {"subdivision": "SUBSURF", "subsurf": "SUBSURF", "subdivide": "SUBSURF", "displacement": "DISPLACE",
               "displace": "DISPLACE", "bevel": "BEVEL", "array": "ARRAY", "solidify": "SOLIDIFY",
               "boolean": "BOOLEAN", "mirror": "MIRROR", "wireframe": "WIREFRAME", "remesh": "REMESH",
               "screw": "SCREW", "simple_deform": "SIMPLE_DEFORM", "curve": "CURVE", "weld": "WELD",
               "smooth": "SMOOTH", "decimate": "DECIMATE", "triangulate": "TRIANGULATE", "wave": "WAVE",
               "cast": "CAST", "shrinkwrap": "SHRINKWRAP", "lattice": "LATTICE", "edge_split": "EDGE_SPLIT"}


def add_modifier(state, target, type, name=None, **props):
    """Add any modifier. type: friendly alias or Blender id (BEVEL, SUBSURF, ARRAY, SOLIDIFY,
    BOOLEAN, DISPLACE, MIRROR, WIREFRAME, REMESH, SCREW, SIMPLE_DEFORM, WAVE, ...).
    Object-valued props (object, offset_object, start_cap, curve...) accept names.
    Special props: texture {type:'CLOUDS'|..., noise_scale, ...} for DISPLACE;
    angle-like props (angle_limit, angle, deform angle) are DEGREES."""
    obj = util.get_obj(state, target)
    mtype = MOD_ALIASES.get(str(type).lower(), str(type).upper())
    mod = obj.modifiers.new(name or mtype.title(), mtype)
    tex = props.pop("texture", None)
    for k, v in props.items():
        if not hasattr(mod, k):
            warn(f"modifier {mtype} has no property '{k}' (ignored)")
            continue
        cur = getattr(mod, k)
        if isinstance(cur, bpy.types.Object) or (cur is None and isinstance(v, str) and k in (
                "object", "offset_object", "start_cap", "end_cap", "mirror_object", "target", "origin", "curve_object")):
            v = util.get_obj(state, v)
        elif isinstance(v, str) and k == "collection":
            v = bpy.data.collections[v]
        elif k in ("angle_limit", "angle", "split_angle") and isinstance(v, (int, float)):
            v = math.radians(v)
        setattr(mod, k, v)
    if tex is not None and hasattr(mod, "texture"):
        tex = dict(tex) if isinstance(tex, dict) else {"type": str(tex)}
        t = bpy.data.textures.new(f"{obj.name}_{mtype}_tex", tex.pop("type", "CLOUDS").upper())
        for k, v in tex.items():
            if hasattr(t, k):
                setattr(t, k, v)
        mod.texture = t
        if hasattr(mod, "texture_coords"):
            mod.texture_coords = "GLOBAL" if props.get("texture_coords") is None else props["texture_coords"]
    return {"object": obj.name, "modifier": mod.name}


def _wrap(mtype, defaults):
    def fn(state, target, **params):
        p = dict(defaults)
        p.update(params)
        return add_modifier(state, target, mtype, **p)
    fn.__doc__ = f"Add a {mtype} modifier. Defaults: {defaults}. Any modifier property can be passed."
    fn.__name__ = mtype.lower()
    return fn


bevel = _wrap("BEVEL", {"width": 0.03, "segments": 4, "limit_method": "ANGLE", "harden_normals": False})
subdivision = _wrap("SUBSURF", {"levels": 2, "render_levels": 2})
array = _wrap("ARRAY", {"count": 5, "relative_offset_displace": [1.1, 0, 0]})
solidify = _wrap("SOLIDIFY", {"thickness": 0.05})
displace = _wrap("DISPLACE", {"strength": 0.3, "texture": {"type": "CLOUDS", "noise_scale": 0.6}})


def boolean(state, target, cutter, operation="DIFFERENCE", solver="EXACT", hide_cutter=True, apply=False, **_):
    """Boolean target with cutter object (DIFFERENCE|UNION|INTERSECT)."""
    obj = util.get_obj(state, target)
    cut = util.get_obj(state, cutter)
    mod = obj.modifiers.new("Boolean", "BOOLEAN")
    mod.operation = operation.upper()
    try:
        mod.solver = solver.upper()
    except TypeError:
        pass
    mod.object = cut
    if hide_cutter:
        cut.hide_render = True
        cut.display_type = "WIRE"
    if apply:
        apply_modifiers(state, obj.name)
    return {"object": obj.name, "modifier": mod.name}


def apply_modifiers(state, target, **_):
    """Apply (bake) all modifiers into the mesh using the evaluated depsgraph."""
    obj = util.get_obj(state, target)
    deps = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(obj.evaluated_get(deps), preserve_all_data_layers=True, depsgraph=deps)
    obj.modifiers.clear()
    old = obj.data
    obj.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)
    return {"object": obj.name}


def shade_smooth(state, target, smooth=True, auto_angle=None, **_):
    """Smooth/flat shading. auto_angle (degrees) adds 'Smooth by Angle' behavior via edge split."""
    obj = util.get_obj(state, target)
    if obj.type == "MESH":
        vals = [bool(smooth)] * len(obj.data.polygons)
        obj.data.polygons.foreach_set("use_smooth", vals)
        obj.data.update()
        if smooth and auto_angle:
            m = obj.modifiers.new("AutoSmooth", "EDGE_SPLIT")
            m.split_angle = math.radians(auto_angle)
    return {"object": obj.name}


# --------------------------------------------------------------------------- transforms & hierarchy
def transform(state, target, location=None, rotation=None, scale=None, offset=None, rotate_by=None, **_):
    """Set absolute location/rotation(deg)/scale and/or relative offset/rotate_by(deg)."""
    for obj in util.get_objs(state, target):
        util.set_transform(obj, location, rotation, scale)
        if offset is not None:
            obj.location += util.vec3(offset)
        if rotate_by is not None:
            r = util.rad3(rotate_by)
            obj.rotation_euler = (obj.rotation_euler[0] + r[0], obj.rotation_euler[1] + r[1], obj.rotation_euler[2] + r[2])
    return {"objects": [o.name for o in util.get_objs(state, target)]}


def set_parent(state, child, parent, keep_transform=True, **_):
    par = util.get_obj(state, parent)
    for c in util.get_objs(state, child):
        mw = c.matrix_world.copy()
        c.parent = par
        if keep_transform:
            c.matrix_parent_inverse = par.matrix_world.inverted()
            c.matrix_world = mw
    return {"parent": par.name}


def duplicate(state, target, name=None, linked=False, location=None, rotation=None, scale=None, offset=None, **_):
    src = util.get_obj(state, target)
    obj = src.copy()
    if src.data is not None and not linked:
        obj.data = src.data.copy()
    for coll in src.users_collection:
        coll.objects.link(obj)
    obj.name = name or (src.name + "_copy")
    util.set_transform(obj, location, rotation, scale)
    if offset is not None:
        obj.location += util.vec3(offset)
    return util.register(state, obj, obj.name).name


def delete(state, target, **_):
    names = []
    for obj in util.get_objs(state, target):
        names.append(obj.name)
        state.get("objects", {}).pop(obj.name, None)
        bpy.data.objects.remove(obj, do_unlink=True)
    return {"deleted": names}


def hide(state, target, render=True, viewport=True, **_):
    for obj in util.get_objs(state, target):
        obj.hide_render = render
        obj.hide_viewport = viewport
    return {}


def set_origin(state, target, mode="BOUNDS_CENTER", **_):
    """Move origin: BOUNDS_CENTER | BOTTOM (center of bottom face) | WORLD_ORIGIN. Keeps geometry in place."""
    obj = util.get_obj(state, target)
    if obj.type != "MESH":
        raise ValueError("set_origin supports mesh objects")
    me = obj.data
    cos = [v.co for v in me.vertices]
    mn = mathutils.Vector([min(c[i] for c in cos) for i in range(3)])
    mx = mathutils.Vector([max(c[i] for c in cos) for i in range(3)])
    if mode.upper() == "WORLD_ORIGIN":
        pivot_world = mathutils.Vector((0, 0, 0))
        pivot = obj.matrix_world.inverted() @ pivot_world
    else:
        pivot = (mn + mx) / 2
        if mode.upper() == "BOTTOM":
            pivot.z = mn.z
    me.transform(mathutils.Matrix.Translation(-pivot))
    obj.location = obj.matrix_world @ pivot
    return {"object": obj.name}


# --------------------------------------------------------------------------- instancing / scatter
def instance_grid(state, source, count=(5, 5, 1), spacing=(1.2, 1.2, 1.2), name="Grid", center=True,
                  linked=True, location=(0, 0, 0), random_scale=0.0, random_rotation=0.0, seed=0, **_):
    """Grid of linked duplicates of source (count [x,y,z], spacing [x,y,z]). Returns parent empty name."""
    src = util.get_obj(state, source)
    cnt = [int(c) for c in util.vec3(count, (1, 1, 1))]
    cnt = [max(1, c) for c in cnt]
    sp = util.vec3(spacing)
    root = util.get_obj(state, empty(state, name=name, location=location))
    r = util.rng(seed)
    off = mathutils.Vector([(cnt[i] - 1) * sp[i] / 2 if center else 0 for i in range(3)])
    k = 0
    for ix in range(cnt[0]):
        for iy in range(cnt[1]):
            for iz in range(cnt[2]):
                o = src.copy()
                if not linked and src.data is not None:
                    o.data = src.data.copy()
                util.link_object(o)
                o.name = f"{name}_{k:04d}"
                o.parent = root
                o.location = mathutils.Vector((ix * sp[0], iy * sp[1], iz * sp[2])) - off
                if random_scale:
                    s = 1.0 + r.uniform(-random_scale, random_scale)
                    o.scale = src.scale * s
                if random_rotation:
                    o.rotation_euler = [math.radians(r.uniform(-random_rotation, random_rotation)) for _ in range(3)]
                util.register(state, o, o.name)
                k += 1
    src.hide_render = True
    src.hide_viewport = True
    state.setdefault("vars", {})[name + "_count"] = k
    return root.name


def scatter(state, source, count=50, area=(10, 10, 0), center=(0, 0, 0), seed=1, scale_min=0.6, scale_max=1.2,
            random_rotation=(0, 0, 360), name="Scatter", surface=None, min_distance=0.0, hide_source=True, **_):
    """Random linked duplicates of source inside a box (area [x,y,z]) or on a surface object's faces.
    random_rotation: max degrees per axis. For dense scatters (1000s) use geonodes.gn_scatter."""
    src = util.get_obj(state, source)
    r = util.rng(seed)
    root = util.get_obj(state, empty(state, name=name))
    pts = []
    if surface:
        surf = util.get_obj(state, surface)
        deps = bpy.context.evaluated_depsgraph_get()
        me = surf.evaluated_get(deps).to_mesh()
        me.calc_loop_triangles()
        tris = list(me.loop_triangles)
        areas = [t.area for t in tris]
        total = sum(areas) or 1.0
        mw = surf.matrix_world
        for _ in range(int(count) * 4):
            if len(pts) >= count:
                break
            x = r.random() * total
            acc = 0.0
            for t, a in zip(tris, areas):
                acc += a
                if acc >= x:
                    break
            a, b, c = (me.vertices[i].co for i in t.vertices)
            u, v = r.random(), r.random()
            if u + v > 1:
                u, v = 1 - u, 1 - v
            p = mw @ (a + (b - a) * u + (c - a) * v)
            if min_distance and any((p - q).length < min_distance for q in pts):
                continue
            pts.append(p)
        surf.evaluated_get(deps).to_mesh_clear()
    else:
        ar, c0 = util.vec3(area), util.vec3(center)
        for _ in range(int(count) * 20):
            if len(pts) >= count:
                break
            p = c0 + mathutils.Vector([r.uniform(-ar[i] / 2, ar[i] / 2) for i in range(3)])
            if min_distance and any((p - q).length < min_distance for q in pts):
                continue
            pts.append(p)
    rr = util.vec3(random_rotation)
    for k, p in enumerate(pts):
        o = src.copy()
        util.link_object(o)
        o.name = f"{name}_{k:04d}"
        o.parent = root
        o.location = p
        s = r.uniform(scale_min, scale_max)
        o.scale = src.scale * s
        o.rotation_euler = [math.radians(r.uniform(-rr[i], rr[i])) for i in range(3)]
        util.register(state, o, o.name)
    if hide_source:
        src.hide_render = True
        src.hide_viewport = True
    return root.name


# --------------------------------------------------------------------------- curves
def curve_path(state, points, name="Path", closed=False, bevel_depth=0.0, bevel_resolution=4, smooth=True,
               material=None, resolution=24, **_):
    """Bezier/poly curve through points [[x,y,z],...]. bevel_depth>0 makes a tube (great for neon)."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.resolution_u = int(resolution)
    cu.bevel_depth = float(bevel_depth)
    cu.bevel_resolution = int(bevel_resolution)
    cu.use_fill_caps = True
    if smooth:
        sp = cu.splines.new("BEZIER")
        sp.bezier_points.add(len(points) - 1)
        for bp, p in zip(sp.bezier_points, points):
            bp.co = util.vec3(p)
            bp.handle_left_type = bp.handle_right_type = "AUTO"
    else:
        sp = cu.splines.new("POLY")
        sp.points.add(len(points) - 1)
        for pt, p in zip(sp.points, points):
            pt.co = (*util.vec3(p), 1.0)
    sp.use_cyclic_u = bool(closed)
    obj = util.new_object(name, cu)
    if material:
        from . import materials
        materials.assign(state, obj, material)
    return util.register(state, obj, name).name


def circle_path(state, radius=5.0, height=0.0, name="CirclePath", center=(0, 0, 0), **_):
    """Closed circular bezier path (for follow_path orbits)."""
    pts = [[center[0] + radius * math.cos(a), center[1] + radius * math.sin(a), center[2] + height]
           for a in [i * math.pi / 4 for i in range(8)]]
    return curve_path(state, pts, name=name, closed=True)


def convert_to_mesh(state, target, **_):
    """Convert curve/text/metaball (with modifiers) into a mesh object in place."""
    obj = util.get_obj(state, target)
    deps = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(obj.evaluated_get(deps), depsgraph=deps)
    new = util.new_object(obj.name + "_mesh", me)
    new.matrix_world = obj.matrix_world.copy()
    name = obj.name
    bpy.data.objects.remove(obj, do_unlink=True)
    new.name = name
    return util.register(state, new, name).name


OPS = {
    "add_primitive": add_primitive,
    "rounded_box": rounded_box,
    "empty": empty,
    "backdrop": backdrop,
    "floor": floor,
    "import_model": import_model,
    "image_plane": image_plane,
    "modifier": add_modifier,
    "bevel": bevel,
    "subdivision": subdivision,
    "array": array,
    "solidify": solidify,
    "displace": displace,
    "boolean": boolean,
    "apply_modifiers": apply_modifiers,
    "shade_smooth": shade_smooth,
    "transform": transform,
    "parent": set_parent,
    "duplicate": duplicate,
    "delete": delete,
    "hide": hide,
    "set_origin": set_origin,
    "instance_grid": instance_grid,
    "scatter": scatter,
    "curve_path": curve_path,
    "circle_path": circle_path,
    "convert_to_mesh": convert_to_mesh,
}
