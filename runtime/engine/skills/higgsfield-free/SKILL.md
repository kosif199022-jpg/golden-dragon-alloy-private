---
name: higgsfield-free
description: "هيجز فيلد ببلاش — استغلال كل الإمكانيات المجانية في Higgsfield من غير ما يتصرف كريدت: سحابة لينكس للرندر والترميز والتفريغ (sandbox_exec)، Blender مستضاف (3D Jutsu)، موشن بالكود (higgsedit)، كابشن وتلوين ومؤثرات ريل جاهزة، تحليل الترند وتفكيك أي ريل، ورفع وتسليم بلينك. فيه حصر مُقاس (28 بند: مجاني مُقاس / رسمي / خطوة مدفوعة / مدفوع)، وبوابة تمنع أي أداة بتصرف قبل الموافقة، وسكربتات جاهزة للصق في السحابة (تجهيز، رندر متوازي، فحص تسليم). Use whenever Higgsfield tools are connected and the user says «هيجز فيلد ببلاش»، «المجاني في هيجز فيلد»، «رندر على السحابة»، «وفّر الجهاز»، «من غير كريدت»، «استغل هيجز فيلد»، «سحابة مجانية»، free Higgsfield, cloud render, sandbox render, offload encoding, or before ANY Higgsfield tool call to check whether it spends credits. Also use it when a render, encode, transcription or batch job would tie up the PC and could run in the cloud instead."
---

# higgsfield-free — كل المجاني في Higgsfield، من غير صرف

المهارة دي بتجاوب على سؤالين: **إيه اللي ينفع يتعمل في Higgsfield من غير كريدت؟** و**إزاي أعمله صح؟**
«مجاني» هنا معناه **اتقاس**: الرصيد قبل وبعد متطابق ومفيش قيد في `transactions`. Higgsfield ممكن يغيّر ده في أي وقت، فالقياس بيتكرر في كل شغلانة.

```
S=~/.claude/skills/higgsfield-free
python -X utf8 $S/scripts/hf.py free                 # الحصر كله (28 بند) بحالة كل واحد
python -X utf8 $S/scripts/hf.py free ID              # بند واحد: الطريقة، الدليل، الحدود
python -X utf8 $S/scripts/hf.py free --status measured
python -X utf8 $S/scripts/hf.py check TOOL           # exit 0 = اتقاس مجاني · exit 3 = بيصرف أو مش معروف
python -X utf8 $S/scripts/hf.py ask TOOL --price N --balance B   # نص طلب الموافقة
python -X utf8 $S/scripts/hf.py paste JOB            # أمر واحد يتلصق في sandbox_exec: تجهيز + خطوط عربي + فحص + رندر متوازي
python -X utf8 $S/scripts/hf.py trend commands URL   # أمر يفكك أي ريل مرجع (قطعات، BPM، كلمات) في السحابة
python -X utf8 $S/scripts/hf.py blender rules        # قواعد Blender المستضاف (3D Jutsu) وقالب مشهد اشتغل
python -X utf8 $S/scripts/hf.py higgsedit            # قالب موشن بالكود مع قاعدة الخط العربي
python -X utf8 $S/scripts/hf.py workflows            # فهرس سير العمل الجاهز
```
الأوامر دي بتطبع بس: مابتتصلش بـ Higgsfield ومابتصرفش. اللي بينفّذ هو أدوات `mcp__claude_ai_Higgsfield__*` في المحادثة.

