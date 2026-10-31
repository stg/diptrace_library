"""Library slots remain editable, with format-specific output requirements."""
import unittest

from lib import new_schematic
from lib.common.asc import dumps
from lib.common.binary import BinaryWriter
from lib.schematic.formats.capabilities import DCH
from lib.schematic.formats.dch.cache import read_cache
from lib.schematic.formats.dch.read import Reader
from lib.common.model import Element


def empty_cache(version, path='unused.eli'):
    """A standalone cache section, with one slot and no definitions."""
    writer = BinaryWriter()
    writer.buffer.extend(b'\x07DTSCHEM')
    writer.integer(version)
    writer.text('Project')
    for value in (2, 0, 0, 0):  # Library type/content, folder/library counts.
        writer.integer(value)
    writer.boolean(False)
    for value in (-1, 0, 0, 0, 1, 0):  # Active prefix, links, catalogues, slots, variants.
        writer.integer(value)
    writer.text(path)
    return bytes(writer.buffer)


class CacheSlotConstraintTests(unittest.TestCase):
    def test_earlier_cache_keeps_empty_slots_without_an_unowned_literal_path(self):
        for version in range(34, 45):
            with self.subTest(version=version):
                data = empty_cache(version)
                reader, owner = Reader(data), Element('Schematic')
                self.assertEqual(read_cache(reader, owner), ())
                slot = owner.one('CacheLib/Slots/Slot')
                self.assertEqual(slot.values, (0, ''))
                self.assertFalse(slot.children('Definition'))
                self.assertEqual(reader.pos, len(data))

    def test_current_path_section_requires_a_definition_for_each_slot(self):
        for version in (value for value in DCH.read_versions if value >= 45):
            with self.subTest(version=version):
                reader = Reader(empty_cache(version))
                with self.assertRaisesRegex(ValueError, 'requires at least one definition'):
                    read_cache(reader, Element('Schematic'))

    def test_binary_export_rejects_empty_slots_without_mutating_the_model(self):
        document = new_schematic()
        slot = document.one('/Schematic/CacheLib/Slots').add('Slot', 0, 'library.eli')
        slot['VariablePath'] = '${LIB}/library.eli'
        slot['Model3DFile_Variable'] = 'model.step'
        before = dumps(document, preserve=False)
        for version in DCH.write_versions:
            with self.subTest(version=version):
                with self.assertRaisesRegex(ValueError, 'requires at least one definition'):
                    document.to_dch_bytes(version=version)
                self.assertEqual(dumps(document, preserve=False), before)
        self.assertEqual(slot['LibPath'], 'library.eli')
        self.assertFalse(slot.children('Definition'))


if __name__ == '__main__':
    unittest.main()
