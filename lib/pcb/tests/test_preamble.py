"""Initial PCB records expose named values and honor independent PCB gates."""
from decimal import Decimal, localcontext
import unittest

from lib.common.binary import BinaryWriter
from lib.common.model import Element
from lib.pcb.formats.dip.read import Reader
from lib.pcb.formats.dip.preamble import read_initial_sections


def section_fixture(version):
    """A small wire fixture ending at the first component, with distinct values.

    The old rectangle deliberately disagrees with the authored outline. The
    decoder must use the point sequence, not retain the obsolete rectangle.
    """
    writer = BinaryWriter()
    writer.buffer.extend(b'\x07DTBOARD'+(1_000_000+version).to_bytes(3, 'big'))

    def text(value):
        if version >= 38:
            writer.text(value)
        else:
            data = value.encode('cp1252')
            writer.integer(len(data))
            writer.buffer.extend(data)

    def integers(*values):
        for value in values:
            writer.integer(value)

    def numbers(*values):
        for value in values:
            writer.number(value)

    writer.number(.5)
    integers(7, -3)
    text('linked.dch')
    writer.boolean(True)
    numbers(9, 8, 7, 6)
    writer.integer(3)
    for x, y, arc in ((0, 0, False), (9, 0, True), (9, 6, False)):
        numbers(x, y)
        writer.boolean(arc)
    writer.boolean(False)
    integers(1, 1)
    numbers(0, 0)
    if version > 31:
        writer.boolean(True)
        numbers(.6, 0, 0, 0)
    for value in (False, True, False):
        writer.boolean(value)
    writer.integer(2)
    for index, name in enumerate(('Top', 'Bottom')):
        writer.boolean(True)
        writer.integer(index)
        writer.color(0x123456+index)
        text(name)
        integers(0, 0, -1)
        writer.number(.6)
        writer.boolean(False)
    integers(0, 1, 0, 2, 6, 5)
    text('Arial')
    numbers(1.5, -2)
    writer.boolean(True)
    numbers(-2, 1)
    for value in (False, True, False, False, True):
        writer.boolean(value)
    text('OrderNumber')
    text('Footprint')
    writer.boolean(True)
    if version > 32:
        integers(0, 1)
        text('Assembly')
        integers(17, 1, 99)
        text('Group A')
    writer.integer(1)
    text('Default')
    writer.boolean(True)
    numbers(1.8, .9)
    integers(0, 1, 1)
    text('Signal')
    writer.integer(0)
    for value in (True, False, True, False):
        writer.boolean(value)
    writer.integer(1)
    numbers(.3, .03, 300, .45, -.5)
    numbers(*([-1]*20))
    numbers(0, 0)
    integers(1, 0)
    for value in (False, True, False, True):
        writer.boolean(value)
    integers(4, 8)
    numbers(30, 6, .9)
    writer.integer(2)
    writer.boolean(True)
    writer.boolean(False)
    writer.integer(123)
    writer.boolean(True)
    integers(1, 1)
    writer.boolean(True)
    writer.integer(2)
    numbers(.3, .6)
    writer.integer(2)
    writer.buffer.extend(b'END')
    return bytes(writer.buffer)


class PreambleTests(unittest.TestCase):
    def read(self, version):
        root = Element('')
        reader = Reader(section_fixture(version), source='fixture.dip')
        state = read_initial_sections(reader, root)
        self.assertEqual(reader.take(3), b'END')
        return root, state

    def test_authored_outline_and_rule_values_are_available_by_name(self):
        root, state = self.read(54)
        board = root.one('/Board')
        self.assertEqual(root.one('/Scale').values, (50,))
        self.assertEqual(board['RelSchem'], 'linked.dch')
        self.assertEqual(board.one('Points/pt[2]').values, (9, 0, True))
        self.assertIsNone(board.child('Xmin'))
        self.assertEqual(board.one('NetClasses/NetClass/LayProperties/LayProperty')['MaxWidth'], 300)
        self.assertAlmostEqual(float(board.one('NetClasses/NetClass/LayProperties/LayProperty')['MinWidth']), .03)
        self.assertEqual(board.one('NetClasses/NetClass')['PriorityValue'], 4)
        self.assertEqual(board.one('ClassClearances/Row/Cell/Values/Item[2]').values[0], Decimal('.6'))
        self.assertEqual((state.component_count, state.legacy_picture_count), (2, 0))
        self.assertEqual(state.legacy_markings, (1, 0, 2, 6))
        self.assertIsNone(board.child('ShowText'))

    def test_legacy_gates_leave_following_records_aligned(self):
        for version in (31, 32, 37, 38, 62):
            with self.subTest(version=version):
                root, state = self.read(version)
                board = root.one('/Board')
                self.assertEqual(len(board.one('HierarchySheets').children()), int(version > 32))
                self.assertEqual(board['RailShow'], version > 31)
                self.assertEqual(state.component_count, 2)

    def test_scalar_provenance_stays_with_the_pcb_field(self):
        root, _ = self.read(54)
        field = root.one('/Board/Layers/Layer[1]/Color')
        span = field.arguments[0].source
        self.assertEqual((span.format, span.source), ('dip', 'fixture.dip'))
        self.assertEqual(span.end-span.start, 3)
        self.assertEqual(field.values, (0x123456,))

    def test_camera_scale_is_bounded_and_independent_of_decimal_context(self):
        for factor, percent in ((Decimal('3.221'), Decimal('322.1')),
                                (-1, Decimal(1)), (1001, Decimal(100000))):
            with self.subTest(factor=factor):
                encoded = BinaryWriter()
                encoded.number(factor)
                data = section_fixture(54)
                data = data[:11]+bytes(encoded.buffer)+data[15:]
                with localcontext() as context:
                    context.prec = 2
                    root = Element('')
                    read_initial_sections(Reader(data), root)
                    scale = root.one('/Scale').arguments[0]
                    self.assertEqual((scale.value, scale.unit), (percent, '%'))


if __name__ == '__main__':
    unittest.main()
