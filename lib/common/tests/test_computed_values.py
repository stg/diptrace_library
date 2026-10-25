"""Calculated property copies follow ordinary values and changing identities."""
import unittest
from unittest.mock import patch

from lib.common.model import Document, Element
from lib.common.references import Guard, Index, Property, ReferenceError
from lib.common.schema import Field, Record


def basis(node):
    links = node._owner().references.outgoing(node, role='basis')
    return links[0].target if links else None


BASE = Record('Base', {'Value': Field('Value', 'number', default=1)})
DERIVED = Record('Derived', {'Value': Field('Value', 'number',
    getter=lambda node: target['Value']*2 if (target := basis(node)) is not None else 0,
    reference_dependencies=lambda node: ((node, 'basis', 'outgoing'),),
    value_dependencies=lambda node: ((target, 'Value'),) if (target := basis(node)) is not None else ())})


class ComputedValueTests(unittest.TestCase):
    def design(self):
        document = Document()
        first = document.root.append(Element('Base').bind_schema(BASE))
        first['Value'] = 2
        second = document.root.append(Element('Base').bind_schema(BASE))
        second['Value'] = 7
        derived = document.root.append(Element('Derived').bind_schema(DERIVED))
        link = document.references.bind(derived, first, role='basis')
        probe = document.root.add('Probe', 0)
        document.references.bind(probe, derived, Property(probe, 'Value'), role='copy')
        return document, first, second, derived, link, probe

    def test_scalar_changes_propagate_without_scanning_the_document_or_graph(self):
        document, first, _, derived, _, probe = self.design()
        with patch.object(document.root, 'walk', side_effect=AssertionError('whole document scan')), \
             patch.object(type(document.references), '__iter__', side_effect=AssertionError('whole graph scan')):
            first['Value'] = 3
            self.assertEqual((derived['Value'], probe.values), (6, (6,)))
        document.validate()

    def test_retarget_refreshes_value_and_content_dependencies(self):
        document, first, second, _, link, probe = self.design()
        document.references.retarget(link, second)
        self.assertEqual(probe.values, (14,))
        first['Value'] = 99
        self.assertEqual(probe.values, (14,))
        document.remove(first)
        second['Value'] = 5
        self.assertEqual(probe.values, (10,))
        document.validate()

    def test_nested_calculations_follow_inner_relationship_changes(self):
        document, first, second, derived, link, _ = self.design()
        next_level = document.root.append(Element('Derived').bind_schema(DERIVED))
        document.references.bind(next_level, derived, role='basis')
        probe = document.root.add('Nested', 0)
        document.references.bind(probe, next_level, Property(probe, 'Value'), role='copy')
        self.assertEqual(probe.values, (8,))
        document.references.retarget(link, second)
        self.assertEqual(probe.values, (28,))
        second['Value'] = 4
        self.assertEqual(probe.values, (16,))
        first['Value'] = 10
        self.assertEqual(probe.values, (16,))
        document.validate()

    def test_downstream_guard_rejects_the_original_value_change_atomically(self):
        document, first, _, _, _, probe = self.design()
        output = probe.add('Target', 0)
        document.references.bind(probe, first, Index(output), guards=(Guard(probe, (4,)),))
        with self.assertRaises(ReferenceError):
            first['Value'] = 3
        self.assertEqual((first['Value'], probe.values), (2, (4,)))
        document.validate()

    def test_copy_cycle_through_a_calculated_value_is_rejected(self):
        document, first, _, derived, _, _ = self.design()
        with self.assertRaisesRegex(ReferenceError, 'cycle'):
            document.references.bind(first, derived, Property(first.one('Value'), 'Value'))
        self.assertEqual(first['Value'], 2)
        document.validate()


if __name__ == '__main__':
    unittest.main()
