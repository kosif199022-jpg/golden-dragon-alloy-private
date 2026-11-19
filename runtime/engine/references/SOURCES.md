# المصادر: منين تجيب المادة وإزاي

اقرا ده امتى: قبل أي تحميل من لينك، ولما يبعت لينكات أو يقول «رفعت»، وقبل ما لقطة stock أو متولّدة أو أغنية تدخل الفيلم.

- `$D` = `python3 <skill>/scripts/dragon.py` (على ويندوز `python`). `$J` = فولدر الشغلانة. `D` = مدة الفيلم بالثواني.
- `$K` = `python3 <kosif-tool>/.claude/skills/kosif-superpowers/scripts`: موجود في kosif-tool بس. على جهازه `~/kosif-own/kosif-tool` (`$D where` ← `old_repos`)، وفي جلسة Claude Code هو فولدر الريبو نفسه. في claude.ai مش موجود.
- `fetch_video` في الجدول = `$K/fetch_video.py URL -o DIR`. من غير kosif-tool: `yt-dlp --no-playlist -o "DIR/v.%(ext)s" URL`.

## 1. جدول المنصات
وجّه كل لينك على حسب منصته قبل التحميل. مهلة لكل لينك: 120 ث للكليب (`timeout 120`)، و300 ث للأغنية (`timeout 300`).

| المنصة | الأمر | بيشتغل من | امتى تقف | الحقوق |
|---|---|---|---|---|
| إنستجرام `/reel/` | fetch_video (§5) | السحابة غالبًا، وجهازه | «Log in for access» | مادة لمونتاجه، والحق لصاحبها |
| إنستجرام `/p/` | مفيش: غالبًا بوست صور | — | «No video formats found!»: حطه في «ما اتنزّلش» واطلب الصور أو ريل | زي الريل |
| تيك توك فيديو | fetch_video (§5) | السحابة ساعات، وجهازه | `BLOCKED`، «Log in for access» | زي الريل |
| تيك توك فيديو (مرجع ستايل بس) | المتصفح المدمج على جهازه: كابشن الصفحة + `canvas` seek كل 1 ث ← ورقة كادرات (LESSONS.md، 2026-11-10) | السحابة لما الجهاز مربوط | السكرين شوت timeout: كرّر مرة | للتحليل بس، مش لنسخ المادة |
| تيك توك `/photo/` | `$D tool tiktok-post` (§3) | السحابة (اتجرب 2026-11-08) وجهازه | exit 1 | للمونتاج الشخصي، واسم `creator` |
| بروفايل تيك توك أو إنستجرام | مفيش: اطلب لينكات فردي | ولا مكان | على طول (رفض أو JSON/429) | شخص عادي: PROTOCOL.md |
| يوتيوب | fetch_video على جهازه | جهازه بس | السحابة: «Sign in to confirm» على طول | مرجع، مش ترخيص |
| SoundCloud | `yt-dlp "scsearch6:…"` بـ `--match-filter id=…` (§12) | السحابة وجهازه | «DRM protected» | `RIGHTS.md` (§11) |
| Pinterest | WebSearch على pinterest.com، وبعدين `fetch_video --classify` | السحابة وجهازه | الـ pin مش فيديو | مش مصدر ترخيص: لقطة تانوية (≤720p) باسم صاحبها |
| Pexels | WebSearch على pexels.com، وبعدين `$K/stock_fetch.py pexels` (§10) | السحابة ساعات، وجهازه | Cloudflare challenge | Pexels License |
| Mixkit، Coverr، Commons | `$K/free_footage.py search` وبعدين `download` (§10) | السحابة وجهازه | 429 بـ Retry-After 600 ث | لكل كليب (§11) |
| معاينة أغنية عليها DRM | `$K/song_preview.py` (§12) | السحابة وجهازه | — | `.rights.json`: مسودة خاصة |
| نص القرآن | `$K/quran_text.py fetch 35:34 --out DIR`، ومن غيره `api.alquran.cloud/v1/ayah/35:34/quran-simple` | السحابة وجهازه | exit 3 (شبكة) أو 4 (آية غير المطلوبة) | بالحرف من الـ API، عمره ما يتكتب بالإيد |
| التاريخ الهجري | api.aladhan.com (`/v1/gToH/DD-MM-YYYY`) | السحابة وجهازه | — | — |
| رقم على الشاشة | مصدرين أخبار بلينك | — | مصدر واحد = مايظهرش | سطر في `sources.md` (PROTOCOL.md) |

