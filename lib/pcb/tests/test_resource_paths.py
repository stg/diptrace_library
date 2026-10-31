"""Resource paths remain explicit data, including paths in empty cache slots."""
import unittest

from lib.common.binary import BinaryWriter
from lib.common.model import Element
from lib.pcb.formats.dip.paths import read_variable_paths, read_column_titles
from lib.pcb.formats.dip.read import Reader


class ResourcePathTests(unittest.TestCase):
    def test_paths_and_empty_slot_paths_do_not_require_companion_files(self):
        for version in (53, 54, 62):
            with self.subTest(version=version):
                writer = BinaryWriter()
                writer.buffer.extend(b'\x07DTBOARD')
                writer.integer(version)
                for path in ('related.dch', 'parts.lib', 'package.step', 'logo.png',
                             'parts', 'catalog.lib', 'cached.lib', 'cached.step',
                             'empty.lib', 'empty.step', '%PROJECT_DIR%'):
                    writer.text(path)
                writer.boolean(True)
                writer.boolean(False)
                if version > 53:
                    writer.text('Reference')
                writer.integer(17)
                board = Element('Board')
                board.add('Panel')
                component = board.add('Components').add('Component')
                component.add('Pattern').add('Model3D')
                shape = board.add('Shapes').add('Shape')
                board.add('ProjectLibs_Folders').add('Folder', 'parts')
                board.add('ProjectLibs_Libs').add('Lib', 'catalog.lib')
                slots = board.add('CacheLib').add('Slots')
                full = slots.add('Slot', 0, 'cached.lib')
                full.add('Definition').add('Pattern').add('Model3D')
                empty = slots.add('Slot', 1, 'empty.lib')
                column = board.add('Tables').add('Table').add('AutoUpdate').add('Columns').add('Column')
                reader = Reader(bytes(writer.buffer))
                self.assertFalse(read_variable_paths(reader, board))
                read_column_titles(reader, board)
                self.assertEqual(reader.integer(), 17)
                self.assertEqual(reader.pos, len(reader.data))
                self.assertEqual(board['ProjectDir'], '%PROJECT_DIR%')
                self.assertEqual(component['LibPath_Variable'], 'parts.lib')
                self.assertEqual(shape['Picture_File_Variable'], 'logo.png')
                self.assertEqual(full.one('Definition/Pattern/Model3D')['Model3DFile_Variable'], 'cached.step')
                self.assertEqual(empty['Model3DFile_Variable'], 'empty.step')
                self.assertTrue(board.one('Panel')['PanelizeSingle'])
                if version > 53:
                    self.assertEqual(column['Title'], 'Reference')
                else:
                    self.assertIsNone(column.child('Title'))

    def test_old_input_does_not_consume_variable_path_extensions(self):
        writer = BinaryWriter()
        writer.buffer.extend(b'\x07DTBOARD')
        writer.integer(52)
        writer.integer(17)
        reader = Reader(bytes(writer.buffer))
        self.assertFalse(read_variable_paths(reader, Element('Board')))
        self.assertEqual(reader.integer(), 17)


if __name__ == '__main__':
    unittest.main()
