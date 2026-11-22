"""accounting_v21 V29: explicit example flag, and bank_reconcile ledger_csv / bank_csv input."""
import tempfile
import unittest
from pathlib import Path

import accounting_v21 as acc

LEDGER_CSV = 'id,date,amount,ref\nL1,2026-03-02,2500.00,INV-77\nL2,2026-03-05,-450.75,CHQ 12\nL3,2026-03-09,1200.00,INV-78\n'
BANK_CSV = 'id,date,amount,ref\nB1,2026-03-03,2500.00,TRF INV77\nB2,2026-03-06,-450.75,12\nB3,2026-03-09,1201.00,INV78\n'


class CsvCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def write(self, name, text, encoding='utf-8'):
        p = self.dir / name
        p.write_bytes(text.encode(encoding))
        return str(p)

    def reconcile(self, **params):
        return acc.run('bank_reconcile', params)


class TestExampleFlag(CsvCase):
    def test_every_op_flags_builtin_example(self):
        for op in acc.OPS:
            out = acc.run(op, {})
            self.assertEqual(set(out), {'op', 'result', 'assumptions', 'limits'})
            self.assertIs(out['result']['example_data'], True, op)
            self.assertEqual(out['result']['input'], 'built_in_example', op)
            self.assertIn('BUILT-IN EXAMPLE', out['assumptions'][0])

    def test_example_rows_still_returned(self):
        r = acc.run('bank_reconcile', {})['result']
        self.assertEqual(r['counts']['matched'], 2)
        self.assertIn('matched', r)

    def test_owner_data_is_not_example(self):
        r = acc.run('trial_balance', {'lines': [{'entry_id': 'J', 'account': '1', 'debit': '5'},
                                                {'entry_id': 'J', 'account': '2', 'credit': '5'}]})['result']
        self.assertEqual((r['input'], r['example_data']), ('params', False))
        r = acc.run('meat_costing', {'price_per_kg': '31.00'})['result']
        self.assertFalse(r['example_data'])
        r = acc.run('cash_flow', {'sales': ['1'], 'payments': ['1']})['result']
        self.assertFalse(r['example_data'])


class TestBankCsv(CsvCase):
    def test_three_row_fixture(self):
        r = self.reconcile(ledger_csv=self.write('ledger.csv', LEDGER_CSV),
                           bank_csv=self.write('bank.csv', BANK_CSV))['result']
        self.assertEqual((r['input'], r['example_data']), ('csv', False))
        self.assertEqual(r['totals'], {'ledger': '3249.25', 'bank': '3250.25', 'difference': '1.00'})
        self.assertEqual(r['counts']['matched'], 2)
        self.assertEqual([x['id'] for x in r['unmatched_ledger']], ['L3'])
        self.assertEqual([x['id'] for x in r['unmatched_bank']], ['B3'])
        near = [n for n in r['near_misses'] if n['type'] == 'amount']
        self.assertEqual(near[0]['amount_difference'], '1.00')
        self.assertNotIn('ignored_columns', r)
        self.assertNotIn('warnings', r)

    def test_same_result_as_inline_rows(self):
        import csv, io
        rows = lambda t: list(csv.DictReader(io.StringIO(t)))
        inline = self.reconcile(ledger=rows(LEDGER_CSV), bank=rows(BANK_CSV))['result']
        from_csv = self.reconcile(ledger_csv=self.write('l.csv', LEDGER_CSV),
                                  bank_csv=self.write('b.csv', BANK_CSV))['result']
        self.assertEqual(inline['input'], 'params')
        for key in ('matched', 'unmatched_ledger', 'unmatched_bank', 'near_misses', 'totals', 'counts'):
            self.assertEqual(inline[key], from_csv[key])
        mixed = self.reconcile(ledger=rows(LEDGER_CSV), bank_csv=self.write('b2.csv', BANK_CSV))['result']
        self.assertEqual(mixed['input'], 'params+csv')

    def test_unknown_column_reported(self):
        text = LEDGER_CSV.replace('id,date,amount,ref', 'id,date,amount,description')
        r = self.reconcile(ledger_csv=self.write('l.csv', text), bank_csv=self.write('b.csv', BANK_CSV))['result']
        self.assertEqual(r['ignored_columns'], ['description'])
        self.assertTrue(any('ignored' in w for w in r['warnings']))
        self.assertEqual(r['counts']['ledger'], 3)

    def test_arabic_digits_bom_semicolon(self):
        text = ('id;date;amount;ref\nL1;٢٠٢٦-٠٣-٠٢;٢٥٠٠٫٠٠;INV-77\nL2;2026-03-05;-450.75;CHQ 12\n'
                'L3;2026-03-09;1,200.00;INV-78\n')
        r = self.reconcile(ledger_csv=self.write('l.csv', '﻿' + text),
                           bank_csv=self.write('b.csv', BANK_CSV))['result']
        self.assertEqual(r['totals']['ledger'], '3249.25')
        self.assertTrue(any('Arabic-Indic' in w for w in r['warnings']))
        self.assertEqual(r['counts']['matched'], 2)

    def test_csv_errors(self):
        good = self.write('b.csv', BANK_CSV)
        cases = {
            'missing amount': ('id,date,ref\nL1,2026-03-02,x\n', 'missing amount'),
            'empty': ('', 'empty'),
            'header only': ('id,date,amount\n', 'no data rows'),
            'float-ish': ('id,date,amount\nL1,2026-03-02,1e3\n', 'decimal'),
            'bad date': ('id,date,amount\nL1,02/03/2026,1.00\n', 'ISO date'),
            'dup column': ('id,date,amount,amount\nL1,2026-03-02,1,1\n', 'duplicate column'),
            'too many fields': ('id,date,amount\nL1,2026-03-02,1,extra\n', 'fields'),
            'empty cell': ('id,date,amount\nL1,,1\n', 'date is empty'),
        }
        for name, (text, msg) in cases.items():
            with self.subTest(case=name):
                with self.assertRaisesRegex(ValueError, msg):
                    self.reconcile(ledger_csv=self.write(f'{len(name)}x.csv', text), bank_csv=good)
        with self.assertRaisesRegex(ValueError, 'UTF-8'):
            self.reconcile(ledger_csv=self.write('cp.csv', 'id,date,amount,ref\nL1,2026-03-02,1,é\n', 'cp1252'),
                           bank_csv=good)
        with self.assertRaisesRegex(ValueError, 'not found'):
            self.reconcile(ledger_csv=str(self.dir / 'missing.csv'), bank_csv=good)
        with self.assertRaisesRegex(ValueError, r'\.csv'):
            self.reconcile(ledger_csv=self.write('l.txt', LEDGER_CSV), bank_csv=good)
        with self.assertRaisesRegex(ValueError, 'not both'):
            self.reconcile(ledger=[], ledger_csv=good, bank_csv=good)
        with self.assertRaisesRegex(ValueError, 'together'):
            self.reconcile(ledger_csv=good)
        with self.assertRaises(ValueError):
            self.reconcile(ledger_csv=1, bank_csv=good)


if __name__ == '__main__':
    unittest.main()
