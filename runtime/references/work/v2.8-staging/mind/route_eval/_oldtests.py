"""route_tests.json + understand_tests.json against the staging rd.py (with an empty machine memory)."""
import importlib.util, json, os, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
os.environ["RED_DRAGON_HOME"] = tempfile.mkdtemp(prefix="rd-ot-")
spec = importlib.util.spec_from_file_location("rdo", Path(sys.argv[1]) / "rd.py" if len(sys.argv) > 1 else HERE.parent.parent / "scripts" / "rd.py")
rd = importlib.util.module_from_spec(spec); sys.argv = [sys.argv[0]]; spec.loader.exec_module(rd)
bad = 0
rt = json.loads((rd.MIND / "route_tests.json").read_text(encoding="utf-8"))
for q, want in rt.items():
    pb, _ = rd.route(rd.understand(q)["text"])
    got = pb[0][1]["id"] if pb else "none"
    if got != want:
        bad += 1
        print(f"ROUTE ✗ «{q[:60]}» → {got}, want {want}")
ct = json.loads((rd.MIND / "route_ctx_tests.json").read_text(encoding="utf-8")) if (rd.MIND / "route_ctx_tests.json").is_file() else []
for c in ct:
    pb, _ = rd.route(rd.understand(c["q"])["text"], prev=rd.understand(c["prev"])["text"])
    got = pb[0][1]["id"] if pb else "none"
    if ("want" in c and got != c["want"]) or got == c.get("not"):
        bad += 1
        print(f"CTX ✗ «{c['prev'][:30]} ← {c['q'][:40]}» → {got}, want {c.get('want') or 'not ' + str(c.get('not'))}")
ut = json.loads((rd.MIND / "understand_tests.json").read_text(encoding="utf-8"))
for raw, want in ut.items():
    got = rd.understand(raw)["text"]
    if got != want:
        bad += 1
        print(f"UNDERSTAND ✗ «{raw[:50]}» → «{got[:60]}», want «{want[:60]}»")
print(f"{rd.VERSION}: route {len(rt)} · ctx {len(ct)} · understand {len(ut)} · failures {bad}")
