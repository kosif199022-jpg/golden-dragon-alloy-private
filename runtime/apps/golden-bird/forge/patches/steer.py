"""patches/steer.py — «تغيير المسار وهو شغال» (2026-11-14), applied by make_golden_bird.py after the gold layer.

What changes in the generated app (the logic itself lives in modules/golden_steer.py):
  subscription engine  Claude Code runs with stdin open (--input-format stream-json --replay-user-messages). A message
                       written while it works is read at the next step of the SAME turn; «⚡ قاطعه دلوقتي» / an urgent
                       message interrupts the running step first. Unread messages are re-sent in a resumed run.
  API engine           a queued message makes the rest of the turn's tool calls wait (the model reads it first);
                       «⚡» also drops a half-written reply and stops the running command.
  Codex / Gemini       «⚡» stops the CLI and the message starts the next run at once (they have no open stdin).
  UI                   the queued badge gets the «⚡ قاطعه دلوقتي» button; each message is ticked when it is really read.
  prompt               «تغيير المسار» rules + a self-check that catches a wrong path early.
Every anchor is counted by the caller's sub(): a changed upstream stops the forge instead of half-patching.
"""

PROMPT = """
## تغيير المسار وأنت شغال (جديد)
- **رسالة وصلت في نص الشغل:** اقراها قبل أي أداة تانية، وصنّفها:
  - **إضافة:** كمّل شغلك وضيفها للخطة.
  - **تصحيح:** وقّف الطريق الحالي، واكتب سطر واحد: «اتغيّر كذا، وهسيب كذا زي ما هو»، وكمّل على الجديد. ماترجعش للخطة القديمة.
  - **سؤال:** جاوب في سطرين وكمّل اللي كنت فيه.
- **لو اتقاطعت (⚡):** الخطوة اللي كانت شغالة وقفت في نصها. افحص ناتجها (ملف ناقص، رندر مقطوع) قبل ما تبني عليه، وامسح الناقص.
- **راجع اتجاهك لوحدك:** كل 5 أو 6 خطوات، وبعد أي فشلين ورا بعض، اسأل نفسك: «أنا لسه ماشي ناحية Done-when؟».
  - نفس الخطأ اتكرر مرتين: غيّر الطريقة، وماتعيدش نفس الأمر مرة تالتة.
  - لقيت نفسك بتعمل حاجة صاحب الشغل ماطلبهاش: ارجع للطلب الأصلي.
- **قول اتجاهك بدري:** في أول الشغل الطويل اكتب خطتك في 3 سطور قبل أول أداة تقيلة، علشان صاحب الشغل يلحق يصحّحك قبل ما الوقت يتصرف.
"""

SESSION_FIELDS = '''        self.steer = threading.Event()   # «⚡ قاطعه دلوقتي»: the queued message takes over now (cleared by drain_queue)
        self.cc_chan = None              # golden_steer.Channel: the open stdin of the running Claude Code (subscription)
'''

QUEUE_OLD = '''        self.emit("user", text=text, atts=[Path(p).name for p in self.attach], queued=True)
        self.attach = []
        with self.qlock:
            self.queue.append(blocks)
'''
QUEUE_NEW = '''        self.emit("user", text=text, atts=[Path(p).name for p in self.attach], queued=True)
        self.attach = []
        now = golden_steer.urgent(text)      # «وقف»، «غلط»، «استنى»… at the start: do not wait for the running step
        chan = self.cc_chan
        if chan and chan.send(golden_steer.wrap(self._text_of(blocks), now), payload=blocks, now=now):
            if now:
                self.api._emit("steer", sid=self.id)
            return                           # Claude Code reads it at its next step; the echo ticks the badge
        with self.qlock:
            self.queue.append(blocks)
        if now:
            self.steer_now()

    def steer_now(self):
        """«⚡ قاطعه دلوقتي»: stop the running step so the message that is waiting is read now, not at the next step."""
        if not self.busy:
            return False
        chan = self.cc_chan
        if chan:
            ok = chan.interrupt()
        else:
            with self.qlock:
                ok = bool(self.queue)
            if ok:
                self.steer.set()
                self.kill_procs()
        if ok:
            self.api._emit("steer", sid=self.id)
        return ok

    def run_calls(self, calls):
        """This turn's tool calls, in order. Once the owner has written (or pressed «⚡»), the calls that did not start
        yet are answered with «read the new message first», so the model sees the message before it does more work."""
        out = []
        for c in calls:
            with self.qlock:
                waiting = bool(self.queue)
            if waiting or self.steer.is_set():
                self.emit("tool", id=c.id, name=c.name, args={})
                self.emit("tool_result", id=c.id, error=True, text=golden_steer.SKIPPED)
                out.append({"type": "tool_result", "tool_use_id": c.id, "content": golden_steer.SKIPPED, "is_error": True})
            else:
                out.append(self.run_tool(c))
        return out
'''

