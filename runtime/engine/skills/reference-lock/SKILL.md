---
name: reference-lock
description: >-
  قفل المرجع: لما صاحب الشغل يقول «نفس الخط» أو «نفس الألوان» أو «زي ده بالظبط»، المهارة دي بتستخرج من المرجع الألوان (hex) والخطوط، وتقفلهم كقيود، وتقيس الناتج قدامهم قبل التسليم. بتقرا الصور والفيديو وPDF وCSS/HTML/SVG/ASS/JSON وملفات الخطوط. بتتعرف على الخط من صورة بمقارنة النص بكل الخطوط المتثبتة. Use whenever the user asks for the same font, same colours, same style, match this reference, exact palette, brand colours: نفس الخط، نفس الألوان، نفس الستايل، زي الصورة دي بالظبط، مطابق للمرجع.
---

# قفل المرجع (reference-lock)

**القاعدة:** «نفس» يعني نفسه بالظبط. ممنوع «قريب منه»، وممنوع تبدّل في السكات. لو حاجة مش متاحة، قول واسأل.

```bash
R="python3 -X utf8 scripts/rd.py"
$R ref lock brand ref.png --text "النص اللي ظاهر في الصورة" [--crop x,y,w,h]   # يقفل الألوان والخط
$R ref lock brand style.css subs.ass font.ttf                                  # ملفات نصية: قيم بالحرف
$R ref lock brand --font "Cairo" --color "#E63946"                             # صاحب الشغل قال الاسم
$R ref show brand          # القيود كنص يتحط في الكود أو البرومبت
$R ref verify brand out.png [--text "…" --crop …]   # 0 ✅ مطابق · 1 ❌ صلّح · 2 ⚠ بُص بعينك
$R ref fontmatch img.png --text "…" [--fonts-dir DIR]  # ترتيب الخطوط حسب الشبه
```

- ألوان وخطوط الملفات النصية **مؤكدة**. خط الصورة **مرشّح**: أكّده بالعين أو اسأل قبل ما تكمّل.
- الخط المش متثبت بيتقال بالاسم: «هاته»، مش «حطيت شبهه».
- `verify` بيفشل على: لون مقفول مش موجود (ΔE > 10 للصور، أي فرق للملفات النصية)، لون كبير جديد مش في المرجع (`--allow` لو مقصود)، خط مختلف.
- كل فشل بيتسجل في `~/.red-dragon/refs/misses.jsonl`.
- `selftest`: 11 فحص (ألوان، خط من البكسل، CSS، ASS بترتيب BGR، رفض خلفية متغيرة وخط مختلف).
