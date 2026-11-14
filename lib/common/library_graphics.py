"""Library-footprint drawing, drill and measurement arrays.

Each family selects its own revision policy; schema numbers are not shared.
"""
import math

from .dimension_codec import read_dimension_properties
from .drawing_codec import read_text_properties
from .footprint_codec import read_holes
from .footprint_geometry import expand_normalized_drawing


def _fields(reader, owner, kind, names):
    reader.fields(owner, ((name, kind) for name in names.split()))


def read_library_graphics(reader, pattern, *, physical_coordinates,
                          drawing_pad_links=False, extended_fonts=False):
    shapes = reader.add(pattern, 'Shapes')
    for index in range(reader.count('pattern drawings')):
        shape = reader.add(shapes, 'Shape', index)
        reader.field_into(shape, 'Type', 'integer')
        controls = () if physical_coordinates else tuple(reader.number() for _ in range(6))
        reader.field_into(shape, 'Locked', 'boolean')
        reader.field_into(shape, 'Layer', 'integer')
        if not physical_coordinates:
            reader.add_into(reader.add(shape, 'TextLine'), 'pt', reader.argument('text'))
        reader.field_into(shape, 'FontName', 'text')
        reader.field_into(shape, 'VectorFont', 'boolean')
        reader.field_into(shape, 'FontSize', 'integer')
        _fields(reader, shape, 'number', 'FontScale FontWidth')
        orientation = 0 if physical_coordinates else reader.integer()
        reader.field_into(shape, 'TextShow', 'integer')
        reader.field_into(shape, 'Width', 'number')
        points = reader.add(shape, 'Points_New')
        reader.points(points, reader.count('pattern drawing points'))
        if physical_coordinates:
            read_text_properties(reader, shape)
            reader.field_into(shape, 'AllLayers', 'boolean')
            reader.field_into(shape, 'Group', 'integer')
        else:
            _expand_drawing(reader, pattern, shape, controls, orientation)
        if drawing_pad_links:
            selected = reader.integer()
            reader.add_into(shape, 'PadId', selected if selected else -1)
        else:
            reader.add_into(shape, 'PadId', -1)
        _font_extension(reader, shape, extended_fonts)
    holes = read_holes(reader, pattern, grouped=physical_coordinates)
    if not physical_coordinates:
        for hole in holes.children('Hole'):
            hole.set_values(*hole.arguments, -1)
    _read_dimensions(reader, pattern, physical_coordinates, extended_fonts)
    return shapes


def _read_dimensions(reader, pattern, physical_coordinates, extended_fonts):
    dimensions = reader.add(pattern, 'Dimensions')
    for index in range(reader.count('pattern dimensions')):
        dimension = reader.add(dimensions, 'Dimension', index)
        _fields(reader, dimension, 'boolean', 'Enabled Locked')
        read_dimension_properties(reader, dimension)
        if physical_coordinates:
            reader.field_into(dimension, 'Group', 'integer')
        else:
            reader.add_into(dimension, 'Group', -1)
        _font_extension(reader, dimension, extended_fonts)


def _font_extension(reader, owner, extended_fonts):
    if extended_fonts:
        reader.field_into(owner, 'FontMono', 'boolean')
        reader.field_into(owner, 'FontSize', 'number', replace=True)
    else:
        reader.add_into(owner, 'FontMono', False)


def _expand_drawing(reader, pattern, shape, controls, orientation):
    """Consume older normalized controls into the current physical geometry."""
    kind = shape['Type']
    outline = shape.one('Points_New')
    current_kind, points = expand_normalized_drawing(kind,
        tuple(zip(controls[::2], controls[1::2])),
        [point.values for point in outline.children('pt')],
        (pattern['Width'], pattern['Height']), text_orientation=orientation)
    if current_kind in (2, 3, 4, 5) and len(points) == 2:
        first, last = points
        points = ((min(first[0], last[0]), min(first[1], last[1])),
                  (max(first[0], last[0]), max(first[1], last[1])))
    shape.one('Type').set_values(current_kind)
    for point in tuple(outline.children()):
        point.detach()
    for point in points:
        reader.add_into(outline, 'pt', *point)
    for name, value in dict(TextAngle=orientation*math.pi/2 if kind == 7 else 0,
            TextHorz=-1 if kind == 7 else 0, TextVert=-1 if kind == 7 else 0,
            TextAlign=-1, LineSpacing=1.2, AllLayers=False, Group=-1).items():
        reader.add_into(shape, name, value)
