"""Public keys and positional IDs cannot turn a missing pad into a valid link."""
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib import new_schematic, parse_dchxml, parse_dch, ExportReport, ReferenceError
from lib.schematic.model.pads import (empty_pad)
from lib.schematic.model.objects import (new_symbol, new_pattern, new_pin)
from lib.schematic.model.refs import (bind_schematic_references)


PART = '/Schematic/CacheLib/Slots/Slot/Definition/Part'
PATTERN = '/Schematic/CacheLib/Slots/Slot/Definition/Pattern'


class PadKeyTests(unittest.TestCase):
    def test_named_public_key_access_rejects_collisions_before_mutation(self):
        source = self.source()
        pad = source.one(PATTERN+'/Pads/Pad[3]')
        original = pad['Id']
        with self.assertRaisesRegex(ValueError, 'unresolved assignment'):
            pad['Id'] = 5
        self.assertEqual(pad['Id'], original)
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            pad['Id'] = 10
        self.assertEqual(pad['Id'], original)
        pad['Id'] = 200
        self.assertEqual(source.as_dchxml(report=ExportReport()).one(
            '/Source/Library/Components/Component/Part/Pins/Pin[1]').scalar('PadId'), 200)
        source.validate()

    def test_linked_pad_copy_preserves_public_key_uniqueness_before_attachment(self):
        source = self.source()
        source.references.discard_issue(source.references.issues[0])
        source.one(PART+'/Pins/Pin[2]/UnresolvedKeys/Key').detach()
        pad = source.one(PATTERN+'/Pads/Pad[3]')
        before = tuple(source.references)
        with self.assertRaisesRegex(ValueError, 'duplicates another key'):
            source.copy(pad, index=2)
        self.assertEqual(tuple(source.references), before)
        source.validate()

    def source(self):
        document = new_schematic()
        slot = document.one('/Schematic/CacheLib/Slots').add('Slot', 0, '')
        slot.add('VariablePath', '')
        definition = slot.add('Definition', 0)
        part = definition.append(new_symbol('Connector', 'J', placed=False))
        for index, number in enumerate((2, 1)):
            pin = part.one('Pins').append(new_pin(index, placed=False))
            pin.set_field('Number', number)
        pattern = new_pattern('Five pads')
        for index in range(1, 6):
            pad = empty_pad(index)
            pad.set_values(index, str(index), '', index*3, 0)
            pad.set_field('Number_New', index)
            pad.set_field('PadWidth_New', 1)
            pad.set_field('PadHeight_New', 1)
            pattern.one('Pads').insert(pad, index)
        definition.append(pattern)
        bind_schematic_references(document)
        tree = ET.fromstring(document.to_dchxml_bytes())
        for index, pad in enumerate(tree.findall('Library/Library/Patterns/Pattern/Pads/Pad'), 1):
            pad.set('Id', str(index*10))
        pins = tree.findall('Library/Components/Component/Part/Pins/Pin')
        pins[0].set('PadId', '20')
        pins[1].set('PadId', '5')
        return parse_dchxml(ET.tostring(tree)).as_schematic()

    def test_missing_key_stays_unresolved_instead_of_binding_to_the_fifth_pad(self):
        source = self.source()
        pins = source.one(PART).select('Pins/Pin')
        self.assertEqual(pins[0].scalar('Number'), 2)
        self.assertEqual(pins[1].scalar('Number'), -1)
        self.assertEqual(pins[1].one('UnresolvedKeys/Key').values, ('PadId', 5))
        self.assertEqual(len(source.references.issues), 1)
        xml = source.as_dchxml()
        self.assertEqual([pad.scalar('Id') for pad in xml.select('/Source/Library/Library/Patterns/Pattern/Pads/Pad')], [10, 20, 30, 40, 50])
        self.assertEqual([pin.scalar('PadId') for pin in xml.select('/Source/Library/Components/Component/Part/Pins/Pin')], [20, 5])
        again = xml.as_schematic()
        self.assertEqual(len(again.references.issues), 1)
        self.assertEqual(again.one(PART+'/Pins/Pin[2]/UnresolvedKeys/Key').values, ('PadId', 5))
        report = ExportReport()
        binary = parse_dch(source.to_dch_bytes(report=report))
        self.assertEqual(binary.one(PART+'/Pins/Pin[2]').scalar('Number'), -1)
        self.assertIn('pad-public-ids', {row.rule for row in report.infos})
        self.assertIn('unresolved-pad-assignment', {row.rule for row in report.warnings})
        self.assertEqual(pins[1].one('UnresolvedKeys/Key').values, ('PadId', 5))
        self.assertFalse(source.root.changed)

    def test_unresolved_scope_blocks_reordering_until_the_assignment_is_cleared(self):
        source = self.source()
        changed = source.clone()
        pad = changed.one(PATTERN+'/Pads/Pad[2]')
        with self.assertRaises(ReferenceError):
            pad.move_to(pad.parent, 3)
        changed.validate()
        source.references.discard_issue(source.references.issues[0])
        source.one(PART+'/Pins/Pin[2]/UnresolvedKeys/Key').detach()
        pad = source.one(PATTERN+'/Pads/Pad[2]')
        pad.move_to(pad.parent, 3)
        xml = source.as_dchxml()
        self.assertEqual(xml.one('/Source/Library/Components/Component/Part/Pins/Pin[1]').scalar('PadId'), 20)

    def test_editing_a_key_cannot_alias_an_unresolved_assignment(self):
        source = self.source()
        source.one(PATTERN+'/Pads/Pad[2]/Id').set_values(5)
        with self.assertRaisesRegex(ValueError, 'unresolved assignment'):
            source.to_dchxml_bytes()

    def test_current_public_key_edits_follow_the_resolved_target(self):
        source = self.source()
        source.one(PATTERN+'/Pads/Pad[3]/Id').set_values(200)
        xml = source.as_dchxml(report=ExportReport())
        self.assertEqual(xml.one('/Source/Library/Components/Component/Part/Pins/Pin[1]').scalar('PadId'), 200)
        self.assertEqual(xml.as_schematic().one(PART+'/Pins/Pin[1]').scalar('Number'), 2)
        self.assertFalse(source.select('//StoredData'))

    def test_noncolliding_missing_keys_use_the_same_reference_representation(self):
        for key in (0, 77):
            with self.subTest(key=key):
                source = self.source()
                source.one(PART+'/Pins/Pin[2]/UnresolvedKeys/Key').set_argument(1, key)
                for _ in range(3):
                    source = source.as_dchxml(report=ExportReport()).as_schematic()
                    pin = source.one(PART+'/Pins/Pin[2]')
                    self.assertEqual(pin.scalar('Number'), -1)
                    self.assertEqual(pin.one('UnresolvedKeys/Key').values, ('PadId', key))
                    self.assertEqual(len(source.references.issues), 1)


if __name__ == '__main__':
    unittest.main()
