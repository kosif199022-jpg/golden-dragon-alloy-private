"""Blender native render tests: reviewed presets, isolation and real image proof."""
from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

MODULE = Path(__file__).resolve().parent.parent / "blender_engine.py"
spec = importlib.util.spec_from_file_location("gd_blender_test_module", MODULE)
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)


def test_unsupported_preset_is_blocked():
    with pytest.raises(ValueError, match="unknown Blender scene preset"):
        engine.render_scene(preset="import os; os.system('bad')")


def test_no_arbitrary_script_and_fresh_temp_output(monkeypatch):
    monkeypatch.setattr(engine.shutil, "which", lambda _: "/bin/mock-blender")
    observed = {}

    def fake(argv, **kwargs):
        observed["args"] = argv
        observed["kwargs"] = kwargs
        folder = Path(argv[-2])
        (folder / "render.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 600)
        (folder / "scene.blend").write_bytes(b"BLENDER" + b"x" * 700)
        return SimpleNamespace(returncode=0, stderr=b"", stdout=b"")

    monkeypatch.setattr(engine.subprocess, "run", fake)
    report = None
    try:
        report = engine.render_scene(preset="machine_piston", resolution=256)
        assert report["blender_executed"] is True
        assert report["original_project_modified"] is False
        assert "-b" in observed["args"] or "--background" in observed["args"]
        assert "--disable-autoexec" in observed["args"]
        assert observed["kwargs"]["shell"] is False
        source = Path(report["render_png"]).parent / "render_fixed_scene.py"
        assert source.read_text(encoding="utf-8") == engine._SCRIPT
    finally:
        if report:
            shutil.rmtree(Path(report["render_png"]).parent, ignore_errors=True)


def test_no_blender_reports_missing(monkeypatch):
    monkeypatch.setattr(engine.shutil, "which", lambda _: None)
    with pytest.raises(ValueError, match="Blender is not installed"):
        engine.render_scene()


def test_real_blender_mechanical_gear():
    if not engine.shutil.which("blender"):
        pytest.skip("Blender executable is not installed")
    result = None
    try:
        result = engine.render_scene(preset="mechanical_gear", resolution=256, timeout=120)
        assert result["png_bytes"] > 300
        assert result["blend_bytes"] > 300
        assert Path(result["render_png"]).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
        assert Path(result["project_blend"]).read_bytes()[:7] == b"BLENDER"
        assert not result["arbitrary_user_script_executed"]
    finally:
        if result:
            shutil.rmtree(Path(result["render_png"]).parent, ignore_errors=True)
