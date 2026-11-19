# المونتاج الإبداعي (Creative Montage)

> القاعدة الأولى: كل قطعة (cut) قرار. لو مفيش سبب للقطعة غير "الأغنية بتقول كده" يبقى مفيش سبب.
> الملف ده للتفكير والتنفيذ المتقدم. الأساسيات (trim, concat, export) معروفة.

## الفهرس
1. قواعد المونتاج كاختيارات تعبيرية
2. الإيقاع والـ pacing
3. المونتاج اللي بيقوده الصوت
4. 25 فكرة transition مش presets
5. Speed ramp / freeze / split / echo / reverse / time-remap
6. خاص بالريلز (9:16)
7. وصفات ffmpeg
8. Anti-patterns
9. Checklist نقد المونتاج (10 نقط)

علامات: `[V]` = الأمر متراجع نظرياً لكن لازم تجرّبه على clip قصير قبل ما تعتمد عليه. أي حاجة مش معلّمة `[V]` فهي صيغة قياسية معروفة. نسخة ffmpeg مهمة (xfade محتاج 4.3+، `normalize` في amix محتاج 7.1+).

---

## 1) قواعد المونتاج كاختيارات تعبيرية

### أنواع القطع
- **Match cut**: قطعة بتربط لقطتين بحاجة مشتركة. أربع أنواع:
  - *Graphic*: شكل واحد يتحول (قمر -> لمبة، عجلة -> أسطوانة). اللقطة التانية تبدأ بنفس مكان/حجم الشكل في الفريم. اعمل overlay للفريم الأخير على الأول (opacity 50%) وتأكد إن الشكل متطابق.
  - *Action*: حركة بتبدأ في لقطة وتكمل في التانية (إيد بترمي، إيد تانية بتمسك في مكان تاني). اقطع في منتصف الحركة، مش في أولها.
  - *Sound*: صوت واحد يعدّي من مشهد لمشهد (صوت منبه -> صفارة قطر). الصوت بيكمّل قبل الصورة بـ 2-4 فريمات.
  - *Idea*: فكرة بتتكرر بصورتين مختلفتين (أب بيعلّم ابنه -> الابن بيعلّم تلميذه). ده أقوى نوع في أفلام التكريم لأنه بيقول "الأثر مستمر" من غير كلام.
- **J-cut / L-cut**: الصوت بيسبق الصورة (J) أو بيفضل بعدها (L). بيخلي القطع ناعم وبيخلي المشاهد "ماشي مع" مش "اتنقل". استعمله في أي حوار أو voiceover. القاعدة: 6-12 فريم فرق، أكتر من كده ممكن يربك.
- **Smash cut**: قطع حاد من هدوء لصخب (أو العكس) من غير تمهيد. يشتغل بس لو فيه تباين حقيقي في الصوت والصورة مع بعض. مرة واحدة في الفيلم، مرتين بالكتير.
- **Jump cut**: قطع في نفس اللقطة مع تغيير بسيط. استخدمه كـ *أسلوب* (ضغط وقت، توتر، ثرثرة) مش كـ حل لحذف تلعثم. عشان يبان مقصود: غيّر الـ scale 8-15% في كل قطعة (punch-in بالتبادل).
- **Cross-cutting**: تناوب بين حدثين متزامنين أو متوازيين. الفكرة إن المعنى بيطلع من التصادم. بيزيد التوتر لما تقصّر طول اللقطات كل دورة.
- **Cutting on action**: اقطع وسط الحركة، العين بتنسى القطعة. ده أساس "invisible editing".
- **Invisible vs. visible editing**: invisible = القصة أهم من الأسلوب (حوار، توثيقي). visible = القطعة نفسها جزء من الشكل (ميوزك فيديو، إعلان). اختار واحد لكل مقطع، وماتخلطش بدون سبب.

### Kuleshov effect (عملياً)
نفس الوش + لقطة مختلفة = معنى مختلف. يعني: **اللقطة اللي بعد الوش هي اللي بتقول الشخص حاسس بإيه**. استخدمه لما عندك لقطة وش محايدة واحدة بس: وش + أكل = جوع، وش + طفل = حنان، وش + ملعب فاضي = حنين. في فيلم تكريم: وش البطل (ثابت) -> صور طفولته -> وشه تاني. المعنى جاي من التسلسل، مش من الأداء.

