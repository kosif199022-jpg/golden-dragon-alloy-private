"""v1.3 T5: the stock client is bundled in tools/stock/ and `dragon.py tool stock` works (it crashed with
"No module named 'free_footage'" in v1.2).

Offline commands run through the launcher in a subprocess. Search and download run in-process against saved
NASA API answers (fixtures/stock/*.json) through a fake transport, with a tiny lavfi clip (or a stand-in) as the
file: each download gets a licence sidecar and ATTRIBUTION.md. A network failure is checked through a proxy on a
closed loopback port: one clear line and a hint, never a traceback. No internet, no owner files, no keys."""
import importlib, io, json, os, re, shutil, subprocess, sys, zlib, struct
from pathlib import Path
from unittest import mock
import pytest

ROOT = Path(__file__).resolve().parent.parent            # app/
SKILL = ROOT.parent
STOCK = SKILL / "tools" / "stock"
LAUNCHER = SKILL / "scripts" / "dragon.py"
FIX = Path(__file__).resolve().parent / "fixtures" / "stock"
if not (STOCK / "stock.py").exists():
    pytest.skip(f"{STOCK} is not in this copy (only app/ was copied)", allow_module_level=True)

NO_KEYS = {"PEXELS_API_KEY": "", "PIXABAY_API_KEY": "", "UNSPLASH_ACCESS_KEY": ""}
DEAD = "http://127.0.0.1:9"                               # discard port: nothing listens, so every request is refused
VID, PID = "DRAGON_TEST_VERTICAL_NILE", "DRAGON_TEST_DUNES"


def _load():
    keep = sys.dont_write_bytecode
    sys.dont_write_bytecode = True                        # no __pycache__ inside the skill's tools/stock
    try:
        if str(STOCK) not in sys.path:
            sys.path.insert(0, str(STOCK))
        for lazy in ("_secrets", "stock_fetch"):          # imported later by free_footage._sibling: load them now
            importlib.import_module(lazy)
        return importlib.import_module("stock"), importlib.import_module("free_footage"), \
            importlib.import_module("free_photos")
    finally:
        sys.dont_write_bytecode = keep


ST, FF, FP = _load()


def launch(*args, cwd, env_extra=None):
    env = {**os.environ, **NO_KEYS, "PYTHONDONTWRITEBYTECODE": "1", **(env_extra or {})}
    return subprocess.run([sys.executable, str(LAUNCHER), "tool", "stock", *args], cwd=cwd, env=env,
                          capture_output=True, text=True, encoding="utf-8", timeout=120)


# ------------------------------------------------------------------------------------------------- fake network

class Headers(dict):
    def get(self, k, d=None):
        for kk, v in self.items():
            if kk.lower() == k.lower():
                return v
        return d

    def get_all(self, k, d=None):
        v = self.get(k)
        return [v] if v is not None else d

    def get_content_type(self):
        return (self.get("Content-Type") or "application/octet-stream").split(";")[0]


class Resp:
    def __init__(self, url, body, ctype):
        self.url, self.status, self._b, self._p = url, 200, body, 0
        self.headers = Headers({"Content-Type": ctype, "Content-Length": str(len(body))})

    def read(self, n=-1):
        n = len(self._b) - self._p if n is None or n < 0 else n
        c = self._b[self._p:self._p + n]
        self._p += len(c)
        return c

    def getheader(self, k, d=None):
        return self.headers.get(k, d)

    def close(self):
        pass

    def geturl(self):
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Transport:
    """URL regex -> (body, content type); records the URLs; any other request fails the test."""

    def __init__(self, routes):
        self.routes, self.urls = routes, []

    def __call__(self, req, timeout):
        url = req.full_url
        self.urls.append(url)
        for rx, (body, ctype) in self.routes:
            if re.search(rx, url):
                return Resp(url, body, ctype)
        raise AssertionError(f"unexpected request {url}")


def tiny_mp4(tmp: Path) -> bytes:
    ff = shutil.which("ffmpeg")
    if ff:
        out = tmp / "tiny.mp4"
        r = subprocess.run([ff, "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=270x480:r=30:d=2",
                            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                            str(out)], capture_output=True, timeout=60)
        if r.returncode == 0 and out.stat().st_size > 0:
            return out.read_bytes()
    return b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 2048   # a stand-in with an mp4 header


