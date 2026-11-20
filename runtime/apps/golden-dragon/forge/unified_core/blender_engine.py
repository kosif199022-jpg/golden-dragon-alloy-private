"""Native Blender scene engine: reviewed procedural scenes, no supplied scripts.

The generated Blender script is fixed and has no file/network inputs. Rendering
and .blend save write into a fresh OS TEMP directory only. This module never
opens or edits the user's existing Blender projects.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCENE_PRESETS = ("mechanical_gear", "machine_piston")

_SCRIPT = r'''
import bpy
import math
import sys
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
preset, output_dir, size_str = args
if preset not in ("mechanical_gear", "machine_piston"):
    raise RuntimeError("unsupported fixed Blender scene preset")
size = int(size_str)
if size not in (256, 512, 1024):
    raise RuntimeError("unsupported render dimensions")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.render.resolution_x = size
scene.render.resolution_y = size
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.display.shading.color_type = "MATERIAL"
scene.display.shading.light = "STUDIO"
if hasattr(scene.display.shading, "show_cavity"):
    scene.display.shading.show_cavity = True
if hasattr(scene.display.shading, "show_shadows"):
    scene.display.shading.show_shadows = True
scene.render.film_transparent = False

def material(name, color):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = tuple(color) + (1.0,)
    return mat

steel = material("steel_blue", (0.20, 0.35, 0.49))
gold = material("brass_gold", (0.78, 0.51, 0.16))
dark = material("dark_metal", (0.14, 0.18, 0.22))
floor = material("matte_floor", (0.29, 0.34, 0.40))

def cylinder(name, radius, depth, center, mat, verts=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius, depth=depth, location=center)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    bevel = obj.modifiers.new("safe_bevel", "BEVEL")
    bevel.width = 0.06
    bevel.segments = 2
    obj.modifiers.new("weighted_normals", "WEIGHTED_NORMAL")
    return obj

def gear(name, cx, cy, n_teeth, body_r, tip_r, inner_r, depth, mat):
    n = n_teeth * 4
    outline = []
    for i in range(n):
        radius = tip_r if i % 4 in (1, 2) else body_r
        angle = 2.0 * math.pi * i / n
        outline.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    vertices = []
    for z, inner in ((-depth/2, False), (depth/2, False), (-depth/2, True), (depth/2, True)):
        for i in range(n):
            a = 2.0 * math.pi * i / n
            x, y = (cx + inner_r * math.cos(a), cy + inner_r * math.sin(a)) if inner else outline[i]
            vertices.append((x, y, z))
    faces = []
    for i in range(n):
        j = (i + 1) % n
        faces.extend(((i, j, n+j, n+i),
                      (2*n+j, 2*n+i, 3*n+i, 3*n+j),
                      (n+i, n+j, 3*n+j, 3*n+i),
                      (j, i, 2*n+i, 2*n+j)))
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    bevel = obj.modifiers.new("machined_edges", "BEVEL")
    bevel.width = 0.025
    bevel.segments = 2
    obj.modifiers.new("smooth_weighted_normals", "WEIGHTED_NORMAL")

if preset == "mechanical_gear":
    gear("main_drive_gear", 0.0, 0.0, 18, 1.16, 1.43, 0.43, 0.50, gold)
    cylinder("center_hub", 0.38, 0.78, (0, 0, 0), steel)
    cylinder("drive_axle", 0.18, 1.35, (0, 0, 0.18), dark)
elif preset == "machine_piston":
    cylinder("piston_crown", 1.03, 0.42, (0, 0, 0.72), steel)
    cylinder("piston_body", 0.92, 1.05, (0, 0, 0.03), steel)
    cylinder("piston_rod", 0.24, 2.2, (0, 0, -0.78), gold)
    cylinder("lower_bearing", 0.55, 0.42, (0, 0, -1.55), dark)

bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -1.95))
base = bpy.context.object
base.name = "studio_base"
base.dimensions = (6.8, 6.8, 0.18)
base.data.materials.append(floor)

camera_data = bpy.data.cameras.new("orthographic_product_camera")
camera = bpy.data.objects.new("orthographic_product_camera", camera_data)
bpy.context.collection.objects.link(camera)
camera.location = (3.9, -5.2, 4.3)
target = Vector((0, 0, -0.05))
camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
camera.data.type = "ORTHO"
camera.data.ortho_scale = 5.9
scene.camera = camera
scene.render.filepath = output_dir + "/render.png"
bpy.ops.wm.save_as_mainfile(filepath=output_dir + "/scene.blend", compress=False)
bpy.ops.render.render(write_still=True)
'''


def render_scene(*, preset: str = "mechanical_gear", resolution: int = 512,
                 timeout: int = 120) -> dict:
    """Create actual Blender .blend and PNG from a fixed, original scene."""
    if preset not in SCENE_PRESETS:
        raise ValueError("unknown Blender scene preset")
    if resolution not in (256, 512, 1024):
        raise ValueError("resolution must be 256, 512, or 1024")
    if not 20 <= timeout <= 240:
        raise ValueError("invalid Blender timeout")
    blender = shutil.which("blender")
    if not blender:
        raise ValueError("Blender is not installed or not on PATH")
    folder = Path(tempfile.mkdtemp(prefix="golden-dragon-blender-"))
    script = folder / "render_fixed_scene.py"
    script.write_text(_SCRIPT, encoding="utf-8")
    flags = 0x08000000 if sys.platform == "win32" else 0
    argv = [blender, "--background", "--factory-startup",
            "--disable-autoexec", "--python-exit-code", "2",
            "--python", str(script), "--", preset, str(folder), str(resolution)]
    try:
        result = subprocess.run(
            argv, cwd=folder, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout, shell=False, check=False, creationflags=flags
        )
        png, blend = folder / "render.png", folder / "scene.blend"
        if result.returncode != 0:
            raise ValueError("Blender render failed: " +
                             result.stderr.decode("utf-8", errors="replace")[-350:])
        if not png.is_file() or png.stat().st_size < 300:
            raise ValueError("Blender did not produce a rendered image")
        if png.open("rb").read(8) != b"\x89PNG\r\n\x1a\n":
            raise ValueError("Blender output is not a valid PNG header")
        if not blend.is_file() or blend.open("rb").read(7) != b"BLENDER":
            raise ValueError("Blender did not save an authentic .blend project")
        return {
            "preset": preset, "resolution": resolution,
            "render_png": str(png), "project_blend": str(blend),
            "png_bytes": png.stat().st_size,
            "blend_bytes": blend.stat().st_size,
            "blender_executed": True,
            "arbitrary_user_script_executed": False,
            "original_project_modified": False,
        }
    except (subprocess.TimeoutExpired, ValueError):
        shutil.rmtree(folder, ignore_errors=True)
        raise
