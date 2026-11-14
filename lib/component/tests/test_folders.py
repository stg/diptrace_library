"""Folder membership follows identity rather than a stored collection offset."""
import unittest
import xml.etree.ElementTree as ET

from lib.common.conversion import ConversionReport
from lib.common.references import ReferenceError
from lib.component.model import new_library, new_component, new_part
from lib.component.formats.eli.write import encode
from lib.component.formats.eli.read import parse as read_binary
from lib.component.formats.asc.write import dumps as ascii_text
from lib.component.formats.asc.read import parse as read_ascii
from lib.component.formats.elixml.write import dumps as xml_text
from lib.component.formats.elixml.read import parse as read_xml


class FolderTests(unittest.TestCase):
    def make_document(self):
        document = new_library()
        library = document.one('/Library')
        first = library.one('Subfolders').add('Folder','First')
        selected = library.one('Subfolders').add('Folder','Second')
        component = library.one('Components').append(new_component('Example','U'))
        component.one('Parts').append(new_part('Gate B'))
        component['Folder'] = selected
        return document, component, first, selected

    def test_reorder_rename_clone_and_optional_removal_stay_coordinated(self):
        document, component, _, selected = self.make_document()
        self.assertEqual(1,component['SubfolderIndex'])
        selected.move_to(selected.parent,index=0)
        selected['Name'] = 'Renamed'
        self.assertIs(selected,component['Folder'])
        self.assertEqual(0,component['SubfolderIndex'])
        self.assertEqual([0,0],[part['SubfolderIndex'] for part in component.select('Parts/Part')])
        self.assertIsNone(component.child('SubfolderIndex'))
        clone = document.clone()
        copied = clone.one('/Library/Components/Component')
        self.assertIs(clone.one('/Library/Subfolders/Folder[1]'),copied['Folder'])
        self.assertIsNot(selected,copied['Folder'])
        with self.assertRaises(ReferenceError):
            selected.detach()
        component['Folder'] = None
        self.assertIsNone(component['Folder'])
        self.assertEqual(-1,component['SubfolderIndex'])
        selected.detach()
        document.validate()

    def test_cross_library_assignment_is_atomic(self):
        document, component, _, selected = self.make_document()
        _, _, _, foreign = self.make_document()
        with self.assertRaises(ReferenceError):
            component['Folder'] = foreign
        self.assertIs(selected,component['Folder'])
        self.assertEqual(1,len(document.references.outgoing(component)))

    def test_all_adapters_use_the_same_folder_membership(self):
        document, component, _, selected = self.make_document()
        selected.move_to(selected.parent,index=0)
        selected['Name'] = 'Analog'
        pairs = ((encode,read_binary),(ascii_text,read_ascii),
                 (lambda doc,**kwargs:xml_text(doc,version='4.3.0.5',**kwargs),read_xml))
        for write,read in pairs:
            with self.subTest(write=write):
                imported = read(write(document,report=ConversionReport()),report=ConversionReport())
                result = imported.one('/Library/Components/Component')
                self.assertEqual((0,'Analog'),(result['SubfolderIndex'],result['Folder']['Name']))
                self.assertEqual([0,0],[part['SubfolderIndex'] for part in result.select('Parts/Part')])
        self.assertIs(selected,component['Folder'])

    def test_unavailable_folder_guards_its_scope_until_explicitly_resolved(self):
        document, _, _, _ = self.make_document()
        root = ET.fromstring(xml_text(document,version='4.3.0.5',report=ConversionReport()))
        root.find('Components/Component/Part').set('SubFolderIndex','3')
        document = read_xml(ET.tostring(root),report=ConversionReport())
        component = document.one('/Library/Components/Component')
        self.assertEqual(3,component['UnresolvedSubfolderIndex'])
        folders = document.one('/Library/Subfolders')
        with self.assertRaises(ReferenceError):
            folders.add('Folder','Third')
        self.assertEqual(2,len(folders.children('Folder')))
        with self.assertRaises(ReferenceError):
            _ = component['Folder']
        self.assertEqual(3,component['SubfolderIndex'])
        self.assertEqual(1,len(document.references.issues))
        for write,read in ((encode,read_binary),(ascii_text,read_ascii),
                          (lambda doc,**kwargs:xml_text(doc,version='4.3.0.5',**kwargs),read_xml)):
            report = ConversionReport()
            result = read(write(document,report=report),report=ConversionReport()).one('/Library/Components/Component')
            self.assertIsNone(result['Folder'])
            self.assertEqual(-1,result['SubfolderIndex'])
            self.assertIn('unresolved-library-folder',{notice.rule for notice in report.warnings})
            self.assertEqual(3,component['UnresolvedSubfolderIndex'])
            self.assertEqual(1,len(document.references.issues))
        selected = folders.children('Folder')[1]
        component['Folder'] = selected
        self.assertIs(selected,component['Folder'])
        self.assertEqual([],document.references.issues)
        self.assertIsNone(component.child('UnresolvedSubfolderIndex'))
        folders.add('Folder','Third')
        folders.add('Folder','Fourth')
        self.assertIs(selected,component['Folder'])
        self.assertEqual(1,component['SubfolderIndex'])
        document.validate()


if __name__=='__main__':
    unittest.main()
