## Unreleased: approval-gate hotfix candidate — 2026-11-14

- In the White Bird application, risky tools always require explicit confirmation even when auto mode is set.
- White Bird source generator now repairs known unsafe approval patterns and refuses unknown upstream patterns.
- Added tests for the privilege guard and generator; this is staged in a review branch and is **not** the complete v2.15.0 distribution.
- Golden Bird sources are absent in the current GitHub tree and must be synchronized and checked separately; existing SHA manifest also needs full reconciliation before merge.
- Local tests were run on matching v2.14.0 White Bird files; a full repository selftest and Windows integration test remain pending.

# سجل تغييرات التنين الأحمر

## v3.5.8 — 2026-11-20 (اللي كان في السبيكة بس رجع لـ main)
- **🔌 API مخصص** (`apps/golden-dragon/forge/gd_patches/gd_custom_api.py`): الميزة اللي اتعملت على اللابتوب في 2026-11-19 (OpenRouter وأي موقع متوافق مع OpenAI). كانت محفوظة في السبيكة الخاصة بس (`branches/laptop-installed`).
  - اتوصّلت في `make_golden_dragon.py` قبل إضافة المعرفة، لأن إضافة المعرفة بتضيف `</style>` تاني.
  - المفتاح بيتحفظ في خزنة ويندوز (keyring)، مش في ملف.
  - `app/` مااتلمسش بالإيد (المستودع فيه حارس على كده). الميزة هتظهر مع أول `make_golden_dragon.py` على اللابتوب.
  - `tests/test_custom_api.py`: المولّد بيركّبها، والإضافة بتتركّب على التطبيق الحالي بقاعدة العدد بالظبط، والرابط بيتظبط.
- **`claude-app/golden_mcp.py`:** تصليح كان على نسخة اللابتوب بس. البرامج اللي بيشغّلها مابقتش تورث stdin بتاع Claude Code (كان `fusion doctor` بيعلّق 600 ث). ومعاه اختبار `test_tool_answers_while_stdin_stays_open`.

