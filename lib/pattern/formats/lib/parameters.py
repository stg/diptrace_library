"""Template settings and default-pad facts before the library's physical arrays."""
from ....common.footprint_codec import read_terminals, read_mask_segments


def _fields(reader, target, kind, names):
    reader.fields(target, ((name, kind) for name in names.split()))


def read_parameters(reader, pattern):
    """Consume the standalone template order, distinct from placed/cache records."""
    version = reader.header.version
    _fields(reader, pattern, 'boolean',
            'VariableParameter1 VariableParameter2 VariableParameter3 VariableParameter4')
    _fields(reader, pattern, 'number', 'Width Height Spacing1 Spacing2')
    reader.field_into(pattern, 'VariableParameter5', 'boolean')
    reader.field_into(pattern, 'Spacing3', 'number')
    reader.field_into(pattern, 'LockProperties', 'boolean')
    _fields(reader, pattern, 'integer', 'PatternOrientation Number1 Number2 Type')
    _fields(reader, pattern, 'number', 'PadWidth PadHeight')
    reader.field_into(pattern, 'PadShape', 'integer')
    reader.field_into(pattern, 'SurfacePad', 'boolean')
    _fields(reader, pattern, 'number', 'PadHole PadHoleH')
    reader.field_into(pattern, 'PadHoleType', 'integer')
    points = reader.add(pattern, 'PadPoints')
    reader.points(points, reader.count('default pad points'))
    if version >= 20:
        _fields(reader, pattern, 'number', 'PadCorner PadShape_X PadShape_Y')
        read_terminals(reader, pattern)
        _fields(reader, pattern, 'number',
                'PadMask_Percent PadMask_EdgeGap PadMask_SegmentGap PadMask_SegmentSide')
        read_mask_segments(reader, pattern)
    if version >= 21:
        _fields(reader, pattern, 'integer', 'TopMask_State BotMask_State TopPaste_State BotPaste_State')
        _fields(reader, pattern, 'number', 'CustomSwell_New CustomShrink_New')
    return pattern
