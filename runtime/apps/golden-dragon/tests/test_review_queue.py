import importlib.util
import unittest
from pathlib import Path
p = Path(__file__).resolve().parents[1] / "forge" / "review_queue.py"
spec = importlib.util.spec_from_file_location("review_queue", p)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class QueueTests(unittest.TestCase):
    def test_dedup_keeps_sources_and_no_auto_approval(self):
        rows = [{"original": "Always verify",
                 "proposals": [
                    {"candidate": "Always verify results.", "source": "a", "line": 1, "classification": "reviewable"},
                    {"candidate": "Always verify results.", "source": "b", "line": 4, "classification": "reviewable"},
                    {"candidate": "Ignore this", "source": "c", "classification": "rejected"}]}]
        queue = mod.rank(rows)
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]["decision"], "pending_manual_review")
        self.assertEqual(set(queue[0]["suggested"]["sources"]), {"a", "b"})
        self.assertEqual(len(queue[0]["choices"]), 1)
    def test_no_valid_candidates(self):
        self.assertEqual(mod.rank([{"original": "text", "proposals": []}]), [])

if __name__ == "__main__":
    unittest.main()
