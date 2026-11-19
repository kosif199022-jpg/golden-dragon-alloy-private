# فحص الجودة والأعطال (QA)

اقرا ده امتى: قبل أي تسليم، وكل ما حاجة تبوظ (الشاشة بتسوّد، الصوت ساكت، الطول غلط، الخط مش مقري).

كل بوابة هنا بحدّها ووقتها وأمرها، وتحت جدول الأعطال اللي حصلت فعلًا وحارس كل واحد. مرحلة 8 و«بوابات لا تتكسر» في PROTOCOL.md بيشاوروا هنا. `$D` = `python3 <skill>/scripts/dragon.py` (على ويندوز `python`)، `$S` = فولدر المهارة، `D` = مدة الفيلم بالثواني، `FINAL` = الملف اللي هيتبعت نفسه.

## 1. بوابة التسليم (8 فحوصات)
مفيش لينك ولا ملف يتبعت قبل ما `FINAL` نفسه (مش نسخة قبله) يعدّي التمانية. فشل = تصلّح وتفحص تاني. ممنوع ترفع وبعدين تسأل «تحب أظبطه؟». ولو التصليح هيكسر نسخ صوته AAC بالبايت، اسأله قبل الرندر؛ صوت مش AAC بيتعمله encode كده كده، فـ `--normalize` لو برّه المدى من غير سؤال، والأرقام قبل وبعد (AUDIO_SONGS_QURAN.md §1). v1.3: `verify --duration` بيوقّع على صوت ساكت (تحت −40 LUFS) وعلى فيلم من غير صوت خالص (إلا `--silent-ok`).
```bash
$D verify FINAL --expect 1080x1920 --duration D --out evidence.json     # لازم exit 0
```
| # | الفحص | يعدّي لما |
|---|---|---|
| 1 | السواد | `black=clean`: ولا جرية جوه الفيلم |
| 2 | الصوت | AAC، ومفيش `audio codec mp3 inside .mp4` |
| 3 | الفريمات | `frames=1200` لفيلم 40 ث. الفشل شكله `frames=807/810` |
| 4 | المقاس والـ fps | `1080x1920` و`fps=30.0` بعينك. المقاس الغلط بيطلع `WARN size … != 1080x1920` بس، والـ fps مش متفحوص خالص (فيلم 24 أو 25 fps بيعدّي OK)، وعندنا الاتنين ممنوعين إلا لو طلب غيرهم |
| 5 | فك كامل | `ffmpeg -nostdin -v error -i FINAL -f null -` مايطبعش ولا سطر |
| 6 | MD5 الصوت | لو الصوت اتنسخ: `ffmpeg -v error -i X -map 0:a -c copy -f md5 -` على FINAL وعلى الماستر بنفس الرقم. الماستر بطول D بالظبط؛ لو أطول، `mux` بيقصّه والرقم بيختلف (قص مش عيب) |
| 7 | ورقة QC | اتعملت واتفتحت واتشافت (§7) |
| 8 | وسوم التصدير و+faststart | أمر وسوم التصدير تحت جدول §2 بيطبع `High,yuv420p,bt709,bt709,bt709` وmoov قبل mdat. `verify` مش بيفحصها لسه (ROADMAP T1). لو غلط: encode بأعلام BT.709 (EXTERNAL_SKILLS.md: `scale … out_color_matrix=bt709`، `-profile:v high`، والوسوم التلاتة) و`verify` تاني |

- 1–3 بيوقّعوا `verify` (exit 1 = ممنوع التسليم)، و3 بس لما تدي `--duration`. رقم 4 مش بيوقّع: اقرا `1080x1920` و`fps=30.0` في السطر بعينك، وغيرهم = ممنوع التسليم.
- الـ LUFS والذروة تحذير مش فشل (بالتصميم). لو ظهر `WARN loudness …` أو `true peak …`: الرقمين في التقرير، واعرض `--normalize` (AUDIO_SONGS_QURAN.md).
- أول سطر في التقرير: «✅ عدّى كل الفحوصات» واللينك، أو «⚠️ فشل: <الفحص> — <التصليح>» من غير لينك (GOOD_REPORT.md). وسطر QA زي: «QA: verify OK · stills 24/24 · QC sheet ✓ · black 0 · frames 1350/1350 · audio AAC (copy, MD5 ✓)».

سطور حقيقية (اتقاست 2026-11-08، المسارات متقصّرة):
```
FAIL …/20261106-forty/mayar_bint_masr_40s.mp4  38821 KB  duration_s=40.0  loudness_lufs=-14.2  true_peak_dbtp=-1.5  fps=30.0  1080x1920 h264  frames=1200  black=6 runs  ERRORS black frames t=13.03-13.47 (14), 22.67-23.13 (15), 23.23-23.67 (14), 27.10-27.57 (15), 27.63-27.97 (11), 31.50-31.97 (15): 6 runs, 84 frames
OK  …/20261106-forty/mayar_bint_masr_40s_v2.mp4  41412 KB  duration_s=40.0  loudness_lufs=-14.2  true_peak_dbtp=-1.5  fps=30.0  1080x1920 h264  frames=1200  black=clean
FAIL …/20261108-riyadh/shita_alriyadh.mp4  …  loudness_lufs=-8.7  true_peak_dbtp=1.2 … frames=5012  black=clean  ERRORS audio codec mp3 inside .mp4: iPhone/Safari play it silent; remux with `dragon mux` (AAC 320k)  WARN loudness -8.7 LUFS outside social range (-16..-12); true peak 1.2 dBTP above -1 (owner limit)
OK  …/20261108-riyadh/shita_alriyadh_aac.mp4  …  loudness_lufs=-12.7  true_peak_dbtp=-1.3 … frames=5012  black=clean
```
- ليه: «شتا الرياض» فشل في 3 فحوصات صوت الساعة 10:01 وتاني 10:11 (7/10)، واتبعت 10:13 بملاحظة، و10:18 سأل «اغنية اليسا من غير صوت ليه». وفيلم الـ 40 ث عدّى «١٢ من ١٢» وكان فيه ومضات سواد هو اللي لقاها.

