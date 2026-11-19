# وصفات جاهزة: سحابة Higgsfield المجانية

كل وصفة بتبدأ بـ `balance` وبتخلص بيه، والفرق بيتسجّل بـ `hfc.py ledger add`.
`H` = `python -X utf8 "%USERPROFILE%\.claude\skills\higgsfield-cloud\scripts\hfc.py"`.

## 0. تجهيز الجلسة (مرة واحدة في كل جلسة)
1. `balance`، واكتب الرقم.
2. `H install-cmd`، والناتج يتلصق كما هو في `sandbox_exec` (أمر عادي، مش XL). بيتأكد من النسخة وبصمة sha256 وبيشغّل `doctor`.
3. لو هتكتب عربي على الشاشة (HTML أو ASS): `~/hfc/hfc fonts`. بتاخد حوالي 9 ثواني لـ 26 خط.
4. لو هتعمل ترميز تقيل: `~/hfc/hfc bench --quick` على نفس الحجم اللي هتستخدمه (5–8 ث). سرعة XL اختلفت حوالي مرتين بين جهازين في نفس اليوم، فابعت رقم A لـ `H plan ... --xl-a A` أو `H split ... --xl-a A`.
5. لو النتيجة فيها `sandbox_created:true`، يبقى الجهاز جديد: أعد الخطوة 2.

## 1. رندر أي حاجة بتاخد أكتر من 45 ثانية (القاعدة الذهبية)
```
sandbox_exec background:true  →  ~/hfc/hfc job run NAME -- <الأمر>
sandbox_exec (عادي، كل 30–60 ث)  →  ~/hfc/hfc job status NAME      # الحالة والنسبة والوقت المتبقي
```
- الأمر المباشر اللي بيطوّل حوالي دقيقة رجّع **502 من وسيط الاتصال** (اتقاس 2026-11-11). أي حاجة طويلة تتشغّل في الخلفية.
- طلب `size:"xl"` ممكن ينقل مساحة الشغل لجهاز جديد ويقتل العمليات الشغالة. **ماتطلبش XL وفيه مهمة شغالة**، واعمل `job status` الأول.
- حد المهمة الواحدة في الخلفية 15 دقيقة. الأطول منها يتقسّم أجزاء بـ `enc --start-frame/--frames`، وكل جزء مهمة لوحده، وبعدين `hfc concat`.

## 2. موشن جرافيك / تايتل عربي من HTML لفيديو (أقوى استخدام: مفيش رفع)
1. اكتب الصفحة محليًا (قالب: `cloud/examples/title_ar.html`). الحركة ممكن تبقى بطرق مختلفة، ودقتها مختلفة:
   - CSS animations/transitions أو Web Animations: **مظبوطة على الفريم**.
   - `requestAnimationFrame` و`performance.now()` على الساعة الوهمية الواقفة: دقتها ±16 مللي (أقل من نص فريم).
   - هوك `window.hfcRender = async (t, frame) => {}` لـ canvas وthree.js وGSAP: **مظبوط على الفريم**.
   - **كل الطبقات جوه `.stage{position:fixed;inset:0;overflow:hidden}`**. صفحة RTL فيها عنصر أعرض من الشاشة زحلقت الكادر كله (اتقاس).
   - الخطوط بالاسم بعد `hfc fonts`: Cairo، Tajawal، Almarai، Amiri، Noto Naskh/Kufi Arabic، El Messiri، Reem Kufi، Changa، Lalezar، Aref Ruqaa، IBM Plex Sans Arabic، Readex Pro، Scheherazade New.
2. توصيل الصفحة للسحابة: لو صغيرة (أقل من 100 كيلو) ممكن تتكتب بـ heredoc جوه `sandbox_exec` لأنها **نص بتكتبه أنت مش ملف بايتات بتنقله**. ولو فيها صور أو خطوط: `media_upload` بعدها `H put` بعدها `media_confirm`، وبعدين `hfc get URL` جوه السحابة.
3. `size:"xl"`، `background:true`: `~/hfc/hfc job run title -- ~/hfc/hfc html2mp4 page.html out.mp4 --w 1080 --h 1920 --fps 30 --dur 6 [--audio music.m4a]`
4. `~/hfc/hfc qc out.mp4 --w 1080 --h 1920 --fps 30 --dur 6 --no-audio`، وبعدين `~/hfc/hfc sheet out.mp4 -o s.jpg --n 6` و`image_paths:["s.jpg"]` عشان **تشوف بعينك**. البوابة عدّت فيديو فيه زحلقة وعداد غلط، والعين بس هي اللي كشفتهم.
   - السرعة المقاسة: 180 فريم 1080×1920 في 12 ث رندر + 5 ث ترميز على XL.
