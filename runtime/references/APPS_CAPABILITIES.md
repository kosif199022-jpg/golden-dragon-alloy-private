# قدرات تطبيقات التنين كلها في مكان واحد

الملف ده لأي Claude بيستلم لينك المستودع: إيه التطبيقات، وكل واحد بيعمل إيه، ومكان كوده هنا، وإزاي توصل لنفس القدرة من غير التطبيق. اتعمل 2026-11-16 من مقارنة نسخ الجهاز بالمستودع.

## الشجرة: كل تطبيق مبني على اللي قبله

```
التنين الأسود (engine/app)          محركات المونتاج + تطبيق ويندوز (dragon_desktop)
  └─ الطائر الأبيض (apps/white-bird)   نفس التطبيق + تصميم Apple + Ctrl+K + إضافة كروم v1.4
      └─ الطائر الذهبي (apps/golden-bird)  + استوديو البرامج + مكتبة الموشن + speech_sync + «⚡ قاطعه»
          └─ التنين الذهبي (apps/golden-dragon)  + عقل الانصهار (fusion) + discover + مراجع التفكير + MarkItDown
التنين الأحمر = المهارة نفسها (SKILL.md + scripts/rd.py): العقل والذاكرة والخطط، وبتشتغل في أي شات Claude من غير تطبيق
```

كل تطبيق بيتولّد من اللي تحته بسكربت `forge` (التعديلات بعدد مرات مضبوط، فلو الأصل اتغيّر السكربت بيقف). يعني تصليح في الطائر الأبيض بيوصل للذهبي وللتنين الذهبي مع التوليد الجاي.

## 1) التنين الأسود: المحركات وتطبيق الويندوز
- **الكود:** `engine/app` (CLI: `python -m dragon find | engines | run | film | verify`)، والتطبيق `engine/app/apps/dragon_desktop`.
- **المحركات (18):** blender، cards، chrome، cinema، cloud_browser، dragon_montage، editorial، image_studio، kling_director، kosif، matrices، reel_hooks، render، shadow_theatre، talking_head، toon، voice_studio، web_film.
  - dragon_montage: مونتاج كامل (تحليل، خطة، مونتاج، مراجعة). talking_head: ريل من حد بيتكلم. cinema: أفلام تكريم 9:16 بأغنية. web_film: أفلام موشن كصفحات ويب. editorial: لوك أرشيفي. shadow_theatre: مسرح الظل. voice_studio: صوت بتوقيت الكلمات وتفريغ SRT/VTT. reel_hooks: تقييم أول جملة وتوزيع السكريبت. toon: كرتون وأنمي لصور وفيديو بموديلات مفتوحة على المعالج (`python -m engines.toon setup | styles | image | video`). kosif: مدير تحميل مسرّع.
- **أدوات التطبيق (20):** dragon_find، dragon_show، list_engines، superpowers_find، run_engine، run_command، verify_media، list_dir، read_text_file، view_image، write_file، edit_file، search_files، find_files، rea، retool، omni، skill، rebuild_app، deployment_status.
- **الأمان:** `auto_approve` افتراضيًا مقفول، وأي أداة عليها `approval=True` (run_engine، run_command، rea، retool، rebuild_app، deployment_status) بتسأل دايمًا حتى في الوضع التلقائي (`engine/app/tests/test_v199031_safety.py`).
- **فيه كمان:** 60 أداة في `engine/tools` (superpowers، media_hunter، github_atlas، rea_ultra، visual_forge، toon…)، و47 مهارة في `engine/skills`، و589 مهارة ومرجع في `library`.

## 2) الطائر الأبيض
- **الكود:** `apps/white-bird` (`forge/make_white_bird.py` بيولّد `app/` من كود التنين الأسود).
- **زيادة على التنين:** تصميم Apple فاتح وغامق، خطوط Noto Sans Arabic وInter جوه التطبيق (الملفات `.woff2` مش في المستودع: سياسة الخطوط)، بحث سريع **Ctrl+K**، بروتوكول تفكير (شكل التسليم الأول، تشريح قبل الفشل، ناقد داخلي)، جسر كروم 47831 بإضافة لوحده **v1.4.0** (مراقب، حد وقت لكل أمر، صفحة offscreen بتخلّيها صاحية، جروب تابات).
- **الأمان:** `enforce_approval_gate` في الـ forge بيقفل `auto_approve` افتراضيًا وبيخلّي الموافقة إجبارية.

## 3) الطائر الذهبي
- **الكود:** `apps/golden-bird` (`forge/make_golden_bird.py` بيحمّل forge الطائر الأبيض ويطبّق تعديلاته كلها وبعدين الطبقة الذهبية، والتعديلات اللي بتغيّر كود التطبيق في `forge/patches/`).
- **أدوات زيادة:** `studio` و`studio_run` (10 برامج سطر أوامر مفتوحة المصدر: Rhubarb، Tahoma2D، HandBrakeCLI، Synfig، melt، whisper-cli، oiiotool، Gaffer، Pencil2D، بفحص بصمة الأرشيف قبل الفك)، و`motion_lib` (154 مكتبة موشن: GSAP، anime.js، three.js، lottie-web، manim، hyperframes… و`kit` بيحطها في `vendor` للرندر أوفلاين)، و`speech_sync` (علامات على الكلمات ← ثواني وفريمات و`captions.srt`).
- **تغيير المسار وهو شغال (golden_steer):** الرسالة بتتقري عند الخطوة الجاية، وزرار «⚡ قاطعه دلوقتي»، وكلمات زي «وقف/غلط/استنى» بتقاطعه لوحدها.
- **من غير التطبيق:** `python -X utf8 apps/golden-bird/app/golden_tools.py studio … | lib … | sync …` أو `python -X utf8 scripts/rd.py gold …`.

