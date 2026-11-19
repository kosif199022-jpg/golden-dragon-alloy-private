#!/usr/bin/env python3
"""PSD studio (v10.8.1): Photoshop files without Photoshop — real layered .psd in and out.

    psd.py inspect FILE.psd [--json]                 layers tree: name, kind, visible, opacity, blend, box
    psd.py export FILE.psd --out DIR                 composite.png + one PNG per layer (+ layers.json)
    psd.py build SPEC.json OUT.psd                   layered PSD from images / cut-outs / Arabic titles / fills,
                                                     + OUT.preview.png. Opens with layers in Photoshop, GIMP, Krita, Photopea
    psd.py cutout IMAGE OUT.png [--download]         background removal (rembg; a model is fetched only with --download)
    psd.py doctor                                    what is available here (psd-tools, rembg, GIMP, Krita, Photoshop)

SPEC.json:
  {"size": [1080, 1920], "background": "#0b0b0f",
   "layers": [
     {"type": "image", "path": "bg.jpg", "fit": "cover", "name": "خلفية"},
     {"type": "cutout", "path": "person.jpg", "x": 90, "y": 560, "width": 900, "name": "البطل"},
     {"type": "fill", "color": "#000000", "opacity": 0.35, "name": "تعتيم"},
     {"type": "title", "text": "بطلة تحدي القراءة", "font": "C:/Windows/Fonts/arial.ttf", "size": 110,
      "color": "#f5c542", "x": "center", "y": 220, "stroke": 6, "stroke_color": "#000000", "name": "العنوان"}]}

Why: the owner asked for Photoshop inside the Dragon. Photoshop is not installed here, is paid (Adobe account), and is
not copied or decompiled; this gives the same deliverable (an editable layered PSD) with local tools, and the
downloaded Photoshop-control skills (dragon-repos/creative) stay ready for the day Photoshop is installed.
Nothing overwrites an existing file.
"""
import argparse, json, shutil, sys
from pathlib import Path


def _need_new(p):
    p = Path(p)
    if p.exists():
        sys.exit(f"refusing to overwrite {p}")
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _rgba(hexcolor, alpha=1.0):
    h = hexcolor.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (int(round(255 * alpha)),)


# ------------------------------------------------------------------------------------------- inspect / export
def walk(group, depth=0):
    for L in group:
        yield depth, L
        if L.is_group():
            yield from walk(L, depth + 1)


def inspect(path):
    from psd_tools import PSDImage
    psd = PSDImage.open(path)
    rows = []
    for d, L in walk(psd):
        rows.append({"depth": d, "name": L.name, "kind": L.kind, "visible": L.visible,
                     "opacity": round(L.opacity / 255, 3), "blend": str(L.blend_mode).split(".")[-1],
                     "box": list(L.bbox)})
    return {"path": str(path), "size": [psd.width, psd.height], "mode": str(psd.color_mode).split(".")[-1],
            "depth_bits": psd.depth, "layers": rows}


