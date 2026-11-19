"""Regression tests for the unified diagnostic boundary; no external programs."""
import importlib.util
import struct
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parent.parent / "runtime.py"
spec = importlib.util.spec_from_file_location("golden_runtime", MODULE)
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


def sample_pe(path):
    data = bytearray(512)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\x00\x00"
    struct.pack_into("<HHIIIHH", data, 0x84, 0x8664, 3, 0, 0, 0, 0xF0, 0x22)
    struct.pack_into("<H", data, 0x98, 0x20B)
    path.write_bytes(data)


def test_static_pe_identity_without_execution(tmp_path):
    image = tmp_path / "app.exe"
    sample_pe(image)
    result = core.inspect_pe(image)
    assert result["format"] == "PE32+"
    assert result["machine"] == "0x8664"
    assert result["sections"] == 3
    assert result["execution"] == "not executed"
    assert len(result["sha256"]) == 64


def test_invalid_binary_rejected(tmp_path):
    path = tmp_path / "bad.exe"
    path.write_bytes(b"not an executable")
    with pytest.raises(ValueError, match="MZ"):
        core.inspect_pe(path)


def test_unknown_capability_fails_closed(tmp_path):
    with pytest.raises(ValueError, match="unknown capability"):
        core.GoldenDragonCore(tmp_path).execute("shell.exec")


def test_binary_operation_has_no_other_dependencies(tmp_path):
    image = tmp_path / "app.exe"
    sample_pe(image)
    engine = core.GoldenDragonCore(tmp_path, binary=image)
    output = engine.execute("binary.pe_header")
    assert output["result"]["bytes"] == 512
    assert output["operation"] == "binary.pe_header"
