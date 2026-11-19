"""Dragon Character Memory & Auto Rotoscope: command line.

  python -X utf8 charmem_cli.py doctor
  python -X utf8 charmem_cli.py demo OUT                       # whole experiment on the original test character (≈12 min)
  python -X utf8 charmem_cli.py make-reference OUT/01_reference
  python -X utf8 charmem_cli.py extract VIDEO WORK              # frames + their real timing
  python -X utf8 charmem_cli.py analyze WORK [--gt gt.json]     # parts, joints, face per frame -> WORK/track.json
  python -X utf8 charmem_cli.py redraw WORK                     # SVG per frame + redraw.mp4 + metrics
  python -X utf8 charmem_cli.py memory WORK [--out FILE] [--name NAME]
  python -X utf8 charmem_cli.py animate MEMORY "<أمر بالعربي أو الإنجليزي>" OUT [--head-px 210]
  python -X utf8 charmem_cli.py edit MEMORY --expression laugh --set mouth_w=0.45 --out NEW.json
  python -X utf8 charmem_cli.py export MEMORY OUT_DIR           # rest-pose SVG + a bones/slots/displays JSON
Only one flat-coloured character, seen from the front, closed by one dark outline colour, on a static background.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from charmem import VERSION  # noqa: E402


def doctor():
    ok = True
    for mod in ("numpy", "cv2", "PIL", "scipy", "skimage", "cairosvg"):
        try:
            __import__(mod)
            print(f"ok   python: {mod}")
        except Exception as e:  # noqa: BLE001
            ok = False
            print(f"MISS python: {mod} ({e}) -> pip install {'opencv-python' if mod == 'cv2' else 'pillow' if mod == 'PIL' else 'scikit-image' if mod == 'skimage' else mod}")
    for exe in ("ffmpeg", "ffprobe"):
        p = shutil.which(exe)
        ok &= bool(p)
        print(("ok   " if p else "MISS ") + f"{exe}: {p}")
    print(f"charmem {VERSION}: " + ("DOCTOR OK" if ok else "missing pieces above"))
    return ok


def demo(out):
    from charmem import analyze, animate, evaluate, extract, memory, redraw, reference
    out = Path(out)
    print("1/7 reference video of the original test character")
    reference.make(out / "01_reference")
    print("2/7 frames and timing")
    extract.extract(out / "01_reference" / "reference.mp4", out / "02_work")
    print("3/7 analysis (parts, joints, face, occlusion)")
    analyze.analyze(out / "02_work")
    json.dump(evaluate.report(out / "02_work", out / "01_reference" / "gt.json"), open(out / "02_work" / "tracking_vs_truth.json", "w"), indent=1)
    print("4/7 vector redraw and its error")
    redraw.redraw(out / "02_work")
    print("5/7 character memory")
    memory.build(out / "02_work")
    print("6/7 new scene from memory alone (the source video is hidden meanwhile)")
    shutil.copy(out / "character_memory.json", (out / "04_new_scene").mkdir(parents=True, exist_ok=True) or out / "04_new_scene" / "character_memory.copy.json")
    vid = out / "01_reference" / "reference.mp4"
    hid = vid.with_suffix(".mp4.hidden")
    vid.rename(hid)
    try:
        animate.render(out / "04_new_scene" / "character_memory.copy.json", "خلّي الشخصية تسلّم، وبعدين تمشي للناحية التانية، وبعدين تضحك، وبعدين تقعد على الدكة",
                       out / "04_new_scene")
    finally:
        hid.rename(vid)
    print("7/7 the new scene analysed from scratch (is it the same character?)")
    extract.extract(out / "04_new_scene" / "new_scene.mp4", out / "05_reanalysis")
    analyze.analyze(out / "05_reanalysis")
    memory.build(out / "05_reanalysis", out / "05_reanalysis" / "character_memory_from_new_scene.json", name="(re-learned from the new scene)")
    print("done ->", out)


def edit(mem_path, expression, sets, out):
    from charmem import memory
    mem = memory.load(mem_path)
    e = next((x for x in mem["face"]["expressions"] if x["name"] == expression), None)
    if e is None:
        e = {"name": expression, "observed": False, "generated": True, "params": dict(next(x for x in mem["face"]["expressions"] if x["name"] == "neutral")["params"]),
             "derived_from": "neutral, edited by hand", "confidence": 0.3}
        mem["face"]["expressions"].append(e)
    for kv in sets:
        k, v = kv.split("=", 1)
        e["params"][k] = float(v) if v.replace(".", "", 1).replace("-", "", 1).isdigit() else v
    e.setdefault("edits", []).append({"set": sets})
    Path(out).write_text(json.dumps(mem, ensure_ascii=False, indent=1), encoding="utf-8")
    print("->", out)


def export(mem_path, out_dir, head_px=270):
    """The remembered character as a vector drawing (rest pose) and as a skeleton file: bones, slots (draw order) and
    displays (shapes), the cut-out data model DragonBones popularised (format re-written here, no code copied)."""
    from charmem import animate, memory
    mem = memory.load(mem_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ch = animate.Character(mem, head_px)
    idle = next(m for m in mem["motions"] if m["name"] == "idle")
    c = {k: idle["channels"][k][0] for k in memory.POSE_KEYS}
    c["px"], c["py"] = head_px * 2.0, head_px * 2.0
    layers, J = ch.layers(c, "neutral")
    W, H = int(head_px * 4), int(head_px * 3.6)
    paths = []
    for kind, pts, role, extra in layers:
        col = mem["identity"]["outline"]["hex"] if role == "ink" else next((p["hex"] for p in mem["identity"]["palette"] if p["role"] == role), "#FF00FF")
        ink = mem["identity"]["outline"]["hex"]
        if kind == "limb":
            from charmem import rig
            for a, b in ((pts[0], pts[1]), (pts[1], pts[2])):
                for r, fill in ((extra + ch.ow, ink), (extra, col)):
                    poly = rig.capsule(tuple(a), tuple(b), r)
                    paths.append(f'<path fill="{fill}" d="M{" L".join(f"{x:.1f} {y:.1f}" for x, y in poly)} Z"/>')
        elif kind in ("poly", "fill"):
            stroke = f' stroke="{ink}" stroke-width="{ch.ow:.1f}" stroke-linejoin="round"' if kind == "poly" else ""
            paths.append(f'<path fill="{col}"{stroke} d="M{" L".join(f"{x:.1f} {y:.1f}" for x, y in pts)} Z"/>')
        else:
            paths.append(f'<path fill="none" stroke="{ink}" stroke-width="{ch.ow * extra:.1f}" stroke-linecap="round" d="M{" L".join(f"{x:.1f} {y:.1f}" for x, y in pts)}"/>')
    (out / "character_rest.svg").write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">{"".join(paths)}</svg>', encoding="utf-8")
    skel = {"format": "dragon.cutout-skeleton.v1", "inspired_by": "DragonBones armature/bone/slot/display model (MIT); written independently",
            "name": mem["character"]["name"], "units": "head units",
            "bones": [{"name": b["name"], "parent": b["parent"], "length": b["length_hu"], "confidence": b["confidence"]} for b in mem["skeleton"]["bones"]],
            "attach": mem["skeleton"]["attach_hu"],
            "slots": [{"name": n, "z": i} for i, n in enumerate(mem["layers"]["order"])],
            "displays": [{"slot": p["name"], "bone": p["bone"], "color": p["color_role"], "shape": p["shape"]} for p in mem["parts"]],
            "animations": [{"name": m["name"], "observed": m["observed"], "fps": mem["character"]["source"]["fps"],
                            "channels": m.get("channels"), "pose_delta": m.get("pose_delta")} for m in mem["motions"]],
            "expressions": mem["face"]["expressions"]}
    (out / "character_skeleton.json").write_text(json.dumps(skel, ensure_ascii=False, indent=1), encoding="utf-8")
    print("->", out / "character_rest.svg", out / "character_skeleton.json")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor")
    s = sub.add_parser("demo"); s.add_argument("out")
    s = sub.add_parser("make-reference"); s.add_argument("out")
    s = sub.add_parser("extract"); s.add_argument("video"); s.add_argument("work")
    s = sub.add_parser("analyze"); s.add_argument("work"); s.add_argument("--gt")
    s = sub.add_parser("redraw"); s.add_argument("work")
    s = sub.add_parser("memory"); s.add_argument("work"); s.add_argument("--out"); s.add_argument("--name", default="character")
    s = sub.add_parser("animate"); s.add_argument("memory"); s.add_argument("command"); s.add_argument("out"); s.add_argument("--head-px", type=int, default=210)
    s = sub.add_parser("edit"); s.add_argument("memory"); s.add_argument("--expression", required=True); s.add_argument("--set", action="append", default=[]); s.add_argument("--out", required=True)
    s = sub.add_parser("export"); s.add_argument("memory"); s.add_argument("out")
    a = ap.parse_args()
    if a.cmd == "doctor":
        raise SystemExit(0 if doctor() else 1)
    if a.cmd == "demo":
        demo(a.out)
    elif a.cmd == "make-reference":
        from charmem import reference
        print(reference.make(a.out))
    elif a.cmd == "extract":
        from charmem import extract
        t = extract.extract(a.video, a.work)
        print(f"{len(t['frames'])} frames at {t['fps']} fps -> {a.work}")
    elif a.cmd == "analyze":
        from charmem import analyze, evaluate
        analyze.analyze(a.work)
        if a.gt:
            r = evaluate.report(a.work, a.gt)
            json.dump(r, open(Path(a.work) / "tracking_vs_truth.json", "w"), indent=1)
            print("joints median error", r["all_joints_median_px"], "px")
    elif a.cmd == "redraw":
        from charmem import redraw
        print(json.dumps(redraw.redraw(a.work)["summary"], indent=1))
    elif a.cmd == "memory":
        from charmem import memory
        m = memory.build(a.work, a.out, a.name)
        print(f"memory: {len(m['parts'])} parts, {len(m['face']['expressions'])} expressions, {len(m['motions'])} motions")
    elif a.cmd == "animate":
        from charmem import animate
        print(json.dumps(animate.render(a.memory, a.command, a.out, head_px=a.head_px), ensure_ascii=False, indent=1))
    elif a.cmd == "edit":
        edit(a.memory, a.expression, a.set, a.out)
    elif a.cmd == "export":
        export(a.memory, a.out)


if __name__ == "__main__":
    main()
