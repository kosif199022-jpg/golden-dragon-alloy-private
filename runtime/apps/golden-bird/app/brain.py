"""Red Dragon brain bridge for the desktop app.

Before each message goes to the model, ask the installed Red Dragon skill (~/.claude/skills/red-dragon/scripts/rd.py)
for a short mission brief: the request after fixing wrong-keyboard / voice-typing slips, the suggested playbook with
its steps, approvals and delivery gates, and lessons learned from earlier corrections. Read-only and best-effort:
any failure returns an empty note and the chat goes on exactly as before."""
import argparse, datetime, hashlib, importlib.util, json, os, shutil, subprocess, threading, zipfile  # noqa: F401  (rd.py needs them when the app is frozen)
from pathlib import Path

SKILLS = Path.home() / ".claude" / "skills"
CANDIDATES = (("red-dragon", "rd.py"), ("white-dragon", "wd.py"))
_lock = threading.Lock()
_mod = {"path": None, "mtime": 0, "m": None}


def brain_path():
    for name, script in CANDIDATES:
        p = SKILLS / name / "scripts" / script
        if p.is_file():
            return p
    return None


def _load():
    p = brain_path()
    if not p:
        return None
    mt = p.stat().st_mtime
    with _lock:
        if _mod["m"] is None or _mod["path"] != p or _mod["mtime"] != mt:      # reload when the skill is updated
            spec = importlib.util.spec_from_file_location("dragon_brain_rd", p)
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            _mod.update(path=p, mtime=mt, m=m)
        return _mod["m"]


def status():
    p = brain_path()
    if not p:
        return {"ok": False, "why": "مهارة التنين الأحمر مش متثبتة في ~/.claude/skills/red-dragon"}
    try:
        m = _load()
        return {"ok": True, "name": p.parent.parent.name, "version": getattr(m, "VERSION", "?"), "path": str(p),
                "playbooks": len(m.playbooks()), "lessons": len(m.lessons()), "can_brief": hasattr(m, "brief")}
    except (Exception, SystemExit) as e:      # rd.py reports its own errors with SystemExit
        return {"ok": False, "why": f"{type(e).__name__}: {e}"[:200]}


def understand(text):
    """{'text', 'changed', ...} — the message after fixing layout and dictation slips; the original on any failure."""
    try:
        m = _load()
        if m and hasattr(m, "understand") and text and len(text) < 4000:
            return m.understand(text)
    except (Exception, SystemExit):
        pass
    return {"text": text, "changed": False}


_scores = {}      # (rd.py mtime, message) -> its raw playbook scores: every message of a chat is scored once


def _msg_scores(m, text):
    k = (_mod["mtime"], text)
    v = _scores.get(k)
    if v is None:
        v = m._pb_scores(m.understand(text)["text"], m.playbooks())[0]
        if len(_scores) > 2000:
            _scores.clear()
        _scores[k] = v
    return v


def chat_topic(history):
    """The topic of ONE chat from its own earlier messages (oldest first), with the same fading sum rd.py keeps.
    {} for a chat's first message; None when the installed brain is too old to take a topic."""
    m = _load()
    if not m or not all(hasattr(m, f) for f in ("topic_update", "_pb_scores", "understand", "playbooks")):
        return None
    t = {}
    for h in [h for h in (history or []) if isinstance(h, str) and h.strip() and len(h) <= 4000][-6:]:
        t = m.topic_update(t, _msg_scores(m, h))
    return t


def note(text, history=None):
    """The block put in front of the model for this message, or '' when there is nothing useful to say.
    history = this chat's earlier messages from the owner (oldest first). With it, «كمل» / «فين الملف» are read in the light
    of THIS chat only; without it rd.py falls back to the last message seen anywhere on the machine (another chat's topic)."""
    try:
        m = _load()
        if not m or not hasattr(m, "brief") or not text or not text.strip() or len(text) > 4000:
            return ""
        hist = list(history or [])
        if hist and hist[-1] == text:       # a queued message already in the log is not its own context
            hist.pop()
        prev = chat_topic(hist) if history is not None else None
        b = m.brief(text, prev=prev) if prev is not None else m.brief(text)
        if not b.get("brief"):
            return ""
        root = _mod["path"].parent.parent
        return ("[عقل التنين الأحمر — ملخص اتحسب على الجهاز قبل ما الرسالة توصلك. ده اقتراح مش أمر: لو الطلب واضح إنه حاجة تانية امشي ورا الطلب.\n"
                + b["brief"] + f"\nالتفاصيل: python -X utf8 \"{root / 'scripts' / _mod['path'].name}\" plan \"<الطلب>\" · بعد أي تصحيح من المستخدم: … learn \"<الدرس>\" --domain D]")
    except (Exception, SystemExit):     # a SystemExit from rd.py must never stop the owner's message from being sent
        return ""


def library(q="", limit=40):
    """Rows of the bundled skill library: the best matches for q, or the most famous ones when q is empty."""
    try:
        m = _load()
        if not m or not hasattr(m, "library"):
            return {"ok": False, "why": "مكتبة المهارات محتاجة التنين الأحمر 2.1 أو أحدث", "rows": [], "total": 0}
        rows = m.lib_find(q, limit) if (q or "").strip() else m.library()[:limit]
        have = {x.name for x in SKILLS.iterdir() if x.is_dir()} if SKILLS.is_dir() else set()
        out = [{"name": r["name"], "title": r.get("title", r["name"]), "description": r["description"][:400], "repo": r["repo"], "stars": r["stars"], "license": r["license"],
                "review": r.get("review", []), "path": str(m.LIBRARY / r["name"] / "SKILL.md"), "installed": r["name"] in have} for r in rows]
        return {"ok": True, "rows": out, "total": len(m.library())}
    except Exception as e:
        return {"ok": False, "why": f"{type(e).__name__}: {e}"[:200], "rows": [], "total": 0}


def repos(q="", limit=500):
    """Rows of the top-500 GitHub repository index: best matches for q, or the most starred when q is empty."""
    try:
        m = _load()
        if not m or not hasattr(m, "repos_top"):
            return {"ok": False, "why": "فهرس المستودعات محتاج نسخة أحدث من التنين الأحمر", "rows": [], "total": 0}
        rows = m.repos_find(q, limit) if (q or "").strip() else m.repos_top()[:limit]
        out = [{"rank": r["rank"], "repo": r["repo"], "stars": r["stars"], "category": r.get("category", ""), "what": (r.get("what") or "")[:300], "use_when": (r.get("use_when") or "")[:200],
                "windows": str(r.get("windows_ok", "")), "license": r.get("license") or "", "install": (r.get("install_windows") or "")[:160], "url": r.get("url", "")} for r in rows]
        return {"ok": True, "rows": out, "total": len(m.repos_top())}
    except Exception as e:
        return {"ok": False, "why": f"{type(e).__name__}: {e}"[:200], "rows": [], "total": 0}


def library_install(name):
    """Copy one library skill into ~/.claude/skills. Called only from the user's own click in the app."""
    try:
        m = _load()
        dst = m.lib_install(str(name), yes=True)
        return {"ok": True, "path": str(dst)}
    except SystemExit as e:
        return {"ok": False, "why": str(e)[:200]}
    except Exception as e:
        return {"ok": False, "why": f"{type(e).__name__}: {e}"[:200]}


if __name__ == "__main__":
    import sys
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(status(), ensure_ascii=False, indent=1))
    for q in sys.argv[1:]:
        print("----", q, "\n", note(q))