## 2. جدول البوابات
| gate | الحد | امتى | الأمر | آلي/يدوي/تذكرة |
|---|---|---|---|---|
| verify التسليم | exit 0 | على FINAL قبل أي لينك | `$D verify FINAL --expect 1080x1920 --duration D --out evidence.json` | آلي |
| السواد | ولا فريم Y < 17.5 جوه الفيلم، والحافة ≤ 2 ث | كل فيلم وكل حتة، وبعد أي رندر | جوه `verify` (§3) | آلي |
| حارس الرندر | آخر سطر `SUMMARY … unrecovered=0` | كل رندر render.cjs | `--strict` (exit 3 = فضل أسود) (§4) | آلي |
| صوت AAC | AAC بس جوه MP4 | قبل أي extract أو mux، وفي `verify` | `ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 SRC` | آلي |
| الفريمات | round(D×fps) بالظبط (fps الملف) | بعد كل mux | `$D verify FINAL --duration D` | آلي |
| fps = 30 | `fps=30.0` في سطر verify | على FINAL | سطر `verify` | يدوي (عين) |
| MD5 الصوت | = الماستر | لما الصوت copy | §1 رقم 6 | يدوي · تذكرة |
| فك كامل | ولا سطر خطأ | على FINAL | §1 رقم 5 | يدوي |
| وسوم التصدير | `High,yuv420p,bt709,bt709,bt709`، و`moov` قبل `mdat` | على FINAL | تحت الجدول | يدوي · تذكرة |
| علو الصوت | −16..−12 LUFS، ذروة ≤ −1 dBTP | في `verify` | سطر `WARN` ← التقرير | آلي (تحذير) |
| الستيلز | نص كل لقطة + 4 نقط في كل انتقال + دخول وخروج كل نص | قبل الرندر الكامل | §7 | يدوي (عين) |
| ورقة QC | اتفتحت واتشافت | بعد التجميع | §7 | يدوي |
| الوضوح | تحت الحروف mean ≤ 95 وp95 ≤ 140 | كل لحظة نص | NOTEXT (§8) | يدوي · تذكرة |
| النص والوش | النص ∩ (الوش + 10٪) = ∅، والـ baseline ≤ y 1700 | ستيل عند دخول كل نص | YuNet + ستيلز (STYLE_RECIPES.md) | يدوي · تذكرة |
| نص محروق في المصدر | tx ≤ 0.004 للقطات البطل، ≤ 0.003 للـ b-roll | وقت بناء الـ pool | PPOCR (SOURCES.md) | يدوي · تذكرة |
| مين في اللقطة | الوش الأساسي = البطل في 3 فريمات | قبل الستيلز | §9 | يدوي |
| المكان | اسم المكان في العنوان + 3 فريمات (10/50/90٪) | قبل ما الكليب يدخل | `$D run talking_head sheet DIR clip.mp4` (SOURCES.md) | يدوي |
| الأسماء الممنوعة | 0 | قبل الرندر | `grep -c 'الشوربجي' film/index.html` (LESSONS.md) | يدوي |
| الحقوق | «© Mahmoud Elkosif» طول الفيلم، و«مونتاج وإخراج Mahmoud Elkosif» و«تابعني على فيسبوك» في آخر ~3 ث | ستيلز + ورقة QC | ستيل عند D − 1.5 ث (OWNER.md) | يدوي |
| التجمّد | مفيش أطول من 2 ث غير مقصود | على FINAL | §13 | يدوي (حد مقترح) |

«تذكرة» = الأمر جاي في ROADMAP.md؛ لحد ما ييجي اعمله بالإيد بالطريقة اللي في القسم بتاعه. وسوم التصدير والـ faststart:
```bash
ffprobe -v error -select_streams v:0 -show_entries stream=profile,pix_fmt,color_space,color_transfer,color_primaries -of csv=p=0 FINAL   # High,yuv420p,bt709,bt709,bt709
ffprobe -v trace FINAL 2>&1 | grep -o "type:'\(moov\|mdat\)'" | head -2      # moov الأول = +faststart
```

