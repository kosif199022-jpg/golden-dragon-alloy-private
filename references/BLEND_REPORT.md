# تقرير الصهر — إزاي المستودع كله بقى السبيكة

- **المصدر:** `f617a65 2026-11-19T15:32:46+03:00 Merge pull request #28 from kosif199022-jpg/feat/golden-dragon-local-distillation-20261119`
- **الوقت:** 2026-11-19 17:14:06 ← 2026-11-19 17:16:47 (162.3 ث للخلط)
- **غرفة الماكينات:** 7,226 ملف (217 ميجا) مطابقة لـ main بالبايت · بصمتها `f0fe161df12763f7…`
- **الدفتر:** 7,504 سطر (كل ملفات main + كل ملفات الفروع والجهاز)، والناقص من main = 0
- **قاعدة المعرفة:** 26,363 وحدة في `kb/alloy.db` (46.9 ميجا)

## الوحدات
| النوع | العدد |
|---|---|
| catalog-skill | 15,375 |
| power | 6,129 |
| reference | 1,629 |
| script | 851 |
| skill | 670 |
| superpower | 485 |
| tool | 321 |
| lesson | 222 |
| memory | 163 |
| lib | 154 |
| rule | 134 |
| thinking | 51 |
| road | 43 |
| re | 34 |
| program | 32 |
| cmd | 29 |
| engine | 15 |
| studio | 10 |
| mcp | 7 |
| patch | 7 |
| module | 2 |

| الحالة | العدد | المعنى |
|---|---|---|
| active | 25,646 | شغّالة |
| review-before-run | 496 | سكربت طرف تالت: يتقري قبل --yes |
| private | 163 | ذاكرة المحادثات (مخفية من البحث العادي) |
| merged | 40 | اتدمجت في وحدة تانية شبهها (ومذكورة جنبها) |
| superseded | 8 | فيه نسخة أحدث (مذكورة) |
| staged | 7 | patch من فرع مستني التطبيق |
| quarantined | 3 | معزولة بقاعدة (cookie-copy) |

| المصدر | العدد |
|---|---|
| catalog | 22,074 |
| third-party | 2,351 |
| owner | 1,373 |
| fusion | 517 |
| branch | 41 |
| installed-pc | 7 |

## الدمج والتكرار
- **المستندات:** 2,641 ملف Markdown ← 2,457 وحدة (المتطابق بالبايت بقى وحدة واحدة بكل مصادره).
- **القواعد:** 134 من 5 أماكن، منها 39 نسخة شبه مطابقة اتدمجت (أضعف تشابه اتدمج 0.913، يعني نفس القاعدة بـ `$W` بدل `$R`).
- **الدروس:** 222، منها 1 مكرر (`s09` كان متكرر برقمه في `lessons_seed.jsonl`).
- **الطرق:** 38 طريق × 43 وصفة ← 43 طريق منصهر. أمثلة الطلبات الحقيقية: 219 اتحطت جوه الطرق، و45 من مجموعة test اتشالت عشان القياس يفضل نضيف.
- **فهرس الانصهار:** 1,101 وحدة، منها 539 اتلزقت في مهارات المستودع نفسها، و524 وحدة جديدة.
- **الكتالوج:** 22,404 عنصر، منها 330 اتلزقت في مهارات موجودة.
- **سكربتات بتشتغل:** 851.
- **التعارضات المحلولة (`ledger/conflicts.json`):** skill-version = 1 · lesson-near-duplicate = 1 · rule-near-duplicate = 39 · branch-newer = 7
  - `hf-blender-render`: اتساب `engine/skills/hf-blender-render/SKILL.md` (الأحدث)، و`engine/resources/hf-blender-render/SKILL.md` بقت superseded.

