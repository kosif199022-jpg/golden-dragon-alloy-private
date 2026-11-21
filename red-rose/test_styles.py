import sqlite3, unittest
from contextlib import closing
from styles import save, load, list_styles
from rose import ingest, connect
from pathlib import Path
from tempfile import TemporaryDirectory

class StyleTests(unittest.TestCase):
    def test_save_and_recall_style(self):
        with closing(sqlite3.connect(':memory:')) as db:
            save(db,'صلصال سينمائي',{'palette':['#AABBCC'],'fps':30,'lighting':'soft'})
            self.assertEqual(load(db,'صلصال سينمائي')['recipe']['fps'],30)
            self.assertEqual(list_styles(db),['صلصال سينمائي'])
    def test_update_style(self):
        with closing(sqlite3.connect(':memory:')) as db:
            save(db,'أ',{'fps':24});save(db,'أ',{'fps':60})
            self.assertEqual(load(db,'أ')['recipe']['fps'],60)
    def test_invalid_style(self):
        with closing(sqlite3.connect(':memory:')) as db:
            with self.assertRaises(ValueError): save(db,'',{'a':1})
    def test_skip_secrets_and_owner_memory(self):
        with TemporaryDirectory() as temp:
            db=connect(Path(temp)/'test.db')
            root=Path(temp)
            (root/'public.md').write_text('safe content')
            (root/'.env').write_text('TOKEN=secret')
            (root/'owner-memory').mkdir()
            (root/'owner-memory'/'journal.json').write_text('private memory')
            result=ingest(db,root)
            self.assertEqual(result['imported'],1)
            self.assertEqual(result['unreadable'],1)
            self.assertEqual(db.execute('SELECT count(*) FROM knowledge').fetchone()[0],1)
            db.close()
