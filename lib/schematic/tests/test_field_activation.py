"""Named edits activate new references and keep existing identity constraints."""
import unittest
from unittest.mock import patch

from lib import Element, Guard, Index, Property, ReferenceError
from lib.common.schema import Field, Record
from lib.schematic.model.objects import new_pin, new_symbol, new_schematic_shape
from lib.schematic.tests import test_activation


class FieldActivationTests(unittest.TestCase):
    def design(self):
        return test_activation.ActivationTests().design()

    def drawing(self, doc, *, kind=10, related=-1):
        shape = new_schematic_shape()
        shape['Type'], shape['RelatedNet'] = kind, related
        return doc.one('/Schematic/Shapes').append(shape)

    def test_first_reference_assignment_activates_without_full_rebinding(self):
        doc, _, a, _ = self.design()
        shape = self.drawing(doc)
        with patch.object(doc.root, 'walk', side_effect=AssertionError('document scan')), \
             patch.object(type(doc.references), '__iter__', side_effect=AssertionError('graph scan')), \
             patch('lib.schematic.model.refs.bind_schematic_references', side_effect=AssertionError('full binding')):
            shape['RelatedNet'] = 0
        reference = doc.references.outgoing(shape, role='drawing-net-name')[0]
        self.assertIs(reference.target, a)
        a.move_to(a.parent, 1)
        self.assertEqual(shape['RelatedNet'], 1)
        doc.validate()

    def test_mode_change_activates_retained_data_and_existing_guard_protects_it(self):
        doc, _, a, _ = self.design()
        shape = self.drawing(doc, kind=1, related=0)
        self.assertEqual(doc.references.outgoing(shape, role='drawing-net-name'), [])
        shape['Type'] = 10
        reference = doc.references.outgoing(shape, role='drawing-net-name')[0]
        self.assertIs(reference.target, a)
        with self.assertRaisesRegex(ReferenceError, 'reference mode'):
            shape['Type'] = 1
        self.assertEqual(shape['Type'], 10)
        self.assertIs(doc.references.get(reference.uid).target, a)
        doc.validate()

    def test_downstream_guard_failure_rejects_scalar_and_new_binding_together(self):
        doc, _, a, _ = self.design()
        shape = self.drawing(doc)
        copied = doc.root.add('CopiedNet', -1)
        doc.references.bind(copied, shape, Property(copied, 'RelatedNet'))
        field = copied.add('Target', 0)
        doc.references.bind(copied, a, Index(field), guards=(Guard(copied, (-1,)),))
        before = tuple(doc.references)
        with self.assertRaisesRegex(ReferenceError, 'reference mode'):
            shape['RelatedNet'] = 0
        self.assertEqual((shape['RelatedNet'], copied.values), (-1, (-1,)))
        self.assertEqual(tuple(doc.references), before)
        doc.validate()

    def test_unknown_identity_is_explicit_and_requires_resolution_before_reinterpretation(self):
        doc, _, a, _ = self.design()
        shape = self.drawing(doc)
        shape['RelatedNet'] = 99
        issue = next(issue for issue in doc.references.issues if issue.source is shape)
        self.assertEqual(issue.collections, (doc.one('/Schematic/Nets'),))
        with self.assertRaisesRegex(ValueError, 'reference-managed'):
            shape['RelatedNet'] = 0
        self.assertEqual(shape['RelatedNet'], 99)
        doc.references.discard_issue(issue)
        shape['RelatedNet'] = 0
        self.assertIs(doc.references.outgoing(shape, role='drawing-net-name')[0].target, a)
        doc.validate()

    def test_new_field_is_the_same_object_registered_by_the_plan(self):
        doc, _, a, _ = self.design()
        shape = new_schematic_shape()
        shape['Type'] = 10
        shape.one('RelatedNet').detach()  # Construct an incomplete detached proposal.
        doc.one('/Schematic/Shapes').append(shape)
        shape['RelatedNet'] = 0
        field = shape.one('RelatedNet')
        self.assertTrue(doc.references.manages(field))
        self.assertIs(doc.references.outgoing(shape, role='drawing-net-name')[0].target, a)
        doc.validate()

    def test_hierarchy_controller_includes_affected_nested_pins(self):
        doc, _, _, _ = self.design()
        connector = new_symbol('Port', 'PORT')
        connector['PartType'] = 3
        doc.one('/Schematic/Components').append(connector)
        block = new_symbol('Block', 'HB1')
        pin = block.one('Pins').append(new_pin())
        pin['Number'], pin['StringNumber'] = 1, 'PORT'
        doc.one('/Schematic/Components').append(block)
        block['PartType'] = 4
        self.assertIs(doc.references.outgoing(block, role='hierarchy-page')[0].target, doc.one('/Schematic/Pages/Page'))
        link = doc.references.outgoing(block, role='component-pin-reference')[0]
        self.assertIs(link.target, connector)
        connector['RefDes'] = 'RENAMED'
        self.assertEqual(pin['StringNumber'], 'RENAMED')
        doc.validate()

    def test_target_type_constraint_also_checks_changes_propagated_from_other_fields(self):
        doc, _, _, _ = self.design()
        connector = new_symbol('Port', 'PORT')
        connector['PartType'] = 3
        doc.one('/Schematic/Components').append(connector)
        block = new_symbol('Block', 'HB1')
        block['PartType'] = 4
        pin = block.one('Pins').append(new_pin())
        pin['Number'], pin['StringNumber'] = 1, 'PORT'
        doc.one('/Schematic/Components').append(block)
        schema = Record('Control', {'Type': Field('Type', 'integer')})
        control = doc.root.append(Element('Control').bind_schema(schema))
        control['Type'] = 3
        doc.references.bind(connector, control, Property(connector.one('PartType'), 'Type'), role='type-copy')
        with self.assertRaisesRegex(ReferenceError, 'membership disagrees'):
            control['Type'] = 0
        self.assertEqual((control['Type'], connector['PartType']), (3, 3))
        doc.validate()

    def test_a_scalar_copy_cannot_silently_become_a_different_identity_relationship(self):
        doc, _, _, _ = self.design()
        shape = self.drawing(doc, kind=1, related=0)
        source = doc.root.add('Borrowed', 0)
        link = doc.references.bind(shape, source, Property(shape.one('RelatedNet')), role='borrowed-index')
        with self.assertRaisesRegex(ReferenceError, 'different relationship'):
            shape['Type'] = 10
        self.assertEqual(shape['Type'], 1)
        self.assertIs(doc.references.get(link.uid).target, source)
        doc.validate()
