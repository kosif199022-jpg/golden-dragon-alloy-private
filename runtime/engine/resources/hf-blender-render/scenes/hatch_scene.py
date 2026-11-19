# «فقس» — standalone Blender 5.x scene (self-contained). Driven by env vars:
#   OUT_DIR, MODE=stills|one|anim, ENGINE=EEVEE|CYCLES, SAMPLES, RES_PCT, F0, F1, FRAME (for one)
import bpy, math, random, sys, os, json
from mathutils import Vector
OUT_DIR = os.environ.get("OUT_DIR", os.getcwd())
MODE = os.environ.get("MODE", "stills")


random.seed(7)
sc = bpy.context.scene
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)

FPS, N = 30, 150
sc.render.fps = FPS
sc.frame_start, sc.frame_end = 1, N
sc.render.resolution_x, sc.render.resolution_y = 1080, 1920
sc.render.resolution_percentage = 100
ENGINE = os.environ.get("ENGINE", "EEVEE").upper()
SAMPLES = int(os.environ.get("SAMPLES", "32"))
if ENGINE == "CYCLES":
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = SAMPLES
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.03
    sc.cycles.use_denoising = True
    try: sc.cycles.denoiser = "OPENIMAGEDENOISE"
    except Exception: pass
    sc.cycles.max_bounces = 6; sc.cycles.diffuse_bounces = 2; sc.cycles.glossy_bounces = 2
    sc.cycles.transmission_bounces = 2; sc.cycles.volume_bounces = 0
    sc.render.use_persistent_data = True
else:
    try:
        sc.render.engine = "BLENDER_EEVEE"
    except Exception:
        sc.render.engine = "BLENDER_EEVEE_NEXT"
    sc.eevee.taa_render_samples = SAMPLES
for k, v in (("use_raytracing", True), ("use_shadows", True)):
    try: setattr(sc.eevee, k, v)
    except Exception: pass
try:
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
except Exception:
    pass
sc.render.use_motion_blur = True
sc.render.motion_blur_shutter = 0.4

def hexc(h, a=1.0):
    h = h.lstrip("#"); c = [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return (*c, a)

# ---------------------------------------------------------------- materials
def mat(name, color, rough=0.5, emit=None, estr=0.0, coat=0.0, sss=0.0, metal=0.0, sheen=0.0):
    m = bpy.data.materials.new(name)
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = hexc(color)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    for key, val in (("Coat Weight", coat), ("Subsurface Weight", sss), ("Sheen Weight", sheen)):
        if key in b.inputs: b.inputs[key].default_value = val
    if emit:
        b.inputs["Emission Color"].default_value = hexc(emit)
        b.inputs["Emission Strength"].default_value = estr
    return m

M = {
    "body": mat("Body", "#2c2f4a", 0.38, coat=0.45, sss=0.1, sheen=0.4),
    "belly": mat("Belly", "#ffb48a", 0.5, sss=0.2),
    "snout": mat("Snout", "#3b3f62", 0.4, coat=0.4),
    "gold": mat("Gold", "#ffc95a", 0.22, metal=0.85, emit="#ffb030", estr=0.4),
    "wing": mat("Wing", "#7b4fb8", 0.45, sss=0.4, emit="#5a2e9e", estr=0.15),
    "white": mat("Sclera", "#fbf7f2", 0.2, coat=0.6),
    "iris": mat("Iris", "#ff9d1f", 0.15, coat=1.0, emit="#ff8a00", estr=0.6),
    "pupil": mat("Pupil", "#0b0a12", 0.08, coat=1.0),
    "hl": mat("Highlight", "#ffffff", 0.1, emit="#ffffff", estr=12),
    "blush": mat("Blush", "#ff7a8a", 0.6, emit="#ff6a7a", estr=0.4),
    "moss": mat("Moss", "#4f9a6e", 0.85, sss=0.15),
    "hill": mat("FarHill", "#2a2352", 0.9),
    "hill2": mat("FarHill2", "#3a2c66", 0.9),
    "tree": mat("Tree", "#1c1840", 0.9),
    "spark": mat("Spark", "#ffd36b", 0.3, emit="#ffcf5a", estr=28),
    "fly": mat("Firefly", "#fff1a8", 0.3, emit="#ffe58a", estr=16),
    "star": mat("Star", "#ffffff", 0.3, emit="#e8e6ff", estr=9),
    "moon": mat("Moon", "#fff4d6", 0.5, emit="#fff1cc", estr=5),
    "mush": mat("MushCap", "#7ff0e0", 0.3, emit="#4ff0d8", estr=5),
    "stem": mat("MushStem", "#f2e6d0", 0.6),
    "grass": mat("Grass", "#3f8a5c", 0.7),
}

# egg shell: cream + gold voronoi spots
egg = bpy.data.materials.new("EggShell")
nt = egg.node_tree; b = nt.nodes["Principled BSDF"]
b.inputs["Roughness"].default_value = 0.35
if "Coat Weight" in b.inputs: b.inputs["Coat Weight"].default_value = 0.5
if "Subsurface Weight" in b.inputs: b.inputs["Subsurface Weight"].default_value = 0.25
tc = nt.nodes.new("ShaderNodeTexCoord")
vor = nt.nodes.new("ShaderNodeTexVoronoi"); vor.inputs["Scale"].default_value = 5.5
ramp = nt.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].position = 0.24; ramp.color_ramp.elements[0].color = hexc("#ffbf3f")
ramp.color_ramp.elements[1].position = 0.28; ramp.color_ramp.elements[1].color = hexc("#fff3dc")
nt.links.new(tc.outputs["Object"], vor.inputs["Vector"])
nt.links.new(vor.outputs["Distance"], ramp.inputs["Fac"])
nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
M["egg"] = egg
M["eggin"] = mat("EggInner", "#fff8ea", 0.6, emit="#ffd27a", estr=0.6)

