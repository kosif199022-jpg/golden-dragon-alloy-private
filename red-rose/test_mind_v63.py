import unittest,copy
from rose_mind_v63 import schedule,decision,risks
def task(k,d,deps):
 return {"id":k,"duration":d,"depends_on":deps,"deliverable":k+" output","acceptance":"verified"}
def project():
 return {"tasks":[task("A",3,[]),task("B",5,["A"]),task("C",2,["A"]),task("D",4,["B","C"])]}
def choices():
 return {"criteria":[{"id":"quality","weight":3},{"id":"speed","weight":1}],"required":["rights"],"alternatives":[{"id":"A","gates":{"rights":True},"scores":{"quality":[90,100],"speed":70}},{"id":"B","gates":{"rights":True},"scores":{"quality":70,"speed":90}},{"id":"C","gates":{"rights":False},"scores":{"quality":100,"speed":100}}]}
def risk():
 return {"risks":[{"id":"data","likelihood":1,"impact":5,"failure":"lost data","trigger":"missing backup","owner":"reviewer","status":"open"}]}
class Mind63Tests(unittest.TestCase):
 def test_schedule(self):
  r=schedule(project());self.assertEqual(r["duration_lower_bound"],12);self.assertEqual(r["critical_path"],["A","B","D"]);self.assertEqual(r["total_work"],14);self.assertEqual(r["dependency_layers"],[["A"],["B","C"],["D"]]);self.assertEqual(next(x["slack"] for x in r["tasks"] if x["id"]=="C"),3)
 def test_order_invariance(self):
  j=project();r=schedule(j);j["tasks"].reverse();self.assertEqual(schedule(j),r)
 def test_cycle(self):
  j=project();j["tasks"][0]["depends_on"]=["D"]
  with self.assertRaises(ValueError):schedule(j)
 def test_missing_dep(self):
  j=project();j["tasks"][0]["depends_on"]=["missing"]
  with self.assertRaises(ValueError):schedule(j)
 def test_duplicate(self):
  j=project();j["tasks"][1]["id"]="A"
  with self.assertRaises(ValueError):schedule(j)
 def test_hard_gate(self):
  r=decision(choices());self.assertEqual(r["robust_winner"],"A");self.assertEqual(r["excluded"][0]["id"],"C");self.assertFalse(r["execution_allowed"])
 def test_uncertainty(self):
  j=choices();j["alternatives"][1]["scores"]["quality"]=None;self.assertIsNone(decision(j)["robust_winner"])
 def test_tie(self):
  j=choices();j["alternatives"][1]["scores"]=copy.deepcopy(j["alternatives"][0]["scores"]);self.assertIsNone(decision(j)["robust_winner"])
 def test_unknown_gate(self):
  j=choices();j["alternatives"][0]["gates"]["rights"]=None;self.assertEqual(decision(j)["excluded"][0]["id"],"A")
 def test_incomplete_scores(self):
  j=choices();del j["alternatives"][0]["scores"]["speed"]
  with self.assertRaises(ValueError):decision(j)
 def test_critical_low_probability(self):
  self.assertFalse(risks(risk())["ok"])
 def test_mitigation_evidence(self):
  j=risk();j["risks"][0]["status"]="mitigated";self.assertFalse(risks(j)["ok"]);j["risks"][0]["evidence"]="backup checked";self.assertTrue(risks(j)["ok"]);self.assertFalse(risks(j)["semantic_verified"])
if __name__=="__main__":unittest.main()
