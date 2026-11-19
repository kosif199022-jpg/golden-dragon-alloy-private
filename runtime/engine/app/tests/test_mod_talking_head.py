"""engines.talking_head vs the original talking-head-reels scripts, on the same synthetic 7 s talk.

Parity: transcript / cut list / program words byte-identical, project.json identical, mastered loudness and length equal,
validator messages identical, resolved render plan identical, stills pixel-identical, full render SSIM >= 0.98.
The original scripts run unchanged through a tiny shim that only swaps `-filter_complex_script` (removed in ffmpeg 7)
for `-/filter_complex`."""
import json, os, re, shutil, subprocess, sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
ORIG = Path(r"C:\Users\cinde\kosif-tool\.claude\skills\talking-head-reels\scripts")
ARABIC = Path(r"C:\Users\cinde\kosif-tool\fonts\kosif-jumuah\KOSIFJumuah-Bold.ttf")
HAVE_FF = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
try:
    import numpy  # noqa: F401
    HAVE_NP = True
except ImportError:
    HAVE_NP = False

needs_media = pytest.mark.skipif(not (HAVE_FF and HAVE_NP), reason="ffmpeg/ffprobe or numpy missing")
needs_orig = pytest.mark.skipif(not ORIG.is_dir(), reason="original talking-head-reels scripts not on this machine")

SHIM = r'''import os, runpy, sys
S, script = sys.argv[1], sys.argv[2]
sys.path.insert(0, S)
import common
_run = common.run
common.run = lambda cmd, **kw: _run(['-/filter_complex' if c == '-filter_complex_script' else c for c in cmd], **kw)
sys.argv = [os.path.join(S, script)] + sys.argv[3:]
runpy.run_path(sys.argv[0], run_name='__main__')
'''
WORDS = [{"word": "Hello", "start": 0.3, "end": 0.8}, {"word": "there.", "start": 0.8, "end": 1.3},
         {"word": "this", "start": 2.8, "end": 3.8}, {"word": "works", "start": 5.3, "end": 5.8}, {"word": "now", "start": 5.8, "end": 6.3}]


def env():
    e = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONPATH=str(ROOT))
    if ARABIC.exists():
        e["REEL_FONT_FILES"] = str(ARABIC)
    return e


