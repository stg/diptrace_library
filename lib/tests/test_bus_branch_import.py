"""Canceled branches must not make an otherwise usable bus unreadable."""
import unittest
import xml.etree.ElementTree as ET

from lib import ConversionReport, Index, new_schematic, parse
from lib.schematic.editing.route_normalization import normalize_imported_routes
from lib.tests.test_route_import import encode


BUS = '/Schematic/Buses/Bus'


def source(*, broken=False, enabled=True, incoming=False):
    root = ET.fromstring(new_schematic().to_dchxml_bytes())
    schematic = root.find('Schematic')
    schematic.append(ET.fromstring('<Nets><Net Id="0" NetClass="0"><Name>Signal</Name></Net></Nets>'))
    schematic.append(ET.fromstring('''<BusConnectors><BusConnector Id="0" Sheet="0"
        X="0" Y="0" Connected="Y"><Name>Port</Name></BusConnector></BusConnectors>'''))
    bus = ET.SubElement(ET.SubElement(schematic, 'Buses'), 'Bus', Id='0', Enabled='Y' if enabled else 'N')
    ET.SubElement(bus, 'Name').text = 'DATA'
    ET.SubElement(ET.SubElement(bus, 'Nets'), 'Net', NetId='0', ConnectionNumber='7')
    wires = ET.SubElement(bus, 'Wires')
    for index in range(4):
        wire = ET.SubElement(wires, 'Wire', Id=str(index), Sheet='0',
                             Connected1='Bus Connector', Object1='0', Connected2='Free')
        if broken and index in (2, 3):
            wire.set('Connected2', 'Bus Wire')
            wire.set('Object2', '1')
            wire.set('SubObject2', '1')
        points = ET.SubElement(wire, 'Points')
        ET.SubElement(points, 'Point', X='0', Y='0', Dir='-1')
        if index == 0 or not broken or incoming and index in (2, 3):
            ET.SubElement(points, 'Point', X=str(10+index), Y='0', Dir='0')
    return ET.tostring(root)


class BusBranchImportTests(unittest.TestCase):
    def test_xml_removes_closed_canceled_branches_before_checking_references(self):
        report = ConversionReport()
        current = parse(source(broken=True), report=report)
        self.assertEqual(len(current.select(BUS+'/Lines/Line')), 1)
        self.assertEqual([p.values for p in current.select(BUS+'/Nets/pt')], [(0,)])
        self.assertEqual([p.values for p in current.select(BUS+'/Numbers/pt')], [(7,)])
        self.assertFalse(current.references.issues)
        self.assertIn('bus-modernization', [n.rule for n in report.notices])
        self.assertFalse(report.warnings)
        current.validate()

    def test_free_branches_modernize_across_formats_without_changing_export_source(self):
        original = parse(source())
        for line in original.select(BUS+'/Lines/Line')[1:]:
            line.one('Points/pt[2]').detach()
        retained = [point.values for point in original.select(BUS+'/Lines/Line[1]/Points/pt')]
        for destination in ('dch', 'asc', 'dchxml'):
            with self.subTest(destination=destination):
                current = parse(encode(original, destination), format=destination)
                for _ in range(3):
                    self.assertEqual(len(current.select(BUS+'/Lines/Line')), 1)
                    self.assertEqual([point.values for point in current.select(BUS+'/Lines/Line/Points/pt')], retained)
                    self.assertEqual(current.one(BUS+'/Nets/pt').values, (0,))
                    self.assertEqual(normalize_imported_routes(current), 0)
                    self.assertFalse(current.references.issues)
                    current.validate()
                    current = parse(encode(current, destination), format=destination)
        self.assertEqual(len(original.select(BUS+'/Lines/Line')), 4)
        self.assertEqual(len(original.select(BUS+'/Lines/Line/Points/pt')), 5)
        original.validate()

    def test_external_identity_and_unknown_constraints_keep_the_branch_set(self):
        for unknown in (False, True):
            with self.subTest(unknown=unknown):
                current = parse(source())
                line = current.one(BUS+'/Lines/Line[2]')
                line.one('Points/pt[2]').detach()
                consumer = current.root.add('Consumer', 99)
                if unknown:
                    current.references.note(consumer, 'unknown route consumer', Index(consumer),
                                            collections=(line.parent,))
                else:
                    current.references.bind(consumer, line, Index(consumer), role='test-bus-branch')
                self.assertEqual(normalize_imported_routes(current), 0)
                self.assertEqual(len(current.select(BUS+'/Lines/Line')), 4)
                current.validate()

    def test_retained_incoming_routes_are_not_deleted_to_hide_a_missing_segment(self):
        with self.assertRaisesRegex(ValueError, 'bus-wire-segment-2'):
            parse(source(broken=True, incoming=True))

    def test_disabled_branch_geometry_remains(self):
        current = parse(source(enabled=False))
        line = current.one(BUS+'/Lines/Line[2]')
        line.one('Points/pt[2]').detach()
        self.assertEqual(normalize_imported_routes(current), 0)
        self.assertEqual(len(current.select(BUS+'/Lines/Line')), 4)
        current.validate()

    def test_retained_bus_wire_links_follow_renumbering_after_removed_branches(self):
        root = ET.fromstring(source(broken=True))
        wires = root.find('Schematic/Buses/Bus/Wires')
        wires.append(ET.fromstring('''<Wire Id="4" Sheet="0" Connected1="Free" Connected2="Free">
            <Points><Point X="20" Y="0" Dir="-1"/><Point X="30" Y="0" Dir="0"/></Points></Wire>'''))
        root.find('Schematic/Nets/Net').append(ET.fromstring('''<Wires><Wire Id="0" Sheet="0"
            Connected1="Bus" Bus1="0" Object1="4" SubObject1="1" Connected2="Free">
            <Points><Point X="25" Y="0" Dir="-1"/><Point X="25" Y="5" Dir="1"/></Points>
            </Wire></Wires>'''))
        current = parse(ET.tostring(root))
        self.assertEqual([line.scalar('Number') for line in current.select(BUS+'/Lines/Line')], [0, 1])
        route = current.one('/Schematic/Nets/Net/Lines/Line')
        self.assertEqual(route.scalar('Connect1'), 1)
        reference = next(r for r in current.references.outgoing(route) if r.role == 'wire-bus-segment-1')
        self.assertIs(reference.target.start.parent.parent, current.one(BUS+'/Lines/Line[2]'))
        for destination in ('dch', 'asc', 'dchxml'):
            with self.subTest(destination=destination):
                repeated = parse(encode(current, destination))
                repeated.validate()
                self.assertFalse(repeated.references.issues)
                self.assertEqual(repeated.one('/Schematic/Nets/Net/Lines/Line').scalar('Connect1'), 1)


if __name__ == '__main__':
    unittest.main()
