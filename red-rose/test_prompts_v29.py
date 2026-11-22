"""prompts_v28 (prompt.prepare): every op, its gates and its example flags. Pure, offline."""
import ast
import inspect
import json
import socket
import unittest
from decimal import Decimal
from unittest import mock

import prompts_v28 as P


def _no_network(*a, **k):
    raise AssertionError('network access attempted')


class PromptCase(unittest.TestCase):
    def setUp(self):
        for target, attr in ((socket.socket, 'connect'), (socket, 'create_connection')):
            p = mock.patch.object(target, attr, _no_network)
            p.start()
            self.addCleanup(p.stop)


class TestInterface(PromptCase):
    def test_every_op_runs_with_defaults_and_flags_example(self):
        for op in P.OPS:
            out = P.run(op, {})
            self.assertEqual(set(out), {'op', 'result', 'assumptions', 'limits'})
            json.dumps(out, allow_nan=False)
            self.assertEqual(P.run(op, {}), out)                          # deterministic
            self.assertTrue(any('no money spent' in l for l in out['limits']), op)
            if op != 'style_library':
                self.assertIs(out['result']['example_data'], True, op)
                self.assertEqual(out['result']['input'], 'built_in_example', op)

    def test_dispatcher_validation(self):
        for bad in (('nope', {}), ('image_prompt', []), ('image_prompt', {'zzz': 1}),
                    ('image_prompt', {str(i): 1 for i in range(P.MAX_PARAMS + 1)})):
            with self.assertRaises(ValueError):
                P.run(*bad)

    def test_module_is_pure(self):
        tree = ast.parse(inspect.getsource(P))
        banned = {'os', 'subprocess', 'socket', 'urllib', 'http', 'shutil', 'sqlite3', 'requests'}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    self.assertNotIn(a.name.split('.')[0], banned)
            elif isinstance(node, ast.ImportFrom):
                self.assertNotIn((node.module or '').split('.')[0], banned)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {'open', 'exec', 'eval', 'print'})
        self.assertFalse(any('approve' in op for op in P.OPS))


class TestBlocklist(PromptCase):
    def status(self, **kw):
        return P.run('image_prompt', kw)['result']['status']

    def test_names_refused_in_every_field_and_spelling(self):
        for text in ('Spider-Man poster', 'MICKEY  mouse!', 'ghibli-style forest', 'بالديزني',
                     'إبن ميازاكى', 'Ghíbli', 'in the style of Greg Rutkowski'):
            with self.subTest(text=text):
                self.assertEqual(self.status(subject=text), 'refused')
        self.assertEqual(self.status(subject='cat', mood='very pixar mood'), 'refused')
        self.assertEqual(self.status(subject='cat', style='studio ghibli look'), 'refused')
        self.assertEqual(self.status(subject='cat', negative=['no batman']), 'refused')
        self.assertEqual(self.status(subject='disneyland trip'), 'ready')     # word boundary

    def test_refusal_payload(self):
        r = P.run('image_prompt', {'subject': 'Pikachu on a beach'})['result']
        self.assertIsNone(r['prompt'])
        self.assertEqual(r['blocked_terms'], ['pikachu'])
        self.assertTrue(r['recommended_styles'])
        self.assertTrue(all(s['id'] in P.STYLE_INDEX for s in r['recommended_styles']))
        self.assertIn('محمي', r['message_ar'])
        r = P.run('image_prompt', {'subject': 'Amr Diab portrait'})['result']
        self.assertEqual([s['id'] for s in r['recommended_styles']], list(P.FALLBACK_STYLES))

    def test_caller_can_only_add_terms(self):
        self.assertEqual(self.status(subject='hello kitty mug', blocklist=['Hello Kitty']), 'refused')
        self.assertEqual(self.status(subject='hello kitty mug'), 'ready')
        self.assertEqual(self.status(subject='disney', blocklist=[]), 'refused')
        with self.assertRaises(ValueError):
            self.status(subject='x', blocklist='disney')

    def test_style_library_is_clean(self):
        r = P.run('style_library', {})['result']
        self.assertEqual(r['count_total'], 40)
        self.assertTrue(r['blocklist_clean'])
        self.assertEqual(len({s['id'] for s in r['styles']}), 40)
        r = P.run('style_library', {'category': '3d'})['result']
        self.assertTrue(r['count'] >= 1 and all(s['category'] == '3d' for s in r['styles']))
        self.assertGreaterEqual(P.run('style_library', {'query': 'ضوء'})['result']['count'], 1)
        self.assertEqual(P.run('style_library', {'query': 'zzzz'})['result']['count'], 0)
        with self.assertRaises(ValueError):
            P.run('style_library', {'category': 'sculpture'})


