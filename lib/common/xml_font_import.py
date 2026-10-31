"""Read current XML font facts and consume redundant calculated extents."""
from decimal import Decimal, ROUND_HALF_EVEN

from .model import Value
from .xml_records import length


def read_width(record, *, units, physical, name='FontWidth', default=-1):
    """Resolve physical strokes and earlier discrete negative conventions."""
    width = record.number(name, default)
    value = width.value
    if value >= 0:
        return length(width, units) if physical else width
    if physical or value in (-1, -2, -3):
        return width
    scaled = length(width, units).value
    return Value(min(Decimal(-1), max(Decimal(-3), scaled)).to_integral_value(rounding=ROUND_HALF_EVEN), 'number')


def read_size(record, legacy='FontSize', default=6, *, floating='FontSizeFloat'):
    size = record.number(legacy, default)
    return record.number(floating) if record.has(floating) else size


def read_font(record, target, *, prefix='', size='FontSize', legacy='FontSize',
              floating='FontSizeFloat', default=6, mono='FontMono'):
    target.set_field(size, read_size(record, legacy, default, floating=floating))
    if mono:
        target.set_field(prefix+mono, record.boolean('FontMono', False))


def read_text_extent(record):
    for name in ('TextWidth', 'TextHeight'):
        if record.has(name):
            record.number(name)
