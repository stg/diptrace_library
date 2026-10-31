"""PCB sheet layout uses the shared editable title-block records."""
import unittest

from lib.common.binary import BinaryWriter
from lib.common.model import Element
from lib.common.title_block_codec import read_title_block
from lib.pcb.formats.dip.binary import DipError
from lib.pcb.formats.dip.read import Reader
from lib.pcb.formats.dip.sheet import read_groups, read_sheet_layout


def sheet_fixture():
    writer = BinaryWriter()
    writer.buffer.extend(b'\x07DTBOARD')
    writer.integer(54)

    def values(kind, *items):
        for item in items:
            getattr(writer, kind)(item)

    values('integer', 1)
    values('boolean', True, True, False)
    values('integer', 17)
    values('number', 1, 2)
    values('number', 1260, 891, 15, 15, 15, 15)
    for index in range(6):
        values('text', 'Title '+str(index))
        values('number', 300, 100)
        values('integer', 1, 1)
        values('number', 300, 100)
        values('integer', 0)
        values('boolean', True, False, True, False)
        values('integer', 1)
        values('boolean', False)
        values('integer', 3, 0, 2)
        values('color', 0x123456)
        values('text', 'Revision', 'Arial')
        values('number', 1, 2, 3, 4)
        values('boolean', True)
        values('number', -2, 1)
    values('boolean', True)
    values('integer', 4, 6, 1)
    values('text', 'Arial')
    values('integer', 3)
    values('boolean', True)
    values('number', 6, 9, -.3)
    values('integer', 17)
    return bytes(writer.buffer)


class SheetTests(unittest.TestCase):
    def test_groups_and_title_cells_remain_separate_editable_data(self):
        reader = Reader(sheet_fixture())
        board = Element('Board')
        groups = read_groups(reader, board)
        sheet = read_sheet_layout(reader, board)
        self.assertEqual(reader.integer(), 17)
        self.assertEqual(reader.pos, len(reader.data))
        self.assertEqual(groups[0].values, (17, 1, 2))
        self.assertTrue(groups[0]['Selected'])
        self.assertEqual(sheet['SheetWidth'], 1260)
        blocks = sheet.one('TitleBlocks').children()
        self.assertEqual(len(blocks), 6)
        self.assertEqual(blocks[1].values, (1, 'Title 1'))
        cell = blocks[0].one('Cells/Cell')
        self.assertEqual(cell.one('Edges').values, (True, False, True, False))
        content = blocks[0].one('Contents/Content')
        self.assertEqual(content['Text'], 'Revision')
        self.assertEqual(content['FontWidth'], -2)
        self.assertEqual(content['FontScale'], 1)
        self.assertEqual(content.one('Placement').values, (1, 2, 3, 4))
        self.assertEqual(blocks[0].source.format, 'dip')
        self.assertEqual(sheet.one('BorderZones')['VertZones'], 6)
        self.assertEqual(sheet.one('BorderZones')['HorzBorderSize'], 6)

    def test_group_runtime_switch_is_consumed_without_adding_a_model_property(self):
        for temporary in (False, True):
            with self.subTest(temporary=temporary):
                writer = BinaryWriter()
                writer.buffer.extend(b'\x07DTBOARD')
                writer.integer(54)
                writer.integer(1)
                for flag in (True, False, temporary):
                    writer.boolean(flag)
                writer.integer(17)
                writer.number(1)
                writer.number(2)
                reader = Reader(bytes(writer.buffer))
                group, = read_groups(reader, Element('Board'))
                self.assertEqual(group.values, (17, 1, 2))
                self.assertEqual([item.kind for item in group.children()], ['Enabled', 'Selected'])
                self.assertEqual(reader.pos, len(reader.data))

    def test_oversized_cell_grid_raises_the_owning_adapter_error(self):
        writer = BinaryWriter()
        writer.buffer.extend(b'\x07DTBOARD')
        writer.integer(54)
        writer.text('')
        writer.number(1)
        writer.number(1)
        writer.integer(1)
        writer.integer(1)
        writer.number(1)
        writer.number(1)
        writer.boolean(False)
        with self.assertRaisesRegex(DipError, 'title grid dimensions'):
            read_title_block(Reader(bytes(writer.buffer)), Element('TitleBlocks'), 0)


if __name__ == '__main__':
    unittest.main()
