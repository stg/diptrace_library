"""Authored internal pad pairs retain identity during local data edits."""
import unittest
from unittest.mock import patch

from lib.common.model import Value
from lib.common.references import Property, ReferenceError
from lib.pcb.formats.assembly.assemble import assemble_core
from lib.pcb.formats.dip.binary import DipError
from lib.pcb.model.internal_connections import PAIR
from lib.pcb.tests.test_core_assembly import fixture


def design():
    decoded = fixture()
    decoded.board.one('Components/Component').add('InternalConnection_Records').add('pt', 12, 5)
    return assemble_core(decoded)


class InternalConnectionTests(unittest.TestCase):
    def test_import_resolves_saved_keys_and_derives_compact_public_positions(self):
        result = design()
        component = result.components[41]
        pair = component.one('IntConRecords/Item')
        self.assertIs(pair.schema, PAIR)
        self.assertIs(pair['Pad1'], result.pads[41, 12])
        self.assertIs(pair['Pad2'], result.pads[41, 5])
        self.assertEqual(pair.values, (2, 1))
        self.assertFalse(any(isinstance(item, Value) for item in pair.items))
        self.assertIsNone(component.child('InternalConnection_Records'))

    def test_pad_reorder_and_endpoint_edit_update_consumers_without_global_scans(self):
        result = design()
        document = result.document
        pair = result.components[41].one('IntConRecords/Item')
        result.components[41].one('InternalConnections/IntCon')['Pad'] = pair['Pad1']
        probe = document.root.add('Probe', 0, 0)
        document.references.bind(probe, pair, Property(probe, 'X'), Property(probe, 'Y', argument=1), role='probe')
        with patch.object(document.root, 'walk', side_effect=AssertionError('whole document scan')), \
             patch.object(type(document.references), '__iter__', side_effect=AssertionError('whole graph scan')):
            result.pads[41, 12].move_to(pair['Pad1'].parent, 0)
            self.assertEqual(probe.values, (1, 2))
            pair['Pad2'] = pair['Pad1']
            self.assertEqual(probe.values, (1, 1))

    def test_foreign_pad_and_target_deletion_fail_atomically(self):
        result = design()
        pair = result.components[41].one('IntConRecords/Item')
        original = pair['Pad1']
        with self.assertRaises(ReferenceError):
            pair['Pad1'] = design().pads[41, 12]
        self.assertIs(pair['Pad1'], original)
        with self.assertRaises(ReferenceError):
            result.document.remove(original)
        self.assertIsNotNone(original.parent)

    def test_component_copy_remaps_connections_to_its_owned_pads(self):
        result = design()
        component = result.components[41]
        copied = result.document.copy(component, parent=component.parent, fields={'RefDes': 'U2'})
        pair = copied.one('IntConRecords/Item')
        self.assertIs(pair['Pad1'], copied.one('Pattern/Pads/Pad[2]'))
        self.assertIs(pair['Pad2'], copied.one('Pattern/Pads/Pad[1]'))
        self.assertIsNot(pair['Pad1'], result.pads[41, 12])
        with self.assertRaises(ReferenceError):
            pair['Pad1'] = result.pads[41, 12]
        with self.assertRaises(ReferenceError):
            pair.move_to(component.one('IntConRecords'))
        self.assertIs(pair.parent, copied.one('IntConRecords'))

    def test_unresolved_source_pad_key_is_not_reinterpreted_as_an_array_position(self):
        decoded = fixture()
        decoded.board.one('Components/Component').add('InternalConnection_Records').add('pt', 1, 5)
        with self.assertRaisesRegex(DipError, 'unresolved internal connection'):
            assemble_core(decoded)


if __name__ == '__main__':
    unittest.main()
