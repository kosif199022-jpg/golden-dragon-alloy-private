"""The URL library ('pins'): approval gate, download+unzip from plain URLs, catalogue shipped."""
import csv
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import media_library_v35 as ml

ROOT = Path(__file__).resolve().parent


class PinsLibraryTests(unittest.TestCase):
    def test_listed_with_packs(self):
        row = next(r for r in ml.listing()['libraries'] if r['name'] == 'pins')
        self.assertEqual(row['release'], '6 HTTPS packs')

    def test_needs_approval(self):
        r = ml.fetch('pins')
        self.assertEqual(r['outcome'], 'approval_required')
        self.assertIn('6 zip packs', r['download'])

    def test_catalogue_matches_packs(self):
        with (ROOT / 'agent' / 'pins_catalog.csv').open(encoding='utf-8-sig') as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 602)
        urls = set(ml.KNOWN['pins']['urls'])
        self.assertTrue(all(r['pack_zip_link'] in urls for r in rows))
        self.assertTrue(all(r['pinterest_link'].startswith('https://www.pinterest.com/pin/') for r in rows))

    def test_fetch_from_local_packs(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            packs = []
            for k in range(2):
                z = td / f'p{k}.zip'
                with zipfile.ZipFile(z, 'w') as zz:
                    zz.writestr(f'{k:03d}_clip.mp4', b'x' * 10)
                packs.append(z.as_uri())
            info = dict(ml.KNOWN['pins'], urls=packs)
            libs = td / 'libraries.json'
            with mock.patch.dict(ml.KNOWN, {'pins': info}), mock.patch.object(ml, 'LIBS', libs):
                r = ml.fetch('pins', dest=td / 'out', approve_write=True)
            self.assertTrue(r['ok'], r)
            self.assertEqual(r['clips'], 2)
            self.assertTrue((td / 'out' / 'pins-library-v1' / 'pins_catalog.csv').is_file())
            self.assertEqual(json.loads(libs.read_text())['pins'], str(td / 'out' / 'pins-library-v1'))

    def test_zip_slip_refused(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            z = td / 'bad.zip'
            with zipfile.ZipFile(z, 'w') as zz:
                zz.writestr('../evil.mp4', b'x')
            info = dict(ml.KNOWN['pins'], urls=[z.as_uri()])
            with mock.patch.dict(ml.KNOWN, {'pins': info}), mock.patch.object(ml, 'LIBS', td / 'l.json'):
                r = ml.fetch('pins', dest=td / 'out', approve_write=True)
            self.assertFalse(r['ok'])
            self.assertIn('unsafe', r['error'])
            self.assertFalse((td / 'out' / 'evil.mp4').exists())


if __name__ == '__main__':
    unittest.main()