# sky gradient (emission plane)
sky = bpy.data.materials.new("Sky")
nt = sky.node_tree
for n in list(nt.nodes):
    if n.type != "OUTPUT_MATERIAL": nt.nodes.remove(n)
out = [n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"][0]
tc = nt.nodes.new("ShaderNodeTexCoord"); sep = nt.nodes.new("ShaderNodeSeparateXYZ")
r = nt.nodes.new("ShaderNodeValToRGB"); em = nt.nodes.new("ShaderNodeEmission")
nt.links.new(tc.outputs["Generated"], sep.inputs[0]); nt.links.new(sep.outputs["Y"], r.inputs["Fac"])
cr = r.color_ramp
cr.elements[0].position = 0.15; cr.elements[0].color = hexc("#ffa772")
cr.elements[1].position = 0.75; cr.elements[1].color = hexc("#140e38")
e = cr.elements.new(0.27); e.color = hexc("#d0668c")
e = cr.elements.new(0.42); e.color = hexc("#6a3592")
e = cr.elements.new(0.58); e.color = hexc("#2b1d5e")
em.inputs["Strength"].default_value = 1.0
nt.links.new(r.outputs["Color"], em.inputs["Color"]); nt.links.new(em.outputs[0], out.inputs["Surface"])
M["sky"] = sky

# world (ambient)
w = bpy.data.worlds.new("W"); sc.world = w
bg = w.node_tree.nodes.get("Background")
bg.inputs["Color"].default_value = hexc("#3a2d6e"); bg.inputs["Strength"].default_value = 0.35

# ---------------------------------------------------------------- helpers
def smooth(o, lvl=2):
    for p in o.data.polygons: p.use_smooth = True
    if lvl:
        md = o.modifiers.new("sub", "SUBSURF"); md.levels = 1; md.render_levels = lvl

def sphere(name, loc, r, scale=(1, 1, 1), m=None, parent=None, seg=32, sub=1, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=seg // 2, radius=r, location=loc)
    o = bpy.context.object; o.name = name; o.scale = scale
    o.rotation_euler = [math.radians(a) for a in rot]
    smooth(o, sub)
    if m: o.data.materials.append(m)
    if parent: o.parent = parent
    return o

def cone(name, loc, r, depth, m, parent=None, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=r, radius2=r * 0.12, depth=depth, location=loc,
                                    rotation=[math.radians(a) for a in rot])
    o = bpy.context.object; o.name = name
    for p in o.data.polygons: p.use_smooth = True
    o.data.materials.append(m)
    if parent: o.parent = parent
    return o

def empty(name, loc=(0, 0, 0), parent=None, rot=(0, 0, 0)):
    o = bpy.data.objects.new(name, None); sc.collection.objects.link(o)
    o.location = loc; o.rotation_euler = [math.radians(a) for a in rot]
    if parent: o.parent = parent
    return o

def key(o, path, f, val, interp=None):
    setattr(o, path, val) if not isinstance(val, tuple) else setattr(o, path, val)
    o.keyframe_insert(path, frame=f)

def kv(o, path, frames_vals):
    for f, v in frames_vals:
        setattr(o, path, v); o.keyframe_insert(path, frame=f)

# ---------------------------------------------------------------- environment
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 14, 6))
skyp = bpy.context.object; skyp.name = "SkyPlane"; skyp.scale = (40, 1, 1)
skyp.dimensions = (40, 20, 0); skyp.rotation_euler = (math.radians(90), 0, 0)
skyp.data.materials.append(M["sky"])
skyp.visible_shadow = False

