"""PCB net membership uses identities through ordinary data and record edits."""
from decimal import Decimal
import unittest
from unittest.mock import patch

from lib.common.model import Element, Value
from lib.common.references import Index, Property, ReferenceError
from lib.pcb.model.objects import new_document, new_component, new_pad, new_net


class PcbMembershipTests(unittest.TestCase):
    def design(self):
        document = new_document()
        components, nets = document.one('/Board/Components'), document.one('/Board/Nets')
        first = components.append(new_component('Resistor', 'R1'))
        second = components.append(new_component('Capacitor', 'C1'))
        pad = first.one('Pattern/Pads').append(new_pad('1', x=3, y=6))
        other = first.one('Pattern/Pads').append(new_pad('2'))
        supply, ground = nets.append(new_net('VCC')), nets.append(new_net('GND'))
        return document, first, second, pad, other, supply, ground

    def copied_number(self, document, pad):
        output = document.root.add('Probe', -1)
        document.references.bind(output, pad, Property(output, 'NetNumber'), role='probe')
        return output

    def test_membership_has_one_authority_and_named_reflection(self):
        document, component, _, pad, _, supply, _ = self.design()
        self.assertIsNone(pad['Net'])
        self.assertEqual(pad.get('NetNumber'), -1)
        pad['Net'] = supply
        member = supply.one('Pads/Item')
        self.assertIs(member['Pad'], pad)
        self.assertEqual(member.values, (0, 0))
        self.assertIs(pad['Net'], supply)
        self.assertIsNone(pad.child('NetNumber'))
        self.assertIsNone(pad.child('Number_New'))
        with self.assertRaises(TypeError):
            pad['NetNumber'] = 5
        component['X'], component['Angle'] = 12, Decimal('23.456')
        self.assertEqual(pad['X'], 3)
        self.assertEqual(document.select('/Board/Components/Component',
            where=lambda item: item['X'] >= 12), [component])
        document.validate()

    def test_reassignment_disconnect_and_reorder_refresh_property_users_without_rebuild(self):
        document, first, second, pad, other, supply, ground = self.design()
        copied = self.copied_number(document, pad)
        with patch.object(document.root, 'walk', side_effect=AssertionError('whole document scan')), \
             patch.object(type(document.references), '__iter__', side_effect=AssertionError('whole graph scan')):
            pad['Net'] = ground
            member = ground.one('Pads/Item')
            self.assertEqual(copied.values, (1,))
            first.move_to(first.parent, 1)
            other.move_to(other.parent, 0)
            self.assertEqual(member.values, (1, 1))
            ground.move_to(ground.parent, 0)
            self.assertEqual((pad['NetNumber'], copied.values), (0, (0,)))
            pad['Net'] = supply
            self.assertIs(supply.one('Pads/Item'), member)
            self.assertEqual((pad['NetNumber'], copied.values), (1, (1,)))
            pad['Net'] = None
            self.assertIsNone(pad['Net'])
            self.assertEqual(copied.values, (-1,))
            self.assertEqual(supply.one('Pads').children(), [])
        document.validate()

    def test_bad_retarget_and_cross_document_assignment_leave_the_old_membership(self):
        document, _, _, pad, other, supply, ground = self.design()
        pad['Net'], other['Net'] = supply, ground
        member = supply.one('Pads/Item')
        link = document.references.outgoing(member, role='net-member')[0]
        before = tuple(document.references)
        with self.assertRaisesRegex(ReferenceError, 'already has a net membership'):
            document.references.retarget(link, other)
        foreign = new_document().one('/Board/Nets').append(new_net('Foreign'))
        with self.assertRaisesRegex(ReferenceError, 'outside this PCB'):
            pad['Net'] = foreign
        self.assertEqual(tuple(document.references), before)
        self.assertIs(pad['Net'], supply)
        self.assertIs(member['Pad'], pad)
        document.validate()

    def test_moving_a_member_changes_its_net_and_moving_a_pad_changes_its_component(self):
        document, _, second, pad, _, supply, ground = self.design()
        pad['Net'] = supply
        copied = self.copied_number(document, pad)
        member = supply.one('Pads/Item')
        member.move_to(ground.one('Pads'))
        self.assertIs(pad['Net'], ground)
        self.assertEqual(copied.values, (1,))
        pad.move_to(second.one('Pattern/Pads'))
        self.assertEqual(member.values, (1, 0))
        before = member.parent
        with self.assertRaises((ReferenceError, ValueError)):
            member.move_to(document.root)
        self.assertIs(member.parent, before)
        document.validate()

    def test_component_copy_has_independent_pads_and_document_clone_remaps_members(self):
        document, component, _, pad, _, supply, _ = self.design()
        pad['Net'] = supply
        with self.assertRaisesRegex(ValueError, 'already occupied'):
            document.copy(component)
        copied = document.copy(component, fields={'RefDes': 'R2'})
        self.assertIsNone(copied.one('Pattern/Pads/Pad[1]')['Net'])
        self.assertIs(pad['Net'], supply)
        duplicate = document.clone()
        duplicate_pad = duplicate.one('/Board/Components/Component[1]/Pattern/Pads/Pad[1]')
        duplicate_net = duplicate.one('/Board/Nets/Net[1]')
        self.assertIs(duplicate_pad['Net'], duplicate_net)
        self.assertIs(duplicate_net.one('Pads/Item')['Pad'], duplicate_pad)
        duplicate_pad['Net'] = None
        self.assertIs(pad['Net'], supply)
        document.validate()
        duplicate.validate()

    def test_removing_members_disconnects_pads_and_assigned_pads_are_protected(self):
        document, _, _, pad, _, supply, _ = self.design()
        pad['Net'] = supply
        with self.assertRaises(ReferenceError):
            document.remove(pad)
        document.remove(supply.one('Pads/Item'))
        self.assertIsNone(pad['Net'])
        self.assertEqual(pad['NetNumber'], -1)
        document.remove(pad)
        self.assertIsNone(pad.parent)
        document.validate()

    def test_refdes_prefix_rules_and_atomic_collision_checks_are_shared(self):
        document, first, second, _, _, _, _ = self.design()
        first['RefDes'] = 'R003'
        with self.assertRaisesRegex(ValueError, 'already occupied'):
            second['RefDes'] = 'R3'
        self.assertEqual(second['RefDes'], 'C1')
        self.assertEqual(document.refdes('R').last(), 'R003')
        self.assertEqual(document.refdes('R').first_free(), 'R1')
        collision = new_component('Another', 'R03')
        with self.assertRaisesRegex(ValueError, 'already occupied'):
            first.parent.append(collision)
        self.assertIsNone(collision.parent)
        first['RefDes'] = 'R'
        with self.assertRaisesRegex(ValueError, 'already occupied'):
            second['RefDes'] = 'R0'
        with self.assertRaises(ValueError):
            first['RefDes'] = 'R 1'
        self.assertEqual(first['RefDes'], 'R')

    def test_pcb_named_records_reject_an_unnamed_tail(self):
        document, _, _, pad, _, _, _ = self.design()
        pad._items.insert(0, Value.of(999))  # Deliberately bypass normal named mutation.
        with self.assertRaisesRegex(ValueError, 'unnamed values.*pcb'):
            document.validate()

    def test_enabled_state_and_owner_scope_cannot_orphan_a_membership(self):
        document, first, second, pad, _, supply, ground = self.design()
        pad['Net'] = supply
        for record in (first, supply):
            with self.assertRaisesRegex(ReferenceError, 'disconnect assigned pads'):
                record['Enabled'] = False
            self.assertTrue(record['Enabled'])
            before = record.parent
            with self.assertRaisesRegex(ReferenceError, 'must remain'):
                record.move_to(document.root)
            self.assertIs(record.parent, before)
        ground['Enabled'] = False
        with self.assertRaisesRegex(ReferenceError, 'enabled net'):
            pad['Net'] = ground
        second['Enabled'] = False
        before = pad.parent
        with self.assertRaisesRegex(ReferenceError, 'enabled component'):
            pad.move_to(second.one('Pattern/Pads'))
        self.assertIs(pad.parent, before)
        self.assertIs(pad['Net'], supply)
        document.validate()

    def test_an_unlisted_assignment_remains_independent_of_the_explicit_member_list(self):
        document, first, _, pad, _, supply, ground = self.design()
        copied = self.copied_number(document, pad)
        document.references.bind(pad, supply, role='pad-net')
        self.assertIs(pad['Net'], supply)
        self.assertEqual(supply.one('Pads').children(), [])
        self.assertEqual(copied.values, (0,))
        with self.assertRaisesRegex(ReferenceError, 'disconnect assigned pads'):
            first['Enabled'] = False
        with self.assertRaisesRegex(ReferenceError, 'disconnect assigned pads'):
            supply['Enabled'] = False
        duplicate = document.clone()
        duplicate_pad = duplicate.one('/Board/Components/Component[1]/Pattern/Pads/Pad[1]')
        self.assertIs(duplicate_pad['Net'], duplicate.one('/Board/Nets/Net[1]'))
        with patch.object(type(document.references), '__iter__', side_effect=AssertionError('whole graph scan')):
            pad['Net'] = ground
            self.assertEqual(copied.values, (1,))
            self.assertEqual(ground.one('Pads').children(), [])
            pad['Net'] = None
            self.assertEqual(copied.values, (-1,))
        self.assertIsNone(pad['Net'])
        document.validate()
        duplicate.validate()

    def test_unresolved_assignment_queries_use_the_contact_scope(self):
        document, _, _, pad, other, _, _ = self.design()
        field = pad.add('MissingNet', 42)
        document.references.note(pad, 'pad-net: target index cannot be resolved', Index(field),
                                 collections=(document.one('/Board/Nets'),))

        class NoScan(list):
            def __iter__(self):
                raise AssertionError('whole constraint list scan')

        document.references.issues = NoScan(document.references.issues)
        self.assertIsNone(other['Net'])
        with self.assertRaisesRegex(ReferenceError, 'unresolved net identity'):
            pad['Net']


if __name__ == '__main__':
    unittest.main()
