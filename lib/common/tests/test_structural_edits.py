"""Structural changes preflight affected identity links before tree mutation."""
import unittest
import gc
import weakref
from unittest.mock import patch

from lib import Document, Element, Guard, Index, Key, Property, ReferenceError, Segment
from lib.common.schema import Child, Field, Record


class ReorderTests(unittest.TestCase):
    def linked(self):
        doc = Document()
        rows = doc.root.add('Rows')
        first, second, third = [rows.add('Row') for _ in range(3)]
        link = doc.root.add('Link', 0)
        doc.references.bind(link, first, Index(link))
        return doc, rows, first, second, third, link

    def test_index_and_property_chain_update_without_audit_or_rebuild(self):
        doc, rows, first, _, _, link = self.linked()
        copied = doc.root.add('Copy', 0)
        doc.references.bind(copied, link, Property(copied))
        with patch.object(doc, '_validate_structure', side_effect=AssertionError('full scan')):
            first.move_to(rows, 2)
        self.assertEqual((link.values, copied.values), ((2,), (2,)))
        doc.validate()

    def test_ancestor_indices_update_when_the_ancestor_moves(self):
        doc, rows, first, _, _, _ = self.linked()
        pin = first.add('Pins').add('Pin')
        link = doc.root.add('PinLink', 0, 0)
        doc.references.bind(link, pin, Index(link, ancestor=2), Index(link, argument=1))
        first.move_to(rows, 2)
        self.assertEqual(link.values, (2, 0))

    def test_calculated_index_copies_and_clone_use_their_own_dependencies(self):
        doc, rows, first, _, _, _ = self.linked()
        schema = Record('Row', {'Index': Field('Index', 'integer', getter=lambda node: node._ordinal(),
                                               ordinal_dependencies=lambda node: (node,))}, ('Index',))
        first.bind_schema(schema)
        link = doc.root.add('Computed', 0)
        doc.references.bind(link, first, Property(link))
        copied = doc.clone()
        copied.one('/Rows/Row[1]').move_to(copied.one('/Rows'), 2)
        self.assertEqual(copied.one('/Computed').values, (2,))
        self.assertEqual(link.values, (0,))
        first.move_to(rows, 1)
        self.assertEqual(link.values, (1,))

    def test_downstream_guard_rejects_reorder_atomically(self):
        doc, rows, first, second, _, link = self.linked()
        extra = link.add('Target', 1)
        doc.references.bind(link, second, Index(extra), guards=(Guard(link, (0,)),))
        before = rows.children()
        with self.assertRaisesRegex(ReferenceError, 'reference mode'):
            first.move_to(rows, 2)
        self.assertEqual(rows.children(), before)
        self.assertEqual((link.values, extra.values), ((0,), (1,)))
        doc.validate()

    def test_segment_split_is_atomic_but_reversal_keeps_identity(self):
        doc, rows, first, second, third, _ = self.linked()
        link = doc.root.add('Segment', 1)
        ref = doc.references.bind(link, Segment(first, second), Index(link))
        before = rows.children()
        with self.assertRaisesRegex(ReferenceError, 'segment was split'):
            third.move_to(rows, 1)
        self.assertEqual(rows.children(), before)
        first.move_to(rows, 1)
        self.assertIs(doc.references.get(ref.uid).target.start, first)
        self.assertEqual(link.values, (1,))
        doc.validate()

    def test_retarget_and_discard_release_old_collection_users(self):
        doc, rows, first, second, _, link = self.linked()
        other = doc.root.add('OtherRows')
        a, b = other.add('Row'), other.add('Row')
        # Both parent kinds must agree for an indexed target domain.
        other.kind = 'Rows'
        ref = doc.references.outgoing(link)[0]
        ref = doc.references.retarget(ref, a)
        first.move_to(rows, 2)
        self.assertEqual(link.values, (0,))
        a.move_to(other, 1)
        self.assertEqual(link.values, (1,))
        doc.references.discard(ref)
        a.move_to(other, 0)
        self.assertEqual(link.values, (1,))

    def test_manual_low_level_projection_change_is_not_silently_overwritten(self):
        doc, rows, first, _, _, link = self.linked()
        link.set_values(99)
        before = rows.children()
        with self.assertRaisesRegex(ReferenceError, 'managed index edited'):
            first.move_to(rows, 2)
        self.assertEqual(rows.children(), before)
        self.assertEqual(link.values, (99,))

    def test_noop_is_allowed_in_an_unresolved_scope(self):
        doc, rows, first, _, _, _ = self.linked()
        source = doc.root.add('Unknown', 999)
        doc.references.note(source, 'missing', Index(source), collections=(rows,))
        first.move_to(rows, 0)
        doc.validate()

    def test_insert_and_remove_unreferenced_siblings_update_existing_links(self):
        doc, rows, first, _, _, link = self.linked()
        added = Element('Row')
        with patch.object(doc, '_validate_structure', side_effect=AssertionError('full scan')):
            rows.insert(added, 0)
            self.assertEqual(link.values, (1,))
            added.detach()
        self.assertEqual(link.values, (0,))
        self.assertIs(doc.references.outgoing(link)[0].target, first)
        doc.validate()

    def test_insert_preflights_downstream_guards_before_attaching(self):
        doc, rows, first, second, _, link = self.linked()
        slot = link.add('Target', 1)
        doc.references.bind(link, second, Index(slot), guards=(Guard(link, (0,)),))
        added = Element('Row')
        before = rows.children()
        with self.assertRaisesRegex(ReferenceError, 'reference mode'):
            rows.insert(added, 0)
        self.assertIsNone(added.parent)
        self.assertEqual(rows.children(), before)
        self.assertEqual((link.values, slot.values), ((0,), (1,)))

    def test_inserting_duplicate_public_keys_is_atomic(self):
        doc = Document()
        rows = doc.root.add('Rows')
        first = rows.add('Row')
        first.add('Id', 12)
        link = doc.root.add('Link', 12)
        doc.references.bind(link, first, Key(link))
        added = Element('Row')
        added.add('Id', 12)
        with self.assertRaisesRegex(ReferenceError, 'duplicate'):
            rows.append(added)
        self.assertIsNone(added.parent)
        self.assertEqual(rows.children(), [first])
        doc.validate()

    def test_target_source_and_projection_field_removal_require_explicit_resolution(self):
        doc, rows, first, _, _, link = self.linked()
        for node in (first, link, rows):
            with self.subTest(node=node.kind), self.assertRaisesRegex(ReferenceError, 'referenced content'):
                node.detach()
            self.assertIsNotNone(node.parent)
        ref = doc.references.outgoing(link)[0]
        doc.references.discard(ref)
        first.detach()
        link.detach()
        doc.validate()

    def test_broad_source_does_not_hide_a_managed_field_inside_a_removed_subtree(self):
        doc = Document()
        target = doc.root.add('Rows').add('Row')
        collection = doc.root.add('Fields')
        field = collection.add('Link', 0)
        doc.references.bind(doc.root, target, Index(field))
        with self.assertRaisesRegex(ReferenceError, 'referenced content'):
            collection.detach()
        self.assertIs(field.parent, collection)
        doc.validate()

    def test_cross_parent_move_projects_and_reindexes_ancestor_users(self):
        doc = Document()
        blocks = doc.root.add('Blocks')
        first, second = blocks.add('Block'), blocks.add('Block')
        old, new = first.add('Rows'), second.add('Rows')
        moved = old.add('Row')
        new.add('Row')
        link = doc.root.add('Link', 0, 0)
        doc.references.bind(link, moved, Index(link), Index(link, argument=1, ancestor=2))
        moved.move_to(new)
        self.assertEqual(link.values, (1, 1))
        second.move_to(blocks, 0)
        self.assertEqual(link.values, (1, 0))
        new.insert(Element('Row'), 0)
        self.assertEqual(link.values, (2, 0))
        # The old collection no longer owns the moved target's index projection.
        old.add('Row')
        self.assertEqual(link.values, (2, 0))
        doc.validate()

    def test_cross_parent_domain_failure_leaves_both_collections_unchanged(self):
        doc, rows, first, _, _, link = self.linked()
        other = doc.root.add('Different')
        before = rows.children()
        with self.assertRaisesRegex(ReferenceError, 'incompatible type or scope'):
            first.move_to(other)
        self.assertEqual(rows.children(), before)
        self.assertEqual(other.children(), [])
        self.assertEqual(link.values, (0,))
        doc.validate()

    def test_child_minimum_and_destination_type_are_checked_before_moving(self):
        doc = Document()
        schema = Record('Owner', {}, children={'Row': Child('Row', 'Row', minimum=1, maximum=None)})
        source = doc.root.add('Owner').bind_schema(schema)
        row = source.append(Element('Row').bind_schema(Record('Row', {})))
        destination = doc.root.add('Owner').bind_schema(schema)
        with self.assertRaisesRegex(ValueError, 'child count'):
            row.move_to(destination)
        self.assertIs(row.parent, source)
        source.add('Row')
        wrong = Element('Row').bind_schema(Record('Wrong', {}))
        with self.assertRaisesRegex(TypeError, 'expected Row'):
            destination.append(wrong)
        self.assertIsNone(wrong.parent)

    def test_cross_document_move_rejects_links_and_allows_independent_content(self):
        doc, rows, first, second, _, link = self.linked()
        other = Document()
        with self.assertRaisesRegex(ReferenceError, 'referenced content'):
            first.move_to(other.root)
        second.move_to(other.root)
        self.assertIs(other.get(second.uid), second)
        self.assertEqual(link.values, (0,))
        doc.validate()
        other.validate()

    def test_declared_ordinal_dependency_cannot_be_removed_through_an_unrelated_target(self):
        doc = Document()
        row = doc.root.add('Rows').add('Row')
        summary = doc.root.add('Summary')
        schema = Record('Summary', {'Index': Field('Index', 'integer', getter=lambda node: row._ordinal(),
                       ordinal_dependencies=lambda node: (row,))}, ('Index',))
        summary.bind_schema(schema)
        copy = doc.root.add('Copy', 0)
        reference = doc.references.bind(copy, summary, Property(copy))
        with self.assertRaisesRegex(ReferenceError, 'referenced content'):
            row.detach()
        self.assertIsNotNone(row.parent)
        doc.references.discard(reference)
        row.detach()

    def test_detached_subtrees_are_not_retained_by_prior_watch_and_identity_caches(self):
        doc = Document()
        group = doc.root.add('Group')
        collection = group.add('Rows')
        collection.add('Row')
        for node in (doc.root, group, collection):
            doc.references.watch(node)
        del node
        doc.get(collection.uid)
        group_ref, collection_ref = weakref.ref(group), weakref.ref(collection)
        group.detach()
        del group, collection
        gc.collect()
        self.assertIsNone(group_ref())
        self.assertIsNone(collection_ref())
        doc.validate()

    def test_cross_document_moves_release_the_old_documents_watch_snapshots(self):
        doc, other = Document(), Document()
        group = doc.root.add('Group')
        collection = group.add('Rows')
        doc.references.watch(doc.root)
        doc.references.watch(collection)
        group_ref = weakref.ref(group)
        group.move_to(other.root)
        group.detach()
        del group, collection
        gc.collect()
        self.assertIsNone(group_ref())
        doc.validate()
        other.validate()
