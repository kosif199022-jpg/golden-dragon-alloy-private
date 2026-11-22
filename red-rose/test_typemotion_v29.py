"""W05: every text.motion op exercised with realistic inputs (typemotion_v27)."""
import inspect
import json
import re
import unittest
import xml.etree.ElementTree as ET

import typemotion_v27 as T

SVG_NS = 'http://www.w3.org/2000/svg'
AR_TIMED = [{'word': 'مرحبا', 'start': 0.0, 'end': 0.5}, {'word': 'بكم', 'start': 0.5, 'end': 0.9},
            {'word': None, 'start': 0.9, 'end': 1.1}, {'word': 'الاستوديو', 'start': 1.1, 'end': 1.8},
            {'word': 'الجديد', 'start': 1.8, 'end': 2.4}]


def parse_fragment(frag, w=1080, h=1920):
    return ET.fromstring(f'<svg xmlns="{SVG_NS}" width="{w}" height="{h}">{frag}</svg>')


def texts(root):
    return root.findall('.//{%s}text' % SVG_NS)


class OpsContract(unittest.TestCase):
    def test_ops_are_named_callables_with_docstrings(self):
        self.assertEqual(len(T.OPS), 9)
        for name, fn in T.OPS.items():
            sig = inspect.signature(fn)
            for q in sig.parameters.values():
                self.assertEqual(q.kind, inspect.Parameter.KEYWORD_ONLY, (name, q.name))
                self.assertIsNot(q.default, inspect.Parameter.empty, (name, q.name))
            self.assertTrue(fn.__doc__ and fn.__doc__.strip(), name)
        kt = inspect.signature(T.OPS['kinetic_text']).parameters
        for p in ('text', 'style', 't', 'duration', 'width', 'height', 'font_size', 'plate',
                  'id_prefix', 'document', 'background'):
            self.assertIn(p, kt)
        self.assertIn('srt_text', inspect.signature(T.OPS['srt']).parameters)

    def test_zero_argument_calls_still_succeed(self):
        for name in T.OPS:
            out = T.run(name, {})
            self.assertEqual(set(out), {'op', 'result', 'assumptions', 'limits'}, name)
            json.dumps(out, allow_nan=False)

    def test_unknown_parameter_lists_allowed(self):
        for name, fn in T.OPS.items():
            with self.assertRaises(ValueError) as cm:
                T.run(name, {'zzz_unknown': 1})
            msg = str(cm.exception)
            self.assertIn('allowed:', msg, name)
            for p in inspect.signature(fn).parameters:
                self.assertIn(p, msg, name)


class Kinetic(unittest.TestCase):
    TEXT = 'الوردة الحمراء تتفتّح 2025 Red Rose'

    def test_every_style_parses_never_per_letter_arabic(self):
        for style in T.STYLES:
            r = T.run('kinetic_text', {'text': self.TEXT, 'style': style, 't': 1.0})['result']
            root = parse_fragment(r['svg'])
            for el in texts(root):
                content = el.text or ''
                if re.search('[؀-ۿ]', content):
                    self.assertIn(content, self.TEXT.split(), (style, content))
                    self.assertEqual(el.get('direction'), 'rtl', style)
            self.assertEqual(r['direction'], 'rtl')
            self.assertFalse(r['per_letter_arabic'])

    def test_word_timings_agree_with_visible_words(self):
        words = self.TEXT.split()
        for style in ('fade_up', 'pop_scale', 'stagger_words', 'split_lines', 'word_typewriter'):
            r0 = T.run('kinetic_text', {'text': self.TEXT, 'style': style, 't': 0.9})['result']
            wt = r0['word_timings']
            self.assertEqual([x['word'] for x in wt], words)
            self.assertTrue(all(0 <= x['start'] <= x['end'] <= 3.0 for x in wt), style)
            expected = sum(1 for x in wt if x['start'] < 0.9 - 1e-6)
            self.assertEqual(r0['visible_words'], expected, style)

    def test_document_root_has_canvas_and_background(self):
        r = T.run('kinetic_text', {'text': self.TEXT, 'style': 'fade_up', 't': 1.5, 'document': True,
                                   'width': 720, 'height': 1280, 'background': '#102030'})['result']
        root = ET.fromstring(r['document'])
        self.assertEqual(root.tag, '{%s}svg' % SVG_NS)
        self.assertEqual((root.get('width'), root.get('height')), ('720', '1280'))
        self.assertEqual(root.find('{%s}rect' % SVG_NS).get('fill'), '#102030')
        self.assertNotIn('document', T.run('kinetic_text', {})['result'])

    def test_outline_is_a_separate_copy_not_paint_order(self):
        r = T.run('kinetic_text', {'text': 'Rose', 'style': 'fade_up', 't': 2.5})['result']
        self.assertNotIn('paint-order', r['svg'])
        root = parse_fragment(r['svg'])
        els = texts(root)
        self.assertEqual(len(els), 2)
        self.assertEqual(els[0].get('stroke'), '#000000')
        self.assertIsNone(els[1].get('stroke'))

    def test_contrast_rule_and_font_minimum(self):
        with self.assertRaises(ValueError):
            T.run('kinetic_text', {'stroke': None})
        with self.assertRaises(ValueError):
            T.run('kinetic_text', {'font_size': 20})