## القاعدة اللي مابتتكسرش
1. `balance` **قبل** أي شغل، و`balance` **بعده**، والرقمين في التقرير. لو الرصيد نقص: وقّف وقول فورًا.
2. قبل أي أداة مش متأكد منها: `hf.py check TOOL`. exit 3 معناه ممنوع تتنادى قبل ما المستخدم يوافق في الشات على **الأداة دي والسعر ده**، كل مرة.
3. المدفوع دايمًا: كل `generate_*`، و`upscale_*`، و`remove_background`، و`reframe`، و`outpaint_image`، و`motion_control`، و`dubbing`، و`voice_change`، و`create_voice`، و`execute_preset`، و`scene_builder_3d_generate_*`، وأوامر `*-hf` و`/gpu`.
4. غير المُقاس يتعامل كمدفوع: `video_analysis_create`، و`virality_predictor`، و`media_import_url`، والنشر (`publish_*`، `deploy_website`).
5. `use_unlim` و`use_free_gens` بطلب صريح من المستخدم بس. مفيش فتح تجربة أو اشتراك.
6. أي ملف بيترفع للسحابة بيخرج من الجهاز: ملفات المهمة بس، من غير مفاتيح ولا ملفات شخصية، وقول إيه اللي اترفع.

## إيه اللي مجاني (اتقاس) وبتستخدمه في إيه
| عايز | استخدم | ملاحظة |
|---|---|---|
| رندر وترميز تقيل، ومش عايز الجهاز يتعطّل | `sandbox_exec` | العادي معالج واحد و8 جيجا؛ `size:"xl"` 4 معالجات. من غير GPU |
| تفريغ صوت بتوقيت الكلمة | faster-whisper في السحابة | 50 ث صوت في 23 ث (small int8) |
| Blender من غير جهاز | 3D Jutsu المستضاف (`hf.py blender rules`)، أو Blender الرسمي في السحابة بمهارة **hf-blender-render** | Jutsu: مشهد + رندر EEVEE في 41 ث. رندر أنيميشن جوه Jutsu غير مثبت |
| موشن جرافيك بالكود | higgsedit (`hf.py higgsedit`)، أو HTML + Chromium (Playwright) | العربي لازم `fontFamily` فيه عربي + `direction:"rtl"` |
| كابشن كلمة بكلمة، تلوين سينمائي، مؤثرات ريل | سكربتات `$HF_WORKFLOWS` (video-montage، color-grade، reel-effects) | اقرا `get_workflow_instructions` الأول. الخطوات اللي بتنادي `generate_*` جواها مدفوعة |
| معرفة الترند وتفكيك ريل مرجع | `tiktok_music_trending`، `get_presets`، و`hf.py trend commands URL` | المرجع للتوقيت والطاقة والتكوين بس |
| سعر أي توليد من غير تنفيذ | `get_cost:true` أو `models_explore` | قراية بس |
| تسليم الناتج | `media_upload` ← `curl -X PUT` جوه نفس أمر السحابة ← `media_confirm` | اللينك هو التسليم |

التفاصيل والأدلة والحدود لكل بند: `references/FREE_MEASURED_2026-11-11.md`. الوصفة الكاملة ومواصفات السحابة والمواقع المفتوحة والمقفولة: `references/SANDBOX_RECIPE.md`.

## الوصفة (أي شغلانة رندر أو معالجة)
1. **الرصيد:** `balance`، واكتب الرقم. وابدأ بسطر: «⏱ التقدير ~N د · مفيش خصم متوقع».
2. **قرّر: سحابة ولا جهاز؟** السحابة تكسب لما الشغل تقيل على المعالج والملفات صغيرة أو بتتنزّل من النت. الجهاز يكسب لما فيه GPU مطلوب (demucs، whisperx، EEVEE)، أو الملفات كبيرة والنت بطيء (احسب وقت الرفع والتنزيل)، أو الشغل أقل من دقيقة.
3. **التجهيز:** `python -X utf8 $S/scripts/hf.py paste JOB`، والناتج يتلصق كما هو في `sandbox_exec`. بيعمل فولدر الشغلانة، وينزّل خطوط عربي (Amiri، Cairo، Tajawal، Reem Kufi…)، ويكتب `~/bdtools/qc.sh` و`prender.sh`.
4. **الخامات:** `curl` من لينك (ملف محلي: `media_upload` ← PUT ← `media_confirm` الأول). يوتيوب وتيك توك وإنستجرام مقفولين من السحابة: اطلب الملف من المستخدم، من غير تحايل.
5. **الشغل:** الأمر العادي أقصاه 120 ث. الأطول بـ `background:true` (أقصاه 15 د) وتابع ملف الـ log والـ status بأوامر قصيرة، من غير `nohup` ولا `&`. الشغل الأطول من 15 د يتقسّم مقاطع ويتكمّل.
   - فريمات HTML/SVG: `bash ~/bdtools/prender.sh 4 TOTAL -- <أمر بيقرا $RANGE>` على xl.
   - التصدير: `-c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p`، ولو الحجم كبير `-crf 19 -maxrate 14M -bufsize 28M`. الصوت AAC.
   - النص العربي: ASS أو Chromium أو higgsedit. `drawtext` بيقطّع الحروف.
