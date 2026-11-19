"""Runs INSIDE Krita via kritarunner (installed as %APPDATA%/kritarunner/pykrita/claude_krita_job.py).

Usage (done by krita_draw.py, never by hand):
    kritarunner -s claude_krita_job <job_dir>

Reads <job_dir>/job.json (all paths already ASCII and absolute), builds a Krita document
layer by layer, exports PNG/KRA, and writes <job_dir>/result.json after every step so a
native crash still tells you which step died.

Facts this file relies on (measured on Krita 5.3.4, see references/re_findings.md):
- Node.paint* (brush engine) and Window.addView crash without a GUI -> never called here.
- Pixel order for RGBA/U8 is B,G,R,A == QImage.Format_ARGB32 bytes on little-endian.
- kritarunner turns non-Latin-1 paths into mojibake -> host passes only ASCII paths.
"""
import json
import os
import sys
import time
import traceback

STATE = {"steps": [], "ok": False, "started": time.time()}
JOB_DIR = None


def _dump():
    if not JOB_DIR:
        return
    tmp = os.path.join(JOB_DIR, "result.json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(STATE, fh, ensure_ascii=False, indent=1, default=str)
    os.replace(tmp, os.path.join(JOB_DIR, "result.json"))


def step(name, fn, *a, **kw):
    rec = {"step": name, "status": "running"}
    STATE["steps"].append(rec)
    _dump()
    try:
        val = fn(*a, **kw)
        rec["status"] = "ok"
        if val is not None:
            rec["value"] = val
        return val
    except Exception as e:  # noqa: BLE001
        rec["status"] = "error"
        rec["error"] = repr(e)
        rec["trace"] = traceback.format_exc()[-1500:]
        raise
    finally:
        _dump()


# ----------------------------------------------------------------- helpers
def pump(ms):
    """kritarunner runs our script without a Qt event loop. Vector (shape) layers render
    through queued Qt events, so without this they export blank and saveAs(.kra) returns
    False because the image is still 'busy' (measured: alpha 0 before, 255 after ~1 s)."""
    from PyQt5.QtWidgets import QApplication
    end = time.time() + ms / 1000.0
    while time.time() < end:
        QApplication.processEvents()
        time.sleep(0.01)


def settle(doc, ms):
    pump(ms)
    doc.refreshProjection()
    doc.waitForDone()
    pump(120)


def hex_to_rgba(c, alpha=1.0):
    c = (c or "#000000").lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    a = int(c[6:8], 16) if len(c) == 8 else int(round(255 * alpha))
    return r, g, b, a


def solid_bytes(w, h, color):
    r, g, b, a = hex_to_rgba(color)
    return bytes([b, g, r, a]) * (w * h)


def qimage_bytes(path, want_w=None, want_h=None):
    from PyQt5.QtGui import QImage
    from PyQt5.QtCore import Qt
    img = QImage(path)
    if img.isNull():
        raise RuntimeError("cannot load image: " + path)
    if want_w and want_h and (img.width() != want_w or img.height() != want_h):
        img = img.scaled(want_w, want_h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    img = img.convertToFormat(QImage.Format_ARGB32)
    ptr = img.constBits()
    ptr.setsize(img.sizeInBytes())
    raw = bytes(ptr)
    w, h, bpl = img.width(), img.height(), img.bytesPerLine()
    if bpl != w * 4:  # strip row padding (never happens for ARGB32, kept for safety)
        raw = b"".join(raw[y * bpl:y * bpl + w * 4] for y in range(h))
    return raw, w, h


def svg_fit(svg, doc_w, doc_h, dpi):
    """Krita places SVG user units as points (1/72 in) on the image. Give the root <svg>
    explicit pt width/height so one SVG unit == one image pixel at any document dpi."""
    import re
    m = re.search(r"<svg\b[^>]*>", svg, flags=re.S)
    if not m:
        raise ValueError("no <svg> root element")
    tag = m.group(0)
    vb = re.search(r"""viewBox\s*=\s*(["'])(.+?)\1""", tag)
    new = re.sub(r"""\s(width|height)\s*=\s*(["']).*?\2""", "", tag)
    pt_w, pt_h = doc_w * 72.0 / dpi, doc_h * 72.0 / dpi
    extra = ' width="%.4fpt" height="%.4fpt"' % (pt_w, pt_h)
    if not vb:
        extra += ' viewBox="0 0 %d %d"' % (doc_w, doc_h)
    new = new[:-1].rstrip("/") + extra + (" />" if tag.endswith("/>") else ">")
    return svg[:m.start()] + new + svg[m.end():]


BLEND_ALIASES = {
    "normal": "normal", "multiply": "multiply", "screen": "screen", "overlay": "overlay",
    "darken": "darken", "lighten": "lighten", "add": "add", "subtract": "subtract",
    "difference": "diff", "diff": "diff", "color_dodge": "dodge", "dodge": "dodge",
    "color_burn": "burn", "burn": "burn", "soft_light": "soft_light_svg",
    "hard_light": "hard_light", "color": "color", "hue": "hue", "saturation": "saturation",
    "luminosity": "luminize", "luminize": "luminize", "erase": "erase",
}


def apply_common(node, spec):
    if "opacity" in spec:
        o = float(spec["opacity"])
        node.setOpacity(int(round(o * 255)) if o <= 1.0 else int(o))
    if spec.get("blend"):
        node.setBlendingMode(BLEND_ALIASES.get(spec["blend"], spec["blend"]))
    if spec.get("visible") is False:
        node.setVisible(False)
    if spec.get("locked"):
        node.setLocked(True)
    if spec.get("alpha_locked"):
        node.setAlphaLocked(True)
    if "x" in spec or "y" in spec:
        if spec.get("type") not in ("image",):  # image offset handled at pixel write
            node.move(int(spec.get("x", 0)), int(spec.get("y", 0)))


def apply_filters(k, doc, node, filters):
    """Default: a non-destructive Filter Mask under the layer (works on vector, group and
    fill layers too, and stays editable in Krita). {"destructive": true} bakes it into a
    paint layer with Filter.apply instead."""
    from krita import Selection
    out = []
    for f in filters or []:
        flt = k.filter(f["name"])
        if flt is None:
            raise ValueError("unknown filter %r (valid names: references/krita_live_info.json)" % f["name"])
        cfg = flt.configuration()
        for key, val in (f.get("config") or {}).items():
            cfg.setProperty(key, val)
        flt.setConfiguration(cfg)
        if f.get("destructive") and node.type() == "paintlayer":
            b = node.bounds()
            flt.apply(node, b.x(), b.y(), b.width(), b.height())
            doc.waitForDone()
            out.append(f["name"] + " (baked)")
            continue
        # Blurs must spill past the shape (glows); everything else (noise, halftone,
        # pixelize...) would also paint the transparent area, so clip to the layer's alpha.
        clip = f.get("clip", f["name"] not in SPREADING_FILTERS)
        sel = Selection()
        if clip:
            sel.setPixelData(alpha_bytes(doc, node), 0, 0, doc.width(), doc.height())
        else:
            sel.select(0, 0, doc.width(), doc.height(), 255)
        mask = doc.createFilterMask(f.get("mask_name", f["name"]), flt, sel)
        node.addChildNode(mask, None)
        doc.waitForDone()
        out.append(f["name"] + (" (mask, clipped)" if clip else " (mask)"))
    return out


SPREADING_FILTERS = {"blur", "gaussian blur", "lens blur", "motion blur", "maximize", "minimize"}


def alpha_bytes(doc, node):
    """8-bit selection (w*h) from the node's rendered alpha."""
    settle(doc, 400)
    W, H = doc.width(), doc.height()
    raw = bytes(node.projectionPixelData(0, 0, W, H))
    return raw[3::4] if node.colorDepth() == "U8" else bytes(W * H)


# ----------------------------------------------------------------- builders
def build_layer(k, doc, parent, spec, ctx):
    from krita import InfoObject, Selection
    t = spec.get("type", "paint")
    name = spec.get("name") or t
    W, H = doc.width(), doc.height()

    if t == "group":
        node = doc.createGroupLayer(name)
        parent.addChildNode(node, None)
        for child in spec.get("layers", []):
            build_layer(k, doc, node, child, ctx)
        if spec.get("pass_through"):
            node.setPassThroughMode(True)
        if spec.get("rasterize"):  # animation frame made of several layers -> one raster frame
            settle(doc, 600)
            raw = bytes(node.projectionPixelData(0, 0, W, H))
            paint = doc.createNode(name, "paintlayer")
            parent.addChildNode(paint, node)
            paint.setPixelData(raw, 0, 0, W, H)
            node.remove()
            node = paint

    elif t == "fill":
        # Editable Krita fill layer (color generator); falls back to a painted layer.
        node = None
        if spec.get("editable", True):
            try:
                r, g, b, a = hex_to_rgba(spec.get("color", "#ffffff"))
                info = InfoObject()
                info.setProperty("color", "<!DOCTYPE color><color><RGB r='%f' g='%f' b='%f' space='sRGB-elle-V2-srgbtrc.icc'/></color>" % (r / 255, g / 255, b / 255))
                sel = Selection()
                sel.select(0, 0, W, H, 255)
                node = doc.createFillLayer(name, "color", info, sel)
                parent.addChildNode(node, None)
            except Exception:  # noqa: BLE001
                node = None
        if node is None:
            node = doc.createNode(name, "paintlayer")
            parent.addChildNode(node, None)
            node.setPixelData(solid_bytes(W, H, spec.get("color", "#ffffff")), 0, 0, W, H)

    elif t == "svg":
        node = doc.createVectorLayer(name)
        parent.addChildNode(node, None)
        svg = spec.get("svg")
        if not svg and spec.get("file"):
            with open(spec["file"], "r", encoding="utf-8") as fh:
                svg = fh.read()
        shapes = node.addShapesFromSvg(svg_fit(svg, W, H, ctx["dpi"]))
        ctx.setdefault("svg_shapes", {})[name] = len(shapes)
        if spec.get("rasterize"):  # animation frames must be paint layers (keyframes are raster)
            settle(doc, 600)
            raw = bytes(node.projectionPixelData(0, 0, W, H))
            paint = doc.createNode(name, "paintlayer")
            parent.addChildNode(paint, node)
            paint.setPixelData(raw, 0, 0, W, H)
            node.remove()
            node = paint

    elif t in ("image", "paint"):
        node = doc.createNode(name, "paintlayer")
        parent.addChildNode(node, None)
        if spec.get("file"):
            raw, w, h = qimage_bytes(spec["file"], spec.get("width"), spec.get("height"))
            node.setPixelData(raw, int(spec.get("x", 0)), int(spec.get("y", 0)), w, h)
        elif spec.get("color"):
            node.setPixelData(solid_bytes(W, H, spec["color"]), 0, 0, W, H)

    elif t == "file_layer":  # linked external file, stays live in Krita
        node = doc.createFileLayer(name, spec["file"], spec.get("scaling", "None"))
        parent.addChildNode(node, None)

    elif t == "clone":
        src = doc.nodeByName(spec["source"])
        node = doc.createCloneLayer(name, src)
        parent.addChildNode(node, None)

    else:
        raise ValueError("unknown layer type %r" % t)

    if node.type() in ("vectorlayer", "grouplayer", "filllayer"):
        ctx["vector_like"] = ctx.get("vector_like", 0) + 1
        pump(150)
    doc.waitForDone()
    apply_common(node, spec)
    # Reported in build order (bottom -> top, children before their group); "parent"
    # tells which group a layer belongs to (None = top level).
    info = {"name": name, "type": node.type(), "blend": node.blendingMode(), "opacity": node.opacity(),
            "parent": None if parent == doc.rootNode() else parent.name()}
    if spec.get("filters"):
        info["filters"] = apply_filters(k, doc, node, spec["filters"])
    ctx["layers"].append(info)
    return node


def __main__(args):
    # Krita's excepthook opens a modal error dialog for uncaught exceptions; in a hidden
    # kritarunner that dialog would hang forever, so nothing may escape this function.
    global JOB_DIR
    JOB_DIR = args[0] if args else os.getcwd()
    try:
        _run()
    except Exception as e:  # noqa: BLE001
        STATE["ok"] = False
        STATE["fatal"] = repr(e)
        STATE["fatal_trace"] = traceback.format_exc()[-2000:]
        _dump()


def _run():
    with open(os.path.join(JOB_DIR, "job.json"), "r", encoding="utf-8") as fh:
        job = json.load(fh)

    from krita import Krita, InfoObject
    k = Krita.instance()
    k.setBatchmode(True)  # no dialogs, ever
    STATE["krita_version"] = k.version()

    if job.get("introspect"):
        def intro():
            filters = {}
            for n in k.filters():
                try:
                    flt = k.filter(n)  # keep the Filter alive: its InfoObject dies with it
                    cfg = flt.configuration()
                    filters[n] = {kk: str(v)[:80] for kk, v in cfg.properties().items()}
                except Exception as e:  # noqa: BLE001
                    filters[n] = {"_error": repr(e)}
            return {"version": k.version(), "filters": filters,
                    "brush_presets": sorted(k.resources("preset").keys()),
                    "gradients": sorted(k.resources("gradient").keys()),
                    "patterns": sorted(k.resources("pattern").keys())[:200],
                    "color_models": {m: k.colorDepths(m) for m in k.colorModels()}}
        STATE["info"] = step("introspect", intro)
        STATE["ok"] = True
        _dump()
        return

    cv = job.get("canvas", {})
    dpi = float(cv.get("dpi", 72))
    ctx = {"dpi": dpi, "layers": []}

    def open_doc():
        if job.get("base"):
            d = k.openDocument(job["base"])
            if d is None:
                raise RuntimeError("cannot open base document")
        else:
            d = k.createDocument(int(cv["width"]), int(cv["height"]), cv.get("name", "claude"),
                                 cv.get("color", "RGBA"), cv.get("depth", "U8"), cv.get("profile", ""), dpi)
        d.setBatchmode(True)
        k.setActiveDocument(d)
        return d
    doc = step("create_document", open_doc)

    def bg():
        root = doc.rootNode()
        kids = root.childNodes()
        if job.get("base"):
            return "kept"
        if kids and kids[0].type() == "paintlayer":
            b = cv.get("background")
            if b in (None, "transparent"):
                kids[0].remove()
                return "removed"
            kids[0].setName("Background")
            kids[0].setPixelData(solid_bytes(doc.width(), doc.height(), b), 0, 0, doc.width(), doc.height())
            return b
    step("background", bg)

    root = doc.rootNode()
    for i, spec in enumerate(job.get("layers", [])):
        step("layer[%d] %s:%s" % (i, spec.get("type", "paint"), spec.get("name", "")), build_layer, k, doc, root, spec, ctx)

    if job.get("python"):
        def run_py():
            from PyQt5 import QtCore, QtGui
            g = {"k": k, "doc": doc, "root": root, "InfoObject": InfoObject, "QtCore": QtCore, "QtGui": QtGui,
                 "JOB_DIR": JOB_DIR, "solid_bytes": solid_bytes, "qimage_bytes": qimage_bytes, "result": {}}
            with open(job["python"], "r", encoding="utf-8") as fh:
                code = fh.read()
            exec(compile(code, job["python"], "exec"), g)
            doc.waitForDone()
            return g.get("result")
        step("python", run_py)

    if job.get("anim_export"):
        def anim_export():
            a = job["anim_export"]
            doc.setFramesPerSecond(int(a["fps"]))
            doc.setFullClipRangeStartTime(0)
            doc.setFullClipRangeEndTime(int(a["end"]))
            os.makedirs(a["dir"], exist_ok=True)
            n = 0
            for t in range(int(a["end"]) + 1):
                doc.setCurrentTime(t)
                settle(doc, 120)
                doc.exportImage(os.path.join(a["dir"], "fr_%04d.png" % t), InfoObject())
                n += 1
            doc.setCurrentTime(int(a.get("poster", 0)))
            settle(doc, 200)
            return {"frames": n, "fps": doc.framesPerSecond()}
        STATE["anim"] = step("anim_export", anim_export)

    def export():
        settle(doc, 700 + 250 * ctx.get("vector_like", 0))
        out = {}
        o = job.get("output", {})
        for fmt in ("png", "jpg", "webp", "tif", "psd"):
            if o.get(fmt):
                cfg = InfoObject()
                if fmt == "png":
                    cfg.setProperty("alpha", bool(o.get("alpha", True)))
                    cfg.setProperty("compression", 6)
                    cfg.setProperty("forceSRGB", True)
                    cfg.setProperty("saveSRGBProfile", True)
                if fmt == "jpg":
                    cfg.setProperty("quality", int(o.get("quality", 92)))
                out[fmt] = doc.exportImage(o[fmt], cfg)
        if o.get("kra"):
            ok = False
            for attempt in range(4):  # saveAs refuses while the image is still busy
                ok = doc.saveAs(o["kra"])
                if ok:
                    break
                settle(doc, 800)
            out["kra"] = ok
        return out
    STATE["exports"] = step("export", export)
    STATE["canvas"] = [doc.width(), doc.height()]
    STATE["layers"] = ctx["layers"]
    STATE["svg_shapes"] = ctx.get("svg_shapes", {})
    doc.setModified(False)
    doc.close()
    STATE["ok"] = all(STATE["exports"].values()) if STATE.get("exports") else True
    STATE["seconds"] = round(time.time() - STATE["started"], 2)
    _dump()
