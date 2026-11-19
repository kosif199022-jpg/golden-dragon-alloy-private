"""
blender-pro :: draw  --  Grease Pencil (GPv3, Blender 5.x) drawing control.

Every op has the signature  op(state, **params) -> dict  and is exported in OPS.
Created objects are stored in state["objects"][name]; the "current" drawing
object is state["gp_active"] so later steps may omit "target".

Coordinate system (2D canvas made by gp_canvas):
  * The canvas is the world XZ plane seen by an orthographic camera looking +Y.
  * A point [x, y] maps to world (x, 0, y). Origin is the canvas centre.
  * Canvas width = `width` units (default 16); height follows the aspect ratio
    (16:9 at 1920x1080 -> 16 x 9 units, so x in [-8, 8], y in [-4.5, 4.5]).
  * Stroke `radius` is half the line thickness in world units
    (0.05 on a 16-unit canvas at 1920 px  ~= 12 px wide line).

Colours accept "#RRGGBB" / "#RRGGBBAA" (sRGB hex, converted to linear, renders
exactly as typed under the Standard view transform that gp_canvas sets) or
[r,g,b] / [r,g,b,a] lists (LINEAR 0..1 values, Blender's native space).

This file can also be executed with *system* Python (needs opencv-python)
to trace bitmaps into contour JSON, because Blender's Python has no cv2:
    python draw.py trace input.png out.json [--threshold 128] [--mode contours|edges]
draw_image_trace(method="opencv") calls this automatically.
"""
import json
import math
import os
import random
import re
import subprocess
import sys

try:
    import bpy  # noqa
    import mathutils  # noqa
except ImportError:  # running as plain python helper (trace CLI)
    bpy = None
    mathutils = None


# ---------------------------------------------------------------------------
# Arabic shaping (pure python, no deps) - shared with video.py
# ---------------------------------------------------------------------------
# letter: (isolated, final, initial, medial); None = form does not exist
_AR = {
    0x0621: (0xFE80, None, None, None),
    0x0622: (0xFE81, 0xFE82, None, None), 0x0623: (0xFE83, 0xFE84, None, None),
    0x0624: (0xFE85, 0xFE86, None, None), 0x0625: (0xFE87, 0xFE88, None, None),
    0x0626: (0xFE89, 0xFE8A, 0xFE8B, 0xFE8C), 0x0627: (0xFE8D, 0xFE8E, None, None),
    0x0628: (0xFE8F, 0xFE90, 0xFE91, 0xFE92), 0x0629: (0xFE93, 0xFE94, None, None),
    0x062A: (0xFE95, 0xFE96, 0xFE97, 0xFE98), 0x062B: (0xFE99, 0xFE9A, 0xFE9B, 0xFE9C),
    0x062C: (0xFE9D, 0xFE9E, 0xFE9F, 0xFEA0), 0x062D: (0xFEA1, 0xFEA2, 0xFEA3, 0xFEA4),
    0x062E: (0xFEA5, 0xFEA6, 0xFEA7, 0xFEA8), 0x062F: (0xFEA9, 0xFEAA, None, None),
    0x0630: (0xFEAB, 0xFEAC, None, None), 0x0631: (0xFEAD, 0xFEAE, None, None),
    0x0632: (0xFEAF, 0xFEB0, None, None), 0x0633: (0xFEB1, 0xFEB2, 0xFEB3, 0xFEB4),
    0x0634: (0xFEB5, 0xFEB6, 0xFEB7, 0xFEB8), 0x0635: (0xFEB9, 0xFEBA, 0xFEBB, 0xFEBC),
    0x0636: (0xFEBD, 0xFEBE, 0xFEBF, 0xFEC0), 0x0637: (0xFEC1, 0xFEC2, 0xFEC3, 0xFEC4),
    0x0638: (0xFEC5, 0xFEC6, 0xFEC7, 0xFEC8), 0x0639: (0xFEC9, 0xFECA, 0xFECB, 0xFECC),
    0x063A: (0xFECD, 0xFECE, 0xFECF, 0xFED0), 0x0641: (0xFED1, 0xFED2, 0xFED3, 0xFED4),
    0x0642: (0xFED5, 0xFED6, 0xFED7, 0xFED8), 0x0643: (0xFED9, 0xFEDA, 0xFEDB, 0xFEDC),
    0x0644: (0xFEDD, 0xFEDE, 0xFEDF, 0xFEE0), 0x0645: (0xFEE1, 0xFEE2, 0xFEE3, 0xFEE4),
    0x0646: (0xFEE5, 0xFEE6, 0xFEE7, 0xFEE8), 0x0647: (0xFEE9, 0xFEEA, 0xFEEB, 0xFEEC),
    0x0648: (0xFEED, 0xFEEE, None, None), 0x0649: (0xFEEF, 0xFEF0, None, None),
    0x064A: (0xFEF1, 0xFEF2, 0xFEF3, 0xFEF4),
    0x067E: (0xFB56, 0xFB57, 0xFB58, 0xFB59), 0x0686: (0xFB7A, 0xFB7B, 0xFB7C, 0xFB7D),
    0x0698: (0xFB8A, 0xFB8B, None, None), 0x06A9: (0xFB8E, 0xFB8F, 0xFB90, 0xFB91),
    0x06AF: (0xFB92, 0xFB93, 0xFB94, 0xFB95), 0x06CC: (0xFBFC, 0xFBFD, 0xFBFE, 0xFBFF),
    0x0640: (0x0640, 0x0640, 0x0640, 0x0640),  # tatweel
}
_LAMALEF = {0x0622: (0xFEF5, 0xFEF6), 0x0623: (0xFEF7, 0xFEF8),
            0x0625: (0xFEF9, 0xFEFA), 0x0627: (0xFEFB, 0xFEFC)}


def _transparent(c):
    o = ord(c)
    return 0x064B <= o <= 0x065F or o == 0x0670 or 0x06D6 <= o <= 0x06ED


def _dual(c):
    f = _AR.get(ord(c))
    return bool(f and f[2] is not None)


def has_arabic(text):
    return any(0x0600 <= ord(c) <= 0x06FF or 0x0750 <= ord(c) <= 0x077F for c in text or "")


def _shape_line(line):
    chars = list(line)
    n = len(chars)
    out = []
    i = 0

    def prev_letter(k):
        k -= 1
        while k >= 0 and _transparent(chars[k]):
            k -= 1
        return chars[k] if k >= 0 else None

    def next_letter(k):
        k += 1
        while k < n and _transparent(chars[k]):
            k += 1
        return (chars[k], k) if k < n else (None, None)

    while i < n:
        c = chars[i]
        o = ord(c)
        if o not in _AR:
            out.append(c)
            i += 1
            continue
        p = prev_letter(i)
        joins_prev = p is not None and _dual(p)
        nx, nk = next_letter(i)
        # lam-alef ligature
        if o == 0x0644 and nx is not None and ord(nx) in _LAMALEF:
            iso, fin = _LAMALEF[ord(nx)]
            out.append(chr(fin if joins_prev else iso))
            out.extend(chars[i + 1:nk])  # keep diacritics between
            i = nk + 1
            continue
        forms = _AR[o]
        joins_next = forms[2] is not None and nx is not None and ord(nx) in _AR and ord(nx) != 0x0621
        if joins_prev and joins_next:
            f = forms[3]
        elif joins_prev:
            f = forms[1] if forms[1] is not None else forms[0]
        elif joins_next:
            f = forms[2]
        else:
            f = forms[0]
        out.append(chr(f))
        i += 1
    return "".join(out)


