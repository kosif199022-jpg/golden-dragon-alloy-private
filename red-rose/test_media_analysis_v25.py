"""V25: read-only frame analysis ops, tested on synthetic FFmpeg lavfi media."""
from __future__ import annotations

import ast
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import media_analysis_v25 as ma

ROOT = Path(__file__).resolve().parent
HAVE_FFMPEG = bool(shutil.which('ffmpeg') and shutil.which('ffprobe'))


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _ff(*args):
    subprocess.run(['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error', '-y', *map(str, args)],
                   capture_output=True, check=True, timeout=40)


class ContractTests(unittest.TestCase):
    def test_topics_ops_effects(self):
        self.assertEqual(set(ma.TOPICS), {'20.02', '20.03', '20.04', '20.05', '20.06',
                                          '20.08', '20.09', '20.10'})
        self.assertEqual(set(ma.TOPICS.values()), set(ma.OPS))
        self.assertEqual(ma.EFFECTS, {op: 'read' for op in ma.OPS})
        self.assertEqual(set(ma.TOPIC_NAMES_AR), set(ma.TOPICS))

    def test_io_rules_in_source(self):
        tree = ast.parse((ROOT / 'media_analysis_v25.py').read_text(encoding='utf-8'))
        banned = {'socket', 'urllib', 'http', 'requests', 'ctypes', 'os'}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertFalse({a.name.split('.')[0] for a in node.names} & banned)
            elif isinstance(node, ast.ImportFrom) and node.module:
                self.assertNotIn(node.module.split('.')[0], banned)
            elif isinstance(node, ast.Call):
                name = getattr(node.func, 'id', None) or getattr(node.func, 'attr', None)
                self.assertNotIn(name, {'exec', 'eval', 'print', 'system', 'popen', 'Popen', 'open'})
                if name == 'run' and getattr(node.func.value, 'id', None) == 'subprocess':
                    self.assertIsInstance(node.args[0], (ast.List, ast.Name, ast.BinOp))
                    kw = {k.arg: k.value for k in node.keywords}
                    self.assertIn('timeout', kw)
                    self.assertIn('check', kw)
                    self.assertTrue(getattr(kw.get('capture_output'), 'value', False))
                    self.assertNotIn('shell', kw)

    def test_empty_params_require_source(self):
        for op in ma.OPS:
            with self.subTest(op=op), self.assertRaisesRegex(ValueError, 'source is required'):
                ma.run(op, {})

    def test_rejections(self):
        with self.assertRaises(ValueError):
            ma.run('not_an_op', {})
        for op in ma.OPS:
            with self.subTest(op=op), self.assertRaises(ValueError):
                ma.run(op, {'shell': 'rm -rf /'})
        with self.assertRaisesRegex(ValueError, 'URL'):
            ma.run('sharpness', {'source': 'https://example.com/a.mp4'})
        with self.assertRaises(ValueError):
            ma.run('sharpness', {'source': str(ROOT / 'no_such_file_v25.mp4')})
        with self.assertRaises(ValueError):
            ma.run('sharpness', {'source': str(ROOT / 'README.md')})
        with self.assertRaises(ValueError):
            ma.run('sharpness', {'source': 3})
        with self.assertRaises(ValueError):
            ma.run('sharpness', [])


