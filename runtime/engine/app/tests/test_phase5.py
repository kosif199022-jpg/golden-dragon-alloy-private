"""Phase 5: the old generated card programs (8 MB runners + 3.6 MB power programs) became data/cards/*.json plus ONE
interpreter (engines/cards). Parity: the OLD card and the NEW data card give the same verdict, the same pass/fail per
check and the same measured values. The old code runs in a subprocess (-B, temp cwd and work folder) so nothing is
ever written inside the original repo."""
import json, math, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OLD = Path(r"C:\Users\cinde\kosif-tool\.claude\skills")
RUNNERS = OLD / "kosif-dragon-mind" / "runners"
SCRIPTS = OLD / "kosif-superpowers" / "scripts"
HAVE_OLD = RUNNERS.is_dir() and (SCRIPTS / "power_programs").is_dir()
HAVE_FF = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None

# fast cards from 12 families (audio mastering, ducking, retiming, colour, glow, footage, formats, voice, prompts ...)
PARITY = ["BEAT-01", "BEAT-13", "BEAT-100", "BEAT-173",             # music-beat-sound: loudnorm/ebur128, ducking, beat audio
          "BEAT-181", "BEAT-292",                                       # custom template (_grid_card): cut plan on a click track
          "COLOR-40", "COLOR-48", "GLOW-32", "GLOW-60", "TEX-21",       # colour grading, glow, texture (frame math + ffmpeg)
          "FOOT-12", "FOOT-16", "FMT-12", "FMT-54",                     # photo-video-footage, formats-platforms
          "VOICE-36", "SYNC-20", "EASE-07", "ARAB-75",                  # voice-tts, captions, easing, Arabic typography
          "PROMPT-13", "AGENT-35", "MODEL-01", "PLAN-11", "STORY-71",   # text/logic power programs
          "GEN-88", "BRAND-32"]

_OLD_DRIVER = r'''
import sys, json, importlib, importlib.util
from pathlib import Path
sys.dont_write_bytecode = True
corpus, module, cid, wd, runners, scripts = sys.argv[1:7]
wd = Path(wd)
def plain(v):
    if v is None or isinstance(v, (bool, int, str)): return v
    if isinstance(v, float): return round(v, 6)
    if isinstance(v, (list, tuple)): return [plain(x) for x in v]
    if isinstance(v, dict): return {str(k): plain(x) for k, x in v.items()}
    try: return round(float(v), 6)
    except (TypeError, ValueError): return str(v)
out = {}
try:
    if corpus == "runner":
        sys.path.insert(0, runners)
        import _harness as H
        spec = importlib.util.spec_from_file_location(module[:-3], str(Path(runners) / module))
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        checks, outs = H.REGISTRY[cid]("اعمل فيديو موشن عربي قصير", wd)
        outs = [Path(o) for o in outs or []]
    else:
        sys.path.insert(0, scripts)
        mod = importlib.import_module("power_programs." + module[:-3])
        rows = list(mod.PROGRAMS[cid](wd))
        checks = [{"check": str(n), "passed": bool(ok), "measured": str(obs)[:400]} for n, ok, obs in rows]
        outs = [p for p in sorted(wd.rglob("*")) if p.is_file()]
    ok = bool(checks) and all(c["passed"] for c in checks) and any(o.is_file() and o.stat().st_size for o in outs)
    out = {"verdict": "executed" if ok else "failed", "checks": [{k: plain(c.get(k)) for k in ("check", "passed", "measured")} for c in checks]}
except Exception as e:
    out = {"verdict": "error", "reason": "%s: %s" % (type(e).__name__, str(e)[:300])}
sys.stdout.reconfigure(encoding="utf-8")
print("@@" + json.dumps(out, ensure_ascii=False))
'''


def run_old(rec, wd):
    wd = Path(wd); wd.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "-B", "-c", _OLD_DRIVER, rec["source"]["corpus"], rec["source"]["module"], rec["id"],
                        str(wd), str(RUNNERS), str(SCRIPTS)], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=str(wd), env=env, timeout=240)
    line = next((l for l in r.stdout.splitlines() if l.startswith("@@")), None)
    return json.loads(line[2:]) if line else {"verdict": "error", "reason": (r.stderr or "")[-300:]}


def run_new(cid, wd):
    import engines.cards as C
    return C.run(cid, Path(wd))


NUM = re.compile(r"-?\d+(?:\.\d+)?(?:e-?\d+)?")


def same(a, b, wa="", wb=""):
    """Measured values agree: numbers within 1e-3 (abs) or 1e-3 (rel), work-folder paths normalised."""
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return (math.isnan(a) and math.isnan(b)) or abs(a - b) <= max(1e-3, 1e-3 * max(abs(a), abs(b)))
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(same(x, y, wa, wb) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k], wa, wb) for k in a)
    if isinstance(a, str) and isinstance(b, str):
        for w, tag in ((wa, "<WD>"), (wb, "<WD>")):
            if w:
                for form in (w, w.replace("\\", "/"), w.replace("\\", "\\\\"), repr(w)[1:-1]):
                    a, b = a.replace(form, tag), b.replace(form, tag)
        if NUM.sub("#", a) != NUM.sub("#", b):
            return False
        return same([float(x) for x in NUM.findall(a)], [float(x) for x in NUM.findall(b)])
    return a == b


