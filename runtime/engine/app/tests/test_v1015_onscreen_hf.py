"""v10.15: the owner's v10.12.1 rules are executable (no on-screen description; no Higgsfield credit without a yes)."""
import importlib.util
import json
import os
import pathlib
import subprocess
import sys

SKILL = pathlib.Path(__file__).resolve().parents[2]


def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, SKILL / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


OS = load("tools/onscreen/onscreen.py", "bd_onscreen_test")
HF = load("tools/hf_sandbox/hf.py", "bd_hf_test")


def cli(rel, *args):
    return subprocess.run([sys.executable, str(SKILL / rel), *args], capture_output=True, text=True, encoding="utf-8",
                          env=dict(os.environ, PYTHONIOENCODING="utf-8"), timeout=60)


ASS = """[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:03.00,Title,,0,0,0,,{\\fad(200,200)}شتا الرياض\\Nيا حبيبي
Dialogue: 0,0:00:03.00,0:00:05.00,Title,,0,0,0,,وقهوتها الدافية
Dialogue: 0,0:00:05.00,0:00:07.00,Credit,,0,0,0,,© إخراج محمود الكوسيف
Dialogue: 0,0:00:07.00,0:00:09.00,Title,,0,0,0,,وَشِتَا الرِّيَاض يَا حَبِيبِي
"""


def test_readers_all_formats(tmp_path):
    (tmp_path / "a.ass").write_text(ASS, encoding="utf-8")
    assert OS.read_onscreen(tmp_path / "a.ass")[0] == "شتا الرياض يا حبيبي"
    (tmp_path / "a.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\n<i>سطر</i> أول\n\n2\n00:00:02,000 --> 00:00:03,000\nتاني\n",
                                    encoding="utf-8")
    assert OS.read_onscreen(tmp_path / "a.srt") == ["سطر أول", "تاني"]
    (tmp_path / "s.json").write_text(json.dumps({"lines": [{"text": "واحد"}, {"text": " "}, {"text": "اتنين"}]}), encoding="utf-8")
    assert OS.read_onscreen(tmp_path / "s.json") == ["واحد", "اتنين"]


def test_whisper_formats():
    assert OS.words_json([{"word": "يا"}, {"text": "حبيبي"}]) == ["يا", "حبيبي"]
    assert OS.words_json({"segments": [{"words": [{"word": "شتا"}]}, {"text": "الرياض"}]}) == ["شتا", "الرياض"]
    assert OS.words_json({"text": "كله"}) == ["كله"]


def test_check_flags_description_passes_lyrics_with_tashkeel_and_prefix(tmp_path):
    (tmp_path / "a.ass").write_text(ASS, encoding="utf-8")
    vocab = OS.words("شتا الرياض يا حبيبي")
    rows = OS.check(OS.read_onscreen(tmp_path / "a.ass"), vocab)
    assert [r["verdict"] for r in rows] == ["PASS", "DESCRIPTION", "CREDIT", "PASS"]


def test_reordered_words_are_not_verbatim():
    seq = OS.words("شتا الرياض يا حبيبي والليل طويل")
    rows = OS.check(["يا حبيبي شتا الرياض", "الليل طويل يا حبيبي", "يا حبيبي والليل طويل"], set(seq), seq=seq)
    assert [r["verdict"] for r in rows] == ["ORDER", "ORDER", "PASS"]
    assert OS.order_ratio(OS.words("شتا الرياض"), seq) == 1.0


