# -*- coding: utf-8 -*-
"""التنين الذهبي — إضافات 2026-11-16:
  1) بحث في نص المحادثات المحفوظة كلها (مش العنوان بس)، بالعربي والإنجليزي، ومن غير ما يفرق أ/ا/إ أو ة/ه أو ى/ي.
  2) تثبيت محادثات 📌: المثبّتة بتطلع فوق دايمًا، ومتسجّلة في settings.json («pinned_chats»).
  3) «صح من أول مرة»: بعد كل رد، التطبيق نفسه بيفحص الملفات اللي اتعملت في الدور ده (موجودة؟ مش فاضية؟ بتتفتح؟)
     ويعرض كارت ✅ أو ❌، ومعاه زرار «🔧 صلّح» بيبعت للنموذج اللي فشل بالظبط.
  4) طريق الـ API التاني (المقارنة) بقى بيطلب ملخص التفكير هو كمان (display: summarized).

بيتنادي من make_golden_dragon.py بعد طبقة التنين:  gd_extras.patch_app(t, sub)  و  gd_extras.patch_ui(t, sub)
كل استبدال عليه sub(... count=1) يعني لو النص الأصلي اتغيّر، التوليد يقف بدل ما يطلع تطبيق بايظ.
"""

import re

# ---------------------------------------------------------------- app.py (Python backend)
APP_ANCHOR = "    def delete_saved(self, cid):\n"

