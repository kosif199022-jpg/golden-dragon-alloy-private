import unittest
from rose_metacognition_v54 import review, calibration, protocol

def alt(name, u=.8, passed=True):
    return {"id":name,"constraints_passed":passed,"assumptions":[],
            "scenarios":[{"id":"base","probability":1,"utility":u,"evidence":"test:1"}]}

class TestMetacognitionV54(unittest.TestCase):
    def test_ranking(self):
        self.assertEqual(review({"alternatives":[alt("a"),alt("b",.3)]})["candidate"],"a")
    def test_switch_after_failure(self):
        r=review({"alternatives":[alt("a"),alt("b",.3)],"attempts":[{"id":"a","outcome":"failed","evidence":"test:failed"}]})
        self.assertEqual(r["candidate"],"b")
        self.assertFalse(r["execution_allowed"])
    def test_budget(self):
        r=review({"alternatives":[alt("a")],"budget":1,"attempts":[{"id":"a","outcome":"inconclusive","evidence":"test:1"}]})
        self.assertEqual(r["decision"],"stop_budget")
        self.assertIsNone(r["candidate"])
    def test_constraint(self):
        self.assertEqual(review({"alternatives":[alt("a",passed=False)]})["decision"],"stop_no_eligible")
    def test_premortem(self):
        self.assertEqual(review({"alternatives":[alt("a",-.5)]})["decision"],"seek_evidence")
    def test_tie(self):
        self.assertEqual(review({"alternatives":[alt("a"),alt("b")]})["decision"],"seek_evidence")
    def test_missing_evidence(self):
        a=alt("a");del a["scenarios"][0]["evidence"]
        self.assertEqual(review({"alternatives":[a]})["decision"],"seek_evidence")
    def test_bad_probability(self):
        a=alt("a");a["scenarios"][0]["probability"]=.5
        with self.assertRaises(ValueError):review({"alternatives":[a]})
    def test_calibration(self):
        r=calibration({"observations":[{"id":"a","prediction":.5,"observed":True,"evidence":"test:1"}]})
        self.assertEqual(r["brier_score"],.25)
        self.assertEqual(r["confidence_bias"],-.5)
        self.assertFalse(r["independently_verified"])
    def test_fast_lane(self):
        self.assertFalse(protocol(1)["enabled"])
        self.assertTrue(protocol(2)["enabled"])
    def test_reject_nan_and_duplicates(self):
        with self.assertRaises(ValueError):review({"alternatives":[alt("a",float("nan"))]})
        with self.assertRaises(ValueError):review({"alternatives":[alt("a"),alt("a")]})

if __name__=="__main__":unittest.main()
