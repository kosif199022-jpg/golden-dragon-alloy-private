"""Tests for governance_v22 (Red Rose V22 single-skill governance helpers)."""
import ast
import copy
import hashlib
import inspect
import json
import unittest

import governance_v22 as g


def R(op, **params):
    return g.run(op, params)['result']


class InterfaceTests(unittest.TestCase):
    def test_topics_ops_and_names(self):
        self.assertEqual(list(g.TOPICS), [f'01.{i:02d}' for i in range(1, 11)])
        self.assertEqual(list(g.TOPICS.values()), list(g.OPS))
        self.assertEqual(set(g.TOPIC_NAMES_AR), set(g.TOPICS))

    def test_every_op_runs_with_empty_params_and_is_json(self):
        for op in g.OPS:
            out = g.run(op, {})
            self.assertEqual(set(out), {'op', 'result', 'assumptions', 'limits'})
            self.assertEqual(out['op'], op)
            self.assertTrue(out['assumptions'] and out['limits'])
            json.dumps(out, allow_nan=False)
            self.assertEqual(out, g.run(op, {}), f'{op} not deterministic')
            self.assertEqual(out, g.run(op), f'{op} params=None differs')

    def test_run_validation(self):
        with self.assertRaises(ValueError):
            g.run('nope', {})
        with self.assertRaises(ValueError):
            g.run('skill_contract', [])
        with self.assertRaises(ValueError):
            g.run('skill_contract', {1: 2})
        for op in g.OPS:
            with self.assertRaises(ValueError):
                g.run(op, {'bogus_param': 1})

    def test_missing_required_inputs_raise_value_error(self):
        cases = [
            ('skill_contract', {'contract': 'not a dict'}),
            ('provenance_card', {'action': 'verify'}),
            ('provenance_card', {'idea': 'x'}),
            ('behaviour_compare', {'new_code': 'x = 1'}),
            ('behaviour_compare', {'cases': []}),
            ('capability_overlap', {'capabilities': []}),
            ('capability_overlap', {'capabilities': [{'id': 'a.b'}]}),
            ('legacy_import_audit', {'files': {}}),
            ('legacy_import_audit', {'files': {'a.py': 3}}),
            ('adapter_reality', {'registry': {}}),
            ('capability_passport', {'available': {'ffmpeg': True}}),
            ('approval_lifecycle', {'item': {'id': 'x', 'status': 'proposed'}}),
            ('approval_lifecycle', {'steps': [{'to': 'approved', 'evidence': {}}]}),
            ('snapshot_restore', {'action': 'restore'}),
            ('snapshot_restore', {'action': 'snapshot'}),
            ('snapshot_restore', {'action': 'diff', 'manifest': {}}),
            ('snapshot_restore', {'action': 'snapshot', 'files': {'../x': 'a'}}),
            ('completion_matrix', {'requirements': []}),
            ('completion_matrix', {'requirements': [{'test': 'x'}]}),
            ('capability_overlap', {'capabilities': [
                {'id': 'a', 'effect': 'read', 'inputs': {'p': {1: 'a', 'b': 2}}}]}),
        ]
        for op, params in cases:
            with self.assertRaises(ValueError, msg=f'{op} {params}'):
                g.run(op, params)

    def test_module_hygiene(self):
        tree = ast.parse(inspect.getsource(g))
        banned = {'os', 'subprocess', 'socket', 'urllib', 'http', 'shutil', 'sqlite3', 'ctypes'}
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name.split('.')[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or '').split('.')[0])
            elif isinstance(node, ast.Call):
                self.assertNotIn(getattr(node.func, 'id', None),
                                 ('open', 'exec', 'eval', 'compile', 'print', '__import__'))
        self.assertFalse(imported & banned)
        stdlib_only = {'__future__', 'ast', 'datetime', 'difflib', 'hashlib', 'json', 're',
                       'unicodedata'}
        self.assertLessEqual(imported, stdlib_only)

    def test_module_itself_passes_its_own_legacy_audit(self):
        res = R('legacy_import_audit', files={'governance_v22.py': inspect.getsource(g)})
        self.assertTrue(res['passed'], res['findings'])