_MIRROR = {"(": ")", ")": "(", "[": "]", "]": "[", "{": "}", "}": "{", "<": ">", ">": "<", "\u00ab": "\u00bb", "\u00bb": "\u00ab"}
_LTR_RUN = re.compile(r"[A-Za-z0-9\u0660-\u0669\u06F0-\u06F9](?:[A-Za-z0-9\u0660-\u0669\u06F0-\u06F9 .,:/%+\-_]*[A-Za-z0-9\u0660-\u0669\u06F0-\u06F9])?")


def shape_arabic(text, reorder=True):
    """Shape Arabic letters into presentation forms and (optionally) convert
    logical order to visual LTR order, line by line. Uses arabic_reshaper +
    python-bidi when importable, else the built-in shaper. Non-Arabic text is
    returned unchanged."""
    if not has_arabic(text):
        return text
    try:
        import arabic_reshaper  # type: ignore
        from bidi.algorithm import get_display  # type: ignore
        shaped = arabic_reshaper.reshape(text)
        return "\n".join(get_display(l) for l in shaped.split("\n")) if reorder else shaped
    except Exception:
        pass
    lines = []
    for line in text.split("\n"):
        s = _shape_line(line)
        if reorder:
            r = "".join(_MIRROR.get(c, c) for c in reversed(s))
            r = _LTR_RUN.sub(lambda m: "".join(_MIRROR.get(c, c) for c in reversed(m.group(0))), r)
            s = r
        lines.append(s)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# generic helpers
# ---------------------------------------------------------------------------
def parse_color(c, default=(0, 0, 0, 1)):
    """'#RRGGBB[AA]' | [r,g,b] | [r,g,b,a] | None -> (r,g,b,a) floats.
    Hex values are sRGB and are converted to linear (what Blender stores)."""
    if c is None:
        return tuple(default)
    if isinstance(c, str):
        h = c.lstrip("#")
        if len(h) in (3, 4):
            h = "".join(ch * 2 for ch in h)
        vals = [int(h[i:i + 2], 16) / 255.0 for i in range(0, len(h), 2)]
        rgb = [_srgb_to_lin(v) for v in vals[:3]]
        a = vals[3] if len(vals) > 3 else 1.0
        return (rgb[0], rgb[1], rgb[2], a)
    c = list(c)
    if len(c) == 3:
        c.append(1.0)
    return tuple(float(v) for v in c[:4])


def _srgb_to_lin(v):
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def _objs(state):
    return state.setdefault("objects", {})


def _scene(state, params=None):
    return bpy.context.scene


def _get_gp(state, target=None, create=True):
    """Resolve a grease pencil object by name/state key, or the active one."""
    o = None
    if target:
        o = _objs(state).get(target) or bpy.data.objects.get(target)
        if o is None and not create:
            raise ValueError("grease pencil object not found: %s" % target)
    else:
        o = state.get("gp_active")
        if o is not None:
            try:
                o.name  # still valid?
            except ReferenceError:
                o = None
    if o is None:
        name = target or "Drawing"
        gp = bpy.data.grease_pencils.new(name)
        o = bpy.data.objects.new(name, gp)
        bpy.context.scene.collection.objects.link(o)
        _objs(state)[name] = o
    if o.type != "GREASEPENCIL":
        raise ValueError("%s is not a GREASEPENCIL object (type %s)" % (o.name, o.type))
    state["gp_active"] = o
    return o


def _layer(obj, name=None):
    gp = obj.data
    name = name or (gp.layers.active.name if gp.layers.active else "Lines")
    L = gp.layers.get(name)
    if L is None:
        L = gp.layers.new(name)
        try:
            L.use_lights = False  # flat 2D colours
        except Exception:
            pass
    return L


def _drawing(obj, layer=None, frame=None):
    scene = bpy.context.scene
    frame = int(scene.frame_start if frame is None else frame)
    L = _layer(obj, layer)
    for fr in L.frames:
        if fr.frame_number == frame:
            return fr.drawing
    return L.frames.new(frame).drawing


def _material(obj, color="#000000", fill=None, name=None, mode="LINE", show_stroke=True):
    """Find or create a GP material for (stroke color, fill color). Returns slot index."""
    sc = parse_color(color)
    fc = parse_color(fill) if fill is not None else None
    key = name or "GP_%s_%s_%s" % ("%.3f-%.3f-%.3f-%.2f" % sc,
                                   ("%.3f-%.3f-%.3f-%.2f" % fc) if fc else "nofill",
                                   mode if show_stroke else "nostroke")
    mat = bpy.data.materials.get(key)
    if mat is None or not mat.is_grease_pencil:
        mat = bpy.data.materials.new(key)
        bpy.data.materials.create_gpencil_data(mat)
        g = mat.grease_pencil
        g.color = sc
        g.show_stroke = bool(show_stroke)
        g.mode = mode
        if fc:
            g.show_fill = True
            g.fill_color = fc
        else:
            g.show_fill = False
    mats = obj.data.materials
    for i, m in enumerate(mats):
        if m == mat:
            return i
    mats.append(mat)
    return len(mats) - 1


def _jitter_points(pts, amount, seed=0, scale=1.0):
    """Hand-drawn wobble: low-frequency smooth noise along the stroke."""
    if not amount:
        return pts
    rnd = random.Random(seed)
    n = len(pts)
    # smooth noise: random control values every ~6 points, interpolated
    step = 6
    ctrl = [(rnd.uniform(-1, 1), rnd.uniform(-1, 1)) for _ in range(n // step + 3)]
    out = []
    for i, p in enumerate(pts):
        t = i / step
        k = int(t)
        f = t - k
        f = f * f * (3 - 2 * f)
        jx = ctrl[k][0] * (1 - f) + ctrl[k + 1][0] * f
        jy = ctrl[k][1] * (1 - f) + ctrl[k + 1][1] * f
        out.append((p[0] + jx * amount * scale, p[1] + jy * amount * scale) + tuple(p[2:]))
    return out


def _resample(pts, max_seg):
    """Insert points so no segment is longer than max_seg (keeps jitter smooth)."""
    if max_seg <= 0 or len(pts) < 2:
        return pts
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        d = math.hypot(b[0] - a[0], b[1] - a[1])
        k = max(1, int(math.ceil(d / max_seg)))
        for j in range(1, k + 1):
            t = j / k
            q = [a[i] + (b[i] - a[i]) * t for i in range(min(len(a), len(b)))]
            out.append(tuple(q))
    return out


def _add_stroke(drawing, pts, radius=0.05, pressure=None, opacity=1.0, mat_index=0,
                cyclic=False, plane="XZ", depth=0.0, caps="ROUND", softness=0.0,
                vertex_colors=None, fill_id=None, taper=0.0):
    """Low level: append one stroke. pts = [(x,y[,p])...] in canvas coords."""
    n = len(pts)
    if n < 1:
        return None
    drawing.add_strokes([n])
    s = drawing.strokes[len(drawing.strokes) - 1]
    s.material_index = mat_index
    s.cyclic = bool(cyclic)
    try:
        s.fill_opacity = 1.0
        s.softness = softness
        s.start_cap = caps
        s.end_cap = caps
    except Exception:
        pass
    if fill_id is not None:
        try:
            s.fill_id = int(fill_id)
        except Exception:
            pass
    for i, p in enumerate(pts):
        x, y = float(p[0]), float(p[1])
        pr = p[2] if len(p) > 2 else (pressure[i] if isinstance(pressure, (list, tuple)) and i < len(pressure) else 1.0)
        if taper and n > 2:
            t = i / (n - 1)
            pr *= min(1.0, (min(t, 1 - t) / max(taper, 1e-6)) * 1.0 + 0.15)
        pt = s.points[i]
        pt.position = (x, depth, y) if plane == "XZ" else (x, y, depth)
        pt.radius = max(1e-5, radius * pr)
        pt.opacity = opacity
        if vertex_colors:
            vc = vertex_colors[i % len(vertex_colors)]
            pt.vertex_color = parse_color(vc)
    return s


def _finish(obj, drawing=None):
    try:
        if drawing is not None:
            drawing.tag_positions_changed()
    except Exception:
        pass
    obj.data.update_tag()


# ---------------------------------------------------------------------------
# shape generators -> list of (x, y) points
# ---------------------------------------------------------------------------
def _bezier_pts(cps, res=24):
    """Cubic bezier chain: [p0, h0, h1, p1, h2, h3, p2, ...]."""
    pts = []
    for k in range(0, len(cps) - 3, 3):
        p0, p1, p2, p3 = cps[k:k + 4]
        for j in range(res + (1 if k + 3 >= len(cps) - 1 else 0)):
            t = j / res
            u = 1 - t
            x = u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0]
            y = u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]
            pts.append((x, y))
    return pts


