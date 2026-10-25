"""Shared drawing-record extensions; adapters choose angle and version policy."""
from .model import SourceSpan


def read_angle(reader, owner, name):
    return reader.field(owner, name, 'number', replace=True)


def read_text_lines(reader, shape):
    start = reader.pos
    lines = shape.child('TextLine')
    if lines is None:
        lines = shape.add('TextLine')
    else:
        for child in tuple(lines.children()):
            child.detach()
    for _ in range(reader.count('shape text lines')):
        reader.record(lines, 'pt', 'text')
    lines.source = SourceSpan(reader.source_format, start, reader.pos, reader.source)


def replace_point_coordinates(reader, shape):
    """Replace a compatibility array without reading a second point count."""
    for point in shape.one('Points_New').children('pt'):
        start = reader.pos
        point.set_values(reader.argument('number'), reader.argument('number'))
        point.source = SourceSpan(reader.source_format, start, reader.pos, reader.source)


def read_text_properties(reader, shape, *, angle_reader=read_angle):
    angle_reader(reader, shape, 'TextAngle')
    reader.fields(shape, ((name, 'integer') for name in ('TextHorz', 'TextVert', 'TextAlign')))
    reader.field(shape, 'LineSpacing', 'number')
    read_text_lines(reader, shape)


def read_groups(reader, owner, name):
    groups = owner.add(name)
    for _ in range(reader.count('drawing groups')):
        reader.record(groups, 'pt', 'boolean', 'integer', 'number', 'number')
    return groups