6. **الفحص في السحابة:** `bash ~/bdtools/qc.sh FINAL.mp4 DURATION` لازم يطلع PASS (مقاس، فريمات، AAC، فك كامل، سواد، LUFS والذروة، وحجم أقل من 20 Mbps).
7. **بص بعينك:** contact sheet وارجعه بـ `image_paths` (4 صور بالكتير، 512 KB مع بعض).
8. **التسليم:** خد لينك الرفع بـ `media_upload` **قبل** الأمر، وحط الـ PUT في آخر نفس الأمر، وبعدين `media_confirm`. على اللابتوب نزّل الناتج لمجلد الشغل وقيسه تاني هناك.
9. **الرصيد تاني:** نفس الرقم؟ اكتب الرقمين. لو لأ: قول الفرق وإيه اللي صرف.

لو النتيجة فيها `sandbox_created:true` يبقى السحابة جديدة والملفات القديمة راحت: ارجع للخطوة 3.

## أرقام اتقاست
- 2026-11-11، السحابة العادية (معالج واحد، 8 جيجا، 382 جيجا مساحة): 10 ث فيديو 1080×1920 بـ slow/CRF17 في **8.7 ث**، 300 فريم، والرصيد 347.88 قبل وبعد.
- 2026-11-11، تجربة الوصفة من أولها: `hf.py paste` نزّل 12 خط، وريل 6 ث 1080×1920 بنص عربي (ASS + Amiri، الحروف متشكّلة صح بالعين) اترندر في **5.4 ث**، و`qc.sh` طلّع PASS (180/180 فريم، AAC، 0 سواد)، والرصيد 347.88 قبل وبعد. الرفع والتسليم ماتجربوش في التجربة دي.
- 2026-11-10: نفس اختبار 20 ث فيديو مليان noise: السحابة العادية 383 ث، وxl 147 ث. و732 فريم HTML بـ `prender.sh` على xl في 37 ث بدل حوالي 4 د.
- xl اتقاس يوم 11-10 بس. يوم 11-11 ماتفتحش، فاعتبر تكلفته ومواصفاته محتاجة تأكيد بـ `balance` قبل وبعد أول استخدام.
- الملفات في `/home/user` بتفضل 24 ساعة من آخر استخدام، وxl بيقفل بعد دقيقة من آخر شغل.

## مهارات بتكمّلها
- **hf-blender-render**: Blender الرسمي (Cycles) جوه السحابة بعمال متوازيين واستكمال بعد القطع. استخدمها لأي أنيميشن Blender طويل.
- **black-dragon**: قواعد صاحب الشغل وبوابة التسليم على الجهاز (`dragon verify`)، ونفس أوامر `hf.py` من `dragon.py tool hf`.
- **dragon-genius**: بوابة فحص الميديا لو عايز رأي تاني بعد التنزيل.

## التقرير
أول سطر النتيجة واللينك. وبعده: الرصيد قبل وبعد، إيه اللي اتنفّذ في السحابة وإيه على الجهاز، الأوقات المقاسة، نتيجة `qc.sh`، وإيه اللي اترفع من الجهاز. اللي اتقرا بس ماتقولش عليه اتنفّذ.
