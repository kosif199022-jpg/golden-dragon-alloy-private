"""Regression tests for lazy Anthropic SDK loading in generated Golden Dragon app."""
import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest

ROOT = Path(__file__).resolve().parents[3]
COMPOSER = ROOT / "forge" / "unified_core" / "build_standalone.py"
FORGE = ROOT / "forge" / "make_golden_dragon.py"


@pytest.fixture
def generated_app(tmp_path):
    spec = importlib.util.spec_from_file_location("gd_lazy_source_builder", COMPOSER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    target = tmp_path / "standalone-lazy-test"
    module.build(ROOT, target)
    return target / "app" / "app.py"


def _lazy_nodes(tree):
    klass = next(
        n for n in tree.body
        if isinstance(n, ast.ClassDef) and n.name == "_GoldenLazyAnthropic"
    )
    assignment = next(
        n for n in tree.body if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "anthropic" for t in n.targets)
    )
    return klass, assignment


def test_generated_app_does_not_import_anthropic_at_top_level(generated_app):
    tree = ast.parse(generated_app.read_text(encoding="utf-8-sig"))
    assert not any(
        isinstance(n, ast.Import) and any(x.name == "anthropic" for x in n.names)
        for n in tree.body
    )
    _lazy_nodes(tree)


def test_lazy_proxy_imports_only_on_first_use(generated_app):
    tree = ast.parse(generated_app.read_text(encoding="utf-8-sig"))
    klass, assignment = _lazy_nodes(tree)
    calls = []
    fake = SimpleNamespace(Anthropic=object(), APIStatusError=Exception)
    importer = SimpleNamespace(import_module=lambda name: (calls.append(name), fake)[1])
    mini = ast.Module(body=[klass, assignment], type_ignores=[])
    namespace = {"_gd_importlib": importer}
    exec(compile(ast.fix_missing_locations(mini), "<lazy-proxy-test>", "exec"), namespace)
    assert not calls
    prox = namespace["anthropic"]
    assert prox.Anthropic is fake.Anthropic
    assert calls == ["anthropic"]
    assert namespace["anthropic"] is fake


def test_build_guarantees_hidden_import_when_lazy():
    txt = FORGE.read_text(encoding="utf-8-sig")
    assert 'lazy-load Anthropic SDK at first API request' in txt
    assert "--hidden-import anthropic" in txt
    build = ROOT / "forge" / "unified_core" / "build_isolated.ps1"
    assert "'--hidden-import','anthropic'" in build.read_text(encoding="utf-8-sig")