- صفحة صوت تيك توك (`/music/`) مش مدعومة: اطلب لينك فيديو عليه الصوت ده، أو الملف نفسه.
- ليه: FREE_STOCK.md في v1.1 كان مواقع stock بس، فقواعد المنصات كانت بتتكشف من الأول في كل شغلانة.

## 2. لما اللينك يتقفل
- محاولة واحدة عادية لكل لينك، مش أكتر.
- اتقفل لو طلع: `BLOCKED …`، «Log in for access»، «Sign in to confirm you're not a bot»، «DRM protected»، أو JSON/429 في بروفايل.
- وقّف اللينك ده وكمّل باقي الشغل. السبب IP السحابة، مش الكود. قوله في سطر واحد، واكتبه في «ما اتنزّلش» في التقرير (PROTOCOL.md):
  «اللينك ده مقفول من سيرفر السحابة، مش من الكود. نزّله من التطبيق وارفعه هنا: https://claude.ai/artifact/52jZrcrPnHByPPVKKXFgSP، أو صوّر الشاشة وإنت مشغّله، أو ابعتلي الكلام مكتوب، أو نشغّله على جهازك.»
- على جهازه بدخوله هو (مفيش حاجة بتتنسخ ولا بتتحفظ): `$K/fetch_video.py URL -o DIR --cookies-from-browser chrome`. لو Chrome رفض: `--cookies cookies.txt` متصدّر من متصفحه.
- ممنوع: لف على `player_client`، و`--impersonate`، وتحميل برامج جاهزة من برّه، وretry في لوب. رفض المصنّف نهائي: ماتعيدش صياغة نفس الأمر (ENVIRONMENTS.md).
- ليه: أصر على يوتيوب («لازم تحمل فيديو اليوتيوب … اصنع اي حل»)، والمصنّف رفض لوب `player_client` و`--impersonate` كـ [Bot Check Circumvention]. حمّله هو ورفعه.