@unittest.skipUnless(HAVE_FFMPEG, 'ffmpeg/ffprobe required')
class MediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = Path(cls.tmp.name)
        cls.d = d
        enc = ['-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p']
        # 3-colour clip: cuts at exactly 1.0 s and 2.0 s.
        cls.cuts = d / 'cuts.mp4'
        _ff('-f', 'lavfi', '-i', 'color=c=red:s=160x90:r=25:d=1',
            '-f', 'lavfi', '-i', 'color=c=green:s=160x90:r=25:d=1',
            '-f', 'lavfi', '-i', 'color=c=blue:s=160x90:r=25:d=1',
            '-filter_complex', '[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]', '-map', '[v]',
            *enc, '-crf', '18', cls.cuts)
        # Same white 80x80 square: fixed at x=100, or moving right at 100 px/s.
        cls.static = d / 'static.mp4'
        _ff('-f', 'lavfi', '-i', 'color=c=black:s=320x180:r=25:d=2',
            '-vf', 'drawbox=x=100:y=50:w=80:h=80:color=white:t=fill', *enc, '-crf', '18', cls.static)
        cls.moving = d / 'moving.mp4'
        _ff('-f', 'lavfi', '-i', 'color=c=black:s=320x180:r=25:d=2',
            '-f', 'lavfi', '-i', 'color=c=white:s=80x80:r=25:d=2',
            '-filter_complex', "[0:v][1:v]overlay=x='40+100*t':y=50:eval=frame[v]",
            '-map', '[v]', *enc, '-crf', '18', cls.moving)
        cls.salient = d / 'salient.png'
        _ff('-f', 'lavfi', '-i', 'color=c=0x101010:s=320x180:d=1',
            '-vf', 'drawbox=x=240:y=30:w=40:h=40:color=white:t=fill', '-frames:v', '1', cls.salient)
        cls.img = d / 'img.png'
        _ff('-f', 'lavfi', '-i', 'testsrc2=s=320x180:d=1', '-frames:v', '1', cls.img)
        cls.img_bright = d / 'img_bright.png'
        _ff('-i', cls.img, '-vf', 'eq=brightness=0.06', '-frames:v', '1', cls.img_bright)
        cls.img_other = d / 'img_other.png'
        _ff('-f', 'lavfi', '-i', 'smptebars=s=320x180:d=1', '-frames:v', '1', cls.img_other)
        cls.sharp = d / 'sharp.mp4'
        _ff('-f', 'lavfi', '-i', 'testsrc2=s=320x180:r=25:d=2', *enc, '-crf', '16', cls.sharp)
        cls.blurred = d / 'blurred.mp4'
        _ff('-i', cls.sharp, '-vf', 'gblur=sigma=4', *enc, '-crf', '16', cls.blurred)
        cls.lowq = d / 'lowq.mp4'
        _ff('-i', cls.sharp, '-vf', 'scale=64:36,scale=320:180', *enc, '-crf', '40', cls.lowq)
        cls.sharp_copy = d / 'sharp_copy.mp4'
        cls.sharp_copy.write_bytes(cls.sharp.read_bytes())

        def two(c1, c2, name):
            out = d / name
            _ff('-f', 'lavfi', '-i', f'color=c={c1}:s=160x90:r=25:d=1',
                '-f', 'lavfi', '-i', f'color=c={c2}:s=160x90:r=25:d=1',
                '-filter_complex', '[0:v][1:v]concat=n=2:v=1:a=0[v]', '-map', '[v]',
                *enc, '-crf', '18', out)
            return out
        cls.pal_a = two('red', 'blue', 'pal_a.mp4')
        cls.pal_b = two('blue', 'red', 'pal_b.mp4')
        cls.pal_c = two('green', 'yellow', 'pal_c.mp4')
        cls.pillar = d / 'pillar.mp4'
        _ff('-f', 'lavfi', '-i', 'testsrc2=s=180x320:r=25:d=1',
            '-vf', 'pad=w=568:h=320:x=194:y=0:color=black', *enc, '-crf', '18', cls.pillar)
        cls.inputs = [p for p in d.iterdir() if p.is_file()]
        cls.hashes = {p: _sha(p) for p in cls.inputs}

    @classmethod
    def tearDownClass(cls):
        try:
            for p, h in cls.hashes.items():
                assert _sha(p) == h, f'input modified: {p.name}'
        finally:
            cls.tmp.cleanup()

    def _check(self, out, op):
        self.assertEqual(out['op'], op)
        self.assertTrue(out['assumptions'] and out['limits'])
        json.dumps(out, allow_nan=False)
        return out['result']

    def test_inputs_unchanged_after_runs(self):
        ma.run('sharpness', {'source': str(self.sharp)})
        ma.run('frame_borders', {'source': str(self.pillar)})
        for p, h in self.hashes.items():
            self.assertEqual(_sha(p), h, p.name)
        self.assertEqual(sorted(p.name for p in self.d.iterdir()),
                         sorted(p.name for p in self.inputs))

    def test_20_02_scene_cuts_eval(self):
        r = self._check(ma.run('scene_cuts_eval', {'source': str(self.cuts),
                                                   'labelled_cuts': [1.0, 2.0],
                                                   'tolerance': 0.15}), 'scene_cuts_eval')
        self.assertEqual(len(r['cuts']), 2, r['cuts'])
        ev = r['evaluation']
        self.assertEqual((ev['precision'], ev['recall']), (1.0, 1.0))
        self.assertTrue(all(abs(m['error_s']) <= 0.15 for m in ev['matches']))
        bad = ma.run('scene_cuts_eval', {'source': str(self.cuts), 'labelled_cuts': [0.5],
                                         'tolerance': 0.1})['result']['evaluation']
        self.assertEqual(bad['precision'], 0.0)
        with self.assertRaises(ValueError):
            ma.run('scene_cuts_eval', {'source': str(self.cuts), 'labelled_cuts': [99.0]})
        with self.assertRaises(ValueError):
            ma.run('scene_cuts_eval', {'source': str(self.img)})  # images not allowed

    def test_20_03_motion_stats(self):
        still = self._check(ma.run('motion_stats', {'source': str(self.static)}), 'motion_stats')
        move = ma.run('motion_stats', {'source': str(self.moving)})['result']
        self.assertGreater(still['textured_blocks'], 0)  # edges were observable, not skipped
        self.assertLess(still['mean_magnitude_px_per_s'], 2.0)
        self.assertGreater(move['mean_magnitude_px_per_s'], 10 * max(still['mean_magnitude_px_per_s'], 1.0))
        self.assertEqual(move['dominant_direction'], 'E')
        self.assertGreater(move['mean_vector_px_per_s']['x'], 0)

    def test_20_04_saliency_point(self):
        r = self._check(ma.run('saliency_point', {'source': str(self.salient), 'aspect': '9:16'}),
                        'saliency_point')
        p = r['point_of_interest']
        self.assertAlmostEqual(p['x'], 260, delta=8)
        self.assertAlmostEqual(p['y'], 50, delta=8)
        c = r['suggested_crop']
        self.assertTrue(c['contains_point'])
        self.assertAlmostEqual(c['width'] / c['height'], 9 / 16, delta=0.02)
        self.assertTrue(c['x'] <= 240 and c['x'] + c['width'] >= 280)
        self.assertTrue(c['y'] <= 30 and c['y'] + c['height'] >= 70)
        with self.assertRaises(ValueError):
            ma.run('saliency_point', {'source': str(self.salient), 'aspect': 'tall'})

    def test_20_05_perceptual_dupes(self):
        r = self._check(ma.run('perceptual_dupes', {'sources': [str(self.img), str(self.img_bright),
                                                                str(self.img_other)]}),
                        'perceptual_dupes')
        pairs = {(p['a'], p['b']): p for p in r['pairs']}
        self.assertTrue(pairs[(0, 1)]['duplicate'], pairs[(0, 1)])
        self.assertLessEqual(pairs[(0, 1)]['ahash_distance'], 10)
        self.assertFalse(pairs[(0, 2)]['duplicate'], pairs[(0, 2)])
        self.assertGreater(pairs[(0, 2)]['dhash_distance'], 10)
        self.assertEqual(r['duplicate_groups'], [[0, 1]])
        with self.assertRaises(ValueError):
            ma.run('perceptual_dupes', {'sources': [str(self.img)]})

    def test_20_06_sharpness(self):
        r = self._check(ma.run('sharpness', {'source': str(self.sharp),
                                             'compare': str(self.blurred)}), 'sharpness')
        self.assertLess(r['ratio_compare_to_source'], 0.5, r)
        self.assertGreater(r['source']['laplacian_variance_mean'], 0)

    def test_20_08_colour_stats(self):
        ab = self._check(ma.run('colour_stats', {'source': str(self.pal_a),
                                                 'compare': str(self.pal_b)}), 'colour_stats')
        ac = ma.run('colour_stats', {'source': str(self.pal_a), 'compare': str(self.pal_c)})['result']
        self.assertGreater(ab['similarity']['source_vs_compare'],
                           ac['similarity']['source_vs_compare'] + 0.5)
        self.assertEqual(len(ab['source']['shots']), 2)
        pal = ma.run('colour_stats', {'source': str(self.pal_a),
                                      'palette': ['#ff0000', '#0000ff']})['result']
        self.assertGreater(pal['similarity']['source_vs_palette'], 0.6)
        with self.assertRaises(ValueError):
            ma.run('colour_stats', {'source': str(self.pal_a), 'palette': ['red']})

    def test_20_09_quality_compare(self):
        same = self._check(ma.run('quality_compare', {'source': str(self.sharp),
                                                      'compare': str(self.sharp_copy)}),
                           'quality_compare')
        self.assertIsNone(same['psnr_db'])
        self.assertIn('infinite', same['psnr_note'])
        self.assertEqual(same['ssim'], 1.0)
        low = ma.run('quality_compare', {'source': str(self.sharp), 'compare': str(self.lowq)})['result']
        self.assertIsNotNone(low['psnr_db'])
        self.assertLess(low['psnr_db'], 35)
        self.assertLess(low['ssim'], 0.95)
        for res in (same, low):
            self.assertIn('psnr_db', res)
            self.assertIn('ssim', res)
            self.assertIsNone(res['single_quality_score'])
            ctx = res['context']
            self.assertEqual(ctx['source']['codec'], 'h264')
            self.assertEqual((ctx['compare']['width'], ctx['compare']['height']), (320, 180))
        with self.assertRaisesRegex(ValueError, 'compare is required'):
            ma.run('quality_compare', {'source': str(self.sharp)})

    def test_20_10_frame_borders(self):
        r = self._check(ma.run('frame_borders', {'source': str(self.pillar)}), 'frame_borders')
        self.assertEqual(r['classification'], 'pillarbox')
        self.assertAlmostEqual(r['active_aspect'], 9 / 16, delta=0.03)
        self.assertEqual(r['nearest_standard_aspect'], '9:16')
        self.assertAlmostEqual(r['borders_px']['left'], 194, delta=6)
        full = ma.run('frame_borders', {'source': str(self.sharp)})['result']
        self.assertEqual(full['classification'], 'full_frame')


if __name__ == '__main__':
    unittest.main()
