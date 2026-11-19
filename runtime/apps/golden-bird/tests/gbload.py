"""Load a Golden module from forge\\modules (the source of truth) without changing sys.path order.

The older tests import `golden_tools` from app\\ (conftest puts app\\ first on sys.path) and rely on app\\golden for its
data. Putting forge\\modules on sys.path would shadow that copy, so the tests of the newer modules (golden_hub,
golden_brain, golden_xray, golden_motion, golden_apps, golden_accounts, golden_gate) load them through this helper.

    from gbload import load
    brain = load("golden_brain")
"""
import importlib.util
import sys
from pathlib import Path

MODULES = Path(__file__).resolve().parent.parent / "forge" / "modules"


def load(name, fresh=False):
    """The module forge\\modules\\<name>.py, registered in sys.modules under its plain name (so that a module importing
    another one by name, e.g. golden_hub -> golden_brain, gets the same forge copy). fresh=True re-executes it."""
    path = MODULES / f"{name}.py"
    old = sys.modules.get(name)
    if old is not None and not fresh and Path(getattr(old, "__file__", "") or ".").resolve() == path.resolve():
        return old
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        if old is not None:
            sys.modules[name] = old
        else:
            sys.modules.pop(name, None)
        raise
    return mod