## 4) التنين الذهبي
- **الكود:** `apps/golden-dragon` (`forge/make_golden_dragon.py` بيحمّل forge الطائر الذهبي ويحط طبقة التنين). ملفات التحليل اللي الـ forge بيقراها في `apps/golden-dragon/analysis/`، والتقرير في `تقرير-التحليل.md`.
- **أداة `fusion`:** فهرس واحد فيه ~1100 قدرة (مهارات، playbooks وأوامر التنين الأحمر، أدوات سوبر باور، محركات، برامج استوديو، مكتبات، برامج، أدوات تحليل، خوادم MCP) و42 وصفة. الأوامر: `brief` (قبل الشغل)، `route`، `check` (قبل الرد)، `find`، `show`، `recipes`، `doctor`، `lessons`، و**`discover` و`local`** (v3.5.0: كل اللي على الجهاز دلوقتي كأنواع `pc-*`).
- **زيادة:** 🧐 مراجع تفكير مستقل وهو شغال، 🔎 بحث في المحادثات، 📌 تثبيت محادثات، ✅ فحص الملفات بعد كل رد، 📄 أي PDF أو Word أو Excel بيتحوّل Markdown الأول (MarkItDown)، جسر كروم 47851.
- **من غير التطبيق:** `python -X utf8 apps/golden-dragon/app/dragon_fusion.py brief "…" | route "…" | find "…" | discover`.
- ⚠ **مفتوح لقرار صاحب الشغل:** التطبيق المتولّد هنا لسه `auto_approve` افتراضيًا شغال (اتولّد من forge الجهاز اللي مافيهوش تصليح الأمان). تصليح الأمان موجود في `apps/white-bird/forge`، وأول توليد من المستودع هيطبّقه.

## التحكم في التنين الذهبي اللي على الجهاز (gd-remote)
- **`tools/gd-remote/connect.py --apply`:** بيسجّل خادم MCP اسمه `golden-dragon` في Claude Code وClaude Desktop على الجهاز، فأي جلسة Claude هناك تاخد أداة `blackdragon_app` (status، chats، read، send، ask، reply، stop) على محادثات التنين الذهبي.
- **`tools/gd-remote/gd_remote.py`:** نفس الحاجة من الترمنال (`ping`، `status`، `ask "…"`، `reply --sid`، `stop --sid`).
- الباب على `127.0.0.1:47851` وبكود ربط بيتقري من إعدادات التطبيق وقت التشغيل بس. صلاحيات التطبيق وبوابة الموافقة هي اللي بتحكم، والماوس والكيبورد مش متاحين من برّه. Claude في المتصفح أو السحابة مايقدرش يوصل له: لازم Claude يكون شغّال على الجهاز نفسه.

## 5) التنين الأحمر (المهارة نفسها)
- **الكود:** `SKILL.md` و`BOOT.md` و`scripts/rd.py` و`mind/` و`references/`.
- **أوامر `rd.py`:** start، selftest، think (خطة على الديسك)، check، fuse، route/map/show، teach وlearn وlessons وoutcome (يتعلم من التصحيح)، memory وmind (ذاكرة)، character (ذاكرة الشخصيات)، math، re/repo/repos (هندسة عكسية ومستودعات)، skills، insta/ig، agents، hypit، krita، sync، md، arena، consent (بوابة الموافقة)، gold (أدوات الطائر الذهبي)، desktop، ref، dcm، x.
- **في أي شات Claude:** اقرا `BOOT.md` وبعدين `SKILL.md`، وشغّل `python -X utf8 scripts/rd.py start`.

## اللي اتضاف من الجهاز للمستودع في التحديث ده
| من الجهاز | لفين | ليه |
|---|---|---|
| مصنع الطائر الذهبي وتطبيقه واختباراته | `apps/golden-bird` | نسخة الجهاز أحدث: golden_steer و`forge/patches`، وإضافة كروم v1.4، و76 اختبار بدل 43 |
| مصنع الطائر الأبيض وإضافة كروم v1.4 | `apps/white-bird` | ميزات الإضافة كانت على الجهاز بس، و**تصليح الأمان بتاع المستودع اتحفظ** |
| تطبيق التنين الأسود 2026.11.13-1737 (app.py، brain.py، control.py، mcp_dragon.py، الواجهة والأيقونة) | `engine/app/apps/dragon_desktop` | نسخة الجهاز أحدث من 2026.11.12-0814، و**بوابة الموافقة بتاعة المستودع اتحطت عليها** |
| محرك toon | `engine/app/engines/toon` | كان على الجهاز بس |
| مهارة camera-director | `engine/skills/camera-director` | مهارة صاحب الشغل كانت متثبتة ومش في المستودع |
| سكربتات hf_bootstrap/finish/render | `engine/skills/hf-blender-render/tools` | كانت على الجهاز بس |
| ملفات تحليل التنين الذهبي (صندوق أدوات التفكير، الدروس، قياسات التوجيه، المسارات المنقولة) والتقرير | `apps/golden-dragon/analysis`، `apps/golden-dragon/تقرير-التحليل.md` | الـ forge مكانش يقدر يتولّد من المستودع من غيرها |

**ماتنقلش عن قصد:** ملفات الخطوط (`.woff2` و`.ttf`، سياسة الخطوط)، والـ logs، و`.ruff_cache`، ونسخ `.bak`، وملفات تحليل فيها تاريخ شخصي (`experience.md`، `archives_privacy.md`، `env_vars_set.tsv`)، والبرامج المضغوطة في «مهارات\برامج» (بتتسجّل في الجهاز بـ `fusion discover`). وكل مسار فيه اسم المستخدم اتبدّل بـ `%USERPROFILE%`.
