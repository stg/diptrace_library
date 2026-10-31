"""Legacy placement/frame upgrades preserve current typed geometry."""
from types import SimpleNamespace
import math
import unittest

from lib.common.model import Element
from lib.common.footprint_objects import new_pattern, new_pad, new_pattern_drawing
from lib.common.footprint_geometry import legacy_pad_outline
from lib.pcb.formats.dip.legacy_geometry import rebase_components


def fixture(*, degrees=0, angle=0, flipped=False, horizontal_flip=False, version=46, kind=0):
    component = Element('Component')
    component.add('Angle', angle)
    component.add('Flipped', flipped)
    component.add('HorizontalFlip', horizontal_flip)
    pattern = component.append(new_pattern('Package'))
    pattern['Type'] = kind
    pattern['OriginX'], pattern['OriginY'] = 3, 4
    pads = pattern.one('Pads')
    for key in (-1, 1, -1):
        pad = pads.append(new_pad(x=1, y=0))
        pad['Number_New'] = key
        pad['PadWidth_New'], pad['PadHeight_New'] = 4, 2
        pad['PadShape_New'] = 3
        for point in ((-2, -1), (2, -1), (2, 1), (-2, 1)):
            pad.one('PadPoints_New').add('pt', *point)
    shapes = pattern.one('Shapes')
    shapes.append(new_pattern_drawing())
    shape = shapes.append(new_pattern_drawing(kind=8))
    for point in ((1, 0), (2, 0), (1, 1)):
        shape.one('Points_New').add('pt', *point)
    shapes.append(new_pattern_drawing())
    holes = pattern.one('Holes')
    holes.add('Hole', False, False, 0, 0, 0, 0)
    hole = holes.add('Hole', True, False, 2, 0, 1, 1)
    holes.add('Hole', False, False, 0, 0, 0, 0)
    dimension = pattern.one('Dimensions').add('Dimension')
    for name, value in dict(Enabled=True, Type=0, X1=1, Y1=0, X2=2, Y2=0, XD=1, YD=1).items():
        dimension.add(name, value)
    decoded = SimpleNamespace(header=SimpleNamespace(version=version),
        upgrades=SimpleNamespace(components=(SimpleNamespace(component=component,
            legacy_field_bindings=(-1, -1, degrees)),)))
    return decoded, component, pads.children()[1], shape, hole, dimension


