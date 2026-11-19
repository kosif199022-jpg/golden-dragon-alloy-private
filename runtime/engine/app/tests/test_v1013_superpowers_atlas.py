"""v10.13: freshest Superpowers checkout, live hub bridge (`tool sp`), curated Atlas picks (`tool atlas`).

No test touches the owner's real repos: fake checkouts are built in tmp_path.
"""
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import textwrap

SKILL = pathlib.Path(__file__).resolve().parents[2]


def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, SKILL / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SP = load("app/dragon/superpowers.py", "bd_sp_test")


def fake_checkout(base, git_ts=None, hub_body=None):
    root = base / ".claude" / "skills" / "kosif-superpowers"
    (root / "scripts").mkdir(parents=True)
    (root / "SKILL.md").write_text("name: kosif-superpowers", encoding="utf-8")
    (root / "scripts" / "hub.py").write_text(hub_body or "raise SystemExit('must not run')", encoding="utf-8")
    if git_ts:
        (base / ".git" / "logs").mkdir(parents=True)
        (base / ".git" / "logs" / "HEAD").write_text(
            f"0 1 someone <x@y> {git_ts - 100} +0300\tclone\n0 1 someone <x@y> {git_ts} +0300\tmerge\n", encoding="utf-8")
    return root


def test_git_time_beats_file_mtime(tmp_path, monkeypatch):
    monkeypatch.delenv("DRAGON_SUPERPOWERS_ROOT", raising=False)
    new = fake_checkout(tmp_path / "kosif-tool", git_ts=1794264812)
    old = fake_checkout(tmp_path / "old" / "kosif-tool", git_ts=1794134563)
    os.utime(old / "SKILL.md", (2e9, 2e9))          # older commit, but newer file times (a fresh clone)
    assert SP.pick([old, new]) == new
    assert SP.repo_of(new) == tmp_path / "kosif-tool"


def test_explicit_root_wins(tmp_path, monkeypatch):
    a = fake_checkout(tmp_path / "a", git_ts=1794264812)
    b = fake_checkout(tmp_path / "b", git_ts=1700000000)
    monkeypatch.setenv("DRAGON_SUPERPOWERS_ROOT", str(b))
    assert SP.pick([b, a]) == b


def test_bridge_never_executes_and_keeps_v10_field(tmp_path):
    root = fake_checkout(tmp_path / "kt")
    r = SP.bridge("مونتاج", root=root, full=True)
    assert r["connected_locally"] and not r["executed"]
    assert any("hub.py find" in s["command_template"] for s in r["steps"])
    assert all(s["run"] is False and str(root) in s["command"] for s in r["steps"])


def test_bridge_offline_lists_searched(tmp_path):
    r = SP.bridge("x", root=tmp_path / "missing")
    assert r["connected_locally"] is False and r["searched"]


FAKE_HUB = textwrap.dedent('''
    import json, sys
    a = sys.argv[1:]
    if a[0] == "find":
        print(json.dumps({"brief": a[1], "tools": [{"id": "verify-video", "title_ar": "فحص", "readiness": {"state": "ready"},
              "first_command": "python scripts/verify_video.py in.mp4", "run_from": ".", "safety": "runs-external-programs",
              "consent": ""}], "execution_plan": {"blocked": []}, "powers": [], "guides": []}))
    elif a[0] == "doctor":
        print(json.dumps({"summary": {"tools": 2, "ready": 1, "missing": 1, "biggest_unlocks": [["bin:chromium", 1]]},
              "tools": [{"id": "render-html", "state": "missing", "missing": ["bin:chromium"]}]}))
    elif a[0] == "run":
        sys.exit(0 if "--yes" in a else 3)
''')


def sp_cli(args, env_root):
    env = dict(os.environ, DRAGON_SUPERPOWERS_ROOT=str(env_root), PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, str(SKILL / "tools/superpowers/sp.py")] + args,
                          capture_output=True, text=True, encoding="utf-8", env=env, timeout=60)


def test_sp_find_doctor_and_consent_gate(tmp_path):
    root = fake_checkout(tmp_path / "kt", hub_body=FAKE_HUB)
    f = sp_cli(["find", "ريل"], root)
    assert f.returncode == 0 and "verify-video" in f.stdout and "محتاجة موافقة" in f.stdout
    assert json.loads(sp_cli(["find", "ريل", "--json"], root).stdout)["brief"] == "ريل"
    d = sp_cli(["doctor"], root)
    assert d.returncode == 0 and "render-html" in d.stdout and "بموافقتك" in d.stdout
    blocked = sp_cli(["run", "montage-pro", "build"], root)
    assert blocked.returncode == 3 and "موافقة" in blocked.stderr
    assert sp_cli(["run", "--yes", "montage-pro", "build"], root).returncode == 0


def test_sp_qc_refuses_overwrite(tmp_path):
    root = fake_checkout(tmp_path / "kt", hub_body=FAKE_HUB)
    film = tmp_path / "f.mp4"; film.write_bytes(b"x")
    (tmp_path / "f.sp_qc.json").write_text("{}")
    assert sp_cli(["qc", str(film)], root).returncode == 2


def test_atlas_picks_bundled_with_source():
    at = load("tools/atlas/atlas.py", "bd_atlas_test")
    for name in at.PICKS:
        d = at.PICKS_DIR / name
        assert (d / "SKILL.md").is_file() and (d / "SOURCE.md").is_file(), name
        src = (d / "SOURCE.md").read_text(encoding="utf-8")
        assert "MIT" in src and "Commit" in src, name


def test_atlas_find_safe_filter(tmp_path, monkeypatch):
    idx = {"skills": [
        {"id": 1, "skill": "captions-good", "description": "arabic captions", "license": "MIT",
         "verdict": "READ_ONLY_OK", "risk_flags": [], "path": "s/1"},
        {"id": 2, "skill": "captions-risky", "description": "captions", "license": "MIT",
         "verdict": "REVIEW_BEFORE_INSTALL", "risk_flags": ["shell"], "path": "s/2"},
        {"id": 3, "skill": "captions-gpl", "description": "captions", "license": "GPL-3.0",
         "verdict": "READ_ONLY_OK", "risk_flags": [], "path": "s/3"}]}
    (tmp_path / "index.json").write_text(json.dumps(idx), encoding="utf-8")
    env = dict(os.environ, DRAGON_ATLAS_ROOT=str(tmp_path), PYTHONIOENCODING="utf-8")
    run = lambda *a: subprocess.run([sys.executable, str(SKILL / "tools/atlas/atlas.py"), "find", "captions", "--json", *a],
                                    capture_output=True, text=True, encoding="utf-8", env=env, timeout=60)
    safe = [x["skill"] for x in json.loads(run().stdout)]
    assert safe == ["captions-good"]
    assert len(json.loads(run("--all").stdout)) == 3


def test_launcher_registers_new_tools():
    src = (SKILL / "scripts" / "dragon.py").read_text(encoding="utf-8")
    assert '"sp": "tools/superpowers/sp.py"' in src and '"atlas": "tools/atlas/atlas.py"' in src
