"""font_lab.py - Arabic font lab for the absolute-creativity skill.

  python font_lab.py list [--json] [--dir EXTRA_DIR ...]
  python font_lab.py specimen "النص" --out sheet.png [--size 72] [--filter ruqaa] [--max 40]
  python font_lab.py title "النص" --font PATH --out title.png [--size 160] [--color #F5C542]
        [--stroke 6] [--stroke-color #000000] [--shadow 10] [--width 1080]

Lists fonts that really cover Arabic (checked with fontTools cmap), renders a
specimen sheet with correct shaping (Pillow + libraqm), and renders a
transparent RTL title PNG ready for ffmpeg overlay.
"""
import argparse
import json
import logging
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, features

try:
    from fontTools.ttLib import TTFont, TTCollection
except ImportError:  # pragma: no cover
    TTFont = None

logging.getLogger("fontTools").setLevel(logging.ERROR)
HOME = Path.home()
DEFAULT_DIRS = [
    Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts",
    HOME / "AppData/Local/Microsoft/Windows/Fonts",
    Path("/usr/share/fonts"),
    Path("/usr/local/share/fonts"),
    HOME / ".local/share/fonts",
    Path("/System/Library/Fonts"),
    Path("/Library/Fonts"),
    HOME / "Library/Fonts",
]
# Never distribute the author's machine-specific font cache in the skill.
CACHE = Path(os.environ.get("DRAGON_FONT_CACHE", str(HOME / ".cache/black-dragon/font_lab.json")))
ARABIC_PROBE = [0x0627, 0x0628, 0x0639, 0x0642, 0x0647, 0x064A, 0x0645, 0x0644]
EXTS = {".ttf", ".otf", ".ttc"}


def _cmap_has_arabic(path):
    try:
        if path.suffix.lower() == ".ttc":
            fonts = TTCollection(str(path), lazy=True).fonts
        else:
            fonts = [TTFont(str(path), lazy=True, fontNumber=0)]
        for f in fonts:
            cmap = f.getBestCmap() or {}
            if all(cp in cmap for cp in ARABIC_PROBE):
                name = f["name"].getDebugName(4) or path.stem
                return name
    except Exception:
        return None
    return None


def scan(extra_dirs=(), refresh=False):
    if CACHE.exists() and not refresh and not extra_dirs:
        try:
            cached = json.loads(CACHE.read_text(encoding="utf-8"))
            if isinstance(cached, list) and all(Path(r["path"]).is_file() for r in cached):
                return cached
        except (OSError, ValueError, KeyError, TypeError):
            pass
    seen, out = set(), []
    env_dirs = [Path(x) for x in os.environ.get("DRAGON_FONT_DIRS", "").split(os.pathsep) if x]
    for d in list(DEFAULT_DIRS) + env_dirs + [Path(x) for x in extra_dirs]:
        if not d.exists():
            continue
        for p in d.rglob("*"):
            if p.suffix.lower() not in EXTS or not p.is_file():
                continue
            key = p.name.lower()
            if key in seen:
                continue
            name = _cmap_has_arabic(p)
            if name:
                seen.add(key)
                out.append({"name": name, "path": str(p)})
    out.sort(key=lambda r: r["name"].lower())
    if not extra_dirs:
        try:
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            CACHE.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass  # read-only systems can still list fonts without a cache
    return out


def _font(path, size):
    return ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.RAQM)


def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4)) + (255,)


def cmd_list(a):
    rows = scan(a.dir, a.refresh)
    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
    else:
        for r in rows:
            print(f"{r['name']:<40} {r['path']}")
        print(f"\n{len(rows)} Arabic-capable fonts")


def cmd_specimen(a):
    rows = scan(a.dir)
    if a.filter:
        rows = [r for r in rows if a.filter.lower() in (r["name"] + r["path"]).lower()]
    rows = rows[: a.max]
    if not rows:
        sys.exit("no fonts matched")
    W, pad, lab = 1600, 30, 26
    line_h = int(a.size * 1.9) + lab
    img = Image.new("RGB", (W, pad * 2 + line_h * len(rows)), (14, 14, 16))
    d = ImageDraw.Draw(img)
    label_font = ImageFont.load_default(size=lab - 6) if hasattr(ImageFont, "load_default") else None
    y = pad
    for r in rows:
        d.text((pad, y), r["name"], fill=(150, 150, 150), font=label_font)
        try:
            f = _font(r["path"], a.size)
            d.text((W - pad, y + lab), a.text, font=f, fill=(240, 232, 214),
                   anchor="ra", direction="rtl", language="ar")
        except Exception as e:  # keep going
            d.text((pad, y + lab), f"error: {e}", fill=(200, 80, 80), font=label_font)
        y += line_h
    img.save(a.out)
    print(f"saved {a.out}  ({len(rows)} fonts)")


def cmd_title(a):
    f = _font(a.font, a.size)
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    l, t, r, b = probe.textbbox((0, 0), a.text, font=f, direction="rtl", language="ar",
                                stroke_width=a.stroke)
    margin = a.stroke + a.shadow * 3 + 20
    w = max(a.width or 0, r - l + margin * 2)
    h = b - t + margin * 2
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    pos = ((w - (r - l)) // 2 - l, margin - t)
    if a.shadow:
        sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((pos[0] + a.shadow, pos[1] + a.shadow), a.text, font=f,
                                fill=(0, 0, 0, 170), direction="rtl", language="ar",
                                stroke_width=a.stroke, stroke_fill=(0, 0, 0, 170))
        img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(a.shadow * 0.8)))
    ImageDraw.Draw(img).text(pos, a.text, font=f, fill=_hex(a.color), direction="rtl",
                             language="ar", stroke_width=a.stroke,
                             stroke_fill=_hex(a.stroke_color))
    img.save(a.out)
    print(f"saved {a.out}  {w}x{h}  (overlay: ffmpeg -i in.mp4 -i {a.out} "
          f"-filter_complex \"overlay=(W-w)/2:H*0.7\" -c:a copy out.mp4)")


def main():
    if not features.check("raqm"):
        sys.exit("Pillow libraqm is required for Arabic shaping; refusing incorrect RTL rendering")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("list"); s.add_argument("--json", action="store_true")
    s.add_argument("--refresh", action="store_true", help="rescan disks, ignore cache")
    s.add_argument("--dir", action="append", default=[]); s.set_defaults(fn=cmd_list)
    s = sub.add_parser("specimen"); s.add_argument("text"); s.add_argument("--out", required=True)
    s.add_argument("--size", type=int, default=64); s.add_argument("--filter")
    s.add_argument("--max", type=int, default=40); s.add_argument("--dir", action="append", default=[])
    s.set_defaults(fn=cmd_specimen)
    s = sub.add_parser("title"); s.add_argument("text"); s.add_argument("--font", required=True)
    s.add_argument("--out", required=True); s.add_argument("--size", type=int, default=160)
    s.add_argument("--color", default="#F5C542"); s.add_argument("--stroke", type=int, default=6)
    s.add_argument("--stroke-color", default="#000000"); s.add_argument("--shadow", type=int, default=10)
    s.add_argument("--width", type=int, default=0); s.set_defaults(fn=cmd_title)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