## 3. بوستات صور تيك توك
- اللينك القصير (`vt.tiktok.com`) مابيبانش صور ولا فيديو: حلّه الأول. اللينك اللي فيه `/photo/<id>` عمره ما يروح yt-dlp ولا fetch_video: بيقعوا بـ «Unsupported URL»، وتلميح fetch_video بـ `--update` أو `--cookies` غلط هنا.
```bash
$D tool tiktok-post URL --out $J/src/<id> [--no-images | --no-music] [--html SAVED_PAGE]
```
- الأداة بتحل اللينك لوحدها. `saved 0 images` ومعاها `note: images: this post has none (a video post? …)` = فيديو: روح لـ fetch_video. اللينك الكامل في `resolved_url` جوه `manifest.json`.
- بتحفظ: `00.jpg`، `01.jpg`… بترتيب البوست وبمقاس الصفحة (غالبًا مش 9:16: من 1080×178 لـ 1080×1920)، و`music.mp3` (غالبًا MP3 128 kbps، 44.1 kHz)، و`manifest.json` (`source_url`، `resolved_url`، `id`، `creator`، `desc`، `music_title`، `music_author`، `files`، `failed`، `skipped`، `fetched_at`، `note`).
- exit: `0` كله اتحفظ · `1` البوست ماتقراش (السبب بيتطبع) أو ملف وقع (السبب في `failed` جوه `manifest.json`) · `2` أمر غلط. `--no-images` و`--no-music` مع بعض لأ.
- الصوت MP3: عمره ما يتنسخ جوه MP4 (بيطلع ساكت على الآيفون). بيدخل الفيلم بـ `$D mux film.mp4 $J/src/<id>/music.mp3 final.mp4 --duration D` (AAC 320k 48 kHz).
- الصور مش 9:16: cover أو خلفية مموهة (STYLE_RECIPES.md، C2).
- لينكات الصفحة بتخلص في ساعات: شغّل الأداة تاني بدل اللينكات القديمة. بوست واحد في كل فولدر. `--html` بيقرا صفحة متحفظة، واللينكات اللي جواها لازم تكون لسه شغالة.
- exit 1 من السحابة (login، captcha، منطقة): §2. الصوت ناقص في `skipped`؟ محاولة واحدة: `$K/fetch_video.py https://www.tiktok.com/@user/video/<id> -o DIR --quality audio` (نفس الـ id بـ `/video/` بدل `/photo/`).
- بتقرا `__UNIVERSAL_DATA_FOR_REHYDRATION__` ← `__DEFAULT_SCOPE__["webapp.reflow.video.detail"]` (أو `["webapp.video-detail"]`) ← `itemInfo.itemStruct`: الصور من `imagePost.images[].imageURL.urlList`، والصوت من `music.playUrl`. تيك توك غيّر الصفحة؟ `tools/fetch/README.md`.
- على ويندوز، من فولدر المهارة: `py tools\fetch\tiktok_post.py URL --out "%USERPROFILE%\Desktop\منشور تيك توك"`.
- ماتعملش `mv` ولا glob ولا تقرا `info.json` ورا تحميل ماشفتش الـ exit بتاعه.
- ليه: بوستات صور جت 2026-10-24 و2026-11-06، والمرتين fetch_video اشتغل الأول والخطوات اللي وراه وقعت. يوم 11-06 اتحلت بالإيد: 9 صور و`music.mp3` (MP3، 57.65 ث).

## 4. استلام المادة وسجل اللينكات
- بيبعت دفعات على كذا رسالة ورا بعض («وايضا هذا»، «استفد من ده»): لينكات vt.tiktok.com وإنستجرام، وسكرينشوت بيشاور على مشكلة، وملفات مهارات أو بروتوكول (EXTERNAL_SKILLS.md)، والكبير من صفحة الرفع («رفعت»، §6).
- اللينك اللي يوصل والشغل ماشي يدخل كتالوج نفس الشغلانة. المكرر يتشال بالـ id بتاع البوست (الرقم في اللينك بعد ما يتحل)، مش بالكود القصير.
- كل كليب يتفحص ويتكتب في `$J/catalog.json`: مين، فيه إيه، أشرطة الكتابة المحروقة، الوشوش، الجودة 1–4، مكرر من إيه. زي `out/20261031-mayar7/catalog.json`: `url`، `ok`، `file`، `uploader`، `caption`، `w`، `h`، `dur`، `fps`، `content`، `burned_text`، `her_voice`، `quality`، `duplicate_of`، `best_moments` (`t0`، `t1`، `what`، `clean`).
- ملف لينكات لكل موضوع، زي `out/mayar_links.md` (115 لينك اتأكد إنها عن ميار)، عشان لما يقول «ارسل لي روابط كل مقاطع ميار».
- سجل واحد لكل اللينكات: `{id, url, file, duration, status, date}`، والـ `status` واحدة من `ok` · `blocked` · `photo` · `login`. مكانه `out/links.json` في السحابة، و`data/links.json` في فولدر «التنين الأسود» على جهازه. يدوي (مفيش أمر لسه، شوف ROADMAP.md).
- قبل أي تحميل بُص في السجل. id متسجل `login` (سن أو تسجيل دخول) ماتجربوش تاني، إلا لو قال إنه رفعه.
- ليه: تيك توك 7702950008718413064 («may not be comfortable for some audiences») اتجرب 11-04 وتاني 11-06. ولحد 11-08 بعت تقريبًا 253 لينك vt.tiktok.com و152 إنستجرام (أرقام بتتغير، مش قاعدة).