## الفروع والجهاز
| المصدر | الحكم | اتاخد | patches | مااتاخدش | ملاحظة |
|---|---|---|---|---|---|
| `claude/sharp-ptolemy-mku5pf` | UNIQUE-BLEND | 0 | 1 | 0 | Three .gitignore lines that ignore .arena/, the per-session runtime folder written by main |
| `codex/golden-dragon-fusion-cli` | UNIQUE-BLEND | 7 | 2 | 0 | (1) Motion Reel engine fixes: type.js sets dir=auto and normal letter-spacing on RTL lines |
| `codex/golden-fusion-json-find` | UNIQUE-BLEND | 0 | 1 | 0 | `dragon_fusion.py find ... --json` prints the raw JSON result list; adds validation for -- |
| `feat/golden-anatomy-bridge-20261117` | SUPERSEDED | 0 | 0 | 8 | An earlier, independent bridge to Anatomy (wheresryan22/anatomy, MIT): forge/modules/gd_an |
| `feat/golden-claude-app` | UNIQUE-BLEND | 7 | 0 | 0 | apps/golden-dragon/claude-app/: turns plain Claude Code into the Golden Dragon without the |
| `feat/golden-dragon-runtime-ledger-20261118` | UNIQUE-BLEND | 21 | 0 | 10 | forge/unified_core/ (experimental 'native unified core'). runtime.py: GoldenDragonCore.exe |
| `feat/golden-dragon-skill-distillation` | SUPERSEDED | 0 | 0 | 13 | distill_skills.py (static SKILL.md section extractor with provenance, 2 MB cap, skips syml |
| `feature/golden-dragon-fusion-share` | UNIQUE-BLEND | 26 | 0 | 28 | The newer state of the portable 'golden-dragon-fusion' skill that main holds in an earlier |
| `feature/golden-dragon-maven-bridge-20261118` | SUPERSEDED | 0 | 0 | 4 | integrations/maven_bridge.py: doctor/analyze/new/render wrapper around a privately license |
| `golden-dragon-v3.5.2-stale-review` | UNIQUE-BLEND | 0 | 3 | 11 | auto-update runs pip install -U without asking (dragon rule §2): make it opt-in before app |
| `laptop-installed` | UNIQUE-BLEND | 1 | 0 | 135 | ميزة «API مخصص» (OpenRouter وأي مزوّد متوافق مع OpenAI) اتعملت على اللابتوب 2026-11-19 ومش |

- **SUPERSEDED (3):** شغلها موجود في main بشكل أكمل. ملفاتها متسجّلة في الدفتر «not-taken» ومعاها السبب.
- **الـ patches (7)** محفوظة في `branches/*/PATCHES/`، ومش متطبّقة على `runtime/`. تطبيقها خطوة إصدار: `git apply --3way` في نسخة من المستودع، وبعدين `tools/dragon-maint/manifests.py`، وبعدين selftest، وبعدين أرضية الراوتر. **patch الـ yt-dlp بيحدّث من غير ما يسأل (ضد قاعدة §2): لازم يبقى اختياري الأول.**
- **من اللابتوب:** `gd_custom_api.py` (🔌 API مخصص، 2026-11-19) مش موجود في أي فرع، فاتاخد من النسخة المتثبتة. و2 ملفات claude-app اتاخدوا من اللابتوب لأنها أحدث (تصليح `stdin=DEVNULL`). و122 ملف مشروعات فيديو جوه `motion-reel/videos/` = شغل صاحب الشغل مش معرفة: **يتسابوا في مكانهم وقت التثبيت** (`references/INSTALL.md`).

## القياس (المجموعة المخفية test، مرة واحدة، 2026-11-19)
```
fresh set · split=test · n=112 · rd v3.5.4 · k=2.0 w=0.5   (top1 exact / acceptable / in top 3)
  rd     59% / 72% / 80%
  kb     69% / 76% / 79%
  kb+u   69% / 75% / 78%
  blend  61% / 74% / 86%
  — only requests that have a road (n=108):
    rd     57% / 71% / 80%
    kb     71% / 79% / 81%
    kb+u   71% / 78% / 81%
    blend  59% / 73% / 85%
```
- **نفس الصفوف والتسميات والموضوع وإخفاء الأمثلة زي `runtime/mind/route_eval/route_eval2.py`.** الراوتر لوحده طلع 59/72/80، وده نفس رقم الحسبة الرسمية بالظبط.
- **قيم الدمج (k=2، w=0.5) اتحددت قبل أي قياس، ومفيش ضبط بعد test.** أرقام dev مش نضيفة للمعرفة الموحّدة، لأن أمثلة dev نفسها جوه الطرق، فماتستخدمش للمقارنة.
- **العيّنة 112 طلب (حوالي ±9 نقط).** المعرفة الموحّدة لوحدها طلعت +10 في «الأول صح». ده إشارة، والتأكيد محتاج دفعة طلبات جديدة مخفية.

## حدود معروفة (بصراحة)
- **إرشاد Anthropic الرسمي:** «كذا مهارة مركّزة أحسن من واحدة كبيرة». السبيكة بتعالج ده بإن `SKILL.md` صغير وبيوجّه بس، والمعرفة بتتحمّل وقت الحاجة. بس هي لسه مهارة كبيرة.
- **الحجم:** `runtime/` حوالي 217 ميجا، وقاعدة المعرفة 47 ميجا. حد حجم الرفع على claude.ai مش مكتوب رسمي، فالنسخة المحمولة (من غير `runtime/`) ماتجربتش رفع.
- **وصف المهارة:** فوق الـ 200 حرف اللي مقالة المساعدة بتقول إنها حد رفع claude.ai، رغم إن المواصفة بتسمح بـ 1024. لو الرفع رفضه، الوصف يتختصر.
- **المسارات الشخصية:** `C:\Users\…` موجودة في 115 ملف من ملفات المستودع الأصلية (زي ما هي). الحزمة لصاحبها ولمحادثاته، مش للنشر (قاعدة §6).
- **البحث:** BM25 على نص متطبّع (عربي من غير تشكيل، أ/إ/آ = ا، ة = ه، ى = ي، و«ال» و«و» في الأول). مفيش فهم معاني، فالكلمة الغريبة ممكن تفوت.
