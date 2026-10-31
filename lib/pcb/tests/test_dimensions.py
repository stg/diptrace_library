"""Board dimensions share geometric properties with footprint dimensions."""
import unittest

from lib.common.binary import BinaryWriter
from lib.common.model import Element
from lib.pcb.formats.dip.drawings import read_board_dimensions
from lib.pcb.formats.dip.read import Reader


def dimension_fixture(version):
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
    values('boolean', True, True, False)
    values('integer', 3, 1, 17, 2, 4, 0, 18, 3, 5, 2)
    values('number', 1, 2, 3, 4, 5, 6, .3)
    values('integer', 0)
    values('boolean', True)
    values('text', 'Arial')
    values('integer', 3)
    values('number', 1, -2)
    values('boolean', True)
    values('number', .5)
    values('integer', 0, 1)
    values('text', 'R')
    values('integer', 17)
    values('boolean', True)
    if version > 32:
        values('integer', 4)
    values('integer', 23)
    return bytes(writer.buffer)


class DimensionTests(unittest.TestCase):
    def test_board_specific_flags_do_not_change_shared_dimension_properties(self):
        for version in (31, 32, 33, 37, 38, 54, 62):
            with self.subTest(version=version):
                reader = Reader(dimension_fixture(version))
                dimensions = read_board_dimensions(reader, Element('Board'))
                self.assertEqual(reader.integer(), 23)
                self.assertEqual(reader.pos, len(reader.data))
                dimension = dimensions.one('Dimension')
                self.assertEqual(dimension['Object1'], 17)
                self.assertEqual(dimension['SubObject2'], 3)
                self.assertEqual(dimension['PointerText'], 'R')
                self.assertTrue(dimension['Selected'])
                self.assertTrue(dimension['PanelExclude'])
                self.assertEqual(dimension['NonSignal'], 4 if version > 32 else 0)
                self.assertEqual(dimension['FontWidth'], -2)
                self.assertEqual(dimension['FontScale'], 1)


if __name__ == '__main__':
    unittest.main()
