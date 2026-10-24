"""A net's ordered identity members supply both format occurrences."""
import unittest

from lib import ConversionReport, Element, Guard, Index, Property, ReferenceError, new_schematic, parse
from lib.schematic.model.new import fields
from lib.schematic.model.objects import new_pin, new_symbol, new_wire
from lib.schematic.model.refs import bind_schematic_references, connectivity_mismatches
from lib.common.structural_edits import assembly


def design():
    doc = new_schematic()
    # Assemble paired legacy numeric occurrences, then exercise normalization.
    doc._automatic_structure = False
    part = doc.one('/Schematic/Components').append(new_symbol('Device', 'U1'))
    pins = [part.one('Pins').append(new_pin(index)) for index in range(3)]
    nets = doc.one('/Schematic/Nets')
    for index, name in enumerate(('A', 'B')):
        net = nets.add('Net', name)
        fields(net, Number=index, Enabled=True, UniteByName=False, ConnectPinByName=False,
               Locked=False, ActiveLine=-1, ActivePoint=-1, Width=-1, Clearance=-1,
               NetClass=0, CustomColor=False, WireColor=0, Global=False, HiddenId=index)
        net.add('Parts')
        net.add('Lines')
    pins[0].set_field('NetNumber', 0)
    pins[1].set_field('NetNumber', 0)
    # Preserve meaningful member ordering, independent of pin array order.
    nets.children()[0].one('Parts').add('pt', 0, 1)
    nets.children()[0].one('Parts').add('pt', 0, 0)
    bind_schematic_references(doc)
    doc._automatic_structure = True
    return doc, pins, nets.children()


