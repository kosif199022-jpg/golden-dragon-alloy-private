# سجل دمج v2.7.1 — كل مصدر راح فين (2026-11-13)

الطريقة: كل أرشيف اتفك في مجلد فاضي، وكل ملف فيه اتقارن ببصمة SHA-256 مع كل ملفات التنين الأحمر 2.7.0. اللي بصمته مش موجودة اتدوّر عليه بالاسم، وبعدها بالمحتوى. الأدوات: `scripts/make_map.py` للخريطة، وسكربت المقارنة في سجل الجلسة.

## اتضاف في 2.7.1
| المصدر | راح فين | ليه |
|---|---|---|
| `red-dragon-v2.7.1-blackdragon2-desktop-bridge-patch.zip` | `engine/skills/blackdragon-desktop-bridge/` + `rd.py desktop` | الباتش زي ما هو. قراءة بس، وكل أمر محتاج `--confirm-local-read` |
| `dragon-character-memory-v1.0.0.zip` (النسختين نفس البصمة) | `engine/skills/dragon-character-memory/` + `rd.py dcm` + خطوة في طريق `character-memory` | من غير `integrate.py`: كان هيمسح طريق 2.7 ويحط مكانه. الكلمات المفعّلة ماتغيّرتش |
| `project-files/living-site/skill-kosif/` | `engine/skills/library/living-site-kosif/` | نسخة KOSIF أغنى من living-site: فحص عربي RTL، و`--levels/--json/--strict`، ومخرج Kling، وسجل تكلفة. 23 اختبار ناجح. living-site الأصلية فضلت زي ما هي |
| `protocol/USIP_v6_4_20261101.zip` | `engine/references/prompts/USIP_v6_4/` (من غير مجلد evidence) | المحرك كان فيه v5.6 بس |
| `cinema-c/` | `tools/cinema-c/` | سكربت V35 والفرق والاختبارات ماكانوش في الحزمة (كان فيه ذكر بس) |
| `link-collector/collect-links.js` | `tools/link-collector/` | نفس `USIP_v6_4/scripts/collect_links.js`؛ اتحط في مكان يتلاقى |

## كان موجود بالفعل (بالبصمة أو بنسخة أحدث)
| المصدر | الحالة |
|---|---|
| `skills.rar` | نفس `engine/skills/` بالظبط (938 ملف، صفر فرق) |
| `red-dragon-v2.7.0 2.zip` | نسخة طبق الأصل من `red-dragon-v2.7.0.zip` |
| ملفات النهارده: living-site، GrowKaz Stickman، arabic-minimal-reels، AI Motion Graphics، faceless-shorts، saas-animation، Claude edit skill، motion-reel-kit، talking-head-reels | كلها موجودة بالبصمة في `engine/skills/library/` و`engine/skills/` (اللي فرق `.DS_Store` بس) |
| `nature-palette.skill` | موجودة بالبصمة (`engine/skills/nature-palette`) |
| التنين الأسود v10.17 / v1990.4 / v1990.6 / v1990.9 / black-dragon-skill.zip | المحرك جوه = v1990.10 اللي دمجهم. الفروق ملفات بنفس الاسم أحدث (اختبارات، SKILL، catalog.sqlite). مفيش اسم ملف ناقص غير الخطوط |
| `white-dragon-v1.0.0.zip` | اتدمج في 2.x (WD_* بقت RD_*، و`wd.py` اتطوّر لـ `rd.py`) |
| `kosif-reel-hooks.skill` و`kosif-shadow-theatre.skill` | اتطوّروا لمحركات: `engine/app/engines/reel_hooks/` و`shadow_theatre/` + `engine/references/skills/*.md` |
| بروتوكول الفيديو الإلزامي وبرومبت المونتاج | `engine/references/VIDEO_PROTOCOL_V2_ORIGINAL.md` (بملاحظة مسارات v1.2) و`PASTE_PROMPT.md` |
| `free-stock-media` | `engine/tools/stock/free_photos.py` + `engine/references/FREE_STOCK.md` |
| `craft-anything` | `library/craft-anything/` (المهارة + الأدلة). الكود Rust نفسه برّه، بيتبني على الجهاز |
| `kosif-tool-main.zip` (أطلس 311 أسلوب + kosif-superpowers) | **مقصود إنه مايتحطّش جوه.** المحرك بيقرا المستودع من الجهاز (`~/kosif-tool`) بـ `tool sp` و`tool atlas`. نسخه هنا كان هيزوّد 200 ميجا ويبقى عندنا نسختين |

## اتساب برّه عن قصد
| المصدر | ليه |
|---|---|
| `BlackDragon.rar` | ده مجلد بيانات التطبيق على الجهاز: محادثات (42 ميجا)، تسجيلات صوت، و`settings.json` فيه `bridge_token` و`auto_approve: true`. بيانات شخصية وتوكن، مش كود. مايتشاركش |
| الخطوط (`*.ttf`, `*.woff2`) | سياسة الحزمة: مفيش خطوط جوه الـ zip (`engine/references/FONTS_REQUIRED.md`). 8 منهم موجودين في `black-dragon/skill-install/black-dragon-skill.zip` ويترجعوا بـ `tool fonts fetch --from DIR --yes` بعد موافقتك |
| `fusionforge-hub-bridge/evidence`، `deployment-monitor`، فيديوهات وتقارير التجارب، إكسل القطع البديلة | نواتج شغل أو مشاريع تانية، مش قدرات |
