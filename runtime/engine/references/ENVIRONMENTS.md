# الأماكن اللي المهارة بتشتغل فيها

اقرا ده امتى: أول أمر في أي محادثة (`$D where`)، وقبل أي رندر أو تحميل أو رفع أو شغل طويل، ولما أداة ترفض أو تقع.

`$D` = `python3 <skill>/scripts/dragon.py` (على ويندوز `python`). كل قاعدة عليها مكانها: «سحابة» (claude.ai أو Claude Code سحابة) أو «في كل مكان».

## 1. الأماكن التلاتة
ثقة متوسطة: اتأكد معاه أول مرة إن الجدول ده مطابق لجهازه.

| | claude.ai (شات) | Claude Code سحابة | جهازه (ويندوز) |
|---|---|---|---|
| تعرفه إزاي | فيه `/mnt/user-data`، ومفيش `CLAUDE_CODE_REMOTE` ولا مستودع | `CLAUDE_CODE_REMOTE=true`، ونسخة kosif-tool في أعلى مستودع git | `where` بيقول `"os": "Windows"` و`mode: pc` |
| ملفاته جاية منين | `/mnt/user-data/uploads` | `/root/.claude/uploads/<session>/` + صفحة الرفع (مهارة kosif-upload-link في kosif-tool) | على الجهاز نفسه، مفيش رفع |
| التسليم | `/mnt/user-data/outputs` | `SendUserFile` (نسخة الموبايل) + لينك خاص من Higgsfield (قسم 8) | مسار الملف على جهازه |
| الاستنا | أوامر قصيرة، مفيش Monitor | `job.py` + Monitor أو `run_in_background` (قسم 6) | `job.py` لو kosif-tool موجود |
| الهارد | مش متقاس | ضيق: 0.15–3 GB فاضي (قسم 2) | كبير، بس الفريمات بالجيجات |
| المستودعات | مفيش | kosif-tool | `Desktop\التنين الأسود` أو `~/kosif-own/black-dragon` + kosif-tool وBlender وGPU لو موجودين |

- **[سحابة] جوه Claude Code:** `$D where` بيقول `mode: cloud` و`outputs: /mnt/user-data/outputs`، والفولدر ده كان فيه 0 ملف بعد أسبوعين. يعني ماتسلّمش هناك: سلّم بـ `SendUserFile` واللينك. ونفس `where` بيقول `kosif-tool: false` لأنه بيدور في `~/kosif-own` بس، مع إن kosif-tool موجود (`git rev-parse --show-toplevel`). مود خاص بـ Claude Code تذكرة في ROADMAP.md.
- **[سحابة] الحاجات التقيلة:** مفيش Blender ولا GPU. يوتيوب وتيك توك كتير بيقفلوا التحميل من السيرفر: قوله على طول واطلب الملف أو حمّل من جهازه (SOURCES.md).
- **[في كل مكان] على جهازه:**
  - `python` مش `python3`.
  - فولدر شغل بأسامي إنجليزي (ASCII) برّه OneDrive، لأن الفريمات بالجيجات. الافتراضي `~/bdc_work`، ويتغير بـ `BDC_WORK`.
  - المسارات العربي بين علامتين تنصيص.
  - تعبيرات `select` في ffmpeg قصيرة: `patch-black` بيرفض أكتر من 1000 run (`MAX_RUNS`) عشان حد طول سطر الأوامر في ويندوز.
  - التثبيت بس بسطور `winget` اللي بيطبعها `$D setup`، وبعد «أثبّت؟» وموافقته.
  - الخطوط جوه الصفحة base64 (`$D tool styles SPEC.json --out DIR --embed-fonts`)، لأن Chromium بيمنع `FontFace` من `file://`.
  - التحميل بكوكيز المتصفح اللي هو داخل بيه (`yt-dlp --cookies-from-browser chrome URL`، أو `edge`).

