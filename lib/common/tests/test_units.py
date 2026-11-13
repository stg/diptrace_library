"""Floating physical conversions shared by schematic and PCB adapters."""
from decimal import Decimal, ROUND_UP, ROUND_DOWN, localcontext
import math
import unittest

from lib.common.units import XmlUnits, display_units, square_length, square_root_area


class UnitsTests(unittest.TestCase):
    def assertWithinUlps(self, actual, expected, ulps=2):
        expected = float(expected)
        self.assertIs(type(actual), float)
        self.assertTrue(math.isfinite(actual))
        self.assertAlmostEqual(actual, expected, delta=ulps*math.ulp(expected))

    def test_scaled_float_values_stabilize_without_coordinate_drift(self):
        values = (1.2345678901234567, -.00015259077727923982, -4.144113664024951e21)
        for units in ('mm', 'mil', 'inch'):
            unit = XmlUnits(units)
            for value in values:
                for export, restore in ((unit.length, unit.internal_length), (unit.area, unit.internal_area)):
                    with self.subTest(units=units, value=value, conversion=export.__name__):
                        current = restore(export(value))
                        self.assertWithinUlps(current, value)
                        first = current
                        for _ in range(30):
                            current = restore(export(current))
                        self.assertEqual(current, first)

    def test_padding_and_ambient_decimal_rounding_do_not_change_float_values(self):
        unit = XmlUnits('mm')
        displayed = unit.length(10)
        padded = Decimal(str(displayed)+'0'*20)
        for rounding in (ROUND_UP, ROUND_DOWN):
            with localcontext() as context:
                context.prec, context.rounding = 2, rounding
                self.assertEqual(unit.internal_length(displayed), 10)
                self.assertEqual(unit.internal_length(padded), 10)
                self.assertEqual(unit.length(Decimal('10.000000000000000000000000')), displayed)

    def test_decimal_inputs_are_projected_once_into_the_float_domain(self):
        value = Decimal('1.2345678901234567890123456789012345678901234567')
        for name in ('mm', 'mil', 'inch'):
            unit = XmlUnits(name)
            for power, convert in ((1, unit.internal_length), (2, unit.internal_area)):
                with localcontext() as context:
                    context.prec = 100
                    expected = value*Decimal(str(unit.internal_unit))**power
                self.assertWithinUlps(convert(value), expected)

    def test_xml_areas_use_squared_scales_without_ambient_rounding(self):
        for name, scale in (('mm', '3'), ('mil', '.0762'), ('inch', '76.2')):
            with self.subTest(units=name):
                units = XmlUnits(name)
                expected = Decimal('1.23456789')*Decimal(scale)**2
                with localcontext() as context:
                    context.prec = 2
                    internal = units.internal_area(Decimal('1.23456789'))
                    self.assertWithinUlps(internal, expected)
                    self.assertWithinUlps(units.area(internal), 1.23456789)
                current = internal
                for _ in range(30):
                    current = units.internal_area(units.area(current))
                self.assertEqual(current, internal)

    def test_area_thresholds_ignore_ambient_context_and_stabilize_after_projection(self):
        with localcontext() as context:
            context.prec = 2
            self.assertEqual(square_root_area(Decimal('1.52399025')), 1.2345)
            first = square_length(square_root_area(2))
            current = first
            for _ in range(30):
                current = square_length(square_root_area(current))
            self.assertEqual(current, first)
        self.assertWithinUlps(first, 2, ulps=1)
        for invalid in (-1, True, float('inf'), Decimal('NaN')):
            with self.subTest(invalid=invalid), self.assertRaises((TypeError, ValueError)):
                square_root_area(invalid)

    def test_squared_lengths_ignore_ambient_rounding_with_bounded_float_error(self):
        with localcontext() as context:
            context.prec = 3
            self.assertWithinUlps(square_length(Decimal('1.23456789')), 1.524157875019052, ulps=1)
            self.assertEqual(square_length(Decimal('-0.125')), .015625)
            self.assertEqual(square_length(.3), .09)
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

    def test_large_geometry_and_axis_conversion_ignore_ambient_precision(self):
        length = Decimal('12345678901234567890123456789.25')
        unit = XmlUnits('mil')
        with localcontext() as context:
            context.prec = 6
            converted = unit.internal_length(length)
            restored = unit.length(converted)
            point = unit.internal_point(length, length)
            returned = unit.point(*point)
        self.assertWithinUlps(restored, length)
        self.assertEqual(point, (converted, -converted))
        for actual in returned:
            self.assertWithinUlps(actual, length)

    def test_export_import_cycles_preserve_the_binary_grid(self):
        from lib.common.binary import _number_units
        for name in ('mm', 'mil', 'inch'):
            with self.subTest(name=name):
                unit = XmlUnits(name)
                original = 6.35, -7.62
                first = unit.internal_point(*unit.point(*original))
                for actual, expected in zip(first, original):
                    self.assertWithinUlps(actual, expected)
                point = first
                for _ in range(30):
                    point = unit.internal_point(*unit.point(*point))
                self.assertEqual(point, first)
                self.assertEqual(tuple(_number_units(value, 'binary') for value in point),
                                 tuple(_number_units(value, 'binary') for value in original))

    def test_overflow_does_not_create_nonfinite_geometry(self):
        for convert in (XmlUnits('mm').internal_length, square_length, square_root_area):
            with self.subTest(convert=convert.__name__), self.assertRaises(ValueError):
                convert(Decimal('1e999'))


if __name__ == '__main__':
    unittest.main()
