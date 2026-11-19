"""v1.2 styles kit: tools/styles/build_style.py turns one JSON spec into a canvas film in one of the owner's six proven
styles (nil, beat, wall, medal, chapters, clean). Each style builds a 4 s demo from a testsrc2 clip and a still image
made here (ffmpeg lavfi in tmp_path, under Arabic names on purpose) and renders 3 stills, which must exist, be 1080x1920
and not be black; a page error fails the build. One style is rendered in full (2 s, with a song) through the CLI to prove
render.cjs + the black scan + the exact mux. Spec checks, crop maths, the beat grid, the mix and the kit's sources are
tested without a browser. No network, no owner files; every build folder is deleted after its checks (disk is tight)."""
import json, re, shutil, subprocess, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent          # app/
KIT = ROOT.parent / "tools" / "styles"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(KIT))
from engines.media import exe, ffmpeg, probe  # noqa: E402

try:
    exe("ffmpeg"), exe("ffprobe")
except FileNotFoundError:
    pytest.skip("ffmpeg/ffprobe not installed", allow_module_level=True)

import build_style as B  # noqa: E402

try:
    from PIL import Image, ImageStat
except ImportError:  # only the still checks need Pillow
    Image = ImageStat = None

NODE = shutil.which("node")
STYLES = ["nil", "beat", "wall", "medal", "chapters", "clean"]
CREDIT = ["مونتاج وإخراج اختبار", "تابعني"]
MARK = "© اختبار"
# the same module roots as loadPlaywright() in render.cjs (argv[1] = the renderer's folder)
PW_CHECK = ("const p=require('path'),fs=require('fs');const r=[process.env.KOSIF_ROOT,"
            "p.join(process.env.USERPROFILE||process.env.HOME||'','kosif-tool'),process.argv[1]].filter(Boolean)"
            ".map(x=>p.join(x,'node_modules'));try{const pw=require(require.resolve('playwright',{paths:r}));"
            "process.exit(fs.existsSync(pw.chromium.executablePath())?0:1)}catch(e){process.exit(1)}")

CLIP, STILL = "مصادر/لقطة.mp4", "مصادر/صورة.png"


def clip(**kw):
    return {"src": CLIP, **kw}


def still(**kw):
    return {"src": STILL, **kw}


