"""High-level one-op scenes with cinematic defaults: product_shot, logo_reveal, title_card,
turntable. Each builds geometry, materials, lights, camera, animation and post effects;
everything stays editable by later steps (objects are registered by name)."""
import math

import bpy

from . import animate, camera, lights, materials, objects, render, scene, text3d, util
from .util import log

THEMES = {
    "dark":  {"top": "#16181d", "bottom": "#040405", "backdrop": "#121317", "floor_rough": 0.35},
    "warm":  {"top": "#2a1d14", "bottom": "#080504", "backdrop": "#1d1510", "floor_rough": 0.35},
    "cool":  {"top": "#121a26", "bottom": "#030508", "backdrop": "#0f141c", "floor_rough": 0.3},
    "light": {"top": "#f3f1ee", "bottom": "#cfccc7", "backdrop": "#e9e6e1", "floor_rough": 0.6},
    "black": {"top": "#050505", "bottom": "#000000", "backdrop": "#050505", "floor_rough": 0.18},
}


def _subject(state, subject, model, material, size):
    if model:
        name = objects.import_model(state, model, normalize=size, material=material)
    elif subject:
        name = util.get_obj(state, subject).name
        if material:
            materials.assign(state, util.get_obj(state, name), material)
    else:
        name = objects.rounded_box(state, size=[size * 0.6, size * 0.6, size], radius=size * 0.08, name="Product",
                                   location=[0, 0, size / 2], material=material or "glossy_plastic")
    return name


def _drop_to(state, name, z):
    obj = util.get_obj(state, name)
    bpy.context.view_layer.update()
    mn, mx = util.world_bbox([obj] + list(obj.children_recursive))
    obj.location.z += z - mn.z
    return obj


def product_shot(state, subject=None, model=None, material=None, theme="dark", plinth=True, plinth_material="marble",
                 size=2.0, angle=25.0, elevation=0.18, lens=70.0, fstop=3.2, margin=1.2, accent=None, bloom=True,
                 key_temperature=5600, **_):
    """Premium studio still: seamless sweep, optional marble plinth, soft 3-point light + twin rim
    strips (gives glossy edge reflections), framed camera with shallow DOF, bloom + vignette.
    subject: existing object name | model: file to import (normalized to `size`) | neither: a box.
    theme: dark | warm | cool | light | black. angle: camera azimuth degrees. Returns subject name."""
    th = THEMES.get(theme, THEMES["dark"])
    scene.world_gradient(state, top=th["top"], bottom=th["bottom"], strength=0.6)
    objects.backdrop(state, name="Sweep", color=th["backdrop"], roughness=th["floor_rough"], width=size * 22,
                     depth=size * 12, height=size * 8, curve_radius=size * 2.2, location=[0, size * 2.2, 0])
    base_z = 0.0
    if plinth:
        pm = plinth_material if isinstance(plinth_material, (dict,)) else (
            materials.make_material(state, name="PlinthMat", preset=plinth_material, color2="#5c5f66", scale=3)
            if plinth_material in materials.PRESETS else plinth_material)
        objects.add_primitive(state, "cylinder", name="Plinth", size=size * 1.35, depth=size * 0.22,
                              location=[0, 0, size * 0.11], segments=128, smooth=True, material=pm,
                              bevel={"width": size * 0.01, "segments": 4})
        base_z = size * 0.22
    name = _subject(state, subject, model, material, size)
    _drop_to(state, name, base_z)
    lights.three_point(state, target=name, key_temperature=key_temperature, rim_ratio=1.5)
    lights.rim_light(state, target=name, side="left", temperature=6500, color=accent or "#ffffff")
    lights.rim_light(state, target=name, side="right", temperature=4300)
    a = math.radians(angle)
    cam = camera.camera(state, name="Camera", location=[0, -10, 2], target=name, lens=lens)
    framed = [name] + (["Plinth"] if plinth else [])
    camera.frame_objects(state, targets=framed, direction=[math.sin(a), -math.cos(a), elevation], margin=margin)
    if fstop:
        camera.dof(state, camera=cam, fstop=fstop)
    render.compositor(state, bloom={"threshold": 0.9, "strength": 0.3} if bloom else None,
                      vignette={"strength": 0.3})
    return name


