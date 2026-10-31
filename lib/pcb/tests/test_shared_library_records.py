"""PCB cache decoding reuses encodings while retaining family meanings."""
import unittest
from decimal import Decimal

from lib import new_schematic
from lib.common.binary import BinaryWriter
from lib.common.model import Element
from lib.common.footprint_codec import read_pattern_extensions, write_pattern_extensions
from lib.common.symbol_codec import read_symbol_extensions, write_symbol_extensions
from lib.schematic.formats.dch.write import Writer
from lib.schematic.model.new import fields
from lib.schematic.model.objects import new_pattern, new_symbol, new_pin
from lib.schematic.model.refs import bind_schematic_references
from lib.pcb.formats.dip.cache import read_cache
from lib.pcb.formats.dip.read import Reader


class SharedLibraryTests(unittest.TestCase):
    def test_shared_library_syntax_respects_family_specific_field_meaning(self):
        source = new_schematic()
        slot = source.one('/Schematic/CacheLib/Slots').add('Slot', 0, 'generic.lib')
        slot.add('VariablePath', 'generic.lib')
        definition = slot.add('Definition', 0)
        part = definition.append(new_symbol('Reference', 'U', placed=False))
        pattern = definition.append(new_pattern('Footprint'))
        part['Manufacturer'] = 'Supplier'
        part['ModelNote'] = 'docs/device.pdf'
        pattern.one('Model3D')['Units'] = 1
        pattern['Pattern_Manufacturer'] = 'Footprint supplier'
        pattern['Width'] = 10
        pattern['Height'] = 20
        terminal = pattern.add('PadTerminal', 0)
        fields(terminal, Type=3, X=1, Y=2, Angle=.75, ShapeWidth=3, ShapeHeight=4, ShapeCorner=.2)
        terminal.add('ShapePoints').add('pt', 1, 2)
        pattern.one('PadMask_TopSegments').add('pt', 1, 2, 3, 4)
        shape = pattern.one('Shapes/Shape[1]')
        shape.one('TextLine').add('pt', 'Reference text')
        shape.one('Points_New').add('pt', 1, 2)
        shape['TextAngle'] = .1234
        shape['LineSpacing'] = 1.5
        pin = part.one('Pins').append(new_pin(0, placed=False))
        pin['Name'] = 'IN'
        pin['StringNumber'] = '1'
        bind_schematic_references(source)
        encoder = Writer(version=46)
        encoder.cache(source.one('/Schematic'))
        write_pattern_extensions(encoder, pattern)
        write_symbol_extensions(encoder, part)
        header = BinaryWriter()
        header.buffer.extend(b'\x07DTBOARD')
        header.integer(54)
        header.buffer.extend(encoder.buffer)
        header.integer(17)
        reader = Reader(bytes(header.buffer))
        board = Element('Board')
        inputs = read_cache(reader, board)
        actual = inputs[0].definition
        read_pattern_extensions(reader, actual.one('Pattern'))
        read_symbol_extensions(reader, actual.one('Part'))
        self.assertEqual(reader.integer(), 17)
        self.assertEqual(reader.pos, len(reader.data))
        self.assertEqual(len(inputs), 1)
        self.assertEqual(actual.one('Part')['Manufacturer'], 'Supplier')
        self.assertEqual(actual.one('Part')['Datasheet'], 'docs/device.pdf')
        self.assertIsNone(actual.one('Part').child('ModelNote'))
        self.assertEqual(part['ModelNote'], 'docs/device.pdf')
        self.assertEqual(actual.one('Part/Pins/Pin')['Name'], 'IN')
        self.assertEqual(actual.one('Pattern').values, ('Footprint',))
        self.assertEqual(actual.one('Pattern/Model3D')['Units'], 1)
        self.assertEqual(actual.source.format, 'dip')
        self.assertEqual(board.one('CacheLib/Slots/Slot').values, (0, 'generic.lib'))
        self.assertEqual(actual.one('Pattern')['Pattern_Manufacturer'], 'Footprint supplier')
        self.assertEqual(actual.one('Pattern/PadTerminal/ShapePoints/pt').values, (1, 2))
        self.assertEqual(actual.one('Pattern/PadMask_TopSegments/pt').values, (1, 2, 3, 4))
        self.assertEqual(actual.one('Pattern/Shapes/Shape[1]')['TextAngle'], Decimal('.1234'))
        self.assertEqual(actual.one('Pattern/Shapes/Shape[1]/TextLine/pt').values, ('Reference text',))

    def test_cache_is_absent_before_the_board_cache_revision(self):
        header = BinaryWriter()
        header.buffer.extend(b'\x07DTBOARD')
        header.integer(38)
        header.integer(17)
        reader = Reader(bytes(header.buffer))
        board = Element('Board')
        self.assertEqual(read_cache(reader, board), ())
        self.assertEqual(reader.integer(), 17)
        self.assertIsNone(board.child('CacheLib'))


if __name__ == '__main__':
    unittest.main()