BASE = {"duration": 4, "watermark": MARK, "credit": CREDIT}
DEMOS = {  # style -> (spec, still times): 4 s each, every layer of the style on screen at least once
    "nil": ({**BASE, "style": "nil", "leak": True,
             "shots": [clip(ss=0.5, start=0, end=2.2, focus=[0.3, 0.5]), still(start=2.2, end=4, zoom=1.2)],
             "title": {"text": "عنوان تجريبي", "start": 0.2, "end": 1.8},
             "lines": [{"text": "سطر بالعربي كلمة كلمة", "start": 1.0, "end": 3.0}],
             "end": {"at": 3.0, "title": "النهاية"}}, [1.0, 2.4, 3.5]),
    "beat": ({**BASE, "style": "beat", "beat": {"period": 0.5, "phase": 0.1},
              "shots": [clip(ss=0.2, beats=2), still(beats=2),
                        {"tri": [clip(ss=1.0), still(zoom=1.5), clip(ss=3.0, focus=[0.8, 0.5])], "beats": 3},
                        clip(ss=4.0, rest=True)],
              "slams": [{"text": "اسم…", "beats": [0, 2]}, ["الأولى", 1.2, 2.0]],
              "end": {"title": "النهاية", "sub": "سطر فرعي"}}, [0.6, 2.9, 3.7]),
    "wall": ({**BASE, "style": "wall",
              "tiles": [clip(ss=0), still(), clip(ss=1), clip(ss=2), clip(ss=3, focus=[0.2, 0.5]), still(zoom=2)],
              "heroes": [{"tile": 4, "start": 0, "end": 1.5}],
              "title": {"text": "حلوة يا بلدي", "start": 0.3, "end": 1.4},
              "lines": [{"text": "سطر على الحيطة", "start": 1.6, "end": 3.0}],
              "end": {"at": 3.3, "title": "النهاية", "sub": "سطر فرعي"}}, [0.8, 2.5, 3.6]),
    "medal": ({**BASE, "style": "medal",
               "shots": [clip(ss=0.5, start=0.8, end=2.0), still(start=2.0, end=3.2, move="iris")],
               "title": {"text": "اسم البطل"},
               "lines": [{"text": "سطر تحت اللقطة", "start": 1.7, "end": 2.9}],
               "end": {"at": 3.0, "title": "النهاية"}}, [1.2, 2.4, 3.5]),
    "chapters": ({**BASE, "style": "chapters",
                  "shots": [clip(ss=0.5, start=0, end=2.0), still(start=2.0, end=4.0, broll=True)],
                  "title": {"text": "عنوان", "sub": "فرعي", "start": 0.2, "end": 1.2},
                  "chapters": [{"n": "١", "title": "البداية", "start": 1.2, "dur": 1.6}],
                  "lines": [{"text": "كلامها في مكانه الثابت", "start": 1.3, "end": 2.2}],
                  "verses": [{"text": "سطر الآية الأول|سطر الآية الثاني", "ref": "سورة الفاتحة، ١", "start": 2.2, "end": 3.4}],
                  "lyrics": [{"text": "سطر من الأغنية", "start": 0.4, "end": 1.2}],
                  "labels": [{"text": "عنوان الكارت", "sub": "سطر ذهبي", "start": 2.4, "end": 3.2}],
                  "lowers": [{"text": "اسم المتحدث", "kicker": "صفة", "start": 1.4, "end": 2.2}],
                  "end": {"at": 3.2, "title": "النهاية", "sub": "سطر", "sub2": "سطر ذهبي", "flag": True}},
                 [1.0, 2.5, 3.6]),
    "clean": ({**BASE, "style": "clean",
               "shots": [clip(ss=0.5, start=0, end=2.0), still(start=2.0, end=4.0, broll=True)],
               "title": {"text": "عنوان", "start": 0.1, "end": 1.5},
               "lines": [{"text": "كلام بخط الرقعة|في سطرين", "start": 1.6, "end": 3.2}],
               "end": {"at": 3.2, "title": "النهاية"}}, [0.8, 2.4, 3.7]),
}


@pytest.fixture(scope="module")
def media(tmp_path_factory):
    """A 6 s testsrc2 clip (landscape, so every shot is really cropped), a portrait still and a 6 s tone."""
    root = tmp_path_factory.mktemp("styles")
    d = root / "مصادر"
    d.mkdir()
    ffmpeg("-f", "lavfi", "-i", "testsrc2=s=640x360:d=6:r=30", "-c:v", "libx264", "-preset", "ultrafast",
           "-pix_fmt", "yuv420p", d / "لقطة.mp4")
    ffmpeg("-f", "lavfi", "-i", "testsrc2=s=480x640:d=1:r=1", "-frames:v", "1", d / "صورة.png")
    ffmpeg("-f", "lavfi", "-i", "sine=f=330:d=6", "-c:a", "pcm_s16le", d / "أغنية.wav")
    return root


def write_spec(root, name, spec):
    p = root / f"{name}.json"
    p.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    return p


@pytest.fixture(scope="module")
def renderer():
    if not NODE:
        pytest.skip("node not found")
    try:
        rend = B.find_renderer()
    except B.BuildError as e:
        pytest.skip(str(e))
    if subprocess.run([NODE, "-e", PW_CHECK, str(rend.parent)], capture_output=True, timeout=60).returncode:
        pytest.skip("playwright + chromium not found for render.cjs")
    return rend


def page_cfg(out):
    text = (out / "index.html").read_text(encoding="utf-8")
    m = re.search(r"window\.CFG=(\{.*?\});</script>", text, re.S)
    return json.loads(m.group(1))


def luma(path):
    with Image.open(path) as im:
        return im.size, ImageStat.Stat(im.convert("L")).mean[0]


# ---------------------------------------------------------------- stills for every style

