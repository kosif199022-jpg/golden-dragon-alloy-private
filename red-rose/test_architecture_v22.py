"""Acceptance tests for architecture_v22 (topics 02.01, 02.03-02.10)."""
import ast
import hashlib
import json
import unittest
from pathlib import Path

import architecture_v22 as A

FORBIDDEN_IMPORTS = {'subprocess', 'socket', 'urllib', 'http', 'shutil', 'os', 'sqlite3', 'ctypes'}


class TestInterface(unittest.TestCase):
    def test_topics_and_ops(self):
        expected = ['02.01'] + [f'02.{i:02d}' for i in range(3, 11)]
        self.assertEqual(sorted(A.TOPICS), expected)
        self.assertEqual(set(A.TOPICS.values()), set(A.OPS))
        self.assertEqual(set(A.TOPIC_NAMES_AR), set(A.TOPICS))

    def test_run_all_defaults_json(self):
        for op in A.OPS:
            with self.subTest(op=op):
                out = A.run(op, {})
                self.assertEqual(out['op'], op)
                self.assertEqual(set(out), {'op', 'result', 'assumptions', 'limits'})
                self.assertTrue(out['assumptions'] and out['limits'])
                self.assertTrue(all(isinstance(s, str) for s in out['assumptions'] + out['limits']))
                json.dumps(out, allow_nan=False)
                self.assertEqual(out, A.run(op, {}))  # deterministic

    def test_run_rejects_bad_input(self):
        bad = [
            ('nope', {}), ('cache_key', []), ('cache_key', {'zzz': 1}),
            ('cache_key', {f'k{i}': 1 for i in range(25)}),
            ('cli_spec_check', {'spec': 'x'}), ('cli_spec_check', {'argv': 'render'}),
            ('message_schema', {'schemas': [{'name': 'a', 'version': 1, 'fields': {}}]}),
            ('message_schema', {'schemas': [{'name': 'a', 'version': True, 'fields': {}}],
                                'message': {}}),
            ('distribution_guard', {'paths': [5]}), ('distribution_guard', {'max_bytes': True}),
            ('dependency_status', {'tasks': {'t': ['ffmpeg >> 6']}}),
            ('dependency_status', {'available': {'ffmpeg': 6}}),
            ('config_redact', {'defaults': {'fps': 30}, 'file_config': {'fps': 'thirty'}}),
            ('config_redact', {'defaults': {'fps': 30}, 'env': {'fps': 'abc'}}),
            ('config_redact', {'defaults': {'fps': 30}, 'file_config': {'nope': 1}}),
            ('cache_key', {'permission_scope': 'read'}), ('cache_key', {'input_hashes': {'a': 'zz'}}),
            ('cache_key', {'params': {'x': float('nan')}}),
            ('checkpoint_resume', {'stages': ['rm_rf']}), ('checkpoint_resume', {'interrupt_at': 99}),
            ('path_portability', {'paths': [1]}), ('path_portability', {'compare': [['a']]}),
            ('semver_migrate', {'current': '1.0'}), ('semver_migrate', {'versions': ['01.0.0']}),
            ('semver_migrate', {'data': {}, 'migrations': [{'from': '2.0.0', 'to': '1.0.0', 'ops': []}]}),
        ]
        for op, params in bad:
            with self.subTest(op=op, params=params):
                with self.assertRaises(ValueError):
                    A.run(op, params)

    def test_direct_call_unknown_kw(self):
        for fn in A.OPS.values():
            with self.assertRaises(ValueError):
                fn(bogus=1)

    def test_module_is_pure(self):
        tree = ast.parse(Path(A.__file__).read_text(encoding='utf-8'))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name.split('.')[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split('.')[0])
            elif isinstance(node, ast.Call):
                self.assertNotIn(getattr(node.func, 'id', None),
                                 ('open', 'exec', 'eval', 'compile', 'print'))
        self.assertFalse(imported & FORBIDDEN_IMPORTS)


