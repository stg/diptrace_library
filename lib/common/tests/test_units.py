"""Physical unit conversion is shared by schematic and PCB XML adapters."""
from decimal import Decimal, ROUND_UP, ROUND_DOWN, localcontext
import unittest

from lib.common.units import XmlUnits, display_units, square_length, square_root_area


class UnitsTests(unittest.TestCase):
    def test_high_precision_scaled_values_round_trip_without_losing_authored_digits(self):
        values = (Decimal('1.234567890123456789012345678901234567891'),
                  Decimal('-0.000152590777279239822398150923265146842486189593434'),
                  Decimal('-4144113664024951301709.914103731155542056615066071043853302124947751251854638'))
        for units in ('mm', 'mil', 'inch'):
            unit = XmlUnits(units)
            for value in values:
                for export, restore in ((unit.length, unit.internal_length), (unit.area, unit.internal_area)):
                    with self.subTest(units=units, value=value, conversion=export.__name__):
                        current = value
                        for _ in range(5):
                            current = restore(export(current))
                            self.assertEqual(current, value)

    def test_recovering_guard_digits_ignores_padding_and_ambient_rounding(self):
        unit = XmlUnits('mm')
        displayed = unit.length(Decimal(10))
        parts = displayed.as_tuple()
        padded = Decimal((parts.sign, parts.digits+(0,)*20, parts.exponent-20))
        for rounding in (ROUND_UP, ROUND_DOWN):
            with localcontext() as context:
                context.prec, context.rounding = 2, rounding
                self.assertEqual(unit.internal_length(displayed), 10)
                self.assertEqual(unit.internal_length(padded), 10)
                self.assertEqual(unit.length(Decimal('10.000000000000000000000000')), displayed)

    def test_finite_xml_values_require_the_full_forward_match_before_shortening(self):
        value = Decimal('1.2345678901234567890123456789012345678901234567')
        for name in ('mm', 'mil', 'inch'):
            unit = XmlUnits(name)
            for power, convert in ((1, unit.internal_length), (2, unit.internal_area)):
                with localcontext() as context:
                    context.prec = 100
                    expected = value*Decimal(str(unit.internal_unit))**power
                self.assertEqual(convert(value), expected)

    def test_xml_areas_use_squared_scales_without_ambient_rounding(self):
        for name, scale in (('mm', '3'), ('mil', '.0762'), ('inch', '76.2')):
            with self.subTest(units=name):
                units = XmlUnits(name)
                expected = Decimal('1.23456789')*Decimal(scale)**2
                with localcontext() as context:
                    context.prec = 2
                    internal = units.internal_area(Decimal('1.23456789'))
                    self.assertEqual(internal, expected)
                    self.assertEqual(units.area(internal), Decimal('1.23456789'))
                current = internal
                for _ in range(30):
                    current = units.internal_area(units.area(current))
                self.assertEqual(current, internal)

    def test_area_thresholds_ignore_ambient_context_and_stabilize_after_projection(self):
        with localcontext() as context:
            context.prec = 2
            self.assertEqual(square_root_area(Decimal('1.52399025')), Decimal('1.2345'))
            first = square_length(square_root_area(2))
            current = first
            for _ in range(30):
                current = square_length(square_root_area(current))
            self.assertEqual(current, first)
        self.assertLess(abs(first-2), Decimal('1e-32'))
        for invalid in (-1, True, float('inf'), Decimal('NaN')):
            with self.subTest(invalid=invalid), self.assertRaises((TypeError, ValueError)):
                square_root_area(invalid)

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