class TestImageVideo(PromptCase):
    def test_image_owner_layers(self):
        r = P.run('image_prompt', {'subject': 'قطة', 'action': '', 'style': 'macro_detail',
                                   'aspect_ratio': '9:16', 'long_edge': 1920})['result']
        self.assertEqual(r['status'], 'ready')
        self.assertFalse(r['example_data'])
        self.assertNotIn('input', r)
        self.assertEqual(r['missing_layers'], ['action'])
        self.assertTrue(r['prompt'].startswith('قطة'))
        self.assertTrue(r['prompt'].endswith(P.STYLE_INDEX['macro_detail'][4]))
        self.assertEqual(r['size_hint_px'], [1088, 1920])
        self.assertEqual(r['style']['id'], 'macro_detail')
        for bad in ({'subject': ''}, {'subject': 'x', 'aspect_ratio': '7:3'}, {'subject': 'x', 'long_edge': 100},
                    {'subject': 'x\x01'}, {'subject': 'x' * 601}, {'subject': 'x', 'negative': 'a'}):
            with self.assertRaises(ValueError):
                P.run('image_prompt', bad)

    def test_video_continuity(self):
        sheets = {'hero': 'رجل ببدلة رمادي'}
        shots = [{'description': 'walks', 'camera_move': 'pan_left', 'duration_s': 8, 'motion_strength': 0.9,
                  'anchors': ['hero']},
                 {'description': 'stops', 'camera_move': 'pan_right', 'duration_s': 1.5}]
        r = P.run('video_prompt', {'shots': shots, 'character_sheets': sheets, 'fps': 24})['result']
        self.assertFalse(r['example_data'])
        self.assertEqual([s['frames'] for s in r['shots']], [192, 36])
        self.assertEqual(r['total_frames'], 228)
        self.assertIn('Keep identical [hero]: رجل ببدلة رمادي', r['shots'][0]['prompt'])
        checks = {c['check']: c['status'] for c in r['consistency_checklist']}
        self.assertEqual(checks['shot 1 motion vs length'], 'warn')
        self.assertEqual(checks['shots 1->2 camera direction'], 'warn')
        self.assertEqual(checks['shot 2 has continuity anchors'], 'warn')
        self.assertEqual(r['warnings'], 3)
        bad = [{'shots': []}, {'shots': [{'description': 'a', 'camera_move': 'spin', 'duration_s': 1}]},
               {'shots': [{'description': 'a', 'camera_move': 'static', 'duration_s': 1, 'anchors': ['x']}]},
               {'shots': [{'description': 'a', 'camera_move': 'static', 'duration_s': 70}]},
               {'shots': [{'description': 'a', 'camera_move': 'static', 'duration_s': 1, 'speed': 2}]},
               {'shots': [{'description': 'a', 'camera_move': 'static', 'duration_s': 50}] * 13},
               {'character_sheets': {'bad id!': 'x'}}]
        for params in bad:
            with self.assertRaises(ValueError):
                P.run('video_prompt', params)

    def test_video_blocklist_in_sheets(self):
        r = P.run('video_prompt', {'character_sheets': {'a': 'Batman costume'},
                                   'shots': [{'description': 'x', 'camera_move': 'static', 'duration_s': 2,
                                              'anchors': ['a']}]})['result']
        self.assertEqual(r['status'], 'refused')


