"""Tests for libraries_v24 (stdlib unittest)."""
import ast
import inspect
import json
import unittest

import libraries_v24 as L

ALL_CHECKS = {c: True for c in L.SHAPING_CHECKS}


class TestInterface(unittest.TestCase):
    def test_topics_and_ops(self):
        self.assertEqual(len(L.TOPICS), 10)
        self.assertEqual(set(L.TOPICS.values()), set(L.OPS))
        self.assertEqual(set(L.TOPICS), set(L.TOPIC_NAMES_AR))

    def test_run_all_defaults_json(self):
        for op in L.OPS:
            out = L.run(op, {})
            self.assertEqual(set(out), {'op', 'result', 'assumptions', 'limits'})
            self.assertEqual(out['op'], op)
            self.assertTrue(out['assumptions'] and out['limits'])
            json.dumps(out, allow_nan=False)
            self.assertEqual(out, L.run(op))  # deterministic

    def test_run_rejects_bad_input(self):
        for bad in [('nope', {}), (1, {}), ('lockfile', []), ('lockfile', {1: 2}),
                    ('lockfile', {'bogus': 1}), ('licence_check', {'expression': 5}),
                    ('licence_check', {'usage': 'cloud'}), ('licence_check', {'commercial': 1}),
                    ('licence_check', {'expression': 'MIT AND'}),
                    ('licence_check', {'expression': '(MIT OR ISC'}),
                    ('licence_check', {'expression': 'MIT $ ISC'}),
                    ('tool_benchmark', {'tools': []}),
                    ('tool_benchmark', {'tools': [{'name': 'a', 'wall_time_s': True}]}),
                    ('tool_benchmark', {'tools': [{'name': 'a', 'wall_time_s': 0}]}),
                    ('tool_benchmark', {'tools': [{'name': 'a', 'extra': 1}]}),
                    ('tool_benchmark', {'tools': [{'name': 'a'}, {'name': 'A'}]}),
                    ('webgl_eval', {'environment': {'webgl2': 'yes'}}),
                    ('audio_lib_eval', {'reference': {}}),
                    ('audio_lib_eval', {'reference': {'beats': [float('nan')]}}),
                    ('shot_detect_compare', {'tolerance_s': 0}),
                    ('shot_detect_compare', {'tools': [{'name': 'x'}]}),
                    ('cv_lib_eval', {'targets': [{'os': 'linux'}]}),
                    ('arabic_shaping_eval', {'stacks': [{'name': 'x', 'results': {'kerning': True}}]}),
                    ('lockfile', {'text': 'x' * (L.MAX_TEXT + 1)}),
                    ('lockfile', {'require_hashes': 'no'}),
                    ('lockfile', {'text': 'a==1', 'licences': ['MIT']})]:
            with self.assertRaises(ValueError, msg=str(bad)):
                L.run(*bad)

    def test_direct_call_unknown_kw(self):
        with self.assertRaises(ValueError):
            L.licence_check(foo=1)

    def test_too_many_params(self):
        with self.assertRaises(ValueError):
            L.run('lockfile', {f'k{i}': i for i in range(L.MAX_PARAMS + 1)})

    def test_forbidden_imports_and_calls(self):
        tree = ast.parse(inspect.getsource(L))
        banned_mod = {'os', 'subprocess', 'socket', 'urllib', 'http', 'shutil', 'sqlite3', 'ctypes'}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    self.assertNotIn(a.name.split('.')[0], banned_mod)
            elif isinstance(node, ast.ImportFrom):
                self.assertNotIn((node.module or '').split('.')[0], banned_mod)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {'open', 'exec', 'eval', 'print', '__import__'})


