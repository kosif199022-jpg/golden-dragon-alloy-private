# الأجواء (Atmosphere / Mood) — مرجع «الإبداع المطلق»

الجو مش حاجة بتحطها فوق الشغل، الجو هو الإحساس اللي المشاهد بيطلع بيه. بنبنيه من طبقات كلها لازم تشد في نفس الاتجاه. لو طبقة واحدة بتقول حاجة تانية، الإحساس بيتكسر.

## الفهرس
1. [الـ Atmosphere Stack](#1-الـ-atmosphere-stack)
2. [Mood Matrix (20 جو)](#2-mood-matrix)
3. [Sound atmosphere](#3-sound-atmosphere)
4. [ffmpeg recipes للـ looks](#4-ffmpeg-recipes)
5. [Blender atmosphere](#5-blender-atmosphere)
6. [Atmosphere continuity + Checklist](#6-atmosphere-continuity)

> قاعدة ذهبية: اختار كلمة واحدة للجو («حنين دافي»، «رعب بارد») قبل أي أداة. كل قرار بعد كده يتقاس عليها.
> علامة «غير متحقق» (unverified) معناها: الأمر مكتوب صح syntax لكن لازم تجربه على اللقطة وتعدّل الأرقام بالعين.

---

## 1. الـ Atmosphere Stack

| الطبقة | بتتحكم في إيه | السؤال اللي تسأله |
|---|---|---|
| Light quality | صلب/ناعم، اتجاه، ارتفاع الشمس | الضوء بيحكي إيه؟ دافي ولا قاسي؟ |
| Color temperature & palette | 2700K دافي ... 7500K بارد، 3 ألوان بس | إيه اللون الغالب والتاني واللمسة؟ |
| Contrast / black level | الأسود مرفوع (مات) ولا عميق (crushed) | الظلام مخيف ولا حنين؟ |
| Haze / fog / particles | عمق، شعاع ضوء، غبار | فيه هوا بين الكاميرا والموضوع؟ |
| Weather | مطر، رمل، رطوبة، شمس | الطقس جزء من الإحساس؟ |
| Texture | grain، halation، bloom، vignette | الصورة نضيفة رقمي ولا فيها مادة؟ |
| Lens character | focal length، softness، flare، anamorphic | واسعة (توتر/عزلة) ولا tele (ضغط/حميمية)؟ |
| Pace / editing tempo | طول اللقطة، إيقاع القطع | هادي (تأمل) ولا سريع (قلق)؟ |
| Sound bed | room tone، ambience، foley | المكان بيتنفس؟ |
| Music | key، tempo، instruments، maqam | الموسيقى بتقود ولا بتسند؟ |
| Silence | غياب الصوت | فين الصمت اللي هيوجع؟ |

### قواعد سريعة
- **دفا/برودة:** دافي = ألفة، ذكرى، شمس. بارد = وحدة، خوف، ليل، تكنولوجيا. التضاد (دافي في البؤرة، بارد في الخلفية) بيعمل عمق عاطفي.
- **Black level:** الأسود المرفوع (lifted ~ 5-10%) = حلم/حنين/مات. الأسود العميق = دراما/لوكس/رعب.
- **Contrast:** عالي = قرار، صراع. واطي = هدوء، ضباب، حزن ناعم.
- **Saturation:** ماتزودش الكل. خلّي لون واحد يتشبع والباقي يتهدّى.
- **Focal length:** 18-24mm توتر وعزلة وبيئة. 35mm واقعي. 85-135mm حميمية وانفصال عن الخلفية.
- **Pace:** لقطات طويلة + حركة بطيئة = تأمل/حزن/رهبة. قطع على الإيقاع = فرح/طاقة. قطع غير منتظم = قلق.
- **Silence:** ثانية صمت بعد صوت عالي أقوى من أي score. استخدمه مرة أو اتنين في القطعة، مش أكتر.
- **Imperfection:** شوية grain وبهتان وضوء مش متظبط بيخلّوا الإحساس حقيقي. الكمال الرقمي بيبرّد الجو.

---

## 2. Mood Matrix

ملحوظة عن المقامات: الأوصاف دي ارتباطات شائعة في الذوق العربي، مش قوانين. المقام ممكن يتقال بإحساس تاني حسب الأداء. الـ HEX مقترحات بداية: اختار 3 (أساسي، ثانوي، لمسة).

### الجدول الأول — الصورة

| Mood | Light | Palette (HEX) | Grade | Texture | Camera / pace |
|---|---|---|---|---|---|
| حنين (Nostalgia) | شمس الأصيل ناعمة، practicals دافية | `#E8B87A` `#B5651D` `#F3E3C3` | أسود مرفوع، highlights دافية، sat واطي-متوسط | grain متوسط، halation خفيف، vignette | handheld ناعم، 35-50mm، لقطات طويلة، dissolves |
| رعب/ترقب (Dread) | مصدر واحد جانبي أو علوي، ظلال عميقة | `#0B1A1F` `#2E4A4F` `#7A0F0F` | black عميق، sat واطي، green-teal خافت | grain خشن، vignette تقيل | لقطات ثابتة، wide، push-in بطيء جدًا |
| رهبة/ملحمة (Awe/Epic) | ضوء ذهبي منخفض، god rays، backlight | `#F2C46D` `#1B2A41` `#FFF4D6` | contrast عالي، teal-orange | bloom على highlights، clean | wide 16-24mm، drone/crane، low angle، بطيء ثم يكبر |
| حميمية (Intimacy) | window light ناعم، shallow | `#D9A47A` `#5C3A2E` `#F5E6D3` | دافي، skin tones محمية | grain خفيف، bokeh ناعم | close-ups 85mm، handheld هادي، قطع قليل |
| حزن/شجن (Melancholy) | overcast، ضوء بارد منتشر | `#6F8296` `#2F3E4E` `#C9CED6` | sat واطي، blue-grey، أسود مرفوع | grain ناعم، soft | tele، static أو slow dolly، لقطات طويلة |
| انتصار (Triumph) | شمس عالية أو backlight قوي، rim | `#FFD166` `#C1121F` `#0B132B` | contrast وsat عاليين، ذهبي | bloom قوي، flare | low angle، slow-mo، قطع على الذروة |
| غموض (Mystery) | ضوء جزئي، silhouettes، shafts | `#1D2B3A` `#3E5C76` `#C9A227` | شبه monochrome + لمسة لون | haze، fog، grain | حركة جانبية بطيئة، reveals، rack focus |
| سكينة (Serenity) | ضوء الفجر/الغروب الناعم | `#A8D5BA` `#EDE6D6` `#7FB3D5` | pastel، contrast واطي | نضيف، soft glow | static، دولي بطيء، لقطات 6-10 ثواني |
| فوضى/طاقة مدينة (Urban energy) | نيون، سيارات، مصابيح مختلطة | `#FF2E63` `#08D9D6` `#252A34` | contrast عالي، sat عالي، mixed color temps | grain، lens flare، motion blur | handheld، whip pans، قطع سريع، wide |
| ليالي رمضان الروحانية | فوانيس، لمبات صفرا، ضوء دافي منخفض | `#E3A72F` `#0F3D3E` `#7B2D26` | دافي-ذهبي، بنفسجي/أخضر غامق في الضلال | bokeh فوانيس، glow، grain خفيف | لقطات بطيئة، tilt-up على الزينة، dissolves |
| حر الصيف المصري | شمس عمودية قاسية، ظلال حادة | `#F4D35E` `#EE964B` `#F95738` | highlights شبه محروقة، دافي، contrast عالي | heat shimmer، halation، haze أبيض | handheld، 35mm، لقطات قصيرة، وجوه عرقانة |
| إسكندرية الماطرة | سما رمادية، انعكاس على الأسفلت، لمبات شوارع | `#5B7083` `#2C3E50` `#D8A657` | بارد-أزرق، لمسة صفرا من الأنوار | رطوبة، bokeh مطر، soft | wide على الكورنيش، منظور من ورا إزاز، بطيء |
| عزلة الصحرا (Desert solitude) | شمس مسطحة أو golden hour طويل | `#D8A47F` `#8C5E3C` `#2B4C7E` | ألوان رمل، سما زرقا عميقة | نضيف، رمل متطاير، grain ناعم | wide جدًا، موضوع صغير في الكادر، static |
| فرح/مولد (Festival joy) | ألوان مختلطة، لمبات، شمس | `#FF6B6B` `#FFD93D` `#6BCB77` `#4D96FF` | sat عالي، دافي | confetti، bloom خفيف | handheld، قطع على الإيقاع، zooms |
| حزن الفقد/تأبين (Grief) | ضوء خافت منخفض، شمعة أو نافذة | `#3A3A3C` `#8D7B68` `#C8B6A6` | desaturated، أسود مرفوع شوية | grain ناعم، soft | بطيء جدًا، لقطات تفاصيل (إيد، صورة)، صمت |
| فخامة (Luxury) | ضوء موجّه، specular محكوم، ظلال ناعمة | `#0A0A0A` `#C9A24B` `#F5F0E6` | black عميق، ذهبي محدود، contrast عالي | نضيف جدًا، highlights لامعة | gimbal/slider بطيء، macro، لقطات قليلة |
| حلم (Dreamlike) | backlight، ضوء منتشر، overexposure لطيف | `#CDB4DB` `#FFC8DD` `#A2D2FF` | pastel، أسود مرفوع، حواف glow | bloom قوي، soft focus، halation | slow-mo، floating، dissolves طويلة |
| تمرد (Rebellion) | ضوء قاسي مباشر، flash، ظلال حادة | `#E63946` `#111111` `#F1FAEE` | contrast عالي، crushed blacks، sat انتقائي | grain خشن، scratches، flicker | handheld عصبي، jump cuts، Dutch angle |
| براءة (Innocence) | ضوء نهار ناعم، مستوى عين الطفل | `#FFE5B4` `#9ADCFF` `#FFB5A7` | pastel دافي، high-key | نضيف، bokeh | عدسة مستوى الطفل، تتبّع خفيف، لقطات مرحة |
| تشويق (Suspense) | ظلال طويلة، مصدر ضوء متقطع | `#101820` `#F2AA4C` `#2C5364` | contrast عالي، low-key، teal-shadow | grain، vignette، haze خفيف | slow push، قطع متباعد ثم قصير فجأة |

### الجدول التاني — الصوت والموسيقى والخط

| Mood | Sound bed | Music (key / tempo / instruments) | مقام (ارتباط شائع) | Typography feel |
|---|---|---|---|---|
| حنين | راديو بعيد، شارع هادي، tape hiss خفيف | 70-90 BPM، piano/عود/كمان، reverb دافي | Bayati: دفا وحنين شعبي | Naskh/Amiri خفيف، لون كريمي، حركة fade |
| رعب | low rumble 30-60Hz، تنفس، صرير | drone، no melody، 40-60 BPM أو بدون إيقاع | Hijaz: توتر وغموض شرقي | خط رفيع باهت أو خشن، flicker |
| رهبة/ملحمة | رياح، صدى واسع | 60-90 BPM، طبول كبيرة، brass/strings، build طويل | Hijaz أو Nahawand للقوة والمهابة | Thuluth/Diwani كبير، ذهبي، scale ببطء |
| حميمية | room tone قريب، نفَس، ملابس | 60-75 BPM، عود/بيانو واطي الصوت | Rast: وقار ودفا ومحبة | Naskh ناعم، صغير، مساحة بيضا |
| شجن | مطر خفيف، ساعة بعيدة | 55-70 BPM، ناي/تشيلو/بيانو | Saba: حزن وشجن ووجع. Nahawand أيضًا | Naskh رفيع، رمادي-أزرق، fade بطيء |
| انتصار | جمهور، هتاف، impact | 100-130 BPM، طبول، brass، choir | Rast أو Ajam: فخر وبهجة | Bold Kufi/Thuluth، ذهبي أو أحمر، punch in |
| غموض | نقطة ماية، همس، reverb ذيله طويل | 50-80 BPM، قانون/ناي/synth pad | Hijaz Kar أو Hijaz | خط أنيق ناقص، reveal حرف بحرف |
| سكينة | عصافير، ماية، نسيم | 50-70 BPM، ناي، عود arpeggios، pad | Rast أو Bayati هادي | Naskh/Kufi خفيف، مساحة واسعة |
| طاقة مدينة | زمامير، موتوسيكلات، ناس، ميكروباص | 110-140 BPM، مهرجان/trap/إلكترونيك، bass ثقيل | Hijaz أو Bayati مع إيقاع شعبي | Cairo/Kufi Bold، لون نيون، cut سريع |
| ليالي رمضان | آذان، مسحراتي، ملاعق وأطباق، أطفال بعيد | 60-85 BPM، عود/قانون/ناي، duff، تواشيح | Bayati وRast للروحانية | Ruqaa/Thuluth ذهبي، زخرفة هندسية |
| حر الصيف | صراصير، مراوح، ميكروباص، ترام | 90-105 BPM، سمسمية/guitar/شعبي خفيف | Rast أو Ajam بمزاج صيفي | خط مرح Bold، ألوان حارة |
| إسكندرية الماطرة | مطر، موج، سيارات على أسفلت مبلول، نورس | 60-80 BPM، بيانو/كمان/عود، reverb واسع | Saba أو Nahawand: شجن بحري | Naskh/Amiri رقيق، أبيض خافت |
| عزلة الصحرا | ريح، رمل، صمت واسع | 45-65 BPM، ربابة/ناي، drone، تقاسيم حرة | Hijaz أو Saba للوحدة | Kufi رفيع، مساحة فاضية كبيرة |
| فرح/مولد | زغاريط، طبل، تصفيق، ميكروفون مولد | 100-125 BPM، طبلة/مزمار/رق | Rast وAjam للبهجة | Cairo Bold ملوّن، حركة bounce |
| فقد/تأبين | صمت، نفس، ساعة، ماية بعيد | 50-65 BPM، تلاوة أو ناي وحيد، بدون إيقاع | Saba أو Hijaz مع صمت طويل | Naskh/Amiri أبيض على أسود، ثابت |
| فخامة | room tone نضيف، صدى خفيف، خطوات | 70-95 BPM، بيانو/أوركسترا/عود عميق | Rast أو Nahawand | Serif/Kufi رفيع، ذهبي، تباعد حروف واسع |
| حلم | pads، reversed sounds، همس، reverb ضخم | 60-80 BPM، synth/harp/قانون | Rast أو Bayati مع شفافية | خط خفيف جدًا، blur، tracking واسع |
| تمرد | ضجيج مدينة، هتاف، distortion | 120-150 BPM، drums خام، guitar/bass مشوّش | Hijaz مع صوت خشن | Kufi ثقيل أو خط يدوي، stencil، قطع حاد |
| براءة | ضحك، لعب، نسيم | 80-110 BPM، xylophone/piano/ukulele | Rast أو Ajam بسيط | خط مدوّر مرح، ألوان pastel |
| تشويق | نبض ساعة، خطوات، room tone ضاغط | 70-100 BPM ostinato، strings قصيرة | Hijaz أو Saba توتر | Bold ضيق، أحمر/أبيض، flicker |

### وصف سريع للمقامات (ارتباطات شائعة)
| المقام | الإحساس الشائع |
|---|---|
| Rast | وقار، دفا، فخر هادي، بهجة متزنة |
| Bayati | حنين، شعبي، قرب من القلب، روحانية |
| Hijaz | شرقي درامي، توتر، غموض، شوق |
| Saba | حزن عميق، وجع، شجن |
| Nahawand | رومانسي حزين قريب من minor الغربي |
| Ajam | فرح وبهجة قريب من major الغربي |
| Kurd | رقة حزينة، هدوء |

> نصيحة: ماتلزقش مقام بس عشان اسمه. جرّب مقطعين واسمع بأذنك. وانتبه إن الربع تون محتاج آلة حقيقية (عود/قانون/ناي) أو sample كويس، الـ synth العادي بيبوّظ المقام.

---

## 3. Sound atmosphere

الصوت ٥٠٪ من الجو. الصورة الباردة مع ambience دافي بتتحس غلط.

### طبقات الـ ambience
| الطبقة | مثال | مستوى تقريبي |
|---|---|---|
| Room tone | هواء الأوضة الفاضية | ثابت تحت كل حاجة، -45 إلى -38 dBFS |
| Ambience bed | شارع، موج، ريح، مطر | -35 إلى -28 dBFS |
| Spot sounds | باب، خطوات، كوباية | حسب المشهد |
| Foley | قماش، لمس، تنفس | قريب من الميكروفون، واضح |
| Sweeteners | impact، riser، whoosh، sub drop | عند نقاط التحول بس |
| Music | score أو أغنية | تحت الحوار بـ 10-15 dB |

### تقنيات
- **J-cut للـ ambience:** صوت المشهد الجاي يدخل قبل الصورة بنص ثانية لحد ثانية. المشاهد يتشدّ للمكان قبل ما يشوفه. L-cut بالعكس: ambience المشهد القديم يكمل على الصورة الجديدة عشان الإحساس ما ينقطعش.
- **Reverb = مساحة:** reverb قصير (0.3-0.8s) = أوضة. طويل (2-5s) = مسجد، كنيسة، كهف، حلم. Pre-delay صغير = قريب. Wet كتير = بعيد/ذكرى. استخدم reverb على الـ ambience مش بس على الصوت.
- **Low-end rumble للرعب:** sine/noise تحت 30-60Hz بمستوى حوالي -30 dBFS، بيتحس أكتر ما بيتسمع. زوّده تدريجي مع التوتر.
- **Tape hiss / vinyl:** للحنين، خفيف جدًا.
- **Silence:** اقطع الـ ambience لحظة قبل اللحظة الكبيرة (dropout) وبعدين رجّعه. الأذن بتحس بالفراغ.
- **Frequency space:** سيب مساحة للصوت البشري (1-4kHz) في الموسيقى والـ ambience، قلّل هناك بـ EQ.
- **Ducking:** الـ ambience والموسيقى بينزلوا تلقائي تحت الحوار (sidechaincompress تحت).

### أدوات على الجهاز
| الأداة | الاستخدام | أمر |
|---|---|---|
| demucs | فصل أغنية/تسجيل لـ stems (vocals, drums, bass, other) | `demucs -n htdemucs --two-stems=vocals in.wav` |
| deep-filter | تنضيف ضوضاء الصوت البشري | `deep-filter in.wav -o out_dir` |
| edge-tts | voiceover عربي مصري | `edge-tts --voice ar-EG-SalmaNeural --text "..." --write-media vo.mp3` |

استخدامات demucs في الجو: شيل الـ vocals من أغنية مرجعية واستخدم الباقي كـ bed، أو شيل الـ drums من تراك عشان تخليه أهدى، أو خُد الـ bass لوحده كـ rumble. (الأوامر دي غير متحققة على نسختك، راجع `demucs -h`.)

التنضيف: شغّل deep-filter على الحوار **قبل** إضافة الـ ambience، عشان تنضف الدخلة مش المزيج. ماتبالغش لأن الصوت بيبقى "معدني" ويبوّظ الجو.

### Mixing targets
| البند | الهدف |
|---|---|
| Integrated loudness (سوشيال: reels/TikTok/YouTube Shorts) | حوالي -14 LUFS |
| Dialogue / voiceover | تقريبًا -16 إلى -18 LUFS-ish في الـ mix قبل الماستر، والمهم يبقى مفهوم |
| Music تحت الحوار | أقل بـ 10-15 dB |
| Music لوحدها (بدون حوار) | قريب من مستوى الماستر |
| True peak | -1 dBTP |
| LRA | حوالي 5-9 LU للسوشيال، أوسع للأفلام |

- المنصات بتعدّل الـ loudness بنفسها، فالهدف الأمان من الـ clipping مش الرقم بالظبط.
- القياس: `ffmpeg -i in.mp4 -af loudnorm=I=-14:TP=-1:LRA=9:print_format=json -f null -`
- الموبايل سماعته صغيرة: تأكد إن الرعب والـ sub مش بس في الـ low end، حط harmonic فوق 200Hz عشان يتسمع.

---

## 4. ffmpeg recipes

كل الأمثلة فيها `-c:a copy` للفيديو بس. على Windows استخدم مسارات نسبية أو بدون drive letter جوه الـ filter (الـ `C:` بيتلخبط مع `:`). **كلها unverified: جرّبها على clip قصير وعدّل الأرقام.**

### 4.1 Film grain
```bash
ffmpeg -i in.mp4 -vf "noise=alls=14:allf=t+u" -c:a copy out.mp4
```
`alls` شدة الحبيبات (8 خفيف، 20 تقيل). `t` متغير مع الوقت، `u` منتظم. لو الحبيبات ناعمة أكتر: `gblur=sigma=0.5` بعدها.

### 4.2 Halation / Bloom (split + gblur + blend)
```bash
# bloom عام (بدون لون)
ffmpeg -i in.mp4 -filter_complex "[0:v]split[a][b];[b]gblur=sigma=25[g];[a][g]blend=all_mode=screen:all_opacity=0.35" -c:a copy bloom.mp4

# halation: highlights بس، لونها أحمر-برتقالي
ffmpeg -i in.mp4 -filter_complex "[0:v]split[a][b];[b]format=rgb24,lutrgb=r='if(gt(val,210),val,0)':g='if(gt(val,210),val,0)':b='if(gt(val,210),val,0)',gblur=sigma=30,colorchannelmixer=rr=1:gg=0.3:bb=0.05[h];[a][h]blend=all_mode=screen:all_opacity=0.55" -c:a copy halation.mp4
```
قلّل `210` لو عايز highlights أكتر تلمع. زوّد sigma للتوهج الأوسع.

### 4.3 Vignette
```bash
ffmpeg -i in.mp4 -vf "vignette=angle=PI/4" -c:a copy vig.mp4
```
`angle` أصغر = vignette أقوى. `PI/5` أقوى، `PI/3` أخف.

### 4.4 Teal-orange
```bash
ffmpeg -i in.mp4 -vf "colorbalance=rs=-0.12:gs=-0.02:bs=0.15:rm=0.03:bm=-0.03:rh=0.18:gh=0.05:bh=-0.15" -c:a copy tealorange.mp4
```
الظلال → teal، الـ highlights → برتقالي. لو skin tones اتبوّظت قلّل `rh`/`bh`.

### 4.5 Bleach bypass (تقريبي)
```bash
ffmpeg -i in.mp4 -filter_complex "[0:v]split[a][b];[b]hue=s=0,eq=contrast=1.5[g];[a][g]blend=all_mode=overlay:all_opacity=0.55,eq=saturation=0.75" -c:a copy bleach.mp4
```

### 4.6 Warm nostalgic curves
```bash
ffmpeg -i in.mp4 -vf "curves=all='0/0.06 0.5/0.52 1/0.96':r='0/0.03 0.5/0.56 1/1':b='0/0.02 0.5/0.44 1/0.88',eq=saturation=0.85,noise=alls=10:allf=t,vignette=PI/4.5" -c:a copy warm.mp4
```
الأسود مرفوع، الأزرق مخفوض في الـ highlights، grain وvignette خفيف.

### 4.7 Cold night look
```bash
ffmpeg -i in.mp4 -vf "eq=brightness=-0.05:contrast=1.15:saturation=0.8,colorbalance=rs=-0.05:bs=0.18:bm=0.12:rh=-0.05:bh=0.08,vignette=PI/4" -c:a copy night.mp4
```
لو عايز لمسة صفرا من الأنوار: سيب `rh` موجب شوية.

### 4.8 Haze lift (ضباب خفيف)
```bash
ffmpeg -i in.mp4 -vf "curves=all='0/0.10 0.4/0.45 1/0.93',eq=saturation=0.8,colorbalance=bs=0.05:bh=0.03" -c:a copy haze.mp4
```
بيرفع الأسود ويقلل التباين فيحس إن فيه هوا. للعمق الحقيقي استخدم Blender volumetrics (القسم 5).

### 4.9 Glow بدون lens-dirt
```bash
ffmpeg -i in.mp4 -filter_complex "[0:v]split[a][b];[b]gblur=sigma=40,eq=brightness=0.05[g];[a][g]blend=all_mode=softlight:all_opacity=0.6" -c:a copy glow.mp4
```

### 4.10 .cube LUT
```bash
ffmpeg -i in.mp4 -vf "lut3d=file=look.cube:interp=tetrahedral" -c:a copy lut.mp4
```
حط `look.cube` في نفس الفولدر (تجنّب `C:\` جوه الفلتر). خفّف شدة الـ LUT بالمزج:
```bash
ffmpeg -i in.mp4 -filter_complex "[0:v]split[a][b];[b]lut3d=file=look.cube[l];[a][l]blend=all_mode=normal:all_opacity=0.6" -c:a copy lut_soft.mp4
```

### 4.11 Letterbox (2.39:1)
```bash
# اقطع وكبّر بحدود سودا
ffmpeg -i in.mp4 -vf "crop=iw:iw/2.39,pad=iw:ih*0+iw*9/16:0:(oh-ih)/2:black" out.mp4
# لـ 9:16 (ريلز): أشرطة سودا فوق وتحت من غير قص
ffmpeg -i in.mp4 -vf "drawbox=x=0:y=0:w=iw:h=ih*0.12:color=black:t=fill,drawbox=x=0:y=ih*0.88:w=iw:h=ih*0.12:color=black:t=fill" out.mp4
```
الأولى محتاجة تعديل حسب الأبعاد، الأمان في التانية.

### 4.12 Ambience bed + ducking (amix + sidechaincompress)
```bash
ffmpeg -i dialogue.wav -stream_loop -1 -i ambience.wav -t 30 \
 -filter_complex "[0:a]asplit=2[d1][d2];[1:a]volume=0.6,lowpass=f=9000[amb];[amb][d1]sidechaincompress=threshold=0.04:ratio=8:attack=20:release=400[ducked];[d2][ducked]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1:LRA=9[mix]" \
 -map "[mix]" mix.wav
```
- `-t` بعد الـ inputs بيحدد الطول، عدّله لطول الحوار.
- `normalize=0` موجودة في ffmpeg حديث (7.1+)؛ لو نسختك أقدم شيلها وظبط `volume` يدوي.
- `threshold` أقل = ducking أكتر. `release` أطول = رجوع أنعم.

### 4.13 دمج look كامل (مثال)
```bash
ffmpeg -i in.mp4 -vf "curves=all='0/0.05 1/0.96',colorbalance=rs=-0.08:bs=0.1:rh=0.12:bh=-0.1,eq=saturation=0.9,noise=alls=10:allf=t,vignette=PI/4.5" -c:v libx264 -crf 17 -preset slow -pix_fmt yuv420p -c:a copy final.mp4
```
الترتيب: لون → grain → vignette. الـ grain بعد الـ grade دايمًا.

---

## 5. Blender atmosphere

Blender 4.2+/5: Eevee Next بيدعم volumetrics من الـ World مباشرة. للـ god rays: spot/sun + volume scatter + haze. للـ depth fog: Mist pass في الـ compositor.

```python
import bpy

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE_NEXT'   # في 5.x ممكن الاسم 'BLENDER_EEVEE' (غير متحقق)

# 1) World volume fog (ضباب هواء كامل المشهد)
world = scene.world or bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
nt = world.node_tree
out = nt.nodes.get("World Output")
vol = nt.nodes.new("ShaderNodeVolumeScatter")
vol.inputs["Density"].default_value = 0.02       # 0.005 خفيف .. 0.05 كثيف
vol.inputs["Anisotropy"].default_value = 0.4     # موجب = شعاع أوضح ناحية الضوء
vol.inputs["Color"].default_value = (0.85, 0.9, 1.0, 1)
nt.links.new(vol.outputs["Volume"], out.inputs["Volume"])

# 2) God rays: ضوء قوي + volume
light = bpy.data.lights.new("Sun", 'SUN')
light.energy = 6
light.angle = 0.02                               # حواف شعاع حادة
obj = bpy.data.objects.new("Sun", light)
scene.collection.objects.link(obj)
obj.rotation_euler = (0.9, 0.0, 0.6)             # زاوية منخفضة = شعاع أطول

# 3) Mist pass للعمق
scene.view_layers[0].use_pass_mist = True
world.mist_settings.start = 5
world.mist_settings.depth = 60
world.mist_settings.falloff = 'QUADRATIC'

# 4) Compositor: ادمج الـ mist كضباب لوني
scene.use_nodes = True        # في 5.x قد يتغير (compositor node group) — غير متحقق
tree = scene.node_tree
for n in list(tree.nodes): tree.nodes.remove(n)
rl = tree.nodes.new("CompositorNodeRLayers")
mix = tree.nodes.new("CompositorNodeMixRGB")
mix.blend_type = 'MIX'
mix.inputs[2].default_value = (0.75, 0.8, 0.9, 1)   # لون الضباب
comp = tree.nodes.new("CompositorNodeComposite")
tree.links.new(rl.outputs["Image"], mix.inputs[1])
tree.links.new(rl.outputs["Mist"], mix.inputs[0])    # factor = العمق
tree.links.new(mix.outputs["Image"], comp.inputs["Image"])
```
نصائح:
- ابدأ بكثافة قليلة. الضباب الزيادة بيمسح الـ contrast.
- Volume scatter مع **camera inside** الحجم بيشتغل. ضوء بدون volume = مفيش شعاع.
- Bloom/glare: من الـ compositor (Glare node, Fog Glow) أو Eevee render settings حسب الإصدار.
- Grain/vignette تتضاف بعد الرندر في ffmpeg (القسم 4) أسرع من Blender.
- تشغيل: `blender -b scene.blend -P atmo.py -a`. جرّب frame واحد الأول: `-f 1`.

---

## 6. Atmosphere continuity

### المبدأ
الجو بيتغير بقرار، مش بالصدفة. حدد **جو أساسي** للقطعة كلها، وبعدين **أقواس (arcs)** مقصودة.

| العنصر | ثابت في القطعة | بيتغير مع القصة |
|---|---|---|
| Palette الأساسي | أيوه | درجة التشبع/الحرارة بس |
| Grain/Texture | أيوه (نفس النوع) | الشدة |
| Room tone / ambience family | أيوه | الطبقات تزيد وتقل |
| Music key / مقام | غالبًا | modulation مقصود عند التحول |
| Typography | أيوه | الحركة والحجم |
| Aspect / letterbox | أيوه | يتغير بس لو تحول مقصود |

### قواعد
- **Anchor shot:** اختار لقطة مرجع للجو، وقارن كل لقطة بيها (بجنبها في الـ timeline).
- **Match cuts في اللون:** لو القطع من دافي لبارد، يكون بسبب (انتقال زمن/مكان).
- **Ambience ما بتقطعش على القطع:** استخدم J/L-cuts وcrossfades 200-500ms.
- **لو اتجمعت لقطات من مصادر مختلفة** (فوتيج، stock، AI): طبّق نفس الـ grade + grain + vignette فوق الكل في آخر خطوة، عشان توحّد المادة.
- **Arc:** مثال: بداية باردة هادية → وسط دافي → ذروة ساطعة → خاتمة هادية. اكتبه في سطر واحد قبل المونتاج.
- **اللون = تقدم:** غيّر قيمة واحدة في المرة (الحرارة أو التشبع أو الـ contrast).
- **الاستثناء المقصود:** لقطة واحدة خارج الجو (لون صارخ وسط رمادي) بتبقى هي الصدمة، بشرط تبقى مرة واحدة.
- **تحقق على أجهزة مختلفة:** موبايل بسطوع عالي، سماعة، وشاشة مظلمة.

### Checklist من 10 نقاط
1. عندي كلمة جو واحدة مكتوبة (مثال: «حنين دافي»)؟
2. الـ palette محدود في 3 ألوان (أساسي، ثانوي، لمسة)؟
3. الضوء مناسب للجو (اتجاه، صلابة، حرارة)؟
4. الـ black level مقصود (مرفوع ولا عميق)؟
5. فيه texture موحدة (grain، vignette، halation) على كل اللقطات؟
6. عدسة/زاوية/حركة الكاميرا متسقة مع الإحساس؟
7. إيقاع القطع بيخدم الجو، وفيه لحظة تنفس؟
8. فيه room tone وambience مستمرين تحت كل المشاهد؟
9. الموسيقى (مقام، tempo، آلات) مناسبة، ومتخفضة تحت الحوار؟ والـ mix على -14 LUFS و-1 dBTP؟
10. فيه لحظة صمت واحدة على الأقل في مكان مقصود، وكل الطبقات (صورة/صوت/خط) متفقة، وجربت أسمع وأشوف على موبايل؟

### أخطاء شائعة
| الغلط | الحل |
|---|---|
| teal-orange على كل حاجة | اختار الـ grade من الجدول حسب الجو |
| موسيقى حزينة على صورة مبهجة بدون قصد | وحّد الاتجاه أو اعمل التضاد عن عمد |
| ambience ناقص (صمت ميت بين الجمل) | حط room tone ثابت |
| grain/LUT قوي يخبّي الصورة | قلّل الشدة، وراجع على شاشة تانية |
| ضباب/bloom زيادة بيمسح التفاصيل | ابدأ بنص القيمة |
| نفس المقام والتقاسيم في كل الأجواء | غيّر حسب الجدول وجرّب بالأذن |
