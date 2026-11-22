"""V29 studio: repaired example timeline, dry-run validation, title_frame, fail-closed Arabic QA."""
import base64
import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

import arabic_shape
import studio_v27 as S
from test_arabic_shape_v29 import TITLE, _components

HAVE_RASTER = bool(importlib.util.find_spec('cairosvg') and importlib.util.find_spec('PIL'))
HAVE_FFMPEG = bool(shutil.which('ffmpeg') and shutil.which('ffprobe'))
OLD_BROKEN = {'width': 1080, 'height': 1920, 'fps': 24, 'duration': 4.0, 'background': '#5a1020',
              'layers': [{'module': 'typemotion', 'op': 'kinetic_text', 'start': 0.0, 'end': 2.4,
                          'params': {'text': TITLE, 'direction': 'rtl', 'size': 120,
                                     'color': '#ffffff'}}]}


def _small(text=TITLE, duration=0.5):
    return {'width': 320, 'height': 180, 'fps': 12, 'duration': duration, 'background': '#5a1020',
            'layers': [{'module': 'typemotion', 'op': 'kinetic_text', 'start': 0.0,
                        'end': duration, 'params': {'text': text, 'style': 'fade_up'}}]}


class ValidateTests(unittest.TestCase):
    def test_old_broken_example_is_invalid_and_names_layer(self):
        r = S.run('validate_timeline', {'spec': OLD_BROKEN})['result']
        self.assertFalse(r['valid'])
        self.assertEqual(r['invalid_layers'], [0])
        self.assertTrue(any('layers[0]' in e and 'color' in e for e in r['errors']))

    def test_text_layer_duration_defaults_to_span(self):
        r = S.run('validate_timeline', {'spec': _small(duration=1.5)})['result']
        self.assertTrue(r['valid'], r['errors'])
        self.assertEqual(r['normalized']['layers'][0]['params']['duration'], 1.5)

    def test_example_validates_and_previews(self):
        ex = S.run('example_timeline')['result']
        self.assertGreaterEqual(ex['layers_kept'], 1)
        self.assertTrue(any(l['op'] == 'kinetic_text' for l in ex['spec']['layers']))
        v = S.run('validate_timeline', {'spec': ex['spec']})['result']
        self.assertTrue(v['valid'], v['errors'])
        for t in (0, 1, 2, 3):
            p = S.run('preview_frame', {'spec': ex['spec'], 't': t,
                                        'rasterize': HAVE_RASTER, **({'png_width': 270} if HAVE_RASTER else {})})
            self.assertIn('<svg', p['result']['svg'])
            if HAVE_RASTER:
                self.assertTrue(p['result']['qa']['passed'], p['result']['warnings'])
                self.assertFalse(p['result']['black'])

    @unittest.skipUnless(HAVE_RASTER and HAVE_FFMPEG, 'cairosvg, Pillow and FFmpeg needed')
    def test_example_renders_and_verifies(self):
        ex = S.run('example_timeline')['result']['spec']
        ex = dict(ex, width=270, height=480, fps=12)
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'example.mp4'
            with self.assertRaises(PermissionError):
                S.run('render_timeline', {'spec': ex, 'output': str(out)})
            r = S.run('render_timeline', {'spec': ex, 'output': str(out), 'approve_write': True,
                                          'preset': 'ultrafast'})['result']
            self.assertEqual(r['status'], 'rendered_and_verified')
            self.assertTrue(r['qa']['passed'])
            self.assertIn(r['audio_codec'], (None, 'aac'))
            self.assertFalse(S._is_black(r['first_frame_luma']))
            self.assertEqual(r['shaping']['warnings'], [])
            self.assertTrue(r['shaping']['applied'])
            self.assertTrue(out.is_file())


class TitleFrameTests(unittest.TestCase):
    def test_reel_size_timings_and_both_words(self):
        r = S.run('title_frame', {'text': TITLE, 'rasterize': False})['result']
        self.assertEqual((r['width'], r['height']), (1080, 1920))
        self.assertEqual([w['word'] for w in r['word_timings']], TITLE.split())
        self.assertEqual(r['words_started_at_t'], TITLE.split())
        self.assertTrue(all(w['end'] <= r['t'] for w in r['word_timings']))
        for word in TITLE.split():
            self.assertIn(word, r['svg'])          # svg keeps logical text
        wide = S.run('title_frame', {'text': TITLE, 'platform': 'wide', 'rasterize': False})['result']
        self.assertEqual((wide['width'], wide['height']), (1920, 1080))

    def test_requires_text(self):
        with self.assertRaises(ValueError):
            S.run('title_frame', {})
        with self.assertRaises(ValueError):
            S.run('title_frame', {'text': TITLE, 'nope': 1})

    @unittest.skipUnless(HAVE_RASTER, 'cairosvg and Pillow needed for the raster check')
    def test_shaped_png_has_fewer_components_than_unshaped(self):
        params = {'text': TITLE, 'width': 540, 'height': 300}
        good = S.run('title_frame', params)['result']
        self.assertTrue(good['shaping']['applied'])
        self.assertTrue(good['qa']['passed'])
        self.assertEqual(good['warnings'], [])
        arabic_shape._TEST_DISABLE_SHAPING = True
        try:
            bad = S.run('title_frame', params)['result']
        finally:
            arabic_shape._TEST_DISABLE_SHAPING = False
        self.assertFalse(bad['qa']['passed'])
        self.assertTrue(any(w.startswith('arabic_unshaped') for w in bad['warnings']))
        a = _components(base64.b64decode(good['png_base64']))
        b = _components(base64.b64decode(bad['png_base64']))
        self.assertLess(a, b)

    @unittest.skipUnless(HAVE_RASTER and HAVE_FFMPEG, 'cairosvg, Pillow and FFmpeg needed')
    def test_render_with_shaping_disabled_is_not_verified(self):
        arabic_shape._TEST_DISABLE_SHAPING = True
        try:
            with tempfile.TemporaryDirectory() as d:
                r = S.run('render_timeline', {'spec': _small(), 'output': str(Path(d) / 'x.mp4'),
                                              'approve_write': True, 'preset': 'ultrafast'})['result']
        finally:
            arabic_shape._TEST_DISABLE_SHAPING = False
        self.assertNotEqual(r['status'], 'rendered_and_verified')
        self.assertFalse(r['qa']['passed'])
        self.assertTrue(any(w.startswith('arabic_unshaped') for w in r['warnings']))


if __name__ == '__main__':
    unittest.main()
