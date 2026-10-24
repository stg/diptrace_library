"""Full audits are independent of compatibility-index projection."""
import unittest
from unittest.mock import patch

from lib import Document, Element, Index, ReferenceError


class ValidationTests(unittest.TestCase):
    def linked(self):
        doc = Document()
        targets = doc.root.add('Targets')
        first, second = targets.add('Item'), targets.add('Item')
        link = doc.root.add('Link', 0)
        doc.references.bind(link, first, Index(link))
        return doc, targets, first, second, link

    def test_reorder_projects_immediately_and_validate_does_not_write(self):
        doc, targets, first, _, link = self.linked()
        first.move_to(targets, 1)
        self.assertEqual(link.values, (1,))
        with patch.object(link, 'set_argument', side_effect=AssertionError('audit wrote a value')):
            doc.validate()
        doc.rebuild(force=False)
        self.assertEqual(link.values, (1,))

    def test_validate_rejects_invalid_links_without_applying_other_pending_changes(self):
        doc, targets, first, second, link = self.linked()
        other = doc.root.add('Other', 1)
        doc.references.bind(other, second, Index(other))
        first.move_to(targets, 1)
        # Full audits still detect private corruption of an otherwise safe API.
        targets._items.remove(second)
        second._parent = None
        targets._touch(reordered=True)
        with self.assertRaises(ReferenceError):
            doc.validate()
        self.assertEqual(link.values, (1,))

    def test_repeated_identity_reads_use_one_private_index(self):
        doc, _, first, _, _ = self.linked()
        with patch.object(doc, 'rebuild_index', wraps=doc.rebuild_index) as audit:
            self.assertIs(doc.get(first.uid), first)
            self.assertIs(doc.get(first.uid), first)
            self.assertEqual(audit.call_count, 1)

    def test_identity_index_tracks_insert_move_detach_and_clone(self):
        doc, targets, first, _, _ = self.linked()
        doc.get(first.uid)
        added = targets.add('Item')
        self.assertIs(doc.get(added.uid), added)
        other = Document()
        added.move_to(other.root)
        self.assertIs(other.get(added.uid), added)
        with self.assertRaises(LookupError):
            doc.get(added.uid)
        added.detach()
        with self.assertRaises(LookupError):
            other.get(added.uid)
        copied = doc.clone()
        clone_first = copied.one('/Targets/Item[1]')
        self.assertIs(copied.get(clone_first.uid), clone_first)
        with self.assertRaises(LookupError):
            copied.get(first.uid)

    def test_validate_audits_even_after_the_lookup_index_was_built(self):
        doc, _, first, _, _ = self.linked()
        doc.get(first.uid)
        # Private corruption cannot be caused through the supported API, but a
        # full audit must still find it rather than trusting a warmed cache.
        broken = Element('Broken')
        doc.root._items.append(broken)
        with self.assertRaisesRegex(ValueError, 'inconsistent parent'):
            doc.validate()
