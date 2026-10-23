"""Legacy output coordinates derive from current geometry on a detached view."""
import unittest

from lib.design import ExportReport, new_schematic, parse_asc, parse_dch
from lib.design.schematic_objects import new_pattern_shape, new_symbol
from lib.design.schematic_refs import bind_schematic_references
from lib.design.dch_binary import Cursor


def sample():
    document = new_schematic()
    part = document.one('/Schematic/Components').append(new_symbol('Tiny frame', 'U1'))
    pattern = part.one('Pattern')
    pattern.set_field('Width', .0001)
    pattern.set_field('Height', .0001)
    drawing = pattern.one('Shapes').insert(new_pattern_shape(1, kind=7), 1)
    drawing.one('Points_New').add('pt', -20, -30)
    slot = document.one('/Schematic/CacheLib/Slots').add('Slot', 0, '')
    slot.add('VariablePath', '')
    definition = slot.add('Definition', 0)
    definition.append(new_symbol('Cached frame', '', placed=False))
    definition.append(pattern.clone())
    bind_schematic_references(document)
    raw = parse_asc(document.to_asc_bytes().decode('cp1252'))
    placed = raw.one('/Schematic/Components/Part/Pattern')
    cached = raw.one('/Schematic/CacheLib/cl_Components/cl_Component/cl_Pattern')
    for prefix, owner in (('', placed), ('cl_', cached)):
        owner.one(prefix+'Width').set_values(.0001)
        owner.one(prefix+'Height').set_values(.0001)
        shape = owner.one(prefix+'Shapes/'+prefix+'Shape[2]')
        for index, value in enumerate((-200000, -300000, 0, 0, 0, 0), 3):
            shape.set_argument(index, value)
        points = owner.one(prefix+'Shapes/'+('cl_Point' if prefix else 'Points'))
        for point, values in zip(points.children(), ((-200000, -300000),)):
            point.set_values(*values)
    return raw.as_schematic()


def drawing(document):
    return document.one('/Schematic/Components/Part/Pattern/Shapes/Shape[2]')


def header(data, document):
    cursor = Cursor(data)
    cursor.pos = drawing(document).one('Type').source.end
    return tuple(cursor.number() for _ in range(6))


class CompatibilityCoordinateTests(unittest.TestCase):
    def test_import_keeps_current_coordinates_without_redundant_history(self):
        document = sample()
        shape = drawing(document)
        self.assertEqual([point.values for point in shape.select('Points_New/pt')], [(-20, -30)])
        self.assertFalse(shape.select('StoredData/CompatibilityGeometry'))
        self.assertFalse(shape.select('StoredData/CompatibilityPoints'))
        self.assertFalse(document.root.changed)

    def test_binary_export_bounds_only_the_detached_legacy_view(self):
        document = sample()
        before = document.to_asc_bytes()
        report = ExportReport()
        data = document.to_dch_bytes(report=report)
        loaded = parse_dch(data)
        self.assertEqual(header(data, loaded), (-100000, -100000, 0, 0, 0, 0))
        self.assertEqual([point.values for point in drawing(loaded).select('Points_New/pt')], [(-20, -30)])
        notices = [row for row in report.infos if row.rule == 'dch-compatibility-range']
        self.assertEqual(len(notices), 1)
        self.assertTrue(any('/CacheLib' in path for path in notices[0].paths))
        self.assertTrue(any('/Components' in path for path in notices[0].paths))
        self.assertEqual(document.to_asc_bytes(), before)
        self.assertFalse(drawing(document).select('StoredData/CompatibilityGeometry'))
        self.assertFalse(document.root.changed)

    def test_edited_physical_points_rebuild_bounded_compatibility(self):
        document = sample()
        drawing(document).one('Points_New/pt[1]').set_values(-40, -50)
        data = document.to_dch_bytes(report=ExportReport())
        loaded = parse_dch(data)
        self.assertEqual(drawing(loaded).one('Points_New/pt[1]').values, (-40, -50))
        self.assertEqual(header(data, loaded), (-100000, -100000, 0, 0, 0, 0))
        self.assertEqual(drawing(document).one('Points_New/pt[1]').values, (-40, -50))

    def test_physical_coordinates_outside_the_binary_domain_still_fail(self):
        document = sample()
        drawing(document).one('Points_New/pt[1]').set_values(200000, 0)
        report = ExportReport()
        with self.assertRaisesRegex(ValueError, 'finite value'):
            document.to_dch_bytes(report=report)
        self.assertEqual(len(report.errors), 1)
        self.assertEqual(drawing(document).one('Points_New/pt[1]').values, (200000, 0))


if __name__ == '__main__':
    unittest.main()
