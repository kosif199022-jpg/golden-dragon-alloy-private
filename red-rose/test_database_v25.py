"""Acceptance tests for database_v25 (topics 23.01-23.10)."""
import ast
import contextlib
import hashlib
import hmac
import inspect
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import database_v25 as D

FORBIDDEN_IMPORTS = {'socket', 'urllib', 'http', 'requests', 'ctypes', 'subprocess', 'os', 'shutil'}


def make_db(path, script, rows=()):
    with contextlib.closing(sqlite3.connect(path)) as conn:
        conn.executescript(script)
        for sql, data in rows:
            conn.executemany(sql, data)
        conn.commit()


def query(path, sql, params=()):
    with contextlib.closing(sqlite3.connect(path)) as conn:
        return conn.execute(sql, params).fetchall()


class TestInterface(unittest.TestCase):
    def test_topics_ops_effects(self):
        self.assertEqual(sorted(D.TOPICS), [f'23.{i:02d}' for i in range(1, 11)])
        self.assertEqual(set(D.TOPICS.values()), set(D.OPS))
        self.assertEqual(set(D.EFFECTS), set(D.OPS))
        self.assertTrue(set(D.EFFECTS.values()) <= {'read', 'write'})
        self.assertEqual(set(D.TOPIC_NAMES_AR), set(D.TOPICS))

    def test_run_all_defaults_json(self):
        for op in D.OPS:
            with self.subTest(op=op):
                out = D.run(op, {})
                self.assertEqual(set(out), {'op', 'result', 'assumptions', 'limits'})
                self.assertEqual(out['op'], op)
                self.assertTrue(out['assumptions'] and out['limits'])
                json.dumps(out, allow_nan=False)
                if D.EFFECTS[op] == 'write':
                    self.assertEqual(out['result']['status'], 'approval_required')
                    self.assertFalse(out['result']['changed'])
                    approved = D.run(op, {'approve_write': True})
                    json.dumps(approved, allow_nan=False)
                    self.assertNotEqual(approved['result']['status'], 'approval_required')

    def test_bad_inputs(self):
        bad = [('nope', {}), ('safe_schema', []), ('time_series', {'zzz': 1}),
               ('tenant_query', {'db_path': 'x.sqlite3'}),
               ('index_plan', {'table': 'items; DROP TABLE items'}),
               ('index_plan', {'rows': True}), ('record_conflicts', {'key': 'a"b'}),
               ('safe_migration', {'direction': 'sideways'}), ('import_tabular', {'mapping': {}}),
               ('protect_sensitive', {'pseudonymise': ['iban']}),
               ('protect_sensitive', {'pseudonymise': ['iban'], 'pseudonym_key': 'short'}),
               ('backup_restore', {'backup_name': '../evil.sqlite3'}),
               ('time_series', {'start': '2025-13'}), ('lineage', {'db_path': 'x.db'}),
               ('safe_schema', {'spec': {'tables': [{'name': 'sqlite_x', 'columns': []}]}, 'approve_write': True}),
               ('time_series', {f'k{i}': 1 for i in range(25)})]
        for op, params in bad:
            with self.subTest(op=op, params=params):
                with self.assertRaises(ValueError):
                    D.run(op, params)
        with self.assertRaises(ValueError):
            D.time_series(bogus=1)

    def test_missing_db_file_is_valueerror(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                D.run('time_series', {'db_path': str(Path(tmp) / 'missing.sqlite3')})

    def test_private_db_refused(self):
        private = str(Path.home() / '.red-rose' / 'memory.sqlite3')
        for op in ('time_series', 'tenant_query', 'safe_schema', 'backup_restore'):
            with self.subTest(op=op):
                with self.assertRaises(ValueError) as cm:
                    D.run(op, {'db_path': private, 'tenant_id': 'A', 'sql': 'SELECT 1'}
                          if op == 'tenant_query' else {'db_path': private})
                self.assertIn('private', str(cm.exception))

    def test_static_safety(self):
        tree = ast.parse(inspect.getsource(D))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn(alias.name.split('.')[0], FORBIDDEN_IMPORTS)
            elif isinstance(node, ast.ImportFrom):
                self.assertNotIn((node.module or '').split('.')[0], FORBIDDEN_IMPORTS)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {'exec', 'eval', 'print', 'open', 'compile', '__import__'})


