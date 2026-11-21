"""Acceptance tests for code_analysis_v21 (topics 11.01-11.10)."""
import ast
import json
import time
import unittest
from pathlib import Path

import code_analysis_v21 as C

FORBIDDEN_IMPORTS = {'subprocess', 'socket', 'urllib', 'http', 'shutil', 'os', 'sqlite3', 'ctypes'}


class TestInterface(unittest.TestCase):
    def test_topics_and_ops(self):
        self.assertEqual(sorted(C.TOPICS), [f'11.{i:02d}' for i in range(1, 11)])
        self.assertEqual(set(C.TOPICS.values()), set(C.OPS))
        self.assertEqual(set(C.TOPIC_NAMES_AR), set(C.TOPICS))

    def test_run_all_defaults_json_and_budget(self):
        for op in C.OPS:
            with self.subTest(op=op):
                start = time.perf_counter()
                out = C.run(op, {})
                self.assertLess(time.perf_counter() - start, 3.0)
                self.assertEqual(out['op'], op)
                self.assertEqual(set(out), {'op', 'result', 'assumptions', 'limits'})
                self.assertTrue(out['assumptions'] and out['limits'])
                self.assertTrue(all(isinstance(s, str) for s in out['assumptions'] + out['limits']))
                json.dumps(out, allow_nan=False)

    def test_deterministic(self):
        for op in C.OPS:
            self.assertEqual(json.dumps(C.run(op, {}), sort_keys=True),
                             json.dumps(C.run(op, {}), sort_keys=True))

    def test_run_rejects_bad_input(self):
        bad = [
            ('nope', {}), ('syntax_check', []), ('syntax_check', {'shell': 'rm -rf /'}),
            ('syntax_check', {'files': {}}), ('syntax_check', {'files': 'x = 1'}),
            ('syntax_check', {'files': {'a.py': 1}}),
            ('syntax_check', {'files': {f'f{i}.py': '' for i in range(201)}}),
            ('syntax_check', {'files': {'big.py': 'x' * (200 * 1024 + 1)}}),
            ('duplicate_functions', {'threshold': 2}), ('duplicate_functions', {'min_nodes': True}),
            ('secret_scan', {'ignore_files': 'tests/*'}), ('secret_scan', {'ignore_hashes': ['zz']}),
            ('race_check', {'log': []}), ('race_check', {'log': [{'actor': 'a'}]}),
            ('race_check', {'log': [{'actor': 'a', 'op': 'delete', 'path': 'p', 't_start': 0, 't_end': 1}]}),
            ('race_check', {'log': [{'actor': 'a', 'op': 'read', 'path': 'p', 't_start': 2, 't_end': 1}]}),
            ('traceback_repro', {'traceback': 'nothing here'}), ('traceback_repro', {'before': 'ok'}),
            ('traceback_repro', {'before': 'ok', 'after': 'maybe'}),
            ('boundary_cases', {'spec': {'x': {'type': 'complex'}}}),
            ('boundary_cases', {'spec': {'x': {'type': 'int', 'min': 5, 'max': 1}}}),
            ('boundary_cases', {'spec': {'x': {'type': 'int'}}, 'results': {'nope:min': True}}),
            ('boundary_cases', {'spec': {'x': {'type': 'int', 'min': 0}}, 'results': {'x:min': 'yes'}}),
            ('diff_review', {'diff': ''}), ('diff_review', {'diff': 'just text\n'}),
            ('complexity', {'nested_threshold': 0}),
            ('syntax_check', {f'k{i}': 1 for i in range(25)}),
        ]
        for op, params in bad:
            with self.subTest(op=op, params=str(params)[:60]):
                with self.assertRaises(ValueError):
                    C.run(op, params)

    def test_module_is_pure(self):
        src = Path(C.__file__).read_text(encoding='utf-8')
        tree = ast.parse(src)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name.split('.')[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split('.')[0])
            elif isinstance(node, ast.Call):
                self.assertNotIn(getattr(node.func, 'id', None), ('open', 'exec', 'eval', 'compile', 'print'))
        self.assertFalse(imported & FORBIDDEN_IMPORTS)