class TestLicenceCheck(unittest.TestCase):
    def test_or_allows_choosing_mit(self):
        r = L.run('licence_check', {'expression': 'MIT OR GPL-3.0'})['result']
        self.assertEqual(r['verdict'], 'allowed')
        self.assertEqual(r['chosen'], ['MIT'])
        self.assertEqual(r['chosen_class'], 'permissive')
        self.assertFalse(r['source_disclosure_required'])
        self.assertTrue(r['attribution_required'])

    def test_agpl_saas_source_disclosure(self):
        r = L.run('licence_check', {'expression': 'AGPL-3.0', 'usage': 'saas'})['result']
        self.assertTrue(r['source_disclosure_required'])
        self.assertEqual(r['chosen_class'], 'strong_copyleft')
        g = L.run('licence_check', {'expression': 'GPL-3.0-only', 'usage': 'saas'})['result']
        self.assertFalse(g['source_disclosure_required'])

    def test_unknown_id_rejected(self):
        r = L.run('licence_check', {'expression': 'Foo-License-9'})['result']
        self.assertEqual(r['verdict'], 'rejected')
        self.assertEqual(r['unknown_ids'], ['Foo-License-9'])
        # a known alternative rescues an OR
        r2 = L.run('licence_check', {'expression': 'Foo-License-9 OR Apache-2.0'})['result']
        self.assertEqual((r2['verdict'], r2['chosen']), ('allowed', ['Apache-2.0']))
        # but AND with unknown is rejected
        r3 = L.run('licence_check', {'expression': 'MIT AND Foo-License-9'})['result']
        self.assertEqual(r3['verdict'], 'rejected')

    def test_parentheses_and_with(self):
        r = L.run('licence_check', {'expression': '(MIT OR BSD-3-Clause) AND (LGPL-2.1-or-later OR GPL-2.0-only)'})
        res = r['result']
        self.assertEqual(len(res['alternatives']), 4)
        self.assertEqual(res['chosen'], ['MIT', 'LGPL-2.1-or-later'])
        self.assertTrue(res['source_disclosure_required'])
        w = L.run('licence_check', {'expression': 'GPL-2.0-only WITH Classpath-exception-2.0'})['result']
        self.assertEqual(w['verdict'], 'needs_review')

    def test_internal_and_noncommercial_and_static(self):
        r = L.run('licence_check', {'expression': 'GPL-3.0-only', 'usage': 'internal'})['result']
        self.assertFalse(r['source_disclosure_required'])
        nc = L.run('licence_check', {'expression': 'CC-BY-NC-4.0'})['result']
        self.assertEqual(nc['verdict'], 'rejected')
        nc2 = L.run('licence_check', {'expression': 'CC-BY-NC-4.0', 'commercial': False})['result']
        self.assertEqual(nc2['verdict'], 'allowed')
        st = L.run('licence_check', {'expression': 'LGPL-3.0-only', 'linking': 'static'})['result']
        self.assertTrue(any('relink' in d for d in st['duties']))
        lr = L.run('licence_check', {'expression': 'LicenseRef-Custom'})['result']
        self.assertEqual(lr['verdict'], 'needs_review')

    def test_case_insensitive_and_zero_bsd(self):
        r = L.run('licence_check', {'expression': 'mit or 0bsd'})['result']
        self.assertEqual(r['chosen'], ['0BSD'])
        self.assertFalse(r['attribution_required'])


class TestToolBenchmark(unittest.TestCase):
    def test_missing_feature_cannot_win_and_efficiency(self):
        out = L.run('tool_benchmark', {})['result']
        rows = {r['name']: r for r in out['tools']}
        self.assertFalse(rows['tool_b']['eligible'])
        self.assertIsNone(rows['tool_b']['rank'])
        self.assertNotIn('tool_b', out['ranking'])
        self.assertAlmostEqual(rows['ffmpeg']['efficiency_quality_per_s'], 92.0 / 4.0)
        self.assertAlmostEqual(rows['tool_c']['efficiency_quality_per_s'], 93.0 / 8.0)
        self.assertEqual(out['winner'], 'ffmpeg')
        self.assertEqual(out['missing_measurements']['tool_d'], ['wall_time_s'])
        self.assertIsNone(rows['tool_d']['rank'])

    def test_rank_by_quality_and_unmeasured_feature(self):
        tools = [{'name': 'a', 'features': {'cut': True}, 'wall_time_s': 1, 'quality_score': 5},
                 {'name': 'b', 'features': {'cut': None}, 'wall_time_s': 1, 'quality_score': 9}]
        out = L.run('tool_benchmark', {'tools': tools, 'required_features': ['cut'],
                                       'rank_by': 'quality'})['result']
        self.assertEqual(out['winner'], 'a')


