"""app.py: wire the Red Dragon brain into every message and into the system prompt; expose brain_status to the UI."""
import sys
from pathlib import Path

d = Path(sys.argv[1])
p = d / "app.py"
s = p.read_text(encoding="utf-8")


def rep(old, new, text, count=1):
    assert text.count(old) == count, (text.count(old), old[:80])
    return text.replace(old, new)


if "import brain" not in s:
    s = rep("import anthropic\n", "import anthropic\nimport brain\n", s)
    s = rep('''        if self.control:
            content.insert(0, {"type": "text", "text": CONTROL_NOTE})
        if not self.title:''', '''        if self.control:
            content.insert(0, {"type": "text", "text": CONTROL_NOTE})
        if settings_get("brain", True) and not self.zero:      # Red Dragon brain: decoded request + playbook + lessons
            bn = brain.note(text or "")
            if bn:
                content.insert(0, {"type": "text", "text": bn})
                self.emit("brain", text=bn[:1200])
        if not self.title:''', s)
    s = rep('''اتكلم بالعربي المصري البسيط، باختصار ووضوح، وابدأ ردك بالنتيجة.
''', '''اتكلم بالعربي المصري البسيط، باختصار ووضوح، وابدأ ردك بالنتيجة.

## عقل التنين الأحمر
لو أول الرسالة فيها بلوك «[عقل التنين الأحمر …]»: ده ملخص اتحسب على الجهاز (الطلب بعد فك الكتابة، الطريق المقترح بخطواته، الموافقات، بوابة التسليم، ودروس من تصحيحات قديمة). استخدمه كنقطة بداية، ولو الطلب واضح إنه حاجة تانية امشي ورا الطلب.
- الطلب لو حروف إنجليزي مالهاش معنى يبقى عربي متكتب والكيبورد إنجليزي: اشتغل على النص المفكوك اللي في البلوك، وماتطلبش منه يعيد الكتابة.
- المهارة في `~/.claude/skills/red-dragon`: `python -X utf8 scripts/rd.py plan "<الطلب>"` للخطة الكاملة، و`re TARGET` لأي ملف أو لينك، و`intel "<كلمات>"` للمستودعات المتحلّلة، و`mind/OWNER_ESSENCE.md` لمعرفة صاحب الشغل.
- أي تصحيح أو اعتراض من المستخدم: سجّله في نفس الدور بـ `rd.py learn "<إيه اللي حصل ← إيه اللي يتعمل>" --domain D`، وبعد التسليم `rd.py outcome <playbook> ok|fail`.
- التسليم: المسار الكامل للناتج في أول سطر (والناتج على سطح المكتب)، وبعده «إيه اللي اتغيّر» في نقط، وإيه اللي ماتجربش.
''', s)
    s = rep("def load_settings():", '''def settings_get(k, default=None):
    return load_settings().get(k, default)


def settings_set(k, v):
    d = load_settings()
    d[k] = v
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def load_settings():''', s)
    # API for the UI
    s = rep("    def mcp_status(self,", '''    def brain_status(self):
        st = brain.status()
        st["on"] = bool(settings_get("brain", True))
        return st

    def set_brain(self, on):
        settings_set("brain", bool(on))
        return {"on": bool(on)}

    def understand(self, text):
        return brain.understand(text or "")

    def mcp_status(self,''', s)
p.write_text(s, encoding="utf-8")
print("app.py patched; settings_get:", "def settings_get" in s, "settings_set:", "def settings_set" in s, "self.zero:", "self.zero" in s)

u = d / "ui" / "index.html"
h = u.read_text(encoding="utf-8")
if "e.kind==='brain'" not in h:
    h = rep("  if(e.kind==='attachments'){", """  if(e.kind==='brain'){add(s,'bot','<details class="raw"><summary>🧠 عقل التنين الأحمر فهم الطلب واقترح الطريق</summary><div class="sub" style="white-space:pre-wrap">'+esc(e.text)+'</div></details>'); return}
  if(e.kind==='attachments'){""", h)
    u.write_text(h, encoding="utf-8")
print("ui patched")
