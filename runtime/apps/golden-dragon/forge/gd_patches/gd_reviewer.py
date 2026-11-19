# -*- coding: utf-8 -*-
"""التنين الذهبي — 🧐 مراجع التفكير (2026-11-16)

الفكرة: التنين بيكتب هو بيفكّر في إيه (ملخص التفكير + سطور «💭»)، ووكيل تاني مستقل بيقرا التفكير ده وهو شغال.
لو لقى غلط أو طريقة أحسن، بيبعت تصحيح للتنين ياخده في الخطوة الجاية، وبيظهر كارت في الشات.

- بيشتغل لما جزء من التفكير يخلص (قبل أول أداة أو أول كلام بعده).
- حدود: مراجعة كل 45 ث بالكتير، و6 في الدور الواحد، وأي جزء أقل من 400 حرف مايتراجعش.
- الموديل: settings «reviewer_model» (افتراضي Sonnet 5.5). المفتاح: settings «reviewer» (افتراضي شغّال).
- المحرك: لو التطبيق شغّال بمفتاح API يستخدمه، غير كده Claude Code باشتراكك (من غير أدوات، ومن غير ما يحفظ جلسة).
"""

# ---------------------------------------------------------------- app.py
PROMPT_ANCHOR = "## عقل التنين الذهبي (تفكير فائق بالعربي والإنجليزي)"
PROMPT_SECTION = (
    "## 💭 التفكير المكتوب و🧐 المراجع\n"
    "- **اكتب تفكيرك:** قبل كل خطوة مهمة اكتب سطر «💭» قصير: فهمت إيه، هتعمل إيه وليه، وإيه اللي اتقاس. "
    "تفكيرك بيتعرض لصاحب الشغل وبيراجعه وكيل تاني، فخليه واضح ومحدد (أرقام، أسماء ملفات، الفرضية والبديل).\n"
    "- **رسالة تبدأ بـ «[🧐 مراجع التفكير»:** ده وكيل تاني قرا تفكيرك. قيّمها بالدليل مش بالمجاملة: "
    "لو صح، قول في سطر «💭 المراجع عنده حق: …» وغيّر اتجاهك. ولو غلط، قول في سطر ليه بالدليل وكمّل. ماتتجاهلهاش.\n\n"
)

APP_ANCHOR_API = "    def delete_saved(self, cid):\n"
APP_API = r'''    # ===== 🧐 مراجع التفكير: مفتاح التشغيل =====
    def reviewer_status(self):
        return {"on": bool(settings_get("reviewer", True)), "model": settings_get("reviewer_model", "claude-sonnet-5-5")}

    def set_reviewer(self, on):
        settings_set("reviewer", bool(on))
        return self.reviewer_status()

'''

