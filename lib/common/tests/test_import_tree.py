"""Adapter construction preserves facts without authoring-time graph edits."""
import unittest

from lib import Document, Element, Index
from lib.common.import_tree import move_children, assign_fields
from lib.common.model import Value, SourceSpan
from lib.common.schema import Record, Field
from lib.common.element_storage import RecordItems


class ImportTreeTests(unittest.TestCase):
    def test_scalar_assignment_replaces_empty_or_wide_raw_tuple_fields(self):
        for width in (0, 1, 2):
            with self.subTest(width=width):
                parent = Element('Row')
                parent._content = RecordItems(parent, Record('Row', {'Data': Field('Data', 'tuple')}))
                parent._content.import_field('Data', tuple(Value.of(3) for _ in range(width)))
                assign_fields(parent, (('Data', 3),))
                self.assertEqual(parent.one('Data').values, (3,))

    def test_scalar_assignment_preserves_handles_notes_and_equivalent_spelling(self):
        for compact in (False, True):
            with self.subTest(compact=compact):
                parent = Element('Row')
                if compact:
                    parent._content = RecordItems(parent, Record('Row', {'Width': Field('Width', 'number'),
                        'Label': Field('Label', 'text')}), retain_debug=True)
                original = Value(3, 'number', lexeme='003', source=SourceSpan('asc', 1, 4))
                width = parent.add('Width', original)
                width.annotations['note'] = 'keep'
                uid = width.uid
                assign_fields(parent, (('Width', 3), ('Label', 'value')))
                self.assertIs(parent.one('Width'), width)
                self.assertEqual(width.arguments, (original,))
                self.assertEqual(width.uid, uid)
                self.assertEqual(width.annotations, {'note': 'keep'})
                assign_fields(parent, (('Width', 4),))
                self.assertEqual(width.values, (4,))
                self.assertEqual(parent['Label'], 'value')
                assign_fields(parent, (('Width', 5),), overwrite=False)
                self.assertEqual(width.values, (4,))

    def test_assignment_rejects_live_bindings_and_preflights_the_values(self):
        parent = Element('Row')
        with self.assertRaises(ValueError):
            assign_fields(parent, (('First', 1), ('Bad', float('inf'))))
        self.assertEqual(parent.children(), [])
        named = Element('Row').bind_schema(Record('Named', {}))
        with self.assertRaises(TypeError):
            assign_fields(named, (('First', 1),))
        document = Document()
        parent = document.root.add('Row')
        document.references.watch(parent)
        with self.assertRaisesRegex(ValueError, 'relationship binding'):
            assign_fields(parent, (('First', 1),))
        self.assertEqual(parent.children(), [])

    def test_transfer_preserves_arguments_order_identity_and_invalidates_lookups(self):
        original, destination = Document(), Document()
        source = original.root.add('Source', 'header')
        first, retained, last = (source.add('Row', value) for value in ('first', 'retained', 'last'))
        target = destination.root.add('Target', 10)
        existing = target.add('Existing')
        identity = last.uid
        self.assertIs(original.get(identity), last)
        source.children()
        target.children()
        move_children(source, target, (first, last))
        self.assertEqual(source.values, ('header',))
        self.assertEqual(target.values, (10,))
        self.assertEqual(source.children(), [retained])
        self.assertEqual(target.children(), [existing, first, last])
        self.assertIs(destination.get(identity), last)
        with self.assertRaises(LookupError):
            original.get(identity)
        original.validate()
        destination.validate()

    def test_bound_relationship_rejection_is_atomic(self):
        document = Document()
        source = document.root.add('Source')
        node = source.add('Row')
        link = document.root.add('Link', 0)
        document.references.bind(link, node, Index(link))
        target = Element('Target')
        with self.assertRaisesRegex(ValueError, 'relationship binding'):
            move_children(source, target)
        self.assertEqual(source.children(), [node])
        self.assertEqual(target.children(), [])
        document.validate()

    def test_invalid_selection_and_cycles_do_not_change_ownership(self):
        source, target = Element('Source'), Element('Target')
        row = source.add('Row')
        nested = row.add('Nested')
        for destination, selected in ((target, (row, row)), (target, (Element('Other'),)), (nested, (row,))):
            with self.subTest(destination=destination.kind), self.assertRaises(ValueError):
                move_children(source, destination, selected)
            self.assertEqual(source.children(), [row])
            self.assertIs(nested.parent, row)

    def test_named_parent_requires_the_normal_editing_api(self):
        source = Element('Source').bind_schema(Record('Source', {}))
        with self.assertRaisesRegex(TypeError, 'unbound parser'):
            move_children(source, Element('Target'))
