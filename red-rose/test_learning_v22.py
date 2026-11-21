import ast
import json
import pathlib
import unittest

import learning_v22 as L

SRC = pathlib.Path(__file__).with_name('learning_v22.py')


def _walk_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _walk_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_keys(v)


class Interface(unittest.TestCase):
    def test_topics_and_ops(self):
        self.assertEqual(sorted(L.TOPICS), [f'26.{i:02d}' for i in range(2, 11)])
        self.assertEqual(set(L.TOPICS.values()), set(L.OPS))
        self.assertEqual(set(L.TOPIC_NAMES_AR), set(L.TOPICS))

    def test_every_op_runs_with_empty_params(self):
        for op in L.OPS:
            with self.subTest(op=op):
                out = L.run(op, {})
                self.assertEqual(set(out), {'op', 'result', 'assumptions', 'limits'})
                self.assertEqual(out['op'], op)
                self.assertTrue(out['assumptions'] and out['limits'])
                json.dumps(out, allow_nan=False)
                self.assertEqual(out, L.run(op, {}))  # deterministic

    def test_bad_calls_raise_value_error(self):
        for op in L.OPS:
            with self.subTest(op=op):
                with self.assertRaises(ValueError):
                    L.run(op, {'bogus': 1})
        with self.assertRaises(ValueError):
            L.run('nope', {})
        with self.assertRaises(ValueError):
            L.run('rank_lessons', [])
        partial = {'similar_errors': {'query': 'x'}, 'rank_lessons': {'now': '2026-01-01'},
                   'capability_gaps': {'plan': ['a']}, 'lesson_benefit': {'before': {'tasks': 1, 'repeated_errors': 0}},
                   'forget_request': {'request': {'terms': ['ab']}},
                   'regression_from_defect': {'after': 1}, 'rule_versions': {'action': 'commit'},
                   'rule_proposal': {'action': 'approve'}, 'local_only_guard': {'operations': 'x'}}
        for op, params in partial.items():
            with self.subTest(op=op):
                with self.assertRaises(ValueError):
                    L.run(op, params)

    def test_source_rules(self):
        tree = ast.parse(SRC.read_text(encoding='utf-8'))
        banned = {'os', 'subprocess', 'socket', 'urllib', 'http', 'shutil', 'sqlite3', 'ctypes'}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    self.assertNotIn(a.name.split('.')[0], banned)
            elif isinstance(node, ast.ImportFrom):
                self.assertNotIn((node.module or '').split('.')[0], banned)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {'open', 'exec', 'eval', 'print'})


class SimilarErrors(unittest.TestCase):
    def test_recurring_error_finds_original(self):
        records = [
            {'signature': 'FileNotFoundError', 'message': r"No such file or directory: 'C:\proj\a\clip_17.mp4'",
             'fix': 'check path', 'source_audit_id': 5},
            {'signature': 'UnicodeEncodeError', 'message': "'charmap' codec can't encode character",
             'fix': 'use -X utf8', 'source_audit_id': 6},
            {'signature': 'ValueError', 'message': 'invalid literal for int() with base 10',
             'fix': 'validate', 'source_audit_id': 7},
        ]
        out = L.run('similar_errors', {'records': records, 'query':
                    r"FileNotFoundError: No such file or directory: 'D:\other\b\clip_903.mp4'"})
        m = out['result']['matches']
        self.assertEqual(m[0]['source_audit_id'], 5)
        self.assertGreater(m[0]['score'], m[1]['score'] if len(m) > 1 else 0)

    def test_arabic_normalisation(self):
        self.assertEqual(L.tokens('الملفّ إلى مدرسةـــ'), L.tokens('الملف الي مدرسه'))
        records = [{'signature': 'خطأ ترميز', 'message': 'فشل حفظ الملفّ', 'fix': 'utf-8', 'source_audit_id': 1},
                   {'signature': 'timeout', 'message': 'render took too long', 'fix': 'xl', 'source_audit_id': 2}]
        out = L.run('similar_errors', {'records': records, 'query': 'خطا ترميز الملف'})
        self.assertEqual(out['result']['matches'][0]['source_audit_id'], 1)

    def test_validation(self):
        with self.assertRaises(ValueError):
            L.run('similar_errors', {'records': [{'signature': 'x', 'message': '', 'fix': '',
                                                  'source_audit_id': 0}], 'query': 'x y'})


