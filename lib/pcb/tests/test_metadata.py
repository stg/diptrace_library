"""PCB metadata gates preserve shared footprint and classification meanings."""
import unittest

from lib.common.binary import BinaryWriter
from lib.common.model import Element
from lib.pcb.formats.dip.metadata import read_metadata_extensions
from lib.pcb.formats.dip.read import Reader


def metadata_fixture(version):
    writer = BinaryWriter()
    writer.buffer.extend(b'\x07DTBOARD')
    writer.integer(version)
    if version > 35:
        writer.integer(0)
        writer.integer(1)
    if version > 36:
        writer.integer(1)
        writer.integer(2)
    if version > 37:
        for index in range(2):
            writer.integer(index)
            for text in ('part.pdf', 'Supplier', 'Footprints'):
                writer.text(text)
            writer.integer(4)
            writer.integer(1)
            writer.text('Two terminals')
            writer.text('Surface')
            writer.integer(5)
            writer.integer(6)
            writer.text('Components')
            writer.integer(7)
            writer.integer(1)
            writer.text('Passive')
            writer.text('Resistor')
            writer.integer(8)
            writer.integer(9)
            writer.integer(2)
            writer.text('0603')
            writer.text('0805')
    writer.integer(17)
    return bytes(writer.buffer)


class MetadataTests(unittest.TestCase):
    def test_versions_without_a_cache_initialize_an_empty_active_selection(self):
        from types import SimpleNamespace
        from lib.pcb.formats.dip.cache import read_cache
        for version in (31, 38):
            board = Element('Board')
            reader = SimpleNamespace(header=SimpleNamespace(version=version))
            self.assertEqual(read_cache(reader, board), ())
            self.assertEqual(board['DesignCache_Count'], -1)
            self.assertEqual(board.one('DesignCache_Links').children(), [])

    def test_units_pour_modes_and_classifications_use_their_distinct_gates(self):
        for version in (31, 35, 36, 37, 38, 54, 62):
            with self.subTest(version=version):
                board = Element('Board')
                components = board.add('Components')
                pours = board.add('CopperPours')
                for _ in range(2):
                    components.add('Component').add('Pattern').add('Model3D')
                    pours.add('CopperPour')
                reader = Reader(metadata_fixture(version))
                read_metadata_extensions(reader, board)
                self.assertEqual(reader.integer(), 17)
                self.assertEqual(reader.pos, len(reader.data))
                self.assertEqual([c.one('Pattern/Model3D')['Units'] for c in components.children()],
                                 [0, 1] if version > 35 else [-1, -1])
                self.assertEqual([p['RatlineMode'] for p in pours.children()],
                                 [1, 2] if version > 36 else [0, 0])
                component = components.children()[0]
                pattern = component.one('Pattern')
                if version > 37:
                    self.assertEqual(component['Manufacturer'], 'Supplier')
                    self.assertEqual(component['Datasheet'], 'part.pdf')
                    self.assertEqual(pattern['Mounting'], 0)
                    self.assertEqual(pattern.one('Pattern_CategoryTypes/CategoryType').values,
                                     ('Two terminals', 'Surface', 5, 6))
                    self.assertEqual(component.one('Component_CategoryTypes/CategoryType').values,
                                     ('Passive', 'Resistor', 8, 9))
                    self.assertEqual([n.values for n in pattern.one('PossibleNames').children()],
                                     [('0603',), ('0805',)])
                else:
                    self.assertEqual(component['Manufacturer'], '')
                    self.assertEqual(component['Component_CategoryIndex'], -1)
                    self.assertEqual(pattern['Mounting'], -1)
                    self.assertEqual(pattern['Pattern_CategoryIndex'], -1)


if __name__ == '__main__':
    unittest.main()
