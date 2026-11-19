"""v1.2: Egyptian synonyms reach English skills, the dragon's own engines are in the catalog, doctor/where agree, fetch logs sources."""
import functools, http.server, importlib.util, json, socketserver, sys, threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT.parent
sys.path.insert(0, str(ROOT))
from dragon import router, doctor, catalog, __version__
from dragon.cli import list_engines


def test_version():
    assert __version__.startswith("10.") or __version__.startswith("1990")  # v1990.x: the owner numbered this series 1990 (fix from the v1990.4 branch, merged in v1990.10)


def test_synonyms_expand_egyptian_words():
    syn = router._synonyms()
    assert "blender" in syn["بلندر"] and "denoise" in syn["دوشه"] and "upscale" in syn["تكبير"]
    assert len(syn) >= 120


def test_own_tools_ranked_first():
    hits = router.find("عايز اشيل الدوشه من الفويس", kinds=("tool",), limit=3)["tool"]
    assert any(h["name"] == "deep-filter" for h in hits)
    hits = router.find("غلاف ريل بعنوان عربي", kinds=("tool",), limit=2)["tool"]
    assert hits[0]["name"] == "image-studio" and hits[0]["source"] == "black-dragon"


def test_register_own_is_idempotent():
    con = catalog.connect()
    before = con.execute("SELECT count(*) FROM items WHERE source='black-dragon'").fetchone()[0]
    catalog.register_own()
    after = catalog.connect().execute("SELECT count(*) FROM items WHERE source='black-dragon'").fetchone()[0]
    own = json.loads((ROOT / "data" / "own_tools.json").read_text(encoding="utf-8"))["tools"]
    assert before == after == len(own)


def test_engines_listed():
    names = {n for n, _ in list_engines()}
    assert {"blender", "image_studio", "dragon_montage", "talking_head", "voice_studio"} <= names


def test_doctor_knows_new_programs():
    assert {"upscayl-bin", "rembg", "deep-filter", "inkscape", "melt"} <= set(doctor.PROGRAMS)


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def test_launcher_where_matches_doctor():
    L = _load(SKILL / "scripts" / "dragon.py", "dragon_launcher")
    assert "fetch" in L.TOOLS
    for p in ("ffmpeg", "tesseract"):
        if doctor.find_program(p):
            assert L.find_program(p, ROOT)


def test_fetch_direct_file_logs_source(tmp_path):
    F = _load(SKILL / "tools" / "fetch" / "fetch.py", "fetch_tool")
    assert F.is_direct("https://x.org/a/b/photo.JPG") and not F.is_direct("https://youtube.com/watch?v=1")
    srv_dir = tmp_path / "srv"; srv_dir.mkdir(); (srv_dir / "pic.png").write_bytes(b"\x89PNG" + b"0" * 2048)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(srv_dir))
    handler.log_message = lambda *a, **k: None
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as httpd:
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{httpd.server_address[1]}/pic.png"
        job = tmp_path / "job"
        code = F.main([url, "--dir", str(job), "--licence", "CC0", "--note", "test"])
        httpd.shutdown()
    assert code == 0 and (job / "pic.png").stat().st_size == 2052
    line = (job / "sources.txt").read_text(encoding="utf-8").strip()
    assert "pic.png" in line and url in line and "CC0" in line