def tiny_png() -> bytes:
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + b"\xc8\x96\x32" * 4 for _ in range(8))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 8, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def fx(name) -> bytes:
    return (FIX / name).read_bytes()


def video_routes(mp4):
    return [(r"images-api\.nasa\.gov/search", (fx("nasa_video_search.json"), "application/json")),
            (r"images-api\.nasa\.gov/asset/", (fx("nasa_video_asset.json"), "application/json")),
            (r"/metadata\.json$", (fx("nasa_video_metadata.json"), "application/json")),
            (r"~orig\.mp4$", (mp4, "video/mp4"))]


# ------------------------------------------------------------------------------------------------- tests

def test_launcher_offline_commands_exit_0(tmp_path):
    h = launch("--help", cwd=tmp_path)
    assert h.returncode == 0 and "search" in h.stdout and "download" in h.stdout, h.stderr
    s = launch("sources", cwd=tmp_path)
    assert s.returncode == 0, s.stderr
    assert "mixkit" in s.stdout and "coverr" in s.stdout and "Traceback" not in s.stderr
    assert launch("sources", "--kind", "photo", cwd=tmp_path).returncode == 0
    c = launch("check", cwd=tmp_path)
    assert c.returncode == 0 and "17 sources" in c.stdout, c.stdout + c.stderr
    assert launch("photo", "sources", "--json", cwd=tmp_path).returncode == 0
    assert launch("video", "sources", "--find", "nasa", cwd=tmp_path).returncode == 0
    (tmp_path / "empty").mkdir()
    assert launch("credits", str(tmp_path / "empty"), cwd=tmp_path).returncode == 0
    assert (tmp_path / "empty" / "ATTRIBUTION.md").is_file()
    bad = launch("nonsense", cwd=tmp_path)
    assert bad.returncode == 2 and "unknown stock command" in bad.stderr and "Traceback" not in bad.stderr
    assert not list(STOCK.rglob("__pycache__")), "the launcher left __pycache__ in the skill"


def test_network_failure_is_one_clear_line_not_a_traceback(tmp_path):
    env = {k: DEAD for k in ("HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy")}
    env.update(NO_PROXY="", no_proxy="")
    runs = [launch("search", "night city", "--sources", "coverr,nasa", "--limit", "2", "--delay", "0", cwd=tmp_path,
                   env_extra=env),
            launch("search", "dunes", "--kind", "photo", "--sources", "nasa", "--delay", "0", cwd=tmp_path, env_extra=env),
            launch("download", "nasa:" + VID, "--out", str(tmp_path / "clips"), "--delay", "0", cwd=tmp_path,
                   env_extra=env),
            launch("pexels", "5057523", "-o", str(tmp_path / "px"), "--dry-run", cwd=tmp_path, env_extra=env)]
    for r in runs:
        both = r.stdout + r.stderr
        assert r.returncode != 0, both
        assert "Traceback" not in both, both
        assert "hint: no network reached the site" in r.stderr, both
    assert not list((tmp_path / "clips").glob("*.mp4")) if (tmp_path / "clips").exists() else True


def test_short_pexels_id_is_a_message_not_an_attributeerror(tmp_path):
    r = launch("download", "pexels:1", "--out", str(tmp_path / "c"), cwd=tmp_path)
    assert r.returncode == 1 and "Traceback" not in r.stderr
    assert "not a pexels clip id" in r.stdout + r.stderr


