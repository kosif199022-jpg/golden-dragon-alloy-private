"""v1.2 delivery: `mux` gives an exact length without -shortest (it ended a film 3 frames short) and turns non-AAC audio
into AAC (MP3 inside MP4 played silent on the owner's iPhone); `patch_black` clones the last good frame over black runs
inside a film; the new CLI commands; and the cinema engine's final mux.
Every file is made here with ffmpeg lavfi (180x320, 30 fps) in tmp_path: no network, no owner files."""
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

from engines import deliver, qa  # noqa: E402
from dragon import verify as V  # noqa: E402

FPS, SIZE = 30, "180x320"
# frame N has mean luma 30+N; frames 0-3 are black (a fade from black) and so are 90-95 (the bug: black inside the film)
RAMP = "geq=lum='if(lt(N,4)+between(N,90,95),16,30+N)':cb=128:cr=128"


def video(path, d, preset="ultrafast", vf=None):
    """testsrc2 picture only, H.264. ultrafast has no B-frames; medium has them."""
    args = ["-f", "lavfi", "-i", f"testsrc2=s={SIZE}:d={d}:r={FPS}"] + (["-vf", vf] if vf else [])
    ffmpeg(*args, "-c:v", "libx264", "-preset", preset, "-pix_fmt", "yuv420p", path)
    return Path(path)


def tone(path, d, codec, rate=48000):
    ffmpeg("-f", "lavfi", "-i", f"sine=f=440:d={d}:sample_rate={rate}", "-c:a", codec, path)
    return Path(path)


def mp3(path, d):
    """MP3, or MP2 when this ffmpeg has no LAME: either way not AAC, so mux must re-encode it."""
    try:
        return tone(path, d, "libmp3lame")
    except RuntimeError:
        return tone(Path(path).with_suffix(".mp2"), d, "mp2")


def streams(path):
    j = probe(path)
    pick = lambda kind: next(s for s in j["streams"] if s["codec_type"] == kind)  # noqa: E731
    return pick("video"), pick("audio")