## v3.5.7 — 2026-11-20 (كل الفروع في main + تحديث yt-dlp بإذن بس)
- **كل الـ 27 فرع بقوا في `main`** (PR #31). التعارضات اتحلّت كده:
  - Anatomy: فضل تنفيذ `main` اللي اتدمج قبل كده.
  - fusion-share: اتاخدت نسخته الأحدث.
  - v3.5.2 القديم: اتاخد منه كود yt-dlp بس.
- **video-grabber:** تحديث yt-dlp لوحده بقى مقفول افتراضيًا (قاعدة §2: أي تثبيت محتاج «أيوه»).
  - من غير إذن: الأداة بتقول إن yt-dlp قديم أو فشل، وبتكتب الأمر `grab.py --update`، ومابتثبّتش حاجة.
  - بإذن صاحب الشغل: `--auto-update` (أو `VG_AUTOUPDATE=1`)، و`--no-auto-update` ليه الأولوية دايمًا.
  - اختبار جديد `test_default_never_installs_only_hints`.
  - (تحذير تقرير السبيكة على فرع v3.5.2 اتنفّذ.)

## v3.5.6 — 2026-11-20 (Maven Toon مدموجة بالكامل + رندر أسرع)
- **صاحب الشغل هو صاحب Maven Toon** واتفق إنها تندمج بالكامل: بقت في `engine/skills/maven-toon/` زي ما هي (v1.0، بحقوقها واسم Maven)، **من غير ملفات الخطوط** (قاعدة المستودع). `rd.py mtoon fonts` بيجيب Lalezar وPoppins ExtraBold (OFL) من google/fonts، وهي في `.gitignore` هي والكاش والموديلات.
- **`rd.py mtoon render`:** بيرندر بكل الأنوية (Maven افتراضيًا عاملين). اتقاس على مثال chai-ar (15 ث) هنا على 4 أنوية: **16 ث مقابل 22 ث**.
- `mtoon` بيدوّر على النسخة اللي جوه المستودع الأول، و`MTOON_HOME` بيختار نسخة تانية، و`MTOON_PY` بيختار البايثون. `install` بقى يقبل التحديث جوه فولدر المستودع بس.
- كارت النهاية بتاع `credit` نزل لتحت شوية عشان مايلزقش في الكابشن (اتشاف بالعين).
- **اتجرّب من الأول للآخر:** `doctor` OK ← `silent` ← `plan` (3 مشاهد، 14 حركة) ← `stills` (9) ← `render` DONE ← `join` ← `check` PASSED (1080×1920، 30 fps، 0 وشوش متقصوصة) ← `credit` ← `gate` ✓.
- لينكس: skia محتاجة `libegl1` (`apt-get install -y libegl1 libgl1`)، ومكتوبة في المهارة.

## v3.5.5 — 2026-11-20 (تطعيم Maven Toon)
- **`engine/skills/maven-toon-bridge/` (جديد) و`rd.py mtoon`:** التنين بيشغّل نسخة صاحب الشغل الخاصة من Maven Toon (Maven @maven.iqq، شورتس كرتون 2D رأسي بكابشن عربي على الكلمة) من غير ما ينسخ منها حاجة.
  - `install` بيفك الـ zip برّه المستودع (`~/dragon-tools/maven-toon`) فك آمن (يرفض `../` والوصلات والحجم الغريب) ويكتب إيصال sha256، وبيرفض أي مكان جوه المستودع.
  - `doctor` و`run` بيعدّوا الأوامر لـ `toon.py` بتاع النسخة، ومايقبلش مشروع جوه فولدر المهارة.
  - **فوق Maven:** `script-eg` فحص سكربت بالمصري (هوك ≤7 خبري، تصعيد، «تعرف ليه؟»، قفلة ≤9، الطول، ولهجة واحدة: بيمسك العراقي والفصحى)، و`credit` بيحط «© Mahmoud Elkosif» وكارت النهاية بـ libass وخط Lalezar من النسخة نفسها (الصوت بايت ببايت، نفس عدد الفريمات)، و`gate` لمعيار التصدير.
  - `references/IDEAS.md`: 9 أفكار من طريقة Maven مكتوبة بكلامنا (الإضاءة = الفصول، الكاميرا مابتقفش، الشرح جوه العالم، رندر قابل للاستكمال، نسخة كابشن بس…) تنفع مع `tools/cartoon` و`motion-cartoon` كمان.
- **الراوتر:** طريق جديد `maven-toon` بعد `toon`.
- **الحقوق:** أجزاء Maven ممنوع تتشارك غير من لينكه، والمستودع عام: مفيش ولا ملف من الـ zip اتحط هنا (ولا الخطوط).
- **اتجرّب:** install على الـ zip الحقيقي (52 ملف، v1.0)، `doctor` اشتغل وقال skia-python ناقص، `credit` على كليب 6 ث (العربي متوصّل، MD5 الصوت زي الأصل، gate ✓)، `script-eg` مسك العراقي في مثال chai-ar. **ماتجربش:** رندر Maven الكامل (محتاج pip install بموافقة).

## v3.5.4 — 2026-11-17 (صفحة التحميل ومكتبة الفيديوهات)
- **`tools/video-page/` (جديد):** `video_page.py` بيعمل صفحة تحميل لأي فيديو.
  - الفيديو بيشتغل في الصفحة.
  - زر «تحميل بأعلى جودة» بيجمّع أجزاء 14 MB ويحفظ الملف الأصلي بـ `downloads.save`، فالـ MD5 بيطلع زي الأصل، ومن غير ما يفتح رابط.
  - فيها نسخة خفيفة، وكابشن للنسخ، ورابط مباشر اختياري.
  - `hub-add` بيضيف الفيديو في مكتبة «فيديوهات الكوسف»، و`check` بيتأكد من الأجزاء.
- **قاعدة صاحب الشغل:** كل فيديو بيتسلّم على صفحة تحميل ويتضاف في المكتبة. التفاصيل في `OWNER.md` §8.1 و`RD_RULES.md` §12.
- **أول فيديو في المكتبة:** دعاء يوم الاثنين 16/11/2026.

## v3.5.3 — 2026-11-17 (Cinema-C V36 SmartMedia)
- **`tools/cinema-c/Cinema_C_V36_iPhone.sh`:** هو V35 Studio كامل، ومضاف عليه ميزة صور إنستجرام من V31 SmartMedia اللي صاحب الشغل بعتها: بوستات الصور والكاروسيل بـ gallery-dl، و`--smart` و`--gallery` و`--setup`. ولو yt-dlp قال «There is no video in this post» بيحوّل على gallery-dl لوحده. وفيه سطر gallery-dl في `--doctor`، و5 فحوص جديدة في `--self-test`.
- **`tools/cinema-c/v31_smartmedia/`:** ملفات V31 الأصلية زي ما اتبعتت (السكربت، والـ README، والاختبار).
- **الاختبارات:** `tests/harness.sh` بقى بيختبر V36: فحوص V35 كلها، وفوقهم 13 فحص بـ gallery-dl وهمي (`tests/stubbin/gallery-dl`)، وyt-dlp الوهمي بقى يرجّع «no video» للينكات `/p/PHOTO`.
- **ملحوظة من الشغل:** إنستجرام مقفول من سحابة Claude Code. اللي اشتغل هو yt-dlp على سحابة Higgsfield المجانية (`sandbox_exec`)، وبعدين نقل الملف عن طريق تخزين Higgsfield.

## v3.5.2 — 2026-11-16 (الملفات التلاتة في أول كل محادثة)
- **`CLAUDE.md` و`BOOT.md`:** «افهمه» بقى فيه `apps/golden-dragon/README.md` و`references/APPS_CAPABILITIES.md` و`apps/golden-dragon/THINKING_PATHS.md`، وقاعدة جديدة: كل طلب يعدّي على `dragon_fusion.py brief` مع `rd.py plan`، ولو طلع سبيل تفكير 🧭 تمشي على أدواته وتجاوب سؤال الناقد بتاع كل أداة بدليل.
- طلب صاحب الشغل: «اشتغل بيهم في كل اللي هطلبه».

## v3.5.1 — 2026-11-16 (كل التطبيقات في المستودع)
- **`references/APPS_CAPABILITIES.md`:** خريطة واحدة للتنين الأسود والطائر الأبيض والطائر الذهبي والتنين الذهبي والتنين الأحمر: كل واحد مبني على مين، وأدواته ومحركاته، وكوده فين، وإزاي توصل لنفس القدرة من غير التطبيق. ومربوطة من `README.md` و`SKILL.md`.
- **`tools/gd-remote/` (جديد):** `connect.py` بيوصّل Claude Code وClaude Desktop على الجهاز بالتنين الذهبي الشغّال (خادم MCP `golden-dragon`، وبيعمل نسخة احتياطية من الإعدادات الأول، ومابيلمسش أي خادم تاني)، و`gd_remote.py` بيتحكم فيه من الترمنال (status، send، ask، reply، stop). الكود بيتقري وقت التشغيل ومابيتكتبش، والماوس والكيبورد مش متاحين من برّه. 6 اختبارات على تطبيق وهمي.
- **محرك toon:** كان بيقفل الفيلم بـ `-shortest` (ممنوع من v12 لأنه بيقصّر الفيلم فريمات). بقى `-frames:v` بعدد الفريمات و`fit_audio` من `engines/deliver.py`، فالصوت بيتقص أو يتمد للطول بالظبط. اتجرّب بـ ffmpeg: 24 فريم وصوت 2.000 ث بالظبط، ومن غير صوت بيشتغل عادي.
- **من الجهاز للمستودع:** الطائر الذهبي (golden_steer و`forge/patches` وإضافة كروم v1.4 و76 اختبار)، والطائر الأبيض (إضافة كروم v1.4)، وتطبيق التنين الأسود 2026.11.13-1737 (`brain.py` والواجهة والأيقونة)، ومحرك `toon`، ومهارة `camera-director`، وسكربتات `hf-blender-render/tools`، وملفات تحليل التنين الذهبي اللي الـ forge محتاجها.
- **الأمان اتحفظ:** بوابة الموافقة (`auto_approve` مقفول افتراضيًا والموافقة إجبارية) فضلت في `apps/white-bird/forge` و`engine/app/apps/dragon_desktop/app.py` بعد ما نسخ الجهاز الأحدث نزلت فوقهم.
- **ماتنقلش:** الخطوط، والـ logs، والكاش، ونسخ `.bak`، وملفات التحليل الشخصية. كل مسار فيه اسم المستخدم بقى `%USERPROFILE%`.
- الاختبارات: الطائر الذهبي 76/76، والطائر الأبيض 79 نجحت و1 فشل قديم (الخطوط مش في المستودع)، وأمان تطبيق التنين الأسود 11/11.

## v3.5.0 — 2026-11-16 (التنين الذهبي بيشوف كل اللي على الجهاز)
- **`fusion discover` و`fusion local` (ملف جديد `apps/golden-dragon/forge/modules/gd_discover.py`):** بيلف على الفولدرات اللي صاحب الجهاز شغّال فيها (سطح المكتب وجواه، والتنزيلات، والمستندات، وقايمة ابدأ، و`~/.claude/skills` و`~/.claude/plugins`، وإعدادات MCP) ويضيف لنفس الفهرس 8 أنواع: `pc-skill` و`pc-plugin` و`pc-mcp` و`pc-app` و`pc-script` و`pc-tool` و`pc-repo` و`pc-pack`. بعدها `find` و`show` و`route` بيوصلوا لهم، و`find --kind pc` = كل اللي على الجهاز، و`doctor` بيقول عمر الكتالوج ولو قديم.
- **المسارات بتفضل على الجهاز:** الفولدرات الزيادة (`discover.json`) والنتيجة (`local_units.json`) في `%APPDATA%\GoldenDragon` بس. الكود مافيهوش اسم ولا مسار جهاز. خوادم MCP بتتسجل بالاسم ونوع الاتصال واسم البرنامج بس (من غير arguments ولا env)، وملفات زي `.env` و`credentials` و`token` مابتتفتحش.
- **قراية بس:** مابيشغّلش ولا بيمسح ولا بينقل حاجة. أي `pc-app` أو `pc-script` أو `pc-tool` تشغيله بموافقة، و`copy`/`archive` معناها مش النسخة المتثبّتة.
- اتجرّب حي على الجهاز: 599 حاجة زيادة عن الفهرس في حوالي 10 ثواني. الاختبارات: 60 نجحت و1 متخطّي (منهم 6 جداد في `tests/test_discover.py` على جهاز وهمي، وفيهم إن مفيش سر بيتسجّل).
- `.gd_generated.json` بقى بيكتب مصدر التوليد بـ `%USERPROFILE%` بدل اسم المستخدم.

## v3.4.2 — 2026-11-16 (أدوات صيانة التنين)
- **`tools/dragon-maint/`:** 8 سكربتات اتعمل بيها v3.4.0 (من `_v340_tools` اللي على اللابتوب) بقوا في المستودع عشان أي تحديث جاي يستخدمها: `inventory.py` و`skilldiff.py` و`diff_tree.py` (جرد ومقارنة اللابتوب بالمستودع)، `lessons_diff.py` (دروس الجهاز اللي مش في البذرة)، `install_plan.py` (تحديث المهارة المتثبتة من غير ما يمسح تعديل محلي)، `manifests.py` (بناء وفحص البصمتين)، `overlay_eval.py` (الوصفة الجديدة ماسرقتش أمثلة غيرها: 140/143 قبل وبعد)، `sanitize_paths.py` (اسم المستخدم بقى `--user` أو `%USERNAME%` بدل ما يكون مكتوب جوه). والشرح في `README.md` جنبهم.
- ماتنقلش: `append_lessons.py` و`port_files.py` (شغل لمرة واحدة واتعمل في v3.4.0، والدروس s61–s65 موجودة)، و`install_plan*.json` (ناتج فيه مسارات الجهاز)، و`restore_eol.py` و`time_thinking.py` (الأرشيف كان ناقص بياناتهم فطلعوا فاضيين)، و`v3.4.1-critic-fixes.patch` (فاضي في الأرشيف).
- البصمتين اتبنوا بـ `tools/dragon-maint/manifests.py` نفسه.

## v3.4.1 — 2026-11-16 (مراجع التفكير في التطبيق)
- **🧐 مراجع التفكير ماكانش بيشوف الطلب:** التطبيق بيلزق قبل كلام صاحب الشغل بلوكات «[…]» (التحكم في الجهاز، فهرس 547 مهارة، الأدوات، الفريق، المجلد: ~80 ألف حرف)، والمراجع كان بياخد أول 3000 حرف = بلوك التحكم في الجهاز بس. فالمراجعة كانت من غير الطلب، وفلتر الأمان عند الموديل كان بيوقّفها («safeguards flagged this message»). دلوقتي بياخد رسالة صاحب الشغل زي ما كتبها (`last_sent`)، ولو مش موجودة ياخد اللي بعد آخر بلوك.
- **لو فلتر الأمان وقّف مراجعة عادية بالغلط:** بيسأل موديل تاني مرة واحدة (Sonnet ↔ Opus)، ولو الاتنين وقّفوها بيظهر «المراجع اتخطّى المراجعة دي» بدل خطأ أحمر.
- التعديل في `apps/golden-dragon/forge/gd_patches/gd_reviewer.py` ونفس النص في `app/app.py` (والبصمة في `.gd_generated.json`)، فاختبار «اتولّد من الـ forge ومتلمسش بإيدك» عدّى.
- اختبار `test_golden_modules_are_the_golden_bird_ones_renamed` كان بيفشل في أي نسخة من المستودع لأنه بيدوّر على forge الطائر الذهبي اللي على اللابتوب بس؛ بقى يتخطّى لو مش موجود (على اللابتوب بيشتغل زي ما هو). اختبارات التطبيق: 53 نجح، 1 اتخطّى.

## v3.4.0 — 2026-11-16 (عقل الانصهار جوه المهارة + سلّم التفكير + كل المميزات اللي كانت على الجهاز بس)
- **عقل الانصهار في المهارة نفسها:** `scripts/rd_fusion.py` بيحمّل `apps/golden-dragon/app/dragon_fusion.py` جوه نفس العملية وبيدّيله قراية التنين الأحمر (understand + route) مباشرة. قبل كده كان بيشتغل من التطبيق بس، وبيدوّر على `rd.py` في `~/.claude/skills/golden-dragon` وبيشغّل `python` بالاسم، فعلى claude.ai أو لينكس كان بيرجع للكلمات لوحده من غير ما يقول. الأوامر: `rd.py fuse brief|route|tools|protocol|find|show|recipes|lessons|doctor|stats|selftest` و`rd.py check --request … --draft …`.
- **`plan` فيه قسم 🧠 سلّم التفكير:** العمق (L0–L3) و3 أدوات تفكير بسؤال الناقد بتاع كل واحدة، وسطر `check` قبل الرد. بيتحسب من غير البحث في الـ 1101 وحدة. و`plan --json` فيه مفتاح `thinking`.
- **وصفة «تطوير التنين نفسه»** (`mind/fusion_overlay.json`، فوق بيانات التطبيق المولّدة من غير ما تتلمس): «طور قدرات المستودع… وطور تفكيره» كانت بتروح لـ `app-self-develop` بثقة «قوية» وبوابات forge وpytest. أمثلة الـ 42 وصفة الأصلية بتروح لوصفتها: 140/143 قبل الطبقة وبعدها (أول نسخة سرقت «طوّر التطبيق بالقدرات دي» واتصلّحت).
- **ناقد مستقل:** `agents/rd-critic.md` (sonnet، أدوات قراية بس)، نسخة Claude Code من «🧐 مراجع التفكير» في التطبيق، بوضعين: review للتفكير وverify للناتج من غير استنتاج الوكيل.
- **SKILL.md:** من 284 سطر لـ 107، وأوله سلّم «صح من أول مرة» بأوامره. الوصف كان 1,347 حرف والحد الرسمي 1,024 (`quick_validate.py` بتاع skill-creator)؛ بقى 935، والفاحص قال «Skill is valid!». التاريخ اتنقل بالحرف لـ `references/RD_HISTORY.md` (224 سطر).
- **BOOT.md وCLAUDE.md:** كانوا بيحمّلوا فرع `red-dragon` (واقف على v2.19.0) وهم بيقولوا v3.3.0. التحميل بقى من `main` في `$HOME/golden-dragon` (النسخ القديمة في `$HOME/red-dragon` بتفضل زي ما هي)، ومكان المهارة في Claude Code `~/.claude/skills/golden-dragon`. وقاعدتين جداد: `check` قبل أي رد نهائي، والناقد المستقل للحاجات الغالية. §5 (الرفع) زي ما هي.
- **doc-reader:** ملف `.txt` من ويندوز (CRLF) كان بيطلع `.md` فيه `\r\r\n`، وselftest على `main` كان 13/14. التوحيد بقى في مكان الكتابة نفسه (`write_md`)، فبيغطي كمان HTML وXML وCSV من غير MarkItDown (الناقد المستقل لقاهم). واختبارين جداد بملفات CRLF حقيقية: 16/16.
- **`rd.py check` اتقوّى بعد مراجعة ناقد مستقل (5 مشاكل بـ reproduction، كلهم اتقفلوا بنفس الأوامر):** بيرجع 1 لو فيه ✗ (كان 0)، وبيقرا الرد bytes (UTF-16 بتاع PowerShell 5.1، وUTF-8، وcp1256 بتحذير، وstdin من غير ما ترميز الكونسول يكسّر العربي)، ورسالة واضحة للملف المش موجود أو المجلد أو `--draft` من غير قيمة. والرد الضخم كان بيتقتل بعد 240 ث على 2 MB، ودلوقتي بيتفحص أوله وآخره ومعاه ⚠ في 8 ث.
- **مهارات جديدة في `engine/skills`:** `visible-thinking` (التفكير المرئي) و`arabic-captions-khatt` (كابشن عربي محروق صح؛ كودنا، وkhatt MIT وfreetype-py BSD، والخطوط مش منسوخة).
- **المكتبة 570 ← 589:** 19 مهارة (motion-doctrine وcut-the-curve وseam-craft من hyperframes 0.9.43، وtaste وtaste-application وtaste-distillation وtasteforge-video من ECC، و12 قالب فيديو من open-design)، ومع كل واحدة `LICENSE` من أرشيفها. و5 اتحدّثت لـ HyperFrames 0.9.43 (hyperframes، hyperframes-cli، media-use، reverse-any-video، style-sampling). اتساب `video-template-frame-product-promo-30s` لأن رخصته (MIT باسم صاحب student-kit) مش على الجهاز، واتشال 32 خط woff2 و6 ملفات pyc.
- **الذاكرة:** 26 درس جديد في `mind/lessons_seed.jsonl`: 21 اتعلمهم التنين على اللابتوب ومكانوش بيسافروا مع المستودع، و5 من الشغل ده (s61–s65). و`mind/installed_catalog.json` بقى 547 مهارة بدل 534.
- **مراجع:** `references/REPOS_PILOT_40.md` و7 تقارير `REPOS_BATCH_*` (جرد قدرات 390 مستودع)، والمسارات فيها `%USERPROFILE%` بدل اسم المستخدم.
- **مسارات:** `creative-studio` و`kosif-downloads` بيشاوروا على `Desktop\مهارات\التنين الأسود` (أو `%BLACK_DRAGON_HOME%`). و`font_lab.py` في المستودع اتساب زي ما هو، لأنه بيدوّر في فولدرات خطوط النظام و`DRAGON_FONT_DIRS` بدل مسارات ثابتة.
- **البصمات:** بصمة `engine/` في v3.3.0 كان ناقصها 3 ملفات (`doc-reader` و`app/اقرأني.md`) وعدّادها 2026 والملفات 2035؛ اتعادت كلها.
- **selftest:** فحوص جديدة: عقل الانصهار (العدد، brief، العمق، check، وصفات الطبقة وتوجيهها)، و`plan` في 3 حالات (العقل شغال، مقفول بـ `RD_NO_FUSION=1`، ملفه بايظ) في ذاكرة مؤقتة. النتيجة ok، والراوتر زي ما هو على test: old 66/72/80، fresh 58.9/72.3/80.4.
- **ماتجربش:** التشغيل على لينكس نضيف (سحابة Higgsfield كانت مفصولة)، وzip لـ claude.ai فيه `SKILL.md` واحد (المستودع فيه مئات الـ SKILL.md، والفاحص الرسمي بيرفضها في رفع واحد)، والوصفة الجديدة ماتنقلتش لمصنع التطبيق (`apps/golden-dragon/forge/recipes.py`).

## v3.3.1 — 2026-11-16 (تصليحات)
- doc-reader: ملف نص بنهايات ويندوز (CRLF) كان بيطلع `.md` فيه `\r\r\n`، و`rd.py selftest` كان أحمر على `main` في ويندوز (13/14). اتوحّدت نهايات السطور، وفحص جديد بملف CRLF حقيقي (15/15).
- وصف `SKILL.md` كان 1,347 حرف والحد 1,024 (`quick_validate.py`)، فرفع المهارة بيترفض. اتختصر من غير ما يضيع أي طريق تشغيل مهم.
- BOOT.md وCLAUDE.md كانوا بيحمّلوا فرع `red-dragon` (v2.19.0) وهما بيقولوا v3.3.0. بقوا بيحمّلوا `main` في `~/golden-dragon`، والتحديث بقى فرع ← PR ← `main`.
- reference-lock: على ويندوز من غير fontconfig، الرجوع لمجلد Fonts كان بينادي `fc-scan` ويقع بـ `FileNotFoundError` (وده كان بيوقّع `rd.py selftest`). بقى ياخد اسم الملف لو الأداة مش موجودة، ونفس الحماية لـ `pdffonts` و`fc-list` (11/11).

## v3.3.0 — 2026-11-16 (أي مستند ← Markdown)
- مهارة جديدة `engine/skills/doc-reader` (كودنا) فوق Microsoft MarkItDown (MIT، بيتثبت بـ pip، مش منسوخ): `rd.py md convert|batch|doctor|exts|install|selftest`.
- تصليح الـ PDF العربي اللي pdfminer بيطلّعه بالحروف المعروضة ومقلوب: NFKC بعد قلب السطر، والكلام اللاتيني والأرقام بيرجعوا لاتجاههم. اتجرّب على PDF حقيقي.
- بدائل من غير MarkItDown: نص وCSV وJSON وHTML بالمكتبة العادية، والـ PDF بـ PyMuPDF.
- `docs-office`: أول خطوة بقت التحويل، و`doc-reader` في مهاراته. الراوتر على test زي ما هو (90/92/98).
- CLAUDE.md وBOOT.md: قاعدة «أي PDF أو مستند يتحوّل الأول». `rd.py selftest` بيشغّل `md selftest` (14 فحص).
- التطبيق: `apps/golden-dragon/forge/gd_patches/gd_markitdown.py` بيحوّل المرفقات لـ Markdown.

## v3.2.0 — 2026-11-16 (التنين الذهبي + GitHub v2.15–v2.19)
- دمج 3 اتجاهات من v2.14 (`ddbb6de`): نسخة الجهاز (v3.0 الانصهار، v3.1 الفهم من أول مرة) + `main` على GitHub (v2.15–v2.19). مفيش ملف اتشال من الناحيتين.
- `rd.py`: الأوامر من الناحيتين (`gold`، `consent`، `insta`، `ig`، `agents`، `hypit`، `arena`)، وselftest بيفحص golden-bird وhypit-run وinsta-reader وarena-gate.
- SKILL.md وREADME وBOOT وCLAUDE بقوا باسم التنين الذهبي v3.2.0، والتاريخ القديم كله محفوظ.

## v2.19.0 — 2026-11-14 (الحلبة شرط أساسي)
- مهارة جديدة `engine/skills/arena-gate` (كودنا) فوق `engine/tools/arena/bracket.py` (arena-skill، MIT): size، start، jobs، skip، gate، selftest، والباقي بيروح للـ bracket زي ما هو.
- `agents/rd-fighter.md`: مقاتل Haiku للحلول والجولة الأولى. بيكتب جوه `.arena/` بس، وممنوع يحكم.
- `think.py`: خطوة الحلبة بقت جزء من أي خطة فيها ذوق أو قرار، وسطر الحلبة بيظهر حتى في الطلب المباشر. `rd.py selftest` بيشغّل `arena selftest` (10 حالات حجم + bracket حقيقي بـ 4 وكلاء).
- LIB_AR: حلبه، يتنافسوا، يتعاركوا.

## v2.18.0 — 2026-11-14 (دفعة الصور التانية + أحدث المهارات)
- المكتبة 537 ← 570. من الصور: grill-me (+13 من mattpocock/skills، MIT). frontend-design وHyperFrames (9) كانوا موجودين. Playwright MCP وFigma MCP وphone-harness إعداد بس في `library/mcp_servers.json`.
- أحدث حاجات (اتعملت بين أغسطس ونوفمبر 2026): google/elephant-goldfish-model (7، Apache-2.0)، Ryze open-seo (5، MIT)، huashu-motion، oil-ui، oil-motion، stack-diagram، answer-me-with-html، pinky (MIT/Apache).
- phone-harness وpinky: SKILL.md والتعليمات بس، من غير الكود، وعليهم `device-control`.
- اتسابوا: logo-design-skill وanidoodle (أكبر من حد المكتبة)، reverify (مافيهوش SKILL.md)، scenario-labs (توليد بفلوس).
- DEV_KIT بقى 7 فئات. LIB_AR: 13 كلمة جديدة.

## v2.17.0 — 2026-11-14 (مهارات الصور)
- المكتبة 509 ← 537: vercel-labs/skills (find-skills)، nextlevelbuilder/ui-ux-pro-max-skill (ui-ux-pro-max، من غير tests)، upstash/context7 (context7-cli، context7-mcp، find-docs)، DietrichGebert/ponytail (6)، addyosmani/agent-skills (14 من 25)، usestrix/strix (2 دفاعية؛ مهارات الاختراق الـ 7 اتسابت حسب سياسة المكتبة)، Graphify-Labs/graphify (skills/claude + skill.md).
- أداة «برومت بسيط ← احترافي» من الريل مالهاش اسم ظاهر؛ المكتبة فيها prompt-master من قبل.
- LIB_AR: 15 كلمة عربي جديدة للبحث. `references/DEV_KIT.md` جديد.

## v2.16.0 — 2026-11-14 (instagram-agent-skill)
- `Jakeschincariol/instagram-agent-skill` (commit `d03c56b`، MIT): 10 من الـ 13 مهارة كانوا في المكتبة من 2.7.1 ومطابقين (الفرق نهايات السطور بس). اتضاف ig-viral وig-story وig-repurpose في `library/` و`index.json` (509 مهارة)، و`LICENSE` في الـ 13، و`library/ig-plan/voice.md`.
- جديد: `engine/skills/insta-reader/scripts/ig.py` و`rd.py ig`، و`insta swipe` (instaloader ← TSV ← swipe.py). selftest insta بقى 14.
- السكربتات بتاعتهم stdlib بس ومن غير نت (اتفحصت).

## v2.15.0 — 2026-11-14 (rd-runner + insta-reader)
- جديد: `agents/rd-runner.md` (Haiku)، `scripts/rd_agents.py` (`rd.py agents list|install|check`)، وselftest بيفحص صيغة الـ agents.
- think.py: `ROUTINE`/`TASTE` بيحددوا الخطوات اللي تروح لـ rd-runner، وسطر 🤖 في الخطة. think_cases: 10.
- جديد: `engine/skills/insta-reader` (`insta.py`، 11 فحص من غير نت)، و`rd.py insta`. instaloader 4.16 اتجرّب: كل الخصايص اللي الكود بيستخدمها موجودة. الطلبات الحقيقية لإنستجرام اتحظرت من السحابة، فماتجرّبتش على حساب حقيقي.
- مبني فوق v2.14.0 اللي اترفعت من اللابتوب (hypit-run).

## v2.14.0 — 2026-11-14 (Hypit secure execution)
- Existing Hypit 0.3.2 bridge hardened: missing/unknown provider cost or preflight failures cannot trigger rendering.
- The raw Hypit CLI is inspection-only, so build cannot bypass the provider-price gate.
- Rendering refuses to overwrite an existing output. Priced external providers still require explicit user approval and --allow-paid.
- Added offline regression tests; no Hypit source was copied or third-party service called.
- Full end-to-end rendering, Windows verification and the full Red Dragon selftest remain pending.

## v2.14.0 — 2026-11-14 (طوّر تفكيره وذكائه)
- **بوابة الموافقة** `consent()` + `$R consent` + سطر في `brief` و`plan` + key `consent` في JSON (المفاتيح القديمة زي ما هي).
  - تحليل بالجذر والصيغة لكل جملة لوحدها، وأسماء الأفعال، والمعرّب، والنفي (والنفي اللي بيكمّل بعد «ولا»)، والتأجيل («بكره»، «مش دلوقتي»، «غير بعد ما»، «لما اشوفه»)، وسؤال الاختيار، وفخاخ التعديل.
  - مجموعة عمياء 1 (70، رسايل قصيرة): 56/70 أول قياس. مجموعة عمياء 2 (40، رسايل طويلة): 19/40 أول قياس، منهم 3 موافقات غلط بس. الاتنين اتصلّحوا ودخلوا الاختبارات (179 حالة، selftest بيشغّلهم). مجموعة 3 بعد التجميد: 31/45 مطابقة تمامًا (69%)، فيها 4 موافقات غلط و9 منع ماتمسكش و4 موافقات ماتشافتش (آمنة: بيسأل تاني)؛ بعدها اتصلّحت ودخلت الاختبارات، ومفيش مجموعة رابعة قاست اللي بعد التصليح.
- **understand:** الاختصارات الإنجليزي (don't، it's…) وكلمات أوامر (push، merge، yet، go ahead…) مابقتش تتفك كعربي. اختبارين جداد (18).
- **الراوتر:** قاعدة «تطوير التنين نفسه» بقت تمسك «تفكيره/ذكائه/عقله» و«عقل الطائر». موافقة رفع صريحة في رسالة قصيرة = دفعة لـ `ship` (دليل dev: «ارفعه على واعطيني الرابط» = ship). dev old/fresh قبل وبعد متطابقين. اختبارين جداد في route_tests (40).
- **ذاكرة:** دروس s57–s60، وs09 اتكرر (seen 2). أخطاء M10–M13 في `planning-mind/data/mistakes_seed.jsonl`.

## v2.13.0 — 2026-11-14 (الطائر الذهبي)
- **طلب صاحب الشغل:** «طوّره للطائر الذهبي». الطائر الذهبي = الطائر الأبيض + اللي طلع من الهندسة العكسية لمجلد «مهارات» (studio وmotion_lib وspeech_sync).
- **`apps/golden-bird`** (45 ملف): forge وapp وtests من `Desktop\الطائر الذهبي`، توليد 12:13 (فيه «عقل الطائر الذهبي» من جلسة تانية: تفكير بلغتين، وسلّم 7 درجات، ومستوى تفكير xhigh/max، وبحث مكتبة بيشيل «ال» وحروف العطف) + تصليح `kit` تحت. اتشال ملفين `.woff2` (سياسة الخطوط). اختبار البصمات بيتخطّى ملف الخط الناقص بس، وأي ملف تاني ناقص لسه بيوقّعه. **43/43 اختبار عدّوا** (pytest على اللابتوب، والنسخة اللي في المستودع نفس الملفات من غير الخطوط).
  - مفيش أسرار: مفيش إيميل صاحب الشغل ولا توكنات. الإيميل الوحيد هو عنوان الترخيص التجاري المنشور لمكتبة Lemomo.
  - الكتالوجات فيها مسارات لابتوب صاحب الشغل (`C:\Users\…\مهارات`)، زي 139 ملف موجودين في المستودع قبل كده.
- **`engine/skills/golden-bird`** + **`$R gold`**: بيشغّل نفس `golden_tools.py` بتاع التطبيق. زيادات المهارة:
  - `protocol`، و`where`، و`selftest` (20 فحص).
  - `studio install` محتاج `--yes`.
- **تصليح في الطائر الذهبي نفسه (`forge/modules/golden_tools.py` ← توليد ← `app/golden_tools.py`):** `lib_kit` كان بينسخ `three.module.js` من غير `three.core.js`، فالفيلم كان بيرجع 404 أوفلاين (اتقاس بسيرفر محلي). دلوقتي بيتتبّع الـ imports النسبية لأي ES module ويحطها بنفس مساراتها، وأي import برّه فولدر المكتبة بيبقى فشل صريح بدل ✓، وبيطبع تنبيه `file://`.
  - الاختبار الجديد `test_kit_copies_es_module_imports`. إعادة التوليد غيّرت `golden_tools.py` والختم بس (كود التنين والـ forge بتاع الأبيض ماتغيّروش). احتياطي قبل التعديل: `%APPDATA%\GoldenBird\source_backups\20261114-125956-before-kit-esm`.
  - `GoldenBird.exe` المتثبت ماتبناش: الرام الفاضية كانت 2 جيجا (الحد 4). بياخد التصليح بعد البناء وزرار «حدّث دلوقتي».
- **اتجرّب فعلًا:** `kit` لـ gsap وlottie-web وthree-js، وصفحة HTML اترندرت في Chromium والنت مقفول (مفيش ولا طلب برّه الجهاز)، والـ seek ثابت (0 ← 0.51 ← 1).
  - `file://` عادي بيمنع ES modules.
  - `--allow-file-access-from-files` (اللي `render.cjs` بيستخدمه) أو سيرفر محلي بيشغّلوه.
- **`syncguard.py` `align_units` ← محاذاة DP** (فكرة الذهبي، ومعاها تقسيم وقت الكلمة المدموجة على الحروف):
  - وكيل مستقل قارن الاتنين على 10 حالات و50 فقرة عشوائية.
  - العلامات الصح: B كان 15/20، والذهبي 20/20، وB بعد التعديل 20/20.
  - أقصى خطأ في «ما فيش ← مافيش»: الذهبي 0.27 ث، وB الجديد 0.042 ث.
  - اختبارات جديدة في selftest: كلمة ماتقالتش وليها تكرار بعدها، و«عبدالله ← عبد الله»، و«ما فيش ← مافيش». النسخة القديمة بتفشل فيهم (اللحظة 1.7 بدل 1.0)، والجديدة بتعدّي. sync-guard بقى 20/20.
- **playbooks:**
  - `motion-code`: خطوة `gold lib find`/`kit`، وبوابة «vendor/ مش CDN»، وفخ ES module من `file://`.
  - `voice`: lip sync بـ Rhubarb.
  - `app-dev`: التطبيقات التلاتة.
  - triggers مااتغيّرتش.
- **القدرة `skill-golden`** (52 قدرة). `RD_RULES.md` §11 بروتوكول الذهب.
- **`docs`:**
  - عدد القدرات في `RD_CONNECTIONS.md` بقى بيتحسب (كان 50 ثابت).
  - `RD_LIBRARY.md` اتولّد من جديد (506 مهارة، كانت متأخرة من v2.10).
- **البصمات:** `count` رجع يساوي عدد الملفات (من v2.11 كان واقف على 6120/1992).

## v2.12.0 — 2026-11-13 (أفكار hypit-ai/hypit)
- اتدرس `hypit-ai/hypit` (commit `6bacce0`، 1,721 ملف TypeScript). الكود ماتنسخش: رخصته Apache-2.0 بشروط (ممنوع البيع أو التشغيل كخدمة لناس تانية، ولازم نفس الرخصة لأي نسخة معدّلة). اللي اتاخد أفكار، واتكتبت بكود بايثون بتاعنا.
- `syncguard.py`: `script` (Moment وSelection وفواصل الكابشن والنص المزدوج ← كابشن وكاريوكي وأحداث)، و`grid` (فريمات عليها الكلام)، و`--lock` من reference-lock. selftest بقى 17 فحص.
- playbooks: خطوة في `trend` وخطوة في `reel-montage`. think.py: خطوة التزامن الأولى بتقول `sync script`.
- `references/HYPIT.md`.

## v2.11.0 — 2026-11-13 (claude-mind + WhiteBird)
- **`claude-mind.rar`** (32 ملف) ← `engine/skills/claude-mind` كما هي، و`rd.py mind`. think.py بيشاور على `mind gate` في كل خطة.
- **`WhiteBird_source.zip`** (54 ملف) ← `apps/white-bird`. اتشالت 4 ملفات `.woff2` (سياسة الخطوط)، والرخص OFL فضلت. اختباراته ماتشغّلتش على السحابة.
- **`krita-draw.rar`**: نفس اللي دخل في v2.10.1 (النسخة اللي في المستودع أحدث: فيها `_watch()` و`test_watch.py`)، فماتغيّرش. اتضاف بس خطوة krita في طريق `design-static`.
- مفيش أسرار في الأرشيفات (اتفحصت: مفيش توكنات ولا مفاتيح، `bridge_token` بيتقري من الإعدادات وقت التشغيل بس).

## v2.10.1 — 2026-11-13 (krita-draw من الأرشيف + Krita مابيعلّقش التنين)
- **`krita-draw.rar`** (sha256 `7a151d10…e682`، 19 ملف) اتقارن ملف ملف: مطابق للمهارة المتثبتة واللي في v2.10.0، فمفيش كود جديد. أصله اتوثّق في `engine/skills/krita-draw/SOURCE.json`: مهارة صاحب الشغل، متبنية على هندسة عكسية لـ Krita 5.3.4، وكودها أصلي.
- **تصليح:** مرة من التلاتة Krita خلّص وحفظ وماقفلش، فالتنين فضل مستني `--timeout` كله (300 ث في رسمة بتاخد 16 ث). `_watch()` بقى يقفله بعد 15 ث من علامة النهاية (`seconds` في result.json)، والناتج بيفضل سليم.
  - `scripts/test_watch.py` بيختبر 3 حالات من غير Krita: علّق بعد النهاية، وقفل طبيعي، وعلّق من غير نهاية. التلاتة عدّوا.
- **اتجرّب على Krita الحقيقي من نسخة المستودع:**
  - مثال الصحرا: exit 0 في 10.8 ث.
  - مثال القلب: 16 فريم، MP4 H.264 بمقاس 720×720 و12 فريم في الثانية، وGIF وKRA وPNG، في 42 ث.
  - أول تشغيل بارد خد 131 ث، واتكتب في SKILL.md.
- **جديد:** `rd.py krita render|layers|info` بيروح لـ `engine/skills/krita-draw/scripts/krita_draw.py`.

## v2.10.0 — 2026-11-13 (كل المهارات + تصليح الخطوط على ويندوز)
- **تصليح:** `reference-lock` كان مابيلاقيش ولا خط على ويندوز، لأن `fc-list` بيطلّع `C:/WINDOWS/fonts/x.ttf: Family`، والتقسيم كان عند أول «:» (بتاعة الدرايف). التقسيم بقى بعد امتداد الخط، ولو `fc-list` مش موجود بيدوّر في `%WINDIR%\Fonts` وخطوط المستخدم. الخطوط بقت 352 بدل 0، وselftest بتاعه بقى 11/11 (كان واقع بـ IndexError، فـ `rd.py selftest` كله كان فاشل).
- **جديد: `mind/installed_catalog.json`**: فيه الـ 534 مهارة اللي على لابتوب صاحب الشغل، بالاسم والوصف بس، من غير مسارات ولا ملفات خاصة.
  - `installed()` بترجعله لما الجهاز مافيهوش `~/.claude/skills` (claude.ai، السحابة، جهاز جديد)، والنتايج بتتعلّم «على لابتوب صاحب الشغل».
  - التحديث بيتعمل من اللابتوب: `rd.py skills snapshot`.
  - selftest بيرفض الفهرس لو أقل من 100 مهارة أو فيه مسار مستخدم.
- **المكتبة 500 ← 506:** دخلت 6 مهارات رسمية من `anthropics/skills` معاها `LICENSE.txt` (Apache-2.0): algorithmic-art، canvas-design، frontend-design، mcp-builder، web-artifacts-builder، webapp-testing.
  - الـ 54 خط بتوع canvas-design اتشالوا، ومكانهم `canvas-fonts/README.md` بيقول تجيبهم منين.
  - `doc-coauthoring` مادخلتش، لأنها مالهاش ملف رخصة في المصدر، بس هي موجودة في الفهرس.
- **`lib_find` بقى بيخفي أي مهارة متثبتة على الجهاز اللي شغال عليه.** قبل كده كان بيقترح مهارات متثبتة على إنها «مش متثبتة»، زي book-to-skill. selftest بيقيس البحث العربي من غير الإخفاء، عشان يعدّي على أي جهاز.
- **جديد: `engine/skills/krita-draw`**: الرسم بالكود جوه Krita (ملف .kra بطبقات وأنيميشن)، والمسارات فيه بقت `%USERPROFILE%`.
  - القدرة `skill-krita` في `engine/tools/powers/powers.json` (51 قدرة).
  - كلمات عربي جديدة في قاموس البحث: كريتا، طبقات، طبقه، لوحه، تلوين.
- **اتراجع ومادخلش (موجود أو أقدم):**
  - نسخ التنين الأسود المتثبتة (black-dragon لحد black-dragon-5) أقدم من المحرك اللي هنا (1990.10.0)، أو مطابقة ليه.
  - white-dragon 1.0.0: خططه الـ 28 ودروسه الـ 20 واتصالاته العشرة موجودة كلها هنا.
  - محرك toon متطابق مع الأصل بالـ hash المتسجّل في `tools/toon/SOURCE_TOON.json`.
- **ملاحظة:** المستودع فيه 57 ملف خط من نسخ قديمة، وده عكس قاعدة «ممنوع خطوط». ماتمسحوش في النسخة دي.

## v2.9.1 — 2026-11-13 (قفل المرجع + حارس التزامن)
- جديد: `engine/skills/reference-lock` (`reflock.py`) و`engine/skills/sync-guard` (`syncguard.py`)، و`rd.py ref` و`rd.py sync`.
- think.py: حراس (GUARDS) بيضيفوا خطوة أولى وأخيرة إلزامية وسؤال المرجع، وبيلغوا «نفّذ على طول» لما الطلب فيه مطابقة مرجع أو نص على فيديو.
- mistakes_seed: M08 وM09. think_cases: 9 حالات.
- `rd.py selftest` بيشغّل selftest الاتنين.
- BOOT.md وCLAUDE.md: قاعدتين إلزاميتين جداد.

## v2.9.0 — 2026-11-13 (فكّر وخطّط)
- جديد: `engine/skills/planning-mind/scripts/think.py` و`data/council.json` و`data/mistakes_seed.jsonl` و`evals/think_cases.json`.
- `rd.py think start|revise|check|time|mistake|mistakes|pipeline-selftest` بتروح لـ think.py، والباقي لـ plan.py زي الأول.
- الخطة بتستخدم الراوتر (مش مصنّف منفصل)، وبتسكت في الدردشة و«كمّل»، وبتسأل كل الأسئلة مرة واحدة، والمجلس على كل خطة، والنقد إلزامي (`check` بيرفض «…»).
- العقل الفائق (ultra-mind) متربط: الخطة بتقول أمر `scaffold.py` المناسب للنوع والعمق، وجزء ⑥ فيه تحقق مستقل (CoVe).
- سجل أوقات بيظبط التقدير، وسجل أخطاء بيتعلّم (وبيسجّل درس في `learn` كمان).
- `rd.py selftest` بقى بيشغّل اختبار الخطة (6/6) وبيفشل لو حالة «الراجل والبنت» ماتمسكتش.
- BOOT.md وCLAUDE.md: القاعدة الإلزامية للطلبات متعددة الخطوات بقت `think start`.

## v2.8.2 — 2026-11-13 (دمج 2.8.1 + 2.7.1 + planning-mind)
- **الأساس:** `red-dragon-v2.8.1.zip`. نسخة 2.8 اتبنت فوق 2.7.0، فإضافات 2.7.1 اتنقلت عليها:
  - `engine/skills/blackdragon-desktop-bridge` و`rd.py desktop`.
  - `rd.py dcm`، لأن مجلد dragon-character-memory كان موجود في 2.8.1 من غير أمر.
  - `library/living-site-kosif`.
  - `prompts/USIP_v6_4`.
  - `tools/cinema-c` و`tools/link-collector`.
  - `scripts/make_map.py` و`references/RD_MAP.md` و`MERGE_V271.md`.
  - `BOOT.md` و`CLAUDE.md` و`README.md` و`.gitattributes`.
- **`engine/skills/planning-mind`:**
  - جديدة من `planning-mind.zip`.
  - `rd.py think`.
  - `plan.py` بقى بيدوّر على `rd.py` في نفس الشجرة الأول، وبعدين في `~/.claude/skills/red-dragon`.
  - مااتضافلهاش طريق ولا كلمات تفعيل جديدة، فالراوتر ماتغيّرش.
- **selftest:**
  - `classify` بقت بتقبل `repo`. قبل كده كان بيفشل لما التنين يتنسخ بـ git.
  - `PUBLIC_EDITION.md` اختياري.
- **`v2.8.rar` (مجلد شغل 2.8):** كل ملف فيه بنفس اسم ملف في 2.8.1 طلع متطابق. الـ 60 ملف الزيادة (سكربتات مساعدة وتفريغات تقييم ومقترحات) اتحفظوا في `references/work/v2.8-staging/` من غير ما حاجة تشغّلهم.

## v2.8.1 — 2026-11-13 (بلوك أنضف لتطبيق التنين، وموضوع كل محادثة لوحدها)
- **المشكلة اللي اتقاست في التطبيق (10 رسايل تجربة):**
  - «كمل» ماكانش ليها بلوك خالص، لأن `brain.note` في التطبيق كان بيرفض أي نص أقل من 4 حروف.
  - التطبيق ماكانش بيبعت سياق، فالعقل كان بيقرا الملف المشترك `last_turn.json`، والموضوع كان بيتسرّب بين المحادثات (طلب لوجو راح re-file بعد رسالة تحليل في محادثة تانية).
  - الدردشة («ازيك»، «شكرا») كان بيطلعلها بلوك 376 لـ 849 حرف مالوش لازمة.
- **في العقل (`rd.py`):**
  - `brief` في الدردشة و«كمل» (`greet` / `cont`) مابيضيفش مستودعات ولا مهارات ولا مكتبة ولا دروس.
  - المستودعات ومهارات المكتبة لازم تطابق كلمتين مختلفتين على الأقل من الطلب (`BRIEF_MIN_HITS = 2`، والكلمة العربي بتتحسب مرة واحدة حتى لو اتوسّعت لمرادفات)، أو أول جزء من اسمها يكون في الطلب (`_hits` و`_named` و`_relevant`).
  - الدروس بتتقص على آخر كلمة كاملة (`_clip`) بدل القص في نص الكلمة.
- **في التطبيق (`apps/dragon_desktop/brain.py` و`app.py`):**
  - `brain.note(text, history=...)`: التطبيق بقى بيبعت آخر 6 رسايل للمستخدم من نفس المحادثة (`Session.log`)، و`chat_topic` بيحسب الموضوع منها بـ `topic_update`، ويمرّره لـ `brief(prev=...)`، فمابقاش فيه اعتماد على الملف المشترك.
  - أي نص مش فاضي بياخد بلوك (منها «كمل»).
- **القياس (327 طلب حقيقي، 2.8.0 قدام 2.8.1، نفس المكتبة):**
  - الطريق المختار اتغيّر في **0** طلب.
  - متوسط البلوك 1,190 ← **1,045** حرف.
  - سطر المستودعات ظهر في 255 ← **115** طلب، وسطر المكتبة 153 ← **53**.
  - الدروس المقطوعة في نص كلمة 342 ← **24**.
  - تجربة التطبيق (10 رسايل): الدردشة 0 بلوك، «كمل» بعد تحليل ← re-file (ثقة عالية)، ومفيش تسريب بين المحادثات، والوقت 1.9 ثانية للعشرة.
- **معروف ولسه:** «اعمل لوجو لقناة…» لسه بيروح download بثقة ضعيفة (ضعف في الراوتر نفسه، مش من التعديل ده).

## v2.8.0 — 2026-11-13 (راوتر بذاكرة أمثلة وموضوع المحادثة، مقاس على مجموعة مخفية + بوابة منع التراجع)
اتبنت فوق 2.7.0 المتثبتة، في نسخة شغل منفصلة (`~/rd-staging/v2.8`)، والمتثبت كان مقفول (`guard lock`) طول الشغل.
- **التقييم (`mind/route_eval/`):**
  - مجموعة جديدة اسمها fresh: 221 رسالة من جلسات Claude Code المحلية، ومعاها الرسالة اللي قبل كل واحدة (`fresh_cc.json`).
  - المقيّمين: اتنين مستقلين ماشافوش الراوتر (`labels_fresh.json` و`labels_fresh_b.json`)، اتفقوا على الطريق الأول 86%، والتقييم التوافقي في `labels_fresh_consensus.json`.
  - `route_eval2.py` فيه `--ctx` و`--topic` و`--novel` و`--calib` و`--json` و`--dump`.
  - أمانة الذاكرة: طلبات test للمجموعتين مستخبية دايمًا، وفي dev بيستخبى كمان الطلب اللي بيتقاس (leave-one-out).
  - الضبط كله على dev، وtest اتقاس مرة واحدة بعد ما القيم اتقفلت.
- **الأرقام على test (الأول صح / مقبول / في أول 3):**
  - old من غير سياق: 52/58/66 ← **66/72/80**.
  - fresh بموضوع المحادثة: 23/38/36 ← **59/71/80**. وبالرسالة اللي قبلها بس: 58/71/76. ومن غير سياق خالص: 37/54/54.
  - الطلبات اللي مالهاش شبيه قريب في الذاكرة (تشابه أقل من 0.8): old 70%، fresh 71% مقبول.
  - الثقة على test: العالية 92% في old و88% في fresh، والمتوسطة 73% و67%، والضعيفة 44% و31%.
  - dev كان أعلى (old 78/86/84، fresh 72/83/84)، فالفرق حوالي 12-14 نقطة.
- **`rd.py`:**
  - `strip_wrappers()`، وبقت قبل فك الكيبورد. `understand()` بقى بيرجّع مفتاح `wrappers`.
  - `GREET_RX` و`NONE_EXTRA` و`CONT_RX`.
  - ذاكرة الأمثلة: `examples()`، و`ex_near()`، و`ex_key()`، و`EX_EXCLUDE`. القيم: EX_W=6، وk=5، والحد الأدنى للتشابه 0.3، والأس 2.
  - `translit()`.
  - `_pb_scores()`: الكلمات × IDF، والنوايا، والعبارات × 3، والأمثلة.
  - `route(q, limit, prev)`: وزن السياق 1.0 للرد اللي بيكمّل، و0.5 لو أعلى سكور أقل من 6، و0.1 غير كده.
  - `confidence()`، و`topic_update()`، و`last_turn()`، و`_topic_for()`، و`add_example()`.
  - `brief()` بقى بيكتب `last_turn.json`، وبيرجّع كمان `confidence` و`alternative` و`used_context`.
  - `plan --prev` و`route --prev`.
  - أمر جديد `teach`، و`outcome ok` بقى بيضيف مثال.
  - 3 نوايا جديدة: status، وapp-dev، وself-improve.
  - `_garbled()` بقى يسيب `[TAG]` الكابيتال في حاله.
  - `selftest` فيه بوابة test مع `floor.json`، و`--quick` بيتخطّاها.
- **تصليحين من التجربة الكاملة على المتثبت** (`brief` ثم «كمل» ثم سؤال حالة ثم تحية ثم `teach` ثم `outcome`). كانت 9 من 11 وبقت 11 من 11:
  - **التحية ومعاها كلام ونس بس** («ازيك يا تنين عامل ايه»، «شكرا يا باشا») كانت بتتقري طلب، فالسياق كان بيودّيها لطريق. اتعمل `CHAT_HEAD` و`CHAT_WORDS` و`_chat_rest()`، فالرسالة دي بقت دردشة من غير طريق. ولو بعد شيل كلام الونس فضل «كمل» أو «يلا»، بتتعامل كاستكمال.
  - **سؤال الحالة كان بيتورّث:** «هل خلصت» كان بيدخل موضوع المحادثة بـ 14 نقطة، فطلب جديد ضعيف بعده كان بيروح status. `NO_CARRY = {none, status}` مابيدخلوش الموضوع، ومابيتضافوش من الرسالة اللي قبل.
  - **كسر عشري:** تشابه النسخة المطابقة من مثال متعلّم كان بيطلع 0.99999، فكان بيقع تحت حد «الطلب الضعيف». بقى بيتقرّب لـ 1.0.
  - **اختبارات:** `route_tests.json` بقى 38 (اتضاف «none» للدردشة)، و`route_ctx_tests.json` جديد فيه 7 اختبارات بالرسالة اللي قبلها. النسخة اللي قبل التصليح بتفشل في 5 منهم.
  - **القياس:** dev ماتغيّرش. test اتقاس تاني مرة واحدة: الأول صح والمقبول زي ما هما، و«في أول 3» في fresh نزلت طلب واحد من 112 (81 ← 80). في كل نص فيه مكسب طلب وخسارة طلب.
- **البيانات:**
  - `route_examples.jsonl`: 264 من 322. اتشال سر واحد، ورسالة فاضية، و56 رد قصير معناه من الرسالة اللي قبله.
  - `translit.json`: 58 كلمة.
  - `dictation.json`: من 40 لـ 102. اترفض «اللسة» و«في كروب».
  - `playbooks.json`: +59 كلمة و+57 عبارة من dev بس. الكلمات العامة اللي بتتصادم مادخلتش، لأنها مازوّدتش حاجة على dev.
  - `route_tests.json`: من 31 لـ 36. و`understand_tests.json`: من 6 لـ 16 (الأغلفة، و[ERROR]، والكيبورد).
- **اتجرّب ومااتاخدش:**
  - الكلمات «الخطرة» العامة.
  - وزن موضوع المحادثة: من 0.6 لـ 0.9 كلهم نفس المستوى، فاتاخد 0.7.
  - أس الأمثلة 1: كان بيودّي «حلل مستودع جيت هب ده وضيفه كمهاره» لـ app-dev من أمثلة شبهها ضعيف (0.30-0.35) بتتجمّع، والأس 2 صلّحها.
- **الوكلاء:** 4 بس، لأن الشغل كله في ملف واحد:
  - الأول: تصحيحات الصوت وقاموس الحروف.
  - التاني: الكلمات والعبارات.
  - التالت: الأغلفة.
  - الرابع: المقيّم المستقل التاني.
  - كل اقتراحاتهم اتراجعت واتقاست على dev قبل ما تدخل.

## v2.7.1 — 2026-11-13 (جسر التنين الأسود + dragon-character-memory + جرد كل المحادثات)
التفاصيل في `references/MERGE_V271.md`.

## v2.7.0 — 2026-11-13 (Dragon Character Memory & Auto Rotoscope)
اتبنت فوق 2.6.0 المجهّزة (اللي لسه ماتثبتتش). المتثبت والـ zips القديمة ماتلمسوش.
- **مهارة جديدة `engine/skills/character-memory/`:**
  - `scripts/charmem/`: reference، extract، analyze، redraw، memory، animate، evaluate، rig.
  - `scripts/charmem_cli.py`.
  - `tests/test_charmem.py`.
  - المراجع: FORMAT وGITHUB_REVIEW وCOMPONENTS وRESULTS.
  - محلية بالكامل: numpy وOpenCV وscikit-image وcairosvg وffmpeg.
- **`rd.py character …`** بيشغّل الـ CLI بتاعها. وطريق `character-memory` دخل `playbooks.json`، وسؤالين في `route_tests.json`، وكلمات (روتوسكوب، شخصية، كرتون، تتبع) في `LIB_AR`.
- **دروس اتقاست أثناء البناء:**
  - cv2.imread مابيفتحش مسار عربي، والحل `np.fromfile` + `imdecode`.
  - وسيط الخلفية بيتلوّث لو الشخصية واقفة نص الفيلم، والحل السيلويت من الخط الخارجي.
  - الغامق الثابت (سما المغرب) مش حبر.
  - الراس بالكاب مدوّرة، و«فوق» هو المحور الأقرب للرأسي مش الأطول.
  - كونتور البكسل + تكبير بيدّي 23 dB، والمربعات الزاحفة 29 dB.
  - هيكل الطرف المقطوع بيطلّع شوكات، فالخط المركزي بيتعمل بالشرائح.
  - نسبة الكوع والركبة تتعلّم من الفريمات اللي المفصل فيها متني.

## v2.6.0 — 2026-11-13 (راوتر أذكى مقاس أعمى + كل المهارات المتثبتة + مسرح الدمى + رياضة الرسم)
اتبنت فوق **النسخة المتثبتة** (2.4.0 في الكود، 2.5.0 في SKILL.md، فيها 500 مستودع و500 مهارة من جلسة system32). `red-dragon-v2.5.0.zip` اتقارن بالـ hash وطلع أقدم منها (مكتبة 200، rd.py أصغر، ومفيهوش ولا ملف جديد برّه المكتبة)، فماتبناش عليه.
- **الراوتر (`route()`):** IDF على كلمات الخطط، QSTOP (كلمات سؤال وحشو مصري)، جذر عربي خفيف، غلطة حرف (≥ 5 حروف)، رسالة لينك/مسار/سلامات من غير طريق، 4 قواعد نية، ولينك لوحده حسب الموقع. التوقيع وشكل الرجوع زي ما هما. القياس: 101 طلب حقيقي (`mind/route_eval/`)، ومقيّم مستقل (وكيل ماشافش الراوتر) حدّد الطريق. اتطوّر على الطلبات الزوجية بس. على الفردية (50): الأول صح 44% → 52%، مقبول 48% → 58%، أول 3 58% → 66%. على الكل: 41% → 54%، 49% → 62%، 56% → 66%. طلب النهارده («طوّر التنين… رسم الأشخاص بالظلال… مهارة رياضية») كان بيروح app-dev/status، بقى self-improve ثم draw-math ثم shadow-puppet.
- **المهارات المتثبتة:** `installed()` و`inst_find()` و`inst_line()`؛ `skills find` (نص) بيعرض المتثبت الأول، و`--installed` JSON؛ `plan` (③ب) و`brief` (سطر + مفتاح `installed`). 543 مهارة: 35 بتاعة صاحب الشغل، و500 اتثبتت من المكتبة، و8 باكدجات. القراية الأولى 0.41 ث، والكاش في `~/.red-dragon/installed_index.json`.
- **طريقين جديدين (37):** `shadow-puppet` و`draw-math`، و3 أسئلة توجيه (26 في `route_tests.json`)، و15 كلمة عربي في `LIB_AR` (ظل، دمى، عرائس، مسافة، نسب، زاوية، منظور، فيزيا…).
- **`tools/draw-math/`** (مبنية بوكيل مساعد واتراجعت): `scripts/dmath.py` (16 أمر، مكتبة بايثون القياسية بس)، و`tests/test_dmath.py` (26 ناجح)، و`references/sources.md` بدرجة ثقة لكل مصدر. `$R math …` بيشغّلها.
- **`engine/app/engines/shadow_theatre/`:** `puppet.py` جديد، و`human_figure.py` (تشريح SDF ومشي IK؛ حوض المشي متصلّح بـ smooth-min لكل قدم، فالقفزة في الفريم 0.61% → 0.18% من الطول، ورفعة القدم بتصغر مع الخطوة القصيرة)، وسطر تفعيل في `__init__.py` لما المشهد فيه `puppetry`. مثال كامل شغال: `هام\output\puppet_v2\puppet_demo.py` (فيلم 12 ث).
- `selftest`: ok (37 طريق، 60 قدرة، 126 درس، 162 محادثة). فحص أسماء التطبيق: 12/12.

## v2.4.0 — 2026-11-12 (كل المحادثات + باليتة الطبيعة + دروس الأبيض + تنضيف)
اتبنت فوق v2.3.0 كاملة. مفيش ملف اتمسح غير الكاش.
- **ذاكرة المحادثات 45 → 162:** 6 وكلاء قروا 83 محادثة في مشروع «تطوير» (بـ read_thread، كاملة) و27 جلسة Claude Code سحابية (بـ list_events) وكتبوا ملف لكل محادثة بنفس شكل `mind/chats/`. جلسة «شورت موشن جرافيك» (34 ألف حدث، اتضغطت 21 مرة) اتقسمت 8 مواضيع، واتقرت من آخر ملخص وآخر صفحات ونوتات الحزمة، فاللي قبل 9 نوفمبر فيها جزئي. 9 جلسات سحابة طويلة اتقرا آخرها بس، ومعلّم في أول ملفها «جزئي». لينكين مشاركة (`claude.ai/share/…` و`cshk_…`) مااتفتحوش من السحابة.
- **البحث:** `chats` بيقرا `c*`/`t*`/`s*`. الترتيب بالأحدث بقى بتاريخ البداية مش بالـ id (الـ id بقى بيبدأ بحروف مختلفة). نتايج محادثات المشروع والسحابة × 0.7 قدام محادثات التطبيق. القياس: الاختبار الأعمى أول 3 = 26/30 (كان 24/30 من غير الوزن)، الـ 17 سؤال القدام 17/17، و4 أسئلة جديدة اتضافت لـ `chats_tests.json` (صفحة الرفع، البرجر، إكسل القطع البديلة، موقع تيك توك).
- **70 درس** (h01–h70، من 78 بعد شيل المكرر)، وقسم جديد في `OWNER_ESSENCE.md`، و10 كلمات صوت.
- **`engine/skills/nature-palette`:** مهارة باليتة الطبيعة زي ما اتسلّمت (SKILL.md، `scripts/nature_palette.py`، `references/METHOD.md`، أسماء 84 لون بالعربي، خط Cairo برخصة OFL). أوامرها: `extract` و`reel` و`learn`.
- **طريق جديد `nature-palette`** في `mind/playbooks.json` (35 طريق)، و2 أسئلة توجيه في `route_tests.json`. `route "استخرج الوان الطائر ده"` بيجيبه الأول (6.0، اللي بعده 2.0).
- **ذاكرة التنين الأبيض:** `lessons()` و`outcomes()` بيقروا `~/.white-dragon/` (أو `WHITE_DRAGON_HOME`) قبل `~/.red-dragon/`، فالأحمر يكسب لو نفس الدرس متكرر. اتجرب بدرس وهمي في HOME مؤقت: ظهر في `recall`.
- **المقارنة اللي اتبنت عليها:** الأسود v10.17.0 (1240 ملف)، v1990.4 (1171)، v1990.9.0 (1569)، والأبيض v1.0.0: كل مسار فيهم موجود هنا، و`own_tools.json` مافيهوش أداة ناقصة (85 أداة).
- اتشال `engine/app/apps/dragon_desktop/.ruff_cache`. `selftest`: ok (35 طريق، 60 قدرة، 50 درس، 45 محادثة).

## v2.3.0 — 2026-11-12 (الذاكرة بتحدّث نفسها + بحث بيستحمل الغلط + اختبار أعمى)
v2.2 ماتثبّتتش، فـ v2.3 جواها v2.2 كاملة ومعاها الحاجات دي:
- **تحديث تلقائي من أرشيف التطبيق:** كل محادثة في الفهرس بقى ليها خط أساس (`n_user`)، يعني عدد رسايل صاحب الشغل اللي الخلاصة غطّتها. `rd.py chats --refresh` بيقرا `%APPDATA%\BlackDragon\chat_library`. أي رسالة بعد خط الأساس أو أي محادثة جديدة، بيكتب ليها الطلب وآخر رد و«اللي اتعمل» وملفات التسليم في `~/.red-dragon/chats/`، والمهارة نفسها مابتتلمسش. وبيخبّي الأسرار والإيميلات والأرقام. وبيشتغل لوحده قبل أي بحث لو الأرشيف اتغيّر. قراية محادثة كبيرة بتاخد 1 ملّي ثانية.
- **المسارات اللي فيها مسافات** (`خطابة 2`) بتتاخد من روابط markdown، والنص اللي بين `` ` ``، وقوايم 📄 بس، عشان الكلام العادي مايتفهمش غلط إنه مسار.
- **البحث:**
  - تجريد خفيف للعربي والمصري (بيشطب، تشطب → شطب).
  - قاموس للكلام الإنجليزي المكتوب بحروف عربي (اسكيلات، كرييتف، كلينك، ميموري…).
  - غلطة حرف واحد بفهرس حذف حرف.
  - فك الكيبورد الإنجليزي قبل البحث.
  - ترتيب جديد: أحسن سطر بيجمع كلمات السؤال ليه الوزن الأكبر.
- **الاختبار الأعمى:** وكيل مايعرفش الكود كتب 30 سؤال بطريقة صاحب الشغل. الضبط اتعمل على 15 منهم، والقياس على الـ 15 التانيين اتعمل مرة واحدة: الأولى صح 73% (كانت 67%)، والصح في أول 3 نتايج 93% (كانت 80%). الأسئلة المكتوبة بسرعة: 3 من 3 في أول 3 (كانت 1 من 3). الـ 17 سؤال القدام لسه 17 من 17. `selftest` بيوقع لو أول 3 نتايج نزلوا تحت 85% على الـ 30.
- **حدود معروفة:** الصرف العربي الأعمق (نجحت/ناجح) لسه مابيتطابقش، والأرقام لوحدها من غير كلمات مميزة بتلخبط الترتيب.
- إعادة تلخيص المحادثتين اللي اتحدّثوا الساعة 14:45 (الغسالة والكورنيش، وكل المهارات).

## v2.2.0 — 2026-11-12 (ذاكرة كل المحادثات + الحارس + تحليل «هام» بالـ 34 أداة)
اتركّبت فوق v2.1.0 بسكربت إضافة (`apply_addon.py`) بيدوّر على أماكن الإضافة بأنماط، عشان شغل الجلسة اللي بنت v2.0/v2.1 يفضل زي ما هو. مفيش ملف اتمسح.

**جديد**
- **ذاكرة المحادثات:** `mind/chats/` فيه 45 ملف، ملف لكل محادثة في أرشيف تطبيق التنين (من 2026-11-09 لـ 2026-11-12). كل ملف فيه: الطلبات، والنتيجة وحالتها، والمسارات، والأرقام المقاسة، والقرارات، والدروس، والحدود والرفض، والحاجات اللي لسه مفتوحة. اتلخّصوا بـ 8 وكلاء بالتوازي من الأرشيف الكامل (2.9 ميجا)، واتراجعوا، واتقنّعت فيهم الأسرار والإيميلات والأرقام.
- **`rd.py chats "…"`:** بيوزن الكلمات النادرة أكتر، وبيفهم المرادفات المصرية (اكسل↔excel، هيجز↔higgsfield…)، وأي اسم حرفي زي `v1990.10.0` بيوزن أكتر. ولو محادثتين اتعارضوا الأحدث يكسب، وكلمة «دلوقتي» أو «آخر» بتجيب آخر حقيقة اتقالت في سطر.
- **`rd.py files "…"`:** بيجيب مسار الملف من المحادثات، ومعاه ✓ لو لسه موجود أو ✗ لو اتنقل. اتأكد يدويًا: مجلد `خطابة 2\ديزني_ريل` مابقاش موجود فعلًا.
- **`rd.py guard PATH`:** بيدوّر على الملفات اللي اتغيّرت أو اتنسخت أو بتكبر، وعلى الأقفال، وفيه `--save` و`--diff` (لقطة ومقارنة)، و`lock`/`unlock`. بيبص على وقت الإنشاء كمان، لأن 2,055 ملف اتنسخوا بتواريخ 09:54 الساعة 13:50 والحارس اللي بيبص على وقت التعديل بس ماشافهمش.
- **`plan` و`recall`** بقوا يجيبوا «④ب من ذاكرة المحادثات»، وبيفكّروا بالحارس قبل الكتابة.
- **16 درس جديد (s35–s50)**، والدروس الخام في `RD_CHATS_LESSONS.md`.
- **`references/RE_REPORT_HAM.md`:** فيه الفرضيات الأربعة وحكم كل واحدة، وقسم لكل أداة من الـ 34.
- **`selftest`** بقى يتأكد إن الفهرس مطابق للملفات، وبيشغّل 17 سؤال ذاكرة لازم كل واحد فيهم يجيب المحادثة الصح الأولى.

**ليه الحارس:** التنين الأحمر نفسه اتبنى في جلستين في نفس الوقت. سكربت تثبيت قديم كان هيكتب فوق `rd.py` و`SKILL.md` بتوع v2.1، والـ dry-run هو اللي كشف ده. عشان كده التثبيت بقى «إضافة فوق الموجود وقت التثبيت»، مش نسخ من staging قديم.
