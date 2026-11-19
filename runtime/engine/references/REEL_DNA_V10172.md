# KOSIF Reel DNA — Black Dragon v10.17.2 candidate

## المصدر وحالة التنفيذ

هذا محرك محلي مضاف إلى التنين، يستند إلى **وصف المستخدم** لمجموعة Higgsfield Katana وملفات `analysis/analysis.json` و`energy.json` و`audio/beats.json` و`words.json`، لا إلى شفرة Katana الفعلية. ملفات Katana غير مرفقة بالحزمة؛ لذلك **لم نختبر** أن أسماء الحقول في JSON الحقيقي مطابقة للأسماء المدعومة هنا. أمر توليد أوامر Katana يطبع وصفة للاستخدام بعد مراجعة `--help` داخل Higgsfield، ولا يتصل بالمزود ولا ينزل فيديو.

اختُبر هذا المحرك في البيئة المحلية: استخراج وقراءة وصفة JSON، بناء EDL بملفات مملوكة للمستخدم، إنشاء معاينة MP4 محلية (صور أصلية ملونة للاختبار)، التحقق من عدد الإطارات، وحفظ/بحث وصفة محلية. وهذا **لا يثبت** عمل Katana عن بُعد، أو مجانية Sandbox، أو صلاحية الوسائط الخارجية لإعادة الاستخدام.

## الاستخدام

من داخل مجلد `black-dragon`، باستخدام Python 3:

```bash
python scripts/dragon.py tool reel-dna doctor
python scripts/dragon.py tool reel-dna katana-commands --workdir /home/user/rr/reel1 --url 'https://example.com/authorized-reel'
python scripts/dragon.py tool reel-dna extract \
  --analysis examples/reel_dna/analysis.json \
  --energy examples/reel_dna/energy.json \
  --beats examples/reel_dna/beats.json \
  --words examples/reel_dna/words.json \
  --out out/reel-dna.json
# عيّن عدد ملفاتك = عدد shots في reel-dna.json (مثال المرفق فيه 2)
python scripts/dragon.py tool reel-dna apply --recipe out/reel-dna.json \
  --clips /path/to/owned-clip-1.mp4 /path/to/owned-clip-2.png --out out/reel-edl.json
python scripts/dragon.py tool reel-dna render --edl out/reel-edl.json \
  --out out/preview.mp4 --width 540 --height 960 --preview
python scripts/dragon.py tool reel-dna library add --recipe out/reel-dna.json \
  --name 'ستايل ريل سريع' --tags 'سريع,موشن' --description 'مقاطع 9:16'
python scripts/dragon.py tool reel-dna library list --query 'سريع'
python scripts/dragon.py tool reel-dna library list --tag 'موشن' --json
python scripts/dragon.py tool reel-dna compare --reference out/reel-dna.json --ours out/other-dna.json
```

لإضافة موسيقى **مملوكة أو مرخّصة** استخدم `render ... --audio /path/to/authorized-track.mp3`. لا يستورد `reel-dna` الموسيقى الأصلية، ولا صور المرجع، ولا شخصياته. لا يُسمح بأي توليد أو رفع أو دفع تلقائي.

## تنسيق JSON المعروف

الاستيراد يدعم قائمة `cuts` أو `cut_points` أو `scene_cuts` أو `shot_boundaries`، بأزمنة بالثواني، أو `{time: ...}` أو `{frame: ...}`، أو قائمة `shots/segments/scenes` ببدايات ونهايات. يجب توفر FPS ومدة المرجع داخل `analysis.json` أو إعطاؤهما صراحة عبر `--fps` و`--duration`. لا تُخمن القيم. تُستورد أنواع الطاقة المصرح بها من قائمة `events`، والـbeats من `beats/beat_times/onsets`، والكلام من `words/segments/transcript` إن كان كل عنصر يحمل توقيتًا واضحًا. أي حقول لا تُطابق تُبلغ عنها الأداة؛ ويجب بناء محوّل مخصص بعد رؤية JSON Katana الحقيقي.

- `recipe`: مواعيد القطعات بالفريم، مواقع الأحداث، beat frames، الكلمات، بصمات SHA-256 للمدخلات، وملاحظات صريحة على البيانات المفقودة.
- `EDL`: ترتيب المقاطع، عدد فريماتها، بصمات SHA-256 للوسائط الخاصة، وإشارات المؤثرات غير المنفذة.
- `render`: يطابق عدد الفريمات، يستخدم FFmpeg وlibx264 محليًا، ويطبّق **flash** كتأثير مرئي بسيط فقط. **shake/pan/punch/zoom** تظل علامات في الـEDL لاستكمالها في Katana أو محرك موشن مختلف. النص العربي لا يُحرق تلقائيًا؛ يمكن التعامل معه بـChromium/ASS في مرحلة منفصلة.
- `compare`: مقارنة وصفية لمواضع القطعات فقط، وليست مقارنة آلية لألوان أو طاقة الحركة أو إيقاع الصوت.

## المكتبة والحقوق

المكتبة الافتراضية `~/.kosif/reel-dna/` وتُكتب فقط بطلب `library add`، ويمكن تغيير المجلد بـ`--library`. تحفظ الوصفة والأسماء والوسوم ولا تنزّل الوسائط. لا تُرسل الملفات إلى أي منصة. راجع حقوق الاستخدام لمرجع الريل ومدخلات الصوت واللقطات. استخدام صورة ريل ناجح كمرجع للتحليل لا يعطي إذن نسخ مواد محمية.

## حدود التكلفة

محرك Reel DNA المحلي لا يستدعي APIs خارجية ولا يُجري توليدًا مدفوعًا؛ استخدام `Higgsfield Sandbox` نفسه **قد تكون له تكلفة غير موثقة** ولا يجب وصفه بأنه مجاني بلا تحقق. أي تشغيل Katana أو XL أو رفع أو توليد يتطلب تقييم التكلفة وموافقة المالك.
