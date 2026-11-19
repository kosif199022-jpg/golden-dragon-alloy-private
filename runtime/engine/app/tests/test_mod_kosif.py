"""engines.kosif: accelerated downloads against a local ranged test server (no internet needed).
Checks: byte-exact SHA-256 with 8 connections, Content-Disposition names, no-Range fallback, a server that allows only
3 connections, fatal 403, probe, resume of an interrupted run, and the `dragon run kosif fetch --json` CLI."""
import hashlib, json, os, re, subprocess, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
STATE = tempfile.mkdtemp(prefix="kosif_state_")
os.environ["KOSIF_DATA_DIR"] = STATE            # never touch the real app or Dragon state

from engines import kosif  # noqa: E402

DATA = os.urandom(12 * 1024 * 1024 + 12345)
SHA = hashlib.sha256(DATA).hexdigest()
LOCK, ACTIVE = threading.Lock(), [0]
DELAY = [0.0]


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith("/forbidden"):
            self.send_response(403); self.send_header("Content-Length", "0"); self.end_headers(); return
        if self.path.startswith("/limited"):
            with LOCK:
                if ACTIVE[0] >= 3:
                    self.send_response(503); self.send_header("Content-Length", "0"); self.end_headers(); return
                ACTIVE[0] += 1
            try:
                return self.serve(True)
            finally:
                with LOCK:
                    ACTIVE[0] -= 1
        return self.serve(self.path.startswith("/range"))

    def serve(self, ranged):
        s, e = 0, len(DATA) - 1
        rng = self.headers.get("Range")
        if ranged and rng:
            m = re.match(r"bytes=(\d+)-(\d*)", rng)
            s, e = int(m.group(1)), (int(m.group(2)) if m.group(2) else e)
            self.send_response(206); self.send_header("Content-Range", f"bytes {s}-{e}/{len(DATA)}")
        else:
            self.send_response(200)
        self.send_header("Content-Length", str(e - s + 1))
        self.send_header("Content-Disposition", "attachment; filename*=UTF-8''%D9%84%D9%82%D8%B7%D8%A9.bin")
        self.end_headers()
        try:
            for i in range(s, e + 1, 65536):
                self.wfile.write(DATA[i:min(i + 65536, e + 1)])
                if DELAY[0]:
                    time.sleep(DELAY[0])
        except OSError:
            pass


@pytest.fixture(scope="module")
def base():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _one(res):
    assert len(res) == 1
    return res[0]


def test_segmented_exact(base, tmp_path):
    r = _one(kosif.fetch(f"{base}/range/a", tmp_path, connections=8, log=lambda *_: None))
    assert r["status"] == "done", r["error"]
    assert r["resumable"] and r["sha256"] == SHA and r["size"] == len(DATA)
    assert Path(r["path"]).name == "لقطة.bin"


def test_no_range_fallback(base, tmp_path):
    r = _one(kosif.fetch(f"{base}/plain/b", tmp_path, connections=8, log=lambda *_: None))
    assert r["status"] == "done" and not r["resumable"] and r["sha256"] == SHA


def test_connection_limited_server(base, tmp_path):
    r = _one(kosif.fetch(f"{base}/limited/c", tmp_path, connections=8, log=lambda *_: None))
    assert r["status"] == "done", r["error"]
    assert r["sha256"] == SHA


def test_forbidden_is_fast_error(base, tmp_path):
    t0 = time.time()
    r = _one(kosif.fetch(f"{base}/forbidden/x.zip", tmp_path, log=lambda *_: None))
    assert r["status"] == "error" and "403" in r["error"] and time.time() - t0 < 10


def test_probe(base):
    p = kosif.probe(f"{base}/range/p")
    assert p["size"] == len(DATA) and p["resumable"] and p["filename"] == "لقطة.bin"


def test_resume_interrupted_run(base, tmp_path):
    core = kosif._core()
    m = core.Manager()
    m.settings.update({"download_dir": str(tmp_path), "use_categories": False})
    DELAY[0] = 0.01
    try:
        d = m.add(f"{base}/range/resume", directory=str(tmp_path), connections=4)
        end = time.time() + 30
        while d.downloaded < 2_000_000 and time.time() < end:
            time.sleep(0.05)
        m.shutdown()                       # simulate the Dragon being stopped mid-download
        got = d.downloaded
        assert 0 < got < len(DATA)
    finally:
        DELAY[0] = 0.0
    lines = []
    r = _one(kosif.fetch(f"{base}/range/resume", tmp_path, connections=4, log=lines.append))
    assert any("resuming" in x for x in lines)
    assert r["status"] == "done" and r["sha256"] == SHA


def test_cli_fetch_json(base, tmp_path):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, "-m", "dragon", "run", "kosif", "fetch", f"{base}/range/cli", "-o", str(tmp_path),
                        "-c", "6", "--json"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env=env, timeout=180)
    assert p.returncode == 0, p.stderr
    r = _one(json.loads(p.stdout))
    assert r["status"] == "done" and r["sha256"] == SHA