### DRAGON_HOME و`/tmp/dragon`
- **[في كل مكان]** في السحابة اللانشر بينسخ `app/` لـ `/tmp/dragon` ويشغّل من هناك. في v1.2 بيكتب بصمة (`.bundle_stamp` من أسامي الملفات وأحجامها وتواريخها) وبينسخ تاني لما `app/` يتغير، والكتالوج اللي اتبنى جوه النسخة بيفضل. نسخة v1.1 مالهاش بصمة، فبتتنسخ من جديد.
- **[في كل مكان]** للاختبارات، أو لو `where` قال `engine_version` غير `bundled_version`، أو طلع سطر `could not refresh the engine copy`: شغّل الكود الحي على طول:
```bash
export DRAGON_HOME=<skill>/app      # على ويندوز: set DRAGON_HOME=<skill>\app
$D where                            # engine_version لازم = bundled_version
```
- **[في كل مكان]** على جهازه، المستودع المحلي (`Desktop\التنين الأسود` أو `~/kosif-own/black-dragon`) بيتشغّل زي ما هو. لو أقدم من المهارة بيطلع سطر `note: … has dragon …`: انسخ `app/` فوقه، أو `DRAGON_MODE=cloud` يشغّل النسخة المدمجة.
- **[سحابة]** Playwright هنا متثبت global: `export KOSIF_ROOT=/opt/node22/lib` قبل `render.cjs`.

## 2. الهارد في السحابة
- **[سحابة]** افترض إن الفاضي 0.15–3 GB بس. الديسك 252G والمسموح ~39G، و`/tmp` على نفس الديسك. في 2026-11-08 كان الفاضي 618–628 MB، ووقت المناظرة (247 حتة) نزل لـ 72 MB.
- **[سحابة]** قبل أي رندر أو تحميل: `df -h / | tail -1` و`du -sh <job>/film/f1 <job>/chunks`، واحسب:

| الحاجة | بتاخد قد إيه |
|---|---|
| رندر قديم بفريمات PNG مؤقتة | ~3.4–3.6 MB للفريم (~100 MB لكل ثانية فيلم): حتة 4 ث ~310–400 MB للعامل، حتة 10 ث ~1.1 GB |
| فولدر فريمات JPEG من المصدر | ~1.3–1.5 MB لكل ثانية فيلم (467 MB لـ 310 ث) |
| لقطات ستوك أصلية | ~0.5 GB لكل 12 كليب |
| `render.cjs` المدمج | صفر فريمات مؤقتة: بيبعت الفريمات لـ ffmpeg على طول. فريمات المصدر بس اللي بتتحسب |

- **[سحابة]** ابدأ بس لو الفاضي ≥ عدد العمال × مؤقت الحتة + الفريمات + 1 GB، وخلي ≥ 3 GB فاضيين طول ما العمال شغالين. غير كده امسح الحاجات الوسيطة بتاعة أفلام اتسلمت الأول (قسم 3).
- **[سحابة] الأفلام الطويلة (أكتر من ~5 د):** طلّع فريمات المصدر وقت الحاجة لكل حتة (301 فريم لكل 10 ث) وامسح فولدر الكليب بعد حتته. مثال المناظرة: `clip.sh K` بـ `crop=1392:1080:264:0,scale=1044:810`.
- ليه: «No space left on device» و«Unable to capture screenshot» والحتة 66 البايظة ظهروا في 12 من 16 ملخص.

