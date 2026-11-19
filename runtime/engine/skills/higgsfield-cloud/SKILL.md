---
name: higgsfield-cloud
description: سحابة هيجز المجانية — بتشغّل جهاز لينكس Higgsfield المجاني (sandbox_exec عادي وXL) كمزرعة رندر وتفريغ وتصفّح جنب ويندوز من غير كريدت. عدة بتتثبت بأمر واحد بتحقق sha256: مهام خلفية بحالة ونسبة، ترميز بأجزاء فريم-بفريم، HTML متحرك لفيديو حتمي على Chromium (تايتلات عربي)، تفريغ whisper large-v3، سكرين شوت وPDF، 26 خط عربي، بوابة جودة، لوحة فريمات. وعقل محلي (scripts/hfc.py) بيقرر سحابة ولا جهاز بأرقام مقاسة، ويرفع وينزّل بـ curl بالهيدرات الموقّعة، ويقسّم الرندر بين الجهاز والسحابة، ويمسك دفتر الرصيد. Use for «استغل هيجز فيلد ببلاش»، «رندر على السحابة»، «السحابة المجانية»، «sandbox»، «XL»، «فرّغ على السحابة»، «حوّل HTML لفيديو»، «تايتل عربي متحرك»، «سكرين شوت لموقع»، «نزّل وعالج على السحابة»، or heavy CPU jobs that fit the free sandbox. Never paid Higgsfield generation without the owner's explicit yes and price.
---

# سحابة هيجز المجانية (higgsfield-cloud)

**الفكرة:** حساب Higgsfield بتاع المستخدم فيه جهاز لينكس سحابي **ببلاش** (`sandbox_exec`). XL فيه 4 أنوية و16 جيجا. المهارة دي بتحوّله لمزرعة شغل منضبطة: بتثبّت أدواتها بأمر واحد، وتشغّل الشغل الطويل في الخلفية، وتقيس، وترجّع الناتج متحقق منه، وتحسب قبل أي حاجة هل السحابة أسرع فعلًا ولا الجهاز.

كل رقم هنا اتقاس يوم **2026-11-11**. التفاصيل والأوامر في `references/MEASURED_2026-11-11.md`، وكل الأرقام في `data/measured.json` (`hfc.py facts`).

## القواعد اللي ماتتكسرش
1. **المجاني بس.** قبل أي أداة Higgsfield غير `sandbox_exec` والرفع والقراية: `hfc.py check TOOL`. لو رجّع exit 3 (مدفوع أو مش معروف)، **ماتشغّلهاش** غير بموافقة صريحة من المستخدم في الشات بالأداة والسعر.
2. **`balance` قبل وبعد** أي شغل كبير، والفرق يتسجّل: `hfc.py ledger add BEFORE AFTER "note"`. لو الرصيد نقص: وقّف فورًا وبلّغ.
3. **الخصوصية:** أي ملف بيترفع بيخرج من جهاز المستخدم وبياخد لينك CloudFront دايم. ارفع ملفات المهمة بس. مفيش مفاتيح ولا باسوردات ولا ملفات شخصية. وقول للمستخدم إيه اللي اترفع.
4. **الملفات بتتنقل بـ PUT موقّع من مكانها،** مش كنص base64 جوه الأوامر (ده شرط Higgsfield نفسه). أي نص بتكتبه أنت (HTML، سكربت، JSON صغير) عادي يتكتب بـ heredoc.
5. **أي أمر ممكن يعدّي 45 ثانية يتشغّل `background:true`** تحت `~/hfc/hfc job run NAME --`. الأمر المباشر اللي طوّل حوالي دقيقة رجّع 502.
6. **ماتطلبش `size:"xl"` وفيه مهمة شغالة.** طلب XL ممكن ينقل مساحة الشغل لجهاز جديد ويقتل العمليات. اعمل `job status` الأول.
7. **ماتعلنش إن حاجة خلصت** غير بعد `hfc qc` (exit 0)، و`hfc sheet` + `image_paths` (تشوفها بعينك)، و`hfc.py pull --sha256` (البصمة مطابقة على الجهاز).