def old(tmp, script, *args, ok=(0,)):
    r = subprocess.run([sys.executable, str(tmp / "shim.py"), str(ORIG), script, *map(str, args)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env(), cwd=tmp)
    assert r.returncode in ok, r.stdout[-1500:] + r.stderr[-1500:]
    return r.stdout


def new(tmp, *args, ok=(0,)):
    r = subprocess.run([sys.executable, "-m", "engines.talking_head", *map(str, args)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env(), cwd=ROOT)
    assert r.returncode in ok, r.stdout[-1500:] + r.stderr[-1500:]
    return r.stdout


def edl(prog, small=True):
    k = 0.5 if small else 1.0
    s = lambda v: round(v * k)
    texts = [{"font": "anton", "text": "HELLO", "t0": 0, "t1": 0.6, "x": s(540), "y": s(1100), "size": s(180)},
             {"font": "sub", "text": "works now", "t0": 2.5, "t1": 3.6, "x": s(540), "y": s(1300), "size": s(70), "anim": "words", "shadow": True}]
    if ARABIC.exists():
        texts.append({"font": "ar", "text": "ده شغال دلوقتي", "t0": 2.4, "t1": prog - 0.06, "x": s(540), "y": s(1000), "size": s(110),
                      "color": "#ED3B22", "anim": "build"})
    return {"name": "t", "W": s(1080), "H": s(1920), "accent": "#ED3B22",
            "fonts": {"serif": "Anton-Regular", "didot": "Anton-Regular", "sub": "Anton-Regular", "ar": "KOSIFJumuah-Bold"},
            "zoom": [[0.0, 1.32, "tight"], [1.32, prog, "wide"]], "logos": {"l": "logos/l.png"},
            "inserts": [
                {"id": "b", "t0": 0.6, "t1": 1.3, "kind": "full", "clips": [{"src": "broll/b1.mp4", "t_in": 0.2, "color": True}],
                 "trans": "whip", "flash": "invert"},
                {"id": "num", "t0": 1.32, "t1": 2.3, "kind": "number", "label": "SAVED", "from": 0, "to": 42, "suffix": "%",
                 "count": [0.1, 0.6], "trans": "zoom"},
                {"id": "bar", "t0": 2.5, "t1": 3.3, "kind": "bar", "layout": "split", "label": "ENERGY", "from": 100, "to": 20,
                 "bgclip": {"src": "broll/b1.mp4"}}],
            "text": texts}


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    """The same talk through the old scripts (old/P) and the new engine (new/P), up to the mastered voice + an EDL."""
    if not (HAVE_FF and HAVE_NP and ORIG.is_dir()):
        pytest.skip("needs ffmpeg, numpy and the original scripts")
    tmp = tmp_path_factory.mktemp("talking_head")
    (tmp / "shim.py").write_text(SHIM, encoding="utf-8")
    speech = "+".join(f"between(t\\,{a}\\,{b})" for a, b in ((0.3, 1.3), (2.8, 3.8), (5.3, 6.3)))
    talk = tmp / "talk.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=25:duration=7", "-f", "lavfi", "-i",
                    f"aevalsrc='0.3*sin(2*PI*220*t)*({speech})+0.001*sin(2*PI*50*t)':s=48000:d=7", "-c:v", "libx264", "-preset", "veryfast",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-shortest", str(talk)], check=True)
    words = tmp / "words.json"
    words.write_text(json.dumps(WORDS), encoding="utf-8")
    O, N = tmp / "old" / "P", tmp / "new" / "P"
    out = {"tmp": tmp, "O": O, "N": N}
    out["old_prepare"] = old(tmp, "prepare_project.py", talk, "--project", O)
    old(tmp, "words_to_asr.py", O, words, "--language", "en")
    out["old_cut"] = old(tmp, "cut_pauses.py", O)
    out["old_master"] = old(tmp, "master_audio.py", O)
    new(tmp, "prepare", talk, "--project", N)
    new(tmp, "words", N, words, "--language", "en")
    out["new_cut"] = new(tmp, "cut", N)
    out["new_master"] = new(tmp, "master", N)
    prog = json.loads((N / "project.json").read_text(encoding="utf-8"))["program_dur"]
    for P in (O, N):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=25:duration=3", "-pix_fmt", "yuv420p",
                        "-c:v", "libx264", str(P / "broll" / "b1.mp4")], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=white:s=200x200,format=rgba", "-frames:v", "1",
                        str(P / "logos" / "l.png")], check=True)
        (P / "edl.json").write_text(json.dumps(edl(prog), ensure_ascii=False, indent=1), encoding="utf-8")
    out["prog"] = prog
    return out


def _cfg(P):
    d = json.loads((P / "project.json").read_text(encoding="utf-8"))
    return {k: v for k, v in d.items() if k not in ("project_dir", "source", "presenter")}


def _lufs(path):
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128", "-f", "null", "-"],
                         capture_output=True, text=True, encoding="utf-8", errors="ignore").stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", err)[-1])


def _dur(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                                capture_output=True, text=True).stdout)


# ------------------------------------------------------------------------------------------------ parity
@needs_media
@needs_orig
def test_prepare_and_cut_parity(runs):
    O, N = runs["O"], runs["N"]
    for f in ("analysis/asr.json", "analysis/cuts.json", "analysis/program_words.json"):
        assert (O / f).read_bytes() == (N / f).read_bytes(), f
    assert _cfg(O) == _cfg(N)
    cuts = json.loads((N / "analysis" / "cuts.json").read_text())
    assert [(c["src_t0"], c["src_t1"]) for c in cuts] == [(0.24, 1.4), (2.64, 3.88), (5.2, 6.56)]
    assert runs["new_cut"].splitlines()[:2] == runs["old_cut"].splitlines()[:2]       # threshold + segment summary lines
    assert abs(_dur(O / "audio" / "program_raw.wav") - _dur(N / "audio" / "program_raw.wav")) <= 0.05