MAIN_ANCHOR = '\nif __name__ == "__main__":'
APP_MODULE = r'''

# ===================== التنين الذهبي: 🧐 مراجع التفكير =====================
RV_MIN_CHARS, RV_GAP_SECS, RV_MAX_PER_TURN = 400, 45, 6
# A model's safety filter sometimes stops a normal review by mistake: then ask one other model, once.
RV_FALLBACK = {"claude-sonnet-5-5": "claude-opus-5-5", "claude-opus-5-5": "claude-sonnet-5-5", "claude-haiku-5-5": "claude-sonnet-5-5"}


def _rv_flagged(e):
    t = str(e).lower()
    return any(k in t for k in ("safeguards", "usage policy", "/aup", "flagged this message"))
RV_SYSTEM = (
    "You are the independent REVIEWER of another AI agent (the Golden Dragon). You read its written reasoning while it works, "
    "before it acts. Your job: catch real mistakes early and point out a clearly better approach.\n"
    "Flag ONLY concrete, checkable problems: a misread of the user's request, a wrong fact/number/path/command flag, a missing step "
    "that will make the delivery fail, an unsafe or irreversible action without the user's approval, a plan that ignores a "
    "constraint, or a much cheaper/more reliable way to reach the same result. Do NOT nitpick style, do NOT repeat its plan back, "
    "do NOT invent problems. If the reasoning is fine, say so.\n"
    "Answer with ONE JSON object and nothing else:\n"
    '{"verdict": "ok" | "fix" | "better", "issues": ["<short, specific>", ...], "suggestion": "<the corrected or better step, or empty>", '
    '"confidence": 0.0-1.0}\n'
    "verdict=fix: something is wrong and must change. verdict=better: it works but a clearly better way exists. "
    "Write issues and suggestion in Egyptian Arabic; keep code, paths and flags in English. At most 3 issues, 25 words each."
)


def _rv_user_request(s):
    """The user's own words only. The app glues «[...]» context blocks before them (computer control, the 547-skill index,
    tools, team, work folder: ~80k chars). The old code sent the FIRST 3000 chars of that = the computer-control block only:
    the reviewer never saw the request, and the model's safety filter stopped it («safeguards flagged this message»)."""
    raw = (getattr(s, "last_sent", None) or ("",))[0]
    if raw and raw.strip():
        return raw.strip()[-3000:]
    for m in reversed(s.messages or []):
        if m.get("role") != "user":
            continue
        c = m.get("content")
        parts = [c] if isinstance(c, str) else [b.get("text", "") for b in (c or []) if isinstance(b, dict) and b.get("type") == "text"]
        parts = [p for p in parts if p and p.strip() and not p.lstrip().startswith("[🧐")]
        if not parts:
            continue
        own = [p for p in parts if not p.lstrip().startswith("[")]
        txt = "\n".join(own or parts).strip()
        tail = txt.rsplit("]\n", 1)[-1].strip() if txt.startswith("[") else txt   # after the last context block
        return (tail or txt)[-3000:]
    return ""


def _rv_parse(txt):
    txt = txt or ""
    a, b = txt.find("{"), txt.rfind("}")
    if a < 0 or b <= a:
        return None
    try:
        j = json.loads(txt[a:b + 1])
    except Exception:
        return None
    v = str(j.get("verdict", "ok")).lower()
    if v not in ("ok", "fix", "better"):
        v = "ok"
    issues = [str(x)[:300] for x in (j.get("issues") or []) if str(x).strip()][:3]
    try:
        conf = float(j.get("confidence", 0.7))
    except Exception:
        conf = 0.7
    return {"verdict": v, "issues": issues, "suggestion": str(j.get("suggestion") or "")[:800], "confidence": round(conf, 2)}


def _rv_ask(s, model, prompt):
    """One text-only answer from the reviewer model: the API key when the app runs on the API, else Claude Code (no tools)."""
    if s.api._settings.get("engine", "api") == "api" and s.api._key():
        client = anthropic.Anthropic(api_key=s.api._key(), max_retries=2)
        msg = client.messages.create(model=model, max_tokens=1500, system=RV_SYSTEM, messages=[{"role": "user", "content": prompt}])
        try:
            s.api._charge(s, msg)
        except Exception:
            pass
        return "".join(getattr(b, "text", "") for b in msg.content)
    exe = claude_exe()
    if not exe:
        raise RuntimeError("Claude Code مش متثبت")
    cmd = [exe, "-p", "--model", model, "--output-format", "json", "--tools", "", "--no-session-persistence",
           "--strict-mcp-config", "--system-prompt", RV_SYSTEM]
    r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
                       env=child_env(), cwd=str(Path.home()), creationflags=0x08000000 if os.name == "nt" else 0)
    try:
        j = json.loads(r.stdout)
        if j.get("is_error"):
            raise RuntimeError(str(j.get("result") or "error")[:200])
        return j.get("result") or ""
    except json.JSONDecodeError:
        raise RuntimeError((r.stderr or r.stdout or "no output").strip()[:200])


def _rv_deliver(s, res):
    """Send the reviewer's correction to the running agent; it reads it at its next step."""
    lines = ["[🧐 مراجع التفكير — وكيل تاني مستقل قرا تفكيرك وشايف:]"]
    lines += [f"- {x}" for x in res["issues"]]
    if res["suggestion"]:
        lines.append(("الأصح: " if res["verdict"] == "fix" else "طريقة أحسن: ") + res["suggestion"])
    lines.append("قيّمها بالدليل: لو عنده حق غيّر اتجاهك، ولو غلطان قول ليه في سطر وكمّل.")
    text = "\n".join(lines)
    blocks = [{"type": "text", "text": text}]
    if not s.busy:
        return False
    chan = getattr(s, "cc_chan", None)
    if chan is not None:
        try:
            if chan.send(golden_steer.wrap(text, False), payload=blocks, now=False):
                return True
        except Exception:
            pass
    with s.qlock:
        s.queue.append(blocks)
    return True


def _rv_run(s, rid, model, seg, acts):
    t0 = time.time()
    try:
        req = _rv_user_request(s)
        prompt = ("[USER REQUEST]\n" + (req or "(unknown)") + "\n\n[WORKING FOLDER]\n" + (s.workdir or "-") +
                  ("\n\n[ACTIONS SO FAR THIS TURN]\n" + "\n".join(acts) if acts else "") +
                  "\n\n[AGENT'S REASONING TO REVIEW]\n" + seg)
        try:
            raw = _rv_ask(s, model, prompt)
        except Exception as e1:
            if not _rv_flagged(e1):
                raise
            alt = RV_FALLBACK.get(model, "claude-opus-5-5")
            try:
                raw, model = _rv_ask(s, alt, prompt), alt
            except Exception as e2:
                if not _rv_flagged(e2):
                    raise
                s.emit("review", id=rid, model=alt, ok=False, skipped=True, secs=round(time.time() - t0),
                       error="فلتر الأمان عند الموديلين وقّف المراجعة دي بالغلط")
                return
        res = _rv_parse(raw)
        if res is None:
            s.emit("review", id=rid, model=model, ok=False, error="المراجع ردّ بشكل مش مفهوم", secs=round(time.time() - t0))
            return
        sent = False
        if res["verdict"] != "ok" and res["confidence"] >= 0.5 and (res["issues"] or res["suggestion"]):
            sent = _rv_deliver(s, res)
        s.emit("review", id=rid, model=model, ok=True, sent=sent, secs=round(time.time() - t0), **res)
    except Exception as e:
        s.emit("review", id=rid, model=model, ok=False, error=f"{type(e).__name__}: {str(e)[:160]}", secs=round(time.time() - t0))
    finally:
        s._rv_busy = False


def _rv_maybe(s):
    buf = getattr(s, "_rv_buf", "")
    if len(buf.strip()) < RV_MIN_CHARS or getattr(s, "_rv_busy", False) or not settings_get("reviewer", True):
        return
    if getattr(s, "_rv_run_at", None) != s.run_start:
        s._rv_run_at, s._rv_n = s.run_start, 0
    if s._rv_n >= RV_MAX_PER_TURN or time.time() - getattr(s, "_rv_last", 0) < RV_GAP_SECS:
        return
    seg, s._rv_buf = buf[-6000:], ""
    s._rv_busy, s._rv_n, s._rv_last = True, s._rv_n + 1, time.time()
    model = settings_get("reviewer_model", "claude-sonnet-5-5")
    rid = f"rv{int(time.time() * 1000)}"
    s.emit("review_start", id=rid, model=model, name=MODELS.get(model, model))
    threading.Thread(target=_rv_run, args=(s, rid, model, seg, list(getattr(s, "_rv_acts", []))), daemon=True).start()


_rv_emit_orig = Session.emit


def _rv_emit(self, kind, **data):
    _rv_emit_orig(self, kind, **data)
    try:
        if kind == "thinking":
            self._rv_buf = getattr(self, "_rv_buf", "") + (data.get("text") or "")
        elif kind == "tool":
            acts = getattr(self, "_rv_acts", [])
            if getattr(self, "_rv_acts_at", None) != self.run_start:
                self._rv_acts_at, acts = self.run_start, []
            acts.append(f"{data.get('name')}: {json.dumps(data.get('args') or {}, ensure_ascii=False)[:200]}")
            self._rv_acts = acts[-12:]
            _rv_maybe(self)
        elif kind == "text":
            _rv_maybe(self)
    except Exception:
        pass


Session.emit = _rv_emit
'''


