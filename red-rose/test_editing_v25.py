"""V25 editing ops: interface, safety rules, pure-data ops and FFmpeg-backed media ops."""
from __future__ import annotations

import ast
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import editing_v25 as ed

HERE = Path(__file__).resolve().parent
HAVE_FFMPEG = bool(shutil.which('ffmpeg') and shutil.which('ffprobe'))
FILE_OPS = ['beat_sync_cuts', 'safe_crossfade', 'stabilize_estimate', 'colour_match',
            'vertical_reframe']


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _ff(*args):
    subprocess.run(['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error', '-y', *args],
                   capture_output=True, check=True, timeout=60)


class InterfaceAndRules(unittest.TestCase):
    def test_topics_ops_effects(self):
        self.assertEqual(ed.TOPICS, {
            '15.04': 'beat_sync_cuts', '15.05': 'story_arc', '15.06': 'pacing_balance',
            '15.07': 'safe_crossfade', '15.08': 'stabilize_estimate', '15.09': 'colour_match',
            '15.10': 'vertical_reframe'})
        self.assertEqual(set(ed.OPS), set(ed.TOPICS.values()))
        self.assertEqual(set(ed.EFFECTS), set(ed.OPS))
        self.assertTrue(all(v in ('read', 'write') for v in ed.EFFECTS.values()))
        self.assertEqual(ed.EFFECTS['safe_crossfade'], 'write')
        self.assertEqual(set(ed.TOPIC_NAMES_AR), set(ed.TOPICS))

    def test_run_validation(self):
        with self.assertRaises(ValueError):
            ed.run('nope', {})
        with self.assertRaises(ValueError):
            ed.run('story_arc', [])
        with self.assertRaises(ValueError):
            ed.run('story_arc', {'shots': [{'id': 'a', 'role': 'resolution'}], 'bogus': 1})
        with self.assertRaises(ValueError):
            ed.run('pacing_balance', {'durations': [1, True]})

    def test_file_ops_require_source(self):
        for op in FILE_OPS:
            with self.subTest(op=op):
                with self.assertRaisesRegex(ValueError, 'source is required'):
                    ed.run(op, {})

    def test_urls_and_network_paths_rejected(self):
        for bad in ('https://example.com/a.mp4', 'file:///c:/a.mp4', '\\\\server\\share\\a.mp4'):
            with self.assertRaisesRegex(ValueError, 'URL|network'):
                ed.run('stabilize_estimate', {'source': bad})

    def test_module_io_rules(self):
        tree = ast.parse((HERE / 'editing_v25.py').read_text(encoding='utf-8'))
        allowed_local = {'scene_edit_v16', 'verify_media', 'audio_scene_v17'}
        banned = {'socket', 'urllib', 'http', 'requests', 'ctypes'}
        import sys
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name.split('.')[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [(node.module or '').split('.')[0]]
            else:
                names = []
            for name in names:
                self.assertNotIn(name, banned)
                self.assertTrue(name in allowed_local or name in sys.stdlib_module_names
                                or name == '__future__', name)
            if isinstance(node, ast.Call):
                fn = node.func
                fname = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, 'id', '')
                self.assertNotIn(fname, {'print', 'exec', 'eval', 'system', 'popen', 'Popen',
                                         'call', 'check_output', 'check_call'})
                if isinstance(fn, ast.Attribute) and getattr(fn.value, 'id', '') == 'subprocess':
                    self.assertEqual(fn.attr, 'run')
                    self.assertIsInstance(node.args[0], ast.List)
                    kw = {k.arg: k.value for k in node.keywords}
                    self.assertIn('timeout', kw)
                    self.assertIn('capture_output', kw)
                    self.assertNotIn('shell', kw)


