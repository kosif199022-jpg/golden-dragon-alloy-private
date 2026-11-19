"""v1.2 exact length (ROADMAP C1): the engines that used to mux with -shortest now end on exactly round(duration * fps)
video frames, whatever the length of their audio (a short score used to cut the film; AAC priming cut 3 frames).
Every file is made here with ffmpeg lavfi or raw frames at tiny sizes in tmp_path: no network, no owner files."""
import json, os, subprocess, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from engines.media import exe, ffmpeg, probe  # noqa: E402

try:
    exe("ffmpeg"), exe("ffprobe")
except FileNotFoundError:
    pytest.skip("ffmpeg/ffprobe not installed", allow_module_level=True)

np = pytest.importorskip("numpy")


def frames(path):
    """Decoded video frames (not the container's count)."""
    r = subprocess.run([exe("ffprobe"), "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                        "stream=nb_read_frames", "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return int(r.stdout.strip().split(",")[0])


def audio_s(path):
    """Seconds of decoded audio (samples / rate): works for MP4 (edit list applied) and MKV (no stream duration)."""
    raw = subprocess.run([exe("ffmpeg"), "-v", "error", "-i", str(path), "-map", "0:a:0", "-ac", "1", "-ar", "48000",
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    return len(raw) / 2 / 48000


def tone(path, d, rate=48000):
    ffmpeg("-f", "lavfi", "-i", f"sine=f=440:d={d}:sample_rate={rate}", "-c:a", "pcm_s16le", path)
    return Path(path)


def test_no_shortest_left_in_engines():
    """The ROADMAP acceptance: -shortest survives only in comments/docstrings (and the _slerp keyword)."""
    hits = []
    for p in (ROOT / "engines").rglob("*.py"):
        for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            code = ln.split("#", 1)[0]
            if '"-shortest"' in code or "'-shortest'" in code:
                hits.append(f"{p.relative_to(ROOT)}:{i}")
    assert hits == []


def test_fit_audio_pads_and_trims_to_the_sample(tmp_path):
    from engines.deliver import fit_audio
    for d_in in (0.7, 2.6):  # shorter and longer than the target
        out = tmp_path / f"fit{d_in}.wav"
        ffmpeg("-i", tone(tmp_path / f"t{d_in}.wav", d_in), "-af", fit_audio(1.5), out)
        a = next(s for s in probe(out)["streams"] if s["codec_type"] == "audio")
        assert round(float(a["duration"]) * 48000) == 72000  # 1.5 s at 48 kHz, to the sample


@pytest.mark.parametrize("seconds,n", [(2.0, 60), (1.9, 57)])
def test_dragon_montage_test_clip_exact(tmp_path, seconds, n):
    from engines.dragon_montage.common import make_test_clip
    p = make_test_clip(tmp_path / "clip.mp4", seconds, size="270x480")
    assert frames(p) == n == round(seconds * 30)
    assert audio_s(p) == pytest.approx(seconds, abs=0.03)


def test_shadow_theatre_film_exact(tmp_path):
    import engines.shadow_theatre as S
    spec = json.loads(S.DEMO.read_text("utf-8"))
    spec.update(width=270, height=480, duration=1.6)
    spec["scenes"] = spec["scenes"][:3]
    for s, (a, b) in zip(spec["scenes"], [(0, 0.5), (0.5, 1.1), (1.1, 1.6)]):
        s.update(start=a, end=b, fade_in=0.15, fade_out=0.15)
    out = tmp_path / "shadow.mp4"
    r = S.render_film(spec, out, progress=None)
    assert r["audio"] is True
    assert frames(out) == round(1.6 * 30) == 48
    assert audio_s(out) == pytest.approx(1.6, abs=0.03)


def test_matrices_render_mp4_exact(tmp_path, monkeypatch):
    """The browser render is replaced by an ffmpeg clip one frame short; the score WAV is longer than the film."""
    from engines.matrices import scene
    real = subprocess.run

    def fake_node(cmd, **kw):
        if cmd and cmd[0] == "node":
            out = cmd[cmd.index("--out") + 1]
            ffmpeg("-f", "lavfi", "-i", "testsrc2=s=128x72:r=30:d=1.9667", "-frames:v", 59, "-c:v", "libx264",
                   "-preset", "ultrafast", "-pix_fmt", "yuv420p", out)
            return subprocess.CompletedProcess(cmd, 0, "VIDEO ok\n", "")
        return real(cmd, **kw)

    monkeypatch.setattr(scene.subprocess, "run", fake_node)
    wav = tone(tmp_path / "score.wav", 2.4)
    mp4, _ = scene.render_mp4(tmp_path / "scene.html", tmp_path / "exp.mp4", 30, 2.0, wav, 128, 72)
    assert frames(mp4) == 60 and audio_s(mp4) == pytest.approx(2.0, abs=0.03)
    assert not (tmp_path / "exp.video.mp4").exists()


@pytest.mark.parametrize("audio_d", [2.0, 4.5])  # program audio shorter and longer than the 3.2 s of frames
def test_talking_head_render_exact(tmp_path, monkeypatch, audio_d):
    """The real concat + final mux of talking_head.render; the frame renderer (_setup/_run) is replaced by two lavfi
    segments of 40 frames each at 25 fps (the full pipeline needs ffmpeg 7 for its -/filter_complex script)."""
    import importlib
    R = importlib.import_module("engines.talking_head.render")  # the package re-exports a render() function
    fps, nfr = 25, 80
    audio = tone(tmp_path / "program.wav", audio_d)
    cache = tmp_path / "cache"
    cache.mkdir()
    plan = {"P": str(tmp_path), "name": "t", "audio": str(audio), "fps": fps, "dur": nfr / fps}
    monkeypatch.setattr(R, "_setup", lambda edl: (plan, str(cache), str(cache / "plan.json"), [], nfr))

    def fake_run(jobs, workers):
        segs = []
        for job in jobs:
            seg = job[3]
            f0, f1 = job[2]
            ffmpeg("-f", "lavfi", "-i", f"testsrc2=s=90x160:r={fps}", "-frames:v", f1 - f0, "-c:v", "libx264",
                   "-preset", "ultrafast", "-pix_fmt", "yuv420p", seg)
            segs.append(seg)
        return segs
    monkeypatch.setattr(R, "_run", fake_run)
    r = R.render({}, out=str(tmp_path / "reel.mp4"), workers=2)
    assert r["frames"] == nfr and frames(r["out"]) == nfr == round(r["frames"] / fps * fps)
    assert audio_s(r["out"]) == pytest.approx(nfr / fps, abs=0.03)


# ---------------------------------------------------------------- cards/lib fixture writers

def _rgb(n, w=32, h=18):
    return [np.full((h, w, 3), (i * 7) % 255, np.uint8) for i in range(n)]


@pytest.mark.parametrize("audio_d", [1.0, 3.0])  # a score shorter and longer than the 2 s of frames
def test_cards_writers_exact(tmp_path, audio_d):
    from engines.cards.lib import fam_w3_09, fam_w3_06, photo_video_footage, fam_music_beat_sound, fam_w3_05
    wav = tone(tmp_path / "a.wav", audio_d)
    outs = [fam_w3_09.write_mp4(tmp_path / "w309.mp4", _rgb(60), 30, audio=wav),
            fam_w3_06.write_video(tmp_path / "w306.mp4", _rgb(60), 30, audio=wav),
            photo_video_footage.write_video(tmp_path / "pvf.mkv", _rgb(60), 30, audio=wav),
            photo_video_footage.write_video(tmp_path / "pvf.mp4", _rgb(60), 30, codec="libx264", audio=wav),
            fam_music_beat_sound.write_video(tmp_path / "mbs.mp4", lambda i: _rgb(1, 160, 90)[0], 60, 30, audio=wav),
            fam_w3_05.write_video(tmp_path / "w305.mp4", lambda i: _rgb(1, 160, 90)[0], 60, 30, audio=wav)]
    for p in outs:
        assert frames(p) == 60, p.name
        assert audio_s(p) == pytest.approx(2.0, abs=0.03), p.name


def test_cards_lavfi_and_copy_muxes_exact(tmp_path):
    from engines.cards.lib import formats_platforms, fam_transitions_cuts_a, fam_transitions_cuts_b
    p = formats_platforms.testclip(tmp_path, "fp.mp4", dur=1.5, audio=True)
    assert frames(p) == 45 and audio_s(p) == pytest.approx(1.5, abs=0.03)
    seg = fam_transitions_cuts_b._colour_seg(tmp_path / "seg.mp4", "red", 1.2, size="64x36")
    assert frames(seg) == 36 and audio_s(seg) == pytest.approx(1.2, abs=0.03)
    v = tmp_path / "v.mp4"
    ffmpeg("-f", "lavfi", "-i", "testsrc2=s=64x36:r=30:d=2", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", v)
    for short in (True, False):
        wav = tone(tmp_path / f"m{short}.wav", 1.1 if short else 2.9, 44100)
        a = fam_transitions_cuts_a.mux(tmp_path, v, wav, f"a{short}")
        b = fam_transitions_cuts_b._mux(tmp_path, v, wav, f"b{short}.mkv")
        for p in (a, b):
            assert frames(p) == 60, p.name
            assert audio_s(p) == pytest.approx(2.0, abs=0.01), p.name
