"""Exercise the generated standalone app's actual fused native dispatch."""
import ast
import importlib.util
import json
import struct
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "standalone_native", HERE.parent / "build_standalone.py"
)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
ROOT = HERE.parents[2]


def _dispatch_from_generated(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    func = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name == "fusion_dispatch")
    fragment = ast.Module(body=[func], type_ignores=[])
    namespace = {"json": json, "__file__": str(path)}
    exec(compile(ast.fix_missing_locations(fragment), str(path), "exec"), namespace)
    return namespace["fusion_dispatch"]


def _pe_fixture(path: Path):
    payload = bytearray(512)
    payload[:2] = b"MZ"
    struct.pack_into("<I", payload, 0x3C, 0x80)
    payload[0x80:0x84] = b"PE\x00\x00"
    struct.pack_into("<HHIIIHH", payload, 0x84, 0x8664, 3, 0, 0, 0, 0xF0, 0x22)
    struct.pack_into("<H", payload, 0x98, 0x20B)
    path.write_bytes(payload)


def test_true_standalone_fusion_native_end_to_end(tmp_path, monkeypatch):
    destination = tmp_path / "real-built-app"
    built = builder.build(ROOT, destination)
    assert built["requires_sibling_forges"] is False
    app = destination / "app"
    assert (app / "native_registry.py").is_file()
    assert (app / "gd_runtime.py").is_file()
    monkeypatch.syspath_prepend(str(app))
    dispatch = _dispatch_from_generated(app / "app.py")

    status, error = dispatch({"action": "native_status"})
    assert not error, status
    info = json.loads(status)
    assert info["adapter_count"] == 8
    assert info["indexed_capabilities_all_executable"] is False
    assert all(not a["runtime_tested_by_this_call"] for a in info["adapters"])

    sample = tmp_path / "sample.exe"
    _pe_fixture(sample)
    result, error = dispatch({
        "action": "native_exec", "operation": "binary.pe_header", "path": str(sample)
    })
    assert not error, result
    evidence = json.loads(result)
    assert evidence["operation"] == "binary.pe_header"
    assert evidence["result"]["machine"] == "0x8664"
    assert evidence["result"]["execution"] == "not executed"

    invalid, error = dispatch({
        "action": "native_exec", "operation": "code.exec", "path": str(sample)
    })
    assert error and "unknown native adapter" in invalid

    no_confirm, error = dispatch({
        "action": "native_exec", "operation": "media.transcode",
        "path": str(tmp_path / "not-here.wav"), "profile": "mp3"
    })
    assert error and "approval" in no_confirm