class RankLessons(unittest.TestCase):
    def test_recent_confirmed_wins_and_expired_demoted(self):
        lessons = [
            {'id': 'old', 'topic': 'codec', 'text': 'use mp3', 'created': '2026-01-01', 'confidence': 0.9,
             'confirmations': 5, 'review_by': '2027-01-01', 'source_audit_id': 1},
            {'id': 'new', 'topic': 'Codec', 'text': 'use aac', 'created': '2026-11-10', 'confidence': 0.8,
             'confirmations': 2, 'review_by': '2027-06-01', 'source_audit_id': 2},
            {'id': 'exp', 'topic': 'fonts', 'text': 'embed', 'created': '2026-11-15', 'confidence': 0.9,
             'confirmations': 2, 'review_by': '2026-11-01', 'source_audit_id': 3},
            {'id': 'ok', 'topic': 'fps', 'text': '30 fps', 'created': '2026-11-15', 'confidence': 0.9,
             'confirmations': 2, 'review_by': '2027-11-01', 'source_audit_id': 4},
        ]
        r = L.run('rank_lessons', {'lessons': lessons, 'now': '2026-11-21'})['result']
        order = [x['id'] for x in r['ranked']]
        self.assertLess(order.index('new'), order.index('old'))
        by = {x['id']: x for x in r['ranked']}
        self.assertEqual(by['old']['status'], 'superseded')
        self.assertTrue(by['exp']['expired_review'])
        self.assertLess(by['exp']['score'], by['ok']['score'])
        self.assertLess(order.index('ok'), order.index('exp'))

    def test_requires_now(self):
        with self.assertRaises(ValueError):
            L.run('rank_lessons', {'lessons': L._EXAMPLE_LESSONS})


class RuleProposal(unittest.TestCase):
    def test_pending_until_human_approves(self):
        out = L.run('rule_proposal', {})
        props = out['result']['proposals']
        self.assertEqual(len(props), 1)
        rule = props[0]
        self.assertEqual(rule['status'], 'pending_human_review')
        self.assertEqual(rule['evidence_audit_ids'], [9, 14, 21])
        keys = set(_walk_keys(out))
        self.assertFalse(keys & {'code', 'diff', 'patch', 'edits', 'file_changes'})
        approved = L.run('rule_proposal', {'action': 'approve', 'rule': rule,
                                           'reviewer': 'owner', 'decision': 'approved'})['result']['rule']
        self.assertEqual(approved['status'], 'approved')
        self.assertEqual(approved['review_log'][0]['reviewer'], 'owner')
        self.assertEqual(rule['status'], 'pending_human_review')  # input untouched
        with self.assertRaises(ValueError):
            L.approve(approved, 'owner', 'rejected')
        bad = dict(rule, code='x = 1')
        with self.assertRaises(ValueError):
            L.approve(bad, 'owner', 'approved')
        with self.assertRaises(ValueError):
            L.approve(rule, '  ', 'approved')

    def test_single_evidence_is_not_enough(self):
        lessons = [{'topic': 't', 'text': 'a', 'source_audit_id': 1},
                   {'topic': 't', 'text': 'a', 'source_audit_id': 1}]
        r = L.run('rule_proposal', {'lessons': lessons})['result']
        self.assertEqual(r['proposals'], [])


class CapabilityGaps(unittest.TestCase):
    def test_missing_reported(self):
        registry = {'memory.recall': ('Recall stored lessons', 'read', 'database'),
                    'video.burn': {'description': 'burn subtitles', 'implemented': False}}
        r = L.run('capability_gaps', {'plan': ['memory.recall', 'video.burn', 'stored lessons',
                                               'voice.clone'], 'registry': registry})['result']
        self.assertEqual([x['item'] for x in r['implemented']], ['memory.recall'])
        self.assertEqual({x['item'] for x in r['description_only']}, {'video.burn', 'stored lessons'})
        self.assertEqual([x['item'] for x in r['missing']], ['voice.clone'])


class Regression(unittest.TestCase):
    D = {'id': 'D1', 'input': {'x': 1}, 'expected': 'aac', 'observed_before': 'mp3'}

    def test_valid(self):
        r = L.run('regression_from_defect', {'defect': self.D, 'after': 'aac'})['result']
        self.assertTrue(r['valid'])
        self.assertEqual(r['verdict'], 'valid_regression')

    def test_passing_before_is_rejected(self):
        r = L.run('regression_from_defect', {'defect': self.D, 'before': 'aac', 'after': 'aac'})['result']
        self.assertFalse(r['valid'])
        self.assertEqual(r['verdict'], 'invalid_does_not_reproduce')

    def test_failing_after_and_pending(self):
        r = L.run('regression_from_defect', {'defect': self.D, 'after': 'mp3'})['result']
        self.assertEqual(r['verdict'], 'invalid_fix_not_verified')
        r = L.run('regression_from_defect', {'defect': self.D})['result']
        self.assertEqual(r['verdict'], 'pending_after')


