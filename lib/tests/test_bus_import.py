"""Canceled bus geometry modernizes without discarding connected design data."""
import unittest
import xml.etree.ElementTree as ET

from lib import ConversionReport, Index, new_schematic, parse
from lib.schematic.editing.route_normalization import normalize_imported_routes
from lib.tests.test_route_import import encode


BUS = '/Schematic/Buses/Bus'


def source(*, enabled=True, logical=False):
    root = ET.fromstring(new_schematic().to_dchxml_bytes())
    schematic = root.find('Schematic')
    if logical:
        schematic.append(ET.fromstring('<Nets><Net Id="0" NetClass="0"><Name>N</Name></Net></Nets>'))
    buses = ET.SubElement(schematic, 'Buses')
    for index in range(3):
        bus = ET.SubElement(buses, 'Bus', Id=str(index), Enabled='Y' if enabled or index != 1 else 'N')
        ET.SubElement(bus, 'Name').text = 'DATA'+str(index)
        if logical and index == 1:
            ET.SubElement(ET.SubElement(bus, 'Nets'), 'Net', NetId='0', ConnectionNumber='7')
        wire = ET.SubElement(ET.SubElement(bus, 'Wires'), 'Wire',
                             Id='0', Sheet='0', Connected1='Free', Connected2='Free')
        points = ET.SubElement(wire, 'Points')
        ET.SubElement(points, 'Point', X='0', Y=str(index), Dir='0')
        ET.SubElement(points, 'Point', X='10', Y=str(index), Dir='0')
    document = parse(ET.tostring(root), format='dchxml')
    # Start with valid geometry, then author the saved state under investigation.
    document.one(BUS+'[2]/Lines/Line/Points/pt[2]').detach()
    return document


class BusImportTests(unittest.TestCase):
    def test_all_formats_remove_the_same_isolated_stub_without_ordinary_net_wires(self):
        original = source()
        for destination in ('dch', 'asc', 'dchxml'):
            with self.subTest(destination=destination):
                report = ConversionReport()
                current = parse(encode(original, destination), format=destination, report=report)
                self.assertEqual([bus.values[0] for bus in current.select(BUS)], ['DATA0', 'DATA2'])
                self.assertEqual([bus.scalar('Number') for bus in current.select(BUS)], [0, 1])
                self.assertIn('bus-modernization', [notice.rule for notice in report.notices])
                self.assertFalse(report.warnings)
                for _ in range(3):
                    current.validate()
                    self.assertEqual(current.references.issues, [])
                    self.assertEqual(normalize_imported_routes(current), 0)
                    current = parse(encode(current, destination), format=destination)
                    self.assertEqual([bus.values[0] for bus in current.select(BUS)], ['DATA0', 'DATA2'])
        self.assertEqual(len(original.select(BUS)), 3)
        self.assertEqual(len(original.select(BUS+'[2]/Lines/Line/Points/pt')), 1)
        original.validate()

    def test_binary_and_asc_discard_stale_connection_numbers_with_the_canceled_bus(self):
        original = source()
        numbers = original.one(BUS+'[2]/Numbers')
        for number in (2, 1, 3, 4):
            numbers.add('pt', number)
        for destination in ('dch', 'asc'):
            with self.subTest(destination=destination):
                current = parse(encode(original, destination), format=destination)
                self.assertEqual(len(current.select(BUS)), 2)
                current.to_dchxml_bytes(report=ConversionReport())
        self.assertEqual([point.values[0] for point in numbers.children('pt')], [2, 1, 3, 4])

    def test_memberships_disabled_buses_and_two_point_geometry_remain(self):
        for case in ('membership', 'disabled', 'two-points', 'coincident', 'no-points'):
            with self.subTest(case=case):
                current = source(enabled=case != 'disabled', logical=case == 'membership')
                points = current.one(BUS+'[2]/Lines/Line/Points')
                if case in ('two-points', 'coincident'):
                    points.add('pt', 0 if case == 'coincident' else 30, -3, 0)
                    if case == 'coincident':
                        points.children('pt')[1].set_values(*points.children('pt')[0].values)
                elif case == 'no-points':
                    points.children('pt')[0].detach()
                expected = [point.values for point in points.children('pt')]
                self.assertEqual(normalize_imported_routes(current), 0)
                self.assertEqual(len(current.select(BUS)), 3)
                self.assertEqual([point.values for point in points.children('pt')], expected)
                current.validate()

    def test_external_identity_reference_keeps_the_stub_and_its_bus(self):
        current = source()
        bus = current.one(BUS+'[2]')
        consumer = current.root.add('BusConsumer', 1)
        reference = current.references.bind(consumer, bus, Index(consumer), role='test-bus-owner')
        self.assertEqual(normalize_imported_routes(current), 0)
        self.assertIs(current.references.get(reference.uid).target, bus)
        self.assertEqual(len(current.select(BUS)), 3)
        current.validate()

    def test_unresolved_bus_scope_defers_removal(self):
        current = source()
        consumer = current.root.add('UnknownBus', 99)
        current.references.note(consumer, 'unknown bus', Index(consumer),
                                collections=(current.one('/Schematic/Buses'),))
        self.assertEqual(normalize_imported_routes(current), 0)
        self.assertEqual(len(current.select(BUS)), 3)
        self.assertEqual(len(current.references.issues), 1)
        current.validate()


if __name__ == '__main__':
    unittest.main()