class TestSyntaxCheck(unittest.TestCase):  # 11.01
    def test_error_line_and_valid_files(self):
        files = {'good.py': 'def f(x):\n    return x\n',
                 'bad.py': 'a = 1\nb = 2\nif a == :\n    pass\n'}
        r = C.run('syntax_check', {'files': files})['result']
        self.assertEqual(r['valid'], ['good.py'])
        self.assertEqual(len(r['errors']), 1)
        err = r['errors'][0]
        self.assertEqual((err['file'], err['line']), ('bad.py', 3))
        self.assertIsInstance(err['column'], int)
        self.assertTrue(err['message'])
        self.assertFalse(r['ok'])

    def test_indentation_error_and_all_valid(self):
        r = C.run('syntax_check', {'files': {'i.py': 'def f():\nreturn 1\n'}})['result']
        self.assertEqual(r['errors'][0]['line'], 2)
        self.assertEqual(r['errors'][0]['type'], 'IndentationError')
        r = C.run('syntax_check', {'files': {'a.py': 'x = 1\n', 'b.py': ''}})['result']
        self.assertTrue(r['ok'])
        self.assertEqual(r['valid'], ['a.py', 'b.py'])

    def test_code_is_not_executed(self):
        marker = {'hit': False}
        files = {'evil.py': 'raise SystemExit(3)\nimport this\n'}
        r = C.run('syntax_check', {'files': files})['result']
        self.assertTrue(r['ok'])
        self.assertFalse(marker['hit'])


class TestImportCycles(unittest.TestCase):  # 11.02
    def test_three_cycle_isolated(self):
        files = {'a.py': 'import b\n', 'b.py': 'from c import x\n', 'c.py': 'import a\nx = 1\n',
                 'd.py': 'import a\nimport json\n', 'e.py': 'import d\n'}
        r = C.run('import_cycles', {'files': files})['result']
        self.assertTrue(r['has_cycles'])
        self.assertEqual(len(r['cycles']), 1)
        cyc = r['cycles'][0]
        self.assertEqual(cyc['modules'], ['a', 'b', 'c'])
        self.assertEqual(cyc['example_path'], ['a', 'b', 'c', 'a'])
        self.assertNotIn('d', cyc['modules'])

    def test_relative_imports_in_package(self):
        files = {'pkg/__init__.py': '', 'pkg/a.py': 'from . import b\n',
                 'pkg/b.py': 'from .c import y\n', 'pkg/c.py': 'from .a import z\n'}
        r = C.run('import_cycles', {'files': files})['result']
        self.assertEqual(r['cycles'][0]['modules'], ['pkg.a', 'pkg.b', 'pkg.c'])

    def test_acyclic(self):
        files = {'a.py': 'import b\n', 'b.py': 'import c\n', 'c.py': 'import os\n'}
        r = C.run('import_cycles', {'files': files})['result']
        self.assertFalse(r['has_cycles'])
        self.assertEqual(r['cycles'], [])
        self.assertEqual(len(r['edges']), 2)


class TestDuplicateFunctions(unittest.TestCase):  # 11.03
    def test_renamed_copy_is_identical(self):
        files = {'a.py': ('def mean(values):\n    """Average."""\n    total = 0\n    for v in values:\n'
                          '        total += v\n    return total / len(values)\n'),
                 'b.py': ('def average(xs):\n    acc = 0\n    for item in xs:\n'
                          '        acc += item\n    return acc / len(xs)\n')}
        r = C.run('duplicate_functions', {'files': files})['result']
        self.assertEqual(len(r['identical']), 1)
        names = {f['function'] for f in r['identical'][0]['functions']}
        self.assertEqual(names, {'mean', 'average'})
        self.assertTrue(r['identical'][0]['signatures_differ'])
        self.assertEqual(r['near_duplicates'], [])

    def test_behaviour_different_is_near_not_identical(self):
        body = ('def {name}(a, b):\n    total = a {op} b\n    if total > 10:\n'
                '        return total * 2\n    for i in range(3):\n        total += i\n    return total\n')
        files = {'x.py': body.format(name='plus', op='+'), 'y.py': body.format(name='minus', op='-')}
        r = C.run('duplicate_functions', {'files': files})['result']
        self.assertEqual(r['identical'], [])
        self.assertEqual(len(r['near_duplicates']), 1)
        nd = r['near_duplicates'][0]
        self.assertFalse(nd['identical'])
        self.assertGreaterEqual(nd['ratio'], 0.9)
        self.assertLess(nd['ratio'], 1.0)

    def test_unrelated_not_reported(self):
        files = {'u.py': ('def f(a):\n    return [x * 2 for x in a if x]\n\n'
                          'def g(s):\n    with s as h:\n        h.write("x")\n        h.flush()\n    return None\n')}
        r = C.run('duplicate_functions', {'files': files, 'min_nodes': 1})['result']
        self.assertEqual(r['identical'], [])
        self.assertEqual(r['near_duplicates'], [])


