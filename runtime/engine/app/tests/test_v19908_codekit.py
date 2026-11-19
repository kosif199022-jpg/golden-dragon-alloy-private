"""v1990.8: codekit, the 12 video-from-code tools (4 lines) as one toolbox. Offline and fast."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT.parent
KIT = SKILL / "tools" / "codekit"
SCRIPT = KIT / "codekit.py"
VENDORED = {
    "three": ("three/three.min.js", "three/LICENSE"),
    "anime": ("animejs/anime.umd.min.js", "animejs/LICENSE.md"),
    "mojs": ("mojs/mo.umd.js", "mojs/LICENSE.md"),
    "rough": ("roughjs/rough.js", "roughjs/LICENSE"),
}
LINES = {
    1: ["remotion", "hyperframes", "motion-canvas"],
    2: ["three", "manim", "rough"],
    3: ["gsap", "anime", "mojs"],
    4: ["whisperx", "auto-editor", "ffmpeg"],
}
BANNED = ("Date.now", "Math.random(", "setInterval", "setTimeout", "performance.now", "requestAnimationFrame",
          "http://", "https://")


def run(*a, cwd=None):
    return subprocess.run([sys.executable, str(SCRIPT), *a], capture_output=True, text=True,
                          encoding="utf-8", cwd=cwd)


def test_status_lists_exactly_12_tools_in_4_lines():
    r = run("status", "--json")
    assert r.returncode == 0, r.stderr
    d = json.loads(r.stdout)
    assert d["count"] == 12 and len(d["tools"]) == 12
    assert {x["line"]: x["tools"] for x in d["lines"]} == LINES
    for t in d["tools"]:
        assert t["name"] and t["use"] and t["licence"] and t["how"], t["id"]
        assert isinstance(t["found"], bool)
    by = {t["id"]: t for t in d["tools"]}
    for name in VENDORED:
        assert by[name]["found"] and "vendored" in by[name]["how"] and by[name]["version"]
    assert "faster-whisper" in by["whisperx"]["equivalent"]
    assert "mono" in by["remotion"]["equivalent"]
    assert "gsap.com/standard-license" in by["gsap"]["licence"]


def test_status_text_runs_from_an_empty_folder(tmp_path):
    r = run("status", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    for name in ("Remotion", "HyperFrames", "Motion Canvas", "Three.js", "Manim", "Rough.js",
                 "GSAP", "anime.js", "mo.js", "WhisperX", "auto-editor", "FFmpeg"):
        assert name in r.stdout, name
    assert not list(tmp_path.iterdir())  # probing writes nothing


def test_map_prints_four_lines_and_the_caveats():
    r = run("map")
    assert r.returncode == 0, r.stderr
    for n in (1, 2, 3, 4):
        assert f"الخط {n}" in r.stdout
    assert r.stdout.count("•") == 12
    assert "--margin" in r.stdout and "3 أشخاص" in r.stdout and "مش مفتوح المصدر" in r.stdout


def test_vendored_files_have_licences_and_gsap_is_not_vendored():
    for name, (lib, lic) in VENDORED.items():
        assert (KIT / "vendor" / lib).stat().st_size > 10_000, lib
        assert "MIT" in (KIT / "vendor" / lic).read_text(encoding="utf-8")[:200], lic
    assert not [p for p in KIT.rglob("*") if p.is_file() and "gsap" in p.name.lower() and p.suffix == ".js"]
    for p in (KIT / "vendor").rglob("*.js"):
        assert "greensock" not in p.read_text(encoding="utf-8", errors="replace")[:3000].lower(), p
    assert sum(p.stat().st_size for p in KIT.rglob("*") if p.is_file()) < 2_500_000


@pytest.mark.parametrize("name", sorted(VENDORED))
def test_browser_demo_is_seek_driven_and_self_contained(tmp_path, name):
    r = run("demo", name, str(tmp_path), "--title", "تجربة <b>")
    assert r.returncode == 0, r.stdout + r.stderr
    pages = list(tmp_path.glob("*.html"))
    assert len(pages) == 1
    text = pages[0].read_text(encoding="utf-8")
    assert "window.__kosif = {duration:" in text and "seek: async t" in text
    assert "window.__kosifReady = true" in text
    assert "تجربة &lt;b&gt;" in text and "{{TITLE}}" not in text
    assert "1080px" in text and "1920px" in text
    for bad in BANNED:
        assert bad not in text, bad
    lib = Path(VENDORED[name][0]).name
    assert f'src="./{lib}"' in text
    assert (tmp_path / lib).read_bytes() == (KIT / "vendor" / VENDORED[name][0]).read_bytes()
    assert (tmp_path / f"{lib}.LICENSE.txt").is_file()


def test_timeline_demos_never_autoplay():
    demos = KIT / "demos"
    assert "autoplay: false" in (demos / "anime_demo.html").read_text(encoding="utf-8")
    assert "tl.seek(" in (demos / "anime_demo.html").read_text(encoding="utf-8")
    assert "setProgress(" in (demos / "mojs_demo.html").read_text(encoding="utf-8")
    gsap = (demos / "gsap_demo.html").read_text(encoding="utf-8")
    assert "paused: true" in gsap and "tl.time(" in gsap
    assert "seed:" in (demos / "rough_demo.html").read_text(encoding="utf-8")
    for page in demos.glob("*.html"):
        text = page.read_text(encoding="utf-8")
        assert ".play(" not in text and ".replay(" not in text, page.name
        for bad in BANNED:
            assert bad not in text, (page.name, bad)


def test_command_demos_print_and_manim_writes_a_scene(tmp_path):
    r = run("demo", "manim", str(tmp_path))
    assert r.returncode == 0 and (tmp_path / "manim_scene.py").is_file()
    assert "manim -qh" in r.stdout
    compile((tmp_path / "manim_scene.py").read_text(encoding="utf-8"), "manim_scene.py", "exec")
    out = tmp_path / "none"
    r = run("demo", "auto-editor", str(out))
    assert r.returncode == 0 and "--margin 0.3sec" in r.stdout and "audio:threshold=0.04" in r.stdout
    for name, word in (("remotion", "create-video"), ("hyperframes", "hyperframes init"),
                       ("motion-canvas", "@motion-canvas"), ("whisperx", "word_timestamps=True"),
                       ("ffmpeg", "-crf 17")):
        r = run("demo", name, str(out))
        assert r.returncode == 0 and word in r.stdout, name
    assert not out.exists()
    assert run("demo", "nope", str(out)).returncode == 2


def test_install_without_run_executes_nothing(tmp_path):
    dest = tmp_path / "pkgs"
    r = run("install", "all", "--dest", str(dest), cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert "مفيش أي أمر اتنفّذ" in r.stdout
    assert not dest.exists() and not list(tmp_path.iterdir())
    r = run("install", "whisperx", cwd=tmp_path)
    assert r.returncode == 0 and "pip install whisperx" in r.stdout and "--allow-large" in r.stdout
    r = run("install", "motion-canvas", "--dest", str(dest), cwd=tmp_path)
    assert "--prefix" in r.stdout and "@motion-canvas/core" in r.stdout and not dest.exists()
    assert run("install", "nope").returncode == 2


def test_vendor_gsap_copies_from_an_installed_copy_only(tmp_path):
    r = run("vendor-gsap", str(tmp_path / "a"), "--from", str(tmp_path / "missing"), cwd=tmp_path)
    assert r.returncode == 1 and not (tmp_path / "a").exists()
    fake = tmp_path / "node_modules" / "gsap"
    (fake / "dist").mkdir(parents=True)
    (fake / "package.json").write_text('{"version": "9.9.9"}', encoding="utf-8")
    (fake / "dist" / "gsap.min.js").write_text("/* stand-in */", encoding="utf-8")
    r = run("vendor-gsap", str(tmp_path / "b"), "--from", str(tmp_path), cwd=tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (tmp_path / "b" / "gsap.min.js").read_text(encoding="utf-8") == "/* stand-in */"
    assert "gsap.com/standard-license" in r.stdout and "9.9.9" in r.stdout


def test_codekit_is_stdlib_only():
    import ast
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            mods.add((node.module or "").split(".")[0])
    assert mods <= {"__future__", "argparse", "html", "json", "os", "re", "shutil", "subprocess", "sys",
                    "pathlib", "importlib"}, mods


def test_fusion_demo_drives_five_libraries_from_one_clock():
    from pathlib import Path as _P
    root = _P(__file__).resolve().parents[2]
    html = (root / "tools" / "codekit" / "demos" / "fusion_demo.html").read_text(encoding="utf-8")
    for lib in ("three.min.js", "gsap.min.js", "anime.umd.min.js", "mo.umd.js", "rough.js"):
        assert lib in html, lib
    for call in ("g.time(t)", "a.seek(t*1000)", "m.setProgress(t/D)", "renderer.render(scene,camera)", "rc.rectangle("):
        assert call in html, call
    assert "window.__kosif" in html and "Date.now" not in html and "setInterval" not in html and "Math.random(" not in html
    assert (root / "references" / "VIDEO12_DIRECTOR.md").is_file()
