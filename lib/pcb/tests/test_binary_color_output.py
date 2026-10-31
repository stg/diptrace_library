"""PCB and schematic binary writers share extended-color projection."""
import unittest

from lib.common.binary import BinaryWriter
from lib.common.conversion import ConversionReport, export_diagnostics
from lib.common.model import Element
from lib.pcb.formats.dip.writer import Writer as PcbWriter
from lib.schematic.formats.dch.write import Writer as SchematicWriter


class BinaryColorOutputTests(unittest.TestCase):
    def test_named_colors_share_wire_projection_and_keep_authored_values(self):
        cases = ((0, b'\0\0\0', False), (0x123456, bytes.fromhex('563412'), False),
                 (-1, b'\0\0\0', True), (-2147483648, b'\0\0\0', True),
                 (0x12345678, bytes.fromhex('785634'), True),
                 (0x7FFFFFFF, b'\xff\xff\xff', True),
                 (0x80000002, b'\0\0\0', True), (0xFFFFFFFF, b'\0\0\0', True))
        for format, factory in (('dch', SchematicWriter), ('dip', PcbWriter)):
            @export_diagnostics(format)
            def write_color(node, *, report):
                writer = factory()
                writer.field(node, 'Color', 'color')
                return bytes(writer.buffer)

            for value, expected, warning in cases:
                with self.subTest(format=format, value=value):
                    node = Element('Shape')
                    node.add('Color', value)
                    report = ConversionReport()
                    self.assertEqual(write_color(node, report=report), expected)
                    self.assertEqual(node['Color'], value)
                    self.assertEqual([(row.rule, row.format, row.operation) for row in report.warnings],
                                     [('color-rgb-range', format, 'export')] if warning else [])
                    self.assertFalse(report.errors)

    def test_invalid_color_domains_still_raise_and_raw_scalar_writer_stays_strict(self):
        for factory in (SchematicWriter, PcbWriter):
            for value in (True, -2147483649, 0x100000000, 1.5):
                with self.subTest(writer=factory, value=value):
                    node = Element('Shape')
                    node.add('Color', value)
                    with self.assertRaises((TypeError, ValueError)):
                        factory().field(node, 'Color', 'color')
                    self.assertEqual(node['Color'], value)
        for value in (-1, 0x12345678):
            with self.assertRaises(ValueError):
                BinaryWriter().color(value)


if __name__ == '__main__':
    unittest.main()
