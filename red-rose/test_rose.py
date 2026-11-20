import tempfile, unittest, io, contextlib, json
from pathlib import Path
from rose import main
class RoseTests(unittest.TestCase):
 def test_persistent_memory(self):
  with tempfile.TemporaryDirectory() as d:
   db=str(Path(d)/'rose.db')
   with contextlib.redirect_stdout(io.StringIO()) as out: main(['--db',db,'remember','اختبار الذاكرة'])
   self.assertTrue(json.loads(out.getvalue())['saved'])
   with contextlib.redirect_stdout(io.StringIO()) as out: main(['--db',db,'recall','اختبار'])
   self.assertEqual(len(json.loads(out.getvalue())),1)
 def test_plan_status(self):
  with contextlib.redirect_stdout(io.StringIO()) as out: main(['plan','ارسم وردة'])
  self.assertEqual(json.loads(out.getvalue())['status'],'planned_not_executed')
if __name__=='__main__': unittest.main()
