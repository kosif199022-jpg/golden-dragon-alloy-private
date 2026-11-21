"""Tests for decision_v21 (Red Rose V21 decision/reasoning helpers)."""
import ast
import copy
import inspect
import json
import unittest

import decision_v21 as d


def R(op, **params):
    return d.run(op, params)['result']


class InterfaceTests(unittest.TestCase):
    def test_topics_ops_and_names(self):
        self.assertEqual(list(d.TOPICS), [f'09.{i:02d}' for i in range(1, 11)])
        self.assertEqual(set(d.TOPICS.values()), set(d.OPS))
        self.assertEqual(set(d.TOPIC_NAMES_AR), set(d.TOPICS))

    def test_every_op_runs_with_empty_params_and_is_json(self):
        for op in d.OPS:
            out = d.run(op, {})
            self.assertEqual(set(out), {'op', 'result', 'assumptions', 'limits'})
            self.assertEqual(out['op'], op)
            self.assertTrue(out['assumptions'] and out['limits'])
            json.dumps(out, allow_nan=False)
            self.assertEqual(out, d.run(op, {}), f'{op} not deterministic')

    def test_run_validation(self):
        with self.assertRaises(ValueError):
            d.run('nope', {})
        with self.assertRaises(ValueError):
            d.run('confidence', [])
        for op in d.OPS:
            with self.assertRaises(ValueError):
                d.run(op, {'bogus_param': 1})

    def test_missing_required_inputs_raise_value_error(self):
        cases = [
            ('tool_choice', {'candidates': [{'id': 'a', 'cost': 0, 'accuracy': 1, 'readiness': 1}]}),
            ('tool_choice', {'registry': ['a']}),
            ('blind_review', {'candidates': [{'author': 'x', 'content': 'y'}] * 2}),
            ('failure_log', {'attempt': {'action': 'x'}}),
            ('route_tested', {'rules': {'a': ['b']}}),
            ('incomplete_info', {'provided': {}}),
            ('incomplete_info', {'required': ['a']}),
            ('decision_record', {'mode': 'verify'}),
            ('decision_record', {'rules': []}),
            ('confidence', {'claims': [{'id': 'c1'}]}),
            ('phase_machine', {'events': [{'to': 'plan', 'error': 'x'}]}),
            ('intent_state', {'turns': [{'set': {'a': float('nan')}}]}),
            ('intent_state', {'turns': [{'set': {'a': [1]}}]}),
        ]
        for op, params in cases:
            with self.assertRaises(ValueError, msg=f'{op} {params}'):
                d.run(op, params)

    def test_module_hygiene(self):
        tree = ast.parse(inspect.getsource(d))
        banned = {'os', 'subprocess', 'socket', 'urllib', 'http', 'shutil', 'sqlite3', 'ctypes'}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    self.assertNotIn(a.name.split('.')[0], banned)
            elif isinstance(node, ast.ImportFrom):
                self.assertNotIn((node.module or '').split('.')[0], banned)
                self.assertNotEqual(node.level, 1, 'no project-relative imports')
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {'open', 'exec', 'eval', 'print', '__import__'})
        imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        self.assertLessEqual(imported, {'hashlib', 'json', 'math', 're'})


