"""blender-pro runner - executed INSIDE Blender:

    blender -b [file.blend] --factory-startup --python runner.py -- --mode run --recipe r.json --out DIR [--preview]

Modes: run | exec | info | ops | inspect | thumb.
Protocol (parsed by bl.py): progress lines '[bpylib:level] ...', outputs 'BLPRO_OUTPUT {json}',
final line 'BLPRO_RESULT {json}'. Exit code 0 on success, 1 on failure.
"""
import argparse
import inspect as pyinspect
import json
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import bpy  # noqa: E402

import bpylib  # noqa: E402
from bpylib import util  # noqa: E402

RENDER_KEYS = {"denoise", "motion_blur", "shutter", "transparent", "device", "bounces", "clamp_indirect",
               "adaptive_threshold", "caustics", "raytracing", "volumetrics"}


def emit_result(result):
    print("BLPRO_RESULT " + json.dumps(result, ensure_ascii=False, default=str), flush=True)


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser(prog="runner.py")
    p.add_argument("--mode", required=True, choices=["run", "exec", "info", "ops", "inspect", "thumb"])
    p.add_argument("--recipe")
    p.add_argument("--script")
    p.add_argument("--script-args", default="[]")
    p.add_argument("--out")
    p.add_argument("--preview", action="store_true")
    p.add_argument("--frame", type=int)
    p.add_argument("--engine")
    return p.parse_args(argv)


def jsonable(v):
    try:
        json.dumps(v)
        return v
    except TypeError:
        if isinstance(v, bpy.types.ID):
            return v.name
        return str(v)


# --------------------------------------------------------------------------- run
def preview_name(path):
    stem, ext = os.path.splitext(path)
    return f"{stem}_preview{ext}"


def mode_run(args):
    recipe_path = os.path.abspath(args.recipe)
    with open(recipe_path, encoding="utf-8-sig") as f:
        recipe = json.load(f)
    recipe_dir = os.path.dirname(recipe_path)
    out_dir = os.path.abspath(args.out or recipe.get("out_dir") or os.path.join(
        os.getcwd(), "blender_out", os.path.splitext(os.path.basename(recipe_path))[0]))
    os.makedirs(out_dir, exist_ok=True)
    state = util.new_state(out_dir=out_dir, recipe_dir=recipe_dir, preview=args.preview)
    ops, by_mod, failed = bpylib.discover_ops()
    result = {"ok": False, "outputs": [], "out_dir": out_dir, "preview": args.preview,
              "modules_failed": failed, "steps": []}
    t0 = time.time()
    stage = "setup"
    try:
        if not recipe.get("keep_default_scene"):
            bpylib.run_op(state, "clear_scene")
        sc_cfg = dict(recipe.get("scene") or {})
        rs_cfg = {k: sc_cfg.pop(k) for k in list(sc_cfg) if k in RENDER_KEYS}
        if "engine" not in sc_cfg:
            sc_cfg["engine"] = "CYCLES"
        bpylib.run_op(state, "scene_setup", **sc_cfg)
        bpylib.run_op(state, "render_settings", **rs_cfg)
        stage = "steps"
        for i, step in enumerate(recipe.get("steps") or []):
            step = dict(step)
            if step.pop("enabled", True) is False:
                continue
            for k in ("comment", "_comment", "note"):
                step.pop(k, None)
            name = step.pop("op", None)
            st = time.time()
            try:
                if not name:
                    raise ValueError("step has no 'op'")
                if step.pop("preview_skip", False) and args.preview:
                    util.log(f"step {i} ({name}) skipped in preview")
                    continue
                ret = bpylib.run_op(state, name, **step)
            except Exception as e:
                tb = traceback.format_exc()
                sig = ""
                try:
                    sig = str(pyinspect.signature(bpylib.get_op(name)))
                except Exception:
                    pass
                result["error"] = {"stage": "step", "step": i, "op": name, "message": f"{type(e).__name__}: {e}",
                                   "params": jsonable(step), "signature": sig, "traceback": tb}
                print(f"[bpylib:error] step {i} op '{name}' failed: {type(e).__name__}: {e}\n{tb}", flush=True)
                if recipe.get("continue_on_error"):
                    result.setdefault("errors", []).append(result.pop("error"))
                    continue
                raise _StepFailed()
            result["steps"].append({"i": i, "op": name, "s": round(time.time() - st, 2),
                                    "ret": jsonable(ret)})
            util.log(f"step {i} {name} ok ({time.time() - st:.2f}s)")
        stage = "post"
        if recipe.get("post"):
            bpylib.run_op(state, "compositor", **recipe["post"])
        if bpy.context.scene.camera is None:
            util.warn("recipe made no camera - auto framing")
            bpylib.run_op(state, "frame_objects")
        if recipe.get("save_blend"):
            p = util.out_path(state, recipe["save_blend"])
            bpy.ops.wm.save_as_mainfile(filepath=p, check_existing=False, compress=True)
            state["outputs"].append({"path": p, "type": "blend"})
        if args.preview:
            stage = "preview"
            _apply_preview(state, recipe)
        stage = "render"
        renders = recipe.get("render")
        if renders:
            for r in (renders if isinstance(renders, list) else [renders]):
                r = dict(r)
                kind = r.pop("kind", None)
                if kind in ("draw_still", "animation", "draw_animation") and "filepath" in r:
                    # helper convention for drawing-only recipes -> draw.gp_render
                    fp = preview_name(r["filepath"]) if args.preview else r["filepath"]
                    if kind != "draw_still":
                        bpy.context.scene.frame_step = 1
                    n_before = len(state["outputs"])
                    bpylib.run_op(state, "gp_render", filepath=util.out_path(state, fp), animation=(kind != "draw_still"),
                                  frame=r.get("frame"), fmt=r.get("fmt"), crf=r.get("crf", "HIGH"))
                    if len(state["outputs"]) == n_before:
                        state["outputs"].append({"path": os.path.abspath(fp),
                                                 "type": "image" if kind == "draw_still" else "video"})
                    continue
                if "filepath" in r or r.get("type") == "vse":  # VSE edit -> video.render_mp4 (keeps audio)
                    r.pop("type", None)
                    if args.preview and r.get("filepath"):
                        r["filepath"] = preview_name(r["filepath"])
                    if r.get("filepath"):
                        r["filepath"] = util.out_path(state, r["filepath"])
                    bpy.context.scene.frame_step = 1  # sparse frames would speed up an edit
                    n_before = len(state["outputs"])
                    ret = bpylib.run_op(state, "render_mp4", **r)
                    if len(state["outputs"]) == n_before:
                        p = ret if isinstance(ret, str) else (ret or {}).get("path") if isinstance(ret, dict) else None
                        p = p or r.get("filepath")
                        state["outputs"].append({"path": os.path.abspath(p), "type": "image" if r.get("still_frame") is not None else "video"})
                    continue
                rtype = r.pop("type", "still")
                out = r.pop("out", "render.png" if rtype == "still" else "anim.mp4")
                fmt = r.pop("format", None)
                if fmt and not os.path.splitext(out)[1]:
                    out += {"PNG": ".png", "JPEG": ".jpg", "JPG": ".jpg", "MP4": ".mp4", "MOV": ".mov",
                            "WEBM": ".webm", "EXR": ".exr"}.get(fmt.upper(), "")
                if args.preview:
                    out = preview_name(out)
                bpylib.run_op(state, "render", type=rtype, out=out, format=fmt, **r)
        result["ok"] = True
    except _StepFailed:
        pass
    except Exception as e:
        tb = traceback.format_exc()
        result["error"] = {"stage": stage, "message": f"{type(e).__name__}: {e}", "traceback": tb}
        print(f"[bpylib:error] {stage} failed: {e}\n{tb}", flush=True)
    result["outputs"] = state["outputs"]
    result["seconds"] = round(time.time() - t0, 1)
    if state.get("gpu"):
        result["gpu"] = state["gpu"]
    if result.get("errors"):
        result["ok"] = False if not recipe.get("continue_on_error") else result["ok"]
    return result


