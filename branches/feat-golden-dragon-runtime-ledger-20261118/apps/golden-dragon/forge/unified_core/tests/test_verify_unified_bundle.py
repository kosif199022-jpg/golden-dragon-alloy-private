"""Offline unit tests for the native PyInstaller bundle verifier."""
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("gd_bundle_check", HERE / "verify_unified_bundle.py")
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


def _staged(tmp_path):
    exe = tmp_path / "GoldenDragon.exe"
    exe.write_bytes(b"MZ" + b"x" * 150)
    base = tmp_path / "_internal"
    for f in v.NEED_DATA:
        p = base / f
        p.parent.mkdir(parents=True, exist_ok=True)
        if f == "fusion/index.json":
            p.write_text(json.dumps({"units": [{"id": "skill:x"}]}), encoding="utf-8")
        elif f == "fusion/recipes.json":
            p.write_text(json.dumps([{"id": "recipe"}]), encoding="utf-8")
        elif f.endswith("background.js"):
            p.write_text("const PORT = 47851;", encoding="utf-8")
        else:
            p.write_text("data", encoding="utf-8")
    return exe


def test_valid_synthetic_bundle_passes(tmp_path):
    exe = _staged(tmp_path)
    r = v.verify_inventory(exe, {"app"}, set(v.NEED_MODULES))
    assert r["success"]
    assert r["fusion_units"] == 1
    assert r["runtime_behavior_verified"] is False


def test_missing_native_core_is_failure(tmp_path):
    exe = _staged(tmp_path)
    modules = set(v.NEED_MODULES) - {"gd_runtime"}
    r = v.verify_inventory(exe, {"app"}, modules)
    assert not r["success"]
    assert r["modules_missing"] == ["gd_runtime"]


def test_missing_data_or_wrong_port_is_failure(tmp_path):
    exe = _staged(tmp_path)
    (tmp_path / "_internal" / "ui" / "version.txt").unlink()
    bg = tmp_path / "_internal" / "chrome_extension" / "background.js"
    bg.write_text("const PORT = 47841;", encoding="utf-8")
    r = v.verify_inventory(exe, {"app"}, set(v.NEED_MODULES))
    assert not r["success"]
    assert "ui/version.txt" in r["data_missing"]
    assert not r["extension_port_47851"]


def test_missing_entry_is_failure(tmp_path):
    exe = _staged(tmp_path)
    r = v.verify_inventory(exe, set(), set(v.NEED_MODULES))
    assert not r["success"]