## 3. TMPDIR لكل شغلانة، والمسح بمسارات صريحة
- **[في كل مكان]** كل رندر ليه TMPDIR جوه الشغلانة، ومتغيرات المسح محمية بـ `${VAR:?}`:
```bash
RT="${J:?}/rt"; rm -rf "$RT"; mkdir -p "$RT"
TMPDIR="$RT" node "$S/app/engines/render/render.cjs" --in film.html --out film.mp4 --duration D --strict
rm -rf "${RT:?}"
```
- **[في كل مكان]** ممنوع المسح بـ wildcard في الأماكن المشتركة (`/tmp/kosif-frames-*`، `/root/.cache/huggingface`، مؤقت شغلانات تانية). ممنوع `pkill -9 chrome` مع `rm` في نفس الأمر. ممنوع `rm` بمتغير مش محمي.
- **[في كل مكان]** بعد ما `media_confirm` ينجح بس: امسح الحاجات الوسيطة اللي تتعمل تاني بتاعة الفيلم ده، بمسار كامل صريح: `film/f1`، `chunks/`، `st*_stills/`، `v.mp4` و`v2.mp4`، `rt/`، أصول الستوك اللي اتحولت.
- **[في كل مكان]** ماتمسحش أبدًا: النهائي بتاع شغلانات قديمة، فريمات شغلانة تانية بتستخدمها (مسارات `EXT:` أو symlinks)، كاش الموديلات. افحص الأول:
```bash
find /home/user/kosif-tool/out -maxdepth 4 -type l -printf '%l\n' | grep <job>
grep -l 'EXT:' out/*/build.py out/*/*_lib.py
```
- ليه: 8 رفضات وقت امتلاء الهارد وقّفت التنضيف (`[Shared Scratch Sweep]` ×4، فحص أمان `rm` ×3، `[Irreversible Local Destruction]` ×1). وفولدرات `20261106-short/film/f1` كانت لسه مستخدمة في التريو يوم 11-08.

## 4. رندر تقيل واحد في المرة
- **[في كل مكان]** رندر تقيل واحد على الجهاز، من طابور: كل سكربت أول سطر فيه بيستنى اللي قبله.
```bash
python3 tools/job.py start --dir /abs/out/J/seqjob2 -- bash seq_B.sh
# وأول سطر جوه seq_B.sh بيستنى الشغلانة اللي قبله:
python3 tools/job.py wait --dir /abs/out/J/seqjob1 --quiet
```
  مثال: `seq_all.sh` شغّل `seq_fix40` ← `seq_qalb2` ← `seq_aj2` ورا بعض.
- **[سحابة]** ماتشغّلش رندر مع whisper ولا مع رندر تاني على صندوق الـ 4 CPU.
- **[في كل مكان]** عامل تاني بس لفيلم واحد طويل جدًا: TMPDIR لوحده، حتت منفصلة (الحتة k للعامل w لو k mod N = w)، فريمات وقت الحاجة، و≥ 3 GB فاضي.
- ليه: رندرين مع بعض ملوا `/tmp`، و4 عمال × ~1.1 GB ملوا الهارد، والرندرات مع كاش صور كبير طلّعت فريمات سودا.

## 5. شغل يكمل بعد الوقوع (عقد العامل)
- **[في كل مكان]** كل عامل:
  - بيتخطى الناتج اللي موجود وعدّى الفحص.
  - بيكتب لاسم `.tmp` وبيعمل `mv` لو نجح بس.
  - بيجرب الحتة مرتين بالكتير.
  - بيكتب سطر لكل حتة فيه `STEP` أو `FAIL`، والفشل كمان في `logs/fail.txt`.
- **[في كل مكان]** المجمّع مايشتغلش غير لما العدد = الخطة.
```bash
chunk() {   # $1 = رقم الحتة؛ render_piece بتاعة الشغلانة نفسها
  f="$J/chunks/c$(printf %03d "$1").mp4"; t="${f%.mp4}.tmp.mp4"
  for try in 1 2; do
    [ -s "$f" ] && return 0
    if render_piece "$1" "$t"; then mv "$t" "$f"; echo "STEP chunk $1"; return 0; fi
    echo "FAIL chunk $1 try $try" | tee -a "$J/logs/fail.txt"; rm -f "$t"
  done
}
```
- **[في كل مكان]** التفريغ الطويل حتت ≤ 10 د: `$D words long.wav --lang ar --model medium --offset 0 --duration 600 --out w0.json` وبعدها `--offset 600`.
- **[سحابة] بعد ريستارت:** `job.py status`، قارن العدد بالخطة، وشغّل نفس الطابور تاني. ماتبدأش نسخة تانية وفيه عملية لسه شغالة (`job.py start` بيطبع `ALREADY_RUNNING`). عاملين عمرهم ما يشتغلوا على نفس الحتة (حتت منفصلة أو أسامي مؤقتة مختلفة زي `.t` و`.u`).
- **[في كل مكان] حجم الحتة:** 10 ث بس لو فيه ≥ 1.1 GB مؤقت لكل عامل (الرندر القديم)، 4–5 ث لو الهارد ضيق، و2 ث (1 ث في الإعادة) للصفحات اللي كلها صور.
- ليه: «job process is gone and left no exit code (killed?)» 3 مرات، والتفريغ وقع عند 353 ث، وحد الاستخدام قتل 32 من 52 وكيل، وعاملين بيتسابقوا بوّظوا حتة.