class IntentStateTests(unittest.TestCase):
    TURNS = [
        {'set': {'language': 'ar', 'music': 'soft'}},
        {'set': {'duration_s': 30}},
        {},
        {'unset': ['music']},
        {'set': {'duration_s': 45}},
    ]

    def test_constraint_persists_unset_removes_override_updates_provenance(self):
        r = R('intent_state', turns=self.TURNS)
        self.assertEqual(r['at_turn'], 5)
        self.assertEqual(r['active']['language'], {'value': 'ar', 'turn': 1, 'history': []})
        self.assertNotIn('music', r['active'])
        self.assertEqual(r['removed']['music']['unset_turn'], 4)
        self.assertEqual(r['active']['duration_s']['value'], 45)
        self.assertEqual(r['active']['duration_s']['turn'], 5)
        self.assertEqual(r['active']['duration_s']['history'], [{'value': 30, 'turn': 2}])

    def test_at_turn_folds_prefix(self):
        r = R('intent_state', turns=self.TURNS, at_turn=3)
        self.assertEqual(r['active']['music']['value'], 'soft')
        self.assertEqual(r['active']['duration_s']['turn'], 2)

    def test_set_and_unset_same_key_rejected(self):
        with self.assertRaises(ValueError):
            R('intent_state', turns=[{'set': {'a': 1}, 'unset': ['a']}])
        with self.assertRaises(ValueError):
            R('intent_state', turns=[{'add': {'a': 1}}])
        with self.assertRaises(ValueError):
            R('intent_state', turns=[{}] * 201)


class ConfidenceTests(unittest.TestCase):
    def test_no_evidence_is_never_fact(self):
        r = R('confidence', claims=[{'id': 'x', 'text': 'sure thing', 'claimed_label': 'fact'},
                                     {'id': 'y', 'text': 'blank refs', 'evidence': ['', '  ']}])
        labels = {c['id']: c['label'] for c in r['claims']}
        self.assertEqual(labels, {'x': 'guess', 'y': 'guess'})
        self.assertTrue(r['claims'][0]['downgraded'])
        self.assertIsNone(r['claims'][0]['source'])

    def test_mixed_list_split(self):
        claims = [
            {'id': 'f1', 'text': 'duration 31.2 s', 'evidence': ['ffprobe:31.2']},
            {'id': 'i1', 'text': 'too long for 30 s', 'derived_from': ['f1'], 'reasoning': '31.2>30'},
            {'id': 'i2', 'text': 'needs trim', 'derived_from': ['i1'], 'reasoning': 'policy'},
            {'id': 'g1', 'text': 'no reasoning', 'derived_from': ['f1']},
            {'id': 'g2', 'text': 'bad ref', 'derived_from': ['zz'], 'reasoning': 'x'},
            {'id': 'g3', 'text': 'from guess', 'derived_from': ['g1'], 'reasoning': 'x'},
            {'id': 'g4', 'text': 'vibes'},
        ]
        r = R('confidence', claims=claims)
        labels = {c['id']: c['label'] for c in r['claims']}
        self.assertEqual(labels, {'f1': 'fact', 'i1': 'inference', 'i2': 'inference',
                                  'g1': 'guess', 'g2': 'guess', 'g3': 'guess', 'g4': 'guess'})
        self.assertEqual(r['claims'][0]['source'], {'evidence': ['ffprobe:31.2']})
        self.assertEqual(r['claims'][1]['source']['derived_from'], ['f1'])
        self.assertEqual(r['claims'][4]['missing_refs'], ['zz'])
        s = r['summary']
        self.assertEqual((s['fact'], s['inference'], s['guess'], s['total']), (1, 2, 4, 7))
        self.assertEqual(s['overall'], 'contains_guesses')

    def test_duplicate_ids_rejected(self):
        with self.assertRaises(ValueError):
            R('confidence', claims=[{'id': 'a', 'text': 't'}, {'id': 'a', 'text': 'u'}])