class PureDataOps(unittest.TestCase):
    def test_story_arc_valid_order_passes(self):
        shots = [{'id': 'o', 'role': 'opening', 'intensity': 0.2},
                 {'id': 'r1', 'role': 'rising', 'intensity': 0.4},
                 {'id': 'r2', 'role': 'rising', 'intensity': 0.6},
                 {'id': 'c', 'role': 'climax', 'intensity': 0.95},
                 {'id': 'z', 'role': 'resolution', 'intensity': 0.3}]
        out = ed.run('story_arc', {'shots': shots})
        self.assertEqual(set(out), {'op', 'result', 'assumptions', 'limits'})
        self.assertTrue(out['result']['valid'], out['result']['problems'])
        self.assertEqual(out['result']['problems'], [])
        self.assertEqual(out['result']['suggested_order'], ['o', 'r1', 'r2', 'c', 'z'])

    def test_story_arc_misordered_flagged(self):
        shots = [{'id': 'c', 'role': 'climax', 'intensity': 0.9},
                 {'id': 'o', 'role': 'opening'},
                 {'id': 'r', 'role': 'rising', 'intensity': 0.5},
                 {'id': 'z', 'role': 'resolution'},
                 {'id': 'r2', 'role': 'rising', 'intensity': 0.6}]
        res = ed.run('story_arc', {'shots': shots})['result']
        codes = {p['code'] for p in res['problems']}
        self.assertFalse(res['valid'])
        self.assertIn('climax_before_setup', codes)
        self.assertIn('ending_without_resolution', codes)
        self.assertIn('stage_regression', codes)
        early_res = ed.run('story_arc', {'shots': [
            {'id': 'o', 'role': 'opening'}, {'id': 'z1', 'role': 'resolution'},
            {'id': 'c', 'role': 'climax'}, {'id': 'z2', 'role': 'resolution'}]})['result']
        self.assertIn('resolution_before_climax', {p['code'] for p in early_res['problems']})
        self.assertEqual(res['suggested_order'][0], 'o')
        self.assertEqual(res['suggested_order'][-1], 'z')

    def test_pacing_moves_toward_target_within_bounds(self):
        edl, t = [], 0.0
        for d in [0.6, 7.5, 1.0, 9.0, 0.8, 5.0, 2.2, 6.5]:
            edl.append({'start': t, 'end': t + d})
            t += d + 0.5
        res = ed.run('pacing_balance', {'edl': edl, 'target': 'accelerate', 'strength': 0.7,
                                        'min_duration': 0.6, 'max_duration': 8.0})['result']
        disp = res['dispersion']
        self.assertLess(disp['rms_to_target_after'], disp['rms_to_target_before'])
        self.assertLess(abs(disp['cv_after'] - disp['cv_target']),
                        abs(disp['cv_before'] - disp['cv_target']))
        self.assertTrue(all(0.6 - 1e-9 <= d <= 8.0 + 1e-9 for d in res['durations_after']))
        self.assertTrue(res['total_preserved'])
        self.assertAlmostEqual(sum(res['durations_after']), sum(res['durations_before']), places=2)
        self.assertEqual(len(res['edl_after']), 8)
        flat = ed.run('pacing_balance', {'durations': [1, 4, 1, 4], 'target': 'flat',
                                         'strength': 1.0, 'min_duration': 0.5,
                                         'max_duration': 6})['result']
        self.assertLess(flat['dispersion']['cv_after'], flat['dispersion']['cv_before'])

    def test_svg_namespacing_prevents_collisions(self):
        a = '<svg><defs><linearGradient id="g"/></defs><text id="title" fill="url(#g)">A</text><use href="#title"/></svg>'
        b = '<svg><defs><linearGradient id="g"/></defs><text id="title" fill="url(#g)">B</text></svg>'
        res = ed.namespace_svg_ids([a, b])
        self.assertEqual(res['collisions_before'], ['g', 'title'])
        self.assertEqual(res['collisions_after'], [])
        self.assertTrue(res['ok'])
        self.assertIn('id="clip1-g"', res['fragments'][0])
        self.assertIn('url(#clip1-g)', res['fragments'][0])
        self.assertIn('href="#clip1-title"', res['fragments'][0])
        self.assertIn('url(#clip2-g)', res['fragments'][1])
        with self.assertRaises(ValueError):
            ed.namespace_svg_ids(['<svg><script>x</script></svg>'])


