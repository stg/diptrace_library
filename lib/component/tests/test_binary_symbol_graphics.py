"""Old library corners modernize through the shared symbol geometry rules."""
import math
import unittest

from lib.common.binary_records import RecordWriter
from lib.common.model import Element
from lib.component.formats.eli.reader import Reader
from lib.component.formats.eli.symbols import read_symbol_graphics
from lib.component.tests.test_binary_header import stream


def drawing_payload(version, kind):
    writer = RecordWriter()
    writer.integer(1)
    writer.boolean(True)
    if version < 27:
        writer.integer(1)
    writer.integer(kind)
    writer.integer(6)
    writer.color(0)
    writer.integer(0)
    writer.text('')
    if version < 27:
        writer.text('Example')
    writer.number(.3)
    writer.integer(2)
    for value in (1, 2, 7, 5):
        writer.number(value)
    writer.boolean(False)
    writer.boolean(True)
    writer.number(-1)
    writer.number(1)
    if version >= 27:
        writer.number(.25)
        for value in (0, 0, 0):
            writer.integer(value)
        writer.number(1.2)
        writer.integer(1)
        writer.text('Example')
        writer.integer(-1)
    return bytes(writer.buffer)


class SymbolGraphicsTests(unittest.TestCase):
    def test_old_text_uses_its_oriented_anchor_and_current_text_properties(self):
        reader = Reader(stream(24)+drawing_payload(24, 10)+b'end')
        shape = read_symbol_graphics(reader, Element('Part')).one('Shape')
        self.assertIsNone(shape.child('Points'))
        self.assertEqual([(1, 5)], [point.values for point in shape.select('Points_New/pt')])
        self.assertEqual(math.pi/2, shape['TextAngle'])
        self.assertEqual((-1, -1, -1), tuple(shape[name] for name in ('TextHorz', 'TextVert', 'TextAlign')))
        self.assertEqual('Example', shape.one('TextLine/pt').values[0])
        self.assertEqual(b'end', reader.take(3))

    def test_old_unequal_ellipse_extents_become_a_closed_outline(self):
        reader = Reader(stream(26)+drawing_payload(26, 6))
        shape = read_symbol_graphics(reader, Element('Part')).one('Shape')
        self.assertEqual(8, shape['Type'])
        points = [point.values for point in shape.select('Points_New/pt')]
        self.assertGreater(len(points), 2)
        self.assertEqual(points[0], points[-1])
        self.assertAlmostEqual(1, min(x for x, _ in points))
        self.assertAlmostEqual(7, max(x for x, _ in points))

    def test_current_geometry_is_not_reinterpreted_as_legacy_corners(self):
        reader = Reader(stream(27)+drawing_payload(27, 6)+b'end')
        shape = read_symbol_graphics(reader, Element('Part')).one('Shape')
        self.assertEqual(6, shape['Type'])
        self.assertEqual([(1, 2), (7, 5)], [point.values for point in shape.select('Points_New/pt')])
        self.assertEqual(.25, shape['TextAngle'])
        self.assertEqual(b'end', reader.take(3))


if __name__ == '__main__':
    unittest.main()