class ToolChoiceTests(unittest.TestCase):
    def test_unregistered_never_chosen_and_criterion_named(self):
        cands = [
            {'id': 'ext.best', 'cost': 0.0, 'accuracy': 1.0, 'readiness': 1.0},
            {'id': 'video.verify', 'cost': 0.3, 'accuracy': 0.9, 'readiness': 0.9},
            {'id': 'video.shot_score', 'cost': 0.3, 'accuracy': 0.6, 'readiness': 0.9},
        ]
        r = R('tool_choice', candidates=cands, registry=['video.verify', 'video.shot_score'])
        self.assertEqual(r['chosen'], 'video.verify')
        self.assertEqual(r['deciding_criterion'], 'accuracy')
        self.assertIn('accuracy', r['reason'])
        self.assertIn('ext.best', [e['id'] for e in r['excluded']])
        self.assertNotIn('ext.best', [x['id'] for x in r['ranking']])

    def test_deciding_criterion_follows_weights(self):
        cands = [{'id': 'cheap', 'cost': 0.0, 'accuracy': 0.6, 'readiness': 0.5},
                 {'id': 'exact', 'cost': 1.0, 'accuracy': 0.7, 'readiness': 0.5}]
        r = R('tool_choice', candidates=cands, registry=['cheap', 'exact'],
              weights={'cost': 1.0, 'accuracy': 0.1, 'readiness': 0.0})
        self.assertEqual((r['chosen'], r['deciding_criterion']), ('cheap', 'cost'))
        self.assertIn('cost', r['reason'])

    def test_no_eligible(self):
        r = R('tool_choice', candidates=[{'id': 'x', 'cost': 0, 'accuracy': 1, 'readiness': 1}],
              registry=['y'])
        self.assertIsNone(r['chosen'])
        self.assertEqual(r['status'], 'no_eligible_tool')

    def test_bad_values_rejected(self):
        with self.assertRaises(ValueError):
            R('tool_choice', candidates=[{'id': 'x', 'cost': 2, 'accuracy': 1, 'readiness': 1}],
              registry=['x'])
        with self.assertRaises(ValueError):
            R('tool_choice', candidates=[{'id': 'x', 'cost': True, 'accuracy': 1, 'readiness': 1}],
              registry=['x'])


class PhaseMachineTests(unittest.TestCase):
    def test_skip_review_rejected(self):
        r = R('phase_machine', events=[{'to': 'plan'}, {'to': 'execute'}, {'to': 'done'}])
        self.assertEqual(r['final_phase'], 'execute')
        self.assertFalse(r['completed'])
        self.assertEqual(r['rejected'][0]['from'], 'execute')
        self.assertIn('review', r['rejected'][0]['reason'])
        with self.assertRaises(ValueError):
            R('phase_machine', events=[{'to': 'plan'}, {'to': 'execute'}, {'to': 'done'}],
              strict=True)

    def test_full_path_and_error_drop_between_runs(self):
        run1 = R('phase_machine', events=[
            {'to': 'plan'}, {'to': 'execute'}, {'error': 'e1'}, {'error': 'e2'},
            {'to': 'review'}, {'error': 'e3'}, {'to': 'execute'}, {'to': 'review'}, {'to': 'done'}])
        self.assertTrue(run1['completed'])
        self.assertEqual(run1['error_counts']['execute'], 2)
        self.assertEqual(run1['errors_total'], 3)
        run2 = R('phase_machine', events=[
            {'to': 'plan'}, {'to': 'execute'}, {'error': 'e1'}, {'to': 'review'}, {'to': 'done'}],
            previous_errors=run1['error_counts'])
        t = run2['error_trend']
        self.assertEqual((t['previous_total'], t['current_total'], t['change']), (3, 1, -2))
        self.assertTrue(t['improved'])
        self.assertEqual(t['per_phase_change']['execute'], -1)
        self.assertEqual(sorted(t['dropped_phases']), ['execute', 'review'])

    def test_bad_phase(self):
        with self.assertRaises(ValueError):
            R('phase_machine', events=[{'to': 'ship'}])


