"""Generator: night desert with crescent, stars, dunes, palms.
    python -X utf8 make_scene.py [OUT_DIR]  -> OUT_DIR/scene.json (+ post.py), then krita_draw.py render it."""
import json, math, random, shutil, sys
from pathlib import Path

W, H = 1080, 1350
rnd = random.Random(11)
here = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()  # output dir
here.mkdir(parents=True, exist_ok=True)
shutil.copy2(Path(__file__).with_name("post.py"), here / "post.py")

sky = f"""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {W} {H}'>
<defs><linearGradient id='s' x1='0' y1='0' x2='0' y2='1'>
<stop offset='0' stop-color='#070b1f'/><stop offset='0.55' stop-color='#1d2457'/><stop offset='1' stop-color='#7b4a6b'/></linearGradient></defs>
<rect width='{W}' height='{H}' fill='url(#s)'/></svg>"""

stars = "".join(f"<circle cx='{rnd.uniform(0,W):.1f}' cy='{rnd.uniform(0,H*0.62):.1f}' r='{rnd.choice([0.8,1.1,1.4,2.0]):.1f}' fill='#ffffff' opacity='{rnd.uniform(0.35,1):.2f}'/>" for _ in range(260))
stars_svg = f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {W} {H}'>{stars}</svg>"

# crescent = big circle minus offset circle via even-odd path
cx, cy, r = 780, 300, 95
def crescent(cx, cy, r, ox, oy, r2, n=240):
    """Outer circle minus a shifted inner circle, as one clean polygon."""
    out = [(cx + r * math.cos(t), cy + r * math.sin(t)) for t in (2 * math.pi * i / n for i in range(n))]
    keep = [p for p in out if (p[0] - cx - ox) ** 2 + (p[1] - cy - oy) ** 2 > r2 * r2]
    inner = [(cx + ox + r2 * math.cos(t), cy + oy + r2 * math.sin(t)) for t in (2 * math.pi * i / n for i in range(n))]
    cut = [p for p in inner if (p[0] - cx) ** 2 + (p[1] - cy) ** 2 < r * r]
    # order both arcs by angle around the outer centre so the outline does not cross itself
    ang = lambda p: math.atan2(p[1] - cy, p[0] - cx)
    a0 = math.atan2(-oy, -ox)  # direction of the lit side
    norm = lambda a: (a - a0 + 3 * math.pi) % (2 * math.pi)
    keep.sort(key=lambda p: norm(ang(p)))
    cut.sort(key=lambda p: -norm(ang(p)))
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in keep + cut)


moon = f"""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {W} {H}'>
<polygon fill='#fff3c4' points='{crescent(cx, cy, r, 38, -22, r - 6)}'/></svg>"""
glow = f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {W} {H}'><circle cx='{cx}' cy='{cy}' r='150' fill='#ffd98a' opacity='0.55'/></svg>"


def dune(y0, amp, color, seed):
    rr = random.Random(seed)
    pts = []
    for i in range(0, W + 61, 60):
        pts.append((i, y0 + amp * math.sin(i / 210 + seed) + rr.uniform(-12, 12)))
    d = f"M 0 {H} L " + " L ".join(f"{x:.0f} {y:.0f}" for x, y in pts) + f" L {W} {H} Z"
    return f"<path d='{d}' fill='{color}'/>"


dunes = f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {W} {H}'>" + dune(930, 40, "#3a2a4a", 1) + dune(1030, 55, "#2a1d33", 2) + dune(1150, 35, "#170f1f", 3) + "</svg>"

# palm silhouettes with the ink brush: trunk + fronds
strokes = []
for (px, py, hgt) in [(250, 1120, 330), (360, 1150, 250)]:
    trunk = [[px + 18 * math.sin(t * 2.2), py - t * hgt, 1.0 - 0.45 * t] for t in [i / 10 for i in range(11)]]
    strokes.append({"points": trunk, "tip": "ink", "size": 22, "color": "#0b0710", "taper": [0.0, 0.2]})
    tx, ty = trunk[-1][0], trunk[-1][1]
    for ang in range(-170, 10, 26):
        a = math.radians(ang)
        L = rnd.uniform(110, 160)
        mid = [tx + 0.55 * L * math.cos(a), ty + 0.55 * L * math.sin(a) - 18, 1.0]
        end = [tx + L * math.cos(a), ty + L * math.sin(a) + 35, 0.2]
        strokes.append({"points": [[tx, ty, 0.6], mid, end], "tip": "ink", "size": 16, "color": "#0b0710"})
# wind lines in chalk
for i in range(5):
    y = 860 + i * 22
    strokes.append({"points": [[80 + i * 30, y, 0.3], [400, y - 10, 0.8], [700 + i * 20, y + 6, 0.2]], "tip": "chalk", "size": 5, "color": "#c9b8e8", "opacity": 0.35})

title = f"""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {W} {H}'>
<text x='{W-70}' y='1270' font-size='76' font-family='Sakkal Majalla' fill='#ffe7a8' direction='rtl' text-anchor='start'>ليلة في الصحراء</text></svg>"""

scene = {
    "canvas": {"width": W, "height": H, "background": "#000000"},
    "layers": [
        {"type": "svg", "name": "سماء", "svg": sky},
        {"type": "svg", "name": "نجوم", "svg": stars_svg},
        {"type": "group", "name": "هلال ونور", "blend": "screen", "layers": [
            {"type": "svg", "name": "توهج", "svg": glow, "filters": [{"name": "gaussian blur", "config": {"horizRadius": 60, "vertRadius": 60}}]},
            {"type": "svg", "name": "هلال", "svg": moon}]},
        {"type": "svg", "name": "كثبان", "svg": dunes, "filters": [{"name": "noise", "config": {"level": 30, "opacity": 25, "grayscale": True}}]},
        {"type": "brush", "name": "نخيل وريح", "strokes": strokes},
        {"type": "svg", "name": "عنوان", "svg": title},
    ],
    "python": "post.py",
    "output": {"png": "night_desert.png", "kra": "night_desert.kra"},
}
(here / "scene.json").write_text(json.dumps(scene, ensure_ascii=False, indent=1), encoding="utf-8")
print("strokes", len(strokes))
