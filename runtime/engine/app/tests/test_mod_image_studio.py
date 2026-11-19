"""image_studio: Arabic titles shape (joined, RTL), exact frame sizes, grades obey their maths, 4x upscale, review sheet."""
import subprocess, sys
from pathlib import Path
import numpy as np
import pytest
from PIL import Image, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from engines import image_studio as I


@pytest.fixture
def photo(tmp_path):
    rng = np.random.default_rng(1)
    y, x = np.mgrid[0:300, 0:480]
    arr = np.stack([x / 480 * 255, y / 300 * 255, 128 + 60 * np.sin(x / 20)], -1) + rng.normal(0, 4, (300, 480, 3))
    p = tmp_path / "photo.jpg"; Image.fromarray(arr.clip(0, 255).astype(np.uint8)).save(p, quality=95)
    return p


def test_arabic_is_joined_not_isolated():
    """Shaped «سلام» must be narrower than its letters drawn one by one (isolated forms) — proves joining works."""
    f = ImageFont.truetype(I.font_path("cairo"), 120)
    s, kw = I._shape("سلام")
    joined = f.getbbox(s, **kw)[2]
    isolated = sum(f.getbbox(ch)[2] for ch in "سلام")
    assert joined < isolated * 0.9


def test_title_on_blank_and_on_image(tmp_path, photo):
    r = I.title(tmp_path / "t.png", "التنين الأسود\nمونتاج", size="1080x1920", font="ruqaa")
    assert (r["width"], r["height"]) == (1080, 1920) and r["text"]["rtl"] and r["text"]["lines"] == 2
    a = np.asarray(Image.open(tmp_path / "t.png").convert("L"))
    assert (a > 200).mean() > 0.005          # white text really drawn
    r2 = I.title(tmp_path / "t2.jpg", "Hello", src=photo)
    assert (r2["width"], r2["height"]) == (480, 300) and not r2["text"]["rtl"]


def test_title_autofits_long_text(tmp_path):
    r = I.title(tmp_path / "long.png", "جملة طويلة جدا جدا لازم تصغر لوحدها عشان تدخل في عرض الشاشة", size="1080x1920", px=200)
    assert r["text"]["px"] < 200


@pytest.mark.parametrize("mode", ["blur", "cover", "contain"])
def test_reframe_exact_size(tmp_path, photo, mode):
    r = I.reframe(photo, tmp_path / f"{mode}.jpg", "1080x1920", mode)
    assert (r["width"], r["height"]) == (1080, 1920)


def test_grade_noir_is_monochrome_and_looks_listed(tmp_path, photo):
    I.grade(photo, tmp_path / "n.png", "noir", grain=0)
    a = np.asarray(Image.open(tmp_path / "n.png")).astype(int)
    assert np.abs(a[..., 0] - a[..., 1]).max() <= 1 and np.abs(a[..., 1] - a[..., 2]).max() <= 1
    assert {"teal_orange", "noir", "warm_gold"} <= set(I.looks())
    with pytest.raises(KeyError):
        I.grade(photo, tmp_path / "x.png", "nope")


def test_grade_strength_zero_is_identity(tmp_path, photo):
    I.grade(photo, tmp_path / "id.png", "teal_orange", strength=0, vignette=0, grain=0)
    a = np.asarray(Image.open(tmp_path / "id.png")).astype(int); b = np.asarray(Image.open(photo).convert("RGB")).astype(int)
    assert np.abs(a - b).max() <= 1


def test_cover(tmp_path, photo):
    r = I.cover(photo, tmp_path / "c.jpg", "حكاية الجندي", sub="فيلم قصير", look="warm_gold")
    assert (r["width"], r["height"]) == (1080, 1920) and r["text"]["rtl"]


def test_upscale_4x(tmp_path, photo):
    small = tmp_path / "s.png"; Image.open(photo).resize((120, 75)).save(small)
    r = I.upscale(small, tmp_path / "u.png", 4)
    assert (r["width"], r["height"]) == (480, 300)


def test_sheet(tmp_path):
    clip = tmp_path / "c.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x568:d=3:r=30", "-pix_fmt", "yuv420p", str(clip)], check=True)
    r = I.sheet(clip, tmp_path / "sheet.jpg", n=6, cols=3, width=160)
    assert len(r["frames"]) == 6 and r["width"] == 3 * 160 + 4 * 6


@pytest.mark.skipif(not any((Path.home() / ".u2net").glob("isnet-general-use*.onnx")), reason="rembg model not downloaded yet")
def test_cutout_has_alpha(tmp_path, photo):
    r = I.cutout(photo, tmp_path / "cut.png")
    assert r["mode"] == "RGBA"
