"""Sheet text has one current anchor after source geometry modernization."""
from decimal import Decimal
import unittest

from lib import ConversionReport, new_schematic, parse, serialize
from lib.common.model import Element
from lib.schematic.formats.dch.legacy_drawings import expand_symbol_drawings
from lib.schematic.model.drawing_data import normalize_drawings
from lib.schematic.model.objects import new_schematic_shape, new_symbol, new_symbol_shape


POSITIONS = tuple((Decimal(x), Decimal(y)) for x, y in (
    ('10.125', '20.375'), ('30.125', '40.375'), ('50.125', '60.375')))


def add_points(shape, positions=POSITIONS):
    for position in positions:
        shape.one('Points_New').add('pt', *position)


class SheetTextAnchorTests(unittest.TestCase):
    def test_all_formats_import_the_anchor_without_surplus_bounds(self):
        document = new_schematic()
        shape = document.one('/Schematic/Shapes').append(new_schematic_shape())
        shape['Type'], shape['TextAngle'] = 10, 0
        shape.one('TextLine').add('pt', 'A sheet note')
        add_points(shape)
        for format in ('dch', 'asc', 'dchxml'):
            with self.subTest(format=format):
                data = serialize(document, format=format, report=ConversionReport())
                self.assertEqual([p.values for p in shape.select('Points_New/pt')], list(POSITIONS))
                report = ConversionReport()
                restored = parse(data, format=format, report=report)
                current = restored.one('/Schematic/Shapes/Shape')
                self.assertEqual([p.values for p in current.select('Points_New/pt')], [POSITIONS[0]])
                self.assertEqual(current.one('TextLine/pt').values, ('A sheet note',))
                self.assertEqual(len([n for n in report.infos if n.rule == 'sheet-text-anchor']), 1)
                again_report = ConversionReport()
                again = parse(serialize(restored, format=format, report=ConversionReport()),
                              format=format, report=again_report)
                self.assertEqual(again.one('/Schematic/Shapes/Shape/Points_New/pt').values, POSITIONS[0])
                self.assertFalse(any(n.rule == 'sheet-text-anchor' for n in again_report.notices))

    def test_geometry_and_component_drawings_retain_their_points(self):
        document = new_schematic()
        schematic = document.one('/Schematic')
        outline = schematic.one('Shapes').append(new_schematic_shape())
        outline['Type'] = 8
        add_points(outline)
        component = schematic.one('Components').append(new_symbol('Part', 'U1'))
        text = component.one('Shapes').append(new_symbol_shape())
        text['Type'] = 10
        add_points(text)
        normalize_drawings(schematic)
        for shape in (outline, text):
            self.assertEqual([p.values for p in shape.select('Points_New/pt')], list(POSITIONS))

    def test_legacy_orientation_chooses_the_anchor_before_cleanup(self):
        schematic = Element('Schematic')
        schematic.add('Components')
        shape = schematic.add('Shapes').add('Shape', 0)
        shape.add('Type', 10)
        shape.add('StoredData').add('Orientation', 1)
        geometry = shape.add('Points')
        geometry.add('pt', 1, 2)
        geometry.add('pt', 5, 7)
        expand_symbol_drawings(39, schematic)
        normalize_drawings(schematic)
        self.assertEqual(shape.one('Points_New/pt').values, (1, 7))

    def test_empty_geometry_stays_empty_and_cleanup_is_idempotent(self):
        document = new_schematic()
        schematic = document.one('/Schematic')
        empty = schematic.one('Shapes').append(new_schematic_shape())
        empty['Type'] = 10
        text = schematic.one('Shapes').append(new_schematic_shape(1))
        text['Type'] = 10
        add_points(text)
        normalize_drawings(schematic)
        normalize_drawings(schematic)
        self.assertFalse(empty.select('Points_New/pt'))
        self.assertEqual([p.values for p in text.select('Points_New/pt')], [POSITIONS[0]])


if __name__ == '__main__':
    unittest.main()
