"""Bus attachments are data references, independently of coordinated editing."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from lib.design import Document, ReferenceError, Segment
from lib.design.schematic_refs import bind_schematic_references, connectivity_mismatches


def bus_document(connector_bus_number=9, *, join_bus_number=9, join_segment=1, source_format=None,
                 route_points=2, clamp_segments=False):
    doc = Document()
    if source_format is not None:
        doc.metadata['source_format'] = source_format
    doc.root.add('Source', 'DipTrace-Schematic', 46)
    schematic = doc.root.add('Schematic')
    schematic.add('Pages').add('Page', 'sheet')
    part = schematic.add('Components').add('Part', 'TEST', 'U1')
    part.add('Number', 8)
    part.add('Pins').add('Pin', 0, 5, 5).add('NetNumber', 3)
    net = schematic.add('Nets').add('Net', 'signal')
    net.add('Number', 3)
    net.add('Parts').add('pt', 8, 0)
    wire = net.add('Lines').add('Line')
    for name, value in (('Number', 0), ('NetNumber', 3), ('ConnectMode1', 0),
                        ('Connect1', 8), ('ConnectL1', 0), ('ConnectB1', -1),
                        ('ConnectMode2', 3), ('Connect2', 5), ('ConnectL2', 1), ('ConnectB2', 9)):
        wire.add(name, value)
    points = wire.add('Points')
    points.add('pt', 5, 5, 0)
    points.add('pt', 5, 0, 0)
    connectors = schematic.add('PageConnectors')
    connector = connectors.add('PageConnector', 'connector', 0, 0)
    for name, value in (('Number', 12), ('Connected', True), ('BusNumber', connector_bus_number), ('Page', 0)):
        connector.add(name, value)
    other_connector = connectors.add('PageConnector', 'free', 20, 20)
    other_connector.add('Number', 22)
    other_connector.add('Connected', False)
    other_connector.add('BusNumber', 999)  # Unused, retained data.
    buses = schematic.add('Buses')
    bus = buses.add('Bus', 'bus')
    bus.add('Number', 9)
    bus.add('Nets').add('pt', 3)
    lines = bus.add('Lines')
    route = lines.add('Line')
    for name, value in (('Number', 5), ('BusNumber', 9), ('ConnectMode1', 4),
                        ('Connect1', 12), ('ConnectL1', -1), ('ConnectB1', -1),
                        ('ConnectMode2', 0), ('Connect2', 999)):
        route.add(name, value)
    points = route.add('Points')
    points.add('pt', 0, 0, 0)
    if route_points > 1:
        points.add('pt', 10, 0, 0)
    join = lines.add('Line')
    for name, value in (('Number', 7), ('BusNumber', 9), ('ConnectMode1', 2),
                        ('Connect1', 5), ('ConnectL1', join_segment), ('ConnectB1', join_bus_number)):
        join.add(name, value)
    points = join.add('Points')
    points.add('pt', 7, 0, 0)
    points.add('pt', 7, 10, 0)
    bus.add('ActiveLine', 7)
    bus.add('ActivePoint', 1)
    other_bus = buses.add('Bus', 'other')
    other_bus.add('Number', 4)
    bind_schematic_references(doc, clamp_segments=clamp_segments)
    return doc, wire, bus, route, join, connector, other_bus


class BusReferenceTests(unittest.TestCase):
    def test_one_point_target_keeps_its_links_scoped_and_unresolved(self):
        doc, wire, bus, route, join, *_ = bus_document(route_points=1)
        self.assertEqual(len(doc.references.issues), 2)
        doc.one('/Schematic/Components').add('Part', 'Spare', 'U2').add('Number', 1)
        bind_schematic_references(doc)
        doc.rebuild()
        self.assertEqual(join.scalar('ConnectL1'), 1)
        self.assertEqual(wire.scalar('ConnectL2'), 1)
        self.assertEqual(len(doc.references.issues), 2)
        route.one('Points').add('pt', 10, 0, 0)
        with self.assertRaisesRegex(ReferenceError, 'unresolved references'):
            doc.rebuild()

    def test_bus_join_uses_its_owner_and_projects_the_current_number(self):
        for old in (-1,4,999):
            doc, _, bus, route, join, *_ = bus_document(join_bus_number=old)
            reference = doc.references.outgoing(join, role='bus-wire-segment-1')[0]
            self.assertIs(reference.target.start.parent.parent, route)
            self.assertEqual(join.scalar('ConnectB1'), old)
            self.assertEqual(connectivity_mismatches(doc), [])
            doc.rebuild()
            self.assertEqual(join.scalar('ConnectB1'), 0)

    def test_binary_bus_join_clamps_to_an_existing_segment(self):
        for saved in (-1,0,1,999):
            doc, _, _, route, join, *_ = bus_document(join_segment=saved, source_format='dch', clamp_segments=True)
            reference = doc.references.outgoing(join, role='bus-wire-segment-1')[0]
            self.assertIs(reference.target.end, route.select('Points/pt')[1])
            self.assertEqual(join.scalar('ConnectL1'), saved)
            doc.rebuild()
            self.assertEqual(join.scalar('ConnectL1'), 1)

    def test_explicit_attachment_resolves_a_stale_reverse_cache(self):
        for old in (-1, 4):
            doc, _, bus, _, _, connector, _ = bus_document(old)
            reference = doc.references.outgoing(connector, role='bus-connector-owner')[0]
            self.assertIs(reference.target, bus)
            self.assertEqual(connector.scalar('BusNumber'), old)
            self.assertEqual(connectivity_mismatches(doc), [])
            doc.rebuild()
            self.assertEqual(connector.scalar('BusNumber'), 0)

    def test_bus_segments_and_connectors_survive_reordering(self):
        doc, wire, bus, route, join, connector, other_bus = bus_document()
        self.assertEqual(doc.references.issues, [])
        self.assertEqual(connectivity_mismatches(doc), [])
        target = doc.references.outgoing(wire, role='wire-bus-segment-2')[0].target
        self.assertIsInstance(target, Segment)
        self.assertIs(target.start.parent.parent, route)
        self.assertIs(doc.references.outgoing(route, role='bus-wire-connector-1')[0].target, connector)
        other_bus.move_to(bus.parent, 0)
        route.move_to(route.parent, 1)
        connector.move_to(connector.parent, 1)
        doc.rebuild()
        self.assertEqual(wire.scalar('ConnectB2'), 1)
        self.assertEqual(wire.scalar('Connect2'), 1)
        self.assertEqual(wire.scalar('ConnectL2'), 1)
        self.assertEqual(join.scalar('Connect1'), 1)
        self.assertEqual(join.scalar('ConnectB1'), 1)
        self.assertEqual(route.scalar('Connect1'), 1)
        self.assertEqual(route.scalar('Connect2'), 999)
        self.assertEqual(connector.scalar('BusNumber'), 1)
        self.assertEqual(bus.scalar('ActiveLine'), 0)
        self.assertEqual(connectivity_mismatches(doc), [])
        clone = doc.clone()
        copied_wire = clone.one('/Schematic/Nets/Net/Lines/Line')
        copied = clone.references.outgoing(copied_wire, role='wire-bus-segment-2')[0].target
        self.assertIsNot(copied.start, target.start)
        self.assertEqual(copied.start.values, target.start.values)

    def test_bus_membership_and_endpoint_modes_are_validated(self):
        doc, wire, bus, *_ = bus_document()
        bus.one('Nets/pt').detach()
        with self.assertRaises(ReferenceError):
            doc.rebuild()
        doc, wire, *_ = bus_document()
        wire.set_field('ConnectMode2', 4)  # Free in the net-wire enum.
        with self.assertRaises(ReferenceError):
            doc.rebuild()  # Existing attachment requires an explicit graph edit.

    def test_free_modes_keep_unused_numbers_unbound(self):
        doc, wire, *_ = bus_document()
        doc.references.discard(doc.references.outgoing(wire, role='wire-bus-segment-2')[0])
        wire.set_field('ConnectMode2', 4)
        wire.set_field('Connect2', 999)
        wire.set_field('ConnectL2', 999)
        wire.set_field('ConnectB2', 999)
        doc.rebuild()
        self.assertEqual(wire.scalar('Connect2'), 999)


if __name__ == '__main__':
    unittest.main()
