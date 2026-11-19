# سجل اللينكات (LINKS) - التنين الأسود v10.16.0

> اتولّد أوفلاين من كل محادثات Claude Code القديمة على الجهاز (2026-11-10). مفيش ولا لينك اتفتح. اللينكات الموقّعة/السرية اتشالت، وكل query string اتمسح من لينكات الـ CDN.

البيانات: `app/data/links.json` (schema `black-dragon.links.v1`). الأداة: `python scripts/dragon.py tool links stats|find|list|route|add`.

## الأرقام

- محادثات اتفحصت: 165
- لينكات خام لقيناها: 12068
- فريدة بعد الفلترة: 3139 - محفوظ منها: 1500
- اتشالت للخصوصية/الأسرار/localhost: 456 + 811 ضوضاء (placeholders/IPs/ناقصة)
- لينكات انت لصقتها بنفسك: 252 (كلها محفوظة)
- ريبوهات GitHub: 96 - لينكات Artifact: 8

## حسب الفئة وأداة التنين المسؤولة

| الفئة | العدد | الأداة | الأمر |
|---|---|---|---|
| stock-media | 759 | صيّاد الميديا | `tool hunter hunt "كلمات" --type video  او  tool stock search "كلمات"` |
| other | 432 | مفيش أداة | `-` |
| github-repo | 96 | ربط الريبو | `tool repo status  او  tool repo fusion find "موضوع"` |
| video-source | 84 | تحميل الفيديو | `tool fetch URL --dir out/job  او  tool tiktok-post URL (بوستات صور تيك توك)` |
| ai-service | 45 | hf / visual-forge (حسب الخدمة) | `tool hf guide (Higgsfield)  او  tool visual-forge plan "بريف" (Kling/ChatGPT)` |
| font | 26 | الخطوط | `tool fonts doctor  او  tool fonts fetch --yes` |
| reference | 25 | مفيش أداة - WebFetch يدوي | `-` |
| docs | 20 | المراجع (fusion) | `tool fusion find "موضوع"` |
| claude-artifact | 8 | أداة Artifact (برّه التنين) | `Artifact tool: action=read url=...` |
| music | 5 | fetch --audio | `tool fetch URL --audio  او  tool song-map` |

## أكتر الدومينات

| الدومين | العدد |
|---|---|
| github.com | 99 |
| pexels.com | 89 |
| commons.wikimedia.org | 21 |
| instagram.com | 20 |
| x.com | 19 |
| pixabay.com | 18 |
| esa.int | 18 |
| youtube.com | 18 |
| mixkit.co | 13 |
| arabsstock.com | 13 |
| upload.wikimedia.org | 13 |
| archive.org | 12 |
| code.claude.com | 11 |
| apple.com | 11 |
| storyblocks.com | 11 |
| shutterstock.com | 11 |
| videos.pexels.com | 11 |
| istockphoto.com | 10 |
| videvo.net | 9 |
| flickr.com | 9 |
| pond5.com | 9 |
| claude.ai | 8 |
| coverr.co | 8 |
| polyhaven.com | 8 |
| metmuseum.org | 8 |

## ريبوهات GitHub (الأهم الأول)