5. التسليم: `media_upload` **قبل** أمر الرندر، وفي آخر نفس الأمر `~/hfc/hfc put out.mp4 'UPLOAD_URL' video/mp4`، وبعدين `media_confirm`، وبعدين `H pull URL output\out.mp4 --sha256 <من put>`.

## 3. تفريغ كلام / قرآن / أغنية بتوقيت الكلمة
1. محليًا: استخرج الصوت صغير: `ffmpeg -i IN.mp4 -vn -ac 1 -ar 16000 -c:a libopus -b:a 32k a.ogg` (دقيقة = حوالي 240 كيلو، يعني رفع ثواني).
2. `media_upload a.ogg` بعدها `H put a.ogg URL --type <content_type من الرد>` بعدها `media_confirm type=audio`.
3. XL، background: `~/hfc/hfc job run stt -- bash -c "~/hfc/hfc get URL a.ogg && ~/hfc/hfc whisper a.ogg --lang ar --model large-v3 --out stt"`
4. النتيجة `stt/a.srt .vtt .txt .words.json`: نص صغير، اقراه بـ `cat` مباشرة من `sandbox_exec` واكتبه محليًا بأداة Write (ده نص ناتج مش نقل ملف ميديا).
5. اتأكد بعينك من 3 كلمات في 3 أماكن (`dragon-genius/scripts/transcript_qa.py`).

## 4. ترميز تقيل لفوتيج موجود أونلاين (لينك مباشر مسموح)
- الفوتيج على لينك؟ نزّله جوه السحابة (`hfc get`، بسرعة مركز البيانات)، ورمّزه على XL، ورجّع الناتج بس.
- الفوتيج على جهازك وحجمه كبير؟ **رمّزه محليًا**. الرفع من الجهاز ده اتقاس 0.87 ميجابايت/ث لملف 6 ميجا، وملف 77 ميجا اتقطع بعد 6 دقايق. احسب الأول: `H plan --task encode --in-mb 300 --video-sec 60`.
- مثال: `~/hfc/hfc job run enc -- ~/hfc/hfc enc in.mp4 out.mp4 --size 1080x1920 --preset slow --crf 18 --lufs -14 --maxrate 14M`

## 5. تقسيم رندر بين الجهاز والسحابة (هجين)
بيفيد بس لما المصدر موجود في المكانين من غير تكلفة (اتنزّل في الاتنين من لينك، أو اتعمل في السحابة واتنزّل).
1. `H split SRC --out parts --parts 8 --cloud-share auto --run-local --enc "--preset slow --crf 18"`: بيطبع أمر السحابة، وبيرمّز الأجزاء المحلية بنفس `enc.sh`.
2. شغّل أمر السحابة على XL في الخلفية، و`put` لكل جزء، و`H pull` لكل جزء في `parts\`.
3. `H join parts OUT.mp4`: بيلزق الأجزاء من غير إعادة ترميز، ويضيف صوت المصدر، ويتأكد إن عدد الفريمات مطابق ومفيش أخطاء فك.

## 6. صور ومواقع: سكرين شوت / PDF / فحص صفحة
- `~/hfc/hfc shot https://site out.png --w 1440 --h 900 --full`، أو `--mobile`، أو `out.pdf`.
- لاختبار موقع بتبنيه: `npm i` و`npm run build` جوه السحابة، وبعدين `npx serve` في الخلفية و`shot` على localhost.

## 7. تنزيلات تقيلة ومعالجتها هناك
- نت السحابة سريع وجهازك بطيء في الرفع: نزّل وقصّ واضغط هناك، ورجّع **الناتج الصغير بس**.
- yt-dlp متثبت، لكن يوتيوب وتيك توك وإنستجرام بيقفلوا الـ IP بتاع مراكز البيانات. **ماتزيّفش Referer ولا User-Agent** عشان تعدّي فحص البوتات. Pexels بيرجّع 403. أما Mixkit وarchive.org وGitHub وHugging Face فشغالين.

## 8. بايثون/Node نضيف ومعزول
- `~/hfc/hfc pip fonttools` بيثبّت في `~/pylib`. pip العادي بيقع بـ Permission denied '/root'، والسبب إن البيئة فيها `PYTHONPATH=/pkg/:/root/`. الأمر بيرجّع exit 1 لو فشل.
- `npm i` جوه فولدر شغال عادي. وPlaywright من Node بس (`NODE_PATH` بيتظبط تلقائيًا في `hfc`).

## 9. إنهاء الجلسة
`balance` ← `H ledger add BEFORE AFTER "وصف"`. لو الفرق سالب: **وقّف وبلّغ المستخدم**.
