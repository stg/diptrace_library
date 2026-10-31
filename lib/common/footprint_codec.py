"""Shared footprint record layouts; callers own version and family policy.

These helpers populate named data. Later revision records can replace initial
values before import normalization establishes the authoring model.
"""
from .model import Value
from .drawing_codec import read_angle, read_groups, read_text_properties, replace_point_coordinates


def read_parameters(reader, pattern):
    reader.field(pattern, 'Type', 'integer')
    reader.fields(pattern, ((f'VariableParameter{index}', 'boolean') for index in range(1, 5)))
    reader.fields(pattern, ((name, 'integer') for name in ('Number1', 'Number2')))
    reader.fields(pattern, ((name, 'number') for name in ('Spacing1', 'Spacing2')))
    reader.field(pattern, 'VariableParameter5', 'boolean')
    reader.field(pattern, 'Spacing3', 'number')
    reader.field(pattern, 'LockProperties', 'boolean')
    reader.field(pattern, 'PatternOrientation', 'integer')
    reader.fields(pattern, ((name, 'number') for name in ('Width', 'Height', 'PadWidth', 'PadHeight')))
    reader.field(pattern, 'PadShape', 'integer')
    reader.field(pattern, 'SurfacePad', 'boolean')
    reader.fields(pattern, ((name, 'number') for name in ('PadHole', 'PadHoleH')))
    reader.field(pattern, 'PadHoleType', 'integer')
    pattern.set_values(reader.argument('text'))
    reader.fields(pattern, ((name, 'number') for name in ('OriginX', 'OriginY')))
    return pattern


def read_pad_geometry(reader, pad):
    reader.fields(pad, ((name, 'number') for name in ('PadWidth_New', 'PadHeight_New', 'PadHole', 'PadHoleH')))
    reader.field(pad, 'PadHoleType', 'integer')
    reader.field(pad, 'SurfacePad', 'boolean')
    reader.field(pad, 'PadShape_New', 'integer')
    reader.field(pad, 'Standard', 'boolean')
    count = reader.count('pad contour points')
    if count:
        points = pad.add('PadPoints_New')
        for _ in range(count):
            reader.record(points, 'pt', 'number', 'number')
    return pad


def read_pad_mask_states(reader, pad, *, extended=False):
    for name in ('DisableTopMask', 'DisableBottomMask', 'DisableTopPaste', 'DisableBottomPaste'):
        if extended:
            reader.field(pad, name, 'integer', replace=True)
        else:
            disabled = reader.argument('boolean')
            pad.add(name, Value(2 if disabled.value else 0, 'number', source=disabled.source))
    return pad


def read_holes(reader, pattern):
    holes = pattern.add('Holes')
    for _ in range(reader.count('footprint holes')):
        hole = reader.record(holes, 'Hole', 'boolean', *('number',)*4, 'boolean')
        values = hole.arguments
        # Named tuple order groups the two flags before the geometric values.
        hole.set_values(values[0], values[-1], *values[1:-1])
    return holes


def read_model(reader, pattern):
    model = pattern.add('Model3D')
    reader.field(model, 'Model3DFile', 'text')
    for name in ('Offset', 'Rotate', 'Zoom'):
        vector = model.add(name)
        reader.fields(vector, ((axis, 'number') for axis in ('X', 'Y', 'Z')))
    reader.fields(model, (('Mirror', 'boolean'), ('NoSearch', 'boolean')))
    return model


def read_terminals(reader, owner, *, angle_reader=read_angle):
    for index in range(reader.count('pad terminals')):
        terminal = owner.add('PadTerminal', index)
        reader.field(terminal, 'Type', 'integer')
        reader.fields(terminal, ((axis, 'number') for axis in ('X', 'Y')))
        angle_reader(reader, terminal, 'Angle')
        reader.fields(terminal, ((name, 'number') for name in ('ShapeWidth', 'ShapeHeight', 'ShapeCorner')))
        points = terminal.add('ShapePoints')
        for _ in range(reader.count('terminal polygon points')):
            reader.record(points, 'pt', 'number', 'number')


def read_mask_segments(reader, owner):
    for name in ('PadMask_TopSegments', 'PadMask_BotSegments'):
        count = reader.count('pad mask segments')
        segments = owner.add(name, count)
        for _ in range(count):
            reader.record(segments, 'pt', *('number',)*4)


