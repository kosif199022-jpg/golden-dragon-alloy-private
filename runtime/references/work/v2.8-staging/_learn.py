import subprocess, sys
from pathlib import Path
RD = Path.home() / ".claude" / "skills" / "red-dragon" / "scripts" / "rd.py"
L = [
    ("routing", "عقل التنين وجّه «طوّر ذكاء التنين» لـ paid-gen ← كلمات ذكاء/عقل/التنين مع طوّر = self-improve، واتضافت لاختبارات route_tests"),
    ("routing", "تحية مع كلام ونس («ازيك يا تنين عامل ايه») بعد سؤال حالة كانت بتروح status ← الدردشة greet/none، وstatus/none ماتتورّثش في موضوع المحادثة (NO_CARRY)"),
    ("agents", "بلوك 500 وكيل على شغل في ملف واحد (rd.py) ← 4 وكلاء بس بمحاور مستقلة (صوت وحروف، كلمات، أغلفة، مقيّم تاني) والدمج عند وكيل واحد"),
    ("tools", "كود بايثون أو عربي جوه أمر PowerShell بيبوّظ التنصيص ← اكتب سكربت .py وشغّله بـ python -I -X utf8"),
    ("security", "rg مش على PATH وأداة البحث بتطبع السطر كله بما فيه السر ← عدّ الأسرار بسكربت بيطبع المسار وأول 7 حروف بس"),
    ("security", "فحص الأسرار مسك مفتاح API وباسورد جوه بيانات تقييم متاخدة من محادثات (fresh_cc.json) ← افحص وخبّي أي بيانات من محادثات قبل ما تدخل المهارة أو تتشحن"),
    ("shipping", "باتش مبني على نسخة أقدم (2.7.1 فوق 2.7.0) فيه rd.py كامل ← ماتفكّوش فوق نسخة أحدث، ادمج سطوره بس في rd.py الجديد"),
    ("shipping", "فحص الأسرار وقف الشحن على أمثلة (قاعدة YARA بتكشف المفاتيح، ومفتاح AWS التوضيحي AKIAIOSFODNN7EXAMPLE) ← قايمة سماح بالظبط للمثال ده مش تعطيل الفحص، واستبعاد ملفات البصمات من الجذر بس"),
]
for dom, text in L:
    r = subprocess.run([sys.executable, "-I", "-X", "utf8", str(RD), "learn", text, "--domain", dom], capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(dom, r.returncode, (r.stdout + r.stderr).strip()[:160])
r = subprocess.run([sys.executable, "-I", "-X", "utf8", str(RD), "outcome", "self-improve", "ok"], capture_output=True, text=True, encoding="utf-8", errors="replace")
print("outcome", r.returncode, (r.stdout + r.stderr).strip()[:300])
r = subprocess.run([sys.executable, "-I", "-X", "utf8", str(RD), "outcome", "ship", "ok"], capture_output=True, text=True, encoding="utf-8", errors="replace")
print("outcome ship", r.returncode, (r.stdout + r.stderr).strip()[:300])
