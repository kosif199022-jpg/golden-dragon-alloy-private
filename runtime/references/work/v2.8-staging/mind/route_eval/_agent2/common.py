import json, os, re
from collections import Counter, defaultdict
B = r"C:\Users\cinde\rd-staging\v2.8\mind"
R = os.path.join(B, "route_eval")
def load(p):
    for enc in ("utf-8-sig", "utf-16"):
        try:
            return json.load(open(p, encoding=enc))
        except UnicodeError:
            pass
def clean(t):
    t = t or ""
    t = re.sub(r"\[[^\]]{0,4000}\]", " ", t)          # injected system blocks
    t = re.sub(r"https?://\S+|[A-Za-z]:\\\S+", " ", t)
    t = re.sub(r"[\u064b-\u0652\u0640]", "", t)        # tashkeel + tatweel
    return t
def sentences():
    """yield (file, field, cleaned text)"""
    seen = set()
    for f in ("turns_all.json", "fresh_cc.json", "owner_requests.json"):
        for it in load(os.path.join(R, f)):
            for fld in ("q", "prev"):
                t = it.get(fld)
                if not isinstance(t, str) or not t.strip():
                    continue
                c = clean(t)
                if c in seen:
                    continue
                seen.add(c)
                yield f, fld, c
WORD = re.compile(r"[\u0621-\u064a]+")
def lines(text):
    for ln in re.split(r"[\n\.؟!]+", text):
        ln = " ".join(ln.split())
        if ln:
            yield ln
