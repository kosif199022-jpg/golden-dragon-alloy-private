import sqlite3, unittest
from contextlib import closing
from provenance import register, list_sources
class ProvenanceTests(unittest.TestCase):
    def test_records_source_and_license_state(self):
        with closing(sqlite3.connect(':memory:')) as db:
            register(db,'golden-dragon-alloy-private','SKILL.md','main')
            self.assertEqual(list_sources(db)[0]['license_id'],'unverified')
    def test_requires_revision(self):
        with closing(sqlite3.connect(':memory:')) as db:
            with self.assertRaises(ValueError):
                register(db,'repo','SKILL.md','')
