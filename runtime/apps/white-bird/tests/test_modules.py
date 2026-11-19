"""Every Python file compiles; modules import without side effects (or are checked through ast when importing would
start something)."""
import ast
import json
import os
import subprocess
import sys

import pytest

from conftest import APP, FORGE, mcp_control_tools, read, tree

PY_FILES = sorted(p.relative_to(APP).as_posix() for p in APP.rglob("*.py") if "__pycache__" not in p.parts)


def test_app_folder_has_the_expected_modules():
    for name in ("app.py", "brain.py", "control.py", "mcp_control.py", "mcp_dragon.py", "voice.py"):
        assert name in PY_FILES, f"{name} is missing from app\\"


@pytest.mark.parametrize("rel", PY_FILES)
def test_compiles(rel):
    compile(read(rel), rel, "exec")          # compile() in memory: unlike py_compile it writes no .pyc


def test_forge_compiles():
    compile(read("make_white_bird.py", FORGE), "make_white_bird.py", "exec")


def test_app_import_has_no_side_effects(app_import):
    """Importing app.py must not start threads/servers, write settings, or touch app\\ (a stray file there makes the
    forge refuse to regenerate)."""
    assert app_import.new_threads == [], f"import started threads: {app_import.new_threads}"
    assert app_import.written == [], f"import wrote files: {app_import.written}"
    assert app_import.app_changes == [], f"import changed app\\: {app_import.app_changes}"


def test_app_import_uses_the_redirected_data_folder(app_import):
    assert str(app_import.app.SETTINGS).startswith(str(app_import.appdata)), app_import.app.SETTINGS


def test_server_and_window_code_only_runs_from_main():
    """app.py: the window (webview.start), the file server and the single-instance mutex are reached only from main()."""
    t = tree("app.py")
    top_calls = []
    for node in t.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.If) and "__name__" in ast.dump(node.test):
            continue
        for n in ast.walk(node):
            if isinstance(n, ast.Call):
                f = n.func
                top_calls.append(f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", ""))
    banned = {"start", "create_window", "serve_forever", "main", "Api", "FileServer", "single_instance", "Thread",
              "ThreadingHTTPServer", "Popen", "run", "launch_updater"}
    assert not banned & set(top_calls), f"top-level code calls {sorted(banned & set(top_calls))}"


def test_mcp_control_tools_via_ast():
    tools = mcp_control_tools()
    names = [t["name"] for t in tools]
    assert sorted(names) == ["browser", "computer", "system"], names
    for t in tools:
        assert t["inputSchema"]["type"] == "object" and "action" in t["inputSchema"]["required"], t["name"]


def test_mcp_dragon_imports_in_a_subprocess(tmp_path):
    """mcp_dragon.py reconfigures stdin/stdout at import, so it is imported in its own process (stdin closed)."""
    env = dict(os.environ, APPDATA=str(tmp_path), PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    env.pop("BD_IN_APP", None)
    code = ("import json, sys; sys.path.insert(0, sys.argv[1]); import mcp_dragon as m; "
            "print(json.dumps([t['name'] for t in m.TOOLS_WITH_ALIASES]))")
    r = subprocess.run([sys.executable, "-X", "utf8", "-B", "-c", code, str(APP)], stdin=subprocess.DEVNULL,
                       capture_output=True, text=True, encoding="utf-8", timeout=60, env=env)
    assert r.returncode == 0, r.stderr[-2000:]
    names = json.loads(r.stdout.strip().splitlines()[-1])
    assert names and len(names) == len(set(names)), f"duplicate MCP tool names: {names}"
    assert list(tmp_path.iterdir()) == [], "importing mcp_dragon wrote files"
