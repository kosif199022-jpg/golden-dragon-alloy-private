"""Offline tests for Viral Video Analyzer and Replica Skill core routing."""
import importlib.util
from pathlib import Path

from conftest import FORGE


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_viral_plan_is_truthful_and_requires_approval():
    mod = load(FORGE / "modules" / "gd_core_integrations.py", "gd_core_viral")
    plan = mod.plan("viral", "https://example.org/video")
    assert plan["kind"] == "viral"
    assert "transcript.srt" in plan["outputs"]
    assert "template" in plan["notice"]
    assert plan["requires_approval"] and not plan["executed"]


def test_replica_has_exactly_eleven_stages_and_clean_room_gate():
    mod = load(FORGE / "modules" / "gd_core_integrations.py", "gd_core_replica")
    plan = mod.plan("replica", "my authorized application")
    assert len(plan["stages"]) == 11
    assert plan["stages"][0] == "recon"
    assert plan["stages"][-1] == "deploy"
    assert any("proprietary" in s for s in plan["checks"])
    assert plan["requires_approval"]


def test_doctor_does_not_claim_uninstalled_skills(tmp_path):
    mod = load(FORGE / "modules" / "gd_core_integrations.py", "gd_core_doctor")
    state = mod.doctor(tmp_path)
    assert not state["viral"]["installed"]
    assert not state["replica"]["installed"]


def test_detects_locally_installed_skills(tmp_path):
    mod = load(FORGE / "modules" / "gd_core_integrations.py", "gd_core_installed")
    viral = tmp_path / "viral-video-analyzer"
    viral.mkdir()
    (viral / "analyze_viral_video.py").write_text("pass", encoding="utf8")
    (viral / "requirements.txt").write_text("", encoding="utf8")
    replica = tmp_path / "replica-skill"
    for stage in mod.REPLICA_STAGES:
        folder = replica / ("replica-" + stage)
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text("# test", encoding="utf8")
    result = mod.doctor(tmp_path)
    assert result["viral"]["installed"]
    assert result["replica"]["installed"]
    assert len(result["replica"]["stages_found"]) == 11


def test_patch_registers_both_core_tools_and_dispatchers():
    patch = load(FORGE / "gd_patches" / "gd_anatomy.py", "gd_patch_core")
    assert 'tool("viral_video_analyzer"' in patch.TOOLS
    assert 'tool("replica_skill"' in patch.TOOLS
    assert "core_integrations_dispatch" in patch.CORE_DISPATCH
    assert "gd_core_integrations" in patch.patch_build(
        "--hidden-import gd_discover",
        lambda text, old, new, count, label: text.replace(old, new, count))
    generator = (FORGE / "make_golden_dragon.py").read_text(encoding="utf8")
    assert '"modules" / "gd_core_integrations.py"' in generator
