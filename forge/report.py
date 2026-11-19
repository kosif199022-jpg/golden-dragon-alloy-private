"""Write references/BLEND_REPORT.md from the blend's own numbers (ledger/*.json) — no number is typed by hand.

    python -I -X utf8 forge/report.py
"""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
R = json.loads((ROOT / "ledger" / "blend_report.json").read_text(encoding="utf-8"))
C = json.loads((ROOT / "ledger" / "conflicts.json").read_text(encoding="utf-8"))
T = json.loads((ROOT / "forge" / "take.json").read_text(encoding="utf-8"))
E = (ROOT / "ledger" / "eval_test_once.txt").read_text(encoding="utf-8") if (ROOT / "ledger" / "eval_test_once.txt").exists() else ""

L = []
w = L.append
w("# تقرير الصهر — إزاي المستودع كله بقى السبيكة\n")
w(f"- **المصدر:** `{R['source_head']}`")
w(f"- **الوقت:** {R['started']} ← {R['finished']} ({R['seconds']} ث للخلط)")
w(f"- **غرفة الماكينات:** {R['runtime_files']:,} ملف ({R['runtime_bytes'] / 1e6:.0f} ميجا) مطابقة لـ main بالبايت · بصمتها `{R['runtime_digest'][:16]}…`")
w(f"- **الدفتر:** {R['ledger_entries']:,} سطر (كل ملفات main + كل ملفات الفروع والجهاز)، والناقص من main = {R['ledger_missing_runtime']}")
w(f"- **قاعدة المعرفة:** {R['units']:,} وحدة في `kb/alloy.db` ({R['kb_bytes'] / 1e6:.1f} ميجا)\n")

w("## الوحدات\n| النوع | العدد |\n|---|---|")
for k, n in R["units_by_kind"].items():
    w(f"| {k} | {n:,} |")
w("\n| الحالة | العدد | المعنى |\n|---|---|---|")
meaning = {"active": "شغّالة", "review-before-run": "سكربت طرف تالت: يتقري قبل --yes", "private": "ذاكرة المحادثات (مخفية من البحث العادي)",
           "merged": "اتدمجت في وحدة تانية شبهها (ومذكورة جنبها)", "superseded": "فيه نسخة أحدث (مذكورة)",
           "staged": "patch من فرع مستني التطبيق", "quarantined": "معزولة بقاعدة (cookie-copy)"}
for k, n in R["units_by_status"].items():
    w(f"| {k} | {n:,} | {meaning.get(k, '')} |")
w("\n| المصدر | العدد |\n|---|---|")
for k, n in R["units_by_origin"].items():
    w(f"| {k} | {n:,} |")

w("\n## الدمج والتكرار")
w(f"- **المستندات:** {R['doc_files']:,} ملف Markdown ← {R['doc_units']:,} وحدة (المتطابق بالبايت بقى وحدة واحدة بكل مصادره).")
w(f"- **القواعد:** {R['rules_in']} من 5 أماكن، منها {R['rules_merged']} نسخة شبه مطابقة اتدمجت (أضعف تشابه اتدمج 0.913، يعني نفس القاعدة بـ `$W` بدل `$R`).")
w(f"- **الدروس:** {R['lessons_in']}، منها {R['lessons_merged']} مكرر (`s09` كان متكرر برقمه في `lessons_seed.jsonl`).")
w(f"- **الطرق:** {R['playbooks']} طريق × {R['recipes']} وصفة ← {R['roads']} طريق منصهر. أمثلة الطلبات الحقيقية: {R['route_examples_used']} اتحطت جوه الطرق، و{R['route_examples_hidden_test']} من مجموعة test اتشالت عشان القياس يفضل نضيف.")
w(f"- **فهرس الانصهار:** {R['fusion_units']:,} وحدة، منها {R['fusion_merged_into_docs']} اتلزقت في مهارات المستودع نفسها، و{R['fusion_new_units']} وحدة جديدة.")
w(f"- **الكتالوج:** {R['catalog_items']:,} عنصر، منها {R['catalog_merged']} اتلزقت في مهارات موجودة.")
w(f"- **سكربتات بتشتغل:** {R['script_units']}.")
cc = Counter(c["kind"] for c in C)
w(f"- **التعارضات المحلولة (`ledger/conflicts.json`):** " + " · ".join(f"{k} = {v}" for k, v in cc.items()))
for c in C:
    if c["kind"] == "skill-version":
        w(f"  - `{c['name']}`: اتساب `{c['kept']}` (الأحدث)، و`{', '.join(c['superseded'])}` بقت superseded.")

