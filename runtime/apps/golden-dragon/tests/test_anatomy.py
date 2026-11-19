"""Offline tests for the Golden Dragon / Anatomy integration; no network or Node execution."""
import importlib.util
from pathlib import Path

import pytest

from conftest import FORGE

MODULE = FORGE / "modules" / "anatomy_bridge.py"
PATCH = FORGE / "gd_patches" / "gd_anatomy.py"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def bridge():
    return load(MODULE, "anatomy_bridge_t")


@pytest.fixture
def installed(tmp_path, monkeypatch, bridge):
    root = tmp_path / "anatomy"
    for path, content in (
        ("SKILL.md", "---\nname: anatomy\n---\n# Anatomy\n"),
        ("LICENSE", "MIT License\nCopyright Ryan\n"),
        ("kit/iso-kit.mjs", "export const x = 1;\n"),
        ("scripts/inline-kit.mjs", "export const y = 2;\n"),
        ("examples/dial-indicator/build.mjs", "import '../../kit/iso-kit.mjs';\n"),
        ("examples/raptor-engine/build.mjs", "import '../../kit/iso-kit.mjs';\n"),
    ):
        f = root / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content, encoding="utf-8")
    monkeypatch.setenv("GOLDEN_ANATOMY_HOME", str(root))
    monkeypatch.setattr(bridge, "_node_version",
                        lambda: {"available": True, "compatible": True, "version": "v22.0.0"})
    return root


def test_uninstalled_is_honestly_reported(tmp_path, monkeypatch, bridge):
    monkeypatch.setenv("GOLDEN_ANATOMY_HOME", str(tmp_path / "missing"))
    assert bridge.doctor()["skill_installed"] is False
    assert bridge.doctor()["ok"] is False
    assert "npx skills add" in bridge.doctor()["install_command"]


def test_doctor_and_plan_do_not_build_anything(bridge, installed, tmp_path):
    status = bridge.doctor()
    assert status["ok"] and status["skill_installed"]
    plan = bridge.brief("اشرح حركة محرك صاروخ بالنموذج")
    assert plan["medium"] == "SVG + WebGL" and plan["reference_example"] == "raptor-engine"
    assert plan["skill_ready"] and plan["workflow"]
    assert not list(tmp_path.glob("*.html"))


@pytest.mark.parametrize("prompt, expected", [
    ("interactive gauge with live readout", "dial-indicator"),
    ("محاكاة موجات الماء والضوء", "ripple-tank"),
    ("turntable 3D machine", "turning-dial"),
    ("توضيح لوحة مفاتيح كمبيوتر", "desk-computer"),
])
def test_medium_selection(bridge, prompt, expected):
    assert bridge.brief(prompt)["reference_example"] == expected


def test_scaffold_copies_real_sample_and_license_without_execution(tmp_path, installed, bridge):
    work = tmp_path / "work"
    work.mkdir()
    result = bridge.scaffold("my-demo", workdir=work)
    root = work / "my-demo"
    assert result["ok"] and result["executed"] is False
    assert (root / "LICENSE").read_text(encoding="utf-8").startswith("MIT")
    assert (root / "SKILL.md").is_file()
    assert (root / "kit" / "iso-kit.mjs").is_file()
    assert (root / "scripts" / "inline-kit.mjs").is_file()
    assert (root / "examples" / "dial-indicator" / "build.mjs").is_file()
    assert "node examples/dial-indicator/build.mjs" in result["next_command"]
    assert "not a finished custom drawing" in (root / "GOLDEN_ANATOMY_README.md").read_text(encoding="utf-8")


def test_never_overwrites_or_escapes_workspace(tmp_path, installed, bridge):
    work = tmp_path / "work"
    work.mkdir()
    bridge.scaffold("sample", workdir=work)
    with pytest.raises(FileExistsError):
        bridge.scaffold("sample", workdir=work)
    with pytest.raises(ValueError, match="escapes"):
        bridge.scaffold("../outside", workdir=work)
    with pytest.raises(ValueError, match="NEW relative"):
        bridge.scaffold(str(tmp_path / "absolute"), workdir=work)
    assert not (tmp_path / "outside").exists()


def test_example_must_exist_and_be_bounded(tmp_path, installed, bridge):
    work = tmp_path / "work"
    work.mkdir()
    with pytest.raises(ValueError, match="Unknown example"):
        bridge.scaffold("bad", example="untrusted", workdir=work)
    with pytest.raises(FileNotFoundError):
        bridge.scaffold("no-example", example="turning-dial", workdir=work)
    assert not (work / "no-example").exists()


def test_patch_is_reproducible_and_permission_gated():
    patch = load(PATCH, "gd_anatomy_t")
    def strict_sub(text, old, new, count, desc):
        assert text.count(old) == count, (desc, text.count(old))
        return text.replace(old, new, count)
    source = (
        "SYSTEM = f'''\\n- **قواعد الفهرس:**\\n'''\\n"
        "TOOLS = [\\n    tool(\"rebuild_app\", \"x\", {}, []),\\n]\\n"
        "class Session:\\n    def dispatch(self, name, a):\\n"
        "        if name == \"fusion\":\\n            return fusion_dispatch(a)\\n"
        "def fusion_dispatch(a):\\n    return \"ok\", False\\n"
    )
    source = source.replace("\\n", "\n")  # the mock source uses escaped line breaks
    output = patch.patch_app(source, strict_sub)
    assert 'tool("anatomy"' in output and 'tool("anatomy_scaffold"' in output
    assert "approval=True" in output
    assert "def anatomy_dispatch(" in output
    assert "anatomy_scaffold" in output
    assert "Anatomy: النماذج" in output
    assert "anatomy_bridge" in patch.patch_build("--hidden-import gd_discover", strict_sub)


def test_forge_regenerates_bridge_without_editing_generated_app():
    generator = (FORGE / "make_golden_dragon.py").read_text(encoding="utf-8")
    assert 'gd_patches" / "gd_anatomy.py"' in generator
    assert '"modules" / "anatomy_bridge.py"' in generator
    assert "an.patch_build(patch_build(build), sub)" in generator