def test_cli_exit_codes(tmp_path):
    (tmp_path / "a.ass").write_text(ASS, encoding="utf-8")
    (tmp_path / "l.txt").write_text("شتا الرياض يا حبيبي\nوقهوتها الدافية", encoding="utf-8")
    (tmp_path / "bad.txt").write_text("شتا الرياض يا حبيبي", encoding="utf-8")
    assert cli("tools/onscreen/onscreen.py", "check", str(tmp_path / "a.ass"), "--lyrics", str(tmp_path / "l.txt")).returncode == 0
    r = cli("tools/onscreen/onscreen.py", "check", str(tmp_path / "a.ass"), "--lyrics", str(tmp_path / "bad.txt"), "--json")
    assert r.returncode == 1 and json.loads(r.stdout)["verdict"] == "FAIL"
    r = cli("tools/onscreen/onscreen.py", "check", str(tmp_path / "a.ass"))
    assert r.returncode == 3 and "أكتب كلامك" in r.stdout
    assert cli("tools/onscreen/onscreen.py", "check", str(tmp_path / "missing.ass")).returncode == 2


def test_lint_web(tmp_path):
    (tmp_path / "f.js").write_text("el.animate(k,{duration:300, fill: 'both'})\nel.animate(k,{fill:'forwards'})", encoding="utf-8")
    (tmp_path / "r.sh").write_text("ffmpeg -i a -i b -filter_complex xfade=transition=fade out.mp4", encoding="utf-8")
    (tmp_path / "ok.sh").write_text("ffmpeg -filter_complex \"tpad=stop_mode=clone:stop_duration=1,xfade\"", encoding="utf-8")
    found = OS.lint([str(tmp_path / "f.js"), str(tmp_path / "r.sh"), str(tmp_path / "ok.sh")])
    assert [(pathlib.Path(f["file"]).name, f["line"]) for f in found] == [("f.js", 1), ("r.sh", 0)]
    assert cli("tools/onscreen/onscreen.py", "lint-web", str(tmp_path / "ok.sh")).returncode == 0


def test_hf_free_paid_unknown():
    assert HF.classify("sandbox_exec")[1] == "free"
    assert HF.classify("mcp__claude_ai_Higgsfield__media_upload")[1] == "free"
    assert HF.classify("generate_video")[1] == "paid" and HF.classify("upscale_image")[1] == "paid"
    assert HF.classify("brand_new_tool")[1] == "unknown"
    assert cli("tools/hf_sandbox/hf.py", "check", "generate_image").returncode == 3
    assert cli("tools/hf_sandbox/hf.py", "check", "balance").returncode == 0
    r = cli("tools/hf_sandbox/hf.py", "ask", "generate_video", "--price", "40", "--balance", "350.63")
    assert r.returncode == 0 and "40" in r.stdout and "350.63" in r.stdout and "موافق" in r.stdout


def test_rules_and_lessons_from_v10121_present():
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "مفيش وصف على الشاشة" in skill and "مفيش أي أداة Higgsfield بتخصم رصيد" in skill
    lessons = (SKILL / "references" / "LESSONS.md").read_text(encoding="utf-8")
    for s in ("ممنوع كتابة وصف", "tpad=stop_mode=clone", "fill:'forwards'", "fxtwitter"):
        assert s in lessons, s


def test_opencv_model_path_is_ascii_even_from_an_arabic_folder(tmp_path):
    """v10.15: YuNet silently failed when the skill lived under «خطابة 2» / «التنين الأسود» (OpenCV + non-ASCII path)."""
    sys.path.insert(0, str(SKILL / "app"))
    try:
        from engines.dragon_montage.analyze import cv_safe_path
    finally:
        sys.path.pop(0)
    model = tmp_path / "التنين الأسود" / "face_detection_yunet_2023mar.onnx"
    model.parent.mkdir()
    model.write_bytes(b"onnx-bytes")
    out = cv_safe_path(model)
    assert out.isascii() and pathlib.Path(out).read_bytes() == b"onnx-bytes"
    assert cv_safe_path(pathlib.Path(out)) == out          # an ASCII path is used as is


def test_brain_requires_onscreen_for_video():
    brain = load("tools/brain/brain.py", "bd_brain_v1015")
    b = brain.brief("ريل على أغنية بكلمات على الشاشة", use_live=False)
    assert any("onscreen check" in a for a in b["acceptance"])
    assert b["gates"][0].startswith("أي أداة Higgsfield")
