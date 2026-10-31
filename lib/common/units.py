"""Shared display-unit names and public XML length/axis conversion.

Schematic and PCB lengths use three units per millimetre. Public XML chooses
mm/mil/inch and reverses the two-dimensional Y axis.
Angles, font sizes, scales and enum values must not pass through length().
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
import math

from .model import Value


DISPLAY_UNITS = ('mm', 'mil', 'inch')
_XML_PRECISION = 40
_XML_GUARD_DIGITS = 16


def _significant_digits(value):
    """Count the numeric precision without treating trailing zeros as data."""
    digits = value.as_tuple().digits
    size = len(digits)
    while size > 1 and not digits[size-1]:
        size -= 1
    return size


def display_units(value):
    """Validate a display choice, accepting 'in' as an input alias for 'inch'."""
    if not isinstance(value, str):
        raise TypeError('display units must be text')
    if value == 'in':
        value = 'inch'
    if value not in DISPLAY_UNITS:
        raise ValueError('display units must be mm, mil or inch')
    return value


def _number(value):
    if isinstance(value, Value):
        if value.kind != 'number' or value.unit:
            raise ValueError('unit conversion requires an unqualified number')
        value = value.value
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise TypeError('unit conversion requires a number')
    if isinstance(value, Decimal):
        finite = value.is_finite()
    else:
        finite = math.isfinite(value)
    if not finite:
        raise ValueError('unit conversion requires a finite number')
    return value


def square_length(value):
    """Return an exact decimal area from a finite length, without context drift."""
    value = _number(value)
    value = value if isinstance(value, Decimal) else Decimal(str(value))
    with localcontext() as context:
        context.prec = max(1, 2 * len(value.as_tuple().digits))
        return value * value


def square_root_area(value):
    """Project a nonnegative area to a stable decimal length threshold.

    A fixed 34 significant digits covers the square of a binary double's
    precision and prevents ambient context or repeated conversions causing drift.
    Irrational roots necessarily approximate; exact squares remain exact within
    that precision.
    """
    value = _number(value)
    value = value if isinstance(value, Decimal) else Decimal(str(value))
    if value < 0:
        raise ValueError('area must not be negative')
    with localcontext() as context:
        context.prec = 34
        return value.sqrt()


@dataclass(frozen=True)
class XmlUnits:
    units: str

    def __post_init__(self):
        if self.units not in DISPLAY_UNITS:
            raise ValueError('XML length units must be mm, mil or inch')

    @property
    def internal_unit(self):
        return {'mm': 3., 'mil': .0762, 'inch': 76.2}[self.units]

    def _convert(self, value, *, to_internal=False, power=1):
        value = _number(value)
        if isinstance(value, float):
            factor = self.internal_unit
            if power != 1:
                factor = factor**power
            return value*factor if to_internal else value*(1./factor)
        value = Decimal(value)
        factor = Decimal(str(self.internal_unit))
        with localcontext() as context:
            context.prec = max(_XML_PRECISION, _significant_digits(value)+_XML_GUARD_DIGITS)
            context.rounding = ROUND_HALF_EVEN
            if power != 1:
                factor = factor**power
            result = value*factor if to_internal else value/factor
        if to_internal:
            # Division can introduce guard-digit tails, such as 10/3. Recover
            # a scaled value only when our forward conversion reproduces the
            # incoming number exactly. Other authored digits remain intact.
            start = max(_XML_PRECISION, _significant_digits(value))-_XML_GUARD_DIGITS
            for digits in range(start, _significant_digits(result)):
                with localcontext() as context:
                    context.prec = digits
                    context.rounding = ROUND_HALF_EVEN
                    candidate = +result
                if self._convert(candidate, power=power) == value:
                    return candidate
        return result

    def length(self, value):
        """Convert the current physical length without source-dependent bias."""
        return self._convert(value)

    def area(self, value):
        """Convert a physical area with the square of the length scale."""
        return self._convert(value, power=2)

    def point(self, x, y):
        y = self.length(y)
        return self.length(x), y.copy_negate() if isinstance(y, Decimal) else -y

    def internal_length(self, value):
        """Normalize an XML length before the selected output's quantization."""
        return self._convert(value, to_internal=True)

    def internal_area(self, value):
        """Normalize a displayed physical area into shared square units."""
        return self._convert(value, to_internal=True, power=2)

    def internal_point(self, x, y):
        y = self.internal_length(y)
        return self.internal_length(x), y.copy_negate() if isinstance(y, Decimal) else -y
