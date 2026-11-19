"""Parity: engines.reel_hooks against the original kosif-reel-hooks/scripts/reel_tools.py on the same inputs.
Scores, checks, flags, beat sheets, humanizer results, rendered text and exit codes must be identical."""
import importlib.util, json, os, subprocess, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OLD_DIR = Path(r"C:\Users\cinde\kosif-tool\.claude\skills\kosif-reel-hooks")
OLD_PY = OLD_DIR / "scripts" / "reel_tools.py"
pytestmark = pytest.mark.skipif(not OLD_PY.is_file(), reason="original reel_tools.py not on this machine")

from engines import reel_hooks as new  # noqa: E402


@pytest.fixture(scope="module")
def old():
    spec = importlib.util.spec_from_file_location("old_reel_tools", OLD_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def same(a, b):  # exact, including int vs float (they print differently in --json)
    assert json.dumps(a, ensure_ascii=False, sort_keys=False) == json.dumps(b, ensure_ascii=False, sort_keys=False)


HOOKS = [
    "خسرت ٤٠٠٠ جنيه في عقد ناقصه سطر واحد.",
    "أهلاً بيكم يا جماعة، النهارده هنتكلم عن العقود.",
    "في الفيديو ده هوريكم إزاي تكتب كابشن.",
    "استنى متقلبش! 🔥 #ريلز",
    "Hey guys, in this video I'll show you how.",
    "متبعتش عرض سعر لعميل قبل ما تعمل الحاجة دي.",
    "اشتريت الكتاب من المكتبة",
    "my client Canva paid twice",
    "Something broke at Canva",
    "so I lost $400",
    "محدش بيقولك إن أول ١٠٠ متابع أصعب من أول ١٠ آلاف.",
    "المونتاج كان بياخد مني ٦ ساعات. دلوقتي ساعة.",
    "بطّلت أكتب كابشن من الصفر وبقيت أستخدم قالب واحد.",
    "حياتك هتتغير لما تفهم الحتة دي من غير ما تدفع ولا جنيه.",
    "I wasted 3 years and $20k building the wrong product for nobody",
    "خَسِرْتُ الشغل",
    "الكل بيعمل كده",
    "اسرق القالب ده",
    "We doubled revenue in 30 days without ads, here is the exact playbook we used every single week",
    "",
    "!!!",
    "Ana 3amalt 50% profit fi shahr",
]
SCRIPTS = [
    "خسرت ٤٠٠٠ جنيه في عقد ناقصه سطر واحد. السبب كان بند الدفع. محدش قرأه. ولا أنا. "
    "النهارده بقرا كل سطر. الأربعة آلاف جنيه علموني.",
    "أهلاً بيكم يا جماعة النهارده عايز أكلمكم عن حاجة مهمة جدًا في حياتنا كلنا وهي الوقت والإنتاجية والتركيز.\n"
    "الموضوع ده مهم. لازم نفكر فيه. وناخد بالنا. وخلاص كده.",
    "I lost $400 on one contract. The clause was missing. Nobody read it. Now I read every line. "
    "That $400 taught me more than any course.",
    "",
    "سطر واحد بس؟",
    "Stop scrolling. This is important. Really important. Very important. Okay bye.",
]
CLEAN = [
    "في عالم اليوم، لا شك أن الذكاء الاصطناعي — رحلة رائعة.\u200b علاوة على ذلك دعونا نبدأ.",
    "Let's dive in. In today's world we delve into the tapestry — it's not just a game-changer.",
    "جملة قصيرة هنا. جملة قصيرة هناك. جملة قصيرة كمان. جملة قصيرة تاني. جملة قصيرة أخيرة.",
    "كلام عادي من واحد بيتكلم. مفيش فيه حاجة غريبة خالص، وده المطلوب في الآخر.",
    "\ufeffنص\u200d فيه\u00ad حروف مخفية – وشرطة",
    "",
]


@pytest.mark.parametrize("hook", HOOKS)
def test_score_hook_parity(old, hook):
    same(old.score_hook(hook), new.score_hook(hook))
    same(old.score_hook(hook, "٤٠٠٠ جنيه ضاعوا"), new.score_hook(hook, "٤٠٠٠ جنيه ضاعوا"))
    same(old.score_hook(hook, "استنى قبل ما تبعت العرض ده للعميل"), new.score_hook(hook, "استنى قبل ما تبعت العرض ده للعميل"))


def test_helpers_parity(old):
    for text in HOOKS + SCRIPTS + CLEAN:
        assert old.tokens(text) == new.tokens(text)
        assert old.is_arabic(text) == new.is_arabic(text)
        assert old.concrete_markers(text) == new.concrete_markers(text)
        assert old.content_words(text) == new.content_words(text)
        for t in old.tokens(text):
            assert old.norm(t) == new.norm(t) and old.variants(t) == new.variants(t)
        for name in ("check_length", "check_specificity", "check_stakes", "check_frontload", "check_address"):
            same(getattr(old, name)(text), getattr(new, name)(text))


def test_library_hooks_score_the_same(old):
    lib = new.library()
    assert lib == json.loads((OLD_DIR / "data" / "hooks_ar.json").read_text(encoding="utf-8"))
    assert len(lib["hooks"]) == 16
    for h in lib["hooks"]:
        same(old.score_hook(h["example"], h["on_screen"]), new.score_hook(h["example"], h["on_screen"]))
    rows_old = sorted((old.score_hook(h["example"]) for h in lib["hooks"]), key=lambda r: -r["score"])
    same(rows_old, new.rank_hooks([h["example"] for h in lib["hooks"]]))


@pytest.mark.parametrize("i", range(len(SCRIPTS)))
def test_beat_sheet_parity(old, i):
    for wpm, target in ((None, None), (None, 30), (None, 5), (120.0, 60), (180.0, 10.0)):
        same(old.beat_sheet(SCRIPTS[i], wpm, target), new.beat_sheet(SCRIPTS[i], wpm, target))


@pytest.mark.parametrize("i", range(len(CLEAN)))
def test_clean_parity(old, i):
    for fix in (False, True):
        same(old.clean_text(CLEAN[i], fix), new.clean_text(CLEAN[i], fix))


# ---------------------------------------------------------------- CLI: same stdout, files and exit codes
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}


