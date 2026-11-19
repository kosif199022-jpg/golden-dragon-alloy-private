# مشهد «قلبة الكارت لواجهة شات» (من كومب «المشهد 1» بتاع فارس)

اتحلل من كومب «المشهد 1» واتعاد بناؤه بالسكربت بالظبط في كومب «اعادة صنع» (25-10-2026)، وطلع مطابق في الكونتاكت شيت. الأرقام دي كفاية تعيد بناؤه من الصفر.

## القصة (4 ثواني)
كلمة كلمة على كارت أسود بيعمل Pop من الصفر ← الكارت بيتقلب ← ضهره بلاتة كريمي عليها أيقونة Claude ← البلاتة بتكبر لحد ما تبقى واجهة شات والكاميرا بترجع لورا (Zoom Out) ← الريكوست بيتكتب ← زرار Send بيتضغط ← رسالة اليوزر بتعمل Pop ← رد Claude (كارت فيديو) بيعمل Pop.

## الكومب
- 1080×1920، ‏30fps، ‏122 فريم، Renderer: ‏Advanced 3D، ولون خلفية الكومب أسود.
- Motion Blur شغال: Shutter Angle ‏180، Phase ‏0، Samples ‏16، Adaptive ‏128.
- الخلفية: سوليد 2D اسمه BG بلون ‎#F6F6F6 ‏(0.965).
- كل الليرز 3D، والـ Motion Blur شغال على الشيبس والنصوص والأيقونة. النلاط من غير Motion Blur، ما عدا Card Entrance و Master.

## ترتيب الليرز (من فوق لتحت)
1. Bottom Blur (Adjustment)
2. Blur Map (بري كومب، مخفي)
3. Adjustment Layer 1 (Posterize Time)
4. UI Claude Reply Video
5. UI User Bubble
6. UI User Msg
7. UI Script
8. UI Send Arrow
9. UI Send
10. UI Model
11. UI Plus
12. UI Placeholder (after send)
13. UI Chat Bar
14. UI (world px) (نل)
15. Null 5
16. Cam Null - Zoom Out
17. Camera
18. شغلانة
19. أصلاً
20. دي
21. لأن
22. Card
23. Card Selection Stroke
24. Claude Icon (back)
25. Panel Matte (مخفي)
26. Icon Plate (back)
27. Card Entrance (نل)
28. Master - Scale & Lift (نل)
29. BG
30. فيديو المرجع (مخفي)

## سلسلة الـ Parent
- **الكارت:** Master (Anchor 0، Position (540, 900, 0)، Scale ‏90) ← Card Entrance (Anchor (50, 50)، Position 0) ← Card (Position (50, 50, 0)، Scale ‏78).
- **اللي مربوط في Card:** الكلمات الأربعة، و Card Selection Stroke، و Panel Matte، و Icon Plate (back).
- **واجهة الشات:**
  - Icon Plate (back) ← UI (world px).
  - UI (world px) ← UI Chat Bar، و UI User Bubble، و UI Claude Reply Video، و Claude Icon (back).
  - UI Chat Bar ← UI Script، و UI Send، و UI Model، و UI Plus، و UI Placeholder.
  - UI Send ← UI Send Arrow.
  - UI User Bubble ← UI User Msg.
- **الكاميرا:** Null 5 (من غير Parent، Anchor 0، Position (540, 960, 0)) ← Cam Null (Anchor 0، Position (‎-540, ‎-960, 0)) ← Camera.
  - الكاميرا Two-Node: ‏POI (540, 960, 0)، و Position (540, 960, ‎-1866.67)، و Zoom ‏1866.67، و DOF مقفول.
  - النلّين بيلغوا إزاحة بعض، فالكاميرا بتبدأ في مكانها الطبيعي.

## تركة ضهر الكارت (Back Face)
- **البلاتة ورا الكارت:** Icon Plate (back) و Panel Matte متحطين في Z ‏+66 جوه مساحة Card، يعني ورا الكارت.
  - الإعدادات: Scale ‏128.205 (يعني 100 ÷ 0.78 عشان يلغي Scale الكارت)، و Orientation ‏(180, 0, 180)، و Y Rotation ‏180.
- **لما الكارت يتقلب ‎-180** البلاتة بتيجي قدام.
- **النل UI (world px):** ‏Anchor (50, 50)، و Position (0, 0, 20)، و Orientation ‏(180, 0.478, 180)، و Opacity ‏0.
  - وظيفته إنه يعدل الـ UI المقلوب، وكل اللي جواه بيتحط بالبكسل العادي حوالين نص البلاتة.
- **ميل خفيف:**
  - UI User Bubble و UI Claude Reply Video: ‏Orientation ‏(0, 0.478, 0).
  - Claude Icon: ‏Orientation ‏(180, 359.522, 180).
  - Card Selection Stroke: ‏Orientation ‏(180, 8.972, 180)، وده اللي بيدّي الإطار الأبيض ميل منظوري خفيف وهو بيلف.

