import ast
import json
import time
import unittest
from pathlib import Path

import thinking_v21 as tv

ROOT = Path(__file__).resolve().parent
FORBIDDEN_IMPORTS = {'subprocess', 'socket', 'urllib', 'http', 'shutil', 'os', 'sqlite3', 'ctypes'}
HASH = 'a' * 64


class ContractTests(unittest.TestCase):
    def test_no_io_imports_and_shape(self):
        tree = ast.parse((ROOT / 'thinking_v21.py').read_text(encoding='utf-8'))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name.split('.')[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split('.')[0])
            elif isinstance(node, ast.Call):
                self.assertNotIn(getattr(node.func, 'id', None), ('open', 'exec', 'eval', 'print'))
        self.assertFalse(imported & FORBIDDEN_IMPORTS)
        self.assertEqual(len(tv.TOPICS), 10)
        self.assertEqual(list(tv.TOPICS), [f'04.{i:02d}' for i in range(1, 11)])
        self.assertTrue(set(tv.TOPICS.values()) <= set(tv.OPS))
        self.assertEqual(set(tv.TOPIC_NAMES_AR), set(tv.TOPICS))

    def test_run_rejects_bad_op_and_extra(self):
        with self.assertRaises(ValueError):
            tv.run('not_an_op', {})
        for op in tv.OPS:
            with self.subTest(op=op), self.assertRaises(ValueError):
                tv.run(op, {'shell': 'rm -rf /'})
        with self.assertRaises(ValueError):
            tv.run('causal', [])

    def test_defaults_run_fast_json_and_deterministic(self):
        for key, op in tv.TOPICS.items():
            with self.subTest(topic=key):
                start = time.perf_counter()
                out = tv.run(op, {})
                self.assertLess(time.perf_counter() - start, 2.0)
                self.assertEqual(set(out), {'op', 'result', 'assumptions', 'limits'})
                self.assertEqual(out['op'], op)
                self.assertTrue(out['assumptions'] and out['limits'])
                self.assertEqual(json.dumps(out, sort_keys=True), json.dumps(tv.run(op, {}), sort_keys=True))

    def test_missing_required_inputs_raise_valueerror(self):
        cases = [('causal', {'edges': []}), ('decision_matrix', {'options': ['a', 'b']}),
                 ('premortem', {'controls': []}), ('budget_filter', {'time_budget_s': 5}),
                 ('plan_gaps', {'gap_log': []}), ('lesson_match', {'failure': 'x'}),
                 ('first_principles', {'hypotheses': 'nope'}), ('alternatives', {'options': 5})]
        for op, params in cases:
            with self.subTest(op=op), self.assertRaises(ValueError):
                tv.run(op, params)

    def test_caps(self):
        many = [{'statement': f's{i}', 'prediction': 'p', 'counterexample': 'c'} for i in range(201)]
        with self.assertRaises(ValueError):
            tv.run('first_principles', {'hypotheses': many})
        with self.assertRaises(ValueError):
            tv.run('lesson_match', {'lessons': [{'cause': 'a', 'fix': 'b'}], 'failure': 'x' * 5000})


class FirstPrinciplesTests(unittest.TestCase):
    def test_missing_counterexample_rejected_with_index(self):
        hyps = [{'statement': 'A', 'assumptions': ['x'], 'prediction': 'p', 'counterexample': 'c'},
                {'statement': 'B', 'assumptions': [], 'prediction': 'p'},
                {'statement': 'C', 'assumptions': [], 'counterexample': 'c'}]
        r = tv.run('first_principles', {'hypotheses': hyps})['result']
        self.assertEqual(r['status'], 'rejected')
        self.assertEqual(r['rejected_indices'], [1, 2])
        self.assertIn('counterexample', r['rejected'][0]['reasons'][0])
        self.assertIn('prediction', r['rejected'][1]['reasons'][0])

    def test_valid_set_accepted_and_ordered(self):
        hyps = [{'statement': 'A', 'assumptions': ['x', 'y'], 'prediction': 'p', 'counterexample': 'c'},
                {'statement': 'B', 'assumptions': ['X'], 'prediction': 'p', 'counterexample': 'c'},
                {'statement': 'C', 'assumptions': ['z', 'w', 'v'], 'prediction': 'p', 'counterexample': 'c'}]
        r = tv.run('first_principles', {'hypotheses': hyps})['result']
        self.assertEqual(r['status'], 'accepted')
        self.assertEqual([h['statement'] for h in r['accepted']], ['B', 'A', 'C'])
        self.assertEqual([h['rank'] for h in r['accepted']], [1, 2, 3])
        self.assertEqual(r['shared_assumptions'][0]['hypotheses'], [0, 1])


