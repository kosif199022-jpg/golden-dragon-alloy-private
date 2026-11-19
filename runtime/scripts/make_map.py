import sys,re,json,subprocess
from pathlib import Path
R=Path(sys.argv[1])
def desc(sk):
    t=sk.read_text(encoding='utf-8',errors='replace')
    m=re.search(r'^description:\s*"?(.*?)"?\s*$',t,re.M)
    d=(m.group(1) if m else '').strip()
    if d in ('>-','>','|','|-'):
        after=t[m.end():].splitlines()
        d=' '.join(x.strip() for x in after if x.startswith('  ')).strip() if after else ''
        lines=[];
        for x in t[m.end():].splitlines()[1:]:
            if x.startswith(' '): lines.append(x.strip())
            else: break
        d=' '.join(lines)
    d=re.split(r'(?<=[.!؟])\s| Use (for|first|when)',d)[0]
    return (d[:150]+'…') if len(d)>150 else d
L=["# خريطة التنين الأحمر — كل حاجة فين","","اتولّدت أوتوماتيك من شجرة الملفات بـ `python -I -X utf8 scripts/make_map.py .`. لو حاجة اتنقلت، الخريطة دي اللي تتصدق مش الذاكرة.","",
"## الأبواب (أوامر `rd.py`)","","| الأمر | بيوصل لـ |","|---|---|"]
rd=(R/'scripts/rd.py').read_text(encoding='utf-8')
cmds=re.findall(r'sub\.add_parser\("([a-z0-9-]+)"(?:,\s*help="([^"]*)")?',rd)
for grp in re.findall(r'for n in \(([^)]*)\):\s*\n\s*s_? = sub\.add_parser\(n\)',rd):
    cmds+= [(x,'') for x in re.findall(r'"([a-z]+)"',grp)]
for name,help_ in cmds:
    AR={'start':'يبدأ: يعرف هو شغال فين ويوريك الطريق','where':'بيشتغل فين (claude.ai، سحابة، لابتوب)','doctor':'فحص الأدوات والمكتبات','docs':'يولّد المراجع','selftest':'فحص ذاتي سريع (الطرق، القدرات، الدروس، المحادثات)','retro':'مراجعة بعد الشغل','map':'خريطة الطرق','show':'تفاصيل طريق','learn':'يسجّل درس من تصحيح','lessons':'الدروس','outcome':'يسجّل نتيجة طريق (ثقة)','memory':'ذاكرة المحادثات: فين الملف، اتقرر إيه','re':'هندسة عكسية','repo':'تحليل مستودع','repos':'أهم المستودعات','skills':'دوّر/ثبّت مهارة من المكتبة أو المتثبت','x':'يشغّل أمر من محرك التنين الأسود','understand':'يفهم الطلب (صوت، كيبورد إنجليزي، غلطات)','brief':'ملخص JSON: الطريق والمهارات والقدرات للطلب','plan':'الخطة كاملة للطلب: الطريق والخطوات والمهارات','route':'أحسن الطرق للطلب بالدرجات','recall':'يفتكر من المحادثات القديمة','intel':'مستودعات ومعلومات تخص الطلب','teach':'يعلّم الراوتر: الطلب ده طريقه كذا'}
    L.append(f"| `{name}` | {help_ or AR.get(name,'—')} |")
EXTRA={'cinema-c':'Cinema-C V36 للآيفون: أمر c لتحميل الفيديو بالجودة اللي تختارها (yt-dlp + ffmpeg)، وبوستات صور وكاروسيل إنستجرام بـ gallery-dl (--smart، --gallery، --setup)، والتثبيت بـ --install، مع فرق V35 واختبارات بـ stubs','kosif-source-builder':'KOSIF: حقيبة أدوات الإخراج والتصوير والمونتاج (kosif.py، فهرس المستودعات، سكربتات تثبيت ويندوز ولينكس)','video-page':'video_page.py: صفحة تحميل لكل فيديو (زر أعلى جودة بايت ببايت، نسخة خفيفة، كابشن) ومكتبة «فيديوهات الكوسف» (build، hub-add، check)','link-collector':'collect-links.js: يجمع الروابط من صفحة بمتصفح Chromium حقيقي (--filter، --same-site، --json)'}
def section(title,base,depth=1):
    rows=[]
    for d_ in sorted(x for x in base.iterdir() if x.is_dir() and not (x.name=='library' and base.name=='skills')):
        sk=d_/'SKILL.md'
        if not sk.is_file():
            c=sorted(d_.rglob('SKILL.md'))
            if c: sk=c[0]
        if sk.is_file(): rows.append(f"| `{d_.relative_to(R).as_posix()}` | {desc(sk)} |")
        elif d_.name in EXTRA: rows.append(f"| `{d_.relative_to(R).as_posix()}` | {EXTRA[d_.name]} |")
    if rows: L.extend(["",f"## {title} ({len(rows)})","","| المسار | بيعمل إيه |","|---|---|"]+rows)
section("مهارات المحرك",R/'engine/skills')
section("مكتبة المهارات المدمجة جوه المحرك",R/'engine/skills/library')
section("الأدوات",R/'tools')
lib=R/'library'; n=len(list(lib.glob('*/SKILL.md')))
L+=["",f"## مكتبة المهارات الخارجية: `library/` ({n} مهارة)","","بتتدوّر بـ `rd.py skills find …` وبتتثبت بـ `rd.py skills install NAME --yes`. القايمة كاملة: `references/RD_LIBRARY.md`."]
L+=["","## العقل والذاكرة: `mind/`","","| الملف | فيه إيه |","|---|---|",
"| `playbooks.json` | الطرق (الخطط) اللي الراوتر بيختار منها |","| `route_tests.json` + `route_eval/` | اختبارات الراوتر والقياس الأعمى (أرضية 52/58/66) |",
"| `lessons_seed.jsonl` | الدروس المتعلَّمة من التصحيحات |","| `chats/` + `chats_index.json` | ذاكرة المحادثات |","| `connections.json` | القدرات والاتصالات (MCP، Higgsfield، كروم…) |",
"","## المراجع: `references/` (التنين الأحمر) و`engine/references/` (محرك التنين الأسود)","",
"| ابدأ بـ | ليه |","|---|---|","| `references/RD_RULES.md` | القواعد |","| `references/RD_CHANGELOG.md` | كل نسخة اتغيّر فيها إيه |","| `references/MERGE_V271.md` | كل مصدر من المحادثات القديمة راح فين |",
"| `engine/skills/planning-mind/` (`rd.py think`) | العقل المخطِّط: كارت فهم، أسأل ولا أفترض، ورك فلو |","| `engine/references/PROTOCOL.md` + `VIDEO_PROTOCOL_V2_ORIGINAL.md` | بروتوكول الفيديو الإلزامي |","| `engine/references/PASTE_PROMPT.md` | برومبت التنين الأسود للنسخ |","| `engine/references/prompts/USIP_v6_4/` | آخر نسخة من بروتوكول USIP (v6.4) |","| `engine/references/FONTS_REQUIRED.md` | الخطوط ومنين ترجع |"]
(R/'references/RD_MAP.md').write_text("\n".join(L)+"\n",encoding='utf-8')
print(len(L))