DRAIN_OLD = '''        with self.qlock:
            q, self.queue = self.queue, []
        if not q:
            return []
'''
DRAIN_NEW = '''        self.steer.clear()
        with self.qlock:
            q, self.queue = self.queue, []
        if not q:
            return []
'''

STREAM_OLD = '''                            if self.stop.is_set():
                                break
                            if ev.type == "text":'''
STREAM_NEW = '''                            if self.stop.is_set() or self.steer.is_set():
                                break
                            if ev.type == "text":'''

PARTIAL_OLD = '''                            break  # partial turn dropped; history still ends on a user turn
                        msg = stream.get_final_message()'''
PARTIAL_NEW = '''                            break  # partial turn dropped; history still ends on a user turn
                        if self.steer.is_set():      # «⚡»: drop the half-written reply and hand the new message over now
                            extra = self.drain_queue()
                            if extra:
                                last = self.messages[-1]
                                c = last["content"]
                                last["content"] = (list(c) if isinstance(c, list) else [{"type": "text", "text": str(c)}]) + extra
                            self.emit("turn_continue")
                            continue
                        msg = stream.get_final_message()'''

CC_STDIN_OLD = '''            p.stdin.write(prompt.encode("utf-8"))
            p.stdin.close()
'''
CC_STDIN_NEW = '''            chan = golden_steer.Channel(p.stdin)     # stdin stays open: messages written while it works go straight in
            chan.first(prompt)
            self.cc_chan = chan
'''

CC_INIT_OLD = '''                if t == "system" and e.get("subtype") == "init":
'''
CC_INIT_NEW = '''                if t == "system" and e.get("subtype") == "init":
                    chan.begin()
'''

CC_USER_OLD = '''                elif t == "user":
                    for b in (e.get("message", {}).get("content") or []):
'''
CC_USER_NEW = '''                elif t == "user":
                    for txt in ([] if sub_agent else golden_steer.echo_texts(e)):
                        got = chan.ack(txt)          # Claude Code printed our message back = it has just read it
                        if got is not None:
                            self.messages.append({"role": "user", "content": got})
                            self.cc_sent = len(self.messages)
                            self.emit("queued_in", n=1)
                    for b in (e.get("message", {}).get("content") or []):
'''

CC_RESULT_OLD = '''                    if e.get("result") is not None:
                        self.messages.append({"role": "assistant", "content": [{"type": "text", "text": e.get("result") or ""}]})
            p.wait(timeout=30)
'''
CC_RESULT_NEW = '''                    if e.get("result"):
                        self.messages.append({"role": "assistant", "content": [{"type": "text", "text": e["result"]}]})
                    chan.finish()                    # closes stdin when no message is unread; else the next turn reads it
            p.wait(timeout=30)
'''

CC_FINALLY_OLD = '''            self.kill_procs()
            leftover = [] if self.stop.is_set() else self.drain_queue()
            if leftover:
                self.messages.append({"role": "user", "content": leftover})
'''
CC_FINALLY_NEW = '''            chan, self.cc_chan = self.cc_chan, None
            if chan:
                unread = chan.close()                # written but never read (the run ended first): send them again
                if unread and not self.stop.is_set():
                    with self.qlock:
                        self.queue[:0] = unread
            self.kill_procs()
            leftover = [] if self.stop.is_set() else self.drain_queue()
            if leftover:
                self.messages.append({"role": "user", "content": leftover})
'''

API_OLD = '''    def stop(self, sid):
        s = self._sessions.get(sid)
'''
API_NEW = '''    def steer_now(self, sid):
        """«⚡ قاطعه دلوقتي» button under a message that was sent while the chat works."""
        s = self._sessions.get(sid)
        return {"ok": bool(s and s.steer_now())}

    def stop(self, sid):
        s = self._sessions.get(sid)
'''


