import pathlib, sys
S = pathlib.Path(r"C:\Users\cinde\rd-staging\v2.8")

def sub(p, old, new, count=1):
    f = S / p
    t = f.read_text(encoding="utf-8")
    n = t.count(old)
    if n < 1:
        print("MISSING", p, repr(old[:60])); return False
    t = t.replace(old, new, count)
    f.write_text(t, encoding="utf-8")
    print("ok", p, "found", n)
    return True

sub("SKILL.md", "# التنين الأحمر — Red Dragon v2.8.0 (2026-11-13)", "# التنين الأحمر — Red Dragon v2.8.1 (2026-11-13)")
sub("references/RD_CONNECTIONS.md", "# اتصالات التنين الأحمر — v2.8.0", "# اتصالات التنين الأحمر — v2.8.1")
sub("references/RD_PLAYBOOKS.md", "# Playbooks التنين الأحمر — v2.8.0", "# Playbooks التنين الأحمر — v2.8.1")
sub("references/RD_RE_ROADS.md", "# طرق الهندسة العكسية حسب نوع الهدف — v2.8.0", "# طرق الهندسة العكسية حسب نوع الهدف — v2.8.1")

SEC = """## v2.8.1 — 2026-11-13 (بلوك أنضف لتطبيق التنين، وموضوع كل محادثة لوحدها)
- **المشكلة اللي اتقاست في التطبيق (10 رسايل تجربة):**
  - «كمل» ماكانش ليها بلوك خالص، لأن `brain.note` في التطبيق كان بيرفض أي نص أقل من 4 حروف.
  - التطبيق ماكانش بيبعت سياق، فالعقل كان بيقرا الملف المشترك `last_turn.json`، والموضوع كان بيتسرّب بين المحادثات (طلب لوجو راح re-file بعد رسالة تحليل في محادثة تانية).
  - الدردشة («ازيك»، «شكرا») كان بيطلعلها بلوك 376 لـ 849 حرف مالوش لازمة.
- **في العقل (`rd.py`):**
  - `brief` في الدردشة و«كمل» (`greet` / `cont`) مابيضيفش مستودعات ولا مهارات ولا مكتبة ولا دروس.
  - المستودعات ومهارات المكتبة لازم تطابق كلمتين مختلفتين على الأقل من الطلب (`BRIEF_MIN_HITS = 2`، والكلمة العربي بتتحسب مرة واحدة حتى لو اتوسّعت لمرادفات)، أو أول جزء من اسمها يكون في الطلب (`_hits` و`_named` و`_relevant`).
  - الدروس بتتقص على آخر كلمة كاملة (`_clip`) بدل القص في نص الكلمة.
- **في التطبيق (`apps/dragon_desktop/brain.py` و`app.py`):**
  - `brain.note(text, history=...)`: التطبيق بقى بيبعت آخر 6 رسايل للمستخدم من نفس المحادثة (`Session.log`)، و`chat_topic` بيحسب الموضوع منها بـ `topic_update`، ويمرّره لـ `brief(prev=...)`، فمابقاش فيه اعتماد على الملف المشترك.
  - أي نص مش فاضي بياخد بلوك (منها «كمل»).
- **القياس (327 طلب حقيقي، 2.8.0 قدام 2.8.1، نفس المكتبة):**
  - الطريق المختار اتغيّر في **0** طلب.
  - متوسط البلوك 1,190 ← **1,045** حرف.
  - سطر المستودعات ظهر في 255 ← **115** طلب، وسطر المكتبة 153 ← **53**.
  - الدروس المقطوعة في نص كلمة 342 ← **24**.
  - تجربة التطبيق (10 رسايل): الدردشة 0 بلوك، «كمل» بعد تحليل ← re-file (ثقة عالية)، ومفيش تسريب بين المحادثات، والوقت 1.9 ثانية للعشرة.
- **معروف ولسه:** «اعمل لوجو لقناة…» لسه بيروح download بثقة ضعيفة (ضعف في الراوتر نفسه، مش من التعديل ده).

"""
f = S / "references/RD_CHANGELOG.md"
t = f.read_text(encoding="utf-8")
anchor = "## v2.8.0 — 2026-11-13"
if "## v2.8.1" in t:
    print("changelog already has 2.8.1")
elif anchor in t:
    t = t.replace(anchor, SEC + anchor, 1)
    f.write_text(t, encoding="utf-8")
    print("ok changelog")
else:
    print("MISSING changelog anchor")

# version check in rd.py
r = (S / "scripts/rd.py").read_text(encoding="utf-8")
import re
print("rd.py VERSION:", re.search(r'^VERSION\s*=\s*"([^"]+)"', r, re.M).group(1))