## 6. الشغل الطويل والاستنا والإيقاف
- **[سحابة]** الرندر والتحميل والتفريغ والتجميع يبدأوا منفصلين: `python3 tools/job.py start --dir <job>/<name> -- <cmd>` (ده في kosif-tool؛ `dragon job` مدمج لسه تذكرة في ROADMAP.md). بيكتب `job.log` و`job.pid` و`job.exit`.
- **[سحابة]** الاستنا: Bash بـ `run_in_background` بيشغّل `python3 tools/job.py wait --dir <job>/<name> --quiet` (timeout لحد 7200000 ms)، أو Monitor:
```bash
tail -n 0 -F <job>/<name>/job.log | grep --line-buffered -E 'ASM|FAIL|Error|Traceback|exit='
```
  نظرة سريعة: `python3 tools/job.py status --dir <job>/<name>`. استنا شرط: Monitor `until <check>; do sleep 2; done`.
- **[في كل مكان]** ممنوع `sleep N; check`، وممنوع sleeps ورا بعض، وممنوع `time.sleep` في لوب إعادة. Claude Code وhook المستودع بيقفلوهم.
- **[سحابة]** الرندر نفسه مايبقاش مهمة `run_in_background` (واحد اتقتل عند حد الـ 30 د عند الفريم 1620/1724). مفيش `&` جوه أمر ممكن يخلص وقته، ومفيش TaskStop لمهمة صاحبة رندر.
- **[سحابة]** الاستنا اللي خلص وقته مش معناه إن الرندر مات: شوف `job.py status` واستنى تاني.
- **[في كل مكان] الإيقاف:** `python3 tools/job.py stop --dir <job>/<name>`، أو `kill <pid>` بالرقم من `job.pid`. ممنوع `pkill -f` ولوب `pgrep -f` و`awk` على `ps`، لأنهم بيمسكوا الشيل بتاعك نفسه (exit 144). بعد الإيقاف، `ps -eo pid,args | grep -c '[r]ender\.cjs'` لازم يطبع 0 (في kosif-tool: `'[r]ender_html'`).
- **[سحابة] في claude.ai:** مفيش `job.py` ولا Monitor. الفيلم الطويل الأحسن يتعمل في Claude Code أو على جهازه (اتأكد معاه أول مرة).

## 7. رفض المصنّف والأعطال المؤقتة
- **[سحابة]** الرفض نهائي: روح للطريق المسموح، وماتعيدش صياغة نفس الحاجة.

| الرفض | كان على إيه | الطريق المسموح |
|---|---|---|
| `[Bot Check Circumvention]` | لوب `player_client` على يوتيوب، أو لستة بروفايل تيك توك بـ `--impersonate` | يرفع الملف، أو من جهازه |
| `[Code from External]` | تحميل ffmpeg static | الأدوات المتثبتة، أو `pip`/`npm` بموافقته |
| `[Shared Scratch Sweep]` | مسح wildcard في `/tmp` | TMPDIR لوحده ومسارات صريحة (قسم 3) |
| `[Irreversible Local Destruction]` | `pkill -9` + `rm` | `job.py stop` وPID بالرقم |

