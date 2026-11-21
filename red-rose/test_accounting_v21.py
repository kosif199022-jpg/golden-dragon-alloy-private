import ast
import inspect
import json
import unittest
from decimal import Decimal, ROUND_HALF_UP

import accounting_v21 as acc


def run(op, **params):
    return acc.run(op, params)


class TestInterface(unittest.TestCase):
    def test_topics_and_ops(self):
        self.assertEqual(len(acc.TOPICS), 10)
        self.assertEqual(set(acc.TOPICS.values()), set(acc.OPS))
        self.assertEqual(set(acc.TOPIC_NAMES_AR), set(acc.TOPICS))

    def test_every_op_runs_with_empty_params(self):
        for op in acc.OPS:
            out = acc.run(op, {})
            self.assertEqual(set(out), {'op', 'result', 'assumptions', 'limits'})
            self.assertEqual(out['op'], op)
            json.dumps(out, allow_nan=False)
            self.assertTrue(any('opinion' in x for x in out['limits']))
            self.assertTrue(any('pay' in x for x in out['limits']))
            self.assertEqual(acc.run(op, {}), out)  # deterministic

    def test_unknown_param_and_bad_op(self):
        for op in acc.OPS:
            with self.assertRaises(ValueError):
                acc.run(op, {'nope': 1})
        with self.assertRaises(ValueError):
            acc.run('nope', {})
        with self.assertRaises(ValueError):
            acc.run('trial_balance', [])

    def test_float_money_rejected(self):
        with self.assertRaises(ValueError):
            run('trial_balance', lines=[{'entry_id': 'a', 'account': '1', 'debit': 10.0},
                                        {'entry_id': 'a', 'account': '2', 'credit': '10'}])
        with self.assertRaises(ValueError):
            run('meat_costing', price_per_kg=30.5)

    def test_missing_pair_raises_value_error(self):
        with self.assertRaises(ValueError):
            run('bank_reconcile', ledger=[{'id': 1, 'date': '2026-01-01', 'amount': '1'}])
        with self.assertRaises(ValueError):
            run('payroll_check', payroll=[{'employee_id': 'E1', 'net': '1'}])
        with self.assertRaises(ValueError):
            run('trial_balance', lines=[{'account': '1'}])
        with self.assertRaises(ValueError):
            run('bank_reconcile', ledger=[{'id': 1, 'date': '2026-02-30', 'amount': '1'}],
                bank=[{'id': 1, 'date': '2026-01-01', 'amount': '1'}])

    def test_no_forbidden_imports_or_calls(self):
        tree = ast.parse(inspect.getsource(acc))
        banned = {'os', 'subprocess', 'socket', 'urllib', 'http', 'shutil', 'sqlite3', 'ctypes'}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    self.assertNotIn(a.name.split('.')[0], banned)
            elif isinstance(node, ast.ImportFrom):
                self.assertNotIn((node.module or '').split('.')[0], banned)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {'open', 'exec', 'eval', 'print'})


