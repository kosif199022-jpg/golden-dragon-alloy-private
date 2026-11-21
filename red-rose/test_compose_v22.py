"""Tests for compose_v22 (topics 27.01-27.10)."""
import ast
import inspect
import json
import unittest
import xml.etree.ElementTree as ET
from unittest import mock

import accounting_v21
import compose_v22 as C
import physics_v20

SVG = '{http://www.w3.org/2000/svg}'
ALLOWED_PROJECT = {'physics_v20', 'geometry_v20', 'thinking_v21', 'decision_v21', 'accounting_v21'}


class TestInterface(unittest.TestCase):
    def test_topics_and_ops(self):
        self.assertEqual(len(C.TOPICS), 10)
        self.assertEqual(set(C.TOPICS.values()), set(C.OPS))
        self.assertEqual(set(C.TOPICS), set(C.TOPIC_NAMES_AR))

    def test_every_op_runs_with_empty_params_and_is_json(self):
        for op in C.OPS:
            with self.subTest(op=op):
                out = C.run(op, {})
                self.assertEqual(set(out), {'op', 'result', 'assumptions', 'limits'})
                self.assertEqual(out['op'], op)
                self.assertTrue(out['assumptions'] and out['limits'])
                json.dumps(out, allow_nan=False)

    def test_unknown_params_and_bad_ops_raise_value_error(self):
        for op in C.OPS:
            with self.subTest(op=op):
                with self.assertRaises(ValueError):
                    C.run(op, {'no_such_param': 1})
        with self.assertRaises(ValueError):
            C.run('nope', {})
        with self.assertRaises(ValueError):
            C.run('variations', [])
        with self.assertRaises(ValueError):
            C.run('variations', {'n': True})

    def test_missing_required_inputs_raise_value_error(self):
        cases = [
            ('audio_scene_edl', {'scenes': [{'start': 0, 'end': 1}]}),
            ('retrieve_then_dispatch', {'task': 'x y'}),
            ('accounting_workflow', {'invoices': []}),
            ('accounting_workflow', {'tenant': 't'}),
            ('variations', {'base': {'a': 1.0}}),
            ('originality_check', {'protected_names': ['X']}),
            ('critic_roles', {'proposal': {}}),
            ('capability_proposal', {'entry': {'title': 't'}}),
        ]
        for op, params in cases:
            with self.subTest(op=op, params=params):
                with self.assertRaises(ValueError):
                    C.run(op, params)

    def test_module_hygiene(self):
        tree = ast.parse(inspect.getsource(C))
        banned = {'os', 'subprocess', 'socket', 'urllib', 'http', 'shutil', 'sqlite3', 'ctypes'}
        stdlib_ok = {'__future__', 'inspect', 'json', 'math', 'random', 're', 'xml'}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    root = a.name.split('.')[0]
                    self.assertNotIn(root, banned)
                    self.assertIn(root, stdlib_ok | ALLOWED_PROJECT)
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or '').split('.')[0]
                self.assertNotIn(root, banned)
                self.assertIn(root, stdlib_ok | ALLOWED_PROJECT)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {'open', 'exec', 'eval', 'compile', 'print'})


