"""Pad styles retain independent geometry settings and their XML defaults."""
from decimal import Decimal
import unittest

from lib.common.footprint_objects import new_pad, new_pattern
from lib.common.model import Element
from lib.common.units import XmlUnits
from lib.common.xml_pad_output import project_pad_style
from lib.common.xml_pads import read_pad_style
from lib.common.xml_records import XmlRecord


class XmlPadGeometryTests(unittest.TestCase):
    def test_default_and_individual_styles_keep_inactive_shape_settings(self):
        for constructor, shape_name, points_name in (
                (new_pattern, 'PadShape', 'PadPoints'),
                (new_pad, 'PadShape_New', 'PadPoints_New')):
            for surface in (False, True):
                for shape in (0, 1, 2, 3, 4, 5, 10, 20):
                    with self.subTest(owner=constructor.__name__, surface=surface, shape=shape):
                        source = constructor('Example')
                        source[shape_name], source['SurfacePad'] = shape, surface
                        source['PadCorner'] = Decimal('12.5')
                        source['PadShape_X'], source['PadShape_Y'] = 3, -6
                        points = ((0, 0), (3, 0), (3, 6))
                        for point in points:
                            source.one(points_name).add('pt', *point)
                        xml = project_pad_style(source, name='Example', units=XmlUnits('mm'))
                        current = constructor('Example')
                        read_pad_style(XmlRecord(xml), current, units=XmlUnits('mm'))
                        self.assertEqual((current[shape_name], current['SurfacePad']), (shape, surface))
                        self.assertEqual(current['PadCorner'], Decimal('12.5'))
                        self.assertEqual((current['PadShape_X'], current['PadShape_Y']), (3, -6))
                        self.assertEqual(tuple(row.values for row in current.select(points_name+'/pt')), points)
                        # Selecting the stored polygon later uses the same authored vertices.
                        current[shape_name] = 3
                        self.assertEqual(tuple(row.values for row in current.select(points_name+'/pt')), points)

    def test_terminals_keep_inactive_corner_and_polygon_settings(self):
        for shape in (0, 1, 2, 3, 4):
            with self.subTest(shape=shape):
                source = new_pad('1')
                terminal = source.add('PadTerminal', 0)
                for name, value in dict(Type=shape, X=3, Y=6, Angle=0,
                        ShapeWidth=9, ShapeHeight=12, ShapeCorner=Decimal('7.5')).items():
                    terminal.set_field(name, value)
                points = terminal.add('ShapePoints')
                for point in ((0, 0), (3, 0), (0, 6)):
                    points.add('pt', *point)
                xml = project_pad_style(source, name='Example', units=XmlUnits('mm'))
                current = new_pad('1')
                read_pad_style(XmlRecord(xml), current, units=XmlUnits('mm'))
                actual = current.one('PadTerminal')
                self.assertEqual((actual['Type'], actual['ShapeCorner']), (shape, Decimal('7.5')))
                self.assertEqual(tuple(row.values for row in actual.select('ShapePoints/pt')),
                                 ((0, 0), (3, 0), (0, 6)))

    def test_missing_hole_height_inherits_width_while_explicit_zero_remains_zero(self):
        for kind in ('Surface', 'Through'):
            for height, expected in ((None, Decimal('3.75')), (0, 0), (Decimal('.7'), Decimal('2.1'))):
                with self.subTest(kind=kind, height=height):
                    source = Element('PadStyle')
                    source.add('Name', 'Pad')
                    source.add('Type', kind)
                    source.add('Hole', Decimal('1.25'))
                    if height is not None:
                        source.add('HoleH', height)
                    stack = source.add('MainStack')
                    stack.add('Width', 2)
                    stack.add('Height', 3)
                    target = new_pattern('Package')
                    read_pad_style(XmlRecord(source), target, units=XmlUnits('mm'))
                    self.assertEqual(target['PadHole'], Decimal('3.75'))
                    self.assertEqual(target['PadHoleH'], expected)
                    self.assertEqual(target['SurfacePad'], kind == 'Surface')


if __name__ == '__main__':
    unittest.main()
