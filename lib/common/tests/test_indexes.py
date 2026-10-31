"""Lookup results remain current across supported tree and graph mutations."""
import unittest

from lib import Document, Element, Index, ReferenceError, Segment


class TreeLookupTests(unittest.TestCase):
    def test_reused_selectors_and_paths_follow_field_and_order_changes(self):
        parent = Element('Items')
        first, second = parent.add('Item'), parent.add('Item')
        first.add('Name', 'A')
        second.add('Name', 'B')
        self.assertEqual(parent.select('Item[Name="A"]'), [first])
        first.set_field('Name', 'C')
        self.assertEqual(parent.select('Item[Name="A"]'), [])
        self.assertEqual(first.path, '/Item[1]')
        first.move_to(parent, 1)
        self.assertEqual(first.path, '/Item[2]')
        self.assertEqual(second.path, '/Item[1]')
        self.assertEqual(parent.select('Item[1]'), [second])

    def test_insert_rename_move_and_delete_after_prior_reads(self):
        parent, other = Element('Fields'), Element('Other')
        first = parent.add('Value', 'first')
        second = parent.add('Value', 'second')
        self.assertIs(parent.child('Value'), first)
        parent.children()
        second.kind = 'Label'
        self.assertEqual(parent.children('Value'), [first])
        self.assertIs(parent.child('Label'), second)
        inserted = parent.insert(Element('Value', 'new'), 0)
        self.assertIs(parent.child('Value'), inserted)
        first.move_to(other)
        self.assertEqual(parent.children('Value'), [inserted])
        self.assertIs(other.child('Value'), first)
        inserted.detach()
        self.assertIsNone(parent.child('Value'))
        self.assertEqual(parent.children(), [second])
        self.assertEqual(parent.select('Label'), [second])

    def test_public_child_lists_are_independent(self):
        parent = Element('Fields')
        value = parent.add('Value', 1)
        parent.children().clear()
        parent.children('Value').append(Element('Value', 2))
        self.assertEqual(parent.children(), [value])
        self.assertEqual(parent.scalar('Value'), 1)

    def test_appended_fields_preserve_order_and_isolate_empty_lookups(self):
        first, second = Element('Fields', 'header'), Element('Fields')
        self.assertEqual(first.children(), [])
        self.assertEqual(second.children(), [])
        self.assertIsNone(first.child('Name'))
        earlier = first.children()
        name = first.set_field('Name', 'A')
        self.assertIsNone(first.child('Value'))
        value = first.set_field('Value', 3)
        self.assertEqual(earlier, [])
        self.assertEqual(first.values, ('header',))
        self.assertEqual(first.children(), [name, value])
        self.assertEqual(first.children('Name'), [name])
        self.assertEqual(first.children('Value'), [value])
        self.assertEqual(second.children(), [])
        self.assertIsNone(second.child('Name'))

        # Repeated kinds and middle insertions retain their own child ordinals.
        later = first.set_field('Value', 5, occurrence=1)
        label = first.insert(Element('Label', 'middle'), 1)
        self.assertEqual(first.children(), [name, label, value, later])
        self.assertEqual(first.children('Value'), [value, later])
        self.assertEqual((value.path, later.path), ('/Value[1]', '/Value[2]'))
        value.detach()
        self.assertIs(first.child('Value'), later)
        self.assertEqual(later.path, '/Value[1]')

    def test_value_arity_changes_keep_children_and_scalar_reads_current(self):
        parent = Element('Fields', 'header')
        value = parent.add('Value', 1)
        parent.children()
        parent.set_values('new', 2)
        self.assertEqual(parent.values, ('new', 2))
        self.assertIs(parent.child('Value'), value)
        value.set_values(4, 5)
        self.assertEqual(parent.scalar('Value'), (4, 5))
        value.set_values()
        self.assertEqual(parent.scalar('Value'), ())

    def test_clone_owns_its_children_after_warm_lookups(self):
        parent = Element('Fields')
        original = parent.add('Value', 1)
        parent.children()
        parent.child('Value')
        copied = parent.clone()
        self.assertIsNot(copied.child('Value'), original)
        copied.child('Value').kind = 'Changed'
        self.assertIsNone(copied.child('Value'))
        self.assertIs(parent.child('Value'), original)

    def test_clone_owns_empty_and_nested_annotations(self):
        parent = Element('Fields')
        original = parent.add('Value', 1)
        parent.annotations['notes'] = [{'text': 'original'}]
        copied = parent.clone()
        copied.annotations['notes'][0]['text'] = 'copy'
        copied.child('Value').annotations['notes'] = ['copy']
        self.assertEqual(parent.annotations, {'notes': [{'text': 'original'}]})
        self.assertEqual(original.annotations, {})
        self.assertNotEqual(copied.uid, parent.uid)
        self.assertNotEqual(copied.child('Value').uid, original.uid)


