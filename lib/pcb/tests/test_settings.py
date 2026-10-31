"""PCB display defaults and sheet display choices retain distinct ownership."""
from decimal import Decimal
import unittest

from lib.common.binary import BinaryWriter
from lib.common.model import Element
from lib.pcb.formats.dip.read import Reader
from lib.pcb.formats.dip.settings import read_display_settings, read_rule_settings


class SettingsTests(unittest.TestCase):
    def test_display_settings_do_not_duplicate_sheet_display_fields(self):
        writer = BinaryWriter()
        writer.buffer.extend(b'\x07DTBOARD')
        writer.integer(54)
        writer.number(.3)
        writer.boolean(True)
        writer.number(.6)
        writer.boolean(False)
        writer.boolean(True)
        writer.color(0x123456)
        for flag in (True, False, True, True, False, True, False, True):
            writer.boolean(flag)
        writer.integer(1)
        writer.integer(2)
        writer.boolean(True)
        for width in (.3, .6, .9, 1.2):
            writer.number(width)
        for unit in (False, True, False):
            writer.boolean(unit)
        writer.integer(17)
        reader = Reader(bytes(writer.buffer))
        board = Element('Board')
        sheet = board.add('SheetSettings')
        upgrade = read_display_settings(reader, board)
        self.assertEqual(reader.integer(), 17)
        self.assertEqual(reader.pos, len(reader.data))
        self.assertEqual(upgrade.unit_choices, (False, True, False))
        self.assertTrue(sheet['DisplayTitles'])
        self.assertFalse(sheet['DisplaySheet'])
        self.assertIsNone(upgrade.settings.child('DisplayTitles'))
        self.assertEqual(upgrade.settings['LayerDisplayMode'], 2)
        self.assertEqual(upgrade.settings['TitlesLineWidth'], Decimal('.9'))

    def test_rule_matrix_exposes_one_named_value_per_symmetric_clearance(self):
        writer = BinaryWriter()
        writer.buffer.extend(b'\x07DTBOARD')
        writer.integer(54)
        writer.integer(2)
        for value in (.3, .6, .9, 1.2, 1.5):
            writer.number(value)
        writer.integer(1)
        writer.number(3)
        writer.number(.75)
        writer.text('Manufacturing')
        for flag in (True, True, False, True, False, True, False, True):
            writer.boolean(flag)
        writer.integer(1)
        for first in range(6):
            for second in range(7):
                writer.number(first*100+second)
        writer.integer(1)
        for value in (.3, .6, .1, 3, 5, 7):
            writer.number(value)
        for flag in (True, True, False, True):
            writer.boolean(flag)
        writer.integer(2)
        writer.boolean(False)
        reader = Reader(bytes(writer.buffer))
        board = Element('Board')
        board.add('Settings')
        drc = read_rule_settings(reader, board)
        self.assertEqual(reader.integer(), 2)
        self.assertFalse(reader.boolean())
        self.assertEqual(reader.pos, len(reader.data))
        self.assertEqual(drc['Name'], 'Manufacturing')
        details = drc.one('LayClearances/LayClearance/ClearanceDetails')
        self.assertEqual(len(details.children()), 27)
        self.assertEqual(details['TraceToVia'], 1)
        self.assertEqual(details['CopperToDrill'], 405)
        self.assertEqual(details['DrillToBoard'], 506)
        self.assertIsNone(details.child('ViaToTrace'))
        self.assertEqual(drc.one('LaySizes/LaySize')['MaxNonPlatedHole'], 7)
        self.assertEqual(board.one('Settings/Routing')['ViaHole'], Decimal('.75'))
        self.assertIsNone(drc.child('RealTimeMode'))
        self.assertFalse(board.one('ConnectivityCheck')['Shapes'])


if __name__ == '__main__':
    unittest.main()