def _dust(state, center, extent, count=220, color="#ffd9a0", seed=7):
    em = objects.add_primitive(state, "cube", name="DustVolume", size=1.0, location=list(center))
    o = util.get_obj(state, em)
    o.scale = extent
    o.hide_render = True
    o["blpro_backdrop"] = True
    mote = objects.add_primitive(state, "ico_sphere", name="DustMote", size=1.0, subdivisions=1,
                                 location=[0, 0, -500])
    m = materials.make_material(state, name="DustGlow", preset="emission", color=color, emission_strength=6.0)
    materials.assign(state, util.get_obj(state, mote), m)
    sc = bpy.context.scene
    animate.particles(state, em, count=count, frame_start=sc.frame_start - 200, frame_end=sc.frame_start - 199,
                      lifetime=2000, velocity=0.0, random_velocity=0.02, gravity=0.0, size=0.008, size_random=0.8,
                      instance=mote, emit_from="VOLUME", seed=seed)
    ps = o.particle_systems[0].settings
    ps.brownian_factor = 0.02
    ps.use_rotations = False
    util.get_obj(state, mote).hide_render = True
    return em


def logo_reveal(state, text="LOGO", subtitle=None, font=None, subtitle_font=None, material="gold", theme="black",
                style="rise", frame_start=None, reveal_frames=36, stagger=None, size=1.0, extrude=0.14,
                bevel=0.022, sweep=True, dust=True, reflective_floor=True, push_in=0.12, accent="#ffcc7a",
                bloom=0.55, **_):
    """Cinematic logo/word reveal (Arabic-ready): beveled metal letters rise in with stagger
    (right-to-left for Arabic), a light sweep glints across them, golden dust floats, glossy
    floor reflection, slow camera push-in, bloom + vignette + subtle chromatic aberration.
    material: preset/name (gold, chrome, rose_gold, ...). Returns the text group name."""
    sc = bpy.context.scene
    fs = int(frame_start if frame_start is not None else sc.frame_start + 6)
    th = THEMES.get(theme, THEMES["black"])
    scene.world_gradient(state, top=th["top"], bottom=th["bottom"], strength=0.4, light_strength=0.15)
    arabic = text3d.has_arabic(text)
    z = size * (1.35 if subtitle else 0.8)
    mat = material if (isinstance(material, str) and util.get_mat(state, material, False)) else \
        materials.make_material(state, name="LogoMetal", preset=material if material in materials.PRESETS else "gold")
    grp = text3d.text3d(state, text, name="Logo", font=font, size=size, extrude=extrude, bevel_depth=bevel,
                        bevel_resolution=4, location=[0, 0, z], material=mat, split=True)
    st = stagger if stagger is not None else max(1, int(14 / max(1, len(text3d.text_parts(state, grp)))) + 1)
    text3d.text_reveal(state, grp, style=style, frame_start=fs, duration=reveal_frames, stagger=st)
    parts = text3d.text_parts(state, grp)
    mn, mx = util.world_bbox(parts)
    width = max(mx.x - mn.x, 1.0)
    sub_name = None
    if subtitle:
        sub_mat = materials.make_material(state, name="SubtitleMat", preset="emission", color="#f4e6c8",
                                          emission_strength=2.5)
        sub_name = text3d.text3d(state, subtitle, name="Subtitle", font=subtitle_font or font, size=size * 0.22,
                                 extrude=0.0, bevel_depth=0.0, location=[0, 0, z - size * 0.78], material=sub_mat,
                                 letter_spacing=1.0 if text3d.has_arabic(subtitle) else 1.25)
        sub_start = fs + reveal_frames + st * len(parts) // 2
        animate.fade(state, sub_name, 0.0, 1.0, sub_start, sub_start + 24)
        animate.animate(state, target=sub_name, property="location", from_value=[0, 0, -0.08], to_value=[0, 0, 0],
                        relative=True, frame_start=sub_start, frame_end=sub_start + 30, easing="expo_out", hold=True)
        o = util.get_obj(state, sub_name)
        c = list(o.color)
        c[3] = 0.0
        o.color = c
        o.keyframe_insert("color", index=3, frame=sc.frame_start)
    if reflective_floor:
        objects.floor(state, name="Floor", size=width * 30, color="#050505", roughness=0.12)
    # lighting: top key, two rims, sweep glint
    c = (mn + mx) / 2
    lights.light(state, "AREA", name="TopKey", location=[0, -width * 0.6, z + width * 1.2], target=list(c),
                 energy=60 * width * width, size=width * 1.4, temperature=5200)
    logo_objs = [grp] + ([sub_name] if sub_name else [])
    for nm, x, kw in (("RimL", -1, {"color": accent}), ("RimR", 1, {"temperature": 6500})):
        lights.light(state, "AREA", name=nm, location=[x * width * 0.9, width * 0.7, z + width * 0.5],
                     target=list(c), energy=45 * width * width, size=width * 0.25, **kw)
        lights.light_link(state, nm, logo_objs)
    lights.light(state, "AREA", name="FrontFill", location=[0, -width * 2.2, z], target=list(c),
                 energy=10 * width * width, size=width * 2, temperature=4800)
    lights.light_link(state, "FrontFill", logo_objs)
    if sweep:
        lights.light_sweep(state, target=grp, frame_start=fs + reveal_frames // 2,
                           frame_end=min(sc.frame_end, fs + reveal_frames + 60), color="#fff1d0")
    if dust:
        _dust(state, [c.x, c.y + 0.5, c.z], (width * 2.2, width * 1.2, width * 0.9), color=accent)
    cam = camera.camera(state, name="Camera", location=[0, -10, z], target=grp, lens=50)
    framed = [grp] + ([sub_name] if sub_name else [])
    camera.frame_objects(state, targets=framed, direction=[0, -1, 0.12], margin=1.45)
    camera.dof(state, camera=cam, fstop=4.0)
    if push_in:
        camera.camera_push_in(state, amount=push_in, frame_start=sc.frame_start, frame_end=sc.frame_end,
                              easing="linear")
    render.compositor(state, bloom={"threshold": 0.8, "strength": float(bloom), "size": 0.7},
                      vignette={"strength": 0.45}, lens={"distortion": -0.01, "dispersion": 0.006})
    log(f"logo_reveal: {len(parts)} parts, {'RTL' if arabic else 'LTR'}, reveal starts at {fs}")
    return grp


