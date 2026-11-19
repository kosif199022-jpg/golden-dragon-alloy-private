# تقرير قدرات: المستودعات من 41 لـ 90 في الكتالوج (Batch 041-090)

- **المصدر:** صفوف البيانات من 41 لـ 90 (من غير الهيدر) في `%USERPROFILE%\Downloads\all-repos-catalog.csv`.
- **التاريخ:** 2026-11-16.
- **الطريقة:** نفس طريقة `REPOS_PILOT_40.md`. دوّرنا باسم الأداة أو الباكدج (مش باسم المستودع بس) جوه `golden-dragon` كله (engine وapps وlibrary وmodules وreferences)، وفرّقنا بين الكود (`.py` و`.js` و`.mjs` و`.sh`) وبين الكتالوجات (`library.json` و`fusion/index.json` وكروت `engine/app/data/cards`). وكشفنا على الجهاز بـ `where.exe` و`python -c "import X"` و`npm ls -g` و`%USERPROFILE%\dragon-repos` و`dragon-models`. وقرينا الرخصة والنجوم وآخر push بـ `gh repo view --json licenseInfo,stargazerCount,pushedAt,isArchived`. ماتثبّتش أي حاجة وماعملناش clone وماشغّلناش كود أي مستودع.
- **معنى الحالة:**
  - **مستخدم:** فيه كود في المهارة بيشغّله أو بيعمله vendor أو بيديله وصفة تثبيت (codekit أو استوديو البرامج)، أو مهارة منسوخة جوه `library/` بتشغّله.
  - **متثبت ومش متوصّل:** موجود على الجهاز، بس المهارة بتذكره في مراجع أو قوايم بس، وماحدش بيستدعيه.
  - **قدرة جديدة:** مش متثبت ولا متوصّل. لو ليه ذكر فهو في الكتالوجات والكروت بس.

## الملخص

| الحالة | العدد |
|---|---|
| مستخدم | 21 |
| متثبت ومش متوصّل | 3 |
| قدرة جديدة | 26 |
| **الإجمالي** | **50** |

## جدول الخمسين