## إمتى السحابة وإمتى الجهاز (اتقاس)
| الشغل | الأحسن | ليه |
|---|---|---|
| موشن/تايتل من HTML، تفريغ صوت، سكرين شوت، تنزيل ومعالجة، بناء مشروع ويب، اختبار كود في بيئة نضيفة | **السحابة** | المدخلات صغيرة (نص أو صوت مضغوط أو لينك)، والراجع ناتج بس |
| ترميز فوتيج **موجود على جهازك** وحجمه كبير | **الجهاز** | الرفع من الجهاز ده 0.87 ميجابايت/ث لملف 6 ميجا، وملف 77 ميجا اتقطع بعد 6 دقايق |
| ترميز فوتيج موجود **أونلاين** أو اتعمل في السحابة | **السحابة XL** | نت مركز بيانات، والتنزيل عندك 4.85 ميجابايت/ث. **سرعة XL بتختلف حوالي مرتين حسب الجهاز** (اتقاس أبطأ من جهازك مرة وأسرع منه 1.5 مرة مرة تانية)، فاقيس بـ `hfc bench --quick` الأول |
| رندر 3D بـ Blender، موديلات GPU (rembg تقيل، upscale AI، SD) | **الجهاز** | السحابة مفيهاش GPU ولا Blender |
احسبها بدل ما تخمّن: `hfc.py plan --task encode|whisper|html|download ...`

## البداية (كل جلسة)
```
H = python -X utf8 "%USERPROFILE%\.claude\skills\higgsfield-cloud\scripts\hfc.py"
1) balance                                   ← اكتب الرقم
2) H install-cmd   → الناتج يتلصق في sandbox_exec (عادي): بيثبّت ~/hfc لو مش موجود، ويتأكد من sha256، ويشغّل doctor
3) ~/hfc/hfc fonts                           ← لو فيه عربي على الشاشة (26 خط في ~9 ث)
4) ~/hfc/hfc bench --quick                   ← قبل أي ترميز تقيل (سرعة XL بتختلف حوالي مرتين) ثم hfc.py plan --xl-a A
```
لو العدة اتغيّرت (`cloud/`): `H pack`، وبعدين `media_upload` (اسم الملف `hfc-cloud-VER.tar.gz`)، وبعدين `H put FILE URL --type application/octet-stream`، وبعدين `media_confirm type=file`، وبعدين `H set-url URL`.

## الأوامر جوه السحابة (`~/hfc/hfc ...`)
| الأمر | بيعمل إيه |
|---|---|
| `doctor [--json]` | الحجم الحالي (standard/xl)، والأدوات، والموديلات، والخطوط، والمهام |
| `job run NAME -- CMD` / `job status [NAME]` / `job tail NAME` / `job stop NAME` | مهام بحالة ونسبة ووقت متبقي، بتتشغّل بـ `background:true` |
| `enc IN OUT [--size WxH --preset --crf --lufs -14 --maxrate 14M --vcodec libx265 ...]` | ترميز احترافي بـ faststart، وبيكتب التقدم لـ `job status` |
| `enc ... --start-frame A --frames N` + `concat OUT P1 P2.. --audio-from SRC` | أجزاء فريم-بفريم ولزقها من غير إعادة ترميز (للشغل اللي أطول من 15 د، وللهجين) |
| `html2mp4 PAGE OUT --w --h --fps --dur [--workers] [--audio]` | صفحة متحركة لفيديو، حتمي فريم بفريم، وعلى التوازي |
| `whisper IN --lang ar --model large-v3 --out DIR` | ‎.srt ‎.vtt ‎.txt ‎.words.json بتوقيت الكلمة |
| `shot URL OUT.png|.pdf [--w --h --full --mobile --selector]` | سكرين شوت أو PDF |
| `qc FILE [--w --h --fps --dur --lufs --tp --no-audio]` | بوابة الجودة لأي مقاس (exit 0 = عدّى) |
| `sheet IN -o s.jpg --n 6` | لوحة فريمات ≤480 كيلو تتشاف بـ `image_paths` |
| `get URL OUT` / `put FILE 'UPLOAD_URL' [content-type]` | نقل الملفات (بالهيدرات الموقّعة) |
| `fonts` / `pip PKG` / `bench [--quick]` | خطوط عربي، باكدجات بايثون في `~/pylib`، قياس السرعة (السريع حوالي 5 ث، **في أول كل جلسة تقيلة**) |

