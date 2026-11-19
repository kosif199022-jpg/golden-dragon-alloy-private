"""Guard the generated application's native audit wiring without building an EXE."""
import ast
from pathlib import Path

FORGE = Path(__file__).resolve().parents[2] / "make_golden_dragon.py"


def _named_constant(source: str, name: str) -> str:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"missing source constant: {name}")


def test_forge_compiles_and_exposes_native_audit():
    source = FORGE.read_text(encoding="utf-8-sig")
    compile(source, str(FORGE), "exec")
    tool = _named_constant(source, "FUSION_TOOL")
    dispatch = _named_constant(source, "FUSION_DISPATCH")
    assert '"audit"' in tool
    assert 'if act == "audit":' in dispatch
    assert 'import gd_runtime as _gd_runtime' in dispatch
    assert '_core.execute("catalog.audit")' in dispatch
    assert 'if act == "native_status":' in dispatch
    assert 'if act == "native_exec":' in dispatch
    compile(dispatch.rsplit("\ndef skills_index():", 1)[0], "fusion_dispatch", "exec")


def test_forge_bundles_all_native_modules():
    source = FORGE.read_text(encoding="utf-8-sig")
    assert 'for module in ("runtime.py", "capability_ledger.py", "audit_tree.py", "native_registry.py", "blender_engine.py"):' in source
    assert 'tmp / ("gd_runtime.py" if module == "runtime.py" else module)' in source
    for module in ("gd_runtime", "capability_ledger", "audit_tree", "native_registry", "blender_engine"):
        assert f"--hidden-import {module}" in source


def test_no_unrestricted_execution_path():
    source = FORGE.read_text(encoding="utf-8-sig")
    dispatch = _named_constant(source, "FUSION_DISPATCH")
    assert 'shell=True' not in dispatch
    assert 'subprocess' not in dispatch
    assert 'execute("catalog.audit")' in dispatch
