"""All schematic writers project angles without changing current model facts."""
import math
import unittest

from lib import ExportReport, new_schematic, parse_dch
from lib.schematic.model.angles import (quarter_turns)
from lib.schematic.model.objects import (new_symbol, new_schematic_shape)
from lib.schematic.model.refs import (bind_schematic_references)


class AngleExportTests(unittest.TestCase):
    def test_turn_normalization_and_nearest_quarter(self):
        for angle, expected in ((-810, 3), (-90, 3), (0, 0), (44, 0), (45, 0),
                                (46, 1), (135, 2), (225, 2), (315, 0),
                                (359, 0), (360, 0), (450, 1), (801, 1)):
            with self.subTest(angle=angle):
                self.assertEqual(quarter_turns(angle), expected)
                self.assertEqual(quarter_turns(math.radians(angle), full_turn=math.tau), expected)
        for invalid in (math.inf, math.nan):
            with self.assertRaises(ValueError):
                quarter_turns(invalid)

    def test_all_writers_use_current_angles_and_leave_model_unchanged(self):
        for degrees in (-810, -90, 44, 46, 359, 450):
            with self.subTest(degrees=degrees):
                current = new_schematic()
                part = current.one('/Schematic/Components').append(new_symbol('Box', 'U1'))
                part.set_field('Angle', degrees)
                shape = current.one('/Schematic/Shapes').append(new_schematic_shape())
                shape.set_field('Type', 10)
                shape.set_field('TextAngle', math.radians(degrees))
                shape.one('Points_New').add('pt', 0, 0)
                shape.one('TextLine').add('pt', 'Angle')
                bind_schematic_references(current)
                expected = quarter_turns(degrees)
                report = ExportReport()
                asc = current.as_asc(report=report)
                self.assertEqual(asc.one('/Schematic/Components/Part/Angle').values, (expected*90,))
                self.assertEqual(asc.one('/Schematic/Components/Part/Orientation').values, (expected,))
                self.assertIn('schematic-angle-normalization', {notice.rule for notice in report.infos})
                xml = current.as_dchxml(report=ExportReport())
                self.assertAlmostEqual(float(xml.one('/Source/Schematic/Components/Part').scalar('Angle', 0)), expected*math.pi/2)
                self.assertAlmostEqual(float(xml.one('/Source/Schematic/Shapes/Shape').scalar('Angle', 0)), expected*math.pi/2)
                encoded = current.to_dch_bytes(report=ExportReport())
                binary = parse_dch(encoded)
                self.assertAlmostEqual(float(binary.one('/Schematic/Components/Part').scalar('Angle')), expected*90, delta=.003)
                self.assertEqual(binary.to_dch_bytes(report=ExportReport()), encoded)
                self.assertEqual(part.scalar('Angle'), degrees)
                self.assertAlmostEqual(float(shape.scalar('TextAngle')), math.radians(degrees))


if __name__ == '__main__':
    unittest.main()
