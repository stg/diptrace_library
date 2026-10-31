"""Unplaced footprints have physical data and definition-local pad identities."""
import unittest
from unittest.mock import patch

from lib.common.footprint_objects import new_pad, new_pattern
from lib.common.footprint_records import PAD, PASTE_SEGMENT
from lib.common.references import ReferenceError
from lib.common.conversion import ConversionReport, import_diagnostics
from lib.pcb.formats.assembly.assemble import assemble_core
from lib.pcb.formats.dip.binary import DipError
from lib.pcb.model import library_records
from lib.pcb.model.library_relations import PIN_PAD_ROLE
from lib.pcb.tests.test_core_assembly import fixture


def design(*, invalid_marker=False):
    decoded = fixture()
    slot = decoded.board.add('CacheLib').add('Slots').add('Slot', 0, 'generic.lib')
    for variant in range(2):
        definition = slot.add('Definition', variant)
        symbol = definition.add('Part', 'Device', 'U')
        symbol.add('PartType', 0)
        pins = symbol.add('Pins')
        for index, key in enumerate((3, 1)):
            pin = pins.add('Pin', index, index, 0)
            pin.add('Enabled', True)
            pin.add('Number', key)
        pattern = definition.append(new_pattern('Package'))
        pads = pattern.one('Pads')
        keys = (-1, 1, -1, 1 if invalid_marker else 3, -1)
        for index, key in enumerate(keys):
            pad = pads.append(new_pad(str(index), index=index))
            pad['Number_New'] = key
        pattern.one('InternalConnections').add('IntCon', 3, 1)
        pattern.one('Pads/Pad[2]/PadMask_TopSegments').add('pt', 1, 2, 3, 4)
    return assemble_core(decoded)


