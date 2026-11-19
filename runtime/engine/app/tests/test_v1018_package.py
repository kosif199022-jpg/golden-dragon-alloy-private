"""v10.18.0 package: stamp + checksum + zip the skill to a folder, verify against the manifest.

The roundtrip tests run on a synthetic tree in tmp_path (they never touch the real Desktop or the real
skill tree). One subprocess test confirms `tool package --check` is wired and stdlib-only.
"""
import importlib.util
import json
import subprocess
import sys
import zipfile
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2]
TOOL = SKILL / "tools" / "package" / "package.py"
spec = importlib.util.spec_from_file_location("bd_package", TOOL)
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)


def _fake_skill(tmp: Path, version="9.9.9"):
    (tmp / "app" / "dragon").mkdir(parents=True)
    (tmp / "app" / "data").mkdir(parents=True)
    (tmp / "app" / "dragon" / "__init__.py").write_text(
        f'"""x"""\n__version__ = "{version}"  # trailing comment\n', encoding="utf-8")
    (tmp / "app" / "data" / "library.json").write_text(
        json.dumps({"schema": "black-dragon.library.v1", "version": version, "packs": []}, ensure_ascii=False),
        encoding="utf-8")
    (tmp / "SKILL.md").write_text(
        f"# Black Dragon — التنين الأسود (v{version}، 2026-01-01)\n\nbody\n",
        encoding="utf-8")
    # a file with an Arabic name and a nested one, plus cruft that must be skipped
    (tmp / "app" / "اقرأني.md").write_text("hi", encoding="utf-8")
    (tmp / "app" / "dragon" / "__pycache__").mkdir()
    (tmp / "app" / "dragon" / "__pycache__" / "x.pyc").write_text("junk", encoding="utf-8")
    return tmp


def _point_module_at(tmp: Path):
    P.SKILL = tmp
    P.MANIFEST = tmp / "MANIFEST_SHA256.json"
    P.SUMS = tmp / "SHA256SUMS.txt"
    P.INIT = tmp / "app" / "dragon" / "__init__.py"
    P.LIBRARY_JSON = tmp / "app" / "data" / "library.json"
    P.SKILL_MD = tmp / "SKILL.md"


def test_manifest_excludes_cruft_and_integrity_files(tmp_path, monkeypatch):
    _fake_skill(tmp_path)
    _point_module_at(tmp_path)
    n = P.write_manifest("9.9.9")
    man = json.loads(P.MANIFEST.read_text(encoding="utf-8"))
    assert man["schema"] == "black-dragon.sha256-manifest.v1"
    assert man["version"] == "9.9.9"
    files = set(man["files"])
    assert "SKILL.md" in files and "app/اقرأني.md" in files
    assert "MANIFEST_SHA256.json" not in files and "SHA256SUMS.txt" not in files
    assert not any(".pyc" in f or "__pycache__" in f for f in files)
    assert n == len(files)
    assert len(P.SUMS.read_text(encoding="utf-8").strip().splitlines()) == n


def test_check_passes_then_detects_tamper(tmp_path):
    _fake_skill(tmp_path)
    _point_module_at(tmp_path)
    P.write_manifest("9.9.9")
    assert P.verify_against_manifest() == 0
    (tmp_path / "SKILL.md").write_text("tampered", encoding="utf-8")
    assert P.verify_against_manifest() == 1


def test_set_version_stamps_all_markers(tmp_path):
    _fake_skill(tmp_path, version="9.9.9")
    _point_module_at(tmp_path)
    P.set_version("10.18.0")
    assert '__version__ = "10.18.0"' in P.INIT.read_text(encoding="utf-8")
    assert json.loads(P.LIBRARY_JSON.read_text(encoding="utf-8"))["version"] == "10.18.0"
    assert "(v10.18.0، " in P.SKILL_MD.read_text(encoding="utf-8")
    assert P.read_version() == "10.18.0"


def test_build_zip_roundtrip_and_integrity(tmp_path):
    _fake_skill(tmp_path)
    _point_module_at(tmp_path)
    P.write_manifest("9.9.9")
    out = tmp_path / "out"
    zp = P.build_zip("9.9.9", out)
    assert zp.name == "black-dragon-v9.9.9.zip" and zp.exists()
    with zipfile.ZipFile(zp) as z:
        assert z.testzip() is None
        names = z.namelist()
    assert all(nm.startswith("black-dragon/") for nm in names)
    assert "black-dragon/SKILL.md" in names
    assert "black-dragon/MANIFEST_SHA256.json" in names
    assert not any(".pyc" in nm for nm in names)


def test_check_subprocess_is_wired_and_stdlib_only(tmp_path):
    env = {"PYTHONPATH": ""}
    r = subprocess.run([sys.executable, "-I", "-X", "utf8", str(TOOL), "--check"],
                       capture_output=True, text=True, encoding="utf-8", cwd=str(tmp_path))
    assert r.returncode in (0, 1), r.stderr
    data = json.loads(r.stdout)
    assert "manifest_version" in data and "files_on_disk" in data
