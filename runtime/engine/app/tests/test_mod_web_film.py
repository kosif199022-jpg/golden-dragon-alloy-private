"""Module port gate: engines/web_film vs the original kosif-web-film skill.
Same plan in -> same plan/check JSON and the same page out; rendered with the OLD renderer (tools/render_html.cjs) and the
NEW one (engines/render/render.cjs) the films have the same frame count and duration and SSIM >= 0.98 or VMAF >= 95."""
import json, os, re, shutil, subprocess, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
KOSIF = Path(os.environ.get("KOSIF_ROOT", Path.home() / "kosif-tool"))
OLD = KOSIF / ".claude" / "skills" / "kosif-web-film" / "scripts"
OLD_RENDER = KOSIF / "tools" / "render_html.cjs"
PLAYWRIGHT = KOSIF / "node_modules" / "playwright"
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "KOSIF_PLAYWRIGHT": str(PLAYWRIGHT)}

need_old = pytest.mark.skipif(not OLD.is_dir(), reason="original kosif-web-film skill missing")
need_render = pytest.mark.skipif(shutil.which("node") is None or not PLAYWRIGHT.is_dir() or not OLD_RENDER.is_file(),
                                 reason="node / playwright / old renderer missing")


def run(*cmd, cwd=None):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding="utf-8", errors="replace", env=ENV, cwd=cwd)
    return r


def old(script, *args):
    return run(sys.executable, OLD / script, *args)


def new(*args):
    return run(sys.executable, "-m", "engines.web_film", *args, cwd=ROOT)


def stream(path):
    out = run("ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
              "stream=nb_read_frames,width,height:format=duration", "-of", "json", path).stdout
    j = json.loads(out)
    return int(j["streams"][0]["nb_read_frames"]), float(j["format"]["duration"])


def similarity(a, b):
    err = run("ffmpeg", "-hide_banner", "-i", a, "-i", b, "-lavfi", "[0][1]ssim;[0][1]libvmaf", "-f", "null", "-").stderr
    ssim = float(re.search(r"SSIM .*All:([\d.]+)", err).group(1))
    vmaf = float(re.search(r"VMAF score: ([\d.]+)", err).group(1))
    return ssim, vmaf


def assert_parity(new_mp4, old_mp4, fps=30):
    (fn, dn), (fo, do) = stream(new_mp4), stream(old_mp4)
    ssim, vmaf = similarity(new_mp4, old_mp4)
    print(f"parity {Path(new_mp4).name}: frames {fn}/{fo} duration {dn:.3f}/{do:.3f} SSIM {ssim:.5f} VMAF {vmaf:.2f}")
    assert fn == fo and abs(dn - do) <= 1 / fps + 1e-6
    assert ssim >= 0.98 or vmaf >= 95


def render_old(html, out, w, h, duration=None):
    args = ["node", OLD_RENDER, "--in", html, "--out", out, "--mode", "seek", "--width", w, "--height", h, "--fps", 30, "--offline"]
    r = run(*args, *(["--duration", duration] if duration else []))
    assert r.returncode == 0, r.stderr[-800:]


def render_new(html, out, w, h, duration=None):
    from engines.web_film import render_page
    render_page(html, out, width=w, height=h, fps=30, duration=duration)


@need_old
def test_page_film_plan_check_and_scaffold_match(tmp_path):
    args = ["فيلم تجربة", "--duration", "2", "--require", "اسم الشركة", "--ratio", "4:5"]
    assert old("web_film.py", "plan", *args, "--out", tmp_path / "o.json").returncode == 0
    assert new("plan", *args, "--out", tmp_path / "n.json").returncode == 0
    assert json.loads((tmp_path / "o.json").read_text("utf-8")) == json.loads((tmp_path / "n.json").read_text("utf-8"))
    # empty concept -> both fail with the same errors
    o, n = old("web_film.py", "check", tmp_path / "o.json", "--json"), new("check", tmp_path / "n.json", "--json")
    assert o.returncode == n.returncode == 1 and json.loads(o.stdout) == json.loads(n.stdout)
    plan = json.loads((tmp_path / "n.json").read_text("utf-8"))
    plan.update(concept="x</script>", width=270, height=480)
    for i, s in enumerate(plan["shots"]):
        s["text"] = "كلمة عربية هنا" if i % 2 else "Hello <b>world</b>"
    (tmp_path / "p.json").write_text(json.dumps(plan, ensure_ascii=False), "utf-8")
    assert old("web_film.py", "scaffold", tmp_path / "p.json", "--out", tmp_path / "o.html").returncode == 0
    assert new("scaffold", tmp_path / "p.json", "--out", tmp_path / "n.html").returncode == 0
    assert (tmp_path / "o.html").read_bytes() == (tmp_path / "n.html").read_bytes()
    o = old("web_film.py", "check", tmp_path / "p.json", "--html", tmp_path / "o.html", "--json")
    n = new("check", tmp_path / "p.json", "--html", tmp_path / "n.html", "--json")
    assert json.loads(o.stdout) == json.loads(n.stdout) == {"ok": True, "errors": []}
    bad = (tmp_path / "n.html").read_text("utf-8").replace("window.__kosif.seek(0);", "setTimeout(()=>Math.random(),Date.now());")
    (tmp_path / "bad.html").write_text(bad, "utf-8")
    o = old("web_film.py", "check", tmp_path / "p.json", "--html", tmp_path / "bad.html", "--json")
    n = new("check", tmp_path / "p.json", "--html", tmp_path / "bad.html", "--json")
    assert json.loads(o.stdout) == json.loads(n.stdout) and len(json.loads(n.stdout)["errors"]) == 3