class TestResourceHandling(unittest.TestCase):  # 11.04
    def test_unclosed_flagged_with_not(self):
        files = {'r.py': ('def leak(p):\n    f = open(p)\n    data = f.read()\n    return data\n\n'
                          'def ok(p):\n    with open(p) as f:\n        return f.read()\n')}
        r = C.run('resource_handling', {'files': files})['result']
        warn = [f for f in r['findings'] if f['severity'] == 'warning']
        self.assertEqual(len(warn), 1)
        self.assertEqual((warn[0]['scope'], warn[0]['line'], warn[0]['status']), ('leak', 2, 'unclosed'))
        self.assertEqual(r['managed_calls'], 1)

    def test_closed_wrapped_and_inline(self):
        files = {'r.py': ('import sqlite3, json, contextlib\n'
                          'def a(p):\n    f = open(p)\n    try:\n        return f.read()\n    finally:\n'
                          '        f.close()\n'
                          'def b(p):\n    with contextlib.closing(sqlite3.connect(p)) as c:\n        return 1\n'
                          'def c(p):\n    return json.load(open(p))\n'
                          'def d(p):\n    con = sqlite3.connect(p)\n    return con.execute("x")\n')}
        r = C.run('resource_handling', {'files': files})['result']
        warn = {(f['scope'], f['status']) for f in r['findings'] if f['severity'] == 'warning'}
        self.assertEqual(warn, {('c', 'inline_unclosed'), ('d', 'unclosed')})


class TestSecretScan(unittest.TestCase):  # 11.05
    FAKE = 'AKIA' + 'Q7ZR2LMX' + 'W4PT9B3N'
    TOKEN = 'sk-' + 'test' + 'Fake0123456789abcdefGHIJ'

    def test_detected_and_masked(self):
        files = {'conf.py': f'KEY = "{self.FAKE}"\nOPENAI = "{self.TOKEN}"\ndb_password = "s3cr3t-value"\n'}
        out = C.run('secret_scan', {'files': files})
        text = json.dumps(out)
        kinds = {f['kind'] for f in out['result']['findings']}
        self.assertTrue({'aws_access_key_id', 'sk_token', 'password_assignment'} <= kinds)
        for secret in (self.FAKE, self.TOKEN, 's3cr3t-value', self.FAKE[:10], self.TOKEN[:10]):
            self.assertNotIn(secret, text)
        aws = next(f for f in out['result']['findings'] if f['kind'] == 'aws_access_key_id')
        self.assertEqual((aws['preview'], aws['length'], aws['line']), ('AKIA', 20, 1))

    def test_private_key_and_entropy(self):
        blob = 'Zx9Qw3Lm7Tr5Vb1Nc8Kd2Hf6Jg4Ps0Ay' + 'Ue7Io3'
        files = {'k.py': 'PEM = """-----BEGIN RSA PRIVATE KEY-----\n"""\n'
                         f'blob = "{blob}"\nlow = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"\n'}
        out = C.run('secret_scan', {'files': files})
        kinds = [(f['kind'], f['line']) for f in out['result']['findings']]
        self.assertIn(('private_key_header', 1), kinds)
        self.assertIn(('high_entropy_string', 3), kinds)
        self.assertNotIn(4, [f['line'] for f in out['result']['findings']])
        self.assertNotIn(blob, json.dumps(out))

    def test_ignore_list(self):
        files = {'tests/fixtures/keys.py': f'K = "{self.FAKE}"\n', 'app.py': f'K = "{self.FAKE}"\n'}
        r = C.run('secret_scan', {'files': files, 'ignore_files': ['tests/fixtures/*']})['result']
        self.assertEqual(r['ignored_files'], ['tests/fixtures/keys.py'])
        self.assertEqual([f['file'] for f in r['findings']], ['app.py'])
        fp = r['findings'][0]['fingerprint']
        r2 = C.run('secret_scan', {'files': files, 'ignore_files': ['tests/fixtures/*'],
                                   'ignore_hashes': [fp]})['result']
        self.assertEqual(r2['findings'], [])
        self.assertEqual(r2['ignored_by_hash'], 1)


