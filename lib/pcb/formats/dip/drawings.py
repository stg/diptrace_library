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
    drawings = board.add('Shapes')
    upgrades = []
    for index in range(reader.count('board shapes')):
        start = reader.pos
        drawing = drawings.add('Shape', index)
        _fields(reader, drawing, 'boolean', 'Enabled Selected')
        orientation = reader.integer()
        reader.field(drawing, 'AllLayers', 'boolean')
        # Layer is the layer family; LayId identifies a layer in that family.
        _fields(reader, drawing, 'integer', 'Layer LayId Type FontSize')
        bitmap_index = reader.integer()
        reader.field(drawing, 'Group', 'integer')
        _fields(reader, drawing, 'color', 'Color BrushColor FontColor')
        reader.field(drawing, 'PenWidth', 'number')
        points = drawing.add('Points_New' if reader.header.version >= 47 else 'Points')
        for _ in range(reader.count('board drawing points')):
            reader.record(points, 'pt', 'number', 'number')
        drawing.add('TextLine').add('pt', reader.argument('text'))
        reader.field(drawing, 'FontName', 'text')
        reader.field(drawing, 'Locked', 'boolean')
        reader.field(drawing, 'NetNumber', 'integer')
        reader.field(drawing, 'VectorFont', 'boolean')
        _fields(reader, drawing, 'number', 'FontWidth FontScale')
        previous_number = reader.integer()
        reader.field(drawing, 'PanelExclude', 'boolean')
        drawing.source = SourceSpan('dip', start, reader.pos, reader.source)
        upgrades.append(DrawingUpgrade(drawing, orientation, bitmap_index, previous_number))
    return tuple(upgrades)


def read_board_dimensions(reader, board):
    dimensions = board.add('Dimensions')
    for index in range(reader.count('board dimensions')):
        start = reader.pos
        dimension = dimensions.add('Dimension', index)
        _fields(reader, dimension, 'boolean', 'Enabled Selected Locked')
        read_dimension_properties(reader, dimension)
        reader.field(dimension, 'Group', 'integer')
        reader.field(dimension, 'PanelExclude', 'boolean')
        if reader.header.version > 32:
            reader.field(dimension, 'NonSignal', 'integer')
        else:
            dimension.add('NonSignal', 0)
        dimension.source = SourceSpan('dip', start, reader.pos, reader.source)
    return dimensions
