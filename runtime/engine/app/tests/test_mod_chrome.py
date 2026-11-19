"""Chrome engine: a headless Dragon Chrome on a private port/profile — open, snapshot refs, click, type, password guard, shot, PDF."""
import os, sys, tempfile
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DRAGON_CHROME_DATA", tempfile.mkdtemp(prefix="dragon_chrome_test_"))
from engines import chrome as C

try:
    C.exe(); HAVE = True
except FileNotFoundError:
    HAVE = False
pytestmark = pytest.mark.skipif(not HAVE, reason="Google Chrome not installed")
PORT = 9333
PAGE = ("data:text/html;charset=utf-8,<title>t</title><a href='?x' onclick=\"document.title='clicked';return false\">اضغط</a>"
        "<input id=q placeholder=search><input type=password id=p>")


@pytest.fixture(scope="module")
def chrome():
    # بروفايل وحالة مؤقتين، بعيد عن بروفايل التنين الحقيقي حتى لو المحرك اتعمله import قبل كده
    real = (C.DATA, C.PROFILE, C.STATE)
    C.DATA = Path(tempfile.mkdtemp(prefix="dragon_chrome_test_"))
    C.PROFILE, C.STATE = C.DATA / "profile", C.DATA / "state.json"
    try:
        C.launch(headless=True, port=PORT)
        yield
        C.quit(port=PORT)
    finally:
        C.DATA, C.PROFILE, C.STATE = real


def test_snapshot_click_type_guard(chrome, tmp_path):
    with C.session(port=PORT) as s:
        s.go(PAGE)
        els = s.snapshot()["elements"]
        assert [e["tag"] for e in els] == ["a", "input", "input"]
        assert s.click(ref=1)["title"] == "clicked"
        s.type("التنين", selector="#q")
        assert s.evaluate("document.querySelector('#q').value") == "التنين"
        with pytest.raises(PermissionError):
            s.type("secret", selector="#p")
        assert s.evaluate("document.querySelector('#p').value") == ""
        png = Path(s.shot(tmp_path / "a.png")["file"])
        pdf = Path(s.pdf(tmp_path / "a.pdf")["file"])
    assert png.read_bytes()[:4] == b"\x89PNG" and pdf.read_bytes()[:4] == b"%PDF"


def test_tabs_open_use_close(chrome):
    with C.session(port=PORT) as s:
        s.open("data:text/html,<title>second</title>")
        assert any(t["current"] and t["title"] == "second" for t in s.tabs())
        s.use("second")
        n = len(s.tabs())
        s.close()
        assert len(s.tabs()) == n - 1