## المات (Track Matte الجديد، Alpha)
- الكلمات الأربعة عليها مات Card، والكارت فاضل ظاهر.
- كل ليرز الـ UI (Chat Bar، و Send، و Send Arrow، و Model، و Plus، و Placeholder، و User Bubble، و User Msg، و Reply Video) عليها مات Panel Matte، والمات ده مخفي.
- UI Script عليه مات UI Chat Bar، فالكتابة متقصوصة جوه البار.

## التايملاين بالجرافات
| الفريمات | اللاير | الخاصية | من ← لـ | الجراف |
|---|---|---|---|---|
| 0←43 | Card Entrance | Scale | 0 ← 100 (الـ 3 أبعاد) | Out ‏0.1% بسرعة 13966.67، و In ‏95.47% بسرعة 8.7986. الكيرف `[0.001, 0.2, 0.045, 0.88]` |
| 0 / 11 / 16 / 29 | لأن / دي / أصلاً / شغلانة | In Point (كَت من غير أنيميشن) | — | — |
| 25←65 | Card | Y Rotation | 0 ← ‎-180 | 88% / 88%، السرعة 0. الكيرف `[0.88, 0, 0.12, 1]` |
| 54←84 | Icon Plate (back) | Rect Size / Roundness | ‏296×296 ← 920×1000 / ‏66.6 ← 44 | ‏71% / 76% (السرعة 0) |
| 54←69←94 | Panel Matte | Size / Roundness | ‏296 ← 651.09×696.62 ← 892.83×969.35 / ‏66.6 ← 53.74 ← 44.98 | **كي 1:** Out ‏77.56%. **كي 2:** In ‏15.29% و Out ‏17.21%، والسرعة 2210.42 (W) و 2493.81 (H) و ‎-80.06 (Roundness). **كي 3:** In ‏60.08%، والسرعة 281.08 / 317.11 / ‎-10.18. الكيرفات `[0.776, 0, 0.847, 0.524]` ثم `[0.172, 1.311, 0.399, 0.418]` (Overshoot خفيف) |
| 54←84 | Claude Icon (back) | Position / Scale | ‏(50, 50, ‎-6) ← (‎-306, ‎-346, ‎-6) / ‏9 ← 2.9 | ‏71% / 76% |
| 54←86←108 | Cam Null | Position Z | ‏0 ← ‎-593.985 ← ‎-600 | **كي 1:** Out ‏79.34%. **كي 2:** In ‏89.41% و Out ‏29.89%، والسرعة 65.71. **كي 3:** In ‏36.91%. الكيرفات `[0.793, 0, 0.106, 0.894]` ثم `[0.299, 2.394, 0.631, 1]` |
| 54←121 | Null 5 | Position Z | ‏0 ← ‎-93 | Linear (Drift) |
| 70←86 | UI Script | Range Start | ‏0 ← 100 | Linear |
| 87←90←95 | UI Send | Scale | ‏100 ← 82 ← 100 | ‏71% / 76% |
| 91←106 | UI User Bubble | Scale | ‏50 ← 100 (Z ثابت 100) | Out ‏0.1% بسرعة 8380، و In ‏95.47% بسرعة 5.279. الكيرف `[0.001, 0.084, 0.045, 0.95]` |
| 96←112 | UI Claude Reply Video | Scale | ‏50 ← 100 | نفس جراف البابل، بس السرعة 7856.25 / 4.949 |

- **الـ In/Out بتاعة ليرز الـ UI:**
  - UI Script من 70 لـ 91: بيختفي لحظة الإرسال.
  - Placeholder يبدأ من 91.
  - User Bubble و User Msg من 91 لـ 207.
  - Reply Video من 96 لـ 212.
- **حساب سرعة الـ Pop لما المدة تتغير:**
  - الـ UI Pop: سرعة الـ Out = متوسط السرعة × 83.8، وسرعة الـ In = متوسط السرعة × 0.0528.
  - Card Entrance: سرعة الـ Out = المتوسط × 200.2، وسرعة الـ In = المتوسط × 0.126.
  - متوسط السرعة = المسافة ÷ (عدد الفريمات ÷ 30).
- **الـ Position:** الـ Spatial Tangents كلها 0، و Auto Bezier مقفول.

## الأوفرلاب اللي اتقاس
- **القلبة:** في فريم 54 القلبة كانت قاطعة حوالي 95% من مسافتها، وفي اللحظة دي بيبدأ مع بعض: البلاتة، والمات، والأيقونة، والكاميرا. ده نفس قاعدة الأوفرلابنج (اللي بعده يبدأ واللي قبله في الذيل البطيء).
- **الكتابة:** بتبدأ 70 والكاميرا لسه بتتحرك (لحد 108).
- **التتابع بعد الإرسال:** Send بيتضغط في 87، والبابل بعده بـ 4 فريم (91)، والرد بعده بـ 5 فريم (96).

## الشيبس والنصوص
- **Card:** جروب "Square"، فيه Rect ‏592×592 بـ Roundness ‏83، و Fill أسود.
- **Card Selection Stroke:** ‏Rect ‏560×560 بـ Roundness ‏82، و Stroke ‎#141414 ‏(0.08) عرضه 3، و Scale ‏128.205.
- **Icon Plate (back) و Panel Matte:**
  - الجروب "Group 1"، و Fill ‎#FAF9F5 ‏(0.98, 0.976, 0.961).
  - البلاتة عليها Drop Shadow: أسود، Opacity ‏30، و Direction ‏180، و Distance ‏18، و Softness ‏70.