class SkillContractTests(unittest.TestCase):  # 01.01
    def test_valid_contract_accepted(self):
        res = R('skill_contract')
        self.assertTrue(res['accepted'], res['reasons'])
        self.assertEqual(res['id'], 'video.verify')

    def test_legacy_engine_contract_rejected(self):
        bad = dict(g._EXAMPLE_CONTRACT, dependencies=['ffprobe', 'BlackDragon-engine'],
                   entry_point='golden_dragon.engines.render:run')
        res = R('skill_contract', contract=bad)
        self.assertFalse(res['accepted'])
        fields = {h['field'] for h in res['legacy_references']}
        self.assertEqual(fields, {'dependencies[1]', 'entry_point'})

    def test_structural_errors_and_custom_names(self):
        res = R('skill_contract', contract={'id': 'Bad Id', 'effect': 'delete',
                                            'inputs': {'x': 'banana'}, 'outputs': {},
                                            'dependencies': [], 'version': '1.0'})
        self.assertFalse(res['accepted'])
        self.assertGreaterEqual(len(res['reasons']), 5)
        ok = dict(g._EXAMPLE_CONTRACT, dependencies=['standard.py', 'dragonfly'])
        self.assertFalse(R('skill_contract', contract=ok)['accepted'])  # dragonfly matches 'dragon'
        self.assertTrue(R('skill_contract', contract=ok, legacy_names=['kosif'])['accepted'])
        no_rd = dict(g._EXAMPLE_CONTRACT, dependencies=['standard.py'])
        self.assertTrue(R('skill_contract', contract=no_rd)['accepted'])


class ProvenanceTests(unittest.TestCase):  # 01.02
    def test_build_and_verify(self):
        res = R('provenance_card')
        card = res['card']
        self.assertTrue(res['verification']['valid'])
        self.assertEqual(card['sha256'],
                         hashlib.sha256(res['canonical_json'].encode('utf-8')).hexdigest())
        self.assertTrue(R('provenance_card', action='verify', card=card)['valid'])

    def test_altering_one_field_breaks_verification(self):
        card = R('provenance_card')['card']
        for key in ('idea', 'source', 'url_or_path', 'author'):
            bad = dict(card, **{key: card[key] + ' '})
            res = R('provenance_card', action='verify', card=bad)
            self.assertFalse(res['valid'], key)
        res = R('provenance_card', action='verify', card=dict(card, date='2026-11-22'))
        self.assertFalse(res['valid'])

    def test_unknown_licence_rejected(self):
        card = R('provenance_card')['card']
        fields = {k: card[k] for k in g._CARD_FIELDS}
        fields['licence'] = 'Totally-Free'
        forged = dict(fields, sha256=hashlib.sha256(g._canonical(fields).encode()).hexdigest())
        res = R('provenance_card', action='verify', card=forged)
        self.assertFalse(res['valid'])
        self.assertTrue(any('licence' in r for r in res['reasons']))
        with self.assertRaises(ValueError):
            R('provenance_card', **fields)
        ok = R('provenance_card', allowed_licences=['Totally-Free'], **fields)
        self.assertTrue(ok['verification']['valid'])
        with self.assertRaises(ValueError):
            R('provenance_card', **dict(fields, licence='MIT', date='2026-02-30'))


