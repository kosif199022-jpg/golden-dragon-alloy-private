"""Add v2.8 regression cases to understand_tests.json / route_tests.json (only cases the staging rd.py already passes;
prints the ones it fails so they are judged by hand, never written)."""
import importlib.util, json, os, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
os.environ["RED_DRAGON_HOME"] = tempfile.mkdtemp(prefix="rd-at-")
spec = importlib.util.spec_from_file_location("rda", HERE.parent.parent / "scripts" / "rd.py")
rd = importlib.util.module_from_spec(spec); sys.argv = [sys.argv[0]]; spec.loader.exec_module(rd)
WRITE = "--write" in sys.argv[1:] or os.environ.get("RD_WRITE") == "1"

U = {
    "[فريق الوكلاء: 500 وكيل]\nاعمل مونتاج فيديو للخطبة": "اعمل مونتاج فيديو للخطبة",
    "[مجلد الشغل: C:\\Users\\cinde\\OneDrive\\Desktop\\خطابة 2]\nحلل الملف ده وقولي بيعمل ايه": "حلل الملف ده وقولي بيعمل ايه",
    "[عقل التنين الأحمر: الطريق المقترح: montage [خطوة 1] · ثقة عالية]\nصمم لوجو للقناة": "صمم لوجو للقناة",
    "استخدم كل المهارات المتثبتة (120 مهارة) مع بعض: الطلب: صمم لوجو للقناة": "صمم لوجو للقناة",
    "استخدم مهارة «paint-studio»: ارسم بورتريه زيتي": "ارسم بورتريه زيتي",
    "اعمل ريلز من الفيديو [ملف مرفق: C:\\in\\a.mp4] استخدم المسار ده في الأدوات (مش محتاج ترفعه).": "اعمل ريلز من الفيديو [ملف مرفق: C:\\in\\a.mp4]",
    "نزل الفيديو ده ✕ خطأ: الاتصال اتقطع\nنسخ": "نزل الفيديو ده",
    "[عقل التنين الأحمر: الطلب كان طويل واتقص": "",
    "[ERROR] الفيديو مش بيشتغل": "[ERROR] الفيديو مش بيشتغل",
    "[hl] ;fdv": "جامد كبير",
}
R = {
    "[فريق الوكلاء: 500 وكيل]\nطور عقل التنين الأحمر بمهارة فائقة القدرات": "self-improve",
    "هل خلصت ولا لسه": "status",
    "فين مكان الملف اللي عملته": "status",
    "التطبيق مش شغال بعد التحديث": "app-dev",
    "اضف امكانية تحميل الفيديوهات في التطبيق": "app-dev",
    "حلل مستودع جيت هب ده وضيفه كمهاره": "re-repo",
}

uf = rd.MIND / "understand_tests.json"
rf = rd.MIND / "route_tests.json"
ut = json.loads(uf.read_text(encoding="utf-8"))
rt = json.loads(rf.read_text(encoding="utf-8"))
addu = addr = 0
for raw, want in U.items():
    got = rd.understand(raw)["text"]
    flag = "ok" if got == want else "FAIL"
    print(f"U {flag}: «{raw[:50]!s}» → «{got}»")
    if got == want and raw not in ut:
        ut[raw] = want
        addu += 1
for q, want in R.items():
    pb, _ = rd.route(rd.understand(q)["text"])
    got = pb[0][1]["id"] if pb and pb[0][0] >= 2 else None
    flag = "ok" if got == want else "FAIL"
    print(f"R {flag}: «{q[:50]}» → {got} (want {want}) conf={rd.confidence(pb)}")
    if got == want and q not in rt:
        rt[q] = want
        addr += 1
if WRITE:
    uf.write_text(json.dumps(ut, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    rf.write_text(json.dumps(rt, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(f"{'written' if WRITE else 'dry run'}: understand +{addu} → {len(ut)} · route +{addr} → {len(rt)}")
