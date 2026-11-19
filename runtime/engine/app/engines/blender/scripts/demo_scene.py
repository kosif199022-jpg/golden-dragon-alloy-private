# Runs INSIDE Blender: build a small cinematic proof scene from nothing and render it (PNG or MP4).
import argparse, json, math, os, sys
import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--frames", type=int, default=48)
ap.add_argument("--res", default="540x960")
ap.add_argument("--engine", default="BLENDER_EEVEE_NEXT")
a = ap.parse_args(argv)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
try:
    sc.render.engine = a.engine
except TypeError:
    sc.render.engine = "BLENDER_EEVEE"
w, h = map(int, a.res.lower().split("x"))
sc.render.resolution_x, sc.render.resolution_y = w, h
sc.render.fps, sc.frame_start, sc.frame_end = 30, 1, a.frames

world = bpy.data.worlds.new("night"); sc.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.004, 0.006, 0.012, 1)

bpy.ops.mesh.primitive_cube_add(size=1.4)
obj = bpy.context.active_object
bpy.ops.object.modifier_add(type="BEVEL"); obj.modifiers["Bevel"].width = 0.08; obj.modifiers["Bevel"].segments = 4
gold = bpy.data.materials.new("gold"); gold.use_nodes = True
bsdf = gold.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.83, 0.62, 0.25, 1)
bsdf.inputs["Metallic"].default_value = 1.0
bsdf.inputs["Roughness"].default_value = 0.22
obj.data.materials.append(gold)
obj.rotation_euler = (math.radians(20), 0, 0)
obj.keyframe_insert("rotation_euler", frame=1)
obj.rotation_euler = (math.radians(20), 0, math.radians(120))
obj.keyframe_insert("rotation_euler", frame=a.frames)

bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, -1))
floor = bpy.data.materials.new("floor"); floor.use_nodes = True
floor.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.02, 0.02, 0.025, 1)
floor.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.35
bpy.context.active_object.data.materials.append(floor)

for name, loc, power, col in (("key", (4, -4, 5), 1500, (1, 0.85, 0.65)), ("rim", (-4, 4, 3), 1200, (0.5, 0.7, 1)),
                              ("fill", (-5, -3, 2), 300, (1, 1, 1))):
    L = bpy.data.lights.new(name, "AREA"); L.energy, L.color, L.size = power, col, 3
    o = bpy.data.objects.new(name, L); o.location = loc; sc.collection.objects.link(o)
    o.rotation_euler = (0, 0, 0)
    c = o.constraints.new("TRACK_TO"); c.target = obj

cam_d = bpy.data.cameras.new("cam"); cam_d.lens = 50
cam = bpy.data.objects.new("cam", cam_d); sc.collection.objects.link(cam); sc.camera = cam
cam.constraints.new("TRACK_TO").target = obj
cam.location = (0, -9, 1.6); cam.keyframe_insert("location", frame=1)
cam.location = (0, -6.5, 1.1); cam.keyframe_insert("location", frame=a.frames)   # slow push-in, no cuts

sc.render.filepath = os.path.abspath(a.out)
if a.out.lower().endswith(".png"):
    sc.frame_set(a.frames // 2)
    sc.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)
    print("@@" + json.dumps({"still": os.path.abspath(a.out), "engine": sc.render.engine}))
else:
    sys.argv = [sys.argv[0], "--", "--out", a.out]
    exec(compile(open(os.path.join(os.path.dirname(__file__), "render.py"), encoding="utf-8").read(), "render.py", "exec"))
