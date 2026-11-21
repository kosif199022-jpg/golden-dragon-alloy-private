from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path
from alloy_fusion import import_alloy, find_fused, stats_fused

class AlloyFusionTests(unittest.TestCase):
    def create_source(self, folder):
        path = Path(folder)/'alloy.db'
        with closing(sqlite3.connect(path)) as db, db:
            db.execute('CREATE TABLE units(id TEXT,kind TEXT,title TEXT,summary TEXT,path TEXT,license TEXT,status TEXT,origin TEXT,body BLOB)')
            db.executemany('INSERT INTO units VALUES(?,?,?,?,?,?,?,?,?)', [
                ('a','road','Motion principle','keyframe trajectories','ref/motion.md','owner','active','owner',b'private body not copied'),
                ('b','memory','Owner memory','do not copy me','owner-memory/log.md','owner','private','owner',b'memory'),
                ('c','skill','API','api_key=AAAAAAAAAAAAAAAA','skills/c.md','mit','active','owner',b'secret'),
                ('d','tool','Metadata only','licensed geometry techniques','tools/a.md','unknown','active','third-party',b'licensed bytes'),
                ('e','skill','Run this','suspicious program','tools/b.py','mit','quarantined','third-party',b'executable')])
        return path
    def test_filter_and_knowledge_search(self):
        with tempfile.TemporaryDirectory() as td:
            source = self.create_source(td)
            with closing(sqlite3.connect(':memory:')) as db, db:
                r=import_alloy(db,source)
                self.assertEqual(r['imported'],2)
                self.assertEqual(r['excluded'],3)
                self.assertEqual(r['private_copied'],0)
                self.assertEqual(len(find_fused(db,'geometry')),1)
                self.assertEqual(stats_fused(db)['total'],2)
                self.assertEqual(db.execute('SELECT COUNT(*) FROM fused_knowledge WHERE summary LIKE ?',('%private body%',)).fetchone()[0],0)
                self.assertEqual(import_alloy(db,source)['imported'],0)
    def test_bad_schema(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'bad.sqlite'
            with closing(sqlite3.connect(p)) as db, db:db.execute('CREATE TABLE units(a)')
            with closing(sqlite3.connect(':memory:')) as db, db:
                with self.assertRaises(ValueError):import_alloy(db,p)
    def test_missing(self):
        with closing(sqlite3.connect(':memory:')) as db, db:
            with self.assertRaises(FileNotFoundError):import_alloy(db,'/not/a/real/path')
    def test_sql_wildcard_literal(self):
        with tempfile.TemporaryDirectory() as td:
            source=self.create_source(td)
            with closing(sqlite3.connect(':memory:')) as db, db:
                import_alloy(db,source)
                self.assertEqual(find_fused(db,'%'),[])
    def test_limit_validation(self):
        with tempfile.TemporaryDirectory() as td:
            src=self.create_source(td)
            with closing(sqlite3.connect(':memory:')) as db, db:
                with self.assertRaises(ValueError):import_alloy(db,src,0)
if __name__=='__main__':unittest.main()
