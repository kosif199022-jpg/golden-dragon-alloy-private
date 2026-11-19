"""Standalone harness: runs a JSON recipe (scene/steps/render) with bpylib.draw + bpylib.video
inside Blender, without needing bl.py/runner.py.
usage: blender -b --factory-startup --python harness.py -- recipe.json [out_override_dir]
"""
import json, os, sys, time, traceback
HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.normpath(os.path.join(HERE, "..", "..", "scripts", "bpylib"))
sys.path.insert(0, LIB)
import bpy  # noqa
import draw, video  # noqa

OPS = {}
OPS.update(draw.OPS)
OPS.update(video.OPS)

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
recipe = json.load(open(argv[0], encoding="utf-8"))
state = {"objects": {}, "strips": {}, "recipe_dir": os.path.dirname(os.path.abspath(argv[0]))}
results = []
ok = True
for i, st in enumerate(recipe.get("steps", [])):
    st = dict(st)
    op = st.pop("op")
    t = time.time()
    try:
        r = OPS[op](state, **st)
        results.append({"step": i, "op": op, "ok": True, "result": r, "sec": round(time.time() - t, 2)})
        print("[OK]", op, json.dumps(r, ensure_ascii=False, default=str)[:300])
    except Exception as e:
        ok = False
        traceback.print_exc()
        results.append({"step": i, "op": op, "ok": False, "error": str(e)})
        print("[FAIL]", op, e)
rend = recipe.get("render")
if rend and ok:
    try:
        if "draw_still" == rend.get("kind"):
            r = draw.gp_render(state, rend["filepath"], animation=False, frame=rend.get("frame"))
        elif rend.get("kind") == "animation":
            r = draw.gp_render(state, rend["filepath"], animation=True)
        else:
            r = video.render_mp4(state, **{k: v for k, v in rend.items() if k != "kind"})
        print("[OK] render", r)
    except Exception as e:
        ok = False
        traceback.print_exc()
        print("[FAIL] render", e)
if state.get("warnings"):
    print("WARNINGS", state["warnings"])
print("SUMMARY", json.dumps({"ok": ok, "steps": [(r["op"], r["ok"]) for r in results]}))
sys.exit(0 if ok else 1)
