"""Record lifecycle edits preserve owned topology and protect external users."""
import unittest
import gc
import weakref
from unittest.mock import patch

from lib.common.model import Document, Element
from lib.common.references import Guard, Index, Key, Property, ReferenceError, Segment
from lib.common.schema import Field, Record


NAMED = Record('Item', {'Name': Field('Name', 'text', required=True, default='')}, ('Name',))


class RecordEditTests(unittest.TestCase):
    def design(self):
        doc = Document()
        collection = doc.root.add('Records')
        group = collection.add('Group')
        target = group.add('Targets').append(Element('Item', 'A').bind_schema(NAMED))
        source = group.add('Source')
        slot = source.add('Target', 0)
        doc.references.bind(source, target, Index(slot), role='internal')
        external = doc.root.add('Outside').append(Element('Item', 'E').bind_schema(NAMED))
        key = source.add('External', 'E')
        doc.references.bind(source, external, Key(key, 'Name'), role='external')
        return doc, collection, group, source, target, external

    def test_copy_remaps_internal_targets_and_keeps_external_targets_without_scans(self):
        doc, collection, group, source, target, external = self.design()
        with patch.object(doc.root, 'walk', side_effect=AssertionError('document scan')), \
             patch.object(type(doc.references), '__iter__', side_effect=AssertionError('graph scan')):
            copied = doc.copy(group, index=0)
        own = doc.references.outgoing(copied.one('Source'))
        self.assertIs(own[0].target, copied.one('Targets/Item'))
        self.assertIs(own[1].target, external)
        copied.one('Targets/Item')['Name'] = 'B'
        self.assertEqual(target['Name'], 'A')
        external['Name'] = 'Renamed'
        self.assertEqual((source.one('External').values, copied.one('Source/External').values), (('Renamed',),)*2)
        doc.validate()

    def test_copy_preserves_segment_and_mode_guards(self):
        doc, _, group, source, _, _ = self.design()
        points = group.add('Points')
        a, b = points.add('pt', 0), points.add('pt', 1)
        mode = source.add('Mode', 1)
        field = source.add('Segment', 1)
        doc.references.bind(source, Segment(a, b), Index(field), role='segment', guards=(Guard(mode, (1,)),))
        copied = doc.copy(group)
        link = doc.references.outgoing(copied.one('Source'), role='segment')[0]
        self.assertIs(link.target.start, copied.one('Points/pt[1]'))
        self.assertIs(link.guards[0].field, copied.one('Source/Mode'))
        with self.assertRaises(ReferenceError):
            copied.one('Points').add('pt', 2).move_to(copied.one('Points'), 1)
        doc.validate()

    def test_remove_discards_owned_links_and_leaves_external_targets(self):
        doc, collection, group, source, target, external = self.design()
        with patch.object(doc.root, 'walk', side_effect=AssertionError('document scan')), \
             patch.object(type(doc.references), '__iter__', side_effect=AssertionError('graph scan')):
            removed = doc.remove(group)
        self.assertIs(removed, group)
        self.assertIsNone(group.parent)
        self.assertEqual(len(doc.references), 0)
        self.assertEqual(collection.children(), [])
        self.assertIsNotNone(external.parent)
        self.assertNotIn(target, doc.references._content_users)
        doc.validate()

    def test_external_user_rejects_removal_without_discarding_owned_links(self):
        doc, _, group, _, target, _ = self.design()
        outside = doc.root.add('Selection', 0)
        doc.references.bind(outside, target, Index(outside), role='selection')
        before = tuple(doc.references)
        with self.assertRaisesRegex(ReferenceError, 'referenced content'):
            doc.remove(group)
        self.assertEqual(tuple(doc.references), before)
        self.assertIsNotNone(group.parent)
        doc.validate()

    def test_copy_root_field_override_is_validated_before_attachment(self):
        doc = Document()
        records = doc.root.add('Records')
        node = records.append(Element('Item', 'A').bind_schema(NAMED))
        copied = doc.copy(node, fields={'Name': 'B'})
        self.assertEqual((node['Name'], copied['Name']), ('A', 'B'))
        with self.assertRaises(TypeError):
            doc.copy(node, fields={'Name': 42})
        self.assertEqual(len(records.children()), 2)

    def test_owned_unresolved_links_copy_their_scopes_and_can_be_removed_deliberately(self):
        doc, _, group, source, _, _ = self.design()
        missing = source.add('Missing', 99)
        original = doc.references.note(source, 'missing', Index(missing), collections=(group.one('Targets'),))
        copied = doc.copy(group)
        copied_issue = next(issue for issue in doc.references.issues if issue is not original)
        self.assertIs(copied_issue.source, copied.one('Source'))
        self.assertEqual(copied_issue.collections, (copied.one('Targets'),))
        doc.remove(copied)
        self.assertEqual(doc.references.issues, [original])
        self.assertEqual(doc.references._content_issues(tuple(copied.walk(include_self=True))), ())
        doc.validate()

    def test_external_unresolved_scope_blocks_removing_a_target_collection(self):
        doc, _, group, _, _, _ = self.design()
        outside = doc.root.add('Unknown', 99)
        issue = doc.references.note(outside, 'unknown', Index(outside), collections=(group.one('Targets'),))
        before = tuple(doc.references)
        with self.assertRaisesRegex(ReferenceError, 'unresolved reference content'):
            doc.remove(group)
        self.assertEqual(tuple(doc.references), before)
        self.assertIn(issue, doc.references.issues)
        doc.validate()

    def test_links_with_broader_sources_are_owned_by_their_index_fields(self):
        doc = Document()
        records = doc.root.add('Records')
        row = records.add('Row')
        field = row.add('Target', 0)
        target = doc.root.add('Targets').add('Item')
        doc.references.bind(doc.root, target, Index(field), role='broad-owner')
        copied = doc.copy(row)
        self.assertTrue(doc.references.manages(copied.one('Target')))
        doc.remove(row)
        self.assertEqual(len(doc.references), 1)
        self.assertIs(doc.references.outgoing(doc.root)[0].indices[0].field, copied.one('Target'))
        doc.validate()

    def test_duplicate_key_failure_keeps_original_links_and_tree(self):
        doc, _, group, _, target, _ = self.design()
        outside = doc.root.add('KeyUser', 'A')
        doc.references.bind(outside, target, Key(outside, 'Name'))
        before = tuple(doc.references)
        with self.assertRaisesRegex(ReferenceError, 'duplicate Name key'):
            doc.copy(target)
        self.assertEqual(tuple(doc.references), before)
        self.assertEqual(target.parent.children(), [target])
        other = doc.copy(target, fields={'Name': 'B'})
        self.assertEqual(other['Name'], 'B')
        doc.validate()

    def test_named_fields_use_their_existing_assignment_and_deletion_path(self):
        doc = Document()
        node = doc.root.append(Element('Item', 'A').bind_schema(NAMED))
        for operation in (doc.copy, doc.remove):
            with self.assertRaisesRegex(TypeError, 'named assignment or deletion'):
                operation(node.one('Name'))
        self.assertEqual(node['Name'], 'A')

    def test_copy_options_cannot_silently_override_or_be_overridden_by_a_managed_field(self):
        doc = Document()
        records = doc.root.add('Records')
        node = records.append(Element('Item', 'A').bind_schema(NAMED))
        target = doc.root.append(Element('Item', 'External').bind_schema(NAMED))
        doc.references.bind(node, target, Property(node.one('Name'), 'Name'))
        before = tuple(doc.references)
        with self.assertRaisesRegex(ReferenceError, 'managed projection'):
            doc.copy(node, fields={'Name': 'Conflicting'})
        self.assertEqual(tuple(doc.references), before)
        self.assertEqual(records.children(), [node])
        self.assertEqual(node['Name'], 'External')
        doc.validate()

    def test_removal_releases_owned_issue_and_reference_indexes(self):
        doc, _, group, source, target, external = self.design()
        missing = source.add('Missing', 99)
        issue = doc.references.note(source, 'missing', Index(missing), collections=(group.one('Targets'),))
        observed = weakref.ref(source)
        doc.get(source.uid)  # Populate the lazy identity cache as well.
        doc.remove(group)
        del group, source, target, missing, issue
        gc.collect()
        self.assertIsNone(observed())
        self.assertEqual(doc.references.issues, [])
