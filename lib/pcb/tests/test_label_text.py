"""PCB bound text follows current data and user-field identities atomically."""
from decimal import Decimal
import unittest
from unittest.mock import patch

from lib.common.footprint_objects import new_pattern_drawing
from lib.common.references import Index, Property, ReferenceError
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.model.label_text import USER_ROLE
from lib.pcb.model.objects import new_user_field, new_component, new_document
from lib.pcb.tests.test_graphics import design


def fixture(*modes):
    decoded, _, _ = design()
    component = decoded.board.one('Components/Component')
    component.one('Name').set_values('Device')
    component.one('RefDes').set_values('U1')
    for name, value in (('Value', '10k'), ('Manufacturer', 'Maker'), ('Datasheet', 'Guide')):
        field = component.child(name)
        if field is None:
            component.add(name, value)
        else:
            field.set_values(value)
    component.one('Pattern').set_argument(0, 'Package')
    component.one('Pattern')['Name_Unique'] = 'Unique package'
    users = component.add('UserFields')
    first = users.append(new_user_field('Order', 'A123'))
    second = users.append(new_user_field('Link', 'https://example.test', kind=1))
    shapes = component.one('Pattern/Shapes')
    boundary = shapes.children()[-1].detach()
    labels = []
    for mode in modes:
        shape = new_pattern_drawing(kind=7)
        shape['TextShow'] = mode
        shape['TextAngle'] = Decimal('7.25')
        shape.one('TextLine').add('pt', 'Saved text')
        shape.one('Points_New').add('pt', 12, 34)
        shapes.append(shape)
        labels.append(shape)
    shapes.append(boundary)
    result = assemble_graphics(decoded)
    return result.document, component, labels, first, second


