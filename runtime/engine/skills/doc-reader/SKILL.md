---
name: doc-reader
description: >-
  أي مستند يتحوّل لـ Markdown قبل ما يتقري، بـ Microsoft MarkItDown (MIT): PDF، Word (docx)، PowerPoint (pptx)، Excel (xlsx/xls)، HTML، CSV، JSON، XML، EPUB، Outlook (msg)، ZIP. الـ PDF العربي اللي بيطلع حروفه مقلوبة ومفصولة بيتعدل لوحده. Use whenever the owner sends or points to a PDF or any document to read, summarise, translate, analyse or turn into something else, or says «حوّله لماركداون», «اقرا الملف ده», «لخّص الـ PDF», «إيه اللي في الملف», markdown, MarkItDown.
---

# doc-reader — أي مستند ← Markdown

**القاعدة:** أي PDF أو مستند يوصلك (مرفق، مسار، أو ملف في مجلد الشغل) يتحوّل الأول، وبعدين تقرا الـ `.md`. ده أرخص بكتير من قراية الـ PDF كصور، والجداول بتفضل جداول، والعناوين عناوين.

```bash
R="python -X utf8 scripts/rd.py"
$R md doctor                                   # MarkItDown متثبت؟ وأنهي صيغ شغالة؟
$R md install --yes                            # pip install "markitdown[all]" (مرة واحدة)
$R md convert report.pdf                       # ← _md/report.pdf.md جنب الملف
$R md convert a.docx b.pptx c.xlsx --out D:\work\_md
$R md convert book.pdf --print --max-chars 4000   # يكتب الملف ويطبع أوله
$R md batch D:\inbox --recursive               # كل المستندات اللي في المجلد ← D:\inbox\_md
$R md selftest                                 # فحوص من غير نت
```

## بعد التحويل
- اقرا الـ `.md` بـ Read. لو طويل (أكتر من ~150 ألف حرف) اقراه على أجزاء بـ offset، أو دوّر فيه بـ grep الأول.
- **PDF عربي:** pdfminer بيطلّع أغلب ملفات PDF العربي بالحروف المعروضة ومقلوبة («ﻦﻳﻼﻧوا ﲑﺒﺧ»). الأداة بتعدلها لوحدها (المحرك بيبان `markitdown+arabic-fix`). بُص على أول كام سطر: لو لسه فيه كلام مقلوب، قول كده واقرا الصفحات كصور.
- **نص فاضي أو قليل جدًا** = PDF ممسوح (صور). اقرا الصفحات كصور، أو OCR لو متاح.
- الصور والصوت مش هنا: الصور تتقري بعينك، والصوت بـ `rd.py sync words` (Whisper).

## حدود وأمان
- **ملفات محلية بس.** لينك من النت يتحمّل الأول بموافقة صاحب الشغل، وبعدين يتحوّل.
- الإضافات (plugins) بتاعة MarkItDown مقفولة، ومفيش أي خدمة مدفوعة (Azure Document Intelligence أو LLM للصور) بتشتغل من غير ما صاحب الشغل يقول «أيوه».
- من غير MarkItDown: النص وCSV وJSON وHTML بيتحوّلوا بمكتبة بايثون العادية، والـ PDF بـ PyMuPDF لو موجودة. غير كده بيقولك تثبّته.
- ده شغل روتيني: في الخطة بيتعلّم 🤖، فممكن يتعمل بالعامل الرخيص `rd-runner`.

## المصدر
[microsoft/markitdown](https://github.com/microsoft/markitdown)، رخصة MIT، © Microsoft Corporation. الكود هنا (`scripts/docmd.py`) بتاع التنين، وبيستدعي المكتبة بعد ما تتثبت بـ pip، ومفيش حاجة من كودها منسوخة جوه المستودع.
