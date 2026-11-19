import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
p = Path(__file__).resolve().parents[1] / "forge" / "standalone_brain.py"
spec = importlib.util.spec_from_file_location("standalone_brain", p)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class StandaloneTests(unittest.TestCase):
    def test_preserves_all_statuses_and_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, db = Path(tmp) / "source.json", Path(tmp) / "brain.sqlite"
            source.write_text(json.dumps({
                "instructions": [{"text": "Python testing", "sources": [{"path": "source.md"}]}],
                "quality_quarantine": [{"instruction": {"text": "Python review", "sources": []}}],
                "requires_review": [{"text": "Python conflict", "sources": []}]
            }))
            result = mod.build(source, db)
            self.assertEqual(result["total"], 3)
            self.assertEqual(result["counts"]["active"], 1)
            found = mod.query(db, "Python", include_review=False)
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0]["record"]["sources"][0]["path"], "source.md")
            self.assertEqual(len(mod.query(db, "Python", include_review=True)), 3)
            with self.assertRaises(FileExistsError):
                mod.build(source, db)
if __name__ == "__main__":
    unittest.main()