sphere("Moon", (1.7, 13.5, 6.3), 0.95, m=M["moon"], sub=1)
for i in range(110):
    x = random.uniform(-9, 9); z = random.uniform(2.6, 9.5)
    s = random.uniform(0.02, 0.06) * (1.6 if random.random() < 0.08 else 1)
    st = sphere(f"Star{i}", (x, 13.6, z), s, m=M["star"], seg=8, sub=0)
    st.visible_shadow = False

# far hills + tree silhouettes
for i, (x, y, z, r, sx, mm) in enumerate([(-5, 9, -2.4, 4.5, 1.4, "hill"), (4.5, 10, -2.8, 5, 1.5, "hill"),
                                           (0.5, 7, -2.6, 3.6, 1.6, "hill2"), (-3.5, 5.5, -2.2, 2.6, 1.5, "hill2")]):
    sphere(f"Hill{i}", (x, y, z), r, scale=(sx, 1, 0.75), m=M[mm], sub=1)
for i in range(16):
    x = random.uniform(-6, 6); y = random.uniform(6, 9.5)
    h = random.uniform(0.9, 1.8)
    cone(f"Tree{i}", (x, y, -0.2 + h / 2 + random.uniform(-0.3, 0.6)), h * 0.32, h, M["tree"])

# moss hill under the egg
ground = sphere("Ground", (0, 0.6, -1.95), 3.2, scale=(1.5, 1.2, 0.62), m=M["moss"], seg=64, sub=2)
for i in range(70):
    a = random.uniform(0, 2 * math.pi); d = random.uniform(0.6, 2.4)
    x, y = math.cos(a) * d, 0.6 + math.sin(a) * d * 0.7
    if y < -0.9: continue
    g = cone(f"Grass{i}", (x, y, 0.02), 0.035, random.uniform(0.12, 0.26), M["grass"],
             rot=(random.uniform(-15, 15), random.uniform(-15, 15), 0))
    g.location.z = 0.05 - (d ** 2) * 0.03
for i, (x, y, s) in enumerate([(-0.95, 0.1, 1.0), (-1.2, 0.5, 0.7), (1.05, 0.3, 0.9), (0.85, 0.9, 0.6), (-0.7, -0.35, 0.55)]):
    zz = 0.05 - (x * x + (y - 0.6) ** 2) * 0.03
    stem = sphere(f"Stem{i}", (x, y, zz + 0.07 * s), 0.035 * s, scale=(1, 1, 2.2), m=M["stem"], seg=16)
    cap = sphere(f"Cap{i}", (x, y, zz + 0.16 * s), 0.09 * s, scale=(1, 1, 0.55), m=M["mush"], seg=24)
    pl = bpy.data.lights.new(f"MushL{i}", "POINT"); pl.energy = 6 * s; pl.color = hexc("#4ff0d8")[:3]
    po = bpy.data.objects.new(f"MushL{i}", pl); sc.collection.objects.link(po); po.location = (x, y, zz + 0.2 * s)

# ---------------------------------------------------------------- egg
EGG_Z, CUT = 0.66, 0.74
def egg_half(name, top):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=0.5, location=(0, 0, 0))
    o = bpy.context.object; o.name = name
    for v in o.data.vertices:
        v.co.z *= 1.28
        if v.co.z > 0: v.co.z *= 1.08; v.co.x *= 1 - 0.1 * v.co.z; v.co.y *= 1 - 0.1 * v.co.z
    import bmesh
    bm = bmesh.new(); bm.from_mesh(o.data)
    # zig-zag crack: bisect with plane then jitter the cut edge
    cut_local = CUT - EGG_Z
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    res = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, cut_local), plane_no=(0, 0, 1),
                                 clear_inner=top, clear_outer=not top)
    cutv = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMVert)]
    for v in cutv:
        ang = math.atan2(v.co.y, v.co.x)
        v.co.z += 0.045 * (1 if (int((ang + math.pi) / (2 * math.pi) * 14) % 2) else -1)
    bm.to_mesh(o.data); bm.free()
    for p in o.data.polygons: p.use_smooth = True
    sol = o.modifiers.new("shell", "SOLIDIFY"); sol.thickness = 0.03; sol.material_offset = 1
    o.data.materials.append(M["egg"]); o.data.materials.append(M["eggin"])
    return o

