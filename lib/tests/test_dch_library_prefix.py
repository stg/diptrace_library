"""An obsolete resource count must not change the DCH stream layout."""
from decimal import Decimal
import unittest

from lib import Document, new_schematic, parse_dch
from lib.schematic.formats.dch.read import (Reader, _preamble)


def prefix(version, count):
    def integer(value):
        return (value+1_000_000).to_bytes(3, 'big')

    def number(value):
        return (int(Decimal(value)*10000)+1_000_000_000).to_bytes(4, 'big')

    def text(value):
        raw = value.encode('utf-16-be' if version >= 32 else 'cp1252')
        return (len(raw)//2).to_bytes(2, 'big')+raw if version >= 32 else integer(len(raw))+raw

    data = bytearray(b'\x07DTSCHEM'+integer(version))
    data += number(1)+integer(0)*3  # Scale, viewport, picture count.
    data += integer(1)+text('Sheet')+integer(0)
    data += integer(count)
    data += b''.join(integer(n) for n in (2, 99, 1, 99))
    data += b'\0'+number(0)*2+text('First')+text('Second')+b'\1'+number(-1)+number(1)
    data += integer(0)*2  # No class or component records in this prefix.
    return bytes(data)


class LibraryPrefixTests(unittest.TestCase):
    def test_nonzero_counts_never_consume_inline_strings_in_any_supported_schema(self):
        for version in range(29, 49):
            for count in (0, 1, 3, 7, 200_000):
                with self.subTest(version=version, count=count):
                    raw = prefix(version, count)
                    reader, document = Reader(raw), Document()
                    schematic, components = _preamble(reader, document)
                    self.assertEqual(reader.pos, len(raw))
                    self.assertEqual(components, 0)
                    self.assertEqual(schematic.scalar('ShowText'), 2)
                    self.assertEqual(schematic.scalar('TextAlign'), 99)
                    self.assertEqual(schematic.scalar('FieldName1'), 'First')
                    self.assertEqual(schematic.scalar('FieldName2'), 'Second')
                    self.assertIsNone(schematic.child('StoredData'))
                    self.assertEqual(bool(document.diagnostics), bool(count and version < 42))

    def test_current_outputs_regenerate_zero_without_a_model_count(self):
        current = new_schematic()
        self.assertIsNone(current.one('/Schematic').child('StoredData'))
        for version in (46, 47, 48):
            raw = current.to_dch_bytes(version=version)
            reader = Reader(raw)
            # Read the versioned prefix fields preceding the obsolete count.
            reader.number()
            for _ in range(4):
                reader.integer()
            reader.text()
            reader.integer()
            self.assertEqual(reader.integer(), 0)
            loaded = parse_dch(raw)
            self.assertIsNone(loaded.one('/Schematic').child('StoredData'))
            self.assertEqual(loaded.to_dch_bytes(version=version), raw)


if __name__ == '__main__':
    unittest.main()
