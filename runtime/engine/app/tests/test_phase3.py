"""Phase 3: the piped renderer turns a seekable page into an MP4 with the exact frame count, and stills work.
(The full gate - Mayar film 1 rebuilt on the new system, VMAF 99.46 vs the original - is recorded in REBUILD_PLAN.md.)"""
import shutil, subprocess, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
RENDER = ROOT / "engines" / "render" / "render.cjs"
PAGE = """<!doctype html><meta charset=utf-8><style>html,body{margin:0}</style><canvas id=c width=320 height=568></canvas><script>
const g=document.getElementById('c').getContext('2d');
window.__kosif={duration:1,seek:async t=>{g.fillStyle=`hsl(${t*360},70%,50%)`;g.fillRect(0,0,320,568);g.fillStyle='#fff';
g.font='40px sans-serif';g.fillText(t.toFixed(2),20,300);}};</script>"""


@pytest.mark.skipif(shutil.which("node") is None or subprocess.run(
    ["node", "-e", "try{require.resolve('playwright');process.exit(0)}catch(e){process.exit(1)}"],
    cwd=str(RENDER.parent), capture_output=True).returncode != 0,
    reason="Node Playwright runtime missing (optional renderer dependency)")
def test_render_exact_frames_and_stills(tmp_path):
    html = tmp_path / "p.html"; html.write_text(PAGE, encoding="utf-8")
    out = tmp_path / "p.mp4"
    r = subprocess.run(["node", str(RENDER), "--in", str(html), "--out", str(out), "--width", "320", "--height", "568", "--fps", "30"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    n = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                        "stream=nb_read_frames,width,height,color_space,color_primaries,color_transfer", "-of", "json", str(out)],
                       capture_output=True, text=True).stdout
    import json
    s = json.loads(n)["streams"][0]
    assert (s["width"], s["height"], s["nb_read_frames"]) == (320, 568, "30")
    assert s["color_space"] == s["color_primaries"] == s["color_transfer"] == "bt709"
    r = subprocess.run(["node", str(RENDER), "--in", str(html), "--stills", "0.25,0.75", "--stills-dir", str(tmp_path / "s"),
                        "--width", "320", "--height", "568"], capture_output=True, text=True)
    assert r.returncode == 0 and len(list((tmp_path / "s").glob("still_*.png"))) == 2