@pytest.mark.parametrize("style", STYLES)
def test_style_demo_stills(style, media, renderer, tmp_path):
    if Image is None:
        pytest.skip("Pillow not installed")
    spec, times = DEMOS[style]
    out = tmp_path / f"بناء {style}"
    logs = []
    rep = B.build(write_spec(media, style, spec), out, stills=times, renderer=renderer, log=logs.append)
    try:
        assert rep["ok"], (rep.get("error"), logs)
        assert rep["stills"]["page_errors"] == []
        files = [Path(f) for f in rep["stills"]["files"]]
        assert [f.name for f in files] == [f"still_{t:.3f}.png" for t in times]
        sums = set()
        for f in files:
            size, y = luma(f)
            assert size == (1080, 1920), (f.name, size)
            assert y > 20, f"{style} {f.name} is black (mean luma {y:.1f})"
            sums.add(f.read_bytes())
        assert len(sums) == len(files), "stills at different times must differ"
        cfg = page_cfg(out)  # the page draws from the spec, not from code
        assert cfg["style"] == style and cfg["watermark"] == MARK and cfg["credit"] == CREDIT
        # v10.15: a spec with Quran verses also gets Scheherazade (build_style adds it; Amiri lifts U+0670)
        want = B.STYLES[style]["fonts"] + (["Scheherazade"] if DEMOS[style][0].get("verses")
                                           and "Scheherazade" not in B.STYLES[style]["fonts"] else [])
        assert [f for f, _ in cfg["fonts"]] == want
        for fam in want:
            assert (out / "fonts" / B.FONTS[fam][0]).is_file()
        assert (out / "common.js").is_file() and (out / f"{style}.js").is_file()
    finally:
        shutil.rmtree(out, ignore_errors=True)


def test_medal_card_moves(media, renderer, tmp_path):
    """The card run of the medal style: the card closes, flips edge-on, then floods gold (no page errors, no black)."""
    if Image is None:
        pytest.skip("Pillow not installed")
    spec = {**BASE, "style": "medal", "duration": 6,
            "shots": [clip(ss=0.0, start=1.0, end=1.9), still(start=1.9, end=3.6, move="iris"),
                      clip(ss=1.0, start=3.6, end=4.6, move="flip"), still(start=4.6, end=6.0, move="flood", zoom=1.5)],
            "end": {"at": 5.2, "title": "النهاية"}}
    out = tmp_path / "ميدالية"
    rep = B.build(write_spec(media, "medal_moves", spec), out, stills=[3.1, 3.62, 4.45], renderer=renderer,
                  log=lambda *_: None)
    try:
        assert rep["ok"] and rep["stills"]["page_errors"] == [], rep.get("error")
        card, edge, flood = rep["stills"]["files"]
        for f in (card, edge, flood):
            assert luma(f)[1] > 20
        with Image.open(flood) as im:
            r, g, b = ImageStat.Stat(im.convert("RGB")).mean
        assert r > b + 40 and g > b + 20, f"the flood should be gold, mean RGB {r:.0f},{g:.0f},{b:.0f}"
        cfg = page_cfg(out)
        assert [s.get("move") for s in cfg["shots"]] == ["grow", "iris", "flip", "flood"]
    finally:
        shutil.rmtree(out, ignore_errors=True)


# ---------------------------------------------------------------- the full path once

