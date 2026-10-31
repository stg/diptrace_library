"""Saved rule results retain their typed references and revision boundary."""
import unittest

from lib.common.binary import BinaryWriter
from lib.common.model import Element
from lib.pcb.formats.dip.read import Reader
from lib.pcb.formats.dip.results import read_initial_results


def result_fixture(version):
    writer = BinaryWriter()
    writer.buffer.extend(b'\x07DTBOARD')
    writer.integer(version)
    if version > 34:
        writer.integer(2)
        writer.boolean(True)
        writer.integer(1)
        writer.boolean(True)
        for value in (.3, .6, .1, .2):
            writer.number(value)
        for value in (0, 2, 1, 10, 2, -1, 20, 3, 5, -1, -1):
            writer.integer(value)
        writer.integer(2)
        writer.boolean(True)
        writer.boolean(False)
    writer.integer(17)
    return bytes(writer.buffer)


class ResultTests(unittest.TestCase):
    def test_older_input_has_no_invented_saved_result(self):
        for version in (31, 34):
            reader = Reader(result_fixture(version))
            board = Element('Board')
            drc = board.add('DRC')
            self.assertIsNone(read_initial_results(reader, board))
            self.assertIsNone(drc.child('DRCDone'))
            self.assertIsNone(drc.child('RealTimeMode'))
            self.assertEqual(reader.integer(), 17)

    def test_result_fields_and_layer_flags_are_not_confused_with_rule_settings(self):
        for version in (35, 54, 62):
            reader = Reader(result_fixture(version))
            board = Element('Board')
            drc = board.add('DRC')
            errors = read_initial_results(reader, board)
            self.assertEqual(reader.integer(), 17)
            self.assertEqual(reader.pos, len(reader.data))
            error = errors.one('DesignError')
            self.assertEqual(error['Object1'], 10)
            self.assertEqual(error['Point1'], -1)
            self.assertEqual(error['Object2'], 20)
            self.assertEqual(error['Point2'], 5)
            self.assertEqual(error['ExtObject2'], -1)
            self.assertEqual([item.values for item in error.one('Lays').children()], [(True,), (False,)])
            self.assertEqual(drc['RealTimeMode'], 2)
            self.assertTrue(drc['DRCDone'])
            self.assertIsNone(error.child('RuleType'))


if __name__ == '__main__':
    unittest.main()