class TestRaceCheck(unittest.TestCase):  # 11.06
    def test_simultaneous_writes_flagged(self):
        log = [{'actor': 'A', 'op': 'write', 'path': 'f.txt', 't_start': 0.1, 't_end': 1.0},
               {'actor': 'B', 'op': 'write', 'path': 'f.txt', 't_start': 0.5, 't_end': 2.0},
               {'actor': 'C', 'op': 'write', 'path': 'other.txt', 't_start': 0.5, 't_end': 2.0}]
        r = C.run('race_check', {'log': log})['result']
        self.assertEqual(r['race_count'], 1)
        self.assertEqual(r['races'][0]['path'], 'f.txt')
        self.assertEqual(r['races'][0]['kind'], 'write/write')
        self.assertEqual(r['races'][0]['overlap'], [0.5, 1.0])

    def test_same_with_lock_not_flagged(self):
        log = [{'actor': 'A', 'op': 'lock', 'path': 'f.txt', 't_start': 0.0, 't_end': 0.1},
               {'actor': 'A', 'op': 'write', 'path': 'f.txt', 't_start': 0.1, 't_end': 1.0},
               {'actor': 'A', 'op': 'unlock', 'path': 'f.txt', 't_start': 1.0, 't_end': 1.0},
               {'actor': 'B', 'op': 'lock', 'path': 'f.txt', 't_start': 0.5, 't_end': 1.0},
               {'actor': 'B', 'op': 'write', 'path': 'f.txt', 't_start': 1.0, 't_end': 2.0},
               {'actor': 'B', 'op': 'unlock', 'path': 'f.txt', 't_start': 2.0, 't_end': 2.0}]
        r = C.run('race_check', {'log': log})['result']
        self.assertEqual(r['races'], [])
        self.assertEqual(r['lock_overlaps'], [])

    def test_reader_without_lock_races_with_locked_writer(self):
        log = [{'actor': 'A', 'op': 'lock', 'path': 'f', 't_start': 0, 't_end': 0},
               {'actor': 'A', 'op': 'write', 'path': 'f', 't_start': 0, 't_end': 2},
               {'actor': 'A', 'op': 'unlock', 'path': 'f', 't_start': 2, 't_end': 2},
               {'actor': 'B', 'op': 'read', 'path': 'f', 't_start': 1, 't_end': 1.5},
               {'actor': 'C', 'op': 'read', 'path': 'f', 't_start': 1, 't_end': 1.5}]
        r = C.run('race_check', {'log': log})['result']
        self.assertEqual(sorted(tuple(x['actors']) for x in r['races']), [('A', 'B'), ('A', 'C')])
        self.assertEqual(r['races'][0]['locked'], [True, False])


TB = '''Traceback (most recent call last):
  File "/srv/app/cli.py", line 20, in <module>
    run(sys.argv)
  File "/srv/app/cli.py", line 15, in run
    cfg = load(path)
  File "/usr/lib/python3.12/json/__init__.py", line 293, in load
    return loads(fp.read())
           ^^^^^^^^^^^^^^^^
  File "/srv/app/config.py", line 7, in parse
    value = data["port"]
            ~~~~^^^^^^^^
KeyError: 'port'
'''


