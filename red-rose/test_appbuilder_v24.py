"""Acceptance tests for appbuilder_v24 (topics 10.01-10.10)."""
import ast
import inspect
import json
import time
import unittest

import appbuilder_v24 as A

FORBIDDEN_IMPORTS = {'subprocess', 'socket', 'urllib', 'http', 'shutil', 'os', 'sqlite3', 'ctypes'}


class TestInterface(unittest.TestCase):
    def test_static_rules(self):
        tree = ast.parse(inspect.getsource(A))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name.split('.')[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split('.')[0])
            elif isinstance(node, ast.Call):
                self.assertNotIn(getattr(node.func, 'id', None),
                                 ('open', 'exec', 'eval', 'compile', 'print', '__import__'))
        self.assertFalse(imported & FORBIDDEN_IMPORTS)
        self.assertEqual(list(A.TOPICS), [f'10.{i:02d}' for i in range(1, 11)])
        self.assertEqual(set(A.TOPICS.values()), set(A.OPS))
        self.assertEqual(set(A.TOPIC_NAMES_AR), set(A.TOPICS))

    def test_every_op_runs_with_defaults(self):
        for op in A.TOPICS.values():
            with self.subTest(op=op):
                start = time.perf_counter()
                out = A.run(op, {})
                self.assertLess(time.perf_counter() - start, 2.0)
                self.assertEqual(set(out), {'op', 'result', 'assumptions', 'limits'})
                self.assertEqual(out['op'], op)
                self.assertTrue(out['assumptions'] and out['limits'])
                json.dumps(out, allow_nan=False)
                self.assertEqual(out, A.run(op, {}))  # deterministic

    def test_dispatcher_validation(self):
        with self.assertRaises(ValueError):
            A.run('nope', {})
        with self.assertRaises(ValueError):
            A.run('scaffold', [])
        with self.assertRaises(ValueError):
            A.run('scaffold', {1: 2})
        for op in A.OPS:
            with self.subTest(op=op), self.assertRaises(ValueError):
                A.run(op, {'bogus_param': 1})