### أنواع Soviet montage (Eisenstein) بشكل عملي
| النوع | بيقطع على إيه | مثال تطبيقي |
|---|---|---|
| Metric | طول اللقطة بالفريمات بغض النظر عن المحتوى | كل لقطة 12 فريم بالظبط لتسريع الإحساس |
| Rhythmic | حركة جوه اللقطة (إيقاع الحركة) | اقطع لما الرجل تلمس الأرض، مش على beat الأغنية |
| Tonal | المزاج العام للقطة (إضاءة، لون، حرارة) | تسلسل لقطات دافية -> باردة = فقد |
| Overtonal | مزيج الثلاثة اللي فوق مع بعض | مقطع الذروة: إيقاع + حركة + لون كلهم بيتصاعدوا |
| Intellectual | لقطتين = فكرة تالتة مش في أي منهما | عامل + ترس + صوت ماكينة = "النظام بيكسّر الإنسان" |

قاعدة الاستخدام: قرر النوع الغالب في كل مقطع قبل ما تبدأ. لو مقطعك Metric، ماتكسرش الطول المنتظم إلا في الذروة.

---

## 2) الإيقاع والـ pacing

### منحنى طول اللقطات (shot-length curve)
- ارسم المنحنى على ورقة قبل المونتاج: المحور الأفقي الوقت، الرأسي طول اللقطة.
- شكل شائع للريل 30 ثانية: بطيء قليل (hook) -> متوسط -> يتسارع -> **توقف** -> قطعة أخيرة طويلة (payoff).
- التسارع بيشتغل بالنسب: 2.0s -> 1.4s -> 1.0s -> 0.7s -> 0.5s. بعدها لازم راحة، الأذن بتتشبع.
- كل 3-4 قطعات سريعة محتاجة لقطة "تنفس" 1.2-2s.

### التنفس (breathing / rests)
- لقطة هادية بعد الذروة مش ضعف، هي اللي بتخلي الذروة تتحس.
- مفيش راحة = مفيش إيقاع. السرعة المستمرة بتبقى مسطحة.
- في الفيلم الطويل: لقطة تنفس كل 20-30 ثانية.

### Tension-release map
اعمل جدول بسيط:
```
t(s) | tension 0-10 | shot len | sound        | note
0-2  | 6            | 0.8      | hit + whisper | hook
2-8  | 4            | 1.6      | pad           | build
8-14 | 7            | 0.7      | drums in      | ramp
14-15| 2            | silence  | room tone     | breath
15-22| 9            | 0.4-0.6  | full          | peak
22-30| 3            | 3.0      | piano + VO    | payoff / loop
```
الخطة دي بتتحول لـ EDL بالأرقام، مش بالإحساس.

### Beat-sync من غير ما يبقى ميكانيكي
- **Cut on downbeat**: آمن وقوي، استخدمه في الذروة والـ drop.
- **Syncopation**: اقطع على off-beat (النص بين beats) لمقاطع الـ groove. بيدي إحساس مقصود وإنساني.
- **Cut before the beat**: اقطع 2-4 فريمات *قبل* الـ beat بقليل (الصورة تسبق الصوت). العين بتسجّل القطعة والأذن بتأكّدها، فتحس إنه "سينك مظبوط" أكتر من القطع الحرفي. ده أهم نصيحة في الملف ده.
- اكسر النمط: لو القطعات على كل beat لـ 8 بارات، اتخطى beat واحد أو اقطع على نص beat. ثبّت الشكل ثم كسّره.
- مش لازم تقطع على كل beat. القطع كل 2 beat أو كل بار ونص، مع حركة داخل اللقطة على الباقي، أحسن.
- حرّك الصورة على beats (zoom، flash، shake) وقطّع على phrases.

