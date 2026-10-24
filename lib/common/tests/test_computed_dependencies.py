"""Calculated getters declare their graph/order inputs without storing copies."""
import unittest
from unittest.mock import patch

from lib import Document, Element, Guard, Index, Key, Property, ReferenceError
from lib.common.schema import Field, Record


def selection(node):
    links = node._owner().references.outgoing(node, role='selection')
    return links[0].target if links else None


def selection_index(node):
    selected = selection(node)
    return selected._ordinal() if selected is not None else -1


SELECTION = Record('Selection', {
    'Index': Field('Index', 'integer', getter=selection_index,
                   ordinal_dependencies=lambda node: (target,) if (target := selection(node)) is not None else (),
                   reference_dependencies=lambda node: ((node, 'selection', 'outgoing'),))}, ('Index',))


class ComputedDependencyTests(unittest.TestCase):
    def design(self):
        doc = Document()
        rows = doc.root.add('Rows')
        first, second = rows.add('Row'), rows.add('Row')
        state = doc.root.add('State').bind_schema(SELECTION)
        copy = doc.root.add('Copy', -1)
        doc.references.bind(copy, state, Property(copy))
        return doc, rows, first, second, state, copy

    def test_binding_retarget_discard_and_rebinding_refresh_registered_getters(self):
        doc, rows, first, second, state, copy = self.design()
        with patch.object(type(doc.references), '__iter__', side_effect=AssertionError('whole graph scan')):
            link = doc.references.bind(state, first, role='selection', preserve=True)
            self.assertEqual(copy.values, (0,))
            link = doc.references.retarget(link, second)
            self.assertEqual(copy.values, (1,))
            doc.references.discard(link)
            self.assertEqual(copy.values, (-1,))
            doc.references.bind(state, first, role='selection')
            self.assertEqual(copy.values, (0,))
        first.move_to(rows, 1)
        self.assertEqual(copy.values, (1,))
        doc.validate()

    def test_failed_retarget_and_discard_restore_all_visible_queries(self):
        doc, _, first, second, state, copy = self.design()
        link = doc.references.bind(state, first, role='selection')
        slot = copy.add('Target', 0)
        doc.references.bind(copy, first, Index(slot), guards=(Guard(copy, (0,)),))
        before = tuple(doc.references)
        for operation in (lambda: doc.references.retarget(link, second),
                          lambda: doc.references.discard(link)):
            with self.assertRaisesRegex(ReferenceError, 'reference mode'):
                operation()
            self.assertEqual(tuple(doc.references), before)
            self.assertIs(doc.references.get(link.uid), link)
            self.assertEqual(doc.references.outgoing(state), [link])
            self.assertEqual(doc.references.incoming(second), [])
            self.assertEqual(copy.values, (0,))
        doc.validate()

    def test_clone_indexes_calculated_inputs_against_the_complete_copied_graph(self):
        doc, _, first, second, state, copy = self.design()
        # The property user precedes its semantic producer in graph order.
        doc.references.bind(state, first, role='selection')
        copied = doc.clone()
        copied.one('/Rows/Row[1]').move_to(copied.one('/Rows'), 1)
        self.assertEqual(copied.one('/Copy').values, (1,))
        self.assertEqual(copy.values, (0,))
        copied.validate()

    def test_any_role_incoming_dependency_is_updated_on_both_old_and_new_targets(self):
        doc = Document()
        schema = Record('Counter', {'Count': Field('Count', 'integer',
            getter=lambda node: len(node._owner().references.incoming(node)),
            reference_dependencies=lambda node: ((node, '', 'incoming'),))}, ('Count',))
        rows = doc.root.add('Rows')
        first, second = [rows.add('Counter').bind_schema(schema) for _ in range(2)]
        a, b = doc.root.add('FirstCount', 0), doc.root.add('SecondCount', 0)
        doc.references.bind(a, first, Property(a))
        doc.references.bind(b, second, Property(b))
        # The counting properties themselves are incoming references too.
        self.assertEqual((a.values, b.values), ((1,), (1,)))
        source = doc.root.add('Source')
        link = doc.references.bind(source, first, role='chosen')
        self.assertEqual((a.values, b.values), ((2,), (1,)))
        doc.references.retarget(link, second)
        self.assertEqual((a.values, b.values), ((1,), (2,)))
        doc.validate()

    def test_calculated_guard_on_a_different_scope_rejects_order_changes(self):
        doc, rows, first, second, state, _ = self.design()
        doc.references.bind(state, first, role='selection')
        source = state.add('Unknown', 99)
        other = doc.root.add('Other')
        doc.references.note(state, 'missing target', Index(source), collections=(other,),
                            guards=(Guard(state, (0,)),))
        with self.assertRaisesRegex(ReferenceError, 'reference mode'):
            first.move_to(rows, 1)
        self.assertEqual(rows.children(), [first, second])
        copied = doc.clone()
        with self.assertRaisesRegex(ReferenceError, 'reference mode'):
            copied.one('/Rows/Row[1]').move_to(copied.one('/Rows'), 1)
        doc.validate()

    def test_calculated_header_can_be_selected_by_name_for_property_and_key(self):
        doc = Document()
        rows = doc.root.add('Rows')
        schema = Record('Row', {'Index': Field('Index', 'integer', getter=lambda node: node._ordinal(),
                                               ordinal_dependencies=lambda node: (node,))}, ('Index',))
        first, second = [rows.add('Row').bind_schema(schema) for _ in range(2)]
        property_copy, key_copy = doc.root.add('Property', 0), doc.root.add('Key', 0)
        doc.references.bind(property_copy, first, Property(property_copy, 'Index'))
        doc.references.bind(key_copy, first, Key(key_copy, 'Index'))
        self.assertIsNone(first.child('Index'))
        first.move_to(rows, 1)
        self.assertEqual((property_copy.values, key_copy.values), ((1,), (1,)))
        self.assertEqual(doc.select('/Rows/Row[Index=1]'), [first])
        doc.clone().validate()
        doc.validate()

    def test_named_nonheader_calculation_tracks_collection_edits_and_guards_atomically(self):
        doc = Document()
        schema = Record('Summary', {'Count': Field('Count', 'integer',
            getter=lambda node: len(node.one('Rows').children('Row')),
            collection_dependencies=lambda node: ((node.one('Rows'), 'Row'),))})
        summary = doc.root.add('Summary').bind_schema(schema)
        rows = summary.add('Rows')
        first, second = rows.add('Row'), rows.add('Row')
        copy = doc.root.add('Copy', 2)
        doc.references.bind(copy, summary, Property(copy, 'Count'))
        target = copy.add('Target', 0)
        guard = doc.references.bind(copy, first, Index(target), guards=(Guard(copy, (2,)),))
        added = Element('Row')
        with self.assertRaisesRegex(ReferenceError, 'reference mode'):
            rows.append(added)
        self.assertIsNone(added.parent)
        self.assertEqual(rows.children(), [first, second])
        self.assertEqual(copy.values, (2,))
        doc.references.discard(guard)
        rows.append(added)
        self.assertEqual(copy.values, (3,))
        second.detach()
        self.assertEqual(copy.values, (2,))
        self.assertIsNone(summary.child('Count'))
        doc.validate()
