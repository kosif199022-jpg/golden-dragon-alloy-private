"""No network, file writes, third-party execution, or Golden Dragon imports."""
import importlib.util
import sys
from pathlib import Path

MODULE = Path(__file__).resolve().parent.parent / "capability_ledger.py"
spec = importlib.util.spec_from_file_location("capability_ledger", MODULE)
ledger = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ledger
spec.loader.exec_module(ledger)


def test_ok_status_does_not_mean_runtime_verified():
    d = {"units": [
        {"id": "tool:real", "kind": "tool", "status": "ok"},
        {"id": "engine:claimed", "kind": "engine", "status": "ok"},
    ]}
    x = ledger.build_ledger(d)
    assert x["counts"]["runtime_verified"] == 0
    assert all(not u["runtime_verified"] for u in x["units"])
    assert x["counts"]["catalog_status"]["ok"] == 2


def test_passive_program_detection_is_not_execution(monkeypatch):
    monkeypatch.setattr(ledger.shutil, "which", lambda name: "/bin/fake" if name == "fake" else None)
    d = {"units": [
        {"id": "program:fake", "kind": "program", "probe": "fake", "status": "ok"},
        {"id": "program:gone", "kind": "program", "probe": "gone", "status": "ok"},
    ]}
    x = ledger.build_ledger(d)
    assert [u["passive_observation"] for u in x["units"]] == [
        "program_found_on_path", "program_not_found_on_path"
    ]
    assert x["counts"]["runtime_verified"] == 0


def test_missing_skill_source_and_recipe_references(tmp_path):
    d = {"units": [
        {"id": "skill:lost", "kind": "skill", "path": str(tmp_path / "SKILL.md")},
        {"id": "tool:ok", "kind": "tool", "status": "ok"},
    ]}
    recipes = [{"id": "r", "steps": [
        {"read": ["skill:lost"], "use": ["tool:missing"], "gate_ar": ""},
    ]}]
    x = ledger.build_ledger(d, recipes)
    assert x["counts"]["passive_observations"]["skill_source_missing"] == 1
    assert x["counts"]["recipe_issues"] == 2
    assert {issue["error"] for issue in x["recipe_issues"]} == {"unknown_unit", "missing_gate"}


def test_rejects_duplicate_unit_ids():
    d = {"units": [
        {"id": "tool:x", "kind": "tool"},
        {"id": "tool:x", "kind": "tool"},
    ]}
    x = ledger.build_ledger(d)
    assert x["duplicate_ids"] == ["tool:x"]
