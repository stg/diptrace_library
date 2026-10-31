"""Import reconciles pad declarations without changing their actual settings."""
import math
import unittest

from lib.common.model import Element
from lib.common.footprint_objects import new_pattern, new_pad
from lib.common.footprint_records import TERMINAL
from lib.pcb.formats.assembly.pad_defaults import matches_defaults, normalize_standard_pads
from lib.pcb.formats.assembly.assemble import assemble_core
from lib.pcb.formats.dip.legacy_geometry import rebase_components
from lib.pcb.tests.test_core_assembly import fixture as core_fixture
from lib.pcb.tests.test_legacy_geometry import fixture as rotation_fixture


def fixture():
    board = Element('Board')
    component = board.add('Components').add('Component')
    component.add('Enabled', True)
    component.add('BottomSide', False)
    pattern = component.append(new_pattern('Package'))
    pattern['PadWidth'], pattern['PadHeight'], pattern['PadHole'] = 4, 4, 1
    rows = pattern.one('Pads')
    rows.append(new_pad())
    pad = rows.append(new_pad('1', x=12, y=-9))
    pad['Number_New'], pad['Standard'] = 1, True
    pad['PadWidth_New'], pad['PadHeight_New'], pad['PadHole'] = 4, 4, 1
    rows.append(new_pad())
    return board, component, pattern, pad


def terminal(owner, *, x, angle):
    node = owner.add('PadTerminal', 0)
    for name, value in dict(Type=3, X=x, Y=2, Angle=angle, ShapeWidth=4,
                            ShapeHeight=2, ShapeCorner=0).items():
        node.add(name, value)
    points = node.add('ShapePoints')
    for point in ((1, 0), (2, 1), (1, 2)):
        points.add('pt', *point)
    return node.bind_schema(TERMINAL)