egg_root = empty("EggRoot", (0, 0, 0.05))
egg_bot = egg_half("EggBottom", False); egg_bot.parent = egg_root; egg_bot.location = (0, 0, EGG_Z - 0.05)
egg_top = egg_half("EggTop", True)
top_piv = empty("TopPivot", (0, 0, CUT - 0.05), parent=egg_root)
egg_top.parent = top_piv; egg_top.location = (0, 0, EGG_Z - CUT)

# egg wobble (pivot at base) + anticipation
kv(egg_root, "rotation_euler", [
    (1, (0, 0, 0)), (8, (0, math.radians(4), 0)), (14, (0, math.radians(-5), 0)), (20, (0, 0, 0)),
    (24, (0, math.radians(8), 0)), (28, (0, math.radians(-9), 0)), (32, (0, math.radians(10), 0)),
    (36, (0, math.radians(-10), 0)), (40, (0, 0, 0)), (49, (0, 0, 0)),
    (54, (0, math.radians(-3), 0)), (60, (0, 0, 0))])
kv(egg_root, "scale", [(1, (1, 1, 1)), (40, (1, 1, 1)), (45, (1.1, 1.1, 0.86)), (49, (0.94, 0.94, 1.08)),
                       (53, (1.04, 1.04, 0.96)), (58, (1, 1, 1))])
# small hop on the big wobble
kv(egg_root, "location", [(1, (0, 0, 0.05)), (30, (0, 0, 0.05)), (33, (0, 0, 0.12)), (36, (0, 0, 0.05))])
# top shell pops off and tumbles out of frame
kv(top_piv, "location", [(1, (0, 0, CUT - 0.05)), (47, (0, 0, CUT - 0.05)), (52, (0.35, -0.05, 1.25)),
                         (60, (1.0, -0.2, 2.0)), (72, (1.7, -0.4, 2.2)), (86, (2.6, -0.6, 1.2))])
kv(top_piv, "rotation_euler", [(1, (0, 0, 0)), (47, (0, 0, 0)), (60, (math.radians(-60), math.radians(120), 0)),
                               (86, (math.radians(-160), math.radians(330), math.radians(40)))])

