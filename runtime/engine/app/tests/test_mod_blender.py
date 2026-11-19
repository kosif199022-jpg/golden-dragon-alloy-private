"""Blender engine: headless bpy code runs and returns results; a scene renders to PNG and to a tagged MP4."""
import json, subprocess, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from engines import blender as B

try:
    B.exe(); HAVE = True
except FileNotFoundError:
    HAVE = False
pytestmark = pytest.mark.skipif(not HAVE, reason="Blender not installed")


def test_run_code_returns_results():
    r = B.run_code("import bpy, json\nprint('@@' + json.dumps({'objects': len(bpy.data.objects), 'v': bpy.app.version_string}))")
    assert r["results"] and r["results"][0]["objects"] >= 0 and r["results"][0]["v"].startswith(("4", "5"))


def test_script_error_raises():
    with pytest.raises(RuntimeError):
        B.run_code("raise SystemExit(3)")


def test_demo_still_and_video(tmp_path):
    png = tmp_path / "s.png"
    B.demo(str(png), frames=12, res="135x240")
    assert png.stat().st_size > 1000
    mp4 = tmp_path / "v.mp4"
    B.demo(str(mp4), frames=12, res="136x240")
    s = json.loads(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                                   "stream=nb_read_frames,width,height,color_primaries", "-of", "json", str(mp4)],
                                  capture_output=True, text=True).stdout)["streams"][0]
    assert (s["width"], s["height"], s["nb_read_frames"], s["color_primaries"]) == (136, 240, "12", "bt709")