class _StepFailed(Exception):
    pass


def _apply_preview(state, recipe):
    from bpylib import render
    info = render.apply_preview(state, **(recipe.get("preview") or {}))
    util.log(f"preview mode: {info}")


# --------------------------------------------------------------------------- exec
def mode_exec(args):
    import runpy
    script = os.path.abspath(args.script)
    out_dir = os.path.abspath(args.out or os.path.join(os.getcwd(), "blender_out",
                                                        os.path.splitext(os.path.basename(script))[0]))
    os.makedirs(out_dir, exist_ok=True)
    state = util.new_state(out_dir=out_dir, recipe_dir=os.path.dirname(script), preview=args.preview)
    bpylib.discover_ops()
    sys.argv = [script] + json.loads(args.script_args)
    g = {"STATE": state, "OUT_DIR": out_dir, "PREVIEW": args.preview, "bpylib": bpylib}
    result = {"ok": False, "outputs": [], "out_dir": out_dir}
    try:
        runpy.run_path(script, init_globals=g, run_name="__main__")
        result["ok"] = True
    except SystemExit as e:
        result["ok"] = (e.code in (0, None))
    except Exception as e:
        result["error"] = {"stage": "exec", "message": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()}
        print(f"[bpylib:error] script failed: {e}\n{traceback.format_exc()}", flush=True)
    result["outputs"] = state["outputs"]
    return result


# --------------------------------------------------------------------------- info / ops
def op_catalog():
    ops, by_mod, failed = bpylib.discover_ops()
    cat = {}
    for mod, table in by_mod.items():
        cat[mod] = {}
        for name, fn in table.items():
            try:
                sig = str(pyinspect.signature(fn)).replace("(state, ", "(").replace("(state)", "()")
            except (TypeError, ValueError):
                sig = "(...)"
            cat[mod][name] = {"signature": sig, "doc": pyinspect.getdoc(fn) or ""}
    return cat, failed