| # | Repo | الحالة | الدليل على الجهاز وفي المهارة | الإضافة الملموسة | التشغيل على Windows | ملاحظة الرخصة |
|---|---|---|---|---|---|---|
| 41 | protectwise/troika | قدرة جديدة | مش موجود، ومالوش أي ذكر | `troika-three-text`: نص SDF حاد في three.js من ملفات TTF/WOFF، وبيدعم RTL ووصل الحروف العربية، فتعمل عناوين 3D عربي متحركة من غير ما تحوّل النص لـ mesh | vendor للـ ESM build جنب `codekit/vendor/three` أو `npm i troika-three-text` | MIT |
| 42 | excalidraw/excalidraw | قدرة جديدة | مش متثبت. الذكر في كارت `hand-drawn-draw-on.json` وفي `library/excalidraw-skill` (ودي مهارة لـ `mcp_excalidraw` محتاجة سيرفر مش موجود) | مخططات بشكل اسكتش يدوي من JSON وتصدير SVG/PNG لفيديوهات الشرح | `npm i @excalidraw/excalidraw` (React) أو سيرفر MCP الخاص بالمهارة | MIT. Rough.js الـ vendored بيدّي نفس الشكل |
| 43 | d3/d3 | قدرة جديدة | مش موجود. الذكر في كروت `knowledge-graph` و`shadow_theatre/data` بس | scales وshapes وinterpolators لشارتات بيانات متحركة فريم بفريم (bar race، خطوط بترسم نفسها) | vendor لملف `d3.min.js` والرندر بـ Playwright | ISC |
| 44 | fabricjs/fabric.js | قدرة جديدة | مش موجود، ومالوش ذكر | طبقات canvas قابلة للتعديل (نص وصور وفلاتر) مع حفظ JSON، تنفع لقوالب بوسترات وثمبنيلات | `npm i fabric` (في Node محتاج `canvas`) | MIT |
| 45 | processing/p5.js | مستخدم | `library/algorithmic-art` (منسوخة من anthropics/skills) بتحمّل `p5.min.js` 1.7.0 من cdnjs في `templates/viewer.html` | (موجود) فن توليدي بـ seed | صفحة HTML من المهارة | LGPL-2.1 |
| 46 | rough-stuff/rough | مستخدم | vendored: `engine/tools/codekit/vendor/roughjs/rough.js`، وفي قايمة `codekit.py` و`video12.py`، و`fam_hand_drawn_draw_on.py` بيقلّد أسلوبه | (موجود) شكل مرسوم باليد | vendored | MIT. آخر push كان 2024-07 |
| 47 | paperjs/paper.js | قدرة جديدة | مش موجود (الذكر الوحيد كلمة في ملف prompts) | عمليات boolean على المسارات وحساب نقط على bezier، مفيدة لتقطيع الشعارات وأنيميشن رسم المسار | vendor لملف `paper-full.min.js` | MIT |
| 48 | Automattic/node-canvas | قدرة جديدة | مش متثبت. الذكر في كارت `engines-render-pipeline.json` بس | Canvas 2D جوه Node من غير متصفح، يطلّع PNG/PDF بسرعة لدفعات بطاقات | `npm i canvas` (فيه prebuilt لـ Windows x64) | MIT. Playwright وPillow بيغطوا أغلبه |
| 49 | opentypejs/opentype.js | قدرة جديدة | مش موجود. النتايج اللي طلعت مسارات خطوط (`/fonts/opentype/`) مش الباكدج | يطلّع outlines الحروف كمسارات SVG لأنيميشن رسم الحروف، والمقاسات (metrics) | `npm i opentype.js` | MIT. **مابيعملش shaping للعربي**، لازم معاه harfbuzzjs |
| 50 | mermaid-js/mermaid | قدرة جديدة | `mmdc` مش موجود. `library/beautiful-mermaid` بتستخدم باكدج `beautiful-mermaid` (رندر مختلف)، و`am.mjs` بيفهم صيغة Mermaid بس | يحوّل نص قصير لـ flowchart وsequence وtimeline كـ SVG لمشاهد الشرح | `npx -y @mermaid-js/mermaid-cli -i d.mmd -o d.svg` (بينزّل Chromium) | MIT |
| 51 | apache/echarts | قدرة جديدة | مش موجود (النتيجة الوحيدة `updateCharts` ملهاش علاقة) | شارتات وخرايط بأنيميشن داخلي وSVG renderer، وفيه SSR في Node يطلّع SVG من غير متصفح | vendor لملف `echarts.min.js` أو `npm i echarts` | Apache-2.0 |
| 52 | xyflow/xyflow | قدرة جديدة | مش موجود، الذكر في `github-atlas` بس | مخططات عقد وأسهم تفاعلية بـ React | `npm i @xyflow/react` | MIT. قيمته للفيديو قليلة |
| 53 | plotly/plotly.js | مستخدم | `library/downtrend-duration-analyzer/scripts/generate_histogram_html.py` بيحمّل `plotly-2.27.0.min.js` من CDN، وباكدج Python `plotly` 7.1.0 متثبت | (موجود) شارتات تفاعلية | `import plotly` | MIT |
| 54 | visgl/deck.gl | قدرة جديدة | مش موجود. الذكر في كارت `particles-fluids-physics.json` و`charts.csv` | طبقات WebGL لبيانات جغرافية ضخمة (arcs وhexbins) لفيديوهات خرايط | `npm i deck.gl` | MIT |
| 55 | vega/vega | قدرة جديدة | مش موجود (نتايج الكود كلمات زي `resolveGallerySelection`) | شارتات من JSON وتصدير PNG/SVG من سطر الأوامر | `npm i vega vega-cli` ثم `vg2svg spec.json out.svg` | BSD-3 |
| 56 | maplibre/maplibre-gl-js | مستخدم | `library/hyperframes/scripts/bake-basemap.mjs` بيحمّل `maplibre-gl@5.24.0` ويسجّل حركة الكاميرا في Chrome headless | (موجود) خرايط متحركة | من خلال سكربت hyperframes | BSD-3 |
| 57 | cytoscape/cytoscape.js | قدرة جديدة | مش موجود. الذكر في `agent-recall` و`charts.csv` بس | شبكات عقد وأسهم بـ layouts جاهزة وأنيميشن، لمشاهد علاقات وشبكات | vendor لملف `cytoscape.min.js` | MIT |
| 58 | ggml-org/whisper.cpp | مستخدم (متوصّل بس مش متثبت) | استوديو البرامج في `apps/golden-dragon/app/golden_tools.py` و`app.py` بيدّي `whisper-cli` (المرفق مع Shotcut) بعد فحص sha256. مش موجود على PATH | (موجود كوصفة) تفريغ من غير Python | `studio_run install` ثم `whisper-cli -m model.bin -f a.wav -ojf` | MIT |
| 59 | resemble-ai/chatterbox | قدرة جديدة | مش متثبت، ومالوش ذكر | TTS بنسخ صوت من عيّنة قصيرة وتحكم في الانفعال، والموديل Multilingual فيه العربي، ويشتغل أوفلاين بدل edge-tts الأونلاين | `pip install chatterbox-tts` (torch CPU موجود بس هيبقى بطيء) | MIT. الصوت الناتج عليه watermark (PerTh) مدمج |
| 60 | SYSTRAN/faster-whisper | مستخدم | `faster_whisper` 1.2.1، ومستخدم في `apps/*/app/voice.py` و`dragon_desktop/voice.py`، وفي `doctor.py` | (موجود) تفريغ بتوقيت كل كلمة | `from faster_whisper import WhisperModel` | MIT |
| 61 | m-bain/whisperX | مستخدم | `whisperx.exe` موجود، وفي `codekit.py` (pip)، و`golden_tools.py`، وclone في `dragon-repos\whisperX` | (موجود) تفريغ ومحاذاة كلمات | `whisperx a.wav --language ar --output_format json` | BSD-2. موديلات pyannote للـ diarization محتاجة قبول شروط على HF |
| 62 | rany2/edge-tts | مستخدم | `edge-tts.exe` و7.3.1، ومستخدم في `engines/voice_studio/__init__.py` (أصوات مصري وتوقيت كلمات) | (موجود) | `edge-tts --voice ar-EG-SalmaNeural ...` | LGPL-3.0. بيعتمد على خدمة Microsoft الأونلاين |
| 63 | snakers4/silero-vad | مستخدم (من خلال faster-whisper) | الموديول `silero_vad` مش بيتعمله import، بس الـ clone وملفات `silero_vad.jit/.onnx` موجودين في `dragon-repos\silero-vad`، و`voice.py` بيشغّل `vad_filter=True` (Silero VAD مدمج في faster-whisper) | (موجود جوه التفريغ). كأداة مستقلة يقدر يطلّع مقاطع الكلام لقص الصمت | `pip install silero-vad` أو ONNX من الـ clone | MIT |
| 64 | facebookresearch/demucs | مستخدم | `demucs.exe` و4.1.0، وفي `dragon/capabilities.py` و`doctor.py` و`forge/recipes.py` | (موجود) فصل الصوت عن الموسيقى | `demucs --two-stems=vocals a.wav` | MIT. **الريبو archived** (آخر push 2024-04) |
| 65 | jiaaro/pydub | متثبت ومش متوصّل | `import pydub` شغال، بس بيتذكر في نص `app.py` وقايمة `machine.py` بس، ومافيش `import pydub` في أي كود | تقطيع ودمج وfade للصوت بـ Python بسطور قليلة | `from pydub import AudioSegment` | MIT. ffmpeg المباشر بيغطيه |
| 66 | librosa/librosa | مستخدم | 1.0.0، ومستخدم في `engines/audio.py` و`dragon_montage/analyze.py` (beats وdownbeats) | (موجود) | `import librosa` | ISC |
| 67 | MahmoudAshraf97/ctc-forced-aligner | قدرة جديدة | مش متثبت، ومالوش ذكر | محاذاة سكريبت معروف على الصوت كلمة بكلمة بموديلات MMS اللي بتدعم العربي، فالترجمة تبقى متزامنة بالظبط مع نص مكتوب مسبقًا (أدق من تفريغ whisper للعامية) | `pip install git+https://github.com/MahmoudAshraf97/ctc-forced-aligner.git` ثم `ctc-forced-aligner --audio_path a.wav --text_path t.txt --language ara` | BSD-2 للكود. **الموديل الافتراضي مشتق من MMS ورخصته CC-BY-NC-4.0 (ممنوع تجاري)** |
| 68 | google/fonts | مستخدم | `engine/tools/fonts/fonts.py` بينزّل من `github.com/google/fonts` (مجلد ofl) ويسجّل في `fonts.lock.json`، و`chroma_identity.py` و`higgsfield-cloud/cloud/fonts.sh` | (موجود) | `python scripts/dragon.py tool fonts fetch` | OFL-1.1 لأغلب العائلات، وبعضها Apache-2.0 أو UFL |
| 69 | harfbuzz/harfbuzz | مستخدم (من خلال libass وPillow) | `dragon_montage/render.py` بيعتمد على libass (fribidi + HarfBuzz) للعربي. `uharfbuzz` 0.57.0 متثبت بس ماحدش بيعمله import | (موجود) shaping العربي في الترجمات | جوه ffmpeg | Old MIT |
| 70 | fonttools/fonttools | مستخدم | `fontTools` 4.68.0 و`pyftsubset.exe`، ومستخدم في `absolute-creativity/scripts/font_lab.py` و`brand_logo_identity.py` | (موجود) فحص تغطية العربي وsubset | `pyftsubset font.ttf --text-file=t.txt` | MIT |
| 71 | CAMeL-Lab/camel_tools | قدرة جديدة | مش متثبت. الذكر في كروت `arabic-language.json` و`powers.json` و`modules/ultra/tools.json` | توحيد الكتابة العربية وتحليل صرفي وتمييز اللهجة، ينفع لتنضيف نص الترجمة قبل المحاذاة والـ TTS | `pip install camel-tools` ثم `camel_data -i light` | MIT. بيانات بعض الموديلات ليها رخص منفصلة |
| 72 | mpcabd/python-arabic-reshaper | مستخدم | 3.1.0، ومستخدم في `image_studio/__init__.py` و`blender-pro/scripts/bpylib/draw.py` و`text3d.py` | (موجود) | `arabic_reshaper.reshape(t)` | MIT |
| 73 | harfbuzz/harfbuzzjs | قدرة جديدة | مش موجود، ومالوش ذكر | shaping عربي صحيح جوه المتصفح وNode (WASM) يطلّع glyphs ومواضعها، فتقدر ترسم النص العربي كمسارات SVG متحركة مع opentype.js | `npm i harfbuzzjs` | MIT |
| 74 | MeirKriheli/python-bidi | مستخدم | `import bidi` شغال، ومستخدم في `image_studio` و`psd_studio/psd.py` و`blender-pro` | (موجود) | `from bidi.algorithm import get_display` | LGPL-3.0 |
| 75 | smacke/ffsubsync | متثبت ومش متوصّل | `ffsubsync.exe` 0.5.1 متثبت، وبيتذكر في `montage-repos-hub/SKILL.md` و`MONTAGE_REPOS_HUB_UPLOADED.md` بس | يصلّح إزاحة ملف SRT عن الفيديو تلقائيًا من نشاط الصوت (offset وفرق framerate) | `ffsubsync video.mp4 -i in.srt -o out.srt` | MIT |
| 76 | readbeyond/aeneas | قدرة جديدة | مش متثبت، ومالوش ذكر | محاذاة نص معروف على صوت بـ eSpeak وDTW | `pip install aeneas` (محتاج eSpeak وبناء C، صعب على Windows) | **AGPL-3.0**. آخر push 2026-07 بس التطوير شبه واقف، وctc-forced-aligner أحسن |
| 77 | MontrealCorpusTools/Montreal-Forced-Aligner | قدرة جديدة | `mfa` مش موجود، ومالوش ذكر | محاذاة كلمات وفونيمات (TextGrid) بموديلات جاهزة فيها العربي | `conda install -c conda-forge montreal-forced-aligner` (محتاج conda) | MIT. تقيل وصعب على Windows |
| 78 | libass/libass | مستخدم | داخل ffmpeg (فلتر `subtitles=`/`ass=`)، و`dragon_montage/render.py` بيجهّز `fontsdir` ليه | (موجود) حرق ترجمات ASS بستايل وكاريوكي | `ffmpeg -vf "ass=c.ass:fontsdir=..."` | ISC |
| 79 | tkarabela/pysubs2 | متثبت ومش متوصّل | `pysubs2` 1.9.1 و`pysubs2.exe` متثبتين، ومالوش أي ذكر في المهارة | تحميل وتعديل وretime وتحويل الترجمات بين ASS وSRT وVTT، وتطبيق ستايلات ASS بالكود | `pysubs2 --to ass in.srt` أو `import pysubs2` | MIT |
| 80 | Comfy-Org/ComfyUI | قدرة جديدة | مش متثبت. الذكر في `build_catalog.py` و`library.json` و`moneyprinterturbo-video/mpt_agent.py` (تعليق) | تشغيل workflows JSON للصور والفيديو بالـ API من غير واجهة | ComfyUI Desktop أو portable، ثم `POST /prompt` | GPL-3.0. محتاج GPU، وtorch عندنا CPU |
| 81 | huggingface/diffusers | مستخدم | `paint-studio/scripts/paint_ai.py` و`engine/tools/toon/engine/__init__.py` بيستخدموه من venv `dragon-models\toon` (diffusers 0.42.1). مش متثبت في Python العام | (موجود) text2img وimg2img وinpaint | `dragon-models\toon\venv\Scripts\python.exe paint_ai.py` | Apache-2.0. كل موديل ليه رخصته |
| 82 | lllyasviel/ControlNet | قدرة جديدة | مش موجود. الذكر في كارت `ai-generation.json` ونطاق قوة في `ai_generation.py` بس | توليد صور بيتبع edges أو depth أو pose | من خلال `diffusers` (`ControlNetModel`) في venv الـ toon | Apache-2.0 للكود. الأوزان مبنية على SD (OpenRAIL-M). آخر push 2024-02 |
| 83 | Wan-Video/Wan2.1 | قدرة جديدة | مش موجود. الذكر في `library.json` و`fusion/index.json` بس | text/image-to-video وinterpolation بين أول وآخر فريم | محتاج GPU (1.3B على 8 جيجا VRAM). على الجهاز ده عمليًا سحابة بس | Apache-2.0 (الكود والأوزان) |
| 84 | OpenTalker/SadTalker | قدرة جديدة | مش موجود، ومالوش ذكر | صورة وش + صوت = talking head بحركة شفايف | محتاج torch وGPU، وwebui | Apache-2.0. آخر push 2024-06 |
| 85 | Lightricks/LTX-Video | قدرة جديدة | مش موجود. الذكر في `library.json` وكارت `ai-generation.json` | فيديو سريع من نص أو صورة أو keyframes مع LoRAs للتحكم | محتاج GPU، أو من خلال diffusers/ComfyUI | Apache-2.0 للكود. **الأوزان ليها رخصة LTX منفصلة، راجعها قبل التجاري** |
| 86 | VAST-AI-Research/TripoSR | قدرة جديدة | مش موجود، ومالوش ذكر | mesh 3D بـ texture من صورة واحدة يدخل Blender على طول | clone + `pip install -r requirements.txt` (فيه `torchmcubes` محتاج بناء)، ويشتغل على CPU ببطء | MIT |
| 87 | obra/superpowers | مستخدم | 12 مهارة منسوخة في `library/` (`brainstorming` و`systematic-debugging` و`using-superpowers` وغيرهم، كلهم `SOURCE.json` بيشاور على obra/superpowers)، و`mcp_dragon.py` فيه hub | (موجود) | مهارات SKILL.md | MIT |
| 88 | anthropics/skills | مستخدم | 7 مهارات منسوخة في `library/` (`algorithmic-art` و`canvas-design` و`frontend-design` و`mcp-builder` و`webapp-testing` و`web-artifacts-builder`)، وclone في `dragon-repos\anthropics__skills` | (موجود) | مهارات SKILL.md | Apache-2.0. مهارات المستندات (docx/pdf/pptx/xlsx) source-available مش مفتوحة |
| 89 | upstash/context7 | مستخدم | `library/context7-cli` و`context7-mcp` و`find-docs` منسوخين، و`fam_skills_part6.py` بيرشّحه | (موجود) توثيق مكتبات محدّث | `npx ctx7@latest ...` | MIT. الخدمة نفسها hosted وفيها حدود استخدام |
| 90 | ChromeDevTools/chrome-devtools-mcp | قدرة جديدة | مش متسجّل كـ MCP. الذكر في `library.json` و`github-atlas` بس | Chrome حي للوكيل: performance traces وconsole وnetwork، مفيد لتصحيح صفحات HTML-to-video البطيئة | `npx -y chrome-devtools-mcp@latest` كسيرفر MCP | Apache-2.0 |

