---
name: hypit-run
description: >-
  تشغيل Hypit الحقيقي (hypit-ai/hypit) من التنين: فيديو مكتوب كـ SVML (مكوّنات HTML/CSS/SVG + Timeline مربوط بالكلمة) بيترندر MP4 محليًا ببلاش في Chromium وffmpeg. بيثبّت الحزمة في مجلد لوحده من غير install scripts، ويستخدم المتصفح اللي موجود، ويجيب أمثلتهم وقت التشغيل، ويوقف أي توليد بفلوس لحد «موافق». Use when the user mentions hypit, SVML, svrun, «استنسخ فيديو فيرال»، chat animation، أو عايز موشن/كابشن مربوط بالكلام بأداة جاهزة.
---

# hypit-run: Hypit الحقيقي جوه التنين

**المصدر:** https://github.com/hypit-ai/hypit (npm `@hypit/hypit`، اتجرّب على 0.3.2، commit `6bacce0`). الفكرة والفرق عن `sync script` في `references/HYPIT.md`.
**الرخصة:** Apache-2.0 بشروط. الكود بتاعهم **مش متنسخ هنا**: السكربت بينزّل الحزمة المنشورة ويجيب الأمثلة من المستودع وقت التشغيل. استخدامه لشغلك ولشغل عملائك مسموح، والفيديو اللي بيطلع ملكك. ممنوع تبيعه أو تشغّله كخدمة لناس تانية.

## الأوامر
```bash
R="python -I -X utf8 scripts/rd.py"
$R hypit doctor                                   # Node 22.15+ وffmpeg ومتصفح موجود؟
$R hypit setup                                    # npm install @hypit/hypit في ~/.hypit-rd (--ignore-scripts)
$R hypit example semantic-composition ./proj      # مشروع مستقل من مثالهم، مكوّناته متبنية، والمتصفح متظبط
$R hypit check ./proj chat.svml                   # الـ SVML سليم؟
$R hypit plan  ./proj chat.svrun                  # المزوّدين والأسعار قبل أي تشغيل · exit 3 = فيه حاجة بفلوس
$R hypit render ./proj chat.svrun --to out.mp4    # build + export + ffprobe
$R hypit cli ./proj -- builds                     # أي أمر hypit تاني (inspect, logs, doctor, runtime …)
```

## القواعد
- **الفلوس:** `render` بيقرا `plan` الأول. أي مزوّد مش «local, no Provider charge» (HypiHub، Seedance، GPT Image، …) بيوقف بـ exit 3. اعرض الأداة والسعر على صاحب الشغل، وبعد «موافق» بس: `--allow-paid`.
- **المتصفح:** Hypit بيدوّر على chrome-headless-shell بتاعه في `~/.cache/hypit` ومش هيلاقيه. `example` بيكتب `chromePath` في `hypit.runtime.json` لمتصفح موجود (Playwright، Chrome). غيّره بـ `HYPIT_CHROME`.
- **مشروع من أمثلتهم:** أمثلتهم معمولة جوه monorepo بـ `workspace:*`. `example` بيبدّلها بنسخ npm، ويضيف `"hypit": {"project": true}` والخطوط اللي الـ SVML بيطلبها، ويبني المكوّنات بـ tsc.
- **التزامن:** أي كابشن أو موشن على كلام: `sync script` عندنا للبساطة، وHypit لما المطلوب مشهد كامل بمكوّنات. في الحالتين القياس بـ `rd.py sync check` قبل التسليم.
- **الفحص البصري:** قبل «خلص» اعمل شبكة فريمات وبصّ عليها:
  `ffmpeg -i out.mp4 -vf "fps=1,scale=180:-1,tile=8x1" -frames:v 1 grid.png`

## اتجرّب فعلًا (2026-11-14، سحابة Linux، Node 22.23)
| الخطوة | النتيجة |
|---|---|
| `setup` | 0.3.2 اتثبت |
| `example semantic-composition` | 30 ث، 0 أخطاء |
| `plan chat.svrun` | 3 طلبات، كلها محلية ✅ |
| `render` | 19 ث ← MP4 h264+aac، 540×960، 30fps، 8.0 ث؛ الرسايل الأربعة ظهرت في 0.5/2/3.5/5.2 ث |

## ماتجرّبش لسه
- الأمثلة اللي فيها توليد (ranking-football، interview، podcast): محتاجة حساب HypiHub أو مفتاح.
- WhisperX المحلي (التوقيت من الصوت): بديله عندنا `rd.py sync words`.
- Studio (المعاينة الحية) وويندوز.

## v2.14.0 — بوابة التكلفة الصارمة
- الخطة غير الواضحة أو الفارغة أو التي فشل فحصها تتوقف قبل أي رندر.
- cli للاستعلام فقط. أي build أو get أو deploy يرفض؛ الرندر يمر عبر hypit render.
- لا كتابة فوق الفيديو الموجود؛ الخدمات المدفوعة تتطلب موافقة المستخدم على السعر و--allow-paid.
- فحص: python -I -X utf8 -m unittest discover -s tests -p test_hypit_guard.py
- المصدر والترخيص: https://github.com/hypit-ai/hypit/blob/main/LICENSE