def test_full_render_and_exact_mux(media, renderer, tmp_path):
    """CLI --render: render.cjs, black scan, exact mux with the mixed song -> 60 frames, AAC, 1080x1920, no black."""
    from engines import qa
    spec = {**BASE, "style": "nil", "duration": 2, "name": "فيلم تجريبي",
            "song": {"path": "مصادر/أغنية.wav", "start": 0.5, "fade_in": 0.3, "fade_out": 0.5},
            "shots": [clip(ss=0.5, start=0, end=1.0), still(start=1.0, end=2.0)],
            "title": {"text": "عنوان", "start": 0.1, "end": 0.9},
            "lines": [{"text": "سطر قصير", "start": 0.8, "end": 1.6}],
            "end": {"at": 1.4, "title": "النهاية"}}
    out = tmp_path / "فيلم كامل"
    r = subprocess.run([sys.executable, str(KIT / "build_style.py"), str(write_spec(media, "full", spec)),
                        "--out", str(out), "--render"], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300)
    try:
        assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
        rep = json.loads((out / "build_report.json").read_text(encoding="utf-8"))
        final = Path(rep["final"])
        assert final.name == "فيلم تجريبي.mp4" and final.is_file()
        assert rep["render"]["page_errors"] == []
        assert rep["render"]["recycle"] == ("recycle" in B.renderer_flags(renderer))
        assert rep["qa"]["ok"] and rep["qa"]["body_runs"] == []
        assert rep["mux"]["ok"] and rep["mux"]["frames"] == 60 and rep["mux"]["expected_frames"] == 60
        j = probe(final)
        v = next(s for s in j["streams"] if s["codec_type"] == "video")
        a = next(s for s in j["streams"] if s["codec_type"] == "audio")
        assert (v["width"], v["height"]) == (1080, 1920) and a["codec_name"] == "aac"
        assert qa.frame_check(final, expect_duration=2)["frames_ok"]
        assert qa.audio_check(final) == []
        assert qa.black_runs(final, allow_head=0.2, allow_tail=0.5)["body"] == []
    finally:
        shutil.rmtree(out, ignore_errors=True)


# ---------------------------------------------------------------- page and mix (no browser)

def test_page_mix_and_reuse_without_browser(media, tmp_path):
    spec = {**DEMOS["clean"][0], "song": {"path": "مصادر/أغنية.wav", "start": 1.0}}
    path = write_spec(media, "mix", spec)
    out = tmp_path / "صفحة"
    try:
        rep = B.build(path, out, log=lambda *_: None)
        assert rep["ok"], rep.get("error")
        cfg = page_cfg(out)
        assert [s["d"] for s in cfg["shots"]] == ["frames/S00", "frames/S01"]
        for s in cfg["shots"]:  # 2 s slot + 0.7 s tail at 30 fps
            assert s["n"] == len(list((out / s["d"]).glob("f*.jpg"))) == 81
            assert 0 <= s["fy"] <= 1
        pic = probe(out / "frames" / "S00" / "f0001.jpg")["streams"][0]
        assert (pic["width"], pic["height"]) == (1080, 1920)
        a = next(s for s in probe(out / "mix.m4a")["streams"] if s["codec_type"] == "audio")
        assert a["codec_name"] == "aac" and int(a["sample_rate"]) == 48000 and abs(float(a["duration"]) - 4.0) < 0.03
        again = B.build(path, out, embed_fonts=True, log=lambda *_: None)  # same cuts: reused, fonts inside the page
        assert all(c["reused"] for c in again["cuts"])
        assert "data:font/ttf;base64," in (out / "index.html").read_text(encoding="utf-8")
    finally:
        shutil.rmtree(out, ignore_errors=True)


# ---------------------------------------------------------------- spec, crop, beat grid

def test_examples_are_clean_specs():
    seen = set()
    for p in sorted((KIT / "examples").glob("*.json")):
        spec = json.loads(p.read_text(encoding="utf-8"))
        plan = B.normalise(spec, p.parent, check_files=False)
        assert plan["warnings"] == [], (p.name, plan["warnings"])
        assert "_doc" in spec, f"{p.name} documents its fields"
        seen.add(plan["style"])
    assert seen == set(STYLES)


def test_crop_rect():
    # landscape: the largest 9:16 window, centred on the focus
    assert B.crop_rect(1920, 1080, (0.3, 0.5)) == (606, 1080, 273, 0, 0.5)
    assert B.crop_rect(1920, 1080, (1.0, 1.0))[2] == 1920 - 606          # kept inside the picture
    assert B.crop_rect(1080, 1920, (0.5, 0.42)) == (1080, 1920, 0, 0, 0.42)
    w, h, x, y, fy = B.crop_rect(1080, 1920, (0.5, 0.42), zoom=1.5)        # a closer punch
    assert (w, h, x) == (720, 1280, 180) and abs(y - 166) <= 1 and fy == 0.5
    w, h, x, y, fy = B.crop_rect(1080, 1920, (0.5, 0.45), box=[0, 330, 1080, 1590])  # TV logo cut off
    assert (h, y, fy) == (1590, 330, 0.45) and w == 894 and x == 93
    assert B.crop_rect(720, 1280, (0.5, 0.42), box=[0, 0, 1080, 1560])[:4] == (720, 1280, 0, 0)  # box clamped
    assert B.crop_rect(1080, 2400, (0.5, 0.8))[3] > 0                      # tall picture: centred on the focus


