"""Standalone PCB classification consumes geometry markers, preserving identities."""
import unittest

from lib.common.model import Element
from lib.common.footprint_objects import new_pattern, new_pad, new_pattern_drawing
from lib.pcb.formats.assembly.object_kinds import normalize_objects


def fixture(*, kind=0, pad_kinds=(), holes=0, drawings=()):
    board = Element('Board')
    component = board.add('Components').add('Component')
    component.add('UserFields').add('UserField', 'Order', 'A42', 0)
    component.add('RefDes_SilkShow', 1)
    component.add('RefDes_SilkX', 12)
    pattern = component.append(new_pattern('Object'))
    pattern['Type'] = kind
    pads = pattern.one('Pads')
    for i, shape in enumerate((None, *pad_kinds, None)):
        pad = pads.append(new_pad())
        pad['Number_New'] = i if shape is not None else -1
        if shape is not None:
            pad['PadShape_New'] = shape
    shapes = pattern.one('Shapes')
    for shape in (0, *drawings, 0):
        shapes.append(new_pattern_drawing(kind=shape))
    collection = pattern.one('Holes')
    for enabled in (False, *((True,)*holes), False):
        collection.add('Hole', enabled, False, 0, 0, 2, 2)
    return board, component, pattern


class ObjectNormalizationTests(unittest.TestCase):
    def test_one_physical_pad_becomes_standalone_with_identity_unchanged(self):
        data, component, pattern = fixture(kind=5, pad_kinds=(2,), drawings=(7,))
        pad = pattern.one('Pads/Pad[2]')
        normalize_objects(data)
        self.assertEqual(pattern['Type'], 14)
        self.assertIs(pattern.one('Pads/Pad[2]'), pad)
        self.assertEqual(pad['Number_New'], 1)
        self.assertEqual(component['RefDes_SilkShow'], 1)

    def test_nontext_geometry_prevents_standalone_pad_classification(self):
        data, _, pattern = fixture(kind=14, pad_kinds=(2,), drawings=(1,))
        normalize_objects(data)
        self.assertEqual(pattern['Type'], 0)

    def test_via_and_fiducial_classifications_are_distinct(self):
        for kind, pad_kind, expected in ((16, 2, 16), (0, 20, 20)):
            with self.subTest(kind=kind):
                data, component, pattern = fixture(kind=kind, pad_kinds=(pad_kind,))
                normalize_objects(data)
                self.assertEqual(pattern['Type'], expected)
                self.assertEqual(component['RefDes_SilkShow'], 2)

    def test_a_single_hole_hides_named_and_user_markings_but_preserves_placement(self):
        data, component, pattern = fixture(holes=1)
        normalize_objects(data)
        self.assertEqual(pattern['Type'], 15)
        self.assertEqual(component['RefDes_SilkShow'], 2)
        self.assertEqual(component['Name_AssyShow'], 2)
        self.assertEqual(component['RefDes_SilkX'], 12)
        user = component.one('UserFields/UserField')
        self.assertEqual((user['SilkShow'], user['AssyShow']), (2, 2))
        self.assertEqual(user.values, ('Order', 'A42', 0))

    def test_invalid_standalone_kind_is_reset_without_hiding_an_ordinary_pattern(self):
        data, component, pattern = fixture(kind=15, holes=2)
        normalize_objects(data)
        self.assertEqual(pattern['Type'], 0)
        self.assertEqual(component['RefDes_SilkShow'], 1)

    def test_electrical_keys_do_not_replace_physical_geometry_markers(self):
        data, _, pattern = fixture(kind=14, pad_kinds=(2,))
        pattern.one('Pads/Pad[2]')['Number_New'] = 9
        normalize_objects(data)
        self.assertEqual(pattern['Type'], 0)


if __name__ == '__main__':
    unittest.main()