## 3. السواد («الشاشة بتسوّد»)
- فريم أسود = متوسط Y على تصغير 54×96 أقل من 17.5 (أسود TV = 16.0).
- جرية جوه الفيلم = فشل: أي جرية وراها صورة من الناحيتين، حتى لو في أول 0.6 ث أو آخر 1.5 ث (ومضة عند 0.2–0.4 ث مش فيد). الفيد = جرية لامسة أول فريم (وبادئة في أول 0.6 ث) أو لامسة آخر فريم. جرية على الحافة أطول من 2.0 ث = فشل («not a fade»). فيلم أقصر من 6 ث: الشبابيك والحد بيصغروا بالنسبة لوحدهم. الفيد العادي بيطلع `INFO fade black at start …` ومش فشل.
- افحص كل فيلم بيتسلّم وكل حتة. لو اتلقى عيب في محرك: افحص تاني كل فيلم اتسلّم بيه، واعرض عليه رندر جديد.
- `verify` بيفك كل فريم (فيلم 40 ث = ~10 ث فحص). `--no-black` للفرجة السريعة بس: على فيلم الـ 40 ث القديم بيدّي `OK … black=skipped` وexit 0، يعني بيخبّي العيب.
- العدّاد اليدوي (من `out/fixblack.sh`) للحتت والـ slices؛ بيعدّ الفيد كمان، فللفيلم كله استخدم `verify`:
```bash
ffmpeg -nostdin -i F -vf 'scale=54:96,signalstats,metadata=print:key=lavfi.signalstats.YAVG' -f null - 2>&1 | grep -o 'YAVG=[0-9.]*' | awk -F= '$2<17.5' | wc -l   # لازم 0
```
| الفيلم | الجريات جوه الفيلم (2026-11-08) | النسخة المصلّحة |
|---|---|---|
| فيلم 40 ث `out/20261106-forty/mayar_bint_masr_40s.mp4` | 6 جريات، 84 فريم: 13.03–13.47، 22.67–23.13، 23.23–23.67، 27.10–27.57، 27.63–27.97، 31.50–31.97 ث | `_v2.mp4`: `black=clean` |
| «أجنحة من ورق» `out/20261105-cine/ajniha_min_waraq_bila_musiqa.mp4` | المراجعة القديمة لقت 2: 108.63–108.97 ث (11 فريم) و146.47–147.43 ث (30 فريم). `verify` لقى 6 جريات، 62 فريم: كمان 63.03–63.17 (5)، 83.90–83.97 (3)، 95.87–95.97 (4)، 167.20–167.47 (9) | `_v2.mp4`: `black=clean`، exit 0 |

- الجريات القصيرة في «أجنحة» قطع فجأة جوه نفس اللقطة (Y ~128 ← 16.03 ← ~128)، مش dip مقصود. جرية 3–5 فريم بتفوت العين، فمفيش تسليم من غير `verify`.
- dip مقصود جوه الفيلم بيتعدّ سواد برضه: `fadeblack` بطول 0.3 / 0.5 / 0.9 ث حط 2 / 3 / 5 فريم تحت 17.5 (قياس على مصدر تجريبي 2026-11-08). خلّي الـ dip لـ `#111` مش `#000` (أقل Y = 31)، زي `fade=t=out:st=A:d=0.25:color=0x111111`، أو قطع أو dissolve ≤ 0.16 ث (STYLE_RECIPES.md). `window.__kosif.allowBlack(t)` بيسكّت حارس الرندر بس، مش `verify`. اتأكد على أول فيلم.
- ليه: سأل 2026-11-06 00:45: «ايه مشكلة في ان الشاشة بتنور بتطفي، بتبقى سودة وتقفل وتطفي؟»، والفحص بعدها لقى لحظتين سواد في «أجنحة من ورق» اللي كان اتسلّم.

## 4. حارس الرندر وترتيب الحلول
render.cjs المدمج هو الافتراضي، والحارس شغال لوحده:
- كل فريم في صفحة فيها `<canvas>` بيتقاس (نسخة 27×48 جوه الـ seek). فريم أسود بعد أول `--allow-black-head 0.6` ث وقبل آخر `--allow-black-tail 1.5` ث بيتعاد لحد 3 مرات من صفحة أجدد: reload ← context جديد ← browser جديد.
- reload كل `--recycle 120` فريم (`0` = أبدًا). صفحة صور تقيلة (فوتوز كتير): `--recycle 40` (الفشل اتقاس عند ~50 seek). صفحة فيها random وقت التحميل أو state بين الـ seeks: `--recycle 0`.
- صفحة من غير canvas مابتتفحصش، و`--stills` مالوش حارس. `--no-guard` للتجربة بس.
```bash
node $S/app/engines/render/render.cjs --in film/index.html --out film.mp4 --fps 30 --duration D --strict
$D verify film.mp4 --duration D      # الفيديو ساكت؛ بعده $D mux (§5)
```
| السطر | معناه |
|---|---|
| `RECOVERED t=1.333 tries=1 via=reload` (أو `context` / `browser`) | الفريم اتصلّح لوحده |
| `BLACK_UNRECOVERED t=2.000` | فضل أسود بعد 3 محاولات. بعده سطر عن `allowBlack` لو السواد مقصود |
| `SUMMARY frames=… recovered=… unrecovered=… reloads=… … guard=on` | آخر سطر (بعد `VIDEO film.mp4 N frames`). لازم `unrecovered=0` |

- exit 0 = تمام. exit 2 = الرندر وقع أو flag غلط. exit 3 = `--strict` وفيه فريم فضل أسود؛ الـ MP4 بيتكتب كامل برضه عشان تفحصه أو تصلّحه.
- `$D film spec.json` بيطبع سطور الحارس وآخرها سطر verify. v1.3: `$D run web_film render` بقى بـ `--strict` وبيطبع سطور الحارس وبيقع بالأوقات، وبرضه `$D verify` بعده إجباري. `$D run matrices` لسه من غير `--strict`: `verify` على الناتج هو الحكم.
- كود الصفحة: كاش الصور المفكوكة ≤ 16، صورة ماتحمّلتش تتعاد 4 مرات بينهم 150 ms بـ `?r=k`، وبعدها يترسم آخر فريم سليم من نفس اللقطة، عمره ما يترسم ولا حاجة. ده في `loadImg` بتاع `tools/styles/common.js` (أصله `out/20261108-trio/common.js`، والـ retry من `out/20261106-forty/film/clean.js`). محركات `cinema` و`web_film` لسه مافيهاش الـ retry ده (ROADMAP)، فصفحاتهم بصور كتير: `--recycle 40` و`verify` الكامل. رندر browser واحد في المرة.
- ماتمسحش فولدر الفريمات (`--tidy` في `tool styles`) قبل `verify` exit 0 على FINAL: من غيره مفيش رندر تاني للثواني دي.