class ReferenceLookupTests(unittest.TestCase):
    def design(self):
        document = Document()
        targets = document.root.add('Targets')
        first, second = targets.add('Item'), targets.add('Item')
        sources = document.root.add('Sources')
        left, right = sources.add('Link', 0), sources.add('Link', 1)
        early = document.references.bind(left, first, Index(left), role='left')
        late = document.references.bind(right, second, Index(right), role='right')
        return document, first, second, left, right, early, late

    def test_retarget_preserves_global_order_and_discard_updates_both_directions(self):
        doc, first, second, left, right, early, late = self.design()
        self.assertEqual(doc.references.incoming(second), [late])
        current = doc.references.retarget(early, second)
        self.assertEqual(doc.references.incoming(first), [])
        self.assertEqual(doc.references.incoming(second), [current, late])
        self.assertEqual(doc.references.incoming(second, role='right'), [late])
        self.assertEqual(doc.references.outgoing(left), [current])
        doc.references.discard(current)
        self.assertEqual(doc.references.incoming(second), [late])
        self.assertEqual(doc.references.outgoing(left), [])
        self.assertEqual(doc.references.outgoing(right), [late])

    def test_failed_retarget_does_not_change_query_results(self):
        doc, first, second, left, right, early, late = self.design()
        detached = Element('Item')
        with self.assertRaises(ReferenceError):
            doc.references.retarget(early, detached)
        self.assertEqual(doc.references.outgoing(left), [early])
        self.assertEqual(doc.references.incoming(first), [early])
        self.assertEqual(doc.references.incoming(second), [late])

    def test_segment_queries_include_endpoints_without_duplicate_results(self):
        doc = Document()
        points = doc.root.add('Points')
        first, second, third = [points.add('Point') for _ in range(3)]
        source = doc.root.add('Link', 1)
        target = Segment(first, second)
        link = doc.references.bind(source, target, Index(source), role='segment')
        self.assertEqual(doc.references.incoming(first), [link])
        self.assertEqual(doc.references.incoming(second), [link])
        self.assertEqual(doc.references.incoming(target), [link])
        self.assertEqual(doc.references.incoming(Segment(first, second)), [])
        updated = doc.references.retarget(link, Segment(second, third))
        self.assertEqual(doc.references.incoming(first), [])
        self.assertEqual(doc.references.incoming(second), [updated])
        self.assertEqual(doc.references.incoming(third), [updated])

    def test_clone_queries_use_cloned_owners_and_targets(self):
        doc, first, second, left, right, early, late = self.design()
        copied = doc.clone()
        copy_first = copied.one('/Targets/Item[1]')
        copy_left = copied.one('/Sources/Link[1]')
        result = copied.references.incoming(copy_first)
        self.assertEqual(len(result), 1)
        self.assertIs(result[0].source, copy_left)
        self.assertEqual(copied.references.incoming(first), [])
        copied.references.discard(result[0])
        self.assertEqual(doc.references.incoming(first), [early])


if __name__ == '__main__':
    unittest.main()