## 5. نظافة التحميل
- كل لينك في فولدر لوحده `$J/src/<id>/` بمهلة، والناتج الوحيد اسمه `v.mp4`، وسطر حالة لكل لينك: `<id> <المدة>` أو `<id> FAIL <السبب>`. الخطوات اللي بعده للـ OK بس.
```bash
for u in URL1 URL2; do
  id=$(echo "$u" | sed -E 's#[?].*##; s#/+$##; s#.*/##'); d="$J/src/$id"; mkdir -p "$d"
  timeout 120 $K/fetch_video.py "$u" -o "$d" > "$d/log.txt" 2>&1
  f=$(ls "$d"/*.mp4 2>/dev/null | head -1)
  if [ -n "$f" ]; then mv "$f" "$d/v.mp4"; echo "$id $(ffprobe -v error -show_entries format=duration -of csv=p=0 "$d/v.mp4")"
  else echo "$id FAIL $(tail -1 "$d/log.txt" | cut -c1-120)"; fi
done
```
- ماتعملش glob على أسامي yt-dlp الخام (هاشتاجات، مسافات، عربي) برّه فولدر اللينك.
- انسخ اللينكات من الناتج زي ما هي: ماتكتبش id ولا timestamp بإيدك. `curl -fsSL` عشان خطأ HTTP يوقف بدل ما يتحفظ كملف.
- بعد كل تحميل: النوع والحجم (`file -b F`، `ffprobe`، أو PIL). أقل من 10 KB (حد مقترح)، أو نص أوله `<?xml` أو `version https://git-lfs` = مرفوض.
- موديلات GitHub LFS من media.githubusercontent.com، مش raw (بيدّي مؤشر LFS).
- ليه: `mv: cannot stat 'src/*.mp4'` بعد تحميل فشل؛ لينك CloudFront اتكتب بالإيد فاتحفظت صفحة AccessDenied XML باسم `k8.png`؛ و`yunet.onnx` وصل 378 بايت (مؤشر LFS).

## 6. الملفات اللي هو بيرفعها
- ملف كبير: ابعتله صفحة رفع الفيديوهات https://claude.ai/artifact/52jZrcrPnHByPPVKKXFgSP وقوله: اختار أصغر نسخة (تسجيل شاشة 38 MB أحسن من export 483 MB)، وسيب الصفحة مفتوحة لحد «جاهز» (الآيفون بيوقّفها لو سبتها)، وبعدين اكتب «رفعت».
- السحب محتاج أدوات Artifact وArtifactData (Claude Code). من غيرهم قوله في سطر وكمّل في Claude Code. الصفوف بـ `ArtifactData` (`list`، collection `uploads`)، وكل حتة بـ `Artifact` (`read`، `path: <chunk id>`)، وبعدين الضم:
```bash
python3 -I <kosif-tool>/.claude/skills/kosif-upload-link/scripts/join_parts.py --rows <dir> --parts <dir> --out <dest>
```
- exit 1 = حتة ناقصة أو الحجم غلط. من غير kosif-tool: ضم الحتت بترتيب `index` وقارن الحجم بـ `size` في الصف. يدوي (مفيش أمر لسه، شوف ROADMAP.md).
- قبل البنا: الحجم والمدة وورقة كادرات، وقارنهم باللي قاله عن الملف:
```bash
ffprobe -v error -show_entries format=duration,size -of csv=p=0 F
ffmpeg -nostdin -v error -i F -vf fps=16/DUR,scale=-2:220,tile=8x2 -frames:v 1 sheet.jpg   # DUR = المدة بالثواني
```
- 18 MB بالظبط، أو مدة أقصر من اللي قاله = الملف اتقطع: اطلب رفع تاني أو لينك Drive أو WeTransfer.
- الصفحة شايلة ~1 GB. اسأله قبل ما تمسح رفعات قديمة.
- في claude.ai الملف بيتلزق في الشات ويوصل `/mnt/user-data/uploads`، وعلى جهازه الملفات عنده من غير رفع. رفع التسليم (حتت ≤450 MB) في ENVIRONMENTS.md.
- ليه: رفع `.mov` وقف لما ساب الصفحة؛ mp4 بـ 483 MB مالقاش مكان (700 MB من 1 GB مليانين)؛ ملف المفروض إنه فيديو يوتيوب طلع فيلم قديم؛ وكذا رفعة كانت 18 MB بالظبط.

