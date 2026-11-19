"""v1.2 render guard: engines/render/render.cjs against the Nov 2026 black runs.

tests/fixtures/flaky_page.html is a canvas film that draws nothing but black after 40 seeks in one page lifetime, a
deterministic stand-in for headless Chromium going black on heavy canvas pages. With the guard on, render.cjs sees the
black frames, reloads the page and recaptures them; with --no-guard the same render keeps the black run, so the test is
sensitive. Renders are 270x480 to stay fast. Where a black run would touch the end of the film (and so count as a fade,
'edge'), qa.black_runs is called with no head/tail allowance.
"""
import json, re, shutil, subprocess, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from engines import qa  # noqa: E402
from engines.media import exe  # noqa: E402

RENDER = ROOT / "engines" / "render" / "render.cjs"
ENGINE_JS = ROOT / "engines" / "cinema" / "assets" / "engine.js"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "flaky_page.html"
NODE = shutil.which("node")
W, H, FPS = 270, 480, 30
ZERO_ALLOWANCE = ("--allow-black-head", 0, "--allow-black-tail", 0)

# the same module roots as loadPlaywright() in render.cjs (argv[1] = the renderer's folder)
PW_CHECK = ("const p=require('path'),fs=require('fs');const r=[process.env.KOSIF_ROOT,"
            "p.join(process.env.USERPROFILE||process.env.HOME||'','kosif-tool'),process.argv[1]].filter(Boolean)"
            ".map(x=>p.join(x,'node_modules'));try{const pw=require(require.resolve('playwright',{paths:r}));"
            "process.exit(fs.existsSync(pw.chromium.executablePath())?0:1)}catch(e){process.exit(1)}")

# canvas pages whose canvas can read black while the picture is not (must not be retried)
CAPTION_PAGE = """<!doctype html><meta charset=utf-8><style>html,body{margin:0;background:#000;overflow:hidden}
canvas{display:block}#cap{position:fixed;left:0;right:0;top:40%;text-align:center;color:#fff;font:bold 56px sans-serif}</style>
<canvas id=c></canvas><div id=cap>عنوان الفصل</div><script>
const cv=document.getElementById('c'); cv.width=innerWidth; cv.height=innerHeight; const g=cv.getContext('2d');
window.__kosif={duration:1.5,seek(t){ g.fillStyle='#000'; g.fillRect(0,0,cv.width,cv.height); }};
</script>"""
TRANSPARENT_PAGE = """<!doctype html><meta charset=utf-8><style>html,body{margin:0;background:#fff}
canvas{display:block;position:fixed;left:0;top:0}</style><canvas id=c></canvas><script>
const cv=document.getElementById('c'); cv.width=innerWidth; cv.height=innerHeight; const g=cv.getContext('2d');
window.__kosif={duration:1.5,seek(t){ g.clearRect(0,0,cv.width,cv.height); }};
</script>"""
# a WebGL canvas without preserveDrawingBuffer: only readable inside the seek call (falls back to 2D without WebGL)
WEBGL_PAGE = """<!doctype html><meta charset=utf-8><style>html,body{margin:0;background:#000;overflow:hidden}
canvas{display:block}</style><canvas id=c></canvas><script>
const cv=document.getElementById('c'); cv.width=innerWidth; cv.height=innerHeight;
const gl=cv.getContext('webgl',{preserveDrawingBuffer:false}); const g2=gl?null:cv.getContext('2d');
window.__kosif={duration:1,seek(t){
  if(gl){gl.clearColor(0.8,0.3+0.2*Math.sin(t*6),0.2,1);gl.clear(gl.COLOR_BUFFER_BIT);}
  else{g2.fillStyle='#c63';g2.fillRect(0,0,cv.width,cv.height);}
}};
</script>"""


@pytest.fixture(scope="module")
def renderer():
    if not NODE:
        pytest.skip("node not found")
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not on PATH (render.cjs pipes into it)")
    if subprocess.run([NODE, "-e", PW_CHECK, str(RENDER.parent)], capture_output=True, timeout=60).returncode:
        pytest.skip("playwright + chromium not found for render.cjs")
    return RENDER


