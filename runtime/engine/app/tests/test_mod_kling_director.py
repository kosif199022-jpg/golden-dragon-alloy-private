"""Parity: engines.kling_director against the original kosif-kling-director/scripts/kling_director.py and the
living-site tools/kling_lint.py gate it loads. Blocks, prompt text, storyboards, plan.json, lint results, CLI output
and exit codes must be identical. Text only: nothing here calls Kling or spends credits."""
import importlib.util, json, os, re, subprocess, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
SKILLS = Path(r"C:\Users\cinde\kosif-tool\.claude\skills")
OLD_PY = SKILLS / "kosif-kling-director" / "scripts" / "kling_director.py"
OLD_LINT = SKILLS / "living-site" / "tools" / "kling_lint.py"
pytestmark = pytest.mark.skipif(not (OLD_PY.is_file() and OLD_LINT.is_file()), reason="original scripts not on this machine")

import engines.kling_director as new  # noqa: E402
from engines.kling_director import lint as new_lint  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def old():
    return _load("old_kling_director", OLD_PY)


@pytest.fixture(scope="module")
def old_lint():
    return _load("old_kling_lint", OLD_LINT)


TASKS = ["A courier races the rain to deliver one last letter.", "ساعي بريد يسابق المطر",
         "Perfect 8K hero shot on an ARRI camera.", "flawless 8K shot on a Zeiss lens",
         "  a quiet   duel\n at dawn  ", "dynamic cinematic camera follows a dancer {with braces}"]


def test_plan_parity(old, old_lint):
    for s in range(3, 241):
        assert old.plan(s) == new.plan(s) == old_lint.plan(s)
        assert old.plan(s, True) == new.plan(s, True)
    for d in (3, 7.5, 10, 13, 20, 23, 30):
        for parts in (1, 2, 5, 9):
            assert old.cuts(d, parts) == new.cuts(d, parts)


def test_prompt_text_parity(old):
    for task in TASKS:
        for dur in (3, 5, 6, 7, 10, 12, 15, 20, 22, 23, 29, 30):
            for ratio in new.RATIOS:
                assert old.master_prompt(task, 2, 3, dur, ratio) == new.master_prompt(task, 2, 3, dur, ratio)
                assert old.storyboard_prompt(task, 2, dur, ratio) == new.storyboard_prompt(task, 2, dur, ratio)


def _prompts(old):
    base = old.master_prompt(TASKS[0], 1, 1, 30, "21:9")
    short = "\n".join(["SCENE CONTEXT", "8 s.", "ACTIVE REFERENCES", "@Image1 — CHARACTER — X: not inherited.",
                       "@Video1 — no role here", "@Element2 — LOCATION — Y", "@Image3 — STORYBOARD: follow it.",
                       "ACTION TIMING", "0-4s close-up, 24 mm, dolly push-in pan tilt", "4-8s wide",
                       "ACTING TASK", "x", "AUDIO", "يا صاحبي", "STYLE", "never use avoid", "POSITIVE CONSTRAINTS",
                       "Keyframes mode", "Exactly two people."])
    many = base + "\n" + " ".join(f"@Image{i}" for i in range(1, 13)) + " " + " ".join(f"@Video{i}" for i in range(1, 7))
    return [base, old.plant(base), short, many, "", "random text 12 s", base.replace("6.0-12.0s", "7.0-12.0s"),
            base.replace("OPTICS", "CAMERA", 1), old.master_prompt(TASKS[2], 1, 1, 10, "9:16"),
            base.replace("Exactly 1 person", "one person"), base.replace("CAMERA\n", "CAMERA\nNo cuts. Do not shake. ")]


def test_lint_parity(old, old_lint):
    for text in _prompts(old):
        for duration, flash in ((None, False), (30, False), (10, False), (25, True), (2, False), (30.0, True)):
            assert old_lint.lint(text, duration, flash) == new_lint.lint(text, duration, flash)
        assert old_lint.sections(text) == new_lint.sections(text)
        assert old.summarize(old_lint.lint(text)) == new.summarize(new_lint.lint(text))
        assert old.plant(text) == new.plant(text)


def _tree(d):
    return {p.relative_to(d).as_posix(): p.read_bytes() for p in sorted(Path(d).rglob("*")) if p.is_file()}


def test_build_parity(old, tmp_path):
    for k, (task, secs, ratio, flash) in enumerate([(TASKS[0], 60, "21:9", False), (TASKS[1], 45, "9:16", False),
                                                    (TASKS[3], 10, "1:1", False), (TASKS[4], 45, "16:9", True),
                                                    (TASKS[5], 97, "21:9", False)]):
        a, b = tmp_path / f"old{k}", tmp_path / f"new{k}"
        assert old.build(task, secs, a, ratio, flash) == new.build(task, secs, b, ratio, flash)
        assert _tree(a) == _tree(b)


ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}


def run_old(*args):
    r = subprocess.run([sys.executable, str(OLD_PY), *args], capture_output=True, text=True, encoding="utf-8", env=ENV, timeout=60)
    return r.returncode, r.stdout


def run_new(*args):
    r = subprocess.run([sys.executable, "-m", "engines.kling_director", *args], capture_output=True, text=True,
                       encoding="utf-8", env=ENV, cwd=ROOT, timeout=60)
    return r.returncode, r.stdout


def test_cli_parity(tmp_path):
    for args in (["plan", "90"], ["plan", "45", "--flash", "--json"], ["plan", "2"], ["plan", "200", "--json"]):
        assert run_old(*args) == run_new(*args), args
    for k, (task, secs, extra) in enumerate([("ساعي بريد يسابق المطر", "45", []), ("flawless 8K shot on a Zeiss lens", "10", []),
                                             ("a quiet duel at dawn", "30", ["--ratio", "9:16", "--flash"])]):
        for fmt in ([], ["--json"]):
            a, b = tmp_path / f"o{k}{len(fmt)}", tmp_path / f"n{k}{len(fmt)}"
            ro = run_old("build", "--task", task, "--seconds", secs, "--out", str(a), *extra, *fmt)
            rn = run_new("build", "--task", task, "--seconds", secs, "--out", str(b), *extra, *fmt)
            assert ro[0] == rn[0] and ro[1].replace(str(a), "OUT") == rn[1].replace(str(b), "OUT")
            assert _tree(a) == _tree(b)
    p = tmp_path / "o00" / "block_01.txt"
    gap = tmp_path / "gap.txt"
    gap.write_text(p.read_text(encoding="utf-8").replace("0.0-5.8s", "0.0-5.0s"), encoding="utf-8")
    for f in (p, gap):
        for extra in ([], ["--json"], ["--duration", "23", "--flash"]):
            assert run_old("check", str(f), *extra) == run_new("check", str(f), *extra)
    assert run_old("check", str(tmp_path / "missing.txt"))[0] == run_new("check", str(tmp_path / "missing.txt"))[0] == 2


def test_new_self_test_passes():
    r = subprocess.run([sys.executable, "-m", "engines.kling_director", "--self-test"], capture_output=True, text=True,
                       encoding="utf-8", cwd=ROOT, timeout=60)
    assert r.returncode == 0 and "SELF-TEST PASS" in r.stdout
    assert re.search(r"all 4 planted flaws caught", r.stdout)
