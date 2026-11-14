"""Header boundaries must not be mistaken for complete adapter support."""
import unittest

from lib.common.binary import BinaryWriter
from lib.common.errors import UnsupportedFileError
from lib.pattern.formats.lib.binary import Cursor, PatternError


def stream(version=24, *, name='Example', hint='A small library', count=0):
    writer = BinaryWriter()
    writer.buffer.extend(b'\x06DTCLIB')
    writer.integer(version)
    writer.integer(count)
    for text in (name, hint):
        if version >= 18:
            writer.text(text)
        else:
            encoded = text.encode('cp1252')
            writer.buffer.append(len(encoded))
            writer.buffer.extend(encoded)
    return bytes(writer.buffer)


class BinaryHeaderTests(unittest.TestCase):
    def test_string_transition_and_metadata(self):
        for version, name in ((17, 'caf\u00e9'), (18, '\u03a9'), (24, '\u03a9'), (26, '\u03a9')):
            with self.subTest(version=version):
                data = stream(version, name=name, hint='Notes')
                cursor = Cursor(data)
                self.assertEqual((version, 0, name, 'Notes'), (
                    cursor.header.version, cursor.header.entry_count,
                    cursor.header.name, cursor.header.hint))
                self.assertEqual(len(data), cursor.pos)
                self.assertEqual(version >= 18, cursor.unicode_text)

    def test_exact_body_boundary(self):
        header = stream(count=1)
        cursor = Cursor(header + b'body')
        self.assertEqual(1, cursor.header.entry_count)
        self.assertEqual(len(header), cursor.pos)
        self.assertEqual(b'body', cursor.take(4))

    def test_unsupported_versions_have_identity(self):
        for version in (16, 27):
            with self.subTest(version=version), self.assertRaises(UnsupportedFileError) as caught:
                Cursor(stream(version))
            error = caught.exception
            self.assertEqual(('pattern', 'lib', version, 'version'),
                             (error.family, error.format, error.version, error.reason))

    def test_invalid_prefix_or_count(self):
        with self.assertRaises(PatternError):
            Cursor(b'\x06DTELIB' + stream()[7:])
        with self.assertRaises(PatternError):
            Cursor(stream(count=-1))
        with self.assertRaises(PatternError):
            Cursor(stream(count=1000000))

    def test_truncated_header_is_rejected(self):
        data = stream(name='Text', hint='Description')
        for size in range(len(data)):
            with self.subTest(size=size), self.assertRaises(PatternError):
                Cursor(data[:size])

    def test_metadata_header_is_not_a_complete_library(self):
        from lib.pattern.formats.io import parse
        with self.assertRaisesRegex(PatternError, 'truncated'):
            parse(stream())


if __name__ == '__main__':
    unittest.main()
