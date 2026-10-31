"""Wire values are independent of document-family version numbering."""
from decimal import Decimal, localcontext
import re
import unittest

from lib.common.binary import BinaryReader, BinaryWriter
from lib.common.binary_records import RecordWriter, grid_step_value, write_grid_step
from lib.common.model import Element
from lib.common.conversion import ConversionReport


class BinaryTests(unittest.TestCase):
    def test_known_scalar_bytes(self):
        # A mix of signed, unsigned, fixed-point and text values exercises the
        # actual wire representation, rather than only our reader/writer pair.
        data = bytes.fromhex('0f423f 3b9afa39 01 563412 0002 0041 03a9')
        reader = BinaryReader(data)
        self.assertEqual(reader.integer(), -1)
        self.assertEqual(reader.number(), Decimal('1.2345'))
        self.assertIs(reader.boolean(), True)
        self.assertEqual(reader.color(), 0x123456)
        self.assertEqual(reader.text(), 'A\u03a9')
        self.assertEqual(reader.pos, len(data))
        writer = BinaryWriter()
        writer.integer(-1)
        writer.number(Decimal('1.2345'))
        writer.boolean(True)
        writer.color(0x123456)
        writer.text('A\u03a9')
        self.assertEqual(bytes(writer.buffer), data)

    def test_fixed_point_decode_does_not_use_decimal_context(self):
        with localcontext() as context:
            context.prec = 2
            self.assertEqual(BinaryReader(bytes.fromhex('3b9afa39')).number(), Decimal('1.2345'))

    def test_fixed_point_rounding_uses_exact_decimal_ties_and_ignores_caller_context(self):
        for value, expected in (('.00015', '.0002'), ('-.00015', '-.0002'),
                                 ('1.50005', '1.5000'), ('-1.50005', '-1.5000'),
                                 ('.00014999999999999999999999', '.0001'),
                                 ('.00015000000000000000000001', '.0002')):
            for precision in (2, 28):
                with self.subTest(value=value, precision=precision), localcontext() as context:
                    context.prec = precision
                    writer = BinaryWriter()
                    writer.number(Decimal(value))
                    self.assertEqual(BinaryReader(bytes(writer.buffer)).number(), Decimal(expected))

    def test_float_and_decimal_spellings_use_the_same_number_projection(self):
        for value in (.00015, -.00015, 1.50005, -1.50005):
            with self.subTest(value=value):
                first, second = BinaryWriter(), BinaryWriter()
                first.number(value)
                second.number(Decimal(str(value)))
                self.assertEqual(first.buffer, second.buffer)

    def test_text_mode_and_offset_are_explicit(self):
        data = bytes.fromhex('ff 0f4243 41819f')
        reader = BinaryReader(data, offset=1, unicode_text=False)
        self.assertEqual(reader.text(), 'A\x81\u0178')
        self.assertEqual(reader.pos, len(data))
        self.assertEqual(BinaryReader(bytes.fromhex('0002 d800 0041')).text(), '\ud800A')

    def test_bad_fields_raise_family_error_without_consuming_following_data(self):
        class BadInput(ValueError):
            pass

        class Reader(BinaryReader):
            error_type = BadInput

        reader = Reader(b'\x01\x02')
        with self.assertRaisesRegex(BadInput, 'truncated field'):
            reader.integer()
        self.assertEqual(reader.pos, 0)
        self.assertTrue(reader.boolean())
        with self.assertRaisesRegex(BadInput, 'invalid boolean'):
            reader.boolean()

    def test_lengths_cannot_escape_input(self):
        for data, method in ((b'\x00\x03\x00A', 'text'), (bytes.fromhex('0f423f'), 'count')):
            with self.subTest(method=method):
                with self.assertRaises(ValueError):
                    reader = BinaryReader(data)
                    reader.count('points') if method == 'count' else reader.text()
        for offset in (-1, 2, True):
            with self.subTest(offset=offset):
                with self.assertRaises(ValueError):
                    BinaryReader(b'\x00', offset=offset)

    def test_writer_rejects_values_outside_wire_domain(self):
        for method, value in (('number', float('inf')), ('number', True),
                              ('number', 100001), ('number', Decimal('100000.00000000000000001')),
                              ('integer', 1.5),
                              ('integer', 1000001), ('color', -1),
                              ('boolean', 1), ('text', 'a'*65536)):
            with self.subTest(method=method, value_type=type(value).__name__):
                writer = BinaryWriter()
                with self.assertRaises((ValueError, TypeError)):
                    getattr(writer, method)(value)
                self.assertEqual(writer.buffer, b'')

    def test_record_writer_errors_identify_the_field_without_partial_scalar_output(self):
        root = Element('')
        group = root.add('Group')
        group.add('Width', 1, 2)
        group.add('Size', 100001)
        group.add('Flag', 1)
        for name, codec, location, message in (
                ('Missing', 'number', '/Group[1]/Missing', 'scalar binary value is missing'),
                ('Width', 'number', '/Group[1]/Width[1]', 'expected one scalar binary value'),
                ('Size', 'number', '/Group[1]/Size[1]', ''),
                ('Flag', 'boolean', '/Group[1]/Flag[1]', '')):
            with self.subTest(field=name):
                writer = RecordWriter()
                with self.assertRaisesRegex((TypeError, ValueError), re.escape(location)+': '+message):
                    writer.field(group, name, codec)
                self.assertEqual(writer.buffer, b'')

    def test_named_extended_colors_use_rgb_bytes_and_report_projection(self):
        writer = RecordWriter()
        writer.report = ConversionReport()
        shape = Element('Shape')
        shape.add('Color', -1)
        shape.add('FontColor', 0x12345678)
        writer.fields(shape, 'color', 'Color FontColor')
        self.assertEqual(writer.buffer, bytes.fromhex('000000 785634'))
        self.assertEqual((shape['Color'], shape['FontColor']), (-1, 0x12345678))
        self.assertEqual([row.rule for row in writer.report.warnings], ['color-rgb-range']*2)

    def test_scaled_grid_keeps_small_steps_and_is_independent_of_decimal_context(self):
        for step in (Decimal('.3'), Decimal('.000012345'), Decimal('.0000005')):
            writer = BinaryWriter()
            write_grid_step(writer, step)
            reader = BinaryReader(bytes(writer.buffer))
            numerator, divisor = reader.number(), reader.integer()
            with localcontext() as context:
                context.prec = 2
                result = grid_step_value(numerator, divisor)
            self.assertEqual(result, step)
            self.assertEqual(reader.pos, len(reader.data))
        self.assertEqual(grid_step_value(Decimal('1.2345'), 0), Decimal('1.2345'))


if __name__ == '__main__':
    unittest.main()