class TestSafeSchema(unittest.TestCase):  # 23.01
    def test_duplicate_and_missing_fk_rejected(self):
        r = D.run('safe_schema', {'approve_write': True})['result']
        self.assertTrue(r['foreign_keys'])
        kinds = {x['index']: x['constraint'] for x in r['rejected']}
        self.assertEqual(kinds[2], 'UNIQUE')          # duplicate national_id
        self.assertEqual(kinds[4], 'FOREIGN KEY')     # owner_id 99 does not exist
        self.assertEqual(kinds[5], 'NOT NULL')
        self.assertEqual(r['row_counts'], {'owners': 2, 'accounts': 1})
        self.assertNotIn('1000000001', json.dumps(r['rejected']))

    def test_file_needs_approval_then_applies(self):
        spec = {'tables': [{'name': 'p', 'columns': [{'name': 'id', 'type': 'INTEGER', 'primary_key': True}]},
                           {'name': 'c', 'columns': [{'name': 'id', 'type': 'INTEGER', 'primary_key': True},
                                                     {'name': 'pid', 'type': 'INTEGER', 'references': 'p.id'}]}]}
        rows = [{'table': 'p', 'values': {'id': 1}}, {'table': 'c', 'values': {'id': 1, 'pid': 1}},
                {'table': 'c', 'values': {'id': 2, 'pid': 7}}, {'table': 'p', 'values': {'id': 1}}]
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / 'mem.sqlite3')
            pending = D.run('safe_schema', {'db_path': db, 'spec': spec, 'rows': rows})['result']
            self.assertEqual(pending['status'], 'approval_required')
            self.assertFalse(Path(db).exists())
            r = D.run('safe_schema', {'db_path': db, 'spec': spec, 'rows': rows, 'approve_write': True})['result']
            self.assertEqual([x['constraint'] for x in r['rejected']], ['FOREIGN KEY', 'PRIMARY KEY'])
            self.assertEqual(query(db, 'SELECT COUNT(*) FROM c'), [(1,)])
            with self.assertRaises(ValueError):       # table already exists: no silent reuse
                D.run('safe_schema', {'db_path': db, 'spec': spec, 'approve_write': True})


class TestTenantQuery(unittest.TestCase):  # 23.02
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / 't.sqlite3')
        make_db(self.db, 'CREATE TABLE orders (id INTEGER PRIMARY KEY, tenant_id TEXT, item TEXT);'
                         'CREATE TABLE settings (k TEXT, v TEXT);',
                [('INSERT INTO orders VALUES (?, ?, ?)', [(1, 'A', 'pen'), (2, 'B', 'secret-b'), (3, 'A', 'ink')]),
                 ('INSERT INTO settings VALUES (?, ?)', [('x', 'y')])])

    def tearDown(self):
        self.tmp.cleanup()

    def q(self, tenant, sql, params=None):
        return D.run('tenant_query', {'db_path': self.db, 'tenant_id': tenant, 'sql': sql,
                                      'sql_params': params or {}})['result']

    def test_tenant_a_cannot_read_b(self):
        self.assertEqual(self.q('A', 'SELECT * FROM orders WHERE id = :id', {'id': 2})['rows'], [])
        self.assertEqual([r['id'] for r in self.q('A', 'SELECT id FROM orders ORDER BY id')['rows']], [1, 3])
        r = self.q('A', "SELECT id FROM orders WHERE tenant_id = 'B' OR 1 = 1")
        self.assertEqual([x['id'] for x in r['rows']], [1, 3])
        self.assertNotIn('secret-b', json.dumps(self.q('A', 'SELECT * FROM orders')))
        self.assertEqual([x['item'] for x in self.q('B', 'SELECT item FROM orders')['rows']], ['secret-b'])
        self.assertEqual(D.run('tenant_query', {})['result']['rows'], [])

    def test_escapes_refused(self):
        for sql in ('SELECT * FROM main.orders', 'SELECT * FROM settings', 'DELETE FROM orders',
                    'SELECT 1; DROP TABLE orders', 'PRAGMA table_info(orders)'):
            with self.subTest(sql=sql):
                self.assertEqual(self.q('A', sql)['status'], 'refused')
        self.assertEqual(query(self.db, 'SELECT COUNT(*) FROM orders'), [(3,)])
        with self.assertRaises(ValueError):
            D.run('tenant_query', {'db_path': self.db, 'sql': 'SELECT 1'})


