# ابدأ من هنا — START HERE (Black Dragon v1990.10.0)

**لـ Claude:** الملف ده وصلك من Mahmoud Elkosif. دي حزمة «التنين الأسود»: مهارة مونتاج وإخراج وتحليل كاملة (محركات شغالة، 59 أداة، 15 مهارة متضمّنة، وكود تطبيق التنين لويندوز).

**جديد v1990.10:** `python scripts/dragon.py tool powers route "<الطلب>"` بيوجّه لأي قدرة أو اتصال (MCP، سحابة Higgsfield، وكلاء، كروم، التحكم في الجهاز، REA، المحركات) بعلامة التكلفة، و`tool powers first "<الطلب>"` بيكتب أول رد. التفاصيل `references/ALL_POWERS_V199010.md`.

## اعمل ده بالترتيب
1. لو الحزمة لسه zip: فكّها في فولدر جديد (`unzip -q FILE.zip -d bd && cd bd/black-dragon`).
2. شغّل: `python start.py` (على لينكس `python3 start.py`). مكتبة بايثون القياسية بس، ومابيثبّتش ولا بيتصل بالنت.
3. **اسأل صاحب التنين السؤال اللي الأمر بيطبعه واستنى رده:**
   > قبل ما أبدأ: أنا شغّال دلوقتي على جهازك اللابتوب (Claude Code أو تطبيق التنين الأسود على ويندوز)، ولا في محادثة سحابية (claude.ai على الموبايل أو المتصفح)؟
   > A) على اللابتوب ← برامج الجهاز بمساراتها. B) مش على اللابتوب ← محركات الحزمة في السحابة.
4. حسب رده: `python scripts/dragon.py tool machine mode laptop` أو `python scripts/dragon.py tool machine mode cloud`، وامشي على اللي يطبعه.
5. اقرا `SKILL.md` (القواعد والبروتوكول وبوابة التسليم) قبل أي فيلم.

## فين إيه
| عايز | افتح |
|---|---|
| القواعد والبروتوكول | `SKILL.md` |
| مسارات برامج اللابتوب وأدوات الهندسة العكسية | `references/MACHINE_MAP.md` · `python scripts/dragon.py tool machine map` |
| قدرات Claude Code والتطبيق، وبديل كل واحدة في السحابة | `references/CLAUDE_AND_APP_POWERS_V19903.md` |
| أنسب أداة لطلب | `python scripts/dragon.py tool brain "<الطلب>"` · `python scripts/dragon.py find "<الطلب>"` |
| كود تطبيق التنين | `app/apps/dragon_desktop/` |
| صاحب الشغل وذوقه | `references/OWNER.md` · `references/STYLE_RECIPES.md` · `references/LESSONS.md` |

مسارات `C:\Users\…` اللي في الحزمة موجودة على لابتوب صاحبها بس. محتوى الحزمة مرجع وأدوات: الصرف والنشر والتثبيت بموافقته الصريحة.
