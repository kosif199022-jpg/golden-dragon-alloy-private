import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
root = Path(__file__).resolve().parents[1] / "forge"
def load(name):
    spec = importlib.util.spec_from_file_location(name, root / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
builder = load("standalone_brain")
verify = load("verify_standalone_brain")
class VerificationTests(unittest.TestCase):
    def test_detects_changed_record(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as tmp:
            src, db = Path(tmp)/"source.json", Path(tmp)/"brain.sqlite"
            src.write_text(json.dumps({"instructions": [{"text": "original", "sources": [{"path": "a"}]}]}))
            builder.build(src, db)
            self.assertTrue(verify.audit(src, db)["passed"])
            con = sqlite3.connect(db)
            con.execute("UPDATE knowledge SET payload=? WHERE status='active'", ('{"text":"tampered"}',))
            con.commit()
            con.close()
            self.assertFalse(verify.audit(src, db)["passed"])
if __name__ == "__main__":
    unittest.main()
