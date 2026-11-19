"""Regression tests for the portable thinking toolkit generation path."""
import importlib.util
import json
import shutil
import sys
import types
from pathlib import Path

import pytest


FORGE_SOURCE = Path(__file__).resolve().parents[2] / "make_golden_dragon.py"
BUNDLED_TOOLKIT = FORGE_SOURCE.parent / "data" / "fusion" / "thinking.json"


def _load_builder():
    spec = importlib.util.spec_from_file_location("golden_builder_isolated_t", FORGE_SOURCE)
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    return builder


def test_no_external_analysis_required_for_thinking(tmp_path, monkeypatch):
    builder = _load_builder()
    builder.GD = tmp_path / "golden-dragon"  # intentionally no analysis folder
    builder.FORGE = tmp_path / "forge"
    builder.FUSION = builder.FORGE / "data" / "fusion"
    builder.FUSION.mkdir(parents=True)
    shutil.copy2(BUNDLED_TOOLKIT, builder.FUSION / "thinking.json")
    builder.log = []
    monkeypatch.setitem(sys.modules, "build_fusion", types.ModuleType("build_fusion"))

    data = json.loads(BUNDLED_TOOLKIT.read_text(encoding="utf-8-sig"))
    assert len(data["protocol_ar"]) == 8
    result = builder.scholars_section()
    assert "أدوات العلماء (" + str(len(data["tools"])) in result
    assert any("optional book overlay absent" in x for x in builder.log)


def test_present_book_overlay_requires_merge_implementation(tmp_path, monkeypatch):
    builder = _load_builder()
    builder.GD = tmp_path / "empty-golden-dragon"
    builder.FORGE = tmp_path / "forge"
    builder.FUSION = builder.FORGE / "data" / "fusion"
    builder.FUSION.mkdir(parents=True)
    shutil.copy2(BUNDLED_TOOLKIT, builder.FUSION / "thinking.json")
    books = builder.FORGE / "data" / "thinking_books.json"
    books.write_text('{"tools": []}', encoding="utf-8")
    monkeypatch.setitem(sys.modules, "build_fusion", types.ModuleType("build_fusion"))

    with pytest.raises(SystemExit, match="refusing to drop tools"):
        builder.scholars_section()
