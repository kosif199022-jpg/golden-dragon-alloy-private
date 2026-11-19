# Higgsfield المجاني — حصر مُقاس (v1990، 2026-11-11)

الحصر الكامل القابل للبحث: `tool hf free` (المصدر `tools/hf_sandbox/free.json`، 28 بند). الصفحة دي ملخص القياس.

**الطريقة:** `balance` و`transactions` قبل كل مجموعة تجارب وبعدها. الرصيد 347.88 قبل وبعد، وآخر قيد فضل بتاريخ 2026-11-10. القياس اتعمل على جولتين في نفس اليوم، والتانية أعادت فحص أرقام الأولى. ده قياس يوم واحد على خطة Ultra، مش وعد من Higgsfield: `balance` قبل وبعد أي شغل كبير.

## مُجرَّب فعليًا من غير خصم
| الأداة | التجربة | النتيجة |
|---|---|---|
| 3D Jutsu (Blender 5.2 LTS مستضاف) | مشروع + مشهد (حلقة معدنية، أرضية، Sun + Point، كاميرا) + رندر EEVEE 540×960 | 41 ث؛ ‎.blend 629 KB، GLB 31 KB، PNG. أول محاولة وقعت لأن المشروع الجديد مالوش World |
| Match Cut + Tracelab (`apps_invoke`) | `create_typewriter` | MP4 720×1278، 3.5 ث. 28 action في التطبيق؛ واحد بس اتقاس |
| higgsedit | 540×960: 72 فريم. 1080×1920 / 30 fps: 90 فريم | حوالي 11 ms و24.4 ms للفريم. العربي **مابيظهرش** بالخط الافتراضي؛ بيظهر بـ`fontFamily: "DejaVu Sans"` و`direction: "rtl"` |
| تحليل Katana | ريل What-If 50 ث، وريل 60 ث (ink-gold) | 78 ث للأول: 5 قطعات، 106.35 BPM، 89 beat، 27 صفحة فريمات. التاني: 38 لقطة، 142 beat، 64 حدث طاقة، 183 كلمة |
| faster-whisper | 50 ث صوت، small int8 | 23 ث |
| color-grade | فريم بلوك the-matrix | نجح |
| `tool framecheck` على الـsandbox | فيلم دعاء حقيقي 1080×1920، 684 فريم | 15 ث: 0 نطّة، 0 قطع متداخل، نقلتين سريعتين (4 و8 فريمات)، 5 ورقات مترقّمة |
| `tiktok_music_trending` | SA/7DAY ثم EG/7DAY | 100 تراك كل مرة بروابط استماع؛ الحساب active |
| `get_presets` (genjutsu-trending) | مرتين بينهم حوالي نص ساعة | 12 بريسيت كل مرة، والقايمة اتغيرت. كل بريسيت بفيديو معاينة عام (HEAD 200) |
| 56 مرجع What-If | HEAD من الـsandbox | 56/56 = 200 |
| `media_upload` + PUT + `media_confirm` | MP4 | HTTP 200 + تأكيد |
| `get_cost` | gpt_image_2_6 | 0.25 كريدت، من غير تنفيذ |

## مواصفات الـsandbox المُقاسة (Standard)
gVisor على Modal، Debian 12، 2 vCPU (cgroup)، 8 GiB، من غير GPU ولا Swap ولا root. ffmpeg 5.1.9 (x264، x265، libaom، SVT-AV1، rav1e، VP9، ProRes: كلها اتجرّب ترميزها). nvenc وvaapi في القايمة بس مابيشتغلوش. Chromium 153 عن طريق Playwright 1.63. Python 3.12، Node 22. مفيش Blender ولا torch ولا Remotion. الأمر الواحد 120 ث بالكتير، والخلفية 15 د.

## مش مجاني حتى لو شكله كده
أوامر `*-grade-hf` و`*-hf` (Seedance 2.5 video edit)، `/gpu`، كل `generate_*`، `remove_background`، Genjutsu (نقل الحركة)، `scene_builder_3d_generate_*`.

## غير مُقاس (اعتبره مدفوع)
`video_analysis_create`، `virality_predictor`، `media_import_url`، Sandbox XL (قياس 11-10 القديم لم يُعَد)، وباقي الـ27 action في Match Cut.
التوليد ببلاش: `unlim.available=false` للحساب يوم القياس. `use_unlim` و`use_free_gens` بطلبه الصريح بس، ومفيش فتح تجربة أو اشتراك من التنين.

## الترند: إيه اللي ينفع وإيه اللي لأ
- **ينفع ببلاش:** سحب قايمة الترند (موسيقى تيك توك، بريسيتات Genjutsu الرائجة والجديدة، Viral، Katana، What-If)، وتحليل أي فيديو معاينة أو مرجع عام بـ`tool hf trend commands SLUG|URL`.
- **ماينفعش:** تنزيل تراك ترند من CDN تيك توك بتزوير Referer أو User-Agent (اترفض كتحايل على فحص البوتات). التراك بيتركّب من ودجت النشر في تيك توك، والنشر ممنوع من التنين.
- **بكريدت:** تنفيذ أي بريسيت (`execute_preset`)، ونقل الحركة نفسه.
- القايمة حية وبتتغير: اسحبها كل مرة، وماتعتمدش على لقطة محفوظة.

## الخطوط العربية
مفيش خط عربي مخصص في الـsandbox (DejaVu وFreeSerif بس). ffmpeg مش مبني بـharfbuzz، فـ`drawtext` ممكن يقطّع الحروف. العربي يتكتب بـASS أو Chromium أو higgsedit مع `fontFamily` صريح، والأفضل تنزيل Cairo وAmiri بـ`bootstrap.sh`.

## مؤثرات الريل (reel-effects): تصنيف من نص التعليمات (2026-11-11)
- **بلا كريدت:** `/captions`، `/tier-list`، `/grade-wipe`، `/glass-graph`، `/katana-file-scroll`، `/katana-ig-follow`، `/katana-reel-cards`، `/katana-cool-girl`.
- **خطوة مدفوعة واحدة (ماسك الشخص):** `/text-behind`، `/freeze-frame`، `/katana-bold`، `/over-the-shoulder`، `/katana-app-window`، `/katana-orbit`، `/katana-cool-dude` (الأخير بيشتغل من غير الماسك).
- كلها محتاجة مقطع متكلم، ولم تُجرَّب في القياس.

## Blender: إضافات الجولة التالتة
- كتالوج 3D Jutsu: 994 موديل (البحث مُقاس، الاستيراد لأ).
- رندر أنيميشن MP4 جوه Jutsu: 48 فريم 540×960 فضلت running أكتر من 7 دقايق من غير نتيجة: **غير مثبت**.
- `/use-blender`: Blender المحلي على جهازه عن طريق `fnf-blender-mcp@latest`، من Code → Local بس.
