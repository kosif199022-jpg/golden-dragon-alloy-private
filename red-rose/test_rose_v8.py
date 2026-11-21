import tempfile, unittest
from contextlib import closing
from pathlib import Path
from rose_v8 import dbopen, ingest, figure, storyboard
class RoseV8Tests(unittest.TestCase):
 def test_figure_changes(self):
  self.assertNotEqual(figure(0),figure(.25))
 def test_invalid_size(self):
  with self.assertRaises(ValueError): figure(0,0,100)
 def test_memory_and_knowledge(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/"lesson.md").write_text("useful learning")
   (root/"secret.env").write_text("password=hidden")
   with closing(dbopen(root/"db.sqlite")) as db:
    self.assertEqual(ingest(db,root),1)
    self.assertEqual(ingest(db,root),0)
    self.assertEqual(db.execute("select count(*) from knowledge").fetchone()[0],1)
 def test_storyboard(self):
  with tempfile.TemporaryDirectory() as d:
   self.assertEqual(storyboard(d,[{"seconds":1}],12),12)
   self.assertEqual(len(list(Path(d).glob("frame_*.svg"))),12)
if __name__=="__main__":unittest.main()
