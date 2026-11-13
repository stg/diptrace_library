"""Compact immutable values and optional notes retain their public behavior."""
from dataclasses import FrozenInstanceError, fields, replace
from decimal import Decimal
import unittest

from lib.common.model import Element, SourceSpan, Value


class ModelStorageTests(unittest.TestCase):
    def test_immutable_values_keep_reflection_replacement_and_source_locations(self):
        source = SourceSpan('example', 2, 9, 'input')
        original = Value(Decimal('1.25'), 'number', source=source)
        self.assertEqual([field.name for field in fields(original)],
                         ['value', 'kind', 'unit', 'lexeme', 'source'])
        changed = replace(original, value=Decimal('2.5'))
        self.assertIs(changed.source, source)
        self.assertEqual((source.start, source.end), (2, 9))
        with self.assertRaises(FrozenInstanceError):
            original.value = 3

    def test_empty_notes_are_not_allocated_by_clone_or_inspection(self):
        original = Element('Example', 1)
        original.add('Value', 2)
        copied = original.clone()
        self.assertEqual(original.inspect()['annotations'], {})
        self.assertIsNone(original._annotations)
        self.assertIsNone(copied._annotations)
        self.assertIsNone(copied.child('Value')._annotations)

    def test_user_notes_remain_mutable_and_cloned_independently(self):
        original = Element('Example')
        notes = original.annotations
        self.assertIs(notes, original.annotations)
        notes['notes'] = [{'value': 1}]
        copied = original.clone()
        copied.annotations['notes'][0]['value'] = 2
        self.assertEqual(original.annotations['notes'][0]['value'], 1)
        self.assertEqual(copied.annotations['notes'][0]['value'], 2)


if __name__ == '__main__':
    unittest.main()
