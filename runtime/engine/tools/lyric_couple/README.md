# lyric_couple — فيلم الكلام بالراجل والبنت (v1990.5.0)

- `template.html`: صفحة الفيلم اللي اتعمل بيها حوالي 40 فيلم (9–10 نوفمبر 2026): صور ثابتة بحركة كاميرا أو فريمات لقطات متحركة، الكلام أبيض رقعة + سطر أحمر، العلامة المائية والتوقيع آخر 3 ث، صفر overlay.
- `mk.py JOB spec.json` (أو `dragon.py tool lyric JOB spec.json`): يكتب `JOB/film/index.html` ويحط الخطوط.
- `imgs.py JOB/film/img a1=<stem> …`: ينزّل صور Higgsfield، يفتّح الغامق، يعمل depth map (rembg u2netp لو موجود) وورقة `JOB/sheet.jpg`.
- `render.sh JOB OUT.mp4 [--from S]`: رندر + الصوت `JOB/song.m4a` بطوله بالظبط + verify. `--from S` يكمّل من الثانية S على `JOB/video.mp4` الموجود.
- الخطوط Aref Ruqaa وTajawal وAmiri: رخصة SIL Open Font License 1.1 (مجانية، مسموح نشرها مع البرامج).
- المرجع الكامل: `references/LOOKS_LIBRARY_V19905.md` و`references/SESSION_HARVEST_V19905.md`.
