"""v1.3 dogfood fixes in the delivery gate and the tools around it.

Pinned findings: verify passing a silent film («من غير صوت»); mux padding a short video silently; an old repo on the
Desktop running the old gate; `where` naming /mnt/user-data/outputs in a Claude Code session; render.cjs without
--start; the styles kit --check too weak (requirements, missing files, bans, a song under verses, overlapping text),
verses silently not drawn outside `chapters`, the credit showing 1-2 s, long black runs frozen, no song copy mode;
web_film render swallowing the guard; cartoon mix.py writing NaN; words downloading models silently; align folding
leading silence into the first piece; `cut` crashing on audio; lyrics-sheet without paging.
Media are tiny lavfi files (270x480, 2-4 s) in tmp_path; no network, no browser."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent           # app/
SKILL = ROOT.parent
LAUNCHER = SKILL / "scripts" / "dragon.py"
KIT = SKILL / "tools" / "styles"
CARTOON = SKILL / "tools" / "cartoon" / "tools"
RENDER = ROOT / "engines" / "render" / "render.cjs"
sys.path.insert(0, str(ROOT))
FF = shutil.which("ffmpeg")
need_ff = pytest.mark.skipif(not FF, reason="ffmpeg not installed")


def ff(*args):
    subprocess.run([FF, "-nostdin", "-v", "error", "-y", *map(str, args)], check=True)


def video(path, seconds=2, audio=None):
    """270x480 30 fps H.264; audio: None, 'sine' or 'silent' (AAC)."""
    args = ["-f", "lavfi", "-i", f"testsrc2=s=270x480:r=30:d={seconds}"]
    if audio:
        src = "sine=f=440:r=48000" if audio == "sine" else "anullsrc=r=48000:cl=stereo"
        args += ["-f", "lavfi", "-t", str(seconds), "-i", src]
    args += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast"]
    args += (["-c:a", "aac", "-b:a", "96k", "-shortest"] if audio else [])
    ff(*args, path)
    return path


def dragon(*args, env=None):
    e = dict(os.environ, DRAGON_HOME=str(ROOT), PYTHONDONTWRITEBYTECODE="1", **(env or {}))
    return subprocess.run([sys.executable, str(LAUNCHER), *map(str, args)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=e, timeout=120)


def launcher():
    spec = importlib.util.spec_from_file_location("dragon_launcher_v13", LAUNCHER)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ---------------------------------------------------------------- verify: silence is a failure

@need_ff
def test_verify_fails_a_silent_film_and_a_film_without_audio(tmp_path):
    from dragon.verify import probe_file
    silent = video(tmp_path / "silent.mp4", audio="silent")
    r = probe_file(silent, duration=2)
    assert not r["ok"] and any("audio is silent" in e for e in r["errors"])
    sound = video(tmp_path / "sound.mp4", audio="sine")
    assert not any("silent" in e for e in probe_file(sound, duration=2)["errors"])
    mute = video(tmp_path / "mute.mp4")
    assert probe_file(mute, duration=2)["ok"]                          # the library default stays as it was
    cli = dragon("verify", mute, "--duration", "2", "--no-black")
    assert cli.returncode == 1 and "no audio stream" in cli.stdout + cli.stderr
    assert dragon("verify", mute, "--duration", "2", "--no-black", "--silent-ok").returncode == 0


@need_ff
def test_mux_fails_when_more_than_half_a_second_is_frozen(tmp_path):
    v = video(tmp_path / "v.mp4", seconds=1)
    a = tmp_path / "a.m4a"
    ff("-f", "lavfi", "-i", "sine=f=330:r=48000:d=3", "-c:a", "aac", a)
    r = dragon("mux", v, a, tmp_path / "out.mp4", "--duration", "2")
    assert r.returncode == 1 and "frozen" in r.stderr
    assert dragon("mux", v, a, tmp_path / "out2.mp4", "--duration", "2", "--allow-pad").returncode == 0


# ---------------------------------------------------------------- launcher: old repos, where on Claude Code

def _fake_repo(root, version):
    (root / "dragon").mkdir(parents=True)
    (root / "dragon" / "cli.py").write_text("# old\n", encoding="utf-8")
    (root / "dragon" / "__init__.py").write_text(f'__version__ = "{version}"\n', encoding="utf-8")
    return root


def test_old_repo_never_runs_the_gate_commands(tmp_path, monkeypatch, capsys):
    L = launcher()
    repo = _fake_repo(tmp_path / "Desktop" / "التنين الأسود", "1.1.0")
    monkeypatch.setattr(L, "HOME", tmp_path)
    calls = []
    monkeypatch.setattr(L, "run", lambda args, home=None: calls.append((args, home)) or 0)
    monkeypatch.setattr(L, "ensure_home", lambda mode, home: home)
    monkeypatch.setenv("DRAGON_HOME", str(repo))
    monkeypatch.setenv("DRAGON_MODE", "pc")
    assert L.main(["verify", "x.mp4"]) == 0
    assert calls[-1][1] != repo and "runs on the skill's engine" in capsys.readouterr().err
    assert L.main(["stats"]) == 0 and calls[-1][1] == repo                 # other commands: his repo, with the note
    assert "DRAGON_MODE=cloud" not in L.older_repo_note(repo) and "DRAGON_HOME=" in L.older_repo_note(repo)
    assert any("OneDrive" in str(c) for c in L.PC_CANDIDATES)


def test_where_on_claude_code_cloud_delivers_with_senduserfile(monkeypatch):
    L = launcher()
    monkeypatch.setenv("CLAUDE_CODE_REMOTE", "true")
    assert L.surface() == "claude-code-cloud" and "SendUserFile" in L.outputs_line()
    monkeypatch.delenv("CLAUDE_CODE_REMOTE")
    assert "SendUserFile" not in L.outputs_line()


# ---------------------------------------------------------------- render.cjs --start

@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_render_cjs_has_a_start_option():
    assert subprocess.run(["node", "--check", str(RENDER)]).returncode == 0
    h = subprocess.run(["node", str(RENDER), "--help"], capture_output=True, text=True, timeout=60).stdout
    assert "--start" in h and "relative to the chunk" in h
    bad = subprocess.run(["node", str(RENDER), "--in", "x.html", "--out", "y.mp4", "--start", "-1"],
                         capture_output=True, text=True, timeout=60)
    assert bad.returncode == 2 and "--start needs a number" in bad.stderr
    src = RENDER.read_text(encoding="utf-8")
    assert "const t = (o.start || 0) + local" in src and "local >= this.head" in src


# ---------------------------------------------------------------- styles kit

def kit():
    spec = importlib.util.spec_from_file_location("build_style_v13", KIT / "build_style.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


BASE = {"style": "clean", "duration": 12, "watermark": "© Mahmoud Elkosif",
        "credit": ["مونتاج وإخراج Mahmoud Elkosif", "تابعني على فيسبوك"],
        "shots": [{"src": "a.mp4", "start": 0, "end": 12}], "end": {"at": 8}}


def test_verses_outside_chapters_are_an_error():
    B = kit()
    for key in ("verses", "lyrics", "labels", "lowers", "chapters"):
        with pytest.raises(B.SpecError, match="only by the chapters style"):
            B.normalise({**BASE, key: [{"text": "x", "start": 1, "end": 2}]}, ".", check_files=False)


def test_check_gate_requirements_bans_song_under_verses_overlaps():
    B = kit()
    spec = {**BASE, "requirements": ["ميار وهي ساجدة", "الأغنية كاملة"],
            "shots": [{"src": "a.mp4", "start": 0, "end": 12, "covers": ["r1"]}],
            "lines": [{"text": "ميار الشوربجي", "start": 1, "end": 4}, {"text": "سطر", "start": 3, "end": 5}]}
    plan = B.normalise(spec, ".", check_files=False)
    errors, warns = B.check_spec(spec, plan, allow_missing=True)
    assert any("requirement r2" in e for e in errors) and not any("requirement r1" in e for e in errors)
    assert any("الشوربجي" in e for e in errors)
    assert any("two texts at once" in w for w in warns)
    ch = {**BASE, "style": "chapters", "song": "s.m4a", "verses": [{"text": "آية", "start": 1, "end": 3}]}
    errs, _ = B.check_spec(ch, B.normalise(ch, ".", check_files=False), allow_missing=True)
    assert any("song plays under Quran verses" in e for e in errs)
    late = {**BASE, "end": {"at": 11.5}}
    _, w = B.check_spec(late, B.normalise(late, ".", check_files=False), allow_missing=True)
    assert any("too late for the credit" in x for x in w)


def test_check_cli_fails_on_missing_files_and_placeholders(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({**BASE, "title": {"text": "اسمها", "start": 0.2, "end": 3}}, ensure_ascii=False), encoding="utf-8")
    run = lambda *a: subprocess.run([sys.executable, "-B", str(KIT / "build_style.py"), str(p), "--check", *a],  # noqa: E731
                                    capture_output=True, text=True, encoding="utf-8", timeout=60)
    r = run()
    assert r.returncode == 2 and "MISSING" in r.stdout and "placeholder" in r.stdout
    assert run("--allow-missing").returncode == 0


def test_credit_never_starts_after_duration_minus_3():
    common = (KIT / "common.js").read_text(encoding="utf-8")
    assert "a = Math.max(0, Math.min(a, DUR - 3));" in common


def test_long_black_runs_are_rerendered_not_frozen(monkeypatch, tmp_path):
    B = kit()
    from engines import qa, deliver
    monkeypatch.setattr(qa, "black_runs", lambda *a, **k: {"frames": 60, "body": [{"start": 1.0, "end": 2.0, "frames": 30}],
                                                            "edge": []})
    monkeypatch.setattr(deliver, "patch_black", lambda *a, **k: pytest.fail("a 30-frame run must not be frozen"))
    res = B.black_check(tmp_path / "v.mp4", {"duration": 2.0}, tmp_path, log=lambda *_: None)
    assert res["ok"] is False and res["rerender"] and res["patched_frames"] == 0
    monkeypatch.setattr(qa, "black_runs", lambda *a, **k: {"frames": 60, "body": [{"start": 1.0, "end": 1.07, "frames": 2}],
                                                            "edge": []})
    (tmp_path / "v.mp4").write_bytes(b"x")

    def patch(src, dst):
        Path(dst).write_bytes(b"y")
        return {"patched_frames": 2, "remaining": [], "ok": True}
    monkeypatch.setattr(deliver, "patch_black", patch)
    res = B.black_check(tmp_path / "v.mp4", {"duration": 2.0}, tmp_path, log=lambda *_: None)
    assert res["patched"] and res["patched_frames"] == 2 and res["ok"]


@need_ff
def test_song_copy_keeps_the_aac_packets(tmp_path):
    B = kit()
    song = tmp_path / "song.m4a"
    ff("-f", "lavfi", "-i", "sine=f=500:r=48000:d=3", "-c:a", "aac", song)
    r = B.mix_song({"path": str(song), "start": 0.0, "fade_in": 0.0, "fade_out": 0.0, "copy": True}, 2.0,
                   tmp_path / "mix.m4a", log=lambda *_: None)
    assert r["mode"] == "copy" and r["md5_identical"] is True
    wav = tmp_path / "song.wav"
    ff("-f", "lavfi", "-i", "sine=f=500:r=48000:d=3", wav)
    with pytest.raises(B.BuildError, match="AAC"):
        B.mix_song({"path": str(wav), "start": 0.0, "fade_in": 0, "fade_out": 0, "copy": True}, 2.0,
                   tmp_path / "mix2.m4a", log=lambda *_: None)
    plan = B.normalise({**BASE, "song": {"path": str(song), "normalize": False}}, ".", check_files=False)
    assert plan["song"]["normalize"] is False
    r = B.mix_song(plan["song"], 2.0, tmp_path / "mix3.m4a", log=lambda *_: None)
    assert r["mode"] == "encode" and "lufs_before" in r


# ---------------------------------------------------------------- web_film

def test_web_film_scaffold_into_a_folder_and_render_raises_on_black(tmp_path, monkeypatch):
    from engines.web_film import page, render
    plan = {"duration": 3, "width": 1080, "height": 1920, "shots": [{"kind": "title", "text": "اهلا", "start": 0, "end": 3}]}
    pf = tmp_path / "p.json"
    pf.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    out = page.write_scaffold(pf, tmp_path / "film")
    assert out == tmp_path / "film" / "index.html" and out.is_file()

    class R:
        returncode, stdout, stderr = 3, "BLACK_UNRECOVERED t=1.200\nSUMMARY frames=90 unrecovered=1\n", ""
    monkeypatch.setattr(render.subprocess, "run", lambda *a, **k: R())
    with pytest.raises(RuntimeError, match=r"t=1\.200"):
        render._run(["node"], guard=True)
    src = (ROOT / "engines" / "web_film" / "render.py").read_text(encoding="utf-8")
    assert '"--strict"' in src and "deliver import mux" in src and '"-t"' not in src


# ---------------------------------------------------------------- cartoon

@need_ff
def test_cartoon_mix_stops_on_a_silent_stem(tmp_path):
    pytest.importorskip("numpy")
    v, m = tmp_path / "v.wav", tmp_path / "m.wav"
    ff("-f", "lavfi", "-i", "sine=f=300:r=48000:d=2", v)
    ff("-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", "2", m)
    r = subprocess.run([sys.executable, "-B", str(CARTOON / "mix.py"), v, m, m], cwd=tmp_path, capture_output=True,
                       text=True, timeout=60)
    assert r.returncode == 1 and "silent" in r.stderr and not (tmp_path / "mix_raw.wav").exists()
    import shutil
    if shutil.which("bash"):                    # v10.15: Windows without bash on PATH -> skip only the syntax check
        assert subprocess.run(["bash", "-n", str(CARTOON / "finish.sh")]).returncode == 0
    fin = (CARTOON / "finish.sh").read_text(encoding="utf-8")
    assert "-shortest" not in fin.replace("no -shortest", "") and "192k" not in fin.replace("AAC 192k", "")
    assert "bt709" in fin and "$D mux" in fin


# ---------------------------------------------------------------- audio, songs, cut, lyrics

def test_words_never_downloads_without_yes(monkeypatch):
    from engines import audio
    import types
    calls = {}

    class WM:
        def __init__(self, *a, **k):
            calls.update(k)
            raise OSError("not in cache")
    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=WM))
    with pytest.raises(audio.ModelNotCached, match="1.5 GB"):
        audio.load_model("medium", threads=2)
    assert calls["local_files_only"] is True and calls["cpu_threads"] == 2


def test_align_trims_leading_silence_and_a_tone():
    np = pytest.importorskip("numpy")
    from engines import songs
    sr = 8000
    rng = np.random.default_rng(1)
    noise = (rng.standard_normal(3 * sr) * 0.2).astype("float32")
    for head in (np.zeros(sr, "float32"), (0.3 * np.sin(2 * np.pi * 440 * np.arange(sr) / sr)).astype("float32")):
        x = np.concatenate([head, noise])
        seg = [{"ref_start": 0.0, "ref_end": 4.0, "song_start": 10.0, "song_end": 14.0, "offset": 10.0, "score": 0.9,
                "windows": 1}]
        (p,) = songs.trim_edges(seg, x, sr)
        assert p["ref_start"] == pytest.approx(1.0, abs=0.15) and p["song_start"] == pytest.approx(11.0, abs=0.15)
        assert p["trimmed_head"] == pytest.approx(1.0, abs=0.15)


@need_ff
def test_cut_on_audio_only_input(tmp_path):
    from engines.montage import smart_cut
    a = tmp_path / "r.m4a"
    ff("-f", "lavfi", "-i", "sine=f=200:r=48000:d=3", "-c:a", "aac", a)
    r = smart_cut(a, 0.5, 2.0, tmp_path / "c.m4a")
    assert r["mode"] == "audio-copy" and (tmp_path / "c.m4a").stat().st_size > 0


@need_ff
def test_lyrics_sheet_pages_and_row_transcripts(tmp_path, capsys):
    pytest.importorskip("PIL")
    from engines import songs
    v = video(tmp_path / "v.mp4", seconds=3)
    times = [round(0.1 * k, 2) for k in range(1, 26)]
    outs = songs.lyrics_sheet(v, tmp_path / "s.jpg", times=times + [9.0], per_sheet=20, width=120)
    assert [o.name for o in outs] == ["s_01.jpg", "s_02.jpg"] and all(o.is_file() for o in outs)
    assert "outside the video" in capsys.readouterr().err
    one = songs.lyrics_sheet(v, tmp_path / "r.jpg", transcript=[[0.2, 0.6, "a"], [1.0, 1.4, "b"]], width=120)
    assert Path(one).is_file()
    bad = tmp_path / "bad.json"
    bad.write_text('"just text"', encoding="utf-8")
    with pytest.raises(ValueError, match="transcript must be"):
        songs.lyrics_sheet(v, tmp_path / "x.jpg", transcript=bad, width=120)
