# -*- coding: utf-8 -*-
import json, io
d = json.load(io.open("proposals_triggers.json", encoding="utf-8"))
odd = [r for v in d.values() for r in v["evidence_dev_ids"] if int(r.split(":")[1]) % 2]
mx = max(len(v["add"].split()) + len(v["phrases"]) for v in d.values())
print("plans", len(d), "| odd refs:", odd, "| max terms per plan:", mx, "| no-evidence plans:", [k for k, v in d.items() if not v["evidence_dev_ids"]])
for k, v in d.items():
    print(k, "|", v["add"], "|", " ; ".join(v["phrases"]), "|", len(v["evidence_dev_ids"]))
