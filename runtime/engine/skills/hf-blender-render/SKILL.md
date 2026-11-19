---
name: hf-blender-render
description: التنين الأسود — تجربة Blender على Higgsfield Sandbox بوضع تجريبي، رندر CPU مع الموافقة والقياس أولًا. بيثبّت Blender الرسمي للينكس في الـ sandbox، ويرندر الفريمات بـ Cycles على 4 أنوية بعمال متوازيين مع استكمال لو الشغل اتقطع، ويعمل الصوت بالكود، ويجمّع MP4 بمواصفات التنين (H.264 High CRF 17 BT.709، AAC 320k، ‎-14 LUFS)، ويشغّل بوابة التسليم (فريمات، مقاس، fps، سواد، فك كامل)، ويرجّع الفيلم للجهاز. فيه مشهد جاهز «فقس» (تنين كرتون بيفقس، 5 ث 9:16). Use for «رندر على هيجز فيلد»، «رندر بلندر في السحابة»، «هيجز فيلد ببلاش»، «اعمل الكرتون على السحابة»، «وفّر الجهاز»، cloud Blender render, render on Higgsfield sandbox, free cloud render, or when a Blender animation would tie up the PC for a long time.
---

## مراجعة KOSIF v1990.4 — تعليمات نافذة مقدمة على الخطوات التاريخية
- هذه نسخة **تجريبية**. لم يتم اختبار المشهد والحزمة المحدثة على Higgsfield أو Windows في هذه الجلسة.
- `tool hf-blender doctor|plan|pack|check-frames|source|policy` محلي ولا يتصل بالسحابة.
- `hf_bootstrap.sh` لا يحمل أو يثبت شيئًا تلقائيًا؛ يتطلب `HF_BLENDER_ALLOW_DOWNLOAD=YES` بعد موافقة المستخدم، ولا يحاول apt أو pip.
- `hf_finish.sh` يرجع خطأ (exit 1) عند `GATE_FAIL` ويجب فحص الفيديو بعين بشرية.
- `pack.py` يقبل اسم مهمة مأمونًا وملفات Python عادية فقط ويمنع الكتابة فوق ملف موجود افتراضيًا. لا ترسل الناتج إلى Sandbox قبل مراجعته.
- **الملف الأصلي يحتوي على تقديرات تاريخية فقط**: XL 4 vCPU / الأداء / مجانية الكريدت كلها ليست مواصفات مضمونة للحساب الحالي.
- Blender Cycles CPU افتراضي للتجارب. عدم وجود GPU مؤكد لجلسة Standard السابقة فقط؛ لا تعمم على XL دون قياس.
- ملف `hatch_scene.py` عُدّل لاستخدام materials/world nodes صراحة وأُضيف توافق جزئي لاختلاف motion blur؛ يجب اختبار نسخة Blender المطلوبة قبل الرندر الثقيل.

---

# hf-blender-render — Blender على Higgsfield Sandbox (Pilot فقط)

⚠️ **المجانية غير مضمونة:** سجل جلسات سابق لم يُظهر خصمًا، لكنه ليس توثيقًا رسميًا أو تعهدًا بأن XL أو التحميل أو رفع الملفات مجاني. لا تشغّل جلسة XL أو تثبّت Blender أو ترفع ملفات دون إذن واضح. الأدوات المسموحة في خطة التجربة فقط: `sandbox_exec` و`balance` و`media_upload` و`media_confirm`. أي أداة `generate_*` أو `upscale_*` ممنوعة من غير موافقة صريحة على السعر.

```
S=~/.claude/skills/hf-blender-render
scripts/pack.py          # على الجهاز: بيحوّل السكربتات والمشهد لأمر bash واحد يتلصق في sandbox_exec
scripts/hf_bootstrap.sh  # في السحابة: بينزّل Blender 5.2.3 Linux (وفيه نسخ احتياطية لو الأولى مش موجودة)، ومتكيّش 24 ساعة
scripts/hf_render.sh     # في السحابة: رندر متوازي ببداية ونهاية لكل عامل، وبيكمّل لوحده بعد أي قطع
scripts/hf_finish.sh     # في السحابة: الترميز + الصوت + بوابة التسليم + ورقة QC
scenes/hatch_scene.py    # مشهد «فقس» مستقل، مش محتاج أي مكتبة
scenes/hatch_sound.py    # مزيكا ومؤثرات بالكود (numpy)، 5.000 ث
```

