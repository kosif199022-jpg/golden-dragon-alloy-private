"""Apply agent 2's trigger / phrase proposals (dev evidence only) to mind/playbooks.json.

  python -I -X utf8 apply_triggers.py [--risky]      default leaves out the generic words that collide; --risky adds them too
  python -I -X utf8 apply_triggers.py --restore      put back mind/route_eval/_playbooks_v27.json
"""
import json, shutil, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PB = HERE.parent / "playbooks.json"
BK = HERE / "_playbooks_v27.json"
if not BK.exists():
    shutil.copy2(PB, BK)
if "--restore" in sys.argv:
    shutil.copy2(BK, PB)
    raise SystemExit("restored")
RISKY = set("حوله روابط ترسم ارفع ارفعه المجانيه مجانيه الكاميرا البرنامج المحاكي".split())
MINE = {  # read off the dev misses, kept to words that name the job
    "pc-task": ("powershell ffmpeg بامر cmd terminal تيرمنال", []),
    "reconcile": ("كشوفات مستفيد المستفيد حوالات تحويلات المبلغ", ["حوالات رجعت", "بنفس المبلغ"]),
    "toon": ("ديزني disney pixar", ["ديزني استايل"]),
    "self-improve": ("قدراتك امكانياتك", ["ملف التعليمات", "ملف تعليمات", "كل قدراتك", "سوبر باور"]),
    "app-dev": ("", ["حدث التطبيق", "اضف امكانيه", "مشكله التحديث", "عدل التطبيق"]),
    "status": ("", ["ولا لسه", "باقي لك", "هل صنعت", "هل خلصت"]),
}
props = json.loads((HERE / "proposals_triggers.json").read_text(encoding="utf-8"))
d = json.loads(BK.read_text(encoding="utf-8"))
risky = "--risky" in sys.argv
n_w = n_p = 0
for p in d["playbooks"]:
    pr = props.get(p["id"], {})
    words = [w for w in (pr.get("add", "") + " " + MINE.get(p["id"], ("", []))[0]).split() if w and (risky or w not in RISKY)]
    have = set(p.get("triggers", "").split())
    new = [w for w in dict.fromkeys(words) if w not in have]
    if new:
        p["triggers"] = p.get("triggers", "") + " " + " ".join(new)
        n_w += len(new)
    phr = list(dict.fromkeys(pr.get("phrases", []) + MINE.get(p["id"], ("", []))[1]))
    if not risky:
        phr = [x for x in phr if x not in ("مش شغال",)]          # every app says that: leave it to the intent rule
    if phr:
        p["phrases"] = phr
        n_p += len(phr)
PB.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"playbooks.json: +{n_w} trigger words, {n_p} phrases ({'with' if risky else 'without'} the risky generic words)")
