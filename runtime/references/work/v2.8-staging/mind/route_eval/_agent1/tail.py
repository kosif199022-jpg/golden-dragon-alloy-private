import json, sys
d = json.load(open(r"C:\Users\cinde\rd-staging\v2.8\mind\route_eval\fresh_cc.json", encoding="utf-8"))
sys.stdout.reconfigure(encoding="utf-8")
for f in (113, 132):
    q = d[f]["q"].replace("\n", " ⏎ ")
    print("#%d LEN %d TAIL: %s\n" % (f, len(q), q[-700:]))
print("fids ok:", [m["fid"] for m in d] == list(range(226)))
