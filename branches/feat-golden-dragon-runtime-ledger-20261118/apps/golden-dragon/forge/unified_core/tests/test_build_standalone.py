"""The independent source composer must not call White or Golden Bird forge."""
import ast
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
MODULE = HERE.parent / "build_standalone.py"
spec = importlib.util.spec_from_file_location("gd_standalone_builder", MODULE)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
PROJECT = HERE.parents[2]


def test_independent_builder_avoids_sibling_forge_imports():
    txt = MODULE.read_text(encoding="utf-8")
    assert "load_golden_bird(" not in txt
    assert "load_white_bird(" not in txt
    assert "import make_golden_bird" not in txt
    assert "import make_white_bird" not in txt


def test_python_ast_transform_preserves_other_code():
    original = """import anthropic
VALUE = 'لغة عربية 🐉'
TOOLS = [tool('other', 'existing'), tool('fusion', 'old')]
def fusion_dispatch(a):
    return 'old'
def unrelated():
    return VALUE
"""
    forge = '''FUSION_TOOL = """    tool("fusion", "new", {"audit":"x", "probe_media":"x", "inspect_binary_imports":"x", "transcode_media":"x", "native_status":"x", "native_exec":"x"}),\\n"""
FUSION_DISPATCH = """def fusion_dispatch(a):
    import gd_runtime
    return {"audit":1, "probe_media":1, "inspect_binary_imports":1, "transcode_media":1, "native_status":1, "native_exec":1}
def skills_index():
"""
'''
    patched = builder.compose_app(original, forge)
    ast.parse(patched)
    assert 'VALUE = ' in patched
    assert 'لغة عربية 🐉' in patched
    assert "tool('other', 'existing')" in patched
    assert '"fusion", "new"' in patched
    assert "return 'old'" not in patched
    assert "import gd_runtime" in patched
    assert "class _GoldenLazyAnthropic" in patched


def test_rejects_non_temp_output():
    with pytest.raises(ValueError, match="TEMP"):
        builder._safe_destination(Path.home() / "GoldenDragon")


def test_detects_missing_baseline_and_does_not_write(tmp_path):
    destination = tmp_path / "new"
    with pytest.raises(ValueError, match="incomplete"):
        builder.build(tmp_path / "empty", destination)
    assert not destination.exists()


def test_real_repository_dry_run_is_independent(tmp_path):
    result = builder.build(PROJECT, tmp_path / "dry-run-source", dry_run=True)
    assert result["dry_run"] is True
    assert result["requires_sibling_forges"] is False
    assert result["catalog_units"] > 100
    assert result["recipes"] > 0
    assert not (tmp_path / "dry-run-source").exists()


def test_real_repository_standalone_source(tmp_path):
    target = tmp_path / "real-standalone"
    result = builder.build(PROJECT, target)
    assert result["requires_sibling_forges"] is False
    app = target / "app" / "app.py"
    assert app.is_file()
    txt = app.read_text(encoding="utf-8")
    assert "def fusion_dispatch(" in txt
    for action in builder.EVIDENCE_ACTIONS:
        assert action in txt
    assert not (target / "app" / "build.ps1").exists()
    assert (target / "forge" / "unified_core" / "build_isolated.ps1").is_file()
    assert (target / "app" / "gd_runtime.py").is_file()
    assert (target / "app" / "capability_ledger.py").is_file()
    assert (target / "app" / "audit_tree.py").is_file()
    assert (target / "app" / "native_registry.py").is_file()
    assert (target / "app" / "blender_engine.py").is_file()
    assert len(json.loads((target / "standalone-manifest.json").read_text(encoding="utf-8"))["files"]) > 25
    stamp = json.loads((target / "app" / ".gd_generated.json").read_text(encoding="utf-8"))
    assert stamp["schema"] == "golden-dragon.generated-standalone.v1"
    assert stamp["recipes"] >= 40
    assert stamp["fusion_counts"]["skill"] >= 500
    assert builder.verify_standalone_output(target)["verified"] is True
    with pytest.raises(ValueError, match="overwrite"):
        builder.build(PROJECT, target)


def test_tampered_generated_source_is_rejected(tmp_path):
    target = tmp_path / "untouched"
    builder.build(PROJECT, target)
    changed = target / "app" / "gd_runtime.py"
    changed.write_bytes(changed.read_bytes() + b"\\n# unexpected mutation")
    with pytest.raises(ValueError, match="checksum mismatch"):
        builder.verify_standalone_output(target)


def test_extra_file_is_rejected(tmp_path):
    target = tmp_path / "untouched"
    builder.build(PROJECT, target)
    (target / "app" / "unlisted.py").write_text("pass", encoding="utf-8")
    with pytest.raises(ValueError, match="file list differs"):
        builder.verify_standalone_output(target)