class Captions(unittest.TestCase):
    def test_wrap_never_splits_and_keeps_blank(self):
        words = ['هذه', 'جملة', None, 'طويلة', 'جدا', 'للتجربة']
        r = T.run('wrap_caption', {'words': words, 'max_chars': 10})['result']
        self.assertEqual(r['blank_indices'], [2])
        idx = [i for pg in r['pages'] for ln in pg['lines'] for i in ln['indices']]
        self.assertEqual(idx, list(range(len(words))))

    def test_caption_words_inside_safe_box(self):
        r = T.run('caption', {'words': 'نص الترجمة كما قاله المتحدث بالحرف', 'preset': 'cinema_subtle',
                              'width': 1920, 'height': 1080})['result']
        root = parse_fragment(r['svg'], 1920, 1080)
        x, y, w, h = r['safe_box']
        for el in texts(root):
            self.assertTrue(x <= float(el.get('x')) <= x + w)
            self.assertTrue(y <= float(el.get('y')) <= y + h + 1)

    def test_karaoke_highlights_current_word_only_from_given_timings(self):
        r = T.run('karaoke_caption', {'words_with_times': AR_TIMED, 't': 1.3})['result']
        self.assertEqual(r['current_word'], 'الاستوديو')
        root = parse_fragment(r['svg'])
        lit = [el.text for el in texts(root) if el.get('fill') == '#FFD400']
        self.assertEqual(lit, ['الاستوديو'])
        shown = {el.text for el in texts(root)}
        self.assertTrue(shown <= {w['word'] for w in AR_TIMED if w['word']})

    def test_karaoke_plate_contains_words(self):
        r = T.run('karaoke_caption', {'words_with_times': AR_TIMED, 't': 0.2, 'preset': 'punchy',
                                      'width': 1920, 'height': 1080})['result']
        root = parse_fragment(r['svg'], 1920, 1080)
        plate = root.find('.//{%s}rect' % SVG_NS)
        px, pw = float(plate.get('x')), float(plate.get('width'))
        first_line = root.find('.//{%s}g[@class="rr-line"]' % SVG_NS)
        for el in texts(first_line):
            self.assertTrue(px <= float(el.get('x')) <= px + pw)

    def test_srt_build_and_parse(self):
        r = T.run('srt', {'words_with_times': AR_TIMED, 'max_chars': 12})['result']
        self.assertEqual(r['mode'], 'build')
        self.assertGreaterEqual(r['cue_count'], 2)
        self.assertNotIn('None', r['srt'])
        p = T.run('srt', {'srt_text': '1\n00:00:01,000 --> 00:00:02,500\nمرحبا\n'})['result']
        self.assertEqual(p['cues'][0]['start'], 1.0)
        self.assertEqual(p['cues'][0]['direction'], 'rtl')


class LowerThirdCanvasCatalogue(unittest.TestCase):
    def test_arabic_lower_third_text_centred_on_card(self):
        r = T.run('lower_third', {'name': 'سارة أحمد', 'role': 'مخرجة', 't': 2.0})['result']
        self.assertEqual(r['side'], 'right')
        x, y, w, h = r['plate_box']
        root = parse_fragment(r['svg'], 1920, 1080)
        for el in texts(root):
            self.assertEqual(el.get('text-anchor'), 'middle')
            self.assertTrue(x <= float(el.get('x')) <= x + w)

    def test_derive_canvas(self):
        r = T.run('derive_canvas', {'platform': 'youtube', 'fps': 25})['result']
        self.assertEqual((r['width'], r['height'], r['fps'], r['aspect']), (1920, 1080, 25.0, '16:9'))

    def test_list_styles(self):
        r = T.run('list_styles')['result']
        self.assertEqual(r['count'], 15)

    def test_catalogue_one_render_per_language(self):
        r = T.run('catalogue', {'langs': ['ar', 'en'], 't': 1.5})['result']
        self.assertEqual([x['lang'] for x in r['renders']], ['ar', 'en'])
        for x in r['renders']:
            ET.fromstring(x['svg'])
        with self.assertRaises(ValueError):
            T.run('catalogue', {'langs': ['fr']})


if __name__ == '__main__':
    unittest.main()
