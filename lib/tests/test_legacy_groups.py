"""Old membership lists are codec input, separate from current group facts."""
import unittest

from lib import ExportReport, new_schematic, parse
from lib.schematic.formats.dch.read import (Reader)
from lib.common.library_codec import discard_legacy_groups
from lib.schematic.model.objects import (new_pattern, new_symbol)
from lib.schematic.model.refs import (bind_schematic_references)


def integer(value):
    return (value+1_000_000).to_bytes(3, 'big')


def obsolete_groups(kinds):
    result = bytearray(integer(2))
    for group in range(2):
        result.extend(bytes((group % 2,))+integer(27-group))
        for kind in range(kinds):
            result.extend(integer(kind+1))
            for member in range(kind+1):
                result.extend(integer((-1, 777, 1_000_007)[member]))
    return bytes(result)


def source():
    current = new_schematic()
    slot = current.one('/Schematic/CacheLib/Slots').add('Slot', 0, '')
    slot.add('VariablePath', '')
    definition = slot.add('Definition', 0)
    part = definition.append(new_symbol('Symbol', 'U', placed=False))
    pattern = definition.append(new_pattern('Footprint'))
    for owner, container, marker in ((part, 'Groups', 'symbol-group-boundary'),
                                     (pattern, 'Pattern_Groups', 'pattern-group-boundary')):
        owner.one(container).add('pt', True, 0, 4, -7)
        values = (marker, 'Editable', 0)+((0,)*7 if owner is part else ())
        owner.one('UserFields').add('UserField', *values)
    bind_schematic_references(current)
    return current


class LegacyGroupTests(unittest.TestCase):
    def test_nonempty_obsolete_lists_do_not_replace_current_groups(self):
        current = source()
        for version in (46, 47, 48):
            with self.subTest(version=version):
                canonical = current.to_dch_bytes(version=version, report=ExportReport())
                changed = canonical
                for name, kinds in (('pattern-group-boundary', 3), ('symbol-group-boundary', 2)):
                    raw = name.encode('utf-16-be')
                    marker = (len(raw)//2).to_bytes(2, 'big')+raw
                    self.assertEqual(changed.count(marker), 1)
                    position = changed.index(marker)
                    self.assertEqual(changed[position-6:position], integer(0)+integer(1))
                    changed = changed[:position-6]+obsolete_groups(kinds)+changed[position-3:]
                loaded = parse(changed, format='dch')
                self.assertTrue(loaded.complete)
                self.assertFalse(loaded.select('//StoredData'))
                self.assertFalse(loaded.select('//SourceGroups'))
                self.assertFalse(loaded.select('//SourcePattern_Groups'))
                self.assertEqual([node.values for node in loaded.select('//Definition/Part/Groups/pt')],
                                 [(True, 0, 4, -7)])
                self.assertEqual([node.values for node in loaded.select('//Definition/Pattern/Pattern_Groups/pt')],
                                 [(True, 0, 4, -7)])
                self.assertEqual(loaded.to_dch_bytes(version=version, report=ExportReport()), canonical)

    def test_discarding_lists_keeps_the_next_record_aligned(self):
        for kinds in (2, 3):
            for count in (0, 2):
                raw = obsolete_groups(kinds) if count else integer(0)
                for version in range(34, 49):
                    header = b'\x07DTSCHEM'+integer(version)
                    reader = Reader(header+raw+integer(123))
                    discard_legacy_groups(reader, range(kinds))
                    self.assertEqual(reader.pos, len(header)+len(raw))
                    self.assertEqual(reader.integer(), 123)

    def test_unknown_storage_wrappers_cannot_hide_unmapped_content(self):
        current = source()
        current.one('//Definition/Part').add('StoredData').add('UnknownMeaning', 42)
        for destination in ('dch', 'asc', 'dchxml'):
            with self.subTest(destination=destination):
                with self.assertRaisesRegex(ValueError, 'unsupported schematic field|no .*projection'):
                    getattr(current, 'to_'+destination+'_bytes')(report=ExportReport())


if __name__ == '__main__':
    unittest.main()