### librosa: beats و onsets
```python
import librosa, json
y, sr = librosa.load("song.wav", sr=None, mono=True)
tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units="time")
onsets = librosa.onset.onset_detect(y=y, sr=sr, units="time", backtrack=False)
# قوة الـ onset عشان تختار القطعات القوية بس
env = librosa.onset.onset_strength(y=y, sr=sr)
times = librosa.times_like(env, sr=sr)
# downbeats تقريبية: كل 4 beats من أول beat قوي (راجعها بالسمع)
downbeats = beats[::4]
json.dump({"tempo": float(tempo), "beats": beats.tolist(),
           "onsets": onsets.tolist(), "downbeats": downbeats.tolist()},
          open("beats.json", "w"))
```
- استخدم `beats` للإيقاع الثابت، `onsets` للضربات الفعلية (drums, hits).
- اطرح 0.05-0.08s من كل وقت قطع (cut before the beat).
- افلتر الـ onsets بأعلى 30% في `env` عشان ماتقطعش على كل صوت صغير.
- راجع بالسمع دايماً: tempo detection بيغلط (نص أو ضعف السرعة).

---

## 3) المونتاج اللي بيقوده الصوت

- **Sound bridge**: صوت المشهد الجاي يبدأ قبل الصورة بنص ثانية (J-cut)، أو صوت المشهد القديم يفضل (L-cut). بيخلي أي transition يبان ناعم من غير مؤثر بصري.
- **Silence drop**: قبل الذروة، اقطع كل الصوت 0.3-0.8s (حتى الموسيقى). السكوت أعلى صوت. ارجّع الصوت بقطعة بصرية حادة.
- **Risers**: ابنيها 1-4 ثواني قبل الـ drop. اضبط نهايتها بالظبط على الـ downbeat. riser من غير drop = إحباط.
- **Whooshes**: استخدمها نادراً (3-4 مرات في الفيلم). حطها على حركة فيها فعلاً سرعة، مش على كل قطعة. اخفض مستواها 6-10dB عن الـ dialogue، وغيّر الـ pitch/النوع كل مرة.
- **Ducking**: الموسيقى تنزل 8-12dB تحت الصوت البشري، بـ attack سريع (10-30ms) و release أبطأ (300-500ms). (وصفة sidechaincompress تحت.)
- **Room tone**: دايماً سجّل أو خد 10 ثواني هدوء من الموقع. املا بيها الفجوات بين اللقطات، لأن "سكوت ديجيتال" تام = بيبان إنه قطع. لو مفيش، استخدم ambience خفيف جداً (-40 dBFS).
- **Foley صغير**: خطوة، قماش، نفس. بتدي واقعية أكتر من أي موسيقى.
- **Layer نظام**: (1) dialogue/VO (2) موسيقى (3) ambience/room (4) SFX نقاط (5) accents. لو مش سامع طبقة، مش محتاجها.

---

## 4) 25 فكرة transition مش presets

الشغل المشترك: التحضير في التصوير/الاختيار أهم من الفلتر. `A` = لقطة خارجة، `B` = لقطة داخلة.

