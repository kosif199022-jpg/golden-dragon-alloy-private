import unittest
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import rose_white_native as w

class WhiteNativeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.db=self.root/"queue.sqlite"
    def add(self):
        return w.enqueue(self.db,"motion-ease",{"name":"linear","samples":3})["id"]
    def test_real_execution_and_persistence(self):
        jid=self.add()
        self.assertEqual(w.work_one(self.db)["state"],"done")
        self.assertEqual(w.result(self.db,jid)["result"]["samples"],[0,.5,1])
        self.assertEqual(w.listing(self.db)["counts"],{"done":1})
    def test_concurrent_claim(self):
        jid=self.add()
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs=list(pool.map(lambda _:w.claim(self.db),range(2)))
        self.assertEqual(sum(j is not None for j in jobs),1)
    def test_recovery_and_stale_claim(self):
        jid=self.add(); old=w.claim(self.db,now=100)
        self.assertEqual(w.recover(self.db,now=401)["requeued"],1)
        new=w.claim(self.db,now=402)
        self.assertFalse(w.finish(self.db,jid,old["token"],result={"bad":1}))
        self.assertTrue(w.finish(self.db,jid,new["token"],result={"ok":True}))
    def test_retry_limit(self):
        jid=self.add()
        for i in range(3):
            w.claim(self.db,now=i*400); w.recover(self.db,now=i*400+301)
        self.assertEqual(w.result(self.db,jid)["state"],"failed")
    def test_refuse_write_operations(self):
        with self.assertRaises(ValueError):w.enqueue(self.db,"dua-render",{})
        self.assertFalse(self.db.exists())
    def test_no_implicit_db_creation(self):
        self.assertEqual(w.listing(self.db)["counts"],{})
        self.assertFalse(self.db.exists())
    def test_verify_and_escape(self):
        work=self.root/"work";work.mkdir();(work/"a.txt").write_bytes(b"hello")
        r=w.verify_outputs(work,["a.txt"])
        self.assertEqual(r["files"][0]["sha256"],"2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824")
        (self.root/"secret.txt").write_text("dummy")
        with self.assertRaises(ValueError):w.verify_outputs(work,["../secret.txt"])
    def test_pairs(self):
        self.assertTrue(w.check_pairs([{"type":"call","id":"1"},{"type":"result","id":"1"}])["ok"])
        self.assertFalse(w.check_pairs([{"type":"call","id":"1"},{"type":"result","id":"2"}])["ok"])
    def test_compare(self):
        self.assertEqual(w.compare([{"id":"b","score":1},{"id":"a","score":1}])["winners"],["a","b"])
    def test_failed_job(self):
        jid=w.enqueue(self.db,"motion-ease",{"name":"linear","samples":0})["id"]
        self.assertEqual(w.work_one(self.db)["state"],"failed")
        self.assertIsNotNone(w.result(self.db,jid)["error"])
