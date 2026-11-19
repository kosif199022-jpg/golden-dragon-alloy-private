# -*- coding: utf-8 -*-
"""Agent4: build proposals_triggers.json from hand-picked terms.
Input evidence = dev_by_playbook.json, which dev_dump.py built from EVEN ids only.
Checks: term not already in own triggers, evidence refs (even only), collisions with other playbooks."""
import json, io, os, re
B = r"C:\Users\cinde\rd-staging\v2.8\mind\route_eval"
PB = r"C:\Users\cinde\rd-staging\v2.8\mind\playbooks.json"
A4 = os.path.join(B, "_agent4")

def norm(s):
    s = str(s).lower()
    s = re.sub(u"[\u064b-\u0652\u0640]", "", s)
    for a, b in ((u"أ", u"ا"), (u"إ", u"ا"), (u"آ", u"ا"), (u"ة", u"ه"), (u"ى", u"ي")):
        s = s.replace(a, b)
    s = re.sub(r"[^\w\s]", " ", s, flags=re.U)
    return " ".join(s.split())

def stem(w):
    for p in (u"وال", u"بال", u"لل", u"ال", u"و", u"ل", u"ب"):
        if w.startswith(p) and len(w) - len(p) >= 3:
            return w[len(p):]
    return w

# hand-picked from the even-id dump (dev_dump.txt). normalised spelling (ه not ة).
P = {
 "app-dev": (u"البرنامج التحديث امكانيه واقف الايجنت معاينه القائمه اخطاء",
             [u"حدث التطبيق", u"اضف امكانيه", u"مش شغال", u"عدل التطبيق", u"حسن التطبيق", u"مشكله التحديث"]),
 "clone-own-tool": (u"المحاكي الكاميرا لايف تسجيلات تطبيقي الافلام",
             [u"محاكي اندرويد", u"تطبيق شبيه", u"تطبيق مثله", u"تسجيل لايف", u"بيانات الدخول", u"برنامج التحميل", u"المتصفح السحابي", u"نسخه سطح"]),
 "reconcile": (u"مستفيد المستفيد لمستفيد طابقه اتحولت المبلغ لمورد",
             [u"تواريخ التحويل", u"بنفس المبلغ", u"حوالات رجعت", u"حساب بنك"]),
 "status": (u"لسه قدامك لاقي",
             [u"هل خلصت", u"ولا لسه", u"باقي لك", u"مش لاقي", u"هل صنعت", u"هو شغال"]),
 "self-improve": (u"احقن احقنه احقنها قدراتك امكانياتك خلاصه",
             [u"كل قدراتك", u"ملف التعليمات", u"ملف تعليمات", u"سوبر باور"]),
 "re-repo": (u"مستودعات المستودعات جيتهاب استنساخ",
             [u"جيت هاب", u"مستودعات جيت", u"مستودع جيت"]),
 "build-skill": (u"",
             [u"طور مهاره", u"اصنع مهاره", u"مهاره تعمل", u"يمكن لكلاود"]),
 "ship": (u"ارفعه ارفع",
             [u"اعطيني الرابط", u"مجلد علي"]),
 "pc-task": (u"التبويب تبويب powershell",
             [u"اسم التبويب", u"بامر واحد"]),
 "site-style": (u"تناسق وخطوط",
             [u"الوان وخطوط", u"اقترح تطوير", u"طور الالوان"]),
 "deep-research": (u"روابط",
             [u"كل المواقع", u"مفتوحه المصدر"]),
 "app-to-skill": (u"حوله وحوله",
             [u"الي مهاره", u"مهاره كلاود", u"حلله وحوله"]),
 "re-site": (u"",
             [u"تفاصيل طلبات"]),
 "toon": (u"ديزني لديزني disney",
             [u"ديزني استايل", u"نماذج تحويل"]),
 "web-build": (u"",
             [u"اعمل موقع", u"موقع شبيه", u"الي تطبيق", u"موقع متقدم"]),
 "reel-montage": (u"",
             [u"مونتاج لاغنيه"]),
 "motion-code": (u"جرافك انميشن وانميشن",
             [u"موشن جرافك"]),
 "paid-gen": (u"ارخص بدائل",
             [u"بدائل ارخص"]),
 "design-static": (u"ترسم", []),
 "re-apk": (u"apks", []),
 "re-file": (u"سيرفر سيرفرات السيرفرات السيفرات server", []),
 "cloud-render": (u"المجانيه مجانيه",
             [u"الخدمات المجانيه"]),
 "nature-palette": (u"طائر",
             [u"صوره طائر"]),
}