class LibraryFootprintTests(unittest.TestCase):
    def test_import_consumes_handles_and_non_pad_slots_without_electrical_membership(self):
        result = design()
        local = result.cached_footprints[0]
        pads = local.pattern.one('Pads').children()
        self.assertEqual([pad['StringNumber'] for pad in pads], ['1', '3'])
        self.assertEqual(set(local.pads), {1, 3})
        self.assertIs(local.pads[3], pads[1])
        self.assertIs(pads[0].schema, library_records.PAD)
        self.assertIs(pads[0].schema.fields['PadHole'], PAD.fields['PadHole'])
        self.assertNotIn('Net', pads[0].schema.fields)
        self.assertNotIn('Number_New', pads[0].schema.fields)
        self.assertIsNone(pads[0].child('Number_New'))
        self.assertEqual([pad['Index'] for pad in pads], [0, 1])
        symbol = local.pattern.parent.one('Part')
        self.assertEqual([pin['Number'] for pin in symbol.select('Pins/Pin')], [2, 1])
        self.assertEqual(local.pattern.one('InternalConnections/IntCon').values, (2, 1))
        segment = pads[0].one('PadMask_TopSegments/pt')
        self.assertIs(segment.schema, PASTE_SEGMENT)
        segment['X2'] = 8
        self.assertEqual(segment.values, (1, 2, 8, 4))

    def test_pad_edits_reorder_and_retarget_update_local_users_without_global_scans(self):
        result = design()
        document, local = result.document, result.cached_footprints[0]
        pair = local.pattern.one('InternalConnections/IntCon')
        symbol = local.pattern.parent.one('Part')
        with patch.object(document.root, 'walk', side_effect=AssertionError('whole-document scan')), \
             patch.object(type(document.references), '__iter__', side_effect=AssertionError('whole-graph scan')):
            local.pads[3].move_to(local.pattern.one('Pads'), 0)
            self.assertEqual(pair.values, (1, 2))
            self.assertEqual([pin['Number'] for pin in symbol.select('Pins/Pin')], [1, 2])
            local.pads[3]['StringNumber'] = 'Exposed pad'
            pair['Pad2'] = local.pads[3]
            self.assertEqual(pair.values, (1, 1))
            link = document.references.outgoing(symbol, role=PIN_PAD_ROLE)[0]
            document.references.retarget(link, local.pads[1])
            self.assertEqual(symbol.one('Pins/Pin[1]')['Number'], 2)

    def test_foreign_component_targets_and_referenced_pad_removal_are_atomic(self):
        result = design()
        document = result.document
        first, other = result.cached_footprints
        pair = first.pattern.one('InternalConnections/IntCon')
        symbol = first.pattern.parent.one('Part')
        link = document.references.outgoing(symbol, role=PIN_PAD_ROLE)[0]
        slot = first.pattern.parent.parent
        foreign = document.copy(slot, parent=slot.parent)
        foreign_pad = foreign.one('Definition[1]/Pattern/Pads/Pad[2]')
        with self.assertRaises(ReferenceError):
            document.references.retarget(link, foreign_pad)
        with self.assertRaises(ReferenceError):
            pair['Pad1'] = other.pads[3]
        with self.assertRaises(ReferenceError):
            document.remove(first.pads[3])
        with self.assertRaises(ReferenceError):
            first.pads[3].move_to(other.pattern.one('Pads'))
        self.assertIs(pair['Pad1'], first.pads[3])
        self.assertIs(first.pads[3].parent, first.pattern.one('Pads'))
        self.assertEqual(symbol.one('Pins/Pin[1]')['Number'], 2)
        with self.assertRaises(ReferenceError):
            symbol['PartType'] = 1
        self.assertEqual(symbol['PartType'], 0)

    def test_multipart_sections_share_the_imported_footprint_without_an_ordinal_dependency(self):
        result = design()
        first, second = result.cached_footprints
        slot = first.pattern.parent.parent
        first_part, second_part = first.pattern.parent.one('Part'), second.pattern.parent.one('Part')
        link = result.document.references.outgoing(second_part, role=PIN_PAD_ROLE)[0]
        self.assertIs(link.target, first.pads[3])
        first.pads[3].move_to(first.pattern.one('Pads'), 0)
        self.assertEqual(first_part.one('Pins/Pin[1]')['Number'], 1)
        self.assertEqual(second_part.one('Pins/Pin[1]')['Number'], 1)
        self.assertEqual(second.pattern.one('InternalConnections/IntCon').values, (2, 1))
        first.pattern.parent.move_to(slot, 1)
        self.assertIs(result.document.references.outgoing(second_part, role=PIN_PAD_ROLE)[0].target, first.pads[3])

    def test_definition_copy_and_document_clone_remap_all_local_assignments(self):
        result = design()
        definition = result.cached_footprints[0].pattern.parent
        copied = result.document.copy(definition, parent=definition.parent)
        pair = copied.one('Pattern/InternalConnections/IntCon')
        copied_pad = copied.one('Pattern/Pads/Pad[2]')
        self.assertIs(pair['Pad1'], copied_pad)
        self.assertIsNot(pair['Pad1'], result.cached_footprints[0].pads[3])
        copied_pad.move_to(copied_pad.parent, 0)
        self.assertEqual(copied.one('Part/Pins/Pin[1]')['Number'], 1)
        self.assertEqual(definition.one('Part/Pins/Pin[1]')['Number'], 2)
        clone = result.document.clone()
        target = clone.one('/Board/CacheLib/Slots/Slot/Definition[1]/Pattern/Pads/Pad[2]')
        cloned_pair = clone.one('/Board/CacheLib/Slots/Slot/Definition[1]/Pattern/InternalConnections/IntCon')
        self.assertIs(cloned_pair['Pad1'], target)

    def test_an_invalid_pad_marker_does_not_retarget_a_pair_to_another_pad(self):
        with self.assertRaisesRegex(DipError, 'unresolved cached internal connection'):
            design(invalid_marker=True)

    def test_a_pin_to_a_deleted_cached_pad_remains_explicit_without_retargeting(self):
        decoded = fixture()
        definition = decoded.board.add('CacheLib').add('Slots').add('Slot', 0, '').add('Definition', 0)
        symbol = definition.add('Part', 'Device', 'U')
        symbol.add('PartType', 0)
        pin = symbol.add('Pins').add('Pin', 0, 0, 0)
        pin.add('Enabled', True)
        pin.add('Number', 1)
        pattern = definition.append(new_pattern('Package'))
        for index, marker in enumerate((-1, -1, 2, -1)):
            pad = pattern.one('Pads').append(new_pad(str(index), index=index))
            pad['Number_New'] = marker

        @import_diagnostics('dip')
        def load():
            return assemble_core(decoded).document

        report = ConversionReport()
        document = load(report=report)
        self.assertEqual(pin['Number'], 1)
        self.assertTrue(document.references.unresolved_slot(pin.one('Number')))
        self.assertFalse(document.references.outgoing(symbol, role=PIN_PAD_ROLE))
        self.assertEqual(len([notice for notice in report.warnings if notice.rule == 'unresolved-reference']), 1)
        # A surviving pad now has current number 1. That coincidence cannot
        # reinterpret the deleted source assignment or acquire its connection.
        self.assertEqual(pattern.one('Pads/Pad')['StringNumber'], '2')
        with self.assertRaises(ReferenceError):
            pattern.one('Pads/Pad').detach()


if __name__ == '__main__':
    unittest.main()