## 7. بوابات بنك اللقطات
البنك (pool) بيتبني آلي، وكل لقطة بتعدّي على دول:

| البوابة | الحد | ملاحظة |
|---|---|---|
| القطعات | `select=gt(scene,0.30)` | جوه كل range مختار [ss, ss+L] كمان: اللقطة = تصويرة واحدة. فيه قطع؟ حرّك ss بعده أو قصّر L |
| الطول | أقل من 2.2 ث يتشال | التصويرة الطويلة تتقسم كل 6.5 ث |
| الوش | YuNet | الكادر على الوش: `$D run dragon_montage station analyze --job $J --clip a.mp4` بيكتب `faces_box` و`face_center` |
| الكتابة المحروقة | tx = نسبة البكسل اللي p > 0.3 | لقطة البطل: tx > 0.004 تتشال. الـ b-roll: tx > 0.003 |
| الضلمة | متوسط luma للـ b-roll أقل من 48 (من 255) يتشال | على كادر من نص اللقطة |
| الناس | b-roll فيه ناس يتشال لو الطلب «من غير ناس» | `--no-people` في free_footage بيبص على العنوان بس: بُص بعينك |
| البديل | الـ b-roll اللي وقع | الكليب الجاي اللي مااتستخدمش من نفس الـ theme (`next_alt()`) |

- موديل الكتابة: `text_detection_en_ppocrv3_2023may.onnx` (opencv_zoo، ~2.4 MB، مش جوه المهارة) بـ onnxruntime. الدخل يتصغّر لمضاعف 32 بنفس النسبة، ويتعمله normalise RGB: `(x/255 − [0.485,0.456,0.406]) / [0.229,0.224,0.225]`. من غير ده بيرجّع 0 لكل لقطة.
- الكود: `out/20261105-ten/pool.py` سطر 66 (القطعات) و94–95 (2.2 و6.5)، و`extract.py` سطر 25–37 (`lum`، `txscore`) و39–46 (`next_alt`) و74 (البوابة). يدوي (مفيش أمر لسه، شوف ROADMAP.md).
- فحص سريع للقطعات جوه المهارة: `$D run talking_head sheet DIR clip.mp4` بيطبع `hard cuts at: …` (scene > 0.35).
- ليه: دخلت كولاجات، وb-roll ضلمة، ولقطة مسرح فاتحة على كابشن قناة تانية، وX05 قطع على لقطة عياط عليها كابشن، والموديل رجّع 0 لكل اللقطات.

## 8. الكابشن المحروق والأسماء الممنوعة
- لكل مصدر: الفترات المتوسخة (`[in, out]`) والـ content box. عمرك ما تختار لحظة جوه فترة متوسخة أو برّه الـ box.
- الكابشن واللوجو والشريط: قص بالـ box. `box` = `[x, y, w, h]` بالبكسل للجزء النضيف اللي يفضل. اللي اتعرفوا:

| المصدر | box |
|---|---|
| ريلز منى الشاذلي | `[0,0,1080,1420]` (`MB` في `out/20261108-trio/trio_lib.py`) |
| استقبال السيسي | `[0,330,1080,1590]` |
| DfHn7AVMiS_ | `[0,0,1080,1560]` |
| t5 (720×1280) | `[0,0,720,1040]` |
| c25 | `[0,170,720,1110]` |