class LabelTextTests(unittest.TestCase):
    def test_component_fields_refresh_text_without_changing_drawing_appearance(self):
        document, component, labels, _, _ = fixture(1, 2, 3, 4, 5, 6, 7, 0)
        self.assertEqual([shape.one('TextLine/pt')['Text'] for shape in labels],
                         ['Device', 'U1', '10k', 'Package', 'Unique package', 'Guide', 'Maker', 'Saved text'])
        shape = labels[1]
        anchor = shape.one('Points_New/pt').values
        row = shape.one('TextLine/pt')
        with patch.object(document.root, 'walk', side_effect=AssertionError('whole document scan')), \
             patch.object(type(document.references), '__iter__', side_effect=AssertionError('whole graph scan')):
            component['RefDes'] = 'U12'
            component.one('Pattern')['Name'] = 'Other package'
            component.one('Pattern')['Name_Unique'] = 'Other unique name'
        self.assertIs(shape.one('TextLine/pt'), row)
        self.assertEqual(row['Text'], 'U12')
        self.assertEqual(labels[3].one('TextLine/pt')['Text'], 'Other package')
        self.assertEqual(labels[4].one('TextLine/pt')['Text'], 'Other unique name')
        self.assertEqual(shape['TextAngle'], Decimal('7.25'))
        self.assertEqual(shape.one('Points_New/pt').values, anchor)
        self.assertEqual(labels[-1].one('TextLine/pt')['Text'], 'Saved text')

    def test_user_identity_survives_reordering_value_edits_and_cloning(self):
        document, component, labels, first, second = fixture(20, 21)
        shape, other = labels
        reference, = document.references.outgoing(shape, role=USER_ROLE)
        self.assertIs(reference.target, first)
        first.move_to(first.parent, 1)
        self.assertEqual((shape['TextShow'], other['TextShow']), (21, 20))
        self.assertEqual(shape.one('TextLine/pt')['Text'], 'A123')
        first['Value'] = 'A456'
        self.assertEqual(shape.one('TextLine/pt')['Text'], 'A456')
        self.assertEqual(other.one('TextLine/pt')['Text'], second['Value'])
        clone = document.clone()
        copied = clone.one('/Board/Components/Component[1]')
        copied.one('UserFields/UserField[2]')['Value'] = 'Copied'
        self.assertEqual(copied.one('Pattern/Shapes/Shape[2]/TextLine/pt')['Text'], 'Copied')
        self.assertEqual(shape.one('TextLine/pt')['Text'], 'A456')
        self.assertIsNot(copied, component)

    def test_user_reference_retargeting_updates_text_and_rejects_foreign_fields(self):
        document, component, labels, first, second = fixture(20)
        shape, = labels
        link, = document.references.outgoing(shape, role=USER_ROLE)
        document.references.retarget(link, second)
        self.assertEqual(shape['TextShow'], 21)
        self.assertEqual(shape.one('TextLine/pt')['Text'], second['Value'])
        foreign = document.one('/Board/Components').append(new_component('Other', 'U2'))
        field = foreign.one('UserFields').append(new_user_field('Order', 'Foreign'))
        with self.assertRaisesRegex(ReferenceError, 'own component'):
            document.references.retarget(document.references.outgoing(shape, role=USER_ROLE)[0], field)
        self.assertEqual(shape['TextShow'], 21)
        self.assertEqual(shape.one('TextLine/pt')['Text'], second['Value'])

    def test_user_fields_cannot_leave_their_bound_component_or_be_removed(self):
        document, _, labels, first, _ = fixture(20)
        other = document.one('/Board/Components').append(new_component('Other', 'U2'))
        parent = first.parent
        with self.assertRaisesRegex(ReferenceError, 'own component'):
            first.move_to(other.one('UserFields'))
        self.assertIs(first.parent, parent)
        with self.assertRaises(ReferenceError):
            document.remove(first)
        self.assertIs(first.parent, parent)
        self.assertEqual(labels[0].one('TextLine/pt')['Text'], 'A123')

    def test_named_mode_changes_activate_identity_links_and_keep_bound_text_readonly(self):
        document, _, labels, first, second = fixture(0)
        shape, = labels
        shape['TextShow'] = Decimal(20)
        self.assertEqual(shape.one('TextLine/pt')['Text'], first['Value'])
        self.assertIs(document.references.outgoing(shape, role=USER_ROLE)[0].target, first)
        second.move_to(second.parent, 0)
        self.assertEqual(shape['TextShow'], 21)
        with self.assertRaisesRegex(TypeError, 'calculated'):
            shape.one('TextLine/pt')['Text'] = 'Independent'
        with self.assertRaises(ReferenceError):
            shape['Type'] = 1
        self.assertEqual(shape['Type'], 7)
        link, = document.references.outgoing(shape, role=USER_ROLE)
        document.references.discard(link)
        shape['TextShow'] = 0
        shape.one('TextLine/pt')['Text'] = 'Literal'
        first['Value'] = 'Changed'
        self.assertEqual(shape.one('TextLine/pt')['Text'], 'Literal')

    def test_text_property_consumers_follow_calculations_and_cycles_are_rejected(self):
        document, component, labels, _, _ = fixture(1)
        shape, = labels
        row = shape.one('TextLine/pt')
        probe = document.root.add('Probe', '')
        document.references.bind(probe, row, Property(probe, 'Text'), role='probe')
        component['Name'] = 'Updated'
        self.assertEqual(probe.values, ('Updated',))
        with self.assertRaisesRegex(ReferenceError, 'cycle'):
            document.references.bind(component, row, Property(component.one('Name'), 'Text'))
        self.assertEqual(component['Name'], 'Updated')

    def test_unresolved_user_selection_retains_text_and_guards_its_scope(self):
        document, _, labels, _, _ = fixture(25)
        shape, = labels
        self.assertEqual(shape.one('TextLine/pt')['Text'], 'Saved text')
        issue, = document.references.issues
        self.assertIs(issue.source, shape)
        with self.assertRaises(ReferenceError):
            shape['Type'] = 1
        with self.assertRaises(ReferenceError):
            shape.parent.parent.parent.one('UserFields').append(new_user_field('Later', 'Value'))
        self.assertEqual(shape['TextShow'], 25)

    def test_repair_failure_preserves_source_and_all_text_rows(self):
        document, component, labels, _, _ = fixture(3)
        shape, = labels
        extra = shape.one('TextLine').add('pt', 'Extra')
        dependent = document.root.add('Dependency', 1)
        document.references.bind(dependent, extra, Index(dependent))
        with self.assertRaisesRegex(ReferenceError, 'referenced text row'):
            component['Value'] = 'Changed'
        self.assertEqual(component['Value'], '10k')
        self.assertEqual([row.values for row in shape.one('TextLine').children()], [('10k',), ('Extra',)])

    def test_new_components_and_drawings_activate_local_bound_text(self):
        from lib.pcb.model.objects import new_pattern_drawing as new_pcb_drawing

        document = new_document()
        component = new_component('Device', 'U1')
        user = component.one('UserFields').append(new_user_field('Order', 'A123'))
        shape = new_pcb_drawing(kind=7)
        shape['TextShow'] = 20
        shape.one('TextLine').add('pt', 'Stale')
        component.one('Pattern/Shapes').append(shape)
        document.one('/Board/Components').append(component)
        self.assertEqual(shape.one('TextLine/pt')['Text'], 'A123')
        self.assertIs(document.references.outgoing(shape, role=USER_ROLE)[0].target, user)
        added = new_pcb_drawing(kind=7)
        added['TextShow'] = 2
        component.one('Pattern/Shapes').append(added)
        self.assertEqual(added.one('TextLine/pt')['Text'], 'U1')
        component['RefDes'] = 'U3'
        self.assertEqual(added.one('TextLine/pt')['Text'], 'U3')
        document.validate()

    def test_component_copy_normalizes_text_and_keeps_user_targets_local(self):
        document, component, labels, _, _ = fixture(2, 20)
        copied = document.copy(component, fields={'RefDes': 'U2'})
        self.assertEqual(copied.one('Pattern/Shapes/Shape[2]/TextLine/pt')['Text'], 'U2')
        copied_user = copied.one('UserFields/UserField[1]')
        copied_user['Value'] = 'Other order'
        copied_label = copied.one('Pattern/Shapes/Shape[3]')
        self.assertIs(document.references.outgoing(copied_label, role=USER_ROLE)[0].target, copied_user)
        self.assertEqual(copied_label.one('TextLine/pt')['Text'], 'Other order')
        self.assertEqual(labels[1].one('TextLine/pt')['Text'], 'A123')

    def test_moving_bound_drawing_refreshes_its_new_owner_and_property_consumers(self):
        document, _, labels, _, _ = fixture(2)
        shape, = labels
        row = shape.one('TextLine/pt')
        probe = document.root.add('Probe', '')
        document.references.bind(probe, row, Property(probe, 'Text'))
        other = document.one('/Board/Components').append(new_component('Other', 'U2'))
        shape.move_to(other.one('Pattern/Shapes'))
        self.assertEqual(row['Text'], 'U2')
        self.assertEqual(probe.values, ('U2',))
        other['RefDes'] = 'U3'
        self.assertEqual(probe.values, ('U3',))

    def test_failed_move_does_not_change_owner_or_derived_text(self):
        document, component, labels, _, _ = fixture(2)
        shape, = labels
        extra = shape.one('TextLine').add('pt', 'Referenced row')
        probe = document.root.add('Probe', 1)
        document.references.bind(probe, extra, Index(probe))
        other = document.one('/Board/Components').append(new_component('Other', 'U2'))
        with self.assertRaisesRegex(ReferenceError, 'referenced text row'):
            shape.move_to(other.one('Pattern/Shapes'))
        self.assertIs(shape.parent, component.one('Pattern/Shapes'))
        self.assertEqual(shape.one('TextLine/pt[1]')['Text'], 'U1')

    def test_cross_document_move_calculates_text_only_in_its_destination(self):
        _, _, labels, _, _ = fixture(2)
        shape, = labels
        destination = new_document()
        component = destination.one('/Board/Components').append(new_component('Other', 'U8'))
        shape.move_to(component.one('Pattern/Shapes'))
        self.assertIs(shape._owner(), destination)
        self.assertEqual(shape.one('TextLine/pt')['Text'], 'U8')
        component['RefDes'] = 'U9'
        self.assertEqual(shape.one('TextLine/pt')['Text'], 'U9')


if __name__ == '__main__':
    unittest.main()