APP_METHODS = r'''    # ===== التنين الذهبي 2026-11-16: بحث في المحادثات + تثبيت + فحص التسليم =====
    _gd_cache = {}

    _GD_MAP = {"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ة": "ه", "ى": "ي"}

    @classmethod
    def _gd_norm_map(cls, t):
        """Normalized text + for every normalized char the index of the raw char it came from (for real snippets)."""
        out, idx = [], []
        for i, ch in enumerate(t or ""):
            o = ord(ch)
            if 0x064B <= o <= 0x0652 or o in (0x0670, 0x0640):   # تشكيل وتطويل
                continue
            ch = ch.lower()
            ch = cls._GD_MAP.get(ch, " " if ch.isspace() else ch)
            out.append(ch)
            idx.append(i)
        return "".join(out), idx

    @classmethod
    def _gd_norm(cls, t):
        return re.sub(r" +", " ", cls._gd_norm_map(t)[0])

    def _gd_chat_text(self, f):
        """(title, updated, workdir, raw text, normalized text) of a saved chat, cached by mtime."""
        key, mt = str(f), f.stat().st_mtime
        hit = self._gd_cache.get(key)
        if hit and hit[0] == mt:
            return hit[1]
        d = json.loads(f.read_text(encoding="utf-8"))
        parts = [d.get("title") or ""]
        for m in d.get("messages", []):
            c = m.get("content")
            if isinstance(c, str):
                parts.append(c)
            elif isinstance(c, list):
                for p in c:
                    if isinstance(p, dict) and p.get("type") == "text":
                        tx = p.get("text") or ""
                        if tx.startswith("[عقل التنين") or tx.startswith("[فريق الوكلاء") or tx.startswith("[مجلد الشغل"):
                            continue          # the app's own injected notes are the same in every chat: not worth matching
                        parts.append(tx)
        raw = "\n".join(parts)
        norm, idx = self._gd_norm_map(raw)
        rec = (d.get("title") or "محادثة", d.get("updated", ""), d.get("workdir", ""), raw, norm, idx)
        self._gd_cache[key] = (mt, rec)
        return rec

    def list_saved_gd(self):
        """Like list_saved, plus the 📌 flag; pinned chats first (and never cut by the 200 limit)."""
        pins = [p for p in (settings_get("pinned_chats", []) or []) if isinstance(p, str)]
        files = sorted(CHATS.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
        keep = [f for f in files if f.stem in pins] + [f for f in files if f.stem not in pins][:200]
        out = []
        for f in keep:
            if f.stem in self._sessions:
                continue
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                out.append({"id": d["id"], "title": d.get("title") or "محادثة", "updated": d.get("updated", ""),
                            "cost": round(d.get("cost", 0.0), 3), "workdir": d.get("workdir", ""), "pinned": d["id"] in pins})
            except Exception:
                continue
        out.sort(key=lambda c: (not c["pinned"], pins.index(c["id"]) if c["pinned"] else 0))
        return out

    def set_pinned(self, cid, on):
        cid = Path(str(cid)).name
        pins = [p for p in (settings_get("pinned_chats", []) or []) if isinstance(p, str) and p != cid]
        if on:
            pins.insert(0, cid)
        settings_set("pinned_chats", pins[:100])
        return {"ok": True, "pinned": bool(on)}

    def search_saved(self, q, limit=60):
        """Full-text search over every saved chat. All words must appear (any order); title hits rank first."""
        qn = self._gd_norm(q).strip()
        if not qn:
            return []
        words = [w for w in qn.split(" ") if w]
        pins = settings_get("pinned_chats", []) or []
        out = []
        for f in CHATS.glob("*.json"):
            try:
                title, updated, workdir, raw, norm, idx = self._gd_chat_text(f)
            except Exception:
                continue
            if not all(w in norm for w in words):
                continue
            tn = self._gd_norm(title)
            score = sum(3 for w in words if w in tn) + min(sum(norm.count(w) for w in words), 20) / 20
            i = norm.find(qn)
            if i < 0:
                i = norm.find(words[0])
            r0 = idx[i] if i < len(idx) else 0                 # back to the raw text: the snippet shows the real words
            a = max(0, r0 - 60)
            snip = re.sub(r"\s+", " ", raw[a:r0 + 110]).strip()
            out.append({"id": f.stem, "title": title, "updated": updated, "workdir": workdir, "pinned": f.stem in pins,
                        "snippet": ("…" if a else "") + snip + "…", "score": round(score, 3)})
        out.sort(key=lambda c: c["updated"], reverse=True)    # newest first among equal scores (sort is stable)
        out.sort(key=lambda c: c["score"], reverse=True)
        return out[:int(limit)]

    def verify_turn(self, sid):
        """«صح من أول مرة»: measure every file this chat created/changed in the last turn. Read-only, no network."""
        s = self._sessions.get(sid)
        if not s or not s.run_start:
            return {"items": []}
        fresh = [it["path"] for it in list(s.files.values()) if it.get("mtime", 0) >= s.run_start - 2]
        items = []
        probe = shutil.which("ffprobe")
        for p in sorted(set(fresh))[:40]:
            P = Path(p)
            ext = P.suffix.lower()
            ok, note = True, ""
            try:
                if not P.is_file():
                    ok, note = False, "الملف مش موجود"
                elif P.stat().st_size == 0:
                    ok, note = False, "الملف فاضي (0 بايت)"
                elif ext == ".py":
                    compile(P.read_text(encoding="utf-8", errors="replace"), P.name, "exec")
                    note = "الكود سليم (اتعمله compile)"
                elif ext == ".json":
                    json.loads(P.read_text(encoding="utf-8-sig"))
                    note = "JSON سليم"
                elif ext in (".mp4", ".mov", ".mkv", ".webm", ".m4v", ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"):
                    if not probe:
                        note = "ffprobe مش موجود، ماتقاسش"
                    else:
                        r = subprocess.run([probe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(P)],
                                           capture_output=True, text=True, timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                        dur = float((r.stdout or "0").strip().split("\n")[0] or 0)
                        ok, note = (dur > 0.05), (f"المدة {dur:.1f} ث" if dur > 0.05 else "الملف مابيتشغلش (مدة صفر أو بايظ)")
                elif ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"):
                    from PIL import Image
                    with Image.open(P) as im:
                        im.verify()
                    with Image.open(P) as im:
                        note = f"{im.width}×{im.height}"
                elif ext in (".zip", ".docx", ".xlsx", ".pptx", ".skill"):
                    import zipfile
                    with zipfile.ZipFile(P) as z:
                        bad = z.testzip()
                    ok, note = (bad is None), ("الأرشيف سليم" if bad is None else f"ملف بايظ جوه الأرشيف: {bad}")
                elif ext == ".pdf":
                    with open(P, "rb") as fh:
                        ok = fh.read(5) == b"%PDF-"
                    note = "PDF سليم" if ok else "مش PDF حقيقي"
                elif ext in (".html", ".htm", ".md", ".txt", ".css", ".js", ".csv", ".srt", ".vtt", ".ass"):
                    txt = P.read_text(encoding="utf-8")
                    ok, note = bool(txt.strip()), ("مقروء UTF-8" if txt.strip() else "مفيهوش غير مسافات")
                else:
                    note = f"{P.stat().st_size:,} بايت"
            except UnicodeDecodeError:
                ok, note = False, "الترميز مش UTF-8 (ممكن العربي يبان بايظ)"
            except SyntaxError as e:
                ok, note = False, f"غلط في الكود سطر {e.lineno}: {e.msg}"
            except Exception as e:
                ok, note = False, f"{type(e).__name__}: {str(e)[:120]}"
            items.append({"path": p, "name": P.name, "ok": bool(ok), "note": note})
        return {"items": items, "ok": all(i["ok"] for i in items)}

'''