class TestMusicVoice(PromptCase):
    def test_music_never_invents_lyrics(self):
        r = P.run('music_prompt', {})['result']
        self.assertEqual(r['status'], 'needs_owner_lyrics')
        self.assertIsNone(r['lyrics'])
        self.assertIn('مش هألّف', r['request_ar'])
        lyrics = 'يا ليل  يا عين\n\nآه يا ليل \n'
        r = P.run('music_prompt', {'genre': 'طرب', 'lyrics': lyrics, 'bpm': 90})['result']
        self.assertEqual(r['status'], 'ready')
        self.assertEqual(r['lyrics'], lyrics)                         # byte-for-byte
        self.assertEqual(r['lyrics_lines'], 2)
        self.assertEqual(r['lyrics_source'], 'owner')
        self.assertFalse(r['example_data'])
        self.assertEqual(r['seconds_per_bar'], round(4 * 60 / 90, 4))
        r = P.run('music_prompt', {'vocal': 'none', 'structure': ['intro', 'drop'], 'lyrics': 'x'})['result']
        self.assertEqual(r['status'], 'ready')
        self.assertIn('lyrics will be ignored', ' '.join(r['warnings']))
        r = P.run('music_prompt', {'structure': ['intro', 'outro']})['result']
        self.assertIn('no vocal section', ' '.join(r['warnings']))

    def test_music_artist_refused_with_advice(self):
        r = P.run('music_prompt', {'genre': 'pop like Taylor Swift'})['result']
        self.assertEqual(r['status'], 'refused')
        self.assertIn('advice_ar', r)
        self.assertEqual(r['recommended_styles'], [])
        r = P.run('music_prompt', {'lyrics': 'غني زي عمرو دياب'})['result']
        self.assertEqual(r['status'], 'refused')
        for bad in ({'bpm': 20}, {'vocal': 'robot'}, {'time_signature': '5/4'}, {'structure': ['solo']},
                    {'instruments': []}):
            with self.assertRaises(ValueError):
                P.run('music_prompt', bad)

    def test_voice_script_passthrough(self):
        script = ' أهلًا\tبيكم، النهارده 3 حاجات. OK? '
        r = P.run('voice_prompt', {'script': script, 'pace': 1.25, 'stability': 0.2})['result']
        self.assertEqual(r['status'], 'ready')
        self.assertEqual(r['script'], script)
        self.assertFalse(r['example_data'])
        joined = ' '.join(r['warnings'])
        for word in ('digits', 'mixed Arabic and Latin', 'stability'):
            self.assertIn(word, joined)
        ex = P.run('voice_prompt', {})['result']
        self.assertEqual((ex['status'], ex['script_source']), ('example_only', 'example_default'))
        for bad in ({'pace': 3}, {'speaker_boost': 1}, {'output_format': 'flac'}, {'script': ''}):
            with self.assertRaises(ValueError):
                P.run('voice_prompt', bad)