ترتيب الحلول لما يفضل سواد:
1. الحارس (لوحده). `unrecovered=0` و`verify` نضيف = خلصت.
2. فضل `BLACK_UNRECOVERED`، أو `verify` لقى جرية: رندر الثواني دي تاني حتت 1–2 ث في صفحة جديدة، لحد 4 محاولات، وعدّاد YAVG (§3) على كل حتة = 0. لو حتة 2 ث فضلت سودا، قسّمها 1 ث. v1.3: `render.cjs --start` بيرندر الحتة على طول:
```bash
T0=146.4   # الثانية الصحيحة قبل الجرية (ممكن كسر)؛ الحتة = T0..T0+2
T1=$(python3 -c "print($T0+2)")
node $S/app/engines/render/render.cjs --in film/index.html --out fix.mp4 --start $T0 --duration 2 --allow-black-head 0 --allow-black-tail 0 --strict
ffmpeg -nostdin -v error -y -i film.mp4 -i fix.mp4 -filter_complex "[0:v]split[x][y];[x]trim=end=$T0,setpts=PTS-STARTPTS[a];[y]trim=start=$T1,setpts=PTS-STARTPTS[c];[a][1:v][c]concat=n=3:v=1:a=0[v]" -map "[v]" -c:v libx264 -profile:v high -preset slow -crf 17 -pix_fmt yuv420p -color_primaries bt709 -color_trc bt709 -colorspace bt709 -an -movflags +faststart film_fixed.mp4
```
   `--allow-black-head 0 --allow-black-tail 0` لأن حتة 2 ث بالشبابيك العادية مافيهاش ولا فريم بيتفحص. اللصق اتجرّب على مصدر تجريبي: 300 من 300 فريم. بعده `$D mux film_fixed.mp4 master.m4a final.mp4 --duration D` و`$D verify`.
3. آخر حل: `$D patch-black IN OUT`، لفريمات قليلة متفرقة بس. بينسخ آخر فريم سليم فوق السواد، ويضغط تاني (CRF 17 slow، BT.709)، والصوت يتنسخ (MP3/PCM جوه MP4 يبقى AAC 320k، وPCM جوه .mov يتنسخ)، ومصدر webm يطلع .mp4، ويفحص تاني (exit 1 لو فضل حاجة). بيطبع `patch-black -> OUT  patched: N run(s), F frames [a-b (n), …]` و`… black runs left inside the film: 0`. ده تجميد بيبان: جرية 30 فريم (1 ث) هتبان وقفة، فرندرها تاني. في التقرير: «اتصلّح بتجميد N فريم عند T ث».
- `$D tool styles SPEC.json --out DIR --render` بيعمل patch-black لوحده لو لقى سواد: دوّر في اللوج على `QA patched N black frame(s) with the previous good frame; left: K`. N كبير = رندر تاني، وN قليل = سطر التجميد في التقرير.
- ليه: أول تشخيص (الهارد مليان) طلع غلط. السبب: ~120 صورة كبيرة في الكاش مع رندرات بالتوازي، وبعدين سواد بعد ~50 seek تقيل ورا بعض في نفس الصفحة، ونفس الثواني من صفحة جديدة طلعت سليمة. فيلم الـ 40 ث و«قلب العرب» v2 ونسختين «أجنحة من ورق» وفيلم التلاوة اترندروا تاني.

## 5. الطول بالفريم و`$D mux`
- ممنوع تقفل فيلم بـ `-shortest`، أو بـ `-t` على نسخ (stream copy). الماستر الصوتي D ث بالظبط، والفيديو N = round(D×30) فريم بالظبط (رندر بـ 30 fps؛ `mux` بيحافظ على fps الداخل): 27 ث = 810، 40 ث = 1200، 45 ث = 1350.
```bash
$D mux film.mp4 master.m4a final.mp4 --duration D
$D verify final.mp4 --expect 1080x1920 --duration D --out evidence.json
```
- بياخد الصورة من VIDEO بس والصوت من AUDIO بس، فينفع تعدّي عليه ناتج أي محرك فيه صوت.
- الفيديو: copy لو فيه ≥ N فريم، encode لو المصدر فيه B-frames وأطول من N، pad بآخر فريم لو قصير. الصوت: AAC يتنسخ (بيتقص عند حافة packet، فممكن يقصر frame AAC واحد: 1.984 ث بدل 2.0 ث)، أي كوديك تاني AAC 320k 48 kHz بالعينة، و`--normalize` = loudnorm I=-14:TP=-1.5:LRA=11.
- بيطبع `mux -> OUT  N frames at 30 fps = D s  video copy|encode|pad (n frames in)  audio <codec> -> aac copy|encode|normalize (s s)` وبعده سطر verify، وexit 1 لو فشل. الفحص ده من غير سواد (`black=skipped`)، فـ `$D verify` الكامل بعده إجباري.
- يدوي (زي `out/20261108-trio/render.sh`):
```bash
F=$(python3 -c "print(round(45*30))")
ffmpeg -nostdin -i v.mp4 -frames:v $F -c:v libx264 -profile:v high -preset slow -crf 17 -color_primaries bt709 -color_trc bt709 -colorspace bt709 -an v2.mp4
ffmpeg -nostdin -i v2.mp4 -i mix.m4a -map 0:v -map 1:a -c copy -movflags +faststart OUT.mp4
```
- المحركات (`talking_head`، `matrices`، `shadow_theatre`، `cinema`، كروت `app/engines/cards/lib`، وكليب اختبار `dragon_montage`) بقت تقفل بطول مظبوط من غير `-shortest`: round(D×fps) فريم والصوت متمد/متقص لنفس الطول (`tests/test_v12_exact_length.py`). برضه عدّي فيلم التسليم على `$D mux` بالماستر لو الصوت المسلَّم غير صوت المحرك، و`$D verify --duration D` إجباري. v1.3: `$D run web_film render … --audio` بقى بيعمل الصوت بـ `deliver.mux`، و`tools/cartoon/tools/finish.sh` بقى فيديو BT.709 من غير صوت وبعده `$D mux` و`$D verify`. وفي kosif-tool: `out/seq_saas.sh` و`out/seq_aj2.sh` و`out/seq_fix40.sh`.
- ليه: فيلم الميدالية 27 ث طلع 807 فريم بـ `-shortest`، و812 فريم / 27.067 ث بـ `-t 27`؛ اللي عدّى بس اتقص 810 بالظبط. وremux بـ `-shortest` وقّع آخر packet AAC (MD5 مختلف).

