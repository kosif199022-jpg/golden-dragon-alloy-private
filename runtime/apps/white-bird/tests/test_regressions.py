"""Regression tests for the bugs fixed on 2026-11-13 (found by an independent review, each one reproduced first).
If one of these fails, the bug is back: read the docstring before «fixing» the test."""
import ast
import importlib.util
import re
import subprocess
import sys
import time

import pytest

from conftest import APP, find_def, read, tree


def _mcp_dragon():
    # mcp_dragon.py calls sys.stdin/stdout.reconfigure() at import (it is an MCP stdio server); pytest's captured streams
    # don't have reconfigure, so give it real text streams just for the import
    import io
    spec = importlib.util.spec_from_file_location("wb_mcp_dragon_under_test", APP / "mcp_dragon.py")
    m = importlib.util.module_from_spec(spec)
    old = sys.stdin, sys.stdout
    sys.stdin, sys.stdout = io.TextIOWrapper(io.BytesIO()), io.TextIOWrapper(io.BytesIO())
    try:
        spec.loader.exec_module(m)
    finally:
        sys.stdin, sys.stdout = old
    return m


def test_skill_read_refuses_dotdot():
    """blackdragon_skill name='..' used to resolve to ~/.claude and read .credentials.json (the Claude login)."""
    md = _mcp_dragon()
    for nm in ("..", ".", ".claude"):
        r, err = md.execute_tool("blackdragon_skill", {"action": "read", "name": nm, "file": ".credentials.json"})
        assert err and r[0]["text"].startswith("pass the skill name"), f"name={nm!r} was not refused"


def test_computer_wait_has_a_handler():
    """'wait' is in the computer tool's enum; the standalone handler used to answer 'unknown action: wait'."""
    r, err = _mcp_dragon().run_computer_standalone({"action": "wait", "seconds": 0.05})
    assert not err and r[0]["text"].startswith("waited")


def test_run_cmd_timeout_kills_the_tree():
    """subprocess.run(timeout=) killed only the direct child and then waited on pipes a grandchild (ffmpeg, blender)
    still held, so a 60 s timeout on a 30 min render did not fire. ping is the grandchild here (cmd -> ping)."""
    md = _mcp_dragon()
    t0 = time.time()
    with pytest.raises(subprocess.TimeoutExpired):
        md.run_cmd(["cmd", "/c", "ping -n 30 127.0.0.1 >nul"], cwd=APP, timeout=1.5)
    assert time.time() - t0 < 15, "timeout fired late: the grandchild kept the pipes open"


def test_mcp_dragon_talks_to_white_bird():
    """The fork's copy must use White Bird's bridge port and settings (token), not the Black Dragon's 47821."""
    src = read("mcp_dragon.py")
    assert "47821" not in src
    assert src.count('os.environ.get("BD_PORT", "47831")') == 2
    assert '/ "WhiteBird" / "settings.json"' in src


def _q():
    line = next(l for l in read("control.py").splitlines() if l.strip().startswith("return \"'\" + re.sub("))
    return eval("lambda s: " + line.strip()[len("return "):], {"re": re})


@pytest.mark.parametrize("ch", ["'", "‘", "’", "‚", "‛"])
def test_ps_quote_doubles_every_single_quote(ch):
    """PowerShell ends a '...' literal at the curly quotes too; only ASCII ' used to be doubled (command injection)."""
    out = _q()(f"a{ch}b")
    assert out == f"'a{ch}{ch}b'"


def test_ps_quote_blocks_injection_for_real():
    evil = "Brave’s'; Write-Output INJECTED; '"
    ps = "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Write-Output " + _q()(evil)
    out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True, timeout=60)
    assert out.stdout.decode("utf-8", "replace").strip() == evil


def test_kill_guard_protects_this_app():
    """system kill target='WhiteBird' used to run Stop-Process on the app itself (only 'blackdragon' was protected)."""
    assert re.search(r'name\.lower\(\) in \([^)]*"whitebird"', read("control.py"))


def test_open_saved_restores_control_state():
    """A reopened chat showed 🖥 control OFF while the model still had the control tools (control was never returned)."""
    fn = find_def(tree("app.py"), "Api", "open_saved")
    ret = [n for n in ast.walk(fn) if isinstance(n, ast.Return) and isinstance(n.value, ast.Dict)][-1].value
    assert "control" in [k.value for k in ret.keys if isinstance(k, ast.Constant)]
    js = read("ui/index.html")
    body = js[js.index("async function openSaved"):js.index("replaying=true", js.index("async function openSaved"))]
    assert "control:!!r.control" in body


def test_settings_set_goes_through_the_running_app(app, monkeypatch, tmp_path):
    """settings_set wrote the file directly and the next Api._save() rewrote it from memory, silently undoing the toggle."""
    settings = tmp_path / "settings.json"
    monkeypatch.setattr(app, "SETTINGS", settings)

    class FakeApi:
        def __init__(self):
            import threading
            self._lock, self._settings, self.saved = threading.RLock(), {"spent": 1.0}, 0

        def _save(self):
            self.saved += 1
            settings.write_text(__import__("json").dumps(self._settings), encoding="utf-8")

    fake = FakeApi()
    monkeypatch.setitem(app._LIVE, "api", fake)
    app.settings_set("brain", False)
    assert fake._settings == {"spent": 1.0, "brain": False} and fake.saved == 1
    fake._save()                                   # what every API turn does
    assert app.settings_get("brain", True) is False


def test_settings_set_without_app_is_atomic(app, monkeypatch, tmp_path):
    settings = tmp_path / "s" / "settings.json"
    monkeypatch.setattr(app, "SETTINGS", settings)
    monkeypatch.setattr(app, "_LIVE", {})
    app.settings_set("show_thinking", True)
    assert app.settings_get("show_thinking") is True
    assert not list(settings.parent.glob("*.tmp"))


def test_rebuild_compiles_every_module():
    """_rebuild_app compiled only app.py and control.py; a typo in brain.py shipped an exe that dies at start."""
    src = ast.unparse(find_def(tree("app.py"), "Api", "_rebuild_app"))
    assert 'for f in ("app.py", "control.py")' not in src
    assert "glob('*.py')" in src or 'glob("*.py")' in src
