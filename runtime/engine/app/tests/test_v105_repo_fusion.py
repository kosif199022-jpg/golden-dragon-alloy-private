"""Black Dragon v10.5: REA repo fusion, 615-site Media Hunter and the kosif-tool link. No network."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RF_DIR = ROOT / "tools" / "repo_fusion"
LAUNCHER = ROOT / "scripts" / "dragon.py"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rf = _load("bd_v105_repo_fusion", RF_DIR / "scripts" / "repo_fusion.py")
link = _load("bd_v105_repo_link", ROOT / "tools" / "repo_link" / "repo_link.py")


def _dragon(*args, env=None):
    return subprocess.run([sys.executable, str(LAUNCHER), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=300, env=env)


def test_fusion_data_counts():
    data = rf.load()
    caps = [c for r in data["repos"] for c in r["capabilities"]]
    assert len(data["repos"]) == 10 and len(caps) == 101
    assert sum(c["status"] == "native-implemented" for c in caps) == 47
    assert len(data["modules"]) == 9
    for m in data["modules"]:
        assert (RF_DIR / "scripts" / "fusion" / m["file"]).is_file()
    for r in data["repos"]:
        assert (RF_DIR / r["report"]).is_file()


def test_fusion_find_arabic():
    hits = rf.find(rf.load(), "تقسيم الأغنية دروب")
    assert hits and hits[0]["repo"] == "librosa/librosa"


@pytest.mark.parametrize("name", ["promptlib", "rapier_bake"])
def test_stdlib_module_self_tests(name):
    res = rf.run_self_tests(rf.load(), name)
    assert res and res[0]["ok"], res


def test_launcher_registers_new_tools():
    out = _dragon("tool")
    for name in ("repo", "fusion", "hunter615", "musicmap", "pixelfx", "shotcraft", "physics-bake", "promptlib"):
        assert name in out.stdout
    assert "hunter," in out.stdout  # the v10.2 hunter stays available


def test_repo_link_pin_and_dry_run_sync():
    assert link.REPO_URL.endswith("kosif199022-jpg/kosif-tool")
    assert link.PINNED_COMMIT == "85cb965"
    st = link.status()
    assert st["bundled_fusion"] is True
    assert "linked" in st
    out = _dragon("tool", "repo", "sync")
    assert out.returncode == 0 and "dry run" in out.stdout and "push" not in out.stdout.split("plan:")[1].split("\n")[0]


def test_hunter615_offline_sites(tmp_path):
    pytest.importorskip("httpx")
    env = dict(os.environ, MH_CACHE=str(tmp_path), MH_OUT=str(tmp_path))
    out = _dragon("tool", "hunter615", "sites", "camel desert", "--json", env=env)
    assert out.returncode == 0, out.stderr[-400:]
    sites = json.loads(out.stdout)
    assert len(sites) > 5 and all(s["url"].startswith("http") for s in sites)
    assert not (ROOT / "tools" / "media_hunter_615" / "keys.json").exists()
