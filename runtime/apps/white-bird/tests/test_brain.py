"""brain.py asks the Red Dragon skill (~/.claude/skills/red-dragon/scripts/rd.py) for a brief before each message.
Contract: best effort, note() returns "" on any failure and never raises. Every test points brain.SKILLS at a temp folder,
so the real installed skill is never loaded."""
import textwrap

import pytest

import brain

STUB = '''
CALLS = []

def playbooks():
    return ["montage", "design"]

def understand(text):
    CALLS.append(("understand", text))
    return {"text": text.strip(), "changed": False}

def _pb_scores(q, pbs):
    CALLS.append(("_pb_scores", q, tuple(pbs)))
    return ({"montage": float(len(q))}, None)

def topic_update(topic, s):
    CALLS.append(("topic_update", dict(topic), dict(s)))
    return {k: topic.get(k, 0) * 0.5 + v for k, v in s.items()}

def brief(text, limit=1400, prev=None):
    CALLS.append(("brief", text, prev))
    return {"brief": "STUB BRIEF for " + text}
'''


@pytest.fixture
def skills(monkeypatch, tmp_path):
    monkeypatch.setattr(brain, "_mod", {"path": None, "mtime": 0, "m": None})
    monkeypatch.setattr(brain, "_scores", {})
    root = tmp_path / "skills"
    root.mkdir()
    monkeypatch.setattr(brain, "SKILLS", root)
    return root


def install(root, body, name="red-dragon", script="rd.py"):
    p = root / name / "scripts" / script
    p.parent.mkdir(parents=True)
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


def test_missing_module(skills):
    assert brain.brain_path() is None
    assert brain.note("اعمل مونتاج") == ""
    assert brain.note("اعمل مونتاج", history=["قبلها"]) == ""
    assert brain.understand("x") == {"text": "x", "changed": False}
    assert brain.status()["ok"] is False


@pytest.mark.parametrize("body", [
    "def brief(:\n",                                            # syntax error
    "raise RuntimeError('broken at import')\n",                 # crashes on import
    "import module_that_does_not_exist_wb\n",                   # missing dependency
    "def brief(text, prev=None):\n    raise ValueError('x')\n",  # brief() crashes
    "def brief(text, prev=None):\n    return None\n",           # wrong return type
    "def brief(text, prev=None):\n    return {'brief': ''}\n",  # nothing to say
    "VERSION = 1\n",                                            # no brief() at all
], ids=["syntax", "import-error", "missing-dep", "brief-raises", "brief-none", "brief-empty", "no-brief"])
def test_broken_module_returns_empty(skills, body):
    install(skills, body)
    assert brain.note("اعمل مونتاج") == ""
    assert brain.note("اعمل مونتاج", history=["a", "b"]) == ""


def test_bad_input_returns_empty(skills):
    install(skills, STUB)
    assert brain.note("") == ""
    assert brain.note("   ") == ""
    assert brain.note(None) == ""
    assert brain.note("x" * 4001) == ""


def test_stub_module_without_history(skills):
    p = install(skills, STUB)
    out = brain.note("اعمل ريل")
    assert out.startswith("[عقل التنين الأحمر")
    assert "STUB BRIEF for اعمل ريل" in out
    assert str(p) in out and out.endswith("]")
    calls = brain._mod["m"].CALLS
    assert ("brief", "اعمل ريل", None) in calls            # no history: rd.py's own fallback (prev not passed)


def test_stub_module_with_history_uses_this_chats_topic(skills):
    install(skills, STUB)
    out = brain.note("كمل", history=["اعمل مونتاج", "  ", 123, "كمل"])   # junk entries and the message itself are dropped
    assert "STUB BRIEF for كمل" in out
    calls = brain._mod["m"].CALLS
    briefs = [c for c in calls if c[0] == "brief"]
    assert briefs == [("brief", "كمل", {"montage": float(len("اعمل مونتاج"))})], briefs
    assert ("_pb_scores", "اعمل مونتاج", ("montage", "design")) in calls
    assert not [c for c in calls if c[0] == "_pb_scores" and c[1] == "كمل"], "the message itself was used as its own context"


def test_first_message_of_a_chat_gets_empty_topic(skills):
    install(skills, STUB)
    brain.note("اعمل مونتاج", history=[])
    assert [c for c in brain._mod["m"].CALLS if c[0] == "brief"] == [("brief", "اعمل مونتاج", {})]


def test_old_brain_without_topic_support(skills):
    install(skills, STUB.replace("def topic_update", "def _old_topic_update"))
    out = brain.note("كمل", history=["اعمل مونتاج"])
    assert "STUB BRIEF for كمل" in out
    assert [c for c in brain._mod["m"].CALLS if c[0] == "brief"] == [("brief", "كمل", None)]


def test_white_dragon_fallback(skills):
    install(skills, STUB, name="white-dragon", script="wd.py")
    assert "STUB BRIEF" in brain.note("ابدأ")


# Fixed 2026-11-13: a SystemExit from rd.py (its way of reporting errors) used to escape note() and drop the message.
def test_note_survives_system_exit(skills):
    install(skills, "def brief(text, prev=None):\n    raise SystemExit('rd.py error')\n")
    assert brain.note("اعمل مونتاج") == ""
