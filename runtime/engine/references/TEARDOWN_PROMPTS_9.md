# برومبتات «teardown» التسعة — قالب للتنين (2026-11-12)

المصدر: مقال Elvar (@elvar_official) على X، ومهارته https://github.com/elvarofficial/teardown (MIT). النص الإنجليزي بتاعه كما هو؛ العربي تحته ملاحظات التنين.
**اتجرّب جزئيًا:** أمثلة المستودع التلاتة اتبنت هنا واتصورت لقطات منها؛ البرومبتات نفسها (بناء ماكينة جديدة) ماتجربتش، والفيديو بطيء جدًا من غير كارت شاشة. القالب ده للاستخدام على جهاز صاحب التنين في Claude Code، أو بمحرك التنين + Three.js المتضمّن.
غيّر كل اللي بين [أقواس]. معيار صاحب التنين: 9:16، 30 fps، عربي — عدّل الخطوتين 4 و8 على كده.

## 0. التثبيت (على جهازه)
```
npx skills add elvarofficial/teardown -g -a claude-code
cd ~/.claude/skills/teardown && npm install && npx playwright install chromium
```
محتاج Node 20+، وffmpeg وPython 3 للفيديو والصوت.

## 1–2. اختار الماكينة وهات مرجع
ماكينة ليها **مدخل واحد متحرك** وأرقام حقيقية + صورة واحدة (قطاع من كتالوج، صورة، كليب). من غير مرجع بتطلع «لعبة عامة».

## 3. ابنِ الماكينة
```
/teardown Build [the Cessna 337 main landing gear] as an interactive 3D simulator. Reference attached: [a cutaway drawing of the gear].

Build it from code in real units: [the main plate, the hydraulic actuator, the rack, the pinion on its output shaft, the universal joints, the side tubes, the spring legs and the wheels].

Before you draw anything, write the model as pure functions of one input: [stroke from 0 to 1]. Use the real numbers: [the rack travels 201 mm, the pinion has 32 teeth at module 4 mm, so the legs turn exactly 180°]. Check them by hand and show me the check. If you are not sure a number is real, say so and tell me where it comes from.

Every part, every panel and every label reads from that one model. Nothing is animated by hand.
```

## 4. ابنِ اللوحة
```
Lay out a console around the machine at 1600×900:
- the title and the main live number top left, big: [engine speed in rpm]
- live charts that move with the machine: [valve lift over 720° of crank, the pressure-volume loop of the tracked cylinder]
- a schematic panel that redraws the mechanism in 2D from the same model
- one button per subsystem: isolate it, cut it, show it alone
- camera views as buttons: [hero, front, side, top, inside the valley]
- callouts with thin leader lines into the parts they name
Every panel redraws from the frame's state. No number on screen is typed in.
```
للتنين: بدّل `1600×900` بـ `1080×1920` (الماكينة في التلتين اللي فوق، واللوحات تحت)، والعناوين بالعربي.

## 5. الشكل
```
Style: a clean study model on a pale studio.
- light background, soft shadows on an invisible floor, one accent colour for the part that is working right now
- the machine fills 60 to 70% of its view
- dark parts glossy, liners glass, metal roughness at least 0.45 so it never streaks white
- if a part is near-white, give it a thin ink outline or a darker ground
- pick the camera for the mechanism: if it collapses into a lattice face-on, use a 3/4 view
```

## 6. راجعه زي ناقد
```
Before you show me anything:
1. Render a still at every beat of the tour and read each one: a part passing through another, a part floating off its mount, a label covering what it names, a number that disagrees with the pose.
2. Scrub every transition at 0.2 s steps and look for a jump.
3. Fix collisions with a number in the parameter block. Never hide them with the camera.
Tell me what you checked and what you fixed. Show me the stills.
```

## 7. صفحة بتتساق
```
Make the simulator a page people drive:
- the tour from the film plays by itself, with a cursor that walks to each button and presses it
- any click, drag, scroll or key hands control to the visitor; 25 seconds of quiet hands it back
- drag to orbit, scroll to zoom, a key to hide the panels
- warm every shader before the first frame so the page never freezes
- test it on an integrated GPU and add quality steps: no ambient occlusion, a lower pixel ratio, smaller shadows, panels redrawn every other frame
```

## 8. فيديو وصوت
```
Record the tour: render(t) has to be a pure function of time, so draw every frame at 60 fps at 1920×1080 in headless Chrome and pipe it into ffmpeg as H.264, yuv420p, faststart. Then show me a contact sheet of every beat.
```
```
Score it in code on the same timeline: [Am9 chords at 92 bpm, a soft thump on every power stroke so the beat tightens when the throttle opens, a quiet click on every button press, rising air under the throttle drag]. Master to -14 LUFS with the true peak under -1 dB and mux it into the video.
```
للتنين: `30 fps at 1080×1920`، CRF 17 preset slow، وبعدها `dragon.py verify`.

## 9. النشر
```
Publish the simulator as a page:
- keep the HTML under 1 MB; move any large model out as a file next to the page
- a 1200×630 preview card from the best frame, with absolute image URLs
- deploy it to Vercel
```
النشر مايتعملش إلا بطلب صريح من صاحب التنين.

## إضافة: خليهم يكسروه
```
Add one slider for [the wind, 0 to 15 m/s] and run the model live when it moves: [a light breeze barely turns the crank, a gale makes the legs blur]. Show it on the same panels.
```

## 5 ماكينات مقترحة في المقال لسه ماتعملتش
ترس الدراجة على 11 سن · ميزان ساعة ميكانيكية 4 Hz · دفرنس عربية في ملف · ماكينة خياطة بتعمل غرزة · دراع حفار بيحفر جردل.
