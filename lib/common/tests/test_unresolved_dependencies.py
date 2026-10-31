"""An unresolved selection can depend on another identity without storing a copy."""
from dataclasses import replace
import unittest

from lib.common.model import Document, Element
from lib.common.references import Index, ReferenceError
from lib.common.reference_edits import preview_references
from lib.common.schema import Field, Record


def selection(node):
    links = node._owner().references.outgoing(node, role='scope')
    return links[0].target if links else None


STATE = Record('State', {'Scope': Field('Scope', 'reference', nullable=True, getter=selection,
    reference_dependencies=lambda node: ((node, 'scope', 'outgoing'),))})
SOURCE = Record('Selection', {'Id': Field('Id', 'integer', getter=lambda node: node._ordinal(),
    ordinal_dependencies=lambda node: (node,))})


class ScopedDocument(Document):
    def _unresolved_reference_fields(self, issue):
        return ((issue.source.parent, STATE.fields['Scope']), (issue.source, SOURCE.fields['Id']))

    def _validate_unresolved_reference(self, issue):
        if issue.collections != (selection(issue.source.parent),):
            raise ReferenceError('the unavailable selection must keep its current scope')


def design(document_type=ScopedDocument):
    document = document_type()
    first, second = document.root.add('Scope'), document.root.add('Scope')
    state = document.root.append(Element('State').bind_schema(STATE))
    link = document.references.bind(state, first, role='scope')
    source = state.append(Element('Selection').bind_schema(SOURCE))
    slot = source.add('MissingIndex', 99)
    document.references.note(source, 'unavailable selection', Index(slot), collections=(first,))
    return document, state, source, link, first, second


class UnresolvedDependencyTests(unittest.TestCase):
    def test_moving_unresolved_content_revalidates_scope_without_an_ordinal_dependency(self):
        class OwnershipDocument(ScopedDocument):
            def _unresolved_reference_fields(self, issue):
                return ((issue.source.parent, STATE.fields['Scope']),)
        document, state, source, link, first, second = design(OwnershipDocument)
        other = document.root.append(Element('State').bind_schema(STATE))
        document.references.bind(other, second, role='scope')
        with self.assertRaisesRegex(ReferenceError, 'current scope'):
            source.move_to(other)
        self.assertIs(source.parent, state)
        document.references.validate()
    def test_relationship_changes_preflight_the_existing_unresolved_scope(self):
        document, state, source, link, first, second = design()
        with self.assertRaises(ReferenceError):
            document.references.retarget(link, second)
        with self.assertRaises(ReferenceError):
            document.references.discard(link)
        self.assertIs(state['Scope'], first)
        second.add('Item')  # Another scope is independently editable.
        document.references.validate()

    def test_copy_and_removal_apply_owned_links_and_issues_as_one_change(self):
        document, state, source, link, first, second = design()
        copied = document.copy(state)
        self.assertIs(copied['Scope'], first)
        self.assertEqual(len(document.references.issues), 2)
        document.remove(copied)
        document.remove(state)
        self.assertEqual(document.references.issues, [])
        document.references.validate()

    def test_moving_the_unavailable_selection_cannot_silently_change_its_scope(self):
        document, state, source, link, first, second = design()
        other = document.root.append(Element('State').bind_schema(STATE))
        document.references.bind(other, second, role='scope')
        with self.assertRaises(ReferenceError):
            source.move_to(other)
        self.assertIs(source.parent, state)
        document.references.validate()

    def test_content_query_uses_planned_removals_retargets_and_local_additions(self):
        document = Document()
        a, b, c = [document.root.add(kind) for kind in ('A', 'B', 'C')]
        first = document.references.bind(a, b)
        second = document.references.bind(c, b)
        replacement = replace(first, target=c)
        addition = replace(first, uid='added', source=c, target=a)
        d, e = document.root.add('D'), document.root.add('E')
        unrelated = replace(first, uid='unrelated', source=d, target=e)
        with preview_references(document.references, {first.uid: replacement, second.uid: None,
                                                      addition.uid: addition, unrelated.uid: unrelated}):
            self.assertEqual(document.references._content_references((a,)), (replacement, addition))
            self.assertEqual(document.references._content_references((c,)), (replacement, addition))
            self.assertEqual(document.references._content_references((b,)), (replacement,))
        self.assertEqual(document.references._content_references((a,)), (first,))


if __name__ == '__main__':
    unittest.main()
