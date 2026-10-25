"""Wire values are independent of document-family version numbering."""
from decimal import Decimal, localcontext
import unittest

from lib.common.binary import BinaryReader, BinaryWriter


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
                              ('number', 100001), ('integer', 1.5),
                              ('integer', 1000001), ('color', -1),
                              ('boolean', 1), ('text', 'a'*65536)):
            with self.subTest(method=method, value_type=type(value).__name__):
                writer = BinaryWriter()
                with self.assertRaises((ValueError, TypeError)):
                    getattr(writer, method)(value)
                self.assertEqual(writer.buffer, b'')


if __name__ == '__main__':
    unittest.main()
