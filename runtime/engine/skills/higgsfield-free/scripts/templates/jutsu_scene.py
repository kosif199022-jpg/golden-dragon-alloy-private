# Black Dragon v1990 — 3D Jutsu starter (hosted Blender 5.2). Ran as-is on 2026-11-11: 41 s, no credit debit.
# Use: scene_builder_3d_create_project -> scene_builder_3d_query_python (get revision + sceneSequence)
#      -> scene_builder_3d_run_python(code=THIS, revision=R, expectedSceneSequence=S, operationId="build-01")
#      -> scene_builder_3d_get_operation until terminal -> get_artifact (look at the PNG) -> show_scene(revisionAfter).
# Rules measured the hard way:
#   * a new project has NO world: create one before touching world nodes (first run failed on this).
#   * engines: BLENDER_EEVEE | BLENDER_WORKBENCH | CYCLES only. Sun/Spot/Point lights (Area lights are dropped by GLB).
#   * set image_settings.media_type BEFORE file_format; files leave only through artifacts.file(...).publish().
#   * no network, no pip, ~5 min per operation: small renders, split big builds, one mutation at a time.
#   * names by role: HERO_ ENV_ CAM_ LGT_. Each operation starts from the settled scene: look objects up by name.
import bpy, math

HERO_COLOR = (0.8, 0.05, 0.02, 1)      # change me
SIZE = (540, 960)                      # preview size; raise only for the final still

s = bpy.context.scene
bpy.ops.mesh.primitive_plane_add(size=10)
fl = bpy.context.object; fl.name = "ENV_floor"
m = bpy.data.materials.new("MAT_floor"); m.use_nodes = True
m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.05, 0.05, 0.06, 1)
fl.data.materials.append(m)

bpy.ops.mesh.primitive_torus_add(major_radius=1.0, minor_radius=0.25, location=(0, 0, 1.3))
h = bpy.context.object; h.name = "HERO_ring"; h.rotation_euler = (math.radians(70), 0, math.radians(20))
bpy.ops.object.shade_smooth()
mh = bpy.data.materials.new("MAT_hero"); mh.use_nodes = True
b = mh.node_tree.nodes["Principled BSDF"]
b.inputs["Base Color"].default_value = HERO_COLOR
b.inputs["Metallic"].default_value = 0.9; b.inputs["Roughness"].default_value = 0.25
h.data.materials.append(mh)

bpy.ops.object.light_add(type='SUN', location=(4, -4, 6)); k = bpy.context.object
k.name = "LGT_key"; k.data.energy = 3; k.rotation_euler = (math.radians(50), 0, math.radians(45))
bpy.ops.object.light_add(type='POINT', location=(-3, 2, 3)); f = bpy.context.object
f.name = "LGT_fill"; f.data.energy = 300
bpy.ops.object.camera_add(location=(0, -5.5, 1.8)); c = bpy.context.object
c.name = "CAM_main"; c.rotation_euler = (math.radians(85), 0, 0); s.camera = c

if s.world is None:                     # REQUIRED on a fresh project
    s.world = bpy.data.worlds.new("World")
s.world.use_nodes = True
bg = s.world.node_tree.nodes.get("Background")
if bg: bg.inputs["Strength"].default_value = 0.3

s.render.engine = 'BLENDER_EEVEE'
s.render.resolution_x, s.render.resolution_y = SIZE
t = artifacts.file(name="preview.png", media_type="image/png")
s.render.filepath = str(t.path)
s.render.image_settings.media_type = "IMAGE"
s.render.image_settings.file_format = "PNG"
bpy.ops.render.render(write_still=True); t.publish()
result = {"objects": [o.name for o in bpy.data.objects]}
