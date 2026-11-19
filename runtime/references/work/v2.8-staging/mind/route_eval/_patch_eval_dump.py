from pathlib import Path
p = Path(__file__).resolve().parent / "route_eval2.py"
c = p.read_text(encoding="utf-8")
assert "--dump" not in c
old = '''    top = ranked[0] if pb and pb[0][0] >= 2 else "none"
    conf = rd.confidence(pb) if hasattr(rd, "confidence") else None
    return top, ranked[:3], conf'''
new = '''    top = ranked[0] if pb and pb[0][0] >= 2 else "none"
    conf = rd.confidence(pb) if hasattr(rd, "confidence") else None
    LASTS[:] = [pb[0][0] if pb else 0.0, pb[1][0] if len(pb) > 1 else 0.0]
    return top, ranked[:3], conf'''
assert c.count(old) == 1
c = c.replace(old, new)
old2 = '''        if conf:
            b = buckets.setdefault(conf, [0, 0])'''
new2 = '''        if dump is not None:
            dump.append({"set": name, "id": r["id"], "s1": LASTS[0], "s2": LASTS[1], "good": bool(good), "top": top})
        if conf:
            b = buckets.setdefault(conf, [0, 0])'''
assert c.count(old2) == 1
c = c.replace(old2, new2)
old3 = "TEST_KEYS = set()\n"
new3 = "TEST_KEYS = set()\nLASTS = [0.0, 0.0]\ndump = [] if \"--dump\" in args else None\n"
assert c.count(old3) == 1
c = c.replace(old3, new3)
old4 = '''for s in (["old", "fresh"] if which == "both" else [which]):
    run(s)'''
new4 = '''for s in (["old", "fresh"] if which == "both" else [which]):
    run(s)
if dump is not None:
    Path(opt("--dump", "dump.json")).write_text(json.dumps(dump), encoding="utf-8")'''
assert c.count(old4) == 1
c = c.replace(old4, new4)
p.write_text(c, encoding="utf-8")
print("patched")