def export(path, out):
    from psd_tools import PSDImage
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    psd = PSDImage.open(path)
    comp = _need_new(out / "composite.png")
    psd.composite().save(comp)
    meta = []
    for i, (d, L) in enumerate(walk(psd), 1):
        if L.is_group():
            continue
        im = L.composite() if L.kind != "pixel" else L.topil()
        if im is None:
            continue
        safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in L.name).strip() or "layer"
        f = _need_new(out / f"{i:02d}_{safe}.png")
        im.save(f)
        meta.append({"file": f.name, "name": L.name, "box": list(L.bbox), "visible": L.visible})
    (out / "layers.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return comp, meta


# ------------------------------------------------------------------------------------------- build
def _fit(im, W, H, mode):
    from PIL import Image, ImageOps
    if mode == "cover":
        return ImageOps.fit(im, (W, H), Image.LANCZOS)
    if mode == "contain":
        c = im.copy(); c.thumbnail((W, H), Image.LANCZOS)
        return c
    return im


def _scale(im, layer):
    from PIL import Image
    w = layer.get("width")
    if w:
        im = im.resize((int(w), int(round(im.height * int(w) / im.width))), Image.LANCZOS)
    return im


def _pos(layer, im, W, H):
    x, y = layer.get("x", 0), layer.get("y", 0)
    if x == "center":
        x = (W - im.width) // 2
    if y == "center":
        y = (H - im.height) // 2
    return int(x), int(y)


REMBG_MODELS = {"u2net": "176 MB", "isnet-general-use": "179 MB", "birefnet-general": "973 MB", "bria-rmbg": "1 GB"}


class ModelNotCached(RuntimeError):
    pass


def rembg_model(allow_download=False):
    """A rembg model that is already on disk (~/.u2net or U2NET_HOME). rembg's own default downloads ~1 GB silently,
    so nothing is fetched unless allow_download (the owner said yes); then the small u2net (176 MB) is used."""
    import os
    home = Path(os.environ.get("U2NET_HOME") or Path.home() / ".u2net")
    for name in REMBG_MODELS:
        if (home / f"{name}.onnx").is_file():
            return name
    if allow_download:
        return "u2net"
    raise ModelNotCached(f"no background-removal model in {home}. Downloading the smallest (u2net, 176 MB) needs "
                         "your yes: run again with --download")


def cutout(src, dst=None, allow_download=False):
    from PIL import Image
    from rembg import new_session, remove
    im = remove(Image.open(src).convert("RGBA"), session=new_session(rembg_model(allow_download)))
    if dst:
        im.save(_need_new(dst))
    return im


def title_image(text, font, size, color="#ffffff", stroke=0, stroke_color="#000000", max_width=None):
    """Arabic-safe text as a tight RGBA image (shaped + RTL with arabic_reshaper/python-bidi when installed)."""
    from PIL import Image, ImageDraw, ImageFont, features
    kw = {}
    if features.check("raqm"):  # libraqm shapes and orders Arabic itself: reshaping as well would reverse it
        shaped = text
        if any("؀" <= c <= "ۿ" for c in text):
            kw = {"direction": "rtl", "language": "ar"}
    else:
        try:
            import arabic_reshaper
            from bidi.algorithm import get_display
            shaped = "\n".join(get_display(arabic_reshaper.reshape(ln)) for ln in text.split("\n"))
        except ImportError:
            shaped = text
    f = ImageFont.truetype(font, int(size))
    d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    box = d.multiline_textbbox((0, 0), shaped, font=f, stroke_width=int(stroke), align="center", **kw)
    w, h = box[2] - box[0] + 4, box[3] - box[1] + 4
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(im).multiline_text((2 - box[0], 2 - box[1]), shaped, font=f, fill=_rgba(color),
                                      stroke_width=int(stroke), stroke_fill=_rgba(stroke_color), align="center", **kw)
    if max_width and im.width > max_width:
        im = im.resize((int(max_width), int(im.height * max_width / im.width)), Image.LANCZOS)
    return im


def build(spec_path, out_psd, allow_download=False):
    from PIL import Image
    from psd_tools import PSDImage
    from psd_tools.api.layers import PixelLayer
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8-sig"))
    base = Path(spec_path).resolve().parent
    W, H = spec.get("size", [1080, 1920])
    out_psd = _need_new(out_psd)
    preview = _need_new(out_psd.with_suffix(".preview.png"))
    psd = PSDImage.new(mode="RGB", size=(W, H), color=_rgba(spec.get("background", "#000000"))[:3])
    flat = Image.new("RGBA", (W, H), _rgba(spec.get("background", "#000000")))
    report = []
    for i, L in enumerate(spec.get("layers", []), 1):
        t = L["type"]
        if t in ("image", "cutout"):
            p = Path(L["path"]); p = p if p.is_absolute() else base / p
            im = cutout(p, allow_download=allow_download) if t == "cutout" else Image.open(p).convert("RGBA")
            im = _scale(_fit(im, W, H, L.get("fit")), L)
        elif t == "fill":
            im = Image.new("RGBA", (W, H), _rgba(L.get("color", "#000000")))
        elif t == "title":
            im = title_image(L["text"], L.get("font") or "C:/Windows/Fonts/arial.ttf", L.get("size", 96),
                             L.get("color", "#ffffff"), L.get("stroke", 0), L.get("stroke_color", "#000000"),
                             L.get("max_width", W - 80))
        else:
            sys.exit(f"layer {i}: unknown type {t}")
        x, y = (0, 0) if t == "fill" else _pos(L, im, W, H)
        op = float(L.get("opacity", 1.0))
        name = L.get("name") or f"{t} {i}"
        layer = PixelLayer.frompil(im, psd, f"layer {i}", top=y, left=x)
        layer.name = name  # Arabic names: legacy field "?" + Photoshop's Unicode name block (luni)
        layer.opacity = int(round(255 * op))
        psd.append(layer)
        tmp = im.copy()
        if op < 1:
            a = tmp.getchannel("A").point(lambda v: int(v * op)); tmp.putalpha(a)
        flat.alpha_composite(tmp, (max(x, 0), max(y, 0)) if x >= 0 and y >= 0 else (0, 0))
        report.append({"name": name, "type": t, "box": [x, y, x + im.width, y + im.height], "opacity": op})
    psd.save(out_psd)
    flat.convert("RGB").save(preview)
    back = inspect(out_psd)
    return {"psd": str(out_psd), "preview": str(preview), "size": [W, H], "layers": report,
            "reopened_layers": len(back["layers"])}


def _repos_dir():
    """Folder that holds the downloaded skill repos. DRAGON_REPOS overrides; default is ~/dragon-repos."""
    import os
    return Path(os.environ.get("DRAGON_REPOS") or Path.home() / "dragon-repos")


def doctor():
    import importlib.util as u
    ps = [p for p in (Path("C:/Program Files/Adobe"),) if p.exists() and any(p.glob("Adobe Photoshop*"))]
    return {"psd-tools": bool(u.find_spec("psd_tools")), "rembg": bool(u.find_spec("rembg")),
            "arabic_reshaper": bool(u.find_spec("arabic_reshaper")), "bidi": bool(u.find_spec("bidi")),
            "gimp": shutil.which("gimp-console-3.2") or shutil.which("gimp-console"),
            "krita": shutil.which("kritarunner"), "magick": shutil.which("magick"),
            "photoshop": bool(ps),
            "photoshop_skills": f"{_repos_dir() / 'creative'} (photoshop-mcp, photoshop-python-api-mcp-server, "
                                "claude-photoshop-skill) — usable only once Photoshop is installed and licensed"}


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="psd", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("inspect"); i.add_argument("file"); i.add_argument("--json", action="store_true")
    e = sub.add_parser("export"); e.add_argument("file"); e.add_argument("--out", required=True)
    b = sub.add_parser("build"); b.add_argument("spec"); b.add_argument("out"); b.add_argument("--download", action="store_true")
    c = sub.add_parser("cutout"); c.add_argument("image"); c.add_argument("out"); c.add_argument("--download", action="store_true")
    sub.add_parser("doctor")
    a = ap.parse_args(argv)
    if a.cmd == "inspect":
        r = inspect(a.file)
        if a.json:
            print(json.dumps(r, ensure_ascii=False, indent=1)); return 0
        print(f"{r['path']}  {r['size'][0]}x{r['size'][1]} {r['mode']} {r['depth_bits']}-bit  · {len(r['layers'])} طبقة")
        for L in r["layers"]:
            print(f"  {'  ' * L['depth']}{'👁' if L['visible'] else '  '} {L['name']}  [{L['kind']}] "
                  f"opacity {L['opacity']} {L['blend']} {L['box']}")
    elif a.cmd == "export":
        comp, meta = export(a.file, a.out)
        print(f"composite -> {comp}\n{len(meta)} layer PNGs -> {Path(a.out).resolve()}")
    elif a.cmd == "build":
        print(json.dumps(build(a.spec, a.out, a.download), ensure_ascii=False, indent=1))
    elif a.cmd == "cutout":
        cutout(a.image, a.out, a.download); print("cutout ->", a.out)
    elif a.cmd == "doctor":
        print(json.dumps(doctor(), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ModelNotCached as e:
        sys.exit(f"cutout: {e}")