@needs_media
@needs_orig
def test_master_parity(runs):
    O, N = runs["O"], runs["N"]
    a, b = O / "audio" / "program_master.wav", N / "audio" / "program_master.wav"
    assert abs(_lufs(a) - _lufs(b)) <= 0.1 and abs(_lufs(b) + 14) <= 0.5
    assert abs(_dur(a) - _dur(b)) <= 0.05 and abs(_dur(b) - runs["prog"]) <= 0.05
    assert runs["old_master"].splitlines()[-1].split("->")[0] == runs["new_master"].splitlines()[-1].split("->")[0]


@needs_media
@needs_orig
def test_validate_parity(runs):
    tmp, O, N = runs["tmp"], runs["O"], runs["N"]
    assert old(tmp, "validate_edl.py", O / "edl.json") == new(tmp, "validate", N / "edl.json")
    for P in (O, N):                                             # two planted flaws: overlapping insert, unknown font
        bad = json.loads((P / "edl.json").read_text(encoding="utf-8"))
        bad["inserts"].append(dict(bad["inserts"][1], id="clash", t0=bad["inserts"][1]["t0"] + 0.2))
        bad["text"][0]["font"] = "comic"
        (P / "planted.json").write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    o, n = old(tmp, "validate_edl.py", O / "planted.json", ok=(1,)), new(tmp, "validate", N / "planted.json", ok=(1,))
    assert o == n and "overlaps num" in n and "font must be" in n


@needs_media
@needs_orig
def test_plan_parity(runs):
    O, N = runs["O"], runs["N"]
    code = "import json,sys; sys.path.insert(0, sys.argv[1]); from reel_plan import build_plan; print(json.dumps(build_plan(sys.argv[2])))"
    o = subprocess.run([sys.executable, "-c", code, str(ORIG), str(O / "edl.json")], capture_output=True, text=True, env=env(), check=True).stdout
    from engines.talking_head import build_plan
    n = json.dumps(build_plan(str(N / "edl.json")))
    assert json.loads(o.replace(json.dumps(str(O))[1:-1], json.dumps(str(N))[1:-1])) == json.loads(n)


@needs_media
@needs_orig
def test_stills_identical(runs):
    tmp, O, N = runs["tmp"], runs["O"], runs["N"]
    times = ["0.3", "0.9", "1.8", "2.9"]
    old(tmp, "render_reel.py", O / "edl.json", "--stills", *times, "--out-dir", O / "qa" / "s", "--workers", 2, ok=(0, 1))  # its sheet fails on Windows
    new(tmp, "stills", N / "edl.json", *times, "--out-dir", N / "qa" / "s", "--workers", 2)
    assert (N / "qa" / "s" / "sheet.jpg").exists()
    names = sorted(p.name for p in (O / "qa" / "s").glob("f_*.png"))
    assert len(names) == 4 and names == sorted(p.name for p in (N / "qa" / "s").glob("f_*.png"))
    import numpy as np
    for nm in names:
        a, b = (np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", str(P / "qa" / "s" / nm), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                             capture_output=True).stdout, np.uint8).astype(int) for P in (O, N))
        assert a.size and np.abs(a - b).max() <= 1, nm


@needs_media
@needs_orig
def test_render_parity(runs):
    tmp, O, N = runs["tmp"], runs["O"], runs["N"]
    a, b = O / "render" / "old.mp4", N / "render" / "new.mp4"
    old(tmp, "render_reel.py", O / "edl.json", "--out", a, "--workers", 2)
    out = new(tmp, "render", N / "edl.json", "--out", b, "--workers", 2)
    assert "540x960" in out and "audio yes" in out
    assert abs(_dur(a) - _dur(b)) <= 0.05 and abs(_dur(b) - runs["prog"]) <= 0.1
    count = lambda p: subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                                      "stream=nb_read_frames", "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout.strip()
    assert count(a) == count(b) == str(round(runs["prog"] * 25))
    err = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(a), "-i", str(b), "-lavfi", "ssim", "-f", "null", "-"],
                         capture_output=True, text=True, encoding="utf-8", errors="ignore").stderr
    ssim = float(re.search(r"All:([\d.]+)", err).group(1))
    print(f"render SSIM old vs new: {ssim:.5f}")
    assert ssim >= 0.98
    assert abs(_lufs(a) - _lufs(b)) <= 0.1