def parity(cid, tmp):
    import engines.cards as C
    rec = C.cards()[cid]
    wa, wb = Path(tmp) / "old", Path(tmp) / "new"
    old, new = run_old(rec, wa), run_new(cid, wb)
    problems = []
    if old["verdict"] != new["verdict"]:
        problems.append("verdict old=%s new=%s (%s | %s)" % (old["verdict"], new["verdict"], old.get("reason"), new.get("reason")))
    oc, nc = old.get("checks", []), new.get("checks", [])
    if len(oc) != len(nc):
        problems.append("check count %d vs %d" % (len(oc), len(nc)))
    for o, n in zip(oc, nc):
        if o["check"] != n["check"] or o["passed"] != n["passed"]:
            problems.append("check %r: old %s new %s" % (o["check"], o["passed"], n["passed"]))
        elif not same(o.get("measured"), n.get("measured"), str(wa), str(wb)):
            problems.append("measured %r: old %r new %r" % (o["check"], o.get("measured"), n.get("measured")))
    return old, new, problems


@pytest.mark.skipif(not (HAVE_OLD and HAVE_FF), reason="old corpus or ffmpeg missing")
@pytest.mark.parametrize("cid", PARITY)
def test_parity_old_vs_new(cid, tmp_path):
    import engines.cards as C
    rec = C.cards().get(cid)
    assert rec is not None and rec["status"] in ("data", "custom"), (cid, rec and rec.get("reason"))
    old, new, problems = parity(cid, tmp_path)
    assert not problems, problems
    assert new["verdict"] == "executed"


def test_parity_sample_spans_families():
    import engines.cards as C
    fams = {C.cards()[c]["family"] for c in PARITY if c in C.cards()}
    assert len(PARITY) >= 20 and len(fams) >= 8, fams


def test_data_covers_every_card_and_is_honest():
    import engines.cards as C
    idx = json.loads((ROOT / "data" / "cards" / "_index.json").read_text(encoding="utf-8"))
    st = C.stats()
    assert st["cards"] == idx["cards"] >= 5000          # every old card has a record (data, custom, not_ported or gap)
    assert set(st["status"]) <= {"data", "custom", "not_ported", "gap"}
    assert st["status"]["data"] >= 2500
    for r in C.cards().values():                          # a card is either runnable here or says why not
        assert ("program" in r) == (r["status"] == "data")
        assert r["status"] in ("data", "custom") or r.get("reason"), r["id"]


def test_formula_whitelist_refuses_code():
    from engines.cards import formula
    for bad in ("import os", "x = ().__class__", "x = __import__('os')", "eval('1')", "open('x')", "class A: pass",
                "global g", "x = getattr(1, 'real')", "x = type(1)", "x = (1).__class__"):
        with pytest.raises((formula.FormulaError, SyntaxError)):
            formula.run([bad], "0", {})
    assert formula.run(["a = [i * i for i in range(4)]", "b = sum(a) if a else 0"], "(a, b)", {}) == ([0, 1, 4, 9], 14)
    src = """def card(n):
    t = 0
    for i in range(n):
        if i % 2:
            t += i
    f = lambda v: v * 2
    try:
        1 / 0
    except ZeroDivisionError:
        t += 1
    return f(t)"""
    assert formula.run_card(src, [5], {}) == 10            # loops, if, lambda, try/except are allowed
    with pytest.raises(PermissionError):
        formula.resolve_import("subprocess").run(["cmd", "/c", "echo", "x"])   # shim: ffmpeg/ffprobe/node only
    with pytest.raises(formula.FormulaError):
        formula.resolve_import("os")
    old = formula.MAX_ITER
    formula.MAX_ITER = 1000
    try:
        with pytest.raises(formula.FormulaError):
            formula.run_card("def card():\n    while True:\n        pass", [], {})   # iteration cap
    finally:
        formula.MAX_ITER = old


def test_cli_list_and_stats():
    r = subprocess.run([sys.executable, "-B", "-m", "engines.cards", "stats"], cwd=str(ROOT), capture_output=True,
                       text=True, encoding="utf-8")
    assert r.returncode == 0 and json.loads(r.stdout)["status"]["data"] >= 2500
    r = subprocess.run([sys.executable, "-B", "-m", "engines.cards", "list", "--status", "data"], cwd=str(ROOT),
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0 and len(r.stdout.splitlines()) >= 2500


def test_code_is_far_smaller_than_the_old_programs():
    old = sum(p.stat().st_size for d in (RUNNERS, SCRIPTS / "power_programs") for p in d.glob("*.py")) if HAVE_OLD else 11_600_000
    cards = ROOT / "engines" / "cards"
    lib = sum(p.stat().st_size for p in (cards / "lib").glob("*.py"))
    core = sum(p.stat().st_size for p in cards.glob("*.py")) + (ROOT / "tools" / "extract_cards.py").stat().st_size
    assert old > 11_000_000
    assert core < 120_000                       # the hand-written interpreter + extractor
    assert (core + lib) * 5 < old, (core, lib, old)   # with the verbatim helper packs, still far below the old programs
