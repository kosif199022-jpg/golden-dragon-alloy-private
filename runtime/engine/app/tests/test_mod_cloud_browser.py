"""Cloud browser «سحاب»: the input normaliser, and a live server on a private port — auth, a streamed frame, navigation."""
import asyncio, json, os, sys, tempfile
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SAHAB_DATA", tempfile.mkdtemp(prefix="sahab_test_"))
# v10.16.1: skip cleanly when the optional deps are missing (was a collection ERROR that stopped the whole suite)
aiohttp = pytest.importorskip("aiohttp")
pytest.importorskip("playwright")
from engines import cloud_browser as CB
from engines.cloud_browser.server import resolve_input
PORT = 8833


def test_resolve_input():
    assert resolve_input("example.com", "ddg") == "https://example.com"
    assert resolve_input("localhost:3000", "ddg") == "http://localhost:3000"
    assert resolve_input("file:///C:/x", "ddg").startswith("https://duckduckgo.com/?q=")
    assert resolve_input("javascript:alert(1)", "ddg").startswith("https://duckduckgo.com/?q=")
    assert resolve_input("سحاب", "google").startswith("https://www.google.com/search?q=")


@pytest.fixture(scope="module")
def server():
    # عزل كامل عن بيانات المستخدم الحقيقية حتى لو المحرك اتعمله import قبل كده بمسار تاني
    real = (CB.DATA, CB.STATE)
    CB.DATA = Path(tempfile.mkdtemp(prefix="sahab_test_"))
    CB.STATE = CB.DATA / "engine.json"
    try:
        st = CB.start(port=PORT, extra=("--no-doh",))
        assert st["port"] == PORT and CB.DATA.as_posix() in Path(st["data"]).as_posix()
        yield st
        CB.stop()
    finally:
        CB.DATA, CB.STATE = real


def test_live_session(server):
    async def go():
        jar = aiohttp.CookieJar(unsafe=True)
        async with aiohttp.ClientSession(cookie_jar=jar) as s:
            async with s.get(f"http://127.0.0.1:{PORT}/api/state") as r:
                assert r.status == 401
            await s.get(server["url"])
            async with s.ws_connect(f"http://127.0.0.1:{PORT}/ws") as ws:
                first = json.loads((await ws.receive()).data)
                assert first["t"] == "tabs" and first["tabs"]
                await ws.send_str(json.dumps({"t": "resize", "w": 640, "h": 400, "dpr": 1}))
                await ws.send_str(json.dumps({"t": "nav", "url": "data:text/html,x"}))  # data: is refused -> search URL
                frame = None
                for _ in range(200):
                    m = await asyncio.wait_for(ws.receive(), 20)
                    if m.type == aiohttp.WSMsgType.BINARY:
                        frame = m.data
                        break
                assert frame and frame[:2] == b"\xff\xd8"  # JPEG
    asyncio.run(go())