1. **Shape-morph**: شكل (دايرة/مستطيل/حرف) يكبر ويكشف B. ffmpeg: `xfade=transition=circleopen` أو ماسك مرسوم بـ `geq`/alphamerge. للتحكم الكامل: ولّد mask متحركة في Blender/Python وركّبها `alphamerge`.
2. **Object wipe**: جسم بيعدّي قدام الكاميرا (إيد، ظهر شخص، سيارة) يغطي الفريم، وعليه B تبدأ. اقطع وقت التغطية الكاملة. من غير فلتر، بس اختيار لقطات.
3. **In-camera match**: نهاية A وبداية B فيهم نفس الشكل/اللون/الاتجاه في نفس المكان بالفريم. صوّرها كـ pair، أو اختارها من الأرشيف بـ overlay مقارنة.
4. **Light flash on beat**: فريم أبيض 2-4 فريمات بيبدأ قبل الـ beat بفريم. (وصفة flash تحت.)
5. **Typographic transition**: كلمة ضخمة بتملا الفريم، الـ B ظاهرة جواها (text كـ mask). `drawtext` على لون أسود ثم `alphamerge`/`blend` أو اعمله في Python/Pillow وركّب. بالعربي استخدم خط Ruqaa/Cairo/Amiri.
6. **Freeze + ink**: جمّد آخر فريم، حبر أسود ينتشر عليه ويكشف B. محتاج ink-bleed footage (overlay) + `blend=all_mode=multiply` أو `colorkey`/`alphamerge`.
7. **Rack-focus transition**: A تفقد البؤرة تدريجي (`gblur` بـ sigma بيكبر)، B تبدأ blur وتتضح. `gblur=sigma='min(t*20,30)':steps=2` على A و `gblur` بيصغر على B ثم `xfade=fade`.
8. **Speed-ramp مع motion blur**: A تسرّع بشدة، قطعة وهي blurry، B تبدأ سريعة وتهدّى. استخدم `tmix`/`minterpolate` للـ blur. (قسم 5.)
9. **Whip pan**: حركة كاميرا سريعة أفقية في آخر A وأول B. ffmpeg: `crop` متحرك بتعبير `x` + `gblur=sigmaV=0` (blur أفقي بس) أو `xfade=transition=slideleft` مع blur. الأفضل تستخدم whip pan حقيقي.
10. **Luma wipe**: صورة grayscale (texture، ورق، دخان) تتحكم في اللي يتكشف. `xfade` مدعوم بـ custom expression، أو `blend` مع luma map عبر `threshold` متحرك. `[V]`
11. **Frame-in-frame (شاشة داخل شاشة)**: B تظهر جوه شاشة موبايل/نافذة في A، ثم نكبّر لحد ما تملا الفريم. `overlay` + `scale` بـ `eval=frame` لتكبير تدريجي.
12. **Zoom through**: نكبّر لجوه A (عين، باب، ثقب) والـ B تتفتح من الظلام. `scale` متحرك + `fade` أسود قصير.
13. **Black-hole / dark pass**: لقطة B تبدأ من جسم أسود عابر (جاكيت، كتف). كالـ object wipe بس مع إخفاء فوري.
14. **Glitch على الـ beat**: RGB split + displacement 3-5 فريمات. `rgbashift=rh=-8:bh=8` + `noise` + `tblend`. استخدمه بس لو الثيم رقمي.
15. **Mirror / kaleidoscope reveal**: A تنعكس وتتكرر ثم تتحول لـ B. `split` + `hflip` + `hstack` ثم `xfade`.
16. **Time-freeze reveal**: الكل متجمد إلا حاجة واحدة بتتحرك (فتاة تجري)، ثم تتحرك B. `loop`/`tpad` للتجميد + ماسك.
17. **Pixel/halftone melt**: `xfade=transition=pixelize` أو `hlslice/vuslice` مع blur خفيف. الجمال في المدة القصيرة (6-10 فريمات).
18. **Light leak / lens flare**: overlay لتسريب ضوء في وقت القطع. `blend=all_mode=screen`. حاجة أصلية أفضل من تحميل جاهز، لو قدرت صوّر ضوء خلف إيدك.
19. **Sound-first cut**: الصورة ثابتة والصوت هو اللي ينقل (J-cut مبالغ فيه)، ثم الصورة تقفز. صفر فلتر، أقوى تأثير.
20. **Scale-match (zoom match)**: A تنتهي بوش قريب جداً، B تبدأ بنفس حجم الوش لشخص تاني. اضبط الـ scale بـ `scale`+`crop` عشان المسافة بين العينين تتطابق.
21. **Color-flood**: A تتغمر بلون واحد (أحمر/ذهبي) ثم B تنبثق منه. `colorize`/`eq` + `fade=t=out:color=...` وبعدين `fade in`.
22. **Paper/ink-line wipe**: خط يرسم نفسه عبر الفريم ويكشف B خلفه. ارسمه بـ Python (OpenCV) كـ mask متحركة -> `alphamerge`.
23. **Rotating cube/page turn**: `xfade=transition=` (مفيش cube جاهز في ffmpeg)، استخدم Blender (plane flip) أو `perspective` يدوي. `[V]`
24. **Beat-stutter**: اعمل 3-4 تكرارات قصيرة للفريم الأخير من A على الـ beat (8 فريمات، 4، 2)، ثم B. `loop` + `trim` + `concat`.
25. **Silence-cut**: اسكت، اقطع لـ B، ثم ارجع بالصوت. مفيش مؤثر صورة. الأقوى لأي لحظة عاطفية.

