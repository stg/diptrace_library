"""Net import separates route geometry, endpoint kinds and pad membership."""
from decimal import Decimal
import unittest

from lib.common.binary import BinaryWriter
from lib.common.model import Element
from lib.pcb.formats.capabilities import DIP
from lib.pcb.formats.dip.nets import read_connections, read_base_nets
from lib.pcb.formats.dip.read import Reader


def routing_fixture(version, *, previous_point=(0, 1.2, True, .6, 0, 1),
                    previous_net=(1.2, .3, True)):
    writer = BinaryWriter()
    # Retain the valid header; the test begins directly at the routing sections.
    writer.buffer.extend(b'\x07DTBOARD')
    writer.integer(version)

    def values(kind, *items):
        for item in items:
            if kind == 'text' and version < 38:
                data = item.encode('cp1252')
                writer.integer(len(data))
                writer.buffer.extend(data)
            else:
                getattr(writer, kind)(item)

    values('integer', 2)
    for index in range(2):
        values('boolean', True)
        values('number', 1, 2, 3, 4)
        values('integer', index, index+1, 2, 3)
        if version > 33:
            values('boolean', True)
    values('integer', 1)
    values('boolean', True, False)
    values('integer', 0, 1, -1, 42, 2)
    values('number', .6, .3)
    values('text', 'VCC')
    values('number', *previous_net[:2])
    values('boolean', previous_net[2], False, True, False, True)
    values('color', 0x13579b)
    values('integer', 2, 2, 0, 2, 1, 3)
    values('integer', 2)
    for trace in range(2):
        values('integer', 0, 2, 0, 1, 3, 1)
        values('boolean', True, False, trace == 1, False, True)
        values('integer', 7, trace+100, 2)
        for point in range(2):
            values('number', 1+point, 2+trace)
            direction, size, through, hole, first, last = previous_point
            values('integer', trace, direction)
            values('number', .6, size)
            values('boolean', through)
            values('integer', 0)
            values('boolean', point == 1)
            values('integer', 3 if point == 1 else -1)
            values('number', hole)
            values('integer', first, last)
            values('boolean', point == 0)
    values('integer', 17)
    return bytes(writer.buffer)


class NetTests(unittest.TestCase):
    def test_active_selection_reads_point_before_line_in_every_supported_schema(self):
        # The independent wire fixture declares the two slots as 0, 1.
        # Reading a stream produced by our writer would conceal a shared swap.
        for version in DIP.read_versions:
            with self.subTest(version=version):
                reader, board = Reader(routing_fixture(version)), Element('Board')
                read_connections(reader, board)
                read_base_nets(reader, board)
                net = board.one('Nets/Net')
                self.assertEqual((net['ActivePoint'], net['ActiveLine']), (0, 1))

    def read(self, version):
        reader = Reader(routing_fixture(version))
        board = Element('Board')
        connections = read_connections(reader, board)
        upgrades = read_base_nets(reader, board)
        self.assertEqual(reader.integer(), 17)
        self.assertEqual(reader.pos, len(reader.data))
        return connections, upgrades

    def test_connection_hidden_gate_does_not_shift_following_records(self):
        for version in (31, 33, 34, 37, 38, 54, 62):
            with self.subTest(version=version):
                connections, upgrades = self.read(version)
                self.assertEqual(connections.one('Connection[1]')['Hidden'], version > 33)
                self.assertIsNone(connections.one('Connection[1]').child('Selected'))
                self.assertEqual(connections.one('Connection[1]')['Pad2'], 3)
                self.assertEqual(upgrades[0].net['Name'], 'VCC')

    def test_membership_and_endpoint_modes_are_named_separate_facts(self):
        _, upgrades = self.read(54)
        net = upgrades[0].net
        self.assertEqual(net['Number'], 42)
        self.assertEqual(net['TraceColor'], 0x13579b)
        self.assertEqual([item.values for item in net.one('Pads').children()], [(0, 2), (1, 3)])
        self.assertEqual([u.trace['Connected1'] for u in upgrades[0].traces], [1, -1])
        self.assertEqual(upgrades[0].traces[1].trace['Connected2'], 0)
        self.assertEqual(upgrades[0].traces[0].trace['SubObject2'], 3)
        self.assertIsNone(net.child('StoredData'))

    def test_compatibility_via_values_do_not_replace_current_point_settings(self):
        _, upgrades = self.read(54)
        trace = upgrades[0].traces[0]
        point = trace.points[1]
        self.assertEqual(point['ViaStyle'], 3)
        self.assertEqual(point['Width'], Decimal('.6'))
        self.assertTrue(point['Arc'])
        self.assertFalse(point['Selected'])
        self.assertEqual(trace.previous_number, 100)
        self.assertEqual(point.source.format, 'dip')

    def test_saved_direction_and_via_snapshots_do_not_become_authored_point_data(self):
        expected = None
        for previous in ((0, 1.2, True, .6, 0, 1), (4, 9, False, 3, 2, 7)):
            reader = Reader(routing_fixture(54, previous_point=previous,
                                           previous_net=(previous[1], previous[3], previous[2])))
            board = Element('Board')
            read_connections(reader, board)
            net, = read_base_nets(reader, board)
            current = [tuple((child.kind, child.values) for child in point.children())
                       for trace in net.traces for point in trace.points]
            if expected is None:
                expected = current
            self.assertEqual(current, expected)
            self.assertEqual(reader.integer(), 17)
            self.assertEqual(reader.pos, len(reader.data))
            self.assertEqual(net.net['Width'], Decimal('.6'))
            self.assertEqual(net.net['Clearance'], Decimal('.3'))
            self.assertIsNone(net.net.child('ViaSize'))


if __name__ == '__main__':
    unittest.main()