class TestIndexPlan(unittest.TestCase):  # 23.03
    def test_scan_to_search(self):
        r = D.run('index_plan', {'rows': 5000, 'repeat': 5, 'approve_write': True})['result']
        self.assertEqual(r['before']['access'], 'SCAN')
        self.assertEqual(r['after']['access'], 'SEARCH USING INDEX')
        self.assertTrue(r['switched_scan_to_search'])
        self.assertTrue(r['same_result_count'])
        self.assertGreater(r['before']['median_ms'], 0)

    def test_file_preview_does_not_create_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / 'i.sqlite3')
            make_db(db, 'CREATE TABLE t (id INTEGER PRIMARY KEY, code TEXT)',
                    [('INSERT INTO t (code) VALUES (?)', [(f'c{i}',) for i in range(500)])])
            p = D.run('index_plan', {'db_path': db, 'table': 't', 'columns': ['code']})['result']
            self.assertEqual(p['status'], 'approval_required')
            self.assertEqual(query(db, "SELECT COUNT(*) FROM sqlite_master WHERE type='index'"), [(0,)])
            r = D.run('index_plan', {'db_path': db, 'table': 't', 'columns': ['code'], 'approve_write': True,
                                     'repeat': 3})['result']
            self.assertTrue(r['switched_scan_to_search'])


class TestRecordConflicts(unittest.TestCase):  # 23.04
    def test_contradictory_accounts_with_rowids(self):
        r = D.run('record_conflicts', {})['result']
        owner = [v for v in r['violations'] if v['rule'] == 'same_key_different_value']
        self.assertEqual(len(owner), 1)
        self.assertEqual(owner[0]['key'], 'ACC-100')
        self.assertEqual(sorted(e['rowid'] for e in owner[0]['evidence']), [1, 3])
        bal = [v for v in r['violations'] if v['rule'] == 'balance_not_sum_of_entries']
        self.assertEqual([v['key'] for v in bal], ['ACC-200'])
        self.assertEqual([(e['table'], e['rowid']) for e in bal[0]['evidence']], [('accounts', 2), ('entries', 3)])

    def test_normalize_off_flags_case_variant(self):
        r = D.run('record_conflicts', {'normalize': False})['result']
        self.assertIn('ACC-300', [v['key'] for v in r['violations']])