# ------------------------------------------------------------------------------------------------ units
def test_asr_from_words_segments():
    from engines.talking_head import asr_from_words
    segs = asr_from_words(WORDS)
    assert [s["text"] for s in segs] == [" Hello there.", " this", " works now"]
    assert segs[0]["words"][0] == {"s": 0.3, "e": 0.8, "w": " Hello", "p": 1.0}
    with pytest.raises(ValueError):
        asr_from_words([{"word": "x", "start": 2, "end": 1}])


def test_keep_segments_pauses_and_removals():
    from engines.talking_head import keep_segments, retime
    words = [{"s": 0.3, "e": 1.3, "w": " one."}, {"s": 2.8, "e": 3.8, "w": " two"}, {"s": 5.3, "e": 6.3, "w": " three"}]
    regs = [[0.3, 1.3], [2.8, 3.8], [5.3, 6.3]]
    cuts = keep_segments(regs, words, 7.0, 25)
    # sentence end keeps a 0.22 s pause (0.08 tail + 0.14 head), mid-sentence 0.14 s (0.07 + 0.07)
    assert [(c["src_t0"], c["src_t1"], c["prog_t0"]) for c in cuts] == [(0.24, 1.4, 0.0), (2.64, 3.88, 1.16), (5.2, 6.56, 2.4)]
    cut2 = keep_segments(regs, words, 7.0, 25, remove=[(3.0, 3.4)])
    assert len(cut2) == 4 and cut2[1]["src_t1"] == 3.0 and cut2[2]["src_t0"] == 3.4
    pw = retime(words, cuts)
    assert [w["s"] for w in pw] == [0.06, 1.32, 2.5]


def test_ease_and_ass_helpers():
    from engines.talking_head.text import ass_time, bez, hexcol, ramp, text_lines
    assert ramp(0.5, 0, 1, 0, 10) == 5 and ramp(-1, 0, 1, 3, 9) == 3 and ramp(2, 0, 1, 3, 9) == 9
    assert abs(bez(0.5, 0.8, 0.8) - 0.5) < 1e-6 and bez(0.1, 0.8, 0.8) < 0.1
    assert hexcol("#ED3B22") == "223BED" and ass_time(61.257) == "0:01:01.25"
    assert text_lines("AB\nCD") == [(0, "AB"), (3, "CD")]


def test_font_metrics_anton(tmp_path):
    from engines.talking_head.text import Fonts, faces, libass_factor
    f = faces(ROOT / "engines" / "talking_head" / "data" / "fonts" / "Anton-Regular.ttf")[0]
    assert f["ps"] == "Anton-Regular" and 1.0 < libass_factor(f) < 2.0
    F = Fonts(str(tmp_path))
    assert "Anton-Regular" in F.factor and F.tags("Anton-Regular").startswith("\\b")


def test_data_tables_drive_the_code():
    from engines.talking_head import edl, project
    assert set(edl.STYLE["kinds"]) >= {"full", "band", "number", "cutout"} and edl.STYLE["transitions"]["bulge"] == 0.26
    assert project.CFG["master"]["lufs"] == -14.0 and project.nice_fps(29.97002997) == 29.97
