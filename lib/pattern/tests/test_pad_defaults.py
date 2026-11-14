"""Standalone binary loading reconciles style membership in both directions."""
import math
import unittest

from lib.pattern.formats.lib.read import parse
from lib.pattern.formats.lib.write import encode
from lib.pattern.model import new_library, new_pattern, new_pad


def fixture():
    document = new_library()
    pattern = new_pattern('Example')
    document.one('/Library/Patterns').append(pattern)
    pad = new_pad('1')
    pattern.one('Pads').append(pad)
    pattern['PadWidth'], pattern['PadHeight'] = 6, 3
    pad['PadWidth_New'], pad['PadHeight_New'] = 6, 3
    return document, pattern, pad


class PadDefaultsTests(unittest.TestCase):
    def test_matching_custom_becomes_standard_but_rotation_is_independent(self):
        document, _, pad = fixture()
        pad['Standard'], pad['PadAngle'] = False, math.pi/2
        result = parse(encode(document)).one('/Library/Patterns/Pattern/Pads/Pad')
        self.assertTrue(result['Standard'])
        self.assertEqual(1.5708, result['PadAngle'])
        self.assertFalse(pad['Standard'])

    def test_mismatched_standard_becomes_custom_without_changing_geometry(self):
        document, _, pad = fixture()
        pad['Standard'], pad['PadWidth_New'], pad['CustomSwell_New'] = True, 7, 2
        result = parse(encode(document)).one('/Library/Patterns/Pattern/Pads/Pad')
        self.assertFalse(result['Standard'])
        self.assertEqual((7, 2), (result['PadWidth_New'], result['CustomSwell_New']))
        self.assertTrue(pad['Standard'])

    def test_side_reflection_compares_offsets_and_mask_sides(self):
        document, pattern, pad = fixture()
        pad['Sided'] = True
        pattern['PadShape_X'], pad['PadShape_X'] = 1, -1
        pattern['TopMask_State'], pad['DisableBottomMask'] = 2, 2
        result = parse(encode(document)).one('/Library/Patterns/Pattern/Pads/Pad')
        self.assertTrue(result['Standard'])
        self.assertEqual((True, -1), (result['Sided'], result['PadShape_X']))

    def test_fiducial_does_not_acquire_default_style_membership(self):
        document, _, pad = fixture()
        pad['Standard'], pad['PadShape_New'] = True, 20
        result = parse(encode(document)).one('/Library/Patterns/Pattern/Pads/Pad')
        self.assertTrue(result['Standard'])
        self.assertEqual(20, result['PadShape_New'])


if __name__ == '__main__':
    unittest.main()
