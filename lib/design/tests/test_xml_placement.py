"""Import modernizes placement; export projects current schematic angles."""
from decimal import Decimal
import math
import unittest
import xml.etree.ElementTree as ET

from lib.design import ExportReport, new_schematic, parse_dch, parse_dchxml
from lib.design.schematic_objects import new_symbol, new_pin, new_symbol_shape
from lib.design.schematic_refs import bind_schematic_references


PART = '/Schematic/Components/Part'


def source(radians):
    document = new_schematic()
    part = document.one('/Schematic/Components').append(new_symbol('Box', 'U1'))
    for name, value in (('X', 10), ('Y', 20), ('Width', 10), ('Height', 6),
                        ('Origin_X', 2.5), ('Origin_Y', -3)):
        part.set_field(name, value)
    pin = part.one('Pins').append(new_pin())
    pin.set_values(0, 3, 4)
    shape = part.one('Shapes').append(new_symbol_shape())
    shape.set_field('Type', 4)
    for point in ((-2, -1), (3, 4)):
        shape.one('Points_New').add('pt', *point)
    bind_schematic_references(document)
    tree = ET.fromstring(document.to_dchxml_bytes(report=ExportReport()))
    tree.find('Schematic/Components/Part').set('Angle', str(radians))
    return parse_dchxml(ET.tostring(tree)).as_schematic()


def geometry(document):
    part = document.one(PART)
    pin = part.one('Pins/Pin')
    return (part.scalar('Width'), part.scalar('Height'), part.scalar('Origin_X'),
            part.scalar('Origin_Y'), pin.values[1:], pin.scalar('Orientation'),
            tuple(point.values for shape in part.select('Shapes/Shape')
                  if shape.scalar('MarkingGenerated') not in (True, 'Y')
                  for point in shape.select('Points_New/pt')))


def binary_precision(values):
    return tuple(binary_precision(value) if isinstance(value, tuple) else
                 Decimal(str(value)).quantize(Decimal('.0001')) for value in values)


class XmlPlacementTests(unittest.TestCase):
    def test_positive_angles_use_discrete_placement_and_survive_xml_cycles(self):
        for degrees, expected in ((10, 90), (45, 90), (135, 180), (225, 270),
                                  (450, 90), (720, 0)):
            with self.subTest(degrees=degrees):
                radians = Decimal(str(math.radians(degrees)))
                current = source(radians)
                expected_geometry = geometry(source(math.radians(expected)))
                for _ in range(3):
                    self.assertEqual(current.one(PART).scalar('Angle'), expected)
                    self.assertEqual(geometry(current), expected_geometry)
                    xml = current.as_dchxml(report=ExportReport())
                    self.assertAlmostEqual(float(xml.one('/Source/Schematic/Components/Part').scalar('Angle', 0)), math.radians(expected))
                    self.assertEqual(current.select(PART+'/StoredData/AngleRadians'), [])
                    self.assertEqual(current.select(PART+'/StoredData/PlacementAngleRadians'), [])
                    self.assertFalse(current.root.changed)
                    current = xml.as_schematic()

    def test_negative_and_small_imported_angles_normalize_only_on_export(self):
        baseline = geometry(source(0))
        for angle in (Decimal('-.7854'), Decimal('-12.5664'), Decimal('.0001')):
            with self.subTest(angle=angle):
                current = source(angle)
                self.assertEqual(geometry(current), baseline)
                self.assertAlmostEqual(float(current.one(PART).scalar('Angle')), math.degrees(float(angle)))
                expected = round((math.degrees(float(angle)) % 360)/90) % 4
                for _ in range(3):
                    xml = current.as_dchxml(report=ExportReport())
                    self.assertAlmostEqual(float(xml.one('/Source/Schematic/Components/Part').scalar('Angle', 0)), expected*math.pi/2)
                    self.assertEqual(geometry(xml.as_schematic()), baseline)
                self.assertAlmostEqual(float(current.one(PART).scalar('Angle')), math.degrees(float(angle)))
                self.assertFalse(current.root.changed)

    def test_binary_output_uses_resolved_angle_without_source_backups(self):
        current = source(Decimal('.7854'))
        report = ExportReport()
        output = parse_dch(current.to_dch_bytes(report=report))
        self.assertAlmostEqual(float(output.one(PART).scalar('Angle')), 90, places=3)
        self.assertEqual(binary_precision(geometry(output)), binary_precision(geometry(current)))
        self.assertEqual(current.select(PART+'/StoredData/AngleRadians'), [])
        self.assertFalse(current.root.changed)
        current.one(PART).set_field('Angle', 180)
        angle = current.as_dchxml(report=ExportReport()).one('/Source/Schematic/Components/Part').scalar('Angle')
        self.assertAlmostEqual(float(angle), math.pi)

    def test_nonterminating_placement_is_rejected_with_a_bounded_error(self):
        with self.assertRaisesRegex(ValueError, 'no terminating discrete placement'):
            source(math.radians(315))


if __name__ == '__main__':
    unittest.main()