class TestScaffold(unittest.TestCase):
    def test_kinds_parse(self):
        for kind in ('cli', 'web_static', 'api'):
            with self.subTest(kind=kind):
                r = A.run('scaffold', {'spec': {'name': 'shop', 'kind': kind,
                                                'entities': ['product', 'order']}})['result']
                self.assertIn('shop.py', r['files'])
                self.assertIn('test_shop.py', r['files'])
                self.assertIn('README.md', r['files'])
                for path, text in r['files'].items():
                    if path.endswith('.py'):
                        ast.parse(text)
                    if path.endswith('.json'):
                        json.loads(text)
                self.assertFalse(r['written'])

    def test_malicious_names_rejected(self):
        for bad in ('x; import os', 'Os', '1abc', 'class', 'a-b', '', 'x\nimport os'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                A.run('scaffold', {'spec': {'name': bad, 'kind': 'cli', 'entities': ['a']}})
        with self.assertRaises(ValueError):
            A.run('scaffold', {'spec': {'name': 'ok', 'entities': ['x; import os']}})
        with self.assertRaises(ValueError):
            A.run('scaffold', {'spec': {'kind': 'cli'}})

    def test_description_is_escaped(self):
        desc = "'''\nimport os\n\"\"\" <script>alert(1)</script>"
        r = A.run('scaffold', {'spec': {'name': 'site', 'kind': 'web_static',
                                        'entities': ['page'], 'description': desc}})['result']
        tree = ast.parse(r['files']['site.py'])
        top_imports = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
        self.assertEqual([a.name for n in top_imports for a in n.names], ['html'])
        self.assertTrue(r['description_roundtrip'])
        self.assertNotIn('<script>', r['files']['index.html'])
        self.assertNotIn('<script>', r['files']['README.md'])


class TestRtlUi(unittest.TestCase):
    def test_rtl_aria_and_escaping(self):
        r = A.run('rtl_ui', {'title': 'لوحة', 'sections': [
            {'id': 'a', 'title': 'أول', 'body': '<script>alert(1)</script>'},
            {'id': 'b', 'title': '"x" <img src=x onerror=1>'}]})['result']
        page = r['html']
        self.assertIn('<html lang="ar" dir="rtl">', page)
        self.assertIn('role="tablist"', page)
        self.assertEqual(page.count('role="tab" id='), 2)
        self.assertEqual(page.count('aria-selected="true" aria-controls="panel-a"'), 1)
        self.assertEqual(page.count('aria-selected="false" aria-controls="panel-b"'), 1)
        self.assertEqual(page.count('role="tabpanel" id='), 2)
        self.assertIn('aria-labelledby="tab-a"', page)
        self.assertNotIn('<script>alert', page)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', page)
        self.assertNotIn('<img', page)
        self.assertEqual(page.count('<script'), 1)
        self.assertNotIn('src=', page.replace('&lt;img src=x', ''))
        self.assertIn('@media (max-width:640px)', page)
        self.assertIn('@media (min-width:1024px)', page)
        self.assertTrue(all(r['checks'].values()))

    def test_no_script_option_and_validation(self):
        r = A.run('rtl_ui', {'include_script': False})['result']
        self.assertNotIn('<script', r['html'])
        with self.assertRaises(ValueError):
            A.run('rtl_ui', {'sections': [{'id': 'Bad Id', 'title': 't'}]})
        with self.assertRaises(ValueError):
            A.run('rtl_ui', {'sections': [{'id': 'a', 'title': 't'}, {'id': 'a', 'title': 'u'}]})


class TestOpenApi(unittest.TestCase):
    def test_crud_and_scopes(self):
        r = A.run('openapi_spec', {'resources': [
            {'name': 'book', 'fields': {'title': 'string', 'pages': 'integer'}}]})['result']
        spec = json.loads(r['files']['openapi.json'])
        self.assertTrue(spec['openapi'].startswith('3.0'))
        self.assertEqual(set(spec['paths']['/books']) - {'parameters'}, {'get', 'post'})
        self.assertEqual(set(spec['paths']['/books/{id}']) - {'parameters'},
                         {'get', 'put', 'delete'})
        ids = set()
        for item in spec['paths'].values():
            for method, op in item.items():
                if method == 'parameters':
                    continue
                ids.add(op['operationId'])
                scopes = op['security'][0]['oauth2']
                if method == 'get':
                    self.assertEqual(scopes, ['book:read'])
                else:
                    self.assertEqual(scopes, ['book:write'])
        self.assertEqual(ids, {'list_book', 'get_book', 'create_book', 'update_book',
                               'delete_book'})
        self.assertTrue(r['checks']['valid'])
        self.assertEqual(r['checks']['problems'], [])

    def test_validation(self):
        with self.assertRaises(ValueError):
            A.run('openapi_spec', {'resources': [{'name': 'x', 'fields': {'a': 'object'}}]})
        with self.assertRaises(ValueError):
            A.run('openapi_spec', {'version': '1.0'})


class TestSqlSchema(unittest.TestCase):
    def test_default_ddl_and_idempotent(self):
        r = A.run('sql_schema', {})['result']
        self.assertIn('CREATE TABLE IF NOT EXISTS "note"', r['ddl'])
        self.assertIn('PRIMARY KEY', r['ddl'])
        self.assertIn('REFERENCES "note"("id")', r['ddl'])
        self.assertIn('ADD COLUMN "done" INTEGER NOT NULL DEFAULT 0', r['ddl'])
        self.assertTrue(r['idempotent'])
        self.assertEqual(r['second_pass_statements'], 0)
        self.assertEqual(r['plan_sha256'], A.run('sql_schema', {})['result']['plan_sha256'])

    def test_duplicate_migration_entries_are_noops(self):
        mig = [{'id': '0001', 'op': 'add_column', 'table': 'note',
                'column': {'name': 'done', 'type': 'INTEGER', 'default': 0}},
               {'id': '0002', 'op': 'add_column', 'table': 'note',
                'column': {'name': 'done', 'type': 'INTEGER', 'default': 0}}]
        r = A.run('sql_schema', {'migrations': mig})['result']
        self.assertEqual(sum('ADD COLUMN' in p['sql'] for p in r['plan']), 1)
        self.assertTrue(r['idempotent'])

    def test_drop_refused(self):
        with self.assertRaises(ValueError):
            A.run('sql_schema', {'migrations': [{'id': '0001', 'sql': 'DROP TABLE note'}]})
        with self.assertRaises(ValueError):
            A.run('sql_schema', {'migrations': [{'id': '0001', 'op': 'drop_table',
                                                 'table': 'note'}]})
        with self.assertRaises(ValueError):
            A.run('sql_schema', {'migrations': [{'id': '0001', 'op': 'rename_table',
                                                 'table': 'note', 'new_name': 'n'}]})
        with self.assertRaises(ValueError):
            A.run('sql_schema', {'migrations': [
                {'id': '0001', 'sql': 'CREATE TABLE IF NOT EXISTS a (id INTEGER); DROP TABLE b'}]})
        r = A.run('sql_schema', {'allow_destructive': True, 'migrations': [
            {'id': '0001', 'op': 'drop_table', 'table': 'tag'}]})['result']
        self.assertEqual(r['destructive_statements'], ['0001'])
        self.assertTrue(r['idempotent'])

    def test_order_and_fk_validation(self):
        with self.assertRaises(ValueError):
            A.run('sql_schema', {'migrations': [
                {'id': '0002', 'sql': 'CREATE INDEX IF NOT EXISTS i ON note (id)'},
                {'id': '0001', 'sql': 'CREATE INDEX IF NOT EXISTS j ON note (id)'}]})
        with self.assertRaises(ValueError):
            A.run('sql_schema', {'migrations': [], 'tables': [{'name': 'a', 'columns': [
                {'name': 'id', 'type': 'INTEGER', 'pk': True},
                {'name': 'b_id', 'type': 'INTEGER', 'ref': 'missing.id'}]}]})


class TestSessionTokens(unittest.TestCase):
    KEY = 'super-secret-key-XYZ-123456'

    def issue(self, **kw):
        params = {'action': 'issue', 'key': self.KEY, 'subject': 'u1',
                  'scopes': ['notes:read'], 'issued_at': 1000, 'ttl': 60}
        params.update(kw)
        return A.run('session_tokens', params)

    def verify(self, token, now, scope='notes:read', key=None):
        return A.run('session_tokens', {'action': 'verify', 'key': key or self.KEY,
                                        'token': token, 'now': now,
                                        'required_scope': scope})['result']

    def test_valid_expired_tampered_scope(self):
        out = self.issue()
        token = out['result']['token']
        self.assertNotIn(self.KEY, json.dumps(out, ensure_ascii=False))
        self.assertTrue(self.verify(token, 1001)['valid'])
        self.assertEqual(self.verify(token, 1060)['reason'], 'expired')
        self.assertEqual(self.verify(token, 1001, 'notes:write')['reason'], 'wrong_scope')
        self.assertEqual(self.verify(token, 1001, key='another-key-000000000')['reason'],
                         'bad_signature')
        for i in range(len(token)):
            if token[i] == '.':
                continue
            alt = token[:i] + ('A' if token[i] != 'A' else 'B') + token[i + 1:]
            self.assertFalse(self.verify(alt, 1001)['valid'], i)
        verify_out = A.run('session_tokens', {'action': 'verify', 'key': self.KEY,
                                              'token': token, 'now': 1001})
        self.assertNotIn(self.KEY, json.dumps(verify_out, ensure_ascii=False))

    def test_demo_and_validation(self):
        r = A.run('session_tokens', {})['result']
        self.assertTrue(r['all_as_expected'])
        self.assertTrue(r['demo_key_used'])
        with self.assertRaises(ValueError):
            A.run('session_tokens', {'action': 'issue'})
        with self.assertRaises(ValueError):
            A.run('session_tokens', {'action': 'issue', 'key': 'short'})
        with self.assertRaises(ValueError):
            A.run('session_tokens', {'action': 'verify', 'key': self.KEY, 'now': 5})
        with self.assertRaises(ValueError):
            A.run('session_tokens', {'action': 'issue', 'key': self.KEY, 'ttl': True})


class TestRouter(unittest.TestCase):
    PAGES = [{'id': 'a', 'component': 'PageA', 'links': ['#/b']},
             {'id': 'b', 'component': 'PageB', 'links': ['#/c']},
             {'id': 'c', 'component': 'PageC', 'links': ['#/']},
             {'id': 'lost', 'component': 'Lost', 'links': []}]
    ROUTES = [{'path': '#/', 'page': 'a'}, {'path': '#/b', 'page': 'b'},
              {'path': '#/c', 'page': 'c'}, {'path': '#/lost', 'page': 'lost'}]

    def test_back_twice_returns_to_a(self):
        r = A.run('router_spec', {'pages': self.PAGES, 'routes': self.ROUTES, 'start': '#/',
                                  'navigation': ['#/b', '#/c', 'back', 'back']})['result']
        self.assertEqual(r['history']['current'], '#/')
        self.assertEqual(r['trail'], ['#/', '#/b', '#/c', '#/b', '#/'])
        self.assertEqual(r['unreachable_pages'], ['lost'])

    def test_forward_truncation_and_defaults(self):
        r = A.run('router_spec', {'pages': self.PAGES, 'routes': self.ROUTES,
                                  'navigation': ['#/b', 'back', '#/c', 'forward', 'back',
                                                 'back', '#/nowhere']})['result']
        self.assertEqual(r['history']['stack'], ['#/', '#/c'])
        self.assertEqual(r['history']['current'], '#/')
        self.assertIn('ignored', r['events'][-1])
        d = A.run('router_spec', {})['result']
        self.assertEqual(d['unreachable_pages'], ['archive'])

    def test_duplicate_route_rejected(self):
        routes = self.ROUTES + [{'path': '#/b', 'page': 'c'}]
        with self.assertRaises(ValueError):
            A.run('router_spec', {'pages': self.PAGES, 'routes': routes})
        with self.assertRaises(ValueError):
            A.run('router_spec', {'pages': self.PAGES + [self.PAGES[0]], 'routes': self.ROUTES})


class TestFeatureTests(unittest.TestCase):
    SPEC = {'module': 'textutils', 'name': 'slugify', 'params': ['text'],
            'examples': [{'args': ['Hello World'], 'expected': 'hello-world'},
                         {'args': ['  A  '], 'expected': 'a'},
                         {'args': [''], 'expected': ''}],
            'invalid': [{'args': [None], 'raises': 'TypeError'},
                        {'args': [5], 'raises': 'TypeError'}]}

    def test_generated_module(self):
        r = A.run('feature_tests', {'function': self.SPEC})['result']
        text = r['files']['test_slugify.py']
        tree = ast.parse(text)
        names = [n.name for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name.startswith('test_')]
        self.assertEqual(sum(n.startswith('test_example_') for n in names), 3)
        self.assertEqual(sum(n.startswith('test_invalid_') for n in names), 2)
        self.assertEqual(sum(n.startswith('test_integration') for n in names), 1)
        self.assertEqual(r['counts']['total'], 6)
        self.assertTrue(r['self_check']['asserted_values_match_spec'])
        self.assertTrue(r['self_check']['all_mutants_detected'])
        self.assertIn('from textutils import slugify', text)

    def test_validation(self):
        bad = dict(self.SPEC, name='x; import os')
        with self.assertRaises(ValueError):
            A.run('feature_tests', {'function': bad})
        bad = dict(self.SPEC, invalid=[{'args': [1], 'raises': 'SystemExit'}])
        with self.assertRaises(ValueError):
            A.run('feature_tests', {'function': bad})
        bad = dict(self.SPEC, examples=[{'args': [1, 2], 'expected': 3}])
        with self.assertRaises(ValueError):
            A.run('feature_tests', {'function': bad})
        bad = dict(self.SPEC, examples=[{'args': [object()], 'expected': 3}])
        with self.assertRaises(ValueError):
            A.run('feature_tests', {'function': bad})


class TestDocs(unittest.TestCase):
    SRC = '''"""Tool. Commands: build and serve."""


def build(path: str, *, force=False) -> int:
    """Build the site."""
    return 0


def clean():
    pass
'''

    def test_undocumented_cli_command_reported(self):
        r = A.run('docs_from_code', {'source': self.SRC, 'module_name': 'tool', 'cli': {
            'prog': 'tool', 'commands': ['build', 'serve', 'clean']}})['result']
        self.assertEqual(r['undocumented_cli_commands'], ['clean'])
        self.assertFalse(r['cli_fully_documented'])
        self.assertEqual(r['missing_docstrings'], ['clean'])
        self.assertIn('def build(path: str, *, force=False) -> int', r['markdown'])
        d = A.run('docs_from_code', {})['result']
        self.assertEqual(d['undocumented_cli_commands'], ['purge'])

    def test_validation(self):
        with self.assertRaises(ValueError):
            A.run('docs_from_code', {'source': 'def (:'})
        with self.assertRaises(ValueError):
            A.run('docs_from_code', {'source': 'x = 1', 'cli': {'commands': ['Bad Name']}})


class TestPackage(unittest.TestCase):
    FILES = {'app/main.py': 'print("hi")\n', 'README.md': '# app\n'}

    def test_verified_and_tampered(self):
        r = A.run('package_manifest', {'name': 'app', 'version': '2.1.0', 'files': self.FILES,
                                       'dependencies': ['requests==2.32.3']})['result']
        self.assertTrue(r['verified'])
        self.assertEqual(len(r['manifest']['files']), 2)
        t = A.run('package_manifest', {'name': 'app', 'version': '2.1.0', 'files': self.FILES,
                                       'tamper': {'app/main.py': 'print("evil")\n'}})['result']
        self.assertFalse(t['verified'])
        self.assertEqual(t['install_simulation']['mismatched_files'], ['app/main.py'])

    def test_rejections(self):
        for dep in ('requests', 'requests>=2.0', 'requests==2.*', 'requests~=2.1'):
            with self.subTest(dep=dep), self.assertRaises(ValueError):
                A.run('package_manifest', {'files': self.FILES, 'dependencies': [dep]})
        with self.assertRaises(ValueError):
            A.run('package_manifest', {'version': 'v1'})
        for path in ('../evil.py', '/abs.py', 'C:/x.py', 'a\\b.py', 'a/../b.py'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                A.run('package_manifest', {'files': {path: 'x'}})


class TestDeploy(unittest.TestCase):
    def test_refused_without_rollback(self):
        for res in ('fail', 'skipped'):
            r = A.run('deploy_plan', {'staging_results': {'rollback_drill_staging': res},
                                      'approved_by': 'owner'})['result']
            self.assertEqual(r['production_status'], 'refused')
            self.assertIn('rollback', r['reason'])
            self.assertFalse(any(e['step'] == 'deploy_production' and e['result'] != 'refused'
                                 for e in r['simulation']))

    def test_gate_and_ready(self):
        self.assertEqual(A.run('deploy_plan', {})['result']['production_status'], 'blocked')
        r = A.run('deploy_plan', {'approved_by': 'owner'})['result']
        self.assertEqual(r['production_status'], 'ready_simulated')
        ids = [s['id'] for s in r['plan']]
        self.assertLess(ids.index('rollback_drill_staging'), ids.index('approval_gate'))
        self.assertLess(ids.index('approval_gate'), ids.index('deploy_production'))
        self.assertFalse(r['executed'])

    def test_no_secret_values(self):
        with self.assertRaises(ValueError):
            A.run('deploy_plan', {'secrets': {'DATABASE_URL': 'postgres://u:pw@h/db'}})
        with self.assertRaises(ValueError):
            A.run('deploy_plan', {'secrets': ['DATABASE_URL=postgres://u:pw@h/db']})
        out = json.dumps(A.run('deploy_plan', {'secrets': ['API_TOKEN'], 'approved_by': 'o'}))
        self.assertIn('secret_ref:production/API_TOKEN', out)
        self.assertNotIn('=', out.replace('==', ''))


if __name__ == '__main__':
    unittest.main()
