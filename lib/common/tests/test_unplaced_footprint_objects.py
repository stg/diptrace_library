"""Detached footprint constructors retain typed editing and unit contracts."""
import unittest

from lib.common.unplaced_footprint_objects import new_pattern, new_pad, new_drawing
from lib.common.drawing_records import POINTS, TEXT_LINES
from lib.common.footprint_records import PASTE_SEGMENTS


class UnplacedFootprintObjectTests(unittest.TestCase):
    def test_detached_pad_contour_and_mask_segments_are_typed(self):
        pad = new_pad('A')
        points = pad.one('PadPoints_New')
        self.assertIs(POINTS, points.schema)
        self.assertIs(PASTE_SEGMENTS, pad.one('PadMask_TopSegments').schema)

    def test_detached_drawing_text_and_geometry_are_typed(self):
        drawing = new_drawing(kind=7)
        self.assertIs(TEXT_LINES, drawing.one('TextLine').schema)
        self.assertIs(POINTS, drawing.one('Points_New').schema)
        self.assertEqual(6, drawing['FontSize'])
        self.assertNotIn('Width', drawing)

    def test_detached_pattern_model_vectors_are_typed(self):
        pattern = new_pattern('Example')
        vector = pattern.one('Model3D/Offset')
        self.assertIsNotNone(vector.schema)
        vector['X'] = 3
        self.assertEqual(3, vector['X'])
        with self.assertRaises(TypeError):
            vector['Y'] = 'invalid length'
        self.assertEqual(0, vector['Y'])


if __name__ == '__main__':
    unittest.main()
