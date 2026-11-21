from contextlib import closing
import sqlite3,unittest
from alloy_fusion import init
from knowledge_router import route
class RouterTests(unittest.TestCase):
 def test_road_relevant(self):
  with closing(sqlite3.connect(':memory:')) as db, db:
   init(db)
   rows=[('road:motion','road','motion design','Animation timing','owner','owner','ref.md','active','a','now'),
         ('tool:sql','tool','SQL databases','database indexing','owner','owner','db.md','active','b','now')]
   db.executemany('INSERT INTO fused_knowledge VALUES(?,?,?,?,?,?,?,?,?,?)',rows)
   r=route(db,'motion animation')
   self.assertEqual(r['references'][0]['id'],'road:motion')
   self.assertEqual(r['status'],'reference_retrieved_not_executed')
 def test_empty_db(self):
  with closing(sqlite3.connect(':memory:')) as db, db:
   self.assertEqual(route(db,'motion')['references'],[])
 def test_invalid(self):
  with closing(sqlite3.connect(':memory:')) as db, db:
   with self.assertRaises(ValueError):route(db,'')
 def test_query_escaping(self):
  with closing(sqlite3.connect(':memory:')) as db, db:
   self.assertEqual(route(db,'100%')['references'],[])
if __name__=='__main__': unittest.main()