- **[سحابة]** «The server-side auto mode classifier gave no verdict (error)» = عطل من ناحية Anthropic، مش غلط في الأمر. أعد نفس الأمر بالحرف مرة واحدة. لو وقع تاني: اشتغل حاجات من غير شيل، ارجع بعدين (`send_later`)، وقوله بوضوح إن العطل من ناحية Anthropic. حصل 12 مرة في دفعتين (10-25 06:21–06:26 و11-05 16:56).
- **[سحابة]** Higgsfield: PUT رجّع 520، أو `media_confirm` قال «Something went wrong»، أو MCP فصل = إعادة واحدة (نفس `upload_url` صالح 24 ساعة)، وبعدين بلّغه.

## 8. الرفع ولينك التسليم (من السحابة)
- **[سحابة] الإذن:** لينك خاص للفيلم النهائي على ميديا Higgsfield بتاعته أو في الشات = موافقة دايمة (طلب لينك خاص 2026-10-25). ثقة متوسطة: اتأكد معاه أول مرة في v1.2. الرفع لأي طرف تالت والنشر محتاجين «أيوه» كل مرة. وممنوع `tiktok_publish`.
- **[سحابة]** مفيش لينك قبل `$D verify FINAL --expect 1080x1920 --duration D` يخرج 0 على الملف النهائي نفسه (QA.md).
- **[سحابة] الخطوات:**
  1. حمّل الأدوات: `ToolSearch select:mcp__Higgsfield__media_upload,mcp__Higgsfield__media_confirm`.
  2. `media_upload` بـ ≤ 5 ملفات في النداء (15 ملف طلّعوا رد 65,122 حرف أكبر من المسموح).
  3. PUT لكل ملف بـ `curl -T` (بيبعت الملف حتة حتة؛ `--data-binary` حمّل 1.2 GB في الرام ووقع)، بالهيدرز الموقّعة بالظبط، ولازم 200:
```bash
curl -sS -o /dev/null -w '%{http_code}' -T FILE -X PUT -H 'Content-Type: video/mp4' -H 'If-None-Match: *' '<upload_url>'
```
  4. `media_confirm` (النوع `video`؛ zip/tar = `file`) بعد ما كله يرجع 200 بس.
  5. سلّم حقل `url` اللي رجع، عمرك ما تركّب لينك بإيدك.
  6. اتأكد إن الحجم اللي اترفع = الحجم اللي عندك: `curl -sI '<url>' | grep -i content-length` قصاد `stat -c %s FILE`.
  7. ابعت نسخة الموبايل كمان بـ `SendUserFile`.
- **[سحابة] حد الحجم: كل ملف ≤ 450 MB.** 410–465 MB عدّوا، و920 MB و1.2 GB رجعوا HTTP 413. الأكبر يتقسم من غير ما يتعاد ترميزه:
```bash
ffmpeg -i final.mp4 -map 0 -c copy -f segment -segment_time S -reset_timestamps 1 part_%02d.mp4   # S ≈ D × 430 / حجم الملف بالـ MB
```
  وابعت معاه نسخة مضغوطة (CRF 25–26) للموبايل لو حب.
- **[في كل مكان]** `upload_url` ممنوع يتكتب في لوج أو ملف أو رسالة. اللينكات الموقّعة بتخلص بعد 24 ساعة: نادي `media_upload` تاني.