## عقد المشهد (أي مشهد جديد لازم يمشي عليه)
السكربت بيقرا متغيرات البيئة دي: `OUT_DIR`، و`MODE=stills|one|anim`، و`ENGINE=EEVEE|CYCLES`، و`SAMPLES`، و`RES_PCT`، و`F0`/`F1` (مدى الفريمات)، و`FRAME` (للوضع `one`).
- في وضع `anim` لازم يكتب `OUT_DIR/frames/f_####.png` ومعاه `use_overwrite=False` و`use_placeholder=True`.
- **ممنوع يستورد bpylib أو أي مكتبة من الجهاز.** الـ sandbox فيه Blender وبايثون بتاعه بس.
- العربي في Blender قد يحتاج تشكيلًا مسبقًا عبر `arabic_reshaper` و`python-bidi`، أو تحويل النص إلى رسومات. لا تُثبّت أي مكتبة جديدة داخل Sandbox قبل إذن المستخدم وفحص التكلفة.
- مشهد معمول بمهارة blender-pro يتحوّل بنفس طريقة «فقس»: الـ compositor اتكتب جوه المشهد، واختيار الـ engine بقى من متغيرات البيئة.

## الخطوات (بالترتيب، ومن غير ما تتخطّى الفحص)
0. **الرصيد والتكلفة:** `balance` قبل الشغل وبعده، واسأل عن تكلفة XL رسميًا. لا تؤكد عدم الخصم قبل قياسه، ولا تفتح XL إلا بموافقة صريحة. السطر بالشكل ده: «⏱ التقدير ~N د · الانتهاء نحو HH:MM».
1. **التجميع على الجهاز:**
   `python -X utf8 $S/scripts/pack.py JOB $S/scenes/hatch_scene.py $S/scenes/hatch_sound.py --out cmd.sh`
   الأمر حوالي 18 KB. اقرا `cmd.sh` وابعته كما هو في `sandbox_exec` (`size:"xl"`) لحد ما يطلع `PACK_OK`.
2. **Blender:** بعد الموافقة الصريحة على تنزيل النسخة الرسمية: `HF_BLENDER_ALLOW_DOWNLOAD=YES bash /home/user/bdtools/hf_bootstrap.sh` بـ `size:"xl"` و`background:true` (التحميل حوالي 350 MB). تابع الـ log لحد ما يطلع `BLENDER_READY`. لو طلع `BLENDER_FAILED` شوف الـ log، ولو الإصدار مش موجود جرّب إصدار تاني كأول معامل.
3. **فريم تجربة الأول (إجباري):**
   `cd /home/user/jobs/JOB && OUT_DIR=$PWD/test MODE=one ENGINE=CYCLES SAMPLES=24 FRAME=118 /home/user/bd_blender/current/blender -b --factory-startup --python in/hatch_scene.py -t 4`
   اقيس الوقت (`/usr/bin/time` أو `date`)، وارجع الـ PNG للجهاز واتفرج عليه بـ Read. ولو `sandbox_created:true` ظهر في أي خطوة، يبقى الجهاز اتغيّر ولازم ترجع للخطوة 1.
4. **الرندر:** `bash /home/user/bdtools/hf_render.sh /home/user/jobs/JOB /home/user/jobs/JOB/in/hatch_scene.py 150 2 CYCLES 24 100 > /home/user/jobs/JOB/render.log 2>&1` بـ `background:true` و`size:"xl"`.
   - **الحد 15 دقيقة لكل تشغيل في الخلفية بحسب قياس سابق.** لو `status` طلع `RUNNING` لسه أو `PARTIAL`، شغّل نفس الأمر تاني: بيمسح الفريمات الفاضية والمقطوعة ويكمّل من مكانه (اتجرّب).
   - التقدم: `ls /home/user/jobs/JOB/frames | wc -l` و`cat status`، بأوامر قصيرة كل كام دقيقة (من غير sleep طويل).
   - الافتراضي عاملين بـ 2 thread لكل واحد، عشان تجهيز المشهد يتعمل بالتوازي. ده افتراض لسه ماتقاسش على السحابة: قارنه بعامل واحد بـ 4 في أول تشغيل. ولو المشهد تقيل في الذاكرة استخدم عامل واحد.