def patch_app(t, sub):
    t = sub(t, "import brain\n", "import brain\nimport golden_steer\n", 1, "steer: import")
    t = sub(t, "        self.qlock = threading.Lock()\n", "        self.qlock = threading.Lock()\n" + SESSION_FIELDS, 1, "steer: session fields")
    t = sub(t, QUEUE_OLD, QUEUE_NEW, 1, "steer: queue_message + steer_now + run_calls")
    t = sub(t, DRAIN_OLD, DRAIN_NEW, 1, "steer: drain clears the flag")
    t = sub(t, '"[رسالة جديدة من المستخدم وأنت شغال، خدها في اعتبارك من دلوقتي:]"', "golden_steer.NOTE", 1, "steer: note text")
    # API engine
    t = sub(t, STREAM_OLD, STREAM_NEW, 1, "steer: api stream stops on ⚡")
    t = sub(t, PARTIAL_OLD, PARTIAL_NEW, 1, "steer: api half-written reply")
    t = sub(t, "                results = [self.run_tool(c) for c in calls]\n", "                results = self.run_calls(calls)\n", 1,
            "steer: api tool calls wait for the message")
    # subscription engine (Claude Code)
    t = sub(t, 'cmd = [exe, "-p", "--output-format", "stream-json", "--verbose", "--include-partial-messages",',
            'cmd = [exe, "-p", "--input-format", "stream-json", "--replay-user-messages",\n'
            '                   "--output-format", "stream-json", "--verbose", "--include-partial-messages",', 1, "steer: cc open stdin flags")
    t = sub(t, CC_STDIN_OLD, CC_STDIN_NEW, 1, "steer: cc channel")
    t = sub(t, CC_INIT_OLD, CC_INIT_NEW, 1, "steer: cc turn began (init)")
    t = sub(t, '                        self.emit("turn_start"); started = True\n',
            '                        self.emit("turn_start"); started = True; chan.begin()\n', 1, "steer: cc turn began (message)")
    t = sub(t, CC_USER_OLD, CC_USER_NEW, 1, "steer: cc receipt")
    t = sub(t, '                    if e.get("is_error"):\n', '                    if e.get("is_error") and not chan.expected_stop(e.get("subtype")):\n', 1,
            "steer: cc interrupt is not an error")
    t = sub(t, CC_RESULT_OLD, CC_RESULT_NEW, 1, "steer: cc end of turn")
    t = sub(t, CC_FINALLY_OLD, CC_FINALLY_NEW, 1, "steer: cc unread messages are re-sent")
    # Codex / Gemini: a CLI killed by ⚡ is not an error either
    t = sub(t, "if p.returncode not in (0, None) and not self.stop.is_set():",
            "if p.returncode not in (0, None) and not self.stop.is_set() and not self.steer.is_set():", 2, "steer: killed CLI is not an error")
    t = sub(t, API_OLD, API_NEW, 1, "steer: Api.steer_now")
    t = sub(t, "\n## عقل التنين الأحمر", PROMPT + "\n## عقل التنين الأحمر", 1, "steer: prompt rules")
    return t


UI_BADGE = '<div class="badge run">📨 هيوصله وهو شغال…</div>'
UI_BADGE_NEW = ('<div class="badge run">📨 هيقراها عند أول خطوة…</div>'
                '<button class="gb-now" onclick="gbNow(this)" title="يوقّف الخطوة اللي شغالة ويقرا رسالتك دلوقتي">⚡ قاطعه دلوقتي</button>')
UI_ACK_OLD = "if(e.kind==='queued_in'){(s.qbadges||[]).splice(0).forEach(b=>{b.className='badge ok';b.textContent='✓ وصلته وهو شغال'}); return}"
UI_ACK_NEW = ("if(e.kind==='queued_in'){(s.qbadges||[]).splice(0,e.n||99).forEach(b=>{b.className='badge ok';b.textContent='✓ قراها وهو شغال';"
              "b.parentNode?.querySelector('.gb-now')?.remove()}); return}\n"
              "  if(e.kind==='steer'){s.el.querySelectorAll('.gb-now').forEach(b=>b.remove()); if(s.busy) setState(s,'run','⚡ بيغيّر المسار…'); return}")
UI_FN = ("async function gbNow(btn){   // «⚡ قاطعه دلوقتي»: stop the running step, the waiting message is read now\n"
         "  btn.disabled=true; btn.textContent='⚡ بيقاطعه…';\n"
         "  try{const r=await pywebview.api.steer_now(act); if(!r||!r.ok) btn.remove()}catch(_){btn.remove()}}\n"
         "async function send(q){")
UI_CSS = """
/* «تغيير المسار»: the interrupt button under a message sent while the chat works */
.gb-now{margin:6px 6px 0 0;padding:3px 11px;border-radius:999px;font:inherit;font-size:12px;cursor:pointer;
  background:var(--accent-soft);color:var(--accent);border:.5px solid var(--ring)}
.gb-now:hover{background:var(--accent);color:var(--on-accent)}
.gb-now:disabled{opacity:.6;cursor:default}
"""


def patch_ui(t, sub):
    t = sub(t, UI_BADGE, UI_BADGE_NEW, 2, "steer: ⚡ button on queued messages")
    t = sub(t, UI_ACK_OLD, UI_ACK_NEW, 1, "steer: per-message receipt + steer event")
    t = sub(t, "async function send(q){", UI_FN, 1, "steer: gbNow()")
    t = sub(t, "</style>", UI_CSS + "</style>", 1, "steer: button style")
    return t


def patch_build(t, sub):
    return sub(t, "--hidden-import golden_tools `", "--hidden-import golden_tools --hidden-import golden_steer `", 1, "steer: bundle golden_steer")
