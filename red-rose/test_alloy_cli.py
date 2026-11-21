from contextlib import closing
import contextlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from rose import main

class AlloyCLITests(unittest.TestCase):
    def runcli(self,*args):
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            main(list(args))
        return json.loads(buf.getvalue())
    def test_cli_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            old=Path(tmp)/'alloy.db'; new=Path(tmp)/'red-rose.sqlite'
            with closing(sqlite3.connect(old)) as db, db:
                db.execute('CREATE TABLE units(id,kind,title,summary,origin,license,status,path)')
                db.execute('INSERT INTO units VALUES(?,?,?,?,?,?,?,?)',('id1','road','Timeline motion','keyframes','owner','owner','active','notes.md'))
            r=self.runcli('--db',str(new),'fuse-alloy',str(old))
            self.assertEqual(r['imported'],1)
            self.assertEqual(self.runcli('--db',str(new),'fuse-stats')['total'],1)
            self.assertEqual(self.runcli('--db',str(new),'fuse-search','keyframes')[0]['id'],'id1')
if __name__=='__main__':unittest.main()
