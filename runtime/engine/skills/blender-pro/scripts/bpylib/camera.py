"""Camera: creation, lens/DOF, track-to via an aim empty, auto framing, and cinematic moves
(orbit, dolly, push-in, crane, zoom, rack focus, follow path, handheld shake) with easing.

Design: a camera made with a target tracks an AIM EMPTY named '<Camera>_Aim' (Track To
constraint). Moving/shaking the aim empty re-aims the camera; camera_shake adds noise to both."""
import math

import bpy
import mathutils

from . import util
from .lights import target_center, target_bounds


def _cam(state, camera=None):
    if camera:
        return util.get_obj(state, camera)
    cam = bpy.context.scene.camera
    if cam is None:
        raise RuntimeError("no camera: add one with the 'camera' op first")
    return cam


def _aim(state, cam, create_at=None):
    name = f"{cam.name}_Aim"
    aim = bpy.data.objects.get(name)
    if aim is None and create_at is not None:
        aim = util.new_object(name, None)
        aim.empty_display_size = 0.3
        aim.location = util.vec3(create_at)
        util.register(state, aim, name)
    return aim


def track_to(state, target, aim, up="UP_Y", **_):
    """Make object `target` (camera/light/any) face object/point `aim` via Track To constraint."""
    obj = util.get_obj(state, target)
    if isinstance(aim, (list, tuple)):
        e = util.new_object(f"{obj.name}_Aim", None)
        e.location = util.vec3(aim)
        aim_obj = util.register(state, e, e.name)
    else:
        aim_obj = util.get_obj(state, aim)
    for c in [c for c in obj.constraints if c.type == "TRACK_TO"]:
        obj.constraints.remove(c)
    c = obj.constraints.new("TRACK_TO")
    c.target = aim_obj
    c.track_axis = "TRACK_NEGATIVE_Z"
    c.up_axis = up
    return {"object": obj.name, "aim": aim_obj.name}


def camera(state, name="Camera", location=(0, -8, 2), target=None, look_at=None, lens=50.0, sensor=36.0,
           type="PERSP", ortho_scale=6.0, clip_start=0.05, clip_end=500.0, fstop=None, focus=None,
           shift_x=0.0, shift_y=0.0, active=True, rotation=None, follow_target=False, **_):
    """Add a camera. target: object name or [x,y,z] -> tracked through an aim empty at its center
    (follow_target=True parents the aim to the object so the camera follows it).
    fstop enables depth of field (focus defaults to the target). lens in mm."""
    cd = bpy.data.cameras.new(name)
    cd.type = type.upper()
    cd.lens = float(lens)
    cd.sensor_width = float(sensor)
    cd.ortho_scale = float(ortho_scale)
    cd.clip_start, cd.clip_end = float(clip_start), float(clip_end)
    cd.shift_x, cd.shift_y = float(shift_x), float(shift_y)
    cam = util.new_object(name, cd)
    cam.location = util.vec3(location)
    util.register(state, cam, name)
    aim_point = target if target is not None else look_at
    if aim_point is not None:
        c = target_center(state, aim_point)
        aim = _aim(state, cam, create_at=c)
        if follow_target and isinstance(target, str):
            tgt = util.get_obj(state, target)
            aim.parent = tgt
            aim.matrix_parent_inverse = tgt.matrix_world.inverted()
        track_to(state, cam.name, aim.name)
    elif rotation is not None:
        cam.rotation_euler = util.rad3(rotation)
    if fstop:
        dof(state, camera=cam.name, fstop=fstop, focus=focus if focus is not None else (target if isinstance(target, str) else None))
    if active:
        bpy.context.scene.camera = cam
    return cam.name


def dof(state, camera=None, fstop=2.8, focus=None, distance=None, blades=0, **_):
    """Depth of field. focus: object name (tracked) or None to use distance / aim empty."""
    cam = _cam(state, camera)
    d = cam.data.dof
    d.use_dof = True
    d.aperture_fstop = float(fstop)
    d.aperture_blades = int(blades)
    if isinstance(focus, str):
        d.focus_object = util.get_obj(state, focus)
    elif distance is not None:
        d.focus_distance = float(distance)
    else:
        aim = _aim(state, cam)
        if aim is not None:
            d.focus_object = aim
        else:
            mn, mx = util.world_bbox(util.renderable_objects())
            d.focus_distance = (cam.location - (mn + mx) / 2).length
    return {"camera": cam.name}


