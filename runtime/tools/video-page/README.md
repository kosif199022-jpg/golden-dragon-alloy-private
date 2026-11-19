# صفحة التحميل ومكتبة الفيديوهات

القاعدة بتاعتها في `engine/references/OWNER.md` §8.1 و`references/RD_RULES.md` §12.

- **المكتبة:** «فيديوهات الكوسف»، https://claude.ai/artifact/825sEpWvtJ81fhHygbWnsY (Artifact واحد ثابت). ملف `videos.json` جواها هو السجل.
- **صفحة لكل فيديو:** Artifact لوحده، ومعلن فيه `capabilities: {downloads: true}`.
  - الفيديو بيشتغل من `light.mp4`.
  - زر «تحميل بأعلى جودة» بيجمّع `full/p*.mp4`، وبعدين `downloads.save`، فبيطلع نفس الملف الأصلي.
  - زر «نسخة خفيفة».
  - كابشن، ورابط مباشر اختياري.

## الخطوات (فيديو جديد)
```bash
T=tools/video-page/video_page.py
python3 $T build final.mp4 --id <slug-تاريخ> --title "العنوان" --date "16 / 11 / 2026" \
    --caption-file caption.txt [--direct-url URL] --hub-url https://claude.ai/artifact/825sEpWvtJ81fhHygbWnsY \
    --filename <اسم-الملف> --out out/video-pages/<id>
```
1. **انشر صفحة الفيديو:** دفعات `publish.json` بالترتيب.
   - كل دفعة حدها 64 MB.
   - أول دفعة فيها `index.html`، و`icon: "video"`، و`capabilities: {"downloads": true}`.
   - الدفعات اللي بعدها بنفس `file_path`.
2. **هات `videos.json` الحالي من المكتبة:** `Artifact read` بـ `url` المكتبة و`path: "videos.json"`. حطّه في `out/video-pages/_hub/`، ومعاه `index.html` من `read` و`posters/`.
3. شغّل `python3 $T hub-add out/video-pages/<id>/entry.json --page-url <لينك الصفحة> --hub out/video-pages/_hub`.
4. **انشر المكتبة:** بنفس `url` المكتبة، والملفات `videos.json` و`posters/<id>.jpg`.
5. شغّل `python3 $T check out/video-pages/<id>`، ولازم يطلع «md5 matches».

## حدود اتعملت على أساسها
- **ملف ثنائي:** 15 MB، فالأجزاء 14 MB.
- **الدفعة الواحدة:** 64 MB.
- **نسخة الـ Artifact:** 256 MB، فكل صفحة فيها فيديو واحد، والمكتبة فيها صور ولينكات بس.
- **روابط `<a download>`:** مابتشتغلش جوه الـ Artifact، فالحفظ بـ `downloads.save` بس.
- **فيديو من موقع برّه:** الـ CSP بيمنعه، فالتشغيل لازم يكون من ملف منشور جوه الصفحة.