class TestCliSpec(unittest.TestCase):  # 02.01
    def test_every_command_parses_example(self):
        r = A.run('cli_spec_check', {})['result']
        self.assertTrue(r['spec_valid'])
        self.assertEqual(set(r['examples']), {'render', 'doctor'})
        self.assertTrue(r['all_examples_parse'])
        p = r['parsed']
        self.assertTrue(p['ok'])
        self.assertEqual(p['values'], {'input': 'in.mp4', 'fps': 25, 'preset': 'final', 'dry_run': False})

    def test_unknown_flag_and_command_rejected(self):
        for argv, msg in [(['render', 'a.mp4', '--bogus'], 'unknown flag'),
                          (['explode'], 'unknown command'), (['render'], 'missing required'),
                          (['render', 'a', '--fps', 'x'], 'integer'),
                          (['render', 'a', '--preset', 'ultra'], 'not one of'),
                          (['render', 'a', 'b'], 'unexpected positional')]:
            p = A.run('cli_spec_check', {'argv': argv})['result']['parsed']
            self.assertFalse(p['ok'], argv)
            self.assertIn(msg, p['error'])

    def test_bad_spec_reported(self):
        spec = {'commands': {'go': {'args': {'--n': {'type': 'int', 'default': 'x'},
                                             'pos': {'type': 'flag'}}}}}
        r = A.run('cli_spec_check', {'spec': spec, 'argv': ['go']})['result']
        self.assertFalse(r['spec_valid'])
        self.assertIsNone(r['parsed'])
        self.assertGreaterEqual(len(r['spec_issues']), 2)


class TestMessageSchema(unittest.TestCase):  # 02.03
    def test_v1_upgraded_to_v2(self):
        r = A.run('message_schema', {})['result']
        self.assertTrue(r['valid'])
        self.assertEqual(r['upgrade_path'], [[1, 2]])
        self.assertEqual(r['upgraded'], {'name': 'job.request', 'version': 2,
                                         'data': {'input_path': 'a.mp4', 'fps': 30, 'priority': 5}})

    def test_unknown_field_and_wrong_version_rejected(self):
        schemas = [{'name': 'm', 'version': 1, 'fields': {'a': 'int'}}]
        r = A.run('message_schema', {'schemas': schemas,
                                     'message': {'name': 'm', 'version': 1, 'data': {'a': 1, 'b': 2}}})
        self.assertFalse(r['result']['valid'])
        self.assertIn("unknown field 'b'", r['result']['errors'])
        r = A.run('message_schema', {'schemas': schemas,
                                     'message': {'name': 'm', 'version': 3, 'data': {'a': 1}}})
        self.assertFalse(r['result']['valid'])
        r = A.run('message_schema', {'schemas': schemas,
                                     'message': {'name': 'm', 'version': 1, 'data': {'a': True}}})
        self.assertFalse(r['result']['valid'])


class TestDistributionGuard(unittest.TestCase):  # 02.04
    def test_memory_db_blocks(self):
        r = A.run('distribution_guard', {'paths': ['rose.py', 'data/memory.sqlite3']})['result']
        self.assertFalse(r['safe_to_package'])
        self.assertEqual(r['flagged'][0]['path'], 'data/memory.sqlite3')

    def test_ignored_paths_pass(self):
        r = A.run('distribution_guard', {'paths': ['rose.py', 'data/memory.sqlite3', 'kb/alloy.db',
                                                   'owner-memory/x.json', '.env'],
                                         'ignore': ['data/', '*.db', 'owner-memory/', '.env*']})['result']
        self.assertTrue(r['safe_to_package'])
        self.assertEqual(len(r['ignored']), 4)

    def test_default_flags(self):
        r = A.run('distribution_guard', {})['result']
        flagged = {f['path'] for f in r['flagged']}
        self.assertIn('.env.local', flagged)
        self.assertIn('owner-memory/notes.json', flagged)
        self.assertNotIn('cache/big.bin', flagged)
        r = A.run('distribution_guard', {'paths': ['credentials\\token.json', '../x.py',
                                                   {'path': 'a.bin', 'size': 11}], 'max_bytes': 10})
        self.assertEqual(len(r['result']['flagged']), 3)