class BehaviourCompareTests(unittest.TestCase):  # 01.03
    def test_example_matches_and_is_not_copy(self):
        res = R('behaviour_compare')
        self.assertTrue(res['behaviour_ok'])
        self.assertFalse(res['similarity']['copy_risk'])
        self.assertEqual(res['verdict'], 'accepted')

    def test_mismatch_reported_per_case(self):
        res = R('behaviour_compare', cases=[
            {'input': 1, 'expected': 1.0, 'observed': 1.1, 'tolerance': 0.01},
            {'input': 2, 'expected': [1, 2], 'observed': [1, 2]},
            {'input': 3, 'expected': True, 'observed': 1}])
        self.assertEqual([c['passed'] for c in res['cases']], [False, True, False])
        self.assertEqual(res['verdict'], 'rejected_behaviour_mismatch')

    def test_copied_text_flagged_even_if_behaviour_passes(self):
        ref = g._EXAMPLE_REFERENCE + 'def area(r):\n    return 3.14159 * r * r\n'
        copied = ref.replace('    ', '\t') + '\n\n'
        res = R('behaviour_compare', cases=g._EXAMPLE_CASES, new_code=copied,
                reference_code=ref)
        self.assertTrue(res['behaviour_ok'])
        self.assertTrue(res['similarity']['copy_risk'])
        self.assertGreaterEqual(res['similarity']['score'], 0.8)
        self.assertEqual(res['verdict'], 'rejected_copy_risk')


class CapabilityOverlapTests(unittest.TestCase):  # 01.04
    def test_merge_candidate_and_conflict(self):
        res = R('capability_overlap')
        merges = {tuple(m['ids']) for m in res['merge_candidates'] if m['kind'] == 'same_name'}
        self.assertIn(('video.verify', 'Video-Verify'), merges)
        self.assertIn(('تحقق_الفيديو', 'تَحقّق.الفيدیو'), merges)
        conflicts = [c for c in res['conflicts'] if c['kind'] == 'effect_mismatch']
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]['effects'], {'media.export': 'write', 'MEDIA_EXPORT': 'read'})

    def test_signature_mismatch_and_same_contract(self):
        res = R('capability_overlap', capabilities=[
            {'id': 'a.x', 'effect': 'read', 'inputs': {'p': 'string'}, 'outputs': {'o': 'any'}},
            {'id': 'A_X', 'effect': 'read', 'inputs': {'q': 'string'}, 'outputs': {'o': 'any'}},
            {'id': 'b.y', 'effect': 'read', 'inputs': {'q': 'string'}, 'outputs': {'o': 'any'}}])
        self.assertEqual([c['kind'] for c in res['conflicts']], ['signature_mismatch'])
        self.assertEqual(res['merge_candidates'][0]['kind'], 'same_contract')
        self.assertEqual(sorted(res['merge_candidates'][0]['ids']), ['A_X', 'b.y'])
        self.assertEqual(g.normalise_name('  Video__Verify '), 'video.verify')


class LegacyImportAuditTests(unittest.TestCase):  # 01.05
    def test_flags_legacy_imports_and_passes_clean_code(self):
        files = {'a.py': 'import black_dragon\n',
                 'b.py': "import importlib\nm = importlib.import_module('golden_dragon.x')\n",
                 'c.py': 'from Alloy.fusion import run\n__import__("kosif_tools")\n',
                 'd.py': "import subprocess\nsubprocess.Popen(['python', 'C:/x/rd.py', 'plan'])\n",
                 'clean.py': 'import json\nimport standard_lib\nx = "dragon in a comment string"\n'}
        res = R('legacy_import_audit', files=files)
        self.assertFalse(res['passed'])
        self.assertEqual(res['flagged_files'], ['a.py', 'b.py', 'c.py', 'd.py'])
        self.assertEqual(res['clean_files'], ['clean.py'])
        kinds = {(f['file'], f['kind']) for f in res['findings']}
        self.assertIn(('a.py', 'import'), kinds)
        self.assertIn(('b.py', 'dynamic_import'), kinds)
        self.assertIn(('d.py', 'command_string'), kinds)
        self.assertTrue(R('legacy_import_audit', files={'ok.py': files['clean.py']})['passed'])

    def test_unparseable_and_dynamic_warning(self):
        res = R('legacy_import_audit', files={'bad.py': 'def (:\n',
                                              'dyn.py': 'import importlib\nn = "x"\n'
                                                        'importlib.import_module(n)\n'})
        self.assertFalse(res['passed'])
        self.assertEqual(res['unparsed_files'], ['bad.py'])
        self.assertTrue(any('dynamic' in w for w in res['warnings']))