class TestCostApproval(PromptCase):
    TABLE = [{'provider': 'p1', 'model': 'img', 'unit': 'image', 'price_per_unit': '0.035', 'currency': 'usd',
              'source': 'owner quote', 'as_of': '2026-11-01'},
             {'provider': 'p1', 'model': 'vid', 'unit': 'second', 'price_per_unit': '0.1', 'currency': 'USD'},
             {'provider': 'p2', 'model': 'vid', 'unit': 'second', 'price_per_unit': '2', 'currency': 'EGP'},
             {'provider': 'p2', 'model': 'vid', 'unit': 'clip', 'price_per_unit': '30', 'currency': 'EGP'}]

    def test_decimal_totals_per_currency(self):
        jobs = [{'provider': 'p1', 'model': 'img', 'quantity': 3},
                {'provider': 'p1', 'model': 'vid', 'quantity': '0.3'},
                {'provider': 'p2', 'model': 'vid', 'unit': 'clip', 'quantity': 2}]
        r = P.run('cost_estimate', {'price_table': self.TABLE, 'jobs': jobs})['result']
        self.assertEqual(r['totals_by_currency'], {'EGP': '60', 'USD': '0.135'})
        self.assertEqual(r['totals_rounded_2dp'], {'EGP': '60.00', 'USD': '0.14'})
        self.assertFalse(r['single_currency'])
        self.assertFalse(r['example_data'])
        self.assertEqual(r['lines'][1]['subtotal'], '0.03')
        self.assertEqual(Decimal(r['lines'][0]['subtotal']), Decimal('0.105'))
        with self.assertRaisesRegex(ValueError, 'budget_currency is required'):
            P.run('cost_estimate', {'price_table': self.TABLE, 'jobs': jobs, 'budget_cap': '1'})
        r = P.run('cost_estimate', {'price_table': self.TABLE, 'jobs': jobs, 'budget_cap': '50',
                                    'budget_currency': 'egp'})['result']
        self.assertEqual(r['budget'], {'cap': '50', 'currency': 'EGP', 'total': '60', 'within_budget': False,
                                       'remaining': '-10'})

    def test_example_prices_flagged_even_with_owner_jobs(self):
        out = P.run('cost_estimate', {'jobs': [{'provider': 'example_provider', 'model': 'image-model-x',
                                                'quantity': 2}]})
        r = out['result']
        self.assertTrue(r['example_prices'])
        self.assertFalse(r['example_jobs'])
        self.assertTrue(r['example_data'])
        self.assertTrue(out['assumptions'][0].startswith('EXAMPLE price table'))

    def test_cost_errors(self):
        bad = [{'price_table': self.TABLE, 'jobs': [{'provider': 'p2', 'model': 'vid', 'quantity': 1}]},
               {'price_table': self.TABLE, 'jobs': [{'provider': 'zz', 'model': 'vid', 'quantity': 1}]},
               {'price_table': self.TABLE, 'jobs': [{'provider': 'p1', 'model': 'img', 'quantity': 0}]},
               {'price_table': self.TABLE + self.TABLE[:1], 'jobs': [{'provider': 'p1', 'model': 'img',
                                                                      'quantity': 1}]},
               {'price_table': [dict(self.TABLE[0], currency='$')]},
               {'budget_currency': 'USD'}]
        for params in bad:
            with self.assertRaises(ValueError):
                P.run('cost_estimate', params)

    def test_approval_request_cannot_be_approved_here(self):
        items = [{'label': 'cover', 'quantity': 4, 'unit': 'image', 'price_per_unit': '0.04'}]
        out = P.run('approval_request', {'provider': 'p1', 'model': 'img', 'items': items,
                                         'purpose': 'غلاف', 'expected_total': '0.16'})
        r = out['result']
        req = r['request']
        self.assertEqual(req['status'], 'awaiting_owner_approval')
        self.assertTrue(req['irreversible'])
        self.assertEqual(req['total'], '0.16')
        self.assertFalse(r['example_data'])
        self.assertIn(req['request_id'], req['approval_phrase'])
        self.assertIn(req['approval_phrase'], r['message_ar'])
        changed = P.run('approval_request', {'provider': 'p1', 'model': 'img', 'purpose': 'غلاف',
                                             'items': [dict(items[0], quantity=5)]})['result']['request']
        self.assertNotEqual(changed['request_id'], req['request_id'])
        self.assertEqual(P.run('approval_request', {'provider': 'p1', 'model': 'img', 'items': items,
                                                    'purpose': 'غلاف'})['result']['request']['request_id'],
                         req['request_id'])
        for bad in ({'expected_total': '1'}, {'items': []}, {'items': [{'label': 'x'}]},
                    {'status': 'approved'}, {'approved': True}, {'currency': 'dollars!'}):
            with self.assertRaises(ValueError):
                P.run('approval_request', bad)


if __name__ == '__main__':
    unittest.main()
