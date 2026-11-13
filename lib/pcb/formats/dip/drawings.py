"""Board drawings before later geometry, text and picture extensions."""
from dataclasses import dataclass

from ....common.model import Element, SourceSpan
from ....common.dimension_codec import read_dimension_properties
from .preamble import _fields


@dataclass(frozen=True)
class DrawingUpgrade:
    drawing: Element
    orientation: int
    bitmap_index: int
    previous_number: int


def read_base_drawings(reader, board):
    """Decode the initial board drawing section for subsequent modernization."""
    drawings = reader.add(board, 'Shapes')
    upgrades = []
    for index in range(reader.count('board shapes')):
        start = reader.pos
        drawing = reader.add(drawings, 'Shape', index)
        _fields(reader, drawing, 'boolean', 'Enabled Selected')
        orientation = reader.integer()
        reader.field_into(drawing, 'AllLayers', 'boolean')
        # Layer is the layer family; LayId identifies a layer in that family.
        _fields(reader, drawing, 'integer', 'Layer LayId Type FontSize')
        bitmap_index = reader.integer()
        reader.field_into(drawing, 'Group', 'integer')
        _fields(reader, drawing, 'color', 'Color BrushColor FontColor')
        reader.field_into(drawing, 'PenWidth', 'number')
        points = reader.add(drawing, 'Points_New' if reader.header.version >= 47 else 'Points')
        reader.points(points, reader.count('board drawing points'))
        reader.add_into(reader.add(drawing, 'TextLine'), 'pt', reader.argument('text'))
        reader.field_into(drawing, 'FontName', 'text')
        reader.field_into(drawing, 'Locked', 'boolean')
        reader.field_into(drawing, 'NetNumber', 'integer')
        reader.field_into(drawing, 'VectorFont', 'boolean')
        _fields(reader, drawing, 'number', 'FontWidth FontScale')
        previous_number = reader.integer()
        reader.field_into(drawing, 'PanelExclude', 'boolean')
        drawing.source = SourceSpan('dip', start, reader.pos, reader.source)
        upgrades.append(DrawingUpgrade(drawing, orientation, bitmap_index, previous_number))
    return tuple(upgrades)


def read_board_dimensions(reader, board):
    dimensions = reader.add(board, 'Dimensions')
    for index in range(reader.count('board dimensions')):
        start = reader.pos
        dimension = reader.add(dimensions, 'Dimension', index)
        _fields(reader, dimension, 'boolean', 'Enabled Selected Locked')
        read_dimension_properties(reader, dimension)
        reader.field_into(dimension, 'Group', 'integer')
        reader.field_into(dimension, 'PanelExclude', 'boolean')
        if reader.header.version > 32:
            reader.field_into(dimension, 'NonSignal', 'integer')
        else:
            reader.add_into(dimension, 'NonSignal', 0)
        dimension.source = SourceSpan('dip', start, reader.pos, reader.source)
    return dimensions
