import importlib.util
import pathlib

P = pathlib.Path(__file__).resolve().parents[2] / "tools" / "caption" / "tags.py"
spec = importlib.util.spec_from_file_location("tags", P)
tags = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tags)

REF = ("دعاء يوم الثلاثاء 🤲 10.11.2026 #دعاء_يوم_الثلاثاء #ادعية_يومية #دعاء_الصباح "
       "#صباحكم_معطر_بذكر_الله #alihadkc2ok #ادعية_يومية")


def test_extract_dedup_order():
    assert tags.extract(REF) == ["دعاء_يوم_الثلاثاء", "ادعية_يومية", "دعاء_الصباح",
                                 "صباحكم_معطر_بذكر_الله", "alihadkc2ok"]


def test_handle_dropped_and_reach_last():
    out = tags.build(REF, topic="دعاء يوم الثلاثاء", n=9)
    assert "#alihadkc2ok" not in out
    assert out[0] == "#دعاء_يوم_الثلاثاء"
    assert out[-2:] == ["#fyp", "#foryou"]
    assert len(out) == len({t.lower() for t in out})


def test_limit_and_no_reach():
    out = tags.build(REF, extra="#a #b #c #d #e #f #g", n=5, reach=False)
    assert len(out) == 5 and "#fyp" not in out


def test_block_is_copyable_code():
    md = tags.block("كابشن", ["#x", "#y"], "@me")
    assert md.startswith("```\n") and md.endswith("\n```")
    assert "الصوت: @me" in md


def test_hf_tool_prints_pasteable_scripts():
    import subprocess, sys
    root = pathlib.Path(__file__).resolve().parents[2]
    out = subprocess.run([sys.executable, str(root / "scripts" / "dragon.py"), "tool", "hf", "paste", "demo"],
                         capture_output=True, text=True).stdout
    assert "cat > bootstrap.sh <<'XEOF'" in out and "cat > qc.sh <<'XEOF'" in out and out.rstrip().endswith("bash bootstrap.sh demo")
    assert "HIGGSFIELD_FREE" in (root / "SKILL.md").read_text(encoding="utf-8")
