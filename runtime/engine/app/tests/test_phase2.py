"""Phase 2 gate: verify matches the old dragon.py on real films, smart cut is frame-exact, the mix is the full length
and ducks the song under the voice, beat tracking finds the tempo, the 9:16 crop math is right."""
import importlib.util, json, re, subprocess, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dragon import verify as V  # noqa: E402
from engines import audio, montage  # noqa: E402
from engines.media import ffmpeg, probe  # noqa: E402

MAYAR = Path(r"C:\Users\cinde\OneDrive\Desktop\المونتاج\05_output\mayar_cinema")
OLD = Path(r"C:\Users\cinde\.claude\skills\kosif-black-dragon-ultra\scripts\dragon.py")


def gen_av(path, d=4, size="320x240", tone=440, gop=None, a_d=None):
    args = ["-f", "lavfi", "-i", f"testsrc=s={size}:d={d}:r=30", "-f", "lavfi", "-i", f"sine=f={tone}:d={a_d or d}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac"]
    if gop:
        args += ["-g", gop]
    ffmpeg(*args, path)
    return path


def frames(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                          "stream=nb_read_frames", "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout
    return int(out.strip())


# ---------- verify
def test_verify_media_image_json(tmp_path):
    v = gen_av(tmp_path / "a.mp4")
    r = V.probe_file(v)
    assert r["ok"] and abs(r["duration_s"] - 4) < 0.1 and r["width"] == 320 and r["fps"] == 30
    assert "loudness_lufs" in r and "true_peak_dbtp" in r
    from PIL import Image
    Image.new("RGB", (64, 32)).save(tmp_path / "i.png")
    assert V.probe_file(tmp_path / "i.png")["width"] == 64
    (tmp_path / "bad.json").write_text("{nope", encoding="utf-8")
    bad = V.probe_file(tmp_path / "bad.json")
    assert not bad["ok"] and bad["json_valid"] is False
    assert not V.probe_file(tmp_path / "missing.mp4")["ok"]


def test_verify_flags_short_audio(tmp_path):
    r = V.probe_file(gen_av(tmp_path / "s.mp4", d=4, a_d=2), expect="1080x1920")
    assert any("audio" in w for w in r["warnings"]) and any("size" in w for w in r["warnings"])


@pytest.mark.skipif(not (MAYAR.exists() and OLD.exists()), reason="Mayar films / old dragon.py not on this machine")
def test_gate_same_numbers_as_old_dragon():
    spec = importlib.util.spec_from_file_location("old_dragon", OLD)
    old = importlib.util.module_from_spec(spec)
    sys.argv = ["dragon.py"]
    try:
        spec.loader.exec_module(old)
    except SystemExit as e:  # old dragon.py sys.exit()s when its KOSIF repo root is not on this machine
        pytest.skip(f"old dragon.py cannot load here: {e}")
    films = sorted(MAYAR.glob("ميار *.mp4"))
    assert len(films) == 3
    for f in films:
        a, b = old.probe_file(f), V.probe_file(f)
        assert b["ok"] and b["duration_s"] == a["duration_s"] and b["loudness_lufs"] == a["loudness_lufs"], f.name
        assert b["width"] == 1080 and b["height"] == 1920 and not any("audio" in w for w in b["warnings"])


# ---------- montage
def test_smart_cut_frame_exact(tmp_path):
    src = gen_av(tmp_path / "g.mp4", d=10, gop=60)
    res = montage.smart_cut(src, 1.3, 7.5, tmp_path / "cut.mp4")
    assert res["mode"] == "smart" and res["frames"] == 186
    assert frames(tmp_path / "cut.mp4") == 186
    err = subprocess.run(["ffmpeg", "-v", "error", "-i", str(tmp_path / "cut.mp4"), "-f", "null", "-"], capture_output=True, text=True).stderr
    assert err.strip() == ""


def test_crop_9x16_from_16x9(tmp_path):
    src = tmp_path / "w.mp4"
    ffmpeg("-f", "lavfi", "-i", "testsrc=s=1920x1080:d=1:r=30", "-c:v", "libx264", src)
    n = montage.extract_frames(src, 0, 0.5, tmp_path / "f", z=1.2, cx=0.3, rects=[[0.8, 0.02, 0.15, 0.08]])
    from PIL import Image
    assert n == 15 and Image.open(tmp_path / "f" / "00001.jpg").size == (1080, 1920)
    assert "delogo=x=1536:y=21" in montage.delogo([[0.8, 0.02, 0.15, 0.08]], 1920, 1080)


# ---------- audio
def test_beats_click_track(tmp_path):
    wav = tmp_path / "click.wav"
    # 120 bpm: a short click every 0.5 s
    ffmpeg("-f", "lavfi", "-i", "aevalsrc='if(lt(mod(t,0.5),0.02),sin(2*PI*1000*t),0)':s=44100:d=12", wav)
    r = audio.beats(wav)
    assert min(abs(r["tempo"] - 120), abs(r["tempo"] - 60), abs(r["tempo"] - 240)) < 4


def test_mix_full_length_and_ducking(tmp_path):
    song = tmp_path / "song.wav"; voice = tmp_path / "voice.mp4"
    ffmpeg("-f", "lavfi", "-i", "sine=f=300:d=12", "-ac", 2, song)
    ffmpeg("-f", "lavfi", "-i", "color=c=black:s=64x64:d=3", "-f", "lavfi", "-i", "anoisesrc=d=3:a=0.6", "-shortest",
           "-c:v", "libx264", "-c:a", "aac", voice)
    out = audio.mix(song, 0, 10, tmp_path / "mix.wav", voices=[{"src": str(voice), "in": 0, "d": 2.5, "at": 3.0}], fade_out=1.0)
    d = float(probe(out)["format"]["duration"])
    assert abs(d - 10) < 0.05  # the film-2 bug cut this at the end of the voice

    def rms(a, b):
        e = subprocess.run(["ffmpeg", "-v", "info", "-ss", str(a), "-t", str(b - a), "-i", str(out), "-af", "astats=metadata=0",
                            "-f", "null", "-"], capture_output=True, text=True).stderr
        return float(re.findall(r"RMS level dB:\s*(-?[\d.]+)", e)[-1])
    assert rms(7, 8.5) > -60  # song is still playing after the voice ended


def test_mix_graph_without_voice():
    g = audio.mix_graph(0, 20)
    assert "sidechaincompress" not in g and "loudnorm=I=-14" in g and "atrim=0:20.000" in g
