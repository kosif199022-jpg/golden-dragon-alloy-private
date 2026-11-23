import unittest
import dua_catalog_v40 as dc


class DuaCatalogV44(unittest.TestCase):
    def test_new_occasions(self):
        for tid in ('shaban', 'eid_fitr', 'eid_adha', 'arafah', 'ramadan_farewell', 'hijri_new_year', 'shifa', 'walidain', 'mawta'):
            r = dc.show(tid)
            self.assertTrue(r['ok'], tid)
            self.assertGreaterEqual(len(r['theme']['lines']), 2)

    def test_days_grew_and_stay_unique(self):
        for day in ('sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'saturday'):
            lines = dc.by_day(day)['lines']
            self.assertGreaterEqual(len(lines), 4, day)
            self.assertEqual(len(lines), len(set(lines)))

    def test_find_arabic(self):
        self.assertGreaterEqual(dc.find('عرفة')['count'], 1)


if __name__ == '__main__':
    unittest.main()
