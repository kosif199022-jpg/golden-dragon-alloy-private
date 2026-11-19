"""«تغيير المسار وهو شغال»: golden_steer (urgent words, the open-stdin channel) and the patches in the generated app.

Offline: the channel is tested with a fake pipe, the Session methods by executing just those functions out of app.py.
"""
import ast
import io
import json
import threading
import time

import pytest

from conftest import APP, FORGE, read
from gbload import load

gs = load("golden_steer")


class Pipe(io.BytesIO):
    """stdin of a fake Claude Code: keeps what was written after close()."""

    def close(self):
        self.done = self.getvalue()
        super().close()

    def lines(self):
        raw = self.done if self.closed else self.getvalue()
        return [json.loads(x) for x in raw.decode("utf-8").splitlines()]


# ---------------------------------------------------------------- urgent words
@pytest.mark.parametrize("text", ["وقف", "وقّف الرندر ده", "استنى شوية", "لا لا مش ده", "غلط، الملف التاني", "  ⚠ وقف!", "STOP", "wait, wrong file",
                                  "إلغي اللي بتعمله", "مش كده خالص", "بلاش الموسيقى دي"])
def test_urgent_yes(text):
    assert gs.urgent(text)


@pytest.mark.parametrize("text", ["وكمان ضيف موسيقى", "ضيف زرار وقف في الآخر", "قفل الملف بعد ما تخلص", "وقفة حلوة في النص", "stopwatch on screen",
                                  "خلّي الخط أكبر", "", "ممكن تستنى الرندر يخلص وبعدين ترفعه"])
def test_urgent_no(text):
    assert not gs.urgent(text)


def test_wrap_and_lines():
    assert gs.wrap("x").startswith(gs.NOTE) and gs.wrap("x", True).startswith(gs.NOTE_NOW) and gs.wrap("x").endswith("x")
    assert gs.user_line("هاي")["message"]["content"] == [{"type": "text", "text": "هاي"}]
    assert gs.interrupt_line(3) == {"type": "control_request", "request_id": "gb-steer-3", "request": {"subtype": "interrupt"}}
    ev = {"type": "user", "message": {"content": [{"type": "tool_result", "content": "x"}, {"type": "text", "text": "رسالة"}]}}
    assert gs.echo_texts(ev) == ["رسالة"] and gs.echo_texts({"message": {"content": "نص"}}) == ["نص"] and gs.echo_texts({}) == []


# ---------------------------------------------------------------- the channel
def test_channel_message_read_inside_the_turn():
    p = Pipe()
    ch = gs.Channel(p)
    ch.first("الطلب")
    assert ch.send("غيّر اللون", payload=["blocks"])
    assert ch.ack("حاجة تانية") is None and ch.ack("الطلب") is None          # the prompt's own echo is not a receipt
    assert ch.ack("غيّر  اللون ") == ["blocks"] and ch.ack("غيّر اللون") is None
    assert ch.finish() is True and p.closed                                 # nothing unread: stdin closes, the process exits
    assert [x["type"] for x in p.lines()] == ["user", "user"]
    assert ch.send("بعد القفل") is False and ch.close() == []


def test_channel_unread_message_keeps_stdin_open_then_is_returned():
    p = Pipe()
    ch = gs.Channel(p, stall=30)
    ch.first("الطلب")
    ch.send("رسالة متأخرة", payload="P")
    assert ch.finish() is False and not p.closed                            # the next turn will read it
    ch.begin()
    assert ch._timer is None
    assert ch.close() == ["P"] and p.closed                                 # run died first: the app re-sends it


def test_channel_gives_up_when_no_turn_starts():
    p = Pipe()
    ch = gs.Channel(p, stall=0.05)
    ch.first("الطلب")
    ch.send("رسالة", payload="P")
    assert ch.finish() is False
    time.sleep(0.4)
    assert p.closed and ch.close() == ["P"]


def test_channel_interrupt():
    p = Pipe()
    ch = gs.Channel(p)
    ch.first("الطلب")
    assert ch.interrupt() is False                                          # nothing is waiting to take over
    assert ch.send("وقف", payload="P", now=True)
    kinds = [(x["type"], x.get("request", {}).get("subtype")) for x in p.lines()]
    assert kinds == [("user", None), ("control_request", "interrupt"), ("user", None)]
    assert ch.expected_stop("success") is False
    assert ch.expected_stop("error_during_execution") is True and ch.expected_stop("error_during_execution") is False
    assert ch.interrupt() is True and len(p.lines()) == 4                   # the button, while the message is still unread


def test_channel_broken_pipe_falls_back():
    class Dead(Pipe):
        def write(self, b):
            raise OSError("pipe closed")
    ch = gs.Channel(Dead())
    assert ch.send("x") is False and ch.open is False and ch.interrupt() is False


