import unittest,tempfile,subprocess,sys,json
from pathlib import Path
import rose_white_native as w

class BatchV56(unittest.TestCase):
    def test_bounded_parallel(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"jobs.sqlite"
            ids=[w.enqueue(db,"motion-ease",{"name":"linear","samples":3})["id"] for _ in range(6)]
            r=w.work_batch(db,limit=4,workers=3)
            self.assertTrue(r["ok"]);self.assertEqual(r["processed"],4);self.assertEqual(r["remaining"],2)
            self.assertEqual(len({x["id"] for x in r["results"]}),4)
            self.assertEqual(w.work_batch(db,limit=4)["processed"],2)
            self.assertTrue(all(w.result(db,i)["state"]=="done" for i in ids))
    def test_invalid_limits(self):
        with self.assertRaises(ValueError):w.work_batch("unused",limit=21)
        with self.assertRaises(ValueError):w.work_batch("unused",workers=0)
    def test_cli_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"q.sqlite"
            cmd=[sys.executable,str(Path(__file__).with_name("rose.py")),"white-native","work-batch","--queue-db",str(db)]
            res=subprocess.run(cmd,capture_output=True,text=True,encoding="utf-8",timeout=30)
            self.assertEqual(res.returncode,3);self.assertFalse(db.exists())
            res=subprocess.run(cmd+["--approve-write"],capture_output=True,text=True,encoding="utf-8",timeout=30)
            self.assertEqual(res.returncode,0);self.assertEqual(json.loads(res.stdout)["processed"],0);self.assertFalse(db.exists())
