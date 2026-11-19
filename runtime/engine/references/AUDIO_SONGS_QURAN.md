# الصوت والأغاني والقرآن والدعاء

اقرا ده امتى: أي فيلم فيه أغنية أو صوت حد أو دعاء أو تلاوة، وقبل أي مكساج أو mux أو كلام أغنية على الشاشة.

`$D` = `python3 <skill>/scripts/dragon.py` (على ويندوز `python`)، `D` = مدة الفيلم بالثواني = مدة ماستر الصوت، `FINAL` = الملف اللي هيتبعت نفسه. الأوامر bash (على ويندوز Git Bash). بوابات التسليم كلها في QA.md.

## 1. قرار الصوت في 3 صفوف
قيس الأول الكوديك والعلو:
```bash
ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 SRC   # aac ولا mp3 ولا غيرهم
$D verify SRC                                                                        # بيطبع loudness_lufs وtrue_peak_dbtp
```
| الصوت اللي جاي | تعمل إيه | في التقرير |
|---|---|---|
| AAC، والعلو بين −16 و−12 LUFS، والذروة مش فوق −1 dBTP | `$D mux VIDEO AUDIO OUT --duration D` بينسخه (`audio aac -> aac copy`)، وبعده MD5 (§3) | «audio AAC (copy, MD5 ✓)» |
| AAC برّه الحدود | نفس الأمر: يتنسخ برضه، وصوته مايتغيّرش من غير ما يقول (السؤال الوحيد: لأن `--normalize` هيكسر النسخ بالبايت) | الـ LUFS والذروة، و«لو عايز أظبط الصوت للمستوى العادي قولي». التظبيط = نفس الأمر + `--normalize` |
| مش AAC (MP3، Opus، FLAC، WAV/PCM) | `$D mux VIDEO AUDIO OUT --duration D` بيحوّله AAC 320k 48 kHz كده كده، فلو برّه −16..−12 LUFS أو فوق −1 dBTP: `--normalize` افتراضي من غير سؤال | «اتحوّل AAC 320k»، والأرقام قبل وبعد |

- `--normalize` = `loudnorm=I=-14:TP=-1.5:LRA=11`. المكساج بتاعنا دايمًا −14 LUFS / TP −1.5 dBTP (§5).
- `verify` عمره ما بيفشل على العلو: بيطبع `WARN loudness …` و`WARN true peak …` بس (بالتصميم)، فالرقمين يتكتبوا في رسالة التسليم بإيدك. التحذير بيطلع برّه −16.5..−11.5 بس (هامش 0.5)، فاقرا الرقم نفسه.
- `$D verify FINAL` exit 1 (MP3 جوه MP4، سواد، فريمات غلط) = يتصلّح قبل الرفع، مش بعده.
- الرياض: MP3 عند −8.7 LUFS و+1.2 dBTP، اتصلّح AAC 48 kHz 320 kb/s متظبط، ومااعترضش. دلوقتي ده: `$D mux silent.mp4 song.mp3 final.mp4 --duration 167.08 --normalize`.

## 2. AAC بس جوه MP4، والكوديك قبل الحاوية
- صوت أي MP4 بيتسلّم = AAC. AAC بس هو اللي يتنسخ؛ MP3 وOpus وFLAC وWAV/PCM يبقوا AAC-LC 320k 48 kHz.
- MP3 جوه MP4 بيطلع ساكت على الآيفون حتى لو ffprobe شايف صوت: 2026-10-25 («الفيديو من غير صوت، اتأكد من المشكلة دي»)، و«شتا الرياض» 2026-11-08 (`assemble.py` نسخ `a.mp3` بـ `-c:a copy` فطلع mp3 44.1 kHz 128 kb/s؛ المصلّح aac 48 kHz 320 kb/s).
- MP3 غالبًا في: أصل تيك توك، مزيكا بوستات الصور (`$D tool tiktok-post URL --out DIR` بيحفظ `music.mp3`، SOURCES.md)، تحميلات Suno، وشوية تراكات SoundCloud.

| الكوديك | للتحليل | للفيلم |
|---|---|---|
| aac | `ffmpeg -nostdin -i SRC -vn -map 0:a:0 -c:a copy song.m4a` | نفس الـ m4a |
| mp3 | `ffmpeg -nostdin -i SRC -vn -map 0:a:0 -c:a copy song.mp3` | ادّي الـ mp3 لـ `$D mux` على طول |
| غيرهم | `ffmpeg -nostdin -i SRC -vn -ac 2 -ar 48000 song.wav` | `$D mux` |

- نسخ MP3 جوه `.m4a` بيفشل: `Tag mp4a incompatible with output codec id '86017'`. و`$D beats` و`$D words` بياخدوا WAV (librosa مابيقراش m4a).
- `$D verify` بيفشل على `audio codec mp3 inside .mp4`.
- على جهازه، kosif-tool لسه بيسمح بـ MP3 جوه MP4 (`.claude/skills/kosif-superpowers/scripts/export_profile.py` سطر 41، `tools/render_html.cjs` سطر 693، `verify_video.py` سطر 18، `playbooks/export-standard.md` سطر 15): أي ناتج منه يعدّي على `$D mux` برضه.

## 3. النسخ بالبايت وMD5
تراكه AAC ومفيش حاجة متضافة عليه = يتنسخ بالبايت، ويتثبت إن MD5 صوت الناتج = MD5 الماستر:
```bash
a=$(ffmpeg -v error -i FINAL -map 0:a -c copy -f md5 -)
b=$(ffmpeg -v error -i AUDIO_MASTER -map 0:a -c copy -f md5 -)
[ "$a" = "$b" ] && echo AUDIO_MD5_OK || echo AUDIO_MISMATCH
```
- الرقمين بيتطابقوا لما الماستر بطول D بالظبط. لو أطول، `mux` بيقصّه عند حافة packet (ممكن يقصر frame AAC واحد، 21–23 ms) والـ MD5 الكامل يختلف، وده مش عيب. الإثبات ساعتها packet بـ packet:
```bash
ffprobe -v error -select_streams a:0 -show_entries packet=data_hash -show_data_hash md5 -of csv=p=0 FINAL > out.txt
ffprobe -v error -select_streams a:0 -show_entries packet=data_hash -show_data_hash md5 -of csv=p=0 AUDIO_MASTER | head -n "$(wc -l < out.txt)" | cmp - out.txt && echo PACKETS_OK
```
- مقطع من أول الأغنية من غير fade: ادّي الأغنية كاملة لـ `$D mux`: بيقص AAC الطويل عند حافة packet لوحده. لو لازم مقطع من النص: `ffmpeg -nostdin -ss A -i song.m4a -map 0:a:0 -c copy master.m4a` (من غير `-t`: الطول بيتحدد في `mux --duration`)، ومفيش MD5 للأغنية كلها بعدها. مقطع بـ fades أو بأصوات = مكساج (§5)، والـ MD5 بيتقارن بالمكساج.
- `mux` بيطبع الوضع: `aac -> aac copy` = اتنسخ؛ `encode` أو `normalize` = اتضغط تاني، فمفيش MD5.
- ممنوع remux لماستر مترندر بـ `-shortest`: مرة وقّع آخر packet AAC والـ MD5 اختلف.
- مثال حقيقي: «أجنحة من ورق» v2، MD5 صوت الفيلم = MD5 `mix.m4a` = `0b25d2e6…`. الفحص يدوي (مفيش أمر لسه، شوف ROADMAP.md).

