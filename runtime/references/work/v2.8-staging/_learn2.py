import subprocess, sys
from pathlib import Path
RD = Path.home() / ".claude" / "skills" / "red-dragon" / "scripts" / "rd.py"
t = ("فحص الأسرار وقف الشحن على أمثلة (قاعدة YARA بتكشف المفاتيح الخاصة، ومفتاح AWS التوضيحي الرسمي في مرجع) ← قايمة سماح بالظبط للمثال ده"
     " مش تعطيل الفحص، واستبعاد ملفات البصمات من جذر المهارة بس")
r = subprocess.run([sys.executable, "-I", "-X", "utf8", str(RD), "learn", t, "--domain", "shipping"], capture_output=True, text=True, encoding="utf-8", errors="replace")
print(r.returncode, (r.stdout + r.stderr).strip()[:200])