def run_old(*args, stdin=None):
    r = subprocess.run([sys.executable, str(OLD_PY), *args], capture_output=True, text=True, encoding="utf-8",
                       input=stdin, env=ENV, timeout=60)
    return r.returncode, r.stdout


def run_new(*args, stdin=None):
    r = subprocess.run([sys.executable, "-m", "engines.reel_hooks", *args], capture_output=True, text=True,
                       encoding="utf-8", input=stdin, env=ENV, cwd=ROOT, timeout=60)
    return r.returncode, r.stdout


def test_cli_parity(tmp_path):
    hooks = tmp_path / "هوكات.txt"
    hooks.write_text("\n".join(HOOKS[:12]) + "\n", encoding="utf-8")
    one = tmp_path / "one.txt"
    one.write_text(HOOKS[0] + "\n", encoding="utf-8")
    script = tmp_path / "سكريبت.txt"
    script.write_text(SCRIPTS[0], encoding="utf-8")
    draft = tmp_path / "draft.txt"
    draft.write_text(CLEAN[0], encoding="utf-8")
    cases = [["hook", "--hook", HOOKS[0]], ["hook", "--hook", HOOKS[1], "--screen", "كارت"],
             ["hook", "--hook", HOOKS[5], "--json"], ["hook", str(hooks)], ["hook", str(hooks), "--json"],
             ["hook", str(one)], ["beats", str(script), "--target", "30"], ["beats", str(script), "--json", "--wpm", "150"],
             ["clean", str(draft)], ["clean", str(draft), "--json"]]
    for args in cases:
        assert run_old(*args) == run_new(*args), args
    assert run_old("beats", stdin=SCRIPTS[2]) == run_new("beats", stdin=SCRIPTS[2])
    o, n = tmp_path / "o.txt", tmp_path / "n.txt"
    assert run_old("clean", str(draft), "--fix", "--out", str(o)) == run_new("clean", str(draft), "--fix", "--out", str(n))
    assert o.read_bytes() == n.read_bytes()
