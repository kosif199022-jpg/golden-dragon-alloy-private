import unittest
from rose_see_native_v52 import native_gate

class SeeV53(unittest.TestCase):
    def test_arabic_facts(self):
        r=native_gate("fact-check",{"before":"الرصيد ١٠٠ ريال","after":"الرصيد 100 ريال"})
        self.assertTrue(r["ok"]);self.assertFalse(r["semantic_verification"])
    def test_changed_amount(self):
        r=native_gate("fact-check",{"before":"100 SAR","after":"110 SAR"})
        self.assertFalse(r["ok"]);self.assertEqual(r["dropped"][0]["value"],"100")
    def test_graph(self):
        g={"nodes":[{"id":"a","source_file":"a.py"},{"id":"b","source_file":"b.py"},{"id":"c","source_file":"c.py"}],"links":[{"source":"a","target":"b","confidence":"EXTRACTED"},{"source":"b","target":"c","confidence":"INFERRED"}]}
        r=native_gate("graph-impact",{"graph":g,"path":"a.py","depth":1})
        self.assertTrue(r["ok"]);self.assertEqual(r["reachable_nodes"],2);self.assertFalse(r["runtime_verified"])
    def test_graph_depth(self):
        with self.assertRaises(ValueError):native_gate("graph-impact",{"graph":{},"path":"a.py","depth":99})
    def test_contract_invalid(self):
        self.assertFalse(native_gate("contract",{"verified":True})["ok"])
    def test_contract_reported(self):
        r=native_gate("contract",{"status":"success","summary":"test","owner":"local","evidence":["file"],"artifacts":[],"next_actions":[],"retryable":False,"verified":True})
        self.assertTrue(r["ok"]);self.assertFalse(r["independently_verified"])
    def test_lesson_consent(self):
        p={"record":{"project_id":"rose","trigger":"error","action":"test","evidence":"fixture","observed_at":"2026-11-25"},"consent":False}
        self.assertFalse(native_gate("lesson-proposal",p)["ok"])
        p["consent"]=True
        r=native_gate("lesson-proposal",p)
        self.assertTrue(r["ok"]);self.assertFalse(r["saved"]);self.assertFalse(r["applied"])
    def test_global_lesson_block(self):
        r=native_gate("lesson-proposal",{"record":{"project_id":"rose","trigger":"error","action":"test","evidence":"fixture","observed_at":"2026-11-25","scope":"global"},"consent":True})
        self.assertFalse(r["ok"])
