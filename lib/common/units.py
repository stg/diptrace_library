"""Shared display-unit names and public XML length/axis conversion.

Schematic and PCB lengths use three units per millimetre. Public XML chooses
mm/mil/inch and reverses the two-dimensional Y axis.
Angles, font sizes, scales and enum values must not pass through length().
"""
from dataclasses import dataclass, field
from decimal import Decimal
import math

from .model import Value
from .measurements import UNIT_NAMES, SHARED_PER_UNIT, unit_name


DISPLAY_UNITS = UNIT_NAMES
_INTERNAL_SCALES = SHARED_PER_UNIT


def display_units(value):
    """Validate a display choice, accepting 'in' as an input alias for 'inch'."""
    return unit_name(value)


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
    """Return a floating area from a finite length."""
    value = float(_number(value))
    result = value*value
    if not math.isfinite(result):
        raise ValueError('area is outside finite float range')
    return result


def square_root_area(value):
    """Project a finite nonnegative area to a floating length threshold."""
    value = float(_number(value))
    if not math.isfinite(value):
        raise ValueError('area is outside finite float range')
    if value < 0:
        raise ValueError('area must not be negative')
    return math.sqrt(value)


@dataclass(frozen=True, slots=True)
class XmlUnits:
    units: str
    _scale: float = field(init=False, repr=False)

    def __post_init__(self):
        if self.units not in DISPLAY_UNITS:
            raise ValueError('XML length units must be mm, mil or inch')
        object.__setattr__(self, '_scale', _INTERNAL_SCALES[self.units])

    @property
    def internal_unit(self):
        return self._scale

    def _convert(self, value, *, to_internal=False, power=1):
        value = float(_number(value))
        factor = self._scale if power == 1 else self._scale**power
        # Divide directly: multiplying by a rounded reciprocal introduces an
        # extra rounding step and can turn an exact scale cycle into drift.
        result = value*factor if to_internal else value/factor
        if not math.isfinite(result):
            raise ValueError('unit conversion is outside finite float range')
        return result

    def length(self, value):
        """Convert the current physical length without source-dependent bias."""
        return self._convert(value)

    def area(self, value):
        """Convert a physical area with the square of the length scale."""
        return self._convert(value, power=2)

    def point(self, x, y):
        y = self.length(y)
        return self.length(x), -y

    def internal_length(self, value):
        """Normalize an XML length before the selected output's quantization."""
        return self._convert(value, to_internal=True)

    def internal_area(self, value):
        """Normalize a displayed physical area into shared square units."""
        return self._convert(value, to_internal=True, power=2)

    def internal_point(self, x, y):
        y = self.internal_length(y)
        return self.internal_length(x), -y