class TestDependencyStatus(unittest.TestCase):  # 02.05
    def test_missing_and_old(self):
        r = A.run('dependency_status', {'tasks': {'render': ['ffmpeg>=6.0'], 'svg': ['cairosvg>=2.5'],
                                                  'ok': ['python>=3.10']},
                                        'available': {'cairosvg': '2.4.9', 'python': '3.12.1'}})['result']
        self.assertEqual(r['tasks']['render']['status'], 'blocked')
        self.assertEqual(r['tasks']['render']['missing'], ['ffmpeg'])
        self.assertIn('ffmpeg', r['tasks']['render']['reasons'][0])
        self.assertEqual(r['tasks']['svg']['status'], 'blocked')
        self.assertIn('2.4.9', r['tasks']['svg']['reasons'][0])
        self.assertEqual(r['ready'], ['ok'])

    def test_semantic_compare(self):
        r = A.run('dependency_status', {'tasks': {'t': ['x>=1.10']}, 'available': {'x': '1.9.9'}})
        self.assertEqual(r['result']['tasks']['t']['status'], 'blocked')
        r = A.run('dependency_status', {'tasks': {'t': ['x>=1.9']}, 'available': {'x': 'v1.10.0-rc'}})
        self.assertEqual(r['result']['tasks']['t']['status'], 'ready')


class TestConfigRedact(unittest.TestCase):  # 02.06
    TOKEN = 'ghp_' + 'A1b2C3d4E5f6G7h8I9j0K1l2M3n4'

    def test_token_never_printed(self):
        defaults = {'service': {'auth_token': '', 'url': ''}, 'note': '', 'fps': 30, 'keyframes': 4}
        r = A.run('config_redact', {'defaults': defaults,
                                    'file_config': {'service': {'auth_token': self.TOKEN}},
                                    'env': {'note': 'using ' + self.TOKEN + ' today', 'fps': '24',
                                            'service.url': 'https://u:p4ssw0rd@host/x'}})
        text = json.dumps(r)
        self.assertNotIn(self.TOKEN, text)
        self.assertNotIn('p4ssw0rd', text)
        res = r['result']
        self.assertEqual(res['printable']['fps'], 24)
        self.assertEqual(res['printable']['keyframes'], 4)
        self.assertEqual(res['sources']['fps'], 'env')
        self.assertIn('service.auth_token', res['redacted_paths'])

    def test_default_example_hides_key(self):
        r = A.run('config_redact', {})
        self.assertNotIn('sk-DEMO0000placeholder0000', json.dumps(r))
        self.assertEqual(r['result']['printable']['render'], {'fps': 25, 'scale': 0.5, 'preset': 'draft'})
        self.assertIs(r['result']['printable']['debug'], True)

    def test_type_errors_rejected_without_echo(self):
        with self.assertRaises(ValueError) as cm:
            A.run('config_redact', {'defaults': {'port': 1}, 'file_config': {'port': self.TOKEN}})
        self.assertNotIn(self.TOKEN, str(cm.exception))
        with self.assertRaises(ValueError):
            A.run('config_redact', {'defaults': {'on': False}, 'env': {'on': 'maybe'}})


class TestCacheKey(unittest.TestCase):  # 02.07
    def test_scope_and_code_change_miss(self):
        r = A.run('cache_key', {})['result']
        self.assertEqual(r['hit_checks'], {'same': True, 'params_changed': False, 'input_changed': False,
                                           'code_version_changed': False,
                                           'permission_scope_changed': False})
        self.assertEqual(r['key'], hashlib.sha256(r['canonical'].encode()).hexdigest())

    def test_cache_class(self):
        h = hashlib.sha256(b'in').hexdigest()
        comp = dict(capability='c', params={'a': 1}, input_hashes={'f': h}, code_version='1',
                    permission_scope=['read', 'write'])
        cache = A.PermissionAwareCache()
        cache.put({'v': 1}, **comp)
        self.assertTrue(cache.get(**dict(comp, permission_scope=['write', 'read', 'read']))['hit'])
        self.assertFalse(cache.get(**dict(comp, permission_scope=['read']))['hit'])
        self.assertFalse(cache.get(**dict(comp, code_version='2'))['hit'])
        cache.put({'v': 2}, **dict(comp, code_version='2'))  # supersedes the v1 entry
        self.assertFalse(cache.get(**comp)['hit'])
        self.assertEqual(len(cache), 1)
        self.assertEqual(cache.invalidate(capability='c'), 1)
        with self.assertRaises(ValueError):
            cache.get(**dict(comp, extra=1))


