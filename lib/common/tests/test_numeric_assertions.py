"""Conversion comparison bounds retain strict identity and structure checks."""
from decimal import Decimal
import math
import unittest

from .numeric_assertions import assert_float_facts


class NumericAssertionTests(unittest.TestCase):
    def test_scaled_float_rounding_is_allowed_within_the_stated_bound(self):
        assert_float_facts(self, {'Width': math.nextafter(.3, 1)}, {'Width': Decimal('.3')})

    def test_a_changed_wire_value_is_not_float_roundoff(self):
        with self.assertRaises(AssertionError):
            assert_float_facts(self, .3001, .3)

    def test_large_integer_identities_remain_exact(self):
        with self.assertRaises(AssertionError):
            assert_float_facts(self, float(9007199254740993), Decimal('9007199254740993'))
        with self.assertRaises(AssertionError):
            assert_float_facts(self, 9007199254740992, 9007199254740993)

    def test_optional_states_booleans_keys_and_order_remain_strict(self):
        for actual, expected in ((False, 0), (None, 0), ({'A': 0}, {'B': 0}),
                                 ([1, 2], [2, 1]), ((1, 2), [1, 2])):
            with self.subTest(actual=actual, expected=expected), self.assertRaises(AssertionError):
                assert_float_facts(self, actual, expected)

    def test_nonfinite_numbers_cannot_pass_a_projection_comparison(self):
        for value in (math.nan, math.inf, Decimal('NaN')):
            with self.subTest(value=value), self.assertRaises(AssertionError):
                assert_float_facts(self, value, .3)
            with self.subTest(value=value), self.assertRaises(AssertionError):
                assert_float_facts(self, value, value)
