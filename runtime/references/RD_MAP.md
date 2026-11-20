# خريطة التنين الأحمر — كل حاجة فين

اتولّدت أوتوماتيك من شجرة الملفات بـ `python -I -X utf8 scripts/make_map.py .`. لو حاجة اتنقلت، الخريطة دي اللي تتصدق مش الذاكرة.

## الأبواب (أوامر `rd.py`)

| الأمر | بيوصل لـ |
|---|---|
| `start` | يبدأ: يعرف هو شغال فين ويوريك الطريق |
| `where` | بيشتغل فين (claude.ai، سحابة، لابتوب) |
| `doctor` | فحص الأدوات والمكتبات |
| `docs` | يولّد المراجع |
| `retro` | مراجعة بعد الشغل |
| `selftest` | فحص ذاتي سريع (الطرق، القدرات، الدروس، المحادثات) |
| `teach` | a request was routed wrong: remember «request → playbook» (example + lesson) |
| `map` | خريطة الطرق |
| `show` | تفاصيل طريق |
| `learn` | يسجّل درس من تصحيح |
| `lessons` | الدروس |
| `outcome` | يسجّل نتيجة طريق (ثقة) |
| `memory` | ذاكرة المحادثات: فين الملف، اتقرر إيه |
| `re` | هندسة عكسية |
| `repo` | تحليل مستودع |
| `repos` | أهم المستودعات |
| `skills` | دوّر/ثبّت مهارة من المكتبة أو المتثبت |
| `x` | يشغّل أمر من محرك التنين الأسود |
| `character` | character memory + auto rotoscope: doctor, demo, extract, analyze, redraw, memory, animate, edit, export |
| `math` | drawing maths (draw-math): body, dist, angle, ik2, cam, frame-fit, puppet-shadow, gait, ease ... |
| `dcm` | dragon-character-memory v1.0 (second engine): extract, analyze, redraw, memory, rebuild, animate, identity, demo |
| `desktop` | guarded BlackDragon desktop bridge: catalog, doctor, read, snapshot |
| `ref` | reference-lock: lock, show, verify, fontmatch, list, selftest (same font/colours = exactly the same) |
| `mind` | claude-mind: brief, gate, learn, lessons, types (how Claude thinks and checks before delivery) |
| `insta` | insta-reader: doctor, profile, top, post, download, login, selftest (Instagram via instaloader, MIT) |
| `ig` | instagram-agent-skill tools (library/ig-*, MIT): list, hooks, beats, caption, humanize, detect, swipe, voice |
| `agents` | subagents: list, install, check (rd-runner = cheap Haiku worker for routine steps) |
| `hypit` | hypit-run: doctor, setup, example, check, plan, render, cli, selftest (the real Hypit SVML video engine, local and free; paid Providers blocked without --allow-paid) |
| `krita` | krita-draw: render scene.json | layers file.kra | info (draw with code inside the real Krita) |
| `sync` | sync-guard: words, check, fix, onsets, script, grid, selftest (captions and motion on the spoken word) |
| `md` | doc-reader (v3.3): convert, batch, doctor, exts, install, selftest (any PDF, Word, PowerPoint, Excel, HTML, EPUB… → Markdown with Microsoft MarkItDown, MIT) |
| `mtoon` | maven-toon-bridge (v3.5.6): install, where, doctor, fonts, render, run, script-eg, credit, gate, selftest (the owner's private Maven Toon copy + Egyptian script check, credit, export gate) |
| `arena` | arena-gate (v2.19): size, start, jobs, next, collect, advance, winner, skip, gate, selftest (the arena is a required step: competing copies, bracket, judge) |
| `consent` | consent gate: which outward actions this message explicitly approves or forbids («كمل» approves none) |
| `gold` | Golden Bird: studio list/show/install/cmd · lib find/show/kit/stats · sync · protocol · where · selftest |
| `think` | think & plan: start, revise, check, time, mistake, mistakes, pipeline-selftest · planning-mind: card, gate, workflow, learn, lessons, types, selftest |
| `fuse` | v3.4 fusion brain: brief, route, check, tools, protocol, find, show, recipes, lessons, doctor, stats, selftest |
| `check` | v3.4 critic gate before sending an answer (= fuse check) |
| `understand` | يفهم الطلب (صوت، كيبورد إنجليزي، غلطات) |
| `brief` | ملخص JSON: الطريق والمهارات والقدرات للطلب |
| `plan` | الخطة كاملة للطلب: الطريق والخطوات والمهارات |
| `route` | أحسن الطرق للطلب بالدرجات |
| `recall` | يفتكر من المحادثات القديمة |
| `intel` | مستودعات ومعلومات تخص الطلب |

## مهارات المحرك (48)

| المسار | بيعمل إيه |
|---|---|
| `engine/skills/absolute-creativity` | الإبداع المطلق — محرك ابتكار وإخراج فني كامل بيطلّع أفكار أصلية مش كليشيه، وبيحوّلها لشغل حقيقي في المونتاج والتصوير السينمائي والفوتوغرافي والحبكة ال… |
| `engine/skills/arabic-captions-khatt` | حرق كابشن عربي صح على الفيديو (حروف متوصّلة، من اليمين للشمال، تشكيل، لام-ألف) بمكتبة khatt (HarfBuzz + FreeType) وffmpeg، من غير Raqm ولا moviepy. |
| `engine/skills/arena-gate` | الحلبة شرط أساسي في شغل التنين: أي مهمة فيها ذوق أو قرار (تصميم، كتابة، مونتاج، خطة، كود فيه أكتر من حل) تتعمل كحلبة. |
| `engine/skills/atlas-picks` | Build Awwwards-quality web experiences with spring physics, GLSL shaders, R3F, post-processing, particles, Framer Motion, and interactive 3D. |
| `engine/skills/black-dragon-cinema` | التنين الأسود — سينما الفوتيج. |
| `engine/skills/blackdragon-desktop-bridge` | جسر اختياري آمن لتشخيص القدرات الموجودة في تطبيق BlackDragon على ويندوز وقراءة معلومات أو التقاط صورة للشاشة بموافقة صريحة. |
| `engine/skills/blender-pro` | Headless Blender 5.2 control for 3D, drawing and video through JSON recipes or raw bpy scripts. |
| `engine/skills/camera-director` | مدير التصوير — makes Claude shoot like a cinematographer whenever it composes a video, whatever the engine. |
| `engine/skills/character-memory` | Dragon Character Memory & Auto Rotoscope — بياخد فيديو لشخصية كرتون واحدة (ألوان مسطحة وخط خارجي واحد، من قدّام، خلفية ثابتة)، ويتتبّع أجزاءها ومفاصله… |
| `engine/skills/chroma-motion` | كروما موشن — بيحوّل أي صورة (طير، وردة، فراشة، منظر، لوحة، منتج) لهوية بصرية كاملة بألوانها وحركتها. |
| `engine/skills/claude-mind` | عقل Claude: الطريقة اللي Claude بيفكّر ويشتغل بيها فعلًا، مكتوبة عشان أي موديل في التطبيق يمشي عليها. |
| `engine/skills/creative-studio` | التنين الأسود — استوديو Blender وPhotoshop وAfter Effects. |
| `engine/skills/doc-reader` | أي مستند يتحوّل لـ Markdown قبل ما يتقري، بـ Microsoft MarkItDown (MIT): PDF، Word (docx)، PowerPoint (pptx)، Excel (xlsx/xls)، HTML، CSV، JSON، XML، … |
| `engine/skills/dragon-character-memory` | ذاكرة الشخصية والروتوسكوب الآلي — بيحلل فيديو لشخصية كرتونية واحدة فريم بفريم، يعيد رسم كل فريم كأشكال متجهة (SVG) ويقيس الفرق عن الأصل، ويتتبع الرأس … |
| `engine/skills/dragon-genius` | عبقرية التنين — نظام تشغيل لـ Claude مستخلص من تحليل 100 مستودع GitHub (55 تفكير ووكلاء وذاكرة ومهارات، 45 مونتاج وصوت وأنيميشن وتحسين صورة). |
| `engine/skills/expert-council` | مجلس الخبراء — بيجمع مجلس شخصيات خبراء عالميين لأي مجال (عدسات مستوحاة من مبادئ الأساتذة)، كل واحد يدي رأي مستقل، بعدين يتناقشوا ويتحقق المتشكك، والرئ… |
| `engine/skills/github-atlas` | أطلس GitHub — خريطة أقوى 1000 مستودع على GitHub بالنجوم (من build-your-own-x 561k لـ etcher 35k، اتسحبت 2026-11-11) ومعاها تحميلات الإصدارات، كل مستود… |
| `engine/skills/golden-bird` | الطائر الذهبي (Golden Bird) جوه التنين الأحمر: استوديو 10 برامج سطر أوامر مفتوحة المصدر من «مهارات\\برامج» (Rhubarb lip sync، HandBrakeCLI، Synfig، Ta… |
| `engine/skills/hf-blender-render` | التنين الأسود — تجربة Blender على Higgsfield Sandbox بوضع تجريبي، رندر CPU مع الموافقة والقياس أولًا. |
| `engine/skills/higgsfield-cloud` | سحابة هيجز المجانية — بتشغّل جهاز لينكس Higgsfield المجاني (sandbox_exec عادي وXL) كمزرعة رندر وتفريغ وتصفّح جنب ويندوز من غير كريدت. |
| `engine/skills/higgsfield-free` | هيجز فيلد ببلاش — استغلال كل الإمكانيات المجانية في Higgsfield من غير ما يتصرف كريدت: سحابة لينكس للرندر والترميز والتفريغ (sandbox_exec)، Blender مست… |
| `engine/skills/hypit-run` | تشغيل Hypit الحقيقي (hypit-ai/hypit) من التنين: فيديو مكتوب كـ SVML (مكوّنات HTML/CSS/SVG + Timeline مربوط بالكلمة) بيترندر MP4 محليًا ببلاش في Chromi… |
| `engine/skills/insta-reader` | قراية وتحميل من إنستجرام بـ instaloader (MIT): بيانات حساب (متابعين، بايو، عدد بوستات)، آخر البوستات بلايكاتها وكومنتاتها ومشاهداتها وكابشنها، أعلى ال… |
| `engine/skills/kosif-black-dragon-ultra` | التنين الأسود الفائق — one front door to all 21 KOSIF modules: video montage, motion/web films, voice-over and subtitles, reels and hooks, Kling promp… |
| `engine/skills/kosif-downloads` | KOSIF «كوسيف» — مدير تحميل مسرّع زي Internet Download Manager مدموج في التنين الأسود. |
| `engine/skills/krita-draw` | Draw and paint with code through the real Krita installed on this PC, with no GUI. |
| `engine/skills/maven-toon` | Maven Toon, by Maven (@maven.iqq). |
| `engine/skills/maven-toon-bridge` | التنين الذهبي بيشغّل نسخة صاحب الشغل الخاصة من Maven Toon (مهارة Maven @maven.iqq: شورتس كرتون 2D رأسي 1080×1920، شخصيات بحبر وديكورات مرسومة بعمق، إض… |
| `engine/skills/media-hunter` | Media Hunter within Black Dragon: search currently integrated open/free media APIs for footage and photos, discover complementary site-search links fo… |
| `engine/skills/montage-arena` | حلبة المونتاج — مجلس خبراء مونتاج صدامي. |
| `engine/skills/montage-repos-hub` | Index of the downloaded open-source montage repos and their agent skills in C:\Users\cinde\dragon-repos (video-use, hyperframes, Remotion skills, cut-… |
| `engine/skills/nature-palette` | باليتة الطبيعة — يستخرج باليتة ألوان من صورة طائر أو حيوان أو حشرة أو أي شيء (عربية، فاكهة، منتج)، ويطلع كارت جاهز للنشر بالـ HEX والأسماء بالعربي وأد… |
| `engine/skills/omni-analyst` | المحلل الشامل (Omni Analyst) — عقل تحليل لأي حاجة في المنظومة الرقمية. |
| `engine/skills/paint-studio` | Full Windows 11 Paint feature set as a scriptable skill. |
| `engine/skills/physics-math` | حاسبة الرياضيات والفيزياء للمونتاج والموشن والـ 3D — أحجام ومساحات وأوزان وكثافات، تحويل وحدات، سقوط حر ومقذوفات وارتداد كورة وسبرينج بكيفريمات فريم ب… |
| `engine/skills/planning-mind` | العقل المخطِّط: طريقة تفكير وتخطيط لأي طلب فيه أكتر من خطوة أو فيه غموض. |
| `engine/skills/rea-ultra` | التنين الأسود — الهندسة العكسية الفائقة بـ REA (MCP mcp__rea__* + CLI rea 6.8.0) على ويندوز، ومعاها Ghidra 12.1.4 وJDK 21 وJADX وapktool وadb وrizin و… |
| `engine/skills/reference-lock` | قفل المرجع: لما صاحب الشغل يقول «نفس الخط» أو «نفس الألوان» أو «زي ده بالظبط»، المهارة دي بتستخرج من المرجع الألوان (hex) والخطوط، وتقفلهم كقيود، وتقي… |
| `engine/skills/reverse-engineer-anything` | Reverse engineer native, managed, Electron/JavaScript, packaged, firmware, and browser targets with REA, and build agent environments (AgentEnv bundle… |
| `engine/skills/saas-animation` | Make short, high-end SaaS, app, product and brand animations (about 8–20s) with Claude, built as code and rendered to 4K video, without any AI video o… |
| `engine/skills/sync-guard` | حارس التزامن: أي نص أو كابشن أو موشن جرافيك على فيديو فيه كلام أو أغنية لازم يطلع مع الكلمة وهي بتتقال. |
| `engine/skills/teardown` | محاكي 3D لأي ماكينة — صفحة واحدة أوفلاين فيها الماكينة شغالة، بعدادات حية وزرار لكل جزء (عزل، قطاع، x-ray، تفكيك) وجولة أوتوماتيك، وبعدها فيلم 60 فريم… |
| `engine/skills/theme-factory` | Toolkit for styling artifacts with a theme. |
| `engine/skills/ultra-mind` | العقل الفائق — بروتوكول تفكير مبني على خلاصة كتب التفكير العالمية (Polya، Kahneman، Tetlock، Heuer، Popper، Pearl، Meadows، TRIZ، de Bono) وأبحاث الاس… |
| `engine/skills/video-grabber` | نزّل فيديو من أي موقع بأمر واحد وبأعلى جودة — تحميل فيديو، حمّل من يوتيوب / تيك توك / انستجرام / فيسبوك / تويتر (X) / فيميو / أي موقع، رابط فيديو، است… |
| `engine/skills/visible-thinking` | التفكير المرئي — المهارة اللي مستخرجة من التنين الأسود والتنين الذهبي، وبتخلّي Claude يكتب هو بيفكّر في إيه وهو شغال، بالعربي المصري، زي «💭 بيفكّر دلو… |
| `engine/skills/visual-forge` | مصنع الصورة — بيعمل صور احترافية بـ ChatGPT وفيديوهات حركة بـ Kling بطريقة مبنية على خطة وخطوات: بريف ← 3 كونسبتات ← كتاب لوك ← قايمة لقطات ← برومنتات… |
| `engine/skills/windows-commands` | فهم ويندوز للأوامر — إزاي PowerShell 5.1 وcmd وGit Bash (MSYS2) والبرنامج نفسه بيقروا الأمر فعلًا، مقاس على الجهاز بالتجربة والهندسة العكسية (ILSpy وG… |

## مكتبة المهارات المدمجة جوه المحرك (13)

| المسار | بيعمل إيه |
|---|---|
| `engine/skills/library/ai-motion-graphics` | Motion graphics, animated explainers and sound design for videos, rendered in code (Python + ffmpeg). |
| `engine/skills/library/arabic-minimal-reels` | Edit a raw Arabic talking-head clip into a 9:16 reel in a minimal style - short line, one big key word, blue lines, paintings, flat canvases, returnin… |
| `engine/skills/library/editorial-film-edit` | Edit footage in an archival editorial style with bundled video and photo references, kinetic text, film grain, bloom, masks and presenter splits. |
| `engine/skills/library/faceless-shorts` | Make narrated faceless YouTube Shorts / TikToks / Reels fully in code on the user's computer, with a free local AI voice and word-synced captions, $0. |
| `engine/skills/library/growkaz-stickman` | This skill should be used when the user wants a narrated animated video in the GrowKaz Stickman style (cinematic stick figures with rim light, moody 2… |
| `engine/skills/library/kosif-source-builder` | KOSIF: حقيبة أدوات الإخراج والتصوير والمونتاج (kosif.py، فهرس المستودعات، سكربتات تثبيت ويندوز ولينكس) |
| `engine/skills/library/living-site` | Build a living website in three levels. |
| `engine/skills/library/living-site-kosif` | KOSIF variant of living-site (Arabic RTL checks, --levels/--json/--strict gate, Kling director as level 2, cost ledger). |
| `engine/skills/library/motion-reel` | Produce a beat-synced product launch reel / showreel / promo video in code. |
| `engine/skills/library/omar-hasan-kling-cinematic-director` | Cinematic short-film director for Kling 4 - pitches 10 film ideas, asks duration, then gives Nano Banana asset prompts, a 3x3 storyboard prompt and fi… |
| `engine/skills/library/pro-motion` | برو موشن — أسلوب فارس في التحريك (الأوفرلابنج: ليرز 3D + كاميرا مربوطة في نلاط) وجرافاته وتركاته، وإزاي تعمل الفيديو يا جنريت بالكود يا جوه After Effe… |
| `engine/skills/library/saas-animation` | Make short, high-end SaaS, app, product and brand animations (about 8–20s) with Claude, built as code and rendered to 4K video, without any AI video o… |
| `engine/skills/library/talking-head-reels` | Turn a talking-head recording into a finished vertical 9:16 Instagram Reel / TikTok / YouTube Short in a bold editorial style - tightened pauses, kine… |

## الأدوات (4)

| المسار | بيعمل إيه |
|---|---|
| `tools/cinema-c` | Cinema-C V36 للآيفون: أمر c لتحميل الفيديو بالجودة اللي تختارها (yt-dlp + ffmpeg)، وبوستات صور وكاروسيل إنستجرام بـ gallery-dl (--smart، --gallery، --setup)، والتثبيت بـ --install، مع فرق V35 واختبارات بـ stubs |
| `tools/draw-math` | Precise geometry, measurement and proportion calculator for drawing and animating people and scenes (shadow-puppet films, 3D silhouette films, 2D figu… |
| `tools/link-collector` | collect-links.js: يجمع الروابط من صفحة بمتصفح Chromium حقيقي (--filter، --same-site، --json) |
| `tools/video-page` | video_page.py: صفحة تحميل لكل فيديو (زر أعلى جودة بايت ببايت، نسخة خفيفة، كابشن) ومكتبة «فيديوهات الكوسف» (build، hub-add، check) |

## مكتبة المهارات الخارجية: `library/` (590 مهارة)

بتتدوّر بـ `rd.py skills find …` وبتتثبت بـ `rd.py skills install NAME --yes`. القايمة كاملة: `references/RD_LIBRARY.md`.

## العقل والذاكرة: `mind/`

| الملف | فيه إيه |
|---|---|
| `playbooks.json` | الطرق (الخطط) اللي الراوتر بيختار منها |
| `route_tests.json` + `route_eval/` | اختبارات الراوتر والقياس الأعمى (أرضية 52/58/66) |
| `lessons_seed.jsonl` | الدروس المتعلَّمة من التصحيحات |
| `chats/` + `chats_index.json` | ذاكرة المحادثات |
| `connections.json` | القدرات والاتصالات (MCP، Higgsfield، كروم…) |

## المراجع: `references/` (التنين الأحمر) و`engine/references/` (محرك التنين الأسود)

| ابدأ بـ | ليه |
|---|---|
| `references/RD_RULES.md` | القواعد |
| `references/RD_CHANGELOG.md` | كل نسخة اتغيّر فيها إيه |
| `references/MERGE_V271.md` | كل مصدر من المحادثات القديمة راح فين |
| `engine/skills/planning-mind/` (`rd.py think`) | العقل المخطِّط: كارت فهم، أسأل ولا أفترض، ورك فلو |
| `engine/references/PROTOCOL.md` + `VIDEO_PROTOCOL_V2_ORIGINAL.md` | بروتوكول الفيديو الإلزامي |
| `engine/references/PASTE_PROMPT.md` | برومبت التنين الأسود للنسخ |
| `engine/references/prompts/USIP_v6_4/` | آخر نسخة من بروتوكول USIP (v6.4) |
| `engine/references/FONTS_REQUIRED.md` | الخطوط ومنين ترجع |
