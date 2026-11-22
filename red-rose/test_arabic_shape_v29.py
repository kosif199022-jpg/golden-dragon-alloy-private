"""V29: Arabic shaping before CairoSVG (joining, lam-alef, tashkeel, bidi, stroke split)."""
import importlib.util
import unittest

import arabic_shape as A

TITLE = 'الوردة الحمراء'   # الوردة الحمراء
TITLE_VISUAL = 'ﺀﺍﺮﻤﺤﻟﺍ ﺓﺩﺭﻮﻟﺍ'

HAVE_RASTER = bool(importlib.util.find_spec('cairosvg') and importlib.util.find_spec('PIL'))


def _components(png_bytes, threshold=128):
    """Connected light-ink components (4-neighbour) of a PNG."""
    import io
    from PIL import Image
    with Image.open(io.BytesIO(png_bytes)) as im:
        g = im.convert('L')
        w, h = g.size
        px = g.load()
        ink = [[px[x, y] > threshold for x in range(w)] for y in range(h)]
    seen = [[False] * w for _ in range(h)]
    count = 0
    for y in range(h):
        for x in range(w):
            if ink[y][x] and not seen[y][x]:
                count += 1
                stack = [(x, y)]
                seen[y][x] = True
                while stack:
                    cx, cy = stack.pop()
                    for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                        if 0 <= nx < w and 0 <= ny < h and ink[ny][nx] and not seen[ny][nx]:
                            seen[ny][nx] = True
                            stack.append((nx, ny))
    return count


class ShapeTests(unittest.TestCase):
    def test_title_golden_and_no_base_letters(self):
        r = A.shape(TITLE)
        self.assertEqual(r['visual'], TITLE_VISUAL)
        self.assertTrue(r['changed'])
        self.assertEqual(r['unsupported'], [])
        self.assertFalse(any(0x0621 <= ord(c) <= 0x064A for c in r['visual']))

    def test_lam_alef(self):
        self.assertEqual(A.shape('لا')['visual'], 'ﻻ')
        self.assertEqual(A.shape('سلام')['visual'], 'ﻡﻼﺳ')

    def test_tashkeel_stays_with_base(self):
        got = A.shape('مَرْحَبًا')['visual']
        self.assertEqual(got, 'ﺎﺒًﺣَﺮْﻣَ')

    def test_arabic_with_digits_keeps_digit_order(self):
        got = A.shape('عرض 50%')['visual']
        self.assertEqual(got, '%50 ﺽﺮﻋ')
        self.assertIn('50', got)

    def test_arabic_with_latin_word(self):
        self.assertEqual(A.shape('مرحبا Red')['visual'],
                         'Red ﺎﺒﺣﺮﻣ')

    def test_latin_unchanged(self):
        r = A.shape('Red Rose 2026 (v29)')
        self.assertEqual(r['visual'], 'Red Rose 2026 (v29)')
        self.assertFalse(r['changed'])

    def test_never_shapes_twice(self):
        once = A.shape(TITLE)['visual']
        self.assertTrue(A.is_shaped(once))
        self.assertFalse(A.needs_shaping(once))
        again = A.shape(once)
        self.assertEqual(again['visual'], once)
        self.assertFalse(again['changed'])
        self.assertTrue(A.needs_shaping(TITLE))

    def test_bad_args(self):
        with self.assertRaises(ValueError):
            A.shape(5)
        with self.assertRaises(ValueError):
            A.shape('x', direction='up')

    def test_selftest(self):
        self.assertEqual(A.selftest()['status'], 'pass')


class SvgTests(unittest.TestCase):
    SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200">'
           '<rect width="400" height="200" fill="#5a1020"/>'
           '<g font-family="Tahoma, sans-serif" font-size="48" fill="#fff" stroke="#000" '
           'stroke-width="6" paint-order="stroke fill">'
           f'<text x="380" y="120" direction="rtl">{TITLE}</text></g></svg>')

    def test_shapes_splits_stroke_and_swaps_anchor(self):
        out, rep = A.shape_svg_for_raster(self.SVG)
        self.assertIn(TITLE_VISUAL, out)
        self.assertNotIn(TITLE, out)
        self.assertEqual(rep['stroke_split'], 1)
        self.assertEqual(out.count('<text'), 2)
        self.assertLess(out.index('fill="none"'), out.index('stroke="none"'))  # stroke under fill
        self.assertIn('text-anchor="end"', out)          # rtl start == right edge
        self.assertEqual(rep['warnings'], [])
        self.assertIn('data-rr-shaped="1"', out)

    def test_idempotent_and_input_untouched(self):
        original = str(self.SVG)
        out, _ = A.shape_svg_for_raster(self.SVG)
        self.assertEqual(self.SVG, original)
        out2, rep2 = A.shape_svg_for_raster(out)
        self.assertEqual(out2, out)
        self.assertTrue(rep2['already_shaped'])

    def test_disabled_hook_fails_closed(self):
        A._TEST_DISABLE_SHAPING = True
        try:
            out, rep = A.shape_svg_for_raster(self.SVG)
        finally:
            A._TEST_DISABLE_SHAPING = False
        self.assertEqual(out, self.SVG)
        self.assertTrue(rep['warnings'])
        self.assertTrue(all(w.startswith('arabic_unshaped') for w in rep['warnings']))

    def test_unparseable_svg_with_arabic_warns(self):
        _, rep = A.shape_svg_for_raster(f'<svg><text>{TITLE}</text>')
        self.assertTrue(rep['warnings'])
        self.assertFalse(rep['parsed'])

    def test_latin_svg_without_paint_order_is_returned_as_is(self):
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><text>Rose</text></svg>'
        out, rep = A.shape_svg_for_raster(svg)
        self.assertEqual(out, svg)
        self.assertEqual(rep['warnings'], [])

    def test_font_check(self):
        res = A.resolve_raster_font('Tahoma, Arial, sans-serif')
        if res['family'] is None:
            self.skipTest('no Arabic-capable font found on this machine')
        self.assertTrue(A.font_supports_forms(res['paths'][0]))
        self.assertIsNone(A.font_supports_forms(__file__))

    @unittest.skipUnless(HAVE_RASTER, 'cairosvg and Pillow are needed for the raster check')
    def test_shaped_raster_has_fewer_ink_components(self):
        import cairosvg
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="420" height="120">'
               '<rect width="420" height="120" fill="#000"/>'
               f'<text x="210" y="80" text-anchor="middle" direction="rtl" font-size="56" '
               f'font-family="Tahoma" fill="#fff">{TITLE}</text></svg>')
        shaped, rep = A.shape_svg_for_raster(svg)
        self.assertEqual(rep['warnings'], [])
        a = _components(cairosvg.svg2png(bytestring=shaped.encode('utf-8')))
        b = _components(cairosvg.svg2png(bytestring=svg.encode('utf-8')))
        self.assertLess(a, b)


if __name__ == '__main__':
    unittest.main()