def page(folder, config=None, name="flaky_page.html"):
    """The fixture page, with an optional window.FLAKY_CONFIG block (see the fixture's header)."""
    text = FIXTURE.read_text(encoding="utf-8")
    if config:
        text = text.replace("<!--config-->", f"<script>window.FLAKY_CONFIG = {json.dumps(config)};</script>")
    p = Path(folder) / name
    p.write_text(text, encoding="utf-8")
    return p


def render(html, out, *args):
    return subprocess.run([NODE, str(RENDER), "--in", str(html), "--out", str(out), "--width", str(W), "--height", str(H),
                           "--fps", str(FPS), *map(str, args)], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=240)


def summary(stdout):
    m = re.search(r"^SUMMARY (.+)$", stdout, re.M)
    assert m, stdout[-1500:]
    return {k: int(v) if v.isdigit() else v for k, v in (kv.split("=", 1) for kv in m.group(1).split())}


def framemd5(path):
    r = subprocess.run([exe("ffmpeg"), "-v", "error", "-i", str(path), "-map", "0:v:0", "-f", "framemd5", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return [ln.rsplit(",", 1)[-1].strip() for ln in r.stdout.splitlines() if ln.strip() and not ln.startswith("#")]


@pytest.fixture(scope="module")
def healthy(renderer, tmp_path_factory):
    """The same film from a page that never fails, rendered the v1.1 way (no guard, no recycling): frame hashes."""
    d = tmp_path_factory.mktemp("healthy")
    out = d / "healthy.mp4"
    r = render(page(d, {"fail_after": 0}), out, "--no-guard", "--recycle", 0)
    assert r.returncode == 0, r.stderr[-1500:]
    return framemd5(out)


def test_guard_recovers_the_black_run(renderer, healthy, tmp_path):
    out = tmp_path / "guarded.mp4"
    r = render(page(tmp_path), out, "--recycle", 0, *ZERO_ALLOWANCE)
    assert r.returncode == 0, r.stderr[-1500:]
    # black from the 41st seek of each page lifetime: frames 40 and 80, each fixed by the first reload
    rec = re.findall(r"^RECOVERED t=([\d.]+) tries=(\d+) via=(\w+)", r.stdout, re.M)
    assert rec == [("1.333", "1", "reload"), ("2.667", "1", "reload")], r.stdout
    assert "BLACK_UNRECOVERED" not in r.stdout
    s = summary(r.stdout)
    assert (s["frames"], s["recovered"], s["unrecovered"], s["reloads"], s["guard"]) == (90, 2, 0, 2, "on")
    runs = qa.black_runs(out, allow_head=0, allow_tail=0)
    assert runs["frames"] == 90 and runs["body"] == [] and runs["runs"] == []
    assert framemd5(out) == healthy  # the recaptured frames are exactly what a healthy page draws


def test_no_guard_keeps_the_black_run(renderer, tmp_path):
    out = tmp_path / "unguarded.mp4"
    r = render(page(tmp_path), out, "--recycle", 0, "--no-guard")
    assert r.returncode == 0, r.stderr[-1500:]
    assert not re.search(r"^(RECOVERED|BLACK_UNRECOVERED)", r.stdout, re.M)
    assert summary(r.stdout)["guard"] == "off"
    runs = qa.black_runs(out, allow_head=0, allow_tail=0)
    assert [(b["start_frame"], b["frames"]) for b in runs["body"]] == [(40, 50)]


def test_normal_page_renders_the_same_frames(renderer, healthy, tmp_path):
    d = tmp_path / "فيلم عادي"  # Arabic folder and file names
    d.mkdir()
    out = d / "فيلم.mp4"
    r = render(page(d, {"fail_after": 0}, name="صفحة.html"), out, "--recycle", 30)  # guard on, reload every 30 frames
    assert r.returncode == 0, r.stderr[-1500:]
    s = summary(r.stdout)
    assert (s["frames"], s["recovered"], s["unrecovered"], s["recycle_reloads"], s["recovery_reloads"]) == (90, 0, 0, 2, 0)
    fc = qa.frame_check(out, expect_duration=3)
    assert fc["frames"] == 90 and fc["frames_ok"], fc
    assert framemd5(out) == healthy  # guard + recycling change nothing on a normal page


def test_strict_exits_3_when_black_stays(renderer, tmp_path):
    out = tmp_path / "strict.mp4"
    # black for t in [1.0, 1.1) in every page lifetime: no fresh page can fix it (default allowances check 0.6..1.5 s)
    cfg = {"fail_after": 0, "black_from": 1.0, "black_to": 1.1}
    r = render(page(tmp_path, cfg), out, "--recycle", 0, "--strict")
    assert r.returncode == 3, (r.returncode, r.stderr[-800:])
    assert re.findall(r"^BLACK_UNRECOVERED t=([\d.]+)", r.stdout, re.M) == ["1.000", "1.033", "1.067"]
    s = summary(r.stdout)
    # the first black frame climbs the whole ladder (reload, new context, new browser); the next two get one reload
    assert (s["recovered"], s["unrecovered"], s["recovery_reloads"]) == (0, 3, 5), r.stdout
    assert qa.frame_check(out, expect_duration=3)["frames"] == 90  # the MP4 is still written, ready for patching


def test_declared_and_edge_black_is_left_alone(renderer, tmp_path):
    out = tmp_path / "declared.mp4"
    cfg = {"fail_after": 0, "head_black": 0.3, "black_from": 1.0, "black_to": 1.2, "declare": True}
    r = render(page(tmp_path, cfg), out, "--recycle", 0)  # default allowances: 0.6 s head, 1.5 s tail
    assert r.returncode == 0, r.stderr[-1500:]
    s = summary(r.stdout)
    assert (s["recovered"], s["unrecovered"], s["reloads"]) == (0, 0, 0), r.stdout
    runs = qa.black_runs(out)  # the black is really there: a fade-in edge and the declared body run
    assert [(x["start_frame"], x["frames"]) for x in runs["edge"]] == [(0, 9)]
    assert [(x["start_frame"], x["frames"]) for x in runs["body"]] == [(30, 6)]


@pytest.mark.parametrize("name,html", [("caption", CAPTION_PAGE), ("transparent", TRANSPARENT_PAGE)])
def test_black_canvas_under_a_visible_picture_is_kept(renderer, tmp_path, name, html):
    p = tmp_path / f"{name}.html"
    p.write_text(html, encoding="utf-8")
    r = render(p, tmp_path / f"{name}.mp4", "--recycle", 0, *ZERO_ALLOWANCE)
    assert r.returncode == 0, r.stderr[-1500:]
    s = summary(r.stdout)
    assert (s["frames"], s["recovered"], s["unrecovered"], s["reloads"]) == (45, 0, 0, 0), r.stdout
    assert 1 <= s["picture_checks"] <= 2  # the picture is decoded now and then (cooldown), not on every frame


def test_webgl_canvas_is_read_inside_the_seek_call(renderer, tmp_path):
    p = tmp_path / "webgl.html"
    p.write_text(WEBGL_PAGE, encoding="utf-8")
    r = render(p, tmp_path / "webgl.mp4", "--recycle", 0, *ZERO_ALLOWANCE)
    assert r.returncode == 0, r.stderr[-1500:]
    s = summary(r.stdout)
    # read after the capture this canvas would look empty on every frame
    assert (s["frames"], s["recovered"], s["unrecovered"], s["picture_checks"]) == (30, 0, 0, 0), r.stdout


@pytest.mark.skipif(NODE is None, reason="node not found")
def test_bad_guard_option_fails_fast(tmp_path):
    r = subprocess.run([NODE, str(RENDER), "--in", str(tmp_path / "x.html"), "--out", str(tmp_path / "x.mp4"),
                        "--recycle", "-1"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    assert r.returncode == 2 and "--recycle needs a number >= 0" in r.stderr


@pytest.mark.skipif(NODE is None, reason="node not found")
def test_js_files_parse_and_engine_cache_is_small():
    for f in (RENDER, ENGINE_JS):
        r = subprocess.run([NODE, "--check", str(f)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
    code = "\n".join(ln.split("//")[0] for ln in ENGINE_JS.read_text(encoding="utf-8").splitlines())  # comments out
    assert "cache.size > 16" in code and ".decode(" not in code and "im.onerror" in code
