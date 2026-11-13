"""Compare conversion facts with explicit float rounding bounds.

Keys, ordering, strings, optional states, booleans and integral identities stay
exact. Four float steps cover input rounding plus the two physical scale
operations in these conversion fixtures. Geometry tests with additional
arithmetic can supply their own independently justified absolute error budget.
This helper never normalizes model data or changes production comparisons.
"""
from collections.abc import Mapping
from decimal import Decimal
import math


def assert_float_facts(case, actual, expected, message=None, *, ulps=4, absolute=0.0):
    if isinstance(actual, Mapping) and isinstance(expected, Mapping):
        case.assertEqual(actual.keys(), expected.keys(), message)
        for name in expected:
            assert_float_facts(case, actual[name], expected[name], str(name), ulps=ulps, absolute=absolute)
        return
    if isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
        case.assertIs(type(actual), type(expected), message)
        case.assertEqual(len(actual), len(expected), message)
        for index, (first, second) in enumerate(zip(actual, expected)):
            assert_float_facts(case, first, second, f'{message or "value"}[{index}]',
                               ulps=ulps, absolute=absolute)
        return
    if isinstance(actual, bool) or isinstance(expected, bool):
        case.assertIs(type(actual), type(expected), message)
        case.assertEqual(actual, expected, message)
        return
    for value in (actual, expected):
        if isinstance(value, float):
            case.assertTrue(math.isfinite(value), message)
        elif isinstance(value, Decimal):
            case.assertTrue(value.is_finite(), message)
    if actual == expected:
        return
    numeric = (int, float, Decimal)
    if isinstance(actual, numeric) and isinstance(expected, numeric):
        case.assertTrue((not isinstance(actual, (float, Decimal)) or math.isfinite(actual))
                        and (not isinstance(expected, (float, Decimal)) or math.isfinite(expected)), message)
        # A rounded large ID must never compare equal to a neighboring integer.
        if actual == int(actual) and expected == int(expected):
            case.assertEqual(actual, expected, message)
            return
        first, second = float(actual), float(expected)
        case.assertTrue(math.isfinite(first) and math.isfinite(second), message)
        case.assertAlmostEqual(first, second, delta=max(absolute, ulps*max(math.ulp(first), math.ulp(second))),
                               msg=message)
        return
    case.assertEqual(actual, expected, message)
