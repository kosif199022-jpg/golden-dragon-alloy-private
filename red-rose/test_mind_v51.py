import unittest,tempfile,hashlib
from pathlib import Path
from unittest.mock import patch
import rose_mind_v51 as m

class MindV51(unittest.TestCase):
    def test_source_and_select(self):
        self.assertEqual(len(m.profile()["methods"]),44)
        self.assertEqual(len(m.profile()["protocol_ar"]),8)
        self.assertTrue(any(x["id"]=="constraint-ledger" for x in m.select_methods("بالظبط من غير تغيير","understand",12)))
    def test_depth_and_question_gate(self):
        with patch("rose_agent.brief",return_value={"depth":"L0","route":{"type":"op","id":"demo"},"decision":"run","approvals":[],"kind":"plan"}):
            a=m.plan({"request":"build","unknowns":[{"id":"a","question":"which output?","impact":3,"uncertainty":2},{"id":"b","question":"which color?","impact":1,"uncertainty":1}]})
        self.assertEqual(a["depth"],"L3");self.assertEqual(len(a["stages"]),8)
        self.assertEqual(a["next_question"]["id"],"a");self.assertFalse(a["execution_allowed"])
    def test_short_path(self):
        with patch("rose_agent.brief",return_value={"depth":"L0","route":{"type":"none"},"decision":"none","approvals":[],"kind":"greet"}):
            a=m.plan({"request":"hello"})
        self.assertEqual(len(a["stages"]),2)
        self.assertTrue(a["requires_review"])
    def test_approval_preserved(self):
        with patch("rose_agent.brief",return_value={"depth":"L1","route":{"type":"op"},"decision":"run","approvals":["write"],"kind":"plan"}):
            a=m.plan({"request":"build","external":True})
        self.assertEqual(a["depth"],"L3");self.assertEqual(a["approvals"],["write"])
        self.assertTrue(a["requires_review"])
    def test_actual_router(self):
        a=m.plan({"request":"اعمل ريل دعاء","impact":2,"uncertainty":2})
        self.assertGreaterEqual(int(a["depth"][-1]),2);self.assertIn("base_route",a)
    def test_gate_real_hash_and_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/"e.txt";f.write_bytes(b"evidence")
            h=hashlib.sha256(b"evidence").hexdigest()
            p={"workspace":tmp,"files":["e.txt"],"depth":0,"constraints":[{"id":"a","passed":True}],"checks":[{"stage":m.STAGES[i],"passed":True,"file":"e.txt","sha256":h} for i in (0,7)]}
            self.assertTrue(m.gate(p)["ok"])
            f.write_bytes(b"changed");self.assertFalse(m.gate(p)["ok"])
    def test_missing_evidence_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/"e.txt").write_bytes(b"e")
            a=m.gate({"workspace":tmp,"files":["e.txt"],"constraints":[],"checks":[]})
            self.assertEqual(len(a["blockers"]),8)
    def test_learn_dedup_no_auto_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/"e.txt";f.write_bytes(b"repro")
            db=Path(tmp)/"lessons.sqlite"
            p={"task":"test","workspace":tmp,"file":"e.txt","observation":{"id":"case1","category":"general","severity":"high","recurrences":1,"summary":"reproduced test","reproduced":True,"evidence_sha":hashlib.sha256(b"repro").hexdigest()}}
            self.assertEqual(m.learn(p,db,False)["outcome"],"approval_required");self.assertFalse(db.exists())
            self.assertTrue(m.learn(p,db,True)["saved"])
            self.assertFalse(m.learn(p,db,True)["saved"]);self.assertEqual(len(m.lessons(db)["lessons"]),1)
            f.write_bytes(b"changed")
            with self.assertRaises(ValueError):m.learn(p,db,True)
