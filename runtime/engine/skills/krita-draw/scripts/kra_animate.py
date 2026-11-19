"""kra_animate.py - turn N frame layers of a .kra into ONE animated paint layer with real
timeline keyframes (headless Krita cannot create keyframes: importAnimation crashes and
setPixelData on an animated layer never adds a key - measured on 5.3.4).

How: Krita stores a raster keyframe as <keyframe time=T frame="<data file>"> inside
layers/<layer>.keyframes.xml, and the frame data file can be any paint-layer data file in
the same .kra. So we keep every frame layer's pixel file, point keyframes at them, and drop
the extra <layer> elements from maindoc.xml. Krita re-saves it in its own naming on next save.

    python -X utf8 kra_animate.py in.kra out.kra --frames f0 f1 f2 ... [--name anim] [--fps 12] [--hold 1 1 2 ...]
"""
from __future__ import annotations

import argparse
import re
import zipfile

KF_HEAD = ("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
           "<!DOCTYPE keyframes PUBLIC '-//KDE//DTD krita-keyframes 1.0//EN' "
           "'http://www.calligra.org/DTD/krita-keyframes-1.0.dtd'>\n")


def layer_elements(maindoc: str):
    """name -> (full element text, filename) for self-closing paint layers."""
    out = {}
    for m in re.finditer(r"<layer\b[^>]*?/>", maindoc, flags=re.S):
        el = m.group(0)
        nm = re.search(r'\bname="([^"]*)"', el)
        fn = re.search(r'\bfilename="([^"]*)"', el)
        nt = re.search(r'\bnodetype="([^"]*)"', el)
        if nm and fn and nt and nt.group(1) == "paintlayer":
            out[nm.group(1)] = (el, fn.group(1))
    return out


def animate(kra_in, kra_out, frames, name="animation", fps=12, holds=None):
    zin = zipfile.ZipFile(kra_in)
    maindoc = zin.read("maindoc.xml").decode("utf-8")
    els = layer_elements(maindoc)
    missing = [f for f in frames if f not in els]
    if missing:
        raise SystemExit("frame layers not found (must be top-level paint layers): %s" % missing)
    holds = holds or [1] * len(frames)
    first_el, first_file = els[frames[0]]
    doc_name = re.search(r'<IMAGE\b[^>]*\bname="([^"]*)"', maindoc).group(1)
    layers_dir = doc_name + "/layers/"

    # keyframes point at each frame layer's own data file
    t, keys = 0, []
    for f, h in zip(frames, holds):
        keys.append('  <keyframe time="%d" frame="%s" color-label="0">\n   <offset type="point" x="0" y="0"/>\n  </keyframe>' % (t, els[f][1]))
        t += int(h)
    total = t
    kf_name = first_file + ".keyframes.xml"
    kf_xml = KF_HEAD + '<keyframes xmlns="http://www.calligra.org/DTD/krita-keyframes">\n <channel name="content">\n' + "\n".join(keys) + "\n </channel>\n</keyframes>\n"

    from xml.sax.saxutils import escape
    safe = escape(name, {'"': "&quot;"})
    new_el = re.sub(r'\bname="[^"]*"', lambda _m: 'name="%s"' % safe, first_el, count=1)
    new_el = new_el.replace("<layer ", '<layer keyframes="%s" ' % kf_name, 1)
    md = maindoc.replace(first_el, new_el, 1)
    for f in frames[1:]:
        md = md.replace(els[f][0], "", 1)

    idx_name = doc_name + "/animation/index.xml"
    idx = zin.read(idx_name).decode("utf-8") if idx_name in zin.namelist() else (
        '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE animation-metadata PUBLIC \'-//KDE//DTD krita 1.1//EN\' '
        '\'http://www.calligra.org/DTD/krita-1.1.dtd\'>\n<animation-metadata xmlns="http://www.calligra.org/DTD/krita">\n'
        ' <framerate value="12" type="value"/>\n <range to="0" from="0" type="timerange"/>\n'
        ' <currentTime value="0" type="value"/>\n</animation-metadata>\n')
    # Qt writes XML attributes in varying order (type/value swap), so match the whole element.
    idx = re.sub(r"<framerate\b[^>]*/>", '<framerate type="value" value="%d"/>' % fps, idx)
    idx = re.sub(r"<range\b[^>]*/>", '<range type="timerange" from="0" to="%d"/>' % (total - 1), idx)

    with zipfile.ZipFile(kra_out, "w") as zout:
        zout.writestr(zipfile.ZipInfo("mimetype"), zin.read("mimetype"), compress_type=zipfile.ZIP_STORED)
        for info in zin.infolist():
            n = info.filename
            if n in ("mimetype", "maindoc.xml", idx_name):
                continue
            zout.writestr(info, zin.read(n), compress_type=zipfile.ZIP_DEFLATED)
        zout.writestr("maindoc.xml", md.encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED)
        zout.writestr(layers_dir + kf_name, kf_xml.encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED)
        zout.writestr(idx_name, idx.encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED)
    return {"layer": name, "keyframes": len(frames), "frames_total": total, "fps": fps, "data_file": first_file}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("kra_in")
    ap.add_argument("kra_out")
    ap.add_argument("--frames", nargs="+", required=True)
    ap.add_argument("--name", default="animation")
    ap.add_argument("--fps", type=int, default=12)
    ap.add_argument("--hold", nargs="*", type=int)
    a = ap.parse_args()
    import json
    print(json.dumps(animate(a.kra_in, a.kra_out, a.frames, a.name, a.fps, a.hold), ensure_ascii=False))