def packet_md5(path, sel="a:0"):
    """MD5 of every packet's payload: equal lists mean the stream was copied byte for byte."""
    r = subprocess.run([exe("ffprobe"), "-v", "error", "-select_streams", sel, "-show_entries", "packet=data_hash",
                        "-show_data_hash", "md5", "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return [ln.split(",")[0].strip() for ln in r.stdout.splitlines() if ln.strip()]


def frame_times(path):
    r = subprocess.run([exe("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries", "frame=pts_time",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return [float(x.split(",")[0]) for x in r.stdout.split()]


def run_cli(*args):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    return subprocess.run([sys.executable, "-m", "dragon", *map(str, args)], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env, timeout=120)


# ---------------------------------------------------------------- mux

def test_mux_pads_a_short_video_and_turns_mp3_into_aac(tmp_path):
    v, a = video(tmp_path / "v19.mp4", 1.9), mp3(tmp_path / "a25.mp3", 2.5)   # 57 frames, 2.5 s of MP3
    out = tmp_path / "out" / "film.mp4"
    r = deliver.mux(v, a, out, duration=2.0)
    assert (r["frames"], r["expected_frames"], r["source_frames"], r["video_mode"]) == (60, 60, 57, "pad")
    assert r["audio_source_codec"] in ("mp3", "mp2") and r["audio_codec"] == "aac" and r["audio_mode"] == "encode"
    assert r["audio_s"] == pytest.approx(2.0, abs=0.03)
    assert r["ok"] and r["verify"]["ok"] and r["verify"]["frame_check"]["frames"] == 60
    vs, au = streams(out)
    assert vs["nb_frames"] == "60" and vs["profile"] == "High" and vs["color_primaries"] == "bt709"
    assert au["codec_name"] == "aac" and au["sample_rate"] == "48000"
    assert float(au["duration"]) == pytest.approx(2.0, abs=0.03)
    (row,) = V.verify([out], duration=2.0)                       # the full gate agrees, black scan included
    assert row["ok"] and row["errors"] == [] and row["frame_check"]["frames_ok"]
    lum = [y for _, y in qa.luma_series(out)]                    # the 3 added frames repeat the last real one
    assert len(lum) == 60 and all(abs(y - lum[56]) < 0.5 for y in lum[57:])
    assert [p.name for p in out.parent.iterdir()] == ["film.mp4"]   # no half-written .part file left behind


def test_mux_copies_aac_byte_for_byte_unless_normalize(tmp_path):
    v = video(tmp_path / "v3.mp4", 3.0)                          # 90 frames, no B-frames: the first 60 copy cleanly
    a = tone(tmp_path / "a25.m4a", 2.5, "aac", rate=44100)
    out = tmp_path / "copy.mp4"
    r = deliver.mux(v, a, out, duration=2.0)
    assert (r["video_mode"], r["audio_mode"], r["audio_codec"], r["frames"]) == ("copy", "copy", "aac", 60) and r["ok"]
    _, au = streams(out)
    assert au["sample_rate"] == "44100"                          # not resampled to 48 kHz: copied
    assert abs(float(au["duration"]) - 2.0) <= 1024 / 44100 + 0.002   # cut at an AAC frame edge
    got = packet_md5(out)
    assert got and got == packet_md5(a)[:len(got)]
    assert packet_md5(out, "v:0") == packet_md5(v, "v:0")[:60]
    n = deliver.mux(v, a, tmp_path / "norm.mp4", duration=2.0, normalize=True)
    assert (n["audio_mode"], n["audio_codec"]) == ("normalize", "aac") and n["ok"]
    _, au = streams(tmp_path / "norm.mp4")
    assert au["sample_rate"] == "48000" and float(au["duration"]) == pytest.approx(2.0, abs=0.03)
    assert n["verify"]["loudness_lufs"] == pytest.approx(-14, abs=1.5)   # the plain tone sits near -22 LUFS
    assert r["verify"]["loudness_lufs"] < -18


def test_mux_reencodes_a_b_frame_cut_and_defaults_to_the_video_length(tmp_path):
    v = video(tmp_path / "vb.mp4", 3.0, preset="medium")        # B-frames: the first 60 packets are not frames 0..59
    a = tone(tmp_path / "a.aac", 2.5, "aac")                     # raw ADTS AAC is copied into the MP4 as well
    r = deliver.mux(v, a, tmp_path / "cut.mp4", duration=2.0)
    assert (r["video_mode"], r["frames"], r["audio_mode"]) == ("encode", 60, "copy") and r["ok"]
    assert [round(t * FPS) for t in frame_times(tmp_path / "cut.mp4")] == list(range(60))
    own = deliver.mux(video(tmp_path / "v19.mp4", 1.9), a, tmp_path / "own.mp4")   # no duration: its own 57 frames
    assert (own["frames"], own["video_mode"], own["duration_s"]) == (57, "copy", 1.9) and own["ok"]


# ---------------------------------------------------------------- patch_black

def test_patch_black_clones_the_last_good_frame(tmp_path):
    src = tmp_path / "black.mp4"
    ffmpeg("-f", "lavfi", "-i", f"color=c=gray:s={SIZE}:r={FPS}:d=6.5", "-f", "lavfi", "-i", "sine=f=330:d=6.5",
           "-vf", RAMP, "-c:v", "libx264", "-preset", "ultrafast", "-qp", "0", "-pix_fmt", "yuv420p", "-c:a", "aac", src)
    before = qa.black_runs(src)
    assert [(x["start_frame"], x["frames"]) for x in before["body"]] == [(90, 6)]
    out = tmp_path / "fixed" / "film.mp4"
    r = deliver.patch_black(src, out)
    assert (r["mode"], r["patched_frames"], r["remaining"], r["ok"]) == ("patched", 6, [], True)
    assert r["frames"] == r["source_frames"] == 195
    after = qa.black_runs(out)
    assert after["frames"] == 195 and after["body"] == []
    assert [(x["start_frame"], x["frames"]) for x in after["edge"]] == [(0, 4)]   # the fade from black stays
    lum = [y for _, y in qa.luma_series(out)]
    assert all(abs(y - (30 + 89)) < 1.5 for y in lum[89:96])      # frame 89 fills the six black slots
    assert abs(lum[96] - (30 + 96)) < 1.5                          # and the film goes on where it was
    vs, _ = streams(out)
    assert vs["color_primaries"] == "bt709" and vs["nb_frames"] == "195"
    assert packet_md5(out) == packet_md5(src)                      # audio copied
    (row,) = V.verify([out])
    assert row["ok"] and row["black"]["body"] == []
    again = deliver.patch_black(out, tmp_path / "again.mp4")       # nothing left to patch: a plain copy
    assert again["mode"] == "copy" and again["patched"] == [] and (tmp_path / "again.mp4").read_bytes() == out.read_bytes()


def test_patch_black_never_ships_mp3_inside_mp4(tmp_path):
    src, out = tmp_path / "mp3.mp4", tmp_path / "fixed.mp4"
    args = ["-f", "lavfi", "-i", f"testsrc2=s={SIZE}:d=4:r={FPS}", "-f", "lavfi", "-i", "sine=f=440:d=4",
            "-vf", "drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:enable='between(n,45,50)'",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p"]
    try:
        ffmpeg(*args, "-c:a", "libmp3lame", src)
    except RuntimeError:                                           # no LAME in this ffmpeg
        ffmpeg(*args, "-c:a", "mp2", src)
    assert qa.audio_check(src)                                     # the iPhone-silent file
    r = deliver.patch_black(src, out)
    assert r["ok"] and r["patched_frames"] == 6 and r["audio_mode"] == "encode"
    _, au = streams(out)
    assert au["codec_name"] == "aac" and qa.audio_check(out) == []
    assert V.verify([out])[0]["ok"]


# ---------------------------------------------------------------- CLI

def test_cli_help_lists_the_new_commands():
    top = run_cli("--help")
    assert top.returncode == 0
    for word in ("mux", "patch-black", "align", "lyrics-sheet", "--duration", "--no-black", "--normalize"):
        assert word in top.stdout, word
    for cmd, flags in {"verify": ("--duration", "--no-black"), "mux": ("--duration", "--normalize"),
                       "patch-black": ("IN", "OUT", "--threshold"), "align": ("--win", "--hop", "--out"),
                       "lyrics-sheet": ("--band", "--times", "--every", "--transcript")}.items():
        h = run_cli(cmd, "--help")
        assert h.returncode == 0 and all(f in h.stdout for f in flags), cmd


def test_cli_mux_verify_and_patch_black(tmp_path):
    v, a = video(tmp_path / "v.mp4", 1.9), mp3(tmp_path / "a.mp3", 2.5)
    out = tmp_path / "فيلم" / "نهائي.mp4"                        # Arabic folder and file name
    m = run_cli("mux", v, a, out, "--duration", "2")
    assert m.returncode == 0, m.stderr
    assert "60 frames" in m.stdout and "-> aac encode" in m.stdout and out.exists()
    ok = run_cli("verify", out, "--duration", "2", "--no-black")
    assert ok.returncode == 0 and "frames=60" in ok.stdout and "black=skipped" in ok.stdout
    short = run_cli("verify", out, "--duration", "2.1")         # 63 frames intended, 60 there
    assert short.returncode == 1 and "frames 60 vs 63" in short.stdout
    bad = run_cli("mux", v, tmp_path / "missing.wav", tmp_path / "x.mp4")
    assert bad.returncode == 1 and "dragon mux:" in bad.stderr and "Traceback" not in bad.stderr
    blk = video(tmp_path / "blk.mp4", 4, vf="drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:enable='between(n,45,50)'")
    p = run_cli("patch-black", blk, tmp_path / "fixed.mp4")
    assert p.returncode == 0, p.stdout + p.stderr
    assert "1 run(s), 6 frames" in p.stdout and "black runs left inside the film: 0" in p.stdout


def test_cli_align_and_lyrics_sheet(tmp_path):
    song, ref, out = tmp_path / "song.wav", tmp_path / "ref.wav", tmp_path / "map.json"
    ffmpeg("-f", "lavfi", "-i", "anoisesrc=d=24:c=pink:r=8000:a=0.5:seed=7",
           "-af", "volume='0.3+0.7*abs(sin(1.7*t)*sin(0.37*t))':eval=frame", song)
    ffmpeg("-ss", "5", "-t", "9", "-i", song, ref)               # the reel uses song 5..14 s
    r = run_cli("align", ref, song, "--win", "3", "--hop", "1.5", "--out", out)
    assert r.returncode == 0, r.stderr
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["windows"] and doc["gaps"] == [] and len(doc["spans"]) == 1
    assert doc["spans"][0]["offset"] == pytest.approx(5.0, abs=0.05) and doc["spans"][0]["score"] > 0.9
    assert "piece 1" in r.stdout and "0:05" in r.stdout
    pytest.importorskip("PIL")
    clip, sheet = video(tmp_path / "lyrics.mp4", 2.0), tmp_path / "sheet.jpg"
    s = run_cli("lyrics-sheet", clip, sheet, "--band", "0.8:0.95", "--times", "0.5,1.5")
    assert s.returncode == 0, s.stderr
    from PIL import Image
    with Image.open(sheet) as im:
        assert im.format == "JPEG" and im.width > im.height > 0   # two tiles side by side
    need = run_cli("lyrics-sheet", clip, sheet)                 # a time source is required
    assert need.returncode == 2 and "--times" in need.stderr
    bad = run_cli("lyrics-sheet", clip, sheet, "--band", "top", "--every", "1")
    assert bad.returncode == 2 and "band must be" in bad.stderr


# ---------------------------------------------------------------- cinema

def test_cinema_final_mux_is_exact(tmp_path):
    """cinema.build(remux=True) skips the browser render and runs only the mix and the final mux: a render that ran
    long (66 frames) still gives exactly round(2.0 * 30) = 60 frames and 2.0 s of AAC from the PCM mix."""
    from engines import cinema
    work, music, out_dir = tmp_path / "work", tmp_path / "music", tmp_path / "deliver"
    (work / "out").mkdir(parents=True)
    music.mkdir()
    tone(music / "song.wav", 3.0, "pcm_s16le")
    video(work / "out" / "film_video.mp4", 2.2)
    spec = {"title": "film", "duration": 2.0, "fps": FPS, "shots": [{"type": "title", "d": 2.0}],
            "audio": {"song": "song.wav", "start": 0, "fadeIn": 0.1, "fadeOut": 0.5},
            "paths": {"refs": str(tmp_path / "refs"), "audio": str(music), "deliver": str(out_dir), "work": str(work),
                      "luts": str(tmp_path / "luts")}}
    sp = tmp_path / "film.json"
    sp.write_text(json.dumps(spec), encoding="utf-8")
    final, r = cinema.build(sp, remux=True, log=lambda *a: None)
    assert Path(final) == out_dir / "film.mp4" and r["ok"]
    fc = qa.frame_check(final, 2.0)
    assert fc["frames"] == 60 and fc["frames_ok"]
    _, au = streams(final)
    assert au["codec_name"] == "aac" and au["sample_rate"] == "48000"
    assert float(au["duration"]) == pytest.approx(2.0, abs=0.03)