class PadDefaultTests(unittest.TestCase):
    def test_matching_standard_pad_stays_standard_and_custom_is_not_promoted(self):
        board, _, pattern, pad = fixture()
        self.assertTrue(matches_defaults(pattern, pad))
        normalize_standard_pads(board)
        self.assertTrue(pad['Standard'])
        pad['Standard'] = False
        normalize_standard_pads(board)
        self.assertFalse(pad['Standard'])

    def test_explicit_zero_mask_swell_differs_from_inherited_default(self):
        board, _, pattern, pad = fixture()
        pad['CustomSwell_New'] = 0
        before = (pad['X'], pad['Y'], pad['PadWidth_New'], pad['PadHole'])
        normalize_standard_pads(board)
        self.assertFalse(pad['Standard'])
        self.assertEqual(pad['CustomSwell_New'], 0)
        self.assertEqual(pattern['CustomSwell_New'], -1000)
        self.assertEqual((pad['X'], pad['Y'], pad['PadWidth_New'], pad['PadHole']), before)

    def test_inactive_boundary_unassigned_and_fiducial_entries_are_exempt(self):
        for field, value in (('Number_New', 7), ('Number_New', -1), ('PadShape_New', 20)):
            with self.subTest(field=field, value=value):
                board, _, _, pad = fixture()
                pad[field], pad['CustomSwell_New'] = value, 0
                normalize_standard_pads(board)
                self.assertTrue(pad['Standard'])
        board, component, pattern, pad = fixture()
        component.set_field('Enabled', False)
        pad['CustomSwell_New'] = 0
        boundary = pattern.one('Pads').children()[0]
        boundary['Standard'], boundary['Number_New'] = True, 0
        normalize_standard_pads(board)
        self.assertTrue(pad['Standard'])
        self.assertTrue(boundary['Standard'])

    def test_unused_hole_corner_and_disabled_mask_options_are_ignored(self):
        _, _, pattern, pad = fixture()
        pattern['SurfacePad'], pad['SurfacePad'] = True, True
        pad['PadHole'], pad['PadHoleH'], pad['PadHoleType'], pad['PadCorner'] = 5, 9, 1, 25
        for default, own in (('TopMask_State', 'DisableTopMask'), ('BotMask_State', 'DisableBottomMask'),
                             ('TopPaste_State', 'DisableTopPaste'), ('BotPaste_State', 'DisableBottomPaste')):
            pattern[default], pad[own] = 2, 2
        pad['CustomSwell_New'], pad['CustomShrink_New'], pad['PadMask_Percent'] = 1, 2, 99
        self.assertTrue(matches_defaults(pattern, pad))

    def test_used_drill_slot_rectangle_corner_and_segment_options_must_agree(self):
        for name, value, setup in (
                ('PadHole', 2, None),
                ('PadHoleH', 3, 'slot'),
                ('PadCorner', 10, 'rectangle'),
                ('PadMask_Percent', 75, 'segments')):
            with self.subTest(name=name):
                _, _, pattern, pad = fixture()
                if setup == 'slot':
                    pattern['PadHoleType'], pad['PadHoleType'] = 1, 1
                elif setup == 'rectangle':
                    pattern['PadShape'], pad['PadShape_New'] = 2, 2
                elif setup == 'segments':
                    pattern['TopPaste_State'], pad['DisableTopPaste'] = 3, 3
                pad[name] = value
                self.assertFalse(matches_defaults(pattern, pad))

    def test_geometry_and_mask_comparisons_have_distinct_tolerances(self):
        _, _, pattern, pad = fixture()
        pad['PadWidth_New'] = 4.0009
        pattern['CustomSwell_New'], pad['CustomSwell_New'] = 0, .0029
        self.assertTrue(matches_defaults(pattern, pad))
        pad['PadWidth_New'] = 4.0011
        self.assertFalse(matches_defaults(pattern, pad))
        pad['PadWidth_New'], pad['CustomSwell_New'] = 4, .0031
        self.assertFalse(matches_defaults(pattern, pad))

    def test_mirrored_polygon_offset_and_mask_sides_use_a_detached_comparison(self):
        _, _, pattern, pad = fixture()
        pattern['PadShape'], pad['PadShape_New'] = 3, 3
        pattern['PadShape_X'], pad['PadShape_X'] = 1, -1
        for point in ((-2, -1), (2, -1), (2, 1), (-2, 1)):
            pattern.one('PadPoints').add('pt', *point)
            pad.one('PadPoints_New').add('pt', -point[0], point[1])
        pattern['BotMask_State'], pad['DisableTopMask'] = 2, 2
        before = [point.values for point in pattern.select('PadPoints/pt')]
        self.assertTrue(matches_defaults(pattern, pad, mirrored=True))
        self.assertFalse(matches_defaults(pattern, pad))
        self.assertEqual([point.values for point in pattern.select('PadPoints/pt')], before)

    def test_bottom_placement_and_pad_side_together_select_the_comparison_frame(self):
        board, component, pattern, pad = fixture()
        component.set_field('BottomSide', True)
        pattern['PadShape_X'], pad['PadShape_X'] = 1, -1
        normalize_standard_pads(board)
        self.assertTrue(pad['Standard'])
        pad['Sided'] = True
        normalize_standard_pads(board)
        self.assertFalse(pad['Standard'])

    def test_terminal_geometry_mirrors_and_normalizes_angle_without_mutating_defaults(self):
        _, _, pattern, pad = fixture()
        default = terminal(pattern, x=3, angle=math.tau+.2)
        actual = terminal(pad, x=-3, angle=-.2)
        for point in actual.select('ShapePoints/pt'):
            point.set_values(-point.values[0], point.values[1])
        self.assertTrue(matches_defaults(pattern, pad, mirrored=True))
        self.assertAlmostEqual(float(default['Angle']), math.tau+.2)
        actual['Angle'] = -.22
        self.assertFalse(matches_defaults(pattern, pad, mirrored=True))

    def test_rebased_nonround_standard_pad_becomes_custom_but_round_pad_does_not(self):
        for shape, expected in ((2, False), (0, True)):
            with self.subTest(shape=shape):
                decoded, component, pad, _, _, _ = rotation_fixture(degrees=17)
                pattern = component.one('Pattern')
                pattern['PadShape'], pad['PadShape_New'] = shape, shape
                pattern['PadWidth'], pattern['PadHeight'] = 4, 4
                pad['PadWidth_New'], pad['PadHeight_New'], pad['Standard'] = 4, 4, True
                rebase_components(decoded)
                board = Element('Board')
                board.add('Components').append(component)
                normalize_standard_pads(board)
                self.assertEqual(pad['Standard'], expected)

    def test_shared_assembly_normalizes_without_altering_connectivity(self):
        decoded = core_fixture()
        component = decoded.board.one('Components/Component')
        pad = component.one('Pattern/Pads').children()[1]
        pad['Number_New'], pad['Standard'], pad['CustomSwell_New'] = 1, True, 0
        decoded.board.one('Nets/Net/Pads/Item').set_values(41, 1)
        result = assemble_core(decoded)
        self.assertFalse(pad['Standard'])
        self.assertIs(pad['Net'], result.nets[73])
        self.assertIs(result.nets[73].one('Pads/Item')['Pad'], pad)


if __name__ == '__main__':
    unittest.main()