class TestCheckpointResume(unittest.TestCase):  # 02.08
    def test_builtin_resume_equals_uninterrupted(self):
        for k in range(0, 6):
            r = A.run('checkpoint_resume', {'interrupt_at': k})['result']
            self.assertTrue(r['matches_uninterrupted'], k)
            self.assertTrue(r['each_stage_ran_once'], k)
        self.assertEqual(r['output'], ['cat', 'dog', 'the'])

    def test_custom_stages_interrupt_and_crash(self):
        calls = {}

        def stage(name, fn):
            def wrapped(d):
                calls[name] = calls.get(name, 0) + 1
                return fn(d)
            return (name, wrapped)
        stages = [stage('double', lambda d: [x * 2 for x in d]), stage('inc', lambda d: [x + 1 for x in d]),
                  stage('sum', sum), stage('square', lambda d: d * d)]
        clean = A.run_pipeline([(n, f) for n, f in stages], [1, 2, 3])
        self.assertEqual(clean['output'], 225)
        calls.clear()
        first = A.run_pipeline(stages, [1, 2, 3], stop_after=2)
        self.assertEqual(first['status'], 'interrupted')
        self.assertEqual(first['ran'], ['double', 'inc'])
        second = A.run_pipeline(stages, [1, 2, 3], checkpoint=first['checkpoint'])
        self.assertEqual(second['output'], clean['output'])
        self.assertEqual(second['skipped'], ['double', 'inc'])
        self.assertEqual(calls, {'double': 1, 'inc': 1, 'sum': 1, 'square': 1})
        # changed input invalidates everything downstream
        third = A.run_pipeline(stages, [1, 2, 4], checkpoint=second['checkpoint'])
        self.assertEqual(third['invalidated'], ['double', 'inc', 'sum', 'square'])
        self.assertEqual(third['output'], 289)
        # a crashing stage leaves a resumable checkpoint
        state = {'fail': True}

        def flaky(d):
            if state['fail']:
                raise RuntimeError('power cut')
            return d
        st = [('a', lambda d: d + 1), ('flaky', flaky), ('b', lambda d: d * 10)]
        r1 = A.run_pipeline(st, 1)
        self.assertEqual((r1['status'], r1['checkpoint'][1]['done']), ('failed', False))
        state['fail'] = False
        r2 = A.run_pipeline(st, 1, checkpoint=r1['checkpoint'])
        self.assertEqual((r2['status'], r2['output'], r2['skipped']), ('complete', 20, ['a']))

    def test_tampered_checkpoint_reruns(self):
        st = [('a', lambda d: d + 1), ('b', lambda d: d * 2)]
        cp = A.run_pipeline(st, 1)['checkpoint']
        cp[0]['output'] = 99
        r = A.run_pipeline(st, 1, checkpoint=cp)
        self.assertEqual((r['output'], r['ran']), (4, ['a']))

    def test_changed_data_param(self):
        r = A.run('checkpoint_resume', {'changed_data': 'b a'})['result']['changed_input']
        self.assertEqual(r['output'], ['a', 'b'])
        self.assertTrue(r['invalidated'])


class TestPathPortability(unittest.TestCase):  # 02.09
    def test_sample_set(self):
        arabic = 'تقارير/ملخص.txt'
        r = A.run('path_portability', {'paths': [arabic, 'src/main.py', 'CON.txt', 'docs/aux.md',
                                                 'a\\b.txt', 'x. ', 'A/File.txt', 'a/file.txt',
                                                 'bad\udcff.txt', 'q?.txt', 'p/' + 'n' * 300],
                                       'compare': [['src/./main.py', 'src/main.py'],
                                                   ['A/File.txt', 'a/file.txt']]})['result']
        items = {it['path']: it for it in r['paths']}
        for p in (arabic, 'src/main.py'):
            self.assertTrue(items[p]['same_parts'])
            self.assertTrue(items[p]['portable'], items[p])
        self.assertEqual(items[arabic]['name_windows'], 'ملخص.txt')
        self.assertEqual(items[arabic]['name_posix'], 'ملخص.txt')
        self.assertTrue(items[arabic]['round_trip'])
        self.assertIn('reserved_windows_name', items['CON.txt']['problems'])
        self.assertIn('reserved_windows_name', items['docs/aux.md']['problems'])
        self.assertIn('backslash_in_posix', items['a\\b.txt']['problems'])
        self.assertFalse(items['a\\b.txt']['same_parts'])
        self.assertIn('trailing_dot_or_space', items['x. ']['problems'])
        self.assertIn('non_utf8_surrogate', items['bad\udcff.txt']['problems'])
        self.assertIn('invalid_windows_character', items['q?.txt']['problems'])
        self.assertIn('windows_max_path', items['p/' + 'n' * 300]['problems'])
        self.assertEqual(r['case_collisions'], [['A/File.txt', 'a/file.txt']])
        self.assertEqual(r['compare'][0]['same_on_windows'], True)
        self.assertEqual(r['compare'][0]['same_on_posix'], True)
        self.assertEqual((r['compare'][1]['same_on_windows'], r['compare'][1]['same_on_posix']),
                         (True, False))
        json.dumps(r)


