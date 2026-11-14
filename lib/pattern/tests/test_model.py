"""Data and relationship contracts for a standalone pattern library."""
import unittest

from lib.common.references import ReferenceError
from lib.pattern.model import new_library, new_pattern, new_pad, new_drawing, new_group
from lib.pattern.model.schema import pattern_schema


class PatternModelTests(unittest.TestCase):
    def design(self):
        document = new_library('Example', hint='Demonstration')
        pattern = new_pattern('Package')
        document.one('/Library/Patterns').append(pattern)
        pad = new_pad('1', x=3, y=6)
        pattern.one('Pads').append(pad)
        drawing = new_drawing()
        pattern.one('Shapes').append(drawing)
        return document, pattern, pad, drawing

    def test_complete_schema_and_shared_data_access(self):
        document, pattern, pad, _ = self.design()
        self.assertIn('PatternDocument', pattern_schema())
        self.assertEqual('Example', document.one('/Library')['Name'])
        self.assertEqual('Package', pattern['Name'])
        self.assertEqual('1', pad['StringNumber'])
        self.assertEqual(3, pad['X'])
        pad['X'] = 9
        self.assertEqual(9, pad.get('X'))
        document.validate()

    def test_default_value_and_optional_removal(self):
        document, pattern, _, _ = self.design()
        pattern['Value'] = 'A value'
        pattern['Datasheet'] = 'https://example.com/data'
        self.assertEqual('A value', pattern['Value'])
        del pattern['Datasheet']
        self.assertIsNone(pattern.get('Datasheet'))
        document.validate()

    def test_group_membership_follows_reordering(self):
        document, pattern, pad, _ = self.design()
        groups = pattern.one('Pattern_Groups')
        first, second = new_group(), new_group()
        groups.append(first)
        groups.append(second)
        pad['Group'] = second
        self.assertIs(second, pad['Group'])
        self.assertEqual(1, pad['GroupId'])
        second.move_to(groups, index=0)
        self.assertIs(second, pad['Group'])
        self.assertEqual(0, pad['GroupId'])
        document.validate()

    def test_drawing_pad_assignment_is_identity_based(self):
        document, pattern, first, drawing = self.design()
        second = new_pad('2')
        pattern.one('Pads').append(second)
        drawing['Pad'] = second
        second.move_to(pattern.one('Pads'), index=0)
        self.assertIs(second, drawing['Pad'])
        self.assertEqual(1, drawing['PadId'])
        document.validate()

    def test_cross_pattern_relationship_is_atomic(self):
        document, pattern, pad, drawing = self.design()
        drawing['Pad'] = pad
        another = new_pattern('Another')
        document.one('/Library/Patterns').append(another)
        other_pad = new_pad('1')
        another.one('Pads').append(other_pad)
        with self.assertRaises(ReferenceError):
            drawing['Pad'] = other_pad
        self.assertIs(pad, drawing['Pad'])
        document.validate()

    def test_referenced_pad_cannot_move_to_another_pattern(self):
        document, _, pad, drawing = self.design()
        drawing['Pad'] = pad
        another = new_pattern('Another')
        document.one('/Library/Patterns').append(another)
        original = pad.parent
        with self.assertRaises(ReferenceError):
            pad.move_to(another.one('Pads'))
        self.assertIs(original, pad.parent)
        self.assertIs(pad, drawing['Pad'])
        document.validate()

    def test_group_role_requires_a_declared_member(self):
        document, pattern, _, _ = self.design()
        group = new_group()
        pattern.one('Pattern_Groups').append(group)
        with self.assertRaises(ReferenceError):
            document.references.bind(pattern, group, role='pattern-group')
        self.assertEqual(0, len(document.references))

    def test_group_cannot_be_disabled_while_used(self):
        document, pattern, pad, _ = self.design()
        group = new_group()
        pattern.one('Pattern_Groups').append(group)
        pad['Group'] = group
        with self.assertRaises(ReferenceError):
            group['Enabled'] = False
        self.assertTrue(group['Enabled'])
        pad['Group'] = None
        group['Enabled'] = False
        document.validate()

    def test_clone_owns_independent_relationships(self):
        document, _, pad, drawing = self.design()
        drawing['Pad'] = pad
        copied = document.clone()
        copied_pad = copied.one('/Library/Patterns/Pattern/Pads/Pad')
        copied_drawing = copied.one('/Library/Patterns/Pattern/Shapes/Shape')
        self.assertIs(copied_pad, copied_drawing['Pad'])
        self.assertIsNot(pad, copied_pad)
        copied_pad['X'] = 100
        self.assertEqual(3, pad['X'])
        copied.validate()

    def test_natural_unit_view_uses_the_same_facts(self):
        document, _, pad, _ = self.design()
        view = document.in_units('mm')
        visible = view.one('/Library/Patterns/Pattern/Pads/Pad')
        self.assertEqual(1, visible['X'])
        visible['X'] = 2
        self.assertEqual(6, pad['X'])
        document.validate()


if __name__ == '__main__':
    unittest.main()
