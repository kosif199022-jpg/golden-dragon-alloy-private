"""«discover»: the PC catalog (gd_discover.py) and how the fusion index uses it. Everything happens in pytest's temp
folder: a fake PC with a skill, a program, a script, a skill archive, a tool folder, a browser extension, a secret file
and an MCP config whose arguments hold a fake key."""
import importlib
import json
import zipfile

import pytest

from conftest import APP, read


@pytest.fixture()
def pc(tmp_path, monkeypatch):
    root = tmp_path / "pc"
    (root / "tools" / "logo-maker").mkdir(parents=True)
    (root / "tools" / "logo-maker" / "SKILL.md").write_text(
        "---\nname: logo-maker\ndescription: Animated logo reveal for reels\n---\n# x\n", encoding="utf-8")
    (root / "programs" / "Zebra Paint" / "bin").mkdir(parents=True)
    (root / "programs" / "Zebra Paint" / "bin" / "ZebraPaint.exe").write_bytes(b"MZ" + b"0" * 64)
    (root / "programs" / "Zebra Paint" / "bin" / "unins000.exe").write_bytes(b"MZ")
    (root / "scripts").mkdir()
    (root / "scripts" / "render_quokka.py").write_text('"""Render the quokka title card to MP4."""\nprint(1)\n', encoding="utf-8")
    (root / "scripts" / ".env").write_text("API_KEY=sk-should-never-be-read\n", encoding="utf-8")
    with zipfile.ZipFile(root / "walrus-pack.skill", "w") as z:
        z.writestr("walrus/SKILL.md", "---\nname: walrus\n---\n")
    (root / "proj").mkdir()
    (root / "proj" / "package.json").write_text(json.dumps({"name": "proj", "description": "Narwhal subtitle burner",
                                                             "scripts": {"build": "x"}}), encoding="utf-8")
    (root / "ext").mkdir()
    (root / "ext" / "manifest.json").write_text(json.dumps({"manifest_version": 3, "name": "Okapi Clipper", "version": "1.0",
                                                            "description": "save clips"}), encoding="utf-8")
    (root / "ext" / "bg.js").write_text("//x\n", encoding="utf-8")
    (root / "skipme").mkdir()
    (root / "skipme" / "hidden_tool.py").write_text('"""nope"""\n', encoding="utf-8")
    mcp = tmp_path / "claude_desktop_config.json"
    mcp.write_text(json.dumps({"mcpServers": {"capybara": {"command": "C:/x/node.exe",
                                                           "args": ["--token", "sk-fake-secret-123"],
                                                           "env": {"KEY": "sk-fake-env-456"}}}}), encoding="utf-8")
    home = tmp_path / "home"
    home.mkdir()
    (home / "discover.json").write_text(json.dumps({"roots": [{"path": str(root), "depth": 4, "label": "fake"}],
                                                    "exclude": ["skipme"], "use_defaults": False}), encoding="utf-8")
    monkeypatch.setenv("GOLDEN_LOCAL_HOME", str(home))
    import gd_discover
    gd = importlib.reload(gd_discover)
    monkeypatch.setattr(gd, "mcp_configs", lambda: [mcp])
    yield gd, home
    monkeypatch.delenv("GOLDEN_LOCAL_HOME", raising=False)
    importlib.reload(gd_discover)


def _by_name(units):
    return {u["name"]: u for u in units}


def test_scan_finds_every_kind(pc):
    gd, home = pc
    data = gd.scan()
    u = _by_name(data["units"])
    assert u["logo-maker"]["kind"] == "pc-skill" and u["logo-maker"]["status"] == "copy"
    assert u["ZebraPaint"]["kind"] == "pc-app"
    assert "unins000" not in u, "installers/uninstallers are not programs"
    assert u["render_quokka.py"]["kind"] == "pc-script" and "quokka title card" in u["render_quokka.py"]["what"]
    assert u["walrus-pack"]["kind"] == "pc-pack" and u["walrus-pack"]["status"] == "archive"
    assert u["proj"]["kind"] == "pc-tool" and "Narwhal" in u["proj"]["what"]
    assert u["Okapi Clipper"]["kind"] == "pc-tool"
    assert u["capybara"]["kind"] == "pc-mcp" and u["capybara"]["extra"]["program"] == "node.exe"
    assert "hidden_tool.py" not in u, "exclude globs are honoured"
    assert (home / "local_units.json").is_file()


def test_scan_never_stores_secrets(pc):
    gd, home = pc
    gd.scan()
    text = (home / "local_units.json").read_text(encoding="utf-8")
    for secret in ("sk-fake-secret-123", "sk-fake-env-456", "sk-should-never-be-read"):
        assert secret not in text


def test_running_needs_approval(pc):
    gd, _ = pc
    u = _by_name(gd.scan()["units"])
    for name in ("ZebraPaint", "render_quokka.py", "proj"):
        assert u[name]["cost"] == "approval" and u[name].get("warn_ar")


def test_fusion_sees_the_pc_catalog(pc, fz, monkeypatch):
    gd, _ = pc
    monkeypatch.delenv("GOLDEN_NO_LOCAL", raising=False)
    monkeypatch.setattr(fz, "_gdd", gd)
    fz._cache.clear()
    n_index = len(fz.index()["units"])
    out = fz.md_discover()
    assert "اكتشاف الجهاز" in out
    assert len(fz.units()) > n_index
    hits = fz.find("render quokka", kind="pc")
    assert hits and hits[0]["name"] == "render_quokka.py"
    assert fz.resolve(hits[0]["id"])["kind"] == "pc-script"
    assert "كتالوج الجهاز" in fz.md_doctor()
    assert "render_quokka.py" in fz.md_local("pc-script") or "quokka" in fz.md_local("pc-script")
    ids = [u["id"] for u in fz.units()]
    assert len(ids) == len(set(ids)), "a pc unit never shadows an index id"


def test_no_local_switch(fz):
    assert fz.local().get("off") and all(not u["kind"].startswith("pc-") for u in fz.units())


def test_discover_is_wired_into_the_app():
    app = read("app.py")
    assert '"discover", "local"' in app and "fz.md_discover()" in app
    assert "gd_discover" in read("build.ps1")
    src = read("gd_discover.py")
    assert "C:\\Users\\" not in src and "C:/Users/" not in src, "no machine path in the module"
