"""Component pins, physical pads and local groups retain identities while editing."""
import unittest

from lib.common.references import ReferenceError
from lib.component.model import (new_library, new_component, new_part, new_pattern,
    new_pad, new_pin, new_group, new_drawing, new_pattern_drawing)
from lib.component.model import symbols


class RelationshipTests(unittest.TestCase):
    def make_document(self):
        document = new_library()
        component = document.one('/Library/Components').append(new_component('Example', 'U'))
        first = component.one('Parts/Part')
        second = component.one('Parts').append(new_part('Gate B'))
        pattern = component.append(new_pattern('Example footprint'))
        pads = [pattern.one('Pads').append(new_pad(number)) for number in ('A', 'B')]
        return document, component, first, second, pattern, pads

    def test_pin_pad_identity_survives_reordering_and_clone(self):
        document, _, first, _, pattern, pads = self.make_document()
        pin = first.one('Pins').append(new_pin())
        pin['Pad'] = pads[1]
        self.assertEqual((2, 2), (pin['PadId'], pin['Number']))
        pads[0].move_to(pattern.one('Pads'))
        self.assertIs(pads[1], pin['Pad'])
        self.assertEqual((1, 1), (pin['PadId'], pin['Number']))
        clone = document.clone()
        copied_pin = clone.one('/Library/Components/Component/Parts/Part[1]/Pins/Pin')
        copied_pad = clone.select('/Library/Components/Component/Pattern/Pads/Pad')[0]
        self.assertIs(copied_pad, copied_pin['Pad'])
        self.assertIsNot(pads[1], copied_pad)
        document.validate()
        clone.validate()

    def test_label_orientation_choices_are_integral_and_unit_independent(self):
        document, _, first, _, _, _ = self.make_document()
        pin = first.one('Pins').append(new_pin())
        for name in ('PinNumRotate', 'PinNameRotate'):
            pin[name] = 1
            with self.assertRaises(TypeError):
                pin[name] = .5
            self.assertEqual(1, pin[name])
            self.assertEqual(1, document.in_units('mm').one(
                '/Library/Components/Component/Parts/Part[1]/Pins/Pin')[name])
        document.validate()

    def test_parts_share_the_physical_pad_scope_and_reject_a_foreign_component(self):
        document, _, first, second, _, pads = self.make_document()
        pins = [part.one('Pins').append(new_pin()) for part in (first, second)]
        for pin in pins:
            pin['Pad'] = pads[0]
        other = document.one('/Library/Components').append(new_component('Other', 'R'))
        foreign_pad = other.append(new_pattern()).one('Pads').append(new_pad('1'))
        with self.assertRaises(ReferenceError):
            pins[1]['Pad'] = foreign_pad
        self.assertIs(pads[0], pins[1]['Pad'])
        with self.assertRaises(ReferenceError):
            second.move_to(other.one('Parts'))
        self.assertIs(first.parent, second.parent)
        document.validate()

    def test_symbol_group_scope_is_per_part_and_disable_requires_unassignment(self):
        document, _, first, second, pattern, _ = self.make_document()
        group = first.one('Groups').append(new_group())
        foreign_group = second.one('Groups').append(new_group())
        physical_group = pattern.one('Pattern_Groups').append(new_group())
        pin = first.one('Pins').append(new_pin())
        drawing = first.one('Shapes').append(new_drawing())
        pin['Group'] = group
        drawing['Group'] = group
        for target in (foreign_group, physical_group):
            with self.subTest(target=target.path), self.assertRaises(ReferenceError):
                pin['Group'] = target
        with self.assertRaises(ReferenceError):
            group['Enabled'] = False
        pin['Group'] = None
        drawing['Group'] = None
        group['Enabled'] = False
        document.validate()

    def test_physical_drawing_uses_the_same_owned_pad_records(self):
        document, _, first, _, pattern, pads = self.make_document()
        drawing = pattern.one('Shapes').append(new_pattern_drawing())
        group = pattern.one('Pattern_Groups').append(new_group())
        drawing['Pad'] = pads[1]
        drawing['Group'] = group
        pin = first.one('Pins').append(new_pin())
        pin['Pad'] = drawing['Pad']
        pads[1].move_to(pattern.one('Pads'), index=0)
        self.assertEqual((1, 1), (drawing['PadId'], pin['PadId']))
        self.assertIs(drawing['Pad'], pin['Pad'])
        document.validate()

    def test_unavailable_pad_can_be_resolved_without_rebuilding(self):
        document, _, first, _, pattern, pads = self.make_document()
        pin = first.one('Pins').append(new_pin())
        pin.add('UnresolvedPadId', 99)
        document.references.note(pin, symbols.PAD_ROLE+': unavailable key 99',
                                 collections=(pattern.one('Pads'),))
        self.assertEqual(99, pin['PadId'])
        with self.assertRaises(ReferenceError):
            pin['Pad']
        pin['Pad'] = pads[0]
        self.assertEqual([], document.references.issues)
        self.assertIsNone(pin.child('UnresolvedPadId'))
        self.assertEqual(1, pin['Number'])
        document.validate()


if __name__ == '__main__':
    unittest.main()