class LegacyGeometryTests(unittest.TestCase):
    def test_extra_rotation_is_owned_by_placement_and_removed_from_local_geometry(self):
        decoded, component, pad, shape, hole, dimension = fixture(degrees=90)
        rebase_components(decoded)
        self.assertEqual(float(component['Angle']), math.pi/2)
        self.assertEqual((pad['X'], pad['Y']), (0, 1))
        self.assertEqual([point.values for point in pad.one('PadPoints_New').children()],
                         [(1, -2), (1, 2), (-1, 2), (-1, -2)])
        self.assertEqual((pad['PadWidth_New'], pad['PadHeight_New']), (2, 4))
        self.assertEqual(shape.one('Points_New/pt[1]').values, (0, 1))
        self.assertEqual(hole.values[2:4], (0, 2))
        self.assertEqual((dimension['Type'], dimension['X1'], dimension['Y1']), (2, 0, 1))
        self.assertEqual((component.one('Pattern')['OriginX'], component.one('Pattern')['OriginY']), (-4, 3))

    def test_polygon_orientation_uses_geometry_marker_and_saved_quarter_turn(self):
        decoded, _, pad, _, _, _ = fixture(angle=math.pi)
        rebase_components(decoded)
        self.assertEqual(pad.one('PadPoints_New/pt[1]').values, (2, 1))
        decoded, _, pad, _, _, _ = fixture(angle=3*math.pi/2)
        pad['PadAngle'] = math.pi/2
        rebase_components(decoded)
        self.assertEqual(pad.one('PadPoints_New/pt[1]').values, (-2, -1))
        decoded, _, pad, _, _, _ = fixture(degrees=90)
        pad['Number_New'] = 7  # An electrical key is not this physical geometry marker.
        rebase_components(decoded)
        self.assertEqual((pad['X'], pad['Y']), (1, 0))

    def test_old_horizontal_flip_frame_has_an_explicit_type_boundary(self):
        for kind, expected_angle, expected_x in ((0, math.pi, -1), (13, math.pi, -1), (14, 0, 1)):
            with self.subTest(kind=kind):
                decoded, component, pad, _, _, _ = fixture(horizontal_flip=True, kind=kind)
                rebase_components(decoded)
                self.assertEqual(float(component['Angle']), expected_angle)
                self.assertEqual(pad['X'], expected_x)
                self.assertEqual(component['Flipped'], kind < 14)
                self.assertEqual(component['HorizontalFlip'], kind >= 14)

        decoded, component, _, _, _, _ = fixture(flipped=True, horizontal_flip=True)
        rebase_components(decoded)
        self.assertFalse(component['Flipped'])
        self.assertFalse(component['HorizontalFlip'])

    def test_sided_flip_alone_does_not_rotate_the_local_frame(self):
        decoded, component, pad, _, _, _ = fixture(flipped=True, angle=math.pi/2)
        rebase_components(decoded)
        self.assertEqual(float(component['Angle']), math.pi/2)
        self.assertEqual((pad['X'], pad['Y']), (1, 0))

    def test_horizontal_flip_text_keeps_anchor_alignment_and_changes_paragraph_alignment(self):
        decoded, _, _, shape, _, _ = fixture(horizontal_flip=True)
        shape['Type'] = 7
        shape['TextAngle'] = .2
        shape['TextHorz'], shape['TextVert'], shape['TextAlign'] = -1, 1, -1
        for point in shape.select('Points_New/pt')[1:]:
            point.detach()
        rebase_components(decoded)
        self.assertEqual(shape.one('Points_New/pt').values, (-1, 0))
        self.assertAlmostEqual(float(shape['TextAngle']), math.pi+.2)
        self.assertEqual((shape['TextHorz'], shape['TextVert'], shape['TextAlign']), (-1, 1, 1))

    def test_current_geometry_is_not_rebased_again(self):
        decoded, component, pad, shape, hole, dimension = fixture(degrees=90, horizontal_flip=True, version=47)
        before = component.clone()
        rebase_components(decoded)
        self.assertEqual(component.values, before.values)
        self.assertEqual((pad['X'], pad['Y']), (1, 0))
        self.assertEqual(hole.values[2:4], (2, 0))
        self.assertEqual(dimension['Type'], 0)

    def test_near_circular_drawing_keeps_axis_aligned_radius_after_rebasing(self):
        decoded, _, _, shape, _, _ = fixture(degrees=90)
        shape['Type'] = 3
        points = shape.one('Points_New')
        for point in tuple(points.children()):
            point.detach()
        points.add('pt', 1, 2)
        points.add('pt', 3, 4)
        rebase_components(decoded)
        self.assertEqual([point.values for point in points.children()], [(-4, 1), (-2, 3)])

    def test_basic_pad_outline_shapes_have_observable_contours(self):
        ellipse = legacy_pad_outline(0, 6, 2)
        self.assertEqual(len(ellipse), 20)
        self.assertEqual(ellipse[0], (3, 0))
        for width, height in ((6, 2), (2, 6)):
            oval = legacy_pad_outline(1, width, height)
            self.assertEqual(len(oval), 16)
            self.assertAlmostEqual(max(x for x, y in oval)-min(x for x, y in oval),
                                   width if height > width else width-2+2*math.cos(math.pi/14))
        self.assertEqual(legacy_pad_outline(2, 4, 2), ((-2, -1), (2, -1), (2, 1), (-2, 1)))
        self.assertEqual(len(legacy_pad_outline(4, 2, 4)), 15)


if __name__ == '__main__':
    unittest.main()