## 6. قبل الـ concat (رندر حتت)
للـ fallback وللأفلام الطويلة اللي بتترندر حتت:
- جدول الحتت يتعمل مرة واحدة من D: start_k = k·P، dur_k = min(P, D − k·P). وكل حتة تترندر لـ `<out>.tmp.mp4` وتتنقل بـ `mv` لما تنجح بس.
- قبل الـ concat لازم: العدد = المخطط؛ كل ملف > 0 بايت ويتقري (مفيش `moov atom not found`)؛ 1080×1920 و30/1؛ nb_read_packets = dur_k×30. غير كده اطبع `ASM_FAIL n=<count>` وماتجمّعش.
```bash
ffprobe -v error -select_streams v:0 -count_packets -show_entries stream=width,height,r_frame_rate,nb_read_packets -of csv=p=0 chunk.mp4   # 1080,1920,30/1,60 لحتة 2 ث
ls chunks/c*.mp4 | wc -l      # لازم = عدد الحتت المخطط قبل الـ concat
(cd chunks && ls c*.mp4 | sort | sed 's/^/file /') > chunks/l.txt
ffmpeg -nostdin -f concat -safe 0 -i chunks/l.txt -c copy -an v.mp4
```
- اسم واحد بس: `c$(printf %03d $k).mp4` (نفس PROTOCOL.md «فيلم طويل»؛ `f1_*` اسم قديم). الحتة k: `render.cjs --start k·P --duration dur_k`، والحتت اللي في النص `--allow-black-head 0 --allow-black-tail 0`، وكل حتة `$D verify cNNN.mp4 --duration dur_k --silent-ok`. القايمة جوه فولدر الحتت بأسامي مجردة، وكل المسارات من متغير واحد مطلق `JOB`.
- ليه: chunk0066 ماكانش بيتقري بعد ما الهارد اتملا؛ حتة 149 طلعت 2.46 ث بسبب `[ $k = $LAST ]` لكل worker؛ `Impossible to open 'chunks/chunks/f1_000.mp4'`؛ ورندر قرا `chunks.txt` من فولدر يوم تاني.

## 7. الستيلز وورقة QC والقفزات
- قبل الرندر الكامل: ستيل في نص كل لقطة، و4 نقط في كل انتقال طوله X (القطع − 0.05، +X/4، +X/2، +X)، وعند دخول وخروج كل نص.
- `$D film spec.json --stills 1.5,7.5,12`، أو `node $S/app/engines/render/render.cjs --in film.html --stills 1,4.5,9 --stills-dir dir` (الملفات `still_1.000.png` …).
- افتح الشبكة ودوّر على: شخص غلط، كتابة أو لوجو محروق، نص على وش، تكرار، كليب ضلمة أو مغبّش، لوك ممنوع (OWNER.md، STYLE_RECIPES.md). صلّح وصوّر تاني.
- بعد الرندر، ورقة QC للملف النهائي (فريم كل 7 ث، 8×3):
```bash
ffmpeg -nostdin -v error -y -i final.mp4 -vf 'fps=1/7,scale=-2:300,tile=8x3' -frames:v 1 qc.jpg
```
- مع `tile` الـ `-frames:v` بيعدّ ورق مش فريمات: ورقة واحدة = 24 خانة × 7 ث = 168 ث (1344×900 px). فيلم أطول: شيل `-frames:v 1` واكتب `qc_%02d.jpg` (ورقة لكل 168 ث).
- القفزات عند كل وصلة: قارن الفريم اللي قبلها واللي بعدها. أوقات القطعات اللي في الملف: `ffmpeg -nostdin -i final.mp4 -vf "select='gt(scene,0.30)',showinfo" -f null - 2>&1 | grep -o 'pts_time:[0-9.]*'`؛ قطع مش في الـ EDL = قفزة. يدوي (مفيش أمر لسه، شوف ROADMAP.md).
- في التقرير: الستيلز مش فرجة. قول شفت إيه بالظبط («stills 24/24 · QC sheet ✓»).
- ليه: كل أفلام الأيام اللي فاتت مشيت ستيلز ← تصليح ← رندر (trio A اتصلّح فيه لقطتين، B اتقص منه لوجو قناة، C اتبدّل فيه بلاطتين بطل). وورقة QC بتاعة الرياض لقطت برج الساعة في مكة بعد التجميع (كان ظاهر 5 مرات).

