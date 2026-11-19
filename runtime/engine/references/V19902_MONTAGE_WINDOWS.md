# v1990.2 — Montage Arena + Windows Commands

## مصدر الإضافة
- `montage-arena.zip`: حلبة صدامية مستقلة، لا تُحل محل `tool arena` الأصلي. مصادر 15 اختبارًا مدّعاة في الحزمة، وتقييمات A/B وتفسير مشاهد، ومراجع بروتوكول.
- `windows-commands(1).zip`: مطابقة بايتية للملف السابق. أضيفت أداة فحص ثابتة `windows-lint` وقواعد ترميز ومسارات Windows.
- `github-atlas(1).zip`: مطابقة بايتية لـ `github-atlas.zip` — لم تُكرر بيانات 1000 مستودع.

## استخدام عملي
```bash
python3 scripts/dragon.py tool montage-arena roster --type reel
python3 scripts/dragon.py tool montage-arena new "ريل قصير من لقطاتي" --type reel --size quick --dir /tmp/my_arena
python3 scripts/dragon.py tool windows-lint --shell bash 'taskkill /F /IM foo.exe'
python3 scripts/dragon.py tool windows-lint --shell powershell --file command.txt --json
```

`montage-arena` يقوم بإنشاء خطط وسجلات محلية والمقارنة بقياسات FFmpeg عند الطلب، ولا يعني إنشاء وكلاء AI مستقلين. وضع `war` يعرض بريفات لكل وكيل؛ لا ينفذ الوكلاء. Windows lint تحليل نصي فقط ولا ينفذ الأمر. `NativeExact.ps1` يعمل فقط عند تحميله صراحة من PowerShell على Windows.

## الربط مع Reel DNA وHiggsfield
- Reel DNA: تجميع وصفة القطعات والطاقة.
- Montage Arena: حكم بين خطتين أو نسختين باستخدام بيانات وتقارير A/B.
- Higgsfield: تنفيذ منفصل اختياري بعد موافقة التكلفة. لا تجارب عن بُعد في هذا الدمج.

## القواعد
- لا تثبيت تلقائي، ولا استدعاء خدمات مدفوعة، ولا تنفيذ لأوامر Windows غير موثوقة.
- لا إعادة استخدام ملفات أو أصوات الآخرين دون حقوق مناسبة.
- المقاييس الكمية لا تُثبت تفوقًا فنيًا أو احتفاظ الجمهور؛ هي جزء من التحكيم.
- تجارب الفيديو المحلية قد تكتب داخل مجلد حلبة جديد؛ لا تعمل فوق الملف الأصلي.
- نتيجة النسخة على Linux لا تثبت سلامة NativeExact.ps1 على Windows.