def mode_info(args):
    from bpylib import render, text3d
    sc = bpy.context.scene
    engines = []
    for e in ("CYCLES", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "BLENDER_WORKBENCH"):
        try:
            sc.render.engine = e
            engines.append(e)
        except TypeError:
            pass
    gpu = render.gpu_setup()
    try:
        shaped = text3d.shape("مرحبا")
        shaping = "ok" if shaped != "مرحبا" and shaped != "مرحبا"[::-1] else "fallback"
    except Exception as e:
        shaping = f"error: {e}"
    cat, failed = op_catalog()
    return {"ok": True, "blender": bpy.app.version_string, "python": sys.version.split()[0],
            "engines": engines, "gpu": gpu, "arabic_shaping": shaping,
            "ffmpeg": render.ffmpeg_exe(), "modules": sorted(cat), "modules_failed": failed,
            "ops": {m: {n: (v["doc"].splitlines() or [""])[0] for n, v in t.items()} for m, t in cat.items()}}


def mode_ops(args):
    cat, failed = op_catalog()
    return {"ok": True, "catalog": cat, "modules_failed": failed}


# --------------------------------------------------------------------------- inspect / thumb
def mode_inspect(args):
    import math
    sc = bpy.context.scene

    def fcount(idd):
        try:
            return len(util.fcurves(idd))
        except Exception:
            return 0
    objs = []
    for o in sc.objects:
        d = {"name": o.name, "type": o.type, "parent": o.parent.name if o.parent else None,
             "location": [round(v, 4) for v in o.location],
             "rotation_deg": [round(math.degrees(v), 2) for v in o.rotation_euler],
             "scale": [round(v, 4) for v in o.scale], "dimensions": [round(v, 4) for v in o.dimensions],
             "hide_render": o.hide_render, "animated_channels": fcount(o),
             "modifiers": [f"{m.name}:{m.type}" for m in o.modifiers],
             "constraints": [c.type for c in o.constraints],
             "materials": [s.material.name for s in o.material_slots if s.material]}
        if o.type == "CAMERA":
            d["lens"] = o.data.lens
            d["dof"] = o.data.dof.use_dof
        if o.type == "LIGHT":
            d["light"] = {"type": o.data.type, "energy": o.data.energy, "color": list(o.data.color)}
        if o.type == "FONT":
            d["text"] = o.data.body
        objs.append(d)
    mats = [{"name": m.name, "users": m.users,
             "nodes": [n.bl_idname for n in m.node_tree.nodes] if m.node_tree else []} for m in bpy.data.materials]
    return {"ok": True, "file": bpy.data.filepath, "blender": bpy.app.version_string,
            "scene": {"name": sc.name, "engine": sc.render.engine,
                      "resolution": [sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage],
                      "fps": sc.render.fps / sc.render.fps_base, "frame_start": sc.frame_start, "frame_end": sc.frame_end,
                      "camera": sc.camera.name if sc.camera else None, "world": sc.world.name if sc.world else None,
                      "view_transform": sc.view_settings.view_transform, "look": sc.view_settings.look},
            "objects": objs, "materials": mats,
            "collections": [c.name for c in bpy.data.collections],
            "images": [i.filepath for i in bpy.data.images if i.filepath]}


def mode_thumb(args):
    from bpylib import render
    sc = bpy.context.scene
    state = util.new_state(out_dir=os.path.dirname(os.path.abspath(args.out or "thumb.png")))
    if args.engine:
        render.render_settings(state, engine=args.engine)
    if sc.render.engine == "CYCLES":
        sc.cycles.samples = 16
        sc.cycles.use_denoising = True
    elif sc.render.engine.startswith("BLENDER_EEVEE"):
        sc.eevee.taa_render_samples = 8
    longest = max(sc.render.resolution_x, sc.render.resolution_y)
    sc.render.resolution_percentage = max(5, min(100, int(800 * 100 / longest)))
    if args.frame is not None:
        sc.frame_set(args.frame)
    out = os.path.abspath(args.out or (os.path.splitext(bpy.data.filepath)[0] + "_thumb.png"))
    render.render_still(state, out=out)
    return {"ok": True, "outputs": state["outputs"]}


def main():
    args = parse_args()
    try:
        result = {"run": mode_run, "exec": mode_exec, "info": mode_info, "ops": mode_ops,
                  "inspect": mode_inspect, "thumb": mode_thumb}[args.mode](args)
    except Exception as e:
        result = {"ok": False, "error": {"stage": args.mode, "message": f"{type(e).__name__}: {e}",
                                         "traceback": traceback.format_exc()}}
    emit_result(result)
    sys.stdout.flush()
    os._exit(0 if result.get("ok") else 1)  # skip Blender's slow teardown


if __name__ == "__main__":
    main()
