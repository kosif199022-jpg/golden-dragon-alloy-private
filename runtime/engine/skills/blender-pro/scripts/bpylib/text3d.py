"""3D text with proper Arabic (RTL + letter shaping), font lookup, extrude/bevel, per-part
splitting and reveal animations.

Blender's text engine does not shape Arabic. shape() converts logical Arabic text into visual
order with presentation forms using arabic_reshaper + python-bidi: in-process when installed in
Blender's python, otherwise through the system python (env BLPRO_SYSPY, set by bl.py, or
`python` on PATH). Fonts must contain Arabic presentation forms (Arial, Tahoma, Segoe UI,
Sakkal Majalla, Traditional Arabic, Amiri, Cairo...)."""
import json
import os
import re
import shutil
import subprocess
import tempfile

import bmesh
import bpy
import mathutils

from . import util
from .util import log, warn

ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")
_SHAPE_CACHE = {}
DEFAULT_ARABIC_FONT = "arialbd"
DEFAULT_LATIN_FONT = "arialbd"

_SHAPER_CODE = r"""
import json, sys
import arabic_reshaper
try:
    from bidi import get_display
except ImportError:
    from bidi.algorithm import get_display
texts = json.loads(sys.stdin.buffer.read().decode('utf-8'))
out = ["\n".join(get_display(arabic_reshaper.reshape(l)) for l in t.split("\n")) for t in texts]
sys.stdout.buffer.write(json.dumps(out).encode('utf-8'))
"""


def has_arabic(text):
    return bool(ARABIC_RE.search(text or ""))


def _shape_inprocess(texts):
    import arabic_reshaper  # noqa: F401
    try:
        from bidi import get_display
    except ImportError:
        from bidi.algorithm import get_display
    return ["\n".join(get_display(arabic_reshaper.reshape(l)) for l in t.split("\n")) for t in texts]


def _system_python():
    for c in (os.environ.get("BLPRO_SYSPY"), shutil.which("python"), shutil.which("python3"), shutil.which("py")):
        if c and os.path.exists(c) and "blender" not in c.lower():
            return c
    return None


def shape_many(texts):
    """Shape a list of strings (only Arabic ones are changed). Cached."""
    todo = [t for t in texts if has_arabic(t) and t not in _SHAPE_CACHE]
    if todo:
        shaped = None
        try:
            shaped = _shape_inprocess(todo)
        except ImportError:
            py = _system_python()
            if py:
                try:
                    r = subprocess.run([py, "-c", _SHAPER_CODE], input=json.dumps(todo).encode("utf-8"),
                                       capture_output=True, timeout=60, cwd=tempfile.gettempdir())
                    if r.returncode == 0:
                        shaped = json.loads(r.stdout.decode("utf-8"))
                    else:
                        warn(f"system python shaping failed: {r.stderr.decode('utf-8', 'replace')[-400:]}")
                except Exception as e:
                    warn(f"system python shaping failed: {e}")
        if shaped is None:
            warn("Arabic shaping unavailable (pip install arabic-reshaper python-bidi in system python); "
                 "falling back to reversed text - letters will NOT connect")
            shaped = ["\n".join(l[::-1] for l in t.split("\n")) for t in todo]
        _SHAPE_CACHE.update(zip(todo, shaped))
    return [_SHAPE_CACHE.get(t, t) for t in texts]


def shape(text):
    return shape_many([text])[0]


# --------------------------------------------------------------------------- fonts
FONT_DIRS = [os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"),
             os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts"),
             os.path.join(util.ASSETS_DIR, "fonts"),
             "/usr/share/fonts", "/Library/Fonts", os.path.expanduser("~/Library/Fonts")]


def find_font(spec):
    """Resolve a font: absolute path, file name ('arialbd.ttf'), or stem ('arialbd', 'Amiri-Bold')."""
    if not spec:
        return None
    p = os.path.expandvars(os.path.expanduser(spec))
    if os.path.isfile(p):
        return os.path.abspath(p)
    stem = os.path.splitext(os.path.basename(p))[0].lower()
    best = None
    for d in FONT_DIRS:
        if not d or not os.path.isdir(d):
            continue
        for root, _, files in os.walk(d):
            for f in files:
                if not f.lower().endswith((".ttf", ".otf", ".ttc", ".pfb")):
                    continue
                s = os.path.splitext(f)[0].lower()
                if s == stem:
                    return os.path.join(root, f)
                if best is None and s.replace(" ", "").replace("-", "") == stem.replace(" ", "").replace("-", ""):
                    best = os.path.join(root, f)
    return best


def load_font(spec, arabic=False):
    path = find_font(spec) if spec else None
    if spec and not path:
        warn(f"font '{spec}' not found in {FONT_DIRS[:3]}; using default")
    if not path:
        path = find_font(DEFAULT_ARABIC_FONT if arabic else DEFAULT_LATIN_FONT)
    if not path:
        return None  # Blender built-in font (no Arabic glyphs)
    return bpy.data.fonts.load(path, check_existing=True)


