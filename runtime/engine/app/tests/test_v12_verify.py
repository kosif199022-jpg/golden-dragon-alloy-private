"""v1.2 delivery gate: `dragon verify` FAILS black frames inside a film, a black tail too long to be a fade, MP3 audio
inside an MP4 and (when the intended duration is given) a video that is frames short. Fades at the very start/end are
info, true peak warns above -1.0 dBTP, and the v1.1 positional API and evidence keys still work.
Every clip is made here with ffmpeg lavfi (270x480, 30 fps): no network, no owner files."""
import json, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dragon import verify as V  # noqa: E402
from engines import qa  # noqa: E402
from engines.media import exe, ffmpeg  # noqa: E402

try:
    exe("ffmpeg"), exe("ffprobe")
except FileNotFoundError:
    pytest.skip("ffmpeg/ffprobe not installed", allow_module_level=True)

BLACK = "drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:enable='{when}'"  # paints whole frames black (Y=16)


def clip(path, d=2.0, vf=None, acodec="aac", a_d=None):
    """testsrc2 picture + 440 Hz tone, 270x480, 30 fps, H.264."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    args = ["-f", "lavfi", "-i", f"testsrc2=s=270x480:d={d}:r=30", "-f", "lavfi", "-i", f"sine=f=440:d={a_d or d}:sample_rate=48000"]
    if vf:
        args += ["-vf", vf]
    ffmpeg(*args, "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", acodec, path)
    return path


def mp3_clip(path):
    """H.264 + MP3 inside .mp4 (played silent on the owner's iPhone); MP2 if this ffmpeg has no LAME."""
    try:
        return clip(path, acodec="libmp3lame")
    except RuntimeError:
        return clip(path, acodec="mp2")


def tone(path, amp, d=1.0):
    ffmpeg("-f", "lavfi", "-i", f"aevalsrc={amp}*sin(2*PI*440*t):s=48000:d={d}", "-c:a", "pcm_s16le", path)
    return path


def test_clean_h264_aac_passes(tmp_path):
    r = V.probe_file(clip(tmp_path / "clean.mp4"))
    assert r["ok"] and r["errors"] == [] and r["info"] == []
    assert r["black"]["frames"] == 60 and r["black"]["body"] == [] and r["black"]["edge"] == []
    assert r["frame_check"]["frames"] == 60 and r["frame_check"]["frames_ok"]
    s = V.line(r)
    assert s.startswith("OK ") and "frames=60" in s and "black=clean" in s and "ERRORS" not in s


def test_black_in_the_middle_fails(tmp_path):
    r = V.probe_file(clip(tmp_path / "mid.mp4", d=4, vf=BLACK.format(when="between(t,1.49,1.88)")))
    assert not r["ok"]
    (run,) = r["black"]["body"]
    assert run["frames"] == 12 and run["start"] == pytest.approx(1.5, abs=0.02) and run["end"] == pytest.approx(1.867, abs=0.02)
    assert "black frames t=1.50-1.87 (12 frames)" in r["errors"]
    s = V.line(r)
    assert s.startswith("FAIL") and "black=1 run" in s and "ERRORS black frames t=1.50-1.87 (12 frames)" in s
    # a 2 s clip keeps a middle too: the fade windows shrink below 6 s
    r = V.probe_file(clip(tmp_path / "mid2.mp4", vf=BLACK.format(when="between(t,0.79,1.18)")))
    assert not r["ok"] and [x["frames"] for x in r["black"]["body"]] == [12] and r["black"]["allow_tail"] < 1.5


def test_many_runs_print_on_one_entry(tmp_path):
    when = "between(t,1.99,2.09)+between(t,3.49,3.79)+between(t,4.99,5.19)"  # 3 + 9 + 6 black frames in a 7 s film
    r = V.probe_file(clip(tmp_path / "runs.mp4", d=7, vf=BLACK.format(when=when)))
    assert not r["ok"] and [x["frames"] for x in r["black"]["body"]] == [3, 9, 6] and len(r["errors"]) == 3
    assert r["black"]["allow_head"] == 0.6 and r["black"]["allow_tail"] == 1.5  # full windows from 6 s up
    s = V.line(r)
    assert "black=3 runs" in s and "black frames t=2.00-2.07 (3), 3.50-3.77 (9), 5.00-5.17 (6): 3 runs, 18 frames" in s


def test_fade_from_black_at_start_passes(tmp_path):
    r = V.probe_file(clip(tmp_path / "fade_in.mp4", vf="fade=t=in:st=0.3:d=0.4"))  # 0.3 s held black, then fade in
    assert r["ok"] and r["errors"] == [] and r["black"]["body"] == []
    (run,) = r["black"]["edge"]
    assert run["start"] == 0 and 9 <= run["frames"] <= 11
    assert r["info"][0].startswith("fade black at start t=0.00-") and "INFO fade black at start" in V.line(r)
    r = V.probe_file(clip(tmp_path / "fade_both.mp4", d=3, vf="fade=t=in:st=0:d=0.3,fade=t=out:st=2.4:d=0.4"))
    assert r["ok"] and len(r["black"]["edge"]) == 2 and r["black"]["body"] == []


def test_black_to_the_end_or_whole_video_fails(tmp_path):
    # the renderer went black at 5 s and stayed black: qa calls it an edge run, verify fails it as too long for a fade
    r = V.probe_file(clip(tmp_path / "tail.mp4", d=8, vf=BLACK.format(when="gte(t,5)")))
    assert not r["ok"] and r["black"]["body"] == [] and r["black"]["edge"][0]["too_long"]
    assert "black at end t=5.00-7.97 (90 frames): longer than 2 s, not a fade" in r["errors"]
    assert "black=1 run" in V.line(r)
    blank = tmp_path / "blank.mp4"
    ffmpeg("-f", "lavfi", "-i", "color=c=black:s=270x480:d=2:r=30", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", blank)
    r = V.probe_file(blank)
    assert not r["ok"] and r["errors"] == ["whole video is black (60 frames)"]


def test_mp3_audio_in_mp4_fails(tmp_path):
    r = V.probe_file(mp3_clip(tmp_path / "mp3.mp4"))
    assert not r["ok"] and r["black"]["body"] == []
    assert any(e.startswith("audio codec mp") and "inside .mp4" in e for e in r["errors"])
    assert "ERRORS audio codec mp" in V.line(r)


def test_intended_duration_gate(tmp_path):
    short = clip(tmp_path / "short.mp4", d=1.9, a_d=2.0)  # 57 frames under 2.0 s of audio: the -shortest incident
    r = V.probe_file(short)  # no intended length: a warning only
    assert r["ok"] and r["frame_check"]["frames"] == 57
    assert any(w.startswith("frames 57 vs ") and "container" in w for w in r["warnings"])
    r = V.probe_file(short, duration=2.0)
    assert not r["ok"] and "frames 57 vs 60 for intended 2 s at 30 fps (-3)" in r["errors"]
    assert "frames=57/60" in V.line(r)
    assert V.probe_file(short, duration=1.9)["ok"]
    assert V.probe_file(clip(tmp_path / "exact.mp4"), duration="2.0")["ok"]  # a CLI string works too


def test_black_false_skips_the_scan(tmp_path, monkeypatch):
    f = clip(tmp_path / "mid.mp4", d=4, vf=BLACK.format(when="between(t,1.49,1.88)"))
    monkeypatch.setattr(qa, "black_runs", lambda *a, **k: pytest.fail("black scan ran with black=False"))
    r = V.probe_file(f, black=False)
    assert r["ok"] and r["black"] == {"skipped": True, "body": [], "edge": []} and "black=skipped" in V.line(r)
    assert V.verify([f], black=False)[0]["ok"]


def test_scan_problems_fail_closed(tmp_path, monkeypatch):
    f = clip(tmp_path / "c.mp4")

    def boom(*a, **k):
        raise RuntimeError("decoder crashed")
    monkeypatch.setattr(qa, "black_runs", boom)
    r = V.probe_file(f)
    assert not r["ok"] and r["errors"] == ["black scan failed: RuntimeError: decoder crashed"]
    monkeypatch.setattr(qa, "black_runs", lambda *a, **k: {"frames": 0, "runs": [], "body": [], "edge": []})
    assert V.probe_file(f)["errors"] == ["black scan read no frames"]
    monkeypatch.setattr(qa, "black_runs", lambda *a, **k: {"frames": 50, "duration_s": 1.667, "runs": [], "body": [], "edge": []})
    r = V.probe_file(f)
    assert r["ok"] and "decoded 50 of 60 frames (damaged stream?)" in r["warnings"]


def test_true_peak_warns_above_minus_one(tmp_path):
    hot = V.probe_file(tone(tmp_path / "hot.wav", 0.91))  # about -0.8 dBTP: the v1.1 limit (-0.5) said nothing
    safe = V.probe_file(tone(tmp_path / "safe.wav", 0.85))  # about -1.4 dBTP
    assert -1.0 < hot["true_peak_dbtp"] < -0.5 and hot["ok"]
    assert any(w.startswith("true peak") and "above -1" in w for w in hot["warnings"])
    assert safe["true_peak_dbtp"] <= -1.0 and not any(w.startswith("true peak") for w in safe["warnings"])
    assert "black" not in hot and "frame_check" not in hot  # audio only: no picture checks


def test_audio_only_duration_and_cover_art(tmp_path):
    wav = tone(tmp_path / "mix.wav", 0.5, d=2)
    assert V.probe_file(wav, duration=2.0)["ok"]
    r = V.probe_file(wav, duration=2.5)
    assert not r["ok"] and r["errors"] == ["duration 2 s vs intended 2.5 s (-0.500 s)"]
    cover, m4a = tmp_path / "cover.png", tmp_path / "song.m4a"
    ffmpeg("-f", "lavfi", "-i", "color=c=red:s=64x64:d=1", "-frames:v", 1, cover)
    ffmpeg("-f", "lavfi", "-i", "sine=d=2", "-i", cover, "-map", "0:a", "-map", "1:v", "-c:a", "aac", "-c:v", "png",
           "-disposition:v", "attached_pic", m4a)
    r = V.probe_file(m4a, duration=2.0)
    assert r["ok"] and "black" not in r and "frame_check" not in r  # cover art is not a picture track


def test_v11_positional_api_and_evidence(tmp_path):
    good, bad = clip(tmp_path / "good.mp4"), mp3_clip(tmp_path / "bad.mp4")
    ev = tmp_path / "ev" / "evidence.json"
    rows = V.verify([good, bad], ev, "270x480")  # the v1.1 call: files, out, expect
    assert [r["ok"] for r in rows] == [True, False]
    doc = json.loads(ev.read_text(encoding="utf-8"))
    v11 = {"path", "exists", "warnings", "bytes", "duration_s", "streams", "width", "height", "codec", "fps",
           "loudness_lufs", "true_peak_dbtp", "video_s", "audio_s", "ok"}
    assert {"verified_at", "files"} <= set(doc) and v11 <= set(doc["files"][0])
    assert {"black", "frame_check", "errors", "info"} <= set(doc["files"][0])
    assert doc["ok"] is False and doc["checks"] == {"expect": "270x480", "duration": None, "black": True, "true_peak_max_dbtp": -1.0}
    assert any(w.startswith("size 270x480 != 1080x1920") for w in V.probe_file(good, "1080x1920")["warnings"])
    missing = V.probe_file(tmp_path / "nope.mp4")
    assert not missing["ok"] and missing["errors"] == ["file not found"] and "ERRORS file not found" in V.line(missing)


def test_arabic_paths(tmp_path):
    f = clip(tmp_path / "أفلام" / "فيلم نظيف.mp4")
    ev = tmp_path / "أدلة" / "تحقق.json"
    rows = V.verify([str(f)], out=ev, duration=2.0)
    assert rows[0]["ok"] and "فيلم نظيف.mp4" in V.line(rows[0])
    assert json.loads(ev.read_text(encoding="utf-8"))["files"][0]["path"] == str(f)


def test_cli_exit_codes(tmp_path, capsys):
    from dragon.cli import main
    good, bad = clip(tmp_path / "good.mp4"), mp3_clip(tmp_path / "bad.mp4")
    with pytest.raises(SystemExit) as e:
        main(["verify", str(good), "--expect", "270x480"])
    assert e.value.code == 0 and any(s.startswith("OK ") and "good.mp4" in s for s in capsys.readouterr().out.splitlines())
    with pytest.raises(SystemExit) as e:
        main(["verify", str(good), str(bad)])
    lines = capsys.readouterr().out.splitlines()
    assert e.value.code == 1 and any(s.startswith("FAIL") and "bad.mp4" in s and "audio codec mp" in s for s in lines)
