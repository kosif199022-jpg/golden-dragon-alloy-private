import sqlite3, tempfile, unittest, os
from pathlib import Path
import dragon_memory_v47 as dm


class DragonMemory(unittest.TestCase):
    def test_import_is_idempotent_and_searchable(self):
        root = Path(tempfile.mkdtemp())
        (root / 'runtime/mind/chats').mkdir(parents=True)
        (root / 'runtime/mind/chats/c1.md').write_text('# فيلم أبو كاب والأسد والسلم\nالأسد لقى السلم والحل القيلولة', encoding='utf-8')
        (root / 'owner-memory/live').mkdir(parents=True)
        (root / 'owner-memory/live/lessons.jsonl').write_text('{"text": "درس: الكابشن كلمة كلمة مش حرف حرف"}\napi_key=sk-abcdefghijklmnopqrstuvwx\n', encoding='utf-8')
        db = sqlite3.connect(':memory:')
        a = dm.import_dragon_memory(db, root); b = dm.import_dragon_memory(db, root)
        self.assertEqual(a['added'], 2); self.assertEqual(b['added'], 0)
        hits = dm.dragon_search(db, 'أبو كاب')
        self.assertTrue(hits and 'كاب' in hits[0]['text'])
        self.assertFalse(any('sk-abc' in r['text'] for r in dm.dragon_search(db, 'api key')))


if __name__ == '__main__':
    unittest.main()