@unittest.skipUnless(HAVE_FFMPEG, 'FFmpeg unavailable')
class MediaOps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        root = cls.root = Path(cls.temp.name)
        cls.click = root / 'click120.mkv'
        _ff('-f', 'lavfi', '-i', 'color=c=gray:s=64x36:r=10:d=4',
            '-f', 'lavfi', '-i',
            "aevalsrc=exprs='if(lt(mod(t\\,0.5)\\,0.012)\\,0.8*sin(2*PI*1500*t)\\,0)':s=22050:d=4",
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'pcm_s16le', '-shortest',
            str(cls.click))
        cls.clip_a = root / 'a.mp4'
        cls.clip_b = root / 'b.mp4'
        _ff('-f', 'lavfi', '-i', 'testsrc2=s=160x90:r=25:d=2',
            '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=2',
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', str(cls.clip_a))
        _ff('-f', 'lavfi', '-i', 'smptebars=s=160x90:r=25:d=2',
            '-f', 'lavfi', '-i', 'sine=frequency=660:sample_rate=48000:duration=2',
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', str(cls.clip_b))
        cls.shaky = root / 'shaky.mp4'
        _ff('-f', 'lavfi', '-i', 'color=c=black:s=320x240:r=15:d=3',
            '-vf', "format=gray,geq=lum='128+50*sin(X/7)*cos(Y/5)+40*sin((X+2*Y)/11)+30*sin(X*Y/900)',"
                   "crop=w=192:h=144:x='40+0.5*n+6*sin(n*2.3)':y='30+5*cos(n*1.7)',format=yuv420p",
            '-c:v', 'libx264', '-crf', '12', str(cls.shaky))
        cls.ref = root / 'ref_blue.mp4'
        cls.tgt = root / 'tgt_green.mp4'
        _ff('-f', 'lavfi', '-i', 'color=c=black:s=128x72:r=10:d=1',
            '-vf', "format=gbrp,geq=r='60+20*sin(X/5)':g='90+30*sin(Y/4)':b='170+40*sin((X+Y)/6)',format=yuv420p",
            '-c:v', 'libx264', '-crf', '10', str(cls.ref))
        _ff('-f', 'lavfi', '-i', 'color=c=black:s=128x72:r=10:d=1',
            '-vf', "format=gbrp,geq=r='70+20*sin(X/5)':g='140+30*sin(Y/4)':b='60+20*sin((X+Y)/6)',"
                   "drawbox=x=8:y=8:w=40:h=40:color=0xD09070@1:t=fill,format=yuv420p",
            '-c:v', 'libx264', '-crf', '10', str(cls.tgt))
        cls.wide = root / 'wide.mp4'
        _ff('-f', 'lavfi', '-i', 'color=c=0x202020:s=320x180:r=10:d=4',
            '-f', 'lavfi', '-i', 'color=c=white:s=30x30:r=10:d=4',
            '-filter_complex', "[0:v][1:v]overlay=x='20+t*65':y=60,format=yuv420p[v]",
            '-map', '[v]', '-c:v', 'libx264', str(cls.wide))
        cls.hashes = {p: _sha(p) for p in (cls.click, cls.clip_a, cls.clip_b, cls.shaky,
                                           cls.ref, cls.tgt, cls.wide)}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def tearDown(self):
        for path, digest in self.hashes.items():
            self.assertEqual(_sha(path), digest, f'source modified: {path.name}')

    def test_beat_sync_requires_rights(self):
        res = ed.run('beat_sync_cuts', {'source': str(self.click)})['result']
        self.assertEqual(res['status'], 'audio_rights_confirmation_required')
        self.assertNotIn('beats', res)

    def test_beat_sync_click_track_120bpm(self):
        out = ed.run('beat_sync_cuts', {'source': str(self.click), 'audio_rights_confirmed': True,
                                        'cut_times': [1.03, 2.21, 3.38]})
        res = out['result']
        self.assertAlmostEqual(res['tempo_bpm'], 120, delta=3)
        beats = res['beats']
        self.assertGreaterEqual(len(beats), 7)
        for x, y in zip(beats, beats[1:]):
            self.assertAlmostEqual(y - x, 0.5, delta=0.02)
        for b in beats:
            self.assertLess(abs(b - round(b * 2) / 2), 0.02)
        for c in res['snapped_cuts']:
            self.assertTrue(c['snapped'])
            self.assertLess(abs(c['snapped_to'] - round(c['snapped_to'] * 2) / 2), 0.02)
            self.assertAlmostEqual(c['distance_ms'], (c['beat'] - c['cut']) * 1000, delta=0.2)

    def test_crossfade_approval_gate_writes_nothing(self):
        target = self.root / 'xfade_gate.mp4'
        res = ed.run('safe_crossfade', {'source': str(self.clip_a), 'source_b': str(self.clip_b),
                                        'output': str(target), 'overlap': 0.4})['result']
        self.assertEqual(res['status'], 'approval_required')
        self.assertFalse(target.exists())
        self.assertEqual(sorted(p.name for p in self.root.glob('.rose-xfade-*')), [])

    def test_crossfade_render_verified(self):
        target = self.root / 'xfade.mp4'
        svg = ['<svg><g id="t"/><use href="#t"/></svg>', '<svg><g id="t"/></svg>']
        out = ed.run('safe_crossfade', {'source': str(self.clip_a), 'source_b': str(self.clip_b),
                                        'output': str(target), 'overlap': 0.4,
                                        'svg_titles': svg, 'approve_write': True})
        res = out['result']
        self.assertEqual(res['status'], 'rendered_and_verified')
        self.assertTrue(target.is_file())
        self.assertLessEqual(abs(res['video_seconds'] - (2 + 2 - 0.4)), 1 / 25 + 1e-6)
        self.assertEqual(res['qa']['audio_codec'], 'aac')
        self.assertGreater(res['first_frame_luma']['mean'], 16)
        self.assertEqual(res['plan']['svg_titles']['collisions_after'], [])
        self.assertEqual(res['plan']['svg_titles']['collisions_before'], ['t'])
        self.assertEqual(list(self.root.glob('.rose-xfade-*')), [])
        before = _sha(target)
        with self.assertRaisesRegex(ValueError, 'new .mp4'):
            ed.run('safe_crossfade', {'source': str(self.clip_a), 'source_b': str(self.clip_b),
                                      'output': str(target), 'approve_write': True})
        with self.assertRaises(ValueError):
            ed.run('safe_crossfade', {'source': str(self.clip_a), 'source_b': str(self.clip_b),
                                      'output': str(self.clip_a), 'approve_write': True})
        self.assertEqual(_sha(target), before)
        json.dumps(out)

    def test_stabilize_estimate_reduces_jitter(self):
        res = ed.run('stabilize_estimate', {'source': str(self.shaky), 'proxy_width': 96,
                                            'smoothing_seconds': 0.4})['result']
        self.assertEqual(res['status'], 'estimated_not_rendered')
        self.assertGreater(res['jitter_before'], 1.0)
        self.assertLess(res['jitter_after'], 0.5 * res['jitter_before'])
        self.assertGreater(res['crop_margin_px'][0], 0)
        w, h = res['suggested_crop']
        self.assertEqual((w % 2, h % 2), (0, 0))
        self.assertEqual(res['search_saturated_pairs'], 0)

    def test_colour_match_reduces_delta_e_and_protects_skin(self):
        res = ed.run('colour_match', {'source': str(self.tgt), 'reference': str(self.ref),
                                      'strength': 0.9, 'skin_hue_limit_deg': 4})['result']
        self.assertLess(res['delta_e76_mean_after'], res['delta_e76_mean_before'] - 5)
        self.assertGreater(res['skin']['pixels'], 100)
        self.assertLessEqual(res['skin']['max_hue_shift_deg'], 4 + 1e-6)
        self.assertFalse(res['applied_to_footage'])
        unprotected = ed.run('colour_match', {'source': str(self.tgt), 'reference': str(self.ref),
                                              'strength': 0.9, 'skin_protect': False})['result']
        self.assertEqual(unprotected['skin']['pixels'], 0)
        self.assertLess(unprotected['delta_e76_mean_after'], unprotected['delta_e76_mean_before'])

    def test_vertical_reframe_keeps_protected_box(self):
        box = {'x': 0.30, 'y': 0.70, 'w': 0.12, 'h': 0.15, 'label': 'title'}
        res = ed.run('vertical_reframe', {'source': str(self.wide), 'protected_boxes': [box],
                                          'sample_fps': 5})['result']
        cw, ch = res['crop_size']
        self.assertEqual((cw % 2, ch % 2), (0, 0))
        self.assertTrue(res['even_dimensions'])
        self.assertTrue(res['all_protected_inside'])
        self.assertGreater(len(res['track']), 10)
        bx0, bx1 = box['x'] * 320, (box['x'] + box['w']) * 320
        for s in res['track']:
            self.assertLessEqual(s['x'], bx0)
            self.assertGreaterEqual(s['x'] + s['w'], bx1)
            self.assertGreaterEqual(s['x'], 0)
            self.assertLessEqual(s['x'] + s['w'], 320)
        free = ed.run('vertical_reframe', {'source': str(self.wide), 'sample_fps': 5})['result']
        self.assertGreater(free['track'][-1]['x'], free['track'][0]['x'] + 60)
        keyed = ed.run('vertical_reframe', {'source': str(self.wide),
                                            'poi': [{'t': 0, 'x': 0.2, 'y': 0.5},
                                                    {'t': 4, 'x': 0.8, 'y': 0.5}]})['result']
        self.assertEqual(keyed['poi_method'], 'supplied_keyframes')


if __name__ == '__main__':
    unittest.main()
