"""Regression tests for the private-machine standalone Alloy importer."""
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from fuse_alloy_v10 import migrate, search

class FusionTests(unittest.TestCase):
    def test_no_private_or_executable_blob_and_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'old.db'
            with closing(sqlite3.connect(source)) as db:
                db.execute('CREATE TABLE units(id,kind,title,summary,path,license,status,origin,body BLOB)')
                db.executemany('INSERT INTO units VALUES(?,?,?,?,?,?,?,?,?)',[
                    ('1','road','Motion','Frame timing','ref/x.md','owner','active','owner',b'dangerous bytes'),
                    ('2','memory','private','identity','owner-memory/a','owner','private','owner',b'secret'),
                    ('3','script','Sensitive','api_key=123456789012345','tools/x.py','mit','active','owner',b'key'),
                    ('4','tool','Physics','gravity simulation','tools/physics.md','mit','active','owner',b'raw code'),
                ])
                db.commit()
            with closing(sqlite3.connect(':memory:')) as db:
                r=migrate(db,source)
                self.assertEqual(r['imported'],2)
                self.assertEqual(r['excluded'],2)
                self.assertEqual(r['private_copied'],0)
                self.assertEqual(migrate(db,source)['imported'],0)
                self.assertEqual(search(db,'gravity')[0]['id'],'4')
                self.assertNotIn('body',[x[1] for x in db.execute('pragma table_info(fused_knowledge)')])
    def test_rejects_unknown_schema(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'old.db'
            with closing(sqlite3.connect(source)) as db:
                db.execute('CREATE TABLE units(id)')
                db.commit()
            with closing(sqlite3.connect(':memory:')) as db:
                with self.assertRaises(ValueError):migrate(db,source)

if __name__=='__main__':
    unittest.main()