5. **التجميع والفحص:** `bash /home/user/bdtools/hf_finish.sh /home/user/jobs/JOB hatch.mp4 5 /home/user/jobs/JOB/in/hatch_sound.py 1080x1920`. لازم `GATE_PASS`.
   `GATE_FAIL` معناه مفيش تسليم: صلّح السبب وأعد الخطوة. تقدر تمسح فريمات بعينها وتشغّل الخطوة 4 تاني.
6. **الرجوع للجهاز:** `media_upload` الأول (خد `upload_url`)، وبعدين في أمر واحد:
   `curl -f -X PUT --upload-file hatch.mp4 '<upload_url>' && echo UP_OK`، وبعده `media_confirm`.
   نزّل الرابط لمجلد الشغل، واعمل نفس الحاجة لـ `qc_sheet.jpg`.
7. **التحقق على الجهاز:** `python -m dragon verify FILE --expect 1080x1920` من مجلد التنين، وRead لورقة QC. `balance` تاني؛ سجّل أي اختلاف دون افتراض أنه صفر.

## الأرقام اللي اتقاست (2026-11-11)
- على الجهاز (Core 5 120U): EEVEE بـ 32 عينة حوالي 18 ث للفريم 1080×1920، والفيلم كله (150 فريم) خد حوالي 45 د.
  Cycles بـ 8 عينات و15٪: 6 فريمات بعاملين في 34 ث.
  **Cycles بـ 24 عينة وبالمقاس الكامل 1080×1920 (مع denoise): 82 ث للفريم على الجهاز، منهم حوالي 10 ث تجهيز.** الجودة مطابقة لـ EEVEE واتشافت بالعين.
- التقدير لسحابة xl (محسوب، ماتقاسش): 30 إلى 37 ث للفريم، يعني 150 فريم في حوالي 75 إلى 90 د، وده 6 لـ 7 تشغيلات بحد الـ 15 دقيقة.
  ده **أبطأ من EEVEE على الجهاز (45 د)**، بس الجهاز بيفضل فاضي. لو السرعة أهم: جرّب `SAMPLES=12` أو `RES_PCT=67` واكبّر بعدها، أو قسّم الشغل: جزء من الفريمات في السحابة والباقي على الجهاز، **بنفس الـ engine ونفس عدد العينات** (لو خلطت EEVEE مع Cycles الشكل هيقفز في النص). استخدم `F0`/`F1` على الجهاز، وانسخ الفريمات لـ `frames/` قبل `hf_finish`.
- سحابة xl: 4 أنوية، وأسرع من الجهاز 2.2 إلى 2.7 مرة في المعالج. **مفيش GPU**، فـ EEVEE ممكن مايشتغلش (محتاج OpenGL/Vulkan). عشان كده Cycles على المعالج هو الافتراضي هنا، وEEVEE يتجرّب بالخطوة 3 بس.
- ⚠️ لحد كتابة الملف ده، السكربتات **اتجرّبت على الجهاز بس** (bash وBlender 5.2.3 وffmpeg). أول تشغيل حقيقي على Higgsfield: سجّل الأرقام هنا (وقت الـ bootstrap، وثواني الفريم على xl، وعدد مرات الـ 15 دقيقة) وصحّح أي حاجة اختلفت.

## قواعد
- كل ملف بيترفع بيخرج من الجهاز: ابعت سكربتات المهمة بس، ومن غير مفاتيح.
- ماتقولش «خلص» قبل `GATE_PASS` في السحابة و`verify` على الجهاز.
- مفيش كتابة على الفيديو غير اللي المستخدم طلبه (قاعدة التنين).
