"""Board drawings, supplied pour fill, dimensions and group binary sections."""
from ....common.conversion import info, warn
from ....common.dimension_codec import write_dimension_properties
from ....common.drawing_codec import write_text_properties
from ....common.picture_sources import picture_source_paths
from ....common.units import square_root_area
from ...model import graphic_records as model
from ..errors import PcbError
from ..output_indices import non_signal_number
from ..output_validation import check_tree, field_value


def _members(board, collection, kind):
    source = board.child(collection)
    if source is not None:
        check_tree(source, model.COLLECTIONS[collection], destination='DIP')
    return board.select(collection+'/'+kind)


def write_base_drawings(writer, board):
    drawings = _members(board, 'Shapes', 'Shape')
    writer.integer(len(drawings))
    for shape in drawings:
        if model.layer_scope(shape) is not None and shape['LayerTarget'] is None:
            raise PcbError(f'{shape.path}: select a drawing layer before export')
        writer.fields(shape, 'boolean', 'Enabled Selected')
        writer.integer(writer.quarter_turns(field_value(shape, 'TextAngle')))
        writer.field(shape, 'AllLayers', 'boolean')
        writer.fields(shape, 'integer', 'Layer LayId Type FontSize')
        writer.integer(-1)  # Current picture sources are written in later sections.
        writer.field(shape, 'Group', 'integer')
        writer.fields(shape, 'color', 'Color BrushColor FontColor')
        writer.field(shape, 'PenWidth', 'number')
        writer.rows(shape.child('Points'), 'pt', 'number number')
        lines = shape.select('TextLine/pt')
        writer.text(lines[0]['Text'] if lines else '')
        writer.field(shape, 'FontName', 'text')
        writer.field(shape, 'Locked', 'boolean')
        writer.field(shape, 'NetNumber', 'integer')
        writer.field(shape, 'VectorFont', 'boolean')
        writer.fields(shape, 'number', 'FontWidth FontScale')
        writer.field(shape, 'Id', 'integer')
        writer.field(shape, 'PanelExclude', 'boolean')


def write_groups(writer, board):
    groups = _members(board, 'Groups', 'Group')
    writer.integer(len(groups))
    for group in groups:
        writer.fields(group, 'boolean', 'Enabled Selected')
        writer.boolean(False)
        writer.field(group, 'Id', 'integer')
        writer.fields(group, 'number', 'X Y')


def _fill_lines(writer, fill, name, *, width=False):
    rows = fill.select(name+'/Line') if fill is not None else ()
    writer.integer(len(rows))
    for row in rows:
        writer.fields(row, 'number', 'X1 Y1 X2 Y2'+(' Width' if width else ''))
        writer.field(row, 'RegionId', 'integer')


def write_base_pours(writer, board):
    pours = _members(board, 'CopperPours', 'CopperPour')
    writer.integer(len(pours))
    for pour in pours:
        if pour['Layer'] is None:
            raise PcbError(f'{pour.path}: select a copper layer before export')
        fill = pour.child('Fill')
        writer.fields(pour, 'boolean', 'Enabled Selected')
        writer.boolean(field_value(pour, 'Poured') and fill is not None)
        if fill is None:
            info(writer.report, 'pour-fill-unavailable', 'dip',
                 'Unavailable pour fill is written as unfilled with empty calculated lists', (pour,),
                 recoverability='boundary and settings remain; fill can be calculated by a geometric editor')
        writer.fields(pour, 'number', 'LineWidth Clearance')
        try:
            writer.number(square_root_area(field_value(pour, 'MinimumArea')))
        except (TypeError, ValueError) as error:
            raise PcbError(f'{pour.path}: {error}') from error
        writer.fields(pour, 'integer', 'Group Lay NetId')
        writer.rows(pour.child('Points'), 'pt', 'number number')
        _fill_lines(writer, fill, 'Lines')
        polygons = fill.select('Polygons/Poly') if fill is not None else ()
        writer.integer(len(polygons))
        for polygon in polygons:
            writer.rows(polygon.child('Points'), 'pt', 'number number')
            writer.field(polygon, 'RegionId', 'integer')
        writer.fields(pour, 'integer', 'Type Spoke')
        writer.fields(pour, 'number', 'LineSpacing SpokeWidth')
        _fill_lines(writer, fill, 'SpokeLine', width=True)
        writer.field(pour, 'UseNetClearance', 'boolean')
        writer.boolean(False)
        writer.fields(pour, 'boolean', 'Locked SnapToBoard')
        writer.field(pour, 'BoardClearance', 'number')
        writer.fields(pour, 'boolean', 'IslandRegion IslandInternal IslandConnection')
        writer.field(pour, 'Id', 'integer')
        writer.fields(pour, 'boolean', 'ViaDirect SMD_Separate')
        writer.field(pour, 'SMD_Spoke', 'integer')
        writer.field(pour, 'SMD_SpokeWidth', 'number')
        writer.field(pour, 'PanelExclude', 'boolean')
        from ..pour_classification import available
        writer.boolean(available(fill, destination='dip', report=writer.report))
        writer.field(pour, 'Priority', 'integer')


def write_board_dimensions(writer, board):
    dimensions = _members(board, 'Dimensions', 'Dimension')
    writer.integer(len(dimensions))
    for dimension in dimensions:
        if dimension.child('UnresolvedKeys') is not None:
            raise PcbError(f'{dimension.path}: unresolved dimension extensions need a DIP mapping')
        writer.fields(dimension, 'boolean', 'Enabled Selected Locked')
        write_dimension_properties(writer, dimension)
        writer.field(dimension, 'Group', 'integer')
        writer.field(dimension, 'PanelExclude', 'boolean')
        writer.integer(non_signal_number(dimension, destination='dip', report=writer.report))


def write_board_drawing_extensions(writer, board):
    """Current text/picture geometry; table/title spacing follows separately."""
    for shape in _members(board, 'Shapes', 'Shape'):
        write_text_properties(writer, shape)
        writer.field(shape, 'Inverted', 'boolean')
        writer.fields(shape, 'number', 'PictureWidth PictureHeight')
        writer.field(shape, 'PictureProportions', 'boolean')
        vector = shape.child('PictureVector')
        if vector is None:
            writer.number(0)
            writer.number(0)
            writer.integer(0)
            continue
        writer.fields(vector, 'number', 'Width Height')
        polygons = vector.select('Polygons/Polygon')
        writer.integer(len(polygons))
        for polygon in polygons:
            points = polygon.select('Points/Item')
            writer.integer(len(points))
            for point in points:
                writer.fields(point, 'number', 'X Y')


def write_picture_sources(writer, board, *, legacy_picture_files=None):
    """Project explicit paths only; no image or companion file is opened."""
    for shape in _members(board, 'Shapes', 'Shape'):
        filename, _, index = picture_source_paths(shape, filenames=legacy_picture_files)
        if index >= 0:
            warn(writer.report, 'unresolved-picture-reference', 'dip',
                 'Current DIP pictures require a filename; an unresolved companion reference becomes unassigned',
                 (shape,), recoverability='supply Picture_File or an explicit legacy_picture_files table')
        writer.field(shape, 'PictureRaster', 'boolean')
        writer.text(filename)
        writer.integer(-1)
        writer.field(shape, 'PictureTransparent', 'number')


def board_font_records(board):
    for path in ('Shapes/Shape', 'Dimensions/Dimension'):
        for node in board.select(path):
            yield node, 'FontSize', 'FontMono'
