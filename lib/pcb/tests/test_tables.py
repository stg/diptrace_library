"""Table import keeps geometry, cells and text defaults editable."""
import unittest

from lib.common.binary import BinaryWriter
from lib.common.model import Element
from lib.pcb.formats.dip.read import Reader
from lib.pcb.formats.dip.tables import read_base_tables


def table_fixture(version):
    writer = BinaryWriter()
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

    values('integer', 1)
    values('boolean', True, False)
    values('integer', 2, 1, 3, 0, -1)
    values('color', 0x123456)
    values('number', 6, 3, 1, 2, 13, 5)
    values('text', 'Arial', 'Parts')
    values('integer', 2)
    values('number', 4, 8)
    values('integer', 1)
    values('number', 3)
    for text in ('RefDes', 'Value'):
        values('boolean', False)
        values('integer', 2, 0, 1)
        values('color', 0)
        values('text', text, 'Arial')
        values('number', 0, 0, 4, 3)
        values('boolean', True)
        values('number', -2, 1)
    values('boolean', True, True)
    values('number', -.3, 1)
    values('boolean', False, True)
    if version > 32:
        values('integer', 2)
    values('integer', 17)
    return bytes(writer.buffer)


class TableTests(unittest.TestCase):
    def test_cells_and_layer_gate_are_aligned_in_legacy_and_unicode_files(self):
        for version in (31, 32, 33, 37, 38, 54, 62):
            with self.subTest(version=version):
                reader = Reader(table_fixture(version))
                tables = read_base_tables(reader, Element('Board'))
                self.assertEqual(reader.integer(), 17)
                self.assertEqual(reader.pos, len(reader.data))
                table = tables.one('Table')
                self.assertEqual(table['Name'], 'Parts')
                self.assertEqual(table['NonSignal'], 2 if version > 32 else 0)
                self.assertEqual([c['Text'] for c in table.one('Cells').children()], ['RefDes', 'Value'])
                self.assertEqual([c.values for c in table.one('Cells').children()], [(0, 0), (1, 0)])
                self.assertEqual([c.values for c in table.one('ColWidths').children()], [(4,), (8,)])
                self.assertTrue(table['PanelExclude'])
                self.assertTrue(table['Locked'])
                self.assertEqual(table.one('Cells/Cell[1]')['FontWidth'], -2)
                self.assertIsNone(table.child('StoredData'))


if __name__ == '__main__':
    unittest.main()
