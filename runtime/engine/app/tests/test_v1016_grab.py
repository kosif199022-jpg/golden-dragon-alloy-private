"""v10.16: video-grabber bundled + guarded `tool grab` bridge (offline only, no downloads)."""
import hashlib
import json
import os
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "tools" / "grab" / "bridge.py"
SKILL = ROOT / "skills" / "video-grabber"


def cli(*args):
    return subprocess.run([sys.executable, str(BRIDGE), *args], capture_output=True, text=True, encoding="utf-8",
                          env=dict(os.environ, PYTHONIOENCODING="utf-8"), timeout=90)


def test_doctor_json_exit0():
    r = cli("doctor")
    assert r.returncode == 0
    d = json.loads(r.stdout)
    for k in ("yt_dlp", "aria2c", "ffmpeg", "ffprobe", "playwright_importable", "chromium_installed"):
        assert k in d
    assert d["skill_present"] is True


@pytest.mark.parametrize("url,fam", [
    ("https://www.youtube.com/watch?v=abc", "youtube"),
    ("https://youtu.be/abc", "youtube"),
    ("https://www.tiktok.com/@u/video/1", "tiktok"),
    ("https://www.instagram.com/reel/xyz/", "instagram"),
    ("https://www.facebook.com/watch?v=1", "facebook"),
    ("https://x.com/u/status/1", "x"),
    ("https://vimeo.com/123", "vimeo"),
    ("https://cdn.example.com/a/clip.mp4", "direct"),
    ("https://cdn.example.com/live/master.m3u8?tok=1", "m3u8"),
    ("https://cdn.example.com/v/manifest.mpd", "mpd"),
    ("https://example.com/some/page", "other"),
])
def test_plan_classification(url, fam):
    r = cli("plan", url)
    assert r.returncode == 0
    d = json.loads(r.stdout)
    assert d["family"] == fam and d["network"] is False
    tools = [s["tool"] for s in d["steps"]]
    if fam in ("youtube", "tiktok", "instagram", "facebook", "x", "vimeo", "direct"):
        assert tools[0] == "fetch"
    else:
        assert tools[0] == "grab"
    if fam in ("youtube", "other"):
        assert "ghost" in tools


def test_plan_masks_credentials():
    d = json.loads(cli("plan", "https://user:secret@example.com/v.mp4").stdout)
    assert "secret" not in json.dumps(d)


def test_help_exit0():
    r = cli("--help")
    assert r.returncode == 0 and "doctor" in r.stdout and "--section" in r.stdout


def test_passthrough_help_grab_ghost_proxies():
    for args in (["URL", "--help"], ["ghost", "--help"], ["proxies", "--help"]):
        r = cli(*args)
        assert r.returncode == 0, (args, r.stderr)
        assert "usage" in r.stdout.lower()


def test_source_hashes_match():
    src = json.loads((SKILL / "SOURCE_VIDEO_GRABBER.json").read_text(encoding="utf-8"))
    assert src["files"]
    for rel, want in src["files"].items():
        assert hashlib.sha256((SKILL / rel).read_bytes()).hexdigest() == want, rel
    assert not any("__pycache__" in k or ".pytest_cache" in k for k in src["files"])
    assert "C:\\Users" not in json.dumps(src)


def test_guards(tmp_path):
    for args in (["URL", "--update"], ["URL", "--tor"], ["URL", "--free-proxies"],
                 ["URL", "--proxy", "http://u:p@1.2.3.4:80"], ["URL", "--proxy-file", str(tmp_path / "nope.txt")],
                 ["proxies", "check", "--free"], ["proxies", "newnym"], ["proxies", "check"]):
        r = cli(*args)
        assert r.returncode == 2 and '"ok": false' in r.stderr, args
    existing = tmp_path / "a.png"
    existing.write_bytes(b"x")
    r = cli("ghost", "shot", "https://example.com", str(existing))
    assert r.returncode == 2 and existing.read_bytes() == b"x"


def test_bundled_offline_tests_run():
    """The skill's own offline tests (browser tests need playwright/chromium and are skipped if absent)."""
    tests = [str(p) for p in (SKILL / "tests").rglob("test_*.py")]
    assert tests
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *tests],
                       capture_output=True, text=True, encoding="utf-8", timeout=600,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8"))
    out = r.stdout + r.stderr
    if r.returncode != 0 and ("playwright" in out.lower() or "chromium" in out.lower()):
        pytest.skip("bundled tests need playwright/chromium: " + out[-200:])
    assert r.returncode == 0, out[-1500:]