THINK_OLD = 'thinking={"type": "adaptive"},'
THINK_NEW = 'thinking={"type": "adaptive", "display": "summarized"},'


def patch_app(t, sub):
    t = sub(t, APP_ANCHOR, APP_METHODS + APP_ANCHOR, 1, "gd_extras: search/pin/verify API")
    t = sub(t, THINK_OLD, THINK_NEW, 1, "gd_extras: summarized thinking on the second API path")
    head = "\n".join(line for line in t.splitlines()[:40] if line.startswith("import "))
    for mod in ("json", "re", "shutil", "subprocess"):
        if not re.search(rf"\b{mod}\b", head):
            raise SystemExit(f"✗ gd_extras: app.py no longer imports {mod}")
    return t


# ---------------------------------------------------------------- ui/index.html
CSS = r'''
/* ===== التنين الذهبي 2026-11-16: بحث وتثبيت المحادثات + كارت الفحص ===== */
#gdFind{display:block;width:calc(100% - 16px);margin:2px 8px 6px;padding:6px 10px;border-radius:9px;border:.5px solid var(--line);background:var(--fill2);color:var(--text);font:inherit;font-size:12.5px}
#gdFind:focus{outline:none;border-color:var(--accent,#d4a017);box-shadow:0 0 0 3px var(--ring,rgba(212,160,23,.2))}
#saved .ch .pn{opacity:0;font-size:12px;padding:0 2px;filter:grayscale(1)}
#saved .ch:hover .pn{opacity:.8}
#saved .ch.pinned .pn{opacity:1;filter:none}
#saved .gdsec{font-size:11px;color:var(--mute);padding:6px 10px 2px}
#saved .ch .sn{display:block;font-size:11px;color:var(--mute);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}
#saved .ch .sn mark{background:rgba(212,160,23,.35);color:inherit;border-radius:3px;padding:0 1px}
#saved .ch .nmw{flex:1;min-width:0;display:flex;flex-direction:column}
#saved .ch .nmw .nm{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.gdgate{margin-top:10px;border:1px solid var(--line);border-radius:12px;padding:10px 12px;font-size:12.5px;background:var(--fill2)}
.gdgate.ok{border-color:rgba(52,199,89,.55)} .gdgate.bad{border-color:rgba(255,69,58,.6)}
.gdgate .h{font-weight:700;margin-bottom:6px}
.gdgate .r{display:flex;gap:8px;align-items:baseline;padding:2px 0}
.gdgate .r b{font-weight:600;max-width:55%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.gdgate .r i{font-style:normal;color:var(--mute)}
.gdgate button{margin-top:8px}
'''

UI_SAVED_OLD = '<div id="saved" style="max-height:38%;overflow-y:auto;padding:0 6px 8px"></div>'
UI_SAVED_NEW = ('<input id="gdFind" placeholder="🔎 دوّر في كل المحادثات (العنوان والكلام)…" autocomplete="off" spellcheck="false">'
                + UI_SAVED_OLD)

LOAD_OLD = '''async function loadSaved(){
  const list=await pywebview.api.list_saved(); $('#savedCount').textContent=list.length||'';'''