class TestVector(unittest.TestCase):
    def test_arabic_fail_not_recommended(self):
        out = L.run('vector_lib_eval', {})['result']
        self.assertIn('svg_option_B', out['not_recommended'])
        self.assertIn('svg_option_C', out['not_recommended'])  # untested
        self.assertEqual(out['recommended'], ['svg_option_A'])
        opts = [{'name': 'x', 'licence': 'MIT', 'checks': {'renders_basic_shapes': True,
                                                          'arabic_text_shaped': False}}]
        out2 = L.run('vector_lib_eval', {'options': opts, 'required_checks': ['renders_basic_shapes']})
        self.assertEqual(out2['result']['recommended'], [])
        self.assertIn('arabic_text_shaped', out2['result']['required_checks'])


class TestWebAnim(unittest.TestCase):
    def test_custom_licence_needs_review(self):
        out = L.run('web_anim_eval', {})['result']
        rows = {r['name']: r for r in out['libraries']}
        self.assertEqual(rows['gsap']['status'], 'needs_review')
        self.assertNotEqual(rows['gsap']['licence_class'], 'permissive')
        self.assertEqual(rows['anime.js']['status'], 'ok')
        self.assertEqual(rows['example_heavy_lib']['status'], 'rejected')
        libs = [{'name': 'z', 'licence': 'Proprietary-ish', 'needs_browser': False, 'bundle_kb': 1}]
        r = L.run('web_anim_eval', {'libraries': libs})['result']['libraries'][0]
        self.assertEqual((r['status'], r['licence_class']), ('needs_review', 'custom_needs_review'))
        # gsap claimed as MIT still needs review (no confident reference id)
        g = L.run('web_anim_eval', {'libraries': [{'name': 'GSAP', 'licence': 'MIT',
                                                   'needs_browser': True, 'bundle_kb': 50}]})
        self.assertEqual(g['result']['libraries'][0]['status'], 'needs_review')


class TestWebGL(unittest.TestCase):
    def test_webgl2_scene_on_webgl1_infeasible(self):
        out = L.run('webgl_eval', {})['result']
        self.assertIn('volumetric_title', out['infeasible'])
        self.assertIn('logo_spin', out['feasible'])
        self.assertIn('particle_storm', out['infeasible'])  # 60/3 = 20 fps < 60
        self.assertEqual(out['library']['licence'], 'MIT')

    def test_unknown_when_fact_missing(self):
        out = L.run('webgl_eval', {'environment': {'webgl1': True},
                                   'scenes': [{'name': 's', 'needs_webgl2': True}]})['result']
        self.assertEqual(out['unknown'], ['s'])


class TestAudio(unittest.TestCase):
    def test_f_measure_hand_example(self):
        out = L.run('audio_lib_eval', {'reference': {'beats': [1, 2, 3, 4]},
                                       'libraries': [{'name': 'a', 'beats': [1.02, 2.5, 3.0]}]})
        b = out['result']['libraries'][0]['tasks']['beats']
        self.assertEqual((b['tp'], b['fp'], b['fn']), (2, 1, 2))
        self.assertAlmostEqual(b['precision'], 2 / 3, places=6)
        self.assertAlmostEqual(b['recall'], 0.5)
        self.assertAlmostEqual(b['f_measure'], 4 / 7, places=6)

    def test_silence_boundaries_and_not_measured(self):
        out = L.run('audio_lib_eval', {})['result']
        rows = {r['name']: r for r in out['libraries']}
        s = rows['audio_lib_A']['tasks']['silence']
        self.assertEqual((s['tp'], s['fp'], s['fn']), (1, 1, 1))  # 5.05 hit, 6.3 out of +-0.1
        self.assertEqual(rows['audio_lib_B']['tasks']['silence']['status'], 'not_measured')
        self.assertEqual(out['best_per_task']['beats'], 'audio_lib_B')


