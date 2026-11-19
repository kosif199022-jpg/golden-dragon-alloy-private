"""golden_steer.py — «تغيير المسار»: a message the owner writes while the Golden Bird works reaches the model at once.

Before this module the subscription engine started `claude -p`, wrote the prompt and CLOSED stdin, so a message sent
while it worked waited until the whole run was over. Now stdin stays open (`--input-format stream-json`):

  * a normal message is written to the running Claude Code and is read at the very next step (the next tool boundary),
    inside the same turn — measured with Claude Code 2.1.325: sent at 9.0 s, read at 17.1 s when the running tool ended;
  * an urgent message («وقف»، «غلط»، «استنى»…) or the «⚡ قاطعه دلوقتي» button first sends an interrupt, which stops
    the running tool in under a second, then the message starts the next turn in the same session (context kept).

`--replay-user-messages` makes Claude Code print each user message back when it actually reads it; that echo is the
receipt (`Channel.ack`), so stdin is closed only when nothing is still unread, and an unread message is never lost:
`Channel.close()` hands it back and the app sends it in a resumed run.

No app import here: plain functions + one small class, tested in tests\\test_steer.py with a fake pipe.
"""
import json
import re
import threading

# Words that mean «you are on the wrong path, stop now» at the START of a message (Egyptian Arabic + English).
_URGENT = ("وقف", "وقّف", "اوقف", "أوقف", "قف", "استنى", "استني", "استنا", "اصبر", "بس بس", "لا لا", "لأ لأ", "لا مش", "لأ مش",
           "غلط", "ده غلط", "دا غلط", "مش كده", "مش كدا", "مش ده", "مش دا", "مش هو", "الغي", "إلغي", "الغى", "كنسل", "سيبك", "سيب ده",
           "بلاش", "ارجع", "إرجع", "stop", "wait", "wrong", "cancel", "no no", "abort", "hold on")
_DIAC = re.compile(r"[ً-ْٰـ]")
_LEAD = re.compile(r"^[\s\W_]+", re.UNICODE)


def norm(text):
    """Lower-case, no diacritics / tatweel, one form for alef / ya / ta marbuta, single spaces."""
    t = _DIAC.sub("", (text or "").lower())
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ى", "ي"), ("ة", "ه")):
        t = t.replace(a, b)
    return " ".join(t.split())


_URGENT_N = sorted({norm(w) for w in _URGENT}, key=len, reverse=True)


def urgent(text):
    """True when the message opens with a stop / wrong-path word: the running step is interrupted instead of waited for.
    Only the opening counts («وقف الرندر» yes, «ضيف زرار وقف» no), and the word must end there («قف» does not match «قفل»)."""
    t = _LEAD.sub("", norm(text))
    for w in _URGENT_N:
        if t.startswith(w) and (len(t) == len(w) or not t[len(w)].isalnum()):
            return True
    return False


NOTE = ("[رسالة جديدة من صاحب الشغل وصلت وأنت شغال. اقراها دلوقتي قبل أي خطوة تانية، وحدّد: إضافة، ولا تصحيح، ولا سؤال. "
        "لو تصحيح: سيب الطريق القديم، وقول في سطر واحد إيه اللي اتغيّر وإيه اللي هتسيبه زي ما هو، وكمّل على الجديد.]")
NOTE_NOW = ("[صاحب الشغل قاطعك دلوقتي: الخطوة اللي كانت شغالة اتوقفت في نصها. اللي جاي أهم من أي خطة قبله. "
            "اتأكد إن مفيش ملف ناقص أو نص مكتوب من الخطوة المقطوعة قبل ما تبني عليه، وبعدين نفّذ الرسالة دي.]")
SKIPPED = "ماتنفّذتش: صاحب الشغل بعت رسالة جديدة وأنت شغال. اقراها الأول، وبعدين قرر تعيد الأداة دي ولا لأ."


def wrap(text, now=False):
    return (NOTE_NOW if now else NOTE) + "\n\n" + (text or "")


def user_line(text):
    return {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": text}]}}


def interrupt_line(n):
    return {"type": "control_request", "request_id": f"gb-steer-{n}", "request": {"subtype": "interrupt"}}


def echo_texts(event):
    """The text blocks of a stream-json `user` event (a replayed user message); tool results are not included."""
    c = (event.get("message") or {}).get("content")
    if isinstance(c, str):
        return [c]
    return [b.get("text") or "" for b in (c or []) if isinstance(b, dict) and b.get("type") == "text"]


class Channel:
    """The open stdin of one running `claude -p --input-format stream-json --replay-user-messages` process.

    first(prompt)            the run's own prompt (not tracked)
    send(text, payload, now) a message written while it works; kept in `waiting` until Claude Code echoes it
    interrupt()              stop the running step now (only when a message is waiting to take over)
    ack(text)                the echo arrived: returns the payload of the message that was read, else None
    expected_stop(subtype)   True once per interrupt we sent: that «error_during_execution» result is ours, not an error
    finish()                 a turn ended: closes stdin when nothing is unread (the process then exits) -> True
    close()                  closes and returns the payloads that were never read (the app re-sends them)
    """

    STALL = 90      # seconds after a turn ended with a message still unread and no new turn starting -> close and re-send

    def __init__(self, pipe, stall=None):
        self.pipe, self.lock = pipe, threading.RLock()
        self.open, self.waiting, self.interrupts, self.sent = True, [], 0, 0
        self.stall = self.STALL if stall is None else stall
        self._timer = None

    def _write(self, obj):
        self.pipe.write((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))
        self.pipe.flush()

    def first(self, prompt):
        with self.lock:
            self._write(user_line(prompt))

    def send(self, text, payload=None, now=False):
        with self.lock:
            if not self.open:
                return False
            try:
                if now:
                    self._interrupt()
                self._write(user_line(text))
            except (OSError, ValueError):
                self.open = False
                return False
            self.waiting.append((norm(text), payload if payload is not None else text))
            return True

    def _interrupt(self):
        self.sent += 1
        self._write(interrupt_line(self.sent))
        self.interrupts += 1

    def interrupt(self):
        with self.lock:
            if not self.open or not self.waiting:
                return False
            try:
                self._interrupt()
            except (OSError, ValueError):
                self.open = False
                return False
            return True

    def begin(self):
        """A turn started (Claude Code printed `init` or `message_start`): the wait after the last turn is over."""
        with self.lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None

    def ack(self, text):
        key = norm(text)
        with self.lock:
            for i, (k, payload) in enumerate(self.waiting):
                if k == key:
                    del self.waiting[i]
                    return payload
        return None

    def expected_stop(self, subtype):
        with self.lock:
            if self.interrupts and subtype == "error_during_execution":
                self.interrupts -= 1
                return True
        return False

    def finish(self):
        with self.lock:
            if not self.open:
                return True
            if not self.waiting:
                self._shut()
                return True
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self.stall, self._stalled)
            self._timer.daemon = True
            self._timer.start()
            return False

    def _stalled(self):
        with self.lock:      # no new turn began (begin() cancels this timer): give up waiting, close() returns the unread
            if self.open and self.waiting:
                self._shut()

    def _shut(self):
        self.open = False
        try:
            self.pipe.close()
        except (OSError, ValueError):
            pass

    def close(self):
        with self.lock:
            if self._timer:
                self._timer.cancel()
            self._shut()
            left, self.waiting = [p for _, p in self.waiting], []
            return left