def read_model_extensions(reader, pattern):
    model = pattern.one('Model3D')
    for name, kind in (('IPC_XOff', 'number'), ('IPC_YOff', 'number'),
                       ('AutoHeight', 'number'), ('AutoColor', 'color'), ('Type', 'integer')):
        reader.field(model, name, kind)


def read_pattern_extensions(reader, pattern, *, angle_reader=read_angle):
    """Read the shared definition extension, without placement-specific fields."""
    reader.fields(pattern, ((name, 'boolean') for name in ('OriginCross', 'OriginCircle')))
    reader.fields(pattern, ((name, 'integer') for name in ('OriginCommon', 'OriginCourtyard')))
    reader.fields(pattern, ((name, 'text') for name in ('Name_Description', 'Name_Unique', 'RecoveryCode')))
    reader.fields(pattern, ((name, 'boolean') for name in ('RecoveryCode_Generator', 'RecoveryCode_Model')))
    reader.field(pattern, 'Pattern_Manufacturer', 'text')
    reader.fields(pattern, ((name, 'number') for name in ('PadCorner', 'PadShape_X', 'PadShape_Y')))
    read_terminals(reader, pattern, angle_reader=angle_reader)
    reader.fields(pattern, ((name, 'integer') for name in ('TopMask_State', 'BotMask_State', 'TopPaste_State', 'BotPaste_State')))
    reader.fields(pattern, ((name, 'number') for name in ('CustomSwell_New', 'CustomShrink_New',
        'PadMask_Percent', 'PadMask_EdgeGap', 'PadMask_SegmentGap', 'PadMask_SegmentSide')))
    read_mask_segments(reader, pattern)
    for pad in pattern.one('Pads').children('Pad'):
        reader.field(pad, 'Group', 'integer')
        reader.field(pad, 'PadCorner', 'number')
        angle_reader(reader, pad, 'PadAngle')
        reader.fields(pad, ((name, 'number') for name in ('PadShape_X', 'PadShape_Y')))
        read_terminals(reader, pad, angle_reader=angle_reader)
        reader.fields(pad, ((name, 'number') for name in ('PadMask_Percent', 'PadMask_EdgeGap',
            'PadMask_SegmentGap', 'PadMask_SegmentSide')))
        read_mask_segments(reader, pad)
    for shape in pattern.one('Shapes').children('Shape'):
        replace_point_coordinates(reader, shape)
        read_text_properties(reader, shape, angle_reader=angle_reader)
        reader.field(shape, 'AllLayers', 'boolean')
        reader.field(shape, 'Group', 'integer')
    for hole in pattern.one('Holes').children('Hole'):
        hole.set_values(*hole.arguments, reader.argument('integer'))
    for dimension in pattern.one('Dimensions').children('Dimension'):
        reader.field(dimension, 'Group', 'integer')
    read_groups(reader, pattern, 'Pattern_Groups')
    read_model_extensions(reader, pattern)


def write_parameters(writer, pattern):
    writer.field(pattern, 'Type', 'integer')
    writer.fields(pattern, 'boolean', 'VariableParameter1 VariableParameter2 VariableParameter3 VariableParameter4')
    writer.fields(pattern, 'integer', 'Number1 Number2')
    writer.fields(pattern, 'number', 'Spacing1 Spacing2')
    writer.field(pattern, 'VariableParameter5', 'boolean')
    writer.field(pattern, 'Spacing3', 'number')
    writer.field(pattern, 'LockProperties', 'boolean')
    writer.field(pattern, 'PatternOrientation', 'integer')
    writer.fields(pattern, 'number', 'Width Height PadWidth PadHeight')
    writer.field(pattern, 'PadShape', 'integer')
    writer.field(pattern, 'SurfacePad', 'boolean')
    writer.fields(pattern, 'number', 'PadHole PadHoleH')
    writer.field(pattern, 'PadHoleType', 'integer')
    writer.field(pattern, 'Name', 'text')
    writer.fields(pattern, 'number', 'OriginX OriginY')


