"""exec smoke test: HDRI world from a generated .hdr, product_shot preset on an imported OBJ, still render.
Run: python scripts/bl.py exec tests/smoke_exec.py --out OUT -- hello"""
import os
import sys

import bpy

img = bpy.data.images.new("gen_hdr", 64, 32, float_buffer=True)
px = []
for y in range(32):
    for x in range(64):
        v = 0.2 + 3.0 * (y / 31.0) ** 4
        px += [v, v * 0.9, v * 0.8, 1.0]
img.pixels = px
hdr = os.path.join(OUT_DIR, "gen.hdr")
img.filepath_raw = hdr
img.file_format = "HDR"
img.save()

bpylib.run_op(STATE, "clear_scene")
bpylib.run_op(STATE, "scene_setup", resolution=[960, 540], engine="EEVEE", samples=16)
STATE["recipe_dir"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
bpylib.run_op(STATE, "product_shot", model="wedge.obj", material="chrome", theme="warm", size=1.6)
bpylib.run_op(STATE, "world_hdri", path=hdr, strength=0.8, background=False, background_color="#0b0908")
print("script argv:", sys.argv[1:])
bpylib.run_op(STATE, "render", type="still", out="exec_product.png")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "exec_product.blend"))
