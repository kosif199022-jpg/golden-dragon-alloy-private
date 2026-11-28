import unittest,tempfile,hashlib,json
from pathlib import Path
from unittest.mock import patch
import rose_mind_v56 as m

class AbsorptionV56(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.files=["a.txt","b.txt"]
        self.hashes={}
        for i,f in enumerate(self.files):
            b=("test evidence "+str(i)).encode();(self.root/f).write_bytes(b)
            self.hashes[f]=hashlib.sha256(b).hexdigest()
    def test_profile(self):
        p=m.profile()
        self.assertEqual(len(p["methods"]),44);self.assertEqual(len(p["paths"]),7)
        self.assertEqual(len(p["recipes"]),42);self.assertEqual(len(p["bias_checks"]),9)
        self.assertTrue(all(x["steps_ar"] for x in p["methods"]))
        self.assertTrue(p["source_coverage"]["golden_bird_same_library"])
    def test_fast(self):
        with patch.object(m,"profile",side_effect=AssertionError("profile must not load")):
            self.assertFalse(m.enrich("hello",1,[])["enabled"])
    def test_deep(self):
        r=m.enrich("imagine what if",3,[])
        self.assertTrue(r["enabled"]);self.assertEqual(r["minimum_alternatives"],3)
        self.assertTrue(r["procedures"]);self.assertLessEqual(len(r["procedures"]),12)
        self.assertFalse(r["executed"])
    def test_integrated(self):
        import rose_mind_v51 as v
        r=v.plan({"request":"debug code","impact":3,"uncertainty":2})
        self.assertTrue(r["deep_mind"]["enabled"]);self.assertFalse(r["execution_allowed"])
    def test_council(self):
        for n in (3,5,7):
            r=m.council({"domain":"accounting","size":n})
            self.assertEqual(len(r["seats"]),n);self.assertFalse(r["agents_called"])
            self.assertEqual(len({x["lens"] for x in r["seats"]}),n)
    def test_council_bad(self):
        with self.assertRaises(ValueError):m.council({"domain":"fictional","size":3})
    def packet(self):
        seats=m.council({"domain":"software","size":3})["seats"]
        return {"domain":"software","size":3,"workspace":str(self.root),"files":self.files,"dissent":"Different approach still possible","submissions":[dict(x,position="position "+str(i),counterargument="counter",file=self.files[i%2],sha256=self.hashes[self.files[i%2]]) for i,x in enumerate(seats)]}
    def test_council_review(self):
        r=m.council_review(self.packet());self.assertTrue(r["ok"]);self.assertFalse(r["independent_agents_verified"])
    def test_tamper(self):
        p=self.packet();(self.root/"a.txt").write_text("changed")
        self.assertFalse(m.council_review(p)["ok"])
    def test_duplicate_positions(self):
        p=self.packet();p["submissions"][1]["position"]=p["submissions"][0]["position"]
        self.assertFalse(m.council_review(p)["ok"])
    def test_traversal(self):
        p=self.packet();p["files"]=["../escape.txt"]
        with self.assertRaises((ValueError,OSError)):m.council_review(p)
    def hypothesis(self):
        return {"hypotheses":["A","B"],"workspace":str(self.root),"files":self.files,"evidence":[{"file":f,"sha256":self.hashes[f],"weight":1,"ratings":{"A":"support","B":"contradiction"}} for f in self.files]}
    def test_hypotheses(self):
        r=m.hypothesis_compare(self.hypothesis());self.assertEqual(r["candidate_for_review"],"A")
        self.assertFalse(r["semantic_verification"])
    def test_same_evidence(self):
        p=self.hypothesis();p["evidence"][1]=dict(p["evidence"][0])
        with self.assertRaises(ValueError):m.hypothesis_compare(p)
    def test_missing_evidence(self):
        p=self.hypothesis();p["evidence"][0]["ratings"]["A"]="unknown"
        self.assertIsNone(m.hypothesis_compare(p)["candidate_for_review"])
    def test_reference(self):
        r=m.reference_find({"query":"skill","limit":5})
        self.assertTrue(r["matches"]);self.assertTrue(all(x["state"]=="reference_only" for x in r["matches"]))
        self.assertFalse(r["execution_allowed"])

if __name__=="__main__":unittest.main()