class BlindReviewTests(unittest.TestCase):
    CANDS = [{'author': 'alice_agent', 'content': 'plan A: cut at 12s'},
             {'author': 'bob_agent', 'content': 'plan B: cut at 10s'},
             {'author': 'carol_agent', 'content': 'plan C: no cut'}]

    @staticmethod
    def S(ev, cand, mode, v):
        return {'evaluator': ev, 'candidate': cand, 'mode': mode, 'criteria': {'quality': v}}

    def test_labels_hide_authors_and_are_stable(self):
        r = R('blind_review', candidates=self.CANDS, scores=[])
        blob = json.dumps(r['blind_view'])
        for c in self.CANDS:
            self.assertNotIn(c['author'], blob)
            self.assertNotIn('alice', blob)
        labels = [x['label'] for x in r['blind_view']]
        self.assertEqual(len(set(labels)), 3)
        self.assertTrue(all(lbl.startswith('R-') for lbl in labels))
        self.assertEqual(labels, [x['label'] for x in
                                  R('blind_review', candidates=self.CANDS, scores=[])['blind_view']])

    def test_biased_evaluator_flagged_fair_one_not(self):
        S = self.S
        scores = [
            S('alice_agent', 0, 'blind', 5), S('alice_agent', 0, 'known', 9),
            S('alice_agent', 1, 'blind', 7), S('alice_agent', 1, 'known', 7),
            S('bob_agent', 1, 'blind', 6), S('bob_agent', 1, 'known', 6),
            S('bob_agent', 2, 'blind', 8), S('bob_agent', 2, 'known', 8),
            S('carol_agent', 0, 'blind', 6),
        ]
        r = R('blind_review', candidates=self.CANDS, scores=scores)
        self.assertEqual(r['flagged_evaluators'], ['alice_agent'])
        alice = next(b for b in r['bias'] if b['evaluator'] == 'alice_agent')
        self.assertAlmostEqual(alice['bias'], 4.0)
        bob = next(b for b in r['bias'] if b['evaluator'] == 'bob_agent')
        self.assertFalse(bob['flagged'])
        carol = next(b for b in r['bias'] if b['evaluator'] == 'carol_agent')
        self.assertEqual(carol['status'], 'insufficient_data')
        # ranking is blind-only, then de-anonymised
        top = r['de_anonymised'][0]
        self.assertEqual(top['author'], 'carol_agent')
        means = {x['author']: x['blind_mean'] for x in r['de_anonymised']}
        self.assertAlmostEqual(means['alice_agent'], 5.5)
        self.assertAlmostEqual(means['bob_agent'], 6.5)
        self.assertAlmostEqual(means['carol_agent'], 8.0)

    def test_criteria_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            R('blind_review', candidates=self.CANDS,
              scores=[self.S('x', 0, 'blind', 5)], criteria={'clarity': 1})


class ResolveConflictTests(unittest.TestCase):
    def test_owner_now_beats_earlier_owner(self):
        r = R('resolve_conflict', commands=[
            {'subject': 'aspect', 'value': '16:9', 'source': 'earlier_owner'},
            {'subject': 'Aspect', 'value': '9:16', 'source': 'explicit_owner_now'},
            {'subject': 'aspect', 'value': '1:1', 'source': 'agent_suggestion'}])
        s = r['subjects']['aspect']
        self.assertEqual((s['status'], s['winner'], s['level']),
                         ('resolved', '9:16', 'explicit_owner_now'))
        self.assertEqual(len(s['overridden']), 2)

    def test_nothing_overrides_safety(self):
        for src in d.PRIORITY[1:]:
            r = R('resolve_conflict', commands=[
                {'subject': 'publish', 'value': 'auto', 'source': src},
                {'subject': 'publish', 'value': 'ask_first', 'source': 'safety_rule'}])
            s = r['subjects']['publish']
            self.assertEqual((s['winner'], s['level']), ('ask_first', 'safety_rule'))
            self.assertTrue(s['overridden'][0]['blocked_by_safety'])

    def test_tie_needs_question(self):
        r = R('resolve_conflict', commands=[
            {'subject': 'music', 'value': 'none', 'source': 'explicit_owner_now'},
            {'subject': 'music', 'value': 'soft', 'source': 'explicit_owner_now'},
            {'subject': 'music', 'value': 'loud', 'source': 'repo_rule'}])
        s = r['subjects']['music']
        self.assertEqual(s['status'], 'needs_question')
        self.assertIsNone(s['winner'])
        self.assertEqual(sorted(s['options']), ['none', 'soft'])
        self.assertEqual(r['questions'][0]['subject'], 'music')

    def test_unknown_source_rejected(self):
        with self.assertRaises(ValueError):
            R('resolve_conflict', commands=[{'subject': 'a', 'value': 1, 'source': 'boss'}])


