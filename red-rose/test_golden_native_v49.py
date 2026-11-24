import unittest
import tempfile
from pathlib import Path
import rose_golden_native as n
import rose_golden_deep as d

class GoldenNativeV49(unittest.TestCase):
    def test_new_adapters_execute_default_examples(self):
        self.assertEqual(len(n.NATIVE),28)
        self.assertEqual(len(n.OPS),40)
        for op in n.NATIVE:
            with self.subTest(op=op):
                self.assertIsInstance(n.execute(op,{}),dict)
    def test_independent_profile(self):
        self.assertEqual(d.load()["counts"]["recipes"],42)
        self.assertTrue(any(x["id"]=="lyrics-film" for x in d.search("دعاء")))
    def test_reject_unknown_operation(self):
        with self.assertRaises(ValueError):n.execute("shell",{})
    def test_write_requires_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/"video.mp4"
            result=n.execute("dua-render",{"plan":{"lines":["test"]},"output":str(out)})
            self.assertEqual(result["outcome"],"approval_required")
            self.assertFalse(out.exists())
    def test_motion_result(self):
        self.assertEqual(n.execute("motion-ease",{"name":"linear","samples":5})["samples"],[0,.25,.5,.75,1])
    def test_read_only_guard(self):
        with self.assertRaises(ValueError):n.execute("3d-camera",["not","an","object"])
    def test_no_auto_execution_from_profile(self):
        self.assertEqual(d.load()["recipes"][0]["status"],"catalogued_not_executed")