@need_old
def test_world_film_example_check_beats_review_match(tmp_path):
    assert old("world_film.py", "example", "--out", tmp_path / "o" / "w.json").returncode == 0
    assert new("world", "example", "--out", tmp_path / "n" / "w.json").returncode == 0
    po, pn = (json.loads((tmp_path / d / "w.json").read_text("utf-8")) for d in ("o", "n"))
    for p in (po, pn):
        p["fonts"][0].pop("from")  # where the font comes from: kosif-tool's shared fonts vs this package's assets
    assert po == pn
    for cmd in (["check", "--json"], ["beats"], ["review"]):
        o = old("world_film.py", cmd[0], tmp_path / "o" / "w.json", *cmd[1:])
        n = new("world", cmd[0], tmp_path / "n" / "w.json", *cmd[1:])
        assert o.returncode == n.returncode and o.stdout == n.stdout, cmd
    # a broken plan fails both the same way (hero list, text said aloud, gap, unused object)
    p = json.loads((tmp_path / "n" / "w.json").read_text("utf-8"))
    p["beats"][0]["hero"] = ["egypt", "book"]
    p["beats"][1]["start"] = 3.2
    p["objects"].append({"id": "t_said", "kind": "text", "text": "كتاب واحد", "size": 400})
    p["beats"][1]["text"] = "t_said"
    (tmp_path / "bad.json").write_text(json.dumps(p, ensure_ascii=False), "utf-8")
    o, n = old("world_film.py", "check", tmp_path / "bad.json", "--json"), new("world", "check", tmp_path / "bad.json", "--json")
    assert o.returncode == n.returncode == 1 and o.stdout == n.stdout


@need_old
@need_render
def test_page_film_render_parity(tmp_path):
    assert new("plan", "parity", "--duration", "1.5", "--out", tmp_path / "p.json").returncode == 0
    plan = json.loads((tmp_path / "p.json").read_text("utf-8"))
    plan.update(concept="parity", width=270, height=480)
    for i, s in enumerate(plan["shots"]):
        s["text"] = "التنين الأسود" if i % 2 else "Black Dragon"
    (tmp_path / "p.json").write_text(json.dumps(plan, ensure_ascii=False), "utf-8")
    old("web_film.py", "scaffold", tmp_path / "p.json", "--out", tmp_path / "o.html")
    new("scaffold", tmp_path / "p.json", "--out", tmp_path / "n.html")
    render_old(tmp_path / "o.html", tmp_path / "old.mp4", 270, 480)
    render_new(tmp_path / "n.html", tmp_path / "new.mp4", 270, 480)
    assert stream(tmp_path / "new.mp4")[0] == 45
    assert_parity(tmp_path / "new.mp4", tmp_path / "old.mp4")


@need_old
@need_render
def test_world_film_render_parity(tmp_path):
    for d, fn in (("o", old), ("n", new)):
        args = ("world_film.py", "example") if d == "o" else ("world", "example")
        assert fn(*args, "--out", tmp_path / d / "w.json").returncode == 0
        p = json.loads((tmp_path / d / "w.json").read_text("utf-8"))
        p["format"].update(width=270, height=480)
        (tmp_path / d / "w.json").write_text(json.dumps(p, ensure_ascii=False), "utf-8")
    assert old("world_film.py", "build", tmp_path / "o" / "w.json", "--out", tmp_path / "o" / "film.html").returncode == 0
    assert new("world", "build", tmp_path / "n" / "w.json", "--out", tmp_path / "n" / "film.html").returncode == 0
    assert (tmp_path / "n" / "fonts" / "Cairo.ttf").read_bytes() == (tmp_path / "o" / "fonts" / "Cairo.ttf").read_bytes()
    render_old(tmp_path / "o" / "film.html", tmp_path / "old.mp4", 270, 480, duration=1.5)
    render_new(tmp_path / "n" / "film.html", tmp_path / "new.mp4", 270, 480, duration=1.5)
    assert_parity(tmp_path / "new.mp4", tmp_path / "old.mp4")
