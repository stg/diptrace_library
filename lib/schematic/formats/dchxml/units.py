"""Length/axis conversion between shared schematic data and public DCHXML.

Shared DCH schematic and embedded footprint lengths both use three units per
millimetre. XML chooses mm/mil/inch and reverses the two-dimensional Y axis.
Angles, font sizes, scales and enum values must not pass through length().
"""
from dataclasses import dataclass
from decimal import Decimal, localcontext
import math

from ....common.model import (Value)


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


@dataclass(frozen=True)
class DchXmlUnits:
    units: str

    def __post_init__(self):
        if self.units not in ('mm', 'mil', 'inch'):
            raise ValueError('DCHXML length units must be mm, mil or inch')

    @property
    def internal_unit(self):
        return {'mm': 3., 'mil': .0762, 'inch': 76.2}[self.units]

    def _convert(self, value, *, to_internal=False):
        value = _number(value)
        if isinstance(value, float):
            return value*self.internal_unit if to_internal else value*(1./self.internal_unit)
        value = Decimal(value)
        factor = Decimal(str(self.internal_unit))
        with localcontext() as context:
            context.prec = max(40, len(value.as_tuple().digits)+16)
            return value*factor if to_internal else value/factor

    def length(self, value):
        """Convert the current physical length without source-dependent bias."""
        return self._convert(value)

    def point(self, x, y):
        return self.length(x), -self.length(y)

    def internal_length(self, value):
        """Normalize an XML length before the selected output's quantization."""
        return self._convert(value, to_internal=True)

    def internal_point(self, x, y):
        return self.internal_length(x), -self.internal_length(y)
