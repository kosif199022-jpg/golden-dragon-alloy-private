import contextlib,io,json,tempfile,unittest
from pathlib import Path
from rose import main
class Tests(unittest.TestCase):
 def run_cli(self,*args):
  with contextlib.redirect_stdout(io.StringIO()) as out:main(list(args))
  return json.loads(out.getvalue())
 def test_memory_persists(self):
  with tempfile.TemporaryDirectory() as d:
   db=str(Path(d)/'db.sqlite');self.run_cli('--db',db,'remember','درس جديد');self.assertEqual(self.run_cli('--db',db,'recall','درس')[0]['content'],'درس جديد')
 def test_ingest_search_and_dedup(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'note.md').write_text('الفيزياء والمونتاج',encoding='utf8');db=str(p/'db.sqlite')
   self.assertEqual(self.run_cli('--db',db,'ingest',d)['imported'],1)
   self.assertEqual(self.run_cli('--db',db,'ingest',d)['imported'],0)
   self.assertEqual(self.run_cli('--db',db,'search','الفيزياء')[0]['source'],'note.md')
 def test_plan_honesty(self):self.assertEqual(self.run_cli('plan','تصميم')['status'],'planned_not_executed')
if __name__=='__main__':unittest.main()