def shape_points(shape, center=(0, 0), size=(4, 3), r=2.0, rx=None, ry=None, sides=6, points=None,
                 r_inner=None, start_angle=0.0, end_angle=180.0, turns=3, segments=64, rotation=0.0,
                 corner=0.0, p1=None, p2=None):
    cx, cy = center
    rot = math.radians(rotation)
    pts = []
    cyclic = True
    shape = shape.lower()
    if shape == "line":
        p1 = p1 or (cx - r, cy)
        p2 = p2 or (cx + r, cy)
        pts = [tuple(p1), tuple(p2)]
        cyclic = False
    elif shape in ("rect", "rectangle", "square"):
        w, h = (size, size) if isinstance(size, (int, float)) else size
        if corner > 0:
            c = min(corner, w / 2, h / 2)
            quarter = max(4, segments // 8)
            for (qx, qy, a0) in ((w / 2 - c, h / 2 - c, 0), (-w / 2 + c, h / 2 - c, 90),
                                 (-w / 2 + c, -h / 2 + c, 180), (w / 2 - c, -h / 2 + c, 270)):
                for j in range(quarter + 1):
                    a = math.radians(a0 + 90 * j / quarter)
                    pts.append((cx + qx + c * math.cos(a), cy + qy + c * math.sin(a)))
        else:
            pts = [(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2), (cx + w / 2, cy + h / 2), (cx - w / 2, cy + h / 2)]
    elif shape in ("circle", "ellipse"):
        ax = rx if rx is not None else r
        ay = ry if ry is not None else r
        pts = [(cx + ax * math.cos(2 * math.pi * i / segments), cy + ay * math.sin(2 * math.pi * i / segments)) for i in range(segments)]
    elif shape == "polygon":
        pts = [(cx + r * math.cos(math.pi / 2 + 2 * math.pi * i / sides), cy + r * math.sin(math.pi / 2 + 2 * math.pi * i / sides)) for i in range(sides)]
    elif shape == "star":
        ri = r_inner if r_inner is not None else r * 0.45
        for i in range(sides * 2):
            rr = r if i % 2 == 0 else ri
            a = math.pi / 2 + math.pi * i / sides
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    elif shape == "arc":
        a0, a1 = math.radians(start_angle), math.radians(end_angle)
        nseg = max(2, int(segments * abs(a1 - a0) / (2 * math.pi)) + 1)
        ax = rx if rx is not None else r
        ay = ry if ry is not None else r
        pts = [(cx + ax * math.cos(a0 + (a1 - a0) * i / nseg), cy + ay * math.sin(a0 + (a1 - a0) * i / nseg)) for i in range(nseg + 1)]
        cyclic = False
    elif shape == "bezier":
        pts = _bezier_pts([tuple(p) for p in points], res=max(4, segments // 3))
        cyclic = False
    elif shape == "spiral":
        nseg = int(segments * turns)
        pts = [(cx + r * (i / nseg) * math.cos(2 * math.pi * turns * i / nseg), cy + r * (i / nseg) * math.sin(2 * math.pi * turns * i / nseg)) for i in range(nseg + 1)]
        cyclic = False
    elif shape in ("polyline", "path"):
        pts = [tuple(p) for p in points]
        cyclic = False
    else:
        raise ValueError("unknown shape %r" % shape)
    if rot:
        cr, sr = math.cos(rot), math.sin(rot)
        pts = [(cx + (x - cx) * cr - (y - cy) * sr, cy + (x - cx) * sr + (y - cy) * cr) for x, y in pts]
    return pts, cyclic


# ---------------------------------------------------------------------------
# OPS
# ---------------------------------------------------------------------------
def gp_canvas(state, width=16.0, resolution=(1920, 1080), background="#FFFFFF", transparent=False,
              name="Drawing", layer="Lines", fps=None, frame_start=1, frame_end=None, view_transform="Standard",
              clear=True, samples=16):
    """Set up a 2D drawing canvas: ortho camera looking at the XZ plane, flat
    colours, background, and an empty Grease Pencil object to draw on.
    params: width=16 (canvas width in units; height from aspect), resolution=[1920,1080],
      background="#FFFFFF", transparent=False (alpha PNG), name="Drawing", layer="Lines",
      fps=None, frame_start=1, frame_end=None, view_transform="Standard", clear=True
      (delete all existing objects first, e.g. the default cube/light/camera), samples=16 (EEVEE AA samples).
    Canvas coords: x in [-width/2, width/2], y in [-height/2, height/2]."""
    scene = bpy.context.scene
    if clear:
        for o in list(scene.objects):
            bpy.data.objects.remove(o, do_unlink=True)
    rx, ry = int(resolution[0]), int(resolution[1])
    scene.render.resolution_x, scene.render.resolution_y = rx, ry
    scene.render.resolution_percentage = 100
    if fps:
        scene.render.fps = int(round(fps))
        scene.render.fps_base = scene.render.fps / float(fps)
    scene.frame_start = int(frame_start)
    if frame_end:
        scene.frame_end = int(frame_end)
    try:
        scene.render.engine = "BLENDER_EEVEE"
        scene.eevee.taa_render_samples = int(samples)
    except Exception:
        pass
    try:
        scene.view_settings.view_transform = view_transform
        scene.view_settings.look = "None"
    except Exception:
        pass
    height = width * ry / float(rx)
    cam_data = bpy.data.cameras.new("CanvasCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = max(width, height)
    cam = bpy.data.objects.new("CanvasCam", cam_data)
    cam.location = (0, -20, 0)
    cam.rotation_euler = (math.radians(90), 0, 0)
    scene.collection.objects.link(cam)
    scene.camera = cam
    # background
    scene.render.film_transparent = bool(transparent)
    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    bg = parse_color(background)
    try:
        world.use_nodes = True
    except Exception:
        pass
    nt = getattr(world, "node_tree", None)
    if nt is not None:
        bgn = next((n for n in nt.nodes if n.type == "BACKGROUND"), None)
        if bgn is None:
            bgn = nt.nodes.new("ShaderNodeBackground")
            out = next((n for n in nt.nodes if n.type == "OUTPUT_WORLD"), None) or nt.nodes.new("ShaderNodeOutputWorld")
            nt.links.new(bgn.outputs[0], out.inputs[0])
        bgn.inputs[0].default_value = bg
        bgn.inputs[1].default_value = 1.0
    world.color = bg[:3]
    gp = bpy.data.grease_pencils.new(name)
    obj = bpy.data.objects.new(name, gp)
    scene.collection.objects.link(obj)
    _objs(state)[name] = obj
    _objs(state)["CanvasCam"] = cam
    state["gp_active"] = obj
    _layer(obj, layer)
    state["canvas"] = {"width": width, "height": height, "resolution": [rx, ry]}
    return {"object": obj.name, "camera": cam.name, "width": width, "height": height,
            "x_range": [-width / 2, width / 2], "y_range": [-height / 2, height / 2]}


def gp_layer(state, name, target=None, opacity=1.0, blend_mode="REGULAR", hide=False, use_lights=False,
             tint_color=None, tint_factor=0.0, onion=True, active=True):
    """Create/configure a layer on a GP object.
    params: name (required), target=None (GP object, default active), opacity=1.0,
      blend_mode="REGULAR" (REGULAR/HARDLIGHT/ADD/SUBTRACT/MULTIPLY/DIVIDE), hide=False,
      use_lights=False, tint_color=None, tint_factor=0.0, onion=True, active=True."""
    obj = _get_gp(state, target)
    L = _layer(obj, name)
    L.opacity = opacity
    try:
        L.blend_mode = blend_mode
    except Exception:
        pass
    L.hide = hide
    L.use_lights = use_lights
    L.use_onion_skinning = onion
    if tint_color is not None:
        L.tint_color = parse_color(tint_color)[:3]
        L.tint_factor = tint_factor
    if active:
        obj.data.layers.active = L
    return {"object": obj.name, "layer": L.name}


def draw_stroke(state, points, radius=0.05, color="#000000", fill=None, cyclic=False, pressure=None,
                opacity=1.0, target=None, layer=None, frame=None, material=None, jitter=0.0, seed=0,
                taper=0.0, caps="ROUND", softness=0.0, vertex_colors=None, passes=1, resample=0.0,
                stroke=True, smooth=0):
    """Draw one free-hand stroke from a list of points.
    params: points=[[x,y] or [x,y,pressure], ...] (required, canvas units),
      radius=0.05 (half thickness), color="#000000", fill=None (fill colour -> filled
      shape), cyclic=False (close the stroke), pressure=None (list per point, 0..1),
      opacity=1.0, target=None (GP object; default active / auto-created "Drawing"),
      layer=None (default active layer), frame=None (keyframe number; default scene start),
      material=None (force material name), jitter=0.0 (hand-drawn wobble, units),
      seed=0, taper=0.0 (0..0.5 thin the ends), caps="ROUND"|"FLAT", softness=0.0,
      vertex_colors=None (list of colours cycled per point, mixed over material),
      passes=1 (doodle: redraw N times with different jitter seeds), resample=0.0
      (max segment length before jitter; auto when jitter>0), stroke=True (False = fill only),
      smooth=0 (Chaikin smoothing iterations)."""
    obj = _get_gp(state, target)
    d = _drawing(obj, layer, frame)
    mi = _material(obj, color, fill, material, show_stroke=stroke)
    pts = [tuple(p) for p in points]
    for _ in range(int(smooth)):
        pts = _chaikin(pts, cyclic)
    if jitter and not resample:
        resample = max(jitter * 2, 0.05)
    if resample:
        pts = _resample(pts + ([pts[0]] if cyclic else []), resample)
        if cyclic:
            pts = pts[:-1]
    count = 0
    has_fill = fill is not None or bool(obj.data.materials[mi].grease_pencil.show_fill)
    for k in range(max(1, int(passes))):
        p2 = _jitter_points(pts, jitter, seed + k * 101)
        fid = None
        if has_fill and k == 0:  # fill needs a non-zero fill_id (verified 5.2)
            state["fill_counter"] = state.get("fill_counter", 0) + 1
            fid = state["fill_counter"]
        _add_stroke(d, p2, radius if (k or fid is None or stroke) else 0.0001, pressure, opacity, mi,
                    cyclic or has_fill, caps=caps, softness=softness,
                    vertex_colors=vertex_colors, taper=taper, fill_id=fid)
        count += 1
    _finish(obj, d)
    return {"object": obj.name, "strokes": count, "points": len(pts)}


def _chaikin(pts, cyclic):
    if len(pts) < 3:
        return pts
    out = [] if cyclic else [pts[0]]
    seq = pts + ([pts[0]] if cyclic else [])
    for a, b in zip(seq, seq[1:]):
        out.append(tuple(0.75 * a[i] + 0.25 * b[i] for i in range(min(len(a), len(b)))))
        out.append(tuple(0.25 * a[i] + 0.75 * b[i] for i in range(min(len(a), len(b)))))
    if not cyclic:
        out.append(pts[-1])
    return out


def draw_shape(state, shape="circle", center=(0, 0), size=(4, 3), r=2.0, rx=None, ry=None, sides=6,
               points=None, r_inner=None, start_angle=0.0, end_angle=180.0, turns=3, segments=64,
               rotation=0.0, corner=0.0, p1=None, p2=None, **stroke_params):
    """Draw a parametric shape as a stroke.
    shape: line | rect | circle | ellipse | polygon | star | arc | bezier | spiral | polyline
    params: center=[0,0], size=[w,h] (rect), r=2.0 (radius for circle/polygon/star/arc/spiral,
      half-length for default line), rx/ry (ellipse / elliptic arc), sides=6 (polygon sides /
      star points), r_inner (star inner radius, default 0.45*r), start_angle=0/end_angle=180
      (arc, degrees), turns=3 (spiral), segments=64 (smoothness), rotation=0 (degrees),
      corner=0 (rect corner radius), p1/p2 (line end points), points (bezier control chain
      [p0,h0,h1,p1,h2,h3,p2...] or polyline points).
    Plus every draw_stroke param: radius, color, fill, opacity, jitter, passes, taper,
      target, layer, frame, ... (cyclic is decided by the shape unless given)."""
    pts, cyc = shape_points(shape, tuple(center), size, r, rx, ry, int(sides), points, r_inner,
                            start_angle, end_angle, turns, int(segments), rotation, corner, p1, p2)
    stroke_params.setdefault("cyclic", cyc)
    res = draw_stroke(state, pts, **stroke_params)
    res["shape"] = shape
    return res


def _font_default():
    for f in (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\tahoma.ttf", r"C:\Windows\Fonts\segoeui.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"):
        if os.path.exists(f):
            return f
    return None


def text_to_polylines(text, font=None, size=1.0, align="CENTER", resolution=12, shape=True,
                      line_spacing=1.0, letter_spacing=1.0, bold=0.0):
    """Return list of (points, cyclic) outlines of `text` using a temporary
    FONT curve (Blender lays out glyphs, we sample the bezier splines)."""
    body = shape_arabic(text) if shape else text
    cu = bpy.data.curves.new("_tmp_text", "FONT")
    cu.body = body
    font = font or _font_default()
    if font:
        cu.font = bpy.data.fonts.load(font, check_existing=True)
    cu.size = size
    cu.align_x = align
    cu.align_y = "CENTER"
    cu.space_line = line_spacing
    cu.space_character = letter_spacing
    cu.offset = bold
    cu.resolution_u = resolution
    tmp = bpy.data.objects.new("_tmp_text", cu)
    bpy.context.scene.collection.objects.link(tmp)
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = tmp.evaluated_get(dg)
    outlines = []
    try:
        c = ev.to_curve(dg)
        for sp in c.splines:
            pts = []
            if sp.type == "BEZIER":
                bp = sp.bezier_points
                nseg = len(bp) if sp.use_cyclic_u else len(bp) - 1
                for k in range(nseg):
                    a, b = bp[k], bp[(k + 1) % len(bp)]
                    seg = mathutils.geometry.interpolate_bezier(a.co, a.handle_right, b.handle_left, b.co, resolution + 1)
                    pts.extend((v.x, v.y) for v in seg[:-1])
                if not sp.use_cyclic_u:
                    pts.append((bp[-1].co.x, bp[-1].co.y))
            else:
                pts = [(p.co.x, p.co.y) for p in sp.points]
            if len(pts) >= 2:
                outlines.append((pts, bool(sp.use_cyclic_u)))
        ev.to_curve_clear()
    finally:
        bpy.data.objects.remove(tmp, do_unlink=True)
        bpy.data.curves.remove(cu)
    return outlines


def draw_text_outline(state, text, font=None, size=1.5, position=(0, 0), align="CENTER", color="#000000",
                      fill=None, radius=0.02, resolution=12, shape_arabic_text=True, jitter=0.0, seed=0,
                      target=None, layer=None, frame=None, line_spacing=1.0, letter_spacing=1.0,
                      order="ltr", opacity=1.0):
    """Turn text into Grease Pencil outline strokes (optionally filled) via a
    temporary FONT curve. Arabic is auto-shaped (presentation forms + RTL visual
    order) so connected letters render correctly; pass pre-shaped text with
    shape_arabic_text=False if you shaped it yourself.
    params: text (required, "\\n" for new lines), font=None (TTF/OTF path; default Arial on
      Windows - must contain the glyphs, Arabic: arial/tahoma/segoeui/Amiri/Cairo),
      size=1.5 (cap height-ish, canvas units), position=[0,0] (text centre), align=CENTER|LEFT|RIGHT,
      color="#000000" (outline), fill=None (fill colour, e.g. same as color for solid text),
      radius=0.02 (outline half-thickness; 0.0001 for fill-only look), resolution=12,
      shape_arabic_text=True, jitter=0, seed=0, target/layer/frame, line_spacing=1, letter_spacing=1,
      order="ltr"|"rtl" (stroke order for write-on: rtl reverses so Arabic draws right-to-left),
      opacity=1.0.
    Holes (inside of O, ه, ة ...) are cut using a shared fill_id per glyph group."""
    obj = _get_gp(state, target)
    d = _drawing(obj, layer, frame)
    mi = _material(obj, color, fill, None, show_stroke=radius > 0.0005)
    outlines = text_to_polylines(text, font, size, align, resolution, shape_arabic_text, line_spacing, letter_spacing)
    if order == "rtl" or (order == "auto" and has_arabic(text)):
        outlines.sort(key=lambda o: -max(p[0] for p in o[0]))
    else:
        outlines.sort(key=lambda o: min(p[0] for p in o[0]))
    px, py = position
    state["fill_counter"] = state.get("fill_counter", 0) + 1
    text_fid = state["fill_counter"]
    for i, (pts, cyc) in enumerate(outlines):
        pts = [(x + px, y + py) for x, y in pts]
        if jitter:
            pts = _jitter_points(_resample(pts, max(jitter * 2, 0.05)), jitter, seed + i)
        # all outlines share fill id 1 -> even-odd style holes where supported
        _add_stroke(d, pts, radius, None, opacity, mi, cyc, fill_id=text_fid if fill else None)
    _finish(obj, d)
    return {"object": obj.name, "strokes": len(outlines), "text_shaped": shape_arabic(text) if shape_arabic_text else text}


def _new_objects_since(before):
    return [o for o in bpy.data.objects if o.name not in before]


def draw_svg(state, filepath, name=None, scale=1.0, position=(0, 0), resolution=10, fit_width=None,
             import_scale=10.0, target_name=None):
    """Import an SVG file as a Grease Pencil object (Blender's native SVG importer).
    params: filepath (required), name=None (rename result), scale=1.0 (extra uniform scale),
      position=[0,0] (canvas centre of the drawing), resolution=10 (curve sampling),
      fit_width=None (scale so drawing is this many units wide), import_scale=10.0 (importer scale).
    The importer creates one object; it is centred on `position` in the XZ canvas plane."""
    filepath = os.path.abspath(filepath)
    before = set(o.name for o in bpy.data.objects)
    kw = dict(filepath=filepath, directory=os.path.dirname(filepath) + os.sep,
              files=[{"name": os.path.basename(filepath)}], resolution=int(resolution), scale=float(import_scale))
    op = bpy.ops.wm.grease_pencil_import_svg
    props = op.get_rna_type().properties.keys()
    kw = {k: v for k, v in kw.items() if k in props}
    r = op(**kw)
    new = [o for o in _new_objects_since(before) if o.type == "GREASEPENCIL"]
    if not new:
        raise RuntimeError("SVG import produced no grease pencil object (%s)" % r)
    obj = new[0]
    if name:
        obj.name = name
    # centre it
    dg = bpy.context.evaluated_depsgraph_get()
    xs, zs = [], []
    for L in obj.data.layers:
        for fr in L.frames:
            for st in fr.drawing.strokes:
                for p in st.points:
                    v = obj.matrix_world @ mathutils.Vector(p.position)
                    xs.append(v.x)
                    zs.append(v.z)
    if xs:
        w = max(xs) - min(xs)
        s = scale * (fit_width / w if fit_width and w > 0 else 1.0)
        cx, cz = (max(xs) + min(xs)) / 2, (max(zs) + min(zs)) / 2
        obj.scale = [v * s for v in obj.scale]
        obj.location = (obj.location.x + (position[0] - cx * s), obj.location.y, obj.location.z + (position[1] - cz * s))
    for L in obj.data.layers:
        try:
            L.use_lights = False
        except Exception:
            pass
    _objs(state)[obj.name] = obj
    state["gp_active"] = obj
    return {"object": obj.name, "bbox_width": (max(xs) - min(xs)) if xs else 0}


def _trace_opencv(image, threshold=128, mode="contours", min_area=20.0, epsilon=1.0, invert=False):
    """Run this file with *system* python + cv2 and return {'width','height','contours'}."""
    import tempfile
    out = os.path.join(tempfile.gettempdir(), "bp_trace_%d.json" % os.getpid())
    py = os.environ.get("BLENDER_PRO_PYTHON") or "python"
    cmd = [py, os.path.abspath(__file__), "trace", image, out, "--threshold", str(threshold), "--mode", mode,
           "--min-area", str(min_area), "--epsilon", str(epsilon)] + (["--invert"] if invert else [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("opencv trace failed (needs system python with opencv-python): %s %s" % (r.stdout, r.stderr))
    with open(out, encoding="utf-8") as f:
        return json.load(f)


def draw_image_trace(state, image, method="opencv", width=None, position=(0, 0), threshold=128, mode="contours",
                     min_area=20.0, epsilon=1.0, invert=False, color="#000000", fill=None, radius=0.02,
                     jitter=0.0, target=None, layer=None, frame=None, contours=None, contours_file=None,
                     potrace_target=None):
    """Trace a bitmap into Grease Pencil strokes.
    method:
      "opencv"  (default) - contours/edges computed by SYSTEM python + opencv-python
                (Blender's python has no cv2; this file is run as a subprocess:
                python draw.py trace img.png out.json). mode="contours" (threshold
                silhouettes) or "edges" (Canny line art).
      "contours" - use given `contours` ([[[x,y],...],...] pixel coords) or `contours_file` JSON
                {"width","height","contours"} produced elsewhere.
      "potrace" - Blender's built-in bpy.ops.grease_pencil.trace_image (needs an image
                empty; may need a UI context - falls back to opencv on failure).
    params: image (path), width=None (canvas units of traced image; default canvas width*0.8),
      position=[0,0], threshold=128, mode="contours"|"edges", min_area=20, epsilon=1.0
      (polygon simplification px), invert=False (trace light shapes on dark),
      color, fill, radius=0.02, jitter, target/layer/frame."""
    data = None
    if method == "potrace":
        try:
            return _trace_potrace(state, image, width, position, threshold, potrace_target)
        except Exception as e:  # noqa
            state.setdefault("warnings", []).append("potrace failed (%s); using opencv" % e)
            method = "opencv"
    if contours is not None:
        data = {"contours": contours}
    elif contours_file:
        with open(contours_file, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = _trace_opencv(os.path.abspath(image), threshold, mode, min_area, epsilon, invert)
    cs = data["contours"]
    if not cs:
        return {"strokes": 0}
    allx = [p[0] for c in cs for p in c]
    ally = [p[1] for c in cs for p in c]
    iw = data.get("width") or (max(allx) - min(allx))
    ih = data.get("height") or (max(ally) - min(ally))
    cw = state.get("canvas", {}).get("width", 16)
    W = width or cw * 0.8
    s = W / float(iw)
    obj = _get_gp(state, target)
    d = _drawing(obj, layer, frame)
    mi = _material(obj, color, fill)
    for i, c in enumerate(cs):
        pts = [(position[0] + (p[0] - iw / 2.0) * s, position[1] - (p[1] - ih / 2.0) * s) for p in c]
        if jitter:
            pts = _jitter_points(_resample(pts, jitter * 2), jitter, i)
        _add_stroke(d, pts, radius, None, 1.0, mi, mode != "edges", fill_id=(state.setdefault('fill_counter', 0) + 1) if fill else None)
    _finish(obj, d)
    return {"object": obj.name, "strokes": len(cs), "method": method}


def _trace_potrace(state, image, width, position, threshold, target_name):
    img = bpy.data.images.load(os.path.abspath(image))
    emp = bpy.data.objects.new("TraceImage", None)
    emp.empty_display_type = "IMAGE"
    emp.data = img
    emp.rotation_euler = (math.radians(90), 0, 0)
    bpy.context.scene.collection.objects.link(emp)
    vl = bpy.context.view_layer
    for o in vl.objects:
        o.select_set(False)
    emp.select_set(True)
    vl.objects.active = emp
    before = set(o.name for o in bpy.data.objects)
    with bpy.context.temp_override(active_object=emp, object=emp, selected_objects=[emp]):
        bpy.ops.grease_pencil.trace_image(threshold=threshold / 255.0)
    new = [o for o in _new_objects_since(before) if o.type == "GREASEPENCIL"]
    if not new:
        raise RuntimeError("trace_image produced nothing")
    obj = new[0]
    _objs(state)[obj.name] = obj
    state["gp_active"] = obj
    bpy.data.objects.remove(emp, do_unlink=True)
    return {"object": obj.name, "method": "potrace"}


def animate_draw_on(state, target=None, start=1, end=60, mode="SEQUENTIAL", transition="GROW", easing="LINEAR",
                    fade=False, fade_factor=0.1, layer_filter=None, reverse=False, hold=True):
    """Write-on / build-up reveal of a drawing with the Build modifier, driven
    by a keyframed percentage (deterministic, independent of stroke timing).
    params: target=None (GP object), start=1, end=60 (frames: 0% -> 100%),
      mode="SEQUENTIAL" (one stroke after another) | "CONCURRENT" (all at once) | "ADDITIVE",
      transition="GROW" | "SHRINK" | "FADE", easing="LINEAR" | "BEZIER" | "EASE_IN_OUT",
      fade=False (soft leading edge), fade_factor=0.1, layer_filter=None (layer name),
      reverse=False (erase instead of draw), hold=True (stay complete after `end`)."""
    obj = _get_gp(state, target)
    m = obj.modifiers.new("DrawOn", "GREASE_PENCIL_BUILD")
    m.mode = mode
    m.transition = transition
    m.use_percentage = True
    try:
        m.time_mode = "PERCENTAGE"
    except Exception:
        pass
    if fade:
        m.use_fading = True
        m.fade_factor = fade_factor
    if layer_filter:
        m.layer_filter = layer_filter
    a, b = (1.0, 0.0) if reverse else (0.0, 1.0)
    m.percentage_factor = a
    obj.keyframe_insert('modifiers["%s"].percentage_factor' % m.name, frame=start)
    m.percentage_factor = b
    obj.keyframe_insert('modifiers["%s"].percentage_factor' % m.name, frame=end)
    _set_interp(obj, easing)
    scene = bpy.context.scene
    if scene.frame_end < end:
        scene.frame_end = int(end)
    return {"object": obj.name, "modifier": m.name, "frames": [start, end]}


def _fcurves(idblock):
    """All fcurves of an ID's action (handles 4.4+/5.x layered actions)."""
    ad = idblock.animation_data
    if not ad or not ad.action:
        return []
    act = ad.action
    if hasattr(act, "fcurves") and len(getattr(act, "fcurves", [])):
        return list(act.fcurves)
    out = []
    try:
        for layer in act.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    out.extend(cb.fcurves)
    except Exception:
        pass
    return out


def _set_interp(idblock, easing="LINEAR"):
    for fc in _fcurves(idblock):
        for kp in fc.keyframe_points:
            if easing == "LINEAR":
                kp.interpolation = "LINEAR"
            elif easing == "CONSTANT":
                kp.interpolation = "CONSTANT"
            else:
                kp.interpolation = "BEZIER"
                kp.easing = "AUTO"


def gp_materials(state, name, color="#000000", fill=None, target=None, mode="LINE", stroke=True,
                 gradient=None, gradient_type="LINEAR", mix_factor=0.5, texture=None, dots_alignment="PATH",
                 holdout=False, assign_all=False):
    """Create (or edit) a named GP material and add it to the object.
    params: name (required), color="#000000" (stroke), fill=None (fill colour),
      mode="LINE"|"DOTS"|"BOX" (stroke drawn as line or dot/square stamps), stroke=True,
      gradient=None (second fill colour -> gradient fill from `fill` to `gradient`),
      gradient_type="LINEAR"|"RADIAL", mix_factor=0.5, texture=None (image path -> texture fill),
      holdout=False (stroke+fill cut out what is below), assign_all=False (set every stroke of
      the active object to this material). Use `material=<name>` in draw_* ops afterwards."""
    obj = _get_gp(state, target)
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
        bpy.data.materials.create_gpencil_data(mat)
    g = mat.grease_pencil
    g.color = parse_color(color)
    g.show_stroke = stroke
    g.mode = mode
    try:
        g.alignment_mode = dots_alignment
    except Exception:
        pass
    if fill is not None or gradient or texture:
        g.show_fill = True
        g.fill_color = parse_color(fill or "#FFFFFF")
        if gradient:
            g.fill_style = "GRADIENT"
            g.gradient_type = gradient_type
            g.mix_color = parse_color(gradient)
            g.mix_factor = mix_factor
        if texture:
            g.fill_style = "TEXTURE"
            g.fill_image = bpy.data.images.load(os.path.abspath(texture), check_existing=True)
    else:
        g.show_fill = False
    g.use_stroke_holdout = holdout
    g.use_fill_holdout = holdout
    idx = None
    for i, m in enumerate(obj.data.materials):
        if m == mat:
            idx = i
    if idx is None:
        obj.data.materials.append(mat)
        idx = len(obj.data.materials) - 1
    if assign_all:
        for L in obj.data.layers:
            for fr in L.frames:
                for s in fr.drawing.strokes:
                    s.material_index = idx
    return {"material": mat.name, "index": idx}


_FX = {"glow": "FX_GLOW", "shadow": "FX_SHADOW", "blur": "FX_BLUR", "wave": "FX_WAVE", "rim": "FX_RIM",
       "pixel": "FX_PIXEL", "colorize": "FX_COLORIZE", "swirl": "FX_SWIRL", "flip": "FX_FLIP"}
_MODS = {"noise": "GREASE_PENCIL_NOISE", "smooth": "GREASE_PENCIL_SMOOTH", "thickness": "GREASE_PENCIL_THICKNESS",
         "tint": "GREASE_PENCIL_TINT", "color": "GREASE_PENCIL_COLOR", "opacity": "GREASE_PENCIL_OPACITY",
         "offset": "GREASE_PENCIL_OFFSET", "dash": "GREASE_PENCIL_DASH", "envelope": "GREASE_PENCIL_ENVELOPE",
         "array": "GREASE_PENCIL_ARRAY", "subdiv": "GREASE_PENCIL_SUBDIV", "simplify": "GREASE_PENCIL_SIMPLIFY",
         "outline": "GREASE_PENCIL_OUTLINE", "length": "GREASE_PENCIL_LENGTH", "mirror": "GREASE_PENCIL_MIRROR",
         "multiply": "GREASE_PENCIL_MULTIPLY", "time": "GREASE_PENCIL_TIME", "build": "GREASE_PENCIL_BUILD",
         "texture": "GREASE_PENCIL_TEXTURE"}
_FX_DEFAULTS = {
    "glow": {"mode": "COLOR", "threshold": 0.0, "size": [40, 40], "samples": 16, "glow_color": "#FFFFFF", "opacity": 1.0},
    "shadow": {"offset": [12, -12], "shadow_color": [0, 0, 0, 0.6], "blur": [6, 6], "samples": 8},
    "blur": {"size": [8, 8], "samples": 8},
    "wave": {"amplitude": 10.0, "period": 40.0},
    "noise": {"factor": 0.3, "factor_thickness": 0.3, "noise_scale": 0.5, "use_random": True, "step": 4},
}


def _set_props(obj, props, warn):
    for k, v in props.items():
        if not hasattr(obj, k):
            warn.append("%s has no property %r" % (getattr(obj, "name", obj), k))
            continue
        cur = getattr(obj, k)
        try:
            if isinstance(v, str) and v.startswith("#"):
                c = parse_color(v)
                v = c[:len(cur)] if hasattr(cur, "__len__") else c
            elif isinstance(v, (list, tuple)) and hasattr(cur, "__len__") and len(v) > len(cur):
                v = v[:len(cur)]
            elif isinstance(v, (list, tuple)) and hasattr(cur, "__len__") and len(v) < len(cur) and len(cur) == 4 and len(v) == 3:
                v = list(v) + [1.0]
            setattr(obj, k, v)
        except Exception as e:
            warn.append("%s.%s=%r failed: %s" % (getattr(obj, "name", obj), k, v, e))


def gp_effects(state, effects, target=None):
    """Add visual effects (shader FX) and stroke modifiers to a GP object.
    params: effects = list of {"type": <name>, <property>: value, ...}, target=None.
    Shader FX (screen-space, pixels): glow, shadow, blur, wave, rim, pixel, colorize, swirl, flip.
    Modifiers (geometry): noise (wobble/boil: use_random+step), smooth, thickness, tint,
      color, opacity, offset, dash, envelope, array, subdiv, simplify, outline, length,
      mirror, multiply, time, build, texture.
    Any RNA property of the effect can be passed (e.g. glow: glow_color, size=[x,y],
      threshold, mode=COLOR|LUMINANCE, blend_mode, use_glow_under; shadow: offset=[x,y],
      shadow_color, blur=[x,y], use_wave; blur: size=[x,y]; wave: amplitude, period, phase;
      noise: factor, factor_strength, factor_thickness, noise_scale, seed, step, use_random).
    Sensible defaults are applied for glow/shadow/blur/wave/noise."""
    obj = _get_gp(state, target)
    warn = []
    added = []
    for e in effects:
        e = dict(e)
        t = e.pop("type").lower()
        props = dict(_FX_DEFAULTS.get(t, {}))
        props.update(e)
        nm = props.pop("name", t)
        if t in _FX:
            fx = obj.shader_effects.new(nm, _FX[t])
            _set_props(fx, props, warn)
            added.append(fx.name)
        elif t in _MODS:
            md = obj.modifiers.new(nm, _MODS[t])
            _set_props(md, props, warn)
            added.append(md.name)
        else:
            raise ValueError("unknown effect %r (fx: %s, modifiers: %s)" % (t, list(_FX), list(_MODS)))
    return {"object": obj.name, "added": added, "warnings": warn}


def line_art(state, source="SCENE", source_name=None, name="LineArt", color="#111111", radius=0.008,
             thickness=None, crease_angle=140.0, use_contour=True, use_crease=True, use_intersection=True,
             use_material=True, use_edge_mark=True, use_loose=True, opacity=1.0, overscan=0.1,
             fill_strokes=False, camera=None, chaining_threshold=0.1, smooth=0.0):
    """Line Art (toon / ink outlines) over 3D geometry, rendered as Grease Pencil.
    params: source="SCENE"|"COLLECTION"|"OBJECT", source_name (collection/object name),
      name="LineArt", color="#111111", radius=0.008 (line half thickness in world units),
      thickness=None (alias in px-ish: radius=thickness/1000), crease_angle=140 (degrees),
      use_contour/use_crease/use_intersection/use_material/use_edge_mark/use_loose=True,
      opacity=1.0, overscan=0.1, fill_strokes=False, camera=None (custom source camera),
      chaining_threshold=0.1, smooth=0.0 (add Smooth modifier factor).
    Needs a scene camera. Works with EEVEE renders: the 3D shading stays, ink goes on top."""
    scene = bpy.context.scene
    gp = bpy.data.grease_pencils.new(name)
    obj = bpy.data.objects.new(name, gp)
    scene.collection.objects.link(obj)
    L = gp.layers.new("Lines")
    L.use_lights = False
    L.frames.new(scene.frame_start)
    mi = _material(obj, color)
    mat = obj.data.materials[mi]
    m = obj.modifiers.new("LineArt", "LINEART")
    m.source_type = source
    if source == "COLLECTION":
        m.source_collection = bpy.data.collections[source_name]
    elif source == "OBJECT":
        m.source_object = bpy.data.objects[source_name]
    m.target_layer = L.name
    m.target_material = mat
    m.radius = (thickness / 1000.0) if thickness else radius
    m.opacity = opacity
    m.crease_threshold = math.radians(crease_angle)
    m.use_contour, m.use_crease, m.use_intersection = use_contour, use_crease, use_intersection
    m.use_material, m.use_edge_mark, m.use_loose = use_material, use_edge_mark, use_loose
    m.overscan = overscan
    m.fill_strokes = fill_strokes
    m.chaining_image_threshold = chaining_threshold
    if camera:
        m.use_custom_camera = True
        m.source_camera = bpy.data.objects[camera]
    if smooth:
        s = obj.modifiers.new("Smooth", "GREASE_PENCIL_SMOOTH")
        s.factor = smooth
    _objs(state)[obj.name] = obj
    return {"object": obj.name}


def draw_frames(state, frames, target=None, layer=None, onion=True, hold=1, loop=False, clear_layer=False):
    """Frame-by-frame (traditional) animation: a separate drawing per keyframe.
    params: frames = list of {"frame": N, "items": [ <draw_stroke / draw_shape / draw_text_outline params> ]}
      or a dict {"N": [items]}. Each item may contain "op": "draw_shape"|"draw_stroke"|"draw_text_outline"
      (default: draw_shape if "shape" in item else draw_stroke).
      hold=1: if frames are given without explicit "frame", they are placed every `hold` frames
      starting at scene start ("on twos" = hold 2). onion=True enables onion skinning on the layer,
      loop=False (cycle the sequence with a Time modifier), clear_layer=False.
    Example: {"op":"draw_frames","frames":[{"items":[{"shape":"circle","r":1}]},
              {"items":[{"shape":"circle","r":1.5}]}],"hold":2}"""
    obj = _get_gp(state, target)
    L = _layer(obj, layer)
    if clear_layer:
        for fr in list(L.frames):
            L.frames.remove(fr.frame_number)
    if isinstance(frames, dict):
        frames = [{"frame": int(k), "items": v} for k, v in frames.items()]
    scene = bpy.context.scene
    f0 = scene.frame_start
    made = []
    for i, fr in enumerate(frames):
        num = int(fr.get("frame", f0 + i * hold))
        _drawing(obj, L.name, num)
        for it in fr.get("items", []):
            it = dict(it)
            opn = it.pop("op", None) or ("draw_shape" if "shape" in it else ("draw_text_outline" if "text" in it else "draw_stroke"))
            it.update({"target": obj.name, "layer": L.name, "frame": num})
            OPS[opn](state, **it)
        made.append(num)
    L.use_onion_skinning = onion
    last = max(made) + hold if made else f0
    if scene.frame_end < last - 1:
        scene.frame_end = last - 1
    if loop:
        m = obj.modifiers.new("Loop", "GREASE_PENCIL_TIME")
        try:
            m.mode = "NORMAL"
            m.use_custom_frame_range = True
            m.frame_start = min(made)
            m.frame_end = last - 1
        except Exception:
            pass
    return {"object": obj.name, "layer": L.name, "keyframes": made}


def gp_onion(state, target=None, mode="RELATIVE", before=1, after=1, factor=0.5, fade=True,
             color_before="#FF4040", color_after="#40FF40", custom_colors=True):
    """Onion-skin settings (viewport aid for frame-by-frame work; not rendered).
    params: target, mode="RELATIVE"|"ABSOLUTE"|"SELECTED", before=1, after=1, factor=0.5,
      fade=True, color_before, color_after, custom_colors=True."""
    obj = _get_gp(state, target)
    g = obj.data
    g.onion_mode = mode
    g.ghost_before_range = before
    g.ghost_after_range = after
    g.onion_factor = factor
    g.use_onion_fade = fade
    g.use_ghost_custom_colors = custom_colors
    g.before_color = parse_color(color_before)[:3]
    g.after_color = parse_color(color_after)[:3]
    return {"object": obj.name}


def doodle_style(state, target=None, wobble=0.04, boil=True, boil_step=3, thickness_var=0.4, seed=0,
                 smooth=0.0):
    """Hand-made / doodle look for an existing drawing using modifiers:
    Noise (position+thickness wobble). boil=True re-randomises every `boil_step` frames
    (the classic "boiling line" of hand-drawn animation).
    params: target, wobble=0.04 (units), boil=True, boil_step=3, thickness_var=0.4,
      seed=0, smooth=0.0 (Smooth modifier factor before noise).
    For static jitter while drawing use draw_stroke(jitter=..., passes=2..3, taper=0.2)."""
    obj = _get_gp(state, target)
    if smooth:
        s = obj.modifiers.new("DoodleSmooth", "GREASE_PENCIL_SMOOTH")
        s.factor = smooth
    m = obj.modifiers.new("Doodle", "GREASE_PENCIL_NOISE")
    m.factor = wobble * 10.0
    m.factor_thickness = thickness_var
    m.noise_scale = 0.3
    m.seed = seed
    m.use_random = bool(boil)
    m.step = int(boil_step)
    try:
        m.random_mode = "STEP"
    except Exception:
        pass
    return {"object": obj.name, "modifier": m.name}


def gp_transform(state, target=None, location=None, rotation=None, scale=None, keyframes=None):
    """Move/rotate/scale a GP object (canvas units; rotation degrees around the view axis).
    params: target, location=[x,y] (canvas) or [x,y,z] (world), rotation=deg, scale=s or [sx,sy],
      keyframes=[{"frame":1,"location":[..],"rotation":0,"scale":1}, ...] for animation."""
    obj = _get_gp(state, target)

    def apply(loc, rot, sc):
        if loc is not None:
            obj.location = (loc[0], 0, loc[1]) if len(loc) == 2 else tuple(loc)
        if rot is not None:
            obj.rotation_euler = (0, math.radians(-rot), 0)
        if sc is not None:
            obj.scale = (sc, 1, sc) if isinstance(sc, (int, float)) else (sc[0], 1, sc[1])

    apply(location, rotation, scale)
    for k in keyframes or []:
        apply(k.get("location"), k.get("rotation"), k.get("scale"))
        f = int(k["frame"])
        if "location" in k:
            obj.keyframe_insert("location", frame=f)
        if "rotation" in k:
            obj.keyframe_insert("rotation_euler", frame=f)
        if "scale" in k:
            obj.keyframe_insert("scale", frame=f)
    return {"object": obj.name}


def gp_render(state, filepath, animation=False, frame=None, fmt=None, crf="HIGH"):
    """Convenience renderer for drawing-only recipes (the CLI "render" block does the same).
    params: filepath (required; .png for still / animation frames, .mp4 for H.264 video),
      animation=False, frame=None (still frame), fmt=None (auto from extension), crf="HIGH"."""
    scene = bpy.context.scene
    ext = os.path.splitext(filepath)[1].lower()
    ims = scene.render.image_settings
    if ext in (".mp4", ".mov", ".mkv"):
        ims.media_type = "VIDEO"
        ims.file_format = "FFMPEG"
        ff = scene.render.ffmpeg
        ff.format = "MPEG4" if ext == ".mp4" else ("QUICKTIME" if ext == ".mov" else "MKV")
        ff.codec = "H264"
        ff.constant_rate_factor = crf
        ff.ffmpeg_preset = "GOOD"
        ff.audio_codec = "NONE"
        animation = True
    else:
        ims.media_type = "IMAGE"
        ims.file_format = fmt or ("JPEG" if ext in (".jpg", ".jpeg") else "PNG")
        ims.color_mode = "RGBA" if scene.render.film_transparent and ims.file_format == "PNG" else "RGB"
    scene.render.filepath = filepath
    if animation:
        bpy.ops.render.render(animation=True)
    else:
        if frame is not None:
            scene.frame_set(int(frame))
        bpy.ops.render.render(write_still=True)
    return {"filepath": filepath}


OPS = {
    "gp_canvas": gp_canvas,
    "gp_layer": gp_layer,
    "draw_stroke": draw_stroke,
    "draw_shape": draw_shape,
    "draw_text_outline": draw_text_outline,
    "draw_svg": draw_svg,
    "draw_image_trace": draw_image_trace,
    "animate_draw_on": animate_draw_on,
    "gp_materials": gp_materials,
    "gp_effects": gp_effects,
    "line_art": line_art,
    "draw_frames": draw_frames,
    "gp_onion": gp_onion,
    "doodle_style": doodle_style,
    "gp_transform": gp_transform,
    "gp_render": gp_render,
}


# ---------------------------------------------------------------------------
# system-python CLI: bitmap -> contours JSON (opencv)
# ---------------------------------------------------------------------------
def _cli_trace(argv):
    import argparse
    import cv2  # type: ignore
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("out")
    ap.add_argument("--threshold", type=int, default=128)
    ap.add_argument("--mode", default="contours", choices=["contours", "edges"])
    ap.add_argument("--min-area", type=float, default=20.0)
    ap.add_argument("--epsilon", type=float, default=1.0)
    ap.add_argument("--invert", action="store_true")
    a = ap.parse_args(argv)
    import numpy as np  # noqa
    data = np.fromfile(a.image, dtype=np.uint8)  # unicode-safe path read
    img = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise SystemExit("cannot read image " + a.image)
    h, w = img.shape[:2]
    if a.mode == "edges":
        e = cv2.Canny(cv2.GaussianBlur(img, (3, 3), 0), a.threshold * 0.5, a.threshold)
        cs, _ = cv2.findContours(e, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
        cs = [c for c in cs if cv2.arcLength(c, False) > a.min_area]
    else:
        flag = cv2.THRESH_BINARY if a.invert else cv2.THRESH_BINARY_INV
        _, b = cv2.threshold(img, a.threshold, 255, flag)
        cs, _ = cv2.findContours(b, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
        cs = [c for c in cs if abs(cv2.contourArea(c)) > a.min_area]
    out = []
    for c in cs:
        c2 = cv2.approxPolyDP(c, a.epsilon, a.mode != "edges") if a.epsilon > 0 else c
        out.append([[int(p[0][0]), int(p[0][1])] for p in c2])
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"width": w, "height": h, "contours": out}, f)
    print("contours", len(out))


if __name__ == "__main__" and bpy is None:
    if len(sys.argv) > 1 and sys.argv[1] == "trace":
        _cli_trace(sys.argv[2:])
    else:
        print(__doc__)
