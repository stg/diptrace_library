"""User-field label appearance follows field identities through data edits."""
import unittest

from lib.design import ReferenceError, new_schematic, parse
from lib.design.asc_export import prepare_export
from lib.design.schematic_objects import new_symbol
from lib.design.schematic_refs import bind_schematic_references


PART = '/Schematic/Components/Part'


def source():
    current = new_schematic()
    part = current.one('/Schematic/Components').append(new_symbol('Device', 'U1'))
    part.set_field('Width', 10)
    part.set_field('Height', 6)
    users = part.one('UserFields')
    users.add('UserField', 'First', 'First value', 0, 1, 8, 0, 0, -4, 5, 0)
    users.add('UserField', 'Second', 'Second value', 0, 1, 8, 0, 0, 7, -3, 0)
    bind_schematic_references(current)
    current = parse(current.to_dch_bytes(), format='dch')
    for shape in current.select(PART+'/Shapes/Shape'):
        if shape.scalar('FontType') in (20, 21):
            shape.set_field('FontColor', 101 if shape.scalar('FontType') == 20 else 202)
    return current


def markings(current):
    return {shape.one('TextLine/pt').values[0]: shape
            for shape in current.select(PART+'/Shapes/Shape') if shape.scalar('FontType', 0) >= 20
            and shape.scalar('Enabled')}


class MarkingReferenceTests(unittest.TestCase):
    def test_reordering_fields_keeps_each_generated_label_appearance_and_placement(self):
        for incoming in ('dch', 'asc'):
            current = source()
            if incoming == 'asc':
                current = parse(current.to_asc_bytes(), format='asc')
            part = current.one(PART)
            first, second = part.select('UserFields/UserField')
            first.move_to(first.parent, 1)
            first.set_argument(1, 'Edited first')
            before = [(node.kind, node.values) for node in current.root.walk()]
            for outgoing in ('dch', 'asc'):
                with self.subTest(incoming=incoming, outgoing=outgoing):
                    loaded = parse(getattr(current, 'to_'+outgoing+'_bytes')(), format=outgoing)
                    labels = markings(loaded)
                    self.assertEqual(labels['Edited first'].scalar('FontColor'), 101)
                    self.assertEqual(labels['Edited first'].scalar('FontType'), 21)
                    self.assertEqual(labels['Edited first'].one('Points_New/pt').values, (-4, 5))
                    self.assertEqual(labels['Second value'].scalar('FontColor'), 202)
                    self.assertEqual(labels['Second value'].scalar('FontType'), 20)
                    self.assertEqual(labels['Second value'].one('Points_New/pt').values, (7, -3))
                    self.assertEqual([(node.kind, node.values) for node in current.root.walk()], before)

    def test_retargeting_a_label_uses_the_managed_reference_api(self):
        current = source()
        labels = markings(current)
        old = labels['First value']
        other = labels['Second value']
        field = current.one(PART+'/UserFields/UserField[2]')
        # Remove the other label explicitly; both drawings must not compete for
        # a single label role after retargeting.
        for reference in current.references.outgoing(other):
            current.references.discard(reference)
        other.detach()
        reference = current.references.outgoing(old, role='marking-user-field')[0]
        current.references.retarget(reference, field)
        view = prepare_export(current)
        label = markings(view)['Second value']
        self.assertEqual(label.scalar('FontColor'), 101)
        self.assertEqual(label.scalar('FontType'), 21)

    def test_deleted_and_cross_component_targets_are_rejected(self):
        current = source()
        field = current.one(PART+'/UserFields/UserField[1]')
        other = current.one('/Schematic/Components').append(new_symbol('Other', 'U2'))
        bind_schematic_references(current)
        field.move_to(other.one('UserFields'))
        with self.assertRaisesRegex(ReferenceError, 'local collection|incompatible collection'):
            current.to_dch_bytes()
        current = source()
        current.one(PART+'/UserFields/UserField[1]').detach()
        with self.assertRaises(ReferenceError):
            current.to_dch_bytes()

    def test_unresolved_field_links_guard_only_their_own_field_collection(self):
        current = source()
        shape = markings(current)['First value']
        for reference in current.references.outgoing(shape):
            current.references.discard(reference)
        shape.set_field('FontType', 99)
        bind_schematic_references(current)
        issue = next(issue for issue in current.references.issues
                     if issue.message.startswith('marking-user-field:'))
        self.assertEqual(issue.collections, (current.one(PART+'/UserFields'),))
        current.one(PART).set_field('Value', 'Unrelated edit')
        current.to_dch_bytes()
        current.one(PART+'/UserFields').add('UserField', 'New', 'value', 0, 2, 7, 0, 0, 0, 0, 0)
        with self.assertRaisesRegex(ReferenceError, 'unresolved references'):
            current.to_dch_bytes()

    def test_rebinding_never_assigns_a_new_record_to_an_old_missing_literal(self):
        current = source()
        shape = markings(current)['First value']
        for reference in current.references.outgoing(shape):
            current.references.discard(reference)
        shape.set_field('FontType', 22)
        bind_schematic_references(current)
        original_issue = current.references.issues[0]
        current.one(PART+'/UserFields').add('UserField', 'New third', 'value', 0, 2, 7, 0, 0, 0, 0, 0)
        bind_schematic_references(current)
        self.assertIn(original_issue, current.references.issues)
        self.assertEqual(current.references.outgoing(shape, role='marking-user-field'), [])
        with self.assertRaisesRegex(ReferenceError, 'unresolved references'):
            current.rebuild()


if __name__ == '__main__':
    unittest.main()