def patch_app(t, sub):
    t = sub(t, PROMPT_ANCHOR, PROMPT_SECTION + PROMPT_ANCHOR, 1, "gd_reviewer: system prompt section")
    t = sub(t, APP_ANCHOR_API, APP_API + APP_ANCHOR_API, 1, "gd_reviewer: on/off API")
    t = sub(t, MAIN_ANCHOR, APP_MODULE + MAIN_ANCHOR, 1, "gd_reviewer: reviewer module")
    return t


# ---------------------------------------------------------------- ui/index.html
CSS = r'''
/* ===== 🧐 مراجع التفكير ===== */
.gdrev{margin:8px 0;border:1px solid var(--line);border-inline-start:3px solid rgba(120,120,128,.6);border-radius:10px;padding:8px 11px;font-size:12.5px;background:var(--fill2)}
.gdrev.ok{border-inline-start-color:rgba(52,199,89,.8)} .gdrev.fix{border-inline-start-color:rgba(255,69,58,.85)} .gdrev.better{border-inline-start-color:rgba(212,160,23,.9)}
.gdrev .h{font-weight:700;display:flex;gap:6px;align-items:center} .gdrev .h .t{margin-inline-start:auto;font-weight:400;color:var(--mute);font-size:11px}
.gdrev ul{margin:5px 0 3px;padding-inline-start:18px} .gdrev .sg{margin-top:4px} .gdrev .ft{margin-top:5px;color:var(--mute);font-size:11.5px}
.gdrev button{margin-top:6px}
'''

