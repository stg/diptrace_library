"""Shared text measurements preserve full footprint text and authored geometry."""
import math
import unittest

from lib.common.footprint_objects import new_pattern_drawing
from lib.common.text.layout import TextLayout
from lib.common.text.vector import TextMetrics
from lib.common.text.vector_layout import pattern_vector_text_bounds


def drawing(*, vector=True):
    shape = new_pattern_drawing(kind=7)
    shape['VectorFont'] = vector
    shape['FontSize'] = 2
    shape['TextAngle'] = math.pi/4
    shape['TextHorz'], shape['TextVert'] = -1, -1
    shape.one('Points_New').add('pt', 3, 4)
    shape.one('TextLine').add('pt', 'ABC')
    shape.one('TextLine').add('pt', 'DE')
    return shape


class TextLayoutTests(unittest.TestCase):
    def test_full_footprint_and_symbol_bounds_share_text_math(self):
        shape = drawing()
        before = shape.clone()
        full = TextLayout().pattern_bounds(shape)
        symbol = shape.clone()
        symbol['Type'] = 10
        self.assertEqual(full, TextLayout().symbol_bounds(symbol))
        self.assertNotEqual(full, pattern_vector_text_bounds(shape))
        self.assertEqual(shape.one('Points_New/pt').values, before.one('Points_New/pt').values)
        self.assertEqual(shape['TextAngle'], before['TextAngle'])
        self.assertEqual(len(shape.select('TextLine/pt')), 2)

    def test_system_backend_receives_font_environment_without_changing_source(self):
        calls = []

        def measure(text, family, point_size):
            calls.append((text, family, point_size))
            return TextMetrics(len(text)*10, 20 if text else 0)

        shape = drawing(vector=False)
        shape['FontName'] = 'Example family'
        bounds = TextLayout(measure).pattern_bounds(shape)
        self.assertTrue(all(math.isfinite(float(value)) for point in bounds for value in point))
        self.assertTrue(all(family == 'Example family' and size == 17 for _, family, size in calls))
        self.assertEqual({text for text, _, _ in calls}, {'ABC', 'DE', 's'})
        self.assertEqual(shape['FontSize'], 2)

    def test_vector_drawing_never_requests_a_system_backend(self):
        def unexpected(*args):
            raise AssertionError('unexpected platform font access')
        self.assertEqual(TextLayout(unexpected).pattern_bounds(drawing()),
                         TextLayout().pattern_bounds(drawing()))

    def test_system_footprint_trailing_blank_rows_retain_spacing_and_text_height(self):
        def measure(text, family, size):
            return TextMetrics(len(text)*10, 20 if text else 0)
        shape = drawing(vector=False)
        shape['TextAngle'] = 0
        shape.one('TextLine/pt[2]').set_values('')
        shape.one('TextLine').add('pt', ' ')
        lo, hi = TextLayout(measure).pattern_bounds(shape)
        self.assertEqual(lo, (3, 4))
        self.assertAlmostEqual(hi[1]-lo[1], 2+2*(2/2.1)*(float(shape['LineSpacing'])+1))
        shape.one('TextLine/pt[1]').set_values('  ')
        lo, hi = TextLayout(measure).pattern_bounds(shape)
        self.assertEqual((lo[1], hi[1]), (4, 4))


if __name__ == '__main__':
    unittest.main()
