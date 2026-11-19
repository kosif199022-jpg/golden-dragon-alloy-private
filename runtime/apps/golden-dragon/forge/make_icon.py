"""make_icon.py — the «التنين الذهبي» icon: the Red Dragon's glyph, recoloured gold on the Golden Bird's dark ink.

Source: ..\\..\\red-dragon.ico (the Red Dragon app icon in «مهارات», 256 px max). The cream glyph is separated from the red
tile by the green channel (red tile G≈20-60, cream glyph G≈235), which keeps the anti-aliased edges. Writes
overlay\\icon\\gd-<size>.png (16…256, plus 512 upscaled for downscaling only) and golden-dragon.ico.

  python -X utf8 make_icon.py
"""
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

FORGE = Path(__file__).resolve().parent
SRC = FORGE.parent.parent / "red-dragon.ico"
OUT = FORGE / "overlay" / "icon"
INK_TOP, INK_BOTTOM = (46, 40, 30), (20, 19, 17)          # warm dark ink (Golden Bird surfaces)
GOLD_TOP, GOLD_BOTTOM = (247, 220, 128), (200, 145, 30)   # glyph gradient
RIM = (227, 179, 65)


def vgrad(size, top, bottom):
    w, h = size
    g = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        g.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)))
    return g.resize((w, h))


def golden(src):
    src = src.convert("RGBA")
    r, g, b, a = src.split()
    lo, hi = 70, 225                                       # green channel: tile -> 0, glyph -> 255
    glyph = g.point(lambda v: 0 if v <= lo else 255 if v >= hi else round((v - lo) * 255 / (hi - lo)))
    tile = vgrad(src.size, INK_TOP, INK_BOTTOM).convert("RGBA")
    gold = vgrad(src.size, GOLD_TOP, GOLD_BOTTOM).convert("RGBA")
    out = Image.composite(gold, tile, glyph)
    # thin gold rim just inside the tile edge: alpha minus its eroded copy
    w, h = src.size
    inner = a.resize((max(1, w - 6), max(1, h - 6)), Image.LANCZOS)
    shrunk = Image.new("L", src.size, 0)
    shrunk.paste(inner, (3, 3))
    rim = ImageChops.subtract(a, shrunk).point(lambda v: round(v * 0.55))
    out = Image.composite(Image.new("RGBA", src.size, RIM + (255,)), out, rim)
    out.putalpha(a)
    return out


def main():
    ico = Image.open(SRC)
    big = max(ico.info.get("sizes") or [ico.size], key=lambda s: s[0])
    ico.size = big
    base = golden(ico)
    OUT.mkdir(parents=True, exist_ok=True)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    for s in sizes + [512]:
        base.resize((s, s), Image.LANCZOS).save(OUT / f"gd-{s}.png")
    base.save(OUT / "golden-dragon.ico", sizes=[(s, s) for s in sizes])
    print(f"✓ {OUT / 'golden-dragon.ico'} ({', '.join(map(str, sizes))}) + gd-*.png from {SRC.name} {big}")


if __name__ == "__main__":
    main()