اختبار الجودة: لو شيلت الـ transition وفضلت القطعة شغالة، الـ transition زيادة. لو الـ transition هي اللي بتعمل المعنى، فهي صح.

---

## 5) Speed ramp / freeze / split / echo / reverse / time-remap

| الأداة | تخدم المعنى لما... | ماتستخدمهاش لما... |
|---|---|---|
| Speed ramp | فيه لحظة تأثير (قفزة، لكمة، ابتسامة) تحب تضغطها أو تمططها | اللقطة نفسها مفيهاش حركة |
| Freeze frame | عايز المشاهد يتأمل لحظة، أو تضع عنوان/اسم | كحشو في آخر اللقطة |
| Split screen | في مقارنة/توازي أو شخصين بيتكلموا بعيد | الفريم 9:16 مزدحم |
| Repetition / echo | فكرة هوسية، صدى ذاكرة، تأكيد كلمة | بدون تغيير بسيط في كل تكرار |
| Reverse | تراجع، ندم، ذكرى بترجع، سحر | تحرك طبيعي واضح عكسه (ناس بتمشي) |
| Time-remap | عايز تتحكم في الإحساس بين لحظتين | بتعوض لقطة ضعيفة |

نصائح:
- Ramp ناجح = *سرعة -> بطء قبل الـ hit بـ 3-5 فريمات -> hit على البيت -> رجوع سريع*.
- بطء بدون optical flow/frame blending بيتقطع. صوّر 50/60fps لو ناوي تبطّأ.
- Freeze: خلّي الصوت يكمل أو يسكت، بس مايقطعش فجأة.
- Echo في ffmpeg: انسخ اللقطة بـ `tpad` (تأخير) و `blend=all_mode=lighten` أو `addition` بشفافية 40%. `[V]`
- Split screen: `hstack`/`vstack` أو `xstack`. في 9:16 استخدم تقسيم رأسي (فوق/تحت) بدل جنب بجنب.

---

## 6) خاص بالريلز (9:16)

### أول 1.5 ثانية
- فريم أول *يشتغل كـ thumbnail*: وش قريب، حركة، نص كبير، أو سؤال بصري.
- ماتبدأش بلوجو أو fade من الأسود. ابدأ في منتصف الحدث (in medias res).
- الصوت يبدأ فوراً: hit، كلمة، نفس. مفيش صمت أول 0.3s.
- استخدم "الجملة المعلّقة": قول النتيجة أو السؤال الأول وارجع تشرحه.
- جرّب الـ hook كـ flash-forward: اعرض أقوى لقطة في الأول 1s ثم ارجع لبداية الحكاية.

### Loopable endings
- آخر فريم يشبه أول فريم (نفس التكوين، نفس اللون). وآخر كلمة تكمل جملة بتبدأ في الأول.
- صوتياً: الموسيقى تنتهي على نفس النغمة اللي بتبدأ بها. fade قصير جداً أو قطع على beat.
- جرّب: `[V]` ركّب آخر 0.5s فوق أول 0.5s بـ crossfade عشان لوب سلس لو الأداة بتسمح.
- الأفضل تنهي بسؤال أو نص ناقص يخلي المشاهد يعيد.

### إيقاع الكابشن (captions rhythm)
- 2-4 كلمات في الشاشة. كل كلمة تظهر مع نطقها (word-level timestamps من whisperx).
- كلمة التأكيد: أكبر + لون مختلف + pop بسيط (scale 100 -> 112 -> 100 في 4 فريمات).
- الكابشن في الثلث الأوسط/السفلي بعيد عن أزرار المنصة (تجنب آخر 15% و يمين 12%).
- مايبقاش في كابشن لكل كلمة بنفس الشكل. غيّر الشكل مع المعنى (همس = صغير، صراخ = كبير).

