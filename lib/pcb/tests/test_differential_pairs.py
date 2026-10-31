"""Differential routing keeps pad, segment and center relationships distinct."""
from decimal import Decimal
import unittest

from lib.common.binary import BinaryWriter
from lib.common.model import Element
from lib.pcb.formats.dip.differential_pairs import read_initial_pairs
from lib.pcb.formats.dip.read import Reader
from lib.pcb.formats.capabilities import DIP


def pair_fixture(version, *, removed=False):
    writer = BinaryWriter()
    writer.buffer.extend(b'\x07DTBOARD')
    writer.integer(version)

    def values(kind, *items):
        for item in items:
            getattr(writer, kind)(item)

    if version > 39:
        values('number', 1.5, 2.5, .3, .6, 3)
        values('integer', 1)
        pair_start = len(writer.buffer)
        values('boolean', True)
        values('text', 'D0')
        values('integer', 7, 1, 2, 0)
        values('boolean', True)
        values('color', 0x123456)
        values('integer', 1, 10, 2, 11, 3)
        values('integer', 1, 0, 1, 0, 1, -1, -1)
        values('integer', 1)
        values('number', 3, 6)
        values('integer', 0, -1, 3, 2, 0, 1, 2, 3, 1)
        values('boolean', True, False, True)
        values('integer', 1)
        values('number', .25, .5)
        values('boolean', True)
        values('integer', 1)
        values('number', -.25, -.5)
        values('boolean', False)
        pair_data = bytes(writer.buffer[pair_start:])
        for point in range(2):
            values('integer', point)
            values('number', point+.5, point+1.5)
        values('integer', 2, -1, 0, 1)
        values('integer', int(removed))
        if removed:
            writer.buffer.extend(pair_data)
    values('integer', 17)
    return bytes(writer.buffer)


def board_fragment():
    board = Element('Board')
    board.add('NetClasses').add('NetClass').add('LayProperties').add('LayProperty')
    points = board.add('Nets').add('Net').add('Traces').add('Trace').add('Points')
    points.add('Point', 0)
    points.add('Point', 1)
    board.add('DesignErrors').add('DesignError')
    return board


class DifferentialPairTests(unittest.TestCase):
    def test_initial_pair_records_and_link_extensions_stay_aligned(self):
        for version in (40, 41, 54, 62):
            with self.subTest(version=version):
                board = board_fragment()
                reader = Reader(pair_fixture(version))
                pairs = read_initial_pairs(reader, board)
                self.assertEqual(reader.integer(), 17)
                self.assertEqual(reader.pos, len(reader.data))
                pair = pairs.one('DifferentialPair')
                self.assertEqual(pair['Name'], 'D0')
                self.assertEqual(pair['Number'], 7)
                self.assertEqual(pair.one('PadPoints/PadPoint')['NegPad'], 3)
                segment = pair.one('Segments/Segment')
                self.assertEqual(segment['NegTrace'], 1)
                center = segment.one('CenterPoints/CenterPoint')
                self.assertEqual(center['X'], 3)
                self.assertEqual(center['PosTrace_EndPoint'], 1)
                self.assertTrue(center['Necked'])
                self.assertEqual(center.one('NegPoints/NegPoint')['X'], Decimal('-.25'))
                self.assertEqual(board.one('NetClasses/NetClass')['Phase'], Decimal('1.5'))
                self.assertEqual(board.one('Nets/Net/Traces/Trace/Points/Point[2]')['PairPoint'], 1)
                self.assertEqual(board.one('Nets/Net/Traces/Trace/Points/Point[2]')['PhaseFwd'], Decimal('1.5'))
                self.assertEqual(board.one('Nets/Net/Traces/Trace/Points/Point[2]')['PhaseBack'], Decimal('2.5'))
                self.assertEqual(board.one('DesignErrors/DesignError')['RuleType'], 2)

    def test_older_input_does_not_consume_a_pair_block(self):
        for version in (value for value in DIP.read_versions if value <= 39):
            with self.subTest(version=version):
                board = board_fragment()
                reader = Reader(pair_fixture(version))
                self.assertIsNone(read_initial_pairs(reader, board))
                self.assertEqual(reader.integer(), 17)
                self.assertIsNone(board.child('DifferentialPairs'))
                for point in board.select('Nets/Net/Traces/Trace/Points/Point'):
                    self.assertEqual((point['PhaseFwd'], point['PhaseBack']), (0, 0))

    def test_removed_pairs_have_their_own_geometry_collection(self):
        board = board_fragment()
        reader = Reader(pair_fixture(40, removed=True))
        read_initial_pairs(reader, board)
        removed = board.one('RemovedDifferentialPairs/RemovedDifferentialPair')
        self.assertEqual(removed['Name'], 'D0')
        self.assertEqual(removed.one('Segments/Segment/CenterPoints/CenterPoint')['PosTrace_EndPoint'], 1)
        self.assertEqual(reader.integer(), 17)
        self.assertEqual(reader.pos, len(reader.data))

    def test_early_pair_revision_can_end_before_removed_pairs(self):
        board = board_fragment()
        reader = Reader(pair_fixture(40)[:-6])
        read_initial_pairs(reader, board)
        self.assertEqual(reader.pos, len(reader.data))
        self.assertEqual(board.one('RemovedDifferentialPairs').children(), [])


if __name__ == '__main__':
    unittest.main()
