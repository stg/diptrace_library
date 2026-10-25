"""Physical unit conversion is shared by schematic and PCB XML adapters."""
from decimal import Decimal, localcontext
import unittest

from lib.common.units import XmlUnits, display_units, square_length


class UnitsTests(unittest.TestCase):
    def test_squared_lengths_do_not_use_ambient_rounding_or_binary_float_noise(self):
        with localcontext() as context:
            context.prec = 3
            self.assertEqual(square_length(Decimal('1.23456789')), Decimal('1.5241578750190521'))
            self.assertEqual(square_length(Decimal('-0.125')), Decimal('0.015625'))
            self.assertEqual(square_length(0.3), Decimal('0.09'))
        for invalid in (True, float('inf'), Decimal('NaN')):
            with self.subTest(invalid=invalid), self.assertRaises((TypeError, ValueError)):
                square_length(invalid)

    def test_context_aliases_have_one_current_spelling(self):
        self.assertEqual(display_units('in'), 'inch')
        for unit in ('mm', 'mil', 'inch'):
            self.assertEqual(display_units(unit), unit)
        for invalid in ('cm', '', 'MM'):
            with self.assertRaises(ValueError):
                display_units(invalid)
        with self.assertRaises(TypeError):
            display_units(None)

    def test_decimal_geometry_is_independent_of_ambient_precision(self):
        length = Decimal('12345678901234567890123456789.25')
        unit = XmlUnits('mil')
        with localcontext() as context:
            context.prec = 6
            converted = unit.internal_length(length)
            restored = unit.length(converted)
            point = unit.internal_point(length, length)
            returned = unit.point(*point)
        self.assertEqual(restored, length)
        self.assertEqual(point, (converted, converted.copy_negate()))
        self.assertEqual(returned, (length, length))

    def test_export_import_cycles_do_not_accumulate_coordinate_drift(self):
        for name in ('mm', 'mil', 'inch'):
            with self.subTest(name=name):
                unit = XmlUnits(name)
                point = Decimal('6.35'), Decimal('-7.62')
                first = unit.internal_point(*unit.point(*point))
                for actual, original in zip(first, point):
                    self.assertLess(abs(actual-original), Decimal('1e-36'))
                point = first
                for _ in range(30):
                    point = unit.internal_point(*unit.point(*point))
                self.assertEqual(point, first)


if __name__ == '__main__':
    unittest.main()
