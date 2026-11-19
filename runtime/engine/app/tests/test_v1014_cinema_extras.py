"""v10.14: cinema extras (song-map, sheets, skill-atlas) are real CLIs: --help exits 0, nothing is overwritten."""
import hashlib
import os
import pathlib
import shutil
import subprocess
import sys

import pytest

SKILL = pathlib.Path(__file__).resolve().parents[2]
TOOLS = SKILL / "tools" / "cinema_extras"
HAS_FF = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def run(name, *args, env=None):
    e = dict(os.environ, PYTHONIOENCODING="utf-8", **(env or {}))
    return subprocess.run([sys.executable, str(TOOLS / f"{name}.py"), *args], capture_output=True, text=True,
                          encoding="utf-8", env=e, timeout=300)


@pytest.mark.parametrize("name", ["song_map", "sheets", "skill_atlas"])
def test_help_exits_zero_and_writes_nothing(name, tmp_path):
    atlas = SKILL / "references" / "SKILL_ATLAS.md"
    before = hashlib.sha256(atlas.read_bytes()).hexdigest()
    r = run(name, "--help")
    assert r.returncode == 0 and "usage" in r.stdout.lower()
    assert hashlib.sha256(atlas.read_bytes()).hexdigest() == before


def test_skill_atlas_summary_does_not_write(tmp_path):
    atlas = SKILL / "references" / "SKILL_ATLAS.md"
    before = hashlib.sha256(atlas.read_bytes()).hexdigest()
    r = run("skill_atlas", env={"DRAGON_REPOS": str(tmp_path / "none")})
    assert r.returncode == 0 and "skills" in r.stdout
    assert hashlib.sha256(atlas.read_bytes()).hexdigest() == before


def test_skill_atlas_out_needs_force(tmp_path):
    out = tmp_path / "a.md"; out.write_text("keep")
    assert run("skill_atlas", "--out", str(out), env={"DRAGON_REPOS": str(tmp_path / "none")}).returncode == 2
    assert out.read_text() == "keep"


def test_bundled_atlas_has_no_home_paths():
    text = (SKILL / "references" / "SKILL_ATLAS.md").read_text(encoding="utf-8")
    assert str(pathlib.Path.home()) not in text


def test_no_owner_paths_in_cinema_code():
    for f in TOOLS.glob("*.py"):
        src = f.read_text(encoding="utf-8")
        assert "C:\\Users\\" not in src and "\\bdc_work" not in src, f.name


@pytest.mark.skipif(not HAS_FF, reason="ffmpeg unavailable")
def test_sheets_builds_and_keeps_existing(tmp_path):
    clip = tmp_path / "c.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x568:r=30:d=2",
                    "-pix_fmt", "yuv420p", str(clip)], check=True, timeout=60)
    r = run("sheets", str(clip), "--out", str(tmp_path / "s"), "--n", "4", "--cols", "2")
    assert r.returncode == 0, r.stderr
    sheet = tmp_path / "s" / "c.jpg"
    assert sheet.stat().st_size > 1000
    stamp = sheet.stat().st_mtime_ns
    assert "--force" in run("sheets", str(clip), "--out", str(tmp_path / "s")).stdout
    assert sheet.stat().st_mtime_ns == stamp


def test_sheets_missing_clip_exit_2(tmp_path):
    assert run("sheets", "nope-id", "--out", str(tmp_path)).returncode == 2


@pytest.mark.skipif(not HAS_FF, reason="ffmpeg unavailable")
def test_song_map_beats_json(tmp_path):
    pytest.importorskip("librosa")
    wav = tmp_path / "s.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=220:d=6", str(wav)], check=True, timeout=60)
    r = run("song_map", str(wav), "--window", "2")
    assert r.returncode == 0, r.stderr
    import json
    data = json.loads((tmp_path / "s.beats.json").read_text(encoding="utf-8"))
    assert abs(data["duration"] - 6.0) < 0.1 and "tempo" in data
    assert "kept existing" in run("song_map", str(wav)).stdout