class TestLayerComposer(unittest.TestCase):  # 27.01
    def compose(self, layers):
        return C.run('layer_composer', {'layers': layers, 'width': 800, 'height': 600})['result']

    def test_z_order_opacity_unique_ids_and_escaping(self):
        frag = '<defs><linearGradient id="g"/></defs><rect id="r" width="5" height="5" fill="url(#g)"/>'
        layers = [
            {'id': 'top', 'kind': 'text', 'z': 9, 'opacity': 2.5, 'text': 'A & B <c> "d"'},
            {'id': 'v2', 'kind': 'vector', 'z': 5, 'opacity': 0.25, 'blend': 'multiply', 'svg': frag},
            {'id': 'bg', 'kind': 'photo_ref', 'z': -1, 'opacity': 0.9, 'href': 'plate.png'},
            {'id': 'v1', 'kind': 'vector', 'z': 2, 'opacity': -1, 'blend': 'screen', 'svg': frag},
        ]
        r = self.compose(layers)
        self.assertEqual(r['order'], ['bg', 'v1', 'v2', 'top'])
        root = ET.fromstring(r['svg'])
        groups = root.findall(SVG + 'g')
        self.assertEqual([g.get('id') for g in groups],
                         ['layer__bg', 'layer__v1', 'layer__v2', 'layer__top'])
        self.assertEqual([float(g.get('opacity')) for g in groups], [0.9, 0.0, 0.25, 1.0])
        rep = {x['id']: x for x in r['layers']}
        self.assertTrue(rep['top']['opacity_clamped'])
        self.assertFalse(rep['v2']['opacity_clamped'])
        self.assertIn('mix-blend-mode:multiply', groups[2].get('style'))
        # duplicate internal ids made unique and references rewritten
        ids = [e.get('id') for e in root.iter() if e.get('id')]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(r['ids_unique'])
        self.assertIn('v1__g', ids)
        self.assertIn('v2__g', ids)
        self.assertIn('url(#v2__g)', r['svg'])
        self.assertEqual(rep['v1']['ids_renamed'], {'g': 'v1__g', 'r': 'v1__r'})
        # text escaped and round-trips
        self.assertIn('A &amp; B &lt;c&gt;', r['svg'])
        self.assertEqual(groups[3].find(SVG + 'text').text, 'A & B <c> "d"')

    def test_refuses_scripts_and_bad_layers(self):
        bad = [
            [{'id': 'a', 'kind': 'vector', 'svg': '<script>alert(1)</script>'}],
            [{'id': 'a', 'kind': 'vector', 'svg': '<rect onload="x()"/>'}],
            [{'id': 'a', 'kind': 'vector', 'svg': '<rect id="x"/><rect id="x"/>'}],
            [{'id': 'a', 'kind': 'vector', 'svg': '<rect>'}],
            [{'id': 'a', 'kind': 'photo_ref', 'href': 'javascript:alert(1)'}],
            [{'id': 'a', 'kind': 'text', 'text': 'x'}, {'id': 'a', 'kind': 'text', 'text': 'y'}],
            [{'id': 'a', 'kind': 'text', 'text': 'x', 'opacity': float('nan')}],
            [{'id': 'a', 'kind': 'video', 'href': 'x'}],
            [{'id': 'a', 'kind': 'text'}],
        ]
        for layers in bad:
            with self.subTest(layers=layers):
                with self.assertRaises(ValueError):
                    self.compose(layers)


class TestAudioSceneEdl(unittest.TestCase):  # 27.02
    def test_audible_cut_moves_to_nearest_silence_and_never_inside_speech(self):
        scenes = [{'start': 0, 'end': 5.0}, {'start': 5.0, 'end': 10.0}]
        silences = [{'start': 4.5, 'end': 4.8}, {'start': 9.0, 'end': 10.0}]
        r = C.run('audio_scene_edl', {'scenes': scenes, 'silences': silences, 'cuts': [7.0],
                                      'tolerance': 0.5})['result']
        d = {x['requested']: x for x in r['decisions']}
        self.assertEqual(d[5.0]['action'], 'snapped')
        self.assertTrue(4.5 <= d[5.0]['cut'] <= 4.8)
        self.assertAlmostEqual(d[5.0]['cut'], 4.78)
        self.assertEqual(d[7.0]['action'], 'dropped')  # 2 s from any silence
        self.assertEqual(r['cuts_inside_audible'], [])
        for t in r['cut_points']:
            for a, b in r['audible_spans']:
                self.assertFalse(a < t < b, f'cut {t} inside audible {a}-{b}')
        self.assertAlmostEqual(r['scenes'][0]['audible_fraction'], 1 - 0.3 / 5)
        self.assertAlmostEqual(r['scenes'][1]['audible_fraction'], 0.8)
        self.assertEqual(r['edl'][0]['start'], 0.0)
        self.assertEqual(r['edl'][-1]['end'], 10.0)
        for i in range(1, len(r['edl'])):
            self.assertEqual(r['edl'][i]['start'], r['edl'][i - 1]['end'])

    def test_cut_already_in_silence_is_kept(self):
        r = C.run('audio_scene_edl', {'scenes': [{'start': 0, 'end': 2}, {'start': 2, 'end': 4}],
                                      'silences': [{'start': 1.8, 'end': 2.3}]})['result']
        self.assertEqual(r['decisions'][0]['action'], 'kept')
        self.assertEqual(r['cut_points'], [2.0])

    def test_bad_intervals(self):
        with self.assertRaises(ValueError):
            C.run('audio_scene_edl', {'scenes': [{'start': 2, 'end': 1}], 'silences': []})
        with self.assertRaises(ValueError):
            C.run('audio_scene_edl', {'scenes': [{'start': 0, 'end': 5}], 'silences': [],
                                      'duration': 3})