PALETTES = {
    "midnight": {"bg_top": "#1b2140", "bg_bottom": "#06070d", "title": "#f5f1e8", "accent": "#7aa2ff"},
    "sunset":   {"bg_top": "#ff8a5b", "bg_bottom": "#3a0f2e", "title": "#fff7ec", "accent": "#ffd166"},
    "emerald":  {"bg_top": "#0f3d36", "bg_bottom": "#021210", "title": "#f2fff9", "accent": "#5af2c3"},
    "mono":     {"bg_top": "#2b2b2b", "bg_bottom": "#050505", "title": "#ffffff", "accent": "#bbbbbb"},
    "royal":    {"bg_top": "#2a1650", "bg_bottom": "#07030f", "title": "#f7e7b4", "accent": "#d4a640"},
}


def title_card(state, title="TITLE", subtitle=None, palette="midnight", font=None, subtitle_font=None, size=1.0,
               style="slide", material=None, frame_start=None, glow_line=True, **_):
    """Editorial title card: big clean extruded title on a soft gradient backdrop with a thin
    glowing accent line, subtitle fade, gentle camera drift. palette: midnight | sunset |
    emerald | mono | royal. material defaults to a satin title color."""
    sc = bpy.context.scene
    pal = PALETTES.get(palette, PALETTES["midnight"])
    fs = int(frame_start if frame_start is not None else sc.frame_start + 4)
    scene.world_color(state, color=pal["bg_bottom"], strength=0.3)
    back = objects.add_primitive(state, "plane", name="BackPlane", size=60, location=[0, 6, 0], rotation=[90, 0, 0])
    bm = materials.material_graph(state, name="BackGradient", nodes={
        "tc": {"type": "ShaderNodeTexCoord"},
        "grad": {"type": "ShaderNodeTexGradient", "props": {"gradient_type": "SPHERICAL"}},
        "map": {"type": "ShaderNodeMapping", "inputs": {"Scale": [0.08, 0.14, 1], "Location": [0, 0.02, 0]}},
        "ramp": {"type": "ShaderNodeValToRGB"},
        "em": {"type": "ShaderNodeEmission", "inputs": {"Strength": 1.0}},
    }, links=[["tc.Object", "map.Vector"], ["map.Vector", "grad.Vector"], ["grad.Fac", "ramp.Fac"],
              ["ramp.Color", "em.Color"], ["em.Emission", "Material Output.Surface"]])
    mt = util.get_mat(state, bm)
    ramp = mt.node_tree.nodes["ramp"].color_ramp
    ramp.elements[0].color = util.color(pal["bg_bottom"])
    ramp.elements[1].color = util.color(pal["bg_top"])
    ramp.elements[1].position = 0.9
    materials.assign(state, util.get_obj(state, back), bm)
    util.get_obj(state, back)["blpro_backdrop"] = True
    tm = material or materials.make_material(state, name="TitleSatin", preset="plastic", color=pal["title"],
                                             roughness=0.32, coat=0.4)
    grp = text3d.text3d(state, title, name="Title", font=font, size=size, extrude=0.06, bevel_depth=0.012,
                        location=[0, 0, 0.25 * size], material=tm, split=True)
    text3d.text_reveal(state, grp, style=style, frame_start=fs, duration=30, stagger=2)
    mn, mx = util.world_bbox(text3d.text_parts(state, grp))
    w = max(mx.x - mn.x, 1.0)
    framed = [grp]
    if glow_line:
        ln = objects.add_primitive(state, "cube", name="AccentLine", size=1.0, location=[0, 0, mn.z - 0.22 * size])
        lo = util.get_obj(state, ln)
        lo.scale = (w * 0.5, 0.01, 0.012)
        materials.assign(state, lo, materials.make_material(state, name="AccentGlow", preset="emission",
                                                            color=pal["accent"], emission_strength=12))
        animate.animate(state, target=ln, property="scale", from_value=[0.0, 0.01, 0.012], to_value=[w * 0.5, 0.01, 0.012],
                        frame_start=fs + 10, frame_end=fs + 40, easing="expo_out", hold=True)
    if subtitle:
        sm = materials.make_material(state, name="SubtitleMat", preset="emission", color=pal["accent"], emission_strength=2.0)
        sub = text3d.text3d(state, subtitle, name="Subtitle", font=subtitle_font or font, size=size * 0.24,
                            extrude=0.0, bevel_depth=0.0, location=[0, 0, mn.z - 0.55 * size], material=sm,
                            letter_spacing=1.0 if text3d.has_arabic(subtitle) else 1.3)
        animate.fade(state, sub, 0.0, 1.0, fs + 26, fs + 50)
        o = util.get_obj(state, sub)
        c = list(o.color)
        c[3] = 0
        o.color = c
        o.keyframe_insert("color", index=3, frame=sc.frame_start)
        framed.append(sub)
    lights.light(state, "AREA", name="Key", location=[-w * 0.8, -w * 1.2, w], target=[0, 0, 0],
                 energy=50 * w * w, size=w * 1.5, temperature=5600)
    lights.light(state, "AREA", name="Rim", location=[w, w * 0.4, w * 0.6], target=[0, 0, 0],
                 energy=40 * w * w, size=w * 0.5, color=pal["accent"])
    camera.camera(state, name="Camera", location=[0, -10, 0], target=grp, lens=60)
    camera.frame_objects(state, targets=framed, direction=[0.06, -1, 0.05], margin=1.5)
    camera.camera_push_in(state, amount=0.08, frame_start=sc.frame_start, frame_end=sc.frame_end, easing="linear")
    camera.camera_shake(state, strength=0.004, speed=40)
    render.compositor(state, bloom={"threshold": 0.9, "strength": 0.4}, vignette={"strength": 0.35})
    return grp


def turntable(state, subject=None, model=None, material=None, theme="dark", frames=None, degrees=360.0,
              rotate="subject", plinth=True, size=2.0, **kw):
    """Seamless 360 product turntable (loops perfectly): product_shot staging + linear rotation of
    the subject (rotate='subject', plinth spins too) or of the camera (rotate='camera')."""
    sc = bpy.context.scene
    if frames:
        sc.frame_end = sc.frame_start + int(frames) - 1
    name = product_shot(state, subject=subject, model=model, material=material, theme=theme, plinth=plinth,
                        size=size, fstop=kw.pop("fstop", 5.6), **kw)
    if rotate == "camera":
        camera.camera_orbit(state, target=name, start_angle=0, end_angle=degrees, easing="linear", cyclic=True)
    else:
        piv = objects.empty(state, name="TurntablePivot", location=[0, 0, 0])
        objects.set_parent(state, child=[name] + (["Plinth"] if plinth else []), parent=piv)
        animate.turntable(state, piv, degrees=degrees, easing="linear", cyclic=True)
    return name


OPS = {
    "product_shot": product_shot,
    "logo_reveal": logo_reveal,
    "title_card": title_card,
    "turntable_scene": turntable,
}
