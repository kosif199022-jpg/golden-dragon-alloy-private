"""2026-11-15: the dragon folders moved from the Desktop into Desktop\\مهارات. The app must find the engine repo and its own
source wherever they live now (env var, Desktop, Desktop\\مهارات), and must not point the model at the deleted
المونتاج\\CLAUDE.md."""
import ast
import os
from pathlib import Path

from conftest import read, tree


def _home_of():
    fn = next(n for n in tree().body if isinstance(n, ast.FunctionDef) and n.name == "_home_of")
    ns = {"os": os, "Path": Path}
    exec(compile(ast.Module([fn], []), "app.py", "exec"), ns)
    return ns["_home_of"]


def test_paths_use_the_resolver():
    app = read("app.py")
    assert 'REPO = _home_of("BLACK_DRAGON_HOME", REPO_DIRNAME)' in app
    assert 'APP_SOURCE = _home_of("GOLDEN_BIRD_HOME", "الطائر الذهبي") / "app"' in app
    assert 'Path.home() / "OneDrive" / "Desktop" / REPO_DIRNAME))' not in app
    assert 'MONTAGE / "CLAUDE.md"' not in app and "where.exe" in app
    assert "مهارات" in read("mcp_dragon.py")


def test_resolver_order(tmp_path, monkeypatch):
    home = _home_of()
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.delenv("BLACK_DRAGON_HOME", raising=False)
    moved = tmp_path / "OneDrive" / "Desktop" / "مهارات" / "التنين الأسود"
    moved.mkdir(parents=True)
    assert home("BLACK_DRAGON_HOME", "التنين الأسود") == moved
    direct = tmp_path / "OneDrive" / "Desktop" / "التنين الأسود"
    direct.mkdir(parents=True)
    assert home("BLACK_DRAGON_HOME", "التنين الأسود") == direct
    monkeypatch.setenv("BLACK_DRAGON_HOME", str(tmp_path / "x"))
    assert home("BLACK_DRAGON_HOME", "التنين الأسود") == tmp_path / "x"