class TestTopics(unittest.TestCase):
    # 24.01
    def test_bank_one_riyal_difference_is_near_miss(self):
        out = run('bank_reconcile',
                  ledger=[{'id': 'L1', 'date': '2026-01-10', 'amount': '500.00', 'ref': 'INV7'},
                          {'id': 'L2', 'date': '2026-01-11', 'amount': '250.00', 'ref': 'X1'}],
                  bank=[{'id': 'B1', 'date': '2026-01-10', 'amount': '501.00', 'ref': 'INV7'},
                        {'id': 'B2', 'date': '2026-01-12', 'amount': '250.00', 'ref': 'X1'}])['result']
        pairs = {(m['ledger_id'], m['bank_id']) for m in out['matched']}
        self.assertEqual(pairs, {('L2', 'B2')})
        self.assertNotIn(('L1', 'B1'), pairs)
        nm = [n for n in out['near_misses'] if n['ledger_id'] == 'L1' and n['bank_id'] == 'B1']
        self.assertEqual(len(nm), 1)
        self.assertEqual(nm[0]['type'], 'amount')
        self.assertEqual(nm[0]['amount_difference'], '1.00')
        self.assertEqual([u['id'] for u in out['unmatched_ledger']], ['L1'])
        self.assertEqual([u['id'] for u in out['unmatched_bank']], ['B1'])

    def test_bank_date_window_and_reference(self):
        out = run('bank_reconcile',
                  ledger=[{'id': 'L1', 'date': '2026-01-01', 'amount': '10', 'ref': 'ABC'}],
                  bank=[{'id': 'B1', 'date': '2026-01-09', 'amount': '10', 'ref': 'ZZZ'},
                        {'id': 'B2', 'date': '2026-01-02', 'amount': '10', 'ref': 'ABC'},
                        {'id': 'B3', 'date': '2026-01-02', 'amount': '10', 'ref': 'QQQ'}],
                  date_window_days=3)['result']
        self.assertEqual(out['matched'][0]['bank_id'], 'B2')

    # 24.02
    def test_duplicate_invoices(self):
        out = run('duplicate_invoices', invoices=[
            {'id': 1, 'supplier': 'Al Noor', 'invoice_no': 'INV-0012', 'amount': '900.00', 'date': '2026-01-01'},
            {'id': 2, 'supplier': 'al noor', 'invoice_no': 'INV0012', 'amount': '900.00', 'date': '2026-01-02'},
            {'id': 3, 'supplier': 'Beta', 'invoice_no': 'A-1', 'amount': '100.00', 'date': '2026-01-01'},
            {'id': 4, 'supplier': 'Beta', 'invoice_no': 'A1', 'amount': '120.00', 'date': '2026-01-01'},
            {'id': 5, 'supplier': 'Gamma', 'invoice_no': '0012', 'amount': '5', 'date': '2026-01-01'},
            {'id': 6, 'supplier': 'Gamma', 'invoice_no': '12', 'amount': '5', 'date': '2026-03-01'},
        ])['result']
        self.assertEqual(len(out['duplicates']), 1)
        self.assertEqual(out['duplicates'][0]['ids'], ['1', '2'])
        self.assertNotIn('3', out['duplicate_ids'])
        self.assertNotIn('4', out['duplicate_ids'])
        self.assertNotIn('5', out['duplicate_ids'])  # leading zeros kept
        self.assertEqual(out['suspects'], [])  # Gamma rows are 59 days apart

    # 24.03
    def test_trial_balance(self):
        good = run('trial_balance')['result']
        self.assertTrue(good['balanced'])
        self.assertEqual(good['unbalanced_entries'], [])
        bad = run('trial_balance', lines=[
            {'entry_id': 'J1', 'account': '1000', 'debit': '100.00'},
            {'entry_id': 'J1', 'account': '2000', 'credit': '100.00'},
            {'entry_id': 'J2', 'account': '1000', 'debit': '50.00'},
            {'entry_id': 'J2', 'account': '2000', 'credit': '40.00'},
        ])['result']
        self.assertFalse(bad['balanced'])
        self.assertEqual([e['entry_id'] for e in bad['unbalanced_entries']], ['J2'])
        self.assertEqual(bad['unbalanced_entries'][0]['difference'], '10.00')
        self.assertEqual(bad['totals']['difference'], '10.00')

    # 24.04
    def test_payroll(self):
        iban = 'SA0380000000608010167519'
        out = run('payroll_check',
                  payroll=[{'employee_id': 'E1', 'net': '5000.00'}, {'employee_id': 'E1', 'net': '5000.00'},
                           {'employee_id': 'E2', 'net': '3000.00'}],
                  payments=[{'employee_id': 'E1', 'iban': iban, 'amount': '5000.00'},
                            {'employee_id': 'E2', 'iban': 'SA4420000001234567891234', 'amount': '3000.00'},
                            {'employee_id': 'E7', 'iban': 'SA4420000001234567891234', 'amount': '10.00'}])
        types = {(f['type'], f.get('employee_id')) for f in out['result']['flags']}
        self.assertIn(('duplicate_in_payroll', 'E1'), types)
        self.assertIn(('net_not_equal_paid', 'E1'), types)
        self.assertIn(('paid_not_on_payroll', 'E7'), types)
        self.assertIn(('iban_shared_by_employees', None), types)
        text = json.dumps(out, ensure_ascii=False)
        for full in (iban, 'SA4420000001234567891234'):
            self.assertNotIn(full, text)
            self.assertNotIn(full[:-4], text)
        self.assertIn('7519', text)
        default_text = json.dumps(acc.run('payroll_check', {}))
        for p in acc._EX_PAYMENTS:
            self.assertNotIn(p['iban'], default_text)

    def test_payroll_bad_iban_message_hides_value(self):
        try:
            run('payroll_check', payroll=[{'employee_id': 'E1', 'net': '1'}],
                payments=[{'employee_id': 'E1', 'iban': 'SA03-SECRET!', 'amount': '1'}])
        except ValueError as exc:
            self.assertNotIn('SECRET', str(exc))
        else:
            self.fail('expected ValueError')

    # 24.05
    def test_inventory_codes(self):
        out = run('inventory_codes', items=[{'code': '00123'}, {'code': '123'},
                                            {'code': 'AB-001'}, {'code': 'ab 001'}])['result']
        norm = [i['normalised_code'] for i in out['items']]
        self.assertNotEqual(norm[0], norm[1])
        self.assertEqual(norm[2], norm[3])
        self.assertEqual([d['normalised_code'] for d in out['duplicates']], ['AB-001'])
        alt = run('inventory_codes')['result']['alternates']
        self.assertTrue(any(a['codes'] == ['00123', '123'] for a in alt))

    # 24.06
    def test_meat_costing_hand_calc(self):
        out = run('meat_costing', purchase_weight_kg='100', price_per_kg='30.00', trim_pct='10',
                  waste_pct='5', processing_cost='200.00', sale_price_per_kg='45.00',
                  target_margin_pct='20')['result']
        q = lambda d, p='0.01': str(Decimal(d).quantize(Decimal(p), rounding=ROUND_HALF_UP))
        sellable = Decimal('85')
        total = Decimal('3000') + Decimal('200')
        cpk = total / sellable
        self.assertEqual(out['sellable_kg'], '85.000')
        self.assertEqual(out['total_cost'], '3200.00')
        self.assertEqual(out['cost_per_sellable_kg'], q(cpk))
        self.assertEqual(out['cost_per_sellable_kg'], '37.65')
        self.assertEqual(out['break_even_price_per_kg'], '37.65')
        self.assertEqual(out['revenue'], '3825.00')
        self.assertEqual(out['gross_profit'], '625.00')
        self.assertEqual(out['gross_margin_pct'], q(Decimal('625') / Decimal('3825') * 100))
        self.assertEqual(out['gross_margin_pct'], '16.34')
        self.assertEqual(out['price_for_target_margin'], q(cpk / Decimal('0.8')))
        self.assertEqual(out['price_for_target_margin'], '47.06')

    # 24.07
    def test_cash_flow_collection_rate_and_order(self):
        common = dict(opening_cash='1000', sales=['100', '200', '300'],
                      payments=['50', '50', '50'], collection_delay_months=0)
        hi = run('cash_flow', collection_rate_pct='90', **common)['result']['scenarios']
        lo = run('cash_flow', collection_rate_pct='70', **common)['result']['scenarios']
        for m in range(3):
            self.assertLess(Decimal(lo['base']['months'][m]['closing']),
                            Decimal(hi['base']['months'][m]['closing']))
        for res in (hi, lo):
            for m in range(3):
                l, b, h = (Decimal(res[s]['months'][m]['closing']) for s in ('low', 'base', 'high'))
                self.assertLessEqual(l, b)
                self.assertLessEqual(b, h)
        self.assertEqual(hi['base']['months'][0]['closing'], '1040.00')  # 1000 + 90 - 50
        default = run('cash_flow')['result']
        self.assertTrue(default['scenario_order_ok'])
        self.assertIn('minimum_balance_month', default['scenarios']['base'])

    # 24.08
    def test_cost_allocation_exact_and_traceable(self):
        expenses = [{'id': 'X1', 'amount': '100.00'}, {'id': 'X2', 'amount': '0.05'},
                    {'id': 'X3', 'amount': '9999.99'}]
        centres = [{'centre': 'A', 'share': '1'}, {'centre': 'B', 'share': '1'},
                   {'centre': 'C', 'share': '1'}]
        out = run('cost_allocation', expenses=expenses, centres=centres)['result']
        for e in expenses:
            lines = [l for l in out['lines'] if l['source_expense_id'] == e['id']]
            self.assertEqual(len(lines), 3)
            self.assertEqual(sum(Decimal(l['amount']) for l in lines), Decimal(e['amount']))
        ids = {e['id'] for e in expenses}
        self.assertTrue(all(l['source_expense_id'] in ids for l in out['lines']))
        self.assertTrue(out['all_exact'])
        self.assertEqual(Decimal(out['total_allocated']), Decimal(out['total_expenses']))
        pct = run('cost_allocation', method='percent', expenses=[{'id': 'R', 'amount': '1000.01'}],
                  centres=[{'centre': 'P', 'share': '33.33'}, {'centre': 'S', 'share': '66.67'}])['result']
        self.assertEqual(sum(Decimal(l['amount']) for l in pct['lines']), Decimal('1000.01'))
        with self.assertRaises(ValueError):
            run('cost_allocation', method='percent', expenses=[{'id': 'R', 'amount': '1'}],
                centres=[{'centre': 'P', 'share': '50'}])

    # 24.09
    def test_standards_checklist(self):
        out = run('standards_checklist', items=[
            {'id': 'A', 'standard': 'IFRS 15', 'reference': 'IFRS 15.31', 'effective_date': '2018-01-01',
             'answer': 'yes'},
            {'id': 'B', 'standard': 'SOCPA', 'effective_date': '2020-01-01', 'answer': 'no'},
            {'id': 'C', 'standard': 'IFRS 16', 'reference': 'IFRS 16.22'},
        ])['result']
        by = {i['id']: i for i in out['items']}
        self.assertIn('missing_reference', by['B']['flags'])
        self.assertIn('missing_effective_date', by['C']['flags'])
        self.assertEqual(by['A']['flags'], [])
        self.assertEqual(by['B']['status'], 'gap')
        for item in out['items']:
            self.assertFalse(item['definitive'])
            self.assertIn('non-definitive, requires qualified review', item['note'])
        self.assertIn('non-definitive', out['note'])

    # 24.10
    def test_journal_approval(self):
        out = run('journal_approval', entries=[
            {'id': 'S', 'creator': 'Ali', 'created_at': '2026-01-01T09:00', 'approver': ' ali ',
             'approved_at': '2026-01-01T10:00'},
            {'id': 'E', 'creator': 'Ali', 'created_at': '2026-01-01T09:00', 'approver': 'Sara',
             'approved_at': '2026-01-01T10:00',
             'history': [{'user': 'Ali', 'at': '2026-01-01T11:00', 'action': 'edit'}]},
            {'id': 'R', 'creator': 'Ali', 'created_at': '2026-01-01T09:00', 'approver': 'Sara',
             'approved_at': '2026-01-01T10:00',
             'history': [{'user': 'Ali', 'at': '2026-01-01T11:00', 'action': 'edit'},
                         {'user': 'Sara', 'at': '2026-01-01T12:00', 'action': 'approve'}]},
            {'id': 'B', 'creator': 'Ali', 'created_at': '2026-01-02T09:00', 'approver': 'Sara',
             'approved_at': '2026-01-01T10:00'},
        ])['result']
        by = {e['id']: e for e in out['entries']}
        self.assertEqual(by['S']['status'], 'rejected')
        self.assertIn('self_approval', by['S']['issues'])
        self.assertEqual(by['E']['status'], 'flagged')
        self.assertIn('edited_after_approval', by['E']['issues'])
        self.assertEqual(by['R']['status'], 'ok')
        self.assertEqual(by['B']['status'], 'rejected')
        self.assertIn('approval_before_creation', by['B']['issues'])


if __name__ == '__main__':
    unittest.main()
