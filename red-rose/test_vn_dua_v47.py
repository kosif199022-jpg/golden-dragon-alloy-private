import json
import tempfile
import unittest
from pathlib import Path
import zipfile
import vn_dua_v47 as vn

class VNTests(unittest.TestCase):
    def test_zip_metadata_without_extracting_or_exposing_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"sample.vn"
            with zipfile.ZipFile(p,"w") as z:
                z.writestr("../project.json",json.dumps({"tracks":[{"durationMs":2400,"duration":900,"text":"PRIVATE TEXT","font":"example","keyframes":[{"scale":1.2}]}]}))
                z.writestr("clip.mp4",b"fake")
            report=vn.inspect(p,sha=True)
            self.assertEqual(report["status"],"parsed")
            self.assertEqual(report["media_counts"],{".mp4":1})
            self.assertEqual(report["evidence"]["explicit_time_seconds"]["$.tracks[].durationMs"]["median"],2.4)
            self.assertNotIn("$.tracks[].duration",report["evidence"]["explicit_time_seconds"])
            self.assertNotIn("PRIVATE TEXT",json.dumps(report))
            self.assertEqual(list(Path(tmp).iterdir()),[p])
    def test_unsupported_schema_not_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"sample.vn"
            with zipfile.ZipFile(p,"w") as z:z.writestr("project.bin",b"unknown")
            self.assertEqual(vn.inspect(p)["status"],"schema_not_decoded")
            self.assertFalse(vn.batch([p])["ok"])
    def test_plain_json_and_duplicate_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"sample.vn"
            p.write_text('{"durationSec":3}',encoding="utf-8")
            r=vn.batch([p,p])
            self.assertTrue(r["ok"])
            self.assertEqual(r["counts"]["inputs"],1)
    def test_invalid_archive_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"sample.vn"
            p.write_bytes(b"not a known project")
            self.assertEqual(vn.inspect(p)["status"],"unsupported")
    def test_unit_conversion_requires_explicit_unit(self):
        self.assertIsNone(vn.timing_unit("duration"))
        self.assertEqual(vn.timing_unit("startTimeUs"),1000000)

if __name__=="__main__":
    unittest.main()
