"""Symbol pins and drawings stored in shared library definitions."""
from .model import SourceSpan
from .drawing_codec import read_angle, read_groups, read_text_properties


PIN_FONT = (('NameFontSize', 'integer'), ('NameFontWidth', 'number'), ('NameFontScale', 'number'))


def read_cached_pins(reader, part):
    pins = part.add('Pins')
    for index in range(reader.count('cached symbol pins')):
        start = reader.pos
        pin = pins.add('Pin', index)
        reader.field(pin, 'Enabled', 'boolean')
        reader.fields(pin, ((name, 'integer') for name in ('Type', 'Orientation', 'Number')))
        pin.set_values(index, reader.argument('number'), reader.argument('number'))
        reader.field(pin, 'Length', 'number')
        reader.fields(pin, ((name, 'text') for name in ('Name', 'StringNumber')))
        reader.field(pin, 'ShowName', 'boolean')
        reader.fields(pin, ((name, 'number') for name in
                            ('PinNumXShift', 'PinNumYShift', 'PinNameXShift', 'PinNameYShift')))
        reader.field(pin, 'ElectricType', 'integer')
        reader.field(pin, 'Locked', 'boolean')
        reader.field(pin, 'ModelSig', 'text')
        reader.fields(pin, PIN_FONT)
        pin.source = SourceSpan(reader.source_format, start, reader.pos, reader.source)
    return pins


def read_cached_drawings(reader, part, *, physical_points):
    shapes = part.add('Shapes')
    for index in range(part.annotations['declared_shape_count']):
        start = reader.pos
        shape = shapes.add('Shape', index)
        shape.add('ShowPart', False).annotations['default_for_version'] = reader.header.version
        reader.field(shape, 'Enabled', 'boolean')
        reader.fields(shape, ((name, 'integer') for name in ('Orientation', 'Type', 'FontSize')))
        reader.field(shape, 'FontColor', 'color')
        reader.field(shape, 'FontType', 'integer')
        reader.field(shape, 'FontName', 'text')
        reader.field(shape, 'Name', 'text')
        shape.add('TextLine').add('pt', shape.one('Name').arguments[0])
        reader.field(shape, 'PenWidth', 'number')
        points = shape.add('Points_New' if physical_points else 'Points')
        for _ in range(reader.count('cached symbol drawing points')):
            reader.record(points, 'pt', 'number', 'number')
        reader.fields(shape, (('Locked', 'boolean'), ('VectorFont', 'boolean'),
                              ('FontWidth', 'number'), ('FontScale', 'number')))
        shape.add('MarkingGenerated', False)
        shape.source = SourceSpan(reader.source_format, start, reader.pos, reader.source)
        shape.annotations['incomplete'] = 'later drawing properties remain'
    return shapes


def read_symbol_extensions(reader, part, *, placed=False, angle_reader=read_angle):
    for pin in part.one('Pins').children('Pin'):
        reader.field(pin, 'Group', 'integer')
    for shape in part.one('Shapes').children('Shape'):
        read_text_properties(reader, shape, angle_reader=angle_reader)
        reader.field(shape, 'Group', 'integer')
        if placed:
            reader.fields(shape, (('ShowPart', 'boolean'), ('MarkingGenerated', 'boolean')), replace=True)
    if not placed:
        read_groups(reader, part, 'Groups')
