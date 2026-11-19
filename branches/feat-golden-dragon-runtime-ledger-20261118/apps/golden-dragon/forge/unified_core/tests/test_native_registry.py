"""Real adapter registry tests: fail-closed dispatch and honest prerequisites."""
import importlib.util
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
# Source-tree tests must mirror the generated app module lookup path.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
core_spec = importlib.util.spec_from_file_location("gd_runtime", ROOT / "runtime.py")
core_module = importlib.util.module_from_spec(core_spec)
sys.modules["gd_runtime"] = core_module
core_spec.loader.exec_module(core_module)
reg_spec = importlib.util.spec_from_file_location("gd_registry_under_test", ROOT / "native_registry.py")
registry = importlib.util.module_from_spec(reg_spec)
reg_spec.loader.exec_module(registry)


def _catalog(root):
    folder = root / "fusion"
    folder.mkdir(exist_ok=True)
    (folder / "index.json").write_text('{"units":[{"id":"tool:hello","kind":"tool"}]}', encoding="utf-8")
    (folder / "recipes.json").write_text("[]", encoding="utf-8")


def _exe(path):
    buf = bytearray(512)
    buf[:2] = b"MZ"
    struct.pack_into("<I", buf, 0x3C, 0x80)
    buf[0x80:0x84] = b"PE\x00\x00"
    struct.pack_into("<HHIIIHH", buf, 0x84, 0x8664, 3, 0, 0, 0, 0xF0, 0x22)
    struct.pack_into("<H", buf, 0x98, 0x20B)
    path.write_bytes(buf)


def test_registry_is_exactly_real_allowlisted_core_operations():
    assert set(registry.ADAPTERS) == set(core_module.GoldenDragonCore.OPERATIONS)
    assert len(registry.ADAPTERS) == 8


def test_status_is_honest_about_passive_prerequisites(tmp_path, monkeypatch):
    monkeypatch.setattr(registry.shutil, "which", lambda p: None)
    result = registry.native_status(tmp_path)
    assert not result["indexed_capabilities_all_executable"]
    assert all(not x["runtime_tested_by_this_call"] for x in result["adapters"])
    audit = next(x for x in result["adapters"] if x["operation"] == "catalog.audit")
    ffprobe = next(x for x in result["adapters"] if x["operation"] == "media.probe")
    assert not audit["prerequisite_available"]
    assert audit["missing_files"]
    assert not ffprobe["prerequisite_available"]
    _catalog(tmp_path)
    new = registry.native_status(tmp_path)
    audit2 = next(x for x in new["adapters"] if x["operation"] == "catalog.audit")
    assert audit2["prerequisite_available"]


def test_actual_static_pe_adapter_dispatch(tmp_path):
    p = tmp_path / "fixture.exe"
    _exe(p)
    result = registry.native_execute(tmp_path, "binary.pe_header", local_path=str(p))
    assert result["result"]["machine"] == "0x8664"
    assert result["result"]["execution"] == "not executed"


def test_reject_unknown_code_or_remote_url(tmp_path):
    with pytest.raises(ValueError, match="unknown native adapter"):
        registry.native_execute(tmp_path, "arbitrary.shell.exec")
    with pytest.raises(ValueError, match="remote URLs"):
        registry.native_execute(tmp_path, "media.probe", local_path="https://example.com/a.mp4")


def test_transcode_requires_explicit_approval(tmp_path, monkeypatch):
    monkeypatch.setattr(registry.shutil, "which", lambda name: "/mock/ffmpeg")
    with pytest.raises(ValueError, match="explicit approval"):
        registry.native_execute(tmp_path, "media.transcode", local_path=str(tmp_path / "x.wav"))
    calls = []

    class FakeCore:
        def __init__(self, root, **kwargs):
            calls.append(("init", root, kwargs))
        def execute(self, action):
            calls.append(("execute", action))
            return {"operation": action, "result": "stubbed"}

    monkeypatch.setattr(registry, "GoldenDragonCore", FakeCore)
    data = registry.native_execute(tmp_path, "media.transcode", local_path="x.wav",
                                   profile="mp3", approve_new_file=True)
    assert data["operation"] == "media.transcode"
    assert calls[0][2]["profile"] == "mp3"
    assert calls[1] == ("execute", "media.transcode")


def test_registry_catalog_audit_is_real(tmp_path):
    _catalog(tmp_path)
    data = registry.native_execute(tmp_path, "catalog.audit")
    assert data["operation"] == "catalog.audit"
    assert data["result"]["summary"]["indexed_units"] == 1
    assert data["result"]["summary"]["runtime_verified"] == 0
