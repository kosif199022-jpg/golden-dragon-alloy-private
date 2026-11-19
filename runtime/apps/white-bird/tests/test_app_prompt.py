"""The system prompt and the per-request notes assemble without exceptions and keep their key sections."""
import ast
import re

import pytest

from conftest import tree

SECTIONS = [
    "## بروتوكول الطائر الأبيض",            # added by the forge
    "## عقل التنين الأحمر",                  # explains the brain block brain.note() puts in front of each message
    "## أول رد على أي طلب شغل",
    "## اللي تحت إيدك",
    "## طريقة التحليل والهندسة العكسية",
    "## طريقة التفكير",
    "## تطوير نفسك",
    "## اشرح كل اللي بتعمله",
    "## قواعد الشغل",
    "## دروس من أخطاء المحادثات",
]


def test_system_prompt_sections(app):
    s = app.SYSTEM
    assert isinstance(s, str) and len(s) > 5000, "system prompt is empty or cut"
    assert s.startswith("أنت «الطائر الأبيض»"), s[:80]
    missing = [h for h in SECTIONS if h not in s]
    assert not missing, f"missing sections: {missing}"


def test_system_prompt_identity_and_paths(app):
    s = app.SYSTEM
    assert "«التنين الأحمر»" not in s, "the old identity is back in the system prompt"
    assert str(app.APP_SOURCE) in s, "self-development section doesn't point at this app's source"
    assert "الطائر الأبيض" in str(app.APP_SOURCE)
    leftovers = re.findall(r"\{[A-Z_]{3,}\}|\{Path\.home", s)
    assert not leftovers, f"unformatted placeholders: {leftovers}"


def test_subscription_prompt_file(app, tmp_path, monkeypatch):
    monkeypatch.setattr(app, "SETTINGS", tmp_path / "WhiteBird" / "settings.json")
    f = app.cc_system_file()
    assert f.parent == tmp_path / "WhiteBird"
    txt = f.read_text(encoding="utf-8")
    assert txt == app.CC_NOTE + "\n\n" + app.SYSTEM
    assert "## وضع الاشتراك" in txt and "%APPDATA%\\WhiteBird\\source_backups" in txt


def test_short_and_session_notes(app):
    assert app.SYSTEM_SHORT.strip()
    for name in ("DEEP_NOTE", "CLOUD_NOTE"):
        v = getattr(app.Session, name)
        assert isinstance(v, str) and len(v) > 40, name


def test_control_note_rewrite_anchors(app):
    """Subscription mode rewrites CONTROL_NOTE to the MCP tool names (app.py, Session.loop_cc). If an anchor disappears
    the rewrite silently does nothing and Claude Code is told to use tools it doesn't have."""
    for anchor in ("أداة computer", "أداة browser", "وأداة system"):
        assert anchor in app.CONTROL_NOTE, anchor


def _ext_note_format_kwargs():
    """Keyword names app.py passes to EXT_NOTE.format(...), read from the real call sites."""
    calls = [n for n in ast.walk(tree("app.py")) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "format" and getattr(n.func.value, "id", "") == "EXT_NOTE"]
    assert calls, "EXT_NOTE.format(...) call sites not found"
    return [(c.lineno, [k.arg for k in c.keywords]) for c in calls]


# Fixed 2026-11-13 (was KeyError('ultra') on the first ChatGPT/Gemini message): every .format() call must fill every placeholder.
def test_ext_note_formats(app):
    for line, kws in _ext_note_format_kwargs():
        try:
            out = app.EXT_NOTE.format(**{k: "X" for k in kws})
        except (KeyError, IndexError) as e:
            raise AssertionError(f"app.py:{line}: EXT_NOTE.format({', '.join(kws)}) raises {e!r}") from None
        assert "«الطائر الأبيض»" in out
