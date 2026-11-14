"""Indexed choices keep one scalar and commit dependent edits atomically."""
import unittest

from lib.common.model import Document, Element
from lib.common.reference_edits import assign_indexed_reference
from lib.common.references import Guard, Index, Property, ReferenceError
from lib.common.schema import Field, Record


def selection(source):
    document = source._owner()
    if document is None:
        return None
    links = document.references.outgoing(source, role='choice')
    if links:
        return links[0].target
    if source.get('Code', 0) >= 20 and any(issue.message.startswith('choice:')
            for issue in document.references._source_issues(source)):
        raise ReferenceError('unavailable choice')
    return None


CHOICE = Record('Choice', {
    'Code': Field('Code', 'integer'),
    'Selection': Field('Selection', 'reference', nullable=True, getter=selection,
        setter=lambda source, target: assign_indexed_reference(source, target, role='choice',
            field_name='Code', offset=20, none_value=0),
        reference_dependencies=lambda source: ((source, 'choice', 'outgoing'),),
        value_dependencies=lambda source: ((source, 'Code'),) if source.child('Code') else (),
        collection_dependencies=lambda source: ((source, 'Code'),)),
})
MIRROR = Record('Mirror', {'Code': Field('Code', 'integer')})


def example(*, code=0):
    document = Document()
    rows = document.root.add('Rows')
    first, second = rows.add('Row', 'First'), rows.add('Row', 'Second')
    choice = document.root.add('Choice').bind_schema(CHOICE)
    if code is not None:
        choice.add('Code', code)
    return document, choice, first, second


class IndexedSelectionTests(unittest.TestCase):
    def test_first_selection_updates_copies_of_the_previous_literal(self):
        document, choice, _, second = example(code=7)
        mirror = document.root.add('Mirror').bind_schema(MIRROR)
        mirror.add('Code', 0)
        document.references.bind(mirror, choice, Property(mirror.one('Code'), 'Code'), role='copy')
        choice['Selection'] = second
        self.assertEqual((21, 21), (choice['Code'], mirror['Code']))
        document.validate()

    def test_retarget_reorder_clone_and_clear_keep_the_scalar_coordinated(self):
        document, choice, first, second = example()
        choice['Selection'] = second
        self.assertEqual(21, choice['Code'])
        second.move_to(second.parent, index=0)
        self.assertEqual(20, choice['Code'])
        choice['Selection'] = first
        self.assertEqual(21, choice['Code'])
        clone = document.clone()
        copied = clone.one('/Choice')
        self.assertIs(clone.one('/Rows/Row[2]'), copied['Selection'])
        copied['Selection'] = None
        self.assertEqual(0, copied['Code'])
        self.assertIsNone(copied['Selection'])
        self.assertIs(first, choice['Selection'])
        document.validate()
        clone.validate()

    def test_clearing_preflights_dependent_copies_and_guards(self):
        document, choice, first, second = example()
        choice['Selection'] = second
        mirror = document.root.add('Mirror').bind_schema(MIRROR)
        mirror.add('Code', 0)
        graph = document.references
        graph.bind(mirror, choice, Property(mirror.one('Code'), 'Code'), role='copy')
        guard = graph.bind(mirror, first, role='hold', guards=(Guard(mirror.one('Code'), (21,)),))
        with self.assertRaises(ReferenceError):
            choice['Selection'] = None
        self.assertIs(second, choice['Selection'])
        self.assertEqual((21, 21), (choice['Code'], mirror['Code']))
        graph.discard(guard)
        choice['Selection'] = None
        self.assertEqual((0, 0), (choice['Code'], mirror['Code']))
        document.validate()

    def test_unavailable_choices_can_be_resolved_or_cleared(self):
        for clear in (False, True):
            with self.subTest(clear=clear):
                document, choice, _, second = example(code=42)
                document.references.note(choice, 'choice: unavailable', Index(choice.one('Code'), offset=20),
                                         collections=(second.parent,))
                with self.assertRaises(ReferenceError):
                    _ = choice['Selection']
                choice['Selection'] = None if clear else second
                self.assertEqual(0 if clear else 21, choice['Code'])
                self.assertIs(None if clear else second, choice['Selection'])
                self.assertEqual([], document.references.issues)
                document.validate()

    def test_optional_scalar_creation_waits_for_a_valid_target(self):
        document, choice, _, second = example(code=None)
        _, _, foreign, _ = example()
        with self.assertRaises(ReferenceError):
            choice['Selection'] = foreign
        self.assertIsNone(choice.child('Code'))
        self.assertEqual(0, len(document.references))
        choice['Selection'] = second
        self.assertEqual(21, choice['Code'])
        document.validate()

    def test_resolving_an_unavailable_choice_preflights_its_dependent_guards(self):
        document, choice, first, second = example(code=42)
        graph = document.references
        graph.note(choice, 'choice: unavailable', Index(choice.one('Code'), offset=20),
                   collections=(second.parent,))
        mirror = document.root.add('Mirror').bind_schema(MIRROR)
        mirror.add('Code', 0)
        graph.bind(mirror, choice, Property(mirror.one('Code'), 'Code'), role='copy')
        guard = graph.bind(mirror, first, role='hold', guards=(Guard(mirror.one('Code'), (42,)),))
        with self.assertRaises(ReferenceError):
            choice['Selection'] = second
        self.assertEqual((42, 42), (choice['Code'], mirror['Code']))
        self.assertFalse(graph.outgoing(choice, role='choice'))
        self.assertEqual(1, len(graph.issues))
        graph.discard(guard)
        choice['Selection'] = second
        self.assertEqual((21, 21), (choice['Code'], mirror['Code']))
        self.assertEqual([], graph.issues)
        document.validate()


if __name__ == '__main__':
    unittest.main()
