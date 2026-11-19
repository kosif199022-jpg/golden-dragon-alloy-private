import importlib.util,sys,unittest
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"engine/skills/hypit-run/scripts/hypit_guard.py"
spec=importlib.util.spec_from_file_location("hypit_guard",P)
mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
FREE="x (@hypit/provider-html-local) · local, no Provider charge"
PAID="x (@hypit/provider-hypihub) · $0.4 per request"
class GateTests(unittest.TestCase):
 def test_free(self): self.assertTrue(mod.assess_plan(FREE).safe)
 def test_paid(self): self.assertFalse(mod.assess_plan(FREE+"\n"+PAID).safe)
 def test_empty(self): self.assertFalse(mod.assess_plan("").safe)
 def test_missing_price(self): self.assertFalse(mod.assess_plan("x (@hypit/provider-x) · unknown").safe)
 def test_failed_exit(self): self.assertFalse(mod.assess_plan(FREE,1).safe)
 def test_preflight(self): self.assertFalse(mod.assess_plan(FREE+"\n × browser error").safe)
 def test_quantity(self): self.assertTrue(mod.assess_plan(FREE+"\n ×1 width 540").safe)
 def test_package(self): self.assertFalse(mod.assess_plan("x (unknown) · local, no Provider charge").safe)
 def test_safe_cli(self): self.assertTrue(mod.cli_is_inspection_only(["plan","x.svrun"]))
 def test_dangerous_cli(self):
  for args in ([],["build","x"],["get","x"],["check","--","build"],["plan","x","--allow-paid"]):
   self.assertFalse(mod.cli_is_inspection_only(args))
if __name__=="__main__": unittest.main()