## 8. الوضوح وNOTEXT
- لكل لحظة نص: توأم NOTEXT (الحروف مابتترسمش، والبلاطات والشرايط تفضل). الماسك = |العادي − NOTEXT| > 40، وتحت الحروف في NOTEXT لازم mean ≤ 95 وp95 ≤ 140.
- فشل: ضلّم أو سطّح الشريط (لحد alpha 0.94 للقطة)، أو stroke غامق، أو حرّك النص، وأعد الفحص.
- يدوي (مفيش أمر لسه، شوف ROADMAP.md). لأي صفحة canvas:
```bash
cp film/index.html film/notext.html
echo "<script>CanvasRenderingContext2D.prototype.fillText=CanvasRenderingContext2D.prototype.strokeText=function(){}</script>" >> film/notext.html
node $S/app/engines/render/render.cjs --in film/index.html --stills 15.5 --stills-dir tx
node $S/app/engines/render/render.cjs --in film/notext.html --stills 15.5 --stills-dir nt
python3 -c "import numpy as np,sys;from PIL import Image;a,b=(np.asarray(Image.open(f).convert('L'),float) for f in sys.argv[1:3]);v=b[np.abs(a-b)>40];m,p=v.mean(),np.percentile(v,95);print(f'mean {m:.0f} p95 {p:.0f}','FAIL' if m>95 or p>140 else 'OK')" tx/still_15.500.png nt/still_15.500.png
```
- في الجلسة كان `window.__kosif.notext=true` بيخلّي `txt()` ترجع على طول (`if(a<=0.003||NOTEXT)return;`)، والسكربت `gate2.py` (مش مدمج) كان بيطبع mean/p95 لكل وقت و`<-- FAIL`.
- ليه: «الخط غير واضح». أول فيلم لميار فشل في أغلب فريمات الفحص (عند 15.5 ث mean 246) لحد ما الشرايط والـ stroke والبلاطات المسطّحة صلّحوه.

## 9. مين في اللقطة
- في أي تكريم، كل لقطة بطل لازم فيها البطل. كشف وش على 3 فريمات لكل لقطة (أول، نص، آخر)، وورقة متعلّمة بالوقت، وارفض اللقطة اللي وشها الأساسي حد تاني. اسمها مايتكتبش على لقطة مااتأكدتش مين فيها.
- فريم واحد (بورتريه): seek دقيق بـ `-ss` بعد `-i`، وبص عليه قبل ما تستخدمه: `ffmpeg -v error -i src.mp4 -ss 380.5 -frames:v 1 out.jpg`.
- الوش: YuNet `cv2.FaceDetectorYN_create('yunet.onnx','',(320,320))` (OpenCV 5 مافيهوش CascadeClassifier؛ الموديل في ENVIRONMENTS.md). الكادرات: `$D film spec.json --stills …` على أول ونص وآخر كل لقطة، أو `$D run talking_head sheet DIR clip.mp4` للكليب. الورقة المتعلّمة بأمر واحد: يدوي (مفيش أمر لسه، شوف ROADMAP.md).
- ليه: كليب التتويج كان فيه طفلة تانية (اتبدّل بـ J3 عند 36 ث)؛ seek مش دقيق جاب طفلة تانية مكان بورتريه ميار (اتصلّح بـ `-ss` بعد `-i` عند 380.5)؛ 4 لقطات في «قلب العرب» v2 ولقطتين في فيلم تاني كان فيهم بنت تانية؛ وواحد شايلينه على الكتاف طلع راجل.

## 10. فحص الصفحة وقائمة اللقطات
قبل الستيلز أو الرندر:
1. كل خط بوزنه يتحمّل بـ `document.fonts.load`، وframe 0 يترسم، وبعدين `window.__kosifReady=true` (`boot()` في كيت الستايلات بيعمل كده). مثال trio: `Promise.all(['700 40px Ruqaa','700 40px Tajawal','400 40px Lalezar','700 40px Messiri'].map(f=>document.fonts.load(f))).then(async()=>{await render(0);window.__kosifReady=true})`.
2. مفيش `//` جوه دالة JS في سطر واحد: `/* */`.
3. كل موديول في scope لوحده (IIFE) أو أساميه ببادئة. شغّل `--stills` الأول: render.cjs بيطبع `[page error] …` ومابيقفش، فأي سطر زي ده = وقف. ولو مفيش ولا سطر `still` بعد 30 ث، الصفحة مش جاهزة: وقفه واقرا الخطأ.
4. `--in` مسار ملف عادي، من غير `?query`: HTML (أو CFG) لكل نسخة.
5. قائمة اللقطات: كل انتقال موجود في الجدول، مفيش id مكرر، اللقطات المستخبية وقتها بعد D (1000+8k)، وكل لقطة فريماتها كفاية: need = ceil((out − in + tr_in + tr_out)·fps·rate) + off + 1 ≤ الفريمات المستخرجة، والاستخراج = الخانة + 0.7 ث (`L=en-st+.7` في `trio_lib.extract()`). مصدر قصير: يتبطّأ (rate < 1)، أو يقف على آخر فريم، أو يتبدّل.
- آلي جزئيًا: `$D tool styles SPEC.json --check` (WARN / MISSING / OK)، و`$D run web_film check film.plan.json --html film.html` (exit 1 على أي فشل).
- ليه: خط fallback صغير في أول فريم في #42؛ تعليق `//` قفل `txt()`؛ `Identifier 'RED' has already been declared` خلّى ready مايتعرّفش (timeout 30000 ms)؛ `assert need <= nf + 3` فشل 11 مرة في 10 شغلانات؛ `KeyError 'whip'`؛ `--in file not found: …index.html?style=1`.