class TestIkPhysics(unittest.TestCase):  # 27.03
    def test_contact_frames_have_zero_slide_and_spring_decays(self):
        r = C.run('ik_physics', {'frames': 48, 'fps': 24, 'hip_speed': 0.3,
                                 'contacts': [{'start_frame': 0, 'end_frame': 20, 'plant': [0.1, 0.0]},
                                              {'start_frame': 30, 'end_frame': 47, 'plant': [0.4, 0.0]}],
                                 'spring_k': 80.0, 'spring_c': 4.0, 'offset0': 0.1})['result']
        contact_slides = [f['foot_slide'] for f in r['frames'] if f['foot_slide'] is not None]
        self.assertGreater(len(contact_slides), 30)
        self.assertLessEqual(max(contact_slides), 1e-9)
        self.assertLessEqual(r['max_contact_foot_slide'], 1e-9)
        self.assertEqual(r['contact_frames_unreachable'], [])
        self.assertTrue(r['spring']['decays'])
        self.assertLess(r['spring']['second_half_peak_offset'], r['spring']['first_half_peak_offset'])
        self.assertLess(abs(r['frames'][-1]['head_offset']), 0.1)
        # swing frames actually move the foot
        swing = [f for f in r['frames'] if f['contact'] is None]
        self.assertTrue(any(f['foot'][1] > 0.01 for f in swing))

    def test_unreachable_plant_is_reported_as_slide(self):
        r = C.run('ik_physics', {'frames': 24, 'hip_speed': 2.0,
                                 'contacts': [{'start_frame': 0, 'end_frame': 23, 'plant': [0.0, 0.0]}]})['result']
        self.assertTrue(r['contact_frames_unreachable'])
        self.assertGreater(r['max_contact_foot_slide'], 1e-6)

    def test_overlapping_contacts_rejected(self):
        with self.assertRaises(ValueError):
            C.run('ik_physics', {'contacts': [{'start_frame': 0, 'end_frame': 5, 'plant': [0, 0]},
                                              {'start_frame': 5, 'end_frame': 8, 'plant': [0, 0]}]})


class TestRetrieveThenDispatch(unittest.TestCase):  # 27.04
    REFS = [{'id': 'blog', 'description': 'bouncing ball drop height gravity tutorial'},
            {'id': 'fall', 'description': 'falling under gravity'}]

    def test_top_reference_without_adapter_is_never_executed(self):
        registry = {'fall': {'module': 'physics_v20', 'op': 'fall', 'params': {}}}
        with mock.patch.object(physics_v20, 'run', side_effect=AssertionError('executed')) as spy:
            r = C.run('retrieve_then_dispatch', {'task': 'ball drop height under gravity',
                                                 'references': self.REFS, 'registry': registry})['result']
        spy.assert_not_called()
        self.assertEqual(r['chosen'], 'blog')
        self.assertEqual(r['status'], 'reference_only_not_executed')
        self.assertFalse(r['executed'])
        self.assertIsNone(r['execution'])

    def test_top_reference_with_adapter_is_executed(self):
        registry = {'fall': {'module': 'physics_v20', 'op': 'fall', 'params': {'y0': 3.0}}}
        r = C.run('retrieve_then_dispatch', {'task': 'object falling under gravity',
                                             'references': self.REFS, 'registry': registry})['result']
        self.assertEqual(r['chosen'], 'fall')
        self.assertEqual(r['status'], 'executed')
        self.assertEqual(r['execution']['op'], 'fall')

    def test_invalid_adapter_not_executed(self):
        registry = {'fall': {'module': 'physics_v20', 'op': 'fall', 'params': {'height': 3.0}}}
        with mock.patch.object(physics_v20, 'run') as spy:
            r = C.run('retrieve_then_dispatch', {'task': 'falling under gravity',
                                                 'references': self.REFS, 'registry': registry})['result']
        spy.assert_not_called()
        self.assertEqual(r['status'], 'adapter_invalid_not_executed')
        bad = {'fall': {'module': 'os', 'op': 'system', 'params': {}}}
        r = C.run('retrieve_then_dispatch', {'task': 'falling under gravity',
                                             'references': self.REFS, 'registry': bad})['result']
        self.assertFalse(r['executed'])


