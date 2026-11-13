"""Full-precision footprint, marking and drawing records introduced in schema 47."""
from ....common.drawing_codec import read_text_properties, replace_point_coordinates
from ....common.footprint_codec import (read_terminals, read_mask_segments,
    read_model_extensions, read_pattern_extensions)
from ....common.symbol_codec import read_symbol_extensions
from .preamble import _fields
from ...model.markings import NAMES as _MARKINGS, SIDES as _SIDES


def _marking(reader, owner, prefix):
    _fields(reader, owner, 'integer', ' '.join(prefix+name for name in ('Show', 'Align', 'Horz', 'Vert')))
    _fields(reader, owner, 'number', ' '.join(prefix+name for name in ('X', 'Y', 'Angle')))


def _global_markings(reader, board):
    for name in _MARKINGS:
        for side in _SIDES:
            _fields(reader, board, 'integer', f'{name}_Global_{side}Show {name}_Global_{side}Align')
    fields = reader.add(board, 'Userfields_Global')
    for index in range(reader.count('global component fields')):
        field = reader.add(fields, 'UserField', index)
        _fields(reader, field, 'text', 'Name Value')
        _fields(reader, field, 'integer', 'SilkShow SilkAlign AssyShow AssyAlign')


def _internal_connections(reader, component):
    records = reader.add(component, 'InternalConnection_Records')
    for _ in range(reader.count('internal connection records')):
        reader.record(records, 'pt', 'integer', 'integer')
    connections = reader.add(component, 'InternalConnections')
    for index in range(reader.count('internal connections')):
        connection = reader.add(connections, 'IntCon', index)
        reader.field_into(connection, 'ConnectAll', 'boolean')
        pads = reader.add(connection, 'PadId')
        for _ in range(reader.count('internal connection pads')):
            reader.record(pads, 'Item', 'integer')
        lines = reader.add(connection, 'Ratlines')
        for line_index in range(reader.count('internal ratlines')):
            line = reader.add(lines, 'Ratline', line_index)
            _fields(reader, line, 'integer', 'X Y')


def _placed_pattern(reader, component):
    pattern = component.one('Pattern')
    for name in ('Width', 'Height'):
        reader.field_into(pattern, name, 'number', replace=True)
    reader.field_into(component, 'Angle', 'number', replace=True)
    _fields(reader, pattern, 'boolean', 'OriginCross OriginCircle')
    reader.field_into(pattern, 'OriginCommon', 'integer', replace=True)
    reader.field_into(pattern, 'OriginCourtyard', 'integer')
    reader.field_into(component, 'ShowFiducial', 'integer')
    _fields(reader, pattern, 'text', 'Name_Description Name_Unique RecoveryCode')
    _fields(reader, pattern, 'boolean', 'RecoveryCode_Generator RecoveryCode_Model')
    reader.field_into(component, 'CustomMarkingFont', 'boolean')
    reader.field_into(component, 'MarkingFontSize', 'integer')
    reader.field_into(component, 'MarkingFontAll', 'boolean')
    for name in _MARKINGS:
        for side in _SIDES:
            _marking(reader, component, name+'_'+side)
    for field in component.one('UserFields').children('UserField'):
        for side in _SIDES:
            _marking(reader, field, side)
    _fields(reader, pattern, 'number', 'PadCorner PadShape_X PadShape_Y')
    read_terminals(reader, pattern)
    _fields(reader, pattern, 'integer', 'TopMask_State BotMask_State TopPaste_State BotPaste_State')
    _fields(reader, pattern, 'number', 'CustomSwell_New CustomShrink_New PadMask_Percent '
            'PadMask_EdgeGap PadMask_SegmentGap PadMask_SegmentSide')
    read_mask_segments(reader, pattern)
    for pad in pattern.one('Pads').children('Pad'):
        _fields(reader, pad, 'integer', 'Group InternalConnection')
        reader.field_into(pad, 'PadCorner', 'number')
        reader.field_into(pad, 'PadAngle', 'number', replace=True)
        _fields(reader, pad, 'number', 'PadShape_X PadShape_Y')
        read_terminals(reader, pad)
        _fields(reader, pad, 'number', 'PadMask_Percent PadMask_EdgeGap PadMask_SegmentGap PadMask_SegmentSide')
        read_mask_segments(reader, pad)
    for shape in pattern.one('Shapes').children('Shape'):
        replace_point_coordinates(reader, shape)
        read_text_properties(reader, shape)
        reader.field_into(shape, 'AllLayers', 'boolean')
        reader.field_into(shape, 'Group', 'integer')
        reader.field_into(shape, 'MarkingGenerated', 'boolean')
    for hole in pattern.one('Holes').children('Hole'):
        hole.set_values(*hole.arguments, reader.argument('integer'))
    for dimension in pattern.one('Dimensions').children('Dimension'):
        reader.field_into(dimension, 'Group', 'integer')
    read_model_extensions(reader, pattern)
    _internal_connections(reader, component)


