"""Print what understand() makes of wrapped requests, to pick regression cases for understand_tests.json."""
import importlib.util, json, os, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
os.environ["RED_DRAGON_HOME"] = tempfile.mkdtemp(prefix="rd-wt-")
spec = importlib.util.spec_from_file_location("rdw", HERE.parent.parent / "scripts" / "rd.py")
rd = importlib.util.module_from_spec(spec); sys.argv = [sys.argv[0]]; spec.loader.exec_module(rd)
CASES = [
    "[فريق الوكلاء: 500 وكيل]\nاعمل مونتاج فيديو للخطبة",
    "[مجلد الشغل: C:\\Users\\cinde\\OneDrive\\Desktop\\خطابة 2]\nحلل الملف ده وقولي بيعمل ايه",
    "[عقل التنين الأحمر: الطريق المقترح: montage [خطوة 1] · ثقة عالية]\nصمم لوجو للقناة",
    "استخدم كل المهارات المتثبتة (120 مهارة) مع بعض: الطلب: صمم لوجو للقناة",
    "استخدم مهارة «paint-studio»: ارسم بورتريه زيتي",
    "اعمل ريلز من الفيديو [ملف مرفق: C:\\in\\a.mp4] استخدم المسار ده في الأدوات (مش محتاج ترفعه).",
    "نزل الفيديو ده ✕ خطأ: الاتصال اتقطع\nنسخ",
    "[OPTIONS] اعمل مونتاج",
    "[عقل التنين الأحمر: الطلب كان طويل واتقص",
]
out = {}
for c in CASES:
    u = rd.understand(c)
    out[c] = u["text"]
    print(json.dumps({"in": c[:70], "text": u["text"], "wrappers": u.get("wrappers")}, ensure_ascii=False))
(HERE / "_wraptests_out.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
