# -*- coding: utf-8 -*-
"""Make a plain Claude Code session the Golden Dragon (no desktop app needed). Undo with --uninstall.

    python -X utf8 install.py                 install / update (idempotent; re-run after every pull)
    python -X utf8 install.py --uninstall     remove everything it added (backups stay)
    python -X utf8 install.py --status        show what is installed
Options: --home DIR (default: your home; tests use a temp folder)  --no-mcp (don't call `claude mcp`)

What it touches (each file is backed up first to ~/.claude/golden-dragon/backups/<time>/):
  1. ~/.claude/golden-dragon/GOLDEN.md       the app's instructions, generated from ../app/app.py (gen_prompt.py)
  2. ~/.claude/CLAUDE.md                      one import line between markers: @~/.claude/golden-dragon/GOLDEN.md
  3. ~/.claude/settings.json                  a UserPromptSubmit hook -> brief_hook.py (the brain note before each message)
  4. ~/.claude/agents/golden-reviewer.md, golden-helper.md   (the 🧐 reviewer and the parallel helper)
  5. `claude mcp add -s user`: golden-dragon-app (golden_mcp.py) and golden-dragon (../app/mcp_dragon.py: catalog, engines,
     RE tools, and the link to the desktop app when it is open)
Nothing is pushed, published or deleted. New sessions pick it up (the current one doesn't reload CLAUDE.md or MCP servers)."""
import argparse, datetime, json, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gen_prompt  # noqa: E402

START, END = "<!-- golden-dragon-app:start -->", "<!-- golden-dragon-app:end -->"
MARK = "generated-by: golden-dragon claude-app"
MCP_APP, MCP_DRAGON = "golden-dragon-app", "golden-dragon"


def py():
    return shutil.which("python") or sys.executable