## 4. ماستر صوت واحد
- كل شغلانة ليها `AUDIO_MASTER` واحد مكتوب في الخطة أو الـ spec: الأغنية منسوخة، أو `film/audio.m4a` = المكساج النهائي بالأصوات.
- الـ mux والـ MD5 الاتنين بيقروا الملف ده، وأي مكساج في النص ليه اسم تاني (`mix_v1.m4a`). المكساج اتعاد = الـ mux يتعاد.
- ليه: ميار #9 اتعمله mux بـ `audio.m4a` اللي مافيهوش صوتها، واتعاد بـ `audio_mix.m4a`.

## 5. المكساج بـ numpy والـ ducking بالـ dB
ده اللي اتسلّم في كل أفلام نوفمبر (bint، tilawa، forty، qalb2، ajniha2، honor، trio) عند −14 LUFS:

| الحاجة | الرقم |
|---|---|
| الشغل | numpy، 48 kHz ستيريو float32 |
| فك كل حتة | `ffmpeg -nostdin -ss a -t (b-a) -i SRC -ac 2 -ar 48000 -f f32le -` |
| مستوى RMS | الأصوات 0.12–0.15، التلاوة 0.15، الأغنية تحت الكلام 0.10–0.12 (تتقاس بعد أول 5 ث لو المقدمة هادية) |
| الـ fades | حواف الصوت 40–80 ms خطي، حواف الأغنية 0.6–1.0 ث جذر (sqrt)، الآخر 1.5–1.6 ث |
| الذروة | لو عدّت 0.97 تنزل لـ 0.97 |
| التسليم | `loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000`، AAC 320k، بطول الفيلم بالظبط |

- الـ duck بـ dB ثابتة مش sidechaincompress، عشان العمق يبقى مظبوط ويتفحص: ماسك `vm` = 1 مكان أي صوت، متوسط متحرك 0.25–0.4 ث بـ `np.cumsum` (`np.convolve` خلّى الشغلانة تقع timeout)، والجين على الأغنية `1 - sm*(1 - 10**(dB/20))`.
- العمق: −10 dB لمدلي حماسي 40 ث · −11 dB تحت كلامها (الافتراضي) · −13 dB لأغنية بغُنا تحت كلام · −16 dB لمزيكا من غير غُنا تحت كلام طويل. الاختبار: جوه الصوت، الأغنية واطية بالرقم ده ±0.5 dB.
- القالب ده اتجرّب 2026-11-08 على نغمات تجريبية (العمق −11.0 dB والطول بالعينة مظبوط). يدوي (مفيش أمر لسه، شوف ROADMAP.md):
```python
import numpy as np, subprocess
SR, DUR, DB = 48000, 40.0, -11; n = int(DUR * SR)            # طول الفيلم، عمق الـ duck
def load(src, a, b):                                          # الحتة a..b ث: ستيريو 48 kHz float32
    raw = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-ss', str(a), '-t', str(b - a), '-i', src, '-ac', '2',
                          '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()
def prep(x, rms, fade, sq, skip=0.0):                         # RMS ثابت + fade (sq=True جذر للأغنية، False خطي للصوت)
    x *= rms / (np.sqrt((x[int(skip * SR):] ** 2).mean()) + 1e-9); f = int(fade * SR)
    r = np.linspace(0, 1, f)[:, None] ** (.5 if sq else 1); x[:f] *= r; x[-f:] *= r[::-1]; return x
def put(buf, x, at, mask=None):                               # at = مكانها في الفيلم
    i = int(at * SR); m = min(len(x), n - i); buf[i:i + m] += x[:m]
    if mask is not None: mask[i:i + m] = 1
bed, vo, vm = np.zeros((n, 2), np.float32), np.zeros((n, 2), np.float32), np.zeros(n, np.float32)
put(bed, prep(load('song.m4a', 162.8, 176.4), .11, .8, True), 0.0)
put(vo, prep(load('j2.m4a', 59.78, 63.25), .13, .06, False), 3.2, vm)
k = int(.3 * SR); c = np.cumsum(np.r_[0, vm]); sm = (c[k:] - c[:-k]) / k; sm = np.r_[sm, np.full(n - len(sm), sm[-1])]
g = 1 - sm * (1 - 10 ** (DB / 20)); mix = bed * g[:, None] + vo
fo = int(1.6 * SR); mix[-fo:] *= np.linspace(1, 0, fo)[:, None]; mix /= max(1.0, np.abs(mix).max() / 0.97)
mix.astype(np.float32).tofile('mix.f32'); print('duck', round(20 * np.log10(g[vm > 0].min()), 2), 'dB', len(mix) == n)
```
```bash
ffmpeg -nostdin -y -f f32le -ar 48000 -ac 2 -i mix.f32 -af loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000 -c:a aac -b:a 320k film/audio.m4a
```
- `$D mix mix.json mix.wav` لسه موجود من v1.x: `{"song": "song.m4a", "start": 162.8, "duration": 40, "voices": [{"src": "j2.m4a", "in": 59.78, "d": 3.47, "at": 3.2, "gain": 1.0}], "fadeIn": 0.4, "fadeOut": 2.5, "songGain": 1.0}`. آخره `loudnorm=I=-14:TP=-1.5:LRA=11` زي `--normalize` (في v1.2)، بس الـ duck فيه sidechaincompress (`threshold=0.015:ratio=10:attack=15:release=450`، العمق بيتغيّر مع الصوت) ومن غير RMS ثابت. لو استخدمته للسرعة: `$D mux film.mp4 mix.wav final.mp4 --duration D` (بيتحوّل AAC 320k)، واكتب الـ LUFS والذروة اللي `verify` قاسهم.

