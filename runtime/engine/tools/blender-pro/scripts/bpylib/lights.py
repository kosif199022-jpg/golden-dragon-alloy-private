"""Lights: single lights (point/spot/area/sun), studio 3-point rig, rim/kicker, animated light
sweep (glint), HDRI shortcut, volumetric god rays. Energies scale with distance so rigs look
similar at any scene size."""
import math

import bpy
import mathutils

from . import util

DEFAULT_ENERGY = {"POINT": 800.0, "SPOT": 1500.0, "AREA": 500.0, "SUN": 4.0}


def light(state, type="AREA", name=None, location=(4, -4, 5), rotation=None, target=None, energy=None,
          color="#ffffff", temperature=None, size=1.0, size_y=None, shape="RECTANGLE", spot_size=45.0,
          spot_blend=0.3, angle=None, radius=None, shadow=True, visible_camera=False, spread=None, **_):
    """Add a light. type POINT|SPOT|AREA|SUN. target (object name or [x,y,z]) aims it.
    temperature (Kelvin) overrides color. spot_size/angle/spread in degrees.
    visible_camera=False hides area-light panels from camera rays (clean product shots)."""
    t = type.upper()
    name = name or t.title() + "Light"
    ld = bpy.data.lights.new(name, t)
    ld.energy = float(energy if energy is not None else DEFAULT_ENERGY[t])
    ld.color = util.kelvin(temperature) if temperature else util.color3(color)
    if hasattr(ld, "use_shadow"):
        ld.use_shadow = bool(shadow)
    if t == "AREA":
        ld.shape = shape.upper()
        ld.size = float(size)
        if size_y is not None:
            ld.size_y = float(size_y)
        if spread is not None:
            ld.spread = math.radians(spread)
    elif t == "SPOT":
        ld.spot_size = math.radians(spot_size)
        ld.spot_blend = float(spot_blend)
        ld.shadow_soft_size = float(radius if radius is not None else 0.1)
    elif t == "POINT":
        ld.shadow_soft_size = float(radius if radius is not None else 0.25)
    elif t == "SUN":
        ld.angle = math.radians(angle if angle is not None else 1.0)
    obj = util.new_object(name, ld)
    obj.location = util.vec3(location)
    if rotation is not None:
        obj.rotation_euler = util.rad3(rotation)
    elif target is not None:
        util.look_at(obj, target_center(state, target))
    if not visible_camera and hasattr(obj, "visible_camera"):
        obj.visible_camera = False
    return util.register(state, obj, name).name


def target_center(state, target):
    """Center of target: object name (incl. children), [x,y,z], or None (= all renderables)."""
    if target is None:
        mn, mx = util.world_bbox(util.renderable_objects())
        return (mn + mx) / 2
    if isinstance(target, (list, tuple, mathutils.Vector)):
        return util.vec3(target)
    obj = util.get_obj(state, target)
    mn, mx = util.world_bbox([obj] + list(obj.children_recursive))
    return (mn + mx) / 2


def target_bounds(state, target):
    if isinstance(target, str):
        obj = util.get_obj(state, target)
        return util.world_bbox([obj] + list(obj.children_recursive))
    return util.world_bbox(util.renderable_objects())


def three_point(state, target=None, distance=None, intensity=1.0, key_temperature=5200, fill_temperature=6500,
                rim_temperature=7500, key_color=None, rim_color=None, fill_ratio=0.3, rim_ratio=1.2,
                azimuth=0.0, softness=1.0, prefix="Studio", **_):
    """Classic soft studio rig around target (camera assumed on -Y): large key front-left,
    dim fill front-right, strong rim from behind. azimuth rotates the rig (degrees)."""
    c = target_center(state, target)
    mn, mx = target_bounds(state, target)
    radius = max((mx - mn).length / 2, 0.5)
    d = float(distance or radius * 3.2)
    base = 40.0 * d * d * float(intensity)
    rig = [("Key", -50, 45, 1.0, key_temperature, key_color, 1.2),
           ("Fill", 55, 10, fill_ratio, fill_temperature, None, 1.6),
           ("Rim", 160, 40, rim_ratio, rim_temperature, rim_color, 0.6)]
    names = []
    for label, az, el, ratio, temp, col, sz in rig:
        a = math.radians(az + azimuth - 90)  # az 0 = camera side (-Y)
        e = math.radians(el)
        pos = c + mathutils.Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e))) * d
        names.append(light(state, "AREA", name=f"{prefix}{label}", location=pos, target=list(c),
                           energy=base * ratio, color=col or "#ffffff", temperature=None if col else temp,
                           size=d * 0.45 * sz * softness))
    return names


