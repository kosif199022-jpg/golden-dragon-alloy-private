import re
from common import *
Q = """واصمع وسصنع الاختيارةة قداات القواي المكتبوير المكت المجل مجل للمونتات قراراري كروب لكلاد ولاات وضغ خدث مقع
مجالوتكون وثبتاذا عالميؤوناقد والاقائمة اواد اغيل بكال ثباها شحه يعلك ناد محا التا الرجع اللسة المربط الحوال السماك
بشوفات فيزاء جوالات هيجزفيل برتكول الايجمنت والسيرفلات فلاكس بايبيه احجاب وانميشن ستخدم سيرفركلاود فيبل مينت اتحدثش""".split()
seen = set()
for f, fld, c in sentences():
    for ln in lines(c):
        toks = WORD.findall(ln)
        for w in Q:
            if w in toks and (w, ln) not in seen and sum(1 for k in seen if k[0] == w) < 2:
                seen.add((w, ln))
                i = ln.find(w)
                print(f"{w} | {ln[max(0, i-45):i+len(w)+40]}")
