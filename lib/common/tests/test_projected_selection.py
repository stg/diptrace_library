"""Selecting and clearing several projected scalars preflights their consumers."""
import unittest

from lib.common.model import Document
from lib.common.reference_edits import assign_projected_reference
from lib.common.references import Guard, Key, Property, ReferenceError
from lib.common.schema import Field, Record


ENTRY = Record('Entry', {name: Field(name, kind) for name, kind in (('Name', 'text'), ('Index', 'integer'))})


class ProjectedSelectionTests(unittest.TestCase):
    def example(self):
        document = Document()
        source = document.root.add('Source').bind_schema(ENTRY)
        source.add('Name', 'Literal')
        source.add('Index', 42)
        target = document.root.add('Targets').add('Target').bind_schema(ENTRY)
        target.add('Name', 'Selected')
        target.add('Index', 7)
        indices = (Key(source.one('Index'), name='Index'), Property(source.one('Name'), name='Name'))
        mirror = document.root.add('Mirror').bind_schema(ENTRY)
        mirror.add('Name', '')
        mirror.add('Index', 0)
        document.references.bind(mirror, source, Property(mirror.one('Name'), name='Name'),
                                 Property(mirror.one('Index'), name='Index'), role='copy')
        return document, source, target, mirror, indices

    def test_select_retarget_and_clear_update_all_copies(self):
        document, source, target, mirror, indices = self.example()
        assign_projected_reference(source, target, role='choice', indices=indices,
                                    clear_values={'Name': '', 'Index': -1})
        self.assertEqual(('Selected', 7), (mirror['Name'], mirror['Index']))
        target['Name'] = 'Renamed'
        self.assertEqual('Renamed', source['Name'])
        assign_projected_reference(source, None, role='choice', clear_values={'Name': '', 'Index': -1})
        self.assertEqual(('', -1), (mirror['Name'], mirror['Index']))
        document.validate()

    def test_new_selection_and_clear_leave_all_values_unchanged_on_guard_failure(self):
        document, source, target, mirror, indices = self.example()
        graph = document.references
        guard = graph.bind(mirror, target, role='hold', guards=(Guard(mirror.one('Index'), (42,)),))
        with self.assertRaises(ReferenceError):
            assign_projected_reference(source, target, role='choice', indices=indices,
                                        clear_values={'Name': '', 'Index': -1})
        self.assertEqual(('Literal', 42), (source['Name'], source['Index']))
        self.assertEqual(('Literal', 42), (mirror['Name'], mirror['Index']))
        self.assertFalse(graph.outgoing(source, role='choice'))
        graph.discard(guard)
        assign_projected_reference(source, target, role='choice', indices=indices,
                                    clear_values={'Name': '', 'Index': -1})
        guard = graph.bind(mirror, target, role='hold', guards=(Guard(mirror.one('Index'), (7,)),))
        with self.assertRaises(ReferenceError):
            assign_projected_reference(source, None, role='choice', clear_values={'Name': '', 'Index': -1})
        self.assertEqual(('Selected', 7), (source['Name'], source['Index']))
        self.assertEqual(('Selected', 7), (mirror['Name'], mirror['Index']))
        document.validate()