def _board_drawings(reader, board):
    for shape in board.select('Shapes/Shape'):
        read_text_properties(reader, shape)
        reader.field_into(shape, 'Inverted', 'boolean')
        _fields(reader, shape, 'number', 'PictureWidth PictureHeight')
        reader.field_into(shape, 'PictureProportions', 'boolean')
        picture = reader.add(shape, 'PictureVector')
        _fields(reader, picture, 'number', 'Width Height')
        polygons = reader.add(picture, 'Polygons')
        for index in range(reader.count('vector picture polygons')):
            points = reader.add(reader.add(polygons, 'Polygon', index), 'Points')
            for point_index in range(reader.count('vector picture points')):
                point = reader.add(points, 'Item', point_index)
                _fields(reader, point, 'number', 'X Y')
    for table in board.select('Tables/Table'):
        reader.field_into(table, 'DefLineSpacing', 'number')
        for cell in table.select('Cells/Cell'):
            reader.field_into(cell, 'LineSpacing', 'number')
    for title in board.select('SheetSettings/TitleBlocks/TitleBlock'):
        for cell in title.select('Contents/Content'):
            reader.field_into(cell, 'LineSpacing', 'number')


def _display_extensions(reader, board):
    settings = board.one('Settings')
    panel = reader.add(settings, 'LayerPanel')
    _fields(reader, panel, 'boolean', 'TopAssy TopMask TopPaste BotAssy BotMask BotPaste Board '
            'TopTerminals BotTerminals TopCourtyard BotCourtyard TopOutline BotOutline '
            'TopDimensions BotDimensions')
    custom = reader.add(panel, 'NonSignals')
    for index in range(reader.count('non-signal display choices')):
        item = reader.record(custom, 'Item', 'boolean')
        item.set_values(index, *item.arguments)
    for name in ('DRC', 'LastDRC'):
        drc = board.one(name)
        reader.field_into(drc, 'CheckCourtyard', 'boolean')
        reader.field_into(drc, 'SilkClearance', 'number')
    reader.field_into(settings, 'ShowCompFiducials', 'boolean')


def read_drawing_extensions(reader, board, cached_definitions):
    if reader.header.version <= 46:
        return
    _global_markings(reader, board)
    for component in board.select('Components/Component'):
        _placed_pattern(reader, component)
    _board_drawings(reader, board)
    for cached in cached_definitions:
        read_pattern_extensions(reader, cached.definition.one('Pattern'))
        read_symbol_extensions(reader, cached.definition.one('Part'))
    _display_extensions(reader, board)


def read_pin_rotations(reader, cached_definitions):
    if reader.header.version <= 47:
        return
    for cached in cached_definitions:
        for pin in cached.definition.select('Part/Pins/Pin'):
            _fields(reader, pin, 'integer', 'PinNameRotate PinNumRotate')
