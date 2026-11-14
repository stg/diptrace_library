"""Component library metadata has its own ordering and text transition."""
import unittest

from lib.common.binary import BinaryWriter
from lib.common.errors import UnsupportedFileError
from lib.component.formats.eli.binary import Cursor, ComponentError


def stream(version=31, *, name='Example', hint='Notes'):
    writer = BinaryWriter()
    writer.buffer.extend(b'\x06DTELIB')
    writer.integer(version)
    for text in (name, hint):
        if version >= 24:
            writer.text(text)
        else:
            encoded = text.encode('cp1252')
            writer.buffer.append(len(encoded))
            writer.buffer.extend(encoded)
    return bytes(writer.buffer)


class BinaryHeaderTests(unittest.TestCase):
    def test_metadata_precedes_count_and_body(self):
        for version, name in ((23, 'caf\u00e9'), (24, '\u03a9'), (31, '\u03a9'), (33, '\u03a9')):
            with self.subTest(version=version):
                data = stream(version, name=name, hint='Description')
                cursor = Cursor(data + b'body')
                self.assertEqual((version, None, name, 'Description'), (
                    cursor.header.version, cursor.header.entry_count,
                    cursor.header.name, cursor.header.hint))
                self.assertEqual(len(data), cursor.pos)
                self.assertEqual(b'body', cursor.take(4))

    def test_version_error_identifies_component_family(self):
        with self.assertRaises(UnsupportedFileError) as caught:
            Cursor(stream(34))
        self.assertEqual(('component', 'eli', 34, 'version'), (
            caught.exception.family, caught.exception.format,
            caught.exception.version, caught.exception.reason))

    def test_rejects_other_family_signature(self):
        with self.assertRaises(ComponentError):
            Cursor(b'\x06DTCLIB' + stream()[7:])

    def test_truncated_header(self):
        data = stream()
        for size in range(len(data)):
            with self.subTest(size=size), self.assertRaises(ComponentError):
                Cursor(data[:size])

    def test_metadata_header_is_not_a_complete_library(self):
        from lib.component.formats.io import parse
        with self.assertRaisesRegex(ComponentError, 'truncated'):
            parse(stream())


if __name__ == '__main__':
    unittest.main()