- كابشن ممنوع قصير: حرّك الـ in-point. اقتباس J2 اتنقل من 11.7 لـ 17.0 ث، لأن «الشوربجي» ظاهر من ~11 لـ ~16 ث.
- لوجو على وشها: شيل الكليب.
- لوحة (plate) مغطية كابشن: تفضل طول الانتقال. كابشن c12 ظهر في match cut، واتحل لما `coverPlate` كمّل طول الانتقال.
- blur أو delogo بس لو مفيش قص نضيف: blur بحواف ناعمة زي `out/20261029-mayar/blur/S00.json`، أو `-vf delogo=x=X:y=Y:w=W:h=H` للعلامة اللي ماتتقصّش.
- «الشوربجي» عمره ما يظهر على الشاشة، بأي شكل («ميار الشوربجي»، «ميار عثمان الشوربجي»). في الهاشتاج بس (LESSONS.md).
- قبل الرندر: `grep -c 'الشوربجي' film/index.html` لازم 0. ده بيفحص الصفحة بس، والمحروق في الفوتيج بيبان في الستيلز: ستيل عند أول كل لقطة، وبُص عليه.
- اتلقط قبل كده: «ميار الشوربجي» في S00 وJ2، و«علي الجابري» على لقطتين (قص فوقه، واسمه في التترات كمصدر)، وعلامة M.Seoudi، و«عاجل»، ولوجوهات قنوات، ولوجو على وشها.

## 9. المكان في الـ stock
فيلم باسم مكان: الكليب يدخل بس لو:
1. العنوان أو الوصف فيه اسم المكان.
2. 3 كادرات منه (10٪ و50٪ و90٪) مافيهاش معلم من مكان تاني، ولا ناس أو كتابة أو لوجو مش عايزهم.
3. عدّى كلمات الاستبعاد: معالم بلاد تانية، زحمة، تترات، كولاج.
4. عدّى بوابة الضلمة (luma ≥ 48 من 255، §7).
- عنوان عام زي 'City View at Night' مش دليل مكان. الكليب اللي مااتأكدش يتعلّم (`egypt: false` زي `out/20261105-ten/broll_catalog.json`)، وعمره ما يدخل على إنه المكان.
- اكتب في الـ manifest لكل كليب اللي شفته فيه. يدوي (مفيش أمر لسه، شوف ROADMAP.md).
```bash
$D run talking_head sheet $J/sheets clipA.mp4 clipB.mp4     # المقاس والطول والقطعات وشريط 6 كادرات
ffmpeg -nostdin -v error -i clip.mp4 -vf fps=16/DUR,scale=-2:220,tile=8x2 -frames:v 1 sheet.jpg
```
- وبعد التجميع ورقة QC للفيلم كله (QA.md).
- ليه: «شتا الرياض» خد كليب «البرج بالليل» وطلع برج الساعة في مكة، وظهر 5 مرات واتلقط في ورقة QC الأخيرة بس (على الأرجح Pexels 5057523: الـ id الوحيد في الـ manifest اللي مش في `build.py` بعد التصليح). وأفلام مصر خدت هرم مايا، وتشيرليدرز، وتترات، وبالونات كابادوكيا متعلّمة «الأقصر» (هو اللي لقاها).