# ---------------------------------------------------------------- baby dragon (original design)
root = empty("DragonRoot", (0, 0, -1.4))
body = sphere("Body", (0, 0, 0.44), 0.33, scale=(1, 0.95, 1.05), m=M["body"], parent=root)
belly = sphere("Belly", (0, -0.2, 0.5), 0.24, scale=(1, 0.6, 1.1), m=M["belly"], parent=root)
head = empty("HeadPivot", (0, 0, 0.78), parent=root)
skull = sphere("Head", (0, -0.02, 0.2), 0.31, scale=(1.12, 1, 0.98), m=M["body"], parent=head)
snout = sphere("Snout", (0, -0.27, 0.1), 0.14, scale=(1.25, 0.85, 0.75), m=M["snout"], parent=head)
for sx in (-1, 1):
    sphere(f"Nostril{sx}", (sx * 0.05, -0.385, 0.13), 0.018, scale=(1, 0.6, 0.7), m=M["pupil"], parent=head, seg=12)
    sphere(f"Cheek{sx}", (sx * 0.22, -0.2, 0.08), 0.055, scale=(1, 0.5, 0.65), m=M["blush"], parent=head, seg=16)
    cone(f"Horn{sx}", (sx * 0.15, 0.05, 0.47), 0.06, 0.2, M["gold"], parent=head, rot=(-25, sx * 18, 0))
    sphere(f"Ear{sx}", (sx * 0.33, 0.03, 0.27), 0.08, scale=(1.4, 0.35, 0.8), m=M["wing"], parent=head,
           rot=(0, sx * -30, sx * 15), seg=16)
    # eye rig: blink by scaling the eye pivot on Z
    ep = empty(f"Eye{sx}", (sx * 0.125, -0.24, 0.24), parent=head, rot=(0, 0, sx * 12))
    sphere(f"Sclera{sx}", (0, 0, 0), 0.105, scale=(0.95, 0.85, 1.08), m=M["white"], parent=ep, seg=32)
    sphere(f"Iris{sx}", (0, -0.08, -0.005), 0.077, scale=(1, 0.35, 1.08), m=M["iris"], parent=ep, seg=32)
    sphere(f"Pupil{sx}", (0, -0.1, -0.005), 0.046, scale=(1, 0.3, 1.12), m=M["pupil"], parent=ep, seg=24)
    sphere(f"HL{sx}", (-0.028, -0.118, 0.035), 0.019, m=M["hl"], parent=ep, seg=12, sub=0)
    sphere(f"HLs{sx}", (0.022, -0.115, -0.03), 0.009, m=M["hl"], parent=ep, seg=8, sub=0)
    wp = empty(f"WingPivot{sx}", (sx * 0.22, 0.16, 0.66), parent=root, rot=(0, 0, sx * -20))
    sphere(f"Wing{sx}", (sx * 0.17, 0.0, 0.08), 0.2, scale=(1.1, 0.12, 0.75), m=M["wing"], parent=wp,
           rot=(0, sx * -25, 0), seg=24)
    cone(f"WingClaw{sx}", (sx * 0.34, 0, 0.2), 0.025, 0.07, M["gold"], parent=wp, rot=(0, sx * 40, 0))
    sphere(f"Paw{sx}", (sx * 0.27, -0.3, 0.62), 0.075, scale=(1.1, 1, 0.8), m=M["body"], parent=root, seg=24)
    for t in (-1, 0, 1):
        sphere(f"Toe{sx}{t}", (sx * 0.27 + t * 0.035, -0.37, 0.61), 0.018, m=M["gold"], parent=root, seg=10, sub=0)
for i, z in enumerate((0.5, 0.36, 0.2)):
    cone(f"Spine{i}", (0, 0.24 - i * 0.02, z), 0.045 - i * 0.008, 0.11, M["gold"], parent=head if False else head,
         rot=(-70 - i * 10, 0, 0)).location = (0, 0.27 + i * 0.03, z - 0.05 * i)

# pop out of the egg: squash & stretch with pivot at base
B = 0.13
kv(root, "location", [(1, (0, 0, -1.4)), (48, (0, 0, -1.4)), (53, (0, 0, B + 0.12)), (57, (0, 0, B + 0.3)),
                      (62, (0, 0, B)), (66, (0, 0, B + 0.04)), (70, (0, 0, B)),
                      (108, (0, 0, B)), (112, (0, 0, B - 0.02)), (117, (0, 0, B + 0.16)), (123, (0, 0, B)),
                      (126, (0, 0, B - 0.01)), (130, (0, 0, B))])
kv(root, "scale", [(1, (0.01, 0.01, 0.01)), (48, (0.01, 0.01, 0.01)), (53, (0.82, 0.82, 1.25)), (57, (0.95, 0.95, 1.06)),
                   (62, (1.16, 1.16, 0.84)), (66, (0.97, 0.97, 1.04)), (70, (1, 1, 1)),
                   (108, (1, 1, 1)), (112, (1.1, 1.1, 0.88)), (116, (0.94, 0.94, 1.08)), (123, (1.08, 1.08, 0.9)),
                   (127, (1, 1, 1))])
# head acting: look around, curious tilt, final tilt to camera
kv(head, "rotation_euler", [(1, (0, 0, 0)), (68, (0, 0, 0)), (74, (math.radians(-6), 0, math.radians(28))),
                            (84, (math.radians(-6), 0, math.radians(28))), (90, (math.radians(-4), 0, math.radians(-30))),
                            (100, (math.radians(-4), 0, math.radians(-30))), (106, (math.radians(4), 0, 0)),
                            (130, (math.radians(4), 0, 0)),
                            (137, (math.radians(-5), math.radians(-16), math.radians(6))),
                            (150, (math.radians(-6), math.radians(-18), math.radians(6)))])