def test_beat_grid_layout(tmp_path):
    spec = dict(DEMOS["beat"][0])
    plan = B.normalise(spec, tmp_path, check_files=False)
    st = [(s["st"], s["en"]) for s in plan["shots"]]
    assert st[:2] == [(0.0, 1.1), (1.1, 2.1)]                              # opens at 0, then on bt(n) = 0.1 + 0.5 n
    assert st[2] == st[3] == st[4] == (2.1, 3.6) and plan["tri"] == [{"st": 2.1, "en": 3.6, "ix": [2, 3, 4]}]
    assert st[5] == (3.6, 4.0) and plan["end"]["at"] == 3.6                # the rest shot carries the end card
    assert [(q["t"], q["s"], q["e"]) for q in plan["slams"]] == [("اسم،", 0.1, 1.1), ("الأولى", 1.2, 2.0)]
    assert any("Lalezar" in w for w in plan["warnings"])
    assert plan["beat"] == 0.5
    bpm = B.normalise({**spec, "beat": {"bpm": 120, "phase": 0.1}}, tmp_path, check_files=False)
    assert [s["en"] for s in bpm["shots"]] == [s["en"] for s in plan["shots"]]


@pytest.mark.parametrize("patch, words", [
    ({"style": "film"}, "style must be one of"),
    ({"duration": -1}, "duration"),
    ({"shots": [clip(start=2, end=1)]}, "shots[0]: end"),
    ({"shots": [clip(start=0, end=1, focus=[2, 0])]}, "shots[0].focus[0]"),
    ({"shots": [clip(start=0, end=1, box=[0, 0, 0, 10])]}, "shots[0].box"),
    ({"shots": [clip(start=1, end=2), clip(start=0, end=1)]}, "time order"),
    ({"lines": [{"text": "x", "start": 2, "end": 1}]}, "lines[0]: end"),
    ({"lines": [{"text": "x", "start": 0, "end": 1, "font": "Comic"}]}, "lines[0].font"),
    ({"song": {"path": "مصادر/غير موجود.wav"}}, "song.path not found"),
])
def test_spec_errors_name_the_field(media, patch, words):
    spec = {**DEMOS["nil"][0], **patch}
    with pytest.raises(B.SpecError, match=re.escape(words)):
        B.normalise(spec, media)


def test_style_specific_errors(media):
    medal = DEMOS["medal"][0]
    with pytest.raises(B.SpecError, match="flood"):  # flip then iris: the card never opens
        B.normalise({**medal, "shots": [clip(start=1, end=2), clip(start=2, end=3, move="flip"),
                                        clip(start=3, end=4, move="iris")]}, media)
    with pytest.raises(B.SpecError, match="last move"):
        B.normalise({**medal, "shots": [clip(start=1, end=2), clip(start=2, end=4, move="flip")]}, media)
    with pytest.raises(B.SpecError, match="move must be one of"):
        B.normalise({**medal, "shots": [clip(start=1, end=2), clip(start=2, end=4, move="spin")]}, media)
    with pytest.raises(B.SpecError, match="beat grid"):
        B.normalise({**DEMOS["beat"][0], "beat": None}, media)
    with pytest.raises(B.SpecError, match=r"heroes\[0\].tile"):
        B.normalise({**DEMOS["wall"][0], "heroes": [{"tile": 9, "start": 0, "end": 2}]}, media)
    with pytest.raises(B.SpecError, match="needs tiles"):
        B.normalise({**DEMOS["wall"][0], "tiles": []}, media)


