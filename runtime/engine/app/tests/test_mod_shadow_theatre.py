"""Module port gate: engines/shadow_theatre vs the original kosif-shadow-theatre skill.
Same scene in -> the same library/check output, pixel-identical frames, a byte-identical synth score, and rendered films
with the same frame count and duration and SSIM >= 0.98 or VMAF >= 95."""
import importlib, json, os, re, shutil, subprocess, sys
from pathlib import Path
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
KOSIF = Path(os.environ.get("KOSIF_ROOT", Path.home() / "kosif-tool"))
OLD = KOSIF / ".claude" / "skills" / "kosif-shadow-theatre"
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}
pytestmark = pytest.mark.skipif(not (OLD / "scripts" / "shadow_engine.py").is_file(), reason="original shadow theatre skill missing")

from engines import shadow_theatre as N  # noqa: E402


def run(*cmd, cwd=ROOT):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding="utf-8", errors="replace", env=ENV, cwd=cwd)


def old_cli(*a):
    return run(sys.executable, OLD / "scripts" / "shadow_theatre.py", *a)


def new_cli(*a):
    return run(sys.executable, "-m", "engines.shadow_theatre", *a)


@pytest.fixture(scope="module")
def old_mod():
    sys.path.insert(0, str(OLD / "scripts"))
    try:
        yield importlib.import_module("shadow_engine"), importlib.import_module("shadow_theatre")
    finally:
        sys.path.remove(str(OLD / "scripts"))


def all_props_spec():
    """Every prop, costume, cycle, iris shape and a keyed spotlight, so each drawing path is compared."""
    props = ["sun", "crescent", "bird", "palm", "skyline", "dunes", "waves", "lantern", "hand", "circle", "heart", "star", "arch", "foliage"]
    actors = [{"type": "prop", "shape": p, "params": {"chain": 0.3} if p == "lantern" else {},
               "keys": [{"t": 0, "x": 0.1 + 0.06 * i, "y": 0.2 + 0.05 * (i % 6), "scale": 0.08, "rot": 10 * i},
                        {"t": 1, "x": 0.15 + 0.06 * i, "rot": 10 * i + 30, "ease": "out"}]} for i, p in enumerate(props)]
    for i, (c, cyc) in enumerate(zip(["plain", "dress", "child", "elder"], ["walk", "sway", "wave", "flutter"])):
        actors.append({"type": "human", "costume": c, "height": 0.3, "cycle": {"type": cyc, "period": 0.9},
                       "keys": [{"t": 0, "x": 0.2 + 0.2 * i, "pose": "stand", "facing": -1 if i % 2 else 1},
                                {"t": 1.2, "x": 0.25 + 0.2 * i, "pose": ["lunge", "dance_arc", "frond", "hull"][i], "depth": 0.4 * (i % 2)}]})
    scenes = []
    for k, (shape, bd) in enumerate(zip(["circle", "heart", "star", "arch"], ["dawn-green", "crimson-spot", "teal-mist", "moon-indigo"])):
        scenes.append({"start": k * 0.5, "end": (k + 1) * 0.5, "backdrop": bd, "actors": actors, "fade_in": 0.2, "fade_out": 0.1,
                       "iris": {"shape": shape, "keys": [{"t": 0, "scale": 0.3}, {"t": 0.5, "scale": 2.0}]},
                       "spot": {"x": 0.5, "y": 0.4, "r": 0.3, "r_keys": [{"t": 0, "scale": 0.2}, {"t": 0.5, "scale": 0.5}]}})
    return {"width": 270, "height": 480, "fps": 30, "duration": 2.0, "seed": 5, "lamp": {"x": 0.5}, "scenes": scenes}


def short_demo(tmp_path):
    """The demo scene squeezed to 1.6 s at 270x480 (three short chapters taken from its first three)."""
    spec = json.loads(N.DEMO.read_text("utf-8"))
    spec.update(width=270, height=480, duration=1.6)
    spec["scenes"] = spec["scenes"][:3]
    for s, (a, b) in zip(spec["scenes"], [(0, 0.5), (0.5, 1.1), (1.1, 1.6)]):
        s.update(start=a, end=b, fade_in=0.15, fade_out=0.15)
    p = tmp_path / "short.json"
    p.write_text(json.dumps(spec, ensure_ascii=False), "utf-8")
    return p