LOAD_NEW = r'''/* ===== التنين الذهبي 2026-11-16: بحث في المحادثات + تثبيت ===== */
let GDQ='', GDT=null;
function gdMark(t,q){const s=esc(t||''); if(!q) return s;
  const n=x=>x.toLowerCase().replace(/[ً-ٰٟـ]/g,'').replace(/[أإآٱ]/g,'ا').replace(/ة/g,'ه').replace(/ى/g,'ي');
  let out=s; q.split(/\s+/).filter(Boolean).forEach(w=>{const i=n(out).indexOf(n(w)); if(i>=0&&w.length>1) out=out.slice(0,i)+'<mark>'+out.slice(i,i+w.length)+'</mark>'+out.slice(i+w.length)}); return out}
async function loadSaved(){
  const q=($('#gdFind')&&$('#gdFind').value||'').trim(); GDQ=q;
  const list=q?await pywebview.api.search_saved(q):await pywebview.api.list_saved_gd();
  if(q!==GDQ) return;                                   // a newer search already started
  $('#savedCount').textContent=list.length||'';
  const row=c=>`<div class="ch${c.pinned?' pinned':''}" data-c="${esc(c.id)}" title="${esc(c.workdir||'')}"><span class="ic">${c.pinned?'📌':'💾'}</span><span class="nmw"><span class="nm">${gdMark(c.title,q)}</span>${c.snippet?`<span class="sn">${gdMark(c.snippet,q)}</span>`:''}</span><span class="meta">${esc((c.updated||'').slice(5,16).replace('T',' '))}</span><span class="pn" data-p="${esc(c.id)}" data-on="${c.pinned?1:0}" title="${c.pinned?'شيل التثبيت':'ثبّت فوق'}">📌</span><span class="x" data-d="${esc(c.id)}" title="امسح">🗑</span></div>`;
  const pins=list.filter(c=>c.pinned), rest=list.filter(c=>!c.pinned);
  $('#saved').innerHTML=(q&&!list.length)?'<div class="gdsec">مفيش محادثة فيها «'+esc(q)+'»</div>':
    (pins.length&&!q?'<div class="gdsec">📌 المثبّتة</div>'+pins.map(row).join('')+(rest.length?'<div class="gdsec">الباقي</div>':''):'')+(q?list:rest).map(row).join('');
  $('#saved').querySelectorAll('.ch').forEach(d=>d.onclick=()=>openSaved(d.dataset.c));
  $('#saved').querySelectorAll('.pn').forEach(p=>p.onclick=async ev=>{ev.stopPropagation(); await pywebview.api.set_pinned(p.dataset.p,p.dataset.on!=='1'); loadSaved()});
  $('#saved').querySelectorAll('.x').forEach(x=>x.onclick=async ev=>{ev.stopPropagation(); if(!confirm('أمسح المحادثة دي نهائي؟'))return; await pywebview.api.set_pinned(x.dataset.d,false); await pywebview.api.delete_saved(x.dataset.d); loadSaved()});
}
document.addEventListener('input',e=>{if(e.target&&e.target.id==='gdFind'){clearTimeout(GDT); GDT=setTimeout(loadSaved,220)}});
document.addEventListener('keydown',e=>{if(e.target&&e.target.id==='gdFind'&&e.key==='Escape'){e.preventDefault();e.stopPropagation();e.target.value='';loadSaved()}},true);
/* «صح من أول مرة»: بعد كل رد، افحص الملفات اللي اتعملت فعلًا */
async function gdVerify(s){
  let r; try{ r=await pywebview.api.verify_turn(s.sid) }catch(e){ return }
  if(!r||!r.items||!r.items.length) return;
  const bad=r.items.filter(i=>!i.ok);
  const rows=r.items.map(i=>`<div class="r"><span>${i.ok?'✅':'❌'}</span><b title="${esc(i.path)}">${esc(i.name)}</b><i>${esc(i.note||'')}</i></div>`).join('');
  const fix=bad.length?'<button class="gdfix">🔧 صلّح</button>':'';
  const card=add(s,'bot',`<div class="gdgate ${bad.length?'bad':'ok'}"><div class="h">${bad.length?`❌ فحص التسليم: ${bad.length} من ${r.items.length} ملف فيه مشكلة`:`✅ فحص التسليم: ${r.items.length} ملف اتقاسوا وسليمين`}</div>${rows}${fix}</div>`);
  const b=(card&&card.querySelector)?card.querySelector('.gdfix'):null;
  if(b) b.onclick=()=>{const t=$('#inp'); if(!t) return;
    t.value='فحص التسليم التلقائي لقى مشاكل في الملفات دي، صلّحها وقيس تاني قبل ما تقول خلص:\n'+bad.map(i=>'- '+i.path+': '+i.note).join('\n');
    t.dispatchEvent(new Event('input',{bubbles:true})); t.focus(); const sb=$('#sendBtn'); if(sb) sb.click()};
}
async function loadSaved_orig(){
  const list=await pywebview.api.list_saved(); $('#savedCount').textContent=list.length||'';'''

DONE_OLD = "    s.badge=null; if(s.sid===act) paintState()}\n  if(!replaying) renderSide();"
DONE_NEW = ("    s.badge=null; if(s.sid===act) paintState(); if(!replaying&&!e.stopped) gdVerify(s)}\n"
            "  if(!replaying) renderSide();")


def patch_ui(t, sub):
    t = sub(t, "</style>", CSS + "</style>", 1, "gd_extras: css")
    t = sub(t, UI_SAVED_OLD, UI_SAVED_NEW, 1, "gd_extras: search box above saved chats")
    t = sub(t, LOAD_OLD, LOAD_NEW, 1, "gd_extras: loadSaved with search + pins")
    t = sub(t, DONE_OLD, DONE_NEW, 1, "gd_extras: delivery check after each turn")
    return t