# --------------------------------------------------------------------------- text
def text3d(state, text, name="Text", font=None, size=1.0, extrude=0.08, bevel_depth=0.01, bevel_resolution=3,
           align_x="CENTER", align_y="CENTER", location=(0, 0, 0), rotation=(90, 0, 0), material=None,
           letter_spacing=1.0, word_spacing=1.0, line_spacing=1.0, offset=0.0, split=False, to_mesh=False,
           shape_arabic=True, resolution=12, font_bold=None, **_):
    """Create 3D text. Arabic is shaped + reordered automatically and gets an Arabic-capable font.
    rotation default [90,0,0] stands the text upright facing -Y (default camera side).
    split=True converts to one mesh object per glyph cluster (Arabic: per connected word piece),
    parented to an empty named `name` - required for per-letter reveals.
    Returns the name of the text object (or the group empty when split)."""
    raw = str(text)
    arabic = has_arabic(raw)
    body = shape(raw) if (arabic and shape_arabic) else raw
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    f = load_font(font, arabic)
    if f:
        cu.font = f
    if font_bold:
        cu.font_bold = load_font(font_bold, arabic) or cu.font
    cu.size = float(size)
    cu.extrude = float(extrude)
    cu.bevel_depth = float(bevel_depth)
    cu.bevel_resolution = int(bevel_resolution)
    cu.offset = float(offset)
    cu.align_x = align_x.upper()
    cu.align_y = align_y.upper()
    cu.space_character = float(letter_spacing)
    cu.space_word = float(word_spacing)
    cu.space_line = float(line_spacing)
    cu.resolution_u = int(resolution)
    obj = util.new_object(name, cu)
    obj["blpro_text"] = raw
    obj["blpro_rtl"] = arabic
    if material:
        from . import materials
        materials.assign(state, obj, material)
    if split:
        return _split_parts(state, obj, name, location, rotation, arabic)
    util.set_transform(obj, location, rotation)
    util.register(state, obj, name)
    if to_mesh:
        from . import objects
        return objects.convert_to_mesh(state, name)
    return obj.name