- https://github.com/morluto/rea (assistant/tool_result/user, x99)
- https://github.com/kosif199022-jpg/kosif-tool (assistant/tool_result/user, x33)
- https://github.com/google/fonts (assistant/tool_result/user, x28)
- https://github.com/lemomo-ai/lemo-opuscar (assistant/tool_result/user, x10)
- https://github.com/mrdoob/three.js (assistant/tool_result/user, x9)
- https://github.com/patch-gg/pixelfx (assistant/tool_result/user, x9)
- https://github.com/Vincentwei1021/video-shotcraft (assistant/tool_result/user, x8)
- https://github.com/kosif199022-jpg/100-superskills (assistant/tool_result/user, x8)
- https://github.com/kosif199022-jpg/fastify-motion-bro (assistant/tool_result/user, x6)
- https://github.com/kosif199022-jpg/kosif-render-lab (assistant/tool_result/user, x6)
- https://github.com/librosa/librosa (assistant/tool_result/user, x6)
- https://github.com/JohnHeibel/ClaudeAnimationBase (assistant/user, x5)
- https://github.com/joeseesun/opus-video-prompts (assistant/user, x4)
- https://github.com/kosif199022-jpg/ai-style-atlas-prompts (assistant/tool_result/user, x4)
- https://github.com/kosif199022-jpg/kosif-atlas (assistant/tool_result/user, x4)
- https://github.com/yihui-dev/awesome-opus5-5-videos (assistant/user, x4)
- https://github.com/ahujasid/mcp-for-blender (assistant/user, x3)
- https://github.com/pmndrs/react-three-rapier (assistant/tool_result/user, x3)
- https://github.com/NationalSecurityAgency/ghidra (assistant/tool_result, x13)
- https://github.com/yt-dlp/yt-dlp (assistant/tool_result, x13)
- https://github.com/1013503897/jadx-headless-mcp (assistant/tool_result, x12)
- https://github.com/iBotPeaches/Apktool (assistant/tool_result, x12)
- https://github.com/LaurieWired/GhidraMCP (assistant/tool_result, x10)
- https://github.com/Rikorose/DeepFilterNet (assistant/tool_result, x9)
- https://github.com/upx/upx (assistant/tool_result, x8)
- https://github.com/WerWolv/ImHex (assistant/tool_result, x7)
- https://github.com/clearbluejar/ghidriff (assistant/tool_result, x6)
- https://github.com/mandiant/flare-floss (assistant/tool_result, x6)
- https://github.com/skylot/jadx (assistant/tool_result, x6)
- https://github.com/WebAssembly/wabt (assistant/tool_result, x5)
- https://github.com/hasherezade/pe-sieve (assistant/tool_result, x5)
- https://github.com/mandiant/capa (assistant, x5)
- https://github.com/mrexodia/ida-pro-mcp (assistant/tool_result, x5)
- https://github.com/x64dbg/x64dbg (assistant/tool_result, x5)
- https://github.com/PeterL1n/RobustVideoMatting (assistant/tool_result, x4)
- https://github.com/WhiteTowerAI/cut-as-code (assistant/tool_result, x4)
- https://github.com/bethington/ghidra-mcp (assistant/tool_result, x4)
- https://github.com/mandiant/capa-rules (assistant/tool_result, x4)
- https://github.com/mifi/lossless-cut (assistant/tool_result, x4)
- https://github.com/tenfoldmarc/video-edit-skill (assistant/tool_result, x4)
- https://github.com/HexRaysSA/ida-mcp (assistant/tool_result, x3)
- https://github.com/SamboyCoding/Cpp2IL (assistant/tool_result, x3)
- https://github.com/joeseesun/opus-video-prompts@7977c807781d4ba7c235247b8899a72575a30d00 (assistant, x3)
- https://github.com/lordhoell/davinci-resolve-mcp (assistant/tool_result, x3)
- https://github.com/mrexodia/mcp-reversing-dataset (assistant/tool_result, x3)
- https://github.com/patch-gg/pixelfx@044e12a45dc9cc312cec50ee606dfc98afe5adc2 (assistant/tool_result, x3)
- https://github.com/tooflex/davinci-resolve-mcp (assistant/tool_result, x3)
- https://github.com/yihui-dev/awesome-opus5-5-videos@92aee2f586ac0715cb3cbcb6384834f98a33383d (assistant, x3)
- https://github.com/zinja-coder/apktool-mcp-server (assistant/tool_result, x3)
- https://github.com/zinja-coder/jadx-mcp-server (assistant/tool_result, x3)
- https://github.com/AssetRipper/AssetRipper (assistant, x2)
- https://github.com/Impact-I/reFlutter (assistant, x2)
- https://github.com/MobSF/Mobile-Security-Framework-MobSF (assistant, x2)
- https://github.com/OWASP/owasp-mastg (assistant, x2)
- https://github.com/OWASP/owasp-masvs (assistant, x2)
- https://github.com/OWASP/wstg (assistant, x2)
- https://github.com/P1sec/hermes-dec (assistant, x2)
- https://github.com/Perfare/Il2CppDumper (assistant, x2)
- https://github.com/Poly-Haven/Poly-Haven-Asset-Browser (assistant/tool_result, x2)
- https://github.com/Vincentwei1021/video-shotcraft@3ac67b75dd0b3bc2fd807c17f6b7ce35373eef3d (assistant, x2)
- ... وفيه 36 كمان في links.json (`tool links list --category github-repo --limit 100`)

## لينكات التسليم (Artifact / صفحات منشورة)