def frame_objects(state, targets=None, camera=None, direction=(0, -1, 0.3), margin=1.15, lens=None,
                  create=True, name="Camera", **_):
    """Place the camera so targets (default: all renderable non-backdrop objects) fill the frame.
    direction: vector from subject toward the camera. margin > 1 adds breathing room.
    Creates a camera if none exists. The camera tracks an aim empty at the subject center."""
    sc = bpy.context.scene
    objs = util.get_objs(state, targets) if targets else util.renderable_objects()
    if targets:
        objs = objs + [c for o in objs for c in o.children_recursive]
    bpy.context.view_layer.update()
    mn, mx = util.world_bbox(objs)
    center = (mn + mx) / 2
    cam = None
    if camera or sc.camera:
        cam = _cam(state, camera)
    elif create:
        cam = util.get_obj(state, globals()["camera"](state, name=name, location=(0, -10, 2)))
    if lens:
        cam.data.lens = float(lens)
    fwd = -util.vec3(direction).normalized()  # camera looks along fwd
    up = mathutils.Vector((0, 0, 1))
    right = fwd.cross(up)
    if right.length < 1e-6:
        right = mathutils.Vector((1, 0, 0))
    right.normalize()
    cup = right.cross(fwd).normalized()
    aspect = (sc.render.resolution_x * sc.render.pixel_aspect_x) / (sc.render.resolution_y * sc.render.pixel_aspect_y)
    cd = cam.data
    if cd.sensor_fit == "VERTICAL":
        fov_v = 2 * math.atan(cd.sensor_height / (2 * cd.lens))
        fov_h = 2 * math.atan(math.tan(fov_v / 2) * aspect)
    else:
        fov_x = 2 * math.atan(cd.sensor_width / (2 * cd.lens))
        if aspect >= 1:
            fov_h, fov_v = fov_x, 2 * math.atan(math.tan(fov_x / 2) / aspect)
        else:
            fov_v, fov_h = fov_x, 2 * math.atan(math.tan(fov_x / 2) * aspect)
    th, tv = math.tan(fov_h / 2), math.tan(fov_v / 2)
    dist = 0.0
    for x in (mn.x, mx.x):
        for y in (mn.y, mx.y):
            for z in (mn.z, mx.z):
                p = mathutils.Vector((x, y, z)) - center
                px, py, pz = p.dot(right), p.dot(cup), p.dot(fwd)
                dist = max(dist, abs(px) * margin / th + pz, abs(py) * margin / tv + pz)
    dist = max(dist, 0.5)
    cam.location = center - fwd * dist
    aim = _aim(state, cam, create_at=center)
    aim.location = center
    if not any(c.type == "TRACK_TO" for c in cam.constraints):
        track_to(state, cam.name, aim.name)
    cd.clip_end = max(cd.clip_end, dist * 10)
    sc.camera = cam
    return {"camera": cam.name, "distance": round(dist, 3), "center": [round(v, 3) for v in center]}


# --------------------------------------------------------------------------- moves
def _frames(frame_start, frame_end):
    sc = bpy.context.scene
    return int(frame_start if frame_start is not None else sc.frame_start), int(frame_end if frame_end is not None else sc.frame_end)


def camera_move(state, keys, camera=None, easing="smooth", **_):
    """Generic keyed move: keys [{frame, location?, aim?, lens?, fstop?, easing?}].
    'aim' moves the aim empty (where the camera looks)."""
    cam = _cam(state, camera)
    for k in keys:
        e = k.get("easing", easing)
        f = int(k["frame"])
        if "location" in k:
            util.set_key(cam, "location", list(util.vec3(k["location"])), f, easing=e)
        if "aim" in k:
            aim = _aim(state, cam, create_at=k["aim"])
            if not any(c.type == "TRACK_TO" for c in cam.constraints):
                track_to(state, cam.name, aim.name)
            util.set_key(aim, "location", list(util.vec3(k["aim"])), f, easing=e)
        if "lens" in k:
            util.set_key(cam.data, "lens", float(k["lens"]), f, easing=e)
        if "fstop" in k:
            util.set_key(cam.data, "dof.aperture_fstop", float(k["fstop"]), f, easing=e)
    return {"camera": cam.name, "keys": len(keys)}