class TestAccountingWorkflow(unittest.TestCase):  # 27.05
    def data(self, tenant='acme'):
        return {
            'tenant': 'acme',
            'invoices': [{'tenant': tenant, 'id': 1, 'supplier': 'S', 'invoice_no': 'X-1',
                          'amount': '10.00', 'date': '2026-01-01'},
                         {'tenant': 'acme', 'id': 2, 'supplier': 's', 'invoice_no': 'X1',
                          'amount': '10.00', 'date': '2026-01-02'}],
            'ledger': [{'tenant': 'acme', 'id': 'L1', 'date': '2026-01-05', 'amount': '10.00'}],
            'bank': [{'tenant': 'acme', 'id': 'B1', 'date': '2026-01-05', 'amount': '10.00'}],
            'journal': [{'tenant': 'acme', 'entry_id': 'J', 'account': '1', 'debit': '10.00'},
                        {'tenant': 'acme', 'entry_id': 'J', 'account': '2', 'credit': '10.00'}],
        }

    def test_per_tenant_results_match_accounting_v21(self):
        r = C.run('accounting_workflow', self.data())['result']
        self.assertEqual(r['status'], 'completed')
        self.assertEqual([s['step'] for s in r['steps']],
                         ['duplicate_invoices', 'bank_reconcile', 'trial_balance'])
        direct = accounting_v21.run('trial_balance', {'lines': [
            {'entry_id': 'J', 'account': '1', 'debit': '10.00'},
            {'entry_id': 'J', 'account': '2', 'credit': '10.00'}]})
        self.assertEqual(r['steps'][2]['output'], direct)
        self.assertEqual(r['steps'][0]['counts']['duplicate_groups'], 1)
        self.assertEqual(r['steps'][1]['counts']['matched'], 1)

    def test_cross_tenant_record_blocks_before_processing(self):
        with mock.patch.object(accounting_v21, 'run') as spy:
            r = C.run('accounting_workflow', self.data(tenant='other-co'))['result']
            spy.assert_not_called()
        self.assertEqual(r['status'], 'blocked')
        self.assertFalse(r['processed'])
        self.assertEqual(r['rejected'][0]['record_tenant'], 'other-co')
        with mock.patch.object(accounting_v21, 'run') as spy:
            with self.assertRaises(ValueError):
                C.run('accounting_workflow', {**self.data(tenant='other-co'), 'on_cross_tenant': 'raise'})
            spy.assert_not_called()
        d = self.data()
        del d['ledger'][0]['tenant']
        self.assertEqual(C.run('accounting_workflow', d)['result']['status'], 'blocked')