class TestSafeMigration(unittest.TestCase):  # 23.05
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / 'm.sqlite3')
        make_db(self.db, 'CREATE TABLE people (id INTEGER PRIMARY KEY, name TEXT NOT NULL, score REAL)',
                [('INSERT INTO people (name, score) VALUES (?, ?)', [(f'n{i}', i / 7) for i in range(40)])])

    def tearDown(self):
        self.tmp.cleanup()

    def test_up_down_cycle_restores(self):
        sample_before = query(self.db, 'SELECT * FROM people WHERE id IN (1, 7, 40) ORDER BY id')
        schema_before = query(self.db, "SELECT sql FROM sqlite_master WHERE name = 'people'")
        args = {'db_path': self.db, 'table': 'people', 'add_columns': [{'name': 'tier', 'type': 'TEXT',
                                                                         'default': 'gold'}]}
        self.assertEqual(D.run('safe_migration', args)['result']['status'], 'approval_required')
        r = D.run('safe_migration', dict(args, approve_write=True))['result']
        self.assertEqual(r['status'], 'applied')
        self.assertEqual(r['before']['rows'], r['after']['rows'])
        self.assertEqual(r['before']['sample'], r['after']['sample'])
        self.assertTrue(r['original_values_identical'] and r['schema_restored'])
        self.assertEqual(query(self.db, 'SELECT * FROM people WHERE id IN (1, 7, 40) ORDER BY id'), sample_before)
        self.assertEqual(query(self.db, "SELECT sql FROM sqlite_master WHERE name = 'people'"), schema_before)
        self.assertEqual(query(self.db, "SELECT name FROM sqlite_master WHERE name LIKE '\\_%' ESCAPE '\\'"), [])

    def test_up_then_down_separately(self):
        args = {'db_path': self.db, 'table': 'people', 'approve_write': True}
        up = D.run('safe_migration', dict(args, direction='up',
                                          add_columns=[{'name': 'tier', 'type': 'TEXT', 'default': 'x'}]))['result']
        self.assertEqual(up['status'], 'applied')
        self.assertEqual(query(self.db, 'SELECT COUNT(*) FROM people WHERE tier = ?', ('x',)), [(40,)])
        down = D.run('safe_migration', dict(args, direction='down'))['result']
        self.assertEqual(down['status'], 'applied')
        self.assertTrue(down['original_values_identical'])
        self.assertNotIn('tier', down['after']['columns'])

    def test_failure_rolls_back(self):
        before = query(self.db, 'SELECT * FROM people ORDER BY id')
        r = D.run('safe_migration', {'db_path': self.db, 'table': 'people', 'approve_write': True,
                                     'add_columns': [{'name': 'ok_col', 'type': 'TEXT'},
                                                     {'name': 'name', 'type': 'TEXT'}]})['result']
        self.assertEqual(r['status'], 'rolled_back')
        self.assertFalse(r['steps'][0]['ok'])
        self.assertFalse(r['after']['backup_table_exists'])
        self.assertEqual(r['after']['columns'], ['id', 'name', 'score'])
        self.assertEqual(query(self.db, 'SELECT * FROM people ORDER BY id'), before)


class TestImportTabular(unittest.TestCase):  # 23.06
    MAP = {'الاسم': {'to': 'name', 'type': 'text'}, 'المبلغ': {'to': 'amount', 'type': 'decimal'},
           'التاريخ': {'to': 'paid_on', 'type': 'date'}}

    def test_missing_required_column(self):
        r = D.run('import_tabular', {'content': 'الاسم,التاريخ\nا,2026-01-01\n', 'mapping': self.MAP,
                                     'approve_write': True})['result']
        self.assertEqual(r['status'], 'rejected')
        self.assertEqual(r['missing_columns'], ['المبلغ'])
        self.assertIn('المبلغ', r['reason'])
        self.assertFalse(r['changed'])

    def test_cp1256_decoded_and_written(self):
        text = 'الاسم,المبلغ,التاريخ,زيادة\r\nمحمد,"1,000.10",2026-02-01,x\r\nفاطمة,25.5,2026-02-03,y\r\n'
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / 'data.csv'
            src.write_bytes(text.encode('cp1256'))
            db = str(Path(tmp) / 'out.sqlite3')
            pending = D.run('import_tabular', {'path': str(src), 'mapping': self.MAP, 'db_path': db})['result']
            self.assertEqual(pending['status'], 'approval_required')
            self.assertFalse(Path(db).exists())
            prev = pending['preview']
            self.assertEqual(prev['encoding'], 'cp1256')
            self.assertEqual([a['ok'] for a in prev['encoding_attempts']], [False, False, True])
            self.assertEqual(prev['extra_columns'], ['زيادة'])
            r = D.run('import_tabular', {'path': str(src), 'mapping': self.MAP, 'db_path': db,
                                         'approve_write': True})['result']
            self.assertEqual(r['written'], 2)
            self.assertEqual(query(db, 'SELECT name, amount, paid_on FROM imported ORDER BY "_rr_id"'),
                             [('محمد', '1000.10', '2026-02-01'), ('فاطمة', '25.5', '2026-02-03')])

    def test_bad_value_rejects_everything(self):
        csv_text = 'الاسم,المبلغ,التاريخ\nا,12.5,2026-01-01\nب,abc,2026-01-02\nج,1,2,3\n'
        r = D.run('import_tabular', {'content': csv_text, 'mapping': self.MAP, 'approve_write': True})['result']
        self.assertEqual(r['status'], 'rejected')
        self.assertTrue(any(e['row'] == 2 and e['column'] == 'المبلغ' for e in r['errors']))

    def test_json_and_utf8_bom(self):
        payload = json.dumps([{'الاسم': 'س', 'المبلغ': '3.30', 'التاريخ': '2026-03-01'}], ensure_ascii=False)
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / 'd.json'
            src.write_bytes(b'\xef\xbb\xbf' + payload.encode('utf-8'))
            r = D.run('import_tabular', {'path': str(src), 'fmt': 'json', 'mapping': self.MAP})['result']
            self.assertEqual(r['preview']['encoding'], 'utf-8-sig')
            self.assertEqual(r['preview']['preview'][0]['amount'], '3.30')