def camera_orbit(state, target=None, camera=None, radius=None, height=None, start_angle=-30.0, end_angle=30.0,
                 frame_start=None, frame_end=None, easing="sine_in_out", cyclic=False, **_):
    """Orbit around target: camera is parented to a pivot empty at the target center which rotates
    from start_angle to end_angle (degrees, 0 = camera on -Y). Full loop: 0 -> 360, easing linear, cyclic."""
    cam = _cam(state, camera)
    c = target_center(state, target)
    rel = cam.location - c
    r = float(radius) if radius is not None else max(math.hypot(rel.x, rel.y), 1.0)
    h = float(height) if height is not None else rel.z
    pivot = util.new_object(f"{cam.name}_Pivot", None)
    pivot.location = c
    util.register(state, pivot, pivot.name)
    cam.parent = pivot
    cam.matrix_parent_inverse = mathutils.Matrix()
    cam.location = (0, -r, h)
    aim = _aim(state, cam, create_at=c)
    if not any(x.type == "TRACK_TO" for x in cam.constraints):
        track_to(state, cam.name, aim.name)
    fs, fe = _frames(frame_start, frame_end)
    util.set_key(pivot, "rotation_euler", math.radians(start_angle), fs, index=2, easing=easing)
    util.set_key(pivot, "rotation_euler", math.radians(end_angle), fe + (1 if cyclic else 0), index=2, easing=easing)
    if cyclic:
        util.set_cyclic(pivot)
    return {"camera": cam.name, "pivot": pivot.name}


def camera_dolly(state, from_location=None, to_location=None, camera=None, frame_start=None, frame_end=None,
                 easing="sine_in_out", **_):
    """Straight move between two locations (aim stays locked)."""
    cam = _cam(state, camera)
    fs, fe = _frames(frame_start, frame_end)
    a = util.vec3(from_location) if from_location is not None else cam.location.copy()
    b = util.vec3(to_location)
    util.set_key(cam, "location", list(a), fs, easing=easing)
    util.set_key(cam, "location", list(b), fe, easing=easing)
    return {"camera": cam.name}


def camera_push_in(state, amount=0.3, target=None, camera=None, frame_start=None, frame_end=None,
                   easing="sine_in_out", reverse=False, **_):
    """Move toward the subject by `amount` (fraction of current distance). reverse=True pulls out."""
    cam = _cam(state, camera)
    aim = _aim(state, cam)
    c = target_center(state, target) if target is not None else (aim.location.copy() if aim else target_center(state, None))
    start = cam.location.copy()
    end = start + (c - start) * float(amount)
    if reverse:
        start, end = end, start
    return camera_dolly(state, list(start), list(end), cam.name, frame_start, frame_end, easing)


def camera_crane(state, from_height=None, to_height=None, camera=None, frame_start=None, frame_end=None,
                 easing="sine_in_out", **_):
    """Vertical crane move (aim stays on subject, so the angle changes naturally)."""
    cam = _cam(state, camera)
    a = cam.location.copy()
    if from_height is not None:
        a.z = float(from_height)
    b = a.copy()
    b.z = float(to_height if to_height is not None else a.z + 2.0)
    return camera_dolly(state, list(a), list(b), cam.name, frame_start, frame_end, easing)