### Retention dips (أماكن هبوط الانتباه)
- 3s: لو الـ hook ماتحققش.
- منتصف الفيديو: لو الإيقاع ثابت. حط pattern interrupt هنا (تغيير زاوية، zoom، تغير صوت، سؤال).
- قبل النهاية: لو الـ payoff متأخر.
- حل: كل 3-5 ثواني حاجة جديدة (لقطة، كلمة، لون، صوت). ما تكررش نفس نوع التغيير مرتين ورا بعض.

---

## 7) وصفات ffmpeg

كل الأمثلة بصيغة سطر واحد، على Windows استخدم `^` (cmd) أو backtick (PowerShell) أو سطر واحد. المدخلات `a.mp4` و `b.mp4` بنفس الأبعاد والـ fps. لو مختلفين: `scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1`.

### xfade
`offset` = (مدة A) - (مدة الـ transition). مثال: A=5s، transition=0.5 -> offset=4.5.
```
ffmpeg -i a.mp4 -i b.mp4 -filter_complex "[0:v][1:v]xfade=transition=wipeleft:duration=0.5:offset=4.5,format=yuv420p[v];[0:a][1:a]acrossfade=d=0.5[a]" -map "[v]" -map "[a]" -c:v libx264 -crf 18 out.mp4
```
أنواع مفيدة للتجربة: `fadeblack`, `fadewhite`, `circleopen`, `circleclose`, `radial`, `smoothleft`, `slideup`, `pixelize`, `zoomin`, `hlslice`, `vuslice`, `squeezev`, `distance`, `dissolve`.

Custom expression (تحكم كامل):
```
ffmpeg -i a.mp4 -i b.mp4 -filter_complex "[0:v][1:v]xfade=transition=custom:duration=0.6:offset=4.4:expr='if(gt(P,X/W),A,B)'" out.mp4
```
`[V]` (P تقدم الـ transition من 1 لـ 0، X/W الموضع الأفقي. جرّب وعدّل الاتجاه.)

سلسلة 3 لقطات (offsets تراكمية: offset2 = durA + durB - 2*d):
```
ffmpeg -i a.mp4 -i b.mp4 -i c.mp4 -filter_complex "[0:v][1:v]xfade=transition=fadewhite:duration=0.4:offset=4.6[v01];[v01][2:v]xfade=transition=circleopen:duration=0.4:offset=8.8[v]" -map "[v]" out.mp4
```

### Speed ramp بقطع setpts (تسريع/تبطيء في الوسط)
مثال: 0-2s عادي، 2-3s بطيء x0.25، 3-6s عادي. بدون صوت (الصوت يتعامل لوحده).
```
ffmpeg -i in.mp4 -filter_complex "[0:v]split=3[a][b][c];[a]trim=0:2,setpts=PTS-STARTPTS[v1];[b]trim=2:3,setpts=(PTS-STARTPTS)*4,minterpolate=fps=60:mi_mode=mci:mc_mode=aobmc[v2];[c]trim=3:6,setpts=PTS-STARTPTS[v3];[v1]fps=60[w1];[v3]fps=60[w3];[w1][v2][w3]concat=n=3:v=1:a=0[v]" -map "[v]" -an -c:v libx264 -crf 18 ramp.mp4
```
`[V]` (minterpolate بطيء الحساب. لو الجودة مش لازمة استبدله بـ `fps=60` فقط.)
تسريع x2 جزء: `setpts=(PTS-STARTPTS)/2`. صوت مسرّع: `atempo=2.0` (بين 0.5 و 2.0 لكل filter، سلسل لو أكتر).
ramp تدريجي حقيقي = قسّم لـ 6-10 segments بسرعات متدرجة (1, 0.8, 0.6, 0.45, 0.3) أو استخدم Python/MoviePy لتوليد الـ filtergraph.

Motion blur صناعي على جزء سريع: `tmix=frames=3:weights='1 2 1'` أو `minterpolate` ثم `tblend=all_mode=average`.

