import json, sys
a, b = int(sys.argv[1]), int(sys.argv[2])
d = json.load(open(r"C:\Users\cinde\rd-staging\v2.8\mind\route_eval\fresh_cc.json", encoding="utf-8"))
sys.stdout.reconfigure(encoding="utf-8")
print("TOTAL", len(d))
for m in d:
    if a <= m["fid"] <= b:
        q = m["q"].replace("\n", " ⏎ ")
        if len(q) > 900:
            q = q[:450] + " …[CUT %d]… " % (len(q) - 750) + q[-300:]
        p = (m.get("prev") or "").replace("\n", " ")[:140]
        print("#%d Q: %s\n   P: %s" % (m["fid"], q, p))