for sx in (-1, 1):
    ep = bpy.data.objects[f"Eye{sx}"]
    kv(ep, "scale", [(1, (1, 1, 1)), (60, (1, 1, 1)), (62, (1, 1, 0.1)), (65, (1, 1, 1.05)), (67, (1, 1, 1)),
                     (101, (1, 1, 1)), (103, (1, 1, 0.08)), (106, (1, 1, 1)), (140, (1, 1, 1)),
                     (142, (1.05, 1, 0.12)), (145, (1, 1, 1))])
    wp = bpy.data.objects[f"WingPivot{sx}"]
    flap = [(1, (0, 0, math.radians(sx * -20)))]
    for f in range(108, 132, 4):
        up = ((f - 108) // 4) % 2 == 0
        flap.append((f, (0, math.radians(sx * (-40 if up else 15)), math.radians(sx * -20))))
    flap.append((134, (0, 0, math.radians(sx * -20))))
    kv(wp, "rotation_euler", flap)

# ---------------------------------------------------------------- magic: sparks + fireflies + glow
def burst(prefix, f0, center, n, speed, life, size):
    for i in range(n):
        th = random.uniform(0, 2 * math.pi); ph = random.uniform(0.15, 1.35)
        v = Vector((math.cos(th) * math.cos(ph), math.sin(th) * math.cos(ph) * 0.6, math.sin(ph))) * speed * random.uniform(0.6, 1.2)
        s = sphere(f"{prefix}{i}", center, size * random.uniform(0.6, 1.3), m=M["spark"], seg=8, sub=0)
        s.visible_shadow = False
        s.scale = (0, 0, 0); s.keyframe_insert("scale", frame=f0 - 1)
        L = int(life * random.uniform(0.7, 1.2))
        for k in range(0, L + 1, 3):
            t = k / FPS
            s.location = Vector(center) + v * t + Vector((0, 0, -1.4 * t * t))
            s.keyframe_insert("location", frame=f0 + k)
            sc_ = max(0.0, 1.0 - (k / L) ** 1.6) if k > 2 else 1.0
            s.scale = (sc_, sc_, sc_); s.keyframe_insert("scale", frame=f0 + k)

burst("SparkA", 48, (0, 0, 0.85), 48, 2.6, 34, 0.028)
burst("SparkB", 116, (0, -0.05, 1.25), 26, 1.6, 30, 0.02)
for i in range(28):
    x = random.uniform(-1.8, 1.8); y = random.uniform(-1.5, 3.5); z = random.uniform(0.2, 2.6)
    f = sphere(f"Fly{i}", (x, y, z), random.uniform(0.012, 0.022), m=M["fly"], seg=8, sub=0)
    f.visible_shadow = False
    for fr in range(1, N + 31, 30):
        f.location = (x + random.uniform(-0.15, 0.15), y + random.uniform(-0.1, 0.1), z + random.uniform(-0.12, 0.12))
        f.keyframe_insert("location", frame=fr)

glow_l = bpy.data.lights.new("MagicGlow", "POINT"); glow_l.color = hexc("#ffc45a")[:3]; glow_l.shadow_soft_size = 0.2
glow = bpy.data.objects.new("MagicGlow", glow_l); sc.collection.objects.link(glow); glow.location = (0, -0.05, 0.9)
for f, e in [(1, 0), (38, 0), (46, 50), (49, 240), (60, 120), (80, 60), (150, 50)]:
    glow_l.energy = e; glow_l.keyframe_insert("energy", frame=f)

# ---------------------------------------------------------------- lights
def area(name, loc, rot, energy, color, size):
    l = bpy.data.lights.new(name, "AREA"); l.energy = energy; l.color = hexc(color)[:3]; l.size = size
    o = bpy.data.objects.new(name, l); sc.collection.objects.link(o)
    o.location = loc; o.rotation_euler = [math.radians(a) for a in rot]
    return o
area("Key", (-2.4, -3.0, 3.2), (52, 0, -38), 380, "#ffd2a0", 2.2)
area("Rim", (2.3, 2.4, 2.6), (-55, 0, 140), 520, "#8f7bff", 1.4)
area("Rim2", (-2.2, 2.2, 1.6), (-65, 0, -135), 260, "#ff8fb8", 1.2)
area("Fill", (1.8, -3.2, 0.9), (80, 0, 30), 70, "#a9c4ff", 3.0)

# ---------------------------------------------------------------- camera
cam_d = bpy.data.cameras.new("Cam"); cam_d.lens = 50; cam_d.sensor_fit = "AUTO"
cam = bpy.data.objects.new("Cam", cam_d); sc.collection.objects.link(cam); sc.camera = cam
tgt = empty("CamTarget", (0, 0, 0.92))
tr = cam.constraints.new("TRACK_TO"); tr.target = tgt; tr.track_axis = "TRACK_NEGATIVE_Z"; tr.up_axis = "UP_Y"
cam_d.dof.use_dof = True; cam_d.dof.aperture_fstop = 2.2
focus = empty("Focus", (0, -0.25, 0.9)); cam_d.dof.focus_object = focus
kv(cam, "location", [(1, (0.35, -5.9, 1.05)), (150, (-0.15, -4.35, 1.22))])
kv(tgt, "location", [(1, (0, 0, 0.82)), (50, (0, 0, 0.9)), (150, (0, 0, 1.0))])
kv(focus, "location", [(1, (0, -0.4, 0.75)), (50, (0, -0.35, 0.9)), (150, (0, -0.35, 1.0))])
# tiny camera shake on the pop
for f, z in [(48, 0), (49, 0.025), (50, -0.02), (51, 0.012), (53, 0)]:
    pass

# post: bloom + vignette (Blender 5.x node-group compositor, falls back silently)
def post_fx():
    if not hasattr(sc, "compositing_node_group"):
        return
    ng = bpy.data.node_groups.new("Post", "CompositorNodeTree")
    ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    sc.compositing_node_group = ng
    rl = ng.nodes.new("CompositorNodeRLayers"); out = ng.nodes.new("NodeGroupOutput")
    gl = ng.nodes.new("CompositorNodeGlare")
    for nm, v in (("Type", "Bloom"), ("Quality", "Medium")):
        so = next((x for x in gl.inputs if x.name == nm), None)
        if so is not None: so.default_value = v
    for nm, v in (("Threshold", 0.9), ("Strength", 0.55), ("Size", 0.65)):
        so = next((x for x in gl.inputs if x.name == nm), None)
        if so is not None:
            try: so.default_value = v
            except Exception: pass
    ng.links.new(rl.outputs["Image"], gl.inputs["Image"])
    cur = gl.outputs[0]
    try:  # vignette = blurred ellipse mask multiplied over the image
        em = ng.nodes.new("CompositorNodeEllipseMask")
        for nm, v in (("Size", (0.98, 0.85)), ("Mask", 0.0), ("Value", 1.0)):
            so = next((x for x in em.inputs if x.name == nm), None)
            if so is not None: so.default_value = v
        bl = ng.nodes.new("CompositorNodeBlur")
        so = next((x for x in bl.inputs if x.name == "Size"), None)
        if so is not None: so.default_value = (350, 350)
        ng.links.new(em.outputs[0], bl.inputs["Image"])
        mr = ng.nodes.new("ShaderNodeMapRange"); mr.inputs["To Min"].default_value = 0.68
        ng.links.new(bl.outputs[0], mr.inputs["Value"])
        mix = ng.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"
        mix.inputs[0].default_value = 1.0
        ng.links.new(cur, mix.inputs[6]); ng.links.new(mr.outputs[0], mix.inputs[7])
        cur = mix.outputs[2]
    except Exception as ex:
        print("vignette skipped:", ex)
    ng.links.new(cur, out.inputs[0])
try:
    post_fx()
except Exception as ex:
    print("post fx failed:", ex)

RES_PCT = int(os.environ.get("RES_PCT", "100"))
sc.render.resolution_percentage = RES_PCT
os.makedirs(OUT_DIR, exist_ok=True)
if MODE == "one":
    sc.frame_set(int(os.environ.get("FRAME", "118"))); sc.render.filepath = os.path.join(OUT_DIR, "one_%03d.png" % sc.frame_current)
    bpy.ops.render.render(write_still=True)
elif MODE == "stills":
    outs = []
    for f in (1, 34, 49, 54, 64, 80, 96, 104, 118, 148):
        sc.frame_set(f)
        p = os.path.join(OUT_DIR, f"still_{f:03d}.png")
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        outs.append(p)
    print("@@" + json.dumps({"stills": outs}))
else:
    sc.frame_start = int(os.environ.get("F0", "1")); sc.frame_end = int(os.environ.get("F1", str(N)))
    sc.render.use_overwrite = False; sc.render.use_placeholder = True   # parallel workers / resumes skip done frames
    sc.render.image_settings.file_format = "PNG"
    sc.render.filepath = os.path.join(OUT_DIR, "frames", "f_####.png")
    bpy.ops.render.render(animation=True)
    print("@@" + json.dumps({"frames": os.path.join(OUT_DIR, "frames")}))
