"""The White Bird must run NEXT TO the Black Dragon without sharing its window lock, Chrome bridge or data folder.
Values are read from the source (ast / text), and compared with the Black Dragon source when it is on this PC."""
import ast
import json
import re

import pytest

from conftest import APP, UPSTREAM, find_def, read, tree

WB_PORT = 47831
DRAGON_PORT = "47821"
# files that end up inside WhiteBird.exe (build.ps1) or the Chrome extension folder
BUNDLED = ["app.py", "brain.py", "control.py", "mcp_control.py", "voice.py", "ui/index.html",
           "chrome_extension/background.js", "chrome_extension/manifest.json", "chrome_extension/popup.html",
           "chrome_extension/popup.js"]


def mutex_name(root):
    fn = find_def(tree("app.py", root), "single_instance")
    for n in ast.walk(fn):
        if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "CreateMutexW":
            return n.args[2].value
    raise AssertionError("CreateMutexW call not found")


def bridge_port(root):
    for n in tree("control.py", root).body:
        if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "BRIDGE_PORT":
            return n.value.value
    raise AssertionError("BRIDGE_PORT not found in control.py")


def settings_folder(root):
    m = re.search(r'^SETTINGS = Path\(os\.environ\.get\("APPDATA", Path\.home\(\)\)\) / "([^"]+)" / "settings\.json"',
                  read("app.py", root), re.M)
    assert m, "SETTINGS assignment changed shape"
    return m.group(1)


def test_mutex(app):
    name = mutex_name(APP)
    assert "WhiteBird" in name and "BlackDragon" not in name, name


def test_bridge_port_everywhere():
    assert bridge_port(APP) == WB_PORT
    fallbacks = re.findall(r"control\.BRIDGE_PORT if control else (\d+)", read("app.py"))
    assert fallbacks and set(fallbacks) == {str(WB_PORT)}, fallbacks
    assert f'os.environ.get("BD_PORT", "{WB_PORT}")' in read("mcp_control.py")
    assert f"const PORT = {WB_PORT};" in read("chrome_extension/background.js")
    assert f"http://127.0.0.1:{WB_PORT}/*" in json.loads(read("chrome_extension/manifest.json"))["host_permissions"]


def test_no_dragon_port_in_bundled_files():
    hits = [f for f in BUNDLED if DRAGON_PORT in read(f)]
    assert not hits, f"the Black Dragon's bridge port {DRAGON_PORT} appears in {hits}"
    # mcp_dragon.py is the Black Dragon's own MCP server (default port 47821 on purpose); it must stay out of the build
    assert "mcp_dragon" not in read("build.ps1")


def test_data_folders(app):
    assert settings_folder(APP) == "WhiteBird"
    assert app.SETTINGS.parent.name == "WhiteBird"
    assert ".whitebird-build" in str(app.STAGED) and app.STAGED.name == "WhiteBird"


def test_updater_targets_white_bird(app):
    assert "[string]$ProcName = 'WhiteBird'" in app.UPDATER_PS
    assert "BlackDragon" not in app.UPDATER_PS


def test_differs_from_black_dragon():
    if not (UPSTREAM / "app.py").is_file():
        pytest.skip(f"Black Dragon source not found at {UPSTREAM}")
    assert mutex_name(UPSTREAM) != mutex_name(APP)
    assert bridge_port(UPSTREAM) != bridge_port(APP)
    assert settings_folder(UPSTREAM) != settings_folder(APP)