class TestVariations(unittest.TestCase):  # 27.06
    P = {'base': {'a': 0.0, 'b': 1.0}, 'ranges': {'a': [-1, 1], 'b': [0, 2]}, 'n': 12, 'seed': 42,
         'metrics': {'ma': {'param': 'a', 'target': 0.5}, 'mb': {'param': 'b', 'target': 1.0}},
         'weights': {'ma': 2.0, 'mb': 1.0}}

    def test_same_seed_same_output_and_human_pick(self):
        r1 = C.run('variations', dict(self.P))['result']
        r2 = C.run('variations', dict(self.P))['result']
        self.assertEqual(r1, r2)
        self.assertEqual(len(r1['variations']), 12)
        self.assertEqual(r1['status'], 'awaiting_human_pick')
        self.assertIsNone(r1['final_choice'])
        scores = {v['id']: v['score'] for v in r1['variations']}
        ranked = [scores[i] for i in r1['ranking']]
        self.assertEqual(ranked, sorted(ranked, reverse=True))
        r3 = C.run('variations', {**self.P, 'seed': 43})['result']
        self.assertNotEqual(r1['variations'], r3['variations'])

    def test_weights_must_match_metrics(self):
        with self.assertRaises(ValueError):
            C.run('variations', {**self.P, 'weights': {'ma': 1.0}})


class TestCriticRoles(unittest.TestCase):  # 27.07
    def test_missing_tests_is_blocking_and_flag_present(self):
        r = C.run('critic_roles', {'proposal': {'title': 'x', 'claims': [{'text': 'faster', 'evidence': 'bench'}],
                                                'limits': ['2D'], 'assumptions': ['a']}})['result']
        self.assertTrue(r['single_system_simulated_roles'])
        self.assertIn('one system', r['disclosure'])
        self.assertEqual(r['verdict'], 'blocked')
        codes = {(i['code'], i['severity']) for i in r['issues']}
        self.assertIn(('missing_tests', 'blocking'), codes)
        self.assertEqual([x['role'] for x in r['roles']], ['proposer', 'critic', 'skeptic', 'judge'])

    def test_complete_proposal_accepted_and_unsupported_claim_flagged(self):
        good = {'title': 'x', 'claims': [{'text': 'faster', 'evidence': 'bench'}], 'tests': ['test_x'],
                'limits': ['2D'], 'assumptions': ['a']}
        self.assertEqual(C.run('critic_roles', {'proposal': good})['result']['verdict'], 'accept')
        r = C.run('critic_roles', {'proposal': {**good, 'claims': ['always perfect']}})['result']
        self.assertEqual(r['verdict'], 'revise')
        self.assertIn('unsupported_claim', {i['code'] for i in r['issues']})


class TestGenericContract(unittest.TestCase):  # 27.08
    def test_footprint_lists_exactly_used_modules(self):
        r = C.run('generic_contract', {'pipeline': [
            {'module': 'physics_v20', 'op': 'fall', 'params': {'y0': 1.0}},
            {'module': 'geometry_v20', 'op': 'ik_two_bone', 'params': {'l1': 1.0}},
            {'module': 'physics_v20', 'op': 'spring', 'params': {}}],
            'declared_modules': ['physics_v20', 'geometry_v20', 'accounting_v21']})['result']
        self.assertTrue(r['all_valid'])
        self.assertEqual(r['footprint'], ['geometry_v20', 'physics_v20'])
        self.assertEqual(r['declared_but_unused'], ['accounting_v21'])
        self.assertTrue(r['bloat'])
        self.assertFalse(r['executed'])

    def test_wrong_param_rejected_before_execution(self):
        pipeline = [{'module': 'physics_v20', 'op': 'fall', 'params': {'y0': 1.0}},
                    {'module': 'geometry_v20', 'op': 'ik_two_bone', 'params': {'lenght1': 1.0}}]
        with mock.patch.object(physics_v20, 'run') as spy:
            r = C.run('generic_contract', {'pipeline': pipeline, 'execute': True})['result']
        spy.assert_not_called()
        self.assertFalse(r['all_valid'])
        self.assertFalse(r['executed'])
        self.assertIn('lenght1', r['calls'][1]['problems'][0])
        self.assertTrue(r['calls'][0]['valid'])

    def test_valid_pipeline_executes_when_asked(self):
        r = C.run('generic_contract', {'pipeline': [{'module': 'physics_v20', 'op': 'fall', 'params': {}}],
                                       'execute': True})['result']
        self.assertTrue(r['executed'])
        self.assertEqual(r['outputs'][0]['op'], 'fall')

    def test_unknown_module_or_op(self):
        r = C.run('generic_contract', {'pipeline': [{'module': 'os', 'op': 'system'},
                                                    {'module': 'physics_v20', 'op': 'warp'}]})['result']
        self.assertEqual([c['valid'] for c in r['calls']], [False, False])
        self.assertEqual(r['footprint'], ['physics_v20'])


