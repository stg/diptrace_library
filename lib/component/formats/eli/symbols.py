"""Standalone pin and symbol-drawing rows using shared named physical facts."""
from ....common.drawing_codec import read_text_properties
from ....common.symbol_codec import PIN_FONT, read_pin_parameters
from ....common.symbol_geometry import expand_legacy_drawing


def read_pins(reader, part):
    version = reader.header.version
    pins = reader.add(part, 'Pins')
    for index in range(reader.count('symbol pins')):
        pin = reader.add(pins, 'Pin', index)
        read_pin_parameters(reader, pin, index)
        for name in ('PinNumRotate', 'PinNameRotate'):
            if version >= 28:
                reader.field_into(pin, name, 'integer')
            else:
                reader.add_into(pin, name, 0)
        reader.field_into(pin, 'ElectricType', 'integer')
        reader.field_into(pin, 'Locked', 'boolean')
        reader.field_into(pin, 'ModelSig', 'text')
        reader.fields(pin, PIN_FONT)
        if version >= 25:
            reader.field_into(pin, 'SignalDelay', 'number')
        else:
            reader.add_into(pin, 'SignalDelay', 0)
        if version >= 27:
            reader.field_into(pin, 'Group', 'integer')
        else:
            reader.add_into(pin, 'Group', -1)
        if version >= 33:
            reader.field_into(pin, 'NameFontMono', 'boolean')
            reader.field_into(pin, 'NameFontSize', 'number', replace=True)
        else:
            reader.add_into(pin, 'NameFontMono', False)
    return pins


def read_symbol_graphics(reader, part):
    version = reader.header.version
    shapes = reader.add(part, 'Shapes')
    for index in range(reader.count('symbol drawings')):
        shape = reader.add(shapes, 'Shape', index)
        reader.field_into(shape, 'Enabled', 'boolean')
        orientation = reader.integer() if version < 27 else 0
        reader.fields(shape, ((name, 'integer') for name in ('Type', 'FontSize')))
        reader.field_into(shape, 'FontColor', 'color')
        reader.field_into(shape, 'FontType', 'integer')
        reader.field_into(shape, 'FontName', 'text')
        if version < 27:
            reader.add_into(reader.add(shape, 'TextLine'), 'pt', reader.argument('text'))
        reader.field_into(shape, 'PenWidth', 'number')
        points = reader.add(shape, 'Points' if version < 27 else 'Points_New')
        reader.points(points, reader.count('symbol drawing points'))
        reader.fields(shape, ((name, 'boolean') for name in ('Locked', 'VectorFont')))
        reader.fields(shape, ((name, 'number') for name in ('FontWidth', 'FontScale')))
        if version >= 27:
            read_text_properties(reader, shape)
            reader.field_into(shape, 'Group', 'integer')
        else:
            expand_legacy_drawing(shape, orientation=orientation)
            reader.add_into(shape, 'Group', -1)
        if version >= 33:
            reader.field_into(shape, 'FontMono', 'boolean')
            reader.field_into(shape, 'FontSize', 'number', replace=True)
        else:
            reader.add_into(shape, 'FontMono', False)
        reader.add_into(shape, 'ShowPart', False)
        reader.add_into(shape, 'MarkingGenerated', False)
    return shapes