## 11. فلاتر التركيب
- screen وlighten في gbrp مش YUV (YUV = لون موف): `[a]format=gbrp[a1];[b]format=gbrp[b1];[a1][b1]blend=all_mode=screen,format=yuv420p`.
- `settb=AVTB,fps=30` على كل مدخل xfade وبعد أي concat: `[0:v]settb=AVTB,fps=30[a];[1:v]settb=AVTB,fps=30[b];[a][b]xfade=transition=fade:duration=0.9:offset=T` (`fadeblack` جوه الفيلم بيفشّل `verify`، §3).
- الماسك RGBA بقناة alpha؛ الماسك الرمادي بيتصرف كأنه مصمت.
- البطل والخلفية على نفس العمق، والـ parallax ±9 px بالكتير، وإلا هالة أو شكل مكسور.
- ليه: كل واحدة حصلت مرة وكلّفت رندر: `First input link main timebase (1/1000000) do not match … (1/15360)`، لون موف من screen في YUV، والخلفية اتحدّت ±9/±7 px.

## 12. نظافة ffmpeg والشل
- `-nostdin` لكل ffmpeg جوه لوب.
- قبل crop/pad/stack: `ffprobe` للعرض والارتفاع لكل مصدر، وclamp: cw ≤ W، ch ≤ H، cx+cw ≤ W، cy+ch ≤ H (زي `crop()` في `out/20261108-trio/trio_lib.py`).
- tile وpad بـ `force_original_aspect_ratio=decrease` + `pad`؛ hstack بنفس الارتفاع؛ deshake rx/ry مضاعفات 16؛ شيل شرايط letterbox الأول.
- السلسلة تقف عند أول فشل (`set -euo pipefail` أو `&&`)، وكل ناتج يتأكد إنه موجود ومش فاضي قبل ما يتاخد: `[ -s out.mp4 ] || { echo MISSING out.mp4; exit 1; }`.
- `tail -n 20` (مش `tail -20` مع كذا ملف). سكربت build مايدخلش pipe في `head`: `python3 build.py > build.log 2>&1; tail -n 20 build.log`.
- تعديل الكود بأداة Edit، مش sed أعمى.
- ليه: 43 `Error opening input file` و8 `cannot stat` جم من خطوات بتاخد ناتج خطوة فشلت؛ 11 فشل filter graph (crop 876×1560 على مصدر 720×1280)؛ و`while read` + ffmpeg أكل الـ stdin.

## 13. التجمّد
ثقة متوسطة: الحد مقترح، اتأكد معاه أول مرة.
- على الفيلم النهائي: تجمّد أطول من 2 ث ومش hold مقصود = فشل QA.
- يدوي (مفيش أمر لسه، شوف ROADMAP.md): `ffmpeg -nostdin -i final.mp4 -map 0:v:0 -vf freezedetect=d=2 -f null - 2>&1 | grep -o 'freeze_[a-z]*: [0-9.]*'` (بيطبع `freeze_start` و`freeze_duration` و`freeze_end`). في kosif-tool: `python3 .claude/skills/kosif-superpowers/scripts/video_eyes.py report film.mp4 --out eyes` (motion energy، frozen flags، hard cuts).
- التصليح: ساعة العالم أبطأ + push صغير، أو plates أطول. وبعد `$D patch-black`: الحتة المنسوخة تتقال في التقرير إنها تجميد.
- ليه: video_eyes لقى تجمّد 3.2 ث في فيلم الذاريات؛ التصليح (ساعة العالم × 0.40، push 1.5٪، plates أطول) رفع motion energy من 0.24 لـ 0.41.

## 14. السبب قبل ما تقوله
- ماتقولوش سبب قبل ما يتكرر على أصغر حالة: رندر 1–2 ث حوالين الوقت الوحش، وغيّر حاجة واحدة في المرة (حجم الكاش، طول الحتة، عدد الرندرات مع بعض، المساحة الفاضية)، واعرض عدد الفريمات السودا قبل وبعد (عدّاد YAVG، §3).
- لحد ما يتثبت قول: «لسه بقيس». ولو تفسير قبل كده طلع غلط، قوله صريح في الرسالة اللي بعدها.
- ليه: خد 3 تفسيرات لنفس السواد: الهارد مليان، وبعدين الذاكرة والرندرات بالتوازي، وبعدين سواد بيتجمّع في آخر حتت الـ 4 ث («أنا قلتلك قبل كده إنه من الهارد المليان، وطلع غلط.»). العزل اللي نفع: «Render 2s at 178 and list per-frame brightness» و«Test a 1-second render at 179».