class TestProtectSensitive(unittest.TestCase):  # 23.07
    KEY = 'caller-secret-key-0123456789'

    def test_masked_iban_only_and_key_absent(self):
        out = D.run('protect_sensitive', {'pseudonymise': ['iban'], 'pseudonym_key': self.KEY})
        blob = json.dumps(out, ensure_ascii=False)
        for raw in ('SA0380000000608010167519', 'EG380019000500000000263180002', 'EG800002000156789012345180002',
                    '+966500000001', '1012345678', self.KEY):
            self.assertNotIn(raw, blob)
        rows = out['result']['rows']
        self.assertEqual(rows[0]['iban'], 'SA******************7519')
        self.assertEqual(rows[0]['iban_pseudonym'], rows[2]['iban_pseudonym'])
        self.assertNotEqual(rows[0]['iban_pseudonym'], rows[1]['iban_pseudonym'])
        expected = 'ps_' + hmac.new(self.KEY.encode(), b'iban:SA0380000000608010167519',
                                                  hashlib.sha256).hexdigest()[:24]
        self.assertEqual(rows[0]['iban_pseudonym'], expected)
        self.assertEqual(out['result']['value_detections'], {'note': 1})
        self.assertFalse(out['result']['key_stored'])

    def test_file_db_with_caller_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / 's.sqlite3')
            make_db(db, 'CREATE TABLE c (id INTEGER, acct TEXT, tel TEXT)',
                    [('INSERT INTO c VALUES (?, ?, ?)', [(1, 'GB82WEST12345698765432', '0123456789')])])
            r = D.run('protect_sensitive', {'db_path': db, 'table': 'c',
                                            'sensitive': {'acct': 'iban', 'tel': 'phone'}})['result']
            self.assertEqual(r['rows'][0], {'id': 1, 'acct': 'GB****************5432', 'tel': '*******789'})


