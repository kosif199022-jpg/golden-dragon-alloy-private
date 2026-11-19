"""Reproduce e2e failure 2 on the staging rd.py with a throwaway HOME, and print the raw scores."""
import json, os, sys, tempfile, importlib.util
from pathlib import Path

HOME = tempfile.mkdtemp(prefix="rd-dbg-")
os.environ["RED_DRAGON_HOME"] = HOME
spec = importlib.util.spec_from_file_location("rd", str(Path(__file__).parent / "scripts" / "rd.py"))
rd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rd)

seq = ["[فريق الوكلاء: 500 وكيل]\nاعمل مونتاج ريلز للخطبة بالفيديو اللي في المجلد", "اعمل مونتاج", "كمل", "هل خلصت ولا لسه", "ازيك يا تنين عامل ايه"]
for q in seq:
    b = rd.brief(q)
    print(f"{q[:40]!r:45} -> {b['playbook']} ({b['confidence']}) ctx={b['used_context']}")
lt = rd.last_turn()
print("topic:", {k: round(v, 2) for k, v in sorted((lt.get("topic") or {}).items(), key=lambda x: -x[1])[:5]})
rd.teach("رتب لي الصور دي في فولدرات حسب التاريخ", "pc-task") if hasattr(rd, "teach") else None
q = "رتب لي الصور دي في فولدرات حسب التاريخ"
s, kind = rd._pb_scores(q, rd.playbooks())
print("raw:", kind, {k: round(v, 2) for k, v in sorted(s.items(), key=lambda x: -x[1])[:5]})
print("ex_near:", [(round(sc, 2), r["pb"]) for sc, r in rd.ex_near(rd.norm(q).strip())[:4]])
pb, _ = rd.route(q, prev=rd._topic_for(q, rd.last_turn()))
print("route:", [(p["id"], round(sc, 2)) for sc, p in pb[:4]])