class AlternativesTests(unittest.TestCase):
    def opts(self):
        return [{'name': 'A', 'benefit': 0.9, 'risk': 0.5, 'cost': 0.5, 'approach': 'blender path tracing render'},
                {'name': 'B', 'benefit': 0.6, 'risk': 0.2, 'cost': 0.2, 'approach': 'ffmpeg overlay of stock footage'},
                {'name': 'C', 'benefit': 0.5, 'risk': 0.3, 'cost': 0.3, 'approach': 'hand drawn krita frames'},
                {'name': 'D', 'benefit': 0.9, 'risk': 0.6, 'cost': 0.5, 'approach': 'unreal engine realtime scene'}]

    def test_pareto_front_hand_example(self):
        r = tv.run('alternatives', {'options': self.opts()})['result']
        # C is dominated by B; D is dominated by A.
        self.assertEqual(r['pareto_front'], ['A', 'B'])
        table = {row['name']: row for row in r['table']}
        self.assertEqual(table['C']['dominated_by'], ['B'])
        self.assertEqual(table['D']['dominated_by'], ['A'])

    def test_duplicates_and_too_few_rejected(self):
        o = self.opts()
        o[3]['approach'] = 'Blender path-tracing render'
        with self.assertRaisesRegex(ValueError, 'near-duplicate'):
            tv.run('alternatives', {'options': o})
        with self.assertRaisesRegex(ValueError, 'at least 3'):
            tv.run('alternatives', {'options': self.opts()[:2]})


class CausalTests(unittest.TestCase):
    P = {'nodes': ['A', 'B', 'C', 'D'], 'edges': [['A', 'B', 2.0], ['B', 'C', 3.0]],
         'base': {'A': 1.0, 'B': 0.5, 'C': 0.0, 'D': 4.0}}

    def test_hand_calc_and_do_changes_only_descendants(self):
        r = tv.run('causal', {**self.P, 'do': {'B': 10.0}})['result']
        self.assertEqual(r['values'], {'A': 1.0, 'B': 2.5, 'C': 7.5, 'D': 4.0})
        iv = r['intervention']
        self.assertEqual(iv['values'], {'A': 1.0, 'B': 10.0, 'C': 30.0, 'D': 4.0})
        self.assertEqual(iv['descendants'], ['C'])
        self.assertEqual(sorted(iv['changed']), ['B', 'C'])
        self.assertTrue(iv['only_descendants_changed'])

    def test_cycle_rejected(self):
        p = {**self.P, 'edges': self.P['edges'] + [['C', 'A', 1.0]]}
        with self.assertRaisesRegex(ValueError, 'cycle'):
            tv.run('causal', p)
        with self.assertRaises(ValueError):
            tv.run('causal', {**self.P, 'do': {'A': 1.0, 'B': 2.0}})


class DecisionMatrixTests(unittest.TestCase):
    P = {'options': ['A', 'B'], 'criteria': ['q', 's'], 'weights': [3, 2], 'scores': [[8, 4], [5, 7]]}

    def test_winner_and_flip_points(self):
        r = tv.run('decision_matrix', self.P)['result']
        self.assertAlmostEqual(r['totals']['A'], 6.4)
        self.assertAlmostEqual(r['totals']['B'], 5.8)
        self.assertEqual(r['winner'], 'A')
        q, s = r['sensitivity']
        # Hand calc: tie when (0.6 - 3d) = 0 for s (d = +0.2) and (0.6 + 3d) = 0 for q (d = -0.2).
        self.assertLess(abs(s['increase']['weight_delta'] - 0.2), 1e-6)
        self.assertLess(abs(s['increase']['flip_weight'] - 0.5), 1e-6)
        self.assertIsNone(s['decrease'])
        self.assertLess(abs(q['decrease']['weight_delta'] + 0.2), 1e-6)
        self.assertLess(abs(q['decrease']['flip_weight'] - 0.5), 1e-6)
        self.assertIsNone(q['increase'])

    def test_tie_reported(self):
        r = tv.run('decision_matrix', {**self.P, 'weights': [1, 1]})['result']
        self.assertTrue(r['tie'])
        self.assertIsNone(r['winner'])
        self.assertEqual(r['tied_options'], ['A', 'B'])


