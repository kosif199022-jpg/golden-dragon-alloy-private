"""REA binary import engine regression tests; PE executable is never launched."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import pytest

spec = importlib.util.spec_from_file_location(
    "gd_runtime_rea", Path(__file__).resolve().parent.parent / "runtime.py"
)
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


def test_uses_direct_rea_cli_and_preserves_evidence(tmp_path, monkeypatch):
    path = tmp_path / "sample.exe"
    path.write_bytes(b"MZ" + b"x" * 64)
    evidence = {
        "operation": "inspect_pe_imports",
        "evidence_id": "ev_test_123",
        "provider": {"id": "rea-pe-imports"},
        "normalized_result": {
            "artifact": {"sha256": "c0ffee"},
            "architecture": "amd64",
            "imports": [
                {"name": "KERNEL32.dll", "functions": [
                    {"name": "CreateFileW"}, {"name": "ReadFile"}]},
            ],
            "coverage": {"status": "complete", "imports": 2},
        },
    }

    def fake_run(args, **kwargs):
        assert "inspect-pe-imports" in args
        assert "--format" in args and args[-1] == "json"
        assert kwargs["shell"] is False
        assert kwargs["timeout"] == 60
        return SimpleNamespace(returncode=0, stdout=json.dumps(evidence).encode(), stderr=b"")

    monkeypatch.setattr(core.shutil, "which", lambda _: "rea.cmd")
    monkeypatch.setattr(core.subprocess, "run", fake_run)
    result = core.GoldenDragonCore(tmp_path, binary=path).execute("binary.imports")
    data = result["result"]
    assert data["evidence_id"] == "ev_test_123"
    assert data["dll_count"] == 1
    assert data["imported_function_count"] == 2
    assert data["rea_executed"]
    assert not data["target_executed"]


def test_untrusted_batch_filename_is_rejected(tmp_path):
    path = tmp_path / "x&echo-danger.exe"
    path.write_bytes(b"MZ")
    with pytest.raises(ValueError, match="unsafe characters"):
        core.inspect_binary_imports(path)


def test_missing_rea_is_not_claimed_as_success(tmp_path, monkeypatch):
    path = tmp_path / "a.exe"
    path.write_bytes(b"MZ")
    monkeypatch.setattr(core.shutil, "which", lambda _: None)
    with pytest.raises(ValueError, match="REA CLI is not available"):
        core.inspect_binary_imports(path)


def test_invalid_evidence_not_accepted(tmp_path, monkeypatch):
    path = tmp_path / "a.exe"
    path.write_bytes(b"MZ")
    monkeypatch.setattr(core.shutil, "which", lambda _: "rea.cmd")
    monkeypatch.setattr(core.subprocess, "run", lambda *args, **kwargs:
                        SimpleNamespace(returncode=0, stdout=b"{}", stderr=b""))
    with pytest.raises(ValueError, match="unexpected evidence structure"):
        core.inspect_binary_imports(path)