def test_lints_and_typos(media):
    def warns(**patch):
        return " | ".join(B.normalise({**DEMOS["nil"][0], **patch}, media)["warnings"])
    assert "unknown field 'duraton'" in warns(duraton=5)
    assert "unknown shot field(s) foucs" in warns(shots=[clip(start=0, end=4, foucs=[0.5, 0.5])])
    assert "light-leak" in warns(leak=True)
    assert "no watermark or credit" in warns(watermark="")
    assert "explainer" in warns(lines=[{"text": "الفصل الأول", "start": 1, "end": 2}])
    assert "Arabic digits" in warns(lines=[{"text": "ميار · ١١ سنة", "start": 1, "end": 2}])
    assert "held" in warns(shots=[clip(start=0, end=2)])                     # last shot ends before the film
    assert warns(_note="ok", leak=False) == ""                             # '_' keys are notes
    # v10.15: numerals are off unless asked ("numbers": true, README); asking for them brings the owner's warning
    ch = B.normalise({**DEMOS["chapters"][0], "numbers": True}, media)["warnings"]
    assert any("numbered chapter" in w for w in ch)
    assert not B.normalise({**DEMOS["chapters"][0], "numbers": False}, media)["warnings"]


# ---------------------------------------------------------------- the kit itself

def test_kit_sources_keep_the_engine_lessons():
    js = {p.name: p.read_text(encoding="utf-8") for p in [KIT / "common.js", *sorted((KIT / "styles").glob("*.js"))]}
    assert set(js) == {"common.js"} | {f"{s}.js" for s in STYLES}
    for name, text in js.items():
        for banned in ("Mahmoud", "Elkosif", "ميار", "/home/", "C:\\"):  # no names or paths, not even in comments
            assert banned not in text, f"{name} contains {banned!r}"
        code = re.sub(r"(?m)^\s*//.*$|//[^'\n]*$", "", re.sub(r"/\*.*?\*/", "", text, flags=re.S))
        for banned in ("Date.now", "Math.random", ".decode("):     # deterministic frames, no decode()
            assert banned not in code, f"{name} calls {banned!r}"
        if name != "common.js":
            assert text.rstrip().endswith("boot(render);"), name
    assert "Math.min(16," in js["common.js"]          # the image cache never holds more than 16 frames
    assert "LAST.get(key)" in js["common.js"]         # last good frame when a frame fails to load
    assert "direction = 'rtl'" in js["common.js"]     # word-by-word reveals right to left
    lic = (KIT / "fonts" / "OFL.txt").read_text(encoding="utf-8")
    for fam, (fname, _) in B.FONTS.items():
        assert (KIT / "fonts" / fname).is_file(), fname
    for fam in ("Amiri", "Aref Ruqaa", "El Messiri", "Lalezar", "Tajawal"):
        assert f"===== {fam} =====" in lic
    assert lic.count("SIL OPEN FONT LICENSE Version 1.1") == 5
    readme = (KIT / "README.md").read_text(encoding="utf-8")
    for s in STYLES:
        assert f"### `{s}`" in readme


def test_cli_list_check_and_errors(media, tmp_path):
    def cli(*args):
        return subprocess.run([sys.executable, str(KIT / "build_style.py"), *map(str, args)], capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=60)
    r = cli("--list")
    assert r.returncode == 0 and all(re.search(rf"^{s}\s", r.stdout, re.M) for s in STYLES)
    r = cli(KIT / "examples" / "medal.json", "--check", "--allow-missing")   # an example is a template (v1.3 flag)
    assert r.returncode == 0 and "OK medal spec: 6 shots" in r.stdout and "MISSING" in r.stdout
    bad = write_spec(media, "bad", {**DEMOS["nil"][0], "shots": [clip(start=3, end=1)]})
    r = cli(bad, "--out", tmp_path / "x")
    assert r.returncode == 2 and "SPEC ERROR shots[0]: end" in r.stderr
    r = cli(write_spec(media, "nostill", DEMOS["nil"][0]), "--out", tmp_path / "y", "--stills", "9")
    assert r.returncode == 2 and "outside the film" in r.stderr
    shutil.rmtree(tmp_path / "y", ignore_errors=True)
