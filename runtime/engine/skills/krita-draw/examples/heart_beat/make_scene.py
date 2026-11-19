"""Animation template: a beating heart with orbiting brush sparkles, 16 frames @ 12 fps.
Each frame is a GROUP (svg heart + brush sparkles) -> flattened into one keyframe.
Static layers below/above the animation stay ordinary layers.

    python -X utf8 make_scene.py [OUT_DIR]   -> OUT_DIR/heart_scene.json, then:
    python -X utf8 <skill>/scripts/krita_draw.py render OUT_DIR/heart_scene.json
"""
import json
import math
import sys
from pathlib import Path

out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
W, H, N = 720, 720, 16
CX, CY = 360, 350


def heart_points(s):
    pts = []
    for i in range(140):
        t = 2 * math.pi * i / 140
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((CX + x * 11 * s, CY - y * 11 * s))
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)


frames = []
for f in range(N):
    ph = 2 * math.pi * f / N
    beat = 1 + 0.14 * max(0.0, math.sin(2 * ph)) ** 3  # double beat per loop
    heart_svg = (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {W} {H}'>"
                 "<defs><radialGradient id='h' cx='0.38' cy='0.32' r='0.75'>"
                 "<stop offset='0' stop-color='#ff9eb1'/><stop offset='1' stop-color='#c9184a'/></radialGradient></defs>"
                 f"<polygon points='{heart_points(beat)}' fill='url(#h)' stroke='#590d22' stroke-width='6'/></svg>")
    sparks = []
    for k in range(6):
        a = ph + k * math.pi / 3
        r0, r1 = 215 + 18 * math.sin(ph * 2 + k), 250 + 18 * math.sin(ph * 2 + k)
        sparks.append({"points": [[CX + r0 * math.cos(a), CY + r0 * math.sin(a), 1.0],
                                  [CX + r1 * math.cos(a), CY + r1 * math.sin(a), 0.15]],
                       "tip": "ink", "size": 10, "color": "#ffd166"})
    sparks.append({"points": [[CX + 140 * beat * math.cos(t / 24 * 2 * math.pi), CY - 10 + 130 * beat * math.sin(t / 24 * 2 * math.pi)]
                              for t in range(25)], "tip": "soft", "size": 70, "color": "#ff4d6d", "opacity": 0.35 * (beat - 1) / 0.14})
    frames.append({"type": "group", "layers": [
        {"type": "brush", "name": "glow+sparks", "strokes": sparks},
        {"type": "svg", "name": "heart", "svg": heart_svg}]})

scene = {
    "canvas": {"width": W, "height": H, "background": "#10002b"},
    "layers": [
        {"type": "svg", "name": "خلفية", "svg": f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {W} {H}'>"
         "<defs><radialGradient id='b' cx='0.5' cy='0.48' r='0.7'><stop offset='0' stop-color='#3a0ca3'/>"
         f"<stop offset='1' stop-color='#10002b'/></radialGradient></defs><rect width='{W}' height='{H}' fill='url(#b)'/></svg>"},
        {"type": "animation", "name": "قلب بينبض", "fps": 12, "frames": frames},
        {"type": "svg", "name": "عنوان", "svg": f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {W} {H}'>"
         "<text x='360' y='665' font-size='54' font-family='Segoe UI' font-weight='bold' fill='#ffd6e0' "
         "direction='rtl' text-anchor='middle'>نبض القلب</text></svg>"},
    ],
    "output": {"kra": "heart_beat.kra", "png": "heart_beat.png", "mp4": "heart_beat.mp4", "gif": "heart_beat.gif"},
}
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "heart_scene.json").write_text(json.dumps(scene, ensure_ascii=False), encoding="utf-8")
print(out_dir / "heart_scene.json")
