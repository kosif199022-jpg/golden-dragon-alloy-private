"""bpylib - headless Blender toolkit for the blender-pro skill.

Every module in this package may define ``OPS = {"op_name": func}`` where each
func has the signature ``func(state, **params)``. ``discover_ops()`` imports all
modules (tolerating broken/missing ones) and merges their OPS tables.

Usage from a raw bpy script (bl.py exec):

    import bpylib
    state = bpylib.new_state()
    bpylib.run_steps(state, [{"op": "add_primitive", "type": "cube", "name": "Box"}])
"""
import importlib
import os
import pkgutil
import traceback

from .util import new_state, log, warn  # noqa: F401  (re-exported)

_REGISTRY = None   # op_name -> func
_BY_MODULE = None  # module -> {op_name: func}
_FAILED = {}       # module -> error string


def discover_ops(force=False):
    """Import every bpylib module and collect OPS. Returns (ops, by_module, failed)."""
    global _REGISTRY, _BY_MODULE
    if _REGISTRY is not None and not force:
        return _REGISTRY, _BY_MODULE, _FAILED
    ops, by_mod = {}, {}
    _FAILED.clear()
    pkg_dir = os.path.dirname(__file__)
    for info in sorted(pkgutil.iter_modules([pkg_dir]), key=lambda m: m.name):
        name = info.name
        if name.startswith("_") or name == "util":
            continue
        try:
            mod = importlib.import_module(f"{__name__}.{name}")
        except Exception as e:  # draw/video may be missing deps or mid-development
            _FAILED[name] = f"{type(e).__name__}: {e}"
            warn(f"bpylib module '{name}' failed to import: {e}\n{traceback.format_exc(limit=3)}")
            continue
        table = getattr(mod, "OPS", None)
        if not isinstance(table, dict):
            continue
        by_mod[name] = dict(table)
        for op_name, fn in table.items():
            ops[f"{name}.{op_name}"] = fn  # qualified name always works
    # plain names; clashes (e.g. fade/transform in animate|objects and video) get a context dispatcher
    owners = {}
    for mod_name, table in by_mod.items():
        for op_name, fn in table.items():
            owners.setdefault(op_name, []).append((mod_name, fn))
    for op_name, cands in owners.items():
        ops[op_name] = cands[0][1] if len(cands) == 1 else _dispatcher(op_name, cands)
    _REGISTRY, _BY_MODULE = ops, by_mod
    return ops, by_mod, _FAILED


def _dispatcher(op_name, cands):
    """Route a clashing op name: target that is a VSE strip -> 'video' module, otherwise the
    first non-video module (3D objects)."""
    def dispatch(state, **params):
        strips = (state or {}).get("strips") or {}
        ref = params.get("target")
        is_strip = isinstance(ref, str) and ref in strips
        for mod, fn in cands:
            if (mod == "video") == is_strip:
                return fn(state, **params)
        return cands[0][1](state, **params)
    mods = ", ".join(m for m, _ in cands)
    dispatch.__name__ = op_name
    dispatch.__doc__ = (f"[shared name: {mods}] Routed to video.{op_name} when target is a VSE strip, otherwise to "
                        f"the 3D version. Use '<module>.{op_name}' to force one.\n\n" +
                        "\n\n".join(f"{m}.{op_name}: {(fn.__doc__ or '').strip()}" for m, fn in cands))
    return dispatch


def get_op(name):
    ops, _, failed = discover_ops()
    if name in ops:
        return ops[name]
    import difflib
    close = difflib.get_close_matches(name, [k for k in ops if "." not in k], n=5)
    hint = f" Did you mean: {close}?" if close else ""
    if failed:
        hint += f" (modules that failed to import: {list(failed)})"
    raise KeyError(f"unknown op '{name}'.{hint}")


def run_op(state, op_name, /, **params):
    return get_op(op_name)(state, **params)


def run_steps(state, steps):
    """Run a list of recipe steps; raises on the first failure."""
    results = []
    for i, step in enumerate(steps):
        step = dict(step)
        if step.pop("enabled", True) is False:
            continue
        step.pop("comment", None)
        step.pop("_comment", None)
        name = step.pop("op")
        results.append(run_op(state, name, **step))
    return results