## 6. مفيش مزيكا تحت كلامها، ونسخة من غير مزيكا جاهزة
- أفلام صوتها، والدعاء، والقرآن: مفيش مزيكا متولّدة ولا مزيكا من غير غُنا (عود، نشيد instrumental، موسيقى Suno ملحمية) تحت الكلام، إلا لو طلب.
- البديل: أغنية مصرية معروفة بغُنا هو اختارها أو وافق عليها (صوتها في فواصلها §7، أو فوقها والأغنية واطية −10/−11 dB)، أو صوتها لوحده.
- نسخة من غير مزيكا تبقى جاهزة على بعد خطوة (`*_bila_musiqa.mp4`)، واعرضها في رسالة التسليم.
- لو قال «أزل / شيل / بلاش الموسيقى»: نفس كود المكساج من غير الأغنية (شيل سطر `put(bed, …)`، ويفضل صوتها + الصوت الطبيعي بتاع اللقطات)، واطلّعه `voice_only.m4a`، والصورة زي ما هي:
```bash
$D mux final.mp4 voice_only.m4a final_bila_musiqa.mp4 --duration D     # video copy: الصورة ماتتلمسش
$D verify final_bila_musiqa.mp4 --expect 1080x1920 --duration D
```
- ليه: شال المزيكا 4 مرات في 3 أيام: الدعاء 2026-11-04 («مش عايز صوت موسيقى، عايز صوت الدعاء»)، العود والنشيد في «أجنحة من ورق» 2026-11-05 («أزل الموسيقى لأنها غير مناسبة جدا. أزل الموسيقى. أزل.»)، العود في «رحلة ميار»، وموسيقى Suno في «قلب العرب» 2026-11-06 («الموسيقى بوظت الدنيا»).

## 7. صوتها في فواصل الأغنية
- اعمل خريطة للأغنية الأول: فين غُنا وفين مزيكا بس، من الفواصل اللي مافيهاش كلام في التفريغ (§10).
- كلامها في حتت المزيكا بس (المقدمة، الكوبري، آخر المازورات)، عمره ما يركب على سطر بيتغنى. حتت الغُنا تتقطع على البيت بنقلات كل 6 و8 بيت.
- مثال «هنحب مين غيرها» (`out/20261106-ajniha2/build.py`): مزيكا 0–41، غُنا 41–115، مزيكا 115–140، غُنا 140–265 ث؛ `cut(B, 40.4, 115.0, [6, 8, 6, 6, 8])`، 143.6 bpm، 74 لقطة.
- ليه: اتعمل كده بعد ما اتضايق من مزيكا بتخانق كلامها، ومااشتكاش بعدها.

## 8. قص الأغنية ونهايتها والمدلي
- المقطع يبدأ قبل أول كلمة بتتغنى ببيت واحد، ويخلص على آخر جملة. fade in 0.15–0.4 ث، fade out 0.65–1.6 ث.
- لو الجزء اللي اختاره هو آخر الأغنية: سيبها لآخر الملف وخلي مدة الفيلم تمشي وراها (مرة طلع 51 ث بدل 60). «الأغنية كاملة» = D هي التراك كله.
- qalb2: الأغنية بتدخل عند 8.8 ث من 229.85 لآخرها 340.75، فـ `DUR = round(8.8 + 340.75 - 229.85, 2)` = 119.7 ث.
- المدلي: من كورس لكورس بترتيب القصة، ومفيش جزء يتكرر. كل أغنية RMS 0.11، fades جذر 0.6 ث، تداخل 0.5–0.6 ث، وfade أخير 1.6 ث.
- forty (مدلي 40 ث، من لحد في الأغنية ← مكانها في الفيلم بالثواني): `shadia` 162.8–176.4 ← 0.0 · `wadih` 28.8–43.2 ← 13.1 · `anthem` 59.8–73.6 ← 26.9.
- ليه: طلب «مجموعة من الأغاني الوطنية المؤثرة متناسقة»، والأغنية لازم «تخلص بنهايتها الطبيعية»، من غير تكرار ولا قطعة نشاز.

## 9. البيت بالـ flux والفيز
- الـ onsets بـ numpy: mono 11025 Hz، فريمات Hann 1024 عينة، hop 256، `S = log1p(10*|FFT|)`، الـ flux = مجموع الفروق الموجبة ناقص متوسط متحرك 0.5 ث، متطبّع. الـ onsets = قمم فوق 0.12. التمبو = قمة الـ autocorrelation بين 60 و180 bpm. القطعات عند `PH + n*P` بفيز مقاس.
- التمبو مش ثابت: اقطع على الـ transients نفسها (music_rhythm_engine ماطلّعش BPM ثابت، فاتاخد 40 transient). واعمل snap لكل قطعة على أقرب onset، إلا القطعة المربوطة بسطر كلام.
- أرقام اتسلّمت: trio B `P = 0.5571` ث و`PH = 0.35` ث. الرياض: مازورة 4×0.859 = 3.436 ث، `PH = 0.31` ث، xfade 0.45 ث على حدود المازورة.
- `$D beats song.wav --out beats.json` = librosa beat_track: تمبو وقايمة بيتات بس، من غير تحكم في الفيز. للقطع: `grid.py`. يدوي (مفيش أمر لسه، شوف ROADMAP.md). اتجرّب على كليكات معروفة (P = 0.5 و0.5571 و0.859 ث): P وPH طلعوا ±0.01 ث.
```python
import json, numpy as np, subprocess, sys
sr, hop, N = 11025, 256, 1024
a = np.frombuffer(subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', sys.argv[1], '-ac', '1', '-ar', str(sr),
                  '-f', 's16le', '-'], capture_output=True).stdout, np.int16).astype(np.float32) / 32768
S = np.log1p(np.abs(np.fft.rfft(np.lib.stride_tricks.sliding_window_view(a, N)[::hop] * np.hanning(N), axis=1)) * 10)
flux = np.r_[0, np.maximum(0, np.diff(S, axis=0)).sum(1)]
k = int(.5 * sr / hop); env = np.maximum(0, flux - np.convolve(flux, np.ones(k) / k, 'same')); env /= env.max() + 1e-9
t = (np.arange(len(env)) * hop + .75 * N) / sr      # قمة الـ flux بتيجي عند 3/4 الفريم (اتقاس على كليكات)
on = [t[i] for i in range(2, len(env) - 2) if env[i] > env[i - 1] and env[i] >= env[i + 1] and env[i] > .12]
ac = np.correlate(env - env.mean(), env - env.mean(), 'full')[len(env) - 1:]
lo, hi = int(60 / 180 * sr / hop), int(sr / hop); L = lo + int(np.argmax(ac[lo:hi]))
y0, y1, y2 = ac[L - 1:L + 2]; P = (L + .5 * (y0 - y2) / (y0 - 2 * y1 + y2)) * hop / sr   # قمة الـ autocorrelation بدقة أقل من hop
PH = max(np.arange(0, P, .01), key=lambda f: np.interp(np.arange(f, t[-1], P), t, env).sum())   # الفيز المقاس
print(f'P={P:.4f} s ({60 / P:.1f} bpm)  PH={PH:.2f} s  onsets={len(on)}')
json.dump({'P': round(float(P), 4), 'PH': round(float(PH), 2), 'onsets': [round(float(x), 3) for x in on]}, open('grid.json', 'w'))
```
تشغيله: `python3 grid.py song.m4a` بيكتب `grid.json`.

