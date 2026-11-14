"""Receiver profiles use observed vector rows without changing text content."""
import unittest

from lib.common.footprint_objects import new_pattern_drawing
from lib.common.library_versions import LibraryApplicationVersion


class LibraryLayoutProfileTests(unittest.TestCase):
    def test_current_and_earlier_profiles_keep_advances_but_have_distinct_rows(self):
        shape = new_pattern_drawing(kind=7)
        for key, value in dict(FontSize=6, FontWidth=-1, FontScale=1,
                TextAngle=0, TextHorz=-1, TextVert=-1, LineSpacing=1.2).items():
            shape[key] = value
        shape.one('Points_New').add('pt', 0, 0)
        for line in ('Control', 'Second line'):
            shape.one('TextLine').add('pt', line)
        # Ordinary controlled-file conversions expose these envelopes through
        # group centres. The last decimal is limited by serialized coordinates.
        for application, height in (((4,3,0,5),17.5112), ((4,9,5,0),17.5112), ((5,3,5,1),18.7198)):
            with self.subTest(application=application):
                low, high = LibraryApplicationVersion(application).text_layout().pattern_bounds(shape)
                self.assertEqual((0, 0), low)
                self.assertAlmostEqual(45.688, high[0], delta=.0001)
                self.assertAlmostEqual(height, high[1], delta=.0001)
        self.assertEqual(['Control','Second line'], [row.values[0] for row in shape.select('TextLine/pt')])


if __name__ == '__main__':
    unittest.main()
