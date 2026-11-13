"""Numeric calculations and explicit serialization-boundary operations."""
from decimal import Decimal
import math


def calculation_number(node, index=0):
    """Read the current numeric value for a floating-point calculation."""
    return float(node.arguments[index].value)


def same_number(first, second):
    """Compare float facts with decimal inputs in their floating domain.

    Integral identities keep Python's exact integer comparisons. This neither
    applies a geometric tolerance nor compares distinct neighboring floats as
    equal.
    """
    if isinstance(first, float) and isinstance(second, Decimal):
        second = float(second)
    elif isinstance(second, float) and isinstance(first, Decimal):
        first = float(first)
    return first == second


def decimal_scale(value, places):
    """Shift a serialized decimal scale without an intermediate rounding tie.

    This is boundary arithmetic, not the storage representation. For floats,
    their shortest decimal spelling supplies the intended serialized value.
    """
    number = value if isinstance(value, Decimal) else Decimal(str(value))
    if not number.is_finite():
        return number
    sign, digits, exponent = number.as_tuple()
    return Decimal((sign, digits, exponent+places))


def fixed_number_text(value):
    """Spell a finite number without exponent notation or lost float digits."""
    if type(value) is int:
        return str(value)
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError('numbers must be finite')
        return format(value, 'f')
    if not isinstance(value, float):
        raise TypeError('numeric text requires a number')
    if not math.isfinite(value):
        raise ValueError('numbers must be finite')
    text = repr(value)
    if 'e' not in text:
        return text
    mantissa, exponent = text.split('e')
    sign = '-' if mantissa.startswith('-') else ''
    whole, dot, fraction = mantissa.lstrip('-').partition('.')
    digits = whole+fraction
    position = len(whole)+int(exponent)
    if position <= 0:
        return sign+'0.'+'0'*(-position)+digits
    if position >= len(digits):
        return sign+digits+'0'*(position-len(digits))
    return sign+digits[:position]+'.'+digits[position:]