class AdapterRealityTests(unittest.TestCase):  # 01.06
    def test_classification(self):
        res = R('adapter_reality')
        cls = {a['id']: a['class'] for a in res['adapters']}
        self.assertEqual(cls, {'qa.trace': 'executable_with_evidence',
                               'fusion.render': 'executable_no_evidence',
                               'media.colour_grade': 'description_only'})

    def test_documented_without_handler_is_description_only(self):
        res = R('adapter_reality',
                registry={'x.y': ['Very well documented adapter', 'read', 'builtin'],
                          'z.w': 'desc'},
                evidence={'z.w': {'handler_present': False, 'sample_output': {'a': 1},
                                  'test_file': 'test_z.py'},
                          'ghost': {'handler_present': True}})
        cls = {a['id']: a['class'] for a in res['adapters']}
        self.assertEqual(cls, {'x.y': 'description_only', 'z.w': 'description_only'})
        self.assertTrue(res['adapters'][0]['documented'])
        self.assertEqual(res['unregistered_evidence'], ['ghost'])


class PassportTests(unittest.TestCase):  # 01.07
    def test_statuses(self):
        res = R('capability_passport')
        by = {p['id']: p for p in res['passports']}
        self.assertEqual(by['qa.trace']['status'], 'executable')
        self.assertEqual(by['media.iphone_export']['status'], 'blocked')
        self.assertIn('ffmpeg', by['media.iphone_export']['reason'])
        self.assertEqual(by['media.iphone_export']['missing_dependencies'], ['ffmpeg'])
        self.assertTrue(by['media.iphone_export']['permissions']['needs_explicit_approval'])
        self.assertEqual(by['media.colour_grade']['status'], 'description_only')

    def test_unknown_dependency_blocks(self):
        res = R('capability_passport', capabilities=[
            {'id': 'a', 'effect': 'read', 'dependencies': ['cairosvg'], 'handler_present': True}])
        p = res['passports'][0]
        self.assertEqual(p['status'], 'blocked')
        self.assertIn('cairosvg', p['reason'])
        res = R('capability_passport', available={'cairosvg': True}, capabilities=[
            {'id': 'a', 'effect': 'read', 'dependencies': 'cairosvg', 'handler_present': True}])
        self.assertEqual(res['passports'][0]['status'], 'executable')


class ApprovalLifecycleTests(unittest.TestCase):  # 01.08
    def test_example_stops_at_missing_e2e_evidence(self):
        res = R('approval_lifecycle')
        self.assertEqual(res['final_status'], 'unit_tested')
        self.assertEqual(res['steps'][-1]['outcome'], 'rejected')

    def test_full_promotion(self):
        steps = copy.deepcopy(g._EXAMPLE_STEPS)
        steps[-1]['evidence'] = {'artifact_sha256': 'a' * 64}
        res = R('approval_lifecycle', item={'id': 'x', 'status': 'proposed'}, steps=steps)
        self.assertTrue(res['all_promoted'])
        self.assertEqual(res['final_status'], 'e2e_verified')
        self.assertEqual(len(res['history']), 4)

    def test_promotion_without_evidence_rejected(self):
        res = R('approval_lifecycle', item={'id': 'x', 'status': 'proposed'},
                steps=[{'to': 'approved', 'evidence': {}},
                       {'to': 'coded', 'evidence': {'file': 'a.py', 'symbol': 'f'}}])
        self.assertEqual(res['final_status'], 'proposed')
        self.assertEqual([s['outcome'] for s in res['steps']], ['rejected', 'not_attempted'])
        wrong_kind = R('approval_lifecycle', item={'id': 'x', 'status': 'coded'},
                       steps=[{'to': 'unit_tested', 'evidence': {'file': 'a.py', 'symbol': 'f'}}])
        self.assertEqual(wrong_kind['final_status'], 'coded')
        failing = R('approval_lifecycle', item={'id': 'x', 'status': 'coded'},
                    steps=[{'to': 'unit_tested', 'evidence': {'test_file': 't.py', 'passing': 3,
                                                              'failing': 1}}])
        self.assertEqual(failing['final_status'], 'coded')

    def test_skipping_a_level_rejected(self):
        res = R('approval_lifecycle', item={'id': 'x', 'status': 'approved'},
                steps=[{'to': 'unit_tested', 'evidence': {'test_file': 't.py', 'passing': 3}}])
        self.assertEqual(res['final_status'], 'approved')
        self.assertIn('skip', res['steps'][0]['reason'])
        back = R('approval_lifecycle', item={'id': 'x', 'status': 'coded'},
                 steps=[{'to': 'approved', 'evidence': {'owner_quote': 'yes ok', 'date': '2026-01-01'}}])
        self.assertEqual(back['steps'][0]['outcome'], 'rejected')


