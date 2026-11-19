"""Module port gate: engines/editorial vs the original editorial-film-edit skill.
The old skill ships layer modules only (no CLI, no wiring), so the parity harness is: the same EDL and the same player
wired to the ORIGINAL modules + reel.css and rendered with the OLD renderer (tools/render_html.cjs), against the NEW package
page rendered with engines/render/render.cjs. Same frame count and duration, SSIM >= 0.98 or VMAF >= 95."""
import json, os, re, shutil, subprocess, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
KOSIF = Path(os.environ.get("KOSIF_ROOT", Path.home() / "kosif-tool"))
OLD = KOSIF / ".claude" / "skills" / "editorial-film-edit" / "implementation" / "browser-reference"
OLD_RENDER = KOSIF / "tools" / "render_html.cjs"
PLAYWRIGHT = KOSIF / "node_modules" / "playwright"
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "KOSIF_PLAYWRIGHT": str(PLAYWRIGHT)}

from engines import editorial as E  # noqa: E402

need_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg missing")
need_render = pytest.mark.skipif(shutil.which("node") is None or not PLAYWRIGHT.is_dir() or not OLD_RENDER.is_file()
                                 or not OLD.is_dir(), reason="node / playwright / old skill or renderer missing")


def run(*cmd):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding="utf-8", errors="replace", env=ENV, cwd=ROOT)


@pytest.fixture(scope="module")
def job(tmp_path_factory):
    d = tmp_path_factory.mktemp("مونتاج_editorial")  # Arabic path on purpose
    r = run(sys.executable, "-m", "engines.editorial", "example", "--out", d)
    assert r.returncode == 0, r.stderr
    return d / "edit.edl.json"


@need_ffmpeg
def test_check_and_build(job, tmp_path):
    r = run(sys.executable, "-m", "engines.editorial", "check", job, "--json")
    res = json.loads(r.stdout)
    assert r.returncode == 0 and res["ok"] and res["stats"] == {"shots": 3, "splits": 1, "caption_words": 6, "type_layers": 4, "frames": 60}
    bad = E.load(job)
    bad["shots"][1]["t0"] = 0.9
    bad["shots"][2]["fx"]["grade"] = "sepia"
    bad["type"][0]["enter"] = "explode"
    bad["captions"]["chunks"][0]["words"][2]["t0"] = 0.2
    bad["media"]["insert"] = {"path": "media/missing.png"}
    errs = E.check(bad, job.parent)["errors"]
    for want in ("shot 1 starts at 0.9", "grade 'sepia'", "enter must be", "appears before", "file not found"):
        assert any(want in e for e in errs), (want, errs)
    page = E.build(job, tmp_path / "page" / "film.html")
    text = page.read_text("utf-8")
    assert "window.__kosif" in text and "import " not in re.sub(r"//.*", "", text.split("<script>")[-1])
    assert len(list((tmp_path / "page" / "media" / "presenter").glob("*.jpg"))) == 60
    assert (tmp_path / "page" / "media" / "insert.png").is_file()


@need_ffmpeg
@need_render
def test_render_parity(job, tmp_path):
    old_page = E.build(job, tmp_path / "old" / "film.html", modules_dir=OLD)
    r = run("node", OLD_RENDER, "--in", old_page, "--out", tmp_path / "old.mp4", "--mode", "seek", "--width", 270, "--height", 480,
            "--fps", 30, "--offline")
    assert r.returncode == 0, r.stderr[-800:]
    r = run(sys.executable, "-m", "engines.editorial", "render", job, "--out", tmp_path / "new.mp4")
    assert r.returncode == 0, r.stderr[-800:]
    v = json.loads(r.stdout.strip().splitlines()[-1])
    assert v["ok"] and v["frames"] == 60
    counts = []
    for f in ("new.mp4", "old.mp4"):
        j = json.loads(run("ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                           "stream=nb_read_frames:format=duration", "-of", "json", tmp_path / f).stdout)
        counts.append((int(j["streams"][0]["nb_read_frames"]), float(j["format"]["duration"])))
    err = run("ffmpeg", "-hide_banner", "-i", tmp_path / "new.mp4", "-i", tmp_path / "old.mp4", "-lavfi",
              "[0][1]ssim;[0][1]libvmaf", "-f", "null", "-").stderr
    ssim = float(re.search(r"SSIM .*All:([\d.]+)", err).group(1))
    vmaf = float(re.search(r"VMAF score: ([\d.]+)", err).group(1))
    (fn, dn), (fo, do) = counts
    print(f"editorial parity: frames {fn}/{fo} duration {dn:.3f}/{do:.3f} SSIM {ssim:.5f} VMAF {vmaf:.2f}")
    assert fn == fo == 60 and abs(dn - do) <= 1 / 30 + 1e-6
    assert ssim >= 0.98 or vmaf >= 95
    # the film is not blank: the grade/grain pipeline really ran (WebGL) — frames differ over time
    sig = run("ffmpeg", "-hide_banner", "-i", tmp_path / "new.mp4", "-vf", "signalstats,metadata=print:key=lavfi.signalstats.YAVG",
              "-f", "null", "-").stderr
    yavg = [float(x) for x in re.findall(r"YAVG=([\d.]+)", sig)]
    assert len(yavg) == 60 and max(yavg) - min(yavg) > 5 and min(yavg) > 10
