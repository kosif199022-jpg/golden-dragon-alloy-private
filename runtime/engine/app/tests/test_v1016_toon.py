"""v10.16: the toon tool (cartoon / anime look) is wired, guarded, never overwrites, and really converts when models exist."""
import hashlib
import json
import os
import pathlib
import subprocess
import sys

import pytest

SKILL = pathlib.Path(__file__).resolve().parents[2]
TOON = SKILL / "tools" / "toon" / "toon.py"


def cli(*args, timeout=300):
    return subprocess.run([sys.executable, str(TOON), *args], capture_output=True, text=True, encoding="utf-8",
                          env=dict(os.environ, PYTHONIOENCODING="utf-8"), timeout=timeout)


def doctor():
    r = cli("doctor")
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_doctor_json():
    d = doctor()
    assert d["schema"] == "black-dragon.toon.v1"
    assert set(d["styles"]) == {"3d", "ai3d", "hayao", "shinkai", "paint"}
    for k in ("ffmpeg", "venv_python_present", "python_modules", "ready_styles"):
        assert k in d


def test_styles_list():
    r = cli("styles")
    assert r.returncode == 0
    assert set(json.loads(r.stdout)["styles"]) == {"3d", "ai3d", "hayao", "shinkai", "paint"}


def test_help_recommends_preview():
    r = cli("--help")
    assert r.returncode == 0 and "--seconds 3" in r.stdout
    assert "overwrite" in cli("video", "--help").stdout


def test_setup_is_dry_run():
    r = cli("setup")
    assert r.returncode == 0
    j = json.loads(r.stdout)
    assert j["dry_run"] is True and "never downloads" in j["would_download"]


def test_no_overwrite_and_missing_input(tmp_path):
    src = tmp_path / "in.png"
    src.write_bytes(b"x")
    dst = tmp_path / "out.png"
    dst.write_bytes(b"keep")
    r = cli("image", str(src), str(dst), "--style", "hayao")
    assert r.returncode != 0 and "refusing to overwrite" in r.stderr
    assert dst.read_bytes() == b"keep"
    r = cli("image", str(tmp_path / "nope.png"), str(tmp_path / "o2.png"))
    assert r.returncode != 0 and not (tmp_path / "o2.png").exists()
    r = cli("video", str(src), str(tmp_path / "o.mp4"))          # wrong input type
    assert r.returncode != 0


def test_source_hashes():
    j = json.loads((SKILL / "tools" / "toon" / "SOURCE_TOON.json").read_text(encoding="utf-8"))
    assert len(j["files"]) == 2
    for f in j["files"]:
        assert f["original"].startswith("%USERPROFILE%")
        copy = SKILL / "tools" / "toon" / f["copy"]
        assert hashlib.sha256(copy.read_bytes()).hexdigest() == f["sha256_copy"]
        assert len(f["sha256_original"]) == 64
    assert not list((SKILL / "tools" / "toon").rglob("*.onnx"))


def test_cartoon_tool_untouched():
    assert (SKILL / "tools" / "cartoon" / "README.md").is_file()


@pytest.mark.parametrize("style", ["hayao", "3d"])
def test_real_tiny_image_arabic_folder(tmp_path, style):
    if style not in doctor()["ready_styles"]:
        pytest.skip(f"{style} models missing")
    from PIL import Image, ImageDraw
    work = tmp_path / "مجلد عربي"
    work.mkdir()
    im = Image.new("RGB", (256, 256), (120, 170, 230))
    d = ImageDraw.Draw(im)
    d.ellipse((80, 70, 176, 190), fill=(230, 180, 150))
    d.rectangle((0, 200, 256, 256), fill=(60, 140, 70))
    src = work / "صورة.png"
    im.save(src)
    before = hashlib.sha256(src.read_bytes()).hexdigest()
    dst = work / "ناتج.png"
    r = cli("image", str(src), str(dst), "--style", style)
    assert r.returncode == 0, r.stderr
    j = json.loads(r.stdout)
    assert j["ok"] and dst.is_file() and dst.stat().st_size > 1000
    assert Image.open(dst).size == (256, 256)
    assert hashlib.sha256(src.read_bytes()).hexdigest() == before
    assert cli("image", str(src), str(dst), "--style", style).returncode != 0   # second run refuses