def rim_light(state, target=None, side="left", energy=None, color="#ffffff", temperature=None, distance=None, **_):
    """Tall strip light behind the subject to draw a bright edge."""
    c = target_center(state, target)
    mn, mx = target_bounds(state, target)
    d = float(distance or max((mx - mn).length, 1.0) * 1.4)
    sx = -1 if side == "left" else 1
    pos = c + mathutils.Vector((sx * d * 0.8, d * 0.9, d * 0.3))
    return light(state, "AREA", name=f"Rim_{side}", location=pos, target=list(c), energy=energy or 70 * d * d,
                 color=color, temperature=temperature, size=d * 0.12, size_y=d * 0.9, shape="RECTANGLE")


def light_sweep(state, target=None, frame_start=None, frame_end=None, energy=None, color="#fff2d6",
                name="SweepLight", easing="sine_in_out", link=True, **_):
    """Animated strip light sliding in front of the subject -> moving specular glint across
    metallic surfaces (the classic gold-logo shine). link=True restricts it to the target
    (no streak reflected in floors)."""
    from . import animate
    c = target_center(state, target)
    mn, mx = target_bounds(state, target)
    w = max(mx.x - mn.x, 1.0)
    h = max(mx.z - mn.z, 0.5)
    d = max(w * 0.6, 1.5)
    n = light(state, "AREA", name=name, location=c, rotation=[90, 0, 0], energy=energy or 90 * d * d,
              color=color, size=w * 0.06, size_y=h * 4, shape="RECTANGLE")
    fs, fe = util.scene_frames()
    animate.animate(state, target=n, property="location", frame_start=frame_start or fs, frame_end=frame_end or fe,
                    from_value=list(c + mathutils.Vector((-w * 0.9, -d, h * 0.3))),
                    to_value=list(c + mathutils.Vector((w * 0.9, -d, h * 0.3))), easing=easing)
    if link and isinstance(target, str):
        light_link(state, n, [target])
    return n


def hdri_light(state, path, strength=1.0, rotation=0.0, background=True, **kw):
    """Shortcut for world_hdri (image based lighting)."""
    from . import scene
    return scene.world_hdri(state, path=path, strength=strength, rotation=rotation, background=background, **kw)


def god_rays(state, target=None, azimuth=150.0, elevation=40.0, density=0.03, energy=None, color="#ffe7c2",
             spot_size=35.0, distance=None, anisotropy=0.6, **_):
    """Volumetric light shafts: strong spot from behind/above (azimuth 0 = camera side) plus a fog box.
    Shafts appear where geometry occludes the beam. Best in Cycles (slow on CPU: keep samples low)."""
    from . import scene
    c = target_center(state, target)
    mn, mx = util.world_bbox(util.renderable_objects())
    d = float(distance or max((mx - mn).length, 2.0) * 2.0)
    az, el = math.radians(azimuth - 90), math.radians(elevation)
    pos = c + mathutils.Vector((math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el))) * d
    n = light(state, "SPOT", name="GodRaySpot", location=pos, target=list(c),
              energy=energy or 400 * d * d, color=color, spot_size=spot_size, spot_blend=0.4, radius=0.02)
    scene.fog(state, density=density, mode="box", anisotropy=anisotropy, size=[d * 2.2] * 3, name="GodRayVolume")
    return n


def light_link(state, light, receivers, name=None, **_):
    """Light linking: the light only illuminates (and only reflects in) the receiver objects.
    Great for glints/rims that must not show up in floors or backdrops. Cycles + EEVEE."""
    lo = util.get_obj(state, light)
    objs = util.get_objs(state, receivers)
    objs = objs + [c for o in objs for c in o.children_recursive]
    coll = bpy.data.collections.new(name or f"{lo.name}_receivers")
    for o in objs:
        if o.name not in coll.objects:
            coll.objects.link(o)
    lo.light_linking.receiver_collection = coll
    return {"light": lo.name, "receivers": len(objs)}


OPS = {
    "light_link": light_link,
    "light": light,
    "three_point": three_point,
    "rim_light": rim_light,
    "light_sweep": light_sweep,
    "hdri_light": hdri_light,
    "god_rays": god_rays,
}
