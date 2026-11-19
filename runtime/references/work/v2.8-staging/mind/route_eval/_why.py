"""Why did the router pick that? python -I -X utf8 _why.py "<request>" ["<prev>"]"""
import importlib.util, os, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
os.environ["RED_DRAGON_HOME"] = tempfile.mkdtemp(prefix="rd-why-")
spec = importlib.util.spec_from_file_location("rdw", HERE.parent.parent / "scripts" / "rd.py")
rd = importlib.util.module_from_spec(spec); q = sys.argv[1]; prev = sys.argv[2] if len(sys.argv) > 2 else None
sys.argv = [sys.argv[0]]; spec.loader.exec_module(rd)
u = rd.understand(q)["text"]
pbs = rd.playbooks(); idf = rd._route_idf(pbs); tr = rd.translit()
t = rd.norm(u).strip()
qp = [w for w in rd.tokens(u) if w not in rd.QSTOP]
print("understood:", u[:150]); print("words:", qp)
for p in pbs:
    parts = []
    for w in qp:
        best, bk = 0.0, ""
        for v in [w] + tr.get(w, []):
            for k in p["_tok"]:
                m = rd._tmatch(v, k)
                if m and m * idf.get(k, 1.0) > best:
                    best, bk = m * idf.get(k, 1.0), k
        if best:
            parts.append(f"{w}~{bk}:{best:.1f}")
    it = [f"INTENT+{b}" for rx, pid, b in rd.INTENT if pid == p["id"] and __import__("re").search(rx, t)]
    ph = [f"PH:{x}" for x in p.get("_ph", ()) if x in t]
    if parts or it or ph:
        print(f"  {p['id']:<16} " + " ".join(parts + it + ph))
for s, r in rd.ex_near(t):
    print(f"  EX {s:.2f} {r['pb']:<14} {r['src']:<8} {r['q'][:70]}")
pb, _ = rd.route(u, prev=rd.understand(prev)["text"] if prev else None)
print("ROUTE:", [(p["id"], round(s, 1)) for s, p in pb], rd.confidence(pb))