class MembershipTests(unittest.TestCase):
    def copied_number(self, doc, pin, name='Copied'):
        copy = doc.root.add(name, pin['NetNumber'])
        doc.references.bind(copy, pin, Property(copy, 'NetNumber'))
        return copy

    def guarded_number(self, doc, pin, net):
        copy = self.copied_number(doc, pin)
        target = copy.add('Target', net._ordinal())
        doc.references.bind(copy, net, Index(target), guards=(Guard(copy, copy.values),))
        return copy

    def test_import_consolidates_duplicate_occurrences_without_losing_order(self):
        doc, pins, nets = design()
        members = nets[0].select('Parts/pt')
        self.assertEqual([member['Pin'] for member in members], [pins[1], pins[0]])
        self.assertEqual([member.values for member in members], [(0, 1), (0, 0)])
        self.assertEqual(members[0].items, ())
        self.assertEqual(pins[0].one('NetNumber').items, ())
        self.assertIs(pins[0]['Net'], nets[0])
        self.assertFalse(any(reference.role == 'pin-net' for reference in doc.references))
        self.assertEqual(connectivity_mismatches(doc), [])

    def test_assignment_and_disconnection_update_both_views_without_rebuild(self):
        doc, pins, nets = design()
        member = nets[0].select('Parts/pt')[1]
        pins[0]['Net'] = nets[1]
        self.assertIs(nets[1].one('Parts/pt'), member)
        self.assertIs(member['Pin'], pins[0])
        self.assertEqual(pins[0]['NetNumber'], 1)
        self.assertEqual(len(nets[0].select('Parts/pt')), 1)
        pins[0]['Net'] = None
        self.assertIsNone(pins[0]['Net'])
        self.assertEqual(pins[0]['NetNumber'], -1)
        self.assertEqual(nets[1].select('Parts/pt'), [])
        pins[2].set('Net', nets[1])
        self.assertIs(nets[1].one('Parts/pt')['Pin'], pins[2])
        self.assertEqual(connectivity_mismatches(doc), [])

    def test_first_assignment_and_disconnection_propagate_calculated_copy_chains(self):
        doc, pins, nets = design()
        copy = self.copied_number(doc, pins[2])
        last = doc.root.add('Last', -1)
        doc.references.bind(last, copy, Property(last))
        pins[2]['Net'] = nets[1]
        self.assertEqual((copy.values, last.values), ((1,), (1,)))
        pins[2]['Net'] = None
        self.assertEqual((copy.values, last.values), ((-1,), (-1,)))
        doc.validate()

    def test_first_assignment_guard_failure_leaves_no_unbound_member(self):
        doc, pins, nets = design()
        copy = self.guarded_number(doc, pins[2], nets[0])
        members = nets[1].one('Parts').children()
        count = len(doc.references)
        with self.assertRaisesRegex(ReferenceError, 'reference mode'):
            pins[2]['Net'] = nets[1]
        self.assertEqual(nets[1].one('Parts').children(), members)
        self.assertEqual(len(doc.references), count)
        self.assertEqual(copy.values, (-1,))
        self.assertIsNone(pins[2]['Net'])
        doc.validate()

    def test_disconnection_guard_failure_keeps_member_and_copies(self):
        doc, pins, nets = design()
        copy = self.guarded_number(doc, pins[0], nets[0])
        member = nets[0].select('Parts/pt')[1]
        with self.assertRaisesRegex(ReferenceError, 'reference mode'):
            pins[0]['Net'] = None
        self.assertIs(member.parent, nets[0].one('Parts'))
        self.assertIs(member['Pin'], pins[0])
        self.assertEqual(copy.values, (0,))
        doc.validate()

    def test_external_member_reference_prevents_partial_disconnection(self):
        doc, pins, nets = design()
        member = nets[0].select('Parts/pt')[1]
        copy = doc.root.add('MemberIndex', 1)
        doc.references.bind(copy, member, Index(copy))
        before = tuple(doc.references)
        with self.assertRaisesRegex(ReferenceError, 'referenced content'):
            pins[0]['Net'] = None
        self.assertEqual(tuple(doc.references), before)
        self.assertIs(member['Pin'], pins[0])
        doc.validate()

    def test_reordering_projects_current_indices_without_rebuild(self):
        _, pins, nets = design()
        member = nets[0].select('Parts/pt')[1]
        pins[0].move_to(pins[0].parent, 2)
        self.assertEqual(member.values, (0, 2))
        nets[0].move_to(nets[0].parent, 1)
        self.assertEqual(pins[0]['NetNumber'], 1)

    def test_copy_of_calculated_net_number_follows_member_move_and_future_reorders(self):
        doc, pins, nets = design()
        copied = doc.root.add('CopiedNumber', 0)
        doc.references.bind(copied, pins[0], Property(copied, 'NetNumber'))
        pins[0]['Net'] = nets[1]
        self.assertEqual(copied.values, (1,))
        nets[1].move_to(nets[1].parent, 0)
        self.assertEqual(copied.values, (0,))
        doc.validate()

    def test_moving_member_collection_cannot_bypass_attached_wire_checks(self):
        doc, pins, nets = design()
        line = nets[0].one('Lines').append(new_wire())
        for name, value in dict(Number=0, NetNumber=0, ConnectMode1=0, Connect1=0, ConnectL1=0).items():
            line.set_field(name, value)
        bind_schematic_references(doc)
        parts = nets[0].one('Parts')
        with self.assertRaisesRegex(ReferenceError, 'net membership disagrees'):
            parts.move_to(nets[1])
        self.assertIs(parts.parent, nets[0])
        self.assertIs(pins[0]['Net'], nets[0])
        doc.validate()

    def test_clone_keeps_relationships_independent(self):
        doc, pins, nets = design()
        copied = doc.clone()
        pin = copied.one('/Schematic/Components/Part/Pins/Pin[1]')
        target = copied.one('/Schematic/Nets/Net[2]')
        pin['Net'] = target
        self.assertIs(pin['Net'], target)
        self.assertIs(pins[0]['Net'], nets[0])
        self.assertIs(copied.one('/Schematic/Nets/Net[2]/Parts/pt')['Pin'], pin)

    def test_clone_assembles_wire_and_membership_graph_before_authoring_checks(self):
        doc, pins, nets = design()
        line = nets[0].one('Lines').append(new_wire())
        for name, value in dict(Number=0, NetNumber=0, ConnectMode1=0, Connect1=0, ConnectL1=0).items():
            line.set_field(name, value)
        bind_schematic_references(doc)
        # Consolidated membership links may follow their wire users in graph order.
        copied = doc.clone()
        copied.validate()
        pin = copied.one('/Schematic/Components/Part/Pins/Pin[1]')
        other = copied.one('/Schematic/Nets/Net[2]')
        with self.assertRaisesRegex(ReferenceError, 'attached wire'):
            pin['Net'] = other
        self.assertIs(pin['Net'], copied.one('/Schematic/Nets/Net[1]'))

    def test_a_member_cannot_acquire_a_second_pin_identity(self):
        doc, pins, nets = design()
        member = nets[0].select('Parts/pt')[0]
        count = len(doc.references)
        with self.assertRaisesRegex(ReferenceError, 'already has a pin identity'):
            doc.references.bind(member, pins[2], role='net-member')
        self.assertEqual(len(doc.references), count)
        self.assertIs(member['Pin'], pins[1])

    def test_structural_member_clone_without_its_link_is_rejected_by_audit(self):
        doc, _, nets = design()
        member = nets[0].select('Parts/pt')[0].clone()
        with self.assertRaisesRegex(ReferenceError, 'needs its pin identity'):
            nets[1].one('Parts').append(member)
        self.assertIsNone(member.parent)
        doc.validate()

    def test_retargeting_member_updates_assignment_and_rejects_duplicate_atomically(self):
        doc, pins, nets = design()
        member = nets[0].select('Parts/pt')[1]
        reference = doc.references.outgoing(member, role='net-member')[0]
        with self.assertRaisesRegex(ReferenceError, 'already has a net'):
            doc.references.retarget(reference, pins[1])
        self.assertIs(member['Pin'], pins[0])
        doc.references.retarget(reference, pins[2])
        self.assertIsNone(pins[0]['Net'])
        self.assertIs(pins[2]['Net'], nets[0])
        self.assertEqual(member.values, (0, 2))

    def test_member_retarget_refreshes_old_new_pin_and_index_property_users(self):
        doc, pins, nets = design()
        member = nets[0].select('Parts/pt')[1]
        old = self.copied_number(doc, pins[0], 'Old')
        new = self.copied_number(doc, pins[2], 'New')
        number = doc.root.add('MemberPin', 0)
        doc.references.bind(number, member, Property(number, target_argument=1))
        doc.references.retarget(doc.references.outgoing(member, role='net-member')[0], pins[2])
        self.assertEqual((old.values, new.values, number.values), ((-1,), (0,), (2,)))
        pins[2].move_to(pins[2].parent, 0)
        self.assertEqual(number.values, (0,))
        copied = doc.clone()
        copied.one('/Schematic/Nets/Net[1]').move_to(copied.one('/Schematic/Nets'), 1)
        self.assertEqual(copied.one('/New').values, (1,))
        self.assertEqual(new.values, (0,))
        copied.validate()
        doc.validate()

    def test_member_retarget_downstream_guard_is_atomic(self):
        doc, pins, nets = design()
        member = nets[0].select('Parts/pt')[1]
        copy = self.guarded_number(doc, pins[2], nets[0])
        reference = doc.references.outgoing(member, role='net-member')[0]
        with self.assertRaisesRegex(ReferenceError, 'reference mode'):
            doc.references.retarget(reference, pins[2])
        self.assertIs(doc.references.get(reference.uid).target, pins[0])
        self.assertIs(pins[0]['Net'], nets[0])
        self.assertIsNone(pins[2]['Net'])
        self.assertEqual(copy.values, (-1,))
        doc.validate()

    def test_explicit_member_link_discard_updates_calculated_consumers(self):
        doc, pins, nets = design()
        copy = self.copied_number(doc, pins[0])
        member = nets[0].select('Parts/pt')[1]
        doc.references.discard(doc.references.outgoing(member, role='net-member')[0])
        self.assertEqual(copy.values, (-1,))
        member.detach()
        doc.validate()

    def test_calculated_guards_protect_relationship_and_ordinal_changes(self):
        for unresolved in (False, True):
            with self.subTest(unresolved=unresolved):
                doc, pins, nets = design()
                pin = pins[0]
                field = pin.add('GuardTarget', 0)
                guards = (Guard(pin.one('NetNumber'), (0,)),)
                if unresolved:
                    doc.references.note(pin, 'missing target', Index(field), guards=guards,
                                        collections=(doc.one('/Schematic/Pages'),))
                else:
                    doc.references.bind(pin, nets[0], Index(field), guards=guards)
                for operation in (lambda: pin.set('Net', None),
                                  lambda: nets[0].move_to(nets[0].parent, 1)):
                    with self.assertRaisesRegex(ReferenceError, 'reference mode'):
                        operation()
                    self.assertEqual(pin['NetNumber'], 0)
                doc.validate()

    def test_attached_wires_block_membership_changes_before_mutation(self):
        doc, pins, nets = design()
        line = nets[0].one('Lines').append(new_wire())
        for name, value in dict(Number=0, NetNumber=0, ConnectMode1=0, Connect1=0, ConnectL1=0).items():
            line.set_field(name, value)
        bind_schematic_references(doc)
        member = nets[0].select('Parts/pt')[1]
        for operation in (lambda: pins[0].set('Net', nets[1]),
                          lambda: member.move_to(nets[1].one('Parts')),
                          lambda: doc.references.retarget(doc.references.outgoing(member)[0], pins[2])):
            with self.assertRaisesRegex(ReferenceError, 'attached wire'):
                operation()
            self.assertIs(pins[0]['Net'], nets[0])
            self.assertIs(member['Pin'], pins[0])

    def test_invalid_target_and_numeric_edit_do_not_change_membership(self):
        doc, pins, nets = design()
        for operation in (lambda: pins[0].set('Net', Element('Net')),
                          lambda: pins[0].set('Net', pins[2]),
                          lambda: pins[0].set('NetNumber', 1)):
            with self.assertRaises((ReferenceError, TypeError)):
                operation()
        self.assertIs(pins[0]['Net'], nets[0])

    def test_rebinding_is_idempotent_and_does_not_restore_duplicate_facts(self):
        doc, pins, nets = design()
        count = len(doc.references)
        for _ in range(2):
            bind_schematic_references(doc)
        self.assertEqual(len(doc.references), count)
        self.assertEqual(pins[0].one('NetNumber').items, ())
        self.assertEqual(nets[0].one('Parts/pt[1]').items, ())

    def test_unresolved_assignment_is_retained_and_cannot_be_overwritten(self):
        doc, pins, nets = design()
        field = pins[2].one('NetNumber')
        with assembly(doc):
            field.detach()
            pins[2].add('NetNumber', 99)
            bind_schematic_references(doc)
        with self.assertRaisesRegex(ReferenceError, 'unresolved net identity'):
            pins[2]['Net'] = nets[0]
        self.assertEqual(pins[2]['NetNumber'], 99)
        self.assertEqual(len(doc.references.issues), 1)

    def test_contradictory_resolved_occurrences_remain_available_for_investigation(self):
        doc, pins, nets = design()
        with assembly(doc):
            pins[2].one('NetNumber').detach()
            pins[2].add('NetNumber', 0)
            nets[1].one('Parts').add('pt', 0, 2)
            bind_schematic_references(doc)
        self.assertEqual(pins[2]['NetNumber'], 0)
        self.assertEqual(nets[1].one('Parts/pt').values, (0, 2))
        with self.assertRaisesRegex(ReferenceError, 'contradictory'):
            pins[2]['Net'] = nets[0]
        self.assertTrue(connectivity_mismatches(doc))

    def test_all_format_pairs_keep_membership_order_and_edits(self):
        source, _, _ = design()
        for incoming in ('dch', 'asc', 'dchxml'):
            doc = parse(getattr(source, 'to_'+incoming+'_bytes')(report=ConversionReport()),
                        format=incoming, report=ConversionReport())
            pins = doc.select('/Schematic/Components/Part/Pins/Pin')
            nets = doc.select('/Schematic/Nets/Net')
            self.assertEqual([row['Pin'] for row in nets[0].select('Parts/pt')], [pins[1], pins[0]])
            pins[0]['Net'] = nets[1]
            for outgoing in ('dch', 'asc', 'dchxml'):
                with self.subTest(incoming=incoming, outgoing=outgoing):
                    result = parse(getattr(doc, 'to_'+outgoing+'_bytes')(report=ConversionReport()),
                                   format=outgoing, report=ConversionReport())
                    current = result.select('/Schematic/Components/Part/Pins/Pin')
                    target = result.select('/Schematic/Nets/Net')
                    self.assertIs(current[0]['Net'], target[1])
                    self.assertEqual([row['Pin'] for row in target[0].select('Parts/pt')], [current[1]])