def write_pad_geometry(writer, pad):
    writer.fields(pad, 'number', 'PadWidth_New PadHeight_New PadHole PadHoleH')
    writer.field(pad, 'PadHoleType', 'integer')
    writer.field(pad, 'SurfacePad', 'boolean')
    writer.field(pad, 'PadShape_New', 'integer')
    writer.field(pad, 'Standard', 'boolean')
    writer.rows(pad.child('PadPoints_New'), 'pt', 'number number')


def write_holes(writer, holes):
    """Write an explicit sequence, including any adapter-generated boundaries."""
    writer.integer(len(holes))
    for hole in holes:
        writer.field(hole, 'Enabled', 'boolean')
        writer.fields(hole, 'number', 'X Y Diam HoleDiam')
        writer.field(hole, 'Locked', 'boolean')


def write_model(writer, pattern):
    model = pattern.one('Model3D')
    writer.field(model, 'Model3DFile', 'text')
    for name in ('Offset', 'Rotate', 'Zoom'):
        writer.fields(model.one(name), 'number', 'X Y Z')
    writer.fields(model, 'boolean', 'Mirror NoSearch')


def write_terminals(writer, owner):
    terminals = owner.children('PadTerminal')
    writer.integer(len(terminals))
    for terminal in terminals:
        writer.field(terminal, 'Type', 'integer')
        writer.fields(terminal, 'number', 'X Y Angle ShapeWidth ShapeHeight ShapeCorner')
        writer.rows(terminal.child('ShapePoints'), 'pt', 'number number')


def write_mask_segments(writer, owner):
    for name in ('PadMask_TopSegments', 'PadMask_BotSegments'):
        writer.rows(owner.child(name), 'pt', 'number '*4)


def write_model_extensions(writer, pattern):
    model = pattern.one('Model3D')
    writer.fields(model, 'number', 'IPC_XOff IPC_YOff AutoHeight')
    writer.field(model, 'AutoColor', 'color')
    writer.field(model, 'Type', 'integer')


def write_pad_extensions(writer, pad):
    """Current pad geometry following the caller's group/connection selectors."""
    writer.fields(pad, 'number', 'PadCorner PadAngle PadShape_X PadShape_Y')
    write_terminals(writer, pad)
    writer.fields(pad, 'number', 'PadMask_Percent PadMask_EdgeGap PadMask_SegmentGap PadMask_SegmentSide')
    write_mask_segments(writer, pad)


def write_pattern_extensions(writer, pattern, *, pads=None, drawings=None, holes=None):
    """Unplaced layout, with optional explicit arrays for generated boundaries."""
    from .drawing_codec import write_text_properties
    writer.fields(pattern, 'boolean', 'OriginCross OriginCircle')
    writer.fields(pattern, 'integer', 'OriginCommon OriginCourtyard')
    writer.fields(pattern, 'text', 'Name_Description Name_Unique RecoveryCode')
    writer.fields(pattern, 'boolean', 'RecoveryCode_Generator RecoveryCode_Model')
    writer.field(pattern, 'Pattern_Manufacturer', 'text')
    writer.fields(pattern, 'number', 'PadCorner PadShape_X PadShape_Y')
    write_terminals(writer, pattern)
    writer.fields(pattern, 'integer', 'TopMask_State BotMask_State TopPaste_State BotPaste_State')
    writer.fields(pattern, 'number', 'CustomSwell_New CustomShrink_New PadMask_Percent '
                  'PadMask_EdgeGap PadMask_SegmentGap PadMask_SegmentSide')
    write_mask_segments(writer, pattern)
    for pad in pattern.select('Pads/Pad') if pads is None else pads:
        writer.field(pad, 'Group', 'integer')
        write_pad_extensions(writer, pad)
    for shape in pattern.select('Shapes/Shape') if drawings is None else drawings:
        for point in shape.select('Points_New/pt'):
            writer.values(point, 'number number')
        write_text_properties(writer, shape)
        writer.field(shape, 'AllLayers', 'boolean')
        writer.field(shape, 'Group', 'integer')
    for hole in pattern.select('Holes/Hole') if holes is None else holes:
        writer.field(hole, 'Group', 'integer')
    for dimension in pattern.select('Dimensions/Dimension'):
        writer.field(dimension, 'Group', 'integer')
    writer.rows(pattern.child('Pattern_Groups'), 'pt', 'boolean integer number number')
    write_model_extensions(writer, pattern)