pbs = json.load(io.open(PB, encoding="utf-8-sig"))["playbooks"]
pbs = pbs if isinstance(pbs, list) else [dict(v, id=v.get("id", k)) for k, v in pbs.items()]
def tx(v):
    return norm(" ".join(map(str, v)) if isinstance(v, list) else (v or ""))
info = {p["id"]: {"triggers": tx(p.get("triggers")), "ar": tx(p.get("ar")), "en": tx(p.get("en"))} for p in pbs}
dev = json.load(io.open(os.path.join(A4, "dev_by_playbook.json"), encoding="utf-8"))
# safety: dev file must be even-only
for k, v in dev.items():
    for e in v:
        assert int(e["ref"].split(":")[1]) % 2 == 0, "ODD id leaked: " + e["ref"]
devn = {k: [(e["ref"], " " + norm(e["q"]) + " ") for e in v] for k, v in dev.items()}

def forms(w):
    out = {w}
    for _ in range(2):
        for x in list(out):
            for p in (u"وال", u"بال", u"لل", u"ال", u"و", u"ل", u"ب"):
                if x.startswith(p) and len(x) - len(p) >= 3:
                    out.add(x[len(p):])
    return out

def has(text_padded, term):
    # substring on the bare form, so prefixed spellings (و/ل/ب/ال) in the request still count
    t = term if " " in term else stem(term)
    return t in text_padded

def other_hits(pid, term):
    out = []
    toks = term.split()
    for oid, d in info.items():
        if oid == pid:
            continue
        blob = " " + d["triggers"] + " | " + d["ar"] + " | " + d["en"] + " "
        if len(toks) > 1:
            hit = term in blob
        else:
            ws = set(blob.split())
            ft = forms(term)
            hit = any(ft & forms(w) for w in ws)
        if hit:
            out.append(oid)
    return out

out, amb, dropped, noev = {}, {}, {}, {}
for pid, (add, phrases) in P.items():
    assert pid in info, "unknown playbook " + pid
    own = " " + info[pid]["triggers"] + " "
    own_set = set(own.split())
    words = [w for w in norm(add).split()]
    keep_w, keep_p = [], []
    for w in words:
        (dropped.setdefault(pid, []).append(w) if w in own_set else keep_w.append(w))
    for ph in [norm(x) for x in phrases]:
        (dropped.setdefault(pid, []).append(ph) if ph in own else keep_p.append(ph))
    assert len(keep_w) + len(keep_p) <= 15, pid
    coll, ev = {}, []
    for t in keep_w + keep_p:
        o = other_hits(pid, t)
        if o:
            coll[t] = o
        refs = [r for r, q in devn.get(pid, []) if has(q, t)]
        if not refs:
            noev.setdefault(pid, []).append(t)
        for r in refs:
            if r not in ev:
                ev.append(r)
        oth = {k: [r for r, q in v if has(q, t)] for k, v in devn.items() if k != pid}
        oth = {k: v for k, v in oth.items() if v}
        if oth:
            amb.setdefault(pid, {})[t] = oth
    ev.sort(key=lambda r: (r.split(":")[0] != "old", int(r.split(":")[1])))
    out[pid] = {"add": " ".join(keep_w), "phrases": keep_p, "collisions": coll, "evidence_dev_ids": ev}

with io.open(os.path.join(B, "proposals_triggers.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
with io.open(os.path.join(A4, "dev_ambiguity.json"), "w", encoding="utf-8") as f:
    json.dump({"same_term_seen_in_even_examples_of_other_playbooks": amb,
               "variants_without_direct_even_evidence": noev,
               "dropped_already_in_own_triggers": dropped}, f, ensure_ascii=False, indent=1)

print("playbooks:", len(out), "terms:", sum(len(v["add"].split()) + len(v["phrases"]) for v in out.values()))
print("DROPPED(already own):", json.dumps(dropped, ensure_ascii=False))
print("NO-EVIDENCE variants:", json.dumps(noev, ensure_ascii=False))
print("COLLISIONS:")
for k, v in out.items():
    if v["collisions"]:
        print(" ", k, json.dumps(v["collisions"], ensure_ascii=False))
print("DEV-AMBIGUITY:")
for k, v in amb.items():
    print(" ", k, json.dumps(v, ensure_ascii=False))
