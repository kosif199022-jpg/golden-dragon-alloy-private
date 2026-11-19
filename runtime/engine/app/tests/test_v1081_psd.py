"""v10.8.1 PSD studio: a real layered PSD with Arabic layer names round-trips, a second reader (ImageMagick) sees the
same layers, the Arabic title is in logical order (not reversed), and no background-removal model is ever fetched
without --download."""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PSD = ROOT / "tools" / "psd_studio" / "psd.py"
pytest.importorskip("psd_tools")
PIL = pytest.importorskip("PIL")
FONT = Path("C:/Windows/Fonts/arial.ttf")
needs_font = pytest.mark.skipif(not FONT.is_file(), reason=f"{FONT} not on this machine")


def _load():
    spec = importlib.util.spec_from_file_location("psd_v1081", PSD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


psd = _load()


@pytest.fixture
def spec(tmp_path):
    from PIL import Image
    Image.new("RGB", (800, 500), (40, 60, 120)).save(tmp_path / "bg.png")
    sub = Image.new("RGBA", (200, 300), (0, 0, 0, 0))
    sub.paste((200, 50, 50, 255), (50, 50, 150, 250))
    sub.save(tmp_path / "sub.png")
    s = {"size": [540, 960], "background": "#000000", "layers": [
        {"type": "image", "path": "bg.png", "fit": "cover", "name": "خلفية"},
        {"type": "fill", "color": "#000000", "opacity": 0.4, "name": "تعتيم"},
        {"type": "image", "path": "sub.png", "x": "center", "y": 400, "width": 300, "name": "البطل"},
        {"type": "title", "text": "بطلة", "font": str(FONT), "size": 80, "x": "center", "y": 100, "name": "العنوان"}]}
    (tmp_path / "spec.json").write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
    return tmp_path


@needs_font
def test_build_inspect_export_roundtrip(spec):
    r = psd.build(spec / "spec.json", spec / "out" / "p.psd")
    assert r["reopened_layers"] == 4 and Path(r["preview"]).is_file()
    info = psd.inspect(spec / "out" / "p.psd")
    assert [L["name"] for L in info["layers"]] == ["خلفية", "تعتيم", "البطل", "العنوان"]
    assert info["size"] == [540, 960] and abs(info["layers"][1]["opacity"] - 0.4) < 0.01
    assert info["layers"][2]["box"][:2] == [120, 400]
    comp, meta = psd.export(spec / "out" / "p.psd", spec / "layers")
    assert comp.is_file() and len(meta) == 4
    with pytest.raises(SystemExit):           # never overwrites
        psd.build(spec / "spec.json", spec / "out" / "p.psd")


@needs_font
@pytest.mark.skipif(not shutil.which("magick"), reason="ImageMagick not installed")
def test_second_reader_sees_the_layers(spec):
    psd.build(spec / "spec.json", spec / "p.psd")
    out = subprocess.run(["magick", "identify", str(spec / "p.psd")], capture_output=True, text=True).stdout
    assert len(out.strip().splitlines()) == 5      # composite + 4 layers


@needs_font
def test_arabic_title_is_not_reversed():
    """The first letter of «بطلة» (ب) must be on the right: compare with the title of «ب» alone."""
    import numpy as np
    whole = np.asarray(psd.title_image("بطلة", str(FONT), 120).getchannel("A")) > 0
    ba = np.asarray(psd.title_image("ب", str(FONT), 120).getchannel("A")) > 0
    cols = whole.any(axis=0).nonzero()[0]
    right_part = whole[:, cols[-1] - ba.shape[1] + 4:]
    assert right_part.sum() > 0.5 * ba.sum()       # the ب sits at the right edge, i.e. RTL order kept


def test_cutout_never_downloads_without_yes(tmp_path, monkeypatch):
    monkeypatch.setenv("U2NET_HOME", str(tmp_path / "empty"))
    with pytest.raises(psd.ModelNotCached, match="176 MB"):
        psd.rembg_model()
    assert psd.rembg_model(allow_download=True) == "u2net"
    (tmp_path / "empty").mkdir()
    (tmp_path / "empty" / "isnet-general-use.onnx").write_bytes(b"x")
    assert psd.rembg_model() == "isnet-general-use"


def test_registered():
    assert '"psd": "tools/psd_studio/psd.py"' in (ROOT / "scripts" / "dragon.py").read_text(encoding="utf-8")
    ids = {t["id"] for t in json.loads((ROOT / "app" / "data" / "own_tools.json").read_text(encoding="utf-8"))["tools"]}
    assert "psd-studio" in ids
