"""Dua audio by day: caption labels, catalogue shipped, library registered."""
import csv, importlib.util, sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'agent' / 'dua_audio'))
import dua_audio as da


class DuaAudio(unittest.TestCase):
    def test_labels(self):
        self.assertEqual(da.label('دعاء ليلة الجمعة يارب'), 'friday_night')
        self.assertEqual(da.label('دعاء يوم الجمعة'), 'friday')
        self.assertEqual(da.label('دعاء صباح يوم الأحد'), 'sunday_morning')
        self.assertEqual(da.label('اللهم في رمضان'), 'ramadan')
        self.assertEqual(da.label('يارب'), 'other')

    def test_catalog_and_library(self):
        with (ROOT / 'agent' / 'dua_audio' / 'dua_audio_catalog.csv').open(encoding='utf-8-sig') as f:
            rows = list(csv.DictReader(f))
        self.assertGreater(len(rows), 2000)
        self.assertTrue({'dxhmen', 'oaun'} <= {r['account'] for r in rows})
        spec = importlib.util.spec_from_file_location('ml', ROOT / 'media_library_v35.py')
        ml = importlib.util.module_from_spec(spec); spec.loader.exec_module(ml)
        self.assertEqual(len(ml.KNOWN['dua_audio']['urls']), 5)
        self.assertEqual(len(ml.KNOWN['dxh_pins']['urls']), 2)


if __name__ == '__main__':
    unittest.main()