class TestCapabilityProposal(unittest.TestCase):  # 27.09
    ENTRY = {'title': 'Rope solver', 'source': 'old index #12', 'licence': 'MIT'}

    def test_registering_without_tests_refused(self):
        with self.assertRaises(ValueError):
            C.run('capability_proposal', {'entry': self.ENTRY, 'status': 'registered'})
        with self.assertRaises(ValueError):
            C.run('capability_proposal', {'entry': self.ENTRY, 'status': 'registered',
                                          'test_evidence': {'test_file': 'test_rope.py', 'passing': 0}})
        with self.assertRaises(ValueError):
            C.run('capability_proposal', {'entry': self.ENTRY, 'status': 'registered',
                                          'test_evidence': {'test_file': 'test_rope.py', 'passing': 5,
                                                            'failing': 1}})
        r = C.run('capability_proposal', {'entry': self.ENTRY, 'status': 'registered',
                                          'test_evidence': {'test_file': 'test_rope.py', 'passing': 5}})
        self.assertEqual(r['result']['record']['status'], 'registered')
        self.assertEqual(C.run('capability_proposal', {'entry': self.ENTRY})['result']['record']['status'],
                         'proposed')

    def test_gpl_needs_owner_review(self):
        gpl = {**self.ENTRY, 'licence': 'GPL-3.0'}
        with self.assertRaises(ValueError):
            C.run('capability_proposal', {'entry': gpl})
        rec = C.run('capability_proposal', {'entry': gpl, 'needs_owner_review': True})['result']['record']
        self.assertEqual(rec['licence_review'], 'needs_owner_review')
        self.assertEqual(rec['status'], 'proposed')
        with self.assertRaises(ValueError):
            C.run('capability_proposal', {'entry': gpl, 'needs_owner_review': True, 'status': 'registered',
                                          'test_evidence': {'test_file': 'test_rope.py', 'passing': 3}})
        with self.assertRaises(ValueError):
            C.run('capability_proposal', {'entry': {**self.ENTRY, 'licence': None}})


class TestOriginalityCheck(unittest.TestCase):  # 27.10
    def test_missing_licence_and_protected_name_flagged(self):
        r = C.run('originality_check', {
            'deliverable': {'title': 'New MegaPhone X launch film',
                            'assets': [{'name': 'shot.png', 'origin': 'original', 'licence': 'owner-original'},
                                       {'name': 'track.wav', 'origin': 'licensed'},
                                       {'name': 'font.otf', 'origin': 'licensed', 'licence': 'CC-BY-4.0'}]},
            'protected_names': ['MegaPhone']})['result']
        codes = {(i['code'], i['asset']) for i in r['issues']}
        self.assertIn(('missing_licence', 'track.wav'), codes)
        self.assertIn(('missing_attribution', 'font.otf'), codes)
        self.assertIn(('protected_name', None), codes)
        self.assertEqual(r['protected_name_hits'][0]['where'], 'title')
        self.assertEqual(r['verdict'], 'needs_fix')

    def test_clean_deliverable_is_clear(self):
        r = C.run('originality_check', {
            'deliverable': {'title': 'Rose film', 'assets': [
                {'name': 'a.png', 'origin': 'owner_supplied', 'licence': 'owner'},
                {'name': 'b.wav', 'origin': 'licensed', 'licence': 'CC-BY-4.0', 'attribution': 'Artist'}]},
            'protected_names': ['Megaphone']})['result']
        self.assertEqual(r['verdict'], 'clear')
        bad_origin = C.run('originality_check', {'deliverable': {'title': 't', 'assets': [
            {'name': 'x', 'origin': 'scraped', 'licence': 'MIT'}]}})['result']
        self.assertEqual(bad_origin['issues'][0]['code'], 'missing_or_invalid_origin')


if __name__ == '__main__':
    unittest.main()