- **Claude Icon (back):** ‏claude-icon.png ‏(2040×2048)، و Anchor (1020, 1024).
- **UI Chat Bar:**
  - Position (50, 450, ‎-3)، و Rect ‏820×190 عند (0, ‎-95) بـ Roundness ‏30.
  - Fill أبيض، و Stroke ‎#E0DDD4 ‏(0.88, 0.865, 0.83) عرضه 2.
- **UI Send:**
  - Position (365, ‎-55, ‎-1)، و Rect ‏58×58 بـ Roundness ‏14، و Fill ‎#D97757 ‏(0.851, 0.467, 0.341).
  - السهم «↑» بخط Arial ‏36 أبيض في النص، و Position (0, 12, ‎-1).
- **UI Model:** «Opus 5.5  ˅» بخط Arial ‏28، محاذاة يمين، لون ‎#6B675E ‏(0.42, 0.404, 0.369)، و Position (290, ‎-42, ‎-1).
- **UI Plus:** «+» بخط Arial ‏50 في النص، بنفس الرمادي، و Position (‎-366, ‎-36, ‎-1).
- **UI Placeholder:** «How can I help you today?» بخط Georgia ‏34، محاذاة شمال، لون ‎#9A968C ‏(0.604, 0.588, 0.549)، و Position (‎-374, ‎-122, ‎-1).
- **UI Script:**
  - Box Text مقاسه 752×120، و Box Pos (‎-376, ‎-190).
  - الخط IBM Plex Sans Arabic Regular ‏34، و Leading ‏48، محاذاة شمال، والاتجاه RTL، واللون ‎#1F1E1D.
  - Position اللاير (0, 32, ‎-1).
  - الأنيميتور "Typing": ‏Opacity ‏0، و Range Selector (Percentage / Characters / Add / Square، و Smoothness ‏100).
- **UI User Bubble:** ‏Position (460, ‎-310, ‎-3)، والجروب "Bubble" فيه Rect ‏403×74 عند (‎-201.5, 0) بـ Roundness ‏24، و Fill ‎#F0EEE6. الـ Anchor على طرفها اليمين، فبتكبر من اليمين.
- **UI User Msg:** نفس النص، بخط Regular ‏34، في النص، RTL، و Anchor (‎-0.595, ‎-9.01)، و Position (‎-201.5, 0, ‎-2).
- **UI Claude Reply Video:** ‏Position (‎-40, 25, ‎-3). الجروبات من فوق لتحت:

  | الجروب | Rect | المكان | Roundness | Fill |
  |---|---|---|---|---|
  | Pause L | ‏22×78 | (‎-20, 0) | 8 | أبيض |
  | Pause R | ‏22×78 | (20, 0) | 8 | أبيض |
  | Pause Circle | ‏140×140 | — | 70 | أبيض 16% |
  | Progress | ‏230×6 | (‎-175, 150) | 3 | ‎#D97757 |
  | Track | ‏580×6 | (0, 150) | 3 | أبيض 25% |
  | Card | ‏640×360 | — | 28 | ‎#1F1E1D |

- **الكلمات:**
  - الخط IBM Plex Sans Arabic Bold، أبيض، في النص، والفقرة LTR (Universal Composer).
  - كلهم في Z ‏‎-70 جوه مساحة Card، يعني قدام الكارت.

  | الكلمة | المقاس | Anchor | Position |
  |---|---|---|---|
  | لأن | 92 | 0 | (163.254, ‎-33.078) |
  | دي | 92 | 0 | (28.52, ‎-33.078) |
  | أصلاً | 92 | (‎-0.092, 0) | (‎-134.734, ‎-33.078) |
  | شغلانة | 150 | (0.75, ‎-53.25) | (0, 87.388) |

## اللوك
- **Adjustment Layer 1:** ‏Posterize Time ‏20fps، فالحركة كلها بتتحرك بإحساس 20 فريم.
- **Bottom Blur (Adjustment):** في أعلى الكومب، وعليه Camera Lens Blur بالإعدادات دي:
  - Radius ‏15، و Iris Shape ‏4، و Roundness ‏0، و Diffraction Fringe ‏100.
  - Blur Map Layer هو لاير الـ Blur Map، و Channel ‏1، و Placement ‏1، و Focal Distance ‏0.
  - Invert Blur Map شغال، و Threshold ‏0.8، و Repeat Edge Pixels شغال، و Linear Working Space شغال.
- **بري كومب الـ Blur Map:**
  - المقاس 1080×1920، والمدة 571 فريم.
  - جواه Black Solid، وفوقه White Solid عليه ماسك بيضاوي مركزه (541, 951) ونص قطره حوالي 117، و Feather ‏65.
  - الـ White Solid عليه Scale ‏385%.
  - اللاير بتاعه مخفي في الكومب الرئيسي، و Opacity ‏78.
  - النتيجة إن النص حاد والأطراف مبلّرة.
