# USIP v6.4 — أحدث نسخة (01-11-2026)

v6.4 = v6.3 + **التنين الأسود جزء من البروتوكول** (ملحق A48): «استدعِ التنين الأسود» = كل القدرات بلا استثناء (7,378 عنصر من 7 أنواع)، والعقل بيدي كل واحدة جزء من الشغل وطريقة استخدام ووزن، والرد بثلاث أرقام منفصلة: متعيّن، بيشتغل هنا، اتنفذ بإيصال SHA-256. نفس الملفات دي في المستودع في نفس الإصدار.

| الملف | المحتوى |
|---|---|
| `USIP_PASTE.md` | البروتوكول المختصر للصق كأول رسالة (نفس نسخة المستودع) |
| `USIP_PORTABLE_v6_4.md` | النسخة المضغوطة (أقل من 40KB) = `docs/protocol/USIP_PORTABLE_v6_4.md` |
| `USIP_PORTABLE_FULL_v6_4.md` | النسخة الكاملة = `.claude/skills/kosif-superpowers/USIP_PORTABLE.md` |
| `CHANGELOG_v6_4.md` | تغييرات v6.4 |
| `A39-v59-photocraft-mcp.md` | PhotoCraft MCP، صور بلا فوتوشوب |
| `A40-v59-living-site.md` | المواقع الحية |
| `A41-v511-kling-director.md` | مخرج Kling |
| `A42-v512-browser-links.md` | المتصفح وجمع الروابط |
| `A43-v60-contracts-receipts-registry.md` | العقد والإيصال والعدّاد |
| `A44-free-stock-media.md` | صور وفيديو مجانية للمونتاج |
| `A45-youtube-download.md` | تنزيل يوتيوب (على الجهاز بس) |
| `A46-suno-mcp.md` | Suno MCP |
| `A47-v62-media-gateway.md` | جيتواي الوسائط وحالته المقيسة |
| `A48-v64-black-dragon.md` | **جديد في v6.4:** التنين الأسود: المحفّز، المخزون، العقل، درجات الدليل، الأمر، شكل الرد |
| `scripts/protocol_lint.py` | بوابة اتساق الإصدار |
| `scripts/check.py` | بوابة المواقع الحية |
| `scripts/collect_links.js` | جمع الروابط |
| `scripts/photocraft_mcp.py` | مساعد PhotoCraft |
| `scripts/validate_receipt.py` | فاحص إيصال A43 |
| `schemas/` `evidence/` | القوالب والأدلة (منها `evidence/A48-black-dragon-report-20261031.md`، تقرير تشغيل حقيقي للتنين) |

**اتقاس:** `python3 scripts/protocol_lint.py v64-20261101 --version 6.4 --project-root /mnt/project-files --repo-root <kosif-tool>`.