def test_channel_send_and_finish_do_not_lose_a_message():
    for _ in range(40):
        p = Pipe()
        ch = gs.Channel(p)
        ch.first("الطلب")
        got = []
        t = threading.Thread(target=lambda: got.append(ch.send("رسالة", payload="P")))
        t.start()
        closed = ch.finish()
        t.join()
        # written before the close -> stays unread and is returned; refused after it -> the app queues it itself
        assert (got == [True] and ch.close() == ["P"]) or (got == [False] and closed and ch.close() == [])


# ---------------------------------------------------------------- the generated app
def _session_methods(*names):
    src = read("app.py")
    cls = next(n for n in ast.parse(src).body if isinstance(n, ast.ClassDef) and n.name == "Session")
    fns = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert sorted(f.name for f in fns) == sorted(names)
    ns = {"golden_steer": gs, "threading": threading}
    exec(compile(ast.Module(body=fns, type_ignores=[]), "app.py", "exec"), ns)
    return ns


class FakeApi:
    def __init__(self):
        self.events = []

    def _emit(self, kind, **data):
        self.events.append(kind)


class FakeSession:
    def __init__(self, ns):
        self.api, self.id, self.busy = FakeApi(), "c1", True
        self.queue, self.qlock, self.steer, self.cc_chan = [], threading.Lock(), threading.Event(), None
        self.ran, self.killed, self.emitted = [], 0, []
        for k, f in ns.items():
            if callable(f) and k in ("steer_now", "run_calls", "drain_queue"):
                setattr(self, k, f.__get__(self))

    def emit(self, kind, **data):
        self.emitted.append(kind)

    def kill_procs(self):
        self.killed += 1

    def run_tool(self, c):
        self.ran.append(c.id)
        if c.id == "b":                       # the owner writes while the second call runs
            self.queue.append([{"type": "text", "text": "غيّر المسار"}])
        return {"type": "tool_result", "tool_use_id": c.id, "content": "ok"}


class Call:
    def __init__(self, i):
        self.id, self.name = i, "run_command"


def test_api_engine_skips_the_calls_that_did_not_start():
    s = FakeSession(_session_methods("run_calls", "steer_now", "drain_queue"))
    out = s.run_calls([Call("a"), Call("b"), Call("c"), Call("d")])
    assert s.ran == ["a", "b"]
    assert [r["tool_use_id"] for r in out] == ["a", "b", "c", "d"]            # every tool_use still gets its tool_result
    assert out[2]["is_error"] and out[2]["content"] == gs.SKIPPED and out[3]["content"] == gs.SKIPPED
    extra = s.drain_queue()
    assert extra[0]["text"] == gs.NOTE and extra[1]["text"] == "غيّر المسار" and not s.queue


def test_steer_now_api_engine_and_subscription_engine():
    s = FakeSession(_session_methods("run_calls", "steer_now", "drain_queue"))
    assert s.steer_now() is False and not s.steer.is_set()                   # nothing waiting: the button does nothing
    s.queue.append([{"type": "text", "text": "وقف"}])
    assert s.steer_now() is True and s.steer.is_set() and s.killed == 1 and s.api.events == ["steer"]
    s.drain_queue()
    assert not s.steer.is_set()                                              # handing the message over clears the flag
    p = Pipe()
    s.cc_chan = gs.Channel(p)
    s.cc_chan.first("الطلب")
    assert s.steer_now() is False
    s.cc_chan.send("وقف", payload="P")
    assert s.steer_now() is True and s.killed == 1                           # Claude Code is interrupted, not killed
    assert p.lines()[-1]["request"]["subtype"] == "interrupt"
    s.busy = False
    assert s.steer_now() is False


def test_app_is_patched():
    t = read("app.py")
    for need in ("import golden_steer", '"--input-format", "stream-json", "--replay-user-messages"', "golden_steer.Channel(p.stdin)",
                 "chan.finish()", "chan.expected_stop(", "results = self.run_calls(calls)", "def steer_now(self, sid):",
                 "## تغيير المسار وأنت شغال"):
        assert need in t, need
    cc = t[t.index("    def loop_cc(self):"):t.index("    def _finish(self):")]
    assert "p.stdin.close()" not in cc, "Claude Code's stdin must stay open while it works"
    assert cc.index("chan.close()") < cc.index("leftover = [] if self.stop.is_set() else self.drain_queue()")


def test_ui_and_build_are_patched():
    ui = read("ui/index.html")
    assert ui.count('onclick="gbNow(this)"') == 2 and "async function gbNow(btn)" in ui and "pywebview.api.steer_now(act)" in ui
    assert "e.kind==='steer'" in ui and ".gb-now{" in ui and "splice(0,e.n||99)" in ui
    assert "--hidden-import golden_steer" in read("build.ps1")


def test_forge_is_the_source_of_every_golden_module():
    mods = sorted(p.name for p in (FORGE / "modules").glob("golden_*.py"))
    assert "golden_steer.py" in mods and "golden_tools.py" in mods
    for name in mods:
        assert (FORGE / "modules" / name).read_bytes() == (APP / name).read_bytes(), name
        compile(read(name), name, "exec")
