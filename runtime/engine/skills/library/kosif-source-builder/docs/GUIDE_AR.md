# دليل الاستخدام

## اختيار المحتوى

- `python kosif.py catalog`: يعرض روابط الأدوات الموثقة.
- `python kosif.py catalog --group own-video`: برامج KOSIF للفيديو فقط.
- `python kosif.py catalog --group own-extended`: باقي مستودعات KOSIF.
- `python kosif.py catalog --group editing`: أدوات المونتاج الخارجية.
- `python kosif.py catalog --json`: فهرس JSON كامل.

## تنزيل الأكواد

`python kosif.py install --group own-video` يستعرض خطة الاستنساخ دون تنفيذ.
`python kosif.py install --group own-video --execute` ينفذ فعليًا بواسطة Git في `workspace/sources/`.
`python kosif.py install --group all --execute --dest D:/KOSIF-SOURCES` لجلب الجميع إلى مسار تختاره.
`python kosif.py install --group ai-video --execute` لنماذج الفيديو **شيفرتها فقط**؛ الأوزان منفصلة.

الاستنساخ لا ينفذ أوامر بناء أو سكربتات مستودعات خارجية بشكل تلقائي؛ افحص تراخيصها ومتطلباتها أولًا.
يمكن تسجيل دخول GitHub للمستودعات الخاصة بواسطة `gh auth login` ثم `gh auth setup-git` (إن كان GitHub CLI مثبتًا)، أو إعداد Git Credential Manager مسبقًا. لا تضع توكن داخل الملفات.

## تكوين فيلم

1. أنشئ ملف خطة: `python kosif.py storyboard --output project/myvideo.json --duration 30 --shots 5`
2. افتح JSON وضع ملفات الصور أو MP4 في `source` لكل مشهد (مسارات نسبية بالنسبة لمجلد ملف الخطة أو مسارات مطلقة).
3. نفّذ: `python kosif.py render --storyboard project/myvideo.json --output output/final.mp4 --audio assets/song.mp3 --width 1080 --height 1920 --fps 30`
4. يعدل البرنامج **مدد المشاهد** نسبيًا لتوافق طول الملف الصوتي. يحافظ على الصوت الأصلي مع ترميزه AAC ويصدر فيديو MP4 عموديًا.
5. راجع ملف `output/final.report.json` وملف المشروع بنفسك.

## ملاحظات فنية

- المشهد بلا `source` يُرندر كخلفية تجريبية. لا تتوقع AI أو فيلمًا سينمائيًا من هذا وحده.
- الرندر الحالي قصّ ذكي إلى مساحة الصورة بالمنتصف، ولا يتضمن كشف وجه أو مونتاج قائم على النص.
- يفضل اختبار المخرجات الصغيرة أولًا: 720×1280/24FPS.
- تنصيب برنامج FFmpeg يتم من المصدر الرسمي أو مدير الحزم الموثوق على جهازك، ليس من ZIP.
