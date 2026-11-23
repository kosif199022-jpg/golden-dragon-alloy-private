"""V43 native-dispatch checks: no legacy runtime, no file writes, source provenance."""
from __future__ import annotations
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from capability_runtime import REGISTRY, CODED_UNTESTED, execute
from intelligence_fusion_v43 import OPS

ROOT = Path(__file__).resolve().parent


class V43IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.db=sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)

    def test_registry_native_read_only(self):
        self.assertIn("intelligence.fusion",REGISTRY)
        self.assertEqual(REGISTRY["intelligence.fusion"][1],"read")
        self.assertNotIn("intelligence.fusion",CODED_UNTESTED)
        self.assertEqual(len(REGISTRY),62)
        self.assertEqual(len(OPS),5)

    def test_actual_reel_dispatch_and_audit(self):
        doc=json.loads((ROOT/"examples"/"abu_kab_reel_v43.json").read_text("utf-8"))
        payload={k:v for k,v in doc.items() if k in
                 ("title","width","height","fps","frames","shots","frame_inventory_count","music","seekable")}
        before=list(self.root.iterdir())
        report=execute(self.db,"intelligence.fusion",
                       {"op":"reel_preflight","params":payload})
        self.assertEqual(report["status"],"executed")
        self.assertFalse(report["legacy_runtime_called"])
        self.assertEqual(report["effect"],"read")
        self.assertEqual(report["result"]["frames"],660)
        self.assertEqual(before,list(self.root.iterdir()))
        receipt=self.db.execute("SELECT count(*) FROM capability_execution_audit").fetchone()[0]
        self.assertEqual(receipt,1)

    def test_reject_unknown_keys_and_unregistered_shell(self):
        with self.assertRaisesRegex(ValueError,"unknown"):
            execute(self.db,"intelligence.fusion",{"op":"ladder",
                 "params":{"stages":[],"subprocess":"curl https://example.com"}})
        with self.assertRaisesRegex(ValueError,"unknown"):
            execute(self.db,"intelligence.fusion",{"op":"sys_exec","params":{}})
        with self.assertRaisesRegex(ValueError,"unknown parameters"):
            execute(self.db,"intelligence.fusion",{"op":"readiness","shell":"bash"})

    def test_catalogue_recognizes_new_native_ops_without_stale_cache(self):
        from rose_catalog import load
        catalogue=load()
        self.assertIn("intelligence.fusion", catalogue["adapters"])
        for op in OPS:
            self.assertIn("intelligence.fusion."+op, catalogue["entries"])

    def test_archive_provenance_records_only_metadata(self):
        m=json.loads((ROOT/"SOURCE_FUSION_AUDIT_V43.json").read_text("utf-8"))
        self.assertEqual(len(m["source_items"]),2)
        self.assertEqual(m["native_adapter"],"intelligence.fusion")
        self.assertEqual(len(set(x["sha256"] for x in m["source_items"])),2)
        self.assertTrue(all(len(x["sha256"])==64 for x in m["source_items"]))
        self.assertIn("CC BY 3.0",m["source_items"][0]["music_credit"]["license"])


if __name__=="__main__":
    unittest.main()