class TestBackupRestore(unittest.TestCase):  # 23.08
    def test_file_backup_restore_hash_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = str(Path(tmp) / 'src.sqlite3')
            make_db(src, 'CREATE TABLE a (id INTEGER PRIMARY KEY, v TEXT, b BLOB); CREATE VIEW va AS SELECT v FROM a;',
                    [('INSERT INTO a (v, b) VALUES (?, ?)', [(f'قيمة {i}', bytes([i])) for i in range(50)])])
            work = Path(tmp) / 'work'
            work.mkdir()
            args = {'db_path': src, 'work_dir': str(work), 'backup_name': 'b.sqlite3', 'restore_name': 'r.sqlite3'}
            pending = D.run('backup_restore', args)['result']
            self.assertEqual(pending['status'], 'approval_required')
            self.assertEqual(list(work.iterdir()), [])
            r = D.run('backup_restore', dict(args, approve_write=True))['result']
            self.assertTrue(r['match'])
            self.assertEqual(r['restored_dump_sha256'], r['manifest']['dump_sha256'])
            manifest = json.loads((work / 'b.sqlite3.manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['backup_file_sha256'],
                             hashlib.sha256((work / 'b.sqlite3').read_bytes()).hexdigest())
            with contextlib.closing(sqlite3.connect(str(work / 'r.sqlite3'))) as conn:
                self.assertEqual(D.canonical_dump_sha256(conn)[0], manifest['dump_sha256'])
            with self.assertRaises(ValueError):          # never overwrites
                D.run('backup_restore', dict(args, approve_write=True))

    def test_in_memory_example(self):
        r = D.run('backup_restore', {'approve_write': True})['result']
        self.assertTrue(r['match'])
        self.assertEqual(r['restored_tables'], {'notes': 200})


class TestTimeSeries(unittest.TestCase):  # 23.09
    def test_empty_month_flagged(self):
        r = D.run('time_series', {})['result']
        months = {m['month']: m for m in r['months']}
        self.assertEqual(len(r['months']), 24)
        self.assertEqual(months['2025-03'], {'month': '2025-03', 'total': '0', 'count': 0, 'empty': True})
        self.assertEqual(r['empty_months'], ['2025-03'])
        self.assertEqual(months['2024-01']['total'], '120.25')
        yoy = {y['month']: y for y in r['yoy']}
        self.assertEqual(yoy['2025-01']['change'], '25.50')
        self.assertEqual(yoy['2025-03']['change_pct'], '-100.0000')
        self.assertEqual(len(r['seasonal_index']), 12)

    def test_range_and_bad_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / 'ts.sqlite3')
            make_db(db, 'CREATE TABLE s (d TEXT, amt TEXT)',
                    [('INSERT INTO s VALUES (?, ?)', [('2026-01-10', '0.10'), ('2026-01-11', '0.20'),
                                                       ('not a date', '1'), ('2026-04-01', '5')])])
            r = D.run('time_series', {'db_path': db, 'table': 's', 'date_column': 'd', 'amount_column': 'amt',
                                      'start': '2025-12', 'end': '2026-03'})['result']
            self.assertEqual([m['month'] for m in r['months']], ['2025-12', '2026-01', '2026-02', '2026-03'])
            self.assertEqual(r['months'][1]['total'], '0.30')
            self.assertEqual(r['empty_months'], ['2025-12', '2026-02', '2026-03'])
            self.assertEqual(r['rejected_count'], 1)
            self.assertEqual(r['rows_outside_range'], 1)
            self.assertIsNone(r['seasonal_index'])


class TestLineage(unittest.TestCase):  # 23.10
    def test_report_traces_to_exact_source_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / 'a.csv'
            a.write_bytes('region,amount\nشمال,10.10\nجنوب,5\nشمال,0.90\n'.encode('cp1256'))
            b = Path(tmp) / 'b.csv'
            b.write_text('region,amount\nجنوب,1\nشمال,4\n', encoding='utf-8')
            db = str(Path(tmp) / 'l.sqlite3')
            sources = [{'name': 'a.csv', 'revision': 'r1', 'path': str(a)},
                       {'name': 'b.csv', 'revision': 'r2', 'path': str(b)}]
            args = {'sources': sources, 'db_path': db, 'imported_at': '2026-11-21T10:00:00+00:00'}
            self.assertEqual(D.run('lineage', args)['result']['status'], 'approval_required')
            self.assertFalse(Path(db).exists())
            r = D.run('lineage', dict(args, approve_write=True, trace='شمال'))['result']
            self.assertEqual(len(r['report']), 1)
            north = r['report'][0]
            self.assertEqual(north['total'], '15.00')
            self.assertTrue(north['trace_verified'])
            got = [(s['source_name'], s['revision'], s['row_number']) for s in north['sources']]
            self.assertEqual(got, [('a.csv', 'r1', 1), ('a.csv', 'r1', 3), ('b.csv', 'r2', 2)])
            sha_a = hashlib.sha256(a.read_bytes()).hexdigest()
            self.assertEqual(north['sources'][0]['source_sha256'], sha_a)
            self.assertEqual(north['sources'][0]['imported_at'], '2026-11-21T10:00:00+00:00')
            again = D.run('lineage', dict(args, approve_write=True))['result']
            self.assertEqual((again['rows_inserted'], again['rows_skipped_duplicate']), (0, 5))
            self.assertEqual(query(db, 'SELECT COUNT(*) FROM "_rr_lineage_rows"'), [(5,)])

    def test_missing_column_rejected(self):
        with self.assertRaises(ValueError):
            D.run('lineage', {'sources': [{'name': 'x', 'revision': '1', 'content': 'region,qty\nn,1\n'}],
                              'approve_write': True})


if __name__ == '__main__':
    unittest.main()
