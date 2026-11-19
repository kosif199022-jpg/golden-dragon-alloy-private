# -*- coding: utf-8 -*-
import io
p = "build_proposals.py"
s = io.open(p, encoding="utf-8").read()
def rep(a, b):
    global s
    assert s.count(a) == 1, a
    s = s.replace(a, b)
rep(u'اخطاء للتطبيق"', u'اخطاء"')
rep(u'u"حوالات رجعت", u"حساب شركه", u"حساب بنك"', u'u"حوالات رجعت", u"حساب بنك"')
rep(u'u"ديزني استايل", u"استايل ديزني", u"نماذج تحويل"', u'u"ديزني استايل", u"نماذج تحويل"')
rep(u'"reel-montage": (u"لاغنيه",', u'"reel-montage": (u"",')
rep('''def has(text_padded, term):
    return (" " + term + " ") in text_padded''', '''def forms(w):
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
    return t in text_padded''')
rep('''            hit = term in ws or stem(term) in set(stem(w) for w in ws)''',
    '''            ft = forms(term)
            hit = any(ft & forms(w) for w in ws)''')
io.open(p, "w", encoding="utf-8").write(s)
print("patched")
