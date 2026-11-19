"""line_art + video_as_texture + scene_strip smoke test. blender -b --factory-startup -P test_3d.py"""
import sys, os, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "scripts", "bpylib")))
import bpy, draw, video
OUT = r"C:\Users\cinde\OneDrive\Desktop\تحليل\output\blender-pro-tests"
M = OUT + r"\media"
st = {}
sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y = 480, 270
# 3D scene: cube + monkey, camera, light  (default scene has cube/light/camera)
bpy.ops.mesh.primitive_monkey_add(location=(0, 0, 0))
cam = sc.camera
cam.location = (0, -7, 1); cam.rotation_euler = (math.radians(86), 0, 0)
print(video.video_as_texture(st, M + r"\clipA.mp4", size=(4, 2.25), location=(2.5, 1, 0), rotation=(90, 0, 0)))
print(draw.line_art(st, source="SCENE", radius=0.01, color="#000000"))
sc.frame_start, sc.frame_end = 1, 3
sc.render.filepath = OUT + r"\lineart_3d.png"
sc.frame_set(2)
bpy.ops.render.render(write_still=True)
# scene strip into a fresh scene
shot = sc
new = bpy.data.scenes.new("Edit")
bpy.context.window.scene = new
new.render.resolution_x, new.render.resolution_y = 480, 270
print(video.scene_strip(st, shot.name, duration=0.1))
print(video.vse_list(st))
print("OK")
