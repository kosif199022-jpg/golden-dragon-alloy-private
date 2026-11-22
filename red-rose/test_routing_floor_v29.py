"""W11 routing floor and decoder rules. Pure Python, offline.

Skipped when evals/ is absent (the package build). Runs the routing harness
in-process on the test split (no record) and fails below the floors in
evals/routing/floor.json, when REPORT.json does not match the live run, or when
a floor was lowered below its history.
"""
import importlib.util
import json
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EV = ROOT / "evals"
HAVE_EVALS = EV.is_dir()


def _load_eval():
    spec = importlib.util.spec_from_file_location("run_eval_w11", EV / "routing" / "run_eval.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _json(path):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


@unittest.skipUnless(HAVE_EVALS, "evals/ absent (package build)")
class RoutingFloorV29(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev = _load_eval()
        cls.floor = _json(EV / "routing" / "floor.json")
        cls.freeze = _json(EV / "routing" / "FREEZE.json")
        cls.report = _json(EV / "routing" / "REPORT.json")

    def test_floor_is_not_below_history(self):
        hist = self.floor["history"]
        self.assertTrue(hist, "floor history must not be empty")
        for key in ("top1", "top3", "abstention_recall"):
            self.assertGreaterEqual(self.floor[key], max(math.floor(h[key] * 1000) / 1000 for h in hist if h.get(key) is not None) - 1e-9,
                                    f"{key} floor was lowered below its history")

    def test_report_and_freeze_match_current_files(self):
        live = self.ev.hashes()
        self.assertEqual(self.freeze["total_sha256"], live["total_sha256"],
                         "code or data changed since FREEZE.json was written")
        self.assertEqual(self.report["freeze_total_sha256"], self.freeze["total_sha256"])
        self.assertEqual(self.freeze["split"], "test")
        self.assertEqual(self.freeze["runs"], self.report["runs"], "runs must match between FREEZE and REPORT")
        self.assertGreaterEqual(self.freeze["runs"], 1)

    def test_test_split_meets_floor(self):
        result = self.ev.measure("test")
        s = result["summary"]
        self.assertGreaterEqual(s["top1"], self.floor["top1"], "top-1 below floor")
        self.assertGreaterEqual(s["top3"], self.floor["top3"], "top-3 below floor")
        self.assertGreaterEqual(s["abstention"]["recall"], self.floor["abstention_recall"],
                                "abstention recall below floor")

    def test_report_matches_live_measurement(self):
        live = self.ev.measure("test")["summary"]
        self.assertEqual(self.report["routing"]["test"]["top1"], live["top1"])
        self.assertEqual(self.report["routing"]["test"]["top3"], live["top3"])
        self.assertEqual(self.report["abstention"]["test"]["recall"], live["abstention"]["recall"])


@unittest.skipUnless(HAVE_EVALS, "evals/ absent (package build)")
class DecoderRulesV29(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev = _load_eval()
        cls.floor = _json(EV / "routing" / "floor.json")
        with open(EV / "decoder" / "cases.jsonl", encoding="utf-8") as f:
            cls.cases = [json.loads(line) for line in f if line.strip()]

    def test_english_inputs_stay_byte_identical(self):
        english = [c for c in self.cases if c["kind"] == "english"]
        self.assertTrue(english)
        for c in english:
            self.assertEqual(c["in"], c["out"])
            self.assertEqual(self.ev.A.understand(c["in"])["text"], c["in"], c["id"])

    def test_layout_cases_have_arabic_targets(self):
        layout = [c for c in self.cases if c["kind"] == "layout"]
        self.assertTrue(layout)
        for c in layout:
            self.assertTrue(any("؀" <= ch <= "ۿ" for ch in c["out"]), c["id"])

    def test_decoder_floors(self):
        dec = self.ev.decoder_eval()
        self.assertGreaterEqual(dec["layout_exact"], self.floor["decoder"]["layout_exact_min"])
        self.assertLessEqual(dec["false_positives_on_english"],
                             self.floor["decoder"]["english_false_positives_max"])


if __name__ == "__main__":
    unittest.main()