## 15. جدول الأعطال
كل صف ليه حارس. عطل جديد = صف جديد بحارسه قبل ما تقفل الشغلانة. التاريخ = أول مرة اتشاف.
| العرض | السبب المقاس | التصليح | الحارس |
|---|---|---|---|
| الشاشة بتسوّد وتنور (2026-11-06) | canvas بيطلع أسود بعد ~50 seek تقيل في نفس الصفحة؛ وقبلها ~120 صورة كبيرة في الكاش مع رندرات بالتوازي | حتت 1–2 ث في صفحة جديدة (§4) | حارس render.cjs + `verify` |
| «١٢ من ١٢» وفيه سواد (2026-11-06) | الفحص القديم مابيعدّش الفريمات السودا | فحص كل فريم | `verify` v1.2 (§3) |
| ساكت على الآيفون (2026-10-25، و«شتا الرياض» 2026-11-08) | MP3 جوه MP4 (الرياض: mp3 44.1 kHz 128 kb/s) | `$D mux` ← AAC 320k 48 kHz، و`--normalize` لو عالي | `verify`: `audio codec mp3 inside .mp4` |
| 807 أو 812 فريم بدل 810 (2026-11-06) | `-shortest` مع AAC priming؛ `-t 27` على نسخ = 27.067 ث | `$D mux … --duration 27` | `verify --duration` (§5) |
| MD5 الصوت مختلف (2026-10-29) | remux بـ `-shortest` وقّع آخر packet AAC | `$D mux` | MD5 يدوي (§1) |
| `Tag mp4a incompatible with output codec id '86017'` (2026-10-25) | نسخ MP3 جوه `.m4a` | MP3 ← `.mp3` للتحليل، أو AAC `.m4a` للـ mux | `ffprobe` الكوديك قبل أي extract (AUDIO_SONGS_QURAN.md) |
| `moov atom not found` (2026-11-02) | حتة اتقطعت لما الهارد اتملا | `.tmp.mp4` و`mv`، ورندر الحتة تاني | فحص الحتت قبل الـ concat (§6) |
| `Unable to capture screenshot` و`No space left on device` (2026-11-02) | الهارد اتملا (72 MB فاضيين وقت المناظرة) | فضّي وسيطات الفيلم ده بمسارها | `df -h /` قبل الرندر (ENVIRONMENTS.md) |
| `TypeError … 'metadata_errors'` (2026-10-29) | PyAV 19 مع faster-whisper لما تديله مسار | numpy float32 من ffmpeg | طريقة whisper (AUDIO_SONGS_QURAN.md) |
| `Exit code 144` (2026-10-25) | `pkill -f` اتطابق مع الشل نفسه | `kill <pid>` بالرقم | الشغل الطويل (ENVIRONMENTS.md) |
| خطأ timebase في xfade (2026-10-26) | `1/1000000` قصاد `1/15360` | `settb=AVTB,fps=30` | §11 |
| لون موف (2026-10-26) | blend screen في YUV | blend في gbrp | §11 |
| عربي مكسور (2026-10-26) | `drawtext` بيكسر وصل الحروف | canvas `fillText` بـ `direction='rtl'`، أو HTML ← PNG | فخاخ الحروف (STYLE_RECIPES.md) |
| «…» طلعت «.» (2026-11-05) | Lalezar بيرسم الحرف ده نقطة واحدة (موجود في الـ cmap، ففحص التغطية مش هيمسكه) | «،» | الكيت بيبدّله «،» لوحده ويحذّر، وفي الصفحة اليدوي القاعدة (STYLE_RECIPES.md B4) |
| «١١ · سنة» اتقرت ١١٠ (2026-10-31) | «·» جنب أرقام هندية | «،» أو «—» | lint الأرقام (STYLE_RECIPES.md) |
| خط صغير (2026-10-30، و#42) | `//` جوه `txt()` في سطر واحد قفل باقي الدالة؛ والخطوط ماتحمّلتش قبل أول فريم | `/* */`؛ `document.fonts.load` قبل أول رسم | §10 + ستيل عند 0 ث |
| `Identifier 'RED' has already been declared` (2026-11-02) | موديولين بنفس الاسم، فـ ready مااتعرّفش | IIFE أو بادئة | `--stills` الأول ومفيش `[page error]` (§10) |
| `while read` بيقف في النص (2026-11-05) | ffmpeg أكل الـ stdin | `-nostdin` | §12 |
| `Invalid too big … width '876' or height '1560'` (2026-11-06) | crop أكبر من مصدر 720×1280 | ffprobe + clamp | §12 |
| وشين فوق بعض (2026-10-26) | crossfade طويل بين لقطتين لنفس الوش | قطع، أو dissolve 0.14–0.16 ث، أو dip لـ `#111` | STYLE_RECIPES.md + ستيلز الانتقال (§7) |
| حد تاني في لقطة البطل (2026-11-04) | كليب التتويج فيه طفلة تانية؛ seek مش دقيق جاب طفلة تانية | J3 عند 36 ث؛ `-ss` بعد `-i` عند 380.5 | §9 |
| برج مكة في فيلم الرياض (2026-11-08) | كليب «البرج بالليل» طلع برج الساعة، 5 مرات على الشاشة | شيله وحط لقطات للرياض | فحص المكان (SOURCES.md) + ورقة QC |
| الخط مش مقري (2026-10-29، وقالها 2026-11-01) | خلفية فاتحة تحت الحروف (15.5 ث: mean 246) | شريط أغمق، stroke، أو حرّك النص | NOTEXT (§8) |
| حتة 149 = 2.46 ث (2026-11-02) | `[ $k = $LAST ]` لكل worker | جدول حتت واحد من D | §6 |
| `Impossible to open 'chunks/chunks/f1_000.mp4'` (2026-11-05) | مسار القايمة اتكرر | القايمة جوه فولدر الحتت بأسامي مجردة | §6 |
| HTTP 413 (2026-11-02) | ملف 920 MB أو 1.2 GB | أجزاء ≤ ~450 MB | الرفع (ENVIRONMENTS.md) |
| `curl: option --data-binary: out of memory` (2026-11-02) | `--data-binary` بيحمّل 1.2 GB في الذاكرة | `curl -T` | الرفع (ENVIRONMENTS.md) |
| Kling 422 (2026-11-05) | text-to-video بيرفض صورة البداية | mode `image-to-video` | شكل نداءات Higgsfield (ENVIRONMENTS.md) |