## أهم 10 إضافات (حسب القيمة لشغل الفيديو والصور والموشن)

| # | الأداة | ليه | أرخص طريقة للإضافة |
|---|---|---|---|
| 1 | **ffsubsync** | يصلّح أي ترجمة مزاحة عن الفيديو تلقائيًا، وده عطل متكرر في الترجمات المستوردة | **مافيش تثبيت** (0.5.1 موجود). خطوة في بوابة الترجمة: `ffsubsync video.mp4 -i in.srt -o out.srt`، وبعدين `transcript_qa.py` |
| 2 | **pysubs2** | تحويل SRT لـ ASS بستايل ثابت وretime وتقسيم السطور بالكود بدل كتابة ASS يدوي | **مافيش تثبيت** (1.9.1 موجود). `import pysubs2` في محرك الترجمات |
| 3 | **ctc-forced-aligner** | محاذاة كلمة بكلمة لسكريبت عربي معروف، فالترجمة والكاريوكي يطابقوا النص المكتوب مش تفريغ whisper | `pip install` من GitHub (torch موجود). **الموديل الافتراضي CC-BY-NC**: للتجاري استخدم whisperX الموجود |
| 4 | **troika-three-text** | عناوين عربي 3D حادة ومتحركة جوه three.js من غير ما تحوّل النص لـ mesh | vendor لملف ESM جنب `codekit/vendor/three` وزوّده في قايمة codekit |
| 5 | **harfbuzzjs + opentype.js** | النص العربي يترسم كمسارات SVG مشكّلة صح، فتعمل أنيميشن كتابة الخط العربي (draw-on) | vendor للاتنين (MIT)، وسكربت صغير يطلّع `path d` لكل كلمة |
| 6 | **d3** | شارتات بيانات متحركة دقيقة (bar race، خطوط بترسم نفسها) لقوالب `motion-charts` | vendor لملف `d3.min.js` واحد، والرندر بـ `render_frames.js` |
| 7 | **chatterbox (Multilingual)** | TTS أوفلاين بالعربي ونسخ صوت، بديل لـ edge-tts اللي محتاج نت | `pip install chatterbox-tts` في venv منفصل. بطيء على CPU، فاستخدمه لجمل قصيرة |
| 8 | **mermaid-cli** | flowcharts وtimelines كـ SVG من نص لمشاهد الشرح | `npx -y @mermaid-js/mermaid-cli` من غير تثبيت دائم |
| 9 | **ECharts** | شارتات وخرايط بأنيميشن جاهز وSSR لـ SVG في Node | vendor لملف `echarts.min.js` |
| 10 | **TripoSR** | mesh 3D من صورة منتج واحدة يدخل `blender-pro` على طول | clone في `dragon-repos` وvenv منفصل. على CPU ببطء، أو على السحابة |

