"""Standalone component organization consumes its own versioned envelope."""
import unittest

from lib.common.binary import BinaryWriter
from lib.component.formats.eli.binary import ComponentError
from lib.component.formats.eli.containers import read_container
from lib.component.formats.eli.reader import Reader
from lib.component.tests.test_binary_header import stream


def fixture(version, *, categories=True):
    writer = BinaryWriter()
    writer.buffer.extend(stream(version, name='Example', hint='Independent fixture'))
    if version >= 33:
        writer.buffer.extend(b'\x12\x34\x56\x78')
    if version < 24:
        def text(value):
            data = value.encode('cp1252')
            writer.buffer.append(len(data))
            writer.buffer.extend(data)
        writer.text = text
    if version >= 24:
        writer.integer(1 if categories else 0)
        if categories:
            for name, key in (('Assembly', 7), ('Headers', 12), ('Through', 31)):
                writer.text(name)
                writer.integer(key)
                if name != 'Through':
                    writer.integer(1)
    writer.integer(2)
    writer.text('First folder')
    writer.text('caf\u00e9')
    writer.integer(3)
    return bytes(writer.buffer)


class BinaryContainerTests(unittest.TestCase):
    def test_catalogue_gate_and_folder_text_follow_the_library_revision(self):
        for version in range(23, 34):
            with self.subTest(version=version):
                data = fixture(version)
                reader = Reader(data+b'body')
                result = read_container(reader)
                self.assertEqual((version, 3, len(data)), (result.header.version,
                    result.header.entry_count, result.body_start))
                self.assertEqual(['First folder', 'caf\u00e9'],
                    [row['Name'] for row in result.library.select('Subfolders/Folder')])
                if version == 23:
                    self.assertFalse(result.library.select('Categories/Category'))
                else:
                    category = result.library.one('Categories/Category')
                    self.assertEqual(('Assembly', 7), category.values)
                    self.assertEqual(('Through', 31), category.one('Type/Subtype').values)
                self.assertEqual(b'body', reader.take(4))

    def test_current_serialization_word_is_not_container_model_data(self):
        result = read_container(Reader(fixture(33)+b'body'))
        self.assertEqual(['Name', 'Hint', 'Categories', 'Subfolders'],
                         [node.kind for node in result.library.children()])
        self.assertIsNone(result.library.child('UID32'))

    def test_empty_catalogue_does_not_consume_the_folder_count(self):
        result = read_container(Reader(fixture(31, categories=False)+b'body'))
        self.assertEqual(3, result.header.entry_count)
        self.assertFalse(result.library.select('Categories/Category'))
        self.assertEqual(2, len(result.library.select('Subfolders/Folder')))

    def test_truncated_container_rejects_every_incomplete_boundary(self):
        data = fixture(33)
        header_size = len(stream(33, name='Example', hint='Independent fixture'))
        for size in range(header_size, len(data)):
            with self.subTest(size=size), self.assertRaises(ComponentError):
                read_container(Reader(data[:size]))


if __name__ == '__main__':
    unittest.main()
