"""PCB revisions select their own text codec over shared scalar primitives."""
from decimal import Decimal
import unittest

from lib.pcb.formats.dip.binary import Cursor, DipError, UnsupportedVersionError, read_header


def header(version):
    return b'\x07DTBOARD'+(1_000_000+version).to_bytes(3, 'big')


class DipBinaryTests(unittest.TestCase):
    def test_modern_and_legacy_headers(self):
        for version in (31, 36, 37, 38, 54, 58, 60, 62):
            with self.subTest(version=version):
                parsed = read_header(header(version))
                self.assertEqual((parsed.signature, parsed.version, parsed.body_offset), ('DTBOARD', version, 11))
        for signature, version in (('DTBOARD2.2', 31), ('DTBOARD2.21', 32), ('DTBOARD2.22', 33)):
            data = bytes((len(signature),))+signature.encode('ascii')
            parsed = read_header(data)
            self.assertEqual((parsed.version, parsed.body_offset), (version, len(data)))

    def test_pcb_unicode_transition_is_not_the_schematic_transition(self):
        old = Cursor(header(37)+bytes.fromhex('0f4242 4181'))
        self.assertEqual(old.text(), 'A\x81')
        modern = Cursor(header(38)+bytes.fromhex('0002 0041 03a9'))
        self.assertEqual(modern.text(), 'A\u03a9')
        self.assertEqual(modern.pos, len(modern.data))

    def test_common_scalar_encodings_work_from_board_body(self):
        cursor = Cursor(header(54)+bytes.fromhex('0f423f 3b9afa39 01 563412'))
        self.assertEqual(cursor.integer(), -1)
        self.assertEqual(cursor.number(), Decimal('1.2345'))
        self.assertIs(cursor.boolean(), True)
        self.assertEqual(cursor.color(), 0x123456)
        with self.assertRaises(DipError):
            cursor.integer()

    def test_other_families_and_unknown_revisions_fail(self):
        for data in (b'\x07DTSCHEM'+bytes.fromhex('0f426e'), header(30), header(63)):
            with self.subTest(data=data), self.assertRaises(UnsupportedVersionError):
                read_header(data)
        for data in (b'', b'\x07DTB', b'\x07DTBOARD', b'\x01\xff'):
            with self.subTest(data=data), self.assertRaises(DipError):
                read_header(data)


if __name__ == '__main__':
    unittest.main()