class Inst:
    def __init__(self, home, mcp=True):
        self.home = Path(home)
        self.claude = self.home / ".claude"
        self.gd = self.claude / "golden-dragon"
        self.mcp = mcp
        self.bak = self.gd / "backups" / datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.log = []

    def backup(self, f):
        if f.exists():
            self.bak.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, self.bak / f.name)

    # 1 + 2
    def prompt(self):
        self.gd.mkdir(parents=True, exist_ok=True)
        g = self.gd / "GOLDEN.md"
        txt = gen_prompt.build()
        g.write_text(txt, encoding="utf-8")
        self.log.append(f"GOLDEN.md: {len(txt):,} حرف ← {g}")
        cm = self.claude / "CLAUDE.md"
        ref = "@~/.claude/golden-dragon/GOLDEN.md" if self.home == Path.home() else "@" + g.as_posix()
        block = f"{START}\n{ref}\n{END}"
        old = cm.read_text(encoding="utf-8") if cm.exists() else ""
        if START in old and END in old:
            new = old[:old.index(START)] + block + old[old.index(END) + len(END):]
        else:
            new = (old.rstrip() + "\n\n" if old.strip() else "") + block + "\n"
        if new != old:
            self.backup(cm)
            cm.write_text(new, encoding="utf-8")
        self.log.append(f"CLAUDE.md: سطر الاستيراد ← {cm}")

    # 3
    def hook_cmd(self):
        return f'"{py()}" -X utf8 "{HERE / "brief_hook.py"}"'

    def settings(self, remove=False):
        f = self.claude / "settings.json"
        d = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        hooks = d.setdefault("hooks", {})
        lst = [e for e in hooks.get("UserPromptSubmit", []) if not any("brief_hook.py" in (h.get("command") or "") for h in e.get("hooks", []))]
        if not remove:
            lst.append({"hooks": [{"type": "command", "command": self.hook_cmd(), "timeout": 15}]})
        if lst:
            hooks["UserPromptSubmit"] = lst
        else:
            hooks.pop("UserPromptSubmit", None)
        if not hooks:
            d.pop("hooks", None)
        self.backup(f)
        self.claude.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.log.append(("شيل" if remove else "hook عقل التنين") + f" ← {f}")

    # 4
    AGENTS = {
        "golden-reviewer": ("sonnet", "Read, Grep, Glob",
                            "مراجع التفكير 🧐 للتنين الذهبي: ابعتله خطتك أو مسودة ردك قبل فعل مابيرجعش أو تسليم كبير، وهو بيمسك الغلط الحقيقي بس.",
                            None),
        "golden-helper": ("sonnet", None,
                          "وكيل مساعد للتنين الذهبي: خد جزء مستقل من المهمة (قراية، قياس، رندر مقطع، بحث) وخلّصه بالتوازي مع غيره.",
                          "أنت وكيل مساعد للتنين الذهبي. خلّص المهمة اللي اتبعتتلك بالأدوات، وماتعملش أي رفع أو نشر أو مسح أو صرف رصيد. "
                          "في الآخر اكتب تقرير قصير بالعربي: النتيجة، والأوامر اللي اتشغّلت، ومسارات الملفات الكاملة، وإيه اللي ماتجربش."),
    }

    def agents(self, remove=False):
        d = self.claude / "agents"
        for name, (model, tools, desc, body) in self.AGENTS.items():
            f = d / f"{name}.md"
            if remove:
                if f.exists() and MARK in f.read_text(encoding="utf-8", errors="replace"):
                    f.unlink()
                    self.log.append(f"شيل {f}")
                continue
            if body is None:
                body = gen_prompt.reviewer() + ("\n\nاكتب ردك بالعربي المصري البسيط. لو مفيش مشكلة حقيقية قول «تمام، مفيش اعتراض» في سطر.")
            fm = [f"name: {name}", f"description: {desc}", f"model: {model}", f"# {MARK}"]
            if tools:
                fm.insert(3, f"tools: {tools}")
            d.mkdir(parents=True, exist_ok=True)
            if f.exists() and MARK not in f.read_text(encoding="utf-8", errors="replace"):
                self.log.append(f"وكيل {name}: فيه ملف بتاعك بنفس الاسم، سبته زي ما هو ← {f}")
                continue
            f.write_text("---\n" + "\n".join(fm) + "\n---\n\n" + body.strip() + "\n", encoding="utf-8")
            self.log.append(f"وكيل {name} ← {f}")

    # 6 (idea from «التنين_الذهبي_بدون_تطبيق.cmd» that the app wrote): a double-click launcher + the engine repo as an extra
    #    folder. Unlike that file it needs no cc_system.md (the app doesn't have to have run): GOLDEN.md is already imported.
    def repo(self):
        for base in (self.home / "OneDrive" / "Desktop", self.home / "Desktop"):
            for sub in ("", "مهارات"):
                c = base / sub / "التنين الأسود"
                if c.is_dir():
                    return c
        return None

    def launcher_path(self):
        return self.gd / "golden-dragon.cmd"         # ASCII: WScript.Shell can't save a shortcut pointing at Arabic names

    def desktop(self):
        for d in (self.home / "OneDrive" / "Desktop", self.home / "Desktop"):
            if d.is_dir():
                return d
        return None

    def shortcut_path(self):
        d = self.desktop()
        return d / "التنين الذهبي - Claude Code.lnk" if d else None

    def launcher(self, remove=False):
        f, lnk = self.launcher_path(), self.shortcut_path()
        if remove:
            for p in (f, lnk):
                if p and p.exists():
                    p.unlink()
                    self.log.append(f"شيل {p}")
            return
        repo = self.repo()
        add = f' --add-dir "{repo}"' if repo else ""
        self.gd.mkdir(parents=True, exist_ok=True)
        f.write_text("\r\n".join([
            "@echo off", "chcp 65001 >nul",
            "rem " + MARK + " — التنين الذهبي من غير التطبيق: Claude Code + GOLDEN.md (من CLAUDE.md) + خوادم golden-dragon.",
            "rem دبل كليك (بيشتغل على سطح المكتب)، أو اسحب مجلد على الاختصار، أو: golden-dragon.cmd \"C:\\مجلد\\الشغل\"",
            "rem الافتراضي سطح المكتب مش مجلد المستخدم: Claude Code بيسأل «تثق في المجلد؟» كل مرة في مجلد المستخدم، وفي غيره مرة واحدة.",
            f'if not "%~1"=="" (cd /d "%~1") else (cd /d "{self.desktop() or self.home}")',
            "title التنين الذهبي - %CD%",
            "echo Golden Dragon (no app) - working folder: %CD%",        # conhost can't draw Arabic right-to-left
            f"claude{add} --permission-mode auto %2 %3 %4 %5",
            ""]), encoding="utf-8")
        self.log.append(f"المشغّل ← {f}")
        if lnk and os.name == "nt" and self.home == Path.home():
            ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:GD_LNK); $s.TargetPath=$env:GD_CMD; "
                  "$s.WorkingDirectory=$env:USERPROFILE; $s.Description='Golden Dragon in Claude Code (no app)'; $s.Save()")
            ico = HERE.parent / "app" / "ui" / "golden-dragon.ico"
            if ico.exists():
                ps = ps.replace("$s.Save()", "$s.IconLocation=$env:GD_ICO; $s.Save()")
            tmp = lnk.with_name("golden-dragon-claude-code.lnk")      # saved under an ASCII name, then renamed in Python
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, timeout=60,
                           env=dict(os.environ, GD_LNK=str(tmp), GD_CMD=str(f), GD_ICO=str(ico)))
            if tmp.exists():
                os.replace(tmp, lnk)
            if lnk.exists():
                self.log.append(f"اختصار سطح المكتب ← {lnk}")

    def extra_dir(self, remove=False):
        """The engine repo in permissions.additionalDirectories, so every session (not only the launcher) can use it."""
        repo = self.repo()
        f = self.claude / "settings.json"
        state_f = self.gd / "state.json"
        state = json.loads(state_f.read_text(encoding="utf-8")) if state_f.exists() else {}
        d = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        dirs = d.setdefault("permissions", {}).setdefault("additionalDirectories", [])
        if remove:
            if state.get("added_dir") in dirs:
                dirs.remove(state["added_dir"])
                self.log.append(f"شيل {state['added_dir']} من additionalDirectories")
            state.pop("added_dir", None)
        elif repo and str(repo) not in dirs:
            dirs.append(str(repo))
            state["added_dir"] = str(repo)
            self.log.append(f"مجلد التنين الأسود في كل الجلسات ← {repo}")
        if not dirs:
            d["permissions"].pop("additionalDirectories")
        if not d.get("permissions"):
            d.pop("permissions", None)
        self.backup(f)
        f.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.gd.mkdir(parents=True, exist_ok=True)
        state_f.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    # 5
    def claude_cli(self, *args):
        exe = shutil.which("claude")
        if not exe:
            raise RuntimeError("أمر claude مش موجود على الـ PATH")
        r = subprocess.run([exe, *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        return r.returncode, (r.stdout + r.stderr).strip()

    def mcp_servers(self, remove=False):
        if not self.mcp:
            self.log.append("MCP: اتخطّى (--no-mcp)")
            return
        self.backup(self.home / ".claude.json")
        for name in (MCP_APP, MCP_DRAGON):
            self.claude_cli("mcp", "remove", "-s", "user", name)
        if remove:
            self.log.append(f"MCP: شيل {MCP_APP} و{MCP_DRAGON}")
            return
        env = ["-e", "PYTHONIOENCODING=utf-8"]
        rc1, o1 = self.claude_cli("mcp", "add", "-s", "user", MCP_APP, *env, "--", py(), "-X", "utf8", str(HERE / "golden_mcp.py"))
        rc2, o2 = self.claude_cli("mcp", "add", "-s", "user", MCP_DRAGON, *env, "-e", "BD_SCOPE=claude-code", "--",
                                  py(), "-X", "utf8", str(HERE.parent / "app" / "mcp_dragon.py"))
        if rc1 or rc2:
            raise RuntimeError(f"claude mcp add فشل:\n{o1}\n{o2}")
        self.log.append(f"MCP: {MCP_APP} (golden_mcp.py) و{MCP_DRAGON} (mcp_dragon.py) متسجّلين على مستوى المستخدم")

    def uninstall(self):
        cm = self.claude / "CLAUDE.md"
        if cm.exists():
            old = cm.read_text(encoding="utf-8")
            if START in old and END in old:
                self.backup(cm)
                new = (old[:old.index(START)] + old[old.index(END) + len(END):]).strip()
                cm.write_text(new + "\n" if new else "", encoding="utf-8")
                self.log.append(f"شيل سطر الاستيراد ← {cm}")
        self.settings(remove=True)
        self.extra_dir(remove=True)
        self.launcher(remove=True)
        self.agents(remove=True)
        self.mcp_servers(remove=True)
        g = self.gd / "GOLDEN.md"
        if g.exists():
            g.unlink()
            self.log.append(f"شيل {g}")

    def status(self):
        cm = self.claude / "CLAUDE.md"
        s = self.claude / "settings.json"
        return {"GOLDEN.md": (self.gd / "GOLDEN.md").exists(),
                "CLAUDE.md import": cm.exists() and START in cm.read_text(encoding="utf-8"),
                "hook": s.exists() and "brief_hook.py" in s.read_text(encoding="utf-8"),
                "agents": {n: (self.claude / "agents" / f"{n}.md").exists() for n in self.AGENTS},
                "launcher": self.launcher_path().exists(),
                "desktop_shortcut": bool(self.shortcut_path() and self.shortcut_path().exists()),
                "engine_repo": str(self.repo() or ""),
                "source": str(HERE)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--home", default=str(Path.home()))
    ap.add_argument("--no-mcp", action="store_true")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    i = Inst(a.home, mcp=not a.no_mcp)
    if a.status:
        print(json.dumps(i.status(), ensure_ascii=False, indent=1))
        return 0
    if a.uninstall:
        i.uninstall()
    else:
        i.prompt()
        i.settings()
        i.extra_dir()
        i.launcher()
        i.agents()
        i.mcp_servers()
    print("\n".join("✓ " + l for l in i.log))
    if i.bak.exists():
        print(f"النسخ الاحتياطية: {i.bak}")
    if not a.uninstall:
        print("خلاص: افتح محادثة Claude Code جديدة، وهتبقى التنين الذهبي بكل أدواته.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
