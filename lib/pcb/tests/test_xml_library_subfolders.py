"""PCB library folder names and symbol selections share the XML mapping."""
import unittest
from xml.etree import ElementTree

from lib.common.conversion import ConversionReport
from lib.pcb.formats import io
from lib.pcb.formats.capabilities import DIPXML
from lib.pcb.tests.test_dipxml_library import source


CACHE = '/Board/CacheLib'


def design():
    root = ElementTree.fromstring(source())
    library = root.find('Library')
    folders = ElementTree.SubElement(library, 'SubFolders')
    for name in ('001', 'Connectors & cables'):
        ElementTree.SubElement(folders, 'Item').text = name
    library.find('Components/Component/Part').set('SubFolderIndex', '1')
    return io.parse(ElementTree.tostring(root), report=ConversionReport())


class PcbXmlLibrarySubfolderTests(unittest.TestCase):
    def test_folder_metadata_survives_every_xml_profile(self):
        document = design()
        for version in DIPXML.write_versions:
            with self.subTest(version=version):
                report = ConversionReport()
                data = io.serialize(document, format='dipxml', version=version, report=report)
                current = io.parse(data, report=ConversionReport())
                self.assertEqual([row['Name'] for row in current.select(CACHE+'/Subfolders/Folder')],
                                 ['001', 'Connectors & cables'])
                self.assertEqual(current.one(CACHE+'/Slots/Slot/Definition/Part')['SubfolderIndex'], 1)
                self.assertFalse(report.errors)

    def test_renamed_folder_remains_data_in_all_three_formats(self):
        document = design()
        document.one(CACHE+'/Subfolders/Folder[2]')['Name'] = 'Renamed'
        for format in ('dip', 'asc', 'dipxml'):
            with self.subTest(format=format):
                rebuilt = io.parse(io.serialize(document, format=format, report=ConversionReport()),
                                   report=ConversionReport())
                self.assertEqual(rebuilt.one(CACHE+'/Subfolders/Folder[2]')['Name'], 'Renamed')
                self.assertEqual(rebuilt.one(CACHE+'/Slots/Slot/Definition/Part')['SubfolderIndex'], 1)


if __name__ == '__main__':
    unittest.main()