class FailureLogTests(unittest.TestCase):
    LOG = [{'action': 'Render reel', 'cause_signature': 'audio silent on iPhone',
            'hypothesis': 'mp3 in mp4', 'experiment': 'play on phone', 'fix': 'raise volume',
            'outcome': 'fail'}]

    def test_same_failing_action_flagged(self):
        for fix in ('', 'Raise  Volume'):
            r = R('failure_log', log=self.LOG,
                  attempt={'action': 'render reel', 'cause_signature': 'Audio silent on iPhone',
                           'fix': fix})
            self.assertEqual(r['check']['verdict'], 'blocked_repeat')
            self.assertTrue(r['check']['flagged'])
            self.assertEqual(r['check']['matched_failures'], [0])

    def test_different_fix_allowed(self):
        r = R('failure_log', log=self.LOG,
              attempt={'action': 'render reel', 'cause_signature': 'audio silent on iPhone',
                       'fix': 'encode audio as AAC'})
        self.assertEqual(r['check']['verdict'], 'allowed_new_fix')
        self.assertFalse(r['check']['flagged'])
        r2 = R('failure_log', log=self.LOG, attempt={'action': 'upload'})
        self.assertEqual(r2['check']['verdict'], 'allowed')


class RouteTestedTests(unittest.TestCase):
    RULES = {'render': ['video.produce', 'video.preview'], 'رندر': ['video.produce'],
             'verify': ['video.verify'], 'magic': ['knowledge.route']}
    STATUS = {'video.produce': 'untested', 'video.preview': 'tested', 'video.verify': 'tested',
              'knowledge.route': 'descriptive'}

    def test_untested_never_selected(self):
        r = R('route_tested', task='render والرندر النهائي and magic', rules=self.RULES,
              status=self.STATUS)
        selected = [s['adapter'] for s in r['selected']]
        self.assertEqual(selected, ['video.preview'])
        self.assertEqual(r['chosen'], 'video.preview')
        ne = {x['adapter']: x for x in r['not_executable']}
        self.assertEqual(set(ne), {'video.produce', 'knowledge.route'})
        self.assertEqual(ne['video.produce']['label'], 'not executable')
        self.assertEqual(ne['video.produce']['keywords'], ['render', 'رندر'])

    def test_only_untested_match(self):
        r = R('route_tested', task='magic please', rules=self.RULES, status=self.STATUS)
        self.assertIsNone(r['chosen'])
        self.assertEqual(r['status'], 'no_tested_adapter')
        r2 = R('route_tested', task='nothing here', rules=self.RULES, status=self.STATUS)
        self.assertEqual(r2['status'], 'no_match')

    def test_unknown_status_value_rejected(self):
        with self.assertRaises(ValueError):
            R('route_tested', task='x', rules=self.RULES, status={'video.verify': 'probably'})


