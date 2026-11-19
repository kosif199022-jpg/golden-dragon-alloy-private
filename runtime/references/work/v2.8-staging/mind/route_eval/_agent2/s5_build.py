import json, os, re
from common import *
FIX = {
 # حرف زايد / مكرر / متبدّل
 "استحخدم": "استخدم", "ستخدم": "استخدم", "اصندع": "اصنع", "واصمع": "واصنع",
 "الادواات": "الادوات", "التبويباتت": "التبويبات", "التجكم": "التحكم", "التحديدث": "التحديث",
 "الخدممات": "الخدمات", "السيفرات": "السيرفرات", "والسيرفلات": "والسيرفرات", "سريفره": "سيرفره",
 "العكشسة": "العكسية", "الههندسة": "الهندسة", "القددرات": "القدرات", "قداات": "قدرات",
 "ققدراتك": "قدراتك", "الكامكيرا": "الكاميرا", "الكبيوتر": "الكمبيوتر", "مهارهة": "مهارة",
 "لطوير": "لتطوير", "تذكون": "تكون", "تستطيح": "تستطيع", "ايضان": "ايضا", "شغاال": "شغال",
 "عندده": "عنده", "قراراري": "قراري", "وادمجخم": "وادمجهم", "بنفيس": "بنفس", "بكال": "بكل",
 "خدث": "حدث", "وضغ": "وضع", "اغيل": "اغير", "مقع": "موقع", "المجل": "المجلد", "اللسة": "الجلسة",
 "والاقائمة": "والقائمة", "بشوفات": "كشوفات", "فيزاء": "فيزياء", "برتكول": "بروتوكول",
 "الايجمنت": "الايجنت", "وانميشن": "وانيميشن", "لكلاد": "لكلاود", "هيجزفيل": "هيجزفيلد",
 # صيغ بسوابق لبنود موجودة في القاموس من غير سابقة
 "المونتاتج": "المونتاج", "والمونتاتج": "والمونتاج", "للمونتات": "للمونتاج",
 "الفديو": "الفيديو", "والفديو": "والفيديو", "الفديوهات": "الفيديوهات",
 "وفديوهات": "وفيديوهات", "للفديوهات": "للفيديوهات", "لمكنة": "لماكينة", "والفوتشوب": "والفوتوشوب",
 # كلمتين لزقوا في بعض
 "مجالوتكون": "مجال وتكون", "وثبتاذا": "وثبت اذا", "عالميؤوناقد": "عالمي وناقد", "سيرفركلاود": "سيرفر كلاود",
 # عبارات بس (الكلمة لوحدها ممكن تبقى صح)
 "جوالات المراجعة": "جولات المراجعة", "في كروب": "في كروم", "سطح المكت": "سطح المكتب",
 "في مجل": "في مجلد", "التا تم": "التي تم", "حساب احجاب": "حساب احجام",
}
TR = {
 "كلاينك": "kling", "بلندر": "blender", "ببلندر": "blender", "كلاود": "claude", "لكلاود": "claude", "الكلاود": "claude",
 "كروم": "chrome", "سيرفر": "server", "السيرفرات": "servers", "البرومنت": "prompt", "استايل": "style", "بستايل": "style",
 "رندر": "render", "الرندر": "render", "الريندر": "render", "موشن": "motion", "الموشن": "motion", "جرافك": "graphic",
 "وانيميشن": "animation", "الايجنت": "agent", "اكسل": "excel", "الاكسل": "excel", "شيت": "sheet", "الشيت": "sheet",
 "لايف": "live", "اللينك": "link", "موديل": "model", "مودل": "model", "المودل": "model", "اللابتوب": "laptop",
 "الموبايل": "mobile", "اندرويد": "android", "سوبر": "super", "باور": "power", "سوبرباور": "superpowers",
 "والكيبورد": "keyboard", "والماوس": "mouse", "والثيم": "theme", "باسوردات": "passwords", "فلاكس": "flux",
 "كمبيوتر": "computer", "كرتون": "cartoon", "كاميرا": "camera", "شات": "chat", "هاب": "hub", "هيجزفلد": "higgsfield",
 "هيجزفيل": "higgsfield", "والافترافك": "after effects", "والفوتشوب": "photoshop", "ويندز": "windows",
 "بايبيه": "ip", "الاسكيلات": "skills", "كلينك": "kling",
}
cur = load(os.path.join(B, "dictation.json"))
texts = [c for _, fld, c in sentences()]
def find(key):
    out = []
    pat = re.compile(r"(?<![\u0621-\u064a])" + re.escape(key).replace(r"\ ", r"\s+") + r"(?![\u0621-\u064a])")
    for t in texts:
        t1 = " ".join(t.split())
        for m in pat.finditer(t1):
            s = max(0, m.end() - 80) if m.end() > 80 else 0
            if s:  # start at a word boundary
                s = t1.find(" ", s) + 1
            e = t1[s:s + 80]
            if key in e and e not in out:
                out.append(e)
            if len(out) >= 2: return out
    return out
fix, ev, dropped = {}, {}, []
for k, v in FIX.items():
    e = find(k)
    if k in cur or not e or len(k) < 3 or k == v:
        dropped.append((k, "in dict" if k in cur else "no evidence")); continue
    fix[k] = v; ev[k] = e
tr = {k: v for k, v in TR.items() if find(k) and len(k) >= 3}
tr_drop = [k for k in TR if k not in tr]
out = {"fix": fix, "translit": tr, "evidence": ev}
p = os.path.join(R, "proposals_dictation.json")
json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
chk = json.load(open(p, encoding="utf-8"))
assert all(k in chk["evidence"] and chk["evidence"][k] and all(k in s and len(s) <= 80 for s in chk["evidence"][k]) for k in chk["fix"])
assert not (set(chk["fix"]) & set(chk["translit"]) - {"هيجزفيل", "والفوتشوب"})
print("fix", len(fix), "translit", len(tr), "dropped", dropped, "tr_drop", tr_drop)
freq = json.load(open(os.path.join(R, "_agent2", "freq.json"), encoding="utf-8"))["freq"]
top = sorted(fix, key=lambda k: -freq.get(k, 1))[:22]
for k in top:
    print(f"{k} -> {fix[k]} ({freq.get(k, 1)}) | {ev[k][0][:60]}")
