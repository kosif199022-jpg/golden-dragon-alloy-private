# اتصالات التنين الأحمر — v3.4.0

الاتصالات اللي التنين الأحمر بيضيفها فوق سجل المحرك (`engine/tools/powers/powers.json`، 50 قدرة). كل بند: إزاي تتأكد إنه موجود في الجلسة دي، إزاي تستخدمه بالظبط، والبديل لو مش موجود. اتقاس على لابتوب صاحب التنين 2026-11-12. أدوات الجلسة (MCP، كروم، وكلاء) مابتتشافش من بايثون: اتأكد منها بـ ToolSearch.

## الملفات والأوامر (Read، Edit، Write، Grep، Glob، Bash، PowerShell) (`rd-files`) — ✅ ببلاش · both
- **إزاي تتأكد إنه موجود:** موجودين دايمًا في Claude Code. في claude.ai: أدوات الملفات بتاعة الحاسوب السحابي.
- **إزاي تستخدمه:** Read بمسار كامل (بيقرا صور وPDF ونوتبوك). Grep بدل grep، وGlob بدل find. Edit لاستبدال نص بالظبط، وWrite لملف جديد. على ويندوز: Bash = Git Bash (‎/dev/null، مسارات /c/…)، وPowerShell 5.1 (مفيهوش && ولا ?:). العربي: python -X utf8 و PYTHONIOENCODING=utf-8. أي سكربت طويل فيه علامات تنصيص: اكتبه في ملف بـ Write وشغّله، مش heredoc. الأمر الطويل: run_in_background وهتوصلك إشارة لما يخلص (ممنوع sleep). الملفات المؤقتة في مجلد scratchpad بتاع الجلسة.
- **لو مش موجود:** claude.ai: ‎/mnt/user-data/uploads للداخل و‎/mnt/user-data/outputs للخارج.

## صفحة Artifact خاصة على claude.ai (تقرير، داشبورد، عرض) (`rd-artifact`) — ✅ ببلاش · both
- **إزاي تتأكد إنه موجود:** أداة Artifact في قايمة الأدوات.
- **إزاي تستخدمه:** أول نداء: Artifact action:quickstart بـ intent (document / slides / design / other). حمّل مهارة artifact-design قبل كتابة الصفحة، وartifact-capabilities لو الصفحة هتحفظ بيانات. اكتب HTML في ملف وانشره بـ file_path؛ التحديث بنفس المسار. الصفحة خاصة لحد ما صاحبها يشاركها. ماتنشرش حاجة بتقلّد جهة أو شخص حقيقي.
- **لو مش موجود:** claude.ai: artifacts العادية.

## سؤال باختيارات، ووضع التخطيط (`rd-ask`) — ✅ ببلاش · pc
- **إزاي تتأكد إنه موجود:** AskUserQuestion و EnterPlanMode (التانية بـ ToolSearch).
- **إزاي تستخدمه:** AskUserQuestion بس لقرار بتاع صاحب الشغل فعلًا ومايتحلّش من الطلب أو الكود: 2–4 اختيارات، والمقترح أول واحد وعليه (Recommended). الاختيارات اللي ليها شكل: preview. غير كده: اختار الافتراضي المعقول، قول اخترت إيه، وكمّل.
- **لو مش موجود:** اسأل في الشات سؤال واحد.

## تحميل أي مهارة متثبتة بالاسم (أداة Skill) (`rd-skill-tool`) — ✅ ببلاش · both
- **إزاي تتأكد إنه موجود:** قايمة المهارات في تذكير النظام. على اللابتوب: 39 مهارة في ~/.claude/skills + مهارات anthropic-skills (docx، pdf، pptx، xlsx، skill-creator، deep-research، computer-use، built-in-browser).
- **إزاي تستخدمه:** Skill {skill:"الاسم بالظبط"} قبل ما تبدأ في أي شغل المهارة بتغطّيه. «استخدم كل المهارات» = اختار اللي يخدم الطلب بس (من playbook: حقل skills)، وقول استخدمت أنهي واحدة في إيه. نسخ المهارات جوه الحزمة: engine/skills/NAME/SKILL.md (تتقري بـ Read لو المهارة مش متثبتة).
- **لو مش موجود:** اقرا engine/skills/NAME/SKILL.md مباشرة.

## أدوات REA بالاسم (229 أداة) حسب نوع الهدف (`rd-rea-tools`) — ✅ ببلاش · pc
- **إزاي تتأكد إنه موجود:** ToolSearch "+rea inspect" · `rea --version` = 6.8.0 · `rea doctor` (healthy:false بس عشان Hopper/IDA الاختياريين).
- **إزاي تستخدمه:** ابدأ دايمًا بـ inspect_artifact ثم binary_overview. الجلسة: open_binary ← … ← close_binary (snapshot_path بيحفظ التحليل).
- **الأدوات بالاسم:** Native: inspect_pe_imports / inspect_pe_resources / inspect_pe_certificates / inspect_macho / inspect_elf_notes / inspect_native_exports / list_procedures / procedure_pseudo_code / procedure_callers / xrefs / search_strings / search_bytes / batch_decompile / build_call_path. Managed (.NET، Java): inspect_managed_artifact / inspect_managed_members / compare_managed_members. Python: inspect_python_pyc. Go / Rust: inspect_go_binary / inspect_rust_binary. JavaScript و Electron: analyze_javascript_application / analyze_web_bundle / recover_javascript_sources / inspect_electron_fuses / inspect_electron_page / trace_javascript_semantics. الويب: inspect_web_page / capture_browser_scenario / inspect_web_network_capture / export_web_scripts / trace_web_module_imports / compare_web_captures. Android: inspect_android_package / inspect_apk_signature / search_android_classes / inspect_android_class / decode_android_resources. بيانات: inspect_sqlite_database / inspect_plist / inspect_packet_capture / inspect_model_artifact / inspect_wasm_artifact / extract_firmware. مقارنة نسخ: compare_artifacts / compare_application_versions / find_changed_behavior / compare_functions. أدلة: record_unknown / list_unknowns / export_evidence_bundle / verify_reconstruction. وقت التشغيل (بموافقة): start_frida_session / instrument_with_frida / start_gdb_session / observe_native_calls / capture_process_scenario / adb (install_adb_package، start_adb_app…).
- **لو مش موجود:** $E tool rea-ultra plan|triage (خطط بس) و $R re TARGET؛ التحليل الفعلي محتاج اللابتوب.

