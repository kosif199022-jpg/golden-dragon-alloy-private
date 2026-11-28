"""Ensure V29 is usable from the real Red Rose dispatcher without side effects."""
import json
import sqlite3
import unittest
from pathlib import Path
from capability_runtime import REGISTRY, CODED_UNTESTED, execute

ROOT = Path(__file__).resolve().parent


class V29AdapterTests(unittest.TestCase):
    def test_real_registry_is_read_only_and_registered(self):
        self.assertIn("intelligence.director", REGISTRY)
        self.assertEqual(REGISTRY["intelligence.director"][1], "read")
        self.assertNotIn("intelligence.director", CODED_UNTESTED)
        self.assertEqual(len(REGISTRY),65)

    def test_real_dispatch_with_audit_receipt(self):
        db=sqlite3.connect(":memory:")
        try:
            out=execute(db,"intelligence.director",{"op":"storyboard_plan","params":{
                "goal":"مقطع قصير","seconds":10,"fps":24,"style":"reel"
            }})
            self.assertEqual(out["status"],"executed")
            self.assertEqual(out["effect"],"read")
            self.assertFalse(out["legacy_runtime_called"])
            self.assertEqual(out["result"]["total_frames"],240)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM capability_execution_audit").fetchone()[0],1)
        finally:
            db.close()

    def test_whitelist_blocks_untrusted_shell_args(self):
        with sqlite3.connect(":memory:") as db:
            with self.assertRaises(ValueError):
                execute(db,"intelligence.director",{"op":"decision_review","params":{
                    "goal":"test","options":[],"shell":"bash"
                }})
            with self.assertRaises(ValueError):
                execute(db,"intelligence.director",{"op":"eval","params":{}})
            with self.assertRaises(ValueError):
                execute(db,"intelligence.director",{"op":"layout_audit","params":{},
                    "approve_write":True})

    def test_source_audit_is_metadata_not_archive_content(self):
        data=json.loads((ROOT/"SOURCE_INTELLIGENCE_AUDIT_V29.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data["sources"]),10)
        self.assertEqual(len({s["sha256"] for s in data["sources"]}),10)
        self.assertTrue(all(len(s["sha256"])==64 for s in data["sources"]))
        self.assertEqual(data["new_adapter"],"intelligence.director")
        self.assertIn("not full",data["fusion_scope"].lower())

if __name__=="__main__":
    unittest.main()
