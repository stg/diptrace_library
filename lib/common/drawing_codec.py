"""Shared drawing-record extensions; adapters choose angle and version policy."""
from .model import SourceSpan
from .drawing_records import POINT


def read_angle(reader, owner, name):
    return reader.field(owner, name, 'number', replace=True)


def read_text_lines(reader, shape):
    start = reader.pos
    lines = shape.child('TextLine')
    if lines is None:
        lines = reader.add(shape, 'TextLine')
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
        if point.schema is POINT and reader.compact_fields and not reader.retain_source:
            # This later wire array is authoritative. A constructed point has
            # named slots already; decode into them just like other fields.
            x, y = reader.number(), reader.number()
            fields = reader._field_storage(point)
            fields.import_value('X', x, replace=True)
            fields.import_value('Y', y, replace=True)
        else:
            point.set_values(reader.argument('number'), reader.argument('number'))
        point.source = SourceSpan(reader.source_format, start, reader.pos, reader.source)


def read_text_properties(reader, shape, *, angle_reader=read_angle):
    angle_reader(reader, shape, 'TextAngle')
    reader.fields(shape, ((name, 'integer') for name in ('TextHorz', 'TextVert', 'TextAlign')))
    reader.field_into(shape, 'LineSpacing', 'number')
    read_text_lines(reader, shape)


def read_groups(reader, owner, name):
    groups = reader.add(owner, name)
    for _ in range(reader.count('drawing groups')):
        reader.record(groups, 'pt', 'boolean', 'integer', 'number', 'number')
    return groups


def write_text_properties(writer, shape):
    """Write the full angle, alignment, spacing and ordered text lines."""
    writer.field(shape, 'TextAngle', 'number')
    writer.fields(shape, 'integer', 'TextHorz TextVert TextAlign')
    writer.field(shape, 'LineSpacing', 'number')
    writer.rows(shape.one('TextLine'), 'pt', 'text')
