# تثبيت السبيكة مكان التنين الذهبي (مااتنفذش: محتاج «ثبّت» صريحة)

> **الهدف:** السبيكة تبقى المهارة الوحيدة المسجّلة. وفي نفس الوقت كل حاجة بتنادي المسارات القديمة تفضل شغالة من غير ما تتعدّل، زي الـ hook اللي بيشغّل `golden-dragon\scripts\rd.py brief` قبل كل رسالة، و`GOLDEN.md`، و`/golden`، والتطبيق.

## اتقاس قبل الخطة (2026-11-19، قراية بس)
`runtime/tools/dragon-maint/diff_tree.py` بين المتثبت (`~/.claude/skills/golden-dragon`، v3.2.1) وغرفة الماكينات (main v3.5.4):
- **136 ملف على اللابتوب بس:**
  - **14 اتصهروا خلاص في السبيكة:** `claude-app` (7)، وpresets الموشن (6)، و`gd_custom_api.py` (1).
  - **122 = مشروعات فيديو بتاعة صاحب الشغل:** موجودة في `engine/skills/library/motion-reel/videos/`، ولازم ترجع مكانها (الخطوة 3).
- **388 ملف جديد في main** مش على اللابتوب، و**115 ملف مختلف**: كلهم أحدث في main (v3.5.4 مقابل v3.2.1).
- **ذاكرة التعلّم:** `~/.red-dragon` برّه المهارتين ومشتركة، فمش محتاجة نقل. اتأكد بـ `runtime/tools/dragon-maint/lessons_diff.py`.

## الخطوات (PowerShell)
```powershell
$S   = "$env:USERPROFILE\.claude\skills"
$NEW = "$S\golden-dragon-alloy"
$ts  = Get-Date -Format yyyyMMdd-HHmm
$BAK = "$env:USERPROFILE\.claude\skills_backup\$ts-golden-dragon-v3.2.1"

# 0) مفيش جلسة تانية بتكتب فيها: python -X utf8 "$S\golden-dragon\scripts\rd.py" guard "$S\golden-dragon"
# 1) نسخة احتياطية = نقل (سريع وبيرجع زي ما كان)
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\skills_backup" | Out-Null
Move-Item "$S\golden-dragon" $BAK

# 2) السبيكة: فك golden-dragon-alloy.skill (zip) جوه $S، فيطلع $NEW\SKILL.md
Expand-Archive "<مسار golden-dragon-alloy.skill>" -DestinationPath $S

# 3) رجّع مشروعات الفيديو بتاعة صاحب الشغل لمكانها
robocopy "$BAK\engine\skills\library\motion-reel\videos" "$NEW\runtime\engine\skills\library\motion-reel\videos" /E   # exit 1 = اتنسخ = نجاح

# 4) وصلات المسارات القديمة: مجلد golden-dragon من غير SKILL.md، وجواه وصلة لكل مجلد في runtime
New-Item -ItemType Directory "$S\golden-dragon" | Out-Null
Get-ChildItem "$NEW\runtime" -Directory | ForEach-Object { cmd /c mklink /J "$S\golden-dragon\$($_.Name)" "$($_.FullName)" | Out-Null }

# 5) الفحص
python -X utf8 "$NEW\alloy.py" selftest
python -X utf8 "$S\golden-dragon\scripts\rd.py" brief "اختبار بعد التثبيت"      # مسار الـ hook القديم
```
- **ليه مفيش `SKILL.md` في مجلد `golden-dragon`:** علشان Claude Code مايسجّلش المهارة مرتين. نفس الطريقة اللي اتعملت لـ `red-dragon` و`black-dragon` في v3.0.0.
- **الوصلات القديمة:** `red-dragon` و`black-dragon` و`kosif-black-dragon-ultra` و`black-dragon-cinema` بيشاوروا على `golden-dragon\…`، والمسار ده هيرجع موجود بالوصلات الجديدة.
- **`golden-dragon-fusion` المتثبتة (بتاعة Codex):** وصفها عام، وممكن تتنافس على نفس الطلبات. هتفضل زي ما هي، والقرار لصاحب الشغل.

## الرجوع (لو أي فحص فشل)
```powershell
# ⚠ في PowerShell 5.1 ماتستعملش Remove-Item -Recurse على مجلد فيه وصلات: ممكن يمشي جوه الوصلة ويمسح الأصل.
Get-ChildItem "$S\golden-dragon" | ForEach-Object { cmd /c rmdir "$($_.FullName)" }   # بيشيل الوصلة بس
cmd /c rmdir "$S\golden-dragon"
Move-Item $NEW "$env:USERPROFILE\.claude\skills_backup\$ts-alloy-removed"
Move-Item $BAK "$S\golden-dragon"
```