def test_library_and_check_match(tmp_path):
    assert old_cli("library").stdout == new_cli("library").stdout
    o, n = old_cli("check", OLD / "scenes" / "lantern-keeper.json"), new_cli("check", N.DEMO)
    assert o.returncode == n.returncode == 0 and o.stdout == n.stdout
    bad = json.loads(N.DEMO.read_text("utf-8"))
    bad["scenes"][1]["start"] = 5.0
    bad["scenes"][2]["actors"][0]["costume"] = "robot"
    bad["scenes"][3]["actors"].append({"type": "prop", "shape": "dragon"})
    bad["scenes"][0]["actors"][1]["keys"][0]["pose"] = "flying"
    for s in bad["scenes"]:
        s.pop("memorable", None)
    (tmp_path / "bad.json").write_text(json.dumps(bad, ensure_ascii=False), "utf-8")
    o, n = old_cli("check", tmp_path / "bad.json"), new_cli("check", tmp_path / "bad.json")
    assert o.returncode == n.returncode == 1 and o.stdout == n.stdout and o.stdout.count("FAIL") >= 5


def test_frames_pixel_identical(old_mod):
    OE, OT = old_mod
    demo = dict(OT.load_spec(OLD / "scenes" / "lantern-keeper.json"), width=270, height=480)
    for spec, times in ((demo, [0.4, 2.0, 5.2, 6.0, 8.3, 11.0, 13.7, 16.0, 18.5, 21.6]), (all_props_spec(), [0.05, 0.3, 0.7, 1.1, 1.45, 1.9])):
        o, n = OE.ShadowRenderer(spec), N.ShadowRenderer(spec)
        for t in times:
            assert np.array_equal(o.render(t).rgb, n.render(t).rgb), t
    assert OT.check_spec(OT.load_spec(OLD / "scenes" / "lantern-keeper.json")) == N.check_spec(N.load_spec(N.DEMO)) == []


def test_synth_score_identical(old_mod, tmp_path):
    _, OT = old_mod
    spec = dict(N.load_spec(N.DEMO), duration=4.0, cues=[1.5])
    spec["scenes"] = [dict(s, start=s["start"] / 6, end=s["end"] / 6) for s in spec["scenes"]][:3]
    OT.synth_score(spec, tmp_path / "o.wav")
    N.synth_score(spec, tmp_path / "n.wav")
    assert (tmp_path / "o.wav").read_bytes() == (tmp_path / "n.wav").read_bytes()


def probe_frames(path):
    j = json.loads(run("ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                       "stream=nb_read_frames,color_primaries:format=duration", "-of", "json", path).stdout)
    return int(j["streams"][0]["nb_read_frames"]), float(j["format"]["duration"]), j["streams"][0].get("color_primaries")


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg missing")
def test_render_parity(tmp_path):
    scene = short_demo(tmp_path)
    o = old_cli("render", scene, "--out", tmp_path / "old.mp4", "--no-audio", "--force")
    n = new_cli("render", scene, "--out", tmp_path / "new.mp4", "--no-audio", "--force")
    assert o.returncode == 0 and n.returncode == 0, o.stderr + n.stderr
    jo, jn = json.loads(o.stdout.strip().splitlines()[-1]), json.loads(n.stdout.strip().splitlines()[-1])
    assert {k: v for k, v in jo.items() if k != "out"} == {k: v for k, v in jn.items() if k != "out"}
    (fn, dn, prim), (fo, do, _) = probe_frames(tmp_path / "new.mp4"), probe_frames(tmp_path / "old.mp4")
    err = run("ffmpeg", "-hide_banner", "-i", tmp_path / "new.mp4", "-i", tmp_path / "old.mp4", "-lavfi",
              "[0][1]ssim;[0][1]libvmaf", "-f", "null", "-").stderr
    ssim = float(re.search(r"SSIM .*All:([\d.]+)", err).group(1))
    vmaf = float(re.search(r"VMAF score: ([\d.]+)", err).group(1))
    print(f"shadow parity: frames {fn}/{fo} duration {dn:.3f}/{do:.3f} SSIM {ssim:.5f} VMAF {vmaf:.2f}")
    assert fn == fo == 48 and abs(dn - do) <= 1 / 30 + 1e-6 and prim == "bt709"
    assert ssim >= 0.98 or vmaf >= 95
    # with the score: an AAC track of the film's length
    n = new_cli("render", scene, "--out", tmp_path / "score.mp4", "--force")
    assert n.returncode == 0 and json.loads(n.stdout.strip().splitlines()[-1])["audio"] is True
    assert not (tmp_path / "score.score.wav").exists()