class IncompleteInfoTests(unittest.TestCase):
    REQ = [{'name': 'duration_s', 'type': 'number'}, {'name': 'platform', 'type': 'string'}]
    RULES = [{'when': [{'input': 'duration_s', 'op': '>', 'value': 60}], 'then': 'trim'}]

    def test_missing_input_gives_gaps_and_no_invented_value(self):
        r = R('incomplete_info', required=self.REQ, provided={'duration_s': 90},
              rules=self.RULES, default_decision='keep')
        self.assertEqual(r['status'], 'needs_input')
        self.assertIsNone(r['decision'])
        self.assertEqual(r['gaps'], [{'name': 'platform', 'problem': 'missing',
                                      'expected_type': 'string'}])
        self.assertIsNone(r['values']['platform'])
        self.assertEqual(r['safe_action'], 'ask_owner')

    def test_wrong_type_and_empty_string_are_gaps(self):
        r = R('incomplete_info', required=self.REQ, provided={'duration_s': '90', 'platform': ' '})
        self.assertEqual({g['name']: g['problem'] for g in r['gaps']},
                         {'duration_s': 'wrong_type', 'platform': 'missing'})
        self.assertIsNone(r['values']['duration_s'])

    def test_complete_inputs_decide(self):
        r = R('incomplete_info', required=self.REQ, provided={'duration_s': 90, 'platform': 'reels'},
              rules=self.RULES, default_decision='keep')
        self.assertEqual((r['status'], r['decision'], r['rule_applied']), ('decided', 'trim', 0))
        r2 = R('incomplete_info', required=self.REQ, provided={'duration_s': 9, 'platform': 'reels'},
               rules=self.RULES, default_decision='keep')
        self.assertEqual((r2['decision'], r2['rule_applied']), ('keep', None))

    def test_rule_on_unknown_input_rejected(self):
        with self.assertRaises(ValueError):
            R('incomplete_info', required=self.REQ, provided={},
              rules=[{'when': [{'input': 'mood', 'op': '==', 'value': 1}], 'then': 'x'}])


class DecisionRecordTests(unittest.TestCase):
    INPUTS = {'duration_s': 31.2, 'platform': 'reels', 'nested': {'b': 1, 'a': [1, 2]}}
    RULES = [{'when': [{'input': 'duration_s', 'op': '>', 'value': 30}], 'then': 'trim'}]

    def build(self, inputs):
        return R('decision_record', inputs=inputs, rules=self.RULES, default='keep',
                 evidence=['ffprobe:duration=31.2'])['record']

    def test_same_inputs_same_hash_and_decision(self):
        a = self.build(self.INPUTS)
        reordered = {'nested': {'a': [1, 2], 'b': 1}, 'platform': 'reels', 'duration_s': 31.2}
        b = self.build(reordered)
        self.assertEqual(a['input_sha256'], b['input_sha256'])
        self.assertEqual(a['record_sha256'], b['record_sha256'])
        self.assertEqual((a['result'], a['rule_applied']), ('trim', 0))
        self.assertEqual(a['evidence'], ['ffprobe:duration=31.2'])
        self.assertEqual(len(a['input_sha256']), 64)
        v = d.verify(a)['result']
        self.assertTrue(v['ok'], v)
        self.assertTrue(d.verify(a, self.INPUTS)['result']['ok'])

    def test_changed_input_changes_hash_and_old_record_fails(self):
        old = self.build(self.INPUTS)
        changed = dict(self.INPUTS, duration_s=29.0)
        new = self.build(changed)
        self.assertNotEqual(old['input_sha256'], new['input_sha256'])
        self.assertEqual(new['result'], 'keep')
        v = d.verify(old, changed)['result']
        self.assertFalse(v['ok'])
        self.assertFalse(v['checks']['input_hash_matches'])
        self.assertFalse(v['checks']['decision_matches'])

    def test_tampered_record_fails(self):
        rec = copy.deepcopy(self.build(self.INPUTS))
        rec['result'] = 'keep'
        v = d.verify(rec)['result']
        self.assertFalse(v['ok'])
        self.assertFalse(v['checks']['record_hash_matches'])

    def test_verify_requires_record_and_rejects_nan(self):
        with self.assertRaises(ValueError):
            d.run('decision_record', {'mode': 'verify'})
        with self.assertRaises(ValueError):
            R('decision_record', inputs={'x': float('inf')}, rules=[])


if __name__ == '__main__':
    unittest.main()