class SnapshotTests(unittest.TestCase):  # 01.09
    def test_demo(self):
        res = R('snapshot_restore')
        self.assertTrue(res['restored_equals_original'])
        self.assertEqual(res['diff']['changed'], ['rose.py'])

    def test_restore_after_modification_and_diff(self):
        original = {'a.txt': 'alpha\r\n', 'dir/b.txt': 'بيتا\n', 'c.txt': 'same'}
        snap = R('snapshot_restore', action='snapshot', files=original)
        edited = dict(original, **{'a.txt': 'ALPHA\n', 'new.txt': 'n'})
        del edited['dir/b.txt']
        snap2 = R('snapshot_restore', action='snapshot', files=edited)
        store = {**snap['store'], **snap2['store']}
        back = R('snapshot_restore', action='restore', manifest=snap['manifest'], store=store)
        self.assertEqual({p: t.encode('utf-8') for p, t in back['files'].items()},
                         {p: t.encode('utf-8') for p, t in original.items()})
        diff = R('snapshot_restore', action='diff', manifest=snap['manifest'],
                 other=snap2['manifest'])
        self.assertEqual(diff['changed'], ['a.txt'])
        self.assertEqual(diff['added'], ['new.txt'])
        self.assertEqual(diff['removed'], ['dir/b.txt'])
        self.assertEqual(diff['unchanged_count'], 1)

    def test_corruption_detected(self):
        snap = R('snapshot_restore', action='snapshot', files={'a.txt': 'x'})
        bad_store = {k: v + '!' for k, v in snap['store'].items()}
        with self.assertRaises(ValueError):
            R('snapshot_restore', action='restore', manifest=snap['manifest'], store=bad_store)
        tampered = copy.deepcopy(snap['manifest'])
        tampered['files']['a.txt']['sha256'] = 'b' * 64
        with self.assertRaises(ValueError):
            R('snapshot_restore', action='restore', manifest=tampered, store=snap['store'])


class CompletionMatrixTests(unittest.TestCase):  # 01.10
    def test_requirement_without_test_not_complete(self):
        res = R('completion_matrix')
        self.assertEqual(res['complete'], 1)
        self.assertAlmostEqual(res['completion_pct'], 33.33)
        by = {r['id']: r for r in res['requirements']}
        self.assertEqual(by['R2']['first_missing'], 'test')
        self.assertEqual(by['R3']['missing_links'], ['implementation', 'test', 'evidence'])

    def test_existing_paths_detects_dangling(self):
        reqs = [{'id': 'R1', 'implementation': 'a.py::f', 'test': 'test_a.py::t',
                 'evidence': 'ok'}]
        self.assertEqual(R('completion_matrix', requirements=reqs)['completion_pct'], 100.0)
        res = R('completion_matrix', requirements=reqs, existing_paths=['a.py'])
        self.assertEqual(res['complete'], 0)
        self.assertEqual(res['requirements'][0]['dangling_refs'],
                         [{'link': 'test', 'ref': 'test_a.py::t'}])


if __name__ == '__main__':
    unittest.main()