## 9. أشكال نداءات Higgsfield
- **[في كل مكان]** `params` object JSON حقيقي (`model`، `prompt`، `aspect_ratio`، `count`، `medias`)، و`context` جملة قصيرة برّاه. مش string فيه JSON، ومفيش `}` زيادة.
```json
{"params": {"model": "kling4_0", "prompt": "one line, no raw double quotes", "aspect_ratio": "9:16", "count": 1,
            "medias": [{"role": "start_image", "...": "..."}], "mode": "image-to-video"},
 "context": "Opening shot for the owner's film."}
```
- **[في كل مكان]** البرومبت سطر واحد: من غير `"` خام، ولا `\` لوحدها، ولا سطور جديدة، ولا علامات تنصيص ذكية.
- **[في كل مكان]** الباتش ≤ 12 عنصر («Too big: expected array to have <=12 items»).
- **[في كل مكان]** Kling 4 بصورة بداية محتاج `mode: "image-to-video"`؛ text-to-video بيرفض المراجع بـ 422 (0 من 6 عدّوا قبل التصليح).
- **[في كل مكان]** لو اقتراح preset وقّف الإرسال: `declined_preset_id`. اللي اتسجل لـ kling4_0 في الجلسة: `24bae836-2c4a-48e0-89b6-49fcc0b21612`.
- **[في كل مكان]** الرد كبير واتحفظ في ملف؟ اقرا الملف، ماتناديش تاني.
- **[في كل مكان]** `InputValidationError … could not be parsed as JSON` = مفيش حاجة اتبعتت ولا كريدت اتصرف. ابني النداء من الأول (مش نفس النص)، محاولتين متصلّحين بالكتير، وبعدين بلّغه.
- **[في كل مكان]** أي توليد بيصرف كريدت: اعرض البرومبت والتكلفة واستنى «أيوه».

## 10. doctor والإصدارات
- **[في كل مكان]** أول الجلسة: `$D doctor` بيقول البرامج والموديولات موجودة ولا لأ، مش إصداراتها ولا سلوكها. الإصدارات يدوي (مفيش أمر لسه، شوف ROADMAP.md):
```bash
ffmpeg -version | head -1
python3 -c 'import cv2; print(cv2.__version__, hasattr(cv2, "CascadeClassifier"))'
python3 -c 'import av; print(av.__version__)'
yt-dlp --version; node -v; nproc; free -m; df -h / | tail -1
```

| الحاجة | المقاس هنا (2026-11-08) | تعمل إيه |
|---|---|---|
| ffmpeg | 6.1.1 | CI بقى 8.0.1 وكسر تعبير `select`: جرّب التعبيرات الطويلة على الإصدار اللي هتشغّل عليه |
| OpenCV | 5.0.0، `CascadeClassifier` مش موجود | YuNet ONNX من `media.githubusercontent.com` (مش لينك GitHub الخام، ده بيرجّع LFS pointer)، أو ثبّت `opencv 4.12.0.88` زي CI. الكاشف لو مش موجود: ورقة لقطات بدل ما الـ pipeline يقع |
| PyAV | 19.0.2 | بيكسر مسارات الملفات في faster-whisper: ابعتله numpy array |
| Node / Playwright | 22.22.0، Playwright في `/opt/node22/lib/node_modules` | `KOSIF_ROOT=/opt/node22/lib` لـ `render.cjs` |
| الجهاز | 4 CPU، 16 GB رام | رندر تقيل واحد (قسم 4) |

- ليه: 13 فشل `metadata_errors`، و7 وقعات `CascadeClassifier`، وفشل ffmpeg 8 في CI بس.

## 11. الوكلاء والجلسات المساعدة
ثقة متوسطة: اتأكد معاه أول مرة.
- **[في كل مكان]** ماتشغّلش workflow أو وكيل بقيم مكانها فاضي زي `__FILL__`. ابعت الـ ids الحقيقية، وسيب الوكلاء يقروا الملفات (الجولة 3 فشلت بسبب كده).
- **[في كل مكان]** كل وكيل ليه نسخته من السكربتات، والمسارات arguments إجبارية (`chain_wt.sh` بياخد الـ worktree في `$1`). مفيش `chain.sh` مشترك يتعدّل: وكيل كتب فوقه واشتغل في worktree غلط.
- **[في كل مكان]** حط في حسابك حد الاستخدام (قتل 32 من 52 وكيل)، وكمّل بـ `resumeFromRunId`.
- **[سحابة]** ماتقسمش الرندر على جلسات سحابة مساعدة: فحص الأمان عندهم رفض `worker.sh` المتحمّل، والمساعدين A وB فضلوا واقفين في مناظرة الـ 247 حتة. ارندر محلي بـ 2–3 عمال بالكتير، أو ابعت للمساعد الأوامر نفسها جوه الرسالة.
