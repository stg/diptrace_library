"""Natural length units over canonical measurements, without changing axes.

This module does not import document families, models or format adapters.
Conversion is a view operation: stored numbers and display settings stay put.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from decimal import Decimal
import math
from types import MappingProxyType


UNIT_NAMES = ('mm', 'mil', 'inch')
SHARED_PER_UNIT = MappingProxyType({'mm': 3., 'mil': .0762, 'inch': 76.2})
_default_units = ContextVar('design_length_units', default='mm')
_ABSENT = object()


def unit_name(value):
    if not isinstance(value, str):
        raise TypeError('display units must be text')
    if value == 'in':
        value = 'inch'
    if value not in UNIT_NAMES:
        raise ValueError('display units must be mm, mil or inch')
    return value


def get_default_units():
    """Length-view preference for the current execution context."""
    return _default_units.get()


def set_default_units(units):
    """Choose the default for subsequently created length views."""
    _default_units.set(unit_name(units))


@contextmanager
def using_units(units):
    """Temporarily select a preference without changing existing views/data."""
    token = _default_units.set(unit_name(units))
    try:
        yield
    finally:
        _default_units.reset(token)


def nonnegative_length(record, value):
    """Negative pen/width values are style selections, not physical lengths."""
    return 'shared length' if _number(value) >= 0 else 'inherited'


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise TypeError('length conversion requires a number')
    try:
        value = float(value)
    except OverflowError:
        raise ValueError('length conversion requires a finite number') from None
    if not math.isfinite(value):
        raise ValueError('length conversion requires a finite number')
    return value


@dataclass(frozen=True, slots=True)
class LengthUnits:
    units: str | None = None
    _scale: float = field(init=False, repr=False)

    def __post_init__(self):
        units = unit_name(get_default_units() if self.units is None else self.units)
        object.__setattr__(self, 'units', units)
        object.__setattr__(self, '_scale', SHARED_PER_UNIT[units])

    def _convert(self, value, *, to_shared=False, power=1, current=_ABSENT):
        if type(power) is not int or power not in (1, 2):
            raise ValueError('length conversion power must be 1 or 2')
        value = _number(value)
        factor = self._scale if power == 1 else self._scale*self._scale
        if to_shared and isinstance(current, (int, float, Decimal)) and not isinstance(current, bool):
            # Setting an unchanged visible value must not repeatedly round the
            # authoritative coordinate. This uses the current fact, not history.
            if value == self._convert(current, power=power):
                return current
        result = value*factor if to_shared else value/factor
        if not math.isfinite(result):
            raise ValueError('unit conversion is outside finite float range')
        return result

    def from_shared(self, value, *, power=1):
        return self._convert(value, power=power)

    def to_shared(self, value, *, power=1, current=_ABSENT):
        return self._convert(value, to_shared=True, power=power, current=current)

    def field_value(self, definition, value, *, record=None, to_shared=False, current=_ABSENT):
        """Convert declared quantities, retaining tuples, optional states and IDs."""
        if value is None:
            return None
        if definition.kind == 'tuple':
            if not isinstance(value, tuple):
                # Preserve the ordinary schema error and its field name.
                definition.validate(value)
            if definition.members:
                if len(value) != len(definition.members):
                    definition.validate(value)
                return tuple(self.field_value(member, item, record=record, to_shared=to_shared,
                                              current=current[index] if isinstance(current, tuple) and index < len(current) else _ABSENT)
                             for index, (member, item) in enumerate(zip(definition.members, value)))
            return tuple(self._field_scalar(definition, item, record=record, to_shared=to_shared,
                                            current=current[index] if isinstance(current, tuple) and index < len(current) else _ABSENT)
                         for index, item in enumerate(value))
        return self._field_scalar(definition, value, record=record, to_shared=to_shared, current=current)

    def _field_scalar(self, definition, value, *, record, to_shared, current):
        if value is None:
            return None
        unit = definition.unit_selector(record, value) if definition.unit_selector else definition.unit
        power = 1 if unit == 'shared length' else 2 if unit == 'shared length squared' else None
        if power is None or value is None:
            return value
        # An authored special selection is independent of measurement units.
        if value in definition.unit_sentinels:
            _number(value)
            if (to_shared and isinstance(current, (int, float, Decimal)) and not isinstance(current, bool)
                    and value == self._field_scalar(definition, current, record=record,
                                                    to_shared=False, current=_ABSENT)):
                # A negative physical quantity can project onto a reserved
                # choice. As with all no-op assignments, keep the current fact.
                return current
            return value
        return self._convert(value, to_shared=to_shared, power=power, current=current)
