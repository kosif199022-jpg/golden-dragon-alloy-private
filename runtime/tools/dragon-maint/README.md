# أدوات صيانة التنين (dragon-maint)

السكربتات اللي اتعمل بيها إصدار v3.4.0 (نقل المميزات اللي كانت على اللابتوب بس للمستودع)، متجمعة هنا عشان أي تحديث جاي يستخدمها بدل ما يكتبها من الأول. كلها بتقرا بس، إلا لو قلت `--apply` أو `--json` أو `--write` أو شغّلت `manifests.py` من غير `--check`.

شغّلهم دايمًا كده: `python -I -X utf8 tools/dragon-maint/<السكربت> …`

| السكربت | بيعمل إيه | الاستخدام |
|---|---|---|
| `inventory.py` | المهارات المتثبتة على الجهاز: ناقصة من المستودع ولا موجودة ولا مختلفة؟ | `inventory.py REPO ~/.claude/skills OUT.json` |
| `skilldiff.py` | للمهارات المختلفة: أنهي ناحية أحدث (اللابتوب ولا آخر commit) وأنهي ملفات | `skilldiff.py REPO SKILLS_DIR OUT.json` |
| `diff_tree.py` | يقارن فولدرين بالـ hash بعد توحيد نهايات السطور | `diff_tree.py A B [--limit N] [--skip a,b]` |
| `lessons_diff.py` | الدروس اللي اتعلمها التنين على الجهاز (`~/.red-dragon/lessons.jsonl`) ومش في `mind/lessons_seed.jsonl`، وبيعلّم اللي شكله فيه سر | `lessons_diff.py REPO [--write OUT.jsonl]` |
| `install_plan.py` | خطة تحديث المهارة المتثبتة من غير ما تمسح تعديلات محلية (same/update/add/foreign/keep) | `install_plan.py REPO INSTALLED_DIR OLD_COMMIT NEW_COMMIT [--json OUT]` |
| `manifests.py` | يبني `MANIFEST_SHA256.json` و`SHA256SUMS.txt` (engine الأول وبعدين الجذر) بنفس شكل الملفات، أو يفحصهم | `manifests.py REPO VERSION DATE [--check]` |
| `overlay_eval.py` | يتأكد إن `mind/fusion_overlay.json` ماسرقش أمثلة الوصفات الأصلية (لازم الرقمين زي بعض) | `overlay_eval.py REPO` |
| `sanitize_paths.py` | يبدّل `C:\Users\<اسم>` بـ `%USERPROFILE%` في الملفات الجديدة أو المتغيرة بس (`REPOS_*.md` و`library/**/SOURCE.json`) | `sanitize_paths.py REPO [--apply] [--user NAME]` |

## ترتيب الشغل المعتاد في نقل حاجة من اللابتوب
1. `inventory.py` ثم `skilldiff.py`: إيه الناقص وإيه المختلف وأنهي أحدث. وقت الـ commit مش دليل إن النسخة أقدم (درس s61): اقرا الفرق.
2. `lessons_diff.py --write` وراجع الدروس قبل ما تضيفها.
3. بعد النقل: `sanitize_paths.py --apply`، وبعدين `manifests.py REPO <VERSION> <DATE>`، وفي الآخر `manifests.py … --check`.
4. لو لمست الوصفات: `overlay_eval.py`.
5. قبل ما تبدّل المهارة المتثبتة: `install_plan.py`، وأي ملف `foreign` ماينكتبش فوقه من غير ما تبص عليه.
