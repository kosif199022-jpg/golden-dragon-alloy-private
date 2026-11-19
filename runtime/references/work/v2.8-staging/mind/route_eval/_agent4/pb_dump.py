# -*- coding: utf-8 -*-
import json, io
PB = r"C:\Users\cinde\rd-staging\v2.8\mind\playbooks.json"
pb = json.load(io.open(PB, encoding="utf-8-sig"))["playbooks"]
items = pb if isinstance(pb, list) else [dict(v, id=v.get("id", k)) for k, v in pb.items()]
print(len(items), "playbooks; keys:", sorted(items[0].keys()))
for p in items:
    t = p.get("triggers")
    if isinstance(t, list):
        t = " | ".join(map(str, t))
    print("## %s | ar=%s | en=%s\n   T: %s" % (p.get("id"), p.get("ar"), p.get("en"), t))
