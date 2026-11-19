# واجهة بايثون في Krita 5.3.4: ملخص مقاس

المرجع الكامل: `krita.pyi`، اللي جنب الملف ده (SIP 6.10، فيه 45 كلاس و757 دالة، ومنسوخ من `lib/krita-python-libs/PyKrita/krita.pyi`). استخدمه مع `"python"` في المشهد. كل اللي تحت ده **اتجرّب جوه kritarunner**، إلا اللي مكتوب عليه غير كده.

## شغال من غير واجهة ✅
| الغرض | الكود |
|---|---|
| مستند جديد | `doc = k.createDocument(w, h, "name", "RGBA", "U8", "", 72.0)`، ثم `doc.setBatchmode(True)` |
| فتح ‎.kra/PSD/PNG | `k.openDocument(path)` |
| طبقة رسم | `n = doc.createNode("اسم", "paintlayer"); root.addChildNode(n, None)` (None = فوق الكل) |
| بكسلات | `n.setPixelData(bytes, x, y, w, h)`، وطولها w*h*4 بترتيب **B,G,R,A** لـ RGBA/U8 |
| قراية بكسلات | `n.pixelData(x,y,w,h)`، `n.projectionPixelData(...)`، `doc.pixelData(...)` |
| فيكتور | `vl = doc.createVectorLayer("n")`، ثم `vl.addShapesFromSvg(svg)`، و`vl.shapes()` و`vl.toSvg()` |
| شكل | `Shape.setPosition(QPointF)`، `setTransformation(QTransform)`، `setZIndex`، `toSvg()` |
| مجموعة | `doc.createGroupLayer("g")`، `setPassThroughMode(True)` |
| Fill | `doc.createFillLayer(name, "color", InfoObject, Selection)` |
| فلتر مباشر | `f = k.filter("blur"); cfg = f.configuration(); cfg.setProperty(...); f.setConfiguration(cfg); f.apply(node, x, y, w, h)` |
| ماسك فلتر | `doc.createFilterMask(name, f, selection)`، ثم `node.addChildNode(mask, None)` |
| تحديد | `s = Selection(); s.select(x,y,w,h,255)`، وكمان `grow/shrink/feather/invert/add/subtract` و`copy/cut/paste` |
| خصايص | `setOpacity(0-255)`، `setBlendingMode("multiply")`، `setVisible`، `setLocked`، `setAlphaLocked`، `move(x,y)` |
| تحويلات | `n.rotateNode(rad)`، `scaleNode(QPointF, w, h, "Bicubic")`، `shearNode`، `cropNode`، `doc.scaleImage/resizeImage/crop/rotateImage` |
| دمج | `n.mergeDown()`، `doc.flatten()`، `n.duplicate()` |
| تصدير | `doc.exportImage(path, InfoObject())` (الصيغة من الامتداد)، و`doc.saveAs(path.kra)` |
| أنيميشن | `setFramesPerSecond`، و`setFullClipRangeStart/EndTime`، و`setCurrentTime(t)` + `exportImage` (بيصدّر الفريم t صح)، و`n.hasKeyframeAtTime(t)`، و`n.pixelDataAtTime(...)`، كلهم ✅ |
| موارد | `k.resources("preset"/"gradient"/"pattern"/"palette")` (dict اسم ← Resource) |

## بيوقّع Krita من غير واجهة ❌ (اتثبت بدليل)
- `Node.paintLine/paintPath/paintEllipse/paintRectangle/paintPolygon`: بيمرّوا بـ `PaintingResources::createHelper` اللي محتاج View نشط. من غير نافذة: Access Violation.
- `Krita.openWindow()` + `Window.addView(doc)`: بيوقع في `KisMainWindow::setMainWindowLayoutForCurrentMainWidget` ← `QAction::menu()` على أكشن null، لأن kritarunner مابيحمّلش قوائم الأكشنز.
- أي `.show()` لنافذة Krita: نفس الوقعة جوه `KisMainWindow::showEvent`.
- `Document.importAnimation(files, first, step)`: Access Violation.
- `Node.enableAnimation()` + `setCurrentTime` + `setPixelData`: مابيوقعش، بس **مابيعملش keyframes** (0 keys، وكل الفريمات = آخر كتابة). فالـ keyframes بتتعمل من برة بـ `scripts/kra_animate.py`.

## صيغة keyframes في ‎.kra (Krita كتبها بنفسه وقت إعادة الحفظ)
- `maindoc.xml`: الطبقة فيها خاصية `keyframes="layerN.keyframes.xml"`.
- `<doc>/layers/layerN.keyframes.xml`: جواه `<keyframes><channel name="content"><keyframe time="T" frame="<ملف بيانات>" color-label="0"><offset type="point" x="0" y="0"/></keyframe>…`.
- خاصية `frame` ممكن تشاور على أي ملف بيانات طبقة رسم في نفس الـ ‎.kra، وKrita بيعيد تسميتها `layerN.fK` لما يحفظ.
- `<doc>/animation/index.xml`: فيه `framerate` و`range`. ترتيب الخصايص بيتغيّر بين حفظ والتاني (Qt)، فماتعتمدش على ترتيب معيّن.

## فخاخ
- **الفيكتور بيترسم بشكل غير متزامن:** من غير `QApplication.processEvents()` لمدة ~1 ثانية، الطبقة بتطلع فاضية و`saveAs` بيرجّع False. `krita_job.py` بيعمل ده في `settle()`.
- **ملكية الكائنات في PyQt:** `k.filter(n).configuration()` على سطر واحد بيدّي «wrapped C/C++ object … deleted». احتفظ بالفلتر في متغيّر الأول.
- **excepthook:** أي exception ماحدش مسكه بيفتح نافذة خطأ وبيعلّق kritarunner. لفّ كودك في try/except.
- **المسارات:** kritarunner بيبوّظ المسارات غير اللاتيني (Latin-1)، والمجلد الحالي بيتضاف لـ `sys.path`. `krita_draw.py` بيشغّل من مجلد مؤقت إنجليزي نضيف.
- **SVG:** وحدات SVG بتتقري كـ pt (1/72 بوصة). عند 300 dpi، شكل عرضه 100 يطلع 24pt، يعني 100px صح، **بشرط** إن root `<svg>` يبقى فيه width/height بالـ pt، و`svg_fit()` بيعمل ده.
- **ترتيب الطبقات:** `addChildNode(node, None)` بيحط الطبقة فوق الكل. `addChildNode(node, other)` بيحطها **فوق** `other`.
