"""Symbol pins and drawings stored in shared library definitions."""
from .model import SourceSpan
from .drawing_codec import read_angle, read_groups, read_text_properties, write_text_properties


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


def write_cached_pins(writer, part):
    pins = part.select('Pins/Pin')
    writer.integer(len(pins))
    for pin in pins:
        writer.field(pin, 'Enabled', 'boolean')
        writer.fields(pin, 'integer', 'Type Orientation Number')
        writer.fields(pin, 'number', 'X Y Length')
        writer.fields(pin, 'text', 'Name StringNumber')
        writer.field(pin, 'ShowName', 'boolean')
        writer.fields(pin, 'number', 'PinNumXShift PinNumYShift PinNameXShift PinNameYShift')
        writer.field(pin, 'ElectricType', 'integer')
        writer.field(pin, 'Locked', 'boolean')
        writer.field(pin, 'ModelSig', 'text')
        for name, codec in PIN_FONT:
            writer.field(pin, name, codec)


def write_symbol_drawings(writer, part, *, orientation, placed=False):
    """Write physical symbol geometry; the family supplies its angle policy."""
    shapes = part.select('Shapes/Shape')
    writer.integer(len(shapes))
    for shape in shapes:
        writer.field(shape, 'Enabled', 'boolean')
        writer.integer(orientation(shape['TextAngle']))
        kind = shape['Type']
        writer.integer(700 if placed and kind == 10 and shape['MarkingGenerated'] else kind)
        writer.field(shape, 'FontSize', 'integer')
        writer.field(shape, 'FontColor', 'color')
        writer.field(shape, 'FontType', 'integer')
        writer.field(shape, 'FontName', 'text')
        lines = shape.select('TextLine/pt')
        writer.text(lines[0]['Text'] if lines else '')
        writer.field(shape, 'PenWidth', 'number')
        writer.rows(shape.child('Points_New'), 'pt', 'number number')
        writer.fields(shape, 'boolean', 'Locked VectorFont')
        writer.fields(shape, 'number', 'FontWidth FontScale')


def write_symbol_extensions(writer, part, *, placed=False):
    for pin in part.select('Pins/Pin'):
        writer.field(pin, 'Group', 'integer')
    for shape in part.select('Shapes/Shape'):
        write_text_properties(writer, shape)
        writer.field(shape, 'Group', 'integer')
        if placed:
            writer.fields(shape, 'boolean', 'ShowPart MarkingGenerated')
    if not placed:
        writer.rows(part.child('Groups'), 'pt', 'boolean integer number number')
