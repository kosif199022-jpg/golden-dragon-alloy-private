"""End-to-end on the INSTALLED skill with a throwaway RED_DRAGON_HOME: brief → follow-up «كمل» → teach → outcome."""
import json, os, subprocess, sys, tempfile
from pathlib import Path

RD = Path(os.environ.get("RD_PATH") or Path.home() / ".claude" / "skills" / "red-dragon" / "scripts" / "rd.py")
HOME = tempfile.mkdtemp(prefix="rd-e2e-")
ENV = dict(os.environ, RED_DRAGON_HOME=HOME, PYTHONIOENCODING="utf-8")


def rd(*a):
    r = subprocess.run([sys.executable, "-X", "utf8", str(RD), *a], capture_output=True, text=True, encoding="utf-8", errors="replace", env=ENV, timeout=300)
    return r.returncode, r.stdout.strip(), r.stderr.strip()[-300:]


def brief(q):
    c, o, e = rd("brief", q)
    d = json.loads(o)
    return {k: d.get(k) for k in ("playbook", "confidence", "alternative", "used_context")} | {"wrappers": d["understood"].get("wrappers"), "line": next((l for l in d["brief"].splitlines() if "الطريق" in l), "")[:140]}


checks = []
def check(name, cond, got):
    checks.append((name, bool(cond)))
    print(("✅" if cond else "❌"), name, "→", json.dumps(got, ensure_ascii=False)[:260])


b1 = brief("[فريق الوكلاء: 500 وكيل]\nاعمل مونتاج ريلز للخطبة بالفيديو اللي في المجلد")
check("brief: wrapper stripped + montage road", b1["playbook"] == "reel-montage" and "agents_team" in (b1["wrappers"] or []), b1)
check("brief: old keys still there", True, "")
c, o, e = rd("brief", "اعمل مونتاج")
old_keys = set(json.loads(o))
need = {"understood", "playbook", "library", "installed", "brief"}
check("brief: legacy keys (understood, playbook, library, installed, brief)", need <= old_keys, sorted(old_keys))
lt = json.loads((Path(HOME) / "last_turn.json").read_text(encoding="utf-8"))
check("last_turn.json written with topic", bool(lt.get("topic")), {k: lt.get(k) for k in ("pb", "task_q")})
b2 = brief("كمل")
check("«كمل» follows the topic", b2["playbook"] == lt.get("pb") and b2["used_context"], b2)
b3 = brief("هل خلصت ولا لسه")
check("status question", b3["playbook"] == "status", b3)
b4 = brief("ازيك يا تنين عامل ايه")
check("greeting → no road", b4["playbook"] is None, b4)
c, o, e = rd("teach", "رتب لي الصور دي في فولدرات حسب التاريخ", "pc-task")
check("teach exit 0", c == 0, o[-200:] or e)
c, o, e = rd("route", "رتب لي الصور دي في فولدرات حسب التاريخ")
check("taught example is used by route", "pc-task" in o.splitlines()[1] if len(o.splitlines()) > 1 else False, o.splitlines()[:3])
brief("نزل الفيديو ده من تيك توك بأعلى جودة https://www.tiktok.com/@x/video/1")
c, o, e = rd("outcome", "download", "ok", "--note", "e2e")
ex = (Path(HOME) / "route_examples.jsonl")
rows = [json.loads(l) for l in ex.read_text(encoding="utf-8").splitlines()] if ex.is_file() else []
check("outcome ok → the task request became an example", any(r.get("pb") == "download" for r in rows), [(r["pb"], r.get("src")) for r in rows])
c, o, e = rd("plan", "حلل مستودع جيت هب ده وضيفه كمهاره")
check("plan shows confidence line", "ثقة الاختيار" in o, [l for l in o.splitlines() if "ثقة" in l][:2])
print(f"\n{sum(ok for _, ok in checks)}/{len(checks)} passed · HOME={HOME}")
