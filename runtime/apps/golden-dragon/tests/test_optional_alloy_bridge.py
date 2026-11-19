"""No private memory is copied or implicitly exposed by the PUBLIC app bridge."""
import importlib.util
import json
from contextlib import closing
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "app"))
spec = importlib.util.spec_from_file_location(
    "public_optional_alloy_bridge", BASE / "forge" / "overlay" / "golden_knowledge_bridge.py")
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class OptionalAlloyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / "alloy.db"
        with closing(sqlite3.connect(self.db)) as con:
            con.execute("CREATE TABLE units(id TEXT PRIMARY KEY, title TEXT, summary TEXT, path TEXT,"
                        "sources TEXT, kind TEXT, status TEXT)")
            con.execute("CREATE VIRTUAL TABLE fts USING fts5(title, summary, body, content='')")
            rows = [
                ("active:1", "Python invoice validation", "Check invoice totals",
                 "skills/invoice.md", '[{"path":"skills/invoice.md"}]', "skill", "active"),
                ("memory:private", "Python owner private memory", "Private details",
                 "owner-memory/private.md", '[{"path":"owner-memory/private.md"}]', "memory", "private"),
                ("unsafe:script", "Python unsafe command", "Do not automatically run",
                 "unsafe.sh", '[{"path":"unsafe.sh"}]', "script", "review-before-run")
            ]
            for row in rows:
                cursor = con.execute("INSERT INTO units VALUES (?,?,?,?,?,?,?)", row)
                con.execute("INSERT INTO fts(rowid,title,summary,body) VALUES(?,?,?,?)",
                            (cursor.lastrowid, row[1], row[2], ""))
            con.commit()

    def tearDown(self):
        self.temp.cleanup()

    def test_only_active_non_memory_records_are_visible(self):
        found = bridge._private_alloy_search("python", 10, self.db)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["origin"], "private-full-alloy")
        self.assertEqual(found[0]["sources"][0]["path"], "skills/invoice.md")
        self.assertNotIn("Private details", str(found))

    def test_missing_private_db_safely_falls_back(self):
        with patch.object(bridge, "_private_alloy_database", return_value=None):
            self.assertEqual(bridge._private_alloy_search("python", 3), [])
            self.assertEqual(bridge._private_alloy_count(), 0)

    def test_untrusted_query_does_not_modify_database(self):
        before = self.db.read_bytes()
        found = bridge._private_alloy_search('python"; DROP TABLE units; --', 10, self.db)
        self.assertTrue(isinstance(found, list))
        with closing(sqlite3.connect(self.db)) as con:
            self.assertEqual(con.execute("SELECT count(*) FROM units").fetchone()[0], 3)


if __name__ == "__main__":
    unittest.main()
