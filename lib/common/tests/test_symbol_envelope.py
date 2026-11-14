"""Pin selection bounds use current geometry and independently supplied metrics."""
import unittest

from lib.common.symbol_objects import new_pin
from lib.common.symbol_envelope import pin_bounds
from lib.common.text.vector import TextMetrics
from lib.common.text.vector_layout import pin_name_metrics


class SymbolEnvelopeTests(unittest.TestCase):
    def test_hidden_name_leaves_the_pin_connection_line(self):
        pin = new_pin()
        pin['X'], pin['Y'], pin['Length'], pin['ShowName'] = 10, 20, 12, False
        expected = ((-2, 20, 10, 20), (10, 8, 10, 20), (10, 20, 22, 20), (10, 20, 10, 32))
        for orientation, box in enumerate(expected):
            pin['Orientation'] = orientation
            result = pin_bounds(pin)
            self.assertEqual(box, (result.left, result.top, result.right, result.bottom))

    def test_named_pin_shift_and_alternate_orientation_keep_the_start_corner(self):
        pin = new_pin()
        pin['Length'], pin['Name'], pin['ShowName'] = 12, 'Signal', True
        measure = lambda _: TextMetrics(10, 3)
        for orientation, expected in enumerate(((-12, -1.5, 13, 1.5), (-1.5, -12, 1.5, 13),
                                                  (-13, -1.5, 12, 1.5), (-1.5, -13, 1.5, 12))):
            pin['Orientation'] = orientation
            box = pin_bounds(pin, measure_name=measure)
            self.assertEqual(expected, (box.left, box.top, box.right, box.bottom))
        pin['Orientation'], pin['PinNameRotate'] = 0, 1
        pin['PinNameXShift'], pin['PinNameYShift'] = 2, -3
        box = pin_bounds(pin, measure_name=measure)
        self.assertEqual((-12, -14.5, 8, 0), (box.left, box.top, box.right, box.bottom))
        self.assertEqual(('Signal', 12, 1), (pin['Name'], pin['Length'], pin['PinNameRotate']))

    def test_symbol_reach_and_name_clearance_are_separate_geometry(self):
        pin = new_pin()
        pin['Length'], pin['Type'], pin['ShowName'] = 12, 10, False  # Amplifier
        self.assertEqual(4, pin_bounds(pin).right)
        pin['ShowName'] = True
        self.assertEqual(16.5, pin_bounds(pin, measure_name=lambda _: TextMetrics(10, 3)).right)

    def test_name_metrics_respect_scale_and_monospacing_without_editing_the_pin(self):
        pin = new_pin()
        pin['Name'] = 'Wi'
        before = tuple((child.kind, child.values) for child in pin.children())
        proportional = pin_name_metrics(pin)
        pin['NameFontMono'] = True
        mono = pin_name_metrics(pin)
        self.assertNotEqual(proportional.width, mono.width)
        pin['NameFontScale'] = 2
        self.assertGreater(pin_name_metrics(pin).width, mono.width)
        pin['NameFontMono'], pin['NameFontScale'] = False, 1
        self.assertEqual(before, tuple((child.kind, child.values) for child in pin.children()))