class TestSemverMigrate(unittest.TestCase):  # 02.10
    def test_ordering_and_compat(self):
        r = A.run('semver_migrate', {})['result']
        self.assertEqual(r['sorted_versions'],
                         ['0.9.9+build.7', '1.0.0-alpha', '1.0.0-alpha.1', '1.0.0-alpha.beta',
                          '1.0.0-beta', '1.0.0-beta.2', '1.0.0-beta.11', '1.0.0-rc.1', '1.0.0'])
        self.assertTrue(r['breaking'])
        self.assertEqual(A.semver_compare('1.0.0+a', '1.0.0+b'), 0)
        self.assertTrue(A.is_compatible('1.2.0', '1.9.3'))
        self.assertFalse(A.is_compatible('0.2.0', '0.3.0'))

    def test_upgrade_then_rollback(self):
        r = A.run('semver_migrate', {})['result']
        self.assertTrue(r['accepted'])
        self.assertTrue(r['round_trip_equal'])
        self.assertEqual(r['rolled_back'], {'title': 'Intro', 'res': 'hd', 'fps': 30})
        self.assertEqual(r['upgraded'], {'title': 'Intro', 'resolution': '1280x720', 'fps': 30, 'schema': 2})

    def test_lossy_rejected(self):
        data = {'q': 'high', 'fps': 30}
        lossy = [
            [{'op': 'remove', 'field': 'fps', 'default': 24}],
            [{'op': 'map', 'field': 'q', 'mapping': {'high': 'hq', 'max': 'hq'}}],
            [{'op': 'add', 'field': 'fps', 'default': 25}],
        ]
        for ops in lossy:
            with self.subTest(ops=ops):
                r = A.run('semver_migrate', {'current': '1.0.0', 'target': '1.1.0', 'data': data,
                                             'migrations': [{'from': '1.0.0', 'to': '1.1.0', 'ops': ops}]})
                self.assertFalse(r['result']['accepted'])
                self.assertIn('lossy', r['result']['rejected_reason'])
                self.assertIsNone(r['result']['upgraded'])
        self.assertEqual(data, {'q': 'high', 'fps': 30})

    def test_chain_and_missing_path(self):
        migs = [{'from': '1.0.0', 'to': '1.1.0', 'ops': [{'op': 'copy', 'from': 'a', 'to': 'b'}]},
                {'from': '1.1.0', 'to': '2.0.0', 'ops': [{'op': 'rename', 'from': 'a', 'to': 'c'}]}]
        r = A.run('semver_migrate', {'current': '1.0.0', 'target': '2.0.0', 'data': {'a': 1},
                                     'migrations': migs})['result']
        self.assertEqual(r['path'], [['1.0.0', '1.1.0'], ['1.1.0', '2.0.0']])
        self.assertEqual(r['upgraded'], {'b': 1, 'c': 1})
        r = A.run('semver_migrate', {'current': '1.0.0', 'target': '3.0.0', 'data': {'a': 1},
                                     'migrations': migs})['result']
        self.assertFalse(r['accepted'])

    def test_check_migration_callables(self):
        ok, _ = A.check_migration(lambda d: {**d, 'v': 2}, lambda d: {k: v for k, v in d.items() if k != 'v'},
                                  [{'a': 1}])
        self.assertTrue(ok)
        ok, why = A.check_migration(lambda d: {}, lambda d: d, [{'a': 1}])
        self.assertFalse(ok)


if __name__ == '__main__':
    unittest.main()