## جسر تطبيق التنين: كلّم التطبيق من Claude Code والعكس (`rd-app-bridge`) — ✅ ببلاش · pc
- **إزاي تتأكد إنه موجود:** $E tool machine app status ← بيرجّع version و engine و model والمحادثات المفتوحة. لو فشل: التطبيق مقفول.
- **إزاي تستخدمه:** HTTP على 127.0.0.1 بورت 47821، مسار ‎/app، والتوكن من %APPDATA%/BlackDragon/settings.json (bridge_token؛ مايتطبعش ولا يتحزّم). الأفعال: status / chats / read sid=… / send text=… [sid=…] / reply / stop. الاستخدام: اختبار حقيقي للتطبيق بعد أي تعديل (ابعت رسالة واقرا الرد)، ومتابعة محادثة شغالة من غير ما تلمس ملفاتها. جوه التطبيق نفسه: أداة blackdragon_app. لو محادثة في التطبيق busy على نفس المجلد: اقرا بس، واشتغل في مجلد منفصل.
- **لو مش موجود:** مش متاح من السحابة.

## 66 مستودع مونتاج وهندسة عكسية وتصميم متنزّلين على اللابتوب (متحلّلين) (`rd-local-repos`) — ✅ ببلاش · pc
- **إزاي تتأكد إنه موجود:** ~/dragon-repos موجود · $R intel "<كلمات>".
- **إزاي تستخدمه:** $R intel "subtitle" ← ملف المستودع: الرخصة، نقط الدخول، الاعتماديات، مهارات Claude جواه، وأنماط «راجع قبل التشغيل». الملفات كلها: references/RD_INTEL_REPOS.md. تحديث ملف: $R repo ~/dragon-repos/NAME --save. فهرس بالاستخدام: مهارة montage-repos-hub.
- **لو مش موجود:** الملفات المتحلّلة جوه الحزمة (mind/intel/repos.json)؛ الكود نفسه على اللابتوب بس.

## محركات ذكاء تانية جوه التطبيق (API، ChatGPT/Codex، Gemini) والمقارنة (`rd-other-ai`) — 🔒 بموافقة · pc
- **إزاي تتأكد إنه موجود:** تطبيق التنين ← قايمة المحرك؛ status بيقول engine الحالي.
- **إزاي تستخدمه:** الافتراضي: اشتراك Claude (Claude Code headless، من غير مفتاح API). وضع API بيصرف من رصيد المفتاح، فبموافقة. المقارنة (cmp) بتبعت نفس السؤال لأكتر من موديل. فريق الوكلاء: موديل لكل وكيل. استخدمه لرأي تاني مستقل في قرار مهم، مش لكل طلب.
- **لو مش موجود:** وكيل Agent ببريف مستقل كرأي تاني.

## GitHub CLI (gh): قراية مستودعات وإصدارات (`rd-gh`) — 🔒 بموافقة · pc
- **إزاي تتأكد إنه موجود:** `gh --version` = 2.103.3 · `gh auth status`.
- **إزاي تستخدمه:** قراية ببلاش: gh repo view OWNER/REPO --json description,licenseInfo,stargazerCount,pushedAt · gh api repos/OWNER/REPO/releases/latest · gh search repos "…" --sort stars. التنزيل (clone / release download) بموافقة. push و pr create و أي كتابة: «أيوه» كل مرة.
- **لو مش موجود:** WebFetch على api.github.com/repos/OWNER/REPO.

## تحليل البرامج المتثبتة على الجهاز (للفهم والأتمتة) (`rd-intel-programs`) — ✅ ببلاش · pc
- **إزاي تتأكد إنه موجود:** engine/references/MACHINE_MAP.md و MACHINE_INVENTORY_*.md (35 برنامج بمساراتهم ونسخهم).
- **إزاي تستخدمه:** لأي برنامج: (1) `PROGRAM --help` و `--version` واحفظ الخيارات. (2) هل ليه وضع من غير واجهة؟ blender -b -P script.py · gimp-console-3.2 -i --batch-interpreter python-fu-eval -b · inkscape --export-type=png · kritarunner -s SCRIPT · melt project.mlt -consumer avformat:out.mp4 · NatronRenderer -w Write1 1-100 proj.ntp · darktable-cli IN OUT · magick. (3) صيغة ملف المشروع (XML/JSON؟) تتولّد بالكود. (4) ملوش CLI: mcp__blackdragon__computer (صورة ← فعل ← تأكيد). (5) سجّل اللي اشتغل: $R learn.
- **لو مش موجود:** ffmpeg / ImageMagick / Blender (بعد تنزيل بموافقة) في sandbox_exec.

## باقي القدرات (52 قدرة من سجل المحرك)
`references/ENGINE_POWERS.md` (نسخة من `engine/references/ALL_POWERS_*.md`) أو `$R map`.
