#!/usr/bin/env python3
"""Build a lyric film page from a spec (v1990.5, the couple/singer films of 9-10 Nov 2026).

    python mk.py JOB_DIR spec.json

spec.json:
{"dur": 30.6, "title": "خليني في حضنك", "credit": 27.4,
 "lyrics_pos": "low",                       # "low" (under faces, y 1200/1325, default) or "top" (y 300/420)
 "shots": [[0, 3.95, "a1"], [3.95, 7.8, "a2"], [7.8, null, "a3"]],      # image JOB/film/img/<name>.jpg; null = to the end
 "seq":   {"a2": 142},                      # optional: shot drawn from JOB/film/s/<name>/f0001.jpg.. (animated clip frames)
 "ly": [[0.34, 3.8, "white line", "red line or empty"]]}

Writes JOB/film/index.html and copies the fonts. Zero overlay effects (no dust/hearts/shade/vignette/glow):
check it with `dragon.py fx check effects.json --html JOB/film/index.html` before rendering.
"""
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def build(job, spec):
    job = Path(job)
    film = job / "film"
    film.mkdir(parents=True, exist_ok=True)
    fonts = film / "fonts"
    fonts.mkdir(exist_ok=True)
    for f in (HERE / "fonts").glob("*.ttf"):
        if not (fonts / f.name).exists():
            shutil.copy2(f, fonts / f.name)
    s = (HERE / "template.html").read_text(encoding="utf-8")
    seq = spec.get("seq", {})
    rows = []
    for k, sh in enumerate(spec["shots"]):
        a, b, name = sh[0], sh[1], sh[2]
        cam = sh[3] if len(sh) > 3 else ("z0:1.0,z1:1.06,x0:0,x1:0,y0:0,y1:-8" if k % 2 == 0
                                          else "z0:1.06,z1:1.0,x0:6,x1:-6,y0:0,y1:0")
        end = "DUR" if b is None else b
        if name in seq:
            cam = cam.replace("1.06", "1.03")
            rows.append(f" [{a},{end},'seq','s/{name}',{{n:{int(seq[name])},{cam}}}],")
        else:
            sign = "" if k % 2 == 0 else "-"
            rows.append(f" [{a},{end},'img','img/{name}.jpg',{{{cam},par:[{sign}.012,.006]}}],")
    i = s.index("const SH=["); j = s.index("];", i) + 2
    s = s[:i] + "const SH=[\n" + "\n".join(rows) + "\n];" + s[j:]
    i = s.index("const LY=["); j = s.index("];", i) + 2
    s = s[:i] + "const LY=" + json.dumps(spec["ly"], ensure_ascii=False) + ";" + s[j:]
    s, n = re.subn(r"DUR=[\d.]+", f"DUR={float(spec['dur'])}", s, count=1); assert n
    s, n = re.subn(r"g\.fillText\('[^']*',540,1500\)", f"g.fillText('{spec['title']}',540,1500)", s, count=1); assert n
    s, n = re.subn(r"credit\(t,[\d.]+\);", f"credit(t,{float(spec['credit'])});", s, count=1); assert n
    if spec.get("lyrics_pos") == "top":
        s = s.replace("draw(l1,l2?1200:1260,l2?96:104,'#ffffff',0);if(l2)draw(l2,1325,84,'#d0102c',.35)}",
                      "draw(l1,300,92,'#ffffff',0);if(l2)draw(l2,420,76,'#d0102c',.35)}")
    s = s.replace("g.filter='saturate(1.15) contrast(1.05) blur(.4px)'", "g.filter='none'")
    s = s.replace("const PRG=(()=>{", "const PRG=!G?null:(()=>{")  # WebGL can be missing after a page reload
    (film / "index.html").write_text(s, encoding="utf-8")
    return film / "index.html"


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    print("wrote", build(sys.argv[1], json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))))