### Freeze frame
تجميد آخر فريم 1 ثانية (بعد trim):
```
ffmpeg -i in.mp4 -vf "trim=0:3,setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration=1" -an freeze_end.mp4
```
تجميد في نص الفيديو (عند 2.0s لمدة 1s):
```
ffmpeg -i in.mp4 -filter_complex "[0:v]split=3[a][b][c];[a]trim=0:2,setpts=PTS-STARTPTS[v1];[b]trim=start=2:end=2.04,setpts=PTS-STARTPTS,loop=loop=29:size=1:start=0[v2];[c]trim=start=2,setpts=PTS-STARTPTS[v3];[v1][v2][v3]concat=n=3:v=1:a=0[v]" -map "[v]" -an freeze_mid.mp4
```
`[V]` (عدّل عدد الـ loop حسب fps. المثال لـ 30fps ≈ 1s. الفريم الواحد = trim قصير، ممكن تحتاج `select='eq(n,60)'` بدل trim للدقة.)

### Zoom punch-in
تكبير سريع 12% بين 2.0s و 2.2s وبيفضل مكبّر:
```
ffmpeg -i in.mp4 -vf "scale=w='1080*(1+0.12*min(max((t-2)/0.2,0),1))':h='1920*(1+0.12*min(max((t-2)/0.2,0),1))':eval=frame:flags=bicubic,crop=1080:1920" -c:v libx264 -crf 18 punch.mp4
```
`[V]` (مدخل 1080x1920. الـ crop بيتمركز تلقائي. للرجوع للحجم الأصلي اجعل التعبير يعود لـ 0.) لو الأداء بطيء، استخدم `zoompan` بس حذر من الاهتزاز على الأعداد الصحيحة.

### Flash frame على beat
فلاش أبيض ناعم عند t=2.0s يتلاشى خلال ~0.2s:
```
ffmpeg -i in.mp4 -vf "eq=brightness='0.9*exp(-14*(t-2))*gte(t,2)':eval=frame" -c:v libx264 -crf 18 -c:a copy flash.mp4
```
`[V]` (لو eq رفض التعبير، استخدم `drawbox=x=0:y=0:w=iw:h=ih:color=white@0.9:t=fill:enable='between(t,2,2.06)'` وهو مضمون.)

### Letterbox 2.39 جوه 9:16
مصدر 16:9 -> شريط سينمائي 1080x452 وسط canvas 1080x1920 أسود:
```
ffmpeg -i in.mp4 -vf "scale=1080:-2,crop=1080:452,pad=1080:1920:0:734:black,setsar=1" -c:v libx264 -crf 18 -c:a copy cine.mp4
```
(734 = (1920-452)/2.) المساحة السودا فوق وتحت تستعمل للكابشن/العنوان. تحذير: الشريط الصغير بياخد ربع الشاشة بس، مناسب للمشاهد الهادية، مش للـ hook.

### Film grain
```
ffmpeg -i in.mp4 -vf "noise=alls=14:allf=t+u,eq=contrast=1.04:saturation=0.95" -c:v libx264 -crf 17 -c:a copy grain.mp4
```
خفيف: alls 8-14. الضغط على السوشيال بيمسح الجرين الخفيف، فاستعمله أعلى شوية من اللي تشوفه كويس على المونيتور.

### Sidechain ducking (الموسيقى تنزل تحت الصوت)
`0` = صوت المتحدث (voice.wav)، `1` = موسيقى (music.wav):
```
ffmpeg -i voice.wav -i music.wav -filter_complex "[0:a]asplit=2[vo][sc];[1:a][sc]sidechaincompress=threshold=0.04:ratio=8:attack=15:release=400:makeup=1[duck];[vo][duck]amix=inputs=2:duration=longest:dropout_transition=0,alimiter=limit=0.95[a]" -map "[a]" mix.wav
```
`[V]` (`amix` بيقسم الصوت على عدد المدخلات في النسخ القديمة. في ffmpeg 7.1+ استخدم `amix=...:normalize=0`. ظبط الـ threshold بالسمع.)
بديل ثابت بدون sidechain: `volume='if(between(t,2,6),0.25,1)':eval=frame` على الموسيقى.

