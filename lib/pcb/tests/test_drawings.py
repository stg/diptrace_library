"""Board drawing layers and geometry have distinct named properties."""
import unittest

from lib.common.binary import BinaryWriter
from lib.common.model import Element
from lib.pcb.formats.dip.drawings import read_base_drawings
from lib.pcb.formats.dip.read import Reader


def drawing_fixture(version):
    writer = BinaryWriter()
    writer.buffer.extend(b'\x07DTBOARD')
    writer.integer(version)

    def values(kind, *items):
        for item in items:
            getattr(writer, kind)(item)

    values('integer', 2)
    for index in range(2):
        values('boolean', True, False)
        values('integer', 1)
        values('boolean', index == 1)
        values('integer', 2, 5, 10, 3, -1, -1)
        values('color', 0x123456, 0xffffff, 0)
        values('number', .3)
        values('integer', 2)
        values('number', 1, 2, 3, 4)
        values('text', 'Board label', 'Arial')
        values('boolean', True)
        values('integer', -1)
        values('boolean', True)
        values('number', -2, 1)
        values('integer', index+20)
        values('boolean', False)
    values('integer', 17)
    return bytes(writer.buffer)


class DrawingTests(unittest.TestCase):
    def test_geometry_transition_keeps_layer_family_separate_from_layer_id(self):
        for version in (46, 47, 54, 62):
            with self.subTest(version=version):
                reader = Reader(drawing_fixture(version))
                board = Element('Board')
                drawings = read_base_drawings(reader, board)
                self.assertEqual(reader.integer(), 17)
                self.assertEqual(reader.pos, len(reader.data))
                drawing = drawings[0].drawing
                self.assertEqual((drawing['Layer'], drawing['LayId'], drawing['Type']), (2, 5, 10))
                points = drawing.one('Points_New' if version >= 47 else 'Points')
                self.assertEqual([point.values for point in points.children()], [(1, 2), (3, 4)])
                self.assertEqual(drawings[0].orientation, 1)
                self.assertEqual(drawings[1].previous_number, 21)
                self.assertIsNone(drawing.child('BitmapIndex'))
                self.assertTrue(drawing['Locked'])
                self.assertEqual(drawing.one('TextLine/pt').values, ('Board label',))


if __name__ == '__main__':
    unittest.main()