class TestCV(unittest.TestCase):
    def test_missing_wheel_reported(self):
        out = L.run('cv_lib_eval', {})['result']
        missing = {(u['os'], u['python'], u['arch']) for u in out['unsupported']}
        self.assertEqual(missing, {('linux', '3.12', 'aarch64'), ('macos', '3.13', 'arm64')})
        self.assertFalse(out['all_supported'])
        self.assertEqual(out['packages'][0]['licence']['expression'], 'Apache-2.0')

    def test_old_opencv_bsd(self):
        pk = [{'name': 'opencv', 'version': '4.4.0', 'wheels': []}]
        out = L.run('cv_lib_eval', {'packages': pk,
                                    'targets': [{'os': 'linux', 'python': '3.8', 'arch': 'x86_64'}]})
        self.assertEqual(out['result']['packages'][0]['licence']['expression'], 'BSD-3-Clause')


class TestShots(unittest.TestCase):
    def test_one_fp_one_miss(self):
        out = L.run('shot_detect_compare', {})['result']
        a = {r['name']: r for r in out['tools']}['detector_A']
        self.assertEqual((a['tp'], a['fp'], a['fn']), (2, 1, 1))
        self.assertAlmostEqual(a['precision'], 2 / 3, places=6)
        self.assertAlmostEqual(a['recall'], 2 / 3, places=6)
        self.assertEqual(a['false_positives'], [5.0])
        self.assertEqual(a['misses'], [3.0])
        self.assertEqual(out['best'], 'detector_B')


class TestLockfile(unittest.TestCase):
    def test_default_fails(self):
        r = L.run('lockfile', {})['result']
        self.assertEqual(r['verdict'], 'not_reproducible')
        self.assertEqual(r['conflicts'][0]['name'], 'pillow')
        self.assertIn('numpy', ' '.join(r['fail_reasons']))
        self.assertEqual(r['licence_summary']['counts'], {'permissive': 3})

    def test_good_and_bad(self):
        h = 'b' * 64
        good = f'Foo_Bar==1.0 --hash=sha256:{h}\nbaz==2.0 \\\n  --hash=sha256:{h}\n'
        r = L.run('lockfile', {'text': good, 'licences': {'foo-bar': 'MIT', 'baz': 'GPL-3.0-only'}})['result']
        self.assertEqual(r['verdict'], 'reproducible', r['fail_reasons'])
        self.assertEqual(r['licence_summary']['counts'], {'permissive': 1, 'strong_copyleft': 1})
        nohash = L.run('lockfile', {'text': 'a==1\nb==2\n'})['result']
        self.assertEqual(nohash['verdict'], 'not_reproducible')
        ok = L.run('lockfile', {'text': 'a==1\nb==2\n', 'require_hashes': False})['result']
        self.assertEqual(ok['verdict'], 'reproducible')
        self.assertEqual(ok['licence_summary']['counts'], {'not_supplied': 2})
        un = L.run('lockfile', {'text': 'a>=1', 'require_hashes': False})['result']
        self.assertEqual(un['verdict'], 'not_reproducible')
        dup = L.run('lockfile', {'text': 'a==1\nA==1\n', 'require_hashes': False})['result']
        self.assertEqual(dup['verdict'], 'reproducible')
        self.assertEqual(len(dup['duplicates']), 1)
        marker = 'a==1 ; python_version<"3.12"\na==2 ; python_version>="3.12"\n'
        mk = L.run('lockfile', {'text': marker, 'require_hashes': False})['result']
        self.assertEqual(mk['conflicts'], [])
        ed = L.run('lockfile', {'text': '-e .\na==1', 'require_hashes': False})['result']
        self.assertEqual(ed['verdict'], 'not_reproducible')


class TestArabicShaping(unittest.TestCase):
    def test_broken_lam_alef_fails(self):
        out = L.run('arabic_shaping_eval', {})['result']
        self.assertEqual(out['passed'], ['stack_A'])
        self.assertIn('stack_B', out['failed'])
        self.assertIn('stack_C', out['failed'])  # untested harakat
        b = {r['name']: r for r in out['stacks']}['stack_B']
        self.assertEqual(b['failed'], ['lam_alef_ligature'])
        one = L.run('arabic_shaping_eval', {'stacks': [
            {'name': 's', 'licence': 'MIT', 'results': dict(ALL_CHECKS, lam_alef_ligature=False)}]})
        self.assertEqual(one['result']['passed'], [])


if __name__ == '__main__':
    unittest.main()
