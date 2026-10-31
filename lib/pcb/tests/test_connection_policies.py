"""Connection settings have one scope; membership and display edges are views."""
import unittest
from unittest.mock import patch

from lib.common.model import Element
from lib.common.references import Property, ReferenceError
from lib.pcb.model.connection_policies import effective
from lib.pcb.model.internal_connections import PAIR
from lib.pcb.formats.dip.binary import DipError
from lib.pcb.tests.test_connection_groups import design


class ConnectionPolicyTests(unittest.TestCase):
    def test_import_uses_saved_policy_scope_when_group_order_differs(self):
        result = design(('1', '1', '2', '2'), flags=(False, True), saved_groups=((3, 4), (1, 2)))
        pads = tuple(result.pads.values())
        self.assertEqual(effective(result.components[41]), ((pads[:2], True), (pads[2:], False)))

    def test_inconsistent_saved_group_membership_is_not_silently_reinterpreted(self):
        with self.assertRaisesRegex(DipError, 'disagrees'):
            design(('1', '1', '2', '2'), flags=(True,), saved_groups=((1, 3),))

    def test_import_consumes_cached_membership_and_preserves_each_policy(self):
        result = design(('1', '1', '2', '2'), flags=(True, False))
        component = result.components[41]
        pads = tuple(result.pads.values())
        first, second = component.select('InternalConnections/IntCon')
        self.assertEqual(effective(component), ((pads[:2], True), (pads[2:], False)))
        self.assertIs(first['Pad'], pads[0])
        self.assertEqual(first['Members'], pads[:2])
        self.assertEqual(first['Ratlines'], ((pads[0], pads[1]),))
        self.assertIsNone(first.child('PadId'))
        self.assertIsNone(first.child('Ratlines'))
        self.assertEqual([pad['InternalConnection'] for pad in pads], [0, 0, 1, 1])
        self.assertTrue(all(pad.child('InternalConnection') is None for pad in pads))
        self.assertEqual((first['Id'], second['Id']), (0, 1))

    def test_reordering_updates_both_policy_and_pad_indices_without_global_scans(self):
        result = design(('1', '1', '2', '2'), flags=(True, False))
        document = result.document
        component = result.components[41]
        first, second = component.select('InternalConnections/IntCon')
        pads = tuple(result.pads.values())
        probe = document.root.add('Probe', 0, 0)
        document.references.bind(probe, first, Property(probe, 'Id'), role='policy-probe')
        probe2 = document.root.add('Probe2', 0)
        document.references.bind(probe2, pads[0], Property(probe2, 'InternalConnection'), role='pad-probe')
        with patch.object(document.root, 'walk', side_effect=AssertionError('whole document scan')), \
             patch.object(type(document.references), '__iter__', side_effect=AssertionError('whole graph scan')):
            pads[2].move_to(pads[2].parent, 0)
            self.assertEqual((first['Id'], second['Id']), (1, 0))
            self.assertEqual(probe.values, (1, 0))
            self.assertEqual(probe2.values, (1,))
            self.assertTrue(first['ConnectAll'])

    def test_policy_selector_must_be_local_and_unique_for_its_group(self):
        result = design(('1', '1', '2', '2'))
        first, second = result.components[41].select('InternalConnections/IntCon')
        original = first['Pad']
        for target in (second['Pad'], design(('1', '1')).pads[41, 10]):
            with self.assertRaises(ReferenceError):
                first['Pad'] = target
            self.assertIs(first['Pad'], original)
        first['Pad'] = result.pads[41, 20]
        self.assertEqual(first['Id'], 0)

    def test_topology_changes_preflight_policy_collisions_and_are_atomic(self):
        result = design(('1', '1', '2', '2'), flags=(True, False))
        component = result.components[41]
        with self.assertRaises(ReferenceError):
            result.pads[41, 10]['StringNumber'] = '2'
        self.assertEqual(result.pads[41, 10]['StringNumber'], '1')
        pair = component.one('IntConRecords').append(Element('Item').bind_schema(PAIR))
        pair['Pad1'] = result.pads[41, 20]
        with self.assertRaises(ReferenceError):
            pair['Pad2'] = result.pads[41, 30]
        self.assertIsNone(pair['Pad2'])
        result.document.remove(component.one('InternalConnections/IntCon[2]'))
        pair['Pad2'] = result.pads[41, 30]
        self.assertEqual(effective(component), ((tuple(result.pads.values()), True),))

    def test_target_removal_requires_retargeting_the_setting_first(self):
        result = design(('1', '1', '1'))
        component = result.components[41]
        first, second, third = result.pads.values()
        policy = component.one('InternalConnections/IntCon')
        with self.assertRaises(ReferenceError):
            result.document.remove(first)
        policy['Pad'] = second
        result.document.remove(first)
        self.assertEqual(policy['Members'], (second, third))

    def test_component_copy_and_clone_rebind_the_policy_to_owned_pads(self):
        result = design(('1', '1'), flags=(True,))
        component = result.components[41]
        copied = result.document.copy(component, parent=component.parent, fields={'RefDes': 'U2'})
        self.assertIs(copied.one('InternalConnections/IntCon')['Pad'], copied.one('Pattern/Pads/Pad[1]'))
        self.assertTrue(effective(copied)[0][1])
        cloned = result.document.clone()
        current = cloned.one('/Board/Components/Component[1]')
        self.assertIs(current.one('InternalConnections/IntCon')['Pad'], current.one('Pattern/Pads/Pad[1]'))

    def test_unconfigured_policy_is_an_explicit_error_and_derived_fields_are_readonly(self):
        result = design(('1', '1'))
        component = result.components[41]
        policy = component.one('InternalConnections/IntCon')
        for field, value in (('Members', ()), ('Ratlines', ()), ('Id', 9)):
            with self.assertRaises(TypeError):
                policy[field] = value
        policy['Pad'] = None
        self.assertIsNone(policy['Members'])
        self.assertIsNone(policy['Ratlines'])
        with self.assertRaises(ReferenceError):
            effective(component)
