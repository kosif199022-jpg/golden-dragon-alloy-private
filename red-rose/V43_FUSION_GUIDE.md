# 🌹 V43 — أبو كاب × عقل التطبيق الفائق

## المصادر التي تمت مراجعتها

1. `ريل أبو كاب.rar`: أرشيف RAR5 من 688 مدخلاً، يحتوي 660 إطار JPEG للتسلسل، فيديو نهائي، مرجعين، HTML/SVG تايملاين بواجهة `window.seek(t)`، وكود `render.py` بواقع 30 FPS و660 إطارًا (22 ثانية)، مع صوت وخط. المراجعة تشمل الكود واللقطات المرجعية وملفات وصف المصدر.
2. `app-super-mind.skill`: حزمة ZIP من 22 مدخلاً: `SKILL.md`، عقل تطبيقي محلي، نظام تقييم، 12 عضوًا، تسع بوابات تطوير، ماسح التطبيق و9 نماذج أعمال.

النتيجة ليست نقل الأرشيفين حرفيًا، بل **خمس وظائف Python مستقلة أصلية** داخل `intelligence_fusion_v43.py`، يمكن لأي وكيل تشغيلها دون وجود المرفقين أو استدعاء سكربتاتهما.

## المحرك التنفيذي

المحوّل الأصلي `intelligence.fusion`، **read-only**:

| العملية | ما تنجزه | ما لا تدّعيه |
|---|---|---|
| `readiness` | 12 درجة (0–4) مع طلب مراجع أدلة، ومؤشر وصفي للفجوات | لا تمنح شهادة ذكاء حقيقية أو تعيد تدريب النموذج |
| `ladder` | التقدم التسلسلي بين 9 بوابات تطوير، ورفض القفز فوق مرحلة أو نجاح بلا مرجع | مسار ملف ليس دليلًا حتى يُفحص |
| `paired_eval` | تحليل حالات اختبار dev/heldout قبل/بعد، مع إحصاء McNemar الدقيق وتنبيهات التراجع | الدرجات المرسلة من المستخدم لم تُشغّل نفسها |
| `reel_preflight` | تدقيق عدد الإطارات/المدة و9:16 وتداخل المشاهد وCTA ونسبة الموسيقى | ليس تحققًا من الفيديو أو الحقوق أو الإخراج الفني |
| `reel_seek` | استعلام حتمي عن المشهد والشخصيات والـprops عند الثانية المطلوبة | لا ينفّذ JavaScript ولا يرسم الإطار |

## مثال أبو كاب

`examples/abu_kab_reel_v43.json` هو قالب سردي **مستخلص** للمدة الأصلية 22 ثانية: الخطر → التسلق → المفاجأة → فكرة انتظار القيلولة → الهروب → خاتمة متابعة.

`music` يحتفظ بنسبة موسيقى `Happy Ukulele` إلى Jason Shaw (Audionautix.com)، `CC BY 3.0`. لا يشمل المستودع ملفات الموسيقى أو الفيديو أو الخط أو 660 صورة؛ عند استخدام موسيقى فعلية احتفظ بالترخيص والنسبة قبل النشر.

## الاستخدام

```bash
cd red-rose
python rose.py capabilities
python rose.py capability-run intelligence.fusion '{"op":"ladder","params":{"stages":[{"step":"understand","passed":true,"evidence":["brief.md:12"]}]}}'
python rose.py capability-run intelligence.fusion '{"op":"paired_eval","params":{"before_sha":"aaaaaaaaaaaaaaaa","after_sha":"bbbbbbbbbbbbbbbb","cases":[{"id":"demo1","case_sha":"cccccccccccccccc","split":"dev","category":"normal","before_pass":false,"after_pass":true}]}}'
python -m unittest test_intelligence_fusion_v43 test_intelligence_bridge_v43 -v
python -W error::ResourceWarning -m unittest discover -v
```

لعرض معاينة تقرير المشروع من دون ملف المستخدم الأصلي:

```python
import json
from intelligence_fusion_v43 import run
p=json.load(open("examples/abu_kab_reel_v43.json",encoding="utf-8"))
allowed={"title","width","height","fps","frames","shots","frame_inventory_count","music","seekable"}
project={k:v for k,v in p.items() if k in allowed}
print(run("reel_preflight",project))
print(run("reel_seek",{"project":project,"time_seconds":12}))
```

## مهم لقياس «الذكاء»

المؤشرات **وصفية وليست IQ**. لا يُسمح بقول «تحسّن الذكاء» من أمثلة مكتوبة بعد رؤية الإجابات. يحتاج ذلك عينات مستقلة، مقارنة قبل/بعد على نفس الحالات الأصلية من نسختين مختلفتين، عدم إفساد السلامة، وإثبات أن تصحيح المستخدم غيّر سلوكًا لاحقًا. `paired_eval` يحسب من مدخلاته ولا يشغّل التطبيقين؛ يمكنه فقط إعلان *مرشح لتحسّن يحتاج تحققًا مستقلًا*.

## حدود الصهر

- لا نسخ أو تنفيذ لأدوات `app-super-mind` الأصلية، ولا إعادة توزيع لملف RAR أو فيديوهات مرجعية/صوت/خطوط.
- لا يقدّم محركًا ثلاثي الأبعاد أو نسخة وفية من المشاهد المرسومة؛ الكود الأصلي الكامل والحركة الفعلية بـSVG/Playwright لم يُعاد بناؤهما في V43.
- اختبارات V43 الجديدة تُضاف إلى الاختبارات القديمة، لكن أي فشل قديم بقياس `heldout` **لا يُعالَج بخفض معيار النجاح**.
- فهرس `rose_catalog` يُعاد توليده في الذاكرة إذا اختلفت قائمة المحوّلات عن القائمة المسجلة، ولا يكتب قاعدة بيانات خاصة.

لمراجعة تفاصيل المرفقات وبصماتها: `SOURCE_FUSION_AUDIT_V43.json`.