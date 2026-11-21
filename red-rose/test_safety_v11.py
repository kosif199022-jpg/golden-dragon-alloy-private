from pathlib import Path
from contextlib import closing
import sqlite3,tempfile,unittest
from rose import connect,ingest
class SafetyV11Tests(unittest.TestCase):
 def test_secrets_not_imported(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d); (p/'good.md').write_text('safe notes')
   (p/'token.txt').write_text('api_key=12345678901234567890')
   (p/'.env').write_text('secret content')
   with closing(connect(p/'test.sqlite')) as db:
    r=ingest(db,p)
    self.assertEqual(r['imported'],1)
    self.assertEqual(db.execute('SELECT count(*) FROM knowledge').fetchone()[0],1)
 def test_source_db_intact(self):
  from alloy_fusion import import_alloy
  with tempfile.TemporaryDirectory() as d:
   source=Path(d)/'source.db'
   with closing(sqlite3.connect(source)) as db,db:
    db.execute('CREATE TABLE units(id TEXT,kind TEXT,title TEXT,summary TEXT,path TEXT,license TEXT,status TEXT,origin TEXT)')
    db.execute("INSERT INTO units VALUES ('x','road','A','safe summary','ref/a.md','owner','active','owner')")
   before=source.read_bytes()
   with closing(sqlite3.connect(':memory:')) as db:import_alloy(db,source)
   self.assertEqual(source.read_bytes(),before)
