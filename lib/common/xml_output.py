"""Small typed XML projections shared by document-family adapters."""
from .model import Value
from .xml import set_attribute


def enum_text(value, labels, *, negative=None):
    number = Value.of(value)
    if number.kind != 'number' or number.unit or number.value != int(number.value):
        raise ValueError('XML enum projection requires an integer')
    value = int(number.value)
    if value < 0 and negative is not None:
        return negative
    return labels[value] if 0 <= value < len(labels) else str(value)


def numeric(value):
    if isinstance(value, Value):
        if value.kind != 'number' or value.unit:
            raise ValueError('XML numeric projection requires an unqualified number')
        value = value.value
    result = Value.of(value)
    if result.kind != 'number' or result.unit:
        raise ValueError('XML numeric projection requires a number')
    return result


def field(parent, name, value):
    if (value.value if isinstance(value, Value) else value) == '':
        return parent.add(name)
    return parent.add(name, value)


def number(parent, name, value):
    return field(parent, name, numeric(value))


def length(parent, name, value, units):
    return number(parent, name, units.length(value))


def stroke_width(value, units):
    current = numeric(value)
    return current if current.value < 0 else numeric(units.length(current))


def point_attributes(target, x, y, units, names=('X', 'Y')):
    for name, value in zip(names, units.point(x, y)):
        set_attribute(target, name, numeric(value))