## 10. whisper
| | المقابلات والكلام | الغُنا والتلاوة والشبابيك القصيرة |
|---|---|---|
| الموديل | `WhisperModel('medium', device='cpu', compute_type='int8')`، `cpu_threads` 1–4 | نفسه |
| VAD | `vad_filter=True` | `False` (التلاوة: 14/14 كلمة بدل 7/14) |
| الباقي | `language='ar'`، `word_timestamps=True`، `beam_size=5` | نفسه |

- المدخل دايمًا array numpy float32 من ffmpeg (`-ac 1 -ar 16000`)، عمره ما يبقى مسار ملف: PyAV 19 بيرمي `TypeError … metadata_errors` (13 فشل بين 10-28 و11-05، حتى بعد PR #191).
- أسامي الناس: `initial_prompt` فيه الأسامي والموضوع، و`beam_size=8`، و`condition_on_previous_text=False`، على شباك `-ss/-t`.
- مصدر طويل (المناظرة 40 دقيقة ماتت عند 353 ث وهي شغلانة واحدة): قسّمه بـ `ffmpeg -ss/-t` لحتت ≤ 10 دقايق، كل حتة `cpu_threads=1` في الخلفية (ENVIRONMENTS.md)، وادمجهم بالإزاحات. وكاش HuggingFace مايتمسحش.
- `$D words song.wav --lang ar --model medium --out words.json` (محتاج `$D setup --full`): الـ VAD فيه شغال دايمًا ومالوش flag، والموديل الافتراضي small. ينفع للمقابلات بس.
- للغُنا والتلاوة والشبابيك القصيرة: `tw.py` (من غير VAD). يدوي (مفيش أمر لسه، شوف ROADMAP.md):
```python
import json, subprocess, sys, numpy as np
from faster_whisper import WhisperModel
MODEL, VAD = 'medium', False                       # VAD=True للمقابلات بس؛ 'large-v3' للتفريغ التاني
src, out, a = sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
win = ['-ss', str(a), '-t', str(float(sys.argv[4]) - a)] if len(sys.argv) > 4 else []
pcm = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', *win, '-i', src, '-ac', '1', '-ar', '16000', '-f', 's16le', '-'],
                     capture_output=True).stdout
x = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768          # array مش مسار (PyAV: metadata_errors)
segs, _ = WhisperModel(MODEL, device='cpu', compute_type='int8', cpu_threads=2).transcribe(
    x, language='ar', word_timestamps=True, vad_filter=VAD, beam_size=5)
r = lambda v: round(a + v, 2)
S = [{'start': r(s.start), 'end': r(s.end), 'text': s.text.strip(),
      'words': [{'word': w.word.strip(), 'start': r(w.start), 'end': r(w.end)} for w in s.words or []]} for s in segs]
json.dump({'segments': S, 'words': [w for s in S for w in s['words']]}, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('\n'.join(f"{s['start']:7.2f}-{s['end']:7.2f}  {s['text']}" for s in S))
```
- `python3 tw.py voice.m4a words.json` للملف كله، أو `python3 tw.py j2.m4a w.json 54.8 64.8` لشباك (الأوقات بترجع بوقت المصدر).
- ناتجه بيتقري في `$D lyrics-sheet --transcript` وفي `quran_text.py align --words`. ملف `$D words` مايتديش لـ `align`: كل سطر فيه بيتقري كلمة واحدة.

## 11. الكلمات المؤكدة بس
- كلام الأغنية يظهر على الشاشة لما يكون متأكد بس، من واحد من 4: (1) تفريغين متفقين بعد توحيد العربي (شيل التشكيل، ووحّد أ/إ/آ وى/ي وة/ه): medium + large-v3، أو medium مرتين والكلمات المعروفة في `initial_prompt`؛ (2) مقري من فيديو الكلمات (§12)؛ (3) هو باعته؛ (4) كلمات المولّد نفسه (Suno، §17).
- كل سطر عليه sure أو unsure، والـ unsure مالوش نص. السجل `{film, text, sure, src}` زي `out/20261029-mayar/audio_plan.json`.
- اشطب المقطع اللي whisper بيألّفه في الأول (بيبدأ عند 0 قبل أول غُنا مقاس، زي «أغنية لبنانية لإليسا ليل يا ليل»)، وزبالة large-v3 («موسيقى»، «اشتركوا في القناة»).
- لو كلام اتساب: قوله، واطلب النص في سطر: «ما قدرتش أتأكد منها حرف حرف، ابعتلي الكلمات لو عايزها على الشاشة».
- على جهازه في kosif-tool: `python3 .claude/skills/kosif-superpowers/scripts/montage_pro.py transcribe song.m4a --out words.json --model large-v3 --language ar --no-vad --no-speech-threshold 1.0 --force`، وجنبه تفريغ medium.
- ليه: اللهجة في الأغاني بتطلع كلام فاضي («فتر والنقص تيلي» بدل «فاكر ولا نسيت يا ليل»)، وفيلم الرياض اتسلّم من غير كلمات لأنها ماتأكدتش حرف حرف.

## 12. القراية من فيديو الكلمات (`$D lyrics-sheet`)
لو فيه فيديو كلمات للأغنية: التوقيت من whisper، والنص من الصورة.
1. فريم كامل واحد تعرف منه شريط الكلام: `ffmpeg -nostdin -ss 17 -i lyric.mp4 -frames:v 1 f17.jpg` وبص عليه.
2. `$D lyrics-sheet lyric.mp4 sheet.jpg --band 925:1010 --times 17,21,26,30.5`
   - `--band y0:y1` بالبكسل (925:1010) أو كسور من الطول (0.84:0.94، الافتراضي = تحت).
   - مصدر وقت واحد لازم من التلاتة: `--times a,b,c` (نص كل segment)، أو `--every S` (نص كل خانة S ث: S/2، 3S/2، …)، أو `--transcript words.json` (نص كل سطر متوقّت).
3. افتح `sheet.jpg` واقرا البلاطات بنفسك، وكل بلاطة عليها وقتها. ده مش OCR: إنت (Claude) اللي بتقرا.
4. حط كل نص على أوقات الـ segment بتاعه.
- `--transcript` بيقرا سطور `{start, end}` (ناتج `$D words` أو `tw.py`). صفوف `[start, end, text]` زي `tr.json` بتاع الجلسة مابتتقريش: ادّي `--times` بنص كل صف أو حوّلها.
- مثال إليسا «ليل يا ليل» (1920×1080، الكلام حوالين y≈965): band 925:1010 والأوقات 17 و21 و26 و30.5 ث طلّعت «في شئ فينا مقوينا» و«وبنسند روحنا علينا»، وwhisper كان كاتب «في شيء فينا موينا» و«وبلس نجرحنا علينا».
- كلام whisper للهجة بتتغنى عمره ما يتنشر.
- ليه: طلب معنى الأغنية بالظبط (2026-11-07)، والشرايط هي اللي جابت السطور الصح.

## 13. توقيت الاقتباسات
- لكل حتة من صوتها: فرّغ تاني شباك ±5 ث حواليها بتوقيت الكلمات (`python3 tw.py SRC w.json A B`)، وحط الـ in على أول كلمة والـ out على آخر كلمة. أمثلة: J2 «الرقم واحد ليس نهاية المطاف» 59.78–63.22 ث؛ J1 «يذهب إلى مصر… ميار» 72.2–76.0 ث.
- المقولة تظهر من at + 0.10–0.15 ث لحد آخر الكليب: `V = [(src, a, b, at)]` و`Q = [(at + 0.15, at + (b - a), text)]`.
- أي وقت صوت اتغيّر = المكساج يتعاد (§4).
- ليه: أول مكساج لفيلم forty كان بأوقات مااتأكدتش واتعاد.

## 14. `$D align`: أنهي حتت من الأغنية
لما تعوز تعرف ريل أو مونتاج مرجع واخد أنهي حتت من أغنية (تبني قطعه، أو تبدّل صوت تيك توك 32–64 kb/s بنسخة أنضف):
```bash
$D align ref.mp4 song.m4a --out map.json      # الافتراضي --win 6 --hop 3
```
بيطبع كده (ريل «قلب العرب» ZSpjRC5Fe على `shadia.m4a`، اتشغّل 2026-11-08 في 2 ث):
```
align: …/v.mp4 -> …/shadia.m4a  (windows 6 s every 3 s)  2 piece(s)
  not in the song: ref 0.00 - 9.22  (9.22 s)
  piece 1  ref    9.22 -   55.77  =  song  230.57 -  277.12 (3:50.57 - 4:37.12)  offset +221.350  score 1.00
  not in the song: ref 55.77 - 62.02  (6.25 s)
  piece 2  ref   62.02 -   72.77  =  song  277.04 -  287.79 (4:37.04 - 4:47.79)  offset +215.020  score 0.94
  not in the song: ref 72.77 - 73.03  (0.26 s)
```
- `piece`: وقت الحتة في الريل = وقتها في الأغنية. `offset` = وقت الأغنية ناقص وقت الريل. `score` = متوسط التشابه (1.00 = نفس الصوت).
- حدود الحتت = قطعات المونتير (هنا 9.22 و55.77 و62.02 و72.77 ث). `not in the song` = حتت مش من الأغنية (كلامها، صوت تاني، سكوت): هنا 6.25 ث مقولة والأغنية مستنياها.
- الـ offset نزل (221.35 ← 215.02) = حاجة اتحطت والأغنية واقفة. طلع = جزء من الأغنية اتشال.
- `map.json` فيه `ref` و`song` و`ref_s` و`song_s` و`win` و`hop` و`spans` (`ref_start`، `ref_end`، `song_start`، `song_end`، `offset`، `score`، `windows`) و`gaps` و`windows`.
- v1.3: السكوت والتون والهيس على أطراف كل حتة بيتشالوا (`trimmed_head`/`trimmed_tail` في `map.json`) وبيطلعوا في الفجوات. الحدود دقتها ±0.5 ث: قبل ما تقص بيها، ظبطها على قطعات صورة المرجع (`dragon_montage station mimic` أو `scdet`).
- **مونتاج على أغنيته بنفس قطعات المرجع («نفس المونتاج بالظبط على أغنيتي»):** سؤال واحد الأول: كليباته هو ولا كليبات المرجع؟ بعدين: (1) قطعات الصورة من المرجع (`$D run dragon_montage plan … --reference ref.mp4 --reference-exact`)، (2) `$D align ref.mp4 song.m4a --out map.json`. لو فيه حتت: قصّ نفس الحتت من ملفه هو (`song_cut` تحت). لو 0 حتت (تسجيل تاني): نفس نمط القطعات على بيت أغنيته (`$D beats`)، مش صوت تيك توك.
```bash
# song_cut: حتت map.json (song_start..song_end) من ملفه، ورا بعض، بعدها الطول بالظبط
ffmpeg -nostdin -i song.m4a -filter_complex "[0:a]atrim=A1:B1,asetpts=N/SR/TB[a1];[0:a]atrim=A2:B2,asetpts=N/SR/TB[a2];[a1][a2]concat=n=2:v=0:a=1[a]" -map "[a]" -c:a aac -b:a 320k -ar 48000 song_cut.m4a
$D mux film.mp4 song_cut.m4a final.mp4 --duration D
```
- تبدّل لنسخة أنضف بس لو نفس التسجيل: الحتت مغطية أجزاء الأغنية في الريل بـ offset ثابت جوه كل حتة، والـ score قريب من 1 (هنا 1.00 و0.94). مفيش حتة أو score واطي = تسجيل تاني: سيب صوت تيك توك وقوله.
- ماتنزلش بـ `--win` تحت ~3 ث: شباك 2 ث خلّى fade-out يتطابق مع آخر الأغنية.
- ليه: نسخ أنضف اتطابقت بالـ envelope لأفلام #9 و#14 و#15، وقطعات مونتاج المرجع ماطلعتش لا بـ whisper ولا بالودن.

## 15. تنضيف الصوت
تسجيلات الموبايل والتسجيلات القديمة قبل المكساج (عرض الـ EQ مااتسجّلش: `w=1` افتراض):
```bash
ffmpeg -nostdin -i v.wav -af highpass=f=110,lowpass=f=9500,afftdn=nr=14,equalizer=f=250:t=q:w=1:g=-3,equalizer=f=3200:t=q:w=1:g=4,acompressor=ratio=3:makeup=4,loudnorm=I=-15 clean.wav
```
- لكل كليب صوت لوحده: `loudnorm=I=-15:TP=-2:LRA=9`. أوضة فيها وش عند −22 dB: `afftdn=nr=8:nf=-30` بس.
- هسهسة أغنية قديمة (أم كلثوم): highpass وafftdn وanlmdn وEQ نزّلوها ~21 dB (قيمهم مااتسجلتش).
- قيس قبل وبعد: العلو بـ `$D verify clean.wav`، والوش في حتة سكوت: `ffmpeg -nostdin -ss A -t 2 -i X -af astats -f null - 2>&1 | grep "RMS level"`.
- ليه: اتعمل على خطبها المتسجلة بالموبايل، وعلى تسجيل «سلامًا شباب النيل» القديم اللي طلب ينضف.

## 16. متكلمين المناظرة
ثقة متوسطة: اتأكد معاه أول مرة. يدوي (مفيش أمر لسه، شوف ROADMAP.md).
- whisper مابيقولش مين بيتكلم. في مناظرة ميار مع البنت التانية اتعلّم بالـ pitch ولون الجاكت مع بعض: المذيع f0 < 205 Hz؛ غير كده f0 < 315 Hz = ميار، وأعلى = المتناظرة التانية؛ ومعاه نسبة بكسلات الجاكت البينك في النص التحتاني من الكادر (ميار ≈ 0.2، التانية ≈ 0.01).
- f0 = الوسيط لكل segment (YIN زي `librosa.yin`، أو autocorrelation).
- راجع 60 segment على الأقل بإيدك، ولو الاتفاق تحت 90٪ وقّف (الجلسة: 63/68 = 93٪). الأرقام دي بتاعة التسجيل ده بس؛ تسجيل تاني = تقيس من الأول.
- بعدها لون الكابشن وإضاءة الهيدر بالمتكلم (فيلم #40 وarena48).

## 17. Suno
- أغنية وطنية أو معروفة من غير لينك: اعرض 3–5 أغاني مصرية معروفة الأول (0 كريدت، بمصدر وحقوق كل واحدة). Suno اختيار تاني بسعره، لأغنية جديدة بس، وبعد موافقة على السعر نفسه. أغنية بالاسم = ملفه هو.
- الأغاني الجديدة والمزيكا الجديدة لـ Suno. أول الجلسة: نداء قراية بس من غير كريدت (`account-me` أو `library-list`). مش متصل = سطر «suno: غير متصل» وإزاي يضيفه: claude.ai ← Settings ← Connectors ← Add custom connector ← `https://api.suno.com/mcp`، أو في Claude Code: `claude mcp add --transport http suno https://api.suno.com/mcp` وبعدها `/mcp`.
- لو بعت لينك أغنية: أغنيته هي اللي تتعمل.
- أغنية أصلية: فصحى رقيقة ومرتبة بترتيب القصة، بالمدة اللي قالها (مثلًا 40 ث)، 2–3 نسخ يختار منها، بأعلى موديل في الاشتراك (LESSONS.md). اعرض الكلمات والستايل واستنى «أيوه».
- الصرف: السعر الدقيق جنب اختيار بـ 0 كريدت (OWNER.md §6). كل `audio-download` بكريدت وبسؤال لوحده (اختار Version 1 المرتين).
- لهجة مصري: قوله إن النطق مش مضمون («ما أقدرش أأكدلك إن نطقه للهجة المصرية هيطلع طبيعي»)، واعرض عينة 30 ث الأول. بديل: ElevenLabs Music v2.5 عن طريق Higgsfield، كان ≈4.36 كريدت لـ 30 ث و15.99 لـ 110 ث (هات السعر تاني من الأداة قبل الصرف).
- الترتيب: `audio-create` (كلمات وستايل ومدة) ← `audio-wait` ← `audio-lyrics-alignment` (توقيت كل كلمة، سطر لكل newline) ← `audio-analysis` (bpm وkey وsections) ← `audio-download` بعد «أيوه».
- `lyrics.json`: صفوف `[start, end, text, big]` بالتشكيل الكامل. السطور الكبيرة Lalezar 118 px دهبي، والـ baseline ≤ y 1700 (اتعمل مرة عند 1730، وده جوه شريط أزرار المنصة؛ STYLE_RECIPES.md).
- اللي بينزل MP3: يدخل الفيلم بـ `$D mux` (يبقى AAC)، مش copy. وقوله إن الاستخدام التجاري ممكن يحتاج اشتراك Suno مدفوع.
- ليه: طلب أغنية فصحى («فصحى جميلة ورقيقة ومرتبة») وسأل Suno بيعرف مصري ولا لأ، وكل تحميل اتوافق عليه بسؤال.

## 18. مؤثرات النقلات (SFX): اختياري
ثقة متوسطة: اتأكد معاه أول مرة. يدوي (مفيش أمر لسه، شوف ROADMAP.md).
- الافتراضي: مفيش SFX (عمره ما طلبها). وعمره ما في SFX تحت قرآن أو دعاء.
- لو طلب: كل أوقات البيت في بلوك واحد `const B={…}` بيحرّك الحركة والصوت مع بعض. الـ cue باسم الحدث بيقع على البيت بتاعه بفرق 0 ms، وأكتر من فريم = bug.
- whoosh على حركات الكاميرا بس (−26 لـ −33 dB)، وpop أو tick على الـ morph والقطع. stem المؤثرات حوالين −20 LUFS والذروة تحت −2 dBFS، والمزيكا أوطى من المؤثرات بـ 8–10 dB.
- شكل الـ cue: `{event, offset, file, db, align}` من `references/sound-and-music.md` بتاع saas-animation اللي رفعه (EXTERNAL_SKILLS.md). أرقام طرف تالت مااتجرّبتش، و`mix.py` و`synth_sfx.py` بتوعه مااتشغّلوش.

## 19. القرآن
### صوت نضيف
- مفيش مزيكا ولا صوت تاني تحت التلاوة. شبابيك الأغاني بتخلص قبلها بـ 0.05 ث على الأقل وترجع بعدها، بـ fades جذر 1.0 ث على حواف الأغنية. كلام راكب على التلاوة يتشال (اتشالت «سجدتُ لله شكراً له» بتاعتها).
- مفيش أي تأثير بصري بيمشي مع علو التلاوة (`playbooks/arabic-typography.md` §11.7 في kosif-tool).
- فحص آلي في سكربت البناء: `assert all(e <= qs or s >= qe for (s, e) in song_and_voice for (qs, qe) in recitation)`.
- مثال bint: `wadih` 0–14.35 · فاطر 34 من 14.4 لـ 29.25 · `shadia` 29.3–33.55 · فاطر 35 من 33.6 لـ 50.75 · `shadia` 50.8–62.4 ث.
- ليه: «وقت التلاوة مفيش أي أغنية ولا أي صوت تاني» هو اللي طلبه.

### النص على الشاشة
- النص يتجاب، عمره ما يتكتب ولا يتفرّغ ولا «يتصحّح». الأداة `quran_text.py` في kosif-tool بس، مش جوه المهارة:
```bash
python3 .claude/skills/kosif-superpowers/scripts/quran_text.py fetch 35:34-35 --out JOB    # verses.json (sha256 لكل آية) + verses.txt
```
- الطبعة الافتراضية `quran-simple` (api.alquran.cloud، نص Tanzil) وماتتغيّرش في نفس الريل. exit 0 تمام، 1 مدخل غلط، 3 شبكة، 4 الـ API رجّع آية تانية.
- من غير kosif-tool (claude.ai): هات `https://api.alquran.cloud/v1/ayah/35:34/quran-simple`، وانسخ `data.text` زي ما هو، واحفظ الـ JSON في الشغلانة. يدوي (مفيش أمر لسه، شوف ROADMAP.md).
- الفحص: النص المرسوم بعد ما تشيل `|` = `text` في verses.json حرف بحرف.
- الخط ScheherazadeNew-Bold بالتشكيل الكامل (`playbooks/arabic-typography.md` §11 في kosif-tool؛ الخط نفسه متضمّن في المهارة: `tools/styles/fonts/ScheherazadeNew-Bold.ttf`). Amiri بس لو الفحص ده طلّع 0، لأنه بيرفع الألف الخنجرية (U+0670) لحد ما تتقري «١»:
```bash
python3 -c "import json,sys; d=json.load(open(sys.argv[1],encoding='utf-8')); print(sum(v['text'].count(chr(0x670)) for v in d['verses']))" JOB/verses.json
```
- الأقواس: «﴿» (U+FD3F) يمين الآية و«﴾» (U+FD3E) شمالها، كل واحد لوحده بـ `direction='ltr'` في مكان مقاس، عمرهم ما يبقوا جوه السطر الـ RTL. المرجع: «سورة فاطر، الآية ٣٤»، ومفيش «·» جنب الأرقام.
- وقت الآية مفيش حاجة تانية على الشاشة: لا كارت فصل ولا كلامها مكتوب. الفحص لكل (فصل، آية): `ch.s + 2.6 <= qv.s or ch.s >= qv.e`.
- الشكل اللي اتسلّم: 60 px أبيض، توهج دهبي `rgba(233,196,106,.45)` blur 22، السطور مقسومة عند `|` عند `y = 1470 + 104*i`، السطر i بيظهر عند `0.3 + 1.2*i` ث في 0.9 ث، المرجع دهبي 34 px بعد 1.6 ث، شريط غامق من y 1240 (alpha 0 ← .55 ← .7)، دخول 0.8 ث وخروج 0.6 ث. ده لسطرين؛ في 3 سطور ارفع البداية عشان سطر المرجع يفضل ≤ y 1700.
- كيت الستايلات (`chapters`) بيرسم `verses` بالمواصفات دي من v1.2: ScheherazadeNew-Bold (متضمّن في `tools/styles/fonts`، OFL)، والأقواس كل واحد لوحده برّه السطر، والمرجع دهبي من غير أقواس، و3 سطور بتبدأ أعلى. النص نفسه لسه من `verses.json` بالحرف (مش من دماغك).
- ليه: أفلام 2026-11-06 كانت كاتبة الآيات بإيدها في build.py (من غير verses.json ولا timing.json)، وبـ Amiri، والأقواس جوه fillText الـ RTL، وكارت الفصل «٣» ظهر عند 14.5 ث فوق آية بتبدأ 14.7 ث. ماحصلش عيب بس لأن الآيات دي مافيهاش U+0670.

### من غير نص («من غير ما تكتب كلامها»)
- لما يقول «من غير ما تكتب كلامها على الشاشة… بدون اي صوت خالص غير صوت القرآن»: الصوت التلاوة بس، ومفيش آيات ولا عناوين ولا فصول ولا كلام مكتوب (`notitle=1`) غير «© Mahmoud Elkosif» الصغيرة. كارت «مونتاج وإخراج Mahmoud Elkosif» و«تابعني على فيسبوك» يبدأ بعد ما التلاوة تخلص.
- تاريخ (kosif-tool): tilawa: التلاوة 0–32.3 ث، كارت النهاية 32.6 ث، المدة 35.4 ث؛ `CH=[]; SUB=[]; QV=[]; SONGS=[]; V=[(QR, 0.0, 32.3, 0.0)]` و`end=32.6, notitle=1`.
- الـ flag لازم يخفي جروب النص كله: `out/20261106-tilawa/film/bint.js` سطر 46 لسه بيرسم شريطين العلم مع `notitle=1`. اتأكد في الـ stills.
- **الطريقة جوه المهارة** (`tilawa` فوق تاريخ في kosif-tool بس): spec لـ `$D tool styles` من غير `title` ولا `lines` ولا `verses` ولا `song` (عشان تلاوته AAC ماتتعملش normalize)، وكارت النهاية بعد التلاوة بـ 0.3 ث:
```json
{"style": "clean", "duration": 35.4, "watermark": "© Mahmoud Elkosif",
 "credit": ["مونتاج وإخراج Mahmoud Elkosif", "تابعني على فيسبوك"],
 "shots": [{"src": "clips/a.mp4", "start": 0, "end": 12}, {"src": "clips/b.mp4", "start": 12, "end": 24},
           {"src": "clips/c.mp4", "start": 24, "end": 35.4}],
 "end": {"at": 32.6}}
```
```bash
# 1) الوقفات، وشيل الآيات اللي مش مناسبة (فاطر 36 في تلاواته): القص في النفَس بعد آخر آية هتفضل
python3 .claude/skills/kosif-superpowers/scripts/quran_text.py pauses recitation.m4a --out pauses.json   # kosif-tool؛ غير كده silencedetect (تحت)
# 2) الماستر: لحد النفَس T (مثلًا 32.3)، ومدّ سكوت لآخر الفيلم: encode مرة واحدة AAC 320k، من غير normalize، ومفيش MD5
ffmpeg -nostdin -i recitation.m4a -af "atrim=0:32.3,apad=whole_dur=35.4" -c:a aac -b:a 320k -ar 48000 master.m4a
ffmpeg -nostdin -ss 32.4 -i master.m4a -af volumedetect -f null - 2>&1 | grep max_volume   # لازم تحت −50 dB: مفيش تلاوة تحت كارت النهاية
# 3) الفيلم
$D tool styles quran.json --check && $D tool styles quran.json --out film --stills 2,34.6 --render   # الـ stills: © + الكريدت (end.at + 2)
$D mux film/<name>.mp4 master.m4a final.mp4 --duration 35.4 && $D verify final.mp4 --expect 1080x1920 --duration 35.4
```
- الصوت هنا اتعمله encode مرة واحدة (عشان القص والمد)، من غير normalize: قول كده في التسليم، ومتقولش MD5.
- «من غير نص» في الكيت = مفيش `title` ولا `lines` ولا `verses`. سطور `notitle` و`CH` و`QV` فوق تاريخ (kosif-tool)، مش مفاتيح في الكيت.
القطعات بين اللقطات جوه وقفات مقاسة (`pauses` تحت، أو `silencedetect`).
- ليه: ده كان طلبه الصريح للنسخة التانية (2026-11-06 12:28)، واتسلّمت بـ 12/12 فحص.

### من غير ترجمة
- مفيش ترجمة على الشاشة إلا لو طلب («بلاش ترجمة خالص»، 2026-10-29). لو طلب: Pickthall بس (`fetch … --translation en.pickthall`، ملك عام)، واسمه مكتوب على الشاشة.
- الشرط ده يتبعت صريح لأي مساعد أو مجلس أو workflow (مرة إطار المجلس قصّ السياق لـ 4 سطور ووقّعه، لحد ما `--constraints` اتضاف في PR #165).
- في سجل الشغلانة `quran.translation = "none"`، والفحص: مفيش حروف لاتيني جوه شبابيك الآيات غير الحقوق.

### الآيات المناسبة
- اقرا معنى كل آية في كليب التلاوة قبل ما تستخدمها.
- آية معناها بيعارض روح الفيلم: تتشال، وقوله أنهي وليه. فاطر 36 (عذاب الكفار) اتشالت من فيلم فرحة: «فشلتها لأنها مش مناسبة للفرحة دي».
- آية مناسبة بالعافية: قوله واعرض تغييرها. فاطر 35 (عن الجنة) اتحطت على العودة زي ما طلب، ومعاها «ولو حاسس إنها مش في مكانها قولي».
- القص قبل آية متشالة يبقى في نفَس مقاس.
- في الخطة سطر لكل آية: المعنى في سطر · مناسبة ولا متعارضة · السبب · نقطة القص (من `pauses`). والسطور دي في رسالة التسليم.

### القص في النفَس
أي قطع أو انتقال أو تقصير في تلاوة يبقى جوه نفَس مقاس:
```bash
python3 .claude/skills/kosif-superpowers/scripts/quran_text.py pauses voice.m4a --out pauses.json
python3 .claude/skills/kosif-superpowers/scripts/quran_text.py align --verses JOB/verses.json --words words.json --audio voice.m4a --out timing.json
```
- `pauses`: فريمات RMS كل 50 ms أوطى من أعلى فريم بـ 22 dB على الأقل، لمدة ≥ 0.30 ث. `--rel-db auto` بس لتسجيل فيه صدى ومستوياته فئتين، وعمره ما يتستخدم مع الوصل.
- `align`: بيحط كل كلمة من الآية على وقتها. الكلمة الطويلة (≥ 2.2 ث) أو اللي بعدها بيدوّر لها جوه 1.8 ث على وطية أعمق بـ 6 dB ويبدّاها عندها.
- `words.json` لـ `align` = ناتج `tw.py` (§10، من غير VAD) أو `montage_pro.py transcribe --no-vad`. ملف `$D words` لأ.
- من غير kosif-tool: `ffmpeg -nostdin -i voice.m4a -af silencedetect=noise=-35dB:d=0.25 -f null - 2>&1 | grep silence_` أو فواصل `words.json`. يدوي (مفيش أمر لسه، شوف ROADMAP.md).
- البوابة دي لازم تبقى أمر في التنين (ROADMAP.md): أفلام 2026-11-06 ماكانش فيها pauses ولا timing.
- ليه: موديل الكلام بيدمج ويقسم ويسمع غلط في التلاوة، وشيل فاطر 36 محتاج قص بالنفَس بالظبط.

## 20. الدعاء
ريلز دعاء الأيام بالقالب اللي اتوافق عليه:
- هيدر باسم اليوم، وميدالية اليوم والشهر الهجري (التاريخ من api.aladhan.com كل مرة، زي `https://api.aladhan.com/v1/gToH/08-11-2026`) + التاريخ الميلادي.
- سطور الدعاء متوقّتة بالكلمة على الصوت، وسطر دهبي «سبحان الله وبحمده» / «صلوا على رسول الله» بقلب بينبض.
- اسمه مكان حساب صاحب المرجع (القالب: «M A H M O U D   E L K O S I F» و«@ELKOSIF»)، ومعاهم «© Mahmoud Elkosif» والكريدت الثابت (OWNER.md).
- فوتيج مفتوح من غير ناس: لا وشوش، لا الكعبة، لا كتابة ولا لوجوهات. القطعات جوه وقفات مقاسة (§19). صوت الدعاء اللي جاي هو الصوت الوحيد (AAC يتنسخ، غيره يتحوّل: §1)، من غير مزيكا ولا ترجمة.
- فرّغ، وبعدين صحّح غلط whisper بالقراية: وساعة ← وسعة، مريبا ← مريضا، جمنتنا ← جمعتنا. واسأله في التشكيل اللي مش أكيد: واشفِ / وأرِح / يا ربَّ / وفرّج. جدول `{heard, written}` في `DECISIONS.md` بتاع الشغلانة.
- يوم جديد = عدّل الصفحة المعتمدة، ماتصممش من الأول. آخر قالب اتوافق عليه: `out/20261106-tt` في kosif-tool (خطوط KOSIFJumuah)؛ `out/20261029-friday/build_film.py` اللي بيعدّل `out/20261028-kidney/film/index.html` أقدم. `out/` في kosif-tool ومش في git، فممكن مايكونش عندك: اطلب منه آخر دعاء اتسلّم.
- **التاريخ كله بيتغيّر، مش اليوم بس:** `film_cfg.json` لازم فيه `hijri_day` و`hijri_month` و`greg_day` و`greg_month_year` (build_film.py القديم بيغيّر الأرقام بس، والشهر الهجري والميلادي ثابتين في القالب، فالجمعة اللي بعدها كانت هتطلع بشهر غلط). عدّلهم كلهم، وزوّدهم على فحص البواقي: `grep` على الشهر القديم في الصفحة لازم يطلع 0، وبص على still فيه الميدالية.
- التاريخ من `api.aladhan.com`؛ لو مفيش شبكة: عدّ من تاريخ معروف (مثلًا 1 جمادى الأولى = تاريخ اتأكد قبل كده) واكتب «مش متأكد، اتحسب» في التسليم.
- **الخطوط:** | الدور | الخط | — الهيدر واسم اليوم: KOSIFJumuah (من القالب، مش في الكيت) · سطور الدعاء: KOSIFJumuah · الأرقام والتاريخ: KOSIFJumuah · الـ © والكريدت: Tajawal. Amiri وCairo أقدم ومش هم المعتمدين. الخطوط دي مش في الكيت (رخصتها مش متأكدة): من القالب بتاعه بس.
- القالب = `index.html` والخطوط بس؛ الصوت والطول دايمًا من `$D mux … --duration D` و`$D verify`. `run.sh` القديم فيه `-c copy -t`: ماتستخدموش. وناتج `dua_wednesday` مسودة لازم تعدّي على `mux` و`verify`.
- قالب kidney مفيهوش © ولا كريدت: زوّدهم (OWNER.md §9) وتأكد في still.
- **صوت الدعاء:** لو مابعتش صوت: نفس القارئ (@dxhmen) ومعاه سطر في `CREDITS.md` («الصوت: @dxhmen»)؛ صوت تاني = سؤال.
- ليه: طلب «اعمل نفس الفديو بس عن يوم الجمعة وغير بس الفديوهات وهات دعاء من الانترنت»، ودعاء الاتنين والتلات والخميس والجمعة اتسلّموا كده.
