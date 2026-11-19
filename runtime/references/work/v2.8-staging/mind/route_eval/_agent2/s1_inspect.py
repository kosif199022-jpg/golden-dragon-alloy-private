import json, os, sys
B = r"C:\Users\cinde\rd-staging\v2.8\mind"
def load(p):
    for enc in ("utf-8-sig", "utf-16"):
        try:
            return json.load(open(p, encoding=enc))
        except UnicodeError:
            pass
d = load(os.path.join(B, "dictation.json"))
print("DICT type", type(d).__name__, "keys" if isinstance(d, dict) else "", list(d.keys())[:20] if isinstance(d, dict) else len(d))
s = json.dumps(d, ensure_ascii=False)
print(len(s)); print(s[:3000])
for f in ("turns_all.json", "fresh_cc.json", "owner_requests.json"):
    x = load(os.path.join(B, "route_eval", f))
    print("\n==", f, type(x).__name__, len(x))
    it = x[0] if isinstance(x, list) else list(x.items())[0]
    print(json.dumps(it, ensure_ascii=False)[:600])
