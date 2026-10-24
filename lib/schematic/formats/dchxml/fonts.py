"""Public XML font compatibility fields over one canonical model size."""
from .syntax import (set_attribute)
from ...model.fonts import (compatibility_size)


def read_size(record, legacy='FontSize', default=6, *, floating='FontSizeFloat'):
    size = record.number(legacy, default)
    return record.number(floating) if record.has(floating) else size


def read_font(record, target, *, prefix='', size='FontSize', legacy='FontSize',
              floating='FontSizeFloat', default=6, mono='FontMono'):
    target.set_field(size, read_size(record, legacy, default, floating=floating))
    if mono:
        target.set_field(prefix+mono, record.boolean('FontMono', False))


def project_size(source, target, *, size='FontSize', legacy='FontSize',
                 floating='FontSizeFloat', mono='FontMono', version=46, attribute=True):
    emit = set_attribute if attribute else lambda parent, name, value: parent.set_field(name, value)
    value = source.scalar(size)
    # An equal Decimal can retain a fractional spelling in an existing Value.
    # This generated compatibility field must have integer syntax for readers
    # that use an integer parser, even when its numerical value is unchanged.
    previous = target.child(legacy)
    if previous is not None:
        previous.set_values()
    emit(target, legacy, compatibility_size(value))
    if version >= 52:
        emit(target, floating, value)
        if mono:
            emit(target, 'FontMono', source.scalar(mono, False))


def read_text_extent(record):
    """Consume optional calculated text extents; layout uses current font facts."""
    for name in ('TextWidth', 'TextHeight'):
        if record.has(name):
            record.number(name)