- https://claude.ai/artifact/GjTX7KLvQs1dppSoAxW7Qj (أول ظهور 2026-11-07)
- https://claude.ai/artifact/5yFRHTqqz5nY3hhEZvTft1 (أول ظهور 2026-10-26)
- https://claude.ai/artifact/JuH77AT2PYZ6dpqHyqLn1H (أول ظهور 2026-10-26)
- https://claude.ai/artifact/VXqKHBFKodSvA2JV7JrD2A (أول ظهور 2026-11-07)
- https://claude.ai/artifact/8jTsAFQMFDb2oA8MsPJ2eL (أول ظهور 2026-10-26)
- https://claude.ai/artifact/52jZrcrPnHByPPVKKXFgSP (أول ظهور 2026-11-07)
- https://claude.ai/artifact/5ynx1gBuPUYMnro8yxRS22 (أول ظهور 2026-11-07)
- https://claude.ai/artifact/TTbHTh5qtBLrruAAWbCXeP (أول ظهور 2026-10-21)

## لينكات الفيديو اللي لصقتها (تيك توك / انستجرام / يوتيوب / X)

- https://vimeo.com/stock/free
- https://vt.tiktok.com/ZSpBGQEVE
- https://vt.tiktok.com/ZSpBg5fpp
- https://vt.tiktok.com/ZSpBg76F1
- https://www.instagram.com/reel/DfAjGYdMBXC
- https://www.instagram.com/reel/DfEs8ddsRXH
- https://www.instagram.com/reel/DfHn7AVMiS_
- https://www.instagram.com/reel/DfIjDb5MXtS
- https://www.instagram.com/reel/DfLPfNmiXfe
- https://vimeo.com/stock/search
- https://vt.tiktok.com/ZSpS99bJM
- https://www.instagram.com/p/DfMZlnKkQSl
- https://www.instagram.com/reel/DfFs4WJxAZF
- https://www.instagram.com/reel/DfG1BZ-n3zH
- https://www.instagram.com/reel/DfNsEGLCRQe
- https://www.instagram.com/reel/DfPzmAeDv0G
- https://www.instagram.com/reel/DfUi8_BlJr-
- https://www.instagram.com/reel/DfUj1woDlG3
- https://www.instagram.com/reel/DfUjvJ9y9UQ
- https://www.instagram.com/reel/DfVw_3EoihV
- https://www.instagram.com/reel/DfX-VatgZ3F
- https://www.instagram.com/reel/DfYG_0rkpzI
- https://www.instagram.com/reel/DfYN9QtkXaP
- https://www.instagram.com/reel/DBi4J7SN9H7

## لينكات لسه مفيش أداة في التنين بتغطيها

- خدمات AI من غير أداة: 35 لينك - أكتر دومينات: creatify.ai (6)، huggingface.co (4)، lumalabs.ai (3)، capcut.com (3)، midjourney.com (2)، pixverse.ai (2)، api.elevenlabs.io (2)، runway.com (1)، api.suno.com (1)، ideogram.ai (1) (Suno وElevenlabs متاحين كـ MCP بس مش أداة dragon؛ Kling/ChatGPT بيتغطوا بـ visual-forge كبرومنت بس).
- فئة other (432): canva.com (4)، google.com (3)، test-streams.mux.dev (2)، w3schools.com (2)، dareful.com (2)، pikwizard.com (2)، placeit.net (2)، kenney.nl (2)، blackbox.global (2)، cubebrush.co (2)، icons8.com (2)، artstation.com (2)، texturify.com (2)، developer.android.com (2)، pngtree.com (2)
- reference (25): مقالات وأخبار وويكيبيديا - بتتقرا بـ WebFetch مش بأداة تنين.
- مواقع ستوك كتير مش في `tool hunter` الحي (discovery فقط): افتحها بإيدك أو ضيفها بـ `tool links add URL --note ...`.
- لينكات تيك توك القصيرة vt.tiktok.com بتتحمّل بـ `tool fetch` بس لو yt-dlp فاتح؛ بوستات الصور بـ `tool tiktok-post`.

## إزاي تستخدمه

```
python scripts/dragon.py tool links stats
python scripts/dragon.py tool links find pexels
python scripts/dragon.py tool links list --category github-repo --limit 30
python scripts/dragon.py tool links route https://www.instagram.com/reel/XXXX
python scripts/dragon.py tool links add https://example.org/page --note "ملاحظتي"
```

`add` بيكتب في `%LOCALAPPDATA%\BlackDragon\links_user.json` بس، ومش جوه الـ skill، وبيرفض أي لينك فيه token أو key أو sig أو إيميل.