class PremortemTests(unittest.TestCase):
    CAUSES = [{'id': 'silent', 'description': 'no audio', 'likelihood': 3, 'impact': 3},
              {'id': 'minor', 'description': 'typo', 'likelihood': 1, 'impact': 1}]

    def test_flag_then_clear(self):
        r = tv.run('premortem', {'causes': self.CAUSES})['result']
        self.assertEqual(r['flagged'], ['silent'])
        self.assertEqual(r['status'], 'blocked')
        self.assertEqual(r['ranked'][0]['id'], 'silent')
        r = tv.run('premortem', {'causes': self.CAUSES,
                                 'controls': [{'cause_id': 'silent', 'action': 'probe audio'}]})['result']
        self.assertEqual(r['flagged'], [])
        self.assertEqual(r['status'], 'clear')
        with self.assertRaises(ValueError):
            tv.run('premortem', {'causes': self.CAUSES, 'controls': [{'cause_id': 'x', 'action': 'y'}]})


class BudgetTests(unittest.TestCase):
    def test_best_quality_over_budget_rejected(self):
        opts = [{'name': 'best', 'time_s': 100, 'memory_mb': 100, 'quality': 0.99},
                {'name': 'ok', 'time_s': 10, 'memory_mb': 50, 'quality': 0.7},
                {'name': 'fat', 'time_s': 10, 'memory_mb': 900, 'quality': 0.9}]
        r = tv.run('budget_filter', {'options': opts, 'time_budget_s': 60, 'memory_budget_mb': 512})['result']
        self.assertEqual(r['best'], 'ok')
        rej = {x['name']: [e['resource'] for e in x['exceeded']] for x in r['rejected']}
        self.assertEqual(rej, {'best': ['time_s'], 'fat': ['memory_mb']})


class PlanGapsTests(unittest.TestCase):
    STEPS = [{'id': 's1', 'inputs': ['brief'], 'outputs': ['clips', 'junk'], 'kind': 'action'},
             {'id': 's2', 'inputs': ['clips', 'music'], 'outputs': ['video'], 'kind': 'write'}]

    def test_each_gap_type_and_closing_record(self):
        p = {'steps': self.STEPS, 'initial_inputs': ['brief'], 'final_outputs': ['video']}
        r = tv.run('plan_gaps', p)['result']
        ids = {g['gap_id'] for g in r['gaps']}
        self.assertEqual(ids, {'unproduced_input:s2:music', 'unused_output:s1:junk', 'unverified_write:s2'})
        self.assertEqual(r['counts'], {'unproduced_input': 1, 'unused_output': 1, 'unverified_write': 1})
        self.assertEqual(r['status'], 'gaps_open')
        log = [{'gap_id': 'unproduced_input:s2:music', 'status': 'closed'},
               {'gap_id': 'unused_output:s1:junk', 'status': 'closed', 'closed_by': 'dropped junk output'},
               {'gap_id': 'nope', 'status': 'closed', 'closed_by': 'x'}]
        r = tv.run('plan_gaps', {**p, 'gap_log': log})['result']
        st = {g['gap_id']: g['status'] for g in r['gaps']}
        self.assertEqual(st['unproduced_input:s2:music'], 'open')
        self.assertEqual(st['unused_output:s1:junk'], 'closed')
        self.assertEqual(r['invalid_log_entries'][0]['gap_id'], 'unproduced_input:s2:music')
        self.assertEqual(r['unknown_log_entries'][0]['gap_id'], 'nope')
        log = [{'gap_id': g, 'status': 'closed', 'closed_by': 'fixed'} for g in ids]
        self.assertEqual(tv.run('plan_gaps', {**p, 'gap_log': log})['result']['status'], 'ok')

    def test_verify_step_clears_write_gap(self):
        steps = self.STEPS + [{'id': 's3', 'inputs': ['video'], 'outputs': [], 'kind': 'verify'}]
        r = tv.run('plan_gaps', {'steps': steps, 'initial_inputs': ['brief', 'music'],
                                 'final_outputs': ['junk']})['result']
        self.assertEqual(r['gaps'], [])
        self.assertEqual(r['status'], 'ok')


