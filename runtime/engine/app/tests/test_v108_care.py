"""Black Dragon v10.8 «الحارس»: lessons from every past conversation, each one checked on real files.

play-check catches MP3-in-MP4 (silent on iPhone), 4:4:4, a truncated render, a non-faststart file, and --fix writes a
new *_phone.mp4 that passes while the original stays byte-identical. The job ledger records a real launcher command and
`status` / `last` report it. The layout fixer decodes the owner's real wrong-layout messages.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CARE = ROOT / "tools" / "care" / "care.py"
LAYOUT = ROOT / "tools" / "care" / "layout.py"
LAUNCHER = ROOT / "scripts" / "dragon.py"
FF = shutil.which("ffmpeg")
needs_ff = pytest.mark.skipif(not (FF and shutil.which("ffprobe")), reason="ffmpeg/ffprobe not installed")


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


care = _load(CARE, "care_v108")
layout = _load(LAYOUT, "layout_v108")


def _ff(*args):
    subprocess.run([FF, "-v", "error", "-y", *map(str, args)], check=True)


def _md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def media(tmp_path_factory):
    if not FF:
        pytest.skip("ffmpeg not installed")
    d = tmp_path_factory.mktemp("care")
    src = ["-f", "lavfi", "-i", "testsrc2=s=320x568:d=1.5", "-f", "lavfi", "-i", "sine=d=1.5"]
    _ff(*src, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart", d / "good.mp4")
    _ff(*src, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "libmp3lame", d / "mp3in.mp4")
    _ff("-f", "lavfi", "-i", "testsrc2=s=320x568:d=1.5", "-c:v", "libx264", "-pix_fmt", "yuv444p", d / "yuv444.mp4")
    _ff(*src, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", d / "slowstart.mp4")
    good = (d / "good.mp4").read_bytes()
    (d / "trunc.mp4").write_bytes(good[: len(good) // 3])
    (d / "empty.mp4").write_bytes(b"")
    return d


@needs_ff
def test_good_file_passes(media):
    r = care.play_check(media / "good.mp4")
    assert r["ok"], r


@needs_ff
def test_mp3_inside_mp4_is_refused_and_fixed_without_touching_original(media):
    before = _md5(media / "mp3in.mp4")
    r = care.play_check(media / "mp3in.mp4")
    assert not r["ok"] and r["fix"]["audio"] and any("AAC" in e for e in r["errors"])
    out, r2 = care.play_fix(media / "mp3in.mp4")
    assert out and out.name == "mp3in_phone.mp4" and r2["ok"], r2
    assert r2["audio"]["codec_name"] == "aac" and _md5(media / "mp3in.mp4") == before
    out2, _ = care.play_fix(media / "mp3in.mp4")  # never overwrites an earlier fix either
    assert out2.name == "mp3in_phone2.mp4"


@needs_ff
def test_444_is_refused_and_reencoded(media):
    r = care.play_check(media / "yuv444.mp4")
    assert not r["ok"] and r["fix"]["video"]
    out, r2 = care.play_fix(media / "yuv444.mp4")
    assert r2["ok"] and r2["video"]["pix_fmt"] == "yuv420p"


@needs_ff
def test_faststart_is_a_warning_and_fix_moves_moov_first(media):
    atoms = [a[0] for a in care.top_atoms(media / "slowstart.mp4")]
    assert atoms.index("moov") > atoms.index("mdat")
    r = care.play_check(media / "slowstart.mp4")
    assert r["ok"] and r["fix"]["faststart"] and r["warnings"]
    out, r2 = care.play_fix(media / "slowstart.mp4")
    fixed = [a[0] for a in care.top_atoms(out)]
    assert fixed.index("moov") < fixed.index("mdat") and r2["ok"]


@needs_ff
def test_truncated_and_empty_renders_fail(media):
    assert not care.play_check(media / "trunc.mp4")["ok"]
    e = care.play_check(media / "empty.mp4")
    assert not e["ok"] and "0" in e["errors"][0]
    assert not care.play_check(media / "missing.mp4")["ok"]


@needs_ff
def test_cli_exit_codes(media):
    ok = subprocess.run([sys.executable, str(CARE), "play", str(media / "good.mp4")], capture_output=True)
    bad = subprocess.run([sys.executable, str(CARE), "play", str(media / "trunc.mp4")], capture_output=True)
    assert ok.returncode == 0 and bad.returncode == 1


def test_resources_reports_memory_and_workers():
    r = care.resources()
    assert r["ram_total_gb"] > 0 and r["workers"] >= 1 and r["level"] in ("ok", "tight", "low") and r["advice"]


@needs_ff
def test_launcher_records_job_and_reports_status_and_last(media, tmp_path):
    env = dict(os.environ, DRAGON_STATE=str(tmp_path / "state"), DRAGON_HOME=str(ROOT / "app"),
               PYTHONIOENCODING="utf-8")
    out = media / "cut_v108.mp4"
    r = subprocess.run([sys.executable, str(LAUNCHER), "cut", "good.mp4", "0.2", "1.0", out.name], cwd=media, env=env,
                       capture_output=True, text=True, encoding="utf-8", timeout=180)
    assert r.returncode == 0, r.stderr[-800:]
    lines = (tmp_path / "state" / "jobs.jsonl").read_text(encoding="utf-8").splitlines()
    start, end = json.loads(lines[0]), json.loads(lines[-1])
    assert start["argv"][0] == "cut" and end["exit"] == 0 and str(out.resolve()) in end["outputs"]
    st = subprocess.run([sys.executable, str(LAUNCHER), "status", "--json"], env=env, capture_output=True, text=True,
                        encoding="utf-8")
    js = json.loads(st.stdout)
    assert not js["running"] and js["recent"][-1]["state"] == "done"
    last = subprocess.run([sys.executable, str(LAUNCHER), "last", "--json"], env=env, capture_output=True, text=True,
                          encoding="utf-8")
    assert json.loads(last.stdout)[0] == str(out.resolve())


def test_stopped_job_is_not_reported_as_running(tmp_path, monkeypatch):
    monkeypatch.setattr(care, "JOBS", tmp_path / "jobs.jsonl")
    (tmp_path / "jobs.jsonl").write_text(json.dumps({"id": "x", "pid": 999999, "argv": ["film"], "start": 1}) + "\n",
                                         encoding="utf-8")
    assert care.read_jobs()[0]["state"] == "stopped"


@pytest.mark.parametrize("typed, arabic", [
    (";LG", "كمل"),
    ("P'DJ TDK LIHVM HGJKDK", "حطيت فين مهارة التنين"),
    ("hgljwtp htjp hgj'fdr la fdtjp", "المتصفح افتح التطبيق مش بيفتح"),
    (";dt hvf'i fhg;hldvh", "كيف اربطه بالكاميرا"),
])
def test_owner_wrong_layout_messages_decode(typed, arabic):
    assert layout.en_to_ar(typed) == arabic


def test_layout_detect_leaves_english_alone():
    assert layout.looks_wrong_layout(";LG")
    assert not layout.looks_wrong_layout("please render the video for the app")
    assert layout.ar_to_en("هىسفشمم") == "install"


def test_whisper_falls_back_to_a_cached_model(monkeypatch, capsys):
    sys.path.insert(0, str(ROOT / "app"))
    try:
        from engines import audio
    finally:
        sys.path.pop(0)
    import types
    tried = []

    class WM:
        def __init__(self, name, **k):
            tried.append(name)
            if name != "small":
                raise OSError("not in cache")
    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=WM))
    assert isinstance(audio.load_model("medium"), WM)
    assert tried[0] == "medium" and tried[-1] == "small" and "using the cached 'small'" in capsys.readouterr().err


def test_v108_registered_everywhere():
    src = LAUNCHER.read_text(encoding="utf-8")
    assert '"care": "tools/care/care.py"' in src and '"layout": "tools/care/layout.py"' in src
    ids = {t["id"] for t in json.loads((ROOT / "app" / "data" / "own_tools.json").read_text(encoding="utf-8"))["tools"]}
    assert {"phone-play-check", "dragon-status", "dragon-last", "dragon-resources", "keyboard-layout-fix"} <= ids
    assert "play-check" in (ROOT / "SKILL.md").read_text(encoding="utf-8")


@needs_ff
def test_normalize_brings_a_loud_mp3_master_to_minus_14(media):
    src = media / "loud.mp4"
    _ff("-f", "lavfi", "-i", "testsrc2=s=320x568:d=4", "-f", "lavfi", "-i", "sine=f=300:d=4,volume=6",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "libmp3lame", src)
    before = care.measure_loudness(src)
    out, r = care.play_fix(src, normalize=True)
    assert r["ok"] and float(before["input_i"]) > -9
    assert abs(r["loudness_after"]["lufs"] + 14) <= 0.5 and r["loudness_after"]["true_peak"] <= -1.5