THINK_LABEL_END = '<input type="checkbox" id="thinkChk" checked> 💭 اعرض التفكير</label>'
REV_LABEL = ('\n        <label title="وكيل تاني مستقل بيقرا تفكير التنين وهو شغال. لو لقى غلط أو طريقة أحسن، بيبعتله تصحيح ياخده في الخطوة الجاية، '
             'وبيظهرلك كارت بكل اللي قاله."><input type="checkbox" id="revChk" checked> 🧐 مراجع التفكير</label>')

JS_ANCHOR = "async function loadSaved(){"
JS = r'''/* ===== 🧐 مراجع التفكير ===== */
function gdReview(e){
  const s=S[e.sid]; if(!s) return;
  let box=document.getElementById('rv_'+e.id);
  if(!box){ const host=s.cur||add(s,'bot',''); host.insertAdjacentHTML('beforeend',`<div class="gdrev" id="rv_${esc(e.id)}"></div>`); box=document.getElementById('rv_'+e.id) }
  if(e.kind==='review_start'){ box.className='gdrev'; box.innerHTML=`<div class="h"><span class="spin"></span>🧐 المراجع (${esc(e.name||e.model||'')}) بيقرا التفكير…</div>`; return }
  if(!e.ok){ box.className='gdrev'; box.innerHTML=`<div class="h">🧐 المراجع ماقدرش يراجع<span class="t">${esc(e.error||'')}</span></div>`; return }
  const head={ok:'✅ المراجع: التفكير سليم',fix:'⚠️ المراجع لقى غلط',better:'💡 المراجع عنده طريقة أحسن'}[e.verdict]||'🧐 المراجع';
  const iss=(e.issues||[]).length?'<ul>'+e.issues.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul>':'';
  const sg=e.suggestion?`<div class="sg"><b>${e.verdict==='fix'?'الأصح':'الاقتراح'}:</b> ${esc(e.suggestion)}</div>`:'';
  const ft=e.verdict==='ok'?'':(e.sent?'<div class="ft">📨 اتبعت للتنين، وهياخده في الخطوة الجاية.</div>':'<button class="gdrevgo">↩ طبّق الاقتراح</button>');
  box.className='gdrev '+e.verdict;
  box.innerHTML=`<div class="h">${head}<span class="t">${esc(e.model||'')} · ${e.secs||0} ث · ثقة ${Math.round((e.confidence||0)*100)}%</span></div>${iss}${sg}${ft}`;
  const b=box.querySelector('.gdrevgo');
  if(b) b.onclick=()=>{const t=$('#inp'); if(!t) return;
    t.value='المراجع (وكيل تاني) راجع تفكيرك وشايف:\n'+(e.issues||[]).map(x=>'- '+x).join('\n')+(e.suggestion?'\nالاقتراح: '+e.suggestion:'')+'\nقيّمه بالدليل، ولو عنده حق طبّقه.';
    t.dispatchEvent(new Event('input',{bubbles:true})); t.focus(); const sb=$('#sendBtn'); if(sb) sb.click()};
}
(function(){const o=window.onDragon; window.onDragon=function(e){
  if(e&&(e.kind==='review_start'||e.kind==='review')){ try{gdReview(e)}catch(_){} return }
  return o.apply(this,arguments)}})();
document.addEventListener('change',async e=>{if(e.target&&e.target.id==='revChk'){try{await pywebview.api.set_reviewer(e.target.checked)}catch(_){}}});
window.addEventListener('pywebviewready',async()=>{try{const r=await pywebview.api.reviewer_status(); const c=$('#revChk'); if(c) c.checked=!!r.on}catch(_){}});
'''


def patch_ui(t, sub):
    t = sub(t, "</style>", CSS + "</style>", 1, "gd_reviewer: css")
    t = sub(t, THINK_LABEL_END, THINK_LABEL_END + REV_LABEL, 1, "gd_reviewer: on/off switch")
    t = sub(t, JS_ANCHOR, JS + JS_ANCHOR, 1, "gd_reviewer: review cards")
    return t