class RuleVersions(unittest.TestCase):
    def test_rollback_restores_exact_rules_and_hash(self):
        a = L.run('rule_versions', {'action': 'commit', 'rules': [{'r': 1}], 'note': 'v1'})['result']
        a = L.run('rule_versions', {'action': 'activate', 'state': a['state'], 'version': 1})['result']
        h1, rules1 = a['active_hash'], a['active_rules']
        b = L.run('rule_versions', {'action': 'commit', 'state': a['state'], 'rules': [{'r': 2}]})['result']
        b = L.run('rule_versions', {'action': 'activate', 'state': b['state'], 'version': 2})['result']
        self.assertNotEqual(b['active_hash'], h1)
        c = L.run('rule_versions', {'action': 'rollback', 'state': b['state']})['result']
        self.assertEqual(c['active_version'], 1)
        self.assertEqual(c['active_hash'], h1)
        self.assertEqual(c['active_rules'], rules1)
        self.assertEqual(c['version_count'], 2)
        self.assertEqual([e['event'] for e in c['state']['changelog']],
                         ['commit', 'activate', 'commit', 'activate', 'rollback'])

    def test_tamper_and_empty_rollback(self):
        a = L.run('rule_versions', {'action': 'commit', 'rules': [1]})['result']['state']
        a['versions'][0]['rules'] = [2]
        with self.assertRaises(ValueError):
            L.run('rule_versions', {'state': a})
        with self.assertRaises(ValueError):
            L.run('rule_versions', {'action': 'rollback'})
        with self.assertRaises(ValueError):
            L.run('rule_versions', {'action': 'activate', 'version': 1})


class LessonBenefit(unittest.TestCase):
    def test_clear_reduction(self):
        r = L.run('lesson_benefit', {'before': {'tasks': 200, 'repeated_errors': 60},
                                     'after': {'tasks': 200, 'repeated_errors': 20}})['result']
        self.assertEqual(r['verdict'], 'reduction')
        self.assertAlmostEqual(r['absolute_reduction'], 0.2)
        self.assertAlmostEqual(r['relative_reduction'], 2 / 3, places=5)
        self.assertGreater(r['z'], 1.96)

    def test_tiny_sample(self):
        r = L.run('lesson_benefit', {'before': {'tasks': 5, 'repeated_errors': 3},
                                     'after': {'tasks': 5, 'repeated_errors': 0}})['result']
        self.assertEqual(r['verdict'], 'insufficient_data')
        with self.assertRaises(ValueError):
            L.run('lesson_benefit', {'before': {'tasks': 5, 'repeated_errors': 6},
                                     'after': {'tasks': 5, 'repeated_errors': 0}})


class LocalOnlyGuard(unittest.TestCase):
    def test_block_and_allow(self):
        ops = [{'type': 'upload', 'destination': 'https://api.example.invalid/x', 'payload_kind': 'memory'},
               {'type': 'http', 'destination': 'collector', 'payload_kind': 'user_text'},
               {'type': 'write', 'destination': 'local:memory.sqlite3', 'payload_kind': 'memory'},
               {'type': 'write', 'destination': 'fine_tune_queue', 'payload_kind': 'memory'}]
        r = L.run('local_only_guard', {'operations': ops})['result']
        self.assertEqual([d['decision'] for d in r['decisions']], ['block', 'block', 'allow', 'block'])
        self.assertEqual(r['verdict'], 'blocked')
        r = L.run('local_only_guard', {'operations': ops[2:3]})['result']
        self.assertEqual(r['verdict'], 'allowed')


class ForgetRequest(unittest.TestCase):
    def test_forget(self):
        stores = {'memory': [{'id': 1, 'text': 'هاتف أحمد السري'}, {'id': 2, 'text': 'likes AAC'}],
                  'notes': [{'id': 9, 'text': 'secret token for Ahmed'}, {'id': 10, 'text': 'fps 30'}],
                  'audit': [{'id': 3, 'text': 'احمد'}]}
        out = L.run('forget_request', {'stores': stores, 'request': {'terms': ['احمد', 'AHMED']},
                                       'authorised_tables': ['memory', 'notes']})
        r = out['result']
        self.assertEqual(r['stores_after']['memory'], [{'id': 2, 'text': 'likes AAC'}])
        self.assertEqual(r['stores_after']['notes'], [{'id': 10, 'text': 'fps 30'}])
        self.assertEqual(r['stores_after']['audit'], stores['audit'])
        self.assertEqual(len(stores['memory']), 2)  # original untouched
        self.assertTrue(r['verification']['passed'])
        rc = r['receipt']
        self.assertEqual(rc['total_deleted'], 2)
        self.assertEqual(rc['matches_outside_scope'], 1)
        text = json.dumps(rc, ensure_ascii=False)
        for secret in ('هاتف', 'السري', 'secret', 'token', 'Ahmed', 'احمد'):
            self.assertNotIn(secret, text)

    def test_ids_and_refused_scope(self):
        stores = {'a': [{'id': 'x1', 'v': 1}, {'id': 'x2', 'v': 2}], 'b': [{'id': 'x1'}]}
        r = L.run('forget_request', {'stores': stores, 'request': {'ids': ['x1'], 'tables': ['a', 'b']},
                                     'authorised_tables': ['a']})['result']
        self.assertEqual(r['stores_after']['a'], [{'id': 'x2', 'v': 2}])
        self.assertEqual(r['stores_after']['b'], [{'id': 'x1'}])
        self.assertEqual(r['plan']['refused_tables'], ['b'])
        with self.assertRaises(ValueError):
            L.run('forget_request', {'stores': stores, 'request': {}, 'authorised_tables': ['a']})


if __name__ == '__main__':
    unittest.main()
