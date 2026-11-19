"""v1.2 integration: the pieces work together.
  * the launcher copies the bundled engine again when the skill changed (an old copy would hide the new commands),
    leaves an owner repo alone and notes when that repo is an older dragon;
  * one version (1.2) everywhere, and every launcher tool exists;
  * a render with a black run inside and MP3 audio goes qa -> patch_black -> mux -> verify and then passes;
  * the cinema engine's final gate checks the intended frame count.
Media is made here with ffmpeg lavfi in tmp_path: no network, no owner files."""
import importlib.util, os, subprocess, sys, time
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent          # app/
LAUNCHER = ROOT.parent / "scripts" / "dragon.py"
sys.path.insert(0, str(ROOT))
import dragon  # noqa: E402


def launcher():
    if not LAUNCHER.is_file():
        pytest.skip("scripts/dragon.py is not next to app/ (an engine-only copy)")
    spec = importlib.util.spec_from_file_location("dragon_launcher", LAUNCHER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fake_app(root, version="1.3.0", cli="# new cli\n"):
    """A tiny engine folder: dragon/__init__.py + cli.py, a catalog and some __pycache__ junk."""
    for d in ("dragon", "data", "__pycache__"):
        (root / d).mkdir(parents=True, exist_ok=True)
    (root / "dragon" / "__init__.py").write_text(f'__version__ = "{version}"\n', encoding="utf-8")
    (root / "dragon" / "cli.py").write_text(cli, encoding="utf-8")
    (root / "data" / "catalog.sqlite").write_bytes(b"bundled catalog")
    (root / "__pycache__" / "junk.pyc").write_bytes(b"x")
    return root


def read(p):
    return Path(p).read_text(encoding="utf-8")


# ---------------------------------------------------------------- launcher

def test_bundled_copy_is_made_again_when_the_skill_changes(tmp_path, monkeypatch):
    L = launcher()
    app = fake_app(tmp_path / "skill_app")
    monkeypatch.setattr(L, "APP", app)
    home = tmp_path / "نسخة المحرك"                      # Arabic folder name
    assert L.ensure_home("cloud", home) == home
    assert read(home / "dragon" / "cli.py") == "# new cli\n" and read(home / L.STAMP) == L.bundle_stamp()
    assert not (home / "__pycache__").exists()
    (home / "dragon" / "cli.py").write_text("# touched\n", encoding="utf-8")
    L.ensure_home("cloud", home)                         # same skill: the copy is left as it is
    assert read(home / "dragon" / "cli.py") == "# touched\n"
    cat = home / "data" / "catalog.sqlite"               # a catalog rebuilt inside the copy is newer: it stays
    cat.write_bytes(b"rebuilt here")
    later = time.time() + 100
    os.utime(cat, (later, later))
    (app / "dragon" / "cli.py").write_text("# newer cli, one line longer\n", encoding="utf-8")
    L.ensure_home("cloud", home)                         # the skill changed: copied again
    assert read(home / "dragon" / "cli.py") == "# newer cli, one line longer\n"
    assert cat.read_bytes() == b"rebuilt here" and read(home / L.STAMP) == L.bundle_stamp()


def test_refresh_survives_read_only_files_and_copy_errors(tmp_path, monkeypatch, capsys):
    L = launcher()
    app = fake_app(tmp_path / "skill_app")
    monkeypatch.setattr(L, "APP", app)
    home = L.ensure_home("cloud", tmp_path / "copy")
    os.chmod(home / "dragon" / "cli.py", 0o444)          # a read-only skill folder gives read-only copies
    (app / "dragon" / "cli.py").write_text("# fixed cli, a bit longer\n", encoding="utf-8")
    L.ensure_home("cloud", home)
    assert read(home / "dragon" / "cli.py") == "# fixed cli, a bit longer\n"
    (app / "dragon" / "cli.py").write_text("# next cli\n", encoding="utf-8")

    def broken(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(L.shutil, "copytree", broken)
    assert L.ensure_home("cloud", home) == home          # an engine is there: keep it, say why it is old
    assert "could not refresh" in capsys.readouterr().err and read(home / "dragon" / "cli.py") != "# next cli\n"
    with pytest.raises(OSError):                         # no engine at all: the error stays an error
        L.ensure_home("cloud", tmp_path / "empty")


def test_copy_made_by_v11_without_a_stamp_is_refreshed(tmp_path, monkeypatch):
    L = launcher()
    app = fake_app(tmp_path / "skill_app")
    old = fake_app(tmp_path / "tmp_dragon", version="0.1.0", cli="# v1.1 cli\n")
    monkeypatch.setattr(L, "APP", app)
    monkeypatch.setattr(L, "BUNDLED_HOMES", (old,))     # stands in for /tmp/dragon
    L.ensure_home("cloud", old)
    assert read(old / "dragon" / "cli.py") == "# new cli\n" and L.engine_version(old) == "1.3.0"


def test_owner_repo_is_used_as_it_is_with_a_note_when_older(tmp_path, monkeypatch, capsys):
    L = launcher()
    monkeypatch.setattr(L, "APP", fake_app(tmp_path / "skill_app"))
    repo = fake_app(tmp_path / "التنين الأسود", version="0.1.0", cli="# owner repo\n")
    assert L.ensure_home("pc", repo) == repo
    assert read(repo / "dragon" / "cli.py") == "# owner repo\n" and not (repo / L.STAMP).exists()
    note = L.older_repo_note(repo)
    # v10.1 safer owner-repo guidance: explicit DRAGON_HOME instead of forcing cloud mode.
    assert "0.1.0" in note and L.engine_version(L.APP) in note and "DRAGON_HOME=" in note
    calls = []
    monkeypatch.setattr(L, "run", lambda args, home=None: calls.append((args, home)) or 0)
    monkeypatch.setenv("DRAGON_HOME", str(repo))
    monkeypatch.setenv("DRAGON_MODE", "pc")
    assert L.main(["stats"]) == 0
    assert calls == [(["-m", "dragon", "stats"], repo)]     # the command still runs in the owner's repo
    assert "has dragon 0.1.0" in capsys.readouterr().err
    for same_or_newer in ("1.3.0", "1.10.0"):
        (repo / "dragon" / "__init__.py").write_text(f'__version__ = "{same_or_newer}"\n', encoding="utf-8")
        assert L.older_repo_note(repo) == ""


def test_one_version_and_every_launcher_tool_exists():
    L = launcher()
    assert dragon.__version__.startswith("10.") or dragon.__version__.startswith("1990")  # v1990.x: owner-chosen series (fix from the v1990.4 branch)
    assert L.engine_version(L.APP) == dragon.__version__ and L.where()["bundled_version"] == dragon.__version__
    assert [rel for rel in L.TOOLS.values() if not (L.SKILL / rel).is_file()] == []
    top = subprocess.run([sys.executable, "-m", "dragon", "--help"], cwd=ROOT, capture_output=True, text=True,
                         encoding="utf-8", errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"}, timeout=60)
    assert top.returncode == 0 and f"Black Dragon {dragon.__version__}" in top.stdout


# ---------------------------------------------------------------- media chain

@pytest.fixture(scope="module")
def ff():
    from engines.media import exe, ffmpeg
    try:
        exe("ffmpeg"), exe("ffprobe")
    except FileNotFoundError:
        pytest.skip("ffmpeg/ffprobe not installed")
    return ffmpeg


def sound(ff, path, d):
    """MP3 (MP2 when this ffmpeg has no LAME): not AAC, so it must not reach an MP4 as it is."""
    try:
        ff("-f", "lavfi", "-i", f"sine=f=440:d={d}:sample_rate=44100", "-c:a", "libmp3lame", path)
        return Path(path)
    except RuntimeError:
        p = Path(path).with_suffix(".mp2")
        ff("-f", "lavfi", "-i", f"sine=f=440:d={d}:sample_rate=44100", "-c:a", "mp2", p)
        return p


def test_black_run_and_mp3_go_through_patch_mux_and_verify(ff, tmp_path):
    from engines import deliver
    from dragon import verify as V
    render = tmp_path / "فيلم" / "render.mp4"          # a canvas render whose page drew nothing for 6 frames
    render.parent.mkdir()
    ff("-f", "lavfi", "-i", "testsrc2=s=180x320:d=4:r=30",
       "-vf", "drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:enable='between(n,45,50)'",
       "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", render)
    song = sound(ff, tmp_path / "song.mp3", 3.0)
    before = V.verify(render, duration=4)[0]
    assert not before["ok"] and any(e.startswith("black frames t=1.50-1.67 (6 frames)") for e in before["errors"])
    fixed = deliver.patch_black(render, tmp_path / "fixed.mp4")
    assert fixed["ok"] and fixed["patched_frames"] == 6 and fixed["frames"] == 120
    final = tmp_path / "فيلم" / "نهائي.mp4"
    m = deliver.mux(tmp_path / "fixed.mp4", song, final, duration=4)
    assert m["ok"] and m["frames"] == 120 and m["audio_codec"] == "aac" and m["audio_mode"] == "encode"
    row = V.verify([final], expect="180x320", duration=4)[0]
    assert row["ok"] and not row["errors"] and row["black"]["body"] == []
    assert row["frame_check"]["frames"] == 120 and row["frame_check"]["frames_ok"]
    assert V.line(row).startswith("OK ") and "black=clean" in V.line(row)


def test_cinema_final_gate_checks_the_intended_frame_count(ff, tmp_path, monkeypatch):
    import functools, json
    from engines import cinema
    from dragon import verify as V
    seen, real = [], V.probe_file

    @functools.wraps(real)                               # keeps the signature deliver.mux inspects
    def spy(*a, **k):
        seen.append((a, k))
        return real(*a, **k)
    monkeypatch.setattr(V, "probe_file", spy)
    work, music = tmp_path / "work", tmp_path / "music"
    (work / "out").mkdir(parents=True)
    music.mkdir()
    ff("-f", "lavfi", "-i", "sine=f=440:d=3:sample_rate=48000", "-c:a", "pcm_s16le", music / "song.wav")
    ff("-f", "lavfi", "-i", "testsrc2=s=180x320:d=2.2:r=30", "-c:v", "libx264", "-preset", "ultrafast",
       "-pix_fmt", "yuv420p", work / "out" / "film_video.mp4")  # the render ran 6 frames long
    spec = {"title": "film", "duration": 2.0, "fps": 30, "shots": [{"type": "title", "d": 2.0}],
            "audio": {"song": "song.wav", "start": 0, "fadeIn": 0.1, "fadeOut": 0.5},
            "paths": {"refs": str(tmp_path / "refs"), "audio": str(music), "deliver": str(tmp_path / "deliver"),
                      "work": str(work), "luts": str(tmp_path / "luts")}}
    sp = tmp_path / "film.json"
    sp.write_text(json.dumps(spec), encoding="utf-8")
    final, r = cinema.build(sp, remux=True, log=lambda *a: None)
    assert r["ok"] and r["frame_check"]["frames"] == 60 and r["frame_check"]["expected_frames"] == 60
    (args, kw), = [c for c in seen if Path(c[0][0]) == Path(final) and c[1].get("black", True)]  # the final gate
    assert kw.get("duration") == 2.0 and r["frame_check"]["reference_s"] == 2.0 and "black" in r