def test_video_search_and_download_with_saved_answers(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for k, v in NO_KEYS.items():
        monkeypatch.setenv(k, v)
    t = Transport(video_routes(tiny_mp4(tmp_path)))
    monkeypatch.setattr(FF, "make_http", lambda args: FF.Http(delay=0, transport=t, sleep=lambda s: None))
    out = io.StringIO()
    with mock.patch("sys.stdout", out):
        assert ST.main(["search", "nile", "--sources", "nasa", "--orientation", "portrait", "--limit", "2"]) == 0
    res = json.loads((tmp_path / "out" / "free-footage" / "last_search.json").read_text(encoding="utf-8"))
    assert [r["id"] for r in res["results"]] == ["nasa:" + VID]
    assert (res["results"][0]["width"], res["results"][0]["height"]) == (270, 480)
    assert "dragon.py tool stock video download" in out.getvalue()
    clips = tmp_path / "job" / "stock"
    with mock.patch("sys.stdout", io.StringIO()):
        assert ST.main(["download", "nasa:" + VID, "--out", str(clips), "--quality", "1080"]) == 0
    files = [p for p in clips.iterdir() if p.suffix == ".mp4"]
    assert len(files) == 1 and files[0].stat().st_size > 0
    side = json.loads(files[0].with_name(files[0].name + ".json").read_text(encoding="utf-8"))
    assert side["result"]["id"] == "nasa:" + VID and side["licence"]["name"] and side["sha256"]
    assert side["result"]["page_url"].startswith("https://images.nasa.gov/") and side["attribution"]
    att = (clips / "ATTRIBUTION.md").read_text(encoding="utf-8")
    assert "Synthetic Nile at night" in att and "dragon.py tool stock video credits" in att
    assert all("nasa.gov" in u for u in t.urls)


def test_photo_search_and_download_with_saved_answers(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for k, v in NO_KEYS.items():
        monkeypatch.setenv(k, v)
    t = Transport([(r"images-api\.nasa\.gov/search", (fx("nasa_photo_search.json"), "application/json")),
                   (r"\.png$", (tiny_png(), "image/png"))])
    real = FF.Http
    monkeypatch.setattr(FF, "Http", lambda *a, **k: real(delay=0, transport=t, sleep=lambda s: None))
    with mock.patch("sys.stdout", io.StringIO()):
        assert ST.main(["search", "dunes", "--kind", "photo", "--sources", "nasa"]) == 0
    res = json.loads((tmp_path / "out" / "free-photos" / "last_search.json").read_text(encoding="utf-8"))
    assert [r["id"] for r in res["results"]] == ["nasa:" + PID]
    # --kind is picked from the results files: this id is only in the photo results
    assert ST.kind_for_ids(["nasa:" + PID]) == "photo"
    out = tmp_path / "pics"
    with mock.patch("sys.stdout", io.StringIO()):
        assert ST.main(["download", "nasa:" + PID, "--out", str(out)]) == 0
    pics = [p for p in out.iterdir() if p.suffix.lower() == ".png"]
    assert len(pics) == 1
    side = json.loads(pics[0].with_name(pics[0].name + ".json").read_text(encoding="utf-8"))
    assert side["id"] == "nasa:" + PID and side["licence"]
    assert "Synthetic dunes" in (out / "ATTRIBUTION.md").read_text(encoding="utf-8")


def test_kind_for_ids_without_results(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert ST.kind_for_ids(["mixkit:41865"]) == "video"
    assert ST.kind_for_ids(["openverse:abc", "met:1"]) == "photo"
    assert ST.kind_for_ids(["met:1", "coverr:x"]) == "video"
    assert ST.kind_for_ids([]) == "video"


def test_launcher_hands_the_bundled_client_to_the_montage_station(monkeypatch):
    sys.path.insert(0, str(ROOT))
    from engines.dragon_montage import stock as station
    monkeypatch.delenv("DRAGON_FREE_FOOTAGE", raising=False)
    with pytest.raises(SystemExit):                       # no guessing without the launcher: never a surprise search
        station.client()
    src = LAUNCHER.read_text(encoding="utf-8")
    assert '"stock": "tools/stock/stock.py"' in src
    probe = ("import os, runpy, subprocess, sys\n"
             "seen = {}\n"
             "subprocess.call = lambda args, env=None: seen.setdefault('ff', (env or {}).get('DRAGON_FREE_FOOTAGE')) and 0\n"
             "mod = runpy.run_path(sys.argv[1])\n"
             "mod['run'](['-c', 'pass'])\n"
             "print(seen['ff'])\n")
    env = {k: v for k, v in os.environ.items() if k != "DRAGON_FREE_FOOTAGE"}
    r = subprocess.run([sys.executable, "-B", "-c", probe, str(LAUNCHER)], capture_output=True, text=True, env=env,
                       timeout=60)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == str(STOCK / "free_footage.py")
    with mock.patch.dict(os.environ, {"DRAGON_FREE_FOOTAGE": str(STOCK / "free_footage.py")}):
        assert station.client() == STOCK / "free_footage.py"
