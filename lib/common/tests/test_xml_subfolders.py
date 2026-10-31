"""Library folder labels are ordered text, including numeric-looking names."""
import unittest

from lib.common.model import Document, Element
from lib.common.xml import loads, dumps
from lib.common.xml_records import XmlRecord
from lib.common.xml_library_values import read_subfolders
from lib.common.xml_library_output import project_subfolders
from lib.common.library_metadata import SUBFOLDER


def library(text):
    return XmlRecord(loads('<Source>'+text+'</Source>').one('/Source/Library'))


class XmlSubfolderTests(unittest.TestCase):
    def test_text_order_and_empty_names_survive_projection(self):
        source = library('<Library><SubFolders><Item>001</Item><Item>A &amp; B</Item>'
                         '<Item></Item><Item>001</Item></SubFolders></Library>')
        folders = read_subfolders(source)
        source.finish()
        cache = Element('CacheLib')
        cache.append(folders)
        for row in folders.children():
            row.bind_schema(SUBFOLDER)
        expected = ['001', 'A & B', '', '001']
        self.assertEqual([row['Name'] for row in folders.children()], expected)
        projected = project_subfolders(cache)
        self.assertEqual([row.values[0] if row.values else '' for row in projected.children()], expected)
        document = Document()
        document.root.add('Source').append(projected)
        self.assertIn('A &amp; B', dumps(document))

    def test_absent_folders_do_not_create_output_metadata(self):
        source = library('<Library/>')
        self.assertIsNone(read_subfolders(source))
        source.finish()
        self.assertIsNone(project_subfolders(Element('CacheLib')))

    def test_unknown_or_duplicate_folder_containers_fail_explicitly(self):
        for text in ('<Library><SubFolders/><SubFolders/></Library>',
                     '<Library><SubFolders><Other/></SubFolders></Library>',
                     '<Library><SubFolders><Item Id="3">Name</Item></SubFolders></Library>'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                read_subfolders(library(text))


if __name__ == '__main__':
    unittest.main()