## التسليم من السحابة لجهازك (الترتيب مهم)
1. `media_upload` بالاسم **قبل** أمر الرندر، وخد `upload_url` و`url` و`content_type`.
2. في آخر **نفس** أمر الرندر: `~/hfc/hfc put out.mp4 'UPLOAD_URL' video/mp4`. ده بيطبع http=200 وبصمة sha256.
3. `media_confirm` (النوع video أو image أو audio أو file).
4. على الجهاز: `H pull URL "WORKDIR\output\out.mp4" --sha256 <البصمة>`، وبعدين `hfc qc` محليًا (نفس السكربت شغال على ويندوز: `python cloud\qc.py`).

## الوصفات
`references/RECIPES.md`: موشن عربي من HTML، وتفريغ قرآن أو كلام، وترميز فوتيج أونلاين، وهجين جهاز + سحابة، ومواقع، وتنزيلات، وبيئة بايثون/Node نضيفة.

## مشاكل اتقاست وحلها
- رفع من ويندوز بـ Python urllib بيرجّع **403 «error code: 1010»** (Cloudflare بيرفض توقيع المكتبة). `hfc.py put` بيستخدم `curl.exe` زي ما Higgsfield طالب.
- اللينك الموقّع بيشمل `content-type` و`if-none-match`: لازم `Content-Type` يطابق اللي رجع من `media_upload` (الملفات العامة بترجع `application/octet-stream`)، ومعاه `If-None-Match: *`.
- `pip install` بيقع (Permission denied '/root'). الحل: `hfc pip PKG`.
- `drawtext` في ffmpeg 5.1 هناك مبني من غير harfbuzz، فالعربي ممكن يتقطّع. العربي يتكتب بـ HTML (`html2mp4`) أو ASS (libass + fribidi) بعد `hfc fonts`.
- Playwright متثبت لـ Node بس، مش بايثون (`hfc` بيظبط `NODE_PATH`).
- Pexels بيرجّع 403، ويوتيوب وتيك توك بيقفلوا مراكز البيانات. ممنوع تزييف Referer أو User-Agent.
- السحابة فيها `PYTHONPATH=/pkg/:/root/` و`/root` ممنوع، فـ pip بيقع. `hfc pip` بيفضّي المسار، و`hfc` بيشيل `/root` من أوامره.
- `page.clock.install()` لوحده بيسيب الوقت ماشي. `html2mp4` بيوقّف الساعة بـ `pauseAt` قبل التحميل، وبيمشيها بمللي ثانية صحيحة، فالرندر بقى حتمي وأسرع 4 مرات.
- صفحة RTL فيها عنصر أعرض من الشاشة بتزحلق الكادر كله. حط كل حاجة جوه `.stage{position:fixed;inset:0;overflow:hidden}` (القالب `cloud/examples/title_ar.html`).
- **بوابة الجودة قالت PASS على فيديو فيه مشكلتين ماتشافوش غير بالعين.** `sheet` + `image_paths` إجباري.
- رقم `sandbox_id` بيتغيّر من غير ما الملفات تضيع. `sandbox_created:true` بس هو اللي معناه إن الجهاز اتمسح.

## المهارات اللي بتشتغل معاها
`dragon-genius` (بوابة التسليم media_gate وtranscript_qa)، و`black-dragon` (محركات المونتاج، وفهرس Workflows بتاعة Higgsfield في `tools/hf_sandbox`)، و`webapp-testing` (أنماط Playwright)، و`windows-commands` (أوامر ويندوز الآمنة).