## 10. شغل الـ stock
ثقة متوسطة (اتجرب في فيلم الرياض بس): اتأكد معاه أول مرة قبل ما تمسح الأصول.
- **مكان بعينه:** WebSearch على pexels.com (allowed_domains)، وخُد الرقم من آخر كل لينك (`-<id>/`):
```bash
$K/stock_fetch.py pexels ID1 ID2 --dry-run                   # الحجم والمقاس الأول
$K/stock_fetch.py pexels ID1 ID2 -o $J/clips --max-mb 0
```
- الافتراضي 120 MB (`--max-mb 120`) بيتخطى كليبات UHD، و`--max-mb 0` = من غير حد. Cloudflare challenge = وقّف، مفيش تجاوز.
- **b-roll عام:** Mixkit وCoverr الأول (سريعين، 1080p، رخصة باسمها)، وCommons الآخر:
```bash
timeout 300 $K/free_footage.py search "night city" --orientation portrait --no-people
$K/free_footage.py download ID1 ID2 --out $J/clips --quality 1080
```
- Commons: الملفات اللي 4K بس بتترفض بـ `--quality 1080` أو `--max-height 1920`، و429 بـ Retry-After 600 ث = غيّر المصدر وماترجعلوش في نفس الشغلانة. Pixabay محتاج `PIXABAY_API_KEY` في البيئة، وعمر المفتاح ما يتلزق في الشات.
- **بعدها:** كل لقطة في الخطة تترندر مرة واحدة 1080×1920، 30 fps (CRF 14 veryfast)، والسرعة والقص والجريد جواها. وبعدين امسح الأصول بمسار صريح، والـ manifest يفضل (§11).
- جوه المهارة مفيش عميل فيديو stock لسه: `$D tool stock` بيقع (`No module named 'free_footage'`)، ومحطة المونتاج محتاجة `DRAGON_FREE_FOOTAGE=<kosif-tool>/.claude/skills/kosif-superpowers/scripts/free_footage.py` قبل `$D run dragon_montage edit … --stock "query"`. في claude.ai: ابعتله روابط البحث (FREE_STOCK.md §4) أو اطلب الملفات (ROADMAP.md، T5).
- أرقام الرياض: 12 كليب Pexels = 462 MB أصول (أكبرهم 132.8 MB)، بمقاسات من 1280×720 لـ 3840×2160 و2160×3840، و24–60 fps. اتمسحوا بعد ما اللقطات اترندرت، والفاضي كان ~300 MB.
- ليه: المصادر اللي من غير مفتاح مافيهاش فوتيج مدن، وCommons ضيّع كليبات في 4K و429، والهارد كان قرب يتملي.

## 11. سجلات الحقوق
- كل كليب stock أو مفتوح ليه سجل: `{id, source, page, file_url, licence, licence_url, licence_terms, bytes, width, height, fps, duration}`، زي `out/20261108-riyadh/pexels_manifest.json` (12 سجل). `stock_fetch.py` بيكتب `manifest.json`، و`free_footage.py` و`free_photos.py` بيكتبوا `<file>.json` جنب كل ملف و`ATTRIBUTION.md`.
- قبل ما تمسح فولدر الكليبات، السجل يطلع لفولدر الشغلانة:
```bash
cp $J/clips/manifest.json $J/pexels_manifest.json && rm -r $J/clips
```
- Mixkit: الرخصة لكل كليب. Restricted = مفيش استخدام تجاري (5 من 9 في `out/20261106-tt/foot/ATTRIBUTION.md`). إعلان أو شغل بفلوس: `--commercial`.
- كل أغنية ليها `$J/song/RIGHTS.md`: المصدر (الرافع ورقم التراك)، وإنه هو اللي اختارها، وشباك المقطع بأول وآخر كلمة، والمعالجة، و«not cleared for commercial use»، وكريدت في كارت النهاية. مثال من `out/20261101-mayar22/song/RIGHTS.md`:
```text
Source used: SoundCloud upload by "A Eid" (track 2422446687), fetched for the owner's personal tribute edit at his explicit choice.
Excerpt: 110.0–168.6 s («وقف الخلق ينظرون جميعًا… كفوني الكلام عند التحدي»), fades 0.3/0.65 s, loudnorm -14 LUFS, AAC 320k.
Rights: the recording/composition belong to their owners; not cleared for commercial use. Credit the song on the end card.
```
- كريدت الأغنية سطر صغير تحت «مونتاج وإخراج Mahmoud Elkosif» و«تابعني على فيسبوك» (OWNER.md §9).
- في رسالة التسليم: صفحات المصادر. وقوله مرة واحدة إن المنصات ممكن تكتم أغنية عليها حقوق، وللنشر العام يستخدم الصوت المرخّص من المنصة.
- مادة تيك توك وإنستجرام: الحق لصاحبها، واسمه من `creator` أو `uploader`.