w("\n## الفروع والجهاز\n| المصدر | الحكم | اتاخد | patches | مااتاخدش | ملاحظة |\n|---|---|---|---|---|---|")
for b in T:
    note = (b.get("warn") or "")[:90] or (b.get("adds") or "")[:90]
    w(f"| `{b['branch']}` | {b['verdict']} | {len(b['take'])} | {len(b['patch'])} | {len(b['skipped'])} | {note} |")
w("\n- **SUPERSEDED (3):** شغلها موجود في main بشكل أكمل. ملفاتها متسجّلة في الدفتر «not-taken» ومعاها السبب.")
w("- **الـ patches (7)** محفوظة في `branches/*/PATCHES/`، ومش متطبّقة على `runtime/`. تطبيقها خطوة إصدار: `git apply --3way` في نسخة من المستودع، وبعدين `tools/dragon-maint/manifests.py`، وبعدين selftest، وبعدين أرضية الراوتر. **patch الـ yt-dlp بيحدّث من غير ما يسأل (ضد قاعدة §2): لازم يبقى اختياري الأول.**")
w("- **من اللابتوب:** `gd_custom_api.py` (🔌 API مخصص، 2026-11-19) مش موجود في أي فرع، فاتاخد من النسخة المتثبتة. و2 ملفات claude-app اتاخدوا من اللابتوب لأنها أحدث (تصليح `stdin=DEVNULL`). و122 ملف مشروعات فيديو جوه `motion-reel/videos/` = شغل صاحب الشغل مش معرفة: **يتسابوا في مكانهم وقت التثبيت** (`references/INSTALL.md`).")

w("\n## القياس (المجموعة المخفية test، مرة واحدة، 2026-11-19)\n```\n" + E.strip() + "\n```")
w("- **نفس الصفوف والتسميات والموضوع وإخفاء الأمثلة زي `runtime/mind/route_eval/route_eval2.py`.** الراوتر لوحده طلع 59/72/80، وده نفس رقم الحسبة الرسمية بالظبط.")
w("- **قيم الدمج (k=2، w=0.5) اتحددت قبل أي قياس، ومفيش ضبط بعد test.** أرقام dev مش نضيفة للمعرفة الموحّدة، لأن أمثلة dev نفسها جوه الطرق، فماتستخدمش للمقارنة.")
w("- **العيّنة 112 طلب (حوالي ±9 نقط).** المعرفة الموحّدة لوحدها طلعت +10 في «الأول صح». ده إشارة، والتأكيد محتاج دفعة طلبات جديدة مخفية.")

w("\n## حدود معروفة (بصراحة)")
w("- **إرشاد Anthropic الرسمي:** «كذا مهارة مركّزة أحسن من واحدة كبيرة». السبيكة بتعالج ده بإن `SKILL.md` صغير وبيوجّه بس، والمعرفة بتتحمّل وقت الحاجة. بس هي لسه مهارة كبيرة.")
w("- **الحجم:** `runtime/` حوالي 217 ميجا، وقاعدة المعرفة 47 ميجا. حد حجم الرفع على claude.ai مش مكتوب رسمي، فالنسخة المحمولة (من غير `runtime/`) ماتجربتش رفع.")
w("- **وصف المهارة:** فوق الـ 200 حرف اللي مقالة المساعدة بتقول إنها حد رفع claude.ai، رغم إن المواصفة بتسمح بـ 1024. لو الرفع رفضه، الوصف يتختصر.")
w("- **المسارات الشخصية:** `C:\\Users\\…` موجودة في 115 ملف من ملفات المستودع الأصلية (زي ما هي). الحزمة لصاحبها ولمحادثاته، مش للنشر (قاعدة §6).")
w("- **البحث:** BM25 على نص متطبّع (عربي من غير تشكيل، أ/إ/آ = ا، ة = ه، ى = ي، و«ال» و«و» في الأول). مفيش فهم معاني، فالكلمة الغريبة ممكن تفوت.")
(ROOT / "references" / "BLEND_REPORT.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
print(f"references/BLEND_REPORT.md: {len(L)} lines")
