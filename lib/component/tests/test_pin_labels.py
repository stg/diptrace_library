"""Pin labels are authored text; pad assignments follow physical identities."""
import unittest

from lib.common.conversion import ConversionReport
from lib.component.formats import io
from lib.component.model import new_library, new_component, new_pattern, new_pad, new_pin


class PinLabelTests(unittest.TestCase):
    def test_edits_and_all_outputs_keep_labels_independent_of_pad_selection(self):
        document = new_library('Example')
        component = document.one('/Library/Components').append(new_component('Device', 'U'))
        pattern = component.append(new_pattern('Package'))
        first = pattern.one('Pads').append(new_pad('11', x=-3))
        second = pattern.one('Pads').append(new_pad('22', x=3))
        pins = component.one('Parts/Part/Pins')
        one, two = pins.append(new_pin()), pins.append(new_pin())
        one['StringNumber'], two['StringNumber'] = '1', '2'
        one['Pad'], two['Pad'] = first, second
        one['Pad'], two['Pad'] = second, first
        second.move_to(second.parent, index=0)
        first['StringNumber'] = '33'
        self.assertEqual(('1', '2'), (one['StringNumber'], two['StringNumber']))
        for format in ('eli', 'asc', 'elixml'):
            with self.subTest(format=format):
                rebuilt = io.parse(io.serialize(document, format=format, report=ConversionReport()))
                actual = [(pin['StringNumber'], pin['PadId'], pin['Pad']['StringNumber'])
                          for pin in rebuilt.select('/Library/Components/Component/Parts/Part/Pins/Pin')]
                self.assertEqual([('1', 1, '22'), ('2', 2, '33')], actual)
                rebuilt.validate()
        clone = document.clone()
        copied = clone.one('/Library/Components/Component/Parts/Part/Pins/Pin[1]')
        copied['Pad'] = None
        self.assertEqual('1', copied['StringNumber'])
        self.assertIs(second, one['Pad'])
        self.assertEqual(('1', '2'), (one['StringNumber'], two['StringNumber']))
        document.validate()
        clone.validate()


if __name__ == '__main__':
    unittest.main()