def camera_zoom(state, from_lens=35.0, to_lens=85.0, camera=None, frame_start=None, frame_end=None,
                easing="sine_in_out", dolly_zoom=False, **_):
    """Animate focal length. dolly_zoom=True also moves the camera to keep the subject size (vertigo)."""
    cam = _cam(state, camera)
    fs, fe = _frames(frame_start, frame_end)
    util.set_key(cam.data, "lens", float(from_lens), fs, easing=easing)
    util.set_key(cam.data, "lens", float(to_lens), fe, easing=easing)
    if dolly_zoom:
        aim = _aim(state, cam)
        c = aim.location if aim else target_center(state, None)
        d0 = (cam.location - c).length
        d1 = d0 * float(to_lens) / float(from_lens)
        dirv = (cam.location - c).normalized()
        util.set_key(cam, "location", list(cam.location), fs, easing=easing)
        util.set_key(cam, "location", list(c + dirv * d1), fe, easing=easing)
    return {"camera": cam.name}


def rack_focus(state, from_target, to_target, camera=None, frame_start=None, frame_end=None, fstop=1.8,
               easing="sine_in_out", **_):
    """Animate focus distance between two objects."""
    cam = _cam(state, camera)
    cam.data.dof.use_dof = True
    cam.data.dof.aperture_fstop = float(fstop)
    cam.data.dof.focus_object = None
    fs, fe = _frames(frame_start, frame_end)
    d0 = (cam.matrix_world.translation - target_center(state, from_target)).length
    d1 = (cam.matrix_world.translation - target_center(state, to_target)).length
    util.set_key(cam.data, "dof.focus_distance", d0, fs, easing=easing)
    util.set_key(cam.data, "dof.focus_distance", d1, fe, easing=easing)
    return {"camera": cam.name}


def camera_shake(state, camera=None, strength=0.03, speed=12.0, rotation=0.0, seed=1, frame_start=None,
                 frame_end=None, **_):
    """Handheld shake: noise on the camera location and its aim (strength in scene units,
    speed = noise period in frames; rotation adds roll jitter in degrees)."""
    from . import animate
    cam = _cam(state, camera)
    kw = dict(frame_start=frame_start, frame_end=frame_end)
    animate.noise(state, cam.name, "location", strength=strength, scale=speed, seed=seed, **kw)
    aim = _aim(state, cam)
    if aim is not None:
        animate.noise(state, aim.name, "location", strength=strength * 1.5, scale=speed * 1.3, seed=seed + 7, **kw)
    else:  # untracked camera: shake its rotation directly (aim noise already rotates tracked cameras)
        rot = rotation or math.degrees(strength) * 0.5
        animate.noise(state, cam.name, "rotation_euler", strength=rot, scale=speed, seed=seed + 3, **kw)
    return {"camera": cam.name}


def follow_path(state, path, target=None, camera=None, frame_start=None, frame_end=None, easing="sine_in_out",
                follow=False, **_):
    """Move an object (default: active camera) along a curve object over the frame range.
    follow=True also rotates it along the curve (otherwise its aim/Track To keeps it pointed)."""
    obj = util.get_obj(state, target) if target else _cam(state, camera)
    curve = util.get_obj(state, path)
    obj.location = (0, 0, 0)
    c = obj.constraints.new("FOLLOW_PATH")
    c.target = curve
    c.use_fixed_location = True
    c.use_curve_follow = bool(follow)
    # keep Track To after Follow Path
    for i, con in enumerate(list(obj.constraints)):
        if con.type == "TRACK_TO":
            obj.constraints.move(i, len(obj.constraints) - 1)
    fs, fe = _frames(frame_start, frame_end)
    path_ = f'constraints["{c.name}"].offset_factor'
    util.set_key(obj, path_, 0.0, fs, easing=easing)
    util.set_key(obj, path_, 1.0, fe, easing=easing)
    return {"object": obj.name, "path": curve.name}


OPS = {
    "camera": camera,
    "dof": dof,
    "track_to": track_to,
    "frame_objects": frame_objects,
    "camera_move": camera_move,
    "camera_orbit": camera_orbit,
    "camera_dolly": camera_dolly,
    "camera_push_in": camera_push_in,
    "camera_crane": camera_crane,
    "camera_zoom": camera_zoom,
    "rack_focus": rack_focus,
    "camera_shake": camera_shake,
    "follow_path": follow_path,
}