### ملاحظات جانبية

- **silero-vad:** شغال فعلًا جوه faster-whisper (`vad_filter=True`)، والـ ONNX موجود في `dragon-repos`، فممكن يتوصّل كأداة قص صمت مستقلة من غير تثبيت.
- **pydub:** متثبت بس ffmpeg المباشر بيغطيه، فمش مستاهل يتوصّل.
- **harfbuzz:** `uharfbuzz` 0.57 متثبت ومحدش بيستخدمه. ممكن يتوصّل لقياس عرض النص العربي بدقة قبل الرندر.
- **demucs:** الريبو archived. شغال ومستقر، بس مافيش تحديثات جاية.
- **ComfyUI وWan2.1 وLTX-Video وSadTalker وControlNet:** محتاجين GPU، وtorch عندنا CPU. مكانهم السحابة (higgsfield-free / hf_sandbox)، مش الجهاز.
- **aeneas وMontreal-Forced-Aligner:** صعبين على Windows (eSpeak وconda وKaldi)، وaeneas رخصته AGPL. ctc-forced-aligner وwhisperX بيغطوا نفس الاحتياج.
- **excalidraw وfabric.js وpaper.js وnode-canvas وvega وxyflow وdeck.gl وcytoscape:** قيمتهم للفيديو أقل، أو بيغطيهم Rough.js وPlaywright وmaplibre الموجودين.
- **camel_tools:** مفيد لتنضيف النص العربي قبل المحاذاة، بس مش أولوية.
