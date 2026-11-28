import unittest, tempfile, hashlib, itertools, copy
from pathlib import Path
from rose_mind_v62 import experiments,diagnose,acceptance,profile
def experiment_job():
    return {"hypotheses":[{"id":"a","mechanism":"timeout","falsifier":"complete frames"},{"id":"b","mechanism":"encode failure","falsifier":"valid prefix"},{"id":"c","mechanism":"missing asset","falsifier":"valid asset"}],
    "budget":5,"tests":[{"id":"probe","method":"count frames","controlled_variable":"same input","cost":1,"safe":True,"predictions":{"a":"partial","b":"invalid","c":"missing"}},{"id":"retry","method":"retry","controlled_variable":"same timeout","cost":4,"safe":True,"predictions":{"a":"partial","b":"partial","c":None}},{"id":"unsafe","method":"delete cache","controlled_variable":"cache","cost":.1,"safe":False,"predictions":{"a":"yes","b":"no","c":"other"}}]}
def failure():
    return {"symptom":"missing frames","boundaries":[{"id":"source","status":"pass","evidence":"probe"},{"id":"encoder","status":"fail","evidence":"exit 1"}],"reproduced":True,"root_cause_evidenced":True}
class Mind62Tests(unittest.TestCase):
    def test_discrimination(self):
        r=experiments(experiment_job());self.assertEqual(r["recommended_test"],"probe");self.assertEqual(r["ranked"][0]["pair_coverage"],1);self.assertEqual(r["ranked"][1]["pair_coverage"],0);self.assertFalse(r["execution_allowed"])
    def test_unsafe(self):
        r=experiments(experiment_job());self.assertEqual(r["excluded"][0]["id"],"unsafe")
    def test_budget(self):
        j=experiment_job();j["budget"]=.5;self.assertIsNone(experiments(j)["recommended_test"])
    def test_incomplete_prediction(self):
        j=experiment_job();del j["tests"][0]["predictions"]["c"]
        with self.assertRaises(ValueError):experiments(j)
    def test_permutation_invariance(self):
        j=experiment_job();r=experiments(j)
        for p in itertools.permutations(j["hypotheses"]):
            k=copy.deepcopy(j);k["hypotheses"]=list(p);self.assertEqual(experiments(k)["ranked"],r["ranked"])
    def test_duplicate(self):
        j=experiment_job();j["hypotheses"][1]["id"]="a"
        with self.assertRaises(ValueError):experiments(j)
    def test_missing_root(self):
        j=failure();j["root_cause_evidenced"]=False;self.assertEqual(diagnose(j)["next_action"],"collect_diagnostic_evidence")
    def test_upstream_unknown(self):
        j=failure();j["boundaries"][0]["status"]="unknown";self.assertTrue(diagnose(j)["earlier_unknown"]);self.assertEqual(diagnose(j)["next_action"],"collect_diagnostic_evidence")
    def test_red_green(self):
        j=failure();self.assertEqual(diagnose(j)["next_action"],"create_failing_regression");j["regression_test_fails_before"]=True;self.assertEqual(diagnose(j)["next_action"],"propose_single_fix_and_retest");j["regression_test_passes_after"]=True;self.assertEqual(diagnose(j)["next_action"],"review_fresh_verification")
    def test_retry_stop(self):
        j=failure();j["attempts"]=[{"id":str(i),"result":"failed","change":"one variable","evidence":"failed test"} for i in range(3)];self.assertEqual(diagnose(j)["next_action"],"review_architecture")
    def test_acceptance(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/"result.txt").write_text("verified output")
            digest=hashlib.sha256((p/"result.txt").read_bytes()).hexdigest()
            j={"workspace":td,"run_id":"run2","required":["test","visual"],"receipts":[{"id":"test","run_id":"run2","status":"pass","file":"result.txt","sha256":digest}]}
            self.assertFalse(acceptance(j)["ok"])
            j["receipts"].append(dict(j["receipts"][0],id="visual"))
            self.assertTrue(acceptance(j)["ok"]);self.assertFalse(acceptance(j)["semantic_verified"])
            j["receipts"][1]["run_id"]="old";self.assertFalse(acceptance(j)["ok"])
            j["receipts"][1]["run_id"]="run2";(p/"result.txt").write_text("changed");self.assertFalse(acceptance(j)["ok"])
    def test_escape(self):
        with tempfile.TemporaryDirectory() as td:
            j={"workspace":td,"run_id":"run","required":["a"],"receipts":[{"id":"a","status":"pass","run_id":"run","file":"../outside","sha256":"a"*64}]}
            with self.assertRaises(ValueError):acceptance(j)
    def test_profile(self):
        self.assertFalse(profile(1)["enabled"]);self.assertTrue(profile(2)["enabled"])
if __name__=="__main__":unittest.main()
