"""Pair routing extends existing geometry without duplicating connectivity."""
import unittest

from lib.common.binary import BinaryWriter
from lib.pcb.formats.dip.differential_pairs import read_initial_pairs, read_routing_extensions
from lib.pcb.formats.dip.read import Reader
from .test_differential_pairs import board_fragment, pair_fixture


def routing_fixture(version):
    writer = BinaryWriter()
    writer.buffer.extend(b'\x07DTBOARD')
    writer.integer(version)

    def values(kind, *items):
        for item in items:
            getattr(writer, kind)(item)

    if version > 40:
        writer.text('Previous check')
        values('boolean', True, False, True, False, True, False, True, False)
        writer.integer(1)
        values('number', *range(42))
        writer.integer(1)
        values('number', 1, 2, 3, 4, 5, 6)
        writer.boolean(False)
        writer.integer(2)
        values('integer', 0, 1)
        writer.boolean(True)
        values('integer', 2, -1)
        writer.boolean(False)
        writer.integer(1)  # One positive separate trace.
        values('integer', 10, 2, -1, 0, 1, 3, 0, 2)
        writer.boolean(True)
        values('integer', -1, 4, 25)
        writer.integer(1)
        values('number', 3, 6)
        values('integer', 1, 0)
        values('number', .3, .9)
        writer.boolean(True)
        writer.integer(0)
        writer.boolean(False)
        writer.integer(1)
        writer.number(.4)
        values('integer', 0, 1)
        values('boolean', True, True)
        writer.integer(0)  # No negative separate traces.
        values('integer', 4, 2, -1)
        for index in range(2):
            writer.integer(index+3)
            writer.boolean(bool(index))
        # Removed pairs retain the geometry needed to restore their routing.
        values('integer', 3, 1)
        writer.boolean(True)
        values('integer', 4, -1)
        writer.boolean(False)
    writer.integer(17)
    return bytes(writer.buffer)


def pair_board():
    board = board_fragment()
    read_initial_pairs(Reader(pair_fixture(41)), board)
    trace = board.one('Nets/Net/Traces/Trace')
    trace.add('Connected1', 0)
    trace.add('Connected2', 0)
    removed = board.one('RemovedDifferentialPairs').add('RemovedDifferentialPair')
    center = removed.add('Segments').add('Segment').add('CenterPoints').add('CenterPoint')
    center.add('PosPoints').add('PosPoint')
    center.add('NegPoints').add('NegPoint')
    return board


class PairExtensionTests(unittest.TestCase):
    def test_routing_extends_existing_pairs_and_trace_endpoints(self):
        for version in (41, 42, 54, 62):
            with self.subTest(version=version):
                reader = Reader(routing_fixture(version))
                board = pair_board()
                upgrades = read_routing_extensions(reader, board)
                self.assertEqual(reader.integer(), 17)
                self.assertEqual(reader.pos, len(reader.data))
                self.assertEqual(board.one('LastDRC')['Name'], 'Previous check')
                self.assertFalse(board.one('LastDRC')['CheckSize'])
                pair = board.one('DifferentialPairs/DifferentialPair')
                self.assertFalse(pair['AutoPadPoints'])
                self.assertEqual(pair['RouteMode'], 2)
                self.assertEqual(pair.one('Segments/Segment/CenterPoints/CenterPoint/NegPoints/NegPoint')['Lay'], 2)
                separate = pair.one('PosSeparateTraces/PosTrace')
                self.assertEqual(separate['TraceId'], 4)
                self.assertEqual(separate['Connected2'], 2)
                self.assertTrue(separate.one('Points/Point')['PairNecked'])
                self.assertEqual(len(upgrades), 1)
                self.assertIs(upgrades[0].trace, separate)
                self.assertEqual(upgrades[0].previous_number, 25)
                trace = board.one('Nets/Net/Traces/Trace')
                self.assertEqual(trace['Connected1'], 2)
                self.assertEqual(trace['Connected2'], -1)
                self.assertEqual(len(trace.children('Connected1')), 1)
                self.assertEqual(trace.one('Points/Point[1]')['PairSubPoint'], 3)
                removed = board.one('RemovedDifferentialPairs/RemovedDifferentialPair')
                self.assertEqual(removed.one('Segments/Segment/CenterPoints/CenterPoint/PosPoints/PosPoint')['Lay'], 3)

    def test_schema_40_has_no_routing_extension(self):
        reader = Reader(routing_fixture(40))
        board = pair_board()
        self.assertEqual(read_routing_extensions(reader, board), ())
        self.assertIsNone(board.child('LastDRC'))
        self.assertEqual(reader.integer(), 17)


if __name__ == '__main__':
    unittest.main()
