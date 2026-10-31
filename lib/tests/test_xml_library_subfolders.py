"""Schematic XML retains the same shared library-folder vocabulary as PCB."""
import unittest
from xml.etree import ElementTree

from lib import parse, serialize, ConversionReport, new_schematic, new_symbol
from lib.schematic.formats.capabilities import DCHXML


class SchematicXmlLibrarySubfolderTests(unittest.TestCase):
    def test_cached_folder_names_and_index_survive_supported_xml_outputs(self):
        initial = new_schematic()
        initial.one('/Schematic/Components').append(new_symbol('Device', 'U1'))
        source = ElementTree.fromstring(serialize(initial, format='dchxml', report=ConversionReport()))
        library = source.find('Library')
        folders = ElementTree.SubElement(library, 'SubFolders')
        for name in ('001', 'Connectors & cables'):
            ElementTree.SubElement(folders, 'Item').text = name
        library.find('Components/Component/Part').set('SubFolderIndex', '1')
        document = parse(ElementTree.tostring(source), report=ConversionReport())
        for version in DCHXML.write_versions:
            with self.subTest(version=version):
                current = parse(serialize(document, format='dchxml', version=version,
                                          report=ConversionReport()), report=ConversionReport())
                self.assertEqual([row['Name'] for row in current.select('/Schematic/CacheLib/Subfolders/Folder')],
                                 ['001', 'Connectors & cables'])
                self.assertEqual(current.one('/Schematic/CacheLib/Slots/Slot[1]/Definition/Part')['SubfolderIndex'], 1)
        for format in ('dch', 'asc'):
            with self.subTest(format=format):
                current = parse(serialize(document, format=format, report=ConversionReport()),
                                report=ConversionReport())
                self.assertEqual([row['Name'] for row in current.select('/Schematic/CacheLib/Subfolders/Folder')],
                                 ['001', 'Connectors & cables'])
                self.assertEqual(current.one('/Schematic/CacheLib/Slots/Slot[1]/Definition/Part')['SubfolderIndex'], 1)


if __name__ == '__main__':
    unittest.main()