class TestTracebackRepro(unittest.TestCase):  # 11.07
    def test_frames_parsed(self):
        r = C.run('traceback_repro', {'traceback': TB})['result']
        self.assertEqual(r['exception_type'], 'KeyError')
        self.assertEqual(r['message'], "'port'")
        self.assertEqual([(f['file'], f['line'], f['function']) for f in r['frames']], [
            ('/srv/app/cli.py', 20, '<module>'), ('/srv/app/cli.py', 15, 'run'),
            ('/usr/lib/python3.12/json/__init__.py', 293, 'load'), ('/srv/app/config.py', 7, 'parse')])
        self.assertEqual(r['frames'][3]['code'], 'value = data["port"]')
        rep = r['repro']
        self.assertEqual(rep['entry_frame']['line'], 20)
        self.assertEqual(rep['failing_frame']['function'], 'parse')
        self.assertEqual(rep['failing_project_frame']['file'], '/srv/app/config.py')
        self.assertIn('inputs', rep)
        self.assertEqual(rep['seed'], 0)

    def test_before_after_verdicts(self):
        r = C.run('traceback_repro', {'traceback': TB, 'before': TB, 'after': 'ok'})['result']
        self.assertEqual(r['check']['verdict'], 'fixed')
        r = C.run('traceback_repro', {'traceback': TB, 'before': {'status': 'error', 'exception_type': 'KeyError'},
                                      'after': {'status': 'error', 'exception_type': 'KeyError'}})['result']
        self.assertEqual(r['check']['verdict'], 'still_failing')
        r = C.run('traceback_repro', {'traceback': TB, 'before': 'ok', 'after': 'error'})['result']
        self.assertEqual(r['check']['verdict'], 'regressed')
        r = C.run('traceback_repro', {'traceback': TB, 'before': {'status': 'ok', 'output': 1},
                                      'after': {'status': 'ok', 'output': 2}})['result']
        self.assertEqual(r['check']['verdict'], 'ok_output_changed')

    def test_chained(self):
        chained = TB + '\nDuring handling of the above exception, another exception occurred:\n\n' + \
            'Traceback (most recent call last):\n  File "/srv/app/cli.py", line 22, in <module>\n' + \
            '    fail()\nRuntimeError: config broken\n'
        r = C.run('traceback_repro', {'traceback': chained})['result']
        self.assertEqual(len(r['chain']), 2)
        self.assertEqual(r['exception_type'], 'RuntimeError')
        self.assertEqual(r['chain'][0]['exception_type'], 'KeyError')


class TestComplexity(unittest.TestCase):  # 11.08
    SRC = ('def f(x):\n'
           '    if x > 0 and x < 10:\n'          # if +1, and +1
           '        for i in range(x):\n'        # for +1
           '            if i % 2:\n'             # if +1
           '                pass\n'
           '    elif x == 0:\n'                  # elif +1
           '        return 0\n'
           '    try:\n        pass\n'
           '    except ValueError:\n'            # except +1
           '        pass\n'
           '    return [y for y in range(3) if y]\n'   # comprehension +1, its if +1
           '\n'
           'def g(m):\n'
           '    n = 0\n'
           '    for a in m:\n'
           '        for b in a:\n'
           '            while b:\n'
           '                b -= 1\n'
           '                n += 1\n'
           '    return n\n')

    def test_hand_counted(self):
        r = C.run('complexity', {'files': {'c.py': self.SRC}})['result']
        rows = {x['function']: x for x in r['functions']}
        self.assertEqual(rows['f']['cyclomatic'], 9)
        self.assertEqual(rows['f']['max_loop_depth'], 1)
        self.assertEqual(rows['g']['cyclomatic'], 4)
        self.assertEqual(rows['g']['max_loop_depth'], 3)
        self.assertEqual(rows['g']['growth_hint'], 'O(n^3)')

    def test_triple_nested_is_worst_and_flagged(self):
        r = C.run('complexity', {'files': {'c.py': self.SRC}})['result']
        self.assertEqual(r['worst_case']['function'], 'g')
        self.assertEqual([x['function'] for x in r['flagged']], ['g'])
        self.assertIn('nested_loops>=3', r['flagged'][0]['flags'])


