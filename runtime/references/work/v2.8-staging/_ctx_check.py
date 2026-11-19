"""Run the staging mind/route_ctx_tests.json against any rd.py (argv[1] = scripts dir): proves the tests can fail."""
import importlib.util, json, os, sys, tempfile
from pathlib import Path
os.environ["RED_DRAGON_HOME"] = tempfile.mkdtemp(prefix="rd-cc-")
spec = importlib.util.spec_from_file_location("rdc", Path(sys.argv[1]) / "rd.py")
rd = importlib.util.module_from_spec(spec); sys.argv = [sys.argv[0]]; spec.loader.exec_module(rd)
ct = json.loads((Path(__file__).parent / "mind" / "route_ctx_tests.json").read_text(encoding="utf-8"))
bad = 0
for c in ct:
    pb, _ = rd.route(rd.understand(c["q"])["text"], prev=rd.understand(c["prev"])["text"])
    got = pb[0][1]["id"] if pb else "none"
    fail = ("want" in c and got != c["want"]) or got == c.get("not")
    bad += fail
    print("✗" if fail else "✓", f"«{c['prev'][:25]}» ← «{c['q'][:35]}» → {got}")
print(f"{rd.VERSION}: ctx {len(ct)} · failures {bad}")