class LessonMatchTests(unittest.TestCase):
    LESSONS = [{'id': 'L1', 'cause': 'الصوت ساكت على الآيفون بسبب ترميز MP3',
                'fix': 'AAC', 'bad_action': 'encode audio as mp3'},
               {'id': 'L2', 'cause': ['glow', 'overlay', 'blacks'], 'fix': 'no overlays',
                'bad_action': 'add bloom overlay'}]

    def test_arabic_normalisation_matches(self):
        self.assertEqual(tv.normalize_text('أَيْفُونـــ إِلى مَدْرَسَة'), 'ايفون الي مدرسه')
        r = tv.run('lesson_match', {'lessons': self.LESSONS,
                                    'failure': 'الصَّوْت ساكِت على الأيفون'})['result']
        self.assertEqual(r['matched']['id'], 'L1')
        self.assertIn('الايفون', r['matched']['shared_tokens'])
        self.assertFalse(r['repeat_risk'])

    def test_repeat_risk_flagged(self):
        r = tv.run('lesson_match', {'lessons': self.LESSONS, 'failure': 'overlay lifted the blacks',
                                    'plan_actions': ['trim clips', 'Encode audio as MP3 for speed']})['result']
        self.assertEqual(r['matched']['id'], 'L2')
        self.assertTrue(r['repeat_risk'])
        self.assertEqual([(x['plan_index'], x['lesson_id']) for x in r['repeats']], [(1, 'L1')])


class PocGateTests(unittest.TestCase):
    REC = {'artifact_path': 'out/a.mp4', 'sha256': HASH, 'metric_name': 'fps',
           'metric_value': 30.0, 'target': 24.0, 'direction': 'max'}

    def test_valid_accepted(self):
        r = tv.run('poc_gate', {'record': self.REC})['result']
        self.assertEqual(r['status'], 'accepted')
        self.assertEqual(r['reasons'], [])

    def test_missing_hash_or_metric_rejected(self):
        rec = {k: v for k, v in self.REC.items() if k != 'sha256'}
        r = tv.run('poc_gate', {'record': rec})['result']
        self.assertEqual(r['status'], 'rejected')
        self.assertIn('missing sha256 hash', r['reasons'])
        rec = {k: v for k, v in self.REC.items() if k != 'metric_value'}
        r = tv.run('poc_gate', {'record': rec})['result']
        self.assertEqual(r['status'], 'rejected')
        self.assertIn('missing measured metric_value', r['reasons'])
        r = tv.run('poc_gate', {'record': {**self.REC, 'sha256': 'abc'}})['result']
        self.assertEqual(r['status'], 'rejected')
        r = tv.run('poc_gate', {'record': {**self.REC, 'metric_value': 20.0}})['result']
        self.assertEqual(r['status'], 'rejected')
        self.assertFalse(r['metric']['meets_target'])


class AestheticTests(unittest.TestCase):
    D = {'decision': 'warm grade', 'example_id': 'frame_12',
         'criteria': [{'name': 'black_level', 'measured': 2.0, 'threshold': 4.0, 'direction': '<='}]}

    def test_without_example_rejected(self):
        d = {k: v for k, v in self.D.items() if k != 'example_id'}
        r = tv.run('aesthetic_decision', {'decision': d})['result']
        self.assertEqual(r['status'], 'rejected')
        self.assertIn('example_id', r['reasons'][0])

    def test_pending_then_approved(self):
        r = tv.run('aesthetic_decision', {'decision': self.D})['result']
        self.assertEqual(r['status'], 'pending_review')
        d = {**self.D, 'human_review': {'reviewer': 'owner', 'approved': True}}
        self.assertEqual(tv.run('aesthetic_decision', {'decision': d})['result']['status'], 'approved')
        d = {**self.D, 'criteria': [{'name': 'black_level', 'direction': '<='}]}
        self.assertEqual(tv.run('aesthetic_decision', {'decision': d})['result']['status'], 'rejected')
        d = {**self.D, 'criteria': [{'name': 'black_level', 'measured': 6.0, 'threshold': 4.0, 'direction': '<='}],
             'human_review': {'reviewer': 'owner', 'approved': True}}
        self.assertEqual(tv.run('aesthetic_decision', {'decision': d})['result']['status'], 'failed_criteria')


if __name__ == '__main__':
    unittest.main()