### Loudnorm لـ -14 LUFS (سوشيال)
تمريرتين (الأدق):
```
ffmpeg -i in.mp4 -af loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json -f null -
```
خد القيم measured_I, measured_TP, measured_LRA, measured_thresh, offset من الـ JSON وحطها:
```
ffmpeg -i in.mp4 -af "loudnorm=I=-14:TP=-1.5:LRA=11:measured_I=-18.2:measured_TP=-3.1:measured_LRA=7.4:measured_thresh=-28.9:offset=0.5:linear=true" -c:v copy -c:a aac -b:a 192k out.mp4
```
(القيم أمثلة، استبدلها بقيمك.) تمريرة واحدة سريعة: `-af loudnorm=I=-14:TP=-1.5:LRA=11`.

### أدوات مساعدة
- Reverse: `-vf reverse -af areverse` (للقطات قصيرة فقط، بتحمّل الكل في الرام).
- Split screen رأسي: `[0:v][1:v]vstack=inputs=2` (بعد scale كل واحد لـ 1080x960).
- Echo بصري: `[0:v]split[a][b];[b]tpad=start_duration=0.2:color=black,format=yuva420p,colorchannelmixer=aa=0.4[e];[a][e]overlay` `[V]`.
- كشف القطع: `scenedetect -i in.mp4 detect-content list-scenes` ، وحذف الصمت: `auto-editor in.mp4`.

---

## 8) Anti-patterns

1. قطع على كل beat من أول الأغنية لآخرها.
2. transition مختلف في كل قطعة (معرض preset).
3. whoosh على كل حركة.
4. Zoom/shake دائم من غير سبب.
5. بطء بدون صوت يدعمه.
6. Speed ramp على لقطة مفيهاش حدث.
7. نص بيغطي الوش أو منطقة واجهة المنصة.
8. بداية بلوجو/عنوان/fade طويل في الريلز.
9. موسيقى عالية فوق الكلام (ducking ناقص).
10. لقطات أرشيف بجودات ولون مختلفين من غير توحيد grade.
11. جمل نص كاملة بتظهر مرة واحدة بدل كلمة بكلمة.
12. اللقطة الأخيرة تنتهي بـ fade-to-black طويل بيقتل الـ loop.
13. تطبيق Kuleshov عكسي: لقطة تدّعي إحساس والوش يقول عكسه.
14. استخدام اللقطة الأقوى في الأول ثم استنفاد الفيلم.
15. تجاهل الـ room tone والسكوت الرقمي بين القطعات.
16. تصدير بعد ضغط مرتين (تصدير من تصدير) -> جودة منهارة.

---

## 9) Checklist نقد المونتاج (10 نقط)

اسمع بدون صورة، بعدين شوف بدون صوت، بعدين الاتنين.

1. **Hook**: أول 1.5s فيها سبب للبقاء؟ (صورة + صوت)
2. **Clarity**: بعد 5 ثواني، المشاهد فاهم الفيلم عن إيه؟
3. **Rhythm curve**: فيه تسارع وراحة؟ ولا الإيقاع مسطح؟
4. **Cut motivation**: كل قطعة ليها سبب (حركة، صوت، فكرة، معنى)؟
5. **Continuity**: اتجاه الشاشة، النظرة، الإضاءة، اللون متسقين؟
6. **Sound**: الصوت والكلام واضحين، فيه room tone، الذروة فيها silence أو impact؟
7. **Transitions**: كل transition بتخدم المعنى؟ لو اتشالت، هل الفيلم يتأثر؟
8. **Text/captions**: مقروءة، في safe area، متزامنة، مش متكررة بنفس الشكل؟
9. **Payoff + loop**: النهاية بتدي إحساس مكتمل وبتخلي اللوب أو الإعادة طبيعية؟
10. **Fresh eye**: خد استراحة 20 دقيقة وشوفه مرة. إيه اللي هتشيله لو دقيقة واحدة بس؟ شيله.

قاعدة أخيرة: شيل 10% من اللي عملته. الأقوى دايماً هو الأقل.