class TestBoundaryCases(unittest.TestCase):  # 11.09
    SPEC = {'qty': {'type': 'int', 'min': 1, 'max': 10}, 'price': {'type': 'float', 'min': 0.0, 'max': 99.5}}

    def test_cases_generated(self):
        r = C.run('boundary_cases', {'spec': self.SPEC})['result']
        by_id = {c['id']: c for c in r['cases']}
        self.assertEqual(by_id['qty:min']['value'], 1)
        self.assertEqual(by_id['qty:below_min']['value'], 0)
        self.assertEqual(by_id['qty:above_max']['value'], 11)
        self.assertEqual(by_id['qty:wrong_type']['expected'], 'invalid')
        self.assertEqual(by_id['price:nan']['value_repr'], 'nan')
        self.assertEqual(by_id['qty:missing']['expected'], 'invalid')
        self.assertFalse(r['evaluated'])

    def test_bypass_reported(self):
        results = {'qty:min': True, 'qty:max': True, 'qty:below_min': False, 'qty:above_max': True,
                   'price:nan': True, 'price:max': False}
        r = C.run('boundary_cases', {'spec': self.SPEC, 'results': results})['result']
        self.assertEqual(sorted(b['id'] for b in r['bypasses']), ['price:nan', 'qty:above_max'])
        self.assertEqual([x['id'] for x in r['false_rejections']], ['price:max'])
        self.assertIn('qty:wrong_type', r['untested'])

    def test_str_and_allowed(self):
        spec = {'mode': {'type': 'str', 'allowed': ['a', 'b']}, 'name': {'type': 'str', 'min': 2, 'max': 5}}
        r = C.run('boundary_cases', {'spec': spec, 'results': {'mode:not_allowed': True}})['result']
        self.assertEqual([b['id'] for b in r['bypasses']], ['mode:not_allowed'])
        ids = {c['id']: c for c in r['cases']}
        self.assertEqual(ids['name:above_max_length']['value'], 'aaaaaa')


DIFF_DELETE = '''diff --git a/lib/core.py b/lib/core.py
index 111..222 100644
--- a/lib/core.py
+++ b/lib/core.py
@@ -1,8 +1,5 @@
 import re
-def parse_header(text):
-    return re.split(":", text, 1)
-
 def keep():
     return 1

 x = 2
diff --git a/tests/test_core.py b/tests/test_core.py
--- a/tests/test_core.py
+++ b/tests/test_core.py
@@ -1,5 +1,2 @@
 import core
-def test_parse_header():
-    assert core.parse_header("a:b")
-
 X = 1
'''

DIFF_MOVE = '''diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1,3 +1,1 @@
-def helper(x):
-    return x * 2
 VALUE = 1
diff --git a/b.py b/b.py
new file mode 100644
--- /dev/null
+++ b/b.py
@@ -0,0 +1,2 @@
+def helper(x):
+    return x * 2
'''


class TestDiffReview(unittest.TestCase):  # 11.10
    def test_deleted_function_flagged(self):
        r = C.run('diff_review', {'diff': DIFF_DELETE})['result']
        self.assertEqual(r['files_changed'], 2)
        self.assertEqual((r['lines_added'], r['lines_removed']), (0, 6))
        kinds = {(f['kind'], f.get('name')) for f in r['flags']}
        self.assertIn(('removed_definition', 'parse_header'), kinds)
        self.assertIn(('removed_test', 'test_parse_header'), kinds)
        self.assertEqual(r['verdict'], 'needs_attention')
        old = next(f for f in r['flags'] if f.get('name') == 'parse_header')
        self.assertEqual(old['old_line'], 2)

    def test_move_not_flagged(self):
        r = C.run('diff_review', {'diff': DIFF_MOVE})['result']
        self.assertEqual(r['flags'], [])
        self.assertEqual([m['name'] for m in r['moved_or_modified_definitions']], ['helper'])
        status = {f['path']: f['status'] for f in r['files']}
        self.assertEqual(status, {'a.py': 'modified', 'b.py': 'added'})

    def test_deleted_file(self):
        diff = ('diff --git a/old.py b/old.py\ndeleted file mode 100644\n--- a/old.py\n+++ /dev/null\n'
                '@@ -1,2 +0,0 @@\n-class Gone:\n-    pass\n')
        r = C.run('diff_review', {'diff': diff})['result']
        kinds = {(f['kind'], f.get('name')) for f in r['flags']}
        self.assertEqual(kinds, {('deleted_file', None), ('removed_definition', 'Gone')})
        self.assertEqual(r['files'][0]['status'], 'deleted')

    def test_removed_line_starting_with_dashes_is_content(self):
        diff = ('--- a/n.py\n+++ b/n.py\n@@ -1,2 +1,1 @@\n--- not a header\n x = 1\n')
        r = C.run('diff_review', {'diff': diff})['result']
        self.assertEqual(r['files_changed'], 1)
        self.assertEqual(r['lines_removed'], 1)


if __name__ == '__main__':
    unittest.main()
