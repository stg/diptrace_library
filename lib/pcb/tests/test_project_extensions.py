"""Project metadata, generated-table settings and stored teardrops stay editable."""
from decimal import Decimal
import unittest

from lib.common.binary import BinaryWriter
from lib.common.library_codec import CachedDefinitionInput
from lib.common.model import Element
from lib.pcb.formats.dip.project import read_project_extensions
from lib.pcb.formats.dip.read import Reader
from lib.pcb.formats.dip.teardrops import read_teardrops


def stream(version):
    writer = BinaryWriter()
    writer.buffer.extend(b'\x07DTBOARD')
    writer.integer(version)
    return writer


def values(writer, kind, *items):
    for item in items:
        getattr(writer, kind)(item)


class ProjectExtensionTests(unittest.TestCase):
    def test_project_lists_table_configuration_and_resources_have_separate_owners(self):
        writer = stream(50)
        values(writer, 'integer', 2)
        values(writer, 'text', 'Full', 'Reduced')
        values(writer, 'integer', 1, 1)  # Component exclusion.
        values(writer, 'integer', 2, 1, 0, 2, 1, 2)  # Table row memberships.
        values(writer, 'integer', 1, 2)
        values(writer, 'number', 3, 6)
        values(writer, 'boolean', True, False, True, False, True)
        values(writer, 'text', 'Reduced', '.')
        values(writer, 'integer', 1, 2, 1)
        writer.number(12)
        writer.text('Manufacturer')
        writer.boolean(True)
        writer.text('resources/logo.png')
        writer.integer(3)
        writer.number(25)
        writer.boolean(True)  # Rotate markings with the component.
        writer.integer(1)
        values(writer, 'number', 1, 2, 3, 4, 5, 6, 7)
        writer.boolean(False)
        writer.integer(1)
        writer.number(9)
        writer.integer(2)
        values(writer, 'number', 12, 15, 1.5)
        writer.boolean(True)
        writer.integer(2)
        values(writer, 'boolean', False, True)
        writer.integer(17)
        board = Element('Board')
        board.add('Settings')
        component = board.add('Components').add('Component')
        component.add('Pattern').add('Model3D')
        table = board.add('Tables').add('Table')
        shape = board.add('Shapes').add('Shape')
        definition = Element('Definition')
        definition.add('Pattern').add('Model3D')
        reader = Reader(bytes(writer.buffer))
        read_project_extensions(reader, board, (CachedDefinitionInput(definition, ()),))
        self.assertEqual(reader.integer(), 17)
        self.assertEqual(reader.pos, len(reader.data))
        self.assertEqual(board.one('Settings/AssemblyVariants/AssemblyVariant[2]').values, ('Reduced',))
        self.assertEqual(component.one('AssemblyExclude/Item').values, (1,))
        self.assertEqual(table.one('AutoUpdate/Columns/Column')['Name'], 'Manufacturer')
        self.assertTrue(table.one('AutoUpdate')['BomTotal'])
        self.assertEqual(table.one('RowComponents/Row[2]/Item[2]').values, (2,))
        self.assertEqual(shape['RasterIndex'], 3)
        self.assertEqual(shape['Picture_File'], 'resources/logo.png')
        self.assertEqual(board.one('Panel')['HoleKeepout'], 7)
        self.assertEqual(board.one('Panel/VertTabsY/Item[2]').values, (15,))
        self.assertEqual(board.one('Panel')['CombinedRadius'], Decimal('1.5'))
        self.assertIsNone(board.one('Panel').child('PanelizeSingle'))
        self.assertTrue(board['CompRotate'])
        self.assertFalse(component.one('Pattern/Model3D')['KeepPins'])
        self.assertTrue(definition.one('Pattern/Model3D')['KeepPins'])

    def test_teardrop_settings_and_saved_polygons_remain_distinct(self):
        writer = stream(49)
        for _ in range(2):
            values(writer, 'integer', 1, 2, 0, -1)
            values(writer, 'number', .7, .3, 2, 1, 1.2, 1.5)
        values(writer, 'integer', 1, 0, 1, 1)
        values(writer, 'number', 3, 6)
        writer.integer(2)
        values(writer, 'number', 3, 6, 4, 7)
        writer.integer(17)
        board = Element('Board')
        pad = board.add('Components').add('Component').add('Pattern').add('Pads').add('Pad')
        net = board.add('Nets').add('Net')
        net.add('Traces').add('Trace')
        reader = Reader(bytes(writer.buffer))
        read_teardrops(reader, board)
        self.assertEqual(reader.integer(), 17)
        self.assertEqual(reader.pos, len(reader.data))
        self.assertEqual(pad.one('TeardropParams')['Smd'], 2)
        self.assertEqual(pad.one('TeardropParams')['TJunc'], -1)
        self.assertEqual(net.one('TeardropParams')['PadViaWidth'], Decimal('.7'))
        self.assertEqual(net.one('Traces/Trace/ConnectedTeardrops/Item').values, (0,))
        self.assertEqual(net.one('Teardrops/Teardrop')['Lay'], 1)
        self.assertEqual(net.one('Teardrops/Teardrop/Points/Point[2]')['Y'], 7)

    def test_sections_are_absent_before_their_revisions(self):
        for version, function in ((48, read_teardrops), (49, read_project_extensions)):
            writer = stream(version)
            writer.integer(17)
            reader = Reader(bytes(writer.buffer))
            if function is read_teardrops:
                function(reader, Element('Board'))
            else:
                board = Element('Board')
                function(reader, board, ())
                self.assertTrue(board['CompRotate'])
            self.assertEqual(reader.integer(), 17)


if __name__ == '__main__':
    unittest.main()
