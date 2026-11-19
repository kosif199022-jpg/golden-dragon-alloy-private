"""v10.15: tools/fonts/fonts.py — doctor / fetch on a temp package root. No network, no home-folder scan."""
import importlib.util, json, subprocess, sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT.parent
FONTS_PY = SKILL / "tools" / "fonts" / "fonts.py"
OFL = "SIL OPEN FONT LICENSE Version 1.1\nCopyright The Testfam Project Authors\n"


@pytest.fixture()
def F(monkeypatch):
    spec = importlib.util.spec_from_file_location("bd_fonts_under_test", FONTS_PY)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    monkeypatch.setattr(m, "MANIFEST", [("eng/fonts", "Testfam-Bold.ttf", "Testfam", "ofl/testfam/Testfam-Bold.ttf", "t"),
                                        ("kit/fonts", "Testfam-Bold.ttf", "Testfam", None, "t")])
    monkeypatch.setattr(m, "verify", lambda p, fam: (Path(p).read_bytes().startswith(b"FAKEFONT"), "fake"))

    def no_net(*a, **k):
        raise AssertionError("network used")
    monkeypatch.setattr(m, "download", no_net)
    monkeypatch.setattr(m.urllib.request, "urlopen", no_net)
    return m


def _src(tmp_path, data=b"FAKEFONT-1"):
    s = tmp_path / "src"
    s.mkdir(exist_ok=True)
    (s / "Testfam-Bold.ttf").write_bytes(data)
    (s / "OFL-Testfam.txt").write_text(OFL, encoding="utf-8")
    return s


def _root(tmp_path):
    r = tmp_path / "pkg"
    r.mkdir()
    return r


def test_doctor_reports_missing_then_ok(F, tmp_path, capsys):
    r = _root(tmp_path)
    assert F.doctor(r) == 1
    assert capsys.readouterr().out.count("MISSING") == 2
    for f in ("eng/fonts", "kit/fonts"):
        (r / f).mkdir(parents=True)
        (r / f / "Testfam-Bold.ttf").write_bytes(b"FAKEFONT")
    assert F.doctor(r, as_json=True) == 0
    assert json.loads(capsys.readouterr().out)["missing"] == 0


def test_fetch_dry_run_writes_nothing(F, tmp_path):
    r, s = _root(tmp_path), _src(tmp_path)
    rc, plan = F.fetch(r, [s], use_defaults=False, do_download=True, yes=False, log=lambda *_: None)
    assert [a for a, _, _ in plan] == ["copy", "copy"] and rc == 0
    assert not any(r.rglob("*"))                       # dry run: no folder, no font, no lock
    rc, plan = F.fetch(r, [], use_defaults=False, do_download=False, yes=False, log=lambda *_: None)
    assert [a for a, _, _ in plan] == ["missing", "missing"] and rc == 1
    rc, plan = F.fetch(r, [], use_defaults=False, do_download=True, yes=False, log=lambda *_: None)
    assert [a for a, _, _ in plan] == ["download", "missing"]   # only the entry with a google/fonts path
    assert plan[0][2] == "https://github.com/google/fonts/raw/main/ofl/testfam/Testfam-Bold.ttf"
    assert not any(r.rglob("*"))


def test_fetch_copies_with_licence_and_lock(F, tmp_path):
    r, s = _root(tmp_path), _src(tmp_path)
    rc, placed = F.fetch(r, [s], use_defaults=False, yes=True, log=lambda *_: None)
    assert rc == 0 and len(placed) == 2
    for f in ("eng/fonts", "kit/fonts"):
        d = r / f
        assert (d / "Testfam-Bold.ttf").read_bytes() == b"FAKEFONT-1"
        assert "OPEN FONT LICENSE" in (d / "OFL-Testfam.txt").read_text(encoding="utf-8")
        lock = json.loads((d / "fonts.lock.json").read_text(encoding="utf-8"))
        assert lock["schema"] == "black-dragon.fonts.lock.v1"
        rec = lock["fonts"]["Testfam-Bold.ttf"]
        assert set(rec) >= {"family", "licence", "sha256", "bytes", "source", "source_kind", "licence_file", "placed_at"}
        assert rec["licence"] == "OFL-1.1" and rec["source_kind"] == "local" and len(rec["sha256"]) == 64
        assert rec["sha256"] == F.sha256(d / "Testfam-Bold.ttf") and rec["source"] == str(s / "Testfam-Bold.ttf")
        assert rec["licence_file"] == "OFL-Testfam.txt"
    assert F.doctor(r) == 0


def test_fetch_never_overwrites(F, tmp_path):
    r, s = _root(tmp_path), _src(tmp_path, b"FAKEFONT-new")
    (r / "eng/fonts").mkdir(parents=True)
    (r / "eng/fonts/Testfam-Bold.ttf").write_bytes(b"FAKEFONT-mine")
    (r / "eng/fonts/OFL.txt").write_text("my own licence notes", encoding="utf-8")
    rc, placed = F.fetch(r, [s], use_defaults=False, yes=True, log=lambda *_: None)
    assert rc == 0 and placed == [str(r / "kit/fonts/Testfam-Bold.ttf")]
    assert (r / "eng/fonts/Testfam-Bold.ttf").read_bytes() == b"FAKEFONT-mine"
    assert (r / "eng/fonts/OFL.txt").read_text(encoding="utf-8") == "my own licence notes"
    # a second run changes nothing
    before = {p: p.read_bytes() for p in r.rglob("*") if p.is_file()}
    F.fetch(r, [s], use_defaults=False, yes=True, log=lambda *_: None)
    assert before == {p: p.read_bytes() for p in r.rglob("*") if p.is_file()}


def test_fetch_rejects_a_file_that_is_not_the_font(F, tmp_path):
    r, s = _root(tmp_path), _src(tmp_path, b"<html>not a font</html>")
    rc, placed = F.fetch(r, [s], use_defaults=False, yes=True, log=lambda *_: None)
    assert rc == 1 and placed == [] and not (r / "eng/fonts/Testfam-Bold.ttf").exists()


def test_real_verify_and_manifest_are_ofl(tmp_path):
    spec = importlib.util.spec_from_file_location("bd_fonts_real", FONTS_PY)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    bad = tmp_path / "x.ttf"
    bad.write_bytes(b"not a font at all")
    assert m.verify(bad, "Cairo")[0] is False
    files = {(f, n) for f, n, *_ in m.MANIFEST}
    assert ("tools/styles/fonts", "ArefRuqaa-Bold.ttf") in files and ("app/engines/matrices/assets", "KOSIFJumuah-Bold.woff2") in files
    for e in m.entries(tmp_path):
        assert e["licence"] == "OFL-1.1"
        assert e["url"] is None or e["url"].startswith("https://github.com/google/fonts/raw/main/ofl/")
    with pytest.raises(ValueError):
        m.download("https://example.com/x.ttf", tmp_path)


def test_cli_dry_run_and_registered(tmp_path):
    r = _root(tmp_path)
    p = subprocess.run([sys.executable, "-B", str(FONTS_PY), "--root", str(r), "fetch", "--no-default-sources"],
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert p.returncode == 1 and "dry run" in p.stdout and not any(r.rglob("*"))
    assert subprocess.run([sys.executable, "-B", str(FONTS_PY), "--root", str(tmp_path / "nope"), "doctor"],
                          capture_output=True, timeout=60).returncode == 2
    assert '"fonts": "tools/fonts/fonts.py"' in (SKILL / "scripts" / "dragon.py").read_text(encoding="utf-8")
