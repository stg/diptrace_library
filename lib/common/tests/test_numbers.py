"""Storage-independent numeric boundary behavior."""
from decimal import Decimal, localcontext
import math
import unittest

from lib.common.numbers import decimal_scale, fixed_number_text, same_number


class NumberTextTests(unittest.TestCase):
    def test_float_text_retains_the_float_without_exponent_notation(self):
        for value in (1.2345678901234567, 1e-7, -1e-100, 5e-324, 1e100,
                      math.nextafter(0.1, 1.0), -0.0, 0.0, 1.0):
            with self.subTest(value=value):
                text = fixed_number_text(value)
                self.assertNotIn('e', text.lower())
                self.assertEqual(float(text).hex(), value.hex())

    def test_decimal_and_integer_spelling_is_unchanged(self):
        for value, expected in ((12345678901234567890, '12345678901234567890'),
                                (Decimal('1.2300'), '1.2300'),
                                (Decimal('1e-8'), '0.00000001')):
            self.assertEqual(fixed_number_text(value), expected)

    def test_nonfinite_and_nonnumeric_values_are_rejected(self):
        for value in (math.inf, math.nan, Decimal('NaN'), Decimal('Infinity')):
            with self.assertRaises(ValueError):
                fixed_number_text(value)
        for value in (True, None, '1'):
            with self.assertRaises(TypeError):
                fixed_number_text(value)

    def test_scalar_text_writers_do_not_round_float_payloads_to_six_places(self):
        from lib.common.asc import _value
        from lib.common.model import Value
        from lib.common.xml import _text
        number = Value(1.2345678901234567, 'number')
        self.assertEqual(_value(number, False), '1.2345678901234567')
        self.assertEqual(_text(number), '1.2345678901234567')


class DecimalBoundaryTests(unittest.TestCase):
    def test_public_validation_audits_actual_tuple_payloads_with_warm_views(self):
        from lib.common.model import Document, Element
        from lib.common.schema import Field, Record
        document = Document()
        row = document.root.append(Element('Row').bind_schema(
            Record('Row', {'Values': Field('Values', 'tuple')})))
        row['Values'] = (1, .1, 'value', None)
        row.one('Values')
        document.validate()
        slot = row._content.storage.layout.slots['Values']
        for bad in ((float('nan'),), ([],), (Decimal('1e999'),)):
            with self.subTest(bad=bad):
                row._content.storage._values[slot] = bad
                with self.assertRaises((ValueError, TypeError)):
                    document.validate()
        row._content.storage._values[slot] = (1, .1, 'value', None)
        document.validate()

    def test_out_of_range_numeric_edits_fail_before_creating_optional_fields(self):
        from lib.common.model import Document, Element
        from lib.common.schema import Field, Record
        schema = Record('Row', {'Size': Field('Size', 'number'), 'Values': Field('Values', 'tuple')})
        document = Document()
        row = document.root.append(Element('Row').bind_schema(schema))
        for name, values in (('Size', (Decimal('1e999'),)), ('Values', (Decimal('1e999'),))):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    row.add(name, *values)
                self.assertNotIn(name, row)
                document.validate()

    def test_numeric_comparison_does_not_use_a_tolerance_or_round_integer_ids(self):
        self.assertTrue(same_number(.1, Decimal('.1')))
        self.assertFalse(same_number(.1, math.nextafter(.1, 1)))
        self.assertTrue(same_number(9007199254740993, Decimal('9007199254740993')))
        self.assertFalse(same_number(9007199254740992, Decimal('9007199254740993')))

    def test_wire_representability_is_strict_in_the_float_domain(self):
        from lib.common.binary import number_is_representable
        self.assertTrue(number_is_representable(.1))
        self.assertTrue(number_is_representable(Decimal('.1')))
        self.assertFalse(number_is_representable(math.nextafter(.1, 1)))
        self.assertFalse(number_is_representable(Decimal('.10000001')))

    def test_percent_scaling_avoids_a_float_division_halfway_error(self):
        from lib.common.binary import _number_units
        self.assertEqual(decimal_scale(1.055, -2), Decimal('.01055'))
        self.assertEqual(_number_units(decimal_scale(1.055, -2), 'binary'), 106)

    def test_scale_is_independent_of_ambient_decimal_precision(self):
        with localcontext() as context:
            context.prec = 2
            self.assertEqual(decimal_scale(Decimal('12345.6789'), -2), Decimal('123.456789'))
            self.assertEqual(decimal_scale(.123456789, 2), Decimal('12.3456789'))