## 12. الأغاني وDRM واللوب
- الترتيب: لينكه هو الأول. مفيش؟ رفعة مش DRM بـ `scsearch`، والتراك يتثبت بالـ id:
```bash
yt-dlp --flat-playlist --print "%(id)s | %(title)s" "scsearch6:<title artist>"
timeout 200 yt-dlp -q --no-playlist -x --audio-format m4a --match-filter 'id=52902701' -o 'songs/anthem_inst.%(ext)s' 'scsearch6:Egypt national anthem instrumental'
```
- «DRM protected» = وقّف، مفيش تجاوز. البديل: المعاينة الرسمية 30 ث (iTunes أو Deezer) ومعاها `.rights.json`، أو اطلب الملف منه:
```bash
$K/song_preview.py search "<artist song>" --country eg --out $J/song
$K/song_preview.py download 1 --out $J/song      # نفس --out: بيقرا آخر بحث من الفولدر ده
```
- المعاينة للمسودات الخاصة. النشر العام بصوت المنصة المرخّص، والكريدت للفنان.
- أغنية قصيرة: طوّلها بتكرار جمل كاملة على البيت بس، أو لوب من غير فاصل: طول اللوب بـ correlation search، وcrossfade equal-power 0.08 ث (`a=sqrt(linspace(1,0,n))`، `b=sqrt(linspace(0,1,n))`). يدوي (مفيش أمر لسه، شوف ROADMAP.md). اتعمل لأغنية 15.5 ث في الفيلم الفرحان.
- MP3 أو أي كوديك غير AAC بيدخل الفيلم بـ `$D mux` بس. باقي قواعد الصوت وSuno في AUDIO_SONGS_QURAN.md، والفلوس في OWNER.md.
- ليه: رفعات تامر عاشور وفاطمة عيد الرسمية على SoundCloud كانت DRM، فاتاخدت معاينة iTunes.

## 13. اللقطات المولّدة
ثقة متوسطة: اتأكد معاه أول مرة. التوليد بفلوس: السعر و«أيوه» الأول (OWNER.md §6)، وقواعد الناس في PROTOCOL.md.
- Kling وSeedance وHiggsfield مابيرجعوش بمقاس التسليم. افحص كل كليب، واعمله cover لـ 1080×1920 و30 fps قبل التايملاين:
```bash
ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate:format=duration -of csv=p=0 gen.mp4
ffmpeg -nostdin -v error -i gen.mp4 -vf "scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920,setsar=1,fps=30" -an -c:v libx264 -crf 14 -preset veryfast -pix_fmt yuv420p gen_1080.mp4
```
- هتبطّأه؟ حط `setpts=K*PTS,minterpolate=fps=30:mi_mode=mci` مكان `fps=30` (K = قد إيه أبطأ، زي 1.25).
- كليب اتعمل تاني مكان كليب: السرعة = المدة الجديدة ÷ القديمة، والـ t_in يتضرب في نفس الرقم.
- افحص كل كليب للقطع المستخبي: `$D run talking_head sheet DIR gen.mp4` (`hard cuts at: …`)، أو `python3 <kosif-tool>/.claude/skills/living-site/tools/cutscan.py gen.mp4` (SSIM بين كل فريمين ورا بعض أقل من الوسيط − 0.25 = قطع، وexit 1). فيه قطع؟ ولّده تاني، وعمرك ما تخبيه بـ dissolve.
- الكليبات المتسلسلة: كل واحد يبدأ من آخر فريم في اللي قبله بالظبط (`ffmpeg -nostdin -v error -y -i prev.mp4 -update 1 last.png`)، وكل برومت يبدأ بـ `One continuous single shot, no cuts.` ويسمّي حركة كاميرا واحدة.
- ليه: Kling 4 رجع 1076×1924، 24 fps، 5.04 ث؛ وSeedance بيرجّع ~3.7–5 ث؛ وliving-site شاف موديلات بتقطع في نص الكليب.