def _split_parts(state, obj, name, location, rotation, rtl):
    deps = bpy.context.evaluated_depsgraph_get()
    full = bpy.data.meshes.new_from_object(obj.evaluated_get(deps), depsgraph=deps)
    mats = list(full.materials)
    bpy.data.objects.remove(obj, do_unlink=True)
    bm = bmesh.new()
    bm.from_mesh(full)
    bm.faces.ensure_lookup_table()
    # connected components by faces
    comp_of = {}
    comps = []
    for f in bm.faces:
        if f.index in comp_of:
            continue
        stack, cid = [f], len(comps)
        comp = []
        comp_of[f.index] = cid
        while stack:
            cur = stack.pop()
            comp.append(cur.index)
            for e in cur.edges:
                for nf in e.link_faces:
                    if nf.index not in comp_of:
                        comp_of[nf.index] = cid
                        stack.append(nf)
        comps.append(comp)
    # merge components that overlap in X (dots/diacritics with their letter, holes, i/j)
    ranges = []
    for comp in comps:
        xs = [v.co.x for fi in comp for v in bm.faces[fi].verts]
        ys = [v.co.y for fi in comp for v in bm.faces[fi].verts]
        ranges.append([min(xs), max(xs), min(ys), max(ys)])
    parent = list(range(len(comps)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i in range(len(comps)):
        for j in range(i + 1, len(comps)):
            a, b = ranges[i], ranges[j]
            ov = min(a[1], b[1]) - max(a[0], b[0])
            yov = min(a[3], b[3]) - max(a[2], b[2]) > -0.6 * max(a[3] - a[2], b[3] - b[2])  # same line
            if ov > 0.5 * min(a[1] - a[0], b[1] - b[0]) and yov:
                parent[find(i)] = find(j)
    groups = {}
    for i, comp in enumerate(comps):
        groups.setdefault(find(i), []).extend(comp)
    root = util.new_object(name, None)
    root.empty_display_size = 0.5
    root["blpro_text_group"] = True
    root["blpro_rtl"] = rtl
    parts = []
    ordered = sorted(groups.values(), key=lambda g: min(v.co.x for fi in g for v in bm.faces[fi].verts),
                     reverse=rtl)
    for k, faces in enumerate(ordered):
        b2 = bm.copy()
        b2.faces.ensure_lookup_table()
        keep = set(faces)
        bmesh.ops.delete(b2, geom=[f for f in b2.faces if f.index not in keep], context="FACES")
        bmesh.ops.delete(b2, geom=[v for v in b2.verts if not v.link_faces], context="VERTS")
        me = bpy.data.meshes.new(f"{name}_{k:02d}")
        b2.to_mesh(me)
        b2.free()
        for m in mats:
            me.materials.append(m)
        cos = [v.co for v in me.vertices]
        ctr = mathutils.Vector([(min(c[i] for c in cos) + max(c[i] for c in cos)) / 2 for i in range(3)])
        me.transform(mathutils.Matrix.Translation(-ctr))
        for p in me.polygons:
            p.use_smooth = True
        o = util.new_object(f"{name}_{k:02d}", me)
        o.parent = root
        o.location = ctr
        o["blpro_rest"] = list(ctr)
        util.register(state, o, o.name)
        parts.append(o.name)
    bm.free()
    bpy.data.meshes.remove(full)
    util.set_transform(root, location, rotation)
    root["blpro_parts"] = parts
    util.register(state, root, name)
    log(f"text '{name}' split into {len(parts)} parts")
    return root.name


def text_parts(state, target):
    obj = util.get_obj(state, target)
    if obj.get("blpro_parts"):
        return [util.get_obj(state, n) for n in obj["blpro_parts"]]
    return [obj]


REVEAL_STYLES = ("rise", "drop", "scale", "fade", "slide", "flip", "extrude", "bevel", "typewriter", "blur_rise")


def text_reveal(state, target, style="rise", frame_start=None, duration=24, stagger=3, easing=None,
                distance=None, order=None, fade=True, **_):
    """Animate text in. style: rise | drop | scale | fade | slide | flip | extrude | bevel | typewriter.
    For per-letter stagger create the text with split=true; Arabic orders right-to-left automatically.
    extrude/bevel animate the font geometry (non-split text only)."""
    from . import animate
    style = style.lower()
    if style not in REVEAL_STYLES:
        raise ValueError(f"style must be one of {REVEAL_STYLES}")
    obj = util.get_obj(state, target)
    fs = int(frame_start if frame_start is not None else bpy.context.scene.frame_start)
    fe = fs + int(duration)
    if style in ("extrude", "bevel"):
        if obj.type != "FONT":
            raise ValueError("extrude/bevel reveal needs a non-split FONT object")
        prop = "extrude" if style == "extrude" else "bevel_depth"
        final = getattr(obj.data, prop) or 0.1
        util.set_key(obj.data, prop, 0.0, fs, easing=easing or "expo_out")
        util.set_key(obj.data, prop, final, fe, easing=easing or "expo_out")
        if fade:
            animate.fade(state, obj.name, 0.0, 1.0, fs, fs + max(1, duration // 2))
        return {"target": obj.name}
    parts = text_parts(state, target)
    rtl = bool(obj.get("blpro_rtl"))
    names = [p.name for p in parts]  # already ordered reading-first for split text
    if order == "reverse":
        names.reverse()
    mn, mx = util.world_bbox(parts)
    h = float(distance if distance is not None else max((mx - mn).z, (mx - mn).y, 0.3) * 0.8)
    common = dict(targets=names, frame_start=fs, frame_end=fe, stagger=stagger, hold=True)
    if style == "typewriter":
        for i, n in enumerate(names):
            animate.visibility(state, n, keys=[{"frame": bpy.context.scene.frame_start, "visible": False},
                                                {"frame": fs + i * max(1, stagger), "visible": True}])
        return {"parts": len(names)}
    if style in ("rise", "drop", "blur_rise"):
        dy = -h if style != "drop" else h
        animate.animate(state, property="location", from_value=[0, dy, 0], to_value=[0, 0, 0], relative=True,
                        easing=easing or "back_out", **common)
    elif style == "slide":
        dx = h * (1.5 if rtl else -1.5)
        animate.animate(state, property="location", from_value=[dx, 0, 0], to_value=[0, 0, 0], relative=True,
                        easing=easing or "expo_out", **common)
    elif style == "scale":
        animate.animate(state, property="scale", from_value=0.001, to_value=1.0, easing=easing or "back_out", **common)
    elif style == "flip":
        animate.animate(state, property="rotation", from_value=[-90, 0, 0], to_value=[0, 0, 0],
                        easing=easing or "back_out", **common)
    if fade or style == "fade":
        for i, n in enumerate(names):
            s = fs + i * stagger
            animate.fade(state, n, 0.0, 1.0, s, s + max(2, int(duration * (1.0 if style == "fade" else 0.6))))
            o = util.get_obj(state, n)
            c = list(o.color)
            c[3] = 0.0
            o.color = c
            o.keyframe_insert("color", index=3, frame=bpy.context.scene.frame_start)
    return {"parts": len(names), "frames": [fs, fe + stagger * (len(names) - 1)]}


def text_shape_op(state, text, **_):
    """Return the shaped (visual-order) version of a string (debug helper)."""
    return shape(text)


OPS = {
    "text3d": text3d,
    "text_reveal": text_reveal,
    "shape_text": text_shape_op,
}
